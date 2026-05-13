# ruff: noqa: F403, F405
from ._analyzers_variables_test_support import *


def test_layout_overlap_detects_overlapping_graph_and_interact_objects():
    bp = BasePicture(
        header=_hdr("BasePicture"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[],
        submodules=[],
        modulecode=None,
        moduledef=ModuleDef(
            graph_objects=[
                GraphObject(
                    type="TextObject",
                    properties={"coords": ((0.0, 0.0), (1.0, 1.0))},
                )
            ],
            interact_objects=[
                InteractObject(
                    type="ComBut_",
                    properties={"coords": [((0.5, 0.5), (1.25, 1.25))]},
                )
            ],
        ),
    )

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    overlap_issues = [issue for issue in analyzer.issues if issue.kind is IssueKind.LAYOUT_OVERLAP]

    assert len(overlap_issues) == 1
    assert overlap_issues[0].role == "graph object TextObject #1 overlaps interact object ComBut_ #1"


def test_layout_overlap_ignores_objects_on_different_layers():
    bp = BasePicture(
        header=_hdr("BasePicture"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[],
        submodules=[],
        modulecode=None,
        moduledef=ModuleDef(
            graph_objects=[
                GraphObject(
                    type="TextObject",
                    properties={"coords": ((0.0, 0.0), (1.0, 1.0)), "layer": 1},
                )
            ],
            interact_objects=[
                InteractObject(
                    type="ComBut_",
                    properties={"coords": [((0.5, 0.5), (1.25, 1.25))], "layer": 2},
                )
            ],
        ),
    )

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    overlap_issues = [issue for issue in analyzer.issues if issue.kind is IssueKind.LAYOUT_OVERLAP]

    assert overlap_issues == []


def test_ui_only_variable_detected_for_graphics_invar_reads():
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    WidthSource: integer := 0;
ModuleDef
    ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
    GraphObjects :
        TextObject ( 0.0 , 0.0 ) ( 1.0 , 1.0 )
            "Value" VarName Width_ = 5 : InVar_ "WidthSource"
ENDDEF (*BasePicture*);
"""

    bp = parser_core_parse_source_text(code)
    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    issues = [issue for issue in analyzer.issues if issue.kind is IssueKind.UI_ONLY]

    assert len(issues) == 1
    assert issues[0].variable is not None
    assert issues[0].variable.name == "WidthSource"
    assert not any(issue.kind is IssueKind.READ_ONLY_NON_CONST for issue in analyzer.issues)


def test_ui_only_variable_detected_for_interact_invar_reads():
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    ButtonTypeSource: integer := 0;
ModuleDef
    ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
    InteractObjects :
        ComBut_ ( 0.0 , 0.0 ) ( 1.0 , 1.0 )
            ButtonType = 0 : InVar_ "ButtonTypeSource"
ENDDEF (*BasePicture*);
"""

    bp = parser_core_parse_source_text(code)
    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    issues = [issue for issue in analyzer.issues if issue.kind is IssueKind.UI_ONLY]

    assert len(issues) == 1
    assert issues[0].variable is not None
    assert issues[0].variable.name == "ButtonTypeSource"


def test_ui_only_variable_detected_for_procedure_interact_windowcontent_invar_reads():
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    PArea01Path: integer := 0;
ModuleDef
    ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
    InteractObjects :
        ProcedureInteract ( -0.86 , 0.33 ) ( -0.55 , 0.6 )
            WindowContent
            "" : InVar_ "PArea01Path" 0
            Variable = 0.0
ENDDEF (*BasePicture*);
"""

    bp = parser_core_parse_source_text(code)
    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    issues = [issue for issue in analyzer.issues if issue.kind is IssueKind.UI_ONLY]

    assert len(issues) == 1
    assert issues[0].variable is not None
    assert issues[0].variable.name == "PArea01Path"


def test_ui_only_variable_is_suppressed_by_non_ui_control_usage():
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    WidthSource: integer := 0;
    Output: integer := 0;
ModuleDef
    ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
    GraphObjects :
        TextObject ( 0.0 , 0.0 ) ( 1.0 , 1.0 )
            "Value" VarName Width_ = 5 : InVar_ "WidthSource"
    ModuleCode
        EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
            Output = WidthSource;
ENDDEF (*BasePicture*);
"""

    bp = parser_core_parse_source_text(code)
    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    assert not any(
        issue.kind is IssueKind.UI_ONLY and issue.variable is not None and issue.variable.name == "WidthSource"
        for issue in analyzer.issues
    )


def test_graphics_format_tail_keywords_do_not_log_missing_variables(caplog):
    bp = BasePicture(
        header=_hdr("BasePicture"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[Variable(name="RealSource", datatype=Simple_DataType.INTEGER)],
        submodules=[],
        modulecode=None,
        moduledef=None,
    )
    analyzer = VariablesAnalyzer(bp, debug=True)
    context = ScopeContext(
        env={"realsource": bp.localvariables[0]},
        param_mappings={},
        module_path=[bp.header.name],
        display_module_path=[bp.header.name],
    )

    with caplog.at_level(logging.DEBUG, logger="SattLint"):
        for token in ("Real_Value", "Relative_", "Decimal_", "Int_Value", "Abs_"):
            analyzer._walk_tail(token, context, [bp.header.name])
        analyzer._walk_tail("RealSource", context, [bp.header.name])
        analyzer._walk_tail("MissingVar", context, [bp.header.name])

    messages = [record.message for record in caplog.records]

    assert not any("real_value" in message.lower() for message in messages)
    assert not any("relative_" in message.lower() for message in messages)
    assert not any("decimal_" in message.lower() for message in messages)
    assert not any("int_value" in message.lower() for message in messages)
    assert not any("abs_" in message.lower() for message in messages)
    assert any("missingvar" in message.lower() for message in messages)
    assert analyzer._get_usage(bp.localvariables[0]).read is True


def test_variables_fallback_warnings_are_not_logged_without_debug(caplog):
    bp = BasePicture(
        header=_hdr("BasePicture"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[],
        submodules=[],
        modulecode=None,
        moduledef=None,
    )
    analyzer = VariablesAnalyzer(bp, debug=False, fail_loudly=False)

    with caplog.at_level(logging.WARNING, logger="SattLint"):
        analyzer._warn("test fallback warning")

    assert analyzer.analysis_warnings == ["test fallback warning"]
    assert not caplog.records


def test_interact_litstring_invar_tail_does_not_crash_variable_analysis():
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    WidthSource: integer := 0;
ModuleDef
    ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
    InteractObjects :
        ComBut_ ( 0.0 , 0.0 ) ( 1.0 , 1.0 )
            Abs_ TextObject = "" : InVar_ LitString "Start Sim"
ENDDEF (*BasePicture*);
"""

    bp = parser_core_parse_source_text(code)
    width_source = bp.localvariables[0]

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    assert analyzer._get_usage(width_source).read is False


def test_shadowing_ignores_external_moduletype_instance_locals_for_program_target():
    mt = ModuleTypeDef(
        name="TypeA",
        moduleparameters=[],
        localvariables=[Variable(name="Setting", datatype=Simple_DataType.INTEGER)],
        submodules=[],
        moduledef=None,
        modulecode=None,
        parametermappings=[],
        origin_file="TypeA.x",
        origin_lib="SomeLib",
    )

    instance = ModuleTypeInstance(
        header=_hdr("InstanceA"),
        moduletype_name="TypeA",
        parametermappings=[],
    )

    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[mt],
        localvariables=[Variable(name="setting", datatype=Simple_DataType.INTEGER)],
        submodules=[instance],
        modulecode=None,
        moduledef=None,
        origin_file="Root.x",
        origin_lib="ProgramLib",
    )

    report = analyze_shadowing(bp)

    assert not any(i.kind is IssueKind.SHADOWING for i in report.issues)


def test_variable_analysis_ignores_external_moduletype_usage_for_program_target():
    library_mt = ModuleTypeDef(
        name="LibType",
        moduleparameters=[Variable(name="Input", datatype=Simple_DataType.INTEGER)],
        localvariables=[],
        submodules=[],
        moduledef=None,
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="E1",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[_varref("Input")],
                )
            ]
        ),
        parametermappings=[],
        origin_file="LibType.x",
        origin_lib="SomeLib",
    )

    instance = ModuleTypeInstance(
        header=_hdr("LibInst"),
        moduletype_name="LibType",
        parametermappings=[
            ParameterMapping(
                target=_varref("Input"),
                source_type=const.TREE_TAG_VARIABLE_NAME,
                is_duration=False,
                is_source_global=False,
                source=_varref("ProgramVar"),
                source_literal=None,
            )
        ],
    )

    program_var = Variable(name="ProgramVar", datatype=Simple_DataType.INTEGER)
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[library_mt],
        localvariables=[program_var],
        submodules=[instance],
        modulecode=None,
        moduledef=None,
        origin_file="Root.x",
        origin_lib="ProgramLib",
    )

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    assert any(issue.kind is IssueKind.UNUSED and issue.variable is program_var for issue in analyzer.issues)


def test_variable_analysis_treats_external_moduletype_usage_as_used_for_library_target():
    library_mt = ModuleTypeDef(
        name="LibType",
        moduleparameters=[Variable(name="Input", datatype=Simple_DataType.INTEGER)],
        localvariables=[],
        submodules=[],
        moduledef=None,
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="E1",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[_varref("Input")],
                )
            ]
        ),
        parametermappings=[],
        origin_file="LibType.x",
        origin_lib="SomeLib",
    )

    instance = ModuleTypeInstance(
        header=_hdr("LibInst"),
        moduletype_name="LibType",
        parametermappings=[
            ParameterMapping(
                target=_varref("Input"),
                source_type=const.TREE_TAG_VARIABLE_NAME,
                is_duration=False,
                is_source_global=False,
                source=_varref("LibraryVar"),
                source_literal=None,
            )
        ],
    )

    library_var = Variable(name="LibraryVar", datatype=Simple_DataType.INTEGER)
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[library_mt],
        localvariables=[library_var],
        submodules=[instance],
        modulecode=None,
        moduledef=None,
        origin_file="Root.x",
        origin_lib="ProjectLib",
    )

    analyzer = VariablesAnalyzer(bp, analyzed_target_is_library=True)
    analyzer.run()

    assert not any(issue.variable is library_var for issue in analyzer.issues)


def test_library_typedef_dependency_output_is_treated_as_effectful_for_library_target():
    dependency_mt = ModuleTypeDef(
        name="MES_JournalData",
        moduleparameters=[
            Variable(name="Name", datatype=Simple_DataType.STRING),
            Variable(name="ValueAck", datatype=Simple_DataType.BOOLEAN),
        ],
        localvariables=[],
        submodules=[],
        moduledef=None,
        modulecode=ModuleCode(equations=[], sequences=[]),
        parametermappings=[],
        origin_file="MES_JournalData.s",
        origin_lib="MESLib",
    )
    root_typedef = ModuleTypeDef(
        name="WorkerType",
        moduleparameters=[Variable(name="Name", datatype=Simple_DataType.STRING)],
        localvariables=[Variable(name="ValueAckOnce", datatype=Simple_DataType.BOOLEAN)],
        submodules=[
            ModuleTypeInstance(
                header=_hdr("Journal"),
                moduletype_name="MES_JournalData",
                parametermappings=[
                    ParameterMapping(
                        target=_varref("Name"),
                        source_type=const.TREE_TAG_VARIABLE_NAME,
                        is_duration=False,
                        is_source_global=False,
                        source=_varref("Name"),
                        source_literal=None,
                    ),
                    ParameterMapping(
                        target=_varref("ValueAck"),
                        source_type=const.TREE_TAG_VARIABLE_NAME,
                        is_duration=False,
                        is_source_global=False,
                        source=_varref("ValueAckOnce"),
                        source_literal=None,
                    ),
                ],
            )
        ],
        moduledef=None,
        modulecode=ModuleCode(equations=[], sequences=[]),
        parametermappings=[],
        origin_file="Root.s",
        origin_lib="ProjectLib",
    )

    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[root_typedef, dependency_mt],
        localvariables=[],
        submodules=[],
        modulecode=None,
        moduledef=None,
        origin_file="Root.s",
        origin_lib="ProjectLib",
    )

    analyzer = VariablesAnalyzer(bp, analyzed_target_is_library=True)
    analyzer.run()

    assert not any(
        issue.kind is IssueKind.WRITE_WITHOUT_EFFECT
        and issue.variable is not None
        and issue.variable.name == "ValueAckOnce"
        for issue in analyzer.issues
    )
