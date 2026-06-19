# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportPrivateUsage=false, reportArgumentType=false, reportIndexIssue=false, reportAttributeAccessIssue=false
# ruff: noqa: F403, F405
import pytest

from ._analyzers_suites_test_support import *


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


def test_initial_value_validation_flags_recipe_parameter_without_value_default():
    recipe_parameter = ModuleTypeDef(
        name="RecParReal",
        moduleparameters=[
            Variable(name="Value", datatype=Simple_DataType.REAL),
            Variable(name="MinValue", datatype=Simple_DataType.REAL, init_value=0.0),
            Variable(name="MaxValue", datatype=Simple_DataType.REAL, init_value=100.0),
        ],
        localvariables=[],
        submodules=[],
        moduledef=None,
        modulecode=None,
        parametermappings=[],
        origin_file="Root.s",
    )
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[recipe_parameter],
        localvariables=[],
        submodules=[
            ModuleTypeInstance(
                header=_hdr("RecipeSP"),
                moduletype_name="RecParReal",
                parametermappings=[],
            )
        ],
        modulecode=None,
        moduledef=None,
        origin_file="Root.s",
    )

    report = analyze_initial_values(bp)

    issues = [issue for issue in report.issues if issue.kind == "initial-values.missing_required_default"]
    assert len(issues) == 1
    assert issues[0].module_path == ["Root", "RecipeSP"]
    assert issues[0].data == {
        "parameter_category": "recipe",
        "instance": "RecipeSP",
        "moduletype": "RecParReal",
        "moduletype_label": "RecParReal",
        "required_parameters": ["Value"],
        "parameter_statuses": {"Value": "not_configured"},
    }


def test_initial_value_validation_accepts_engineering_parameter_mapped_from_initialized_variable():
    engineering_parameter = ModuleTypeDef(
        name="EngParReal",
        moduleparameters=[
            Variable(name="Value", datatype=Simple_DataType.REAL),
            Variable(name="MinValue", datatype=Simple_DataType.REAL, init_value=0.0),
            Variable(name="MaxValue", datatype=Simple_DataType.REAL, init_value=100.0),
        ],
        localvariables=[],
        submodules=[],
        moduledef=None,
        modulecode=None,
        parametermappings=[],
        origin_file="Root.s",
    )
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[engineering_parameter],
        localvariables=[Variable(name="ConfiguredLimit", datatype=Simple_DataType.REAL, init_value=42.5)],
        submodules=[
            ModuleTypeInstance(
                header=_hdr("EngineeringLimit"),
                moduletype_name="EngParReal",
                parametermappings=[
                    ParameterMapping(
                        target=_varref("Value"),
                        source_type=const.TREE_TAG_VARIABLE_NAME,
                        is_duration=False,
                        is_source_global=False,
                        source=_varref("ConfiguredLimit"),
                        source_literal=None,
                    ),
                    ParameterMapping(
                        target=_varref("MinValue"),
                        source_type=const.KEY_VALUE,
                        is_duration=False,
                        is_source_global=False,
                        source_literal=0.0,
                    ),
                    ParameterMapping(
                        target=_varref("MaxValue"),
                        source_type=const.KEY_VALUE,
                        is_duration=False,
                        is_source_global=False,
                        source_literal=100.0,
                    ),
                ],
            )
        ],
        modulecode=None,
        moduledef=None,
        origin_file="Root.s",
    )

    report = analyze_initial_values(bp)

    assert report.issues == []


def test_initial_value_validation_analyzer_is_enabled_by_default():
    specs = {spec.key: spec for spec in get_default_analyzers()}

    assert "initial-values" in specs
    assert specs["initial-values"].enabled is True


def test_registry_catalog_report_and_key_helpers_cover_metadata_branches():
    catalog = registry_module.get_default_analyzer_catalog()

    report = cast(dict[str, Any], catalog.to_report(generated_by="test-suite"))

    assert catalog.enabled_specs()
    assert report["generated_by"] == "test-suite"
    assert report["analyzers"]
    assert report["rules"]
    assert report["semantic_layer"]["analyzer_key"] == registry_module.SEMANTIC_LAYER_ANALYZER_KEY
    assert registry_module.get_declared_cli_analyzer_keys() == tuple(
        sorted(analyzer.spec.key for analyzer in catalog.analyzers if analyzer.delivery.cli_exposed)
    )
    assert registry_module.get_actual_cli_analyzer_keys() == tuple(
        spec.key for spec in registry_module.get_default_cli_analyzers()
    )
    assert registry_module.get_declared_lsp_analyzer_keys() == tuple(
        sorted(analyzer.spec.key for analyzer in catalog.analyzers if analyzer.delivery.lsp_exposed)
    )
    assert registry_module.get_actual_lsp_analyzer_keys()


