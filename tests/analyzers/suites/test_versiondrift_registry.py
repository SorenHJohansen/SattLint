# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportPrivateUsage=false, reportArgumentType=false, reportIndexIssue=false, reportAttributeAccessIssue=false
from types import SimpleNamespace
from typing import (
    Any,
    cast,
)

from sattlint.analyzers import registry as registry_module
from sattlint.analyzers.framework import AnalyzerSpec


def test_registry_catalog_report_and_key_helpers_cover_metadata_branches():
    catalog = registry_module.get_default_analyzer_catalog()

    report = cast(dict[str, Any], catalog.to_report(generated_by="test-suite"))

    assert catalog.enabled_specs()
    assert report["generated_by"] == "test-suite"
    assert report["analyzers"]
    declared = {item.spec.key for item in catalog.analyzers if item.delivery.cli_exposed}
    configured = set(registry_module.DEFAULT_CLI_ANALYZER_KEYS)
    actual = set(registry_module.get_actual_cli_analyzer_keys())
    assert declared == configured == actual


def test_build_delivery_metadata_falls_back_for_unknown_analyzer_key():
    spec = AnalyzerSpec(
        key="custom-analyzer",
        name="Custom analyzer",
        description="Synthetic analyzer for fallback coverage.",
        run=lambda context: cast(Any, "custom-analyzer"),
    )

    delivery = registry_module.build_delivery_metadata(spec)

    assert delivery.delivery_scope == "workspace"
    assert delivery.implementation_bucket == "analyzers"
    assert delivery.output_artifacts == ("custom-analyzer.summary",)


def test_default_runner_closures_cover_remaining_paths(monkeypatch):
    calls: list[str] = []

    def _record(name: str):
        def _runner(*args, **kwargs):
            calls.append(name)
            return name

        return _runner

    monkeypatch.setattr(registry_module, "analyze_variables", _record("variables"))
    monkeypatch.setattr(registry_module, "analyze_sfc", _record("sfc"))
    monkeypatch.setattr(registry_module, "analyze_spec_compliance", _record("spec-compliance"))
    monkeypatch.setattr(registry_module, "analyze_alarm_integrity", _record("alarm-integrity"))
    monkeypatch.setattr(registry_module, "analyze_cyclomatic_complexity", _record("cyclomatic-complexity"))
    monkeypatch.setattr(registry_module, "analyze_picture_display_paths", _record("picture-display-paths"))
    monkeypatch.setattr(registry_module, "analyze_same_cycle", _record("same-cycle"))
    monkeypatch.setattr(registry_module, "analyze_version_drift", _record("version-drift"))
    monkeypatch.setattr(registry_module, "analyze_dataflow", _record("dataflow"))
    monkeypatch.setattr(registry_module, "analyze_comment_code", _record("comment-code"))

    specs = {spec.key: spec for spec in registry_module.get_default_analyzers()}
    context: Any = SimpleNamespace(
        base_picture="bp",
        graph=None,
        debug=True,
        unavailable_libraries={"MissingLib"},
        target_is_library=True,
        config={"profile": "test"},
        include_dependency_moduletype_usage=None,
    )
    expected_keys = {
        "variables",
        "picture-display-paths",
        "sfc",
        "spec-compliance",
        "alarm-integrity",
        "cyclomatic-complexity",
        "same-cycle",
        "version-drift",
        "dataflow",
        "comment-code",
    }

    for key in expected_keys:
        assert specs[key].run(context) == key

    assert set(calls) == expected_keys


def test_run_registry_analyzer_falls_back_to_spec_runner_without_registry_attr():
    from sattlint.analyzers._registry_dispatch import run_registry_analyzer  # noqa: PLC0415

    report = SimpleNamespace(issues=[])
    seen: dict[str, object] = {}

    def _run(context: object) -> object:
        seen["context"] = context
        return report

    context = SimpleNamespace(base_picture="bp", shared_artifacts=None)
    spec = SimpleNamespace(key="custom-analyzer", run=_run)

    assert run_registry_analyzer(spec, context) is report
    assert seen["context"] is context


def test_run_registry_analyzer_passes_shared_artifacts_to_dataflow():
    from sattlint.analyzers._registry_dispatch import run_registry_analyzer  # noqa: PLC0415
    from sattlint.analyzers.framework import AnalyzerSpec  # noqa: PLC0415

    report = SimpleNamespace(issues=[])
    seen: dict[str, object] = {}
    shared_artifacts = object()

    def _run(context: object) -> object:
        seen["context"] = context
        return report

    spec = AnalyzerSpec(
        key="dataflow",
        name="Dataflow",
        description="",
        run=_run,
    )
    context: Any = SimpleNamespace(
        base_picture="bp",
        graph=None,
        debug=False,
        target_is_library=True,
        config={"profile": "test"},
        shared_artifacts=shared_artifacts,
        unavailable_libraries={"MissingLib"},
        include_dependency_moduletype_usage=None,
    )

    assert run_registry_analyzer(spec, context) is report
    assert seen["context"] is context
