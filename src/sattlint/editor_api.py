"""Compatibility facade for editor-facing semantic APIs.

The canonical implementation lives in sattlint.core.semantic so the LSP,
batch analysis, and editor helpers share a single semantic pipeline.
"""

from pathlib import Path

from .core.semantic import (
    DEFAULT_SAFETY_SIGNAL_KEYWORDS,
    CallSignatureOccurrence,
    CompletionItem,
    SafetyPathTrace,
    SemanticDiagnostic,
    SemanticSnapshot,
    SymbolAccess,
    SymbolDefinition,
    SymbolReference,
    WorkspaceSnapshotError,
    WorkspaceSourceDiscovery,
    discover_workspace_sources,
)
from .core.semantic import (
    build_source_snapshot_from_basepicture as _build_source_snapshot_from_basepicture,
)
from .core.semantic import (
    load_source_snapshot as _load_source_snapshot,
)
from .core.semantic import (
    load_workspace_snapshot as _load_workspace_snapshot,
)
from .engine import CodeMode
from .models.ast_model import BasePicture
from .semantic_analysis import build_variable_semantic_artifacts


def load_source_snapshot(
    source_file: Path,
    source_text: str,
    *,
    workspace_root: Path | None = None,
    collect_variable_diagnostics: bool = False,
    debug: bool = False,
) -> SemanticSnapshot:
    return _load_source_snapshot(
        source_file,
        source_text,
        workspace_root=workspace_root,
        collect_variable_diagnostics=collect_variable_diagnostics,
        debug=debug,
        _analysis_provider=build_variable_semantic_artifacts,
    )


def build_source_snapshot_from_basepicture(
    base_picture: BasePicture,
    source_file: Path,
    *,
    workspace_root: Path | None = None,
    collect_variable_diagnostics: bool = False,
    debug: bool = False,
) -> SemanticSnapshot:
    return _build_source_snapshot_from_basepicture(
        base_picture,
        source_file,
        workspace_root=workspace_root,
        collect_variable_diagnostics=collect_variable_diagnostics,
        debug=debug,
        _analysis_provider=build_variable_semantic_artifacts,
    )


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
) -> SemanticSnapshot:
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
    "DEFAULT_SAFETY_SIGNAL_KEYWORDS",
    "CallSignatureOccurrence",
    "CompletionItem",
    "SafetyPathTrace",
    "SemanticDiagnostic",
    "SemanticSnapshot",
    "SymbolAccess",
    "SymbolDefinition",
    "SymbolReference",
    "WorkspaceSnapshotError",
    "WorkspaceSourceDiscovery",
    "build_source_snapshot_from_basepicture",
    "discover_workspace_sources",
    "load_source_snapshot",
    "load_workspace_snapshot",
]
