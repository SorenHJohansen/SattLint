"""SattLint package root exports."""

from pathlib import Path

from .__version__ import __version__
from .core.semantic import WorkspaceSourceDiscovery
from .core.semantic import discover_workspace_sources as _discover_workspace_sources
from .core.semantic import load_workspace_snapshot as _load_workspace_snapshot
from .engine import CodeMode
from .grammar import constants as constants
from .semantic_analysis import build_variable_semantic_artifacts


def discover_workspace_sources(workspace_root: Path) -> WorkspaceSourceDiscovery:
    return _discover_workspace_sources(workspace_root)


def load_workspace_snapshot(
    entry_file: Path,
    *,
    workspace_root: Path | None = None,
    discovery: WorkspaceSourceDiscovery | None = None,
    mode: CodeMode | str = "draft",
    other_lib_dirs: list[Path] | None = None,
    abb_lib_dir: Path | None = None,
    scan_root_only: bool = False,
    debug: bool = False,
    collect_variable_diagnostics: bool = True,
):
    return _load_workspace_snapshot(
        entry_file,
        workspace_root=workspace_root,
        discovery=discovery,
        mode=mode,
        other_lib_dirs=other_lib_dirs,
        abb_lib_dir=abb_lib_dir,
        scan_root_only=scan_root_only,
        debug=debug,
        collect_variable_diagnostics=collect_variable_diagnostics,
        _analysis_provider=build_variable_semantic_artifacts,
    )


__all__ = [
    "__version__",
    "constants",
    "discover_workspace_sources",
    "load_workspace_snapshot",
]
