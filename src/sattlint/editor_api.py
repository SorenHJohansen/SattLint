"""Compatibility facade for editor-facing semantic APIs.

The canonical implementation lives in sattlint.core.semantic so the LSP,
batch analysis, and editor helpers share a single semantic pipeline.
"""

from .core.semantic import (
    CallSignatureOccurrence,
    CompletionItem,
    DEFAULT_SAFETY_SIGNAL_KEYWORDS,
    SafetyPathTrace,
    SemanticDiagnostic,
    SemanticSnapshot,
    SymbolAccess,
    SymbolDefinition,
    SymbolReference,
    WorkspaceSnapshotError,
    WorkspaceSourceDiscovery,
    build_source_snapshot_from_basepicture,
    discover_workspace_sources,
    load_source_snapshot,
    load_workspace_snapshot,
)

__all__ = [
    "CallSignatureOccurrence",
    "CompletionItem",
    "DEFAULT_SAFETY_SIGNAL_KEYWORDS",
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