def test_build_delivery_metadata_falls_back_for_unknown_analyzer_key():
    spec = AnalyzerSpec(
        key="custom-analyzer",
        name="Custom analyzer",
        description="Synthetic analyzer for fallback coverage.",
        run=lambda context: cast(Any, "custom-analyzer"),
    )

    delivery = registry_module._build_delivery_metadata(spec, ())

    assert delivery.scope == "workspace"
    assert delivery.implementation_bucket == "analyzers"
    assert delivery.output_artifacts == ("custom-analyzer.summary",)


def test_registry_rule_corpus_cache_and_default_runner_closures_cover_remaining_paths(tmp_path, monkeypatch):  # noqa: PLR0915
    missing_manifest_dir = tmp_path / "missing-manifests"
    monkeypatch.setattr(registry_module, "DEFAULT_CORPUS_MANIFEST_DIR", missing_manifest_dir)
    registry_module._rule_corpus_cases_by_rule_id.cache_clear()
    assert registry_module._rule_corpus_cases_by_rule_id() == {}

    manifest_dir = tmp_path / "manifests"
    manifest_dir.mkdir()
    (manifest_dir / "skip.json").mkdir()
    (manifest_dir / "broken.json").write_text("{not-json", encoding="utf-8")
    (manifest_dir / "invalid-expected-finding-ids.json").write_text(
        json.dumps({"expectation": {"expected_finding_ids": "rule-B"}}),
        encoding="utf-8",
    )
    (manifest_dir / "case-a.json").write_text(
        json.dumps({"expectation": {"expected_finding_ids": ["rule-A"]}}),
        encoding="utf-8",
    )

    monkeypatch.setattr(registry_module, "DEFAULT_CORPUS_MANIFEST_DIR", manifest_dir)
    registry_module._rule_corpus_cases_by_rule_id.cache_clear()
    assert registry_module._rule_corpus_cases_by_rule_id() == {"rule-A": ("case-a",)}

    calls: list[str] = []

    def _record(name: str):
        def _runner(*args, **kwargs):
            calls.append(name)
            return name

        return _runner

    monkeypatch.setattr(registry_module, "analyze_variables", _record("variables"))
    monkeypatch.setattr(registry_module, "analyze_sattline_semantics", _record("sattline-semantics"))
    monkeypatch.setattr(registry_module, "analyze_mms_interface_variables", _record("mms-interface"))
    monkeypatch.setattr(registry_module, "analyze_sfc", _record("sfc"))
    monkeypatch.setattr(registry_module, "analyze_shadowing", _record("shadowing"))
    monkeypatch.setattr(registry_module, "analyze_spec_compliance", _record("spec-compliance"))
    monkeypatch.setattr(registry_module, "analyze_loop_output_refactor", _record("loop-output-refactor"))
    monkeypatch.setattr(registry_module, "analyze_alarm_integrity", _record("alarm-integrity"))
    monkeypatch.setattr(registry_module, "analyze_initial_values", _record("initial-values"))
    monkeypatch.setattr(registry_module, "analyze_interface_contracts", _record("interface-contracts"))
    monkeypatch.setattr(registry_module, "analyze_naming_consistency", _record("naming-consistency"))
    monkeypatch.setattr(registry_module, "analyze_cyclomatic_complexity", _record("cyclomatic-complexity"))
    monkeypatch.setattr(registry_module, "analyze_parameter_drift", _record("parameter-drift"))
    monkeypatch.setattr(registry_module, "analyze_picture_display_paths", _record("picture-display-paths"))
    monkeypatch.setattr(registry_module, "analyze_signal_lifecycle", _record("signal-lifecycle"))
    monkeypatch.setattr(registry_module, "analyze_loop_stability", _record("loop-stability"))
    monkeypatch.setattr(registry_module, "analyze_fault_handling", _record("fault-handling"))
    monkeypatch.setattr(registry_module, "analyze_numeric_constraints", _record("numeric-constraints"))
    monkeypatch.setattr(registry_module, "analyze_data_dependency", _record("data-dependency"))
    monkeypatch.setattr(registry_module, "analyze_config_drift", _record("config-drift"))
    monkeypatch.setattr(registry_module, "analyze_powerup", _record("powerup"))
    monkeypatch.setattr(registry_module, "analyze_scan_concurrency", _record("scan-concurrency"))
    monkeypatch.setattr(registry_module, "analyze_same_cycle", _record("same-cycle"))
    monkeypatch.setattr(registry_module, "analyze_scan_loop_resource_usage", _record("scan-loop-resource-usage"))
    monkeypatch.setattr(registry_module, "analyze_resource_usage", _record("resource-usage"))
    monkeypatch.setattr(registry_module, "analyze_version_drift", _record("version-drift"))
    monkeypatch.setattr(registry_module, "analyze_safety_paths", _record("safety-paths"))
    monkeypatch.setattr(registry_module, "analyze_taint_paths", _record("taint-paths"))
    monkeypatch.setattr(registry_module, "analyze_timing", _record("timing"))
    monkeypatch.setattr(registry_module, "analyze_unsafe_defaults", _record("unsafe-defaults"))
    monkeypatch.setattr(registry_module, "analyze_dataflow", _record("dataflow"))
    monkeypatch.setattr(registry_module, "analyze_state_inference", _record("state-inference"))
    monkeypatch.setattr(registry_module, "analyze_comment_code", _record("comment-code"))
    monkeypatch.setattr(registry_module, "get_configured_mutually_exclusive_step_sets", lambda config: ("mutex",))
    monkeypatch.setattr(registry_module, "get_configured_step_contracts", lambda config: ("contracts",))
    monkeypatch.setattr(registry_module, "get_configured_naming_rules", lambda config: ("rules",))

    specs = {spec.key: spec for spec in registry_module.get_default_analyzers()}
    context: Any = SimpleNamespace(
        base_picture="bp",
        graph=None,
        debug=True,
        unavailable_libraries={"MissingLib"},
        target_is_library=True,
        config={"profile": "test"},
    )
    expected_keys = {
        registry_module.SEMANTIC_LAYER_ANALYZER_KEY,
        "variables",
        "picture-display-paths",
        "mms-interface",
        "sfc",
        "shadowing",
        "spec-compliance",
        "loop-output-refactor",
        "alarm-integrity",
        "initial-values",
        "interface-contracts",
        "naming-consistency",
        "cyclomatic-complexity",
        "parameter-drift",
        "signal-lifecycle",
        "loop-stability",
        "fault-handling",
        "numeric-constraints",
        "data-dependency",
        "config-drift",
        "powerup",
        "scan-concurrency",
        "same-cycle",
        "scan-loop-resource-usage",
        "resource-usage",
        "timing",
        "version-drift",
        "safety-paths",
        "taint-paths",
        "unsafe-defaults",
        "dataflow",
        "state-inference",
        "comment-code",
    }

    for key in expected_keys:
        assert specs[key].run(context) == key

    assert set(calls) == expected_keys
    registry_module._rule_corpus_cases_by_rule_id.cache_clear()


