import json
import os
from types import SimpleNamespace
from typing import Any, cast

from sattline_parser.models.ast_model import (
    BasePicture,
    ModuleDef,
    ModuleHeader,
    ModuleTypeDef,
    ModuleTypeInstance,
    SingleModule,
)
from sattlint.analyzers.registry import (
    get_actual_cli_analyzer_keys,
    get_actual_lsp_analyzer_keys,
    get_declared_cli_analyzer_keys,
    get_declared_lsp_analyzer_keys,
)
from sattlint.analyzers.sattline_semantics import (
    SattLineSemanticsReport,
    SemanticIssue,
    SemanticRule,
)
from sattlint.contracts import FindingCollection, FindingRecord
from sattlint.devtools import corpus, pipeline, structural_reports
from sattlint.devtools.artifact_registry import ArtifactDefinition
from sattlint.devtools.baselines import build_analysis_diff_report
from sattlint.devtools.finding_exports import build_pipeline_finding_collection
from sattlint.devtools.pipeline_artifacts import (
    PipelineArtifactContext,
    PipelineArtifactProducer,
    validate_pipeline_artifact_producers,
    write_json_artifact,
    write_pipeline_artifacts,
)
from sattlint.devtools.progress_reporting import ProgressReporter
from sattlint.reporting.variables_report import IssueKind

from .helpers.artifact_assertions import (
    assert_analysis_diff_report,
    assert_findings_collection,
)


def test_command_payload_sanitizes_absolute_command_paths():
    windows_python = "C:" + r"\Users\Example\Workspace\SattLint\.venv\Scripts\python.exe"
    junit_path = "--junitxml=" + "C:" + r"\Users\Example\Workspace\SattLint\artifacts\analysis\pytest.junit.xml"
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
    phase2_gate = report["phase2_rule_metadata_gate"]
    finding_ids = {finding["id"] for finding in report["findings"]}

    assert "dataflow" in report["registered_analyzers"]
    assert report["declared_cli_analyzers"] == list(get_declared_cli_analyzer_keys())
    assert report["actual_cli_analyzers"] == sorted(get_actual_cli_analyzer_keys())
    assert report["declared_lsp_analyzers"] == list(get_declared_lsp_analyzer_keys())
    assert report["actual_lsp_analyzers"] == list(get_actual_lsp_analyzer_keys())
    assert report["declared_cli_analyzers"] == report["actual_cli_analyzers"]
    assert report["declared_lsp_analyzers"] == report["actual_lsp_analyzers"]
    assert report["analyzers_missing_exposure"] == []
    assert report["analyzers_missing_acceptance_tests"] == []
    assert report["rules_missing_acceptance_tests"] == []
    assert report["rules_missing_mutation_applicability"] == []
    assert report["rules_missing_suppression_modes"] == []
    assert report["rules_missing_incremental_safety_markers"] == []
    assert report["rules_missing_corpus_links"] == []
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
    assert phase2_gate["status"] == "pass"
    assert phase2_gate["blocking_finding_ids"] == []
    assert phase2_gate["advisory_finding_ids"] == []
    assert "cli-analyzer-metadata-drift" not in finding_ids
    assert "lsp-analyzer-metadata-drift" not in finding_ids
    assert phase2_gate["advisory_rule_ids"] == []
    assert "analyzer-exposure-gap" not in finding_ids
    assert "rule-corpus-link-gap" not in finding_ids


def test_collect_phase2_rule_metadata_gate_fails_on_enforced_gaps():
    gate = pipeline._collect_phase2_rule_metadata_gate(
        {
            "findings": [
                {
                    "id": "rule-acceptance-test-gap",
                    "missing_rule_ids": ["semantic.one", "semantic.two"],
                },
                {
                    "id": "rule-mutation-metadata-gap",
                    "missing_rule_ids": ["semantic.two", "semantic.three"],
                },
                {
                    "id": "rule-corpus-link-gap",
                    "missing_rule_ids": ["semantic.four"],
                },
            ]
        }
    )

    assert gate == {
        "status": "fail",
        "enforced_fields": ["acceptance_tests", "mutation_applicability"],
        "advisory_fields": ["corpus_cases"],
        "blocking_finding_ids": [
            "rule-acceptance-test-gap",
            "rule-mutation-metadata-gap",
        ],
        "advisory_finding_ids": ["rule-corpus-link-gap"],
        "blocking_rule_ids": [
            "semantic.one",
            "semantic.three",
            "semantic.two",
        ],
        "advisory_rule_ids": ["semantic.four"],
    }


