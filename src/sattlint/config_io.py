"""Filesystem and TOML helpers for SattLint configuration."""

from __future__ import annotations

import tomllib
from copy import deepcopy
from pathlib import Path
from typing import Any, cast

import tomli_w

from . import _config_paths as _config_paths_module
from . import console as console_module
from .config_types import ConfigDict, ConfigObjectMap, ConfigOverrideDict
from .config_validation import (
    DEFAULT_CONFIG,
    deep_merge_dict,
    load_time_config_warnings,
    normalize_documentation_rule_keys,
    validate_effective_config,
)

emit_output = console_module.print_output


def _merged_effective_config(cfg: ConfigDict | ConfigOverrideDict) -> ConfigDict:
    merged = deep_merge_dict(cast(ConfigObjectMap, deepcopy(DEFAULT_CONFIG)), cast(ConfigObjectMap, cfg))
    merged.pop("ignore_ABB_lib", None)
    return cast(ConfigDict, merged)


def _validation_messages(cfg: ConfigDict | ConfigOverrideDict) -> tuple[str, ...]:
    validation = validate_effective_config(_merged_effective_config(cfg))
    return tuple(f"[{error.key_path}] {error.message}" for error in validation.errors)


def _normalize_telemetry_section(cfg: ConfigOverrideDict) -> ConfigOverrideDict:
    telemetry = cfg.get("telemetry")
    if not isinstance(telemetry, dict) or "path" not in telemetry:
        return cfg

    merged_cfg = dict(cast(ConfigObjectMap, cfg))
    normalized_telemetry = dict(cast(dict[str, Any], telemetry))
    normalized_telemetry.pop("path", None)
    merged_cfg["telemetry"] = normalized_telemetry
    return cast(ConfigOverrideDict, merged_cfg)


def get_config_path() -> Path:
    return _config_paths_module.get_config_path()


def get_graphics_rules_path(config_path: Path | None = None) -> Path:
    return _config_paths_module.get_graphics_rules_path(config_path)


def load_config(path: Path) -> tuple[ConfigDict, bool]:
    if not path.exists():
        emit_output(f"⚠ No config found, creating default: {path}")
        cfg = cast(ConfigDict, deepcopy(DEFAULT_CONFIG))
        save_config(path, cfg)
        return cfg, True

    with path.open("rb") as file_handle:
        cfg = cast(ConfigOverrideDict, tomllib.load(file_handle))

    for warning in load_time_config_warnings(cfg):
        emit_output(f"⚠ Config warning [{warning.key_path}]: {warning.message}")

    cfg = normalize_documentation_rule_keys(cfg)
    normalized_cfg = _normalize_telemetry_section(cfg)

    for message in _validation_messages(normalized_cfg):
        key_path, error_message = message.split("] ", maxsplit=1)
        emit_output(f"⚠ Config warning {key_path}]: {error_message}")

    return _merged_effective_config(normalized_cfg), False


def save_config(path: Path, cfg: ConfigDict | ConfigOverrideDict) -> None:
    sanitized_cfg_obj = cast(object, deepcopy(cast(ConfigObjectMap, cfg)))
    if not isinstance(sanitized_cfg_obj, dict):
        raise ValueError("Config serialization must produce a table/object.")
    sanitized_cfg: ConfigObjectMap = cast(ConfigObjectMap, sanitized_cfg_obj)
    telemetry = sanitized_cfg.get("telemetry")
    if isinstance(telemetry, dict):
        cast(dict[str, Any], telemetry).pop("path", None)

    normalized_cfg = normalize_documentation_rule_keys(cast(ConfigOverrideDict, sanitized_cfg))
    validation_messages = _validation_messages(normalized_cfg)
    if validation_messages:
        raise ValueError("Config validation failed: " + "; ".join(validation_messages))

    def normalize(value: object) -> object:
        if isinstance(value, Path):
            return str(value)
        if isinstance(value, list):
            return [normalize(item) for item in cast(list[object], value)]
        if isinstance(value, tuple):
            return [normalize(item) for item in cast(tuple[object, ...], value)]
        if isinstance(value, dict):
            normalized_mapping = cast(dict[object, object], value)
            return {str(key): normalize(item) for key, item in normalized_mapping.items()}
        if value is None:
            raise ValueError("Cannot serialize None to TOML. Provide a default value or omit the key.")
        return value

    serializable_cfg = normalize(normalized_cfg)
    if not isinstance(serializable_cfg, dict):
        raise ValueError("Config serialization must produce a table/object.")

    with path.open("wb") as file_handle:
        tomli_w.dump(cast(dict[str, Any], serializable_cfg), file_handle)