def test_run_registry_analyzer_falls_back_to_spec_runner_without_registry_attr():
    from sattlint.analyzers.registry._registry_dispatch import run_registry_analyzer  # noqa: PLC0415

    report = SimpleNamespace(issues=[])
    seen: dict[str, object] = {}

    def _run(context: object) -> object:
        seen["context"] = context
        return report

    context = SimpleNamespace(base_picture="bp", shared_artifacts=None)
    spec = SimpleNamespace(key="custom-analyzer", run=_run)

    assert run_registry_analyzer(spec, context) is report
    assert seen["context"] is context


def test_run_registry_analyzer_passes_include_dependency_usage_override(monkeypatch):
    from sattlint.analyzers.registry._registry_dispatch import (  # noqa: PLC0415
        get_registry_analyzer_spec,
        run_registry_analyzer,
    )

    report = SimpleNamespace(issues=[])
    seen: dict[str, object] = {}

    monkeypatch.setattr(
        registry_module,
        "analyze_variables",
        lambda *args, **kwargs: seen.update({"args": args, "kwargs": kwargs}) or report,
    )

    spec = get_registry_analyzer_spec("variables")
    context: Any = SimpleNamespace(
        base_picture="bp",
        graph=None,
        debug=True,
        target_is_library=False,
        selected_issue_kinds=None,
        config={"profile": "test"},
        shared_artifacts=None,
        unavailable_libraries={"MissingLib"},
    )

    assert (
        run_registry_analyzer(
            spec,
            context,
            overrides={"include_dependency_moduletype_usage": True},
        )
        is report
    )
    assert seen["args"] == ("bp",)
    assert seen["kwargs"] == {
        "analysis_context": context,
        "debug": True,
        "unavailable_libraries": {"MissingLib"},
        "analyzed_target_is_library": False,
        "include_dependency_moduletype_usage": True,
        "selected_issue_kinds": None,
        "config": {"profile": "test"},
    }


