# ruff: noqa: F403, F405
from ._analyzers_variables_test_support import *


def test_required_parameter_name_helper_caches_only_runtime_used_parameters():
    typedef = ModuleTypeDef(
        name="ChildType",
        moduleparameters=[
            Variable(name="RequiredValue", datatype=Simple_DataType.INTEGER),
            Variable(name="UnusedValue", datatype=Simple_DataType.INTEGER),
        ],
        localvariables=[Variable(name="Mirror", datatype=Simple_DataType.INTEGER)],
        submodules=[],
        moduledef=None,
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="UseParam",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[(const.KEY_ASSIGN, _varref("Mirror"), _varref("RequiredValue"))],
                )
            ]
        ),
        parametermappings=[],
    )
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[typedef],
        localvariables=[],
        submodules=[],
        modulecode=None,
        moduledef=None,
    )

    analyzer = VariablesAnalyzer(bp)

    first = analyzer._get_required_parameter_names_for_typedef(typedef)
    second = analyzer._get_required_parameter_names_for_typedef(typedef)

    assert first == {"requiredvalue": "RequiredValue"}
    assert second == first
    assert analyzer._required_parameter_names_by_owner[id(typedef)] == first


def test_required_parameter_name_helper_handles_cyclic_typedef_instances():
    type_a = ModuleTypeDef(
        name="TypeA",
        moduleparameters=[Variable(name="AParam", datatype=Simple_DataType.INTEGER)],
        localvariables=[Variable(name="AMirror", datatype=Simple_DataType.INTEGER)],
        submodules=[
            ModuleTypeInstance(
                header=_hdr("UseB"),
                moduletype_name="TypeB",
                parametermappings=[
                    ParameterMapping(
                        target=_varref("BParam"),
                        source_type=const.KEY_VALUE,
                        is_duration=False,
                        is_source_global=False,
                        source=_varref("AParam"),
                        source_literal=None,
                    )
                ],
            )
        ],
        moduledef=None,
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="ReadAParam",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[(const.KEY_ASSIGN, _varref("AMirror"), _varref("AParam"))],
                )
            ]
        ),
        parametermappings=[],
    )
    type_b = ModuleTypeDef(
        name="TypeB",
        moduleparameters=[Variable(name="BParam", datatype=Simple_DataType.INTEGER)],
        localvariables=[Variable(name="BMirror", datatype=Simple_DataType.INTEGER)],
        submodules=[
            ModuleTypeInstance(
                header=_hdr("UseA"),
                moduletype_name="TypeA",
                parametermappings=[
                    ParameterMapping(
                        target=_varref("AParam"),
                        source_type=const.KEY_VALUE,
                        is_duration=False,
                        is_source_global=False,
                        source=_varref("BParam"),
                        source_literal=None,
                    )
                ],
            )
        ],
        moduledef=None,
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="ReadBParam",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[(const.KEY_ASSIGN, _varref("BMirror"), _varref("BParam"))],
                )
            ]
        ),
        parametermappings=[],
    )
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[type_a, type_b],
        localvariables=[],
        submodules=[],
        modulecode=None,
        moduledef=None,
    )

    analyzer = VariablesAnalyzer(bp)

    required_a = analyzer._get_required_parameter_names_for_typedef(type_a)
    required_b = analyzer._get_required_parameter_names_for_typedef(type_b)

    assert required_a == {"aparam": "AParam"}
    assert required_b == {"bparam": "BParam"}
    assert analyzer._required_parameter_names_by_owner[id(type_a)] == required_a
    assert analyzer._required_parameter_names_by_owner[id(type_b)] == required_b


