"""Syntax and parser helper implementations shared across the app."""

import contextlib
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Any

from lark import Lark
from lark.exceptions import UnexpectedInput, VisitError

from sattlint.parser_api import (
    BasePicture,
    SLTransformer,
    describe_parse_error,
    load_source_text,
    source_text_for_parse,
)
from sattlint.parser_api import create_parser as parser_core_create_parser
from sattlint.parser_api import parse_source_file as parser_core_parse_source_file
from sattlint.parser_api import parse_source_text as parser_core_parse_source_text

from ..graphics.graphics_context_helpers import (
    graphics_source_context_path,
    load_picture_display_source_context,
    picture_display_path_warnings,
    resolve_graphics_companion_path,
)
from ..graphics.picture_display_paths import correlate_picture_display_records
from ..graphics.validation import GraphicsValidationResult, validate_graphics_file
from ..validation.policy import validate_basepicture_strict
from ..validation.shared import (
    StructuralValidationError,
    ValidationNotice,
    ValidationWarning,
    coerce_validation_notice,
)


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


def code_ext_candidates(mode: CodeMode) -> tuple[str, ...]:
    return (code_ext(mode),) if mode is CodeMode.OFFICIAL else (code_ext(mode), ".x")


def deps_ext_candidates(mode: CodeMode) -> tuple[str, ...]:
    return (deps_ext(mode),) if mode is CodeMode.OFFICIAL else (deps_ext(mode), ".z")


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


@lru_cache(maxsize=1)
def create_sl_parser() -> Lark:
    # Lark parser instances are reusable across parses; building one costs ~100ms+ even with
    # sattline_parser's own on-disk grammar cache, and every load_project_graph() call built a
    # fresh one. Cache it for the lifetime of the process instead.
    return parser_core_create_parser()


def parse_source_text(
    src: str,
    *,
    parser: Lark | None = None,
    transformer: SLTransformer | None = None,
    debug: Callable[[str], None] | None = None,
    parser_core_parse_source_text_fn: Callable[..., BasePicture] = parser_core_parse_source_text,
    validate_transformed_basepicture_fn: Callable[[BasePicture], None] = validate_basepicture_strict,
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
    validate_transformed_basepicture_fn: Callable[[BasePicture], None] = validate_basepicture_strict,
) -> BasePicture:
    basepic = parser_core_parse_source_file_fn(
        code_path,
        parser=parser,
        transformer=transformer,
        debug=debug,
    )
    validate_transformed_basepicture_fn(basepic)
    return basepic


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
    source_text_for_parse_fn: Callable[..., str] = source_text_for_parse,
    parser_core_parse_source_text_fn: Callable[..., BasePicture] = parser_core_parse_source_text,
    validate_transformed_basepicture_fn: Callable[..., None] = validate_basepicture_strict,
    describe_parse_error_fn: Callable[[UnexpectedInput, str], Any] = describe_parse_error,
    validate_graphics_file_fn: Callable[[Path], GraphicsValidationResult] = validate_graphics_file,
    graphics_source_context_path_fn: Callable[[Path], Path | None] = graphics_source_context_path,
    load_picture_display_source_context_fn: Callable[[Path], BasePicture | None] = load_picture_display_source_context,
    correlate_picture_display_records_fn: Callable[..., Any] = correlate_picture_display_records,
    picture_display_path_warnings_fn: Callable[..., tuple[ValidationNotice, ...]] = picture_display_path_warnings,
    resolve_graphics_companion_path_fn: Callable[..., Path | None] = resolve_graphics_companion_path,
    extract_error_position_fn: Callable[[Exception], tuple[int | None, int | None]] = extract_error_position,
    graphics_validation_to_syntax_result_fn: Callable[
        ..., SyntaxValidationResult
    ] = graphics_validation_to_syntax_result,
    coerce_validation_notice_fn: Callable[[ValidationWarning], ValidationNotice] = coerce_validation_notice,
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
    parse_src = ""
    validation_warnings: list[ValidationWarning] = []
    try:
        # Parse the text the parser reads, so compressed sources keep their
        # original character coordinates in spans and diagnostics.
        parse_src = source_text_for_parse_fn(target_path)
        basepic = parser_core_parse_source_text_fn(parse_src, log_failures=False)
        validate_transformed_basepicture_fn(basepic, warning_sink=validation_warnings.append)
    except UnexpectedInput as exc:
        details = describe_parse_error_fn(exc, parse_src or src)
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
