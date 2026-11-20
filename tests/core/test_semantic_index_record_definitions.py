# pyright: reportPrivateUsage=false
"""Per-library record field definitions in the semantic index.

Two libraries may each declare a record with the same name and a different
field layout. The index keys nested field definitions by the library that
declares the root record so neither library's fields leak into the other.
"""

from __future__ import annotations

from sattline_parser.models.ast_model import (
    BasePicture,
    DataType,
    ModuleTypeDef,
    ScalarDatatype,
    Variable,
)

from sattlint.core._semantic_index import SemanticIndexBuilder
from tests.helpers.variable_test_support import hdr as _hdr


def _datatype(name: str, fields: tuple[tuple[str, ScalarDatatype | str], ...], library: str) -> DataType:
    return DataType(
        name=name,
        description=None,
        datecode=None,
        var_list=[Variable(name=field_name, datatype=datatype) for field_name, datatype in fields],
        origin_file=f"{library}.s",
        origin_lib=library,
    )


def _carrier_type(name: str, library: str) -> ModuleTypeDef:
    return ModuleTypeDef(
        name=name,
        origin_file=f"{library}.s",
        origin_lib=library,
        localvariables=[Variable(name="Rec", datatype="SharedRecord")],
    )


def _two_library_builder() -> SemanticIndexBuilder:
    picture = BasePicture(
        header=_hdr("Root"),
        origin_file="Root.s",
        origin_lib="RootLib",
        datatype_defs=[
            _datatype(
                "SharedRecord",
                (("Alpha", ScalarDatatype.INTEGER), ("Nested", "NestedAlpha")),
                "LibA",
            ),
            _datatype("NestedAlpha", (("AlphaLeaf", ScalarDatatype.INTEGER),), "LibA"),
            _datatype(
                "SharedRecord",
                (("Beta", ScalarDatatype.BOOLEAN), ("Nested", "NestedBeta")),
                "LibB",
            ),
            _datatype("NestedBeta", (("BetaLeaf", ScalarDatatype.BOOLEAN),), "LibB"),
        ],
        moduletype_defs=[_carrier_type("TypeA", "LibA"), _carrier_type("TypeB", "LibB")],
    )
    return SemanticIndexBuilder(picture, root_origin_library="RootLib")


def test_field_definitions_keep_the_declaring_library() -> None:
    builder = _two_library_builder()

    alpha = builder._lookup_field_definition("SharedRecord", ("Alpha",), library="LibA")
    beta = builder._lookup_field_definition("SharedRecord", ("Beta",), library="LibB")

    assert alpha is not None
    assert alpha[0].name == "Alpha"
    assert alpha[1:] == ("LibA.s", "LibA")
    assert beta is not None
    assert beta[0].name == "Beta"
    assert beta[1:] == ("LibB.s", "LibB")


def test_nested_field_definitions_keep_the_library_of_the_root_record() -> None:
    builder = _two_library_builder()

    alpha_leaf = builder._lookup_field_definition(
        "SharedRecord",
        ("Nested", "AlphaLeaf"),
        library="LibA",
    )
    beta_leaf = builder._lookup_field_definition(
        "SharedRecord",
        ("Nested", "BetaLeaf"),
        library="LibB",
    )

    assert alpha_leaf is not None
    assert alpha_leaf[0].name == "AlphaLeaf"
    assert alpha_leaf[1:] == ("LibA.s", "LibA")
    assert beta_leaf is not None
    assert beta_leaf[0].name == "BetaLeaf"
    assert beta_leaf[1:] == ("LibB.s", "LibB")


def test_an_undecidable_record_name_does_not_borrow_another_library_layout() -> None:
    builder = _two_library_builder()

    assert builder._lookup_field_definition("SharedRecord", ("Alpha",), library="RootLib") is None
    assert builder._lookup_field_definition("SharedRecord", ("Beta",), library="RootLib") is None
