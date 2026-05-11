"""Canonical symbol table for case-insensitive lookups."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from sattline_parser.models.ast_model import Simple_DataType, Variable

from .paths import CanonicalPath
from .type_graph import TypeGraph


def _empty_symbols_by_key() -> dict[tuple[str, ...], SymbolDef]:
    return {}


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

    symbols_by_key: dict[tuple[str, ...], SymbolDef] = field(default_factory=_empty_symbols_by_key)

    def add(self, sym: SymbolDef) -> None:
        self.symbols_by_key[sym.canonical_path.key()] = sym

    def add_variable_root(
        self,
        module_path: list[str],
        var: Variable,
        kind: SymbolKind,
        type_graph: TypeGraph,
    ) -> None:
        root = CanonicalPath((*module_path, var.name))
        self.add(SymbolDef(kind=kind, canonical_path=root, datatype=var.datatype))

        # Expand nested record fields to represent every addressable leaf field as a fully-qualified path.
        for field_path in type_graph.iter_leaf_field_paths(var.datatype):
            if not field_path:
                continue
            cp = CanonicalPath((*module_path, var.name, *list(field_path)))
            self.add(SymbolDef(kind=kind, canonical_path=cp, datatype=None))
