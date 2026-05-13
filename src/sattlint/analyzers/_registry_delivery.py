"""Delivery metadata helpers extracted from the analyzer registry."""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache

from .framework import AnalyzerSpec


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
        semantic_layer_analyzer_key: AnalyzerDeliveryMetadata(
            scope="workspace",
            implementation_bucket="shared-semantic-core",
            lsp_exposed=True,
            acceptance_tests=(
                "tests/analyzers/test_sattline_semantics.py",
                "tests/test_pipeline.py",
            ),
            min_fixture_set=shared_fixtures,
        ),
        "symbolic_lite": AnalyzerDeliveryMetadata(
            scope="cross-module",
            implementation_bucket="shared-semantic-core",
            acceptance_tests=(
                "tests/analyzers/test_dataflow.py",
                "tests/analyzers/test_sattline_semantics.py",
            ),
            depends_on_analyzers=(semantic_layer_analyzer_key,),
            min_fixture_set=shared_fixtures,
            exposed_via=(semantic_layer_analyzer_key,),
        ),
        "variables": AnalyzerDeliveryMetadata(
            scope="workspace",
            implementation_bucket="variables-reporting",
            cli_exposed=True,
            lsp_exposed=True,
            acceptance_tests=(
                "tests/test_analyzers.py",
                "tests/analyzers/test_sattline_semantics.py",
                "tests/test_app.py",
            ),
            supports_incremental=True,
            min_fixture_set=shared_fixtures,
            exposed_via=(semantic_layer_analyzer_key,),
        ),
        "mms-interface": AnalyzerDeliveryMetadata(
            scope="workspace",
            implementation_bucket="interface-mapping",
            cli_exposed=True,
            acceptance_tests=(
                "tests/test_analyzers.py",
                "tests/test_app.py",
            ),
            min_fixture_set=shared_fixtures,
        ),
        "sfc": AnalyzerDeliveryMetadata(
            scope="single-file",
            implementation_bucket="shared-semantic-core",
            cli_exposed=True,
            lsp_exposed=True,
            acceptance_tests=(
                "tests/analyzers/test_sfc.py",
                "tests/test_analyzers.py",
                "tests/analyzers/test_sattline_semantics.py",
            ),
            depends_on_analyzers=(semantic_layer_analyzer_key,),
            min_fixture_set=shared_fixtures,
            exposed_via=(semantic_layer_analyzer_key,),
        ),
        "comment-code": AnalyzerDeliveryMetadata(
            scope="single-file",
            implementation_bucket="comment-scan",
            cli_exposed=True,
            acceptance_tests=(
                "tests/analyzers/test_comment_code.py",
                "tests/test_app.py",
            ),
        ),
        "shadowing": AnalyzerDeliveryMetadata(
            scope="workspace",
            implementation_bucket="variables-reporting",
            cli_exposed=True,
            acceptance_tests=(
                "tests/test_analyzers.py",
                "tests/test_app.py",
                "tests/test_pipeline.py",
            ),
            min_fixture_set=shared_fixtures,
        ),
        "spec-compliance": AnalyzerDeliveryMetadata(
            scope="workspace",
            implementation_bucket="engineering-rules",
            cli_exposed=True,
            lsp_exposed=True,
            acceptance_tests=(
                "tests/analyzers/test_spec_compliance.py",
                "tests/test_app.py",
            ),
            min_fixture_set=shared_fixtures,
        ),
        "loop-output-refactor": AnalyzerDeliveryMetadata(
            scope="single-file",
            implementation_bucket="engineering-rules",
            cli_exposed=True,
            acceptance_tests=(
                "tests/test_analyzers.py",
                "tests/test_app.py",
            ),
            min_fixture_set=shared_fixtures,
        ),
        "alarm-integrity": AnalyzerDeliveryMetadata(
            scope="cross-module",
            implementation_bucket="shared-semantic-core",
            lsp_exposed=True,
            acceptance_tests=(
                "tests/test_analyzers.py",
                "tests/analyzers/test_sattline_semantics.py",
            ),
            depends_on_analyzers=(semantic_layer_analyzer_key,),
            min_fixture_set=shared_fixtures,
            exposed_via=(semantic_layer_analyzer_key,),
        ),
        "initial-values": AnalyzerDeliveryMetadata(
            scope="workspace",
            implementation_bucket="engineering-rules",
            lsp_exposed=True,
            acceptance_tests=("tests/test_analyzers.py",),
            min_fixture_set=shared_fixtures,
        ),
        "interface_contracts": AnalyzerDeliveryMetadata(
            scope="workspace",
            implementation_bucket="interface-mapping",
            acceptance_tests=("tests/analyzers/test_interface_contracts.py",),
            min_fixture_set=shared_fixtures,
            exposed_via=("pipeline",),
        ),
        "powerup": AnalyzerDeliveryMetadata(
            scope="workspace",
            implementation_bucket="engineering-rules",
            cli_exposed=True,
            acceptance_tests=("tests/analyzers/test_powerup.py",),
            min_fixture_set=shared_fixtures,
            exposed_via=("cli", "pipeline"),
        ),
        "naming-consistency": AnalyzerDeliveryMetadata(
            scope="workspace",
            implementation_bucket="engineering-rules",
            acceptance_tests=("tests/test_analyzers.py",),
            min_fixture_set=shared_fixtures,
            exposed_via=("pipeline",),
        ),
        "cyclomatic-complexity": AnalyzerDeliveryMetadata(
            scope="single-file",
            implementation_bucket="engineering-rules",
            acceptance_tests=("tests/test_analyzers.py",),
            min_fixture_set=shared_fixtures,
            exposed_via=("pipeline",),
        ),
        "parameter-drift": AnalyzerDeliveryMetadata(
            scope="cross-module",
            implementation_bucket="engineering-rules",
            acceptance_tests=("tests/test_analyzers.py",),
            min_fixture_set=shared_fixtures,
            exposed_via=("pipeline",),
        ),
        "signal_lifecycle": AnalyzerDeliveryMetadata(
            scope="workspace",
            implementation_bucket="engineering-rules",
            cli_exposed=True,
            acceptance_tests=("tests/analyzers/test_signal_lifecycle.py",),
            min_fixture_set=shared_fixtures,
        ),
        "loop_stability": AnalyzerDeliveryMetadata(
            scope="single-file",
            implementation_bucket="engineering-rules",
            cli_exposed=True,
            acceptance_tests=("tests/analyzers/test_loop_stability.py",),
            min_fixture_set=shared_fixtures,
        ),
        "fault_handling": AnalyzerDeliveryMetadata(
            scope="workspace",
            implementation_bucket="engineering-rules",
            cli_exposed=True,
            acceptance_tests=("tests/analyzers/test_fault_handling.py",),
            min_fixture_set=shared_fixtures,
        ),
        "numeric_constraints": AnalyzerDeliveryMetadata(
            scope="workspace",
            implementation_bucket="engineering-rules",
            cli_exposed=True,
            acceptance_tests=("tests/analyzers/test_numeric_constraints.py",),
            min_fixture_set=shared_fixtures,
        ),
        "data_dependency": AnalyzerDeliveryMetadata(
            scope="workspace",
            implementation_bucket="shared-semantic-core",
            cli_exposed=True,
            acceptance_tests=("tests/analyzers/test_data_dependency.py",),
            min_fixture_set=shared_fixtures,
            exposed_via=("cli",),
        ),
        "config_drift": AnalyzerDeliveryMetadata(
            scope="cross-module",
            implementation_bucket="engineering-rules",
            cli_exposed=True,
            acceptance_tests=("tests/analyzers/test_config_drift.py",),
            min_fixture_set=shared_fixtures,
        ),
        "scan-loop-resource-usage": AnalyzerDeliveryMetadata(
            scope="single-file",
            implementation_bucket="engineering-rules",
            acceptance_tests=("tests/test_analyzers.py",),
            min_fixture_set=shared_fixtures,
            exposed_via=("pipeline",),
        ),
        "resource_usage": AnalyzerDeliveryMetadata(
            scope="workspace",
            implementation_bucket="shared-semantic-core",
            cli_exposed=True,
            acceptance_tests=("tests/analyzers/test_resource_usage.py",),
            min_fixture_set=shared_fixtures,
            exposed_via=("cli",),
        ),
        "scan_concurrency": AnalyzerDeliveryMetadata(
            scope="single-file",
            implementation_bucket="shared-semantic-core",
            acceptance_tests=("tests/analyzers/test_scan_concurrency.py",),
            min_fixture_set=shared_fixtures,
            exposed_via=("pipeline",),
        ),
        "timing": AnalyzerDeliveryMetadata(
            scope="single-file",
            implementation_bucket="shared-semantic-core",
            cli_exposed=True,
            acceptance_tests=("tests/analyzers/test_timing.py",),
            min_fixture_set=shared_fixtures,
            exposed_via=("cli", "pipeline"),
        ),
        "version-drift": AnalyzerDeliveryMetadata(
            scope="workspace",
            implementation_bucket="engineering-rules",
            acceptance_tests=(
                "tests/test_analyzers.py",
                "tests/test_docgen.py",
            ),
            min_fixture_set=shared_fixtures,
            exposed_via=("docgen",),
        ),
        "safety-paths": AnalyzerDeliveryMetadata(
            scope="cross-module",
            implementation_bucket="shared-semantic-core",
            lsp_exposed=True,
            acceptance_tests=(
                "tests/test_analyzers.py",
                "tests/test_sattline_semantics.py",
                "tests/test_editor_api.py",
            ),
            depends_on_analyzers=(semantic_layer_analyzer_key,),
            min_fixture_set=shared_fixtures,
            exposed_via=(semantic_layer_analyzer_key, "editor-api"),
        ),
        "taint-paths": AnalyzerDeliveryMetadata(
            scope="cross-module",
            implementation_bucket="graph-tracing",
            lsp_exposed=True,
            acceptance_tests=(
                "tests/test_analyzers.py",
                "tests/test_editor_api.py",
            ),
            min_fixture_set=shared_fixtures,
            exposed_via=(semantic_layer_analyzer_key, "editor-api"),
        ),
        "unsafe-defaults": AnalyzerDeliveryMetadata(
            scope="single-file",
            implementation_bucket="shared-semantic-core",
            lsp_exposed=True,
            acceptance_tests=(
                "tests/test_pipeline.py",
                "tests/test_sattline_semantics.py",
            ),
            depends_on_analyzers=(semantic_layer_analyzer_key,),
            min_fixture_set=shared_fixtures,
            exposed_via=(semantic_layer_analyzer_key,),
        ),
        "dataflow": AnalyzerDeliveryMetadata(
            scope="workspace",
            implementation_bucket="shared-semantic-core",
            lsp_exposed=True,
            acceptance_tests=(
                "tests/analyzers/test_dataflow.py",
                "tests/test_analyzers.py",
                "tests/test_sattline_semantics.py",
            ),
            depends_on_analyzers=(semantic_layer_analyzer_key,),
            min_fixture_set=shared_fixtures,
            exposed_via=(semantic_layer_analyzer_key,),
        ),
        "state_inference": AnalyzerDeliveryMetadata(
            scope="workspace",
            implementation_bucket="shared-semantic-core",
            acceptance_tests=(
                "tests/analyzers/test_state_inference.py",
                "tests/analyzers/test_dataflow.py",
                "tests/test_cli.py",
            ),
            depends_on_analyzers=(semantic_layer_analyzer_key, "dataflow"),
            min_fixture_set=shared_fixtures,
            exposed_via=("cli",),
        ),
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
