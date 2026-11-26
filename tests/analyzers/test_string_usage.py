# pyright: reportPrivateUsage=false
"""String capacity and style checks over synthetic module trees."""

from __future__ import annotations

from sattline_parser import parse_source_text
from sattline_parser.ast import MappingSource
from sattline_parser.models.ast_model import (
    Assignment,
    BasePicture,
    CodeItem,
    Equation,
    FrameModule,
    IfStmt,
    ModuleCode,
    ModuleDef,
    ModuleHeader,
    ModuleTypeDef,
    ModuleTypeInstance,
    ParameterMapping,
    ScalarDatatype,
    SingleModule,
    SLExpression,
    Variable,
)
from sattline_parser.models.expressions import BinOp, FuncCall, FuncCallStmt, VarRef

from sattlint.analyzers._string_models import StringCandidate, StringInferenceResult, StringSlotKey, _AbstractState
from sattlint.analyzers.framework import SimpleReport
from sattlint.analyzers.string_inference import _precise_state, _stabilize_unknown_flags
from sattlint.analyzers.string_usage import analyze_string_capacity, analyze_string_style
from sattlint.config.string_capacities import STANDARD_STRING_CAPACITIES


def _hdr(name: str) -> ModuleHeader:
    return ModuleHeader(name=name, invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0))


def _varref(name: str) -> VarRef:
    return VarRef(name=name)


def _call(name: str, *args: SLExpression) -> FuncCallStmt:
    return FuncCallStmt(call=FuncCall(name=name, args=tuple(args)))


def _equation(code: list[CodeItem]) -> Equation:
    return Equation(name="Main", position=(0.0, 0.0), size=(1.0, 1.0), code=code)


def _base_picture(
    *,
    variables: list[Variable] | None = None,
    code: list[CodeItem] | None = None,
    submodules: list[SingleModule | FrameModule | ModuleTypeInstance] | None = None,
) -> BasePicture:
    return BasePicture(
        header=_hdr("Root"),
        name="Root",
        localvariables=variables or [],
        submodules=submodules or [],
        moduledef=ModuleDef(),
        modulecode=ModuleCode(equationblocks=[_equation(code)]) if code is not None else None,
    )


def _child(
    *,
    parameters: list[Variable] | None = None,
    variables: list[Variable] | None = None,
    code: list[CodeItem] | None = None,
    mappings: list[ParameterMapping] | None = None,
) -> SingleModule:
    return SingleModule(
        header=_hdr("Child"),
        moduleparameters=parameters or [],
        localvariables=variables or [],
        parametermappings=mappings or [],
        submodules=[],
        modulecode=ModuleCode(equationblocks=[_equation(code)]) if code is not None else None,
        moduledef=ModuleDef(),
    )


def _mapping(target: str, source: str) -> ParameterMapping:
    return ParameterMapping(
        target=_varref(target),
        source=_varref(source),
        source_type=MappingSource.VARIABLE,
        is_source_global=False,
        is_duration=False,
        source_literal=None,
    )


def _capacity_kinds(report: SimpleReport) -> list[str]:
    return [issue.kind for issue in report.issues]


def _style_kinds(report: SimpleReport) -> list[str]:
    return [issue.kind for issue in report.issues]


def test_initializer_longer_than_identstring_is_reported() -> None:
    bp = _base_picture(variables=[Variable(name="BatchName", datatype=ScalarDatatype.IDENTSTRING, init_value="x" * 16)])

    report = analyze_string_capacity(bp, string_capacities=STANDARD_STRING_CAPACITIES)

    assert _capacity_kinds(report) == ["string_capacity.literal_overflow"]
    assert "16 characters" in report.issues[0].message
    assert "15" in report.issues[0].message


def test_assignment_longer_than_capacity_is_reported() -> None:
    bp = _base_picture(
        variables=[Variable(name="BatchName", datatype=ScalarDatatype.IDENTSTRING)],
        code=[Assignment(target=_varref("BatchName"), value="x" * 16)],
    )

    report = analyze_string_capacity(bp, string_capacities=STANDARD_STRING_CAPACITIES)

    assert _capacity_kinds(report) == ["string_capacity.literal_overflow"]
    assert "Assignment" in report.issues[0].message