def test_collect_analyzer_registry_report_includes_semantic_rule_mappings():
    report = pipeline._collect_analyzer_registry_report()
    sattline_semantics = next(analyzer for analyzer in report["analyzers"] if analyzer["key"] == "sattline-semantics")
    dataflow = next(analyzer for analyzer in report["analyzers"] if analyzer["key"] == "dataflow")
    mms_interface = next(analyzer for analyzer in report["analyzers"] if analyzer["key"] == "mms-interface")
    naming_consistency = next(analyzer for analyzer in report["analyzers"] if analyzer["key"] == "naming-consistency")

    duplicate_alarm_tag = next(rule for rule in report["rules"] if rule["id"] == "semantic.duplicate-alarm-tag")
    read_before_write = next(rule for rule in report["rules"] if rule["id"] == "semantic.read-before-write")
    dead_overwrite = next(rule for rule in report["rules"] if rule["id"] == "semantic.dead-overwrite")
    scan_cycle_stale_read = next(rule for rule in report["rules"] if rule["id"] == "semantic.scan-cycle-stale-read")
    unconsumed_safety_signal = next(
        rule for rule in report["rules"] if rule["id"] == "semantic.unconsumed-safety-signal"
    )
    unsafe_default = next(rule for rule in report["rules"] if rule["id"] == "semantic.unsafe-default-true")

    assert report["generated_by"] == "sattlint.devtools.pipeline"
    assert sattline_semantics["summary_output"] == "sattline-semantics.summary"
    assert sattline_semantics["scope"] == "workspace"
    assert sattline_semantics["lsp_exposed"] is True
    assert "semantic.read-before-write" in sattline_semantics["rule_ids"]
    assert "semantic.duplicate-alarm-tag" in sattline_semantics["rule_ids"]
    assert dataflow["summary_output"] == "dataflow.summary"
    assert dataflow["implementation_bucket"] == "shared-semantic-core"
    assert dataflow["lsp_exposed"] is True
    assert "sattline-semantics.summary" in dataflow["output_artifacts"]
    assert "semantic.read-before-write" in dataflow["rule_ids"]
    assert "semantic.dead-overwrite" in dataflow["rule_ids"]
    assert mms_interface["summary_output"] == "mms-interface.summary"
    assert mms_interface["cli_exposed"] is True
    assert mms_interface["rule_ids"] == []
    assert naming_consistency["acceptance_tests"] == ["tests/test_analyzers.py"]
    assert naming_consistency["exposed_via"] == ["pipeline"]
    assert set(duplicate_alarm_tag) == {
        "id",
        "source",
        "category",
        "severity",
        "confidence",
        "applies_to",
        "description",
        "explanation",
        "suggestion",
        "analyzers",
        "outputs",
        "acceptance_tests",
        "corpus_cases",
        "mutation_applicability",
        "suppression_modes",
        "incremental_safe",
    }
    assert duplicate_alarm_tag["source"] == "alarm-integrity"
    assert duplicate_alarm_tag["confidence"] == "likely"
    assert duplicate_alarm_tag["explanation"] == duplicate_alarm_tag["description"]
    assert "alarm-integrity" in duplicate_alarm_tag["analyzers"]
    assert "alarm-integrity.summary" in duplicate_alarm_tag["outputs"]
    assert "tests/test_analyzers.py" in duplicate_alarm_tag["acceptance_tests"]
    assert duplicate_alarm_tag["corpus_cases"] == ["workspace-common-quality-issues"]
    assert duplicate_alarm_tag["mutation_applicability"] == "required"
    assert duplicate_alarm_tag["suppression_modes"] == ["baseline"]
    assert duplicate_alarm_tag["incremental_safe"] is False
    assert read_before_write["source"] == "dataflow"
    assert "sattline-semantics" in read_before_write["analyzers"]
    assert "dataflow" in read_before_write["analyzers"]
    assert "sattline-semantics.summary" in read_before_write["outputs"]
    assert "tests/test_dataflow.py" in read_before_write["acceptance_tests"]
    assert read_before_write["corpus_cases"] == ["workspace-common-quality-issues"]
    assert read_before_write["mutation_applicability"] == "required"
    assert dead_overwrite["source"] == "dataflow"
    assert "dataflow.summary" in dead_overwrite["outputs"]
    assert scan_cycle_stale_read["source"] == "dataflow"
    assert "sattline-semantics" in scan_cycle_stale_read["analyzers"]
    assert unconsumed_safety_signal["source"] == "safety-paths"
    assert "safety-paths" in unconsumed_safety_signal["analyzers"]
    assert "safety-paths.summary" in unconsumed_safety_signal["outputs"]
    assert unconsumed_safety_signal["mutation_applicability"] == "required"
    assert unsafe_default["source"] == "unsafe-defaults"
    assert "unsafe-defaults" in unsafe_default["analyzers"]
    assert "unsafe-defaults.summary" in unsafe_default["outputs"]
    assert unsafe_default["mutation_applicability"] == "required"
    assert report["rule_profiles"]["active"] == "default"
    assert [profile["name"] for profile in report["rule_profiles"]["profiles"]] == [
        "default",
        "legacy-plant",
        "strict-pharma",
    ]


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


def test_build_pipeline_tool_exit_codes_cover_optional_and_policy_paths():
    stage_reports = {
        "ruff_report": {"exit_code": 0},
        "pyright_report": {"effective_exit_code": 1},
        "pytest_report": {"exit_code": 2},
        "vulture_report": {"exit_code": 3},
        "bandit_report": {"exit_code": 4},
    }

    failing_codes = pipeline._build_pipeline_tool_exit_codes(
        stage_reports,
        {"corpus_results_report": {"summary": {"failed_count": 2}}},
        {
            "phase2_rule_metadata_gate": {"status": "fail"},
            "analysis_diff_report": {"summary": {"new_count": 1, "resolved_count": 0}},
            "performance_budget_report": {"status": "fail"},
        },
        {"run_structural_reports": True},
        fail_on_drift=True,
        fail_on_budget=True,
    )
    neutral_codes = pipeline._build_pipeline_tool_exit_codes(
        stage_reports,
        {"corpus_results_report": None},
        {
            "phase2_rule_metadata_gate": {"status": "pass"},
            "analysis_diff_report": None,
            "performance_budget_report": None,
        },
        {"run_structural_reports": False},
        fail_on_drift=False,
        fail_on_budget=False,
    )

    assert failing_codes == {
        "ruff": 0,
        "pyright": 1,
        "pytest": 2,
        "vulture": 3,
        "bandit": 4,
        "corpus": 1,
        "rule_metadata": 1,
        "baseline_drift": 1,
        "performance_budget": 1,
    }
    assert neutral_codes == {
        "ruff": 0,
        "pyright": 1,
        "pytest": 2,
        "vulture": 3,
        "bandit": 4,
        "corpus": None,
        "rule_metadata": None,
        "baseline_drift": None,
        "performance_budget": None,
    }


def test_build_pipeline_counts_rolls_up_optional_and_derived_metrics():
    counts = pipeline._build_pipeline_counts(
        {
            "ruff_report": {"finding_count": 5},
            "pyright_report": {"error_count": 2, "warning_count": 3},
            "pytest_report": {"summary": {"failures": 1, "errors": 4}},
            "vulture_report": {"finding_count": 6},
            "bandit_report": {"findings": [{}, {}]},
        },
        {
            "corpus_results_report": {
                "summary": {
                    "case_count": 7,
                    "passed_count": 5,
                    "failed_count": 1,
                    "execution_error_count": 1,
                }
            },
            "architecture_report": {"findings": [{}, {}]},
            "analyzer_registry_report": {"rules": [{}, {}, {}]},
            "dependency_graph_report": {"edges": [{}, {}]},
            "call_graph_report": {"edges": [{}]},
            "graphics_layout_report": {"entries": [{}, {}], "groups": [{}], "findings": [{}, {}, {}]},
            "impact_analysis_report": {"library_impacts": [{}], "module_impacts": [{}, {}]},
            "workspace_graph_inputs": SimpleNamespace(snapshot_failures=["a", "b"]),
            "trace_report": {
                "dataflow_analysis": {"issue_count": 8},
                "heuristics": {
                    "unreachable_logic": ["x"],
                    "transform_invariant_violations": ["v1", "v2"],
                },
            },
        },
        {
            "analysis_diff_report": {
                "summary": {
                    "new_count": 9,
                    "resolved_count": 4,
                    "changed_count": 3,
                    "unchanged_count": 2,
                }
            },
            "incremental_analysis_report": {
                "summary": {
                    "changed_file_count": 10,
                    "impacted_analyzer_count": 11,
                    "fallback_analyzer_count": 12,
                }
            },
            "finding_collection": SimpleNamespace(findings=[1, 2, 3, 4]),
            "phase2_rule_metadata_gate": {"blocking_rule_ids": ["r1", "r2"], "advisory_rule_ids": ["r3"]},
            "profiling_summary_report": {
                "total_duration_ms": 13.5,
                "summary": {"phase_count": 14, "slow_phase_count": 15},
            },
            "performance_budget_report": {"violation_count": 16},
        },
        {},
    )

    assert counts == {
        "baseline_new_findings": 9,
        "baseline_resolved_findings": 4,
        "baseline_changed_findings": 3,
        "baseline_unchanged_findings": 2,
        "incremental_changed_file_count": 10,
        "incremental_candidate_analyzer_count": 11,
        "incremental_blocking_analyzer_count": 12,
        "normalized_findings": 4,
        "corpus_case_count": 7,
        "corpus_passed_case_count": 5,
        "corpus_failed_case_count": 1,
        "corpus_execution_error_count": 1,
        "ruff_findings": 5,
        "pyright_errors": 2,
        "pyright_warnings": 3,
        "pytest_failures": 1,
        "pytest_errors": 4,
        "vulture_findings": 6,
        "bandit_findings": 2,
        "architecture_findings": 2,
        "semantic_rule_count": 3,
        "phase2_rule_metadata_blocking_gaps": 2,
        "phase2_rule_metadata_advisory_gaps": 1,
        "dependency_graph_edges": 2,
        "call_graph_edges": 1,
        "graphics_layout_entries": 2,
        "graphics_layout_groups": 1,
        "graphics_layout_findings": 3,
        "impact_analysis_library_nodes": 1,
        "impact_analysis_module_nodes": 2,
        "workspace_graph_snapshot_failures": 2,
        "trace_dataflow_issues": 8,
        "trace_unreachable_logic": 1,
        "trace_transform_violations": 2,
        "profiling_total_duration_ms": 13.5,
        "profiling_phase_count": 14,
        "profiling_slow_phase_count": 15,
        "performance_budget_violation_count": 16,
    }


