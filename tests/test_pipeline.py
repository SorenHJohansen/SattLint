import json
from types import SimpleNamespace

from sattlint.contracts import FindingCollection, FindingRecord
from sattlint.devtools import corpus, pipeline
from sattlint.devtools.artifact_registry import ArtifactDefinition
from sattlint.devtools.baselines import build_analysis_diff_report
from sattlint.devtools.finding_exports import build_pipeline_finding_collection
from sattlint.devtools.pipeline_artifacts import (
    PipelineArtifactContext,
    PipelineArtifactProducer,
    validate_pipeline_artifact_producers,
    write_pipeline_artifacts,
)
from sattlint.reporting.variables_report import IssueKind

from .helpers.artifact_assertions import (
    assert_analysis_diff_report,
    assert_artifact_registry_report,
    assert_corpus_results_report,
    assert_findings_collection,
    assert_findings_schema,
)


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
    phase2_gate = report["phase2_rule_metadata_gate"]

    assert "dataflow" in report["registered_analyzers"]
    assert report["declared_cli_analyzers"] == report["actual_cli_analyzers"]
    assert report["declared_lsp_analyzers"] == report["actual_lsp_analyzers"]
    assert report["analyzers_missing_exposure"] == ["naming-consistency"]
    assert report["analyzers_missing_acceptance_tests"] == []
    assert report["rules_missing_acceptance_tests"] == []
    assert report["rules_missing_mutation_applicability"] == []
    assert report["rules_missing_suppression_modes"] == []
    assert report["rules_missing_incremental_safety_markers"] == []
    assert "semantic.duplicate-alarm-tag" in report["rules_missing_corpus_links"]
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
    assert phase2_gate["advisory_finding_ids"] == ["rule-corpus-link-gap"]
    assert "semantic.duplicate-alarm-tag" in phase2_gate["advisory_rule_ids"]
    exposure_gap = next(
        finding for finding in report["findings"] if finding["id"] == "analyzer-exposure-gap"
    )
    corpus_gap = next(
        finding for finding in report["findings"] if finding["id"] == "rule-corpus-link-gap"
    )
    assert exposure_gap["missing_analyzers"] == ["naming-consistency"]
    assert "semantic.duplicate-alarm-tag" in corpus_gap["missing_rule_ids"]


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
    sattline_semantics = next(
        analyzer for analyzer in report["analyzers"] if analyzer["key"] == "sattline-semantics"
    )
    dataflow = next(
        analyzer for analyzer in report["analyzers"] if analyzer["key"] == "dataflow"
    )
    mms_interface = next(
        analyzer for analyzer in report["analyzers"] if analyzer["key"] == "mms-interface"
    )
    naming_consistency = next(
        analyzer for analyzer in report["analyzers"] if analyzer["key"] == "naming-consistency"
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
    assert naming_consistency["exposed_via"] == []
    assert set(duplicate_alarm_tag) == {
        "id",
        "source",
        "category",
        "severity",
        "applies_to",
        "description",
        "analyzers",
        "outputs",
        "acceptance_tests",
        "corpus_cases",
        "mutation_applicability",
        "suppression_modes",
        "incremental_safe",
    }
    assert duplicate_alarm_tag["source"] == "alarm-integrity"
    assert "alarm-integrity" in duplicate_alarm_tag["analyzers"]
    assert "alarm-integrity.summary" in duplicate_alarm_tag["outputs"]
    assert "tests/test_analyzers.py" in duplicate_alarm_tag["acceptance_tests"]
    assert duplicate_alarm_tag["corpus_cases"] == []
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
    assert any(item["rule_id"] == "analyzer-exposure-gap" and item["category"] == "architecture" for item in payload["findings"])


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
            producers=(
                PipelineArtifactProducer("summary", lambda artifact_context: {"kind": "summary"}),
            ),
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
    assert "impact_analysis" in full_artifacts


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


def test_run_pipeline_serializes_structural_graph_reports(monkeypatch, tmp_path):
    monkeypatch.setattr(pipeline, "_collect_environment_report", lambda: {"python": {"executable": "python"}})
    monkeypatch.setattr(
        pipeline,
        "_collect_structural_report_bundle",
        lambda workspace_root=pipeline.REPO_ROOT: pipeline.StructuralReportsBundle(
            architecture_report={"findings": []},
            analyzer_registry_report={"rules": []},
            graph_inputs=pipeline.WorkspaceGraphInputs(
                discovery=SimpleNamespace(program_files=(), dependency_files=()),
                snapshots=[],
                snapshot_failures=[],
            ),
            dependency_graph_report={"edges": [{"source": "main", "target": "support"}]},
            call_graph_report={"edges": [{"source": "Main", "target": "Main"}]},
            impact_analysis_report={
                "library_impacts": [{"id": "support"}],
                "module_impacts": [{"id": "Main"}, {"id": "Main.Guard"}],
            },
        ),
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
    artifact_registry = json.loads((tmp_path / "artifact_registry.json").read_text(encoding="utf-8"))
    findings_report = json.loads((tmp_path / "findings.json").read_text(encoding="utf-8"))

    assert (tmp_path / "status.json").exists()
    assert (tmp_path / "findings.json").exists()
    assert (tmp_path / "artifact_registry.json").exists()
    assert (tmp_path / "dependency_graph.json").exists()
    assert (tmp_path / "call_graph.json").exists()
    assert (tmp_path / "impact_analysis.json").exists()
    assert summary["profile"] == "full"
    assert summary["entry_report"] == "status.json"
    assert summary["reports"]["findings"] == "findings.json"
    assert summary["reports"]["artifact_registry"] == "artifact_registry.json"
    assert summary["reports"]["dependency_graph"] == "dependency_graph.json"
    assert summary["reports"]["call_graph"] == "call_graph.json"
    assert summary["reports"]["impact_analysis"] == "impact_analysis.json"
    assert_findings_schema(summary)
    assert_findings_collection(findings_report, finding_count=0, rule_ids=())
    assert_artifact_registry_report(
        artifact_registry,
        generated_by="sattlint.devtools.pipeline",
        profile="full",
        enabled_artifact_ids=("findings", "artifact_registry", "dependency_graph"),
        disabled_artifact_ids=("trace",),
    )
    assert status_report["overall_status"] == "pass"
    assert_findings_schema(status_report)
    assert status_report["tool_statuses"]["pyright"]["status"] == "pass"
    assert status_report["tool_statuses"]["rule_metadata"]["status"] == "pass"
    assert summary["counts"]["dependency_graph_edges"] == 1
    assert summary["counts"]["call_graph_edges"] == 1
    assert summary["counts"]["impact_analysis_library_nodes"] == 1
    assert summary["counts"]["impact_analysis_module_nodes"] == 2
    assert summary["counts"]["workspace_graph_snapshot_failures"] == 0
    assert summary["counts"]["normalized_findings"] == 0
    assert summary["counts"]["baseline_new_findings"] == 0
    assert summary["counts"]["baseline_resolved_findings"] == 0
    assert summary["counts"]["baseline_changed_findings"] == 0
    assert summary["counts"]["baseline_unchanged_findings"] == 0
    assert summary["counts"]["phase2_rule_metadata_blocking_gaps"] == 0
    assert summary["counts"]["phase2_rule_metadata_advisory_gaps"] == 0


def test_run_pipeline_fails_when_enforced_rule_metadata_is_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(pipeline, "_collect_environment_report", lambda: {"python": {"executable": "python"}})
    monkeypatch.setattr(
        pipeline,
        "_collect_structural_report_bundle",
        lambda workspace_root=pipeline.REPO_ROOT: pipeline.StructuralReportsBundle(
            architecture_report={
                "findings": [
                    {
                        "id": "rule-acceptance-test-gap",
                        "severity": "medium",
                        "message": "Some semantic rules do not declare acceptance-test coverage.",
                        "missing_rule_ids": ["semantic.read-before-write"],
                    }
                ],
                "phase2_rule_metadata_gate": {
                    "status": "fail",
                    "enforced_fields": ["acceptance_tests", "mutation_applicability"],
                    "advisory_fields": ["corpus_cases"],
                    "blocking_finding_ids": ["rule-acceptance-test-gap"],
                    "advisory_finding_ids": [],
                    "blocking_rule_ids": ["semantic.read-before-write"],
                    "advisory_rule_ids": [],
                },
            },
            analyzer_registry_report={"rules": []},
            graph_inputs=pipeline.WorkspaceGraphInputs(
                discovery=SimpleNamespace(program_files=(), dependency_files=()),
                snapshots=[],
                snapshot_failures=[],
            ),
            dependency_graph_report={"edges": []},
            call_graph_report={"edges": []},
            impact_analysis_report={"library_impacts": [], "module_impacts": []},
        ),
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

    assert status_report["overall_status"] == "fail"
    assert status_report["tool_statuses"]["rule_metadata"] == {
        "status": "fail",
        "report": "architecture.json",
        "raw_exit_code": None,
        "normalized_exit_code": 1,
        "finding_count": 1,
        "detail": "1 rules missing enforced metadata",
    }
    assert summary["counts"]["phase2_rule_metadata_blocking_gaps"] == 1
    assert summary["counts"]["phase2_rule_metadata_advisory_gaps"] == 0


def test_run_pipeline_writes_analysis_diff_when_baseline_is_supplied(monkeypatch, tmp_path):
    baseline_findings_path = tmp_path / "baseline-findings.json"
    baseline_findings_path.write_text(
        json.dumps(
            {
                "kind": "sattlint.findings",
                "schema_version": 1,
                "finding_count": 1,
                "findings": [
                    {
                        "id": "pytest-old",
                        "rule_id": "pytest.failures",
                        "category": "correctness",
                        "severity": "high",
                        "confidence": "high",
                        "message": "Pytest reported failing tests.",
                        "source": "pytest",
                        "analyzer": "pytest",
                        "artifact": "findings",
                        "location": {
                            "path": None,
                            "line": None,
                            "column": None,
                            "symbol": None,
                            "module_path": [],
                        },
                        "fingerprint": None,
                        "detail": None,
                        "suggestion": None,
                        "data": {},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(pipeline, "_collect_environment_report", lambda: {"python": {"executable": "python"}})
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
            "summary": {"tests": 2, "failures": 1, "errors": 0, "skipped": 0},
            "testcases": [],
        },
    )

    summary = pipeline._run_pipeline(
        tmp_path,
        trace_target=None,
        profile="quick",
        baseline_findings=baseline_findings_path,
    )

    analysis_diff_report = json.loads((tmp_path / "analysis_diff.json").read_text(encoding="utf-8"))
    artifact_registry = json.loads((tmp_path / "artifact_registry.json").read_text(encoding="utf-8"))

    assert summary["reports"]["analysis_diff"] == "analysis_diff.json"
    assert_analysis_diff_report(
        analysis_diff_report,
        summary={
            "new_count": 0,
            "resolved_count": 0,
            "changed_count": 1,
            "unchanged_count": 0,
        },
        baseline_label="<external>/baseline-findings.json",
        current_label="findings.json",
        changed_rule_ids=("pytest.failures",),
    )
    assert summary["counts"]["baseline_new_findings"] == 0
    assert summary["counts"]["baseline_resolved_findings"] == 0
    assert summary["counts"]["baseline_changed_findings"] == 1
    assert summary["counts"]["baseline_unchanged_findings"] == 0
    assert_artifact_registry_report(
        artifact_registry,
        profile="quick",
        enabled_artifact_ids=("analysis_diff",),
    )


def test_run_pipeline_writes_corpus_results_when_manifest_dir_is_supplied(monkeypatch, tmp_path):
    manifest_dir = tmp_path / "manifests"
    manifest_dir.mkdir()

    monkeypatch.setattr(pipeline, "_collect_environment_report", lambda: {"python": {"executable": "python"}})
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
            "summary": {"tests": 1, "failures": 0, "errors": 0, "skipped": 0},
            "testcases": [],
        },
    )
    monkeypatch.setattr(
        pipeline,
        "run_corpus_suite",
        lambda output_dir, manifest_dir, repo_root, write_results=False: corpus.CorpusSuiteResult(
            cases=(
                corpus.CorpusRunResult(
                    manifest=corpus.CorpusCaseManifest(
                        case_id="workspace-semantic",
                        target_file="tests/fixtures/corpus/valid/Program.s",
                        mode="workspace",
                        expectation=corpus.CorpusExpectation(
                            expected_finding_ids=("semantic.read-before-write",),
                        ),
                    ),
                    evaluation=corpus.CorpusEvaluation(
                        case_id="workspace-semantic",
                        passed=True,
                    ),
                    findings_report="findings.json",
                    artifact_dir="corpus_cases/workspace-semantic",
                ),
            ),
            output_dir="artifacts/analysis",
            manifest_root="tests/fixtures/corpus/manifests",
        ),
    )

    summary = pipeline._run_pipeline(
        tmp_path,
        trace_target=None,
        profile="quick",
        corpus_manifest_dir=manifest_dir,
    )

    corpus_report = json.loads((tmp_path / "corpus_results.json").read_text(encoding="utf-8"))
    artifact_registry = json.loads((tmp_path / "artifact_registry.json").read_text(encoding="utf-8"))

    assert summary["reports"]["corpus_results"] == "corpus_results.json"
    assert summary["status"]["tool_statuses"]["corpus"]["status"] == "pass"
    assert summary["counts"]["corpus_case_count"] == 1
    assert summary["counts"]["corpus_failed_case_count"] == 0
    assert_corpus_results_report(
        corpus_report,
        case_count=1,
        failed_case_ids=(),
        expect_findings_schema=False,
    )
    assert corpus_report["cases"][0]["case_id"] == "workspace-semantic"
    assert_artifact_registry_report(
        artifact_registry,
        profile="quick",
        enabled_artifact_ids=("corpus_results",),
    )


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
    artifact_registry = json.loads((tmp_path / "artifact_registry.json").read_text(encoding="utf-8"))
    findings_report = json.loads((tmp_path / "findings.json").read_text(encoding="utf-8"))

    assert [name for name, _command in commands] == ["ruff", "pyright", "pytest"]
    pytest_command = next(command for name, command in commands if name == "pytest")
    assert "-o" in pytest_command
    assert any(part.startswith("addopts=--strict-markers --strict-config") for part in pytest_command)
    assert all(target in pytest_command for target in pipeline.DEFAULT_QUICK_PYTEST_TARGETS)
    assert summary["profile"] == "quick"
    assert summary["reports"]["findings"] == "findings.json"
    assert summary["reports"]["artifact_registry"] == "artifact_registry.json"
    assert summary["reports"]["progress"] == "progress.json"
    assert summary["reports"]["vulture"] is None
    assert summary["reports"]["bandit"] is None
    assert summary["reports"]["architecture"] is None
    assert summary["reports"]["dependency_graph"] is None
    assert_findings_schema(summary)
    assert_findings_collection(findings_report, finding_count=0, rule_ids=())
    assert_artifact_registry_report(
        artifact_registry,
        profile="quick",
        enabled_artifact_ids=("findings", "artifact_registry"),
    )
    assert all(item["artifact_id"] != "architecture" for item in artifact_registry["artifacts"])
    assert summary["counts"]["workspace_graph_snapshot_failures"] == 0
    assert summary["counts"]["normalized_findings"] == 0
    assert summary["counts"]["baseline_changed_findings"] == 0
    assert status_report["overall_status"] == "pass"
    assert status_report["progress_report"] == f"<external>/{tmp_path.name}/progress.json"
    assert_findings_schema(status_report)
    assert status_report["tool_statuses"]["vulture"]["status"] == "skipped"
    assert status_report["tool_statuses"]["bandit"]["status"] == "skipped"
    assert status_report["tool_statuses"]["rule_metadata"]["status"] == "skipped"
