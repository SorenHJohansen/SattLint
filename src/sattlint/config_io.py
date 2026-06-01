"""Filesystem and TOML helpers for SattLint configuration."""

from __future__ import annotations

import os
import re
import tomllib
from copy import deepcopy
from pathlib import Path
from typing import Any, cast

import tomli_w

from . import console as console_module
from .config_validation import DEFAULT_CONFIG, deep_merge_dict, normalize_documentation_rule_keys, validate_config

emit_output = console_module.print_output


def _strip_legacy_telemetry_path(existing_text: str) -> str:
    lines = existing_text.splitlines()
    if not lines:
        return existing_text

    normalized_lines: list[str] = []
    in_telemetry = False
    removed = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            in_telemetry = stripped == "[telemetry]"
        elif in_telemetry and re.fullmatch(r"path\s*=\s*.*", stripped):
            removed = True
            continue
        normalized_lines.append(line)

    if not removed:
        return existing_text

    normalized_text = "\n".join(normalized_lines)
    if existing_text.endswith("\n"):
        normalized_text += "\n"
    return normalized_text


def _normalize_telemetry_section(path: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    existing_text = path.read_text(encoding="utf-8")
    normalized_text = _strip_legacy_telemetry_path(existing_text)

    if "telemetry" not in cfg:
        telemetry_block = "[telemetry]\nenabled = false\n"
        separator = ""
        if normalized_text:
            separator = "\n\n" if not normalized_text.endswith("\n") else "\n"
        path.write_text(f"{normalized_text}{separator}{telemetry_block}", encoding="utf-8")

        merged_cfg = dict(cfg)
        merged_cfg["telemetry"] = deepcopy(cast(dict[str, Any], DEFAULT_CONFIG["telemetry"]))
        return merged_cfg

    if normalized_text != existing_text:
        path.write_text(normalized_text, encoding="utf-8")

    telemetry = cfg.get("telemetry")
    if not isinstance(telemetry, dict) or "path" not in telemetry:
        return cfg

    merged_cfg = dict(cfg)
    normalized_telemetry = dict(cast(dict[str, Any], telemetry))
    normalized_telemetry.pop("path", None)
    merged_cfg["telemetry"] = normalized_telemetry
    return merged_cfg


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
        emit_output(f"⚠ No config found, creating default: {path}")
        cfg = deepcopy(DEFAULT_CONFIG)
        save_config(path, cfg)
        return cfg, True

    with path.open("rb") as file_handle:
        cfg = tomllib.load(file_handle)

    cfg = _normalize_telemetry_section(path, cfg)

    cfg = normalize_documentation_rule_keys(cfg)

    validation = validate_config(cfg)
    if not validation.passed:
        for error in validation.errors:
            emit_output(f"⚠ Config warning [{error.key_path}]: {error.message}")

    merged = deep_merge_dict(DEFAULT_CONFIG, cfg)
    merged.pop("ignore_ABB_lib", None)
    return merged, False


def save_config(path: Path, cfg: dict[str, Any]) -> None:
    sanitized_cfg = deepcopy(cfg)
    telemetry = sanitized_cfg.get("telemetry")
    if isinstance(telemetry, dict):
        cast(dict[str, Any], telemetry).pop("path", None)

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

    normalized_cfg = normalize(sanitized_cfg)
    if not isinstance(normalized_cfg, dict):
        raise ValueError("Config serialization must produce a table/object.")

    with path.open("wb") as file_handle:
        tomli_w.dump(cast(dict[str, Any], normalized_cfg), file_handle)