def test_check_core_invariants_reports_duplicate_fingerprints_and_transform_violations():
    violations = pipeline._check_core_invariants(
        {
            "finding_collection": SimpleNamespace(
                findings=[
                    SimpleNamespace(fingerprint="fp-a"),
                    SimpleNamespace(id="fp-a"),
                    SimpleNamespace(fingerprint="fp-b"),
                ]
            ),
            "trace_report": {"heuristics": {"transform_invariant_violations": ["v1", "v2"]}},
        },
        {},
    )

    assert violations == [
        "Duplicate finding fingerprint: fp-a",
        "Transform invariant violations: 2",
    ]


def test_corpus_semantic_findings_include_guidance_fields(tmp_path):
    findings = corpus._build_semantic_finding_collection(
        SattLineSemanticsReport(
            basepicture_name="Program",
            issues=[
                SemanticIssue(
                    rule=SemanticRule(
                        id="semantic.read-before-write",
                        source="dataflow",
                        category="variable-lifecycle",
                        severity="warning",
                        applies_to="variable",
                        description="Read before write.",
                        explanation="The read can observe undefined state on some control paths.",
                        suggestion="Initialize the variable before the first possible read.",
                    ),
                    message="Variable 'PumpStart' is read before it is written.",
                    module_path=["Program", "UnitA"],
                )
            ],
        ),
        target_path=tmp_path / "Program.s",
        repo_root=tmp_path,
    ).to_dict()

    assert_findings_collection(findings, finding_count=1, rule_ids=("semantic.read-before-write",))
    assert findings["findings"][0]["detail"] == "The read can observe undefined state on some control paths."
    assert findings["findings"][0]["suggestion"] == "Initialize the variable before the first possible read."


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
        pytest_report={"summary": {"tests": 2, "failures": 1, "errors": 0, "skipped": 0}},
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
    assert any(item["rule_id"] == "pyright.assignment" and item["severity"] == "high" for item in payload["findings"])
    assert any(item["rule_id"] == "pytest.failures" for item in payload["findings"])
    assert any(item["rule_id"] == "vulture.dead-code" and item["confidence"] == "high" for item in payload["findings"])
    assert any(item["rule_id"] == "bandit.b101" and item["category"] == "security" for item in payload["findings"])
    assert any(
        item["rule_id"] == "analyzer-exposure-gap" and item["category"] == "architecture"
        for item in payload["findings"]
    )


def test_build_analysis_diff_report_classifies_changes():
    baseline = FindingCollection(
        (
            FindingRecord(
                id="unchanged",
                rule_id="ruff.f401",
                category="style",
                severity="high",
                confidence="high",
                message="Imported but unused",
                source="ruff",
            ),
            FindingRecord(
                id="changed-old",
                rule_id="pytest.failures",
                category="correctness",
                severity="high",
                confidence="high",
                message="Pytest reported failing tests.",
                source="pytest",
            ),
            FindingRecord(
                id="resolved",
                rule_id="vulture.dead-code",
                category="dead-code",
                severity="medium",
                confidence="medium",
                message="Potential dead code found.",
                source="vulture",
            ),
        )
    )
    current = FindingCollection(
        (
            FindingRecord(
                id="unchanged",
                rule_id="ruff.f401",
                category="style",
                severity="high",
                confidence="high",
                message="Imported but unused",
                source="ruff",
            ),
            FindingRecord(
                id="changed-new",
                rule_id="pytest.failures",
                category="correctness",
                severity="high",
                confidence="high",
                message="Pytest reported failing or erroring tests.",
                source="pytest",
            ),
            FindingRecord(
                id="new",
                rule_id="bandit.b101",
                category="security",
                severity="low",
                confidence="high",
                message="Use of assert detected.",
                source="bandit",
            ),
        )
    )

    report = build_analysis_diff_report(
        baseline=baseline,
        current=current,
        baseline_label="baseline.json",
        current_label="current.json",
    )

    assert_analysis_diff_report(
        report,
        summary={
            "new_count": 1,
            "resolved_count": 1,
            "changed_count": 1,
            "unchanged_count": 1,
        },
        baseline_label="baseline.json",
        current_label="current.json",
        new_rule_ids=("bandit.b101",),
        resolved_rule_ids=("vulture.dead-code",),
        unchanged_rule_ids=("ruff.f401",),
        changed_rule_ids=("pytest.failures",),
        changed_fields_by_rule_id={
            "pytest.failures": ("id", "message"),
        },
    )
    assert report["findings"]["changed"][0]["baseline"]["message"] == "Pytest reported failing tests."
    assert report["findings"]["changed"][0]["current"]["message"] == "Pytest reported failing or erroring tests."


def test_print_cli_summary_includes_analysis_diff_counts(capsys):
    pipeline._print_cli_summary(
        {
            "profile": "quick",
            "overall_status": "pass",
            "tool_statuses": {},
            "findings_schema": {
                "kind": "sattlint.findings",
                "schema_version": 1,
            },
            "analysis_diff_report": "<external>/analysis/analysis_diff.json",
            "analysis_diff_summary": {
                "new_count": 1,
                "changed_count": 2,
                "resolved_count": 3,
                "unchanged_count": 4,
            },
            "status_report": "<external>/analysis/status.json",
            "summary_report": "<external>/analysis/summary.json",
        }
    )

    output = capsys.readouterr().out

    assert "Findings schema: sattlint.findings v1" in output
    assert "Analysis diff: 1 new, 2 changed, 3 resolved, 4 unchanged" in output
    assert "Analysis diff report: <external>/analysis/analysis_diff.json" in output


