"""Parsing and project-loading engine for SattLine sources."""

import contextlib
import inspect
import logging
from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace
from enum import Enum
from pathlib import Path
from time import perf_counter
from typing import cast

from lark import Lark
from lark.exceptions import UnexpectedInput, VisitError

from sattline_parser import create_parser as parser_core_create_parser
from sattline_parser import parse_source_file as parser_core_parse_source_file
from sattline_parser import parse_source_text as parser_core_parse_source_text
from sattline_parser.api import describe_parse_error, read_text_with_fallback
from sattline_parser.grammar.parser_decode import is_compressed, preprocess_sl_text
from sattline_parser.models.ast_model import BasePicture, DataType, ModuleTypeDef
from sattline_parser.transformer.sl_transformer import SLTransformer

from ._engine_dependency_helpers import collect_dependency_version_conflicts as _collect_dependency_version_conflicts
from ._engine_graphics_helpers import (
    attach_graphics_companion as _attach_graphics_companion,
)
from ._engine_graphics_helpers import (
    graphics_companion_needs_refresh as _graphics_companion_needs_refresh,
)
from ._engine_graphics_helpers import (
    graphics_source_context_path as _graphics_source_context_path,
)
from ._engine_graphics_helpers import (
    load_picture_display_source_context as _load_picture_display_source_context,
)
from ._engine_graphics_helpers import (
    picture_display_path_warnings as _picture_display_path_warnings,
)
from ._engine_graphics_helpers import (
    resolve_graphics_companion_path,
)
from ._validation_shared import ValidationNotice, ValidationWarning, coerce_validation_notice
from .cache import FileASTCache, FileLookupCache, get_cache_dir
from .graphics_validation import GraphicsValidationResult, validate_graphics_file
from .models.project_graph import ProjectFailure, ProjectGraph
from .picture_display_paths import correlate_picture_display_records
from .utils.text_processing import find_disallowed_comments
from .validation import (
    RawSourceValidationError,
    StructuralValidationError,
    validate_transformed_basepicture,
)

log = logging.getLogger("SattLint")

ContextualFileLookup = Callable[[str, list[str], Path | None, str], Path | None]
LoadStageTimingSink = Callable[[str, str, float], None]
_EXPECTED_UNAVAILABLE_LIBRARY_REASONS: dict[str, str] = {
    "controllib": "expected proprietary dependency",
}


def is_expected_unavailable_library(name: str) -> bool:
    return name.casefold() in _EXPECTED_UNAVAILABLE_LIBRARY_REASONS


def expected_unavailable_library_reason(name: str) -> str | None:
    return _EXPECTED_UNAVAILABLE_LIBRARY_REASONS.get(name.casefold())


class CircularDependencyError(RuntimeError):
    """Exception raised when circular dependencies are detected."""

    def __init__(self, library: str, cycle_path: list[str]):
        self.library = library
        self.cycle_path = cycle_path
        super().__init__(f"Circular dependency detected: {' -> '.join([*cycle_path, cycle_path[0]])}")


class DependencyVersionCompatibilityError(RuntimeError):
    """Exception raised when conflicting dependency datecodes are detected."""

    def __init__(self, conflicts: list[str]):
        self.conflicts = conflicts
        super().__init__(f"Dependency version compatibility check failed: {'; '.join(conflicts)}")


def _record_missing_library(
    graph: ProjectGraph,
    *,
    name: str,
    mode: str,
    strict: bool,
    requester: str | None = None,
) -> None:
    reason = expected_unavailable_library_reason(name)
    if reason:
        graph.unavailable_libraries.add(name.casefold())
        if requester and requester.casefold() != name.casefold():
            _record_project_warning(
                graph,
                requester,
                f"dependency '{name}' unavailable: {reason}",
            )
        else:
            _record_project_warning(graph, name, f"unavailable library: {reason}")
        return

    if requester and requester.casefold() != name.casefold():
        message = f"Missing code file for dependency '{name}' referenced by '{requester}' ({mode})"
    else:
        message = f"Missing code file for '{name}' ({mode})"
    if strict:
        raise FileNotFoundError(message)
    graph.missing.append(message)
    graph.unavailable_libraries.add(name.casefold())


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
    OFFICIAL = "official"  # .x code, .z deps
    DRAFT = "draft"  # .s code, .l deps


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


_normalize_code_mode = normalize_code_mode


