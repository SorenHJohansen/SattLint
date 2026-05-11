"""SattLint package root exports."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from .__version__ import __version__

if TYPE_CHECKING:
    from .core.semantic import WorkspaceSourceDiscovery
    from .engine import CodeMode
    from .grammar import constants as constants


_discover_workspace_sources: Any | None = None
_load_workspace_snapshot: Any | None = None


def _ensure_workspace_api() -> tuple[Any, Any]:
    global _discover_workspace_sources, _load_workspace_snapshot

    if _discover_workspace_sources is None or _load_workspace_snapshot is None:
        from .core.semantic import discover_workspace_sources as discover_workspace_sources_impl
        from .core.semantic import load_workspace_snapshot as load_workspace_snapshot_impl

        _discover_workspace_sources = discover_workspace_sources_impl
        _load_workspace_snapshot = load_workspace_snapshot_impl

    return _discover_workspace_sources, _load_workspace_snapshot


def _ensure_analysis_provider() -> Any:
    analysis_provider = globals().get("build_variable_semantic_artifacts")
    if analysis_provider is None:
        from .semantic_analysis import build_variable_semantic_artifacts as analysis_provider_impl

        globals()["build_variable_semantic_artifacts"] = analysis_provider_impl
        return analysis_provider_impl
    return analysis_provider


def discover_workspace_sources(workspace_root: Path) -> WorkspaceSourceDiscovery:
    discover_workspace_sources_impl, _ = _ensure_workspace_api()
    return discover_workspace_sources_impl(workspace_root)


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
    _, load_workspace_snapshot_impl = _ensure_workspace_api()
    return load_workspace_snapshot_impl(
        entry_file,
        workspace_root=workspace_root,
        discovery=discovery,
        mode=mode,
        other_lib_dirs=other_lib_dirs,
        abb_lib_dir=abb_lib_dir,
        scan_root_only=scan_root_only,
        debug=debug,
        collect_variable_diagnostics=collect_variable_diagnostics,
        _analysis_provider=_ensure_analysis_provider(),
    )


def __getattr__(name: str) -> Any:
    if name == "constants":
        from .grammar import constants as constants_module

        globals()[name] = constants_module
        return constants_module
    if name == "WorkspaceSourceDiscovery":
        from .core.semantic import WorkspaceSourceDiscovery

        globals()[name] = WorkspaceSourceDiscovery
        return WorkspaceSourceDiscovery
    if name == "CodeMode":
        from .engine import CodeMode

        globals()[name] = CodeMode
        return CodeMode
    if name == "build_variable_semantic_artifacts":
        return _ensure_analysis_provider()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "__version__",
    "constants",
    "discover_workspace_sources",
    "load_workspace_snapshot",
]