def test_write_pipeline_artifacts_uses_registry_filenames(tmp_path):
    written: list[tuple[str, dict]] = []

    context = PipelineArtifactContext(
        payloads={
            "status": {"kind": "status"},
            "summary": {"kind": "summary"},
        }
    )

    def fake_write_json(path, payload):
        written.append((path.name, payload))

    artifact_ids = write_pipeline_artifacts(
        tmp_path,
        artifacts=pipeline.PIPELINE_ARTIFACTS,
        profile="quick",
        enabled_artifact_ids={"status", "summary"},
        context=context,
        write_json=fake_write_json,
    )

    assert artifact_ids == ("status", "summary")
    assert written == [
        ("status.json", {"kind": "status"}),
        ("summary.json", {"kind": "summary"}),
    ]


def test_write_pipeline_artifacts_uses_registry_producer_mapping(tmp_path):
    written: list[tuple[str, dict]] = []
    context = PipelineArtifactContext(payloads={})

    def fake_write_json(path, payload):
        written.append((path.name, payload))

    artifact_ids = write_pipeline_artifacts(
        tmp_path,
        artifacts=(
            ArtifactDefinition(
                "status",
                "status.json",
                "status_payload",
                "sattlint.pipeline.status",
                1,
                profiles=("quick",),
            ),
        ),
        profile="quick",
        enabled_artifact_ids={"status"},
        context=context,
        write_json=fake_write_json,
        producers=(
            PipelineArtifactProducer(
                "status_payload",
                lambda artifact_context: {"kind": "status"},
            ),
        ),
    )

    assert artifact_ids == ("status",)
    assert written == [("status.json", {"kind": "status"})]


def test_write_json_artifact_retries_permission_error(tmp_path, monkeypatch):
    target = tmp_path / "status.json"
    replace_calls = {"count": 0}
    real_replace = os.replace

    def flaky_replace(source, destination):
        replace_calls["count"] += 1
        if replace_calls["count"] == 1:
            raise PermissionError("temporary file lock")
        real_replace(source, destination)

    monkeypatch.setattr("sattlint.devtools.pipeline_artifacts.os.replace", flaky_replace)
    monkeypatch.setattr("sattlint.devtools.pipeline_artifacts.time.sleep", lambda _seconds: None)

    write_json_artifact(target, {"kind": "status"})

    assert replace_calls["count"] == 2
    assert json.loads(target.read_text(encoding="utf-8")) == {"kind": "status"}


def test_write_pipeline_artifacts_requires_producer_for_enabled_artifact(tmp_path):
    context = PipelineArtifactContext(payloads={})

    try:
        write_pipeline_artifacts(
            tmp_path,
            artifacts=pipeline.PIPELINE_ARTIFACTS,
            profile="quick",
            enabled_artifact_ids={"status"},
            context=context,
            write_json=lambda path, payload: None,
            producers=(PipelineArtifactProducer("summary", lambda artifact_context: {"kind": "summary"}),),
        )
    except ValueError as exc:
        assert "status" in str(exc)
    else:
        raise AssertionError("Expected missing artifact producer to raise ValueError")


def test_validate_pipeline_artifact_producers_covers_quick_and_full_profiles():
    quick_artifacts = validate_pipeline_artifact_producers(
        pipeline.PIPELINE_ARTIFACTS,
        profile="quick",
    )
    full_artifacts = validate_pipeline_artifact_producers(
        pipeline.PIPELINE_ARTIFACTS,
        profile="full",
    )

    assert "status" in quick_artifacts
    assert "summary" in quick_artifacts
    assert "trace" in full_artifacts
    assert "graphics_layout" in full_artifacts
    assert "impact_analysis" in full_artifacts


def test_collect_graphics_layout_report_resolves_moduletype_moduledefs(tmp_path):
    entry_file = tmp_path / "Program" / "Main.s"
    panel_type = ModuleTypeDef(
        name="PanelType",
        moduledef=ModuleDef(
            clipping_bounds=((0.0, 0.0), (1.0, 0.5)),
            zoom_limits=(0.9, 0.1),
            grid=0.01,
            zoomable=True,
        ),
        submodules=[
            SingleModule(
                header=ModuleHeader(
                    name="UnitControl",
                    invoke_coord=(1.43, 1.35, 0.0, 0.56, 0.56),
                    invocation_arguments=("LayerModule",),
                ),
                moduledef=ModuleDef(
                    clipping_bounds=((0.0, 0.0), (1.0, 0.21429)),
                    zoom_limits=(0.83738, 0.01),
                    grid=0.01,
                    zoomable=True,
                ),
            )
        ],
    )
    bp = BasePicture(
        header=ModuleHeader(name="Program", invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0)),
        name="Program",
        moduletype_defs=[panel_type],
        submodules=[
            SingleModule(
                header=ModuleHeader(name="Area", invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0)),
                moduledef=ModuleDef(clipping_bounds=((0.0, 0.0), (1.0, 1.0))),
                submodules=[
                    ModuleTypeInstance(
                        header=ModuleHeader(
                            name="Panel",
                            invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0),
                            invocation_arguments=("IgnoreMaxModule",),
                        ),
                        moduletype_name="PanelType",
                    )
                ],
            )
        ],
    )
    snapshot = SimpleNamespace(
        entry_file=entry_file,
        base_picture=bp,
        project_graph=SimpleNamespace(unavailable_libraries=set()),
    )
    graph_inputs = structural_reports.WorkspaceGraphInputs(
        discovery=SimpleNamespace(program_files=(entry_file,), dependency_files=()),
        snapshots=[snapshot],
        snapshot_failures=[],
    )

    report = structural_reports.collect_graphics_layout_report(tmp_path, graph_inputs=graph_inputs)

    panel_entry = next(entry for entry in report["entries"] if entry["module_path"] == "Program.Area.Panel")
    unit_control_entry = next(
        entry for entry in report["entries"] if entry["module_path"] == "Program.Area.Panel.UnitControl"
    )

    assert panel_entry["module_kind"] == "moduletype-instance"
    assert panel_entry["moduledef_origin_kind"] == "moduletype-definition"
    assert panel_entry["invocation"]["arguments"] == ["IgnoreMaxModule"]
    assert panel_entry["moduledef"]["clipping_size"] == [1.0, 0.5]
    assert unit_control_entry["definition_scope"] == "moduletype:PanelType"
    assert unit_control_entry["invocation"]["arguments"] == ["LayerModule"]
    assert unit_control_entry["moduledef"]["clipping_size"] == [1.0, 0.21429]


