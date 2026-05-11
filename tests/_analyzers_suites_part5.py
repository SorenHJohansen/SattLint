# ruff: noqa: F403, F405
from ._analyzers_suites_test_support import *


def test_safety_paths_trace_emergency_signal_across_moduletype_mapping():
    guard_type = ModuleTypeDef(
        name="GuardType",
        moduleparameters=[
            Variable(name="InSignal", datatype=Simple_DataType.BOOLEAN),
        ],
        localvariables=[
            Variable(name="Seen", datatype=Simple_DataType.BOOLEAN, init_value=False),
        ],
        submodules=[],
        moduledef=None,
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="GuardEq",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (
                            const.KEY_ASSIGN,
                            _varref("Seen"),
                            _varref("InSignal"),
                        )
                    ],
                )
            ]
        ),
        parametermappings=[],
        origin_file="Root.s",
    )
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[
            Variable(name="EmergencyShutdown", datatype=Simple_DataType.BOOLEAN, init_value=False),
        ],
        moduletype_defs=[guard_type],
        submodules=[
            ModuleTypeInstance(
                header=_hdr("Guard"),
                moduletype_name="GuardType",
                parametermappings=[
                    ParameterMapping(
                        target=_varref("InSignal"),
                        source_type=const.TREE_TAG_VARIABLE_NAME,
                        is_duration=False,
                        is_source_global=False,
                        source=_varref("EmergencyShutdown"),
                        source_literal=None,
                    )
                ],
            )
        ],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Main",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (
                            const.KEY_ASSIGN,
                            _varref("EmergencyShutdown"),
                            True,
                        )
                    ],
                )
            ]
        ),
        origin_file="Root.s",
    )

    report = analyze_safety_paths(bp)

    assert report.issues == []
    assert len(report.traces) == 1
    assert report.traces[0].canonical_path == "Root.EmergencyShutdown"
    assert report.traces[0].writer_module_paths == (("Root",),)
    assert report.traces[0].reader_module_paths == (("Root", "Guard"),)
    assert report.traces[0].spans_multiple_modules is True


def test_safety_paths_reports_unconsumed_shutdown_signal():
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[
            Variable(name="EmergencyShutdown", datatype=Simple_DataType.BOOLEAN, init_value=False),
        ],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Main",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (
                            const.KEY_ASSIGN,
                            _varref("EmergencyShutdown"),
                            True,
                        )
                    ],
                )
            ]
        ),
    )

    report = analyze_safety_paths(bp)

    assert len(report.traces) == 1
    assert len(report.issues) == 1
    assert report.issues[0].kind == "safety-path.unconsumed_signal"
    assert report.issues[0].data is not None
    assert report.issues[0].data["canonical_path"] == "Root.EmergencyShutdown"


def test_taint_paths_trace_operator_input_to_shutdown_sink_across_moduletype_mapping():
    guard_type = ModuleTypeDef(
        name="GuardType",
        moduleparameters=[
            Variable(name="InCommand", datatype=Simple_DataType.BOOLEAN),
        ],
        localvariables=[
            Variable(name="EmergencyShutdown", datatype=Simple_DataType.BOOLEAN, init_value=False),
        ],
        submodules=[],
        moduledef=None,
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="GuardEq",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (
                            const.KEY_ASSIGN,
                            _varref("EmergencyShutdown"),
                            _varref("InCommand"),
                        )
                    ],
                )
            ]
        ),
        parametermappings=[],
        origin_file="Root.s",
    )
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[
            Variable(name="OperatorCommand", datatype=Simple_DataType.BOOLEAN, init_value=False),
        ],
        moduletype_defs=[guard_type],
        submodules=[
            ModuleTypeInstance(
                header=_hdr("Guard"),
                moduletype_name="GuardType",
                parametermappings=[
                    ParameterMapping(
                        target=_varref("InCommand"),
                        source_type=const.TREE_TAG_VARIABLE_NAME,
                        is_duration=False,
                        is_source_global=False,
                        source=_varref("OperatorCommand"),
                        source_literal=None,
                    )
                ],
            )
        ],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Main",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (
                            const.KEY_ASSIGN,
                            _varref("OperatorCommand"),
                            True,
                        )
                    ],
                )
            ]
        ),
        origin_file="Root.s",
    )

    report = analyze_taint_paths(bp)

    assert len(report.traces) == 1
    assert len(report.issues) == 1
    assert report.traces[0].source_kind == "operator"
    assert report.traces[0].source_canonical_path == "Root.OperatorCommand"
    assert report.traces[0].sink_canonical_path == "Root.Guard.EmergencyShutdown"
    assert report.traces[0].path == (
        "Root.OperatorCommand",
        "Root.Guard.InCommand",
        "Root.Guard.EmergencyShutdown",
    )
    assert report.traces[0].spans_multiple_modules is True
    assert report.issues[0].kind == "taint-path.external_input_to_critical_sink"
    assert report.issues[0].data is not None
    assert report.issues[0].data["source_kind"] == "operator"


