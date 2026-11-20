"""Declarative delivery metadata templates for the analyzer registry."""

from __future__ import annotations

from dataclasses import dataclass

_ANALYZER_SUITE_ACCEPTANCE_TESTS = (
    "tests/analyzers/suites/test_dataflow_sfc_transition_versiondrift.py",
    "tests/analyzers/suites/test_module_diff_sfc_guard.py",
    "tests/analyzers/suites/test_naming_alarm_integrity.py",
    "tests/analyzers/suites/test_safety_taint_mms_usage.py",
    "tests/analyzers/suites/test_sfc_dataflow_variables.py",
    "tests/analyzers/suites/test_registry_catalog.py",
)
_APP_ACCEPTANCE_TESTS = ("tests/app/test_cli.py",)


@dataclass(frozen=True)
class AnalyzerDeliveryTemplate:
    key: str
    delivery_scope: str
    implementation_bucket: str
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
            delivery_scope="workspace",
            implementation_bucket="variables-reporting",
            acceptance_tests=(
                *_ANALYZER_SUITE_ACCEPTANCE_TESTS,
                *_APP_ACCEPTANCE_TESTS,
            ),
            supports_incremental=True,
            min_fixture_set=shared_fixtures,
        ),
        AnalyzerDeliveryTemplate(
            key="datatype-fields",
            delivery_scope="workspace",
            implementation_bucket="variables-reporting",
            acceptance_tests=(
                *_ANALYZER_SUITE_ACCEPTANCE_TESTS,
                "tests/analyzers/test_datatype_fields_analyzer.py",
            ),
            min_fixture_set=shared_fixtures,
        ),
        AnalyzerDeliveryTemplate(
            key="moduletype-usage",
            delivery_scope="workspace",
            implementation_bucket="engineering-rules",
            acceptance_tests=(
                "tests/analyzers/test_moduletype_usage.py",
                "tests/app/test_analysis_project_cache.py",
            ),
            min_fixture_set=shared_fixtures,
        ),
        AnalyzerDeliveryTemplate(
            key="picture-display-paths",
            delivery_scope="workspace",
            implementation_bucket="workspace-navigation",
            acceptance_tests=("tests/analyzers/test_picture_display_paths.py", *_APP_ACCEPTANCE_TESTS),
            min_fixture_set=shared_fixtures,
        ),
        AnalyzerDeliveryTemplate(
            key="icf",
            delivery_scope="workspace",
            implementation_bucket="icf-validation",
            acceptance_tests=("tests/analyzers/test_icf_analyzer.py", *_APP_ACCEPTANCE_TESTS),
        ),
        AnalyzerDeliveryTemplate(
            key="sfc",
            delivery_scope="single-file",
            implementation_bucket="shared-semantic-core",
            acceptance_tests=(
                "tests/analyzers/test_sfc.py",
                *_ANALYZER_SUITE_ACCEPTANCE_TESTS,
            ),
            min_fixture_set=shared_fixtures,
        ),
        AnalyzerDeliveryTemplate(
            key="comment-code",
            delivery_scope="single-file",
            implementation_bucket="comment-scan",
            acceptance_tests=("tests/analyzers/test_comment_code.py", *_APP_ACCEPTANCE_TESTS),
        ),
        AnalyzerDeliveryTemplate(
            key="alarm-integrity",
            delivery_scope="cross-module",
            implementation_bucket="shared-semantic-core",
            acceptance_tests=(*_ANALYZER_SUITE_ACCEPTANCE_TESTS,),
            min_fixture_set=shared_fixtures,
        ),
        AnalyzerDeliveryTemplate(
            key="cyclomatic-complexity",
            delivery_scope="single-file",
            implementation_bucket="engineering-rules",
            acceptance_tests=_ANALYZER_SUITE_ACCEPTANCE_TESTS,
            min_fixture_set=shared_fixtures,
        ),
        AnalyzerDeliveryTemplate(
            key="same-cycle",
            delivery_scope="cross-module",
            implementation_bucket="shared-semantic-core",
            acceptance_tests=("tests/analyzers/test_same_cycle.py",),
            min_fixture_set=shared_fixtures,
        ),
        AnalyzerDeliveryTemplate(
            key="dataflow",
            delivery_scope="workspace",
            implementation_bucket="shared-semantic-core",
            acceptance_tests=(
                *_ANALYZER_SUITE_ACCEPTANCE_TESTS,
                "tests/analyzers/test_dataflow_conflicting_constants.py",
            ),
            min_fixture_set=shared_fixtures,
        ),
    )


__all__ = ["AnalyzerDeliveryTemplate", "default_delivery_templates"]