def test_anytype_contracts_collect_read_and_write_field_paths():
    typedef = ModuleTypeDef(
        name="ChildType",
        moduleparameters=[Variable(name="Payload", datatype="AnyType")],
        localvariables=[
            Variable(name="Mirror", datatype=Simple_DataType.INTEGER),
            Variable(name="Source", datatype=Simple_DataType.INTEGER),
        ],
        submodules=[],
        moduledef=None,
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="UsePayload",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (const.KEY_ASSIGN, _varref("Mirror"), _varref("Payload.FieldA")),
                        (const.KEY_ASSIGN, _varref("Payload.FieldB"), _varref("Source")),
                    ],
                )
            ]
        ),
        parametermappings=[],
    )
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[typedef],
        localvariables=[],
        submodules=[],
        modulecode=None,
        moduledef=None,
    )

    analyzer = VariablesAnalyzer(bp)

    contracts = analyzer._anytype_field_contracts_by_owner[id(typedef)]

    assert contracts["payload"].field_paths == ("FieldA", "FieldB")


def test_magic_number_detection_in_equations_and_sfc():
    eq = Equation(
        name="Main",
        position=(0.0, 0.0),
        size=(1.0, 1.0),
        code=[
            (
                const.KEY_ASSIGN,
                _varref("Output"),
                IntLiteral(42, SourceSpan(12, 5)),
            ),
            (
                const.KEY_ASSIGN,
                _varref("Output"),
                IntLiteral(0, SourceSpan(13, 5)),
            ),
            (
                const.KEY_ASSIGN,
                _varref("Output"),
                (const.KEY_MINUS, IntLiteral(0, SourceSpan(14, 5))),
            ),
        ],
    )

    transition = SFCTransition(
        name="ToNext",
        condition=(
            const.KEY_COMPARE,
            _varref("Output"),
            [
                (">", FloatLiteral(2.5, SourceSpan(20, 7))),
                ("<", FloatLiteral(0.0, SourceSpan(21, 9))),
            ],
        ),
    )

    seq = Sequence(
        name="SeqMain",
        type="sequence",
        position=(0.0, 0.0),
        size=(1.0, 1.0),
        code=[transition],
    )

    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[Variable(name="Output", datatype=Simple_DataType.INTEGER)],
        modulecode=ModuleCode(sequences=[seq], equations=[eq]),
        moduledef=None,
    )

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    magic = [i for i in analyzer.issues if i.kind is IssueKind.MAGIC_NUMBER]
    assert len(magic) == 2

    values = sorted(i.literal_value for i in magic if i.literal_value is not None)
    assert values == [2.5, 42]

    spans = {(i.literal_span.line, i.literal_span.column) for i in magic if i.literal_span is not None}
    assert (12, 5) in spans
    assert (20, 7) in spans
    assert (13, 5) not in spans
    assert (14, 5) not in spans
    assert (21, 9) not in spans


def test_shadowing_detected_for_nested_locals():
    child = SingleModule(
        header=_hdr("Child"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[Variable(name="value", datatype=Simple_DataType.INTEGER)],
        submodules=[],
        modulecode=None,
        parametermappings=[],
    )

    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[Variable(name="Value", datatype=Simple_DataType.INTEGER)],
        submodules=[child],
        modulecode=None,
        moduledef=None,
    )

    report = analyze_shadowing(bp)

    assert any(i.kind is IssueKind.SHADOWING for i in report.issues)


def test_shadowing_detected_for_moduletype_instance_locals():
    mt = ModuleTypeDef(
        name="TypeA",
        moduleparameters=[],
        localvariables=[Variable(name="Setting", datatype=Simple_DataType.INTEGER)],
        submodules=[],
        moduledef=None,
        modulecode=None,
        parametermappings=[],
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
    )

    report = analyze_shadowing(bp)

    assert any(i.kind is IssueKind.SHADOWING for i in report.issues)


def test_variable_analysis_marks_invar_reads_across_graphics_and_interact_paths():
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0 : InVar_ "PosX",0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    PosX: integer := 0;
    PanelResize: integer := 0;
    WidthSource: integer := 0;
    FormatSource: integer := 0;
    ColourSource: integer := 0;
    ButtonTypeSource: integer := 0;
