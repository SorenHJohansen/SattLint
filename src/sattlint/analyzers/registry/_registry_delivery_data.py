"""Declarative delivery metadata templates for the analyzer registry."""

from __future__ import annotations

from dataclasses import dataclass

_ANALYZER_SUITE_ACCEPTANCE_TESTS = (
    "tests/test_analyzers_suites_part1.py",
    "tests/test_analyzers_suites_part2.py",
    "tests/test_analyzers_suites_part3.py",
    "tests/test_analyzers_suites_part4.py",
    "tests/test_analyzers_suites_part5.py",
    "tests/test_analyzers_suites_part6.py",
)
_APP_ACCEPTANCE_TESTS = (
    "tests/test_app_cli_commands.py",
    "tests/test_app_menus.py",
)


@dataclass(frozen=True)
class AnalyzerDeliveryTemplate:
    key: str
    scope: str
    implementation_bucket: str
    cli_exposed: bool = False
    lsp_exposed: bool = False
    acceptance_tests: tuple[str, ...] = ()
    depends_on_analyzers: tuple[str, ...] = ()
    depends_on_artifacts: tuple[str, ...] = ()
    supports_baselines: bool = True
    supports_incremental: bool = False
    min_fixture_set: tuple[str, ...] = ()
    exposed_via: tuple[str, ...] = ()


