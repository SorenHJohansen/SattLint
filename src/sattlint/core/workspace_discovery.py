"""Workspace source discovery helpers shared by semantic loading paths."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

_SOURCE_EXTENSIONS = {".s", ".x", ".l", ".z"}
_PROGRAM_EXTENSIONS = {".s", ".x"}
_DEPENDENCY_EXTENSIONS = {".l", ".z"}
_IGNORED_DISCOVERY_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "htmlcov",
    ".pytest_cache",
    ".mypy_cache",
}


def _path_key(path: Path) -> str:
    return path.as_posix().casefold()


def _path_parent_key(path: Path) -> str:
    return _path_key(path.parent)


def _resolved_path(path: Path | None) -> Path | None:
    if path is None:
        return None
    try:
        return path.resolve()
    except OSError:
        return path


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _first_branch_under(root: Path, path: Path) -> str | None:
    if not _is_relative_to(path, root):
        return None
    relative = path.relative_to(root)
    if not relative.parts:
        return None
    return relative.parts[0].casefold()


def _index_source_files(paths: tuple[Path, ...]) -> dict[str, tuple[Path, ...]]:
    index: dict[str, list[Path]] = {}
    for path in paths:
        index.setdefault(path.stem.casefold(), []).append(path)
    return {stem: tuple(sorted(matches, key=_path_key)) for stem, matches in index.items()}


@dataclass(frozen=True, slots=True)
class WorkspaceSourceDiscovery:
    workspace_root: Path
    source_dirs: tuple[Path, ...]
    program_files: tuple[Path, ...]
    dependency_files: tuple[Path, ...]
    abb_lib_dir: Path | None = None
    program_files_by_stem: dict[str, tuple[Path, ...]] = field(
        default_factory=dict,
        repr=False,
        compare=False,
    )
    dependency_files_by_stem: dict[str, tuple[Path, ...]] = field(
        default_factory=dict,
        repr=False,
        compare=False,
    )

    def other_lib_dirs_for(self, entry_file: Path) -> tuple[Path, ...]:
        entry_parent = _resolved_path(entry_file.resolve().parent)
        return self.ordered_source_dirs_for(entry_parent, include_requester=False)

    def ordered_source_dirs_for(
        self,
        requester_dir: Path | None,
        *,
        include_requester: bool = True,
    ) -> tuple[Path, ...]:
        requester = _resolved_path(requester_dir)
        abb_dir = _resolved_path(self.abb_lib_dir)
        ordered: list[Path] = []
        seen: set[str] = set()

        def add(path: Path | None) -> None:
            resolved = _resolved_path(path)
            if resolved is None:
                return
            key = _path_key(resolved)
            if key in seen:
                return
            seen.add(key)
            ordered.append(resolved)

        if requester is not None and include_requester:
            add(requester)

        cluster_root = self.shared_library_root_for(requester)
        if cluster_root is not None and requester is not None:
            requester_branch = _first_branch_under(cluster_root, requester)
            same_branch: list[Path] = []
            sibling_branch: list[Path] = []
            for source_dir in self.source_dirs:
                resolved = _resolved_path(source_dir)
                if resolved is None or resolved == requester:
                    continue
                if not _is_relative_to(resolved, cluster_root):
                    continue
                branch = _first_branch_under(cluster_root, resolved)
                if requester_branch is not None and branch == requester_branch:
                    same_branch.append(resolved)
                else:
                    sibling_branch.append(resolved)
            for source_dir in sorted(same_branch, key=_path_key):
                add(source_dir)
            for source_dir in sorted(sibling_branch, key=_path_key):
                add(source_dir)

        for source_dir in self.source_dirs:
            resolved = _resolved_path(source_dir)
            if resolved is None:
                continue
            if abb_dir is not None and resolved == abb_dir:
                continue
            add(resolved)

        add(abb_dir)
        return tuple(ordered)

    def shared_library_root_for(self, requester_dir: Path | None) -> Path | None:
        requester = _resolved_path(requester_dir)
        workspace_root = _resolved_path(self.workspace_root)
        if requester is None or workspace_root is None or not _is_relative_to(requester, workspace_root):
            return None

        current: Path | None = requester
        while current is not None and _is_relative_to(current, workspace_root):
            branches: set[str] = set()
            for source_dir in self.source_dirs:
                resolved = _resolved_path(source_dir)
                if resolved is None or not _is_relative_to(resolved, current):
                    continue
                branch = _first_branch_under(current, resolved)
                if branch is None:
                    continue
                branches.add(branch)
                if len(branches) > 1:
                    return current
            if current == workspace_root:
                break
            current = current.parent

        return None

    def locate_source_file(
        self,
        name: str,
        *,
        extensions: list[str],
        requester_dir: Path | None,
    ) -> Path | None:
        if not extensions:
            return None

        normalized_extensions = {extension.lower() for extension in extensions}
        if normalized_extensions.issubset(_PROGRAM_EXTENSIONS):
            matches = self.program_files_by_stem.get(name.casefold(), ())
        elif normalized_extensions.issubset(_DEPENDENCY_EXTENSIONS):
            matches = self.dependency_files_by_stem.get(name.casefold(), ())
        else:
            matches = tuple(
                path
                for path in (
                    *self.program_files_by_stem.get(name.casefold(), ()),
                    *self.dependency_files_by_stem.get(name.casefold(), ()),
                )
                if path.suffix.lower() in normalized_extensions
            )

        if not matches:
            return None

        matches_by_parent: dict[str, dict[str, Path]] = {}
        for match in matches:
            suffix = match.suffix.lower()
            if suffix not in normalized_extensions:
                continue
            matches_by_parent.setdefault(_path_parent_key(match), {})[suffix] = match

        for source_dir in self.ordered_source_dirs_for(requester_dir):
            entries = matches_by_parent.get(_path_key(source_dir))
            if not entries:
                continue
            for extension in extensions:
                candidate = entries.get(extension.lower())
                if candidate is not None:
                    return candidate

        for extension in extensions:
            for match in matches:
                if match.suffix.lower() == extension.lower():
                    return match
        return None


def discover_workspace_sources(workspace_root: Path) -> WorkspaceSourceDiscovery:
    root = Path(workspace_root).resolve()
    if not root.exists() or not root.is_dir():
        raise FileNotFoundError(f"Workspace root does not exist: {root}")

    source_dirs: set[Path] = set()
    program_files: list[Path] = []
    dependency_files: list[Path] = []

    for current_root, dir_names, file_names in os.walk(root):
        dir_names[:] = [name for name in dir_names if name.casefold() not in _IGNORED_DISCOVERY_DIRS]

        current_dir = Path(current_root)
        for file_name in file_names:
            path = current_dir / file_name
            suffix = path.suffix.lower()
            if suffix not in _SOURCE_EXTENSIONS:
                continue
            source_dirs.add(current_dir)
            if suffix in _PROGRAM_EXTENSIONS:
                program_files.append(path)
            elif suffix in _DEPENDENCY_EXTENSIONS:
                dependency_files.append(path)

    abb_candidates = sorted(
        (directory for directory in source_dirs if "abb" in directory.name.casefold()),
        key=_path_key,
    )
    abb_lib_dir = abb_candidates[0] if abb_candidates else None

    sorted_program_files = tuple(sorted(program_files, key=_path_key))
    sorted_dependency_files = tuple(sorted(dependency_files, key=_path_key))

    return WorkspaceSourceDiscovery(
        workspace_root=root,
        source_dirs=tuple(sorted(source_dirs, key=_path_key)),
        program_files=sorted_program_files,
        dependency_files=sorted_dependency_files,
        abb_lib_dir=abb_lib_dir,
        program_files_by_stem=_index_source_files(sorted_program_files),
        dependency_files_by_stem=_index_source_files(sorted_dependency_files),
    )


def single_entry_discovery(entry_path: Path, workspace_root: Path) -> WorkspaceSourceDiscovery:
    suffix = entry_path.suffix.lower()
    program_files = (entry_path,) if suffix in _PROGRAM_EXTENSIONS else ()
    dependency_files = (entry_path,) if suffix in _DEPENDENCY_EXTENSIONS else ()
    return WorkspaceSourceDiscovery(
        workspace_root=workspace_root,
        source_dirs=(entry_path.parent,),
        program_files=program_files,
        dependency_files=dependency_files,
        abb_lib_dir=None,
        program_files_by_stem=_index_source_files(program_files),
        dependency_files_by_stem=_index_source_files(dependency_files),
    )


__all__ = [
    "WorkspaceSourceDiscovery",
    "discover_workspace_sources",
    "single_entry_discovery",
]


resolved_path = _resolved_path
first_branch_under = _first_branch_under
