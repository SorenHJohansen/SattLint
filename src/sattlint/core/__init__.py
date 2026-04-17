"""Canonical shared core for workspace discovery, semantics, and document text helpers."""

from .document import LineIndex, utf16_index_to_codepoint_offset
from .semantic import (
    CompletionItem,
    SemanticDiagnostic,
    SemanticSnapshot,
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
    "CompletionItem",
    "LineIndex",
    "SemanticDiagnostic",
    "SemanticSnapshot",
    "SymbolDefinition",
    "SymbolReference",
    "WorkspaceSnapshotError",
    "WorkspaceSourceDiscovery",
    "build_source_snapshot_from_basepicture",
    "discover_workspace_sources",
    "load_source_snapshot",
    "load_workspace_snapshot",
    "utf16_index_to_codepoint_offset",
]
