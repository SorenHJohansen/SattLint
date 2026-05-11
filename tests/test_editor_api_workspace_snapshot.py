from pathlib import Path

import pytest

from sattlint.core import semantic as semantic_core
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
