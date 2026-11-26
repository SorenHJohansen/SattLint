"""Load, save, discover, and scaffold .slproj project files."""

from __future__ import annotations

import os
import tomllib
import uuid
from collections.abc import Mapping
from contextlib import suppress
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import tomli_w

from ..config.string_capacities import validate_string_capacities
from ..config.types import ConfigObjectMap
from .models import SattLintProjectFile
from .types import DEFAULT_PROJECT_DICT, SLPROJ_VERSION, ProjectDict

SLPROJ_SUFFIX = ".slproj"
SLPROJ_FILENAME = SLPROJ_SUFFIX


class ProjectAmbiguousError(ValueError):
    """Two or more project files exist in the first ancestor that has any.

    Discovery never guesses between named project files. The message lists
    every candidate so the caller can pass ``--project`` with one of them.
    """

    def __init__(self, directory: Path, candidates: tuple[Path, ...]) -> None:
        self.directory = directory
        self.candidates = candidates
        listing = ", ".join(str(candidate) for candidate in candidates)
        super().__init__(
            f"Multiple {SLPROJ_SUFFIX} files found in {directory}: {listing}. Pass --project PATH to choose one."
        )


@dataclass(frozen=True, slots=True)
class ProjectDiscovery:
    """The outcome of walking upward from a directory for a project file.

    ``directory`` is the first ancestor that holds any project file, or
    ``None`` when no ancestor holds one. ``candidates`` lists every project
    file in that directory, and ``selected`` is the file discovery chose there.
    A selection is ``None`` only when there is no candidate, or when several
    named files are ambiguous.
    """

    searched_from: Path
    directory: Path | None = None
    candidates: tuple[Path, ...] = ()
    selected: Path | None = None

    @property
    def is_ambiguous(self) -> bool:
        return self.selected is None and len(self.candidates) > 1

    def selected_path(self) -> Path | None:
        """Return the selected project file, raising when the choice is ambiguous."""
        if self.is_ambiguous:
            directory = self.directory if self.directory is not None else self.searched_from
            raise ProjectAmbiguousError(directory, self.candidates)
        return self.selected


def _project_path_hint(path: Path) -> str:
    """Return a short human-readable project location for messages."""
    if path.name == SLPROJ_FILENAME:
        return f"{path.parent.name}/" if path.parent.name else str(path)
    return str(path)


def _project_candidates(directory: Path) -> tuple[Path, ...]:
    """Return the regular files in *directory* whose name ends in .slproj.

    The suffix match is case-insensitive, directories are ignored, and the
    result is sorted so an error message is stable.
    """
    try:
        entries = tuple(directory.iterdir())
    except OSError:
        return ()
    return tuple(
        sorted(
            (entry for entry in entries if entry.is_file() and entry.name.casefold().endswith(SLPROJ_SUFFIX)),
            key=lambda entry: entry.name.casefold(),
        )
    )


def _choose_candidate(candidates: tuple[Path, ...]) -> Path | None:
    """Pick the literal .slproj, else a unique named file, else nothing."""
    for candidate in candidates:
        if candidate.name.casefold() == SLPROJ_FILENAME:
            return candidate
    if len(candidates) == 1:
        return candidates[0]
    return None


def discover_project_result(start: Path | None = None) -> ProjectDiscovery:
    """Walk up from *start* (default CWD) and report the first project directory.

    At each ancestor the literal ``.slproj`` wins over named files; otherwise a
    unique ``*.slproj`` file is used. The walk stops at the first ancestor that
    holds any candidate, so candidates are never merged across directories.
    """
    origin = (Path.cwd() if start is None else start).resolve()
    for ancestor in (origin, *origin.parents):
        candidates = _project_candidates(ancestor)
        if not candidates:
            continue
        return ProjectDiscovery(
            searched_from=origin,
            directory=ancestor,
            candidates=candidates,
            selected=_choose_candidate(candidates),
        )
    return ProjectDiscovery(searched_from=origin)


def discover_project(start: Path | None = None) -> Path | None:
    """Walk up from *start* (default CWD) looking for a project file.

    Returns the first matching path, or *None* if none is found. Raises
    ``ProjectAmbiguousError`` when an ancestor holds two or more project files
    and none of them is the literal ``.slproj``.
    """
    return discover_project_result(start).selected_path()


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


def _version_error(version: int, path: Path) -> ValueError:
    hint = _project_path_hint(path)
    if version == 1:
        return ValueError(
            f"Unsupported .slproj version 1 in {hint}; version 2 requires a top-level [string_capacities] "
            "table with identstring = 15, tagstring = 30, string = 40, linestring = 80, maxstring = 140 "
            "(or the project's own positive values)."
        )
    return ValueError(f"Unsupported .slproj version {version} in {hint}; this tool supports version {SLPROJ_VERSION}.")


def _string_list(key: str, value: object, path: Path) -> list[str]:
    if not isinstance(value, list):
        raise _type_error(key, "a list of strings", path)
    items = cast("list[object]", value)
    if not all(isinstance(item, str) for item in items):
        raise _type_error(key, "a list of strings", path)
    return [cast(str, item) for item in items]


def _validate_project_data(raw: Mapping[str, object], path: Path) -> tuple[ProjectDict, tuple[str, ...]]:
    """Validate a parsed .slproj table against the project defaults.

    Missing scalar keys take their defaults, so a sparse project file stays
    valid. The ``[string_capacities]`` table is the exception: it is required,
    so it is validated from the raw file rather than seeded from the defaults.
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
        raise _version_error(version, path)

    if "string_capacities" not in raw:
        raise ValueError(
            f"Missing required [string_capacities] table in {_project_path_hint(path)}. "
            "Declare identstring, tagstring, string, linestring, and maxstring as positive integers "
            "(standard values: 15, 30, 40, 80, 140)."
        )
    capacities = validate_string_capacities(raw["string_capacities"], location=_project_path_hint(path))
    data["string_capacities"] = capacities.as_dict()

    data["analyzed_programs_and_libraries"] = _string_list(
        "analyzed_programs_and_libraries", data["analyzed_programs_and_libraries"], path
    )
    data["other_lib_dirs"] = _string_list("other_lib_dirs", data["other_lib_dirs"], path)
    data["analyzers"] = _string_list("analyzers", data["analyzers"], path)

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


__all__ = [
    "SLPROJ_FILENAME",
    "SLPROJ_SUFFIX",
    "SLPROJ_VERSION",
    "ProjectAmbiguousError",
    "ProjectDiscovery",
    "discover_project",
    "discover_project_result",
    "init_project",
    "load_project",
    "save_project",
]
