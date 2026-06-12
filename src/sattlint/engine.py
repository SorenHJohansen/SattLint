"""Parsing and project-loading engine for SattLine sources."""

import inspect
import logging
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from time import perf_counter
from typing import Protocol, TypeGuard

from lark import Lark

from sattline_parser import parse_source_file as parser_core_parse_source_file
from sattline_parser import parse_source_text as parser_core_parse_source_text
from sattline_parser.api import describe_parse_error, read_text_with_fallback
from sattline_parser.grammar.parser_decode import is_compressed, preprocess_sl_text
from sattline_parser.models.ast_model import BasePicture, DataType, ModuleTypeDef
from sattline_parser.transformer.sl_transformer import SLTransformer

from . import _engine_syntax_helpers as engine_syntax_helpers
from . import cache as cache_module
from ._engine_dependency_helpers import collect_dependency_version_conflicts as _collect_dependency_version_conflicts
from ._engine_graphics_context_helpers import (
    graphics_source_context_path as _graphics_source_context_path,
)
from ._engine_graphics_context_helpers import (
    load_picture_display_source_context as _load_picture_display_source_context,
)
from ._engine_graphics_context_helpers import (
    picture_display_path_warnings as _picture_display_path_warnings,
)
from ._engine_graphics_context_helpers import (
    resolve_graphics_companion_path,
)
from ._engine_graphics_helpers import (
    attach_graphics_companion as _attach_graphics_companion,
)
from ._engine_graphics_helpers import (
    graphics_companion_needs_refresh as _graphics_companion_needs_refresh,
)
from ._validation_shared import ValidationNotice, ValidationWarning, coerce_validation_notice
from .cache import FileASTCache, FileLookupCache, get_cache_dir
from .graphics_validation import validate_graphics_file
from .models.project_graph import ProjectGraph
from .picture_display_paths import correlate_picture_display_records
from .utils.text_processing import find_disallowed_comments
from .validation import (
    LOCAL_STRUCTURE_VALIDATION_SCHEMA_VERSION,
    StructuralValidationError,
    validate_transformed_basepicture,
    validate_transformed_basepicture_dependency_context,
    validate_transformed_basepicture_locally,
)

log = logging.getLogger("SattLint")

ContextualFileLookup = Callable[[str, list[str], Path | None, str], Path | None]
LoadStageTimingSink = Callable[[str, str, float], None]
GraphicsLoadTimingSink = Callable[[str, str, float], None]
is_expected_unavailable_library = engine_syntax_helpers.is_expected_unavailable_library
expected_unavailable_library_reason = engine_syntax_helpers.expected_unavailable_library_reason
_LOADER_CONFIG_KEYS = ("program_dir", "other_lib_dirs", "ABB_lib_dir", "mode", "scan_root_only", "debug")


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


@dataclass(frozen=True)
class SattLineProjectLoaderConfig:
    program_dir: Path
    other_lib_dirs: Sequence[Path]
    abb_lib_dir: Path
    mode: "CodeMode"
    scan_root_only: bool
    debug: bool
    use_file_ast_cache: bool = True
    refresh_mode: str = "full"

    def __post_init__(self) -> None:
        normalized_refresh_mode = str(self.refresh_mode).strip().lower() or "full"
        if normalized_refresh_mode not in {"full", "ast-only"}:
            raise ValueError(f"Unsupported refresh mode: {self.refresh_mode!r}")

        object.__setattr__(self, "program_dir", Path(self.program_dir))
        object.__setattr__(self, "other_lib_dirs", tuple(Path(path) for path in self.other_lib_dirs))
        object.__setattr__(self, "abb_lib_dir", Path(self.abb_lib_dir))
        object.__setattr__(self, "refresh_mode", normalized_refresh_mode)


@dataclass(frozen=True)
class SattLineProjectLoaderRuntime:
    contextual_lookup: ContextualFileLookup | None = None
    status_update_fn: Callable[[str], None] | None = None
    stage_timing_sink: LoadStageTimingSink | None = None
    graphics_timing_sink: GraphicsLoadTimingSink | None = None


@dataclass(frozen=True)
class SattLineProjectLoaderDependencies:
    cache_manager: cache_module.CacheManager | None = None


class _HasStringValue(Protocol):
    value: str


class _StructuredProjectLoaderFactory(Protocol):
    def __call__(
        self,
        config: SattLineProjectLoaderConfig,
        *,
        runtime: SattLineProjectLoaderRuntime,
        dependencies: SattLineProjectLoaderDependencies | None,
    ) -> "SattLineProjectLoader": ...


class _LegacyProjectLoaderFactory(Protocol):
    def __call__(self, **kwargs: object) -> "SattLineProjectLoader": ...


class _IntrospectableCallable(Protocol):
    def __call__(self, *args: object, **kwargs: object) -> object: ...


