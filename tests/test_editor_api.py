from pathlib import Path
from typing import Any, cast

import pytest

from sattlint import constants as const
from sattlint.editor_api import (
    build_source_snapshot_from_basepicture,
    discover_workspace_sources,
    load_workspace_snapshot,
)
from sattlint.models.ast_model import (
    BasePicture,
    DataType,
    Equation,
    ModuleCode,
    ModuleHeader,
    ModuleTypeDef,
    ModuleTypeInstance,
    ParameterMapping,
    Simple_DataType,
    SourceSpan,
    Variable,
)


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _minimal_moduledef() -> str:
    return "ModuleDef\nClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )\n"


def _record_library_source(record_name: str, field_name: str) -> str:
    return f'''
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
TYPEDEFINITIONS
    {record_name} = RECORD DateCode_ 2
        {field_name}: integer;
    ENDDEF (*{record_name}*);
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ENDDEF (*BasePicture*);
'''.strip()


def _contract_library_source() -> str:
    return '''
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
TYPEDEFINITIONS
    MismatchType = MODULEDEFINITION DateCode_ 2
    MODULEPARAMETERS
        ExpectedValue: real;
    ModuleDef
    ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
    ENDDEF (*MismatchType*);
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ENDDEF (*BasePicture*);
'''.strip()

def _anytype_contract_library_source() -> str:
    return '''
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
TYPEDEFINITIONS
    InnerPayload = RECORD DateCode_ 2
        Other: integer;
    ENDDEF (*InnerPayload*);
    PayloadShape = RECORD DateCode_ 3
        Inner: InnerPayload;
    ENDDEF (*PayloadShape*);
    GenericConsumer = MODULEDEFINITION DateCode_ 4
    MODULEPARAMETERS
        Payload: AnyType;
    LOCALVARIABLES
        Mirror: integer := 0;
    ModuleDef
    ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
    ModuleCode
        EQUATIONBLOCK GenericEq COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
            Mirror = Payload.Inner.Value;
    ENDDEF (*GenericConsumer*);
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ENDDEF (*BasePicture*);
'''.strip()


def _program_with_contract_mismatch_dependency() -> str:
    return '''
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    SourceValue: integer := 1;
SUBMODULES
    Child Invocation
       ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0 ) : MismatchType (
    ExpectedValue => SourceValue);
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ENDDEF (*BasePicture*);
'''.strip()

def _program_with_anytype_contract_dependency() -> str:
    return '''
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    Source: PayloadShape;
SUBMODULES
    Consumer Invocation
       ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0 ) : GenericConsumer (
    Payload => Source);
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ENDDEF (*BasePicture*);
'''.strip()


def _hdr(name: str) -> ModuleHeader:
    return ModuleHeader(name=name, invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0))


def _varref(name: str) -> dict[str, str]:
    return {const.KEY_VAR_NAME: name}


def _program_with_dependency(record_name: str) -> str:
    return f'''
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    Dep: {record_name};
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ENDDEF (*BasePicture*);
'''.strip()


def _guard_library_source() -> str:
    return '''
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
TYPEDEFINITIONS
    GuardType = MODULEDEFINITION DateCode_ 2
    MODULEPARAMETERS
        InSignal: boolean;
    LOCALVARIABLES
        Seen: boolean := False;
    ModuleDef
    ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
    ModuleCode
        EQUATIONBLOCK GuardEq COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
            Seen = InSignal;
    ENDDEF (*GuardType*);
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ENDDEF (*BasePicture*);
'''.strip()


def _program_with_guard_dependency() -> str:
    return '''
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    EmergencyShutdown: boolean := False;
SUBMODULES
    Guard Invocation
       ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0 ) : GuardType (
    InSignal => EmergencyShutdown);
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
        EmergencyShutdown = True;
ENDDEF (*BasePicture*);
'''.strip()


def _taint_guard_library_source() -> str:
    return '''
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
TYPEDEFINITIONS
    GuardType = MODULEDEFINITION DateCode_ 2
    MODULEPARAMETERS
        InCommand: boolean;
    LOCALVARIABLES
        EmergencyShutdown: boolean := False;
    ModuleDef
    ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
    ModuleCode
        EQUATIONBLOCK GuardEq COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
            EmergencyShutdown = InCommand;
    ENDDEF (*GuardType*);
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ENDDEF (*BasePicture*);
'''.strip()


