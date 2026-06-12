"""Filesystem path helpers for SattLint configuration."""

from __future__ import annotations

import os
from pathlib import Path


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
