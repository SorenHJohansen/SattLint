# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportPrivateUsage=false, reportIndexIssue=false
# ruff: noqa: F403, F405
from ._pipeline_collection_test_support import *


def test_collect_analyzer_registry_report_maps_rule_ids_back_to_analyzers():
    report = pipeline._collect_analyzer_registry_report()

    analyzer_rule_ids = {analyzer["key"]: set(analyzer["rule_ids"]) for analyzer in report["analyzers"]}

    for rule in report["rules"]:
        for analyzer_key in rule["analyzers"]:
            assert rule["id"] in analyzer_rule_ids[analyzer_key]


def test_collect_dependency_graph_report_aggregates_library_edges(monkeypatch, tmp_path):
    discovery = SimpleNamespace(
        program_files=(tmp_path / "Program" / "Main.s",),
        dependency_files=(tmp_path / "Program" / "Main.l",),
    )
    snapshot = SimpleNamespace(
        entry_file=tmp_path / "Program" / "Main.s",
        project_graph=SimpleNamespace(
            library_dependencies={
                "main": {"support", "controllib"},
            }
        ),
    )
    failures = [
        {
            "entry_file": "tests/fixtures/Broken.s",
            "error": "broken dependency graph input",
            "error_type": "RuntimeError",
        }
    ]

    monkeypatch.setattr(
        pipeline,
        "_collect_workspace_graph_inputs",
        lambda workspace_root=pipeline.REPO_ROOT: (discovery, [snapshot], failures),
    )

    report = pipeline._collect_dependency_graph_report(tmp_path)

    assert report["nodes"] == [
        {"id": "controllib", "kind": "library"},
        {"id": "main", "kind": "library"},
        {"id": "support", "kind": "library"},
    ]
    assert report["edges"] == [
        {
            "source": "main",
            "target": "controllib",
            "kind": "depends_on",
            "entries": ["Program/Main.s"],
        },
        {
            "source": "main",
            "target": "support",
            "kind": "depends_on",
            "entries": ["Program/Main.s"],
        },
    ]
    assert report["source_files"] == {
        "program_files": ["Program/Main.s"],
        "dependency_files": ["Program/Main.l"],
    }
    assert report["snapshot_failures"] == failures


def test_collect_call_graph_report_aggregates_module_access_edges(monkeypatch, tmp_path):
    definition = SimpleNamespace(
        canonical_path="Main.ExecuteLocal",
        declaration_module_path=("Main",),
        field_path=None,
    )
    snapshot = SimpleNamespace(
        entry_file=tmp_path / "Program" / "Main.s",
        base_picture=SimpleNamespace(name="Main"),
        definitions=(definition,),
    )
    accesses = {
        "Main.ExecuteLocal": [
            SimpleNamespace(kind="write", use_module_path=("Main",), syntactic_ref="ExecuteLocal"),
            SimpleNamespace(kind="read", use_module_path=("Main", "Guard"), syntactic_ref="ExecuteLocal"),
        ]
    }
    snapshot.iter_access_events_by_definition = lambda roots_only=False: (
        (definition, tuple(accesses[definition.canonical_path])),
    )

    monkeypatch.setattr(
        pipeline,
        "_collect_workspace_graph_inputs",
        lambda workspace_root=pipeline.REPO_ROOT: (
            SimpleNamespace(program_files=(snapshot.entry_file,), dependency_files=()),
            [snapshot],
            [],
        ),
    )

    report = pipeline._collect_call_graph_report(tmp_path)

    assert report["graph_kind"] == "module-access"
    assert report["nodes"] == [
        {"id": "Main", "kind": "module"},
        {"id": "Main.Guard", "kind": "module"},
    ]
    assert report["edges"] == [
        {
            "source": "Main",
            "target": "Main",
            "kind": "module-access",
            "reads": 0,
            "writes": 1,
            "access_count": 1,
            "symbol_count": 1,
            "symbols": ["Main.ExecuteLocal"],
            "entries": ["Program/Main.s"],
        },
        {
            "source": "Main.Guard",
            "target": "Main",
            "kind": "module-access",
            "reads": 1,
            "writes": 0,
            "access_count": 1,
            "symbol_count": 1,
            "symbols": ["Main.ExecuteLocal"],
            "entries": ["Program/Main.s"],
        },
    ]