def _has_string_value(value: object) -> TypeGuard[_HasStringValue]:
    return isinstance(getattr(value, "value", None), str)


def _is_object_iterable(value: object) -> TypeGuard[Iterable[object]]:
    return isinstance(value, Iterable) and not isinstance(value, (str, bytes))


def _is_introspectable_callable(value: object) -> TypeGuard[_IntrospectableCallable]:
    return callable(value)


def _coerce_fspath_text(value: object) -> str | None:
    fspath_method = getattr(value, "__fspath__", None)
    if not callable(fspath_method):
        return None
    normalized_path = fspath_method()
    return normalized_path if isinstance(normalized_path, str) else None


def _coerce_path_config_value(value: object, *, key: str) -> Path:
    if isinstance(value, Path):
        return value
    if isinstance(value, str):
        return Path(value)
    normalized_path = _coerce_fspath_text(value)
    if normalized_path is not None:
        return Path(normalized_path)
    raise ValueError(f"Loader config key {key!r} must be path-like, got {type(value).__name__}")


def _coerce_path_sequence_config_value(value: object, *, key: str) -> tuple[Path, ...]:
    if not _is_object_iterable(value):
        raise ValueError(f"Loader config key {key!r} must be an iterable of path-like values")
    return tuple(_coerce_path_config_value(item, key=key) for item in value)


def _coerce_bool_config_value(value: object, *, key: str) -> bool:
    if isinstance(value, bool):
        return value
    raise ValueError(f"Loader config key {key!r} must be a bool, got {type(value).__name__}")


def _coerce_code_mode(value: object) -> "CodeMode":
    if value is None or isinstance(value, (str, engine_syntax_helpers.CodeMode)):
        normalized_mode = engine_syntax_helpers.normalize_code_mode(value)
    elif _has_string_value(value):
        normalized_mode = engine_syntax_helpers.normalize_code_mode(value.value)
    else:
        normalized_mode = None

    if normalized_mode is None:
        raise ValueError(f"Unsupported code mode: {value!r}")
    return normalized_mode


def _supports_structured_loader_init(loader_type: object) -> bool:
    if not _is_introspectable_callable(loader_type):
        return False
    try:
        parameters = list(inspect.signature(loader_type).parameters.values())
    except (TypeError, ValueError):
        return True
    if not parameters:
        return False
    first_parameter = parameters[0]
    return (
        first_parameter.kind
        in (
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
        )
        and first_parameter.name == "config"
    )


def _is_structured_project_loader_factory(value: object) -> TypeGuard[_StructuredProjectLoaderFactory]:
    return callable(value) and _supports_structured_loader_init(value)


def _is_legacy_project_loader_factory(value: object) -> TypeGuard[_LegacyProjectLoaderFactory]:
    return callable(value)


def _legacy_loader_kwargs(
    config: SattLineProjectLoaderConfig,
    runtime: SattLineProjectLoaderRuntime,
) -> dict[str, object]:
    return {
        "program_dir": config.program_dir,
        "other_lib_dirs": list(config.other_lib_dirs),
        "abb_lib_dir": config.abb_lib_dir,
        "mode": config.mode,
        "scan_root_only": config.scan_root_only,
        "debug": config.debug,
        "contextual_lookup": runtime.contextual_lookup,
        "use_file_ast_cache": config.use_file_ast_cache,
        "status_update_fn": runtime.status_update_fn,
        "refresh_mode": config.refresh_mode,
        "stage_timing_sink": runtime.stage_timing_sink,
        "graphics_timing_sink": runtime.graphics_timing_sink,
    }


def _instantiate_project_loader(
    loader_type: object,
    config: SattLineProjectLoaderConfig,
    *,
    runtime: SattLineProjectLoaderRuntime,
    dependencies: SattLineProjectLoaderDependencies | None,
) -> "SattLineProjectLoader":
    if _is_structured_project_loader_factory(loader_type):
        return loader_type(config, runtime=runtime, dependencies=dependencies)
    if _supports_structured_loader_init(loader_type):
        raise TypeError("Structured project loader type must be callable")
    if not _is_legacy_project_loader_factory(loader_type):
        raise TypeError("Legacy project loader type must be callable")
    return loader_type(**_legacy_loader_kwargs(config, runtime))


def validate_loader_config(cfg: Mapping[str, object]) -> None:
    missing_keys = [key for key in _LOADER_CONFIG_KEYS if key not in cfg]
    if missing_keys:
        raise ValueError(f"Missing loader config keys: {', '.join(missing_keys)}")


