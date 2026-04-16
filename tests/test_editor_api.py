from pathlib import Path

import pytest

from sattlint.editor_api import discover_workspace_sources, load_workspace_snapshot


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
