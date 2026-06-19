# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownArgumentType=false
from pathlib import Path

from sattlint.editor_api import load_workspace_snapshot


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _two_field_record_library_source(record_name: str, field_name: str) -> str:
    return f"""
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
TYPEDEFINITIONS
    {record_name} = RECORD DateCode_ 2
        {field_name}: integer;
        MirrorField: integer;
    ENDDEF (*{record_name}*);
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ENDDEF (*BasePicture*);
""".strip()


def test_load_workspace_snapshot_indexes_definitions_and_completions(tmp_path):
    source = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
TYPEDEFINITIONS
    MyRec = RECORD DateCode_ 2
        Value: integer;
        Mirror: integer;
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
        BackupField: integer;
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
        _two_field_record_library_source("DIType", "SwitchSignal"),
    )

    snapshot = load_workspace_snapshot(
        entry_file,
        workspace_root=tmp_path,
        collect_variable_diagnostics=False,
    )

    definitions = snapshot.find_definitions("BasePicture.Signal.SwitchSignal")
    assert len(definitions) == 1
    assert definitions[0].canonical_path == "BasePicture.Signal.SwitchSignal"
