"""Filesystem path helpers for SattLint configuration."""

from __future__ import annotations

import os
from pathlib import Path


def get_config_path() -> Path:
    return get_config_dir() / "config.toml"


def _config_base_dir() -> Path:
    if os.name == "nt":
        appdata = os.environ.get("APPDATA")
        base = Path(appdata) if appdata is not None else Path.home() / "AppData" / "Roaming"
    else:
        xdg_config_home = os.environ.get("XDG_CONFIG_HOME")
        base = Path(xdg_config_home) if xdg_config_home is not None else Path.home() / ".config"
    return base / "sattlint"


def get_config_dir() -> Path:
    """The user configuration directory, created on demand."""
    cfg_dir = _config_base_dir()
    cfg_dir.mkdir(parents=True, exist_ok=True)
    return cfg_dir


def config_dir_location() -> Path:
    """The user configuration directory path without creating it."""
    return _config_base_dir()


def config_path_location() -> Path:
    """The user configuration file path without creating its directory."""
    return _config_base_dir() / "config.toml"


def get_projects_dir() -> Path:
    """Return the directory where project (.slproj) files are stored.

    On Windows this is ``%APPDATA%\\sattlint\\projects``; elsewhere it is
    ``~/.config/sattlint/projects`` (honoring ``XDG_CONFIG_HOME``). The
    directory is created if it does not exist.
    """
    projects_dir = get_config_dir() / "projects"
    projects_dir.mkdir(parents=True, exist_ok=True)
    return projects_dir


def get_change_review_dir() -> Path:
    """Return the default directory for generated Change Review artifacts.

    The directory sits alongside the user config (``~/.config/sattlint/change-review``
    or the equivalent per-platform location) and is created on demand.
    """
    review_dir = get_change_review_dir_location()
    review_dir.mkdir(parents=True, exist_ok=True)
    return review_dir


def get_change_review_dir_location() -> Path:
    """The default Change Review directory path without creating it."""
    return config_dir_location() / "change-review"


__all__ = [
    "config_dir_location",
    "config_path_location",
    "get_change_review_dir",
    "get_change_review_dir_location",
    "get_config_dir",
    "get_config_path",
    "get_projects_dir",
]