def _program_with_taint_guard_dependency() -> str:
    return '''
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    OperatorCommand: boolean := False;
SUBMODULES
    Guard Invocation
       ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0 ) : GuardType (
    InCommand => OperatorCommand);
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
        OperatorCommand = True;
ENDDEF (*BasePicture*);
'''.strip()


def _output_library_source() -> str:
    return '''
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
TYPEDEFINITIONS
    OutputBridge = MODULEDEFINITION DateCode_ 2
    MODULEPARAMETERS
        InSignal: integer;
        OutSignal: integer;
    LOCALVARIABLES
        Cache: integer := 0;
    ModuleDef
    ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
    ModuleCode
        EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
            Cache = InSignal;
            OutSignal = Cache;
    ENDDEF (*OutputBridge*);
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ENDDEF (*BasePicture*);
'''.strip()


def _program_with_output_dependency() -> str:
    return '''
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    InternalSignal: integer := 0;
    FinalOutput: integer := 0;
SUBMODULES
    Bridge Invocation
       ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0 ) : OutputBridge (
    InSignal => InternalSignal,
    OutSignal => FinalOutput);
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
        InternalSignal = 7;
ENDDEF (*BasePicture*);
'''.strip()


def _status_signature_library_source() -> str:
    return '''
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
TYPEDEFINITIONS
    StatusBridge = MODULEDEFINITION DateCode_ 2
    MODULEPARAMETERS
        OperationStatus: integer;
    LOCALVARIABLES
        SourceValue: integer := 1;
        DestinationValue: integer := 0;
    ModuleDef
    ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
    ModuleCode
        EQUATIONBLOCK BridgeEq COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
            CopyVariable(SourceValue, DestinationValue, OperationStatus);
    ENDDEF (*StatusBridge*);
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ENDDEF (*BasePicture*);
'''.strip()


def _program_with_status_signature_dependency() -> str:
    return '''
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    FinalStatus: integer := 0;
SUBMODULES
    Bridge Invocation
       ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0 ) : StatusBridge (
    OperationStatus => FinalStatus);
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ENDDEF (*BasePicture*);
'''.strip()


def _line_col_for(source: str, needle: str, *, occurrence: int = 1) -> tuple[int, int]:
    start = -1
    search_from = 0
    for _ in range(occurrence):
        start = source.index(needle, search_from)
        search_from = start + 1
    prefix = source[:start]
    line = prefix.count("\n") + 1
    last_newline = prefix.rfind("\n")
    column = start + 1 if last_newline < 0 else start - last_newline
    return line, column


def test_discover_workspace_sources_finds_programs_and_dependencies(tmp_path):
    _write_text(tmp_path / "Program" / "Main.s", '"x"\n"y"\n"z"\n')
    _write_text(tmp_path / "Libs" / "Support.l", "Dep\n")
    _write_text(tmp_path / "ABB_lib" / "Vendor.z", "VendorDep\n")
    _write_text(tmp_path / "build" / "Ignored.s", '"no"\n')

    discovery = discover_workspace_sources(tmp_path)

    assert tmp_path / "Program" / "Main.s" in discovery.program_files
    assert tmp_path / "Libs" / "Support.l" in discovery.dependency_files
    assert tmp_path / "ABB_lib" / "Vendor.z" in discovery.dependency_files
    assert tmp_path / "build" / "Ignored.s" not in discovery.program_files
    assert discovery.abb_lib_dir == tmp_path / "ABB_lib"


def test_load_workspace_snapshot_indexes_definitions_and_completions(tmp_path):
    source = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
TYPEDEFINITIONS
    MyRec = RECORD DateCode_ 2
        Value: integer;
    ENDDEF (*MyRec*);
LOCALVARIABLES
    Dv: integer := 0;
    Rec: MyRec;
SUBMODULES
    Child Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 3
    MODULEPARAMETERS
        Param: integer;
    LOCALVARIABLES
        LocalVar: boolean := False;
    ModuleDef
    ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
    ModuleCode
        EQUATIONBLOCK ChildEq COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
            Param = Dv;
            LocalVar = True;
    ENDDEF (*Child*);
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
        Dv = 1;
