# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportPrivateUsage=false, reportArgumentType=false, reportIndexIssue=false, reportAttributeAccessIssue=false
from tests.helpers.analyzers_suites_support import *


def test_version_drift_ignores_datecode_only_differences():
    variant_a = SingleModule(
        header=_hdr("Mixer"),
        datecode=100,
        moduledef=None,
        moduleparameters=[],
        localvariables=[Variable(name="Output", datatype=Simple_DataType.INTEGER)],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Logic",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[(const.KEY_ASSIGN, _varref("Output"), 1)],
                )
            ],
            sequences=[],
        ),
        parametermappings=[],
    )
    variant_b = SingleModule(
        header=_hdr("Mixer"),
        datecode=200,
        moduledef=None,
        moduleparameters=[],
        localvariables=[Variable(name="Output", datatype=Simple_DataType.INTEGER)],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Logic",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[(const.KEY_ASSIGN, _varref("Output"), 1)],
                )
            ],
            sequences=[],
        ),
        parametermappings=[],
    )
    cast(Any, variant_a).origin_file = "Root.s"
    cast(Any, variant_b).origin_file = "Root.s"
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[],
        submodules=[variant_a, variant_b],
        modulecode=None,
        moduledef=None,
        origin_file="Root.s",
    )

    report = analyze_version_drift(bp)

    assert report.issues == []


def test_version_drift_analyzer_is_enabled_by_default():
    specs = {spec.key: spec for spec in get_default_analyzers()}

    assert "version-drift" in specs
    assert specs["version-drift"].enabled is True


def test_registry_catalog_report_and_key_helpers_cover_metadata_branches():
    catalog = registry_module.get_default_analyzer_catalog()

    report = cast(dict[str, Any], catalog.to_report(generated_by="test-suite"))

    assert catalog.enabled_specs()
    assert report["generated_by"] == "test-suite"
    assert report["analyzers"]
    assert registry_module.get_declared_cli_analyzer_keys() == tuple(
        sorted(analyzer.spec.key for analyzer in catalog.analyzers if analyzer.delivery.cli_exposed)
    )
    assert registry_module.get_actual_cli_analyzer_keys() == tuple(
        spec.key for spec in registry_module.get_default_cli_analyzers()
    )


def test_build_delivery_metadata_falls_back_for_unknown_analyzer_key():
    spec = AnalyzerSpec(
        key="custom-analyzer",
        name="Custom analyzer",
        description="Synthetic analyzer for fallback coverage.",
        run=lambda context: cast(Any, "custom-analyzer"),
    )

    delivery = registry_module.build_delivery_metadata(spec, ())

    assert delivery.scope == "workspace"
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