def test_run_registry_analyzer_passes_shared_artifacts_to_dataflow(monkeypatch):
    from sattlint.analyzers.registry._registry_dispatch import (  # noqa: PLC0415
        get_registry_analyzer_spec,
        run_registry_analyzer,
    )

    report = SimpleNamespace(issues=[])
    seen: dict[str, object] = {}
    shared_artifacts = object()

    monkeypatch.setattr(
        registry_module,
        "analyze_dataflow",
        lambda *args, **kwargs: seen.update({"args": args, "kwargs": kwargs}) or report,
    )

    spec = get_registry_analyzer_spec("dataflow")
    context: Any = SimpleNamespace(
        base_picture="bp",
        graph=None,
        debug=False,
        target_is_library=True,
        config={"profile": "test"},
        shared_artifacts=shared_artifacts,
        unavailable_libraries={"MissingLib"},
    )

    assert run_registry_analyzer(spec, context) is report
    assert seen["args"] == ("bp",)
    assert seen["kwargs"] == {
        "unavailable_libraries": {"MissingLib"},
        "analyzed_target_is_library": True,
        "shared_artifacts": shared_artifacts,
    }


def test_get_cli_dispatch_analyzers_includes_required_variables_for_sfc_selection():
    from sattlint.analyzers.registry._registry_dispatch import (  # noqa: PLC0415
        get_cli_dispatch_analyzers,
        get_registry_analyzer_spec,
    )

    variables_spec = get_registry_analyzer_spec("variables")
    sfc_spec = get_registry_analyzer_spec("sfc")

    analyzers = get_cli_dispatch_analyzers(
        selected_keys=["sfc"],
        get_enabled_analyzers_fn=lambda: [sfc_spec, variables_spec],
    )

    assert [spec.key for spec in analyzers] == ["variables", "sfc"]


def test_run_registry_analyzer_requires_variable_artifacts_for_sfc():
    from sattlint.analyzers.registry._registry_dispatch import (  # noqa: PLC0415
        get_registry_analyzer_spec,
        run_registry_analyzer,
    )

    spec = get_registry_analyzer_spec("sfc")
    context: Any = SimpleNamespace(
        base_picture="bp",
        graph=None,
        debug=False,
        target_is_library=False,
        config={},
        shared_artifacts=SimpleNamespace(variable_analysis=None, reports_by_analyzer_key={}),
        unavailable_libraries=set(),
    )

    with pytest.raises(RuntimeError, match="requires analyzer results from: variables"):
        run_registry_analyzer(spec, context)


def test_analyze_sattline_semantics_uses_declared_semantic_contributors(monkeypatch):
    from sattlint.analyzers.framework import Issue  # noqa: PLC0415
    from sattlint.analyzers.sattline_semantics import analyze_sattline_semantics  # noqa: PLC0415
    from sattlint.reporting.variables_report import VariableIssue  # noqa: PLC0415

    calls: list[str] = []
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[Variable(name="UnusedVar", datatype=Simple_DataType.INTEGER)],
        submodules=[],
        modulecode=None,
        moduledef=None,
    )

    fake_catalog = SimpleNamespace(
        analyzers=(
            SimpleNamespace(
                spec=AnalyzerSpec(
                    key="variables",
                    name="Variables",
                    description="",
                    run=lambda _context: SimpleNamespace(issues=[]),
                    analyzer_attr="analyze_variables",
                    semantic_mapping_kind="variable",
                    semantic_rule_source="variables",
                )
            ),
            SimpleNamespace(
                spec=AnalyzerSpec(
                    key="spec-compliance",
                    name="Spec",
                    description="",
                    run=lambda _context: SimpleNamespace(issues=[]),
                    analyzer_attr="analyze_spec_compliance",
                    semantic_mapping_kind="spec",
                    semantic_rule_source="spec-compliance",
                )
            ),
            SimpleNamespace(
                spec=AnalyzerSpec(
                    key="ignored-analyzer",
                    name="Ignored",
                    description="",
                    run=lambda _context: SimpleNamespace(issues=[]),
                    analyzer_attr="analyze_alarm_integrity",
                )
            ),
        )
    )

    monkeypatch.setattr(registry_module, "get_default_analyzer_catalog", lambda: fake_catalog)
    monkeypatch.setattr(
        registry_module,
        "analyze_variables",
        lambda *_args, **_kwargs: (
            calls.append("variables")
            or SimpleNamespace(
                issues=[
                    VariableIssue(
                        kind=IssueKind.UNUSED,
                        module_path=["Root"],
                        variable=Variable(name="UnusedVar", datatype=Simple_DataType.INTEGER),
                    )
                ]
            )
        ),
    )
    monkeypatch.setattr(
        registry_module,
        "analyze_spec_compliance",
        lambda *_args, **_kwargs: (
            calls.append("spec-compliance")
            or SimpleNamespace(issues=[Issue(kind="spec.demo", message="spec issue", module_path=["Root"])])
        ),
    )
    monkeypatch.setattr(
        "sattlint.analyzers.sattline_semantics.detect_transform_invariant_violations",
        lambda _bp: [],
    )

    report = analyze_sattline_semantics(bp)

    assert calls == ["variables", "spec-compliance"]
    assert {issue.rule.source for issue in report.issues} == {"variables", "spec-compliance"}


