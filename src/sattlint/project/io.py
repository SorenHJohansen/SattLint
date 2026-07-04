"""Load, save, discover, and scaffold .slproj project files."""

from __future__ import annotations

import tomllib
from copy import deepcopy
from pathlib import Path
from typing import Any, cast

import tomli_w

from ..config_types import ConfigObjectMap
from .models import SattLineProject
from .types import DEFAULT_PROJECT_DICT, ProjectDict

SLPROJ_FILENAME = ".slproj"
SLPROJ_VERSION = 1


def _project_path_hint(path: Path) -> str:
    """Return a short human-readable project location for messages."""
    if path.name == SLPROJ_FILENAME:
        return f"{path.parent.name}/" if path.parent.name else str(path)
    return str(path)


def discover_project(start: Path | None = None) -> Path | None:
    """Walk up from *start* (default CWD) looking for a .slproj file.

    Returns the first matching path, or *None* if none is found.
    """
    if start is None:
        start = Path.cwd()
    current = start.resolve()
    for ancestor in [current, *current.parents]:
        candidate = ancestor / SLPROJ_FILENAME
        if candidate.is_file():
            return candidate
    return None


def load_project(path: Path) -> SattLineProject:
    """Load a .slproj file and return an ``SattLineProject``.

    Raises ``FileNotFoundError`` if the path does not exist.
    Raises ``ValueError`` if the file is malformed or has an unsupported version.
    """
    path = path.resolve()
    if not path.exists():
        raise FileNotFoundError(f"Project file not found: {path}")

    with path.open("rb") as fh:
        raw = tomllib.load(fh)

    cfg = cast(ProjectDict, cast("dict[str, object]", raw))

    version = cfg.get("slproj_version", 1)
    if version != 1:
        raise ValueError(
            f"Unsupported .slproj version {version} in {_project_path_hint(path)}. "
            f"This tool supports version {SLPROJ_VERSION}."
        )

    return SattLineProject(path=path, data=cfg)


def save_project(path: Path, data: ProjectDict) -> None:
    """Write a ProjectDict to a .slproj TOML file."""
    path = path.resolve()

    serializable: dict[str, Any] = {}
    for key, value in cast(ConfigObjectMap, data).items():
        serializable[key] = _normalize(value)

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as fh:
        tomli_w.dump(serializable, fh)


def _normalize(value: object) -> object:
    """Convert Path objects to strings and recursive containers."""
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, list):
        raw_list: list[object] = cast("list[object]", value)
        result: list[object] = []
        for item in raw_list:
            result.append(_normalize(item))
        return result
    if isinstance(value, dict):
        raw_dict: dict[str, object] = cast("dict[str, object]", value)
        result_dict: dict[str, object] = {}
        for key, val in raw_dict.items():
            result_dict[str(key)] = _normalize(val)
        return result_dict
    return value


def init_project(
    path: Path,
    *,
    name: str | None = None,
    program_dir: str = "",
    ABB_lib_dir: str = "",  # noqa: N803
    icf_dir: str = "",
    other_lib_dirs: list[str] | None = None,
) -> SattLineProject:
    """Scaffold a new .slproj file with defaults.

    If *name* is provided it is used for display; otherwise the parent
    directory name is used.
    """
    path = path.resolve()
    if path.exists():
        raise FileExistsError(f"Project file already exists: {path}")

    data = dict(DEFAULT_PROJECT_DICT)  # shallow copy of top-level keys

    if program_dir:
        data["program_dir"] = program_dir
    if ABB_lib_dir:
        data["ABB_lib_dir"] = ABB_lib_dir
    if icf_dir:
        data["icf_dir"] = icf_dir
    if other_lib_dirs:
        data["other_lib_dirs"] = list(other_lib_dirs)

    data["analysis"] = deepcopy(DEFAULT_PROJECT_DICT["analysis"])
    data["documentation"] = deepcopy(DEFAULT_PROJECT_DICT["documentation"])

    save_project(path, cast(ProjectDict, data))
    return SattLineProject(path=path, data=cast(ProjectDict, data))


def project_status(project: SattLineProject) -> str:
    """Return a one-line summary of the project."""
    d = project.data
    targets = d.get("analyzed_programs_and_libraries", [])
    mode = d.get("mode", "official")
    target_count = len(targets)
    target_preview = ", ".join(targets[:3])
    if target_count > 3:
        target_preview += " ..."
    return (
        f"{project.root.name}/  "
        f"[mode={mode}, "
        f"{target_count} target{'s' if target_count != 1 else ''}"
        f"{': ' + target_preview if target_preview else ''}]"
    )


__all__ = [
    "SLPROJ_FILENAME",
    "SLPROJ_VERSION",
    "discover_project",
    "init_project",
    "load_project",
    "project_status",
    "save_project",
]
