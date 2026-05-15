"""Filesystem and TOML helpers for SattLint configuration."""

from __future__ import annotations

import os
import tomllib
from copy import deepcopy
from pathlib import Path
from typing import Any

import tomli_w

from .config_validation import DEFAULT_CONFIG, _deep_merge_dict, _normalize_documentation_rule_keys, validate_config


def get_config_path() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))

    cfg_dir = base / "sattlint"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    return cfg_dir / "config.toml"


def get_graphics_rules_path(config_path: Path | None = None) -> Path:
    resolved_config_path = config_path or get_config_path()
    return resolved_config_path.with_name("graphics_rules.json")


def load_config(path: Path) -> tuple[dict[str, Any], bool]:
    if not path.exists():
        print(f"⚠ No config found, creating default: {path}")
        cfg = deepcopy(DEFAULT_CONFIG)
        save_config(path, cfg)
        return cfg, True

    with path.open("rb") as file_handle:
        cfg = tomllib.load(file_handle)

    cfg = _normalize_documentation_rule_keys(cfg)

    validation = validate_config(cfg)
    if not validation.passed:
        for error in validation.errors:
            print(f"⚠ Config warning [{error.key_path}]: {error.message}")

    merged = _deep_merge_dict(DEFAULT_CONFIG, cfg)
    merged.pop("ignore_ABB_lib", None)
    return merged, False


def save_config(path: Path, cfg: dict[str, Any]) -> None:
    def normalize(value: Any) -> Any:
        if isinstance(value, Path):
            return str(value)
        if isinstance(value, list | tuple):
            return [normalize(item) for item in value]
        if isinstance(value, dict):
            return {key: normalize(item) for key, item in value.items()}
        if value is None:
            raise ValueError("Cannot serialize None to TOML. Provide a default value or omit the key.")
        return value

    with path.open("wb") as file_handle:
        tomli_w.dump(normalize(cfg), file_handle)