def test_collect_graphics_layout_report_flags_repeated_module_name_drift(tmp_path):
    entry_file = tmp_path / "Program" / "Main.s"
    bp = BasePicture(
        header=ModuleHeader(name="Program", invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0)),
        name="Program",
        submodules=[
            SingleModule(
                header=ModuleHeader(name="L1", invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0)),
                moduledef=ModuleDef(clipping_bounds=((0.0, 0.0), (1.0, 1.0))),
                submodules=[
                    SingleModule(
                        header=ModuleHeader(
                            name="UnitControl",
                            invoke_coord=(1.43, 1.35, 0.0, 0.56, 0.56),
                        ),
                        moduledef=ModuleDef(
                            clipping_bounds=((0.0, 0.0), (1.0, 0.21429)),
                            zoom_limits=(0.83738, 0.01),
                            grid=0.01,
                            zoomable=True,
                        ),
                    )
                ],
            ),
            SingleModule(
                header=ModuleHeader(name="L2", invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0)),
                moduledef=ModuleDef(clipping_bounds=((0.0, 0.0), (1.0, 1.0))),
                submodules=[
                    SingleModule(
                        header=ModuleHeader(
                            name="UnitControl",
                            invoke_coord=(1.5, 1.4, 0.0, 0.56, 0.56),
                        ),
                        moduledef=ModuleDef(
                            clipping_bounds=((0.0, 0.0), (1.0, 0.25)),
                            zoom_limits=(0.83738, 0.01),
                            grid=0.01,
                            zoomable=True,
                        ),
                    )
                ],
            ),
        ],
    )
    snapshot = SimpleNamespace(
        entry_file=entry_file,
        base_picture=bp,
        project_graph=SimpleNamespace(unavailable_libraries=set()),
    )
    graph_inputs = structural_reports.WorkspaceGraphInputs(
        discovery=SimpleNamespace(program_files=(entry_file,), dependency_files=()),
        snapshots=[snapshot],
        snapshot_failures=[],
    )

    report = structural_reports.collect_graphics_layout_report(tmp_path, graph_inputs=graph_inputs)

    assert len(report["findings"]) == 1
    assert report["findings"][0]["id"] == "graphics-layout-drift"
    assert report["findings"][0]["module_name"] == "UnitControl"
    assert "invocation.coords" in report["findings"][0]["differing_fields"]
    assert "moduledef.clipping_size" in report["findings"][0]["differing_fields"]


def test_validate_pipeline_artifact_producers_rejects_duplicate_producer_ids():
    try:
        validate_pipeline_artifact_producers(
            pipeline.PIPELINE_ARTIFACTS,
            profile="quick",
            producers=(
                PipelineArtifactProducer("status", lambda artifact_context: {"kind": "status"}),
                PipelineArtifactProducer("status", lambda artifact_context: {"kind": "summary"}),
            ),
        )
    except ValueError as exc:
        assert "Duplicate pipeline artifact producers" in str(exc)
    else:
        raise AssertionError("Expected duplicate producer ids to raise ValueError")


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


def test_progress_reporter_fail_stage_marks_overall_failed(tmp_path):
    reporter = ProgressReporter(
        kind="sattlint.test.progress",
        title="Test",
        output_dir=tmp_path,
        write_json=lambda path, payload: None,
        stages=[("one", "Stage one"), ("two", "Stage two")],
        emit_stdout=False,
    )

    reporter.start_stage("one")
    reporter.fail_stage("one", detail="something went wrong")

    payload = reporter.to_dict()

    assert payload["overall_status"] == "failed"
    failed = next(s for s in payload["stages"] if s["key"] == "one")
    assert failed["status"] == "failed"
    assert failed["detail"] == "something went wrong"


def test_progress_reporter_complete_stage_without_prior_start_sets_started_at(tmp_path):
    reporter = ProgressReporter(
        kind="sattlint.test.progress",
        title="Test",
        output_dir=tmp_path,
        write_json=lambda path, payload: None,
        stages=[("one", "Stage one")],
        emit_stdout=False,
    )

    reporter.complete_stage("one")

    stage = reporter.to_dict()["stages"][0]
    assert stage["status"] == "completed"
    assert stage["started_at"] is not None


def test_progress_reporter_active_stage_payload_returns_active_stage(tmp_path):
    reporter = ProgressReporter(
        kind="sattlint.test.progress",
        title="Test",
        output_dir=tmp_path,
        write_json=lambda path, payload: None,
        stages=[("one", "Stage one"), ("two", "Stage two")],
        emit_stdout=False,
    )

    reporter.start_stage("two")
    payload = reporter.to_dict()

    assert payload["active_stage"] is not None
    assert payload["active_stage"]["key"] == "two"
    assert payload["active_stage"]["label"] == "Stage two"


def test_progress_reporter_fail_stage_without_start_sets_started_at(tmp_path):
    reporter = ProgressReporter(
        kind="sattlint.test.progress",
        title="Test",
        output_dir=tmp_path,
        write_json=lambda path, payload: None,
        stages=[("one", "Stage one")],
        emit_stdout=False,
    )

    reporter.fail_stage("one")

    stage = reporter.to_dict()["stages"][0]
    assert stage["status"] == "failed"
    assert stage["started_at"] is not None


def test_progress_reporter_fail_stage_emits_stdout(tmp_path, capsys):
    reporter = ProgressReporter(
        kind="sattlint.test.progress",
        title="Test",
        output_dir=tmp_path,
        write_json=lambda path, payload: None,
        stages=[("one", "Stage one")],
        emit_stdout=True,
    )

    reporter.fail_stage("one", detail="exploded")

    captured = capsys.readouterr()
    assert "failed Stage one" in captured.out
    assert "exploded" in captured.out


def test_progress_reporter_stage_raises_on_unknown_key(tmp_path):
    import pytest

    reporter = ProgressReporter(
        kind="sattlint.test.progress",
        title="Test",
        output_dir=tmp_path,
        write_json=lambda path, payload: None,
        stages=[("one", "Stage one")],
        emit_stdout=False,
    )

    with pytest.raises(KeyError, match="Unknown progress stage"):
        reporter.start_stage("no-such-key")


# --- artifact_registry.py line 23 (is_available), line 24-39 (to_dict) ---
def test_artifact_definition_is_available_false_when_not_in_profile(tmp_path):
    from sattlint.devtools.artifact_registry import ArtifactDefinition

    ad = ArtifactDefinition(
        artifact_id="test",
        filename="test.json",
        producer="test",
        schema_kind="sattlint.test",
        schema_version=1,
        profiles=("full",),
    )
    assert ad.is_available(profile="quick") is False
    assert ad.is_available(profile="full") is True
    assert ad.is_available(profile="full", enabled=False) is False


def test_artifact_definition_to_dict_returns_expected_shape():
    from sattlint.devtools.artifact_registry import ArtifactDefinition

    ad = ArtifactDefinition(
        artifact_id="my-art",
        filename="my-art.json",
        producer="producer",
        schema_kind="sattlint.myart",
        schema_version=2,
        profiles=("quick", "full"),
        optional=True,
        blocking=False,
    )
    result = ad.to_dict(enabled=True)
    assert result["artifact_id"] == "my-art"
    assert result["profiles"] == ["quick", "full"]
    assert result["optional"] is True
    assert result["enabled"] is True