def build_project_loader(
    cfg: Mapping[str, object],
    *,
    contextual_lookup: ContextualFileLookup | None = None,
    use_file_ast_cache: bool = True,
    status_update_fn: Callable[[str], None] | None = None,
    refresh_mode: str = "full",
    stage_timing_sink: LoadStageTimingSink | None = None,
    graphics_timing_sink: GraphicsLoadTimingSink | None = None,
    scan_root_only: bool | None = None,
    dependencies: SattLineProjectLoaderDependencies | None = None,
) -> "SattLineProjectLoader":
    validate_loader_config(cfg)

    program_dir = _coerce_path_config_value(cfg["program_dir"], key="program_dir")
    other_lib_dirs = _coerce_path_sequence_config_value(cfg["other_lib_dirs"], key="other_lib_dirs")
    abb_lib_dir = _coerce_path_config_value(cfg["ABB_lib_dir"], key="ABB_lib_dir")
    mode = _coerce_code_mode(cfg["mode"])
    configured_scan_root_only = _coerce_bool_config_value(cfg["scan_root_only"], key="scan_root_only")
    debug = _coerce_bool_config_value(cfg["debug"], key="debug")
    selected_scan_root_only = configured_scan_root_only if scan_root_only is None else scan_root_only

    config = SattLineProjectLoaderConfig(
        program_dir=program_dir,
        other_lib_dirs=other_lib_dirs,
        abb_lib_dir=abb_lib_dir,
        mode=mode,
        scan_root_only=selected_scan_root_only,
        debug=debug,
        use_file_ast_cache=use_file_ast_cache,
        refresh_mode=refresh_mode,
    )
    runtime = SattLineProjectLoaderRuntime(
        contextual_lookup=contextual_lookup,
        status_update_fn=status_update_fn,
        stage_timing_sink=stage_timing_sink,
        graphics_timing_sink=graphics_timing_sink,
    )

    return _instantiate_project_loader(
        SattLineProjectLoader,
        config,
        runtime=runtime,
        dependencies=dependencies,
    )


def load_project_graph(
    cfg: Mapping[str, object],
    target_name: str,
    *,
    contextual_lookup: ContextualFileLookup | None = None,
    use_file_ast_cache: bool = True,
    status_update_fn: Callable[[str], None] | None = None,
    refresh_mode: str = "full",
    stage_timing_sink: LoadStageTimingSink | None = None,
    graphics_timing_sink: GraphicsLoadTimingSink | None = None,
    scan_root_only: bool | None = None,
    dependencies: SattLineProjectLoaderDependencies | None = None,
    strict: bool = False,
) -> tuple["SattLineProjectLoader", BasePicture | None, ProjectGraph]:
    loader = build_project_loader(
        cfg,
        contextual_lookup=contextual_lookup,
        use_file_ast_cache=use_file_ast_cache,
        status_update_fn=status_update_fn,
        refresh_mode=refresh_mode,
        stage_timing_sink=stage_timing_sink,
        graphics_timing_sink=graphics_timing_sink,
        scan_root_only=scan_root_only,
        dependencies=dependencies,
    )
    graph = loader.resolve(target_name, strict=strict)
    root_bp = graph.ast_by_name.get(target_name)
    return loader, root_bp, graph


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


SyntaxValidationResult = engine_syntax_helpers.SyntaxValidationResult


@dataclass(frozen=True)
class _PrefetchedDependencyCandidate:
    name: str
    requester_dir: Path | None
    code_path: Path | None
    deps_path: Path | None


@dataclass(frozen=True)
class _PrefetchedLoadResult:
    basepicture: BasePicture
    load_or_parse_duration_s: float
    ast_cache_save_required: bool


CodeMode = engine_syntax_helpers.CodeMode
code_ext = engine_syntax_helpers.code_ext
deps_ext = engine_syntax_helpers.deps_ext
graphics_ext = engine_syntax_helpers.graphics_ext
graphics_ext_candidates = engine_syntax_helpers.graphics_ext_candidates
normalize_code_mode = engine_syntax_helpers.normalize_code_mode


_normalize_code_mode = normalize_code_mode
_graphics_validation_to_syntax_result = engine_syntax_helpers.graphics_validation_to_syntax_result
_record_project_failure = engine_syntax_helpers.record_project_failure
_record_project_warning = engine_syntax_helpers.record_project_warning
_format_debug_list = engine_syntax_helpers.format_debug_list
_format_debug_missing_entries = engine_syntax_helpers.format_debug_missing_entries


BASE_DIR = Path(__file__).resolve().parent


class DebugMixin:
    debug: bool = False

    def dbg(self, msg: str) -> None:
        if self.debug:
            lines = str(msg).splitlines() or [""]
            for line in lines:
                log.debug(f"[DEBUG] {line}")


is_within_directory = engine_syntax_helpers.is_within_directory
_is_within_directory = is_within_directory


create_sl_parser = engine_syntax_helpers.create_sl_parser
_LOCAL_VALIDATION_MARKER_ATTR = engine_syntax_helpers.LOCAL_VALIDATION_MARKER_ATTR
_ENGINE_PUBLIC_REEXPORTS = (ValidationNotice, LOCAL_STRUCTURE_VALIDATION_SCHEMA_VERSION)


