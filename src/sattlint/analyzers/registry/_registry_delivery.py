"""Delivery metadata helpers extracted from the analyzer registry."""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache
from typing import TYPE_CHECKING

from ..framework import AnalyzerSpec
from ._registry_delivery_data import default_delivery_templates

if TYPE_CHECKING:
    from ...application.findings import Severity

#: Default severity for findings whose kind has no curated entry. It is the
#: analyzer's broad posture, not a copy of its category. An analyzer that mixes
#: advice into its output still defaults to ``warning``; the per-kind table in
#: the findings layer names the advice kinds explicitly.
_DEFAULT_SEVERITY_BY_ANALYZER: dict[str, Severity] = {
    "variables": "warning",
    "datatype-fields": "warning",
    "moduletype-usage": "warning",
    "module-layout": "warning",
    "picture-display-paths": "warning",
    "string-capacity": "warning",
    "string-style": "info",
    "icf": "warning",
    "sfc": "warning",
    "comment-code": "info",
    "alarm-integrity": "warning",
    "cyclomatic-complexity": "info",
    "same-cycle": "warning",
    "dataflow": "warning",
}


@dataclass(frozen=True)
class AnalyzerDeliveryMetadata:
    delivery_scope: str
    implementation_bucket: str
    severity: Severity = "warning"
    output_artifacts: tuple[str, ...] = ()
    acceptance_tests: tuple[str, ...] = ()
    depends_on_artifacts: tuple[str, ...] = ()
    supports_baselines: bool = True
    supports_incremental: bool = False
    min_fixture_set: tuple[str, ...] = ()


def summary_output_for_analyzer(analyzer_key: str) -> str:
    return f"{analyzer_key}.summary"


@cache
def _base_delivery_metadata_by_analyzer() -> dict[str, AnalyzerDeliveryMetadata]:
    shared_fixtures = ("tests/fixtures/sample_sattline_files",)
    return {
        template.key: AnalyzerDeliveryMetadata(
            delivery_scope=template.delivery_scope,
            implementation_bucket=template.implementation_bucket,
            severity=_DEFAULT_SEVERITY_BY_ANALYZER.get(template.key, "warning"),
            acceptance_tests=template.acceptance_tests,
            depends_on_artifacts=template.depends_on_artifacts,
            supports_baselines=template.supports_baselines,
            supports_incremental=template.supports_incremental,
            min_fixture_set=template.min_fixture_set,
        )
        for template in default_delivery_templates(shared_fixtures)
    }


def build_delivery_metadata(spec: AnalyzerSpec) -> AnalyzerDeliveryMetadata:
    base = _base_delivery_metadata_by_analyzer().get(spec.key)
    if base is None:
        return AnalyzerDeliveryMetadata(
            delivery_scope="workspace",
            implementation_bucket="analyzers",
            severity="warning",
            output_artifacts=(summary_output_for_analyzer(spec.key),),
        )

    return AnalyzerDeliveryMetadata(
        delivery_scope=base.delivery_scope,
        implementation_bucket=base.implementation_bucket,
        severity=base.severity,
        output_artifacts=(summary_output_for_analyzer(spec.key),),
        acceptance_tests=base.acceptance_tests,
        depends_on_artifacts=base.depends_on_artifacts,
        supports_baselines=base.supports_baselines,
        supports_incremental=base.supports_incremental,
        min_fixture_set=base.min_fixture_set,
    )


__all__ = [
    "AnalyzerDeliveryMetadata",
    "build_delivery_metadata",
    "summary_output_for_analyzer",
]
