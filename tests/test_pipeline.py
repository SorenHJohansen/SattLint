from types import SimpleNamespace
import json

from sattlint.devtools import pipeline
from sattlint.reporting.variables_report import IssueKind


def test_command_payload_sanitizes_absolute_command_paths():
    windows_python = "C:" + r"\Users\Example\Workspace\SattLint\.venv\Scripts\python.exe"
    junit_path = (
        "--junitxml="
        + "C:"
        + r"\Users\Example\Workspace\SattLint\artifacts\analysis\pytest.junit.xml"
    )
    result = pipeline.CommandResult(
        name="pytest",
        command=[
            windows_python,
            "-m",
            "pytest",
            junit_path,
        ],
        exit_code=0,
        duration_seconds=1.0,
        stdout="",
        stderr="",
    )

    payload = pipeline._command_payload(result)

    assert payload["command"][0].endswith("python.exe") or payload["command"][0] == "<external>/python.exe"
    assert "--junitxml=" in payload["command"][3]


def test_collect_environment_report_has_python_executable(monkeypatch):
    report = pipeline._collect_environment_report()

    assert "python" in report["python"]["executable"].lower()


def test_collect_architecture_report_includes_shadowing_cli_filter():
    report = pipeline._collect_architecture_report()

    assert "dataflow" in report["registered_analyzers"]
    assert IssueKind.SHADOWING.value in report["cli_variable_filter_issue_kinds"]
    assert IssueKind.UI_ONLY.value in report["cli_variable_filter_issue_kinds"]
    assert IssueKind.GLOBAL_SCOPE_MINIMIZATION.value in report["cli_variable_filter_issue_kinds"]
    assert IssueKind.HIDDEN_GLOBAL_COUPLING.value in report["cli_variable_filter_issue_kinds"]
    assert IssueKind.HIGH_FAN_IN_OUT.value in report["cli_variable_filter_issue_kinds"]
    assert report["variables_report_summary_support"][IssueKind.SHADOWING.value] is True
    assert report["variables_report_summary_support"][IssueKind.UI_ONLY.value] is True
    assert report["variables_report_summary_support"][IssueKind.GLOBAL_SCOPE_MINIMIZATION.value] is True
    assert report["variables_report_summary_support"][IssueKind.HIDDEN_GLOBAL_COUPLING.value] is True
    assert report["variables_report_summary_support"][IssueKind.HIGH_FAN_IN_OUT.value] is True


