# pyright: reportPrivateUsage=false
from sattline_parser import parse_source_text as parser_core_parse_source_text
from sattline_parser.models.ast_model import (
    Assignment,
    BasePicture,
    Equation,
    FloatLiteral,
    IntLiteral,
    ModuleCode,
    ModuleTypeDef,
    ModuleTypeInstance,
    ScalarDatatype,
    Sequence,
    SFCTransition,
    SingleModule,
    SourceSpan,
    Variable,
)
from sattline_parser.models.expressions import BoolOp, Compare, UnaryOp

from sattlint.analyzers.variables import (
    IssueKind,
    VariablesAnalyzer,
    analyze_variables,
)
from sattlint.reporting.variables_report import MagicNumberIssue
from tests.helpers.variable_test_support import (
    hdr as _hdr,
)
from tests.helpers.variable_test_support import (
    varref as _varref,
)


def test_magic_number_detection_in_equations_and_sfc():
    eq = Equation(
        name="Main",
        position=(0.0, 0.0),
        size=(1.0, 1.0),
        code=[
            Assignment(target=_varref("Output"), value=IntLiteral(42, SourceSpan(start=0, end=0, line=12, column=5))),
            Assignment(target=_varref("Output"), value=IntLiteral(0, SourceSpan(start=0, end=0, line=13, column=5))),
            Assignment(
                target=_varref("Output"),
                value=UnaryOp(op="-", operand=IntLiteral(0, SourceSpan(start=0, end=0, line=14, column=5))),
            ),
        ],
    )

    transition = SFCTransition(
        name="ToNext",
        condition=BoolOp(
            "AND",
            (
                Compare(
                    left=_varref("Output"),
                    op=">",
                    right=FloatLiteral(2.5, SourceSpan(start=0, end=0, line=20, column=7)),
                ),
                Compare(
                    left=_varref("Output"),
                    op="<",
                    right=FloatLiteral(0.0, SourceSpan(start=0, end=0, line=21, column=9)),
                ),
            ),
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
        localvariables=[Variable(name="Output", datatype=ScalarDatatype.INTEGER)],
        modulecode=ModuleCode(sequences=[seq], equationblocks=[eq]),
        moduledef=None,
    )

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    magic = [i for i in analyzer.issues if isinstance(i, MagicNumberIssue)]
    assert len(magic) == 2

    values = sorted(i.literal_value for i in magic)
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
        localvariables=[Variable(name="value", datatype=ScalarDatatype.INTEGER)],
        submodules=[],
        modulecode=None,
        parametermappings=[],
    )

    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[Variable(name="Value", datatype=ScalarDatatype.INTEGER)],
        submodules=[child],
        modulecode=None,
        moduledef=None,
    )

    report = analyze_variables(bp, selected_issue_kinds=frozenset({IssueKind.SHADOWING}))

    assert any(i.kind is IssueKind.SHADOWING for i in report.issues)


def test_shadowing_detected_for_moduletype_instance_locals():
    mt = ModuleTypeDef(
        name="TypeA",
        moduleparameters=[],
        localvariables=[Variable(name="Setting", datatype=ScalarDatatype.INTEGER)],
        submodules=[],
        moduledef=None,
        modulecode=None,
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
        localvariables=[Variable(name="setting", datatype=ScalarDatatype.INTEGER)],
        submodules=[instance],
        modulecode=None,
        moduledef=None,
    )

    report = analyze_variables(bp, selected_issue_kinds=frozenset({IssueKind.SHADOWING}))

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


def test_variable_analysis_marks_interact_outvar_as_write_not_read_only():
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    Changed: boolean := False;
ModuleDef
    ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
    InteractObjects :
        ComBut_ ( 0.0 , 0.0 ) ( 1.0 , 1.0 )
            Value_Changed = True : OutVar_ "Changed"
ENDDEF (*BasePicture*);
"""

    bp = parser_core_parse_source_text(code)
    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    changed = bp.localvariables[0]
    usage = analyzer._get_usage(changed)

    assert usage.written is True
    assert usage.read is False
    assert not any(
        issue.kind is IssueKind.READ_ONLY_NON_CONST and issue.variable is changed for issue in analyzer.issues
    )


def test_variable_analysis_marks_procedure_interact_outvar_as_write_in_typedef():
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
TYPEDEFINITIONS
    ButtonType = MODULEDEFINITION DateCode_ 1
    LOCALVARIABLES
        WindowDisplayed: boolean := False;
    ModuleDef
        ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
        InteractObjects :
            ProcedureInteract ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
                NewWindow
                False : OutVar_ "WindowDisplayed"
                Variable = 0.0
    ENDDEF (*ButtonType*);
ModuleDef
    ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ENDDEF (*BasePicture*);
"""

    bp = parser_core_parse_source_text(code)
    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    window_displayed = bp.moduletype_defs[0].localvariables[0]
    usage = analyzer._get_usage(window_displayed)

    assert usage.written is True
    assert usage.read is False
    assert not any(
        issue.kind is IssueKind.READ_ONLY_NON_CONST and issue.variable is window_displayed for issue in analyzer.issues
    )


def test_shadowing_reports_a_local_that_captures_a_module_parameter() -> None:
    code = """
"Syntax version 2.23, date: 2026-06-19-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-06-19-12:00:00.000, name: Shadow"

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1
MODULEPARAMETERS
   Setting: integer := 0;
SUBMODULES
   Worker Invocation
      ( 0.0 , 0.0 , 0.0 , 0.4 , 0.4
       ) : MODULEDEFINITION DateCode_ 2
   LOCALVARIABLES
      Setting: integer := 1;
   ModuleDef
   ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
   ENDDEF (*Worker*);
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ENDDEF (*BasePicture*);
"""
    report = analyze_variables(
        parser_core_parse_source_text(code), selected_issue_kinds=frozenset({IssueKind.SHADOWING})
    )

    shadowing = [issue for issue in report.issues if issue.kind is IssueKind.SHADOWING]
    assert len(shadowing) == 1
    assert shadowing[0].variable is not None
    assert shadowing[0].variable.name == "Setting"
    assert shadowing[0].role == "shadows 'Setting' from BasePicture"
