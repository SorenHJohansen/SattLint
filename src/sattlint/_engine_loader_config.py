"""Config and factory helpers for the SattLine project loader."""

from __future__ import annotations

import inspect
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, TypeGuard

from . import _engine_syntax_helpers as engine_syntax_helpers
from . import cache as cache_module

if TYPE_CHECKING:
    from ._engine_project_loader import SattLineProjectLoader


ContextualFileLookup = Callable[[str, list[str], Path | None, str], Path | None]
LoadStageTimingSink = Callable[[str, str, float], None]
GraphicsLoadTimingSink = Callable[[str, str, float], None]
_LOADER_CONFIG_KEYS = ("program_dir", "other_lib_dirs", "ABB_lib_dir", "mode", "scan_root_only", "debug")


@dataclass(frozen=True)
class SattLineProjectLoaderConfig:
    program_dir: Path
    other_lib_dirs: Sequence[Path]
    abb_lib_dir: Path
    mode: CodeMode
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
    ) -> SattLineProjectLoader: ...


class _LegacyProjectLoaderFactory(Protocol):
    def __call__(self, **kwargs: object) -> SattLineProjectLoader: ...


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


def _coerce_code_mode(value: object) -> CodeMode:
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
) -> SattLineProjectLoader:
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


CodeMode = engine_syntax_helpers.CodeMode


def build_project_loader_from_type(
    loader_type: object,
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
) -> SattLineProjectLoader:
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
        loader_type,
        config,
        runtime=runtime,
        dependencies=dependencies,
    )
