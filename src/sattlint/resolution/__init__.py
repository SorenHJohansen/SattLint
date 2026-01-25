"""Resolution layer: canonical symbol paths, type graph, and access graph."""

from .paths import CanonicalPath, ModuleSegment, decorate_segment
from .type_graph import TypeGraph
from .symbol_table import CanonicalSymbolTable, SymbolDef, SymbolKind
from .access_graph import AccessGraph, AccessEvent, AccessKind

__all__ = [
    "CanonicalPath",
    "ModuleSegment",
    "decorate_segment",
    "TypeGraph",
    "CanonicalSymbolTable",
    "SymbolDef",
    "SymbolKind",
    "AccessGraph",
    "AccessEvent",
    "AccessKind",
]