def default_delivery_templates(
    semantic_layer_analyzer_key: str,
    shared_fixtures: tuple[str, ...],
) -> tuple[AnalyzerDeliveryTemplate, ...]:
    return (
        AnalyzerDeliveryTemplate(
            key=semantic_layer_analyzer_key,
            scope="workspace",
            implementation_bucket="shared-semantic-core",
            lsp_exposed=True,
            acceptance_tests=(
                "tests/analyzers/test_sattline_semantics.py",
                "tests/test_pipeline_phase2.py",
            ),
            min_fixture_set=shared_fixtures,
        ),
        AnalyzerDeliveryTemplate(
            key="symbolic_lite",
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
        AnalyzerDeliveryTemplate(
            key="variables",
            scope="workspace",
            implementation_bucket="variables-reporting",
            cli_exposed=True,
            lsp_exposed=True,
            acceptance_tests=(
                *_ANALYZER_SUITE_ACCEPTANCE_TESTS,
                "tests/analyzers/test_sattline_semantics.py",
                *_APP_ACCEPTANCE_TESTS,
            ),
            supports_incremental=True,
            min_fixture_set=shared_fixtures,
            exposed_via=(semantic_layer_analyzer_key,),
        ),
        AnalyzerDeliveryTemplate(
            key="picture-display-paths",
            scope="workspace",
            implementation_bucket="workspace-navigation",
            cli_exposed=True,
            acceptance_tests=("tests/analyzers/test_picture_display_paths.py", *_APP_ACCEPTANCE_TESTS),
            min_fixture_set=shared_fixtures,
        ),
        AnalyzerDeliveryTemplate(
            key="mms-interface",
            scope="workspace",
            implementation_bucket="interface-mapping",
            cli_exposed=True,
            acceptance_tests=(*_ANALYZER_SUITE_ACCEPTANCE_TESTS, *_APP_ACCEPTANCE_TESTS),
            min_fixture_set=shared_fixtures,
        ),
        AnalyzerDeliveryTemplate(
            key="sfc",
            scope="single-file",
            implementation_bucket="shared-semantic-core",
            cli_exposed=True,
            lsp_exposed=True,
            acceptance_tests=(
                "tests/analyzers/test_sfc.py",
                *_ANALYZER_SUITE_ACCEPTANCE_TESTS,
                "tests/analyzers/test_sattline_semantics.py",
            ),
            depends_on_analyzers=(semantic_layer_analyzer_key,),
            min_fixture_set=shared_fixtures,
            exposed_via=(semantic_layer_analyzer_key,),
        ),
        AnalyzerDeliveryTemplate(
            key="comment-code",
            scope="single-file",
            implementation_bucket="comment-scan",
            cli_exposed=True,
            acceptance_tests=("tests/analyzers/test_comment_code.py", *_APP_ACCEPTANCE_TESTS),
        ),
        AnalyzerDeliveryTemplate(
            key="shadowing",
            scope="workspace",
            implementation_bucket="variables-reporting",
            cli_exposed=True,
            acceptance_tests=(
                *_ANALYZER_SUITE_ACCEPTANCE_TESTS,
                *_APP_ACCEPTANCE_TESTS,
                "tests/test_pipeline_phase2.py",
            ),
            min_fixture_set=shared_fixtures,
        ),
        AnalyzerDeliveryTemplate(
            key="spec-compliance",
            scope="workspace",
            implementation_bucket="engineering-rules",
            cli_exposed=True,
            lsp_exposed=True,
            acceptance_tests=("tests/analyzers/test_spec_compliance.py", *_APP_ACCEPTANCE_TESTS),
            min_fixture_set=shared_fixtures,
        ),
        AnalyzerDeliveryTemplate(
            key="loop-output-refactor",
            scope="single-file",
            implementation_bucket="engineering-rules",
            cli_exposed=True,
            acceptance_tests=(*_ANALYZER_SUITE_ACCEPTANCE_TESTS, *_APP_ACCEPTANCE_TESTS),
            min_fixture_set=shared_fixtures,
        ),
        AnalyzerDeliveryTemplate(
            key="alarm-integrity",
            scope="cross-module",
            implementation_bucket="shared-semantic-core",
            lsp_exposed=True,
            acceptance_tests=(
                *_ANALYZER_SUITE_ACCEPTANCE_TESTS,
                "tests/analyzers/test_sattline_semantics.py",
            ),
            depends_on_analyzers=(semantic_layer_analyzer_key,),
            min_fixture_set=shared_fixtures,
            exposed_via=(semantic_layer_analyzer_key,),
        ),
        AnalyzerDeliveryTemplate(
            key="initial-values",
            scope="workspace",
            implementation_bucket="engineering-rules",
            lsp_exposed=True,
            acceptance_tests=_ANALYZER_SUITE_ACCEPTANCE_TESTS,
            min_fixture_set=shared_fixtures,
        ),
        AnalyzerDeliveryTemplate(
            key="interface-contracts",
            scope="workspace",
            implementation_bucket="interface-mapping",
            acceptance_tests=("tests/analyzers/test_interface_contracts.py",),
            min_fixture_set=shared_fixtures,
            exposed_via=("pipeline",),
        ),
        AnalyzerDeliveryTemplate(
            key="powerup",
            scope="workspace",
            implementation_bucket="engineering-rules",
            cli_exposed=True,
            acceptance_tests=("tests/analyzers/test_powerup.py",),
            min_fixture_set=shared_fixtures,
            exposed_via=("cli", "pipeline"),
        ),
        AnalyzerDeliveryTemplate(
            key="naming-consistency",
            scope="workspace",
            implementation_bucket="engineering-rules",
            acceptance_tests=_ANALYZER_SUITE_ACCEPTANCE_TESTS,
            min_fixture_set=shared_fixtures,
            exposed_via=("pipeline",),
        ),
        AnalyzerDeliveryTemplate(
            key="cyclomatic-complexity",
            scope="single-file",
            implementation_bucket="engineering-rules",
            acceptance_tests=_ANALYZER_SUITE_ACCEPTANCE_TESTS,
            min_fixture_set=shared_fixtures,
            exposed_via=("pipeline",),
        ),
        AnalyzerDeliveryTemplate(
            key="parameter-drift",
            scope="cross-module",
            implementation_bucket="engineering-rules",
            acceptance_tests=_ANALYZER_SUITE_ACCEPTANCE_TESTS,
            min_fixture_set=shared_fixtures,
            exposed_via=("pipeline",),
        ),
        AnalyzerDeliveryTemplate(
            key="signal-lifecycle",
            scope="workspace",
            implementation_bucket="engineering-rules",
            lsp_exposed=True,
            acceptance_tests=("tests/analyzers/test_signal_lifecycle.py",),
            min_fixture_set=shared_fixtures,
            exposed_via=("cli",),
        ),
        AnalyzerDeliveryTemplate(
            key="loop-stability",
            scope="single-file",
            implementation_bucket="engineering-rules",
            lsp_exposed=True,
            acceptance_tests=("tests/analyzers/test_loop_stability.py",),
            min_fixture_set=shared_fixtures,
            exposed_via=("cli",),
        ),
        AnalyzerDeliveryTemplate(
            key="fault-handling",
            scope="workspace",
            implementation_bucket="engineering-rules",
            lsp_exposed=True,
            acceptance_tests=("tests/analyzers/test_fault_handling.py",),
            min_fixture_set=shared_fixtures,
            exposed_via=("cli",),
        ),
        AnalyzerDeliveryTemplate(
            key="numeric-constraints",
            scope="workspace",
            implementation_bucket="engineering-rules",
            lsp_exposed=True,
            acceptance_tests=("tests/analyzers/test_numeric_constraints.py",),
            min_fixture_set=shared_fixtures,
            exposed_via=("cli",),
        ),
        AnalyzerDeliveryTemplate(
            key="data-dependency",
            scope="workspace",
            implementation_bucket="shared-semantic-core",
            acceptance_tests=("tests/analyzers/test_data_dependency.py",),
            min_fixture_set=shared_fixtures,
            exposed_via=("cli",),
        ),
        AnalyzerDeliveryTemplate(
            key="config-drift",
            scope="cross-module",
            implementation_bucket="engineering-rules",
            lsp_exposed=True,
            acceptance_tests=("tests/analyzers/test_config_drift.py",),
            min_fixture_set=shared_fixtures,
            exposed_via=("cli",),
        ),
        AnalyzerDeliveryTemplate(
            key="scan-loop-resource-usage",
            scope="single-file",
            implementation_bucket="engineering-rules",
            acceptance_tests=_ANALYZER_SUITE_ACCEPTANCE_TESTS,
            min_fixture_set=shared_fixtures,
            exposed_via=("pipeline",),
        ),
        AnalyzerDeliveryTemplate(
            key="resource-usage",
            scope="workspace",
            implementation_bucket="shared-semantic-core",
            acceptance_tests=("tests/analyzers/test_resource_usage.py",),
            min_fixture_set=shared_fixtures,
            exposed_via=("cli",),
        ),
        AnalyzerDeliveryTemplate(
            key="scan-concurrency",
            scope="single-file",
            implementation_bucket="shared-semantic-core",
            acceptance_tests=("tests/analyzers/test_scan_concurrency.py",),
            min_fixture_set=shared_fixtures,
            exposed_via=("pipeline",),
        ),
        AnalyzerDeliveryTemplate(
            key="timing",
            scope="single-file",
            implementation_bucket="shared-semantic-core",
            cli_exposed=True,
            acceptance_tests=("tests/analyzers/test_timing.py",),
            min_fixture_set=shared_fixtures,
            exposed_via=("cli", "pipeline"),
        ),
        AnalyzerDeliveryTemplate(
            key="version-drift",
            scope="workspace",
            implementation_bucket="engineering-rules",
            acceptance_tests=(
                *_ANALYZER_SUITE_ACCEPTANCE_TESTS,
                "tests/test_docgen_part1.py",
            ),
            min_fixture_set=shared_fixtures,
            exposed_via=("docgen",),
        ),
        AnalyzerDeliveryTemplate(
            key="safety-paths",
            scope="cross-module",
            implementation_bucket="shared-semantic-core",
            lsp_exposed=True,
            acceptance_tests=(
                *_ANALYZER_SUITE_ACCEPTANCE_TESTS,
                "tests/analyzers/test_sattline_semantics.py",
                "tests/test_editor_api.py",
            ),
            depends_on_analyzers=(semantic_layer_analyzer_key,),
            min_fixture_set=shared_fixtures,
            exposed_via=(semantic_layer_analyzer_key, "editor-api"),
        ),
        AnalyzerDeliveryTemplate(
            key="taint-paths",
            scope="cross-module",
            implementation_bucket="graph-tracing",
            lsp_exposed=True,
            acceptance_tests=(
                *_ANALYZER_SUITE_ACCEPTANCE_TESTS,
                "tests/test_editor_api.py",
            ),
            min_fixture_set=shared_fixtures,
            exposed_via=(semantic_layer_analyzer_key, "editor-api"),
        ),
        AnalyzerDeliveryTemplate(
            key="unsafe-defaults",
            scope="single-file",
            implementation_bucket="shared-semantic-core",
            lsp_exposed=True,
            acceptance_tests=(
                "tests/test_pipeline_phase2.py",
                "tests/analyzers/test_sattline_semantics.py",
            ),
            depends_on_analyzers=(semantic_layer_analyzer_key,),
            min_fixture_set=shared_fixtures,
            exposed_via=(semantic_layer_analyzer_key,),
        ),
        AnalyzerDeliveryTemplate(
            key="dataflow",
            scope="workspace",
            implementation_bucket="shared-semantic-core",
            lsp_exposed=True,
            acceptance_tests=(
                "tests/analyzers/test_dataflow.py",
                *_ANALYZER_SUITE_ACCEPTANCE_TESTS,
                "tests/analyzers/test_sattline_semantics.py",
            ),
            depends_on_analyzers=(semantic_layer_analyzer_key,),
            min_fixture_set=shared_fixtures,
            exposed_via=(semantic_layer_analyzer_key,),
        ),
        AnalyzerDeliveryTemplate(
            key="state-inference",
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
    )


__all__ = ["AnalyzerDeliveryTemplate", "default_delivery_templates"]
