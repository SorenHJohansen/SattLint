"""Canonical symbol table for case-insensitive lookups."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from sattlint.parser_api import ScalarDatatype, Variable

from .paths import CanonicalPath, CanonicalPathKey
from .type_graph import TypeGraph


def _symbols_by_key_factory() -> dict[CanonicalPathKey, SymbolDef]:
    return {}


class SymbolKind(Enum):
    LOCAL = "local"
    PARAMETER = "parameter"


@dataclass(frozen=True, slots=True)
class SymbolDef:
    kind: SymbolKind
    canonical_path: CanonicalPath
    datatype: ScalarDatatype | str | None


@dataclass
class CanonicalSymbolTable:
    """Global-ish index of addressable symbols (case-insensitive canonical paths).

    ``collect`` exists because the analyzer stack resolves references through
    ``ScopeContext`` env/mappings and never reads this table; populating it
    there would materialize a canonical path for every record leaf field. The
    semantic-snapshot builders are the consumers and keep the default.
    """

    symbols_by_key: dict[CanonicalPathKey, SymbolDef] = field(default_factory=_symbols_by_key_factory)
    collect: bool = True

    def add(self, sym: SymbolDef) -> None:
        if not self.collect:
            return
        self.symbols_by_key[sym.canonical_path.key()] = sym

    def add_variable_root(
        self,
        module_path: list[str],
        var: Variable,
        kind: SymbolKind,
        type_graph: TypeGraph,
        *,
        library: str | None = None,
    ) -> None:
        """Register a variable and every addressable leaf field below it.

        ``library`` is the library that declares the variable. A record name
        that several libraries declare and this library does not select is
        treated as a leaf, because the layout is unknown.
        """
        if not self.collect:
            return
        root = CanonicalPath((*module_path, var.name))
        self.add(SymbolDef(kind=kind, canonical_path=root, datatype=var.datatype))

        # Expand nested record fields to represent every addressable leaf field as a fully-qualified path.
        for field_path in type_graph.iter_leaf_field_paths(var.datatype, library=library):
            if not field_path:
                continue
            cp = CanonicalPath((*module_path, var.name, *list(field_path)))
            self.add(SymbolDef(kind=kind, canonical_path=cp, datatype=None))
