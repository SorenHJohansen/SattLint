"""Config coercion and parser-binding construction for project loading.

Builds the ``ParserProjectBinding`` the project-loading application seams feed
into :mod:`sattlint.project.parser_adapter`, plus the timing-helper aliases and
cfg validation shared by the loader facade (``sattlint.engine``).
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable, Mapping
from pathlib import Path
from typing import Protocol, TypeGuard

from ..core.syntax import CodeMode, normalize_code_mode
from .parser_adapter import ParserProjectBinding

LoadStageTimingSink = Callable[[str, str, float], None]
GraphicsLoadTimingSink = Callable[[str, str, float], None]
_LOADER_CONFIG_KEYS = ("program_dir", "other_lib_dirs", "ABB_lib_dir", "mode", "debug")

log = logging.getLogger("SattLint")


def _make_debug_fn(enabled: bool) -> Callable[[str], None] | None:
    if not enabled:
        return None

    def debug_fn(msg: str) -> None:
        for line in str(msg).splitlines() or [""]:
            log.debug(f"[DEBUG] {line}")

    return debug_fn


class _HasStringValue(Protocol):
    value: str


def _has_string_value(value: object) -> TypeGuard[_HasStringValue]:
    return isinstance(getattr(value, "value", None), str)


def _is_object_iterable(value: object) -> TypeGuard[Iterable[object]]:
    return isinstance(value, Iterable) and not isinstance(value, (str, bytes))


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
    if value is None or isinstance(value, (str, CodeMode)):
        normalized_mode = normalize_code_mode(value)
    elif _has_string_value(value):
        normalized_mode = normalize_code_mode(value.value)
    else:
        normalized_mode = None

    if normalized_mode is None:
        raise ValueError(f"Unsupported code mode: {value!r}")
    return normalized_mode


def validate_loader_config(cfg: Mapping[str, object]) -> None:
    missing_keys = [key for key in _LOADER_CONFIG_KEYS if key not in cfg]
    if missing_keys:
        raise ValueError(f"Missing loader config keys: {', '.join(missing_keys)}")


def build_parser_binding(
    cfg: Mapping[str, object],
    *,
    status_update_fn: Callable[[str], None] | None = None,
    refresh_mode: str = "full",
    stage_timing_sink: LoadStageTimingSink | None = None,
    graphics_timing_sink: GraphicsLoadTimingSink | None = None,
) -> ParserProjectBinding:
    validate_loader_config(cfg)

    program_dir = _coerce_path_config_value(cfg["program_dir"], key="program_dir")
    other_lib_dirs = _coerce_path_sequence_config_value(cfg["other_lib_dirs"], key="other_lib_dirs")
    raw_abb_lib_dir = cfg.get("ABB_lib_dir")
    abb_lib_dir = (
        None
        if raw_abb_lib_dir is None or not str(raw_abb_lib_dir).strip()
        else _coerce_path_config_value(raw_abb_lib_dir, key="ABB_lib_dir")
    )
    mode = _coerce_code_mode(cfg["mode"])
    debug = _coerce_bool_config_value(cfg["debug"], key="debug")
    normalized_refresh_mode = str(refresh_mode).strip().lower() or "full"
    if normalized_refresh_mode not in {"full", "ast-only"}:
        raise ValueError(f"Unsupported refresh mode: {refresh_mode!r}")

    return ParserProjectBinding(
        program_dir=program_dir,
        other_lib_dirs=other_lib_dirs,
        abb_lib_dir=abb_lib_dir,
        mode=mode,
        refresh_mode=normalized_refresh_mode,
        debug_fn=_make_debug_fn(debug),
        status_update_fn=status_update_fn,
        stage_timing_sink=stage_timing_sink,
        graphics_timing_sink=graphics_timing_sink,
    )