def test_assignment_from_a_longer_string_is_reported() -> None:
    bp = _base_picture(
        variables=[
            Variable(name="Source", datatype=ScalarDatatype.STRING, init_value="x" * 20),
            Variable(name="Target", datatype=ScalarDatatype.IDENTSTRING),
        ],
        code=[Assignment(target=_varref("Target"), value=_varref("Source"))],
    )

    report = analyze_string_capacity(bp, string_capacities=STANDARD_STRING_CAPACITIES)

    assert _capacity_kinds(report) == ["string_capacity.assignment_overflow"]
    assert report.issues[0].suggestion == "Shorten the source, or use a larger string datatype for the target."


def test_assignment_that_fits_its_capacity_is_not_reported() -> None:
    bp = _base_picture(
        variables=[Variable(name="BatchName", datatype=ScalarDatatype.IDENTSTRING)],
        code=[Assignment(target=_varref("BatchName"), value="x" * 15)],
    )

    report = analyze_string_capacity(bp, string_capacities=STANDARD_STRING_CAPACITIES)

    assert report.issues == []


def test_mapped_assignment_uses_the_actual_variable_capacity() -> None:
    wide = Variable(name="Wide", datatype=ScalarDatatype.STRING)
    child = _child(
        parameters=[Variable(name="Name", datatype=ScalarDatatype.IDENTSTRING)],
        code=[Assignment(target=_varref("Name"), value="x" * 20)],
        mappings=[_mapping("Name", "Wide")],
    )

    report = analyze_string_capacity(
        _base_picture(variables=[wide], submodules=[child]),
        string_capacities=STANDARD_STRING_CAPACITIES,
    )

    assert report.issues == []


def test_insertstring_overflow_is_reported_with_its_site() -> None:
    bp = _base_picture(
        variables=[
            Variable(name="Result", datatype=ScalarDatatype.IDENTSTRING, init_value="Test"),
            Variable(name="Source", datatype=ScalarDatatype.IDENTSTRING, init_value="AnotherIdent"),
            Variable(name="Status", datatype=ScalarDatatype.INTEGER),
        ],
        code=[
            _call("SetStringPos", _varref("Result"), 5, _varref("Status")),
            _call("InsertString", _varref("Result"), _varref("Source"), 12, _varref("Status")),
        ],
    )

    report = analyze_string_capacity(bp, string_capacities=STANDARD_STRING_CAPACITIES)

    assert _capacity_kinds(report) == ["string_capacity.procedure_overflow"]
    issue = report.issues[0]
    assert "InsertString" in issue.message
    assert issue.data is not None
    assert issue.data["site"] == "equation block 'Main'"


def test_a_value_written_in_another_module_is_not_followed() -> None:
    """The analyzers only claim lengths the source states in place.

    Following a value through a parameter mapping needs a whole-program fixed
    point, which is what made these analyzers take minutes on a real project.
    The trade is deliberate: a length that needs that analysis is not reported.
    """
    child = _child(
        parameters=[Variable(name="WideIn", datatype=ScalarDatatype.STRING)],
        code=[Assignment(target=_varref("WideIn"), value="x" * 20)],
        mappings=[_mapping("WideIn", "Wide")],
    )
    bp = _base_picture(
        variables=[
            Variable(name="Wide", datatype=ScalarDatatype.STRING),
            Variable(name="Target", datatype=ScalarDatatype.IDENTSTRING),
        ],
        code=[Assignment(target=_varref("Target"), value=_varref("Wide"))],
        submodules=[child],
    )

    report = analyze_string_capacity(bp, string_capacities=STANDARD_STRING_CAPACITIES)

    assert _capacity_kinds(report) == []


def test_putblanks_overflow_is_reported() -> None:
    bp = _base_picture(
        variables=[
            Variable(name="Text", datatype=ScalarDatatype.IDENTSTRING, init_value="Test"),
            Variable(name="Status", datatype=ScalarDatatype.INTEGER),
        ],
        code=[_call("PutBlanks", _varref("Text"), 20, _varref("Status"))],
    )

    report = analyze_string_capacity(bp, string_capacities=STANDARD_STRING_CAPACITIES)

    assert _capacity_kinds(report) == ["string_capacity.procedure_overflow"]
    assert report.issues[0].data is not None
    assert report.issues[0].data["operation"] == "PutBlanks"


def test_extractstring_wider_than_the_target_is_reported() -> None:
    bp = _base_picture(
        variables=[
            Variable(name="Source", datatype=ScalarDatatype.STRING, init_value="x" * 20),
            Variable(name="Dest", datatype=ScalarDatatype.IDENTSTRING),
            Variable(name="Status", datatype=ScalarDatatype.INTEGER),
        ],
        code=[
            _call("SetStringPos", _varref("Source"), 1, _varref("Status")),
            _call("ExtractString", _varref("Dest"), _varref("Source"), 20, _varref("Status")),
        ],
    )

    report = analyze_string_capacity(bp, string_capacities=STANDARD_STRING_CAPACITIES)

    assert _capacity_kinds(report) == ["string_capacity.procedure_overflow"]
    assert report.issues[0].data is not None
    assert report.issues[0].data["operation"] == "ExtractString"