def test_collect_analyzer_registry_report_includes_semantic_rule_mappings():
    report = pipeline._collect_analyzer_registry_report()
    sattline_semantics = next(
        analyzer for analyzer in report["analyzers"] if analyzer["key"] == "sattline-semantics"
    )
    dataflow = next(
        analyzer for analyzer in report["analyzers"] if analyzer["key"] == "dataflow"
    )
    mms_interface = next(
        analyzer for analyzer in report["analyzers"] if analyzer["key"] == "mms-interface"
    )

    duplicate_alarm_tag = next(
        rule for rule in report["rules"] if rule["id"] == "semantic.duplicate-alarm-tag"
    )
    read_before_write = next(
        rule for rule in report["rules"] if rule["id"] == "semantic.read-before-write"
    )
    dead_overwrite = next(
        rule for rule in report["rules"] if rule["id"] == "semantic.dead-overwrite"
    )
    scan_cycle_stale_read = next(
        rule for rule in report["rules"] if rule["id"] == "semantic.scan-cycle-stale-read"
    )
    unconsumed_safety_signal = next(
        rule for rule in report["rules"] if rule["id"] == "semantic.unconsumed-safety-signal"
    )
    unsafe_default = next(
        rule for rule in report["rules"] if rule["id"] == "semantic.unsafe-default-true"
    )

    assert report["generated_by"] == "sattlint.devtools.pipeline"
    assert sattline_semantics["summary_output"] == "sattline-semantics.summary"
    assert "semantic.read-before-write" in sattline_semantics["rule_ids"]
    assert "semantic.duplicate-alarm-tag" in sattline_semantics["rule_ids"]
    assert dataflow["summary_output"] == "dataflow.summary"
    assert "semantic.read-before-write" in dataflow["rule_ids"]
    assert "semantic.dead-overwrite" in dataflow["rule_ids"]
    assert mms_interface["summary_output"] == "mms-interface.summary"
    assert mms_interface["rule_ids"] == []
    assert set(duplicate_alarm_tag) == {
        "id",
        "source",
        "category",
        "severity",
        "applies_to",
        "description",
        "analyzers",
        "outputs",
    }
    assert duplicate_alarm_tag["source"] == "alarm-integrity"
    assert "alarm-integrity" in duplicate_alarm_tag["analyzers"]
    assert "alarm-integrity.summary" in duplicate_alarm_tag["outputs"]
    assert read_before_write["source"] == "dataflow"
    assert "sattline-semantics" in read_before_write["analyzers"]
    assert "dataflow" in read_before_write["analyzers"]
    assert "sattline-semantics.summary" in read_before_write["outputs"]
    assert dead_overwrite["source"] == "dataflow"
    assert "dataflow.summary" in dead_overwrite["outputs"]
    assert scan_cycle_stale_read["source"] == "dataflow"
    assert "sattline-semantics" in scan_cycle_stale_read["analyzers"]
    assert unconsumed_safety_signal["source"] == "safety-paths"
    assert "safety-paths" in unconsumed_safety_signal["analyzers"]
    assert "safety-paths.summary" in unconsumed_safety_signal["outputs"]
    assert unsafe_default["source"] == "unsafe-defaults"
    assert "unsafe-defaults" in unsafe_default["analyzers"]
    assert "unsafe-defaults.summary" in unsafe_default["outputs"]


def test_collect_analyzer_registry_report_exposes_semantic_layer_sources():
    report = pipeline._collect_analyzer_registry_report()

    semantic_layer = report["semantic_layer"]

    assert semantic_layer["analyzer_key"] == "sattline-semantics"
    assert semantic_layer["source_rule_counts"]["variables"] > 0
    assert semantic_layer["source_rule_counts"]["dataflow"] > 0
    assert semantic_layer["source_rule_counts"]["sfc"] > 0
    assert semantic_layer["source_rule_counts"]["alarm-integrity"] > 0
    assert semantic_layer["source_rule_counts"]["safety-paths"] > 0
    assert set(semantic_layer["sources"]).issuperset(
        {"variables", "dataflow", "sfc", "alarm-integrity", "safety-paths"}
    )
    assert sum(semantic_layer["source_rule_counts"].values()) == len(report["rules"])


def test_collect_analyzer_registry_report_maps_rule_ids_back_to_analyzers():
    report = pipeline._collect_analyzer_registry_report()

    analyzer_rule_ids = {
        analyzer["key"]: set(analyzer["rule_ids"])
        for analyzer in report["analyzers"]
    }

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
    snapshot.find_accesses_to = lambda item: list(accesses[item.canonical_path])

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


