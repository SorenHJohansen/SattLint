import json
from types import SimpleNamespace

from sattlint.devtools import impact_analyzer
from sattlint.devtools._semble_adapter import SembleMatch, SembleSearchResponse
from sattlint.devtools.structural_reports import WorkspaceGraphInputs


def test_build_impact_analysis_selection_filters_targets_and_expands_entry_files(tmp_path):
    entry_file = tmp_path / "Program" / "Main.s"
    graph_inputs = WorkspaceGraphInputs(
        discovery=SimpleNamespace(program_files=[entry_file], dependency_files=[]),
        snapshots=[
            SimpleNamespace(
                entry_file=entry_file,
                base_picture=SimpleNamespace(name="Main", origin_lib="main"),
                definitions=[
                    SimpleNamespace(field_path=None, declaration_module_path=("Main",)),
                    SimpleNamespace(field_path=None, declaration_module_path=("Main", "Guard")),
                    SimpleNamespace(field_path=("state",), declaration_module_path=("Main", "Guard")),
                ],
            )
        ],
        snapshot_failures=[],
    )
    impact_report = {
        "library_impacts": [
            {"id": "main", "direct_dependents": ["consumer"]},
            {"id": "support", "direct_dependents": ["main"]},
        ],
        "module_impacts": [
            {"id": "Main", "direct_dependents": ["Main.Observer"]},
            {"id": "Main.Guard", "direct_dependents": ["Main.Observer"]},
            {"id": "Main.Observer", "direct_dependents": []},
        ],
        "snapshot_failures": [{"entry_file": "Program/Broken.s", "error": "boom", "error_type": "RuntimeError"}],
    }

    report = impact_analyzer.build_impact_analysis_selection(
        tmp_path,
        libraries=["SUPPORT"],
        modules=["main"],
        entry_files=["Program/Main.s"],
        graph_inputs=graph_inputs,
        dependency_graph_report={"nodes": [], "edges": [], "snapshot_failures": []},
        call_graph_report={"nodes": [], "edges": [], "snapshot_failures": []},
        impact_analysis_report=impact_report,
    )

    assert report["status"] == "ok"
    assert report["requested_targets"] == {
        "libraries": ["SUPPORT"],
        "modules": ["main"],
        "entry_files": ["Program/Main.s"],
    }
    assert report["resolved_targets"]["libraries"] == ["main", "support"]
    assert report["resolved_targets"]["modules"] == ["Main", "Main.Guard"]
    assert report["resolved_targets"]["entry_files"] == ["Program/Main.s"]
    assert report["resolved_targets"]["entry_file_expansions"] == [
        {
            "entry_file": "Program/Main.s",
            "libraries": ["main"],
            "modules": ["Main", "Main.Guard"],
        }
    ]
    assert [item["id"] for item in report["selected_impacts"]["libraries"]] == ["main", "support"]
    assert [item["id"] for item in report["selected_impacts"]["modules"]] == ["Main", "Main.Guard"]
    assert report["snapshot_failures"] == impact_report["snapshot_failures"]
    assert report["errors"] == []


def test_build_impact_analysis_selection_reports_unknown_targets(tmp_path):
    graph_inputs = WorkspaceGraphInputs(
        discovery=SimpleNamespace(program_files=[], dependency_files=[]),
        snapshots=[],
        snapshot_failures=[],
    )
    impact_report = {
        "library_impacts": [{"id": "support", "direct_dependents": ["main"]}],
        "module_impacts": [{"id": "Main", "direct_dependents": []}],
        "snapshot_failures": [],
    }

    report = impact_analyzer.build_impact_analysis_selection(
        tmp_path,
        libraries=["missing-lib"],
        modules=["missing-module"],
        entry_files=["Program/Missing.s"],
        graph_inputs=graph_inputs,
        dependency_graph_report={"nodes": [], "edges": [], "snapshot_failures": []},
        call_graph_report={"nodes": [], "edges": [], "snapshot_failures": []},
        impact_analysis_report=impact_report,
    )

    assert report["status"] == "error"
    assert report["resolved_targets"] == {
        "libraries": [],
        "modules": [],
        "entry_files": [],
        "entry_file_expansions": [],
    }
    assert report["selected_impacts"] == {"libraries": [], "modules": []}
    assert report["errors"] == [
        {
            "selector_kind": "library",
            "value": "missing-lib",
            "message": "Unknown library selector: missing-lib",
        },
        {
            "selector_kind": "module",
            "value": "missing-module",
            "message": "Unknown module selector: missing-module",
        },
        {
            "selector_kind": "entry_file",
            "value": "Program/Missing.s",
            "message": "Unknown entry-file selector: Program/Missing.s",
        },
    ]


