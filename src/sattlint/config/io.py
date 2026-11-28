"""Filesystem and TOML helpers for SattLint configuration."""

from __future__ import annotations

import os
import tomllib
import uuid
from collections.abc import Callable
from contextlib import suppress
from copy import deepcopy
from pathlib import Path
from typing import Any, cast

import tomli_w

from .. import console as console_module
from . import paths as _config_paths_module
from .defaults import DEFAULT_CONFIG, VALID_TOP_LEVEL_CONFIG_KEYS
from .types import ConfigDict, ConfigObjectMap, ConfigOverrideDict
from .validation import (
    VALID_ANALYSIS_KEYS,
    VALID_OUTPUT_KEYS,
    VALID_REVIEW_KEYS,
    VALID_RUN_HISTORY_KEYS,
    VALID_STRING_CAPACITY_KEYS,
    ConfigValidationError,
    deep_merge_dict,
    load_time_config_warnings,
    strip_unknown_keys,
    validate_config,
    validate_effective_config,
)

emit_output = console_module.print_output

#: The configuration file schema this build reads and writes.
CONFIG_SCHEMA_VERSION = 1
#: The top-level key that records the configuration file schema version.
CONFIG_SCHEMA_VERSION_KEY = "schema_version"

#: Keys owned by the current build in each table that has a fixed contract.
_SECTION_VALID_KEYS: dict[str, frozenset[str]] = {
    "analysis": VALID_ANALYSIS_KEYS,
    "run_history": VALID_RUN_HISTORY_KEYS,
    "output": VALID_OUTPUT_KEYS,
    "review": VALID_REVIEW_KEYS,
    "string_capacities": VALID_STRING_CAPACITY_KEYS,
}


class ConfigVersionError(ValueError):
    """A configuration file declares a schema version this build cannot handle."""


def _merged_effective_config(cfg: ConfigDict | ConfigOverrideDict) -> ConfigDict:
    merged = deep_merge_dict(cast(ConfigObjectMap, deepcopy(DEFAULT_CONFIG)), cast(ConfigObjectMap, cfg))
    return cast(ConfigDict, merged)


def _validation_errors(cfg: ConfigDict | ConfigOverrideDict) -> tuple[ConfigValidationError, ...]:
    return validate_effective_config(_merged_effective_config(cfg)).errors


def _value_validation_errors(cfg: ConfigDict | ConfigOverrideDict) -> tuple[ConfigValidationError, ...]:
    """Validation that does not touch the filesystem.

    Saving settings must not fail because a configured directory is temporarily
    missing; the analysis preflight reports that at run time.
    """
    return validate_config(cast(ConfigOverrideDict, _merged_effective_config(cfg))).errors


def _validation_failure_message(errors: tuple[ConfigValidationError, ...]) -> str:
    return "Config validation failed: " + "; ".join(f"[{error.key_path}] {error.message}" for error in errors)


def _config_warning(error: ConfigValidationError) -> str:
    return f"⚠ Config warning [{error.key_path}]: {error.message}"


def get_config_path() -> Path:
    return _config_paths_module.get_config_path()


def _schema_version(payload: ConfigObjectMap, path: Path) -> int:
    """The schema version recorded in *payload*; a missing key means version 0."""
    value = payload.get(CONFIG_SCHEMA_VERSION_KEY)
    if value is None:
        return 0
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ConfigVersionError(
            f"Configuration file {path} has an invalid {CONFIG_SCHEMA_VERSION_KEY} {value!r}; "
            "expected a non-negative integer."
        )
    return value


def _newer_config_message(path: Path, version: int, *, for_save: bool) -> str:
    message = (
        f"Cannot {'save' if for_save else 'load'} configuration file {path}: "
        f"it declares schema version {version}, but this build supports version {CONFIG_SCHEMA_VERSION}."
    )
    if for_save:
        message += " Saving would discard settings this build does not understand."
    return f"{message} Upgrade SattLint to use this file, or move it aside to create a fresh configuration."


def _read_existing_config(path: Path) -> ConfigObjectMap | None:
    """The raw contents of an existing config file, if it can be read as TOML.

    A missing or unreadable file returns nothing. The caller then writes the
    configuration it was given, which is the only sane choice for a file that
    cannot be parsed.
    """
    if not path.exists():
        return None
    try:
        with path.open("rb") as file_handle:
            return cast(ConfigObjectMap, tomllib.load(file_handle))
    except (OSError, tomllib.TOMLDecodeError):
        return None


def _preserve_unknown_keys(incoming: ConfigObjectMap, existing: ConfigObjectMap) -> ConfigObjectMap:
    """Copy keys this build does not understand from *existing* into *incoming*.

    Known keys come from the caller, so a settings change still replaces them.
    Every other key in the file is carried over verbatim, including keys inside
    a table with a fixed contract. Saving therefore never deletes a setting a
    newer build wrote.
    """
    preserved = deepcopy(incoming)

    for key, value in existing.items():
        if key == CONFIG_SCHEMA_VERSION_KEY or key in VALID_TOP_LEVEL_CONFIG_KEYS:
            continue
        preserved.setdefault(key, deepcopy(value))

    for section_name, valid_keys in _SECTION_VALID_KEYS.items():
        existing_section = existing.get(section_name)
        if not isinstance(existing_section, dict):
            continue
        unknown = {
            key: deepcopy(value)
            for key, value in cast(ConfigObjectMap, existing_section).items()
            if key not in valid_keys
        }
        if not unknown:
            continue
        incoming_section = preserved.get(section_name)
        if isinstance(incoming_section, dict):
            incoming_map = cast(ConfigObjectMap, incoming_section)
            for key, value in unknown.items():
                incoming_map.setdefault(key, value)
        elif incoming_section is None:
            preserved[section_name] = unknown

    return preserved