def _graphics_validation_to_syntax_result(
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


def _record_project_failure(graph: ProjectGraph, name: str, exception: Exception) -> None:
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


def _record_project_warning(graph: ProjectGraph, name: str, message: ValidationWarning) -> None:
    notice = coerce_validation_notice(message)
    graph.warnings.append(f"{name}: {notice.message}")
    warning_notices = getattr(graph, "warning_notices", None)
    if isinstance(warning_notices, list):
        cast(list[tuple[str, ValidationNotice]], warning_notices).append((name, notice))


def _format_debug_list(title: str, entries: Iterable[str]) -> str:
    items = [str(entry) for entry in entries]
    if not items:
        return f"{title}: none"

    lines = [f"{title} ({len(items)}):"]
    lines.extend(f"  - {item}" for item in items)
    return "\n".join(lines)


def _format_debug_missing_entries(entries: Iterable[str]) -> str:
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


BASE_DIR = Path(__file__).resolve().parent


class DebugMixin:
    debug: bool = False

    def dbg(self, msg: str) -> None:
        if self.debug:
            lines = str(msg).splitlines() or [""]
            for line in lines:
                log.debug(f"[DEBUG] {line}")


def is_within_directory(path: Path, directory: Path) -> bool:
    try:
        path.resolve().relative_to(directory.resolve())
        return True
    except ValueError:
        return False


_is_within_directory = is_within_directory


def create_sl_parser() -> Lark:
    """Compatibility wrapper that delegates parser creation to parser-core."""
    return parser_core_create_parser()


def _load_source_text(
    code_path: Path,
    *,
    debug: Callable[[str], None] | None = None,
) -> str:
    source_path = Path(code_path)
    if debug is not None:
        debug(f"Parsing file: {source_path}")

    src = read_text_with_fallback(source_path)
    if is_compressed(src):
        if debug is not None:
            debug("Compressed format detected; decoding before parsing")
        src, _ = preprocess_sl_text(src)
    return src


def parse_source_text(
    src: str,
    *,
    parser: Lark | None = None,
    transformer: SLTransformer | None = None,
    debug: Callable[[str], None] | None = None,
) -> BasePicture:
    basepic = parser_core_parse_source_text(
        src,
        parser=parser,
        transformer=transformer,
        debug=debug,
    )
    validate_transformed_basepicture(basepic)

    return basepic


def parse_source_file(
    code_path: Path,
    *,
    parser: Lark | None = None,
    transformer: SLTransformer | None = None,
    debug: Callable[[str], None] | None = None,
) -> BasePicture:
    basepic = parser_core_parse_source_file(
        code_path,
        parser=parser,
        transformer=transformer,
        debug=debug,
    )
    validate_transformed_basepicture(basepic)
    return basepic


def _extract_error_position(exc: Exception) -> tuple[int | None, int | None]:
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
) -> SyntaxValidationResult:
    target_path = Path(code_path)
    if target_path.suffix.lower() in {".g", ".y"}:
        result = validate_graphics_file(target_path)
        source_context = _graphics_source_context_path(target_path)
        warnings: tuple[ValidationNotice, ...] = ()
        if source_context is not None and (basepic := _load_picture_display_source_context(source_context)) is not None:
            occurrences = correlate_picture_display_records(
                basepic, tuple(getattr(result, "picture_display_records", ()))
            )
            warnings = _picture_display_path_warnings(basepic, occurrences)
        return _graphics_validation_to_syntax_result(target_path, result, warnings=warnings)

    src = ""
    validation_warnings: list[ValidationWarning] = []
    try:
        src = _load_source_text(target_path)
        violations = find_disallowed_comments(src)
        if violations:
            first = violations[0]
            raise RawSourceValidationError(
                "comment is only allowed inside EQUATIONBLOCK or SEQUENCE/OPENSEQUENCE blocks",
                line=first.start_line,
                column=first.start_col,
            )
        basepic = parser_core_parse_source_text(src, log_failures=False)
        validate_transformed_basepicture(
            basepic,
            warning_sink=validation_warnings.append,
            allow_old_state_assignment=target_path.suffix.lower() in {".x", ".z"},
            allow_unresolved_external_datatypes=target_path.suffix.lower() in {".x", ".z"},
        )
    except UnexpectedInput as exc:
        details = describe_parse_error(exc, src)
        return SyntaxValidationResult(
            file_path=target_path,
            ok=False,
            stage="parse",
            message=details.message,
            line=details.line,
            column=details.column,
            warning_notices=tuple(coerce_validation_notice(warning) for warning in validation_warnings),
        )
    except VisitError as exc:
        line, column = _extract_error_position(exc)
        message = str(exc.orig_exc)
        return SyntaxValidationResult(
            file_path=target_path,
            ok=False,
            stage="transform",
            message=message,
            line=line,
            column=column,
            warning_notices=tuple(coerce_validation_notice(warning) for warning in validation_warnings),
        )
    except StructuralValidationError as exc:
        line, column = _extract_error_position(exc)
        return SyntaxValidationResult(
            file_path=target_path,
            ok=False,
            stage="validation",
            message=str(exc),
            line=line,
            column=column,
            warning_notices=tuple(coerce_validation_notice(warning) for warning in validation_warnings),
        )
    except Exception as exc:
        line, column = _extract_error_position(exc)
        stage = "parse" if line is not None or column is not None else "validation"
        return SyntaxValidationResult(
            file_path=target_path,
            ok=False,
            stage=stage,
            message=str(exc),
            line=line,
            column=column,
            warning_notices=tuple(coerce_validation_notice(warning) for warning in validation_warnings),
        )

    companion_path = resolve_graphics_companion_path(target_path, mode=mode)
    if companion_path is not None and companion_path != target_path:
        graphics_result = validate_graphics_file(companion_path)
        graphics_warnings = [*validation_warnings]
        with contextlib.suppress(AttributeError):
            graphics_warnings.extend(
                _picture_display_path_warnings(
                    basepic,
                    correlate_picture_display_records(
                        basepic, tuple(getattr(graphics_result, "picture_display_records", ()))
                    ),
                )
            )
        return _graphics_validation_to_syntax_result(
            companion_path,
            graphics_result,
            warnings=graphics_warnings,
        )

    return SyntaxValidationResult(
        file_path=target_path,
        ok=True,
        stage="ok",
        warnings=tuple(coerce_validation_notice(warning).message for warning in validation_warnings),
        warning_notices=tuple(coerce_validation_notice(warning) for warning in validation_warnings),
    )