def test_a_string_pipeline_that_fits_is_not_reported() -> None:
    bp = _base_picture(
        variables=[
            Variable(name="Left", datatype=ScalarDatatype.IDENTSTRING, init_value="1234567890"),
            Variable(name="Right", datatype=ScalarDatatype.IDENTSTRING, init_value="12345"),
            Variable(name="Result", datatype=ScalarDatatype.IDENTSTRING),
            Variable(name="Copy", datatype=ScalarDatatype.IDENTSTRING),
            Variable(name="Room", datatype=ScalarDatatype.LINESTRING),
            Variable(name="Status", datatype=ScalarDatatype.INTEGER),
        ],
        code=[
            _call("ClearString", _varref("Result")),
            _call("SetStringPos", _varref("Left"), 1, _varref("Status")),
            _call("SetStringPos", _varref("Right"), 1, _varref("Status")),
            _call("Concatenate", _varref("Left"), _varref("Right"), _varref("Result"), _varref("Status")),
            _call("CopyString", _varref("Result"), _varref("Copy"), _varref("Status")),
            _call("SetStringPos", _varref("Copy"), 6, _varref("Status")),
            _call("CutString", _varref("Copy"), 10, _varref("Status")),
            _call("ExtractString", _varref("Copy"), _varref("Result"), 5, _varref("Status")),
            _call("ClearString", _varref("Copy")),
            _call(
                "PutBlanks",
                _varref("Copy"),
                FuncCall(name="MaxStringLength", args=(_varref("Copy"),)),
                _varref("Status"),
            ),
            _call("ClearString", _varref("Room")),
            _call(
                "InsertString",
                _varref("Room"),
                _varref("Left"),
                FuncCall(name="StringLength", args=(_varref("Left"),)),
                _varref("Status"),
            ),
        ],
    )

    report = analyze_string_capacity(bp, string_capacities=STANDARD_STRING_CAPACITIES)

    assert report.issues == []


def test_getstringpos_arithmetic_drives_the_cursor() -> None:
    bp = _base_picture(
        variables=[
            Variable(name="Text", datatype=ScalarDatatype.IDENTSTRING, init_value="12345"),
            Variable(name="Status", datatype=ScalarDatatype.INTEGER),
        ],
        code=[
            _call(
                "SetStringPos",
                _varref("Text"),
                BinOp(
                    left=FuncCall(name="GetStringPos", args=(_varref("Text"),)),
                    op="+",
                    right=0,
                ),
                _varref("Status"),
            )
        ],
    )

    report = analyze_string_capacity(bp, string_capacities=STANDARD_STRING_CAPACITIES)

    assert report.issues == []


def test_unknown_procedure_output_is_not_trusted() -> None:
    child = _child(
        variables=[Variable(name="Name", datatype=ScalarDatatype.STRING, init_value="Short")],
        code=[_call("UnknownProcedure", _varref("Name"))],
    )

    report = analyze_string_style(
        _base_picture(submodules=[child]),
        string_capacities=STANDARD_STRING_CAPACITIES,
    )

    assert report.issues == []


def test_integer_conversion_wider_than_the_target_is_reported() -> None:
    bp = _base_picture(
        variables=[
            Variable(name="Text", datatype=ScalarDatatype.IDENTSTRING),
            Variable(name="Status", datatype=ScalarDatatype.INTEGER),
        ],
        code=[_call("IntegerToString", _varref("Text"), 12345, 20, _varref("Status"))],
    )

    report = analyze_string_capacity(bp, string_capacities=STANDARD_STRING_CAPACITIES)

    assert _capacity_kinds(report) == ["string_capacity.procedure_overflow"]
    assert report.issues[0].data is not None
    assert report.issues[0].data["operation"] == "IntegerToString"


def test_integer_conversion_that_fits_is_not_reported() -> None:
    bp = _base_picture(
        variables=[
            Variable(name="Text", datatype=ScalarDatatype.IDENTSTRING),
            Variable(name="Status", datatype=ScalarDatatype.INTEGER),
        ],
        code=[_call("IntegerToString", _varref("Text"), 12345, 10, _varref("Status"))],
    )

    report = analyze_string_capacity(bp, string_capacities=STANDARD_STRING_CAPACITIES)

    assert report.issues == []


