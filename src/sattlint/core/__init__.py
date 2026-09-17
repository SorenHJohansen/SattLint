"""Canonical shared core for workspace discovery and semantics."""

from .semantic import (
    SemanticSnapshot,
    SymbolDefinition,
    SymbolReference,
    WorkspaceSourceDiscovery,
    build_source_snapshot_from_basepicture,
    load_source_snapshot,
)

__all__ = [
    "SemanticSnapshot",
    "SymbolDefinition",
    "SymbolReference",
    "WorkspaceSourceDiscovery",
    "build_source_snapshot_from_basepicture",
    "load_source_snapshot",
]
