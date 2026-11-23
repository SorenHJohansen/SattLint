"""Delivery metadata helpers extracted from the analyzer registry."""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache

from ..framework import AnalyzerSpec
from ._registry_delivery_data import default_delivery_templates


@dataclass(frozen=True)
class AnalyzerDeliveryMetadata:
    delivery_scope: str
    implementation_bucket: str
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
            output_artifacts=(summary_output_for_analyzer(spec.key),),
        )

    return AnalyzerDeliveryMetadata(
        delivery_scope=base.delivery_scope,
        implementation_bucket=base.implementation_bucket,
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
