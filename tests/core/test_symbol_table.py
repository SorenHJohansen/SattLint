"""Focused tests for canonical symbol-table collection."""

from __future__ import annotations

from sattline_parser.models.ast_model import DataType, ScalarDatatype, Variable

from sattlint.resolution.paths import CanonicalPath
from sattlint.resolution.symbol_table import CanonicalSymbolTable, SymbolDef, SymbolKind
from sattlint.resolution.type_graph import TypeGraph


def _record_type_graph() -> TypeGraph:
    return TypeGraph.from_datatypes(
        [
            DataType(
                name="Rec",
                description=None,
                datecode=None,
                var_list=[
                    Variable(name="A", datatype=ScalarDatatype.INTEGER),
                    Variable(name="B", datatype=ScalarDatatype.REAL),
                ],
            )
        ]
    )


def test_symbol_table_collect_false_skips_population() -> None:
    table = CanonicalSymbolTable(collect=False)

    table.add(SymbolDef(kind=SymbolKind.LOCAL, canonical_path=CanonicalPath(("Root",)), datatype=None))
    table.add_variable_root(
        ["Root"],
        Variable(name="Rec", datatype="Rec"),
        SymbolKind.LOCAL,
        _record_type_graph(),
    )

    assert table.symbols_by_key == {}


def test_symbol_table_collects_root_and_leaf_fields_by_default() -> None:
    table = CanonicalSymbolTable()

    table.add_variable_root(
        ["Root"],
        Variable(name="Rec", datatype="Rec"),
        SymbolKind.LOCAL,
        _record_type_graph(),
    )

    assert set(table.symbols_by_key) == {("root", "rec"), ("root", "rec", "a"), ("root", "rec", "b")}