def test_safety_paths_analyzer_is_enabled_by_default():
    specs = {spec.key: spec for spec in get_default_analyzers()}

    assert "safety-paths" in specs
    assert specs["safety-paths"].enabled is True


def test_taint_paths_analyzer_is_enabled_by_default():
    specs = {spec.key: spec for spec in get_default_analyzers()}

    assert "taint-paths" in specs
    assert specs["taint-paths"].enabled is True


def test_state_inference_analyzer_is_not_in_default_cli_subset():
    from sattlint.analyzers.registry import get_actual_cli_analyzer_keys

    assert "state_inference" not in get_actual_cli_analyzer_keys()


def test_mms_tag_helpers_normalize_external_tags_and_family_keys():
    assert _normalize_external_tag("  Unit.Area.Tag42  ") == "unit.area.tag42"
    assert _normalize_external_tag("12345") is None
    assert _tag_family_key("Plant-AB12.PV") == "plant|ab|12|pv"
    assert _tag_family_key("   ") is None


def test_mms_mapping_helpers_match_casefold_names():
    mapping = ParameterMapping(
        target=_varref("WriteData"),
        source_type=const.TREE_TAG_VARIABLE_NAME,
        is_duration=False,
        is_source_global=False,
        source=_varref("OutTag"),
        source_literal=None,
    )
    variables = [Variable(name="RemoteVarName", datatype=Simple_DataType.TAGSTRING, init_value="TagA")]

    found_mapping = _find_parameter_mapping([mapping], "writedata")
    found_variable = _find_variable(variables, "remotevarname")

    assert found_mapping is mapping
    assert found_variable is variables[0]


def test_mms_extract_external_tag_uses_literal_parameter_mapping_value():
    instance = ModuleTypeInstance(
        header=_hdr("MmsWrite"),
        moduletype_name="MMSWriteVar",
        parametermappings=[
            ParameterMapping(
                target=_varref("Tag"),
                source_type=const.KEY_VALUE,
                is_duration=False,
                is_source_global=False,
                source_literal="Plant.Unit.Tag01",
            )
        ],
    )
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[],
        submodules=[instance],
        modulecode=None,
        moduledef=None,
    )

    tag = _extract_external_tag(bp, ["Root", "MmsWrite"], instance, None)

    assert tag == "Plant.Unit.Tag01"


def test_variable_usage_datatype_report_returns_not_found_message():
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[],
        submodules=[],
        modulecode=None,
        moduledef=None,
    )

    report = analyze_datatype_usage(bp, "MissingValue")

    assert report == "Variable 'MissingValue' not found."


def test_variable_usage_reports_include_field_and_whole_variable_accesses():
    record_type = DataType(
        name="UsageRecord",
        description=None,
        datecode=None,
        var_list=[
            Variable(name="Source", datatype=Simple_DataType.INTEGER),
            Variable(name="Target", datatype=Simple_DataType.INTEGER),
        ],
    )
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[record_type],
        moduletype_defs=[],
        localvariables=[],
        submodules=[
            SingleModule(
                header=_hdr("Unit"),
                moduledef=None,
                moduleparameters=[],
                localvariables=[
                    Variable(name="Dv", datatype="UsageRecord"),
                    Variable(name="Mirror", datatype="UsageRecord"),
                    Variable(name="Sink", datatype=Simple_DataType.INTEGER),
                ],
                submodules=[],
                modulecode=ModuleCode(
                    equations=[
                        Equation(
                            name="Usage",
                            position=(0.0, 0.0),
                            size=(1.0, 1.0),
                            code=[
                                (const.KEY_ASSIGN, _varref("Sink"), _varref("Dv.Source")),
                                (const.KEY_ASSIGN, _varref("Dv.Target"), IntLiteral(1)),
                                (const.KEY_ASSIGN, _varref("Mirror"), _varref("Dv")),
                                (const.KEY_ASSIGN, _varref("Dv"), _varref("Mirror")),
                            ],
                        )
                    ]
                ),
                parametermappings=[],
            )
        ],
        modulecode=None,
        moduledef=None,
    )

    datatype_report = analyze_datatype_usage(bp, "Dv")
    debug_report = debug_variable_usage(bp, "Dv")

    assert "Field usage analysis for variable 'Dv':" in datatype_report
    assert "Fields accessed: 2" in datatype_report
    assert "source: read (r:1, w:0)" in datatype_report.lower()
    assert "target: write (r:0, w:1)" in datatype_report.lower()
    assert "Usage report for variable name 'Dv' (1 declaration(s)):" in debug_report
    assert "Field reads:" in debug_report
    assert "dv.source" in debug_report.lower()
    assert "Field writes:" in debug_report
    assert "dv.target" in debug_report.lower()
    assert "Whole variable:" in debug_report
    assert "R:1 W:1 | Root -> Unit" in debug_report