def test_collect_structural_reports_streams_snapshots_once(monkeypatch, tmp_path):
    entry_files = (
        tmp_path / "Program" / "Main.s",
        tmp_path / "Program" / "Support.s",
    )
    discovery = SimpleNamespace(program_files=entry_files, dependency_files=())
    definition = SimpleNamespace(
        canonical_path="Main.ExecuteLocal",
        declaration_module_path=("Main",),
        field_path=None,
    )
    loaded_entries: list[str] = []
    progress_messages: list[str] = []

    def fake_load_workspace_snapshot(
        entry_file,
        *,
        workspace_root=None,
        discovery=None,
        collect_variable_diagnostics=False,
        _analysis_provider=None,
    ):
        loaded_entries.append(entry_file.name)
        return SimpleNamespace(
            entry_file=entry_file,
            project_graph=SimpleNamespace(library_dependencies={entry_file.stem.lower(): {"support"}}),
            base_picture=SimpleNamespace(name="Main"),
            iter_access_events_by_definition=lambda roots_only=False: (
                (
                    definition,
                    (SimpleNamespace(kind="read", use_module_path=("Main", "Guard"), syntactic_ref="ExecuteLocal"),),
                ),
            ),
        )

    monkeypatch.setattr(structural_reports, "discover_workspace_sources", lambda workspace_root: discovery)
    monkeypatch.setattr(structural_reports, "load_workspace_snapshot", fake_load_workspace_snapshot)
    monkeypatch.setattr(structural_reports, "collect_architecture_report", lambda: {"findings": []})
    monkeypatch.setattr(structural_reports, "collect_analyzer_registry_report", lambda: {"rules": []})

    bundle = structural_reports.collect_structural_reports(
        tmp_path,
        progress_callback=progress_messages.append,
    )

    assert bundle.structural_budget_report["setpoints"] == structural_reports.STRUCTURAL_BUDGET_SETPOINTS
    assert loaded_entries == ["Main.s", "Support.s"]
    assert bundle.graph_inputs.snapshots == []
    assert bundle.dependency_graph_report["snapshot_count"] == 2
    assert bundle.call_graph_report["snapshot_count"] == 2
    assert bundle.dependency_graph_report["edges"] == [
        {
            "source": "main",
            "target": "support",
            "kind": "depends_on",
            "entries": ["Program/Main.s"],
        },
        {
            "source": "support",
            "target": "support",
            "kind": "depends_on",
            "entries": ["Program/Support.s"],
        },
    ]
    assert any(message.startswith("Structural: loading 1/2") for message in progress_messages)
    assert any(message.startswith("Structural: loading 2/2") for message in progress_messages)


def test_collect_structural_reports_limits_entries_to_fixture_programs(monkeypatch, tmp_path):
    fixture_entry = tmp_path / "tests" / "fixtures" / "sample_sattline_files" / "Main.s"
    template_entry = tmp_path / "DocTemplates" / "KaGCUF.x"
    discovery = SimpleNamespace(
        workspace_root=tmp_path,
        source_dirs=(fixture_entry.parent, template_entry.parent),
        program_files=(fixture_entry, template_entry),
        dependency_files=(),
        abb_lib_dir=None,
        program_files_by_stem={},
        dependency_files_by_stem={},
    )
    definition = SimpleNamespace(
        canonical_path="Main.ExecuteLocal",
        declaration_module_path=("Main",),
        field_path=None,
    )
    loaded_entries: list[str] = []

    def fake_load_workspace_snapshot(
        entry_file,
        *,
        workspace_root=None,
        discovery=None,
        collect_variable_diagnostics=False,
        _analysis_provider=None,
    ):
        loaded_entries.append(entry_file.as_posix())
        return SimpleNamespace(
            entry_file=entry_file,
            project_graph=SimpleNamespace(library_dependencies={entry_file.stem.lower(): {"support"}}),
            base_picture=SimpleNamespace(name="Main"),
            iter_access_events_by_definition=lambda roots_only=False: (
                (
                    definition,
                    (SimpleNamespace(kind="read", use_module_path=("Main",), syntactic_ref="ExecuteLocal"),),
                ),
            ),
        )

    monkeypatch.setattr(structural_reports, "discover_workspace_sources", lambda workspace_root: discovery)
    monkeypatch.setattr(structural_reports, "load_workspace_snapshot", fake_load_workspace_snapshot)
    monkeypatch.setattr(structural_reports, "collect_architecture_report", lambda: {"findings": []})
    monkeypatch.setattr(structural_reports, "collect_analyzer_registry_report", lambda: {"rules": []})

    bundle = structural_reports.collect_structural_reports(tmp_path)

    assert bundle.structural_budget_report["setpoints"] == structural_reports.STRUCTURAL_BUDGET_SETPOINTS
    assert loaded_entries == [fixture_entry.as_posix()]
    assert bundle.graph_inputs.discovery.program_files == (fixture_entry,)
    assert bundle.dependency_graph_report["source_files"]["program_files"] == [
        "tests/fixtures/sample_sattline_files/Main.s"
    ]