def _raise_syntax_validation_failure(result: SyntaxValidationResult) -> None:
    if result.ok:
        return
    raise StructuralValidationError(
        result.message or "Syntax validation failed",
        line=result.line,
        column=result.column,
    )


# ---------- Loader with recursive resolution ----------
class SattLineProjectLoader(DebugMixin):
    def __init__(
        self,
        program_dir: Path,
        other_lib_dirs: Iterable[Path],
        abb_lib_dir: Path,
        mode: CodeMode,
        scan_root_only: bool,
        debug: bool,
        contextual_lookup: ContextualFileLookup | None = None,
        use_file_ast_cache: bool = True,
        status_update_fn: Callable[[str], None] | None = None,
        refresh_mode: str = "full",
        stage_timing_sink: LoadStageTimingSink | None = None,
    ):
        self.program_dir = program_dir
        self.other_lib_dirs = list(other_lib_dirs)
        self.abb_lib_dir = abb_lib_dir
        self.mode = mode
        self.scan_root_only = scan_root_only
        self.debug = debug
        self.contextual_lookup = contextual_lookup
        self.use_file_ast_cache = use_file_ast_cache
        self._status_update_fn = status_update_fn
        self.refresh_mode = str(refresh_mode).strip().lower() or "full"
        if self.refresh_mode not in {"full", "ast-only"}:
            raise ValueError(f"Unsupported refresh mode: {refresh_mode!r}")
        self._stage_timing_sink = stage_timing_sink
        self._last_status_message: str | None = None
        self.parser = create_sl_parser()  # reuse your grammar setup
        self.transformer = SLTransformer()  # reuse your transformer
        self._visited: set[str] = set()
        self._visit_stack: list[str] = []  # ordered stack for cycle detection and path reporting
        self._ignored_dirs: set[Path] = set()
        self._lookup_cache = FileLookupCache(get_cache_dir())
        self._ast_cache = FileASTCache(get_cache_dir())
        self._base_indexes: dict[Path, dict[str, dict[str, Path]]] = {}
        self._lib_by_name: dict[str, str] = {}
        self.dbg(f"Selected mode={mode.value}, code_ext={code_ext(mode)}, deps_ext={deps_ext(mode)}")
        self.dbg(f"Programs dir: {self.program_dir}")
        for i, ld in enumerate(self.other_lib_dirs, start=1):
            self.dbg(f"Lib {i}: {ld}")
        self.dbg(f"ABB lib dir: {self.abb_lib_dir}")

    def _record_stage_timing(self, owner_name: str, stage: str, started_at: float) -> None:
        if self._stage_timing_sink is None:
            return
        self._stage_timing_sink(owner_name, stage, perf_counter() - started_at)

    def _update_status(self, message: str) -> None:
        if self._status_update_fn is None:
            return
        text = str(message).strip()
        if not text or text == self._last_status_message:
            return
        self._last_status_message = text
        self._status_update_fn(text)

    def _is_ignored_base(self, base: Path) -> bool:
        try:
            base_r = base.resolve()
        except OSError:
            base_r = base
        return any(base_r == ign for ign in self._ignored_dirs)

    def _is_allowed_base(self, base: Path) -> bool:
        allowed = [self.program_dir, *self.other_lib_dirs, self.abb_lib_dir]
        try:
            base_r = base.resolve()
        except OSError:
            base_r = base
        for candidate in allowed:
            try:
                cand_r = candidate.resolve()
            except OSError:
                cand_r = candidate
            if base_r == cand_r:
                return True
        return False

    def _get_base_index(self, base: Path) -> dict[str, dict[str, Path]]:
        if base in self._base_indexes:
            return self._base_indexes[base]
        index: dict[str, dict[str, Path]] = {}
        if not base.exists() or not base.is_dir():
            self._base_indexes[base] = index
            return index

        for entry in base.iterdir():
            if not entry.is_file():
                continue
            ext = entry.suffix.lower()
            if ext not in {".s", ".x", ".l", ".z"}:
                continue
            stem = entry.stem.casefold()
            index.setdefault(stem, {})[ext] = entry

        self._base_indexes[base] = index
        return index

    def _find_in_index(
        self,
        *,
        base: Path,
        name: str,
        extensions: list[str],
    ) -> Path | None:
        index = self._get_base_index(base)
        entries = index.get(name.casefold())
        if not entries:
            return None
        for ext in extensions:
            p = entries.get(ext)
            if p is not None:
                return p
        return None

    def _add_to_index(self, base: Path, name: str, path: Path) -> None:
        index = self._get_base_index(base)
        index.setdefault(name.casefold(), {})[path.suffix.lower()] = path

    def _find_in_cached_base(
        self,
        *,
        kind: str,
        name: str,
        extensions: list[str],
    ) -> Path | None:
        cached = self._lookup_cache.get(kind, name, self.mode.value)
        if not cached:
            return None

        base = Path(cached.get("base_dir", ""))
        if not base or self._is_ignored_base(base):
            return None
        if not self._is_allowed_base(base):
            self._lookup_cache.forget(kind, name, self.mode.value)
            return None

        cached_ext = cached.get("ext")
        ordered_exts = [cached_ext] if cached_ext in extensions else []
        ordered_exts.extend(ext for ext in extensions if ext != cached_ext)

        for ext in ordered_exts:
            p = base / f"{name}{ext}"
            self.dbg(f"Checking cached {kind} file: {p} (exists={p.exists()})")
            if p.exists():
                self.dbg(f"Using cached {kind} file: {p}")
                return p

        self._lookup_cache.forget(kind, name, self.mode.value)
        return None

    def _find_code(self, name: str) -> Path | None:
        """
        Find code file with fallback support.
        In draft mode: try .s first, fallback to .x
        In official mode: only use .x
        """
        return self._find_code_with_context(name, requester_dir=None)

    def _find_code_with_context(
        self,
        name: str,
        *,
        requester_dir: Path | None,
    ) -> Path | None:
        extensions = [".s", ".x"] if self.mode == CodeMode.DRAFT else [".x"]

        if self.contextual_lookup is not None:
            resolved = self.contextual_lookup(name, extensions, requester_dir, "code")
            if resolved is not None:
                self.dbg(f"Using contextual code file: {resolved} (requested by {requester_dir or self.program_dir})")
                return resolved

        cached = self._find_in_cached_base(
            kind="code",
            name=name,
            extensions=extensions,
        )
        if cached is not None:
            return cached

        for base in [self.program_dir, *self.other_lib_dirs, self.abb_lib_dir]:
            if self._is_ignored_base(base):
                continue

            indexed = self._find_in_index(
                base=base,
                name=name,
                extensions=extensions,
            )
            if indexed is not None:
                self.dbg(f"Using code file: {indexed}")
                self._lookup_cache.set("code", name, self.mode.value, base, indexed.suffix.lower())
                return indexed

            for ext in extensions:
                p = base / f"{name}{ext}"
                self.dbg(f"Checking code file: {p} (exists={p.exists()})")
                if p.exists():
                    self.dbg(f"Using code file: {p}")
                    self._lookup_cache.set("code", name, self.mode.value, base, ext)
                    self._add_to_index(base, name, p)
                    return p

        self.dbg(f"No code file found for '{name}' in mode={self.mode.value}")
        return None

    def _find_deps(self, name: str) -> Path | None:
        """
        Find deps file with fallback support.
        In draft mode: try .l first, fallback to .z
        In official mode: only use .z
        """
        return self._find_deps_with_context(name, requester_dir=None)

    def _find_deps_with_context(
        self,
        name: str,
        *,
        requester_dir: Path | None,
    ) -> Path | None:
        extensions = [".l", ".z"] if self.mode == CodeMode.DRAFT else [".z"]

        if self.contextual_lookup is not None:
            resolved = self.contextual_lookup(name, extensions, requester_dir, "deps")
            if resolved is not None:
                self.dbg(f"Using contextual deps file: {resolved} (requested by {requester_dir or self.program_dir})")
                return resolved

        cached = self._find_in_cached_base(
            kind="deps",
            name=name,
            extensions=extensions,
        )
        if cached is not None:
            return cached

        for base in [self.program_dir, *self.other_lib_dirs, self.abb_lib_dir]:
            if self._is_ignored_base(base):
                continue

            indexed = self._find_in_index(
                base=base,
                name=name,
                extensions=extensions,
            )
            if indexed is not None:
                self.dbg(f"Using deps file: {indexed}")
                self._lookup_cache.set("deps", name, self.mode.value, base, indexed.suffix.lower())
                return indexed

            for ext in extensions:
                p = base / f"{name}{ext}"
                self.dbg(f"Checking deps file: {p} (exists={p.exists()})")
                if p.exists():
                    self.dbg(f"Using deps file: {p}")
                    self._lookup_cache.set("deps", name, self.mode.value, base, ext)
                    self._add_to_index(base, name, p)
                    return p

        self.dbg(f"No deps file found for '{name}' in mode={self.mode.value}")
        return None

    def _find_vendor_code(self, name: str) -> Path | None:
        """Find code file in vendor directories with fallback."""
        extensions = [".s", ".x"] if self.mode == CodeMode.DRAFT else [".x"]

        for ign in self._ignored_dirs:
            for ext in extensions:
                p = ign / f"{name}{ext}"
                if p.exists():
                    return p
        return None

    def _find_vendor_deps(self, name: str) -> Path | None:
        """Find deps file in vendor directories with fallback."""
        extensions = [".l", ".z"] if self.mode == CodeMode.DRAFT else [".z"]

        for ign in self._ignored_dirs:
            for ext in extensions:
                p = ign / f"{name}{ext}"
                if p.exists():
                    return p
        return None

    def _read_deps(self, deps_path: Path) -> list[str]:
        text = read_text_with_fallback(deps_path)
        lines = text.splitlines()
        names = [ln.strip() for ln in lines if ln.strip()]
        self.dbg(f"Deps from {deps_path.name}: {names}")
        return names

    def _read_text_simple(self, path: Path) -> str:
        return read_text_with_fallback(path)

    def _library_name_for_path(self, code_path: Path) -> str:
        """
        Return the top-level root directory name this file belongs to
        (e.g., 'unitlib', 'nnelib', 'projectlib', 'SL_Library').
        """
        rp = code_path.resolve()
        try:
            pr = self.program_dir.resolve()
        except OSError:
            pr = self.program_dir
        if rp.is_relative_to(pr):
            return pr.name
        for ld in self.other_lib_dirs:
            try:
                lr = ld.resolve()
            except OSError:
                lr = ld
            if rp.is_relative_to(lr):
                return lr.name
        try:
            ar = self.abb_lib_dir.resolve()
        except OSError:
            ar = self.abb_lib_dir
        if rp.is_relative_to(ar):
            return ar.name
        # Fallback: parent directory name
        return rp.parent.name

    def _record_library_name(self, name: str, code_path: Path) -> str:
        lib_name = self._library_name_for_path(code_path)
        self._lib_by_name[name.casefold()] = lib_name
        return lib_name

    def _parse_one(self, code_path: Path) -> BasePicture:
        return parser_core_parse_source_file(
            code_path,
            parser=self.parser,
            transformer=self.transformer,
            debug=self.dbg,
        )

    def _load_or_parse(self, code_path: Path, *, owner_name: str | None = None) -> BasePicture | None:
        resolved_owner_name = owner_name or code_path.stem
        started_at = perf_counter()
        if self.use_file_ast_cache:
            cached = self._ast_cache.load(code_path, self.mode.value)
            if isinstance(cached, BasePicture):
                self._update_status(f"Loading {code_path.stem}: using cached AST from {code_path.name}")
                self.dbg(f"Using cached AST for: {code_path}")
                self._record_stage_timing(resolved_owner_name, "load_or_parse", started_at)
                return cached

        self._update_status(f"Loading {code_path.stem}: parsing {code_path.name}")
        bp = self._parse_one(code_path)
        cache_save_started_at = perf_counter()
        self._ast_cache.save(code_path, self.mode.value, bp)
        self._record_stage_timing(resolved_owner_name, "ast_cache_save", cache_save_started_at)
        self._record_stage_timing(resolved_owner_name, "load_or_parse", started_at)
        return bp

    def _load_or_parse_for_owner(self, code_path: Path, *, owner_name: str) -> BasePicture | None:
        load_or_parse = self._load_or_parse
        try:
            signature = inspect.signature(load_or_parse)
        except (TypeError, ValueError):
            return load_or_parse(code_path, owner_name=owner_name)

        accepts_owner_name = "owner_name" in signature.parameters or any(
            parameter.kind is inspect.Parameter.VAR_KEYWORD for parameter in signature.parameters.values()
        )
        if accepts_owner_name:
            return load_or_parse(code_path, owner_name=owner_name)
        return load_or_parse(code_path)

    def _flush_lookup_cache(self) -> None:
        flush = getattr(self._lookup_cache, "flush", None)
        if callable(flush):
            flush()

    def resolve(self, root_name: str, strict: bool = False, *, syntax_check: bool = False) -> ProjectGraph:
        if self.scan_root_only:
            return self._resolve_root_only(root_name, strict)
        self._update_status(f"Loading {root_name}: resolving dependency graph")
        self.dbg(f"Resolving root: {root_name}")
        graph = ProjectGraph()
        previous_root_key = getattr(self, "_active_root_key", None)
        self._active_root_key = root_name.casefold()
        try:
            self._visit(root_name, graph, strict, requester_dir=self.program_dir, syntax_check=syntax_check)
        finally:
            self._flush_lookup_cache()
            self._active_root_key = previous_root_key
        self.dbg(_format_debug_list("Resolved ASTs", graph.ast_by_name.keys()))
        if graph.missing:
            self.dbg(_format_debug_missing_entries(graph.missing))
        return graph

    def _resolve_root_only(self, root_name: str, strict: bool) -> ProjectGraph:
        graph = ProjectGraph()
        try:
            self._update_status(f"Loading {root_name}: locating source file")
            code_path = self._find_code(root_name)
            if not code_path:
                _record_missing_library(
                    graph,
                    name=root_name,
                    mode=f"mode={self.mode.value}",
                    strict=strict,
                )
                return graph

            validation_warnings: list[ValidationWarning] = []
            bp = self._load_or_parse_for_owner(code_path, owner_name=root_name)
            if bp is None:
                message = f"{root_name} transformed to no BasePicture (parse/transform issue?)"
                if strict:
                    raise RuntimeError(message)
                graph.missing.append(message)
                return graph
            self._update_status(f"Loading {root_name}: validating {code_path.name}")
            validation_started_at = perf_counter()
            validate_transformed_basepicture(
                bp,
                allow_unresolved_external_datatypes=True if self.refresh_mode == "ast-only" else not strict,
                enforce_unique_submodule_names=False,
                allow_parameterless_module_mappings=True,
                warn_unknown_parameter_targets=self.refresh_mode != "ast-only",
                warn_incompatible_parameter_mappings=self.refresh_mode != "ast-only",
                warning_sink=validation_warnings.append,
            )
            self._record_stage_timing(root_name, "validate", validation_started_at)
            for warning in validation_warnings:
                _record_project_warning(graph, root_name, warning)
            graph.ast_by_name[root_name] = bp
            if self.refresh_mode == "ast-only":
                return graph
            if _graphics_companion_needs_refresh(bp, code_path=code_path, mode=self.mode):
                self._update_status(f"Loading {root_name}: checking graphics companion")
            graphics_started_at = perf_counter()
            if _attach_graphics_companion(
                bp,
                code_path=code_path,
                mode=self.mode,
                graph=graph,
                owner_name=root_name,
            ):
                self._ast_cache.save(code_path, self.mode.value, bp)
            self._record_stage_timing(root_name, "attach_graphics", graphics_started_at)
            lib_name = self._library_name_for_path(code_path)
            self._update_status(f"Loading {root_name}: indexing definitions")
            index_started_at = perf_counter()
            graph.index_from_basepic(
                bp, source_path=code_path, library_name=lib_name
            )  # collect any defs emitted in this files
            self._record_stage_timing(root_name, "index", index_started_at)
            return graph
        except Exception as ex:
            for warning in locals().get("validation_warnings", []):
                _record_project_warning(graph, root_name, warning)
            if strict:
                raise
            _record_project_failure(graph, root_name, ex)
            return graph
        finally:
            self._flush_lookup_cache()

    def _visit(
        self,
        name: str,
        graph: ProjectGraph,
        strict: bool,
        *,
        requester_dir: Path | None,
        syntax_check: bool = False,
    ) -> None:
        key = name.lower()
        root_key = getattr(self, "_active_root_key", None)

        # Check if already fully processed
        if key in self._visited:
            return

        # Check for circular dependency before entering processing
        if key in self._visit_stack:
            # Construct cycle path from current stack
            cycle_start_idx = self._visit_stack.index(key)
            cycle_path = list(self._visit_stack[cycle_start_idx:])
            raise CircularDependencyError(name, cycle_path)

        # Add to processing stack
        self._visit_stack.append(key)

        try:
            root_code_path: Path | None = None
            if strict and syntax_check and key == root_key:
                self._update_status(f"Loading {name}: running syntax check")
                root_code_path = self._find_code_with_context(name, requester_dir=requester_dir)
                if root_code_path is not None:
                    _raise_syntax_validation_failure(validate_single_file_syntax(root_code_path, mode=self.mode))

            # Resolve dependencies first (from non-vendor dirs only)
            self._update_status(f"Loading {name}: reading dependency list")
            deps_path = self._find_deps_with_context(name, requester_dir=requester_dir)
            dep_names = self._read_deps(deps_path) if deps_path else []
            dependency_requester = deps_path.parent if deps_path is not None else requester_dir

            # Visit each dep
            for index, dep in enumerate(dep_names, start=1):
                self._update_status(f"Loading {name}: resolving dependency {index}/{len(dep_names)} {dep}")
                self._visit(dep, graph, strict, requester_dir=dependency_requester, syntax_check=syntax_check)

            dep_libs: list[str] = []
            for dep in dep_names:
                dep_bp = graph.ast_by_name.get(dep)
                if dep_bp:
                    origin_lib = getattr(dep_bp, "origin_lib", None)
                    if origin_lib:
                        dep_libs.append(origin_lib)
                        continue
                cached_lib = self._lib_by_name.get(dep.casefold())
                if cached_lib:
                    dep_libs.append(cached_lib)

            # Determine code path
            self._update_status(f"Loading {name}: locating source file")
            code_path = root_code_path or self._find_code_with_context(name, requester_dir=requester_dir)
            if code_path is not None:
                try:
                    validation_warnings: list[ValidationWarning] = []
                    bp = self._load_or_parse_for_owner(code_path, owner_name=name)
                    if bp is None:
                        message = f"{name} transform produced no BasePicture (skipped)"
                        if strict:
                            raise RuntimeError(message)
                        graph.missing.append(message)
                        return
                    try:
                        self._update_status(f"Loading {name}: validating {code_path.name}")
                        validation_started_at = perf_counter()
                        validate_transformed_basepicture(
                            bp,
                            external_datatypes=()
                            if self.refresh_mode == "ast-only"
                            else tuple(graph.datatype_defs.values()),
                            external_moduletype_defs=()
                            if self.refresh_mode == "ast-only"
                            else tuple(graph.moduletype_defs.values()),
                            allow_unresolved_external_datatypes=True if self.refresh_mode == "ast-only" else not strict,
                            enforce_unique_submodule_names=False,
                            allow_parameterless_module_mappings=True,
                            warn_unknown_parameter_targets=self.refresh_mode != "ast-only",
                            warn_incompatible_parameter_mappings=self.refresh_mode != "ast-only",
                            warning_sink=validation_warnings.append,
                        )
                        self._record_stage_timing(name, "validate", validation_started_at)
                    except StructuralValidationError as ex:
                        if key == root_key:
                            raise
                        _record_project_warning(graph, name, f"validation warning: {ex}")
                    for warning in validation_warnings:
                        _record_project_warning(graph, name, warning)
                    graph.ast_by_name[name] = bp
                    if self.refresh_mode == "ast-only":
                        return
                    if _graphics_companion_needs_refresh(bp, code_path=code_path, mode=self.mode):
                        self._update_status(f"Loading {name}: checking graphics companion")
                    graphics_started_at = perf_counter()
                    if _attach_graphics_companion(
                        bp,
                        code_path=code_path,
                        mode=self.mode,
                        graph=graph,
                        owner_name=name,
                    ):
                        self._ast_cache.save(code_path, self.mode.value, bp)
                    self._record_stage_timing(name, "attach_graphics", graphics_started_at)
                    lib_name = self._record_library_name(name, code_path)
                    version_conflicts = _collect_dependency_version_conflicts(
                        graph,
                        bp,
                        library_name=lib_name,
                        source_path=code_path,
                    )
                    if version_conflicts:
                        if strict:
                            raise DependencyVersionCompatibilityError(version_conflicts)
                        for conflict in version_conflicts:
                            _record_project_warning(
                                graph,
                                name,
                                f"version compatibility warning: {conflict}",
                            )
                    graph.add_library_dependencies(lib_name, dep_libs)
                    self._update_status(f"Loading {name}: indexing definitions")
                    index_started_at = perf_counter()
                    graph.index_from_basepic(
                        bp, source_path=code_path, library_name=lib_name
                    )  # aggregate defs for global analysis [2]
                    self._record_stage_timing(name, "index", index_started_at)
                except Exception as ex:
                    for warning in locals().get("validation_warnings", []):
                        _record_project_warning(graph, name, warning)
                    if strict:
                        raise
                    _record_project_failure(graph, name, ex)
            else:
                # If we skipped vendor dir and the file exists there, mark as ignored vendor
                v_code = self._find_vendor_code(name)
                v_deps = self._find_vendor_deps(name)
                if v_code or v_deps:
                    graph.ignored_vendor.append(f"{name} (vendor: {v_code or v_deps})")
                    # Track as unavailable library for better error messages
                    graph.unavailable_libraries.add(name.lower())
                else:
                    requester_name = self._visit_stack[-2] if len(self._visit_stack) > 1 else None
                    _record_missing_library(
                        graph,
                        name=name,
                        mode=self.mode.value,
                        strict=strict,
                        requester=requester_name,
                    )
        finally:
            # Always remove from processing stack and mark as visited
            self._visit_stack.remove(key)
            self._visited.add(key)