def test_build_impact_analysis_selection_resolves_query_to_entry_files(tmp_path, monkeypatch):
    entry_file = tmp_path / "Program" / "Main.s"
    graph_inputs = WorkspaceGraphInputs(
        discovery=SimpleNamespace(program_files=[entry_file], dependency_files=[]),
        snapshots=[
            SimpleNamespace(
                entry_file=entry_file,
                base_picture=SimpleNamespace(name="Main", origin_lib="main"),
                definitions=[
                    SimpleNamespace(field_path=None, declaration_module_path=("Main",)),
                    SimpleNamespace(field_path=None, declaration_module_path=("Main", "Guard")),
                ],
            )
        ],
        snapshot_failures=[],
    )
    impact_report = {
        "library_impacts": [{"id": "main", "direct_dependents": ["consumer"]}],
        "module_impacts": [
            {"id": "Main", "direct_dependents": ["Main.Guard"]},
            {"id": "Main.Guard", "direct_dependents": []},
        ],
        "snapshot_failures": [],
    }
    monkeypatch.setattr(
        impact_analyzer,
        "search_local_repo",
        lambda query, *, repo_root, top_k: SembleSearchResponse(
            available=True,
            backend="python-library",
            query=query,
            repo_path=repo_root.as_posix(),
            top_k=top_k,
            results=(
                SembleMatch(
                    file_path="Program/Main.s",
                    start_line=12,
                    end_line=20,
                    content="SEQUENCE Main",
                    score=0.83,
                ),
            ),
            explanation="ok",
        ),
    )

    report = impact_analyzer.build_impact_analysis_selection(
        tmp_path,
        query="guard sequence logic",
        graph_inputs=graph_inputs,
        dependency_graph_report={"nodes": [], "edges": [], "snapshot_failures": []},
        call_graph_report={"nodes": [], "edges": [], "snapshot_failures": []},
        impact_analysis_report=impact_report,
    )

    assert report["status"] == "ok"
    assert report["resolved_targets"]["entry_files"] == ["Program/Main.s"]
    assert report["resolved_targets"]["libraries"] == ["main"]
    assert report["resolved_targets"]["modules"] == ["Main", "Main.Guard"]
    assert report["semantic_query"] == {
        "status": "ok",
        "query": "guard sequence logic",
        "backend": "python-library",
        "candidate_files": [
            {
                "file_path": "Program/Main.s",
                "start_line": 12,
                "end_line": 20,
                "score": 0.83,
                "selected_entry_file": "Program/Main.s",
            }
        ],
        "selected_entry_files": ["Program/Main.s"],
        "explanation": "ok",
    }


def test_build_impact_analysis_selection_reports_unresolved_query_without_explicit_targets(tmp_path, monkeypatch):
    graph_inputs = WorkspaceGraphInputs(
        discovery=SimpleNamespace(program_files=[], dependency_files=[]),
        snapshots=[],
        snapshot_failures=[],
    )
    monkeypatch.setattr(
        impact_analyzer,
        "search_local_repo",
        lambda query, *, repo_root, top_k: SembleSearchResponse(
            available=True,
            backend="python-library",
            query=query,
            repo_path=repo_root.as_posix(),
            top_k=top_k,
            results=(),
            explanation="no hits",
        ),
    )

    report = impact_analyzer.build_impact_analysis_selection(
        tmp_path,
        query="missing guard flow",
        graph_inputs=graph_inputs,
        dependency_graph_report={"nodes": [], "edges": [], "snapshot_failures": []},
        call_graph_report={"nodes": [], "edges": [], "snapshot_failures": []},
        impact_analysis_report={"library_impacts": [], "module_impacts": [], "snapshot_failures": []},
    )

    assert report["status"] == "error"
    assert report["errors"] == [
        {
            "selector_kind": "query",
            "value": "missing guard flow",
            "message": "Semantic query returned no candidate files: missing guard flow",
        }
    ]
    assert report["semantic_query"]["status"] == "no-results"


