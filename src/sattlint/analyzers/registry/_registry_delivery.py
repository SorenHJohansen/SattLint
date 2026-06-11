"""Delivery metadata helpers extracted from the analyzer registry."""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache

from ..framework import AnalyzerSpec
from ._registry_delivery_data import default_delivery_templates


@dataclass(frozen=True)
class AnalyzerDeliveryMetadata:
    scope: str
    implementation_bucket: str
    output_artifacts: tuple[str, ...] = ()
    cli_exposed: bool = False
    lsp_exposed: bool = False
    acceptance_tests: tuple[str, ...] = ()
    depends_on_analyzers: tuple[str, ...] = ()
    depends_on_artifacts: tuple[str, ...] = ()
    supports_baselines: bool = True
    supports_incremental: bool = False
    min_fixture_set: tuple[str, ...] = ()
    exposed_via: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "scope": self.scope,
            "implementation_bucket": self.implementation_bucket,
            "output_artifacts": list(self.output_artifacts),
            "cli_exposed": self.cli_exposed,
            "lsp_exposed": self.lsp_exposed,
            "acceptance_tests": list(self.acceptance_tests),
            "depends_on_analyzers": list(self.depends_on_analyzers),
            "depends_on_artifacts": list(self.depends_on_artifacts),
            "supports_baselines": self.supports_baselines,
            "supports_incremental": self.supports_incremental,
            "min_fixture_set": list(self.min_fixture_set),
            "exposed_via": list(self.exposed_via),
        }


def summary_output_for_analyzer(analyzer_key: str) -> str:
    return f"{analyzer_key}.summary"


@cache
def _base_delivery_metadata_by_analyzer(
    semantic_layer_analyzer_key: str,
) -> dict[str, AnalyzerDeliveryMetadata]:
    shared_fixtures = ("tests/fixtures/sample_sattline_files",)
    return {
        template.key: AnalyzerDeliveryMetadata(
            scope=template.scope,
            implementation_bucket=template.implementation_bucket,
            cli_exposed=template.cli_exposed,
            lsp_exposed=template.lsp_exposed,
            acceptance_tests=template.acceptance_tests,
            depends_on_analyzers=template.depends_on_analyzers,
            depends_on_artifacts=template.depends_on_artifacts,
            supports_baselines=template.supports_baselines,
            supports_incremental=template.supports_incremental,
            min_fixture_set=template.min_fixture_set,
            exposed_via=template.exposed_via,
        )
        for template in default_delivery_templates(semantic_layer_analyzer_key, shared_fixtures)
    }


def build_delivery_metadata(
    spec: AnalyzerSpec,
    rule_ids: tuple[str, ...],
    *,
    semantic_layer_analyzer_key: str,
) -> AnalyzerDeliveryMetadata:
    base = _base_delivery_metadata_by_analyzer(semantic_layer_analyzer_key).get(spec.key)
    if base is None:
        return AnalyzerDeliveryMetadata(
            scope="workspace",
            implementation_bucket="analyzers",
            output_artifacts=(summary_output_for_analyzer(spec.key),),
        )

    output_artifacts = [summary_output_for_analyzer(spec.key)]
    semantic_summary = summary_output_for_analyzer(semantic_layer_analyzer_key)
    if spec.key != semantic_layer_analyzer_key and rule_ids and semantic_summary not in output_artifacts:
        output_artifacts.append(semantic_summary)

    return AnalyzerDeliveryMetadata(
        scope=base.scope,
        implementation_bucket=base.implementation_bucket,
        output_artifacts=tuple(output_artifacts),
        cli_exposed=base.cli_exposed,
        lsp_exposed=base.lsp_exposed,
        acceptance_tests=base.acceptance_tests,
        depends_on_analyzers=base.depends_on_analyzers,
        depends_on_artifacts=base.depends_on_artifacts,
        supports_baselines=base.supports_baselines,
        supports_incremental=base.supports_incremental,
        min_fixture_set=base.min_fixture_set,
        exposed_via=base.exposed_via,
    )


__all__ = [
    "AnalyzerDeliveryMetadata",
    "build_delivery_metadata",
    "summary_output_for_analyzer",
]