# ---------- Merge: build a synthetic “project” BasePicture ----------
def merge_project_basepicture(root_bp: BasePicture, graph: ProjectGraph) -> BasePicture:
    """
    Create a single BasePicture that contains all DataType and ModuleTypeDef
    definitions from the root and its dependencies, so analyzers can resolve
    types across files without changing SLTransformer.
    """
    # Moduletype defs are keyed by (library, name) so same-name types from different
    # libraries are preserved in the merged BasePicture.
    merged_datatypes: list[DataType] = list(graph.datatype_defs.values())
    merged_modtypes: list[ModuleTypeDef] = list(graph.moduletype_defs.values())

    lib_deps = {lib: sorted(deps) for lib, deps in (graph.library_dependencies or {}).items()}

    return replace(
        root_bp,
        datatype_defs=merged_datatypes,
        moduletype_defs=merged_modtypes,
        library_dependencies=lib_deps,
    )


# ---------- Dump functions ----------
def _get_dump_dir() -> Path:
    """Get or create the dump directory."""
    dump_dir = Path.home() / ".sattlint" / "dumps"
    dump_dir.mkdir(parents=True, exist_ok=True)
    return dump_dir


def dump_parse_tree(project: tuple[BasePicture, ProjectGraph]) -> None:
    """Save the parse tree from the root BasePicture to a file."""
    from datetime import datetime

    project_bp, _graph = project

    if project_bp.parse_tree is None:
        print("❌ No parse tree available for the root program.")
        return

    dump_dir = _get_dump_dir()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = dump_dir / f"parse_tree_{project_bp.header.name}_{timestamp}.txt"

    output = project_bp.parse_tree.pretty()
    filename.write_text(output, encoding="utf-8")

    print(f"\n✔ Parse tree saved to: {filename}")
    print()


