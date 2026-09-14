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
_APP_ACCEPTANCE_TESTS = ("tests/test_app_cli_commands.py",)


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
            acceptance_tests=("tests/analyzers/test_sattline_semantics.py",),
            min_fixture_set=shared_fixtures,
        ),
        AnalyzerDeliveryTemplate(
            key="symbolic_lite",
            scope="cross-module",
            implementation_bucket="shared-semantic-core",
            acceptance_tests=("tests/analyzers/test_sattline_semantics.py",),
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
            key="datatype-fields",
            scope="workspace",
            implementation_bucket="variables-reporting",
            acceptance_tests=(
                *_ANALYZER_SUITE_ACCEPTANCE_TESTS,
                "tests/analyzers/test_datatype_fields_analyzer.py",
            ),
            min_fixture_set=shared_fixtures,
            exposed_via=(semantic_layer_analyzer_key, "pipeline"),
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
            key="icf",
            scope="workspace",
            implementation_bucket="icf-validation",
            cli_exposed=True,
            acceptance_tests=("tests/analyzers/test_icf_analyzer.py", *_APP_ACCEPTANCE_TESTS),
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
            cli_exposed=True,
            acceptance_tests=_ANALYZER_SUITE_ACCEPTANCE_TESTS,
            min_fixture_set=shared_fixtures,
            exposed_via=("cli",),
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
            key="same-cycle",
            scope="cross-module",
            implementation_bucket="shared-semantic-core",
            lsp_exposed=True,
            acceptance_tests=(
                "tests/analyzers/test_same_cycle.py",
                "tests/analyzers/test_sattline_semantics.py",
            ),
            depends_on_analyzers=(semantic_layer_analyzer_key,),
            min_fixture_set=shared_fixtures,
            exposed_via=(semantic_layer_analyzer_key,),
        ),
        AnalyzerDeliveryTemplate(
            key="version-drift",
            scope="workspace",
            implementation_bucket="engineering-rules",
            acceptance_tests=(
                *_ANALYZER_SUITE_ACCEPTANCE_TESTS,
                "tests/test_analyzers_version_drift.py",
            ),
            min_fixture_set=shared_fixtures,
            exposed_via=("pipeline",),
        ),
        AnalyzerDeliveryTemplate(
            key="unsafe-defaults",
            scope="single-file",
            implementation_bucket="shared-semantic-core",
            lsp_exposed=True,
            acceptance_tests=("tests/analyzers/test_sattline_semantics.py",),
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
                *_ANALYZER_SUITE_ACCEPTANCE_TESTS,
                "tests/analyzers/test_sattline_semantics.py",
            ),
            depends_on_analyzers=(semantic_layer_analyzer_key,),
            min_fixture_set=shared_fixtures,
            exposed_via=(semantic_layer_analyzer_key,),
        ),
    )


__all__ = ["AnalyzerDeliveryTemplate", "default_delivery_templates"]
