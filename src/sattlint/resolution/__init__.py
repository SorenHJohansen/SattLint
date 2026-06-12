"""Resolution layer: canonical symbol paths, type graph, and access graph."""

from .access_graph import AccessEvent, AccessGraph, AccessKind
from .context_builder import ContextBuilder
from .paths import CanonicalPath, CanonicalPathKey, ModuleSegment, decorate_segment
from .symbol_table import CanonicalSymbolTable, SymbolDef, SymbolKind
from .type_graph import TypeGraph

__all__ = [
    "AccessEvent",
    "AccessGraph",
    "AccessKind",
    "CanonicalPath",
    "CanonicalPathKey",
    "CanonicalSymbolTable",
    "ContextBuilder",
    "ModuleSegment",
    "SymbolDef",
    "SymbolKind",
    "TypeGraph",
    "decorate_segment",
]