def test_collect_impact_analysis_report_aggregates_reverse_dependencies(tmp_path):
    dependency_graph_report = {
        "nodes": [
            {"id": "main", "kind": "library"},
            {"id": "support", "kind": "library"},
            {"id": "shared", "kind": "library"},
        ],
        "edges": [
            {
                "source": "main",
                "target": "support",
                "kind": "depends_on",
                "entries": ["Program/Main.s"],
            },
            {
                "source": "support",
                "target": "shared",
                "kind": "depends_on",
                "entries": ["Libraries/Support.s"],
            },
        ],
        "snapshot_failures": [
            {
                "entry_file": "Program/Broken.s",
                "error": "broken dependency graph input",
                "error_type": "RuntimeError",
            }
        ],
    }
    call_graph_report = {
        "nodes": [
            {"id": "Main", "kind": "module"},
            {"id": "Main.Guard", "kind": "module"},
            {"id": "Main.Observer", "kind": "module"},
        ],
        "edges": [
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
            {
                "source": "Main.Observer",
                "target": "Main.Guard",
                "kind": "module-access",
                "reads": 1,
                "writes": 0,
                "access_count": 1,
                "symbol_count": 1,
                "symbols": ["Main.Guard.Seen"],
                "entries": ["Program/Main.s"],
            },
        ],
        "snapshot_failures": [
            {
                "entry_file": "Program/Broken.s",
                "error": "broken dependency graph input",
                "error_type": "RuntimeError",
            }
        ],
    }

    report = pipeline._collect_impact_analysis_report(
        tmp_path,
        dependency_graph_report=dependency_graph_report,
        call_graph_report=call_graph_report,
    )

    assert report["report_kind"] == "impact-analysis"
    assert report["snapshot_failures"] == dependency_graph_report["snapshot_failures"]

    support_impact = next(item for item in report["library_impacts"] if item["id"] == "support")
    shared_impact = next(item for item in report["library_impacts"] if item["id"] == "shared")
    main_module_impact = next(item for item in report["module_impacts"] if item["id"] == "Main")

    assert support_impact["direct_dependents"] == ["main"]
    assert support_impact["transitive_dependents"] == ["main"]
    assert shared_impact["direct_dependents"] == ["support"]
    assert shared_impact["transitive_dependents"] == ["main", "support"]
    assert shared_impact["transitive_entry_files"] == ["Libraries/Support.s", "Program/Main.s"]

    assert main_module_impact["direct_dependents"] == ["Main.Guard"]
    assert main_module_impact["transitive_dependents"] == ["Main.Guard", "Main.Observer"]
    assert main_module_impact["direct_reads"] == 1
    assert main_module_impact["transitive_reads"] == 2
    assert main_module_impact["direct_access_count"] == 1
    assert main_module_impact["transitive_access_count"] == 2
    assert main_module_impact["direct_symbols"] == ["Main.ExecuteLocal"]
    assert main_module_impact["transitive_symbols"] == ["Main.ExecuteLocal", "Main.Guard.Seen"]
    assert main_module_impact["direct_symbol_count"] == 1
    assert main_module_impact["transitive_symbol_count"] == 2