def test_main_writes_report_json(tmp_path, monkeypatch, capsys):
    expected_report = {
        "generated_by": "sattlint.devtools.impact_analyzer",
        "report_kind": "impact-analysis-selection",
        "status": "ok",
        "workspace_root": ".",
        "requested_targets": {"libraries": ["support"], "modules": [], "entry_files": []},
        "resolved_targets": {
            "libraries": ["support"],
            "modules": [],
            "entry_files": [],
            "entry_file_expansions": [],
        },
        "selected_impacts": {"libraries": [{"id": "support"}], "modules": []},
        "snapshot_failures": [],
        "errors": [],
    }
    monkeypatch.setattr(impact_analyzer, "build_impact_analysis_selection", lambda *args, **kwargs: expected_report)

    output_dir = tmp_path / "artifacts"
    exit_code = impact_analyzer.main(
        [
            "--workspace-root",
            str(tmp_path),
            "--library",
            "support",
            "--output-dir",
            str(output_dir),
        ]
    )

    assert exit_code == 0
    assert json.loads(capsys.readouterr().out) == expected_report
    assert (
        json.loads((output_dir / impact_analyzer.DEFAULT_OUTPUT_FILENAME).read_text(encoding="utf-8"))
        == expected_report
    )


def test_main_returns_failure_when_output_report_write_fails(tmp_path, monkeypatch, capsys):
    expected_report = {
        "generated_by": "sattlint.devtools.impact_analyzer",
        "report_kind": "impact-analysis-selection",
        "status": "ok",
        "workspace_root": ".",
        "requested_targets": {"libraries": ["support"], "modules": [], "entry_files": []},
        "resolved_targets": {
            "libraries": ["support"],
            "modules": [],
            "entry_files": [],
            "entry_file_expansions": [],
        },
        "selected_impacts": {"libraries": [{"id": "support"}], "modules": []},
        "snapshot_failures": [],
        "errors": [],
    }
    monkeypatch.setattr(impact_analyzer, "build_impact_analysis_selection", lambda *args, **kwargs: expected_report)
    monkeypatch.setattr(
        impact_analyzer,
        "_write_impact_report",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(PermissionError("locked")),
    )

    exit_code = impact_analyzer.main(
        [
            "--workspace-root",
            str(tmp_path),
            "--library",
            "support",
            "--output-dir",
            str(tmp_path / "artifacts"),
            "--no-progress",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert json.loads(captured.out) == expected_report
    assert "impact analysis output error: locked" in captured.err


def test_main_returns_error_code_for_invalid_selection(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(
        impact_analyzer,
        "build_impact_analysis_selection",
        lambda *args, **kwargs: {
            "generated_by": "sattlint.devtools.impact_analyzer",
            "report_kind": "impact-analysis-selection",
            "status": "error",
            "workspace_root": ".",
            "requested_targets": {"libraries": [], "modules": [], "entry_files": []},
            "resolved_targets": {
                "libraries": [],
                "modules": [],
                "entry_files": [],
                "entry_file_expansions": [],
            },
            "selected_impacts": {"libraries": [], "modules": []},
            "snapshot_failures": [],
            "errors": [{"selector_kind": "targets", "value": None, "message": "missing"}],
        },
    )

    exit_code = impact_analyzer.main(["--workspace-root", str(tmp_path), "--library", "support"])

    assert exit_code == 2
    assert json.loads(capsys.readouterr().out)["status"] == "error"


def test_main_reports_progress_on_stderr(tmp_path, monkeypatch, capsys):
    expected_report = {
        "generated_by": "sattlint.devtools.impact_analyzer",
        "report_kind": "impact-analysis-selection",
        "status": "ok",
        "workspace_root": ".",
        "requested_targets": {"libraries": ["support"], "modules": [], "entry_files": []},
        "resolved_targets": {
            "libraries": ["support"],
            "modules": [],
            "entry_files": [],
            "entry_file_expansions": [],
        },
        "selected_impacts": {"libraries": [{"id": "support"}], "modules": []},
        "snapshot_failures": [],
        "errors": [],
    }

    def _build_report(*args, **kwargs):
        progress_callback = kwargs.get("progress_callback")
        assert progress_callback is not None
        progress_callback("Impact analysis: loading workspace graph inputs")
        return expected_report

    monkeypatch.setattr(impact_analyzer, "build_impact_analysis_selection", _build_report)

    exit_code = impact_analyzer.main(["--workspace-root", str(tmp_path), "--library", "support"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert json.loads(captured.out) == expected_report
    assert "Impact analysis: loading workspace graph inputs" in captured.err
