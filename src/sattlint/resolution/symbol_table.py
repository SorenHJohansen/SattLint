from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from ..models.ast_model import Simple_DataType, Variable
from .paths import CanonicalPath
from .type_graph import TypeGraph


class SymbolKind(Enum):
    LOCAL = "local"
    PARAMETER = "parameter"


@dataclass(frozen=True, slots=True)
class SymbolDef:
    kind: SymbolKind
    canonical_path: CanonicalPath
    datatype: Simple_DataType | str | None


@dataclass
class CanonicalSymbolTable:
    """Global-ish index of addressable symbols (case-insensitive canonical paths)."""

    symbols_by_key: dict[tuple[str, ...], SymbolDef] = field(default_factory=dict)

    def add(self, sym: SymbolDef) -> None:
        self.symbols_by_key[sym.canonical_path.key()] = sym

    def add_variable_root(
        self,
        module_path: list[str],
        var: Variable,
        kind: SymbolKind,
        type_graph: TypeGraph,
    ) -> None:
        root = CanonicalPath(tuple(module_path + [var.name]))
        self.add(SymbolDef(kind=kind, canonical_path=root, datatype=var.datatype))

        # Expand nested record fields to represent every addressable leaf field as a fully-qualified path.
        for field_path in type_graph.iter_leaf_field_paths(var.datatype):
            if not field_path:
                continue
            cp = CanonicalPath(tuple(module_path + [var.name] + list(field_path)))
            self.add(SymbolDef(kind=kind, canonical_path=cp, datatype=None))