def test_run_pipeline_serializes_structural_graph_reports(monkeypatch, tmp_path):
    monkeypatch.setattr(pipeline, "_collect_environment_report", lambda: {"python": {"executable": "python"}})
    monkeypatch.setattr(pipeline, "_collect_architecture_report", lambda: {"findings": []})
    monkeypatch.setattr(pipeline, "_collect_analyzer_registry_report", lambda: {"rules": []})
    monkeypatch.setattr(
        pipeline,
        "_collect_workspace_graph_inputs",
        lambda workspace_root=pipeline.REPO_ROOT: (SimpleNamespace(program_files=(), dependency_files=()), [], []),
    )
    monkeypatch.setattr(
        pipeline,
        "_collect_dependency_graph_report",
        lambda workspace_root=pipeline.REPO_ROOT, *, graph_inputs=None: {"edges": [{"source": "main", "target": "support"}]},
    )
    monkeypatch.setattr(
        pipeline,
        "_collect_call_graph_report",
        lambda workspace_root=pipeline.REPO_ROOT, *, graph_inputs=None: {"edges": [{"source": "Main", "target": "Main"}]},
    )
    monkeypatch.setattr(
        pipeline,
        "_collect_impact_analysis_report",
        lambda workspace_root=pipeline.REPO_ROOT, *, graph_inputs=None, dependency_graph_report=None, call_graph_report=None: {
            "library_impacts": [{"id": "support"}],
            "module_impacts": [{"id": "Main"}, {"id": "Main.Guard"}],
        },
    )
    monkeypatch.setattr(pipeline, "_resolve_python_executable", lambda: "python")
    monkeypatch.setattr(
        pipeline,
        "_run_command",
        lambda name, command, cwd=pipeline.REPO_ROOT: pipeline.CommandResult(
            name=name,
            command=command,
            exit_code=0,
            duration_seconds=0.0,
            stdout="[]" if name == "ruff" else "",
            stderr="",
        ),
    )
    monkeypatch.setattr(pipeline, "_parse_json_lines", lambda raw_output: [])
    monkeypatch.setattr(
        pipeline,
        "_parse_pytest_junit",
        lambda xml_path: {
            "summary": {"tests": 0, "failures": 0, "errors": 0, "skipped": 0},
            "testcases": [],
        },
    )

    summary = pipeline._run_pipeline(
        tmp_path,
        trace_target=None,
        profile="full",
        include_vulture=False,
        include_bandit=False,
    )

    status_report = json.loads((tmp_path / "status.json").read_text(encoding="utf-8"))

    assert (tmp_path / "status.json").exists()
    assert (tmp_path / "dependency_graph.json").exists()
    assert (tmp_path / "call_graph.json").exists()
    assert (tmp_path / "impact_analysis.json").exists()
    assert summary["profile"] == "full"
    assert summary["entry_report"] == "status.json"
    assert summary["reports"]["dependency_graph"] == "dependency_graph.json"
    assert summary["reports"]["call_graph"] == "call_graph.json"
    assert summary["reports"]["impact_analysis"] == "impact_analysis.json"
    assert status_report["overall_status"] == "pass"
    assert status_report["tool_statuses"]["mypy"]["status"] == "pass"
    assert summary["counts"]["dependency_graph_edges"] == 1
    assert summary["counts"]["call_graph_edges"] == 1
    assert summary["counts"]["impact_analysis_library_nodes"] == 1
    assert summary["counts"]["impact_analysis_module_nodes"] == 2
    assert summary["counts"]["workspace_graph_snapshot_failures"] == 0


def test_run_pipeline_quick_profile_skips_optional_reports(monkeypatch, tmp_path):
    commands: list[tuple[str, list[str]]] = []

    monkeypatch.setattr(pipeline, "_collect_environment_report", lambda: {"python": {"executable": "python"}})
    monkeypatch.setattr(pipeline, "_resolve_python_executable", lambda: "python")

    def fake_run_command(name, command, cwd=pipeline.REPO_ROOT):
        commands.append((name, command))
        stdout = "[]" if name == "ruff" else ""
        return pipeline.CommandResult(
            name=name,
            command=command,
            exit_code=0,
            duration_seconds=0.0,
            stdout=stdout,
            stderr="",
        )

    monkeypatch.setattr(pipeline, "_run_command", fake_run_command)
    monkeypatch.setattr(pipeline, "_parse_json_lines", lambda raw_output: [])
    monkeypatch.setattr(
        pipeline,
        "_parse_pytest_junit",
        lambda xml_path: {
            "summary": {"tests": 3, "failures": 0, "errors": 0, "skipped": 0},
            "testcases": [],
        },
    )

    summary = pipeline._run_pipeline(
        tmp_path,
        trace_target=None,
        profile="quick",
    )

    status_report = json.loads((tmp_path / "status.json").read_text(encoding="utf-8"))

    assert [name for name, _command in commands] == ["ruff", "mypy", "pytest"]
    pytest_command = next(command for name, command in commands if name == "pytest")
    assert "-o" in pytest_command
    assert any(part.startswith("addopts=--strict-markers --strict-config") for part in pytest_command)
    assert summary["profile"] == "quick"
    assert summary["reports"]["vulture"] is None
    assert summary["reports"]["bandit"] is None
    assert summary["reports"]["architecture"] is None
    assert summary["reports"]["dependency_graph"] is None
    assert summary["counts"]["workspace_graph_snapshot_failures"] == 0
    assert status_report["overall_status"] == "pass"
    assert status_report["tool_statuses"]["vulture"]["status"] == "skipped"
    assert status_report["tool_statuses"]["bandit"]["status"] == "skipped"