def _load_source_text(
    code_path: Path,
    *,
    debug: Callable[[str], None] | None = None,
) -> str:
    return engine_syntax_helpers.load_source_text(
        code_path,
        debug=debug,
        read_text_with_fallback_fn=read_text_with_fallback,
        is_compressed_fn=is_compressed,
        preprocess_sl_text_fn=preprocess_sl_text,
    )


def parse_source_text(
    src: str,
    *,
    parser: Lark | None = None,
    transformer: SLTransformer | None = None,
    debug: Callable[[str], None] | None = None,
) -> BasePicture:
    return engine_syntax_helpers.parse_source_text(
        src,
        parser=parser,
        transformer=transformer,
        debug=debug,
        parser_core_parse_source_text_fn=parser_core_parse_source_text,
        validate_transformed_basepicture_fn=validate_transformed_basepicture,
    )


def parse_source_file(
    code_path: Path,
    *,
    parser: Lark | None = None,
    transformer: SLTransformer | None = None,
    debug: Callable[[str], None] | None = None,
) -> BasePicture:
    return engine_syntax_helpers.parse_source_file(
        code_path,
        parser=parser,
        transformer=transformer,
        debug=debug,
        parser_core_parse_source_file_fn=parser_core_parse_source_file,
        validate_transformed_basepicture_fn=validate_transformed_basepicture,
    )


_has_current_local_validation = engine_syntax_helpers.has_current_local_validation
_mark_local_validation = engine_syntax_helpers.mark_local_validation


def _ensure_local_validation(
    basepic: BasePicture,
    *,
    warning_sink: list[ValidationWarning] | None = None,
) -> bool:
    return engine_syntax_helpers.ensure_local_validation(
        basepic,
        warning_sink=warning_sink,
        has_current_local_validation_fn=_has_current_local_validation,
        mark_local_validation_fn=_mark_local_validation,
        validate_transformed_basepicture_locally_fn=validate_transformed_basepicture_locally,
    )


_extract_error_position = engine_syntax_helpers.extract_error_position


def validate_single_file_syntax(
    code_path: Path,
    *,
    mode: CodeMode | str | None = None,
) -> SyntaxValidationResult:
    return engine_syntax_helpers.validate_single_file_syntax(
        code_path,
        mode=mode,
        load_source_text_fn=_load_source_text,
        find_disallowed_comments_fn=find_disallowed_comments,
        parser_core_parse_source_text_fn=parser_core_parse_source_text,
        validate_transformed_basepicture_fn=validate_transformed_basepicture,
        describe_parse_error_fn=describe_parse_error,
        validate_graphics_file_fn=validate_graphics_file,
        graphics_source_context_path_fn=_graphics_source_context_path,
        load_picture_display_source_context_fn=_load_picture_display_source_context,
        correlate_picture_display_records_fn=correlate_picture_display_records,
        picture_display_path_warnings_fn=_picture_display_path_warnings,
        resolve_graphics_companion_path_fn=resolve_graphics_companion_path,
        extract_error_position_fn=_extract_error_position,
        graphics_validation_to_syntax_result_fn=_graphics_validation_to_syntax_result,
        coerce_validation_notice_fn=coerce_validation_notice,
    )


_raise_syntax_validation_failure = engine_syntax_helpers.raise_syntax_validation_failure


