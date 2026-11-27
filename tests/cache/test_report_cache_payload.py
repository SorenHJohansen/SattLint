# pyright: reportPrivateUsage=false
"""A cache entry carries a report's findings, not its run-scoped evidence."""

from __future__ import annotations

import pickle
from pathlib import Path

from sattline_parser.models.ast_model import Variable

from sattlint import cache as cache_module
from sattlint.cache.classes import AnalysisReportCache
from sattlint.reporting.variables_report import UnusedIssue, VariablesReport
from sattlint.resolution.paths import CanonicalPathKey


def _variable(name: str) -> Variable:
    return Variable(name=name, datatype="Integer")


def _report_with_evidence() -> VariablesReport:
    key: CanonicalPathKey = ("BasePicture", "Counter")
    return VariablesReport(
        basepicture_name="BasePicture",
        issues=[UnusedIssue(module_path=["BasePicture"], variable=_variable("Hidden"))],
        accesses_by_definition_key={key: ()},
        effect_flow_edges={key: (key,)},
        effect_flow_display_names={key: "BasePicture.Counter"},
    )


def test_projection_keeps_findings_and_drops_per_access_evidence() -> None:
    report = _report_with_evidence()

    projection = report.cache_payload()

    assert projection.issues == report.issues
    assert projection.basepicture_name == report.basepicture_name
    assert projection.accesses_by_definition_key == {}
    assert projection.effect_flow_edges == {}
    assert projection.effect_flow_display_names == {}


def test_projection_leaves_the_live_report_untouched() -> None:
    report = _report_with_evidence()

    report.cache_payload()

    assert report.accesses_by_definition_key
    assert report.effect_flow_edges
    assert report.effect_flow_display_names


def test_projection_is_a_small_fraction_of_the_live_payload() -> None:
    report = _report_with_evidence()

    full = len(pickle.dumps(report, protocol=pickle.HIGHEST_PROTOCOL))
    projection = len(pickle.dumps(report.cache_payload(), protocol=pickle.HIGHEST_PROTOCOL))

    assert projection < full


def test_a_report_without_evidence_is_its_own_projection() -> None:
    report = VariablesReport(basepicture_name="BasePicture", issues=[])

    assert report.cache_payload() is report


def test_cacheable_payload_passes_unknown_objects_through() -> None:
    payload = {"report": object()}

    assert cache_module.cacheable_report_payload(payload) is payload


def test_a_cached_variable_report_restores_its_findings(tmp_path: Path) -> None:
    report_cache = AnalysisReportCache(tmp_path)
    key = cache_module.compute_analysis_report_cache_key("project", "variables")
    manifest_file = tmp_path / "source.q"
    manifest_file.write_text("program", encoding="utf-8")

    saved = report_cache.save(
        key, report=cache_module.cacheable_report_payload(_report_with_evidence()), files=[manifest_file]
    )
    assert saved

    restored = cache_module._as_mapping(report_cache.load(key))
    assert restored is not None
    restored_report = restored["report"]
    assert isinstance(restored_report, VariablesReport)
    assert [issue.kind for issue in restored_report.issues] == [issue.kind for issue in _report_with_evidence().issues]
    assert restored_report.accesses_by_definition_key == {}
