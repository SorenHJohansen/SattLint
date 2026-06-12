"""Syntax and parser helper implementations shared by engine.py."""

import contextlib
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, cast

from lark import Lark
from lark.exceptions import UnexpectedInput, VisitError

from sattline_parser import create_parser as parser_core_create_parser
from sattline_parser import parse_source_file as parser_core_parse_source_file
from sattline_parser import parse_source_text as parser_core_parse_source_text
from sattline_parser.api import describe_parse_error, read_text_with_fallback
from sattline_parser.grammar.parser_decode import is_compressed, preprocess_sl_text
from sattline_parser.models.ast_model import BasePicture
from sattline_parser.transformer.sl_transformer import SLTransformer

from ._engine_graphics_context_helpers import (
    graphics_source_context_path,
    load_picture_display_source_context,
    picture_display_path_warnings,
    resolve_graphics_companion_path,
)
from ._validation_shared import ValidationNotice, ValidationWarning, coerce_validation_notice
from .graphics_validation import GraphicsValidationResult, validate_graphics_file
from .models.project_graph import ProjectFailure, ProjectGraph
from .picture_display_paths import correlate_picture_display_records
from .utils.text_processing import find_disallowed_comments
from .validation import (
    LOCAL_STRUCTURE_VALIDATION_SCHEMA_VERSION,
    RawSourceValidationError,
    StructuralValidationError,
    validate_transformed_basepicture,
    validate_transformed_basepicture_locally,
)

_EXPECTED_UNAVAILABLE_LIBRARY_REASONS: dict[str, str] = {
    "controllib": "expected proprietary dependency",
}


def is_expected_unavailable_library(name: str) -> bool:
    return name.casefold() in _EXPECTED_UNAVAILABLE_LIBRARY_REASONS


def expected_unavailable_library_reason(name: str) -> str | None:
    return _EXPECTED_UNAVAILABLE_LIBRARY_REASONS.get(name.casefold())


@dataclass(frozen=True)
class SyntaxValidationResult:
    file_path: Path
    ok: bool
    stage: str
    message: str | None = None
    line: int | None = None
    column: int | None = None
    warnings: tuple[str, ...] = ()
    warning_notices: tuple[ValidationNotice, ...] = ()


class CodeMode(Enum):
    OFFICIAL = "official"
    DRAFT = "draft"


def code_ext(mode: CodeMode) -> str:
    return ".x" if mode is CodeMode.OFFICIAL else ".s"


def deps_ext(mode: CodeMode) -> str:
    return ".z" if mode is CodeMode.OFFICIAL else ".l"


def graphics_ext(mode: CodeMode) -> str:
    return ".y" if mode is CodeMode.OFFICIAL else ".g"


def graphics_ext_candidates(mode: CodeMode) -> tuple[str, ...]:
    return (".y",) if mode is CodeMode.OFFICIAL else (".g", ".y")


def normalize_code_mode(mode: CodeMode | str | None) -> CodeMode | None:
    if mode is None:
        return None
    if isinstance(mode, CodeMode):
        return mode
    raw_mode = str(mode).strip().lower()
    if not raw_mode:
        return None
    return CodeMode(raw_mode)


def resolve_dependency_context_path(code_path: Path, mode: CodeMode | str | None = None) -> Path | None:
    suffix = code_path.suffix.lower()
    if suffix not in {".s", ".x", ".g", ".y"}:
        return None
    resolved_mode = normalize_code_mode(mode)
    if resolved_mode is None:
        resolved_mode = CodeMode.OFFICIAL if suffix in {".x", ".y"} else CodeMode.DRAFT
    candidate = code_path.with_suffix(deps_ext(resolved_mode))
    if candidate == code_path or not candidate.exists():
        return None
    return candidate


def graphics_validation_to_syntax_result(
    file_path: Path,
    result: GraphicsValidationResult,
    *,
    warnings: Iterable[ValidationWarning] = (),
) -> SyntaxValidationResult:
    notice_warnings = [coerce_validation_notice(warning) for warning in warnings]
    notice_warnings.extend(ValidationNotice(message=message.message) for message in result.warnings)
    combined_warnings = [notice.message for notice in notice_warnings]
    if result.errors:
        first_error = result.errors[0]
        return SyntaxValidationResult(
            file_path=file_path,
            ok=False,
            stage="graphics",
            message=first_error.message,
            line=first_error.line,
            column=first_error.column,
            warnings=tuple(combined_warnings),
            warning_notices=tuple(notice_warnings),
        )

    return SyntaxValidationResult(
        file_path=file_path,
        ok=True,
        stage="ok",
        warnings=tuple(combined_warnings),
        warning_notices=tuple(notice_warnings),
    )


