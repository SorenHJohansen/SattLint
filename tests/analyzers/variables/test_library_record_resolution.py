# pyright: reportPrivateUsage=false
"""Field and leaf resolution must follow the library that declares a record.

Two libraries may each declare a record with the same name and a different
field layout. Resolution keyed by name alone silently picks one layout, so a
reference from the other library reads and writes fields that do not exist in
its own record.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from sattline_parser import parse_source_text as parser_core_parse_source_text
from sattline_parser.ast import FuncCall, FuncCallStmt
from sattline_parser.models.ast_model import (
    BasePicture,
    DataType,
    Equation,
    ModuleCode,
    ModuleTypeDef,
    ScalarDatatype,
    Variable,
)

from sattlint.analyzers.variables import VariablesAnalyzer
from sattlint.analyzers.variables._variable_issue_collection import (
    _DatatypeFieldVariable,
)
from sattlint.core.semantic import build_snapshot_from_loaded_project
from sattlint.models.project_graph import ProjectGraph
from tests.helpers.variable_test_support import hdr as _hdr
from tests.helpers.variable_test_support import varref as _varref


def _datatype(name: str, fields: tuple[tuple[str, ScalarDatatype | str], ...], library: str) -> DataType:
    return DataType(
        name=name,
        description=None,
        datecode=None,
        var_list=[Variable(name=field_name, datatype=datatype) for field_name, datatype in fields],
        origin_file=f"{library}.s",
        origin_lib=library,
    )


def _copy_typedef(name: str, library: str) -> ModuleTypeDef:
    return ModuleTypeDef(
        name=name,
        origin_file=f"{library}.s",
        origin_lib=library,
        localvariables=[
            Variable(name="Rec", datatype="SharedRecord"),
            Variable(name="Dst", datatype="SharedRecord"),
            Variable(name="Status", datatype=ScalarDatatype.INTEGER),
        ],
        modulecode=ModuleCode(
            equationblocks=[
                Equation(
                    name="Copy",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        FuncCallStmt(
                            call=FuncCall(
                                name="CopyVariable",
                                args=(_varref("Rec"), _varref("Dst"), _varref("Status")),
                            )
                        )
                    ],
                )
            ]
        ),
    )


def _analyzer() -> VariablesAnalyzer:
    analyzer = VariablesAnalyzer(
        BasePicture(
            header=_hdr("Root"),
            datatype_defs=[
                _datatype(
                    "SharedRecord",
                    (("Alpha", ScalarDatatype.INTEGER), ("Nested", "NestedAlpha")),
                    "LibA",
                ),
                _datatype(
                    "SharedRecord",
                    (("Beta", ScalarDatatype.BOOLEAN), ("Nested", "NestedBeta")),
                    "LibB",
                ),
                _datatype("NestedAlpha", (("AlphaLeaf", ScalarDatatype.INTEGER),), "LibA"),
                _datatype("NestedBeta", (("BetaLeaf", ScalarDatatype.BOOLEAN),), "LibB"),
            ],
            moduletype_defs=[_copy_typedef("TypeA", "LibA"), _copy_typedef("TypeB", "LibB")],
        ),
        fail_loudly=False,
    )
    type_a, type_b = analyzer.bp.moduletype_defs
    analyzer._analyze_typedef(type_a, ["Root", "TypeDef:TypeA"])
    analyzer._analyze_typedef(type_b, ["Root", "TypeDef:TypeB"])
    return analyzer


def test_record_wide_access_reads_the_fields_of_the_referencing_library() -> None:
    analyzer = _analyzer()
    type_a, type_b = analyzer.bp.moduletype_defs

    rec_a = type_a.localvariables[0]
    rec_b = type_b.localvariables[0]
    assert set(analyzer.get_usage(rec_a).field_reads) == {"Alpha", "Nested.AlphaLeaf"}
    assert set(analyzer.get_usage(rec_b).field_reads) == {"Beta", "Nested.BetaLeaf"}
    assert analyzer.analysis_warnings == []


def test_datatype_field_inventory_keeps_the_declaring_library() -> None:
    analyzer = _analyzer()

    entries = analyzer.iter_variables_for_datatype_field_analysis()
    by_name = {(entry.variable.name, entry.library) for entry in entries if entry.variable.name == "Rec"}

    assert by_name == {("Rec", "LibA"), ("Rec", "LibB")}
    assert all(isinstance(entry, _DatatypeFieldVariable) for entry in entries)


_AMBIGUOUS_TARGET = """
"Syntax version 2.23, date: 2026-06-19-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-06-19-12:00:00.000, name: Ambiguous"

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
   Rec: SharedRecord;
   Dst: SharedRecord;
   Status: integer := 0;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
   EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      CopyVariable(Rec, Dst, Status);
