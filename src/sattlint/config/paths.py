"""Filesystem path helpers for SattLint configuration."""

from __future__ import annotations

import os
from pathlib import Path


def get_config_path() -> Path:
    if os.name == "nt":
        appdata = os.environ.get("APPDATA")
        base = Path(appdata) if appdata is not None else Path.home() / "AppData" / "Roaming"
    else:
        xdg_config_home = os.environ.get("XDG_CONFIG_HOME")
        base = Path(xdg_config_home) if xdg_config_home is not None else Path.home() / ".config"

    cfg_dir = base / "sattlint"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    return cfg_dir / "config.toml"


def get_projects_dir() -> Path:
    """Return the directory where project (.slproj) files are stored.

    On Windows this is ``%APPDATA%\\sattlint\\projects``; elsewhere it is
    ``~/.config/sattlint/projects`` (honoring ``XDG_CONFIG_HOME``). The
    directory is created if it does not exist.
    """
    if os.name == "nt":
        appdata = os.environ.get("APPDATA")
        base = Path(appdata) if appdata is not None else Path.home() / "AppData" / "Roaming"
    else:
        xdg_config_home = os.environ.get("XDG_CONFIG_HOME")
        base = Path(xdg_config_home) if xdg_config_home is not None else Path.home() / ".config"

    projects_dir = base / "sattlint" / "projects"
    projects_dir.mkdir(parents=True, exist_ok=True)
    return projects_dir
