"""Runtime representation of a SattLint project."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import cast

from ..config.defaults import DEFAULT_CONFIG
from ..config.types import ConfigDict
from ..config.validation import deep_merge_dict
from .types import ProjectDict

PROJECT_ROOT_KEYS: tuple[str, ...] = ("program_dir", "ABB_lib_dir", "icf_dir")
OTHER_LIB_DIRS_KEY = "other_lib_dirs"


@dataclass(frozen=True, slots=True)
class ProjectRoot:
    """A configured root resolved against the directory that holds the project."""

    key: str
    raw: str
    resolved: Path


def _root_label(entry: ProjectRoot) -> str:
    if entry.key == OTHER_LIB_DIRS_KEY:
        return f"{entry.key!r} entry {entry.raw!r}"
    return f"{entry.key!r}"


def resolve_project_root(project_root: Path, raw: str, *, key: str) -> ProjectRoot:
    """Resolve one configured root against the project directory."""
    candidate = Path(raw)
    resolved = candidate.resolve() if candidate.is_absolute() else (project_root / candidate).resolve()
    return ProjectRoot(key=key, raw=raw, resolved=resolved)


def project_root_warnings(entry: ProjectRoot) -> tuple[str, ...]:
    """Warn about absolute roots and roots that traverse upward with ``..``."""
    candidate = Path(entry.raw)
    warnings: list[str] = []
    if candidate.is_absolute():
        warnings.append(
            f"Project root {_root_label(entry)} is absolute: {entry.raw!r} resolves to {entry.resolved}. "
            "Prefer a path relative to the project file."
        )
    if ".." in candidate.parts:
        warnings.append(
            f"Project root {_root_label(entry)} contains a '..' component: {entry.raw!r} resolves to "
            f"{entry.resolved}. Confirm the root is intended or set allow_external_roots = true in the .slproj file."
        )
    return tuple(warnings)


def enforce_project_root(
    project_root: Path,
    raw: str,
    *,
    key: str,
    allow_external_roots: bool,
) -> ProjectRoot:
    """Resolve one root and refuse a path outside the project without the opt-in."""
    entry = resolve_project_root(project_root, raw, key=key)
    if not allow_external_roots and not entry.resolved.is_relative_to(project_root):
        raise ValueError(
            f"Project root {_root_label(entry)} resolves outside the project directory: {entry.raw!r} resolves "
            f"to {entry.resolved}, but the project root is {project_root}. Move the root inside the project or "
            "set allow_external_roots = true in the .slproj file to allow it."
        )
    return entry


@dataclass(frozen=True)
class SattLintProjectFile:
    path: Path
    data: ProjectDict = field(repr=False)
    warnings: tuple[str, ...] = ()

    @property
    def root(self) -> Path:
        return self.path.parent.resolve()

    @property
    def analyzers(self) -> tuple[str, ...]:
        """The analyzer keys this project selects, in declaration order."""
        return tuple(self.data.get("analyzers", ()))

    def _resolve(self, raw: str, *, key: str) -> Path:
        entry = enforce_project_root(
            self.root,
            raw,
            key=key,
            allow_external_roots=self.data.get("allow_external_roots", False),
        )
        return entry.resolved

    def _maybe_resolve(self, raw: str, *, key: str) -> str | Path:
        if not raw:
            return ""
        return self._resolve(raw, key=key)

    def to_config_dict(self) -> ConfigDict:
        d = self.data
        cfg = cast(
            ConfigDict,
            {
                "analyzed_programs_and_libraries": list(d["analyzed_programs_and_libraries"]),
                "mode": d["mode"],
                "program_dir": self._maybe_resolve(d["program_dir"], key="program_dir"),
                "ABB_lib_dir": self._maybe_resolve(d["ABB_lib_dir"], key="ABB_lib_dir"),
                "icf_dir": self._maybe_resolve(d["icf_dir"], key="icf_dir"),
                "other_lib_dirs": [self._resolve(p, key=OTHER_LIB_DIRS_KEY) for p in d["other_lib_dirs"] if p.strip()],
                "string_capacities": dict(d["string_capacities"]),
                "analysis": deepcopy(d.get("analysis", {})),
            },
        )
        return cfg

    def to_default_merged_config_dict(self, base: Mapping[str, object] | None = None) -> ConfigDict:
        """Merge defaults, an optional user config, and this project file.

        Application settings (run history, output retention, review output)
        live in the user config, so opening a project must not reset them to
        the built-in defaults. The project always wins over the base config.
        """
        base_config = cast(dict[str, object], deepcopy(DEFAULT_CONFIG))
        if base is not None:
            base_config = deep_merge_dict(base_config, dict(base))
        merged = deep_merge_dict(base_config, cast(dict[str, object], self.to_config_dict()))
        return cast(ConfigDict, merged)


__all__ = [
    "OTHER_LIB_DIRS_KEY",
    "PROJECT_ROOT_KEYS",
    "ProjectRoot",
    "SattLintProjectFile",
    "enforce_project_root",
    "project_root_warnings",
    "resolve_project_root",
]