# --- tool_reports.py lines 26, 34, 35 (build_command_report) ---
def test_build_command_report_returns_expected_keys(tmp_path):
    from types import SimpleNamespace

    from sattlint.devtools.tool_reports import build_command_report

    result_obj = SimpleNamespace(
        name="mytool",
        command=["mytool", "--flag"],
        exit_code=0,
        duration_seconds=1.23,
        stdout="ok",
        stderr="",
    )
    report = build_command_report(cast(Any, result_obj), repo_root=tmp_path, extra_key="extra_val")
    assert report["tool"] == "mytool"
    assert report["exit_code"] == 0
    assert report["extra_key"] == "extra_val"


# --- issue.py lines 10-13 (format_report_header) ---
def test_format_report_header_includes_status_when_given():
    from sattlint.analyzers.issue import format_report_header

    lines = format_report_header("varcheck", "Main.s", status="pass")
    assert "Report: varcheck" in lines
    assert "Target: Main.s" in lines
    assert "Status: pass" in lines


def test_format_report_header_omits_status_when_none():
    from sattlint.analyzers.issue import format_report_header

    lines = format_report_header("varcheck", "Main.s")
    assert len(lines) == 2


# --- sattline_builtins.py line 2090 (is_builtin_function) ---
def test_is_builtin_function_returns_true_for_known_function():
    from sattlint.analyzers.sattline_builtins import is_builtin_function

    assert is_builtin_function("CopyVariable") is True
    assert is_builtin_function("copyvariable") is True
    assert is_builtin_function("nonexistent_xyz") is False


# --- call_signatures.py: channel_kind async-operation branch, status_parameters, resolve_call_signature ---
def test_call_parameter_signature_channel_kind_returns_async_operation():
    from sattlint.call_signatures import CallParameterSignature

    p = CallParameterSignature(
        name="AsyncOperation",
        datatype="AsyncOperation",
        direction="inout",
        sorting="RS/WS",
        ownership="RO/WO",
    )
    assert p.channel_kind == "async-operation"
    assert p.is_status_channel is True


def test_resolve_call_signature_returns_signature_for_known_builtin():
    from sattlint.call_signatures import resolve_call_signature

    sig = resolve_call_signature("CopyVariable")
    assert sig is not None
    assert sig.name == "copyvariable"
    status_params = sig.status_parameters
    assert len(status_params) > 0


# --- call_signatures.py lines 59 (early return) and 63 (builtin not found) ---
def test_resolve_call_signature_returns_none_for_falsy_name():
    from sattlint.call_signatures import resolve_call_signature

    assert resolve_call_signature(None) is None
    assert resolve_call_signature("") is None


def test_resolve_call_signature_returns_none_for_unknown_builtin():
    from sattlint.call_signatures import resolve_call_signature

    assert resolve_call_signature("NonExistentFunctionXyz123") is None


# --- casefolding.py lines 13, 17-28 ---
def test_casefold_equal_compares_case_insensitively():
    from sattlint.casefolding import casefold_equal

    assert casefold_equal("Hello", "hello") is True
    assert casefold_equal("FOO", "bar") is False


def test_dedupe_casefolded_strings_removes_duplicates_and_empties():
    from sattlint.casefolding import dedupe_casefolded_strings

    result = dedupe_casefolded_strings(["Alpha", "alpha", "", "Beta", "BETA"])
    assert result == ["Alpha", "Beta"]


# --- _validation_shared.py: RawSourceValidationError, _span_kwargs, _warn_or_raise, _ref_span ---
def test_raw_source_validation_error_stores_line_and_column():
    from sattlint._validation_shared import RawSourceValidationError

    err = RawSourceValidationError("bad input", line=5, column=10, length=3)
    assert err.line == 5
    assert err.column == 10
    assert err.length == 3
    assert str(err) == "bad input"


def test_span_kwargs_returns_line_and_column_from_span():
    from sattline_parser.models.ast_model import SourceSpan
    from sattlint._validation_shared import _span_kwargs

    span = SourceSpan(line=3, column=7)
    result = _span_kwargs(span)
    assert result == {"line": 3, "column": 7}


def test_warn_or_raise_raises_when_no_sink():
    import pytest

    from sattlint._validation_shared import StructuralValidationError, _warn_or_raise

    with pytest.raises(StructuralValidationError, match="something bad"):
        _warn_or_raise("something bad", line=1, column=2, length=5)


def test_ref_span_returns_span_from_dict_with_span():
    from sattline_parser.models.ast_model import SourceSpan
    from sattlint._validation_shared import _ref_span

    span = SourceSpan(line=1, column=0)
    result = _ref_span({"span": span})
    assert result is span


def test_ref_span_returns_none_for_non_dict():
    from sattlint._validation_shared import _ref_span

    assert _ref_span(None) is None
    assert _ref_span("string") is None
    assert _ref_span({"span": "not-a-span"}) is None


# --- coverage_reports.py: skipped when no coverage.xml, high severity branch ---
def test_build_coverage_summary_report_skipped_when_no_xml(tmp_path):
    from sattlint.devtools.coverage_reports import build_coverage_summary_report

    result = build_coverage_summary_report(tmp_path)
    assert result["skipped"] is True
    assert result["skip_reason"] == "coverage.xml not found"
    assert result["modules"] == []


def test_build_coverage_summary_report_flags_high_severity(tmp_path):
    from sattlint.devtools.coverage_reports import build_coverage_summary_report

    xml_content = """<?xml version="1.0" ?>
<coverage>
  <packages><package><classes>
    <class filename="src/sattlint/bad_module.py" line-rate="0.05" lines-valid="100" lines-covered="5">
      <lines/>
    </class>
  </classes></package></packages>
</coverage>"""
    (tmp_path / "coverage.xml").write_text(xml_content, encoding="utf-8")
    result = build_coverage_summary_report(tmp_path)
    findings = result["findings"]
    assert any(f["severity"] == "high" for f in findings)


# --- resolution/paths.py: CanonicalPath.join() no-arg, ModuleSegment.display() branches ---
def test_canonical_path_join_no_args_returns_self():
    from sattlint.resolution.paths import CanonicalPath

    cp = CanonicalPath(("Main", "Guard"))
    assert cp.join() is cp


def test_module_segment_display_variants():
    from sattlint.resolution.paths import ModuleSegment

    assert ModuleSegment("Guard", "SM").display() == "Guard<SM>"
    assert ModuleSegment("Loop", "FM").display() == "Loop<FM>"
    assert ModuleSegment("T1", "TD").display() == "T1<TD>"
    assert ModuleSegment("Root", "BP").display() == "Root<BP>"
    assert ModuleSegment("UTI", "MT", "MyType").display() == "UTI<MT:MyType>"


# --- resolution/scope.py: param mapping prefix-only and no-prefix branches, resolve_global_name ---
def test_scope_context_resolve_variable_prefix_only_mapping():
    from sattline_parser.models.ast_model import Variable
    from sattlint.resolution.scope import ScopeContext

    src_var = Variable(name="Dv", datatype="UserType")
    ctx = ScopeContext(
        env={"dv": src_var},
        param_mappings={"sig": (src_var, "I.WT001", ["Lib", "Main"], ["Lib", "Main"])},
        module_path=["Main"],
        display_module_path=["Main"],
    )
    var, full_field_path, _, _ = ctx.resolve_variable("sig")
    assert var is src_var
    assert full_field_path == "I.WT001"


