from pathlib import Path

from sattlint.editor_api import discover_workspace_sources, load_workspace_snapshot


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _minimal_moduledef() -> str:
    return "ModuleDef\nClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )\n"


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