def test_progress_reporter_log_emits_stdout(capsys, tmp_path):
    reporter = ProgressReporter(
        kind="sattlint.test.progress",
        title="Test",
        output_dir=tmp_path,
        write_json=lambda path, payload: None,
        stages=[("one", "Stage one")],
    )

    reporter.log("structural snapshot 1/3")

    output = capsys.readouterr().out

    assert "structural snapshot 1/3" in output


def test_build_pipeline_finding_collection_normalizes_tool_payloads(tmp_path):
    collection = build_pipeline_finding_collection(
        repo_root=tmp_path,
        ruff_findings=[
            {
                "code": "F401",
                "message": "Imported but unused",
                "filename": str(tmp_path / "src" / "sample.py"),
                "location": {"row": 4, "column": 8},
            }
        ],
        pyright_findings=[
            {
                "severity": "error",
                "message": "Incompatible types in assignment",
                "file": str(tmp_path / "src" / "typed.py"),
                "line": 9,
                "column": 3,
                "errorCode": "assignment",
            }
        ],
        pytest_report={
            "summary": {"tests": 2, "failures": 1, "errors": 0, "skipped": 0},
            "testcases": [
                {
                    "classname": "tests.test_sample",
                    "name": "test_failure",
                    "outcome": "failed",
                    "detail": "tests/test_sample.py:23: AssertionError",
                    "nodeid": "tests/test_sample.py::test_failure",
                }
            ],
        },
        vulture_findings=[
            {
                "file": str(tmp_path / "src" / "dead.py"),
                "line": 7,
                "message": "unused function 'helper'",
                "confidence": 95,
            }
        ],
        bandit_findings=[
            {
                "filename": str(tmp_path / "src" / "security.py"),
                "line_number": 12,
                "issue_text": "Use of assert detected.",
                "issue_severity": "LOW",
                "issue_confidence": "HIGH",
                "test_id": "B101",
            }
        ],
        architecture_findings=[
            {
                "id": "analyzer-exposure-gap",
                "severity": "medium",
                "message": "Some analyzers are not exposed.",
                "missing_analyzers": ["naming-consistency"],
            }
        ],
    )

    payload = collection.to_dict()

    assert_findings_collection(
        payload,
        finding_count=6,
        rule_ids=(
            "ruff.f401",
            "pyright.assignment",
            "pytest.failures",
            "vulture.dead-code",
            "bandit.b101",
            "analyzer-exposure-gap",
        ),
    )
    assert any(item["rule_id"] == "ruff.f401" and item["location"]["line"] == 4 for item in payload["findings"])
    assert any(
        item["rule_id"] == "pyright.assignment"
        and item["severity"] == "high"
        and item["location"]["line"] == 9
        and item["owner_surface"] == "python-types"
        for item in payload["findings"]
    )
    assert any(
        item["rule_id"] == "pytest.failures"
        and item["file"] == "tests/test_sample.py"
        and item["line"] == 23
        and item["owner_surface"] == "python-tests"
        and item["minimal_reproducer"] == "python -m pytest tests/test_sample.py::test_failure -x -q --tb=short"
        and item["suggested_next_command"] == "python -m pytest tests/test_sample.py::test_failure -x -q --tb=short"
        for item in payload["findings"]
    )
    assert any(
        item["rule_id"] == "vulture.dead-code"
        and item["confidence"] == "high"
        and item["severity"] == "high"
        and item["data"]
        == {
            "confidence_percent": 95,
            "dead_code_kind": "function",
            "symbol": "helper",
        }
        for item in payload["findings"]
    )
    assert any(item["rule_id"] == "bandit.b101" and item["category"] == "security" for item in payload["findings"])
    assert any(
        item["rule_id"] == "analyzer-exposure-gap" and item["category"] == "architecture"
        for item in payload["findings"]
    )
