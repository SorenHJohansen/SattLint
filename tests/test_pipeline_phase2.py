def test_phase2_rule_metadata_gate_fails_on_enforced_finding():
    """Gate status is 'fail' and rule appears in blocking_rule_ids when an enforced finding is present."""
    from sattlint.devtools.structural_reports import collect_phase2_rule_metadata_gate

    architecture_report = {
        "findings": [
            {
                "id": "rule-acceptance-test-gap",
                "severity": "error",
                "message": "Rule missing acceptance tests",
                "missing_rule_ids": ["semantic.some-new-rule"],
            }
        ]
    }

    gate = collect_phase2_rule_metadata_gate(architecture_report)

    assert gate["status"] == "fail"
    assert "semantic.some-new-rule" in gate["blocking_rule_ids"]
    assert gate["advisory_rule_ids"] == []


def test_phase2_rule_metadata_gate_advisory_finding_does_not_fail():
    """Gate status remains 'pass' when only advisory findings are present."""
    from sattlint.devtools.structural_reports import collect_phase2_rule_metadata_gate

    architecture_report = {
        "findings": [
            {
                "id": "rule-corpus-link-gap",
                "severity": "warning",
                "message": "Rule not linked to corpus case",
                "missing_rule_ids": ["semantic.some-rule"],
            }
        ]
    }

    gate = collect_phase2_rule_metadata_gate(architecture_report)

    assert gate["status"] == "pass"
    assert "semantic.some-rule" in gate["advisory_rule_ids"]
    assert gate["blocking_rule_ids"] == []


def test_phase2_rule_metadata_gate_passes_with_clean_architecture_report():
    """Gate status is 'pass' with no blocking or advisory rule IDs when no gate findings exist."""
    from sattlint.devtools.structural_reports import collect_phase2_rule_metadata_gate

    gate = collect_phase2_rule_metadata_gate({"findings": []})

    assert gate["status"] == "pass"
    assert gate["blocking_rule_ids"] == []
    assert gate["advisory_rule_ids"] == []


def test_phase2_rule_metadata_gate_both_enforced_and_advisory():
    """Blocking findings cause fail; advisory findings are also collected independently."""
    from sattlint.devtools.structural_reports import collect_phase2_rule_metadata_gate

    architecture_report = {
        "findings": [
            {
                "id": "rule-acceptance-test-gap",
                "severity": "error",
                "message": "Missing acceptance tests",
                "missing_rule_ids": ["semantic.rule-a"],
            },
            {
                "id": "rule-corpus-link-gap",
                "severity": "warning",
                "message": "Missing corpus link",
                "missing_rule_ids": ["semantic.rule-b"],
            },
        ]
    }

    gate = collect_phase2_rule_metadata_gate(architecture_report)

    assert gate["status"] == "fail"
    assert "semantic.rule-a" in gate["blocking_rule_ids"]
    assert "semantic.rule-b" in gate["advisory_rule_ids"]


# ---------------------------------------------------------------------------
# ID2/ID7: sattline_semantic and rule_metrics report builder tests
# ---------------------------------------------------------------------------


def test_build_sattline_semantic_report_groups_by_rule():
    """build_sattline_semantic_report extracts semantic findings and groups them correctly."""
    from sattlint.devtools.semantic_reports import build_sattline_semantic_report

    findings_report = {
        "findings": [
            {
                "rule_id": "semantic.unused-variable",
                "severity": "warning",
                "category": "variable-lifecycle",
                "source": "variables",
            },
            {
                "rule_id": "semantic.unused-variable",
                "severity": "warning",
                "category": "variable-lifecycle",
                "source": "variables",
            },
            {
                "rule_id": "semantic.read-before-write",
                "severity": "warning",
                "category": "control-flow",
                "source": "dataflow",
            },
            # Non-semantic finding should be excluded
            {"rule_id": "ruff-e501", "severity": "warning", "category": "style", "source": "ruff"},
        ]
    }

    report = build_sattline_semantic_report(findings_report)

    assert report["kind"] == "sattlint.sattline_semantic"
    assert report["schema_version"] == 1
    assert report["total_count"] == 3
    rule_ids = [r["rule_id"] for r in report["rules"]]
    assert "semantic.unused-variable" in rule_ids
    assert "semantic.read-before-write" in rule_ids
    assert "ruff-e501" not in rule_ids
    unused_entry = next(r for r in report["rules"] if r["rule_id"] == "semantic.unused-variable")
    assert unused_entry["count"] == 2
    assert report["by_severity"]["warning"] == 3
    assert "variable-lifecycle" in report["by_category"]


def test_build_sattline_semantic_report_empty_findings():
    """build_sattline_semantic_report handles zero semantic findings gracefully."""
    from sattlint.devtools.semantic_reports import build_sattline_semantic_report

    report = build_sattline_semantic_report({"findings": []})

    assert report["total_count"] == 0
    assert report["rules"] == []
    assert report["by_category"] == {}
    assert report["by_severity"] == {}


def test_build_rule_metrics_report_counts_firings():
    """build_rule_metrics_report counts per-rule firing frequency."""
    from sattlint.devtools.semantic_reports import build_rule_metrics_report

    findings_report = {
        "findings": [
            {
                "rule_id": "semantic.unused-variable",
                "location": {"path": "src/foo.s"},
            },
            {
                "rule_id": "semantic.unused-variable",
                "location": {"path": "src/bar.s"},
            },
            {
                "rule_id": "semantic.read-before-write",
                "location": {"path": "src/foo.s"},
            },
        ]
    }

    report = build_rule_metrics_report(findings_report)

    assert report["kind"] == "sattlint.rule_metrics"
    assert report["summary"]["total_semantic_finding_count"] == 3
    assert report["summary"]["rules_triggered_count"] == 2
    unused_entry = next(r for r in report["rules"] if r["rule_id"] == "semantic.unused-variable")
    assert unused_entry["finding_count"] == 2
    assert unused_entry["targets_affected"] == 2


def test_build_rule_metrics_report_never_triggered_uses_registry():
    """Rules present in the analyzer registry but not in findings appear in never_triggered."""
    from sattlint.devtools.semantic_reports import build_rule_metrics_report

    findings_report = {"findings": []}
    analyzer_registry = {
        "rules": [
            {"rule_id": "semantic.unused-variable"},
            {"rule_id": "semantic.read-before-write"},
        ]
    }

    report = build_rule_metrics_report(findings_report, analyzer_registry)

    assert "semantic.unused-variable" in report["never_triggered"]
    assert "semantic.read-before-write" in report["never_triggered"]
    assert report["summary"]["rules_never_triggered_count"] == 2


# ---------------------------------------------------------------------------
# ID3: Trace timing aggregation tests
# ---------------------------------------------------------------------------


def test_trace_timing_summary_is_present_and_aggregates_phases():
    """trace_basepicture_analysis includes timing_summary keyed by phase."""
    from sattline_parser.models.ast_model import BasePicture, ModuleHeader
    from sattlint.tracing import trace_basepicture_analysis

    bp = BasePicture(
        header=ModuleHeader(name="Minimal", invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0)),
        localvariables=[],
        modulecode=None,
    )

    result = trace_basepicture_analysis(bp)

    assert "timing_summary" in result
    timing = result["timing_summary"]
    assert isinstance(timing, dict)
    # There should be at least one phase in the summary
    assert len(timing) >= 1
    for _phase, stats in timing.items():
        assert isinstance(stats["event_count"], int)
        assert stats["event_count"] >= 1
        assert isinstance(stats["span_ms"], float)
        assert stats["span_ms"] >= 0.0
