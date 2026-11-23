from collections.abc import Callable
from types import SimpleNamespace
from typing import (
    Any,
    cast,
)

import pytest

from sattlint.analyzers import registry as registry_module
from sattlint.analyzers.framework import AnalysisContext, AnalyzerSpec, Report
from sattlint.config.string_capacities import STANDARD_STRING_CAPACITIES


def test_registry_catalog_report_and_key_helpers_cover_metadata_branches():
    catalog = registry_module.get_default_analyzer_catalog()

    report = cast(dict[str, Any], catalog.to_report(generated_by="test-suite"))

    assert catalog.enabled_specs()
    assert report["generated_by"] == "test-suite"
    assert {entry["key"] for entry in report["analyzers"]} == set(registry_module.get_selectable_analyzer_keys())
    # Selection is per run, so the catalogue publishes no default or CLI flag.
    assert "cli_exposed" not in report["analyzers"][0]


def test_removed_analyzers_are_neither_selectable_nor_catalogued():
    keys = set(registry_module.get_selectable_analyzer_keys())
    catalogued = {analyzer.spec.key for analyzer in registry_module.get_default_analyzer_catalog().analyzers}

    assert "spec-compliance" not in keys
    assert "version-drift" not in keys
    assert "spec-compliance" not in catalogued
    assert "version-drift" not in catalogued


def test_build_delivery_metadata_falls_back_for_unknown_analyzer_key():
    spec = AnalyzerSpec(
        key="custom-analyzer",
        name="Custom analyzer",
        description="Synthetic analyzer for fallback coverage.",
        run=lambda context: cast(Report, "custom-analyzer"),
    )

    delivery = registry_module.build_delivery_metadata(spec)

    assert delivery.delivery_scope == "workspace"
    assert delivery.implementation_bucket == "analyzers"
    assert delivery.output_artifacts == ("custom-analyzer.summary",)


def test_default_runner_closures_cover_remaining_paths(monkeypatch: pytest.MonkeyPatch):
    calls: list[str] = []

    def _record(name: str) -> Callable[..., str]:
        def _runner(*_args: object, **_kwargs: object) -> str:
            calls.append(name)
            return name

        return _runner

    monkeypatch.setattr(registry_module, "analyze_variables", _record("variables"))
    monkeypatch.setattr(registry_module, "analyze_sfc", _record("sfc"))
    monkeypatch.setattr(registry_module, "analyze_alarm_integrity", _record("alarm-integrity"))
    monkeypatch.setattr(registry_module, "analyze_cyclomatic_complexity", _record("cyclomatic-complexity"))
    monkeypatch.setattr(registry_module, "analyze_picture_display_paths", _record("picture-display-paths"))
    monkeypatch.setattr(registry_module, "analyze_same_cycle", _record("same-cycle"))
    monkeypatch.setattr(registry_module, "analyze_dataflow", _record("dataflow"))
    monkeypatch.setattr(registry_module, "analyze_datatype_fields", _record("datatype-fields"))
    monkeypatch.setattr(registry_module, "analyze_moduletype_usage", _record("moduletype-usage"))
    monkeypatch.setattr(registry_module, "analyze_icf_configuration", _record("icf"))
    monkeypatch.setattr(registry_module, "analyze_comment_code", _record("comment-code"))

    specs = {spec.key: spec for spec in registry_module.get_default_analyzers()}
    context = cast(
        AnalysisContext,
        SimpleNamespace(
            base_picture="bp",
            graph=None,
            debug=True,
            unavailable_libraries={"MissingLib"},
            target_is_library=True,
            config={"profile": "test"},
            string_capacities=STANDARD_STRING_CAPACITIES,
            include_dependency_moduletype_usage=None,
            program_ast_loader=None,
        ),
    )
    expected_keys = {
        "variables",
        "picture-display-paths",
        "sfc",
        "alarm-integrity",
        "cyclomatic-complexity",
        "same-cycle",
        "dataflow",
        "comment-code",
        "datatype-fields",
        "moduletype-usage",
        "icf",
    }

    for key in expected_keys:
        assert specs[key].run(context) == key

    assert set(calls) == expected_keys


def test_run_registry_analyzer_falls_back_to_spec_runner_without_registry_attr():
    from sattlint.analyzers._registry_dispatch import run_registry_analyzer  # noqa: PLC0415

    report = SimpleNamespace(issues=[])
    seen: dict[str, object] = {}

    def _run(context: AnalysisContext) -> Report:
        seen["context"] = context
        return cast(Report, report)

    context = cast(AnalysisContext, SimpleNamespace(base_picture="bp", shared_artifacts=None))
    spec = SimpleNamespace(key="custom-analyzer", run=_run)

    assert run_registry_analyzer(spec, context) is report
    assert seen["context"] is context


def test_run_registry_analyzer_passes_shared_artifacts_to_dataflow():
    from sattlint.analyzers._registry_dispatch import run_registry_analyzer  # noqa: PLC0415
    from sattlint.analyzers.framework import AnalyzerSpec  # noqa: PLC0415

    report = SimpleNamespace(issues=[])
    seen: dict[str, object] = {}
    shared_artifacts = object()

    def _run(context: AnalysisContext) -> Report:
        seen["context"] = context
        return cast(Report, report)

    spec = AnalyzerSpec(
        key="dataflow",
        name="Dataflow",
        description="",
        run=_run,
    )
    context = cast(
        AnalysisContext,
        SimpleNamespace(
            base_picture="bp",
            graph=None,
            debug=False,
            target_is_library=True,
            config={"profile": "test"},
            shared_artifacts=shared_artifacts,
            unavailable_libraries={"MissingLib"},
            include_dependency_moduletype_usage=None,
        ),
    )

    assert run_registry_analyzer(spec, context) is report
    assert seen["context"] is context