def record_project_failure(graph: ProjectGraph, name: str, exception: Exception) -> None:
    message = f"{name} parse/transform error: {exception}"
    line = getattr(exception, "line", None)
    column = getattr(exception, "column", None)
    length = getattr(exception, "length", None)
    if isinstance(exception, VisitError):
        line = line if line is not None else getattr(exception.orig_exc, "line", None)
        column = column if column is not None else getattr(exception.orig_exc, "column", None)
        length = length if length is not None else getattr(exception.orig_exc, "length", None)
    graph.missing.append(message)
    graph.failures[name.casefold()] = ProjectFailure(
        name=name,
        message=message,
        line=line,
        column=column,
        length=length,
    )


def record_project_warning(graph: ProjectGraph, name: str, message: ValidationWarning) -> None:
    notice = coerce_validation_notice(message)
    graph.warnings.append(f"{name}: {notice.message}")
    warning_notices = getattr(graph, "warning_notices", None)
    if isinstance(warning_notices, list):
        cast(list[tuple[str, ValidationNotice]], warning_notices).append((name, notice))


def format_debug_list(title: str, entries: Iterable[str]) -> str:
    items = [str(entry) for entry in entries]
    if not items:
        return f"{title}: none"

    lines = [f"{title} ({len(items)}):"]
    lines.extend(f"  - {item}" for item in items)
    return "\n".join(lines)


def format_debug_missing_entries(entries: Iterable[str]) -> str:
    items = [str(entry) for entry in entries]
    if not items:
        return "Missing/failed: none"

    lines = [f"Missing/failed ({len(items)}):"]
    for item in items:
        library_name, separator, detail = item.partition(" parse/transform error: ")
        if separator:
            lines.append(f"  - {library_name}")
            lines.append(f"    parse/transform error: {detail}")
            continue
        lines.append(f"  - {item}")
    return "\n".join(lines)


def is_within_directory(path: Path, directory: Path) -> bool:
    try:
        path.resolve().relative_to(directory.resolve())
        return True
    except ValueError:
        return False


def create_sl_parser() -> Lark:
    return parser_core_create_parser()


def load_source_text(
    code_path: Path,
    *,
    debug: Callable[[str], None] | None = None,
    read_text_with_fallback_fn: Callable[[Path], str] = read_text_with_fallback,
    is_compressed_fn: Callable[[str], bool] = is_compressed,
    preprocess_sl_text_fn: Callable[[str], tuple[str, object]] = preprocess_sl_text,
) -> str:
    source_path = Path(code_path)
    if debug is not None:
        debug(f"Parsing file: {source_path}")

    src = read_text_with_fallback_fn(source_path)
    if is_compressed_fn(src):
        if debug is not None:
            debug("Compressed format detected; decoding before parsing")
        src, _ = preprocess_sl_text_fn(src)
    return src


def parse_source_text(
    src: str,
    *,
    parser: Lark | None = None,
    transformer: SLTransformer | None = None,
    debug: Callable[[str], None] | None = None,
    parser_core_parse_source_text_fn: Callable[..., BasePicture] = parser_core_parse_source_text,
    validate_transformed_basepicture_fn: Callable[[BasePicture], None] = validate_transformed_basepicture,
) -> BasePicture:
    basepic = parser_core_parse_source_text_fn(
        src,
        parser=parser,
        transformer=transformer,
        debug=debug,
    )
    validate_transformed_basepicture_fn(basepic)
    return basepic


def parse_source_file(
    code_path: Path,
    *,
    parser: Lark | None = None,
    transformer: SLTransformer | None = None,
    debug: Callable[[str], None] | None = None,
    parser_core_parse_source_file_fn: Callable[..., BasePicture] = parser_core_parse_source_file,
    validate_transformed_basepicture_fn: Callable[[BasePicture], None] = validate_transformed_basepicture,
) -> BasePicture:
    basepic = parser_core_parse_source_file_fn(
        code_path,
        parser=parser,
        transformer=transformer,
        debug=debug,
    )
    validate_transformed_basepicture_fn(basepic)
    return basepic