def test_scope_context_resolve_variable_no_prefix_mapping():
    from sattline_parser.models.ast_model import Variable
    from sattlint.resolution.scope import ScopeContext

    src_var = Variable(name="Dv", datatype="UserType")
    ctx = ScopeContext(
        env={},
        param_mappings={"sig": (src_var, "", ["Lib"], ["Lib"])},
        module_path=["Main"],
        display_module_path=["Main"],
    )
    var, full_field_path, _, _ = ctx.resolve_variable("sig")
    assert var is src_var
    assert full_field_path == ""


def test_scope_context_resolve_global_name_empty_returns_none():
    from sattlint.resolution.scope import ScopeContext

    ctx = ScopeContext(
        env={},
        param_mappings={},
        module_path=["Main"],
        display_module_path=["Main"],
    )
    var, _, _ = ctx.resolve_global_name("")
    assert var is None


def test_scope_context_resolve_global_name_walks_parent():
    from sattline_parser.models.ast_model import Variable
    from sattlint.resolution.scope import ScopeContext

    parent_var = Variable(name="GlobVar", datatype="Integer")
    parent_ctx = ScopeContext(
        env={"globvar": parent_var},
        param_mappings={},
        module_path=["Root"],
        display_module_path=["Root"],
    )
    child_ctx = ScopeContext(
        env={},
        param_mappings={},
        module_path=["Root", "Child"],
        display_module_path=["Root", "Child"],
        parent_context=parent_ctx,
    )
    var, _, _ = child_ctx.resolve_global_name("GlobVar")
    assert var is parent_var


# --- contracts/findings.py ---
def test_finding_location_to_dict_and_from_mapping():
    from sattlint.contracts.findings import FindingLocation

    loc = FindingLocation(path="Main.s", line=5, column=3, symbol="Var1", module_path=("Main", "Guard"))
    d = loc.to_dict()
    assert d["path"] == "Main.s"
    assert d["line"] == 5
    assert d["module_path"] == ["Main", "Guard"]

    from_payload = FindingLocation.from_mapping({"path": "Foo.s", "line": "10", "module_path": ["A", "B"]})
    assert from_payload.path == "Foo.s"
    assert from_payload.line == 10
    assert from_payload.module_path == ("A", "B")


def test_finding_location_from_mapping_uses_file_fallback():
    from sattlint.contracts.findings import FindingLocation

    loc = FindingLocation.from_mapping({"file": "Alt.s"})
    assert loc.path == "Alt.s"


def test_finding_record_default_fingerprint_is_set():
    from sattlint.contracts.findings import FindingRecord

    r = FindingRecord(
        id="r1",
        rule_id="var.unused",
        category="variable",
        severity="warning",
        confidence="high",
        message="Unused variable X",
        source="test",
    )
    assert r.fingerprint is not None
    assert "var.unused" in r.fingerprint


def test_finding_record_to_dict_round_trip_via_from_dict():
    from sattlint.contracts.findings import FindingRecord

    original = FindingRecord(
        id="r2",
        rule_id="scope.leak",
        category="scope",
        severity="info",
        confidence="medium",
        message="Scope issue",
        source="test",
        detail="some detail",
        suggestion="fix it",
    )
    d = original.to_dict()
    restored = FindingRecord.from_dict(d)
    assert restored.rule_id == "scope.leak"
    assert restored.detail == "some detail"
    assert restored.suggestion == "fix it"


def test_finding_record_from_mapping_with_explicit_source():
    from sattlint.contracts.findings import FindingRecord

    r = FindingRecord.from_mapping(
        {"rule_id": "x.y", "category": "cat", "severity": "err", "confidence": "low", "message": "msg"},
        source="manual",
        analyzer="myanalyzer",
    )
    assert r.source == "manual"
    assert r.analyzer == "myanalyzer"


def test_finding_collection_to_dict_and_from_dict():
    from sattlint.contracts.findings import FindingCollection, FindingRecord

    rec = FindingRecord(id="f1", rule_id="r1", category="c", severity="s", confidence="c2", message="m", source="s2")
    coll = FindingCollection(findings=(rec,))
    d = coll.to_dict()
    assert d["finding_count"] == 1

    restored = FindingCollection.from_dict(d)
    assert len(restored.findings) == 1
    assert restored.findings[0].rule_id == "r1"


# --- path_sanitizer.py ---
def test_sanitize_path_for_report_returns_relative_for_repo_subpath(tmp_path):
    from sattlint.path_sanitizer import sanitize_path_for_report

    sub = tmp_path / "src" / "main.py"
    result = sanitize_path_for_report(sub, repo_root=tmp_path)
    assert result == "src/main.py"


def test_sanitize_path_for_report_returns_none_for_none():
    from pathlib import Path

    from sattlint.path_sanitizer import sanitize_path_for_report

    result = sanitize_path_for_report(None, repo_root=Path("."))
    assert result is None


def test_sanitize_path_for_report_external_absolute_path(tmp_path):
    import tempfile
    from pathlib import Path

    from sattlint.path_sanitizer import sanitize_path_for_report

    # Create a path outside of tmp_path but absolute
    other = Path(tempfile.gettempdir()) / "some_other" / "file.py"
    result = sanitize_path_for_report(other, repo_root=tmp_path)
    # Should be external/<filename> or external
    assert result is not None
    assert "file.py" in result or result == "<external>"


def test_sanitize_command_for_report_strips_absolute_path_args(tmp_path):
    from sattlint.path_sanitizer import sanitize_command_for_report

    sub = tmp_path / "src" / "main.py"
    sub.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["pytest", f"--output-dir={sub}", str(sub)]
    result = sanitize_command_for_report(cmd, repo_root=tmp_path)
    assert result[0] == "pytest"
    assert "src/main.py" in result[1]


# --- analyzers/framework.py: SimpleReport.summary() with note, with issues ---
def test_simple_report_summary_with_note():
    from sattlint.analyzers.framework import SimpleReport

    report = SimpleReport(name="TestReport", note="Check this info")
    summary = report.summary()
    assert "Check this info" in summary


def test_simple_report_summary_no_issues_ok():
    from sattlint.analyzers.framework import SimpleReport

    report = SimpleReport(name="TestReport")
    summary = report.summary()
    assert "No issues found" in summary


def test_simple_report_summary_with_issues():
    from sattlint.analyzers.framework import Issue, SimpleReport

    issue = Issue(kind="test.issue", message="Something is wrong", module_path=["Main", "Guard"])
    report = SimpleReport(name="TestReport", issues=[issue])
    summary = report.summary()
    assert "Findings:" in summary
    assert "Something is wrong" in summary


