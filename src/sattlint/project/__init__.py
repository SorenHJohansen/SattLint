"""Project management for SattLint — the .slproj workflow."""

from __future__ import annotations

from .io import (
    SLPROJ_FILENAME,
    SLPROJ_VERSION,
    discover_project,
    init_project,
    load_project,
    project_status,
    save_project,
)
from .models import SattLineProject
from .types import DEFAULT_PROJECT_DICT, ProjectDict

__all__ = [
    "DEFAULT_PROJECT_DICT",
    "SLPROJ_FILENAME",
    "SLPROJ_VERSION",
    "ProjectDict",
    "SattLineProject",
    "discover_project",
    "init_project",
    "load_project",
    "project_status",
    "save_project",
]