_LOCAL_VALIDATION_MARKER_ATTR = "_sattlint_local_validation_schema"
LOCAL_VALIDATION_MARKER_ATTR = _LOCAL_VALIDATION_MARKER_ATTR


def has_current_local_validation(basepic: BasePicture) -> bool:
    return getattr(basepic, _LOCAL_VALIDATION_MARKER_ATTR, None) == LOCAL_STRUCTURE_VALIDATION_SCHEMA_VERSION


def mark_local_validation(basepic: BasePicture) -> BasePicture:
    setattr(basepic, _LOCAL_VALIDATION_MARKER_ATTR, LOCAL_STRUCTURE_VALIDATION_SCHEMA_VERSION)
    return basepic


def ensure_local_validation(
    basepic: BasePicture,
    *,
    warning_sink: list[ValidationWarning] | None = None,
    has_current_local_validation_fn: Callable[[BasePicture], bool] = has_current_local_validation,
    mark_local_validation_fn: Callable[[BasePicture], BasePicture] = mark_local_validation,
    validate_transformed_basepicture_locally_fn: Callable[..., None] = validate_transformed_basepicture_locally,
) -> bool:
    if has_current_local_validation_fn(basepic):
        return False
    validate_transformed_basepicture_locally_fn(
        basepic,
        allow_unresolved_external_datatypes=True,
        enforce_unique_submodule_names=False,
        allow_parameterless_module_mappings=True,
        warning_sink=None if warning_sink is None else warning_sink.append,
    )
    mark_local_validation_fn(basepic)
    return True


def extract_error_position(exc: Exception) -> tuple[int | None, int | None]:
    line = getattr(exc, "line", None)
    column = getattr(exc, "column", None)
    if isinstance(exc, VisitError):
        line = line if line is not None else getattr(exc.orig_exc, "line", None)
        column = column if column is not None else getattr(exc.orig_exc, "column", None)
    return line, column