def test_concatenate_overflow_is_reported() -> None:
    bp = _base_picture(
        variables=[
            Variable(name="Left", datatype=ScalarDatatype.IDENTSTRING, init_value="Test"),
            Variable(name="Right", datatype=ScalarDatatype.IDENTSTRING, init_value="AnotherIdent"),
            Variable(name="Result", datatype=ScalarDatatype.IDENTSTRING),
            Variable(name="Status", datatype=ScalarDatatype.INTEGER),
        ],
        code=[
            _call("ClearString", _varref("Result")),
            _call("SetStringPos", _varref("Left"), 1, _varref("Status")),
            _call("SetStringPos", _varref("Right"), 1, _varref("Status")),
            _call("Concatenate", _varref("Left"), _varref("Right"), _varref("Result"), _varref("Status")),
        ],
    )

    report = analyze_string_capacity(bp, string_capacities=STANDARD_STRING_CAPACITIES)

    assert _capacity_kinds(report) == ["string_capacity.procedure_overflow"]
    assert report.issues[0].data is not None
    assert report.issues[0].data["operation"] == "Concatenate"


def test_copy_from_an_unknown_source_is_not_reported() -> None:
    bp = _base_picture(
        variables=[
            Variable(name="Source", datatype=ScalarDatatype.IDENTSTRING),
            Variable(name="Target", datatype=ScalarDatatype.IDENTSTRING),
            Variable(name="Status", datatype=ScalarDatatype.INTEGER),
        ],
        code=[_call("CopyString", _varref("Source"), _varref("Target"), _varref("Status"))],
    )

    report = analyze_string_capacity(bp, string_capacities=STANDARD_STRING_CAPACITIES)

    assert report.issues == []


def test_copyvariable_between_strings_suggests_the_string_specific_copy() -> None:
    bp = _base_picture(
        variables=[
            Variable(name="Source", datatype=ScalarDatatype.STRING),
            Variable(name="Target", datatype=ScalarDatatype.STRING),
            Variable(name="Status", datatype=ScalarDatatype.INTEGER),
        ],
        code=[_call("CopyVarNoSort", _varref("Source"), _varref("Target"), _varref("Status"))],
    )

    capacity_report = analyze_string_capacity(bp, string_capacities=STANDARD_STRING_CAPACITIES)
    style_report = analyze_string_style(bp, string_capacities=STANDARD_STRING_CAPACITIES)

    assert capacity_report.issues == []
    assert _style_kinds(style_report) == ["string_style.generic_copy"]
    assert "CopyStringNoSort" in style_report.issues[0].message


def test_copyvariable_suggests_the_string_copy_with_case_sensitivity() -> None:
    bp = _base_picture(
        variables=[
            Variable(name="Source", datatype=ScalarDatatype.STRING),
            Variable(name="Target", datatype=ScalarDatatype.STRING),
            Variable(name="Status", datatype=ScalarDatatype.INTEGER),
        ],
        code=[_call("CopyVariable", _varref("Source"), _varref("Target"), _varref("Status"))],
    )

    report = analyze_string_style(bp, string_capacities=STANDARD_STRING_CAPACITIES)

    assert _style_kinds(report) == ["string_style.generic_copy"]
    assert "CopyString" in report.issues[0].message
    assert "Boolean case-sensitivity" in report.issues[0].message
    assert report.issues[0].data is not None
    assert "Boolean case-sensitivity" in str(report.issues[0].data["argument_change"])


def test_copyvariable_on_a_record_is_not_a_string_suggestion() -> None:
    bp = _base_picture(
        variables=[
            Variable(name="Source", datatype="UnknownRecord"),
            Variable(name="Target", datatype="UnknownRecord"),
            Variable(name="Status", datatype=ScalarDatatype.INTEGER),
        ],
        code=[_call("CopyVariable", _varref("Source"), _varref("Target"), _varref("Status"))],
    )

    report = analyze_string_style(bp, string_capacities=STANDARD_STRING_CAPACITIES)

    assert report.issues == []


def test_a_narrower_datatype_is_suggested_for_a_local_that_only_holds_short_values() -> None:
    child = _child(variables=[Variable(name="Name", datatype=ScalarDatatype.STRING, init_value="ShortValue")])

    report = analyze_string_style(
        _base_picture(submodules=[child]),
        string_capacities=STANDARD_STRING_CAPACITIES,
    )

    assert _style_kinds(report) == ["string_style.narrower_datatype"]
    assert "identstring" in report.issues[0].message


