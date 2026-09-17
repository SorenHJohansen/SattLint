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
    acceptance_tests: tuple[str, ...] = ()
    depends_on_artifacts: tuple[str, ...] = ()
    supports_baselines: bool = True
    supports_incremental: bool = False
    min_fixture_set: tuple[str, ...] = ()


def default_delivery_templates(
    shared_fixtures: tuple[str, ...],
) -> tuple[AnalyzerDeliveryTemplate, ...]:
    return (
        AnalyzerDeliveryTemplate(
            key="variables",
            scope="workspace",
            implementation_bucket="variables-reporting",
            cli_exposed=True,
            acceptance_tests=(
                *_ANALYZER_SUITE_ACCEPTANCE_TESTS,
                *_APP_ACCEPTANCE_TESTS,
            ),
            supports_incremental=True,
            min_fixture_set=shared_fixtures,
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
            acceptance_tests=(
                "tests/analyzers/test_sfc.py",
                *_ANALYZER_SUITE_ACCEPTANCE_TESTS,
            ),
            min_fixture_set=shared_fixtures,
        ),
        AnalyzerDeliveryTemplate(
            key="comment-code",
            scope="single-file",
            implementation_bucket="comment-scan",
            cli_exposed=True,
            acceptance_tests=("tests/analyzers/test_comment_code.py", *_APP_ACCEPTANCE_TESTS),
        ),
        AnalyzerDeliveryTemplate(
            key="spec-compliance",
            scope="workspace",
            implementation_bucket="engineering-rules",
            cli_exposed=True,
            acceptance_tests=("tests/analyzers/test_spec_compliance.py", *_APP_ACCEPTANCE_TESTS),
            min_fixture_set=shared_fixtures,
        ),
        AnalyzerDeliveryTemplate(
            key="alarm-integrity",
            scope="cross-module",
            implementation_bucket="shared-semantic-core",
            acceptance_tests=(*_ANALYZER_SUITE_ACCEPTANCE_TESTS,),
            min_fixture_set=shared_fixtures,
        ),
        AnalyzerDeliveryTemplate(
            key="cyclomatic-complexity",
            scope="single-file",
            implementation_bucket="engineering-rules",
            acceptance_tests=_ANALYZER_SUITE_ACCEPTANCE_TESTS,
            min_fixture_set=shared_fixtures,
        ),
        AnalyzerDeliveryTemplate(
            key="same-cycle",
            scope="cross-module",
            implementation_bucket="shared-semantic-core",
            acceptance_tests=("tests/analyzers/test_same_cycle.py",),
            min_fixture_set=shared_fixtures,
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
        ),
        AnalyzerDeliveryTemplate(
            key="dataflow",
            scope="workspace",
            implementation_bucket="shared-semantic-core",
            acceptance_tests=(
                *_ANALYZER_SUITE_ACCEPTANCE_TESTS,
                "tests/analyzers/test_dataflow_conflicting_constants.py",
            ),
            min_fixture_set=shared_fixtures,
        ),
    )


__all__ = ["AnalyzerDeliveryTemplate", "default_delivery_templates"]
