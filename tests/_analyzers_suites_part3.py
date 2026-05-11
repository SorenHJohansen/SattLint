# ruff: noqa: F403, F405
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


def test_registry_rule_corpus_cache_and_default_runner_closures_cover_remaining_paths(tmp_path, monkeypatch):
    missing_manifest_dir = tmp_path / "missing-manifests"
    monkeypatch.setattr(registry_module, "DEFAULT_CORPUS_MANIFEST_DIR", missing_manifest_dir)
    registry_module._rule_corpus_cases_by_rule_id.cache_clear()
    assert registry_module._rule_corpus_cases_by_rule_id() == {}

    manifest_dir = tmp_path / "manifests"
    manifest_dir.mkdir()
    (manifest_dir / "skip.json").mkdir()
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
    monkeypatch.setattr(registry_module, "analyze_naming_consistency", _record("naming-consistency"))
    monkeypatch.setattr(registry_module, "analyze_cyclomatic_complexity", _record("cyclomatic-complexity"))
    monkeypatch.setattr(registry_module, "analyze_parameter_drift", _record("parameter-drift"))
    monkeypatch.setattr(registry_module, "analyze_scan_loop_resource_usage", _record("scan-loop-resource-usage"))
    monkeypatch.setattr(registry_module, "analyze_version_drift", _record("version-drift"))
    monkeypatch.setattr(registry_module, "analyze_safety_paths", _record("safety-paths"))
    monkeypatch.setattr(registry_module, "analyze_taint_paths", _record("taint-paths"))
    monkeypatch.setattr(registry_module, "analyze_unsafe_defaults", _record("unsafe-defaults"))
    monkeypatch.setattr(registry_module, "analyze_dataflow", _record("dataflow"))
    monkeypatch.setattr(registry_module, "analyze_state_inference", _record("state_inference"))
    monkeypatch.setattr(registry_module, "analyze_comment_code", _record("comment-code"))
    monkeypatch.setattr(registry_module, "get_configured_mutually_exclusive_step_sets", lambda config: ("mutex",))
    monkeypatch.setattr(registry_module, "get_configured_step_contracts", lambda config: ("contracts",))
    monkeypatch.setattr(registry_module, "get_configured_naming_rules", lambda config: ("rules",))

    specs = {spec.key: spec for spec in registry_module.get_default_analyzers()}
    context: Any = SimpleNamespace(
        base_picture="bp",
        debug=True,
        unavailable_libraries={"MissingLib"},
        target_is_library=True,
        config={"profile": "test"},
    )
    expected_keys = {
        registry_module.SEMANTIC_LAYER_ANALYZER_KEY,
        "variables",
        "mms-interface",
        "sfc",
        "shadowing",
        "spec-compliance",
        "loop-output-refactor",
        "alarm-integrity",
        "initial-values",
        "naming-consistency",
        "cyclomatic-complexity",
        "parameter-drift",
        "scan-loop-resource-usage",
        "version-drift",
        "safety-paths",
        "taint-paths",
        "unsafe-defaults",
        "dataflow",
        "state_inference",
        "comment-code",
    }

    for key in expected_keys:
        assert specs[key].run(context) == key

    assert set(calls) == expected_keys
    registry_module._rule_corpus_cases_by_rule_id.cache_clear()


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
