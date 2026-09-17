"""Analyzer guardrail tests."""

from pathlib import Path

from sattlint.analyzers.cyclomatic_complexity import analyze_cyclomatic_complexity
from sattlint.engine import parse_source_file

FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "analyzer_guardrails"


def _fixture(name: str) -> Path:
    return FIXTURE_DIR / name


def test_analyzer_guardrail_complexity_fixture_triggers_complexity_issue():
    bp = parse_source_file(_fixture("CyclomaticComplexityHigh.s"))

    report = analyze_cyclomatic_complexity(bp)

    assert any(issue.kind == "module.cyclomatic_complexity" for issue in report.issues)