def test_a_wider_value_prevents_the_narrower_datatype_suggestion() -> None:
    child = _child(
        variables=[Variable(name="Name", datatype=ScalarDatatype.STRING, init_value="Short")],
        code=[Assignment(target=_varref("Name"), value="x" * 35)],
    )

    report = analyze_string_style(
        _base_picture(submodules=[child]),
        string_capacities=STANDARD_STRING_CAPACITIES,
    )

    assert report.issues == []


def test_an_untaken_branch_keeps_its_long_value_and_prevents_narrowing() -> None:
    child = _child(
        variables=[
            Variable(name="Name", datatype=ScalarDatatype.STRING, init_value="x" * 35),
            Variable(name="Cond", datatype=ScalarDatatype.BOOLEAN),
        ],
        code=[
            IfStmt(
                branches=(
                    (
                        _varref("Cond"),
                        (Assignment(target=_varref("Name"), value="Short"),),
                    ),
                ),
                else_block=None,
            )
        ],
    )

    report = analyze_string_style(
        _base_picture(submodules=[child]),
        string_capacities=STANDARD_STRING_CAPACITIES,
    )

    assert report.issues == []


def test_a_module_parameter_is_never_suggested_as_a_narrower_datatype() -> None:
    child = _child(parameters=[Variable(name="Name", datatype=ScalarDatatype.STRING, init_value="Short")])

    report = analyze_string_style(
        _base_picture(submodules=[child]),
        string_capacities=STANDARD_STRING_CAPACITIES,
    )

    assert report.issues == []


def test_typedef_literal_overflow_is_reported_once_for_two_instances() -> None:
    typedef = ModuleTypeDef(
        name="Unit",
        localvariables=[Variable(name="Name", datatype=ScalarDatatype.IDENTSTRING)],
        moduledef=ModuleDef(),
        modulecode=ModuleCode(equationblocks=[_equation([Assignment(target=_varref("Name"), value="x" * 16)])]),
    )
    bp = BasePicture(
        header=_hdr("Root"),
        name="Root",
        moduledef=ModuleDef(),
        moduletype_defs=[typedef],
        submodules=[
            ModuleTypeInstance(header=_hdr("First"), moduletype_name="Unit"),
            ModuleTypeInstance(header=_hdr("Second"), moduletype_name="Unit"),
        ],
    )

    report = analyze_string_capacity(bp, string_capacities=STANDARD_STRING_CAPACITIES)

    assert _capacity_kinds(report) == ["string_capacity.literal_overflow"]


def test_oscillating_unknown_flag_is_folded_to_unknown() -> None:
    key = StringSlotKey(module_path=("root",), variable_name="name")
    candidate = StringCandidate(text="value")
    previous = _AbstractState(
        string_values={
            key: StringInferenceResult(
                candidates=(candidate,),
                cursor_positions=(6,),
                max_length=15,
                unknown_text=True,
            )
        }
    )
    current = _AbstractState(
        string_values={
            key: StringInferenceResult(
                candidates=(candidate,),
                cursor_positions=(6,),
                max_length=15,
                unknown_text=False,
            )
        }
    )

    assert _precise_state(previous) == _precise_state(current)
    folded = _stabilize_unknown_flags(previous, current)

    assert folded.string_values[key].unknown_text


SFC_STEP_SOURCE = """"Syntax version 2.23, date: 2026-06-19-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-06-19-12:00:00.000, name: StepStr"

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

LOCALVARIABLES
   BatchName: identstring  := "";

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
   SEQUENCE OpSeq (SeqControl, SeqTimer) COORD 0.0, 0.5 OBJSIZE 1.0, 0.5
      SEQINITSTEP Init
         ENTERCODE
            BatchName = "ABCDEFGHIJKLMNOP";
      SEQTRANSITION TrDone WAIT_FOR False
   ENDSEQUENCE
ENDDEF (*BasePicture*);
"""


def test_sfc_step_literal_overflow_is_reported_from_parsed_source() -> None:
    base_picture = parse_source_text(SFC_STEP_SOURCE)

    report = analyze_string_capacity(base_picture, string_capacities=STANDARD_STRING_CAPACITIES)

    assert _capacity_kinds(report) == ["string_capacity.literal_overflow"]
    assert report.issues[0].data is not None
    assert report.issues[0].data["site"] == "sequence 'OpSeq' step 'Init' ENTER"