# ---------- Loader with recursive resolution ----------
class SattLineProjectLoader(DebugMixin):
    def __init__(
        self,
        config: SattLineProjectLoaderConfig,
        *,
        runtime: SattLineProjectLoaderRuntime | None = None,
        dependencies: SattLineProjectLoaderDependencies | None = None,
    ):
        selected_runtime = SattLineProjectLoaderRuntime() if runtime is None else runtime
        selected_dependencies = SattLineProjectLoaderDependencies() if dependencies is None else dependencies
        self.config = config
        self.program_dir = config.program_dir
        self.other_lib_dirs = list(config.other_lib_dirs)
        self.abb_lib_dir = config.abb_lib_dir
        self.mode = config.mode
        self.scan_root_only = config.scan_root_only
        self.debug = config.debug
        self.contextual_lookup = selected_runtime.contextual_lookup
        self.use_file_ast_cache = config.use_file_ast_cache
        self._status_update_fn = selected_runtime.status_update_fn
        self.refresh_mode = config.refresh_mode
        self._stage_timing_sink = selected_runtime.stage_timing_sink
        self._graphics_timing_sink = selected_runtime.graphics_timing_sink
        self._last_status_message: str | None = None
        self.parser = create_sl_parser()  # reuse your grammar setup
        self.transformer = SLTransformer()  # reuse your transformer
        self._visited: set[str] = set()
        self._visit_stack: list[str] = []  # ordered stack for cycle detection and path reporting
        self._ignored_dirs: set[Path] = set()
        if selected_dependencies.cache_manager is None:
            self._cache_dir = get_cache_dir()
            self._cache_manager = cache_module.get_cache_manager(
                self._cache_dir,
                file_lookup_cache_cls=FileLookupCache,
                file_ast_cache_cls=FileASTCache,
            )
        else:
            self._cache_manager = selected_dependencies.cache_manager
            self._cache_dir = self._cache_manager.cache_dir
        self._lookup_cache = self._cache_manager.file_lookup_cache
        self._ast_cache = self._cache_manager.file_ast_cache
        self._base_indexes: dict[Path, dict[str, dict[str, Path]]] = {}
        self._lib_by_name: dict[str, str] = {}
        self._prefetched_dependency_candidates: dict[tuple[str, str | None], _PrefetchedDependencyCandidate] = {}
        self._prefetched_load_results_by_path: dict[Path, _PrefetchedLoadResult] = {}
        self.dbg(f"Selected mode={self.mode.value}, code_ext={code_ext(self.mode)}, deps_ext={deps_ext(self.mode)}")
        self.dbg(f"Programs dir: {self.program_dir}")
        for i, ld in enumerate(self.other_lib_dirs, start=1):
            self.dbg(f"Lib {i}: {ld}")
        self.dbg(f"ABB lib dir: {self.abb_lib_dir}")

    def _record_stage_timing(self, owner_name: str, stage: str, started_at: float) -> None:
        if self._stage_timing_sink is None:
            return
        self._stage_timing_sink(owner_name, stage, perf_counter() - started_at)

    def _record_stage_duration(self, owner_name: str, stage: str, duration: float) -> None:
        if self._stage_timing_sink is None:
            return
        self._stage_timing_sink(owner_name, stage, duration)

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

    def _resolved_lookup_path(self, path: Path | None) -> Path | None:
        if path is None:
            return None
        try:
            return path.resolve()
        except OSError:
            return path

    def _lookup_path_key(self, path: Path) -> str:
        return str(self._resolved_lookup_path(path)).casefold()

    def _lookup_source_dirs(self) -> tuple[Path, ...]:
        return (self.program_dir, *self.other_lib_dirs, self.abb_lib_dir)

    def _is_lookup_relative_to(self, path: Path | None, root: Path | None) -> bool:
        resolved_path = self._resolved_lookup_path(path)
        resolved_root = self._resolved_lookup_path(root)
        if resolved_path is None or resolved_root is None:
            return False
        try:
            resolved_path.relative_to(resolved_root)
        except ValueError:
            return False
        return True

    def _first_lookup_branch_under(self, root: Path, path: Path) -> str | None:
        resolved_root = self._resolved_lookup_path(root)
        resolved_path = self._resolved_lookup_path(path)
        if resolved_root is None or resolved_path is None:
            return None
        try:
            relative_parts = resolved_path.relative_to(resolved_root).parts
        except ValueError:
            return None
        return relative_parts[0] if relative_parts else None

    def _shared_lookup_root_for(self, requester_dir: Path | None) -> Path | None:
        requester = self._resolved_lookup_path(requester_dir)
        if requester is None:
            return None

        candidate_dirs = [
            resolved
            for source_dir in self._lookup_source_dirs()
            if (resolved := self._resolved_lookup_path(source_dir)) is not None and resolved != requester
        ]
        current = requester
        while True:
            branches: set[str] = set()
            for source_dir in candidate_dirs:
                if not self._is_lookup_relative_to(source_dir, current):
                    continue
                branch = self._first_lookup_branch_under(current, source_dir)
                if branch is None:
                    continue
                branches.add(branch)
                if len(branches) > 1:
                    return current
            parent = current.parent
            if parent == current:
                break
            current = parent

        return None

    def _ordered_lookup_bases(self, requester_dir: Path | None) -> tuple[Path, ...]:
        requester = self._resolved_lookup_path(requester_dir)
        abb_dir = self._resolved_lookup_path(self.abb_lib_dir)
        ordered: list[Path] = []
        seen: set[str] = set()

        def add(path: Path | None) -> None:
            resolved = self._resolved_lookup_path(path)
            if resolved is None or self._is_ignored_base(resolved):
                return
            key = self._lookup_path_key(resolved)
            if key in seen:
                return
            seen.add(key)
            ordered.append(resolved)

        if requester is not None and self._is_allowed_base(requester):
            add(requester)

        cluster_root = self._shared_lookup_root_for(requester)
        if cluster_root is not None and requester is not None:
            requester_branch = self._first_lookup_branch_under(cluster_root, requester)
            same_branch: list[Path] = []
            sibling_branch: list[Path] = []
            for source_dir in self._lookup_source_dirs():
                resolved = self._resolved_lookup_path(source_dir)
                if resolved is None or resolved in (requester, abb_dir):
                    continue
                if not self._is_lookup_relative_to(resolved, cluster_root):
                    continue
                branch = self._first_lookup_branch_under(cluster_root, resolved)
                if requester_branch is not None and branch == requester_branch:
                    same_branch.append(resolved)
                else:
                    sibling_branch.append(resolved)
            for source_dir in sorted(same_branch, key=self._lookup_path_key):
                add(source_dir)
            for source_dir in sorted(sibling_branch, key=self._lookup_path_key):
                add(source_dir)

        for source_dir in self._lookup_source_dirs():
            resolved = self._resolved_lookup_path(source_dir)
            if resolved == abb_dir:
                continue
            add(resolved)

        add(abb_dir)
        return tuple(ordered)

    def _find_in_ordered_bases_without_cache(
        self,
        name: str,
        extensions: list[str],
        *,
        requester_dir: Path | None,
        kind: str,
    ) -> Path | None:
        for base in self._ordered_lookup_bases(requester_dir):
            indexed = self._find_in_index(base=base, name=name, extensions=extensions)
            if indexed is not None:
                self.dbg(f"Using ordered lookup file: {indexed}")
                set_cache = getattr(self._lookup_cache, "set", None)
                if callable(set_cache):
                    set_cache(kind, name, self.mode.value, base, indexed.suffix.lower())
                return indexed

            for ext in extensions:
                candidate = base / f"{name}{ext}"
                self.dbg(f"Checking ordered lookup file: {candidate} (exists={candidate.exists()})")
                if candidate.exists():
                    self.dbg(f"Using ordered lookup file: {candidate}")
                    set_cache = getattr(self._lookup_cache, "set", None)
                    if callable(set_cache):
                        set_cache(kind, name, self.mode.value, base, ext)
                    self._add_to_index(base, name, candidate)
                    return candidate

        return None

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
        prefetched = self._prefetched_dependency_candidates.get(self._prefetched_dependency_key(name, requester_dir))
        if prefetched is not None and prefetched.code_path is not None:
            return prefetched.code_path

        extensions = [code_ext(self.mode), ".x"] if self.mode == CodeMode.DRAFT else [code_ext(self.mode)]

        if self.contextual_lookup is not None:
            resolved = self.contextual_lookup(name, extensions, requester_dir, "code")
            if resolved is not None:
                self.dbg(f"Using contextual code file: {resolved} (requested by {requester_dir or self.program_dir})")
                return resolved

        ordered = self._find_in_ordered_bases_without_cache(
            name,
            extensions,
            requester_dir=requester_dir,
            kind="code",
        )
        if ordered is not None:
            return ordered

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

    def _find_deps_with_context(
        self,
        name: str,
        *,
        requester_dir: Path | None,
    ) -> Path | None:
        prefetched = self._prefetched_dependency_candidates.get(self._prefetched_dependency_key(name, requester_dir))
        if prefetched is not None and prefetched.deps_path is not None:
            return prefetched.deps_path

        extensions = [deps_ext(self.mode), ".z"] if self.mode == CodeMode.DRAFT else [deps_ext(self.mode)]

        if self.contextual_lookup is not None:
            resolved = self.contextual_lookup(name, extensions, requester_dir, "deps")
            if resolved is not None:
                self.dbg(f"Using contextual deps file: {resolved} (requested by {requester_dir or self.program_dir})")
                return resolved

        ordered = self._find_in_ordered_bases_without_cache(
            name,
            extensions,
            requester_dir=requester_dir,
            kind="deps",
        )
        if ordered is not None:
            return ordered

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

    def find_dependency_path(
        self,
        name: str,
        *,
        requester_dir: Path | None,
    ) -> Path | None:
        return self._find_deps_with_context(name, requester_dir=requester_dir)

    def _find_vendor_code(self, name: str) -> Path | None:
        """Find code file in vendor directories with fallback."""
        extensions = [code_ext(self.mode), ".x"] if self.mode == CodeMode.DRAFT else [code_ext(self.mode)]

        for ign in self._ignored_dirs:
            for ext in extensions:
                p = ign / f"{name}{ext}"
                if p.exists():
                    return p
        return None

    def _find_vendor_deps(self, name: str) -> Path | None:
        """Find deps file in vendor directories with fallback."""
        extensions = [deps_ext(self.mode), ".z"] if self.mode == CodeMode.DRAFT else [deps_ext(self.mode)]

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

    def read_dependency_names(self, deps_path: Path) -> list[str]:
        return self._read_deps(deps_path)

    def visit_target(
        self,
        target_name: str,
        graph: ProjectGraph,
        syntax_only: bool,
        *,
        requester_dir: Path | None,
        syntax_check: bool,
    ) -> None:
        self._visit(
            target_name,
            graph,
            syntax_only,
            requester_dir=requester_dir,
            syntax_check=syntax_check,
        )

    def flush_lookup_cache(self) -> None:
        self._flush_lookup_cache()

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

    def _dependency_library_name(
        self,
        graph: ProjectGraph,
        dependency_name: str,
        dep_bp: BasePicture | None,
    ) -> str | None:
        root_library_name_for_name = getattr(graph, "root_library_name_for_name", None)
        if callable(root_library_name_for_name):
            graph_library_name = root_library_name_for_name(dependency_name)
            if isinstance(graph_library_name, str) and graph_library_name:
                return graph_library_name

        cached_lib = self._lib_by_name.get(dependency_name.casefold())
        if cached_lib:
            return cached_lib

        origin_lib = getattr(dep_bp, "origin_lib", None) if dep_bp is not None else None
        return origin_lib if isinstance(origin_lib, str) and origin_lib else None

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
        prefetched_result = self._prefetched_load_results_by_path.pop(code_path, None)
        if prefetched_result is not None:
            if prefetched_result.ast_cache_save_required:
                cache_save_started_at = perf_counter()
                self._ast_cache.save(code_path, self.mode.value, prefetched_result.basepicture)
                self._record_stage_timing(resolved_owner_name, "ast_cache_save", cache_save_started_at)
            self._record_stage_duration(
                resolved_owner_name,
                "load_or_parse",
                prefetched_result.load_or_parse_duration_s,
            )
            return prefetched_result.basepicture
        if self.use_file_ast_cache:
            cached = self._ast_cache.load(code_path, self.mode.value)
            if isinstance(cached, BasePicture):
                upgraded_cache_entry = _ensure_local_validation(cached)
                if upgraded_cache_entry:
                    cache_save_started_at = perf_counter()
                    self._ast_cache.save(code_path, self.mode.value, cached)
                    self._record_stage_timing(resolved_owner_name, "ast_cache_save", cache_save_started_at)
                self._update_status(f"Loading {code_path.stem}: using cached AST from {code_path.name}")
                self.dbg(f"Using cached AST for: {code_path}")
                self._record_stage_timing(resolved_owner_name, "load_or_parse", started_at)
                return cached

        self._update_status(f"Loading {code_path.stem}: parsing {code_path.name}")
        bp = self._parse_one(code_path)
        if self.refresh_mode == "ast-only":
            _ensure_local_validation(bp)
        cache_save_started_at = perf_counter()
        self._ast_cache.save(code_path, self.mode.value, bp)
        self._record_stage_timing(resolved_owner_name, "ast_cache_save", cache_save_started_at)
        self._record_stage_timing(resolved_owner_name, "load_or_parse", started_at)
        return bp

    def _prefetched_dependency_key(self, name: str, requester_dir: Path | None) -> tuple[str, str | None]:
        requester_key = None if requester_dir is None else str(requester_dir)
        return name.casefold(), requester_key.casefold() if requester_key is not None else None

    def _prime_base_indexes(self) -> None:
        for base in [self.program_dir, *self.other_lib_dirs, self.abb_lib_dir]:
            self._get_base_index(base)

    def _find_in_bases_without_cache(self, name: str, extensions: list[str]) -> Path | None:
        for base in [self.program_dir, *self.other_lib_dirs, self.abb_lib_dir]:
            if self._is_ignored_base(base):
                continue

            index = self._base_indexes.get(base, {})
            entries = index.get(name.casefold())
            if entries:
                for ext in extensions:
                    indexed = entries.get(ext)
                    if indexed is not None:
                        return indexed

            for ext in extensions:
                candidate = base / f"{name}{ext}"
                if candidate.exists():
                    return candidate

        return None

    def _prefetch_ast_candidates(self, code_paths: list[Path]) -> dict[Path, _PrefetchedLoadResult]:
        if not self.use_file_ast_cache or len(code_paths) < 2:
            return {}

        prefetched: dict[Path, _PrefetchedLoadResult] = {}
        for code_path in code_paths:
            started_at = perf_counter()
            cached = self._ast_cache.load(code_path, self.mode.value)
            if not isinstance(cached, BasePicture):
                continue
            save_required = _ensure_local_validation(cached)
            prefetched[code_path] = _PrefetchedLoadResult(
                basepicture=cached,
                load_or_parse_duration_s=perf_counter() - started_at,
                ast_cache_save_required=save_required,
            )
        return prefetched

    def _prefetch_dependency_candidates(self, dep_names: list[str], *, requester_dir: Path | None) -> None:
        if self.contextual_lookup is not None or len(dep_names) < 2:
            return

        unique_dep_names: list[str] = []
        seen: set[str] = set()
        for dep_name in dep_names:
            dep_key = dep_name.casefold()
            if dep_key in seen:
                continue
            seen.add(dep_key)
            unique_dep_names.append(dep_name)

        if len(unique_dep_names) < 2:
            return

        self._prime_base_indexes()
        code_extensions = [code_ext(self.mode), ".x"] if self.mode == CodeMode.DRAFT else [code_ext(self.mode)]
        deps_extensions = [deps_ext(self.mode), ".z"] if self.mode == CodeMode.DRAFT else [deps_ext(self.mode)]
        code_paths_to_prefetch: list[Path] = []
        for dep_name in unique_dep_names:
            code_path = self._find_in_ordered_bases_without_cache(
                dep_name,
                code_extensions,
                requester_dir=requester_dir,
                kind="code",
            )
            deps_path = self._find_in_ordered_bases_without_cache(
                dep_name,
                deps_extensions,
                requester_dir=requester_dir,
                kind="deps",
            )
            candidate = _PrefetchedDependencyCandidate(
                name=dep_name,
                requester_dir=requester_dir,
                code_path=code_path,
                deps_path=deps_path,
            )
            self._prefetched_dependency_candidates[
                self._prefetched_dependency_key(candidate.name, candidate.requester_dir)
            ] = candidate
            if code_path is not None:
                code_paths_to_prefetch.append(code_path)

        cached_prefetch_results = self._prefetch_ast_candidates(code_paths_to_prefetch)
        self._prefetched_load_results_by_path.update(cached_prefetch_results)

    def _load_or_parse_for_owner(self, code_path: Path, *, owner_name: str) -> BasePicture | None:
        return self._load_or_parse(code_path, owner_name=owner_name)

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
        validation_warnings: list[ValidationWarning] = []

        def _record_validation_warnings() -> None:
            for warning in validation_warnings:
                _record_project_warning(graph, root_name, warning)
            validation_warnings.clear()

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

            try:
                bp = self._load_or_parse_for_owner(code_path, owner_name=root_name)
            except Exception as ex:
                if strict:
                    raise
                _record_project_failure(graph, root_name, ex)
                return graph

            try:
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
                _record_validation_warnings()
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
                    timing_sink=self._graphics_timing_sink,
                ):
                    self._ast_cache.save(code_path, self.mode.value, bp)
                self._record_stage_timing(root_name, "attach_graphics", graphics_started_at)
                lib_name = self._record_library_name(root_name, code_path)
                self._update_status(f"Loading {root_name}: indexing definitions")
                index_started_at = perf_counter()
                graph.index_from_basepic(
                    bp, source_path=code_path, library_name=lib_name
                )  # collect any defs emitted in this files
                self._record_stage_timing(root_name, "index", index_started_at)
                return graph
            except Exception as ex:
                _record_validation_warnings()
                if strict:
                    raise
                _record_project_failure(graph, root_name, ex)
                return graph
        finally:
            self._flush_lookup_cache()

    def _visit(  # noqa: PLR0915
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
            self._prefetch_dependency_candidates(dep_names, requester_dir=dependency_requester)

            # Visit each dep
            for index, dep in enumerate(dep_names, start=1):
                self._update_status(f"Loading {name}: resolving dependency {index}/{len(dep_names)} {dep}")
                self._visit(dep, graph, strict, requester_dir=dependency_requester, syntax_check=syntax_check)

            dep_libs: list[str] = []
            for dep in dep_names:
                dep_bp = graph.ast_by_name.get(dep)
                dependency_library_name = self._dependency_library_name(graph, dep, dep_bp)
                if dependency_library_name:
                    dep_libs.append(dependency_library_name)

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
                        if key != root_key and _has_current_local_validation(bp):
                            validate_transformed_basepicture_dependency_context(
                                bp,
                                external_datatypes=()
                                if self.refresh_mode == "ast-only"
                                else tuple(graph.datatype_defs.values()),
                                external_moduletype_defs=()
                                if self.refresh_mode == "ast-only"
                                else tuple(graph.moduletype_defs.values()),
                                allow_parameterless_module_mappings=True,
                                warn_unknown_parameter_targets=self.refresh_mode != "ast-only",
                                warn_incompatible_parameter_mappings=self.refresh_mode != "ast-only",
                                warning_sink=validation_warnings.append,
                            )
                        else:
                            validate_transformed_basepicture(
                                bp,
                                external_datatypes=()
                                if self.refresh_mode == "ast-only"
                                else tuple(graph.datatype_defs.values()),
                                external_moduletype_defs=()
                                if self.refresh_mode == "ast-only"
                                else tuple(graph.moduletype_defs.values()),
                                allow_unresolved_external_datatypes=True
                                if self.refresh_mode == "ast-only"
                                else not strict,
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
                        timing_sink=self._graphics_timing_sink,
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
    from datetime import datetime  # noqa: PLC0415

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
    from datetime import datetime  # noqa: PLC0415

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
    from datetime import datetime  # noqa: PLC0415

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
