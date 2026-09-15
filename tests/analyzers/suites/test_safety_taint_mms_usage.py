from sattline_parser.models.expressions import Assignment

from tests.helpers.analyzers_suites_support import *


def test_opt_in_analyzer_is_not_in_default_cli_keys():
    from sattlint.analyzers.registry import get_actual_cli_analyzer_keys  # noqa: PLC0415

    assert "version-drift" not in get_actual_cli_analyzer_keys()


def test_mms_tag_helpers_normalize_external_tags():
    assert _normalize_external_tag("  Unit.Area.Tag42  ") == "unit.area.tag42"
    assert _normalize_external_tag("12345") is None


def test_mms_mapping_helpers_match_casefold_names():
    mapping = ParameterMapping(
        target=_varref("LocalVariable"),
        source_type=const.TREE_TAG_VARIABLE_NAME,
        is_duration=False,
        is_source_global=False,
        source=_varref("OutTag"),
        source_literal=None,
    )
    variables = [Variable(name="RemoteVarName", datatype=Simple_DataType.TAGSTRING, init_value="TagA")]

    found_mapping = _find_parameter_mapping([mapping], "localvariable")
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

    report = report_datatype_usage(bp, "MissingValue")

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
                                Assignment(target=_varref("Sink"), value=_varref("Dv.Source")),
                                Assignment(target=_varref("Dv.Target"), value=IntLiteral(1)),
                                Assignment(target=_varref("Mirror"), value=_varref("Dv")),
                                Assignment(target=_varref("Dv"), value=_varref("Mirror")),
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

    datatype_report = report_datatype_usage(bp, "Dv")
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