def validate_single_file_syntax(
    code_path: Path,
    *,
    mode: CodeMode | str | None = None,
    load_source_text_fn: Callable[..., str] = load_source_text,
    find_disallowed_comments_fn: Callable[[str], list[Any]] = find_disallowed_comments,
    parser_core_parse_source_text_fn: Callable[..., BasePicture] = parser_core_parse_source_text,
    validate_transformed_basepicture_fn: Callable[..., None] = validate_transformed_basepicture,
    describe_parse_error_fn: Callable[[UnexpectedInput, str], Any] = describe_parse_error,
    validate_graphics_file_fn: Callable[[Path], GraphicsValidationResult] = validate_graphics_file,
    graphics_source_context_path_fn: Callable[[Path], Path | None] = graphics_source_context_path,
    load_picture_display_source_context_fn: Callable[[Path], BasePicture | None] = load_picture_display_source_context,
    correlate_picture_display_records_fn: Callable[..., Any] = correlate_picture_display_records,
    picture_display_path_warnings_fn: Callable[..., tuple[ValidationNotice, ...]] = picture_display_path_warnings,
    resolve_graphics_companion_path_fn: Callable[..., Path | None] = resolve_graphics_companion_path,
    resolve_dependency_context_path_fn: Callable[
        [Path, CodeMode | str | None], Path | None
    ] = resolve_dependency_context_path,
    extract_error_position_fn: Callable[[Exception], tuple[int | None, int | None]] = extract_error_position,
    graphics_validation_to_syntax_result_fn: Callable[
        ..., SyntaxValidationResult
    ] = graphics_validation_to_syntax_result,
    coerce_validation_notice_fn: Callable[[ValidationWarning], ValidationNotice] = coerce_validation_notice,
    raw_source_validation_error_cls: type[RawSourceValidationError] = RawSourceValidationError,
    structural_validation_error_cls: type[StructuralValidationError] = StructuralValidationError,
) -> SyntaxValidationResult:
    target_path = Path(code_path)
    if target_path.suffix.lower() in {".g", ".y"}:
        result = validate_graphics_file_fn(target_path)
        source_context = graphics_source_context_path_fn(target_path)
        warnings: tuple[ValidationNotice, ...] = ()
        if (
            source_context is not None
            and (basepic := load_picture_display_source_context_fn(source_context)) is not None
        ):
            occurrences = correlate_picture_display_records_fn(
                basepic, tuple(getattr(result, "picture_display_records", ()))
            )
            warnings = picture_display_path_warnings_fn(basepic, occurrences)
        return graphics_validation_to_syntax_result_fn(target_path, result, warnings=warnings)

    src = ""
    validation_warnings: list[ValidationWarning] = []
    try:
        src = load_source_text_fn(target_path)
        violations = find_disallowed_comments_fn(src)
        if violations:
            first = violations[0]
            raise raw_source_validation_error_cls(
                "comment is only allowed inside EQUATIONBLOCK or SEQUENCE/OPENSEQUENCE blocks",
                line=first.start_line,
                column=first.start_col,
            )
        basepic = parser_core_parse_source_text_fn(src, log_failures=False)
        dependency_context_path = resolve_dependency_context_path_fn(target_path, mode)
        validate_transformed_basepicture_fn(
            basepic,
            warning_sink=validation_warnings.append,
            allow_old_state_assignment=target_path.suffix.lower() in {".x", ".z"},
            allow_unresolved_external_datatypes=(
                target_path.suffix.lower() in {".x", ".z"} or dependency_context_path is not None
            ),
        )
    except UnexpectedInput as exc:
        details = describe_parse_error_fn(exc, src)
        return SyntaxValidationResult(
            file_path=target_path,
            ok=False,
            stage="parse",
            message=details.message,
            line=details.line,
            column=details.column,
            warning_notices=tuple(coerce_validation_notice_fn(warning) for warning in validation_warnings),
        )
    except VisitError as exc:
        line, column = extract_error_position_fn(exc)
        message = str(exc.orig_exc)
        return SyntaxValidationResult(
            file_path=target_path,
            ok=False,
            stage="transform",
            message=message,
            line=line,
            column=column,
            warning_notices=tuple(coerce_validation_notice_fn(warning) for warning in validation_warnings),
        )
    except structural_validation_error_cls as exc:
        line, column = extract_error_position_fn(exc)
        return SyntaxValidationResult(
            file_path=target_path,
            ok=False,
            stage="validation",
            message=str(exc),
            line=line,
            column=column,
            warning_notices=tuple(coerce_validation_notice_fn(warning) for warning in validation_warnings),
        )
    except (OSError, RuntimeError, ValueError) as exc:
        line, column = extract_error_position_fn(exc)
        stage = "parse" if line is not None or column is not None else "validation"
        return SyntaxValidationResult(
            file_path=target_path,
            ok=False,
            stage=stage,
            message=str(exc),
            line=line,
            column=column,
            warning_notices=tuple(coerce_validation_notice_fn(warning) for warning in validation_warnings),
        )
    except Exception as exc:
        line, column = extract_error_position_fn(exc)
        if line is None and column is None:
            raise
        stage = "parse" if line is not None or column is not None else "validation"
        return SyntaxValidationResult(
            file_path=target_path,
            ok=False,
            stage=stage,
            message=str(exc),
            line=line,
            column=column,
            warning_notices=tuple(coerce_validation_notice_fn(warning) for warning in validation_warnings),
        )

    companion_path = resolve_graphics_companion_path_fn(target_path, mode=mode)
    if companion_path is not None and companion_path != target_path:
        graphics_result = validate_graphics_file_fn(companion_path)
        graphics_warnings = [*validation_warnings]
        with contextlib.suppress(AttributeError):
            graphics_warnings.extend(
                picture_display_path_warnings_fn(
                    basepic,
                    correlate_picture_display_records_fn(
                        basepic, tuple(getattr(graphics_result, "picture_display_records", ()))
                    ),
                )
            )
        return graphics_validation_to_syntax_result_fn(
            companion_path,
            graphics_result,
            warnings=graphics_warnings,
        )

    return SyntaxValidationResult(
        file_path=target_path,
        ok=True,
        stage="ok",
        warnings=tuple(coerce_validation_notice_fn(warning).message for warning in validation_warnings),
        warning_notices=tuple(coerce_validation_notice_fn(warning) for warning in validation_warnings),
    )


def raise_syntax_validation_failure(
    result: SyntaxValidationResult,
    *,
    structural_validation_error_cls: type[StructuralValidationError] = StructuralValidationError,
) -> None:
    if result.ok:
        return
    raise structural_validation_error_cls(
        result.message or "Syntax validation failed",
        line=result.line,
        column=result.column,
    )