def config_path_location() -> Path:
    return _config_paths_module.config_path_location()


def config_dir_location() -> Path:
    return _config_paths_module.config_dir_location()


def get_projects_dir() -> Path:
    return _config_paths_module.get_projects_dir()


def load_config(path: Path, *, emit_fn: Callable[[str], None] | None = None) -> tuple[ConfigDict, bool]:
    emit = emit_output if emit_fn is None else emit_fn
    if not path.exists():
        emit(f"⚠ No config found, creating default: {path}")
        cfg = cast(ConfigDict, deepcopy(DEFAULT_CONFIG))
        save_config(path, cfg)
        return cfg, True

    with path.open("rb") as file_handle:
        raw = cast(ConfigObjectMap, tomllib.load(file_handle))

    version = _schema_version(raw, path)
    if version > CONFIG_SCHEMA_VERSION:
        raise ConfigVersionError(_newer_config_message(path, version, for_save=False))
    # Version 0 files predate the version key and already have the version 1
    # key shape, so reading them with the current defaults is the whole
    # in-memory migration. A load never rewrites the file; the next save writes
    # the current version.
    raw.pop(CONFIG_SCHEMA_VERSION_KEY, None)
    cfg = cast(ConfigOverrideDict, raw)

    # Report unknown keys before stripping them, otherwise a typo vanishes silently.
    for warning in load_time_config_warnings(cfg):
        emit(f"⚠ Config warning [{warning.key_path}]: {warning.message}")

    strip_unknown_keys(cfg)

    # A wrong-typed value (``debug = "false"``, a string where a list belongs)
    # is a load error, not a warning: applying it produces a confusing failure
    # much later. Missing paths stay warnings; analysis reports those at run
    # time.
    value_errors = _value_validation_errors(cfg)
    if value_errors:
        raise ValueError(_validation_failure_message(value_errors))

    for error in _validation_errors(cfg):
        emit(_config_warning(error))

    return _merged_effective_config(cfg), False


def save_config(path: Path, cfg: ConfigDict | ConfigOverrideDict) -> None:
    sanitized_cfg_obj = cast(object, deepcopy(cast(ConfigObjectMap, cfg)))
    if not isinstance(sanitized_cfg_obj, dict):
        raise ValueError("Config serialization must produce a table/object.")
    sanitized_cfg: ConfigObjectMap = cast(ConfigObjectMap, sanitized_cfg_obj)
    # The version is this build's, not the caller's: a copy loaded from another
    # file must not carry that file's version into this one.
    sanitized_cfg.pop(CONFIG_SCHEMA_VERSION_KEY, None)

    validation_messages = _value_validation_errors(cast(ConfigOverrideDict, sanitized_cfg))
    if validation_messages:
        raise ValueError(_validation_failure_message(validation_messages))

    existing = _read_existing_config(path)
    if existing is not None:
        existing_version = _schema_version(existing, path)
        if existing_version > CONFIG_SCHEMA_VERSION:
            raise ConfigVersionError(_newer_config_message(path, existing_version, for_save=True))
        sanitized_cfg = _preserve_unknown_keys(sanitized_cfg, existing)

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

    serializable_cfg = normalize(sanitized_cfg)
    if not isinstance(serializable_cfg, dict):
        raise ValueError("Config serialization must produce a table/object.")
    serializable_map = cast(dict[str, Any], serializable_cfg)

    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f"{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    try:
        with temp_path.open("wb") as file_handle:
            tomli_w.dump({CONFIG_SCHEMA_VERSION_KEY: CONFIG_SCHEMA_VERSION, **serializable_map}, file_handle)
            file_handle.flush()
            os.fsync(file_handle.fileno())
        os.replace(temp_path, path)
    except OSError:
        with suppress(OSError):
            temp_path.unlink()
        raise


APP_LEVEL_CONFIG_KEYS: tuple[str, ...] = ("debug", "run_history", "output", "review")


def save_app_settings(path: Path, cfg: ConfigDict) -> None:
    """Persist only app-level settings, preserving everything else in the file.

    Loads the existing config file (or defaults when missing) and overwrites
    only the user-scoped app keys (``debug``, ``run_history``, ``output``), so
    writing app settings never pollutes a project file with project keys.
    Unknown/stale keys are dropped from this in-memory copy so validation sees
    only the current contract; :func:`save_config` re-reads the file and writes
    those keys back unchanged, so they are preserved on disk.
    """
    if path.exists():
        with path.open("rb") as file_handle:
            existing: ConfigObjectMap = cast(ConfigObjectMap, tomllib.load(file_handle))
    else:
        existing = cast(ConfigObjectMap, deepcopy(DEFAULT_CONFIG))

    existing.pop(CONFIG_SCHEMA_VERSION_KEY, None)
    strip_unknown_keys(cast(ConfigOverrideDict, existing))

    for key in APP_LEVEL_CONFIG_KEYS:
        if key in cfg:
            existing[key] = deepcopy(cast(ConfigObjectMap, cfg[key]))

    save_config(path, cast(ConfigDict, existing))
