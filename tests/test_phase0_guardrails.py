"""Phase 0 enablement guardrail tests."""

from pathlib import Path

from sattlint.analyzers.cyclomatic_complexity import analyze_cyclomatic_complexity
from sattlint.analyzers.naming import analyze_naming_consistency
from sattlint.analyzers.parameter_drift import analyze_parameter_drift
from sattlint.analyzers.scan_loop_resource_usage import analyze_scan_loop_resource_usage
from sattlint.analyzers.variables import IssueKind, VariablesAnalyzer
from sattlint.engine import parse_source_file

FIXTURE_DIR = (
    Path(__file__).parent
    / "fixtures"
    / "sample_sattline_files"
    / "phase0_guardrails"
)


def _fixture(name: str) -> Path:
    return FIXTURE_DIR / name


def test_phase0_complexity_fixture_triggers_complexity_issue():
    bp = parse_source_file(_fixture("CyclomaticComplexityHigh.s"))

    report = analyze_cyclomatic_complexity(bp)

    assert any(issue.kind == "module.cyclomatic_complexity" for issue in report.issues)


def test_phase0_parameter_drift_fixture_triggers_parameter_drift_issue():
    bp = parse_source_file(_fixture("ParameterDrift.s"))

    report = analyze_parameter_drift(bp)

    assert any(issue.kind == "module.parameter_drift" for issue in report.issues)


def test_phase0_required_parameter_fixture_triggers_required_mapping_issue():
    bp = parse_source_file(_fixture("RequiredParameterConnection.s"))

    issues = VariablesAnalyzer(bp).run()

    assert any(
        issue.kind is IssueKind.REQUIRED_PARAMETER_CONNECTION
        for issue in issues
    )


def test_phase0_scan_loop_fixture_triggers_resource_usage_issue():
    bp = parse_source_file(_fixture("ScanLoopCost.s"))

    report = analyze_scan_loop_resource_usage(bp)

    assert any(issue.kind == "scan_cycle.resource_usage" for issue in report.issues)


def test_phase0_naming_fixture_triggers_naming_style_issue():
    bp = parse_source_file(_fixture("NamingRoleMismatch.s"))

    report = analyze_naming_consistency(bp)

    assert any(issue.kind == "naming.inconsistent_style" for issue in report.issues)
