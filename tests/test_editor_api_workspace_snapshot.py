# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownArgumentType=false, reportPrivateUsage=false
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from sattline_parser.models.ast_model import Simple_DataType
from sattlint.core import semantic as semantic_core
from sattlint.core.semantic import WorkspaceSourceDiscovery
from sattlint.editor_api import load_workspace_snapshot
from sattlint.models.project_graph import ProjectGraph


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_load_source_snapshot_builds_semantic_snapshot(tmp_path):
    source = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    Counter: integer := 0;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ENDDEF (*BasePicture*);
""".strip()
    entry_file = tmp_path / "Program" / "Main.s"

    snapshot = semantic_core.load_source_snapshot(
        entry_file,
        source,
        workspace_root=tmp_path,
        collect_variable_diagnostics=False,
        debug=True,
    )

    assert snapshot.entry_file == entry_file.resolve()
    assert snapshot.workspace_root == tmp_path.resolve()
    assert snapshot.find_definitions("Counter")[0].canonical_path == "BasePicture.Counter"


def test_load_workspace_snapshot_raises_for_missing_entry_file(tmp_path):
    missing_entry = tmp_path / "Program" / "Missing.s"

    with pytest.raises(FileNotFoundError, match="Entry file does not exist"):
        load_workspace_snapshot(missing_entry, workspace_root=tmp_path)


def test_load_workspace_snapshot_reports_missing_root_without_target_failure_detail(tmp_path, monkeypatch):
    entry_file = tmp_path / "Program" / "Main.s"
    _write_text(entry_file, '"x"\n"y"\n"z"\n')

    class FakeLoader:
        def __init__(self, *args, **kwargs):
            pass

        def resolve(self, *args, **kwargs):
            graph = ProjectGraph()
            graph.missing = ["Support parse/transform error: dependency issue"]
            return graph

    monkeypatch.setattr(semantic_core, "SattLineProjectLoader", FakeLoader)

    with pytest.raises(semantic_core.WorkspaceSnapshotError, match="Target 'Main' was not parsed") as exc_info:
        load_workspace_snapshot(entry_file, workspace_root=tmp_path, collect_variable_diagnostics=False)

    assert exc_info.value.line is None
    assert exc_info.value.column is None
    assert exc_info.value.length is None


def test_load_workspace_snapshot_reports_root_parse_failure_detail(tmp_path):
    entry_file = tmp_path / "Program" / "Main.s"
    _write_text(
        entry_file,
        "\n".join(
            [
                '"SyntaxVersion"',
                '"OriginalFileDate"',
                '"ProgramDate"',
                "BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1",
                "LOCALVARIABLES",
                "    ExecuteLocal: boolean := False;",
                "ModuleDef",
                "ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )",
                "ModuleCode",
                "    EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :",
                "        ExecuteLocal = ExecuteLocal:Old;",
                "ENDDEF (*BasePicture*);",
            ]
        ),
    )

    with pytest.raises(
        RuntimeError, match=r"Target 'Main' failed parse/transform:.*uses OLD on non-STATE variable 'ExecuteLocal'"
    ) as exc_info:
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
                "BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1",
                "ModuleDef",
                "ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )",
                "ENDDEF (*BasePicture*);",
            ]
        ),
    )
    _write_text(entry_file.with_suffix(".l"), "ControlLib\n")

    snapshot = load_workspace_snapshot(
        entry_file,
        workspace_root=tmp_path,
        collect_variable_diagnostics=False,
    )

    assert "controllib" in snapshot.project_graph.unavailable_libraries
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
                "BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1",
                "ModuleDef",
                "ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )",
                "ENDDEF (*BasePicture*);",
            ]
        ),
    )
    _write_text(entry_file.with_suffix(".l"), "Support\nControlLib\n")
    _write_text(
        support_file,
        "\n".join(
            [
                '"SyntaxVersion"',
                '"OriginalFileDate"',
                '"ProgramDate"',
                "BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1",
                "ModuleDef",
                "ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )",
                "ENDDEF (*BasePicture*);",
            ]
        ),
    )

    snapshot = load_workspace_snapshot(
        entry_file,
        workspace_root=tmp_path,
        collect_variable_diagnostics=False,
    )

    assert snapshot.project_graph.library_dependencies == {
        "program": {"libraries"},
        "libraries": set(),
    }
    assert "controllib" in snapshot.project_graph.unavailable_libraries
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
            "BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1",
            "ModuleDef",
            "ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )",
            "ENDDEF (*BasePicture*);",
        ]
    )

    _write_text(entry_file, source_text)
    _write_text(entry_file.with_suffix(".l"), "Support\n")
    _write_text(support_file, source_text)
    _write_text(support_file.with_suffix(".l"), "Shared\n")
    _write_text(shared_file, source_text)

    snapshot = load_workspace_snapshot(
        entry_file,
        workspace_root=tmp_path,
        collect_variable_diagnostics=False,
    )

    assert snapshot.project_graph.library_dependencies == {
        "program": {"libraries"},
        "libraries": {"sharedlib"},
        "sharedlib": set(),
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
                "BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1",
                "LOCALVARIABLES",
                "    ExecuteLocal: boolean := False;",
                "ModuleDef",
                "ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )",
                "ModuleCode",
                "    EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :",
                "        ExecuteLocal = ExecuteLocal:Old;",
                "ENDDEF (*BasePicture*);",
            ]
        ),
    )
    _write_text(entry_file.with_suffix(".l"), "ControlLib\nSupport\n")
    _write_text(
        entry_file.parent / "Support.s",
        "\n".join(
            [
                '"SyntaxVersion"',
                '"OriginalFileDate"',
                '"ProgramDate"',
                "BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1",
                "LOCALVARIABLES",
                "    ExecuteLocal: boolean := False;",
                "ModuleDef",
                "ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )",
                "ModuleCode",
                "    EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :",
                "        ExecuteLocal = ExecuteLocal:Old;",
                "ENDDEF (*BasePicture*);",
            ]
        ),
    )

    with pytest.raises(RuntimeError) as exc_info:
        load_workspace_snapshot(entry_file, workspace_root=tmp_path, collect_variable_diagnostics=False)

    message = str(exc_info.value)
    assert (
        "Target 'Main' failed parse/transform: BasePicture equation 'Main' "
        "uses OLD on non-STATE variable 'ExecuteLocal'" in message
    )
    assert "Unavailable libraries (1):" in message
    assert "- controllib (expected proprietary dependency)" in message
    assert "Validation warnings (2):" in message
    assert (
        "Support: validation warning: BasePicture equation 'Main' uses OLD on non-STATE variable 'ExecuteLocal'"
        in message
    )
    assert "Missing: [" not in message


def test_sattlint_package_discover_workspace_sources_wrapper(tmp_path):
    import sattlint  # noqa: PLC0415

    discovery = sattlint.discover_workspace_sources(tmp_path)
    assert discovery is not None


def test_workspace_source_discovery_locate_source_file_prefers_cluster_then_extension(tmp_path):
    root = tmp_path.resolve()
    project_dir = root / "Libs" / "HA" / "ProjectLib"
    sibling_dir = root / "Libs" / "HA" / "NNELib"
    fallback_dir = root / "SharedLib"

    requester = project_dir / "Main.s"
    local_dep = project_dir / "Support.s"
    sibling_dep = sibling_dir / "Support.x"
    fallback_dep = fallback_dir / "Support.s"

    for path in (requester, local_dep, sibling_dep, fallback_dep):
        _write_text(path, '"x"\n"y"\n"z"\n')

    discovery = WorkspaceSourceDiscovery(
        workspace_root=root,
        source_dirs=(project_dir, sibling_dir, fallback_dir),
        program_files=(requester, local_dep, sibling_dep, fallback_dep),
        dependency_files=(),
        abb_lib_dir=None,
        program_files_by_stem={
            "main": (requester,),
            "support": (local_dep, sibling_dep, fallback_dep),
        },
        dependency_files_by_stem={},
    )

    assert discovery.shared_library_root_for(project_dir) == root / "Libs" / "HA"
    assert (
        discovery.locate_source_file(
            "Support",
            extensions=[".s", ".x"],
            requester_dir=project_dir,
        )
        == local_dep
    )
    assert (
        discovery.locate_source_file(
            "Support",
            extensions=[".x", ".s"],
            requester_dir=sibling_dir,
        )
        == sibling_dep
    )


def test_semantic_helpers_format_workspace_failure_and_misc_branches(tmp_path):
    graph = ProjectGraph()
    graph.ast_by_name = {"Main": cast(Any, object()), "Support": cast(Any, object())}
    graph.missing = [
        "Main parse/transform error: root issue",
        "Support parse/transform error: dependency issue",
    ]
    graph.unavailable_libraries = {"controllib", "VendorLib"}
    graph.warnings = ["w1", "w2"]

    message = semantic_core._format_workspace_snapshot_failure("Main", graph, detail="root issue")
    assert "Target 'Main' failed parse/transform: root issue" in message
    assert "Resolved targets (2): Main, Support" in message
    assert "Unavailable libraries (2):" in message
    assert "Other dependency issues (1):" in message
    assert "Validation warnings (2):" in message

    assert semantic_core._format_name_list(["A", "B"], limit=3) == "A, B"
    assert semantic_core._format_name_list(["A", "B", "C"], limit=2).startswith("A, B, ... (+1 more)")

    assert semantic_core._normalize_mode("draft").value == "draft"
    with pytest.raises(ValueError):
        semantic_core._normalize_mode("invalid-mode")

    assert semantic_core._source_file_key(Path("A/B/Main.S")) == "main.s"
    assert semantic_core._source_file_key(None) is None
    assert semantic_core._identifier_contains_column(5, "Value", 7) is True
    assert semantic_core._identifier_contains_column(0, "Value", 7) is False


def test_semantic_helpers_cover_path_and_datatype_edges(tmp_path, monkeypatch):
    assert semantic_core._format_datatype(None) is None
    assert semantic_core._format_datatype(Simple_DataType.INTEGER) == "integer"
    assert semantic_core._format_datatype("CustomType") == "CustomType"
    assert semantic_core._cf("MiXeD") == "mixed"
    assert semantic_core._path_startswith(("BasePicture", "Child"), ("basepicture",)) is True
    assert semantic_core._path_startswith(("BasePicture",), ("BasePicture", "Child")) is False
    assert semantic_core._first_branch_under(tmp_path, tmp_path) is None
    assert semantic_core._first_branch_under(tmp_path, tmp_path / "Libs" / "Support") == "libs"
    assert semantic_core._first_branch_under(tmp_path / "Other", tmp_path / "Libs" / "Support") is None

    broken = tmp_path / "broken"

    def _raise_oserror(self, *args, **kwargs):
        raise OSError("boom")

    monkeypatch.setattr(type(broken), "resolve", _raise_oserror, raising=False)
    assert semantic_core._resolved_path(None) is None
    assert semantic_core._resolved_path(broken) == broken


def test_workspace_source_discovery_orders_sources_and_mixed_extensions(tmp_path):
    root = tmp_path.resolve()
    project_dir = root / "Libs" / "HA" / "ProjectLib"
    sibling_dir = root / "Libs" / "HA" / "SiblingLib"
    shared_dir = root / "SharedLib"
    abb_dir = root / "ABB_lib"

    requester = project_dir / "Main.s"
    local_program = project_dir / "Support.s"
    sibling_program = sibling_dir / "Support.x"
    local_dependency = project_dir / "Support.z"
    abb_dependency = abb_dir / "Vendor.z"

    for path in (requester, local_program, sibling_program, local_dependency, abb_dependency):
        _write_text(path, '"x"\n"y"\n"z"\n')

    discovery = WorkspaceSourceDiscovery(
        workspace_root=root,
        source_dirs=(shared_dir, sibling_dir, project_dir, abb_dir),
        program_files=(requester, local_program, sibling_program),
        dependency_files=(local_dependency, abb_dependency),
        abb_lib_dir=abb_dir,
        program_files_by_stem={
            "main": (requester,),
            "support": (local_program, sibling_program),
        },
        dependency_files_by_stem={
            "support": (local_dependency,),
            "vendor": (abb_dependency,),
        },
    )

    assert discovery.ordered_source_dirs_for(project_dir) == (
        project_dir,
        sibling_dir,
        shared_dir,
        abb_dir,
    )
    assert discovery.other_lib_dirs_for(requester) == (sibling_dir, shared_dir, project_dir, abb_dir)
    assert discovery.shared_library_root_for(root.parent / "Outside") is None
    assert discovery.locate_source_file("Support", extensions=[], requester_dir=project_dir) is None
    assert (
        discovery.locate_source_file("Support", extensions=[".z", ".s"], requester_dir=project_dir) == local_dependency
    )
    assert discovery.locate_source_file("Vendor", extensions=[".z"], requester_dir=project_dir) == abb_dependency


def test_workspace_snapshot_lookup_and_diagnostic_edges(tmp_path):
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

    assert snapshot.list_symbols("v", roots_only=True, limit=1)[0].canonical_path == "BasePicture.Dv"
    assert snapshot.find_definitions("") == []
    assert [definition.canonical_path for definition in snapshot.find_definitions("Value", limit=1)] == [
        "BasePicture.Rec.Value"
    ]
    assert snapshot.find_definitions_at(tmp_path / "Program" / "Missing.s", 1, 1) == []
    assert snapshot.find_references_to("Missing") == []
    assert snapshot.find_accesses_to("Missing") == []
    assert snapshot.find_references_at(tmp_path / "Program" / "Missing.s", 1, 1) == []

    scoped = cast(Any, SimpleNamespace(source_library="Other"))
    unscoped = cast(Any, SimpleNamespace(source_library=None))
    snapshot._semantic_diagnostics_by_file[entry_file.name.casefold()] = (scoped, unscoped)
    assert snapshot.semantic_diagnostics_for_path(entry_file) == (unscoped,)

    single = cast(Any, SimpleNamespace(source_library="Scoped"))
    snapshot._semantic_diagnostics_by_file["single.s"] = (single,)
    assert snapshot.semantic_diagnostics_for_path(tmp_path / "Scoped" / "Single.s") == (single,)

    snapshot._semantic_diagnostics_by_file["ambiguous.s"] = (
        cast(Any, SimpleNamespace(source_library="Alpha")),
        cast(Any, SimpleNamespace(source_library="Beta")),
    )
    assert snapshot.semantic_diagnostics_for_path(tmp_path / "Gamma" / "Ambiguous.s") == ()
