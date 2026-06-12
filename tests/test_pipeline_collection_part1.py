# pyright: reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownArgumentType=false, reportPrivateUsage=false
# ruff: noqa: F403, F405
from ._pipeline_collection_test_support import *


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
    assert "state-inference" not in report["declared_cli_analyzers"]
    assert "state-inference" not in report["actual_cli_analyzers"]
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
    assert "analyzer-acceptance-test-path-gap" not in finding_ids
    assert "rule-acceptance-test-path-gap" not in finding_ids


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


def test_collect_analyzer_registry_report_includes_semantic_rule_mappings():  # noqa: PLR0915
    report = pipeline._collect_analyzer_registry_report()
    sattline_semantics = next(analyzer for analyzer in report["analyzers"] if analyzer["key"] == "sattline-semantics")
    dataflow = next(analyzer for analyzer in report["analyzers"] if analyzer["key"] == "dataflow")
    mms_interface = next(analyzer for analyzer in report["analyzers"] if analyzer["key"] == "mms-interface")
    naming_consistency = next(analyzer for analyzer in report["analyzers"] if analyzer["key"] == "naming-consistency")
    timing = next(analyzer for analyzer in report["analyzers"] if analyzer["key"] == "timing")
    powerup = next(analyzer for analyzer in report["analyzers"] if analyzer["key"] == "powerup")
    scan_concurrency = next(analyzer for analyzer in report["analyzers"] if analyzer["key"] == "scan-concurrency")
    interface_contracts = next(analyzer for analyzer in report["analyzers"] if analyzer["key"] == "interface-contracts")

    duplicate_alarm_tag = next(rule for rule in report["rules"] if rule["id"] == "semantic.duplicate-alarm-tag")
    read_before_write = next(rule for rule in report["rules"] if rule["id"] == "semantic.read-before-write")
    dead_overwrite = next(rule for rule in report["rules"] if rule["id"] == "semantic.dead-overwrite")
    scan_cycle_stale_read = next(rule for rule in report["rules"] if rule["id"] == "semantic.scan-cycle-stale-read")
    parallel_write_race = next(rule for rule in report["rules"] if rule["id"] == "semantic.parallel-write-race")
    cross_module_contract_mismatch = next(
        rule for rule in report["rules"] if rule["id"] == "semantic.cross-module-contract-mismatch"
    )
    unconsumed_safety_signal = next(
        rule for rule in report["rules"] if rule["id"] == "semantic.unconsumed-safety-signal"
    )
    unsafe_default = next(rule for rule in report["rules"] if rule["id"] == "semantic.unsafe-default-true")
    missing_parameter_initial_value = next(
        rule for rule in report["rules"] if rule["id"] == "semantic.missing-parameter-initial-value"
    )

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
    assert naming_consistency["acceptance_tests"] == [
        "tests/test_analyzers_suites_part1.py",
        "tests/test_analyzers_suites_part2.py",
        "tests/test_analyzers_suites_part3.py",
        "tests/test_analyzers_suites_part4.py",
        "tests/test_analyzers_suites_part5.py",
        "tests/test_analyzers_suites_part6.py",
    ]
    assert naming_consistency["exposed_via"] == ["pipeline"]
    assert timing["cli_exposed"] is True
    assert "semantic.scan-cycle-stale-read" in timing["rule_ids"]
    assert powerup["cli_exposed"] is True
    assert {"semantic.missing-parameter-initial-value", "semantic.unsafe-default-true"} <= set(powerup["rule_ids"])
    assert scan_concurrency["cli_exposed"] is False
    assert scan_concurrency["rule_ids"] == ["semantic.parallel-write-race"]
    assert interface_contracts["cli_exposed"] is False
    assert {
        "semantic.unknown-parameter-target",
        "semantic.required-parameter-connection",
        "semantic.cross-module-contract-mismatch",
        "semantic.string-mapping-mismatch",
    } <= set(interface_contracts["rule_ids"])
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
    assert "tests/test_analyzers_suites_part1.py" in duplicate_alarm_tag["acceptance_tests"]
    assert duplicate_alarm_tag["corpus_cases"] == ["workspace-common-quality-issues"]
    assert duplicate_alarm_tag["mutation_applicability"] == "required"
    assert duplicate_alarm_tag["suppression_modes"] == ["baseline"]
    assert duplicate_alarm_tag["incremental_safe"] is False
    assert read_before_write["source"] == "dataflow"
    assert {"sattline-semantics", "dataflow"} <= set(read_before_write["analyzers"])
    assert "sattline-semantics.summary" in read_before_write["outputs"]
    assert "tests/analyzers/test_dataflow.py" in read_before_write["acceptance_tests"]
    assert read_before_write["corpus_cases"] == ["workspace-common-quality-issues"]
    assert read_before_write["mutation_applicability"] == "required"
    assert dead_overwrite["source"] == "dataflow"
    assert "dataflow.summary" in dead_overwrite["outputs"]
    assert scan_cycle_stale_read["source"] == "dataflow"
    assert "sattline-semantics" in scan_cycle_stale_read["analyzers"]
    assert "timing" in scan_cycle_stale_read["analyzers"]
    assert "timing.summary" in scan_cycle_stale_read["outputs"]
    assert parallel_write_race["source"] == "sfc"
    assert "scan-concurrency" in parallel_write_race["analyzers"]
    assert "scan-concurrency.summary" in parallel_write_race["outputs"]
    assert cross_module_contract_mismatch["source"] == "variables"
    assert "interface-contracts" in cross_module_contract_mismatch["analyzers"]
    assert "interface-contracts.summary" in cross_module_contract_mismatch["outputs"]
    assert unconsumed_safety_signal["source"] == "safety-paths"
    assert "safety-paths" in unconsumed_safety_signal["analyzers"]
    assert "safety-paths.summary" in unconsumed_safety_signal["outputs"]
    assert unconsumed_safety_signal["mutation_applicability"] == "required"
    assert unsafe_default["source"] == "unsafe-defaults"
    assert "unsafe-defaults" in unsafe_default["analyzers"]
    assert "powerup" in unsafe_default["analyzers"]
    assert "unsafe-defaults.summary" in unsafe_default["outputs"]
    assert "powerup.summary" in unsafe_default["outputs"]
    assert unsafe_default["mutation_applicability"] == "required"
    assert missing_parameter_initial_value["source"] == "initial-values"
    assert "powerup" in missing_parameter_initial_value["analyzers"]
    assert "powerup.summary" in missing_parameter_initial_value["outputs"]
    assert report["rule_profiles"]["active"] == "default"
    assert [profile["name"] for profile in report["rule_profiles"]["profiles"]] == ["default"]


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