ENDDEF (*BasePicture*);
"""


def _ambiguous_target_picture() -> BasePicture:
    """A target that uses a record name only two dependency libraries declare."""
    parsed = parser_core_parse_source_text(_AMBIGUOUS_TARGET)
    return replace(
        parsed,
        origin_file="Root.s",
        origin_lib="RootLib",
        datatype_defs=[
            _datatype("SharedRecord", (("Alpha", ScalarDatatype.INTEGER),), "LibA"),
            _datatype("SharedRecord", (("Beta", ScalarDatatype.BOOLEAN),), "LibB"),
        ],
    )


def test_ambiguous_record_is_not_fatal_and_warns_once(tmp_path: Path) -> None:
    picture = _ambiguous_target_picture()

    snapshot = build_snapshot_from_loaded_project(
        picture,
        ProjectGraph(),
        entry_file=tmp_path / "Root.s",
        workspace_root=tmp_path,
    )
    paths = {definition.canonical_path for definition in snapshot.definitions}
    assert any(path.endswith(".Rec") for path in paths)
    # The layout is unknown, so the type stays a leaf instead of gaining fields
    # from an arbitrarily chosen library.
    assert not any(".Rec." in path for path in paths)

    analyzer = VariablesAnalyzer(picture, fail_loudly=False)
    analyzer.run()

    ambiguity_warnings = [warning for warning in analyzer.analysis_warnings if "'SharedRecord'" in warning]
    assert len(ambiguity_warnings) == 1
    assert "LibA" in ambiguity_warnings[0]
    assert "LibB" in ambiguity_warnings[0]


_RECORD_LIBRARY_SOURCE = """
"Syntax version 2.23, date: 2026-06-19-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-06-19-12:00:00.000, name: {library}"

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

TYPEDEFINITIONS
   SharedRecord = RECORD DateCode_ 1
      {field}: {scalar} := 0;
      Nested: {nested};
   ENDDEF (*SharedRecord*);

   {nested} = RECORD DateCode_ 2
      {leaf}: {scalar} := 0;
   ENDDEF (*{nested}*);

TYPEDEFINITIONS
   {moduletype} = MODULEDEFINITION DateCode_ 3
   LOCALVARIABLES
      Rec: SharedRecord;
      Dst: SharedRecord;
      Status: integer := 0;
   ModuleDef
   ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
   ModuleCode
   EQUATIONBLOCK Copy COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      CopyVariable(Rec, Dst, Status);
   ENDDEF (*{moduletype}*);

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ENDDEF (*BasePicture*);
"""


def _record_library(
    *,
    library: str,
    field: str,
    scalar: str,
    nested: str,
    leaf: str,
    moduletype: str,
) -> BasePicture:
    parsed = parser_core_parse_source_text(
        _RECORD_LIBRARY_SOURCE.format(
            library=library,
            field=field,
            scalar=scalar,
            nested=nested,
            leaf=leaf,
            moduletype=moduletype,
        )
    )
    return replace(
        parsed,
        origin_file=f"{library}.s",
        origin_lib=library,
        datatype_defs=[
            replace(datatype, origin_file=f"{library}.s", origin_lib=library) for datatype in parsed.datatype_defs
        ],
        moduletype_defs=[
            replace(moduletype_def, origin_file=f"{library}.s", origin_lib=library)
            for moduletype_def in parsed.moduletype_defs
        ],
    )


def test_parsed_libraries_keep_their_own_record_layouts() -> None:
    type_a = _record_library(
        library="LibA",
        field="Alpha",
        scalar="integer",
        nested="NestedAlpha",
        leaf="AlphaLeaf",
        moduletype="TypeA",
    )
    type_b = _record_library(
        library="LibB",
        field="Beta",
        scalar="boolean",
        nested="NestedBeta",
        leaf="BetaLeaf",
        moduletype="TypeB",
    )
    picture = BasePicture(
        header=_hdr("Root"),
        origin_file="Root.s",
        origin_lib="RootLib",
        datatype_defs=[*type_a.datatype_defs, *type_b.datatype_defs],
        moduletype_defs=[*type_a.moduletype_defs, *type_b.moduletype_defs],
    )
    analyzer = VariablesAnalyzer(picture, fail_loudly=False)
    lib_a, lib_b = picture.moduletype_defs

    analyzer._analyze_typedef(lib_a, ["Root", "TypeDef:TypeA"])
    analyzer._analyze_typedef(lib_b, ["Root", "TypeDef:TypeB"])

    assert set(analyzer.get_usage(lib_a.localvariables[0]).field_reads) == {"Alpha", "Nested.AlphaLeaf"}
    assert set(analyzer.get_usage(lib_b.localvariables[0]).field_reads) == {"Beta", "Nested.BetaLeaf"}
    assert analyzer.analysis_warnings == []