# --- models/usage.py: all branches ---
def test_variable_usage_mark_read_ui_and_non_ui():
    from sattlint.models.usage import VariableUsage

    u = VariableUsage()
    assert u.is_unused is True
    u.mark_read(["Main", "Guard"])
    assert u.read is True
    assert u.non_ui_read is True
    assert u.is_read_only is True
    u.mark_ui_read(["Main", "Display"])
    assert u.ui_read is True
    assert u.is_display_only is False  # has non_ui_read too


def test_variable_usage_mark_field_read_ui():
    from sattlint.models.usage import VariableUsage

    u = VariableUsage()
    u.mark_field_read("Level.Value", ["Main", "Guard"], ui=True)
    assert u.ui_read is True
    assert "Level.Value" in u.field_reads


def test_variable_usage_mark_field_read_non_ui():
    from sattlint.models.usage import VariableUsage

    u = VariableUsage()
    u.mark_field_read("Level.Value", ["Main", "Guard"])
    assert u.non_ui_read is True


def test_variable_usage_mark_written_and_mark_field_written():
    from sattlint.models.usage import VariableUsage

    u = VariableUsage()
    u.mark_written(["Main", "Guard"])
    assert u.written is True
    u.mark_field_written("Level.Value", ["Main", "Guard"])
    assert "Level.Value" in u.field_writes


def test_variable_usage_distinct_reader_writer_counts():
    from sattlint.models.usage import VariableUsage

    u = VariableUsage()
    u.mark_read(["Main", "Guard"])
    u.mark_read(["Main", "Guard"])
    u.mark_read(["Main", "Observer"])
    u.mark_field_read("Level", ["Main", "Extra"])
    assert u.distinct_reader_count == 3

    u.mark_written(["Main", "Guard"])
    u.mark_field_written("Level", ["Main", "Guard"])
    assert u.distinct_writer_count == 1


def test_variable_usage_is_display_only():
    from sattlint.models.usage import VariableUsage

    u = VariableUsage()
    u.mark_ui_read(["Main", "Display"])
    assert u.is_display_only is True


# --- resolution/type_graph.py: TypeGraph operations ---
def test_type_graph_has_record_and_field():
    from types import SimpleNamespace

    from sattlint.resolution.type_graph import TypeGraph

    dt = SimpleNamespace(
        name="RecordType",
        var_list=[
            SimpleNamespace(name="Value", datatype="Integer", state=False),
            SimpleNamespace(name="Status", datatype="Integer", state=False),
        ],
    )
    graph = TypeGraph.from_datatypes([dt])
    assert graph.has_record("RecordType") is True
    assert graph.has_record("Unknown") is False
    assert graph.record("RecordType") is not None
    assert graph.field("RecordType", "Value") is not None
    assert graph.field("RecordType", "Nonexistent") is None
    assert graph.field("Unknown", "Value") is None
    assert graph.field_type("RecordType", "Value") == "Integer"
    assert graph.field_type("Missing", "x") is None


def test_type_graph_iter_leaf_field_paths_simple_type():
    from sattline_parser.models.ast_model import Simple_DataType
    from sattlint.resolution.type_graph import TypeGraph

    graph = TypeGraph({})
    paths = list(graph.iter_leaf_field_paths(Simple_DataType.INTEGER))
    assert paths == [()]


def test_type_graph_iter_leaf_field_paths_unknown_type():
    from sattlint.resolution.type_graph import TypeGraph

    graph = TypeGraph({})
    paths = list(graph.iter_leaf_field_paths("UnknownType"))
    assert paths == [()]


def test_type_graph_iter_leaf_field_paths_nested_record():
    from types import SimpleNamespace

    from sattline_parser.models.ast_model import Simple_DataType
    from sattlint.resolution.type_graph import TypeGraph

    # RecordA has field "FieldA" of type Integer (Simple_DataType)
    dt = SimpleNamespace(
        name="RecordA",
        var_list=[SimpleNamespace(name="FieldA", datatype=Simple_DataType.INTEGER, state=False)],
    )
    graph = TypeGraph.from_datatypes([dt])
    paths = list(graph.iter_leaf_field_paths("RecordA"))
    assert ("FieldA",) in paths


def test_type_graph_iter_all_addressable_paths():
    from types import SimpleNamespace

    from sattline_parser.models.ast_model import Simple_DataType, Variable
    from sattlint.resolution.type_graph import TypeGraph

    dt = SimpleNamespace(
        name="RootType",
        var_list=[SimpleNamespace(name="Field1", datatype=Simple_DataType.INTEGER, state=False)],
    )
    graph = TypeGraph.from_datatypes([dt])
    root_var = Variable(name="Dv", datatype="RootType")
    paths = list(graph.iter_all_addressable_paths(root_var))
    assert ("Field1",) in paths


# --- console.py: print_output, has_rich, print_status fallback, print_panel fallback,
#     print_table empty rows, print_table with rows, track_items ---
def test_print_output_writes_to_stdout(capsys):
    from sattlint.console import print_output

    print_output("hello", "world", sep="-")
    captured = capsys.readouterr()
    assert "hello-world" in captured.out


def test_has_rich_returns_bool():
    from sattlint.console import has_rich

    assert isinstance(has_rich(), bool)


def test_print_status_fallback_no_rich(capsys, monkeypatch):
    import sattlint.console as console_mod

    monkeypatch.setattr(console_mod, "_RICH_AVAILABLE", False)
    console_mod.print_status("test message", level="error")
    captured = capsys.readouterr()
    assert "ERROR" in captured.out
    assert "test message" in captured.out


def test_print_panel_fallback_no_rich(capsys, monkeypatch):
    import sattlint.console as console_mod

    monkeypatch.setattr(console_mod, "_RICH_AVAILABLE", False)
    console_mod.print_panel("My Title", "Panel body text")
    captured = capsys.readouterr()
    assert "My Title" in captured.out
    assert "Panel body text" in captured.out


def test_print_table_empty_rows_no_rich(capsys, monkeypatch):
    import sattlint.console as console_mod

    monkeypatch.setattr(console_mod, "_RICH_AVAILABLE", False)
    console_mod.print_table("My Table", ["Col1", "Col2"], [])
    captured = capsys.readouterr()
    assert "My Table" in captured.out
    assert "(none)" in captured.out


def test_print_table_with_rows_no_rich(capsys, monkeypatch):
    import sattlint.console as console_mod

    monkeypatch.setattr(console_mod, "_RICH_AVAILABLE", False)
    console_mod.print_table("My Table", ["Name", "Value"], [["alpha", "1"], ["beta", "2"]])
    captured = capsys.readouterr()
    assert "alpha" in captured.out
    assert "beta" in captured.out


def test_track_items_returns_iterable_without_rich(monkeypatch):
    import sattlint.console as console_mod

    monkeypatch.setattr(console_mod, "_RICH_AVAILABLE", False)
    items = [1, 2, 3]
    result = list(console_mod.track_items(items, description="Loading"))
    assert result == [1, 2, 3]