ModuleDef
    ClippingBounds = ( -1.0 , -1.0 : InVar_ "PanelResize" ) ( 1.0 , 1.0 )
    GraphObjects :
        TextObject ( 0.0 , 0.0 ) ( 1.0 , 1.0 )
            "Value" VarName Width_ = 5 : InVar_ "WidthSource"
            Format_String_ = "" : InVar_ "FormatSource"
            OutlineColour : Colour0 = 5 : InVar_ "ColourSource"
    InteractObjects :
        ComBut_ ( 0.0 , 0.0 ) ( 1.0 , 1.0 )
            ButtonType = 0 : InVar_ "ButtonTypeSource"
ENDDEF (*BasePicture*);
"""

    bp = parser_core_parse_source_text(code)
    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    usage_by_name = {variable.name: analyzer._get_usage(variable) for variable in bp.localvariables}

    assert usage_by_name["PosX"].read is True
    assert usage_by_name["PanelResize"].read is True
    assert usage_by_name["WidthSource"].read is True
    assert usage_by_name["FormatSource"].read is True
    assert usage_by_name["ColourSource"].read is True
    assert usage_by_name["ButtonTypeSource"].read is True
    assert usage_by_name["WidthSource"].ui_read is True
    assert usage_by_name["ButtonTypeSource"].ui_read is True


def test_layout_overlap_detects_overlapping_module_invocations():
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
TYPEDEFINITIONS
    ChildType = MODULEDEFINITION DateCode_ 1
    ModuleDef
        ClippingBounds = ( 0.0 , 0.0 ) ( 1.0 , 1.0 )
    ENDDEF (*ChildType*);
SUBMODULES
    ChildA Invocation ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0 ) : ChildType;
    ChildB Invocation ( 0.5 , 0.5 , 0.0 , 1.0 , 1.0 ) : ChildType;
ModuleDef
    ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ENDDEF (*BasePicture*);
"""

    bp = parser_core_parse_source_text(code)
    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    overlap_issues = [issue for issue in analyzer.issues if issue.kind is IssueKind.LAYOUT_OVERLAP]

    assert len(overlap_issues) == 1
    assert overlap_issues[0].role == "module 'ChildA' overlaps module 'ChildB'"


def test_layout_overlap_ignores_modules_on_different_layers():
    child_moduledef = ModuleDef(clipping_bounds=((-1.0, -1.0), (1.0, 1.0)))
    bp = BasePicture(
        header=_hdr("BasePicture"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[],
        submodules=[
            SingleModule(
                header=ModuleHeader(
                    name="Layer1",
                    invoke_coord=(0.0, 0.0, 0.0, 0.1, 0.1),
                    layer_info="1",
                ),
                moduledef=child_moduledef,
                moduleparameters=[],
                localvariables=[],
                submodules=[],
                modulecode=None,
                parametermappings=[],
            ),
            SingleModule(
                header=ModuleHeader(
                    name="Layer2",
                    invoke_coord=(0.02, 0.02, 0.0, 0.1, 0.1),
                    layer_info="2",
                ),
                moduledef=child_moduledef,
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

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    overlap_issues = [issue for issue in analyzer.issues if issue.kind is IssueKind.LAYOUT_OVERLAP]

    assert overlap_issues == []


def test_layout_overlap_uses_module_clipping_bounds_for_visible_overlap():
    child_moduledef = ModuleDef(clipping_bounds=((-1.0, -1.0), (1.0, 1.0)))
    bp = BasePicture(
        header=_hdr("BasePicture"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[],
        submodules=[
            SingleModule(
                header=ModuleHeader(name="ChildA", invoke_coord=(0.0, 0.0, 0.0, 0.1, 0.1)),
                moduledef=child_moduledef,
                moduleparameters=[],
                localvariables=[],
                submodules=[],
                modulecode=None,
                parametermappings=[],
            ),
            SingleModule(
                header=ModuleHeader(name="ChildB", invoke_coord=(0.1, 0.1, 0.0, 0.1, 0.1)),
                moduledef=child_moduledef,
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

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    overlap_issues = [issue for issue in analyzer.issues if issue.kind is IssueKind.LAYOUT_OVERLAP]

    assert len(overlap_issues) == 1
    assert overlap_issues[0].role == "module 'ChildA' overlaps module 'ChildB'"