ENDDEF (*BasePicture*);
""".strip()

    entry_file = tmp_path / "Program" / "Main.s"
    _write_text(entry_file, source)

    snapshot = load_workspace_snapshot(
        entry_file,
        workspace_root=tmp_path,
        collect_variable_diagnostics=False,
    )

    root_defs = snapshot.find_definitions("BasePicture.Dv")
    assert len(root_defs) == 1
    assert root_defs[0].kind == "local"
    assert root_defs[0].datatype == "integer"

    field_defs = snapshot.find_definitions("Rec.Value")
    assert len(field_defs) == 1
    assert field_defs[0].kind == "field"
    assert field_defs[0].datatype == "integer"

    completions = snapshot.complete(module_path="BasePicture.Child")
    labels = {item.label for item in completions}
    assert {"Dv", "Rec", "Param", "LocalVar"}.issubset(labels)


def test_load_workspace_snapshot_resolves_definitions_at_cursor(tmp_path):
    source = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
TYPEDEFINITIONS
    MyRec = RECORD DateCode_ 2
        Value: integer;
    ENDDEF (*MyRec*);
LOCALVARIABLES
    Dv: integer := 0;
    Rec: MyRec;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
        Dv = Rec.Value;
ENDDEF (*BasePicture*);
""".strip()

    entry_file = tmp_path / "Program" / "Main.s"
    _write_text(entry_file, source)

    snapshot = load_workspace_snapshot(
        entry_file,
        workspace_root=tmp_path,
        collect_variable_diagnostics=False,
    )

    dv_line, dv_column = _line_col_for(source, "Dv =")
    rec_line, rec_column = _line_col_for(source, "Rec.Value")
    value_line, value_column = _line_col_for(source, "Value", occurrence=2)

    dv_defs = snapshot.find_definitions_at(entry_file, dv_line, dv_column)
    rec_defs = snapshot.find_definitions_at(entry_file, rec_line, rec_column)
    value_defs = snapshot.find_definitions_at(entry_file, value_line, value_column)

    assert len(dv_defs) == 1
    assert dv_defs[0].canonical_path == "BasePicture.Dv"
    assert dv_defs[0].declaration_span is not None
    assert dv_defs[0].declaration_span.line == 10

    assert len(rec_defs) == 1
    assert rec_defs[0].canonical_path == "BasePicture.Rec"

    assert len(value_defs) == 1
    assert value_defs[0].canonical_path == "BasePicture.Rec.Value"
    assert value_defs[0].declaration_span is not None
    assert value_defs[0].declaration_span.line == 7


def test_load_workspace_snapshot_skips_unresolved_moduletype_instances(tmp_path):
    source = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