def test_analyze_sattline_semantics_builds_context_with_config_and_shared_artifacts(monkeypatch):
    from sattlint.analyzers.sattline_semantics import analyze_sattline_semantics  # noqa: PLC0415

    seen: dict[str, object] = {}
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[],
        submodules=[],
        modulecode=None,
        moduledef=None,
    )

    monkeypatch.setattr(
        "sattlint.analyzers.sattline_semantics.get_semantic_contributor_specs",
        lambda: (SimpleNamespace(key="variables", semantic_mapping_kind="variable"),),
    )

    def _run_registry_analyzer(spec, context, **kwargs):
        seen["spec"] = spec
        seen["context"] = context
        seen["kwargs"] = kwargs
        return SimpleNamespace(issues=[])

    monkeypatch.setattr("sattlint.analyzers.sattline_semantics.run_registry_analyzer", _run_registry_analyzer)
    monkeypatch.setattr("sattlint.analyzers.sattline_semantics.detect_transform_invariant_violations", lambda _bp: [])

    report = analyze_sattline_semantics(
        bp,
        unavailable_libraries={"MissingLib"},
        analyzed_target_is_library=True,
        config={"mode": "workspace"},
    )

    assert report.issues == []
    context = seen["context"]
    assert context.config == {"mode": "workspace"}
    assert context.target_is_library is True
    assert context.shared_artifacts is not None
    assert context.unavailable_libraries == {"MissingLib"}
    assert seen["kwargs"]["use_shared_artifacts"] is True


def test_naming_consistency_flags_inconsistent_variable_names():
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[Variable(name="FlowRate", datatype=Simple_DataType.INTEGER)],
        submodules=[
            SingleModule(
                header=_hdr("MixerUnit"),
                moduledef=None,
                moduleparameters=[],
                localvariables=[Variable(name="PumpSpeed", datatype=Simple_DataType.INTEGER)],
                submodules=[],
                modulecode=None,
                parametermappings=[],
            ),
            SingleModule(
                header=_hdr("HoldingUnit"),
                moduledef=None,
                moduleparameters=[],
                localvariables=[Variable(name="tank_level", datatype=Simple_DataType.INTEGER)],
                submodules=[],
                modulecode=None,
                parametermappings=[],
            ),
        ],
        modulecode=None,
        moduledef=None,
    )

    report = analyze_naming_consistency(bp)

    issues = [
        issue
        for issue in report.issues
        if issue.kind == "naming.inconsistent_style"
        and issue.data is not None
        and issue.data.get("symbol_kind") == "variable"
    ]
    assert len(issues) == 1
    assert issues[0].module_path == ["Root", "HoldingUnit"]
    assert issues[0].data == {
        "symbol_kind": "variable",
        "name": "tank_level",
        "actual_style": "snake",
        "expected_style": "pascal",
    }


def test_naming_consistency_flags_inconsistent_module_names():
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[],
        submodules=[
            SingleModule(
                header=_hdr("MixerUnit"),
                moduledef=None,
                moduleparameters=[],
                localvariables=[],
                submodules=[],
                modulecode=None,
                parametermappings=[],
            ),
            FrameModule(
                header=_hdr("HoldingFrame"),
                submodules=[],
                moduledef=None,
                modulecode=None,
            ),
            SingleModule(
                header=_hdr("cooling_stage"),
                moduledef=None,
                moduleparameters=[],
                localvariables=[],
                submodules=[],
                modulecode=None,
                parametermappings=[],
            ),
        ],
        modulecode=None,
        moduledef=None,
    )

    report = analyze_naming_consistency(bp)

    issues = [
        issue
        for issue in report.issues
        if issue.kind == "naming.inconsistent_style"
        and issue.data is not None
        and issue.data.get("symbol_kind") == "module"
    ]
    assert len(issues) == 1
    assert issues[0].module_path == ["Root", "cooling_stage"]
    assert issues[0].data == {
        "symbol_kind": "module",
        "name": "cooling_stage",
        "actual_style": "snake",
        "expected_style": "pascal",
    }
