"""Load, save, discover, and scaffold .slproj project files."""

from __future__ import annotations

import os
import tomllib
import uuid
from collections.abc import Mapping
from contextlib import suppress
from copy import deepcopy
from pathlib import Path
from typing import Any, cast

import tomli_w

from ..config.types import ConfigObjectMap
from .models import SattLintProjectFile
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


def load_project(path: Path) -> SattLintProjectFile:
    """Load a .slproj file and return an ``SattLintProjectFile``.

    Raises ``FileNotFoundError`` if the path does not exist.
    Raises ``ValueError`` if the path is a directory or the file is malformed,
    has an unsupported version, or carries a value of the wrong type.
    """
    path = path.resolve()
    if not path.exists():
        raise FileNotFoundError(f"Project file not found: {path}")
    if path.is_dir():
        raise ValueError(f"Project path is a directory, not a .slproj file: {path}")

    with path.open("rb") as fh:
        raw = tomllib.load(fh)

    data, warnings = _validate_project_data(cast(Mapping[str, object], raw), path)
    return SattLintProjectFile(path=path, data=data, warnings=warnings)


def _type_error(key: str, expected: str, path: Path) -> ValueError:
    return ValueError(f"Invalid .slproj value for {key!r} in {_project_path_hint(path)}: expected {expected}.")


def _string_list(key: str, value: object, path: Path) -> list[str]:
    if not isinstance(value, list):
        raise _type_error(key, "a list of strings", path)
    items = cast("list[object]", value)
    if not all(isinstance(item, str) for item in items):
        raise _type_error(key, "a list of strings", path)
    return [cast(str, item) for item in items]


def _validate_project_data(raw: Mapping[str, object], path: Path) -> tuple[ProjectDict, tuple[str, ...]]:
    """Validate a parsed .slproj table against the project defaults.

    Missing keys take their defaults, so a sparse project file stays valid.
    Unknown keys are ignored with a warning instead of being read by accident.
    """
    data: dict[str, object] = deepcopy(dict(DEFAULT_PROJECT_DICT))
    warnings: list[str] = []
    for key, value in raw.items():
        if key not in data:
            warnings.append(f"Ignoring unknown .slproj key {key!r} in {_project_path_hint(path)}.")
            continue
        data[key] = value

    version = data["slproj_version"]
    if isinstance(version, bool) or not isinstance(version, int):
        raise _type_error("slproj_version", "an integer", path)
    if version != SLPROJ_VERSION:
        raise ValueError(
            f"Unsupported .slproj version {version} in {_project_path_hint(path)}; "
            f"this tool supports version {SLPROJ_VERSION}."
        )

    data["analyzed_programs_and_libraries"] = _string_list(
        "analyzed_programs_and_libraries", data["analyzed_programs_and_libraries"], path
    )
    data["other_lib_dirs"] = _string_list("other_lib_dirs", data["other_lib_dirs"], path)

    mode = data["mode"]
    if mode not in ("official", "draft"):
        raise ValueError(
            f"Invalid .slproj value for 'mode' in {_project_path_hint(path)}: expected 'official' or 'draft'."
        )

    for key in ("program_dir", "ABB_lib_dir", "icf_dir"):
        if not isinstance(data[key], str):
            raise _type_error(key, "a string", path)

    if not isinstance(data["analysis"], Mapping):
        raise _type_error("analysis", "a table", path)

    return cast(ProjectDict, data), tuple(warnings)


def save_project(path: Path, data: ProjectDict) -> None:
    """Write a ProjectDict to a .slproj TOML file."""
    path = path.resolve()

    serializable: dict[str, Any] = {}
    for key, value in cast(ConfigObjectMap, data).items():
        serializable[key] = _normalize(value)

    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f"{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    try:
        with temp_path.open("wb") as fh:
            tomli_w.dump(serializable, fh)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(temp_path, path)
    except OSError:
        with suppress(OSError):
            temp_path.unlink()
        raise


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
    program_dir: str = "",
    ABB_lib_dir: str = "",  # noqa: N803
    icf_dir: str = "",
    other_lib_dirs: list[str] | None = None,
) -> SattLintProjectFile:
    """Scaffold a new .slproj file with defaults."""
    path = path.resolve()
    if path.exists():
        raise FileExistsError(f"Project file already exists: {path}")

    data = deepcopy(dict(DEFAULT_PROJECT_DICT))

    if program_dir:
        data["program_dir"] = program_dir
    if ABB_lib_dir:
        data["ABB_lib_dir"] = ABB_lib_dir
    if icf_dir:
        data["icf_dir"] = icf_dir
    if other_lib_dirs:
        data["other_lib_dirs"] = list(other_lib_dirs)

    data["analysis"] = deepcopy(DEFAULT_PROJECT_DICT["analysis"])

    save_project(path, cast(ProjectDict, data))
    return SattLintProjectFile(path=path, data=cast(ProjectDict, data))


def project_status(project: SattLintProjectFile) -> str:
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