SUBMODULES
    Missing Invocation (0.0,0.0,0.0,1.0,1.0) : ControlLibVersion;
    Child Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 2
    LOCALVARIABLES
        LocalVar: boolean := False;
    ModuleDef
    ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
    ModuleCode
        EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
            LocalVar = True;
    ENDDEF (*Child*);
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ENDDEF (*BasePicture*);
""".strip()

    entry_file = tmp_path / "Program" / "Main.s"
    _write_text(entry_file, source)

    snapshot = load_workspace_snapshot(entry_file, workspace_root=tmp_path)

    child_defs = snapshot.find_definitions("BasePicture.Child.LocalVar")
    assert len(child_defs) == 1
    assert child_defs[0].kind == "local"

    completions = snapshot.complete(module_path="BasePicture.Missing")
    assert completions == []


def test_load_workspace_snapshot_prefers_same_directory_dependency_files(tmp_path):
    entry_file = tmp_path / "Libs" / "HA" / "ProjectLib" / "Main.s"
    _write_text(entry_file, _program_with_dependency("SupportRec"))
    _write_text(entry_file.with_suffix(".l"), "Support\n")
    _write_text(entry_file.parent / "Support.s", _record_library_source("SupportRec", "LocalField"))
    _write_text(tmp_path / "AFallbackLib" / "Support.s", _record_library_source("SupportRec", "WrongField"))

    snapshot = load_workspace_snapshot(
        entry_file,
        workspace_root=tmp_path,
        collect_variable_diagnostics=False,
    )

    assert snapshot.find_definitions("BasePicture.Dep.LocalField")
    assert snapshot.find_definitions("BasePicture.Dep.WrongField") == []


def test_load_workspace_snapshot_prefers_sibling_library_cluster_over_workspace_fallback(tmp_path):
    entry_file = tmp_path / "Libs" / "HA" / "ProjectLib" / "Main.s"
    _write_text(entry_file, _program_with_dependency("SupportRec"))
    _write_text(entry_file.with_suffix(".l"), "Support\n")
    _write_text(tmp_path / "Libs" / "HA" / "NNELib" / "Support.s", _record_library_source("SupportRec", "SiblingField"))
    _write_text(tmp_path / "AFallbackLib" / "Support.s", _record_library_source("SupportRec", "FallbackField"))

    snapshot = load_workspace_snapshot(
        entry_file,
        workspace_root=tmp_path,
        collect_variable_diagnostics=False,
    )

    assert snapshot.find_definitions("BasePicture.Dep.SiblingField")
    assert snapshot.find_definitions("BasePicture.Dep.FallbackField") == []


def test_load_workspace_snapshot_falls_back_to_workspace_when_cluster_has_no_match(tmp_path):
    entry_file = tmp_path / "Libs" / "HA" / "ProjectLib" / "Main.s"
    _write_text(entry_file, _program_with_dependency("SupportRec"))
    _write_text(entry_file.with_suffix(".l"), "Support\n")
    _write_text(tmp_path / "SharedLib" / "Support.s", _record_library_source("SupportRec", "SharedField"))

    snapshot = load_workspace_snapshot(
        entry_file,
        workspace_root=tmp_path,
        collect_variable_diagnostics=False,
    )

    assert snapshot.find_definitions("BasePicture.Dep.SharedField")


def test_load_workspace_snapshot_traces_safety_path_through_dependency_moduletype(tmp_path):
    entry_file = tmp_path / "Program" / "Main.s"
    _write_text(entry_file, _program_with_guard_dependency())
    _write_text(entry_file.with_suffix(".l"), "Guard\n")
    _write_text(tmp_path / "Libs" / "Guard.s", _guard_library_source())

    snapshot = load_workspace_snapshot(
        entry_file,
        workspace_root=tmp_path,
        collect_variable_diagnostics=False,
    )

    traces = snapshot.find_safety_paths("EmergencyShutdown")

    assert len(traces) == 1
    assert traces[0].canonical_path == "BasePicture.EmergencyShutdown"
    assert traces[0].writer_module_paths == (("BasePicture",),)
    assert traces[0].reader_module_paths == (("BasePicture", "Guard"),)


def test_load_workspace_snapshot_traces_taint_path_through_dependency_moduletype(tmp_path):
    entry_file = tmp_path / "Program" / "Main.s"
    _write_text(entry_file, _program_with_taint_guard_dependency())
    _write_text(entry_file.with_suffix(".l"), "Guard\n")
    _write_text(tmp_path / "Libs" / "Guard.s", _taint_guard_library_source())

    snapshot = load_workspace_snapshot(
        entry_file,
        workspace_root=tmp_path,
        collect_variable_diagnostics=False,
    )

    traces = snapshot.find_taint_paths("EmergencyShutdown")

    assert len(traces) == 1
    assert traces[0].source_kind == "operator"
    assert traces[0].source_canonical_path == "BasePicture.OperatorCommand"
    assert traces[0].sink_canonical_path == "BasePicture.Guard.EmergencyShutdown"
    assert traces[0].path == (
        "BasePicture.OperatorCommand",
        "BasePicture.Guard.InCommand",
        "BasePicture.Guard.EmergencyShutdown",
    )
    assert traces[0].spans_multiple_modules is True


def test_load_workspace_snapshot_keeps_contract_mismatch_diagnostics_for_dependency_typedef(tmp_path):
    entry_file = tmp_path / "Program" / "Main.s"
    library_file = tmp_path / "Libs" / "Mismatch.s"
    _write_text(entry_file, _program_with_contract_mismatch_dependency())
    _write_text(entry_file.with_suffix(".l"), "Mismatch\n")
    _write_text(library_file, _contract_library_source())

    snapshot = load_workspace_snapshot(
        entry_file,
        workspace_root=tmp_path,
    )

    diagnostics = snapshot.semantic_diagnostics_for_path(library_file)

    assert diagnostics
    assert any(
        "Cross-module contract mismatch" in diagnostic.message
        and "integer" in diagnostic.message
        and "real" in diagnostic.message
        for diagnostic in diagnostics
    )

def test_load_workspace_snapshot_reports_anytype_required_field_mismatch_from_dependency(tmp_path):
    entry_file = tmp_path / "Program" / "Main.s"
    library_file = tmp_path / "Libs" / "GenericSupport.s"
    inner_datatype = cast(Any, DataType)(
        name="InnerPayload",
        description=None,
        datecode=None,
        var_list=[
            Variable(
                name="Other",
                datatype=Simple_DataType.INTEGER,
                declaration_span=SourceSpan(6, 9),
            )
        ],
        origin_file=library_file.name,
        origin_lib="Libs",
        declaration_span=SourceSpan(5, 5),
    )
    payload_datatype = cast(Any, DataType)(
        name="PayloadShape",
        description=None,
        datecode=None,
        var_list=[
            Variable(
                name="Inner",
                datatype="InnerPayload",
                declaration_span=SourceSpan(9, 9),
            )
        ],
        origin_file=library_file.name,
        origin_lib="Libs",
        declaration_span=SourceSpan(8, 5),
    )
    consumer = ModuleTypeDef(
        name="GenericConsumer",
        moduleparameters=[
            Variable(
                name="Payload",
                datatype="AnyType",
                declaration_span=SourceSpan(13, 9),
            )
        ],
        localvariables=[
            Variable(
                name="Mirror",
                datatype=Simple_DataType.INTEGER,
                declaration_span=SourceSpan(15, 9),
            )
        ],
        submodules=[],
        moduledef=None,
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="GenericEq",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (
                            const.KEY_ASSIGN,
                            _varref("Mirror"),
                            _varref("Payload.Inner.Value"),
                        )
                    ],
                )
            ]
        ),
        parametermappings=[],
        origin_file=library_file.name,
        origin_lib="Libs",
    )
    base_picture = BasePicture(
        header=_hdr("BasePicture"),
        datatype_defs=[inner_datatype, payload_datatype],
        moduletype_defs=[consumer],
        localvariables=[
            Variable(
                name="Source",
                datatype="PayloadShape",
                declaration_span=SourceSpan(5, 5),
            )
        ],
        submodules=[
            ModuleTypeInstance(
                header=_hdr("Consumer"),
                moduletype_name="GenericConsumer",
                parametermappings=[
                    ParameterMapping(
                        target=_varref("Payload"),
                        source_type=const.TREE_TAG_VARIABLE_NAME,
                        is_duration=False,
                        is_source_global=False,
                        source=_varref("Source"),
                        source_literal=None,
                    )
                ],
            )
        ],
        modulecode=None,
        moduledef=None,
        origin_file=entry_file.name,
        origin_lib="Program",
    )

    snapshot = build_source_snapshot_from_basepicture(
        base_picture,
        entry_file,
        workspace_root=tmp_path,
        collect_variable_diagnostics=True,
    )

    diagnostics = snapshot.semantic_diagnostics_for_path(library_file)

    assert diagnostics
    assert any(
        "Cross-module contract mismatch" in diagnostic.message
        and "missing required field 'Inner.Value'" in diagnostic.message
        for diagnostic in diagnostics
    )


def test_load_workspace_snapshot_tracks_dependency_mediated_output_accesses(tmp_path):
    entry_file = tmp_path / "Program" / "Main.s"
    _write_text(entry_file, _program_with_output_dependency())
    _write_text(entry_file.with_suffix(".l"), "OutputBridge\n")
    _write_text(tmp_path / "Libs" / "OutputBridge.s", _output_library_source())

    snapshot = load_workspace_snapshot(
        entry_file,
        workspace_root=tmp_path,
        collect_variable_diagnostics=False,
    )

    accesses = snapshot.find_accesses_to("BasePicture.FinalOutput")

    assert any(access.kind == "write" for access in accesses)
    assert any(access.use_module_path == ("BasePicture", "Bridge") for access in accesses)


def test_load_workspace_snapshot_resolves_dependency_call_signatures(tmp_path):
    entry_file = tmp_path / "Program" / "Main.s"
    library_file = tmp_path / "Libs" / "StatusBridge.s"
    _write_text(entry_file, _program_with_status_signature_dependency())
    _write_text(entry_file.with_suffix(".l"), "StatusBridge\n")
    _write_text(library_file, _status_signature_library_source())

    snapshot = load_workspace_snapshot(
        entry_file,
        workspace_root=tmp_path,
        collect_variable_diagnostics=False,
    )

    signatures = snapshot.find_call_signatures("CopyVariable", source_path=library_file)

    assert len(signatures) == 2
    assert all(signature.source_file == library_file.name for signature in signatures)
    assert {signature.module_path for signature in signatures} == {
        ("StatusBridge",),
        ("BasePicture", "Bridge"),
    }
    assert all(signature.signature.call_type == "Procedure" for signature in signatures)
    assert all(
        [parameter.name for parameter in signature.signature.status_parameters] == ["Status"]
        for signature in signatures
    )


def test_load_workspace_snapshot_allows_dependency_datatype_close_to_local_name(tmp_path):
    entry_file = tmp_path / "Libs" / "HA" / "SattLineUnitTests" / "Main.s"
    _write_text(
        entry_file,
        """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