def dump_ast(project: tuple[BasePicture, ProjectGraph]) -> None:
    """Save the AST (BasePicture) structure to a file."""
    from datetime import datetime

    project_bp, _graph = project

    dump_dir = _get_dump_dir()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = dump_dir / f"ast_{project_bp.header.name}_{timestamp}.txt"

    output = str(project_bp)
    filename.write_text(output, encoding="utf-8")

    print(f"\n✔ AST saved to: {filename}")
    print()


def dump_dependency_graph(project: tuple[BasePicture, ProjectGraph]) -> None:
    """Save the dependency graph to a file."""
    from datetime import datetime

    project_bp, graph = project

    dump_dir = _get_dump_dir()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = dump_dir / f"dependency_graph_{project_bp.header.name}_{timestamp}.txt"

    lines = ["--- Dependency Graph ---"]
    lines.append(f"Programs/Libraries parsed: {len(graph.ast_by_name)}")
    for name in sorted(graph.ast_by_name.keys()):
        bp = graph.ast_by_name[name]
        origin_info = f" (from {bp.origin_lib}/{bp.origin_file})" if bp.origin_lib or bp.origin_file else ""
        lines.append(f"  • {name}{origin_info}")

    if graph.datatype_defs:
        lines.append(f"\nDataType Definitions: {len(graph.datatype_defs)}")
        for name in sorted(graph.datatype_defs.keys()):
            dt = graph.datatype_defs[name]
            origin_info = f" (from {dt.origin_lib}/{dt.origin_file})" if dt.origin_lib or dt.origin_file else ""
            lines.append(f"  • {name}{origin_info}")

    if graph.moduletype_defs:
        lines.append(f"\nModuleType Definitions: {len(graph.moduletype_defs)}")
        for (_lib_key, _name_key, _file_key), mt in sorted(graph.moduletype_defs.items()):
            display = f"{mt.origin_lib}:{mt.name}" if mt.origin_lib else mt.name
            origin_info = f" (from {mt.origin_lib}/{mt.origin_file})" if mt.origin_lib or mt.origin_file else ""
            lines.append(f"  • {display}{origin_info}")

    if graph.library_dependencies:
        lines.append("\nLibrary dependencies:")
        for lib, deps in sorted(graph.library_dependencies.items()):
            dep_list = ", ".join(sorted(deps)) if deps else "<none>"
            lines.append(f"  • {lib} -> {dep_list}")

    if graph.missing:
        lines.append(f"\nMissing/Unresolved: {len(graph.missing)}")
        for msg in graph.missing:
            lines.append(f"  ⚠ {msg}")

    if graph.warnings:
        lines.append(f"\nWarnings: {len(graph.warnings)}")
        for msg in graph.warnings:
            lines.append(f"  ⚠ {msg}")

    if graph.ignored_vendor:
        lines.append(f"\nIgnored Vendor: {len(graph.ignored_vendor)}")
        for msg in graph.ignored_vendor:
            lines.append(f"  ⓘ {msg}")

    output = "\n".join(lines)
    filename.write_text(output, encoding="utf-8")

    print(f"\n✔ Dependency graph saved to: {filename}")
    print()