TYPEDEFINITIONS
    IOType = RECORD DateCode_ 2
        LocalField: integer;
    ENDDEF (*IOType*);
LOCALVARIABLES
    Signal: DIType;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ENDDEF (*BasePicture*);
""".strip(),
    )
    _write_text(entry_file.with_suffix(".l"), "nneconfig\n")
    _write_text(
        tmp_path / "Libs" / "HA" / "NNELib" / "nneconfig.s",
        _record_library_source("DIType", "SwitchSignal"),
    )

    snapshot = load_workspace_snapshot(
        entry_file,
        workspace_root=tmp_path,
        collect_variable_diagnostics=False,
    )

    definitions = snapshot.find_definitions("BasePicture.Signal.SwitchSignal")
    assert len(definitions) == 1
    assert definitions[0].canonical_path == "BasePicture.Signal.SwitchSignal"


def test_load_workspace_snapshot_reports_root_parse_failure_detail(tmp_path):
    entry_file = tmp_path / "Program" / "Main.s"
    _write_text(
        entry_file,
        "\n".join(
            [
                '"SyntaxVersion"',
                '"OriginalFileDate"',
                '"ProgramDate"',
                'BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1',
                'LOCALVARIABLES',
                '    ExecuteLocal: boolean := False;',
                'ModuleDef',
                'ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )',
                'ModuleCode',
                '    EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :',
                '        ExecuteLocal = ExecuteLocal:Old;',
                'ENDDEF (*BasePicture*);',
            ]
        ),
    )

    with pytest.raises(RuntimeError, match="Target 'Main' failed parse/transform:.*uses OLD on non-STATE variable 'ExecuteLocal'") as exc_info:
        load_workspace_snapshot(entry_file, workspace_root=tmp_path, collect_variable_diagnostics=False)

    assert getattr(exc_info.value, "line", None) == 11
    assert getattr(exc_info.value, "column", None) == 24
    assert getattr(exc_info.value, "length", None) == len("ExecuteLocal")


def test_load_workspace_snapshot_treats_controllib_as_expected_unavailable(tmp_path):
    entry_file = tmp_path / "Program" / "Main.s"
    _write_text(
        entry_file,
        "\n".join(
            [
                '"SyntaxVersion"',
                '"OriginalFileDate"',
                '"ProgramDate"',
                'BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1',
                'ModuleDef',
                'ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )',
                'ENDDEF (*BasePicture*);',
            ]
        ),
    )
    _write_text(entry_file.with_suffix('.l'), 'ControlLib\n')

    snapshot = load_workspace_snapshot(
        entry_file,
        workspace_root=tmp_path,
        collect_variable_diagnostics=False,
    )

    assert 'controllib' in snapshot.project_graph.unavailable_libraries
    assert snapshot.project_graph.missing == []


def test_load_workspace_snapshot_indexes_library_dependencies_for_graph_inputs(tmp_path):
    entry_file = tmp_path / "Program" / "Main.s"
    support_file = tmp_path / "Libraries" / "Support.s"
    _write_text(
        entry_file,
        "\n".join(
            [
                '"SyntaxVersion"',
                '"OriginalFileDate"',
                '"ProgramDate"',
                'BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1',
                'ModuleDef',
                'ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )',
                'ENDDEF (*BasePicture*);',
            ]
        ),
    )
    _write_text(entry_file.with_suffix('.l'), 'Support\nControlLib\n')
    _write_text(
        support_file,
        "\n".join(
            [
                '"SyntaxVersion"',
                '"OriginalFileDate"',
                '"ProgramDate"',
                'BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1',
                'ModuleDef',
                'ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )',
                'ENDDEF (*BasePicture*);',
            ]
        ),
    )

    snapshot = load_workspace_snapshot(
        entry_file,
        workspace_root=tmp_path,
        collect_variable_diagnostics=False,
    )

    assert snapshot.project_graph.library_dependencies == {
        'program': {'libraries'},
        'libraries': set(),
    }
    assert 'controllib' in snapshot.project_graph.unavailable_libraries
    assert support_file in snapshot.project_graph.source_files


def test_load_workspace_snapshot_indexes_transitive_library_dependencies_for_graph_inputs(tmp_path):
    entry_file = tmp_path / "Program" / "Main.s"
    support_file = tmp_path / "Libraries" / "Support.s"
    shared_file = tmp_path / "SharedLib" / "Shared.s"
    source_text = "\n".join(
        [
            '"SyntaxVersion"',
            '"OriginalFileDate"',
            '"ProgramDate"',
            'BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1',
            'ModuleDef',
            'ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )',
            'ENDDEF (*BasePicture*);',
        ]
    )

    _write_text(entry_file, source_text)
    _write_text(entry_file.with_suffix('.l'), 'Support\n')
    _write_text(support_file, source_text)
    _write_text(support_file.with_suffix('.l'), 'Shared\n')
    _write_text(shared_file, source_text)

    snapshot = load_workspace_snapshot(
        entry_file,
        workspace_root=tmp_path,
        collect_variable_diagnostics=False,
    )

    assert snapshot.project_graph.library_dependencies == {
        'program': {'libraries'},
        'libraries': {'sharedlib'},
        'sharedlib': set(),
    }
    assert support_file in snapshot.project_graph.source_files
    assert shared_file in snapshot.project_graph.source_files


def test_load_workspace_snapshot_formats_dependency_issues_readably(tmp_path):
    entry_file = tmp_path / "Program" / "Main.s"
    _write_text(
        entry_file,
        "\n".join(
            [
                '"SyntaxVersion"',
                '"OriginalFileDate"',
                '"ProgramDate"',
                'BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1',
                'LOCALVARIABLES',
                '    ExecuteLocal: boolean := False;',
                'ModuleDef',
                'ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )',
                'ModuleCode',
                '    EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :',
                '        ExecuteLocal = ExecuteLocal:Old;',
                'ENDDEF (*BasePicture*);',
            ]
        ),
    )
    _write_text(entry_file.with_suffix('.l'), 'ControlLib\nSupport\n')
    _write_text(
        entry_file.parent / 'Support.s',
        "\n".join(
            [
                '"SyntaxVersion"',
                '"OriginalFileDate"',
                '"ProgramDate"',
                'BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1',
                'LOCALVARIABLES',
                '    ExecuteLocal: boolean := False;',
                'ModuleDef',
                'ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )',
                'ModuleCode',
                '    EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :',
                '        ExecuteLocal = ExecuteLocal:Old;',
                'ENDDEF (*BasePicture*);',
            ]
        ),
    )

    with pytest.raises(RuntimeError) as exc_info:
        load_workspace_snapshot(entry_file, workspace_root=tmp_path, collect_variable_diagnostics=False)

    message = str(exc_info.value)
    assert "Target 'Main' failed parse/transform: BasePicture equation 'Main' uses OLD on non-STATE variable 'ExecuteLocal'" in message
    assert 'Unavailable libraries (1):' in message
    assert '- controllib (expected proprietary dependency)' in message
    assert 'Other dependency issues (1):' in message
    assert "Support parse/transform error: BasePicture equation 'Main' uses OLD on non-STATE variable 'ExecuteLocal'" in message
    assert 'Missing: [' not in message
