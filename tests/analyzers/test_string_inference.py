from sattline_parser import parse_source_text as parser_core_parse_source_text
from sattline_parser.models.ast_model import (
    Assignment,
    BasePicture,
    Equation,
    MappingSource,
    ModuleCode,
    ModuleDef,
    ModuleHeader,
    ParameterMapping,
    ScalarDatatype,
    SingleModule,
    Variable,
)
from sattline_parser.models.expressions import BinOp, FuncCall, FuncCallStmt, SLExpression, VarRef

from sattlint.analyzers.string_inference import ExactStringInferenceEngine
from sattlint.config.string_capacities import STANDARD_STRING_CAPACITIES, StringCapacities


def _engine(
    base_picture: BasePicture,
    capacities: StringCapacities = STANDARD_STRING_CAPACITIES,
) -> ExactStringInferenceEngine:
    return ExactStringInferenceEngine(base_picture, capacities=capacities)


def _varref(name: str) -> VarRef:
    return VarRef(name=name)


def _call(name: str, *args: SLExpression) -> FuncCall:
    return FuncCall(name=name, args=tuple(args))


def _func(name: str, *args: SLExpression) -> FuncCallStmt:
    return FuncCallStmt(call=FuncCall(name=name, args=tuple(args)))


def _base_picture(*, variables: list[Variable], code: list[object]) -> BasePicture:
    return BasePicture(
        header=ModuleHeader(name="Root", invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0)),
        name="Root",
        localvariables=variables,
        moduledef=ModuleDef(),
        modulecode=ModuleCode(
            equationblocks=[
                Equation(
                    name="Main",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=code,  # pyright: ignore[reportArgumentType]
                )
            ]
        ),
    )


def test_mapped_literal_uses_the_target_datatype_capacity() -> None:
    child = SingleModule(
        header=ModuleHeader(name="Child", invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0)),
        moduleparameters=[Variable(name="Tag", datatype=ScalarDatatype.STRING)],
        localvariables=[],
        submodules=[],
        modulecode=None,
        moduledef=None,
        parametermappings=[
            ParameterMapping(
                target=VarRef(name="Tag"),
                source_type=MappingSource.VALUE,
                is_duration=False,
                is_source_global=False,
                source=None,
                source_literal="mapped",
            )
        ],
    )
    base_picture = BasePicture(
        header=ModuleHeader(name="Root", invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0)),
        name="Root",
        submodules=[child],
        moduledef=ModuleDef(),
    )

    result = _engine(base_picture).infer("Tag", module_path=("Root", "Child"))

    assert result.max_length == 40


def test_exact_string_inference_putblanks_inserts_blanks_and_fills_gap() -> None:
    base_picture = _base_picture(
        variables=[
            Variable(name="Tag", datatype=ScalarDatatype.STRING),
            Variable(name="Status", datatype=ScalarDatatype.INTEGER),
        ],
        code=[
            _func("ClearString", _varref("Tag")),
            _func("SetStringPos", _varref("Tag"), 3, _varref("Status")),
            _func("PutBlanks", _varref("Tag"), 2, _varref("Status")),
        ],
    )

    result = _engine(base_picture).infer("Tag", module_path=("Root",))

    assert result.texts == ("    ",)
    assert result.cursor_positions == (5,)


def test_exact_string_inference_maxstringlength_drives_result_capacity() -> None:
    base_picture = _base_picture(
        variables=[
            Variable(name="Tag", datatype=ScalarDatatype.STRING),
            Variable(name="Status", datatype=ScalarDatatype.INTEGER),
        ],
        code=[
            _func("ClearString", _varref("Tag")),
            _func("PutBlanks", _varref("Tag"), _call("MaxStringLength", _varref("Tag")), _varref("Status")),
        ],
    )

    result = _engine(base_picture).infer("Tag", module_path=("Root",))

    assert result.texts == (" " * 40,)
    assert result.cursor_positions == (41,)
    assert result.max_length == 40


def test_exact_string_inference_extractstring_uses_source_cursor_and_resets_destination_cursor() -> None:
    base_picture = _base_picture(
        variables=[
            Variable(name="Dest", datatype=ScalarDatatype.STRING, init_value="DummyString"),
            Variable(name="Source", datatype=ScalarDatatype.STRING, init_value="1234567890"),
            Variable(name="Status", datatype=ScalarDatatype.INTEGER),
        ],
        code=[
            _func("SetStringPos", _varref("Source"), 4, _varref("Status")),
            _func("ExtractString", _varref("Dest"), _varref("Source"), 3, _varref("Status")),
        ],
    )

    engine = _engine(base_picture)
    dest_result = engine.infer("Dest", module_path=("Root",))
    source_result = engine.infer("Source", module_path=("Root",))

    assert dest_result.texts == ("456",)
    assert dest_result.cursor_positions == (1,)
    assert source_result.texts == ("1234567890",)
    assert source_result.cursor_positions == (4,)


def test_exact_string_inference_concatenate_reads_from_source_and_result_positions() -> None:
    base_picture = _base_picture(
        variables=[
            Variable(name="Str1", datatype=ScalarDatatype.STRING, init_value="uuuuHello"),
            Variable(name="Str2", datatype=ScalarDatatype.STRING, init_value=" there "),
            Variable(name="Result", datatype=ScalarDatatype.STRING),
            Variable(name="Status", datatype=ScalarDatatype.INTEGER),
        ],
        code=[
            _func("SetStringPos", _varref("Str1"), 5, _varref("Status")),
            _func("SetStringPos", _varref("Str2"), 1, _varref("Status")),
            _func("SetStringPos", _varref("Result"), 3, _varref("Status")),
            _func("Concatenate", _varref("Str1"), _varref("Str2"), _varref("Result"), _varref("Status")),
        ],
    )

    result = _engine(base_picture).infer("Result", module_path=("Root",))

    assert result.texts == ("  Hello there ",)
    assert result.cursor_positions == (15,)


def test_exact_string_inference_overflow_leaves_target_unchanged() -> None:
    base_picture = _base_picture(
        variables=[
            Variable(name="Tag", datatype=ScalarDatatype.IDENTSTRING, init_value="OK"),
            Variable(name="Status", datatype=ScalarDatatype.INTEGER),
        ],
        code=[
            _func("SetStringPos", _varref("Tag"), 2, _varref("Status")),
            _func("PutBlanks", _varref("Tag"), 20, _varref("Status")),
        ],
    )

    result = _engine(base_picture).infer("Tag", module_path=("Root",))

    assert result.texts == ("OK",)
    assert result.cursor_positions == (2,)


def test_exact_string_inference_records_concatenate_overflow_attempt() -> None:
    base_picture = _base_picture(
        variables=[
            Variable(name="Left", datatype=ScalarDatatype.IDENTSTRING, init_value="Test"),
            Variable(name="Right", datatype=ScalarDatatype.IDENTSTRING, init_value="AnotherIdent"),
            Variable(name="Result", datatype=ScalarDatatype.IDENTSTRING),
            Variable(name="Status", datatype=ScalarDatatype.INTEGER),
        ],
        code=[
            _func("ClearString", _varref("Result")),
            _func("SetStringPos", _varref("Left"), 1, _varref("Status")),
            _func("SetStringPos", _varref("Right"), 1, _varref("Status")),
            _func("Concatenate", _varref("Left"), _varref("Right"), _varref("Result"), _varref("Status")),
        ],
    )

    result = _engine(base_picture).infer("Result", module_path=("Root",))

    assert result.texts == ("",)
    assert result.cursor_positions == (1,)
    assert result.overflow_operations == ("Concatenate",)
    assert "TestAnotherIdent" in result.overflow_examples


def test_exact_string_inference_records_insertstring_overflow_attempt() -> None:
    base_picture = _base_picture(
        variables=[
            Variable(name="Result", datatype=ScalarDatatype.IDENTSTRING, init_value="Test"),
            Variable(name="Source", datatype=ScalarDatatype.IDENTSTRING, init_value="AnotherIdent"),
            Variable(name="Status", datatype=ScalarDatatype.INTEGER),
        ],
        code=[
            _func("SetStringPos", _varref("Result"), 5, _varref("Status")),
            _func("InsertString", _varref("Result"), _varref("Source"), 12, _varref("Status")),
        ],
    )

    result = _engine(base_picture).infer("Result", module_path=("Root",))

    assert result.texts == ("Test",)
    assert result.cursor_positions == (5,)
    assert result.overflow_operations == ("InsertString",)
    assert "TestAnotherIdent" in result.overflow_examples


def test_exact_string_inference_nationaluppercase_transforms_destination() -> None:
    base_picture = _base_picture(
        variables=[
            Variable(name="Source", datatype=ScalarDatatype.STRING, init_value="abz"),
            Variable(name="Dest", datatype=ScalarDatatype.STRING),
            Variable(name="NationCode", datatype=ScalarDatatype.INTEGER, init_value=1),
            Variable(name="Status", datatype=ScalarDatatype.INTEGER),
        ],
        code=[
            _func(
                "NationalUpperCase",
                _varref("Source"),
                _varref("Dest"),
                _varref("NationCode"),
                _varref("Status"),
            )
        ],
    )

    result = _engine(base_picture).infer("Dest", module_path=("Root",))

    assert result.texts == ("ABZ",)
    assert result.cursor_positions == (4,)


def test_exact_string_inference_invalid_setstringpos_leaves_state_unchanged() -> None:
    base_picture = _base_picture(
        variables=[
            Variable(name="Tag", datatype=ScalarDatatype.IDENTSTRING),
            Variable(name="Status", datatype=ScalarDatatype.INTEGER),
        ],
        code=[
            _func("ClearString", _varref("Tag")),
            _func("SetStringPos", _varref("Tag"), 16, _varref("Status")),
        ],
    )

    result = _engine(base_picture).infer("Tag", module_path=("Root",))

    assert result.texts == ("",)
    assert result.cursor_positions == (1,)


SFC_STEP_STRING_SOURCE = """"Syntax version 2.23, date: 2026-06-19-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-06-19-12:00:00.000, name: StepStr"

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

LOCALVARIABLES
   PictureName: string  := "";

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
   SEQUENCE OpSeq (SeqControl, SeqTimer) COORD 0.0, 0.5 OBJSIZE 1.0, 0.5
      SEQINITSTEP Init
         ENTERCODE
            PictureName = "InitView";
      SEQTRANSITION TrDone WAIT_FOR False
   ENDSEQUENCE
ENDDEF (*BasePicture*);
"""

FRAME_MODULE_STRING_SOURCE = """"Syntax version 2.23, date: 2026-06-19-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-06-19-12:00:00.000, name: FrameStr"

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

SUBMODULES
   FrameRoot Invocation
      ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
       ) : MODULEDEFINITION DateCode_ 1 (Frame_Module)
      LOCALVARIABLES
         FrameText: string  := "";
      ModuleDef
      ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
      ModuleCode
         EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
            FrameText = "FrameView";
      ENDDEF (*FrameRoot*);

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )

ENDDEF (*BasePicture*);
"""


def test_inference_reads_string_assignments_inside_sequence_steps() -> None:
    base_picture = parser_core_parse_source_text(SFC_STEP_STRING_SOURCE)

    result = _engine(base_picture).infer("PictureName", module_path=("BasePicture",))

    assert result.texts == ("InitView",)


def test_inference_resolves_frame_module_locals() -> None:
    base_picture = parser_core_parse_source_text(FRAME_MODULE_STRING_SOURCE)

    result = _engine(base_picture).infer("FrameText", module_path=("BasePicture", "FrameRoot"))

    assert result.texts == ("FrameView",)


def test_inference_stops_when_string_values_are_stable_even_if_an_integer_counter_grows() -> None:
    """A scan counter grows forever; string values are what the engine solves."""
    base_picture = _base_picture(
        variables=[Variable(name="Counter", datatype=ScalarDatatype.INTEGER, init_value=0)],
        code=[
            Assignment(
                target=_varref("Counter"),
                value=BinOp(left=_varref("Counter"), op="+", right=1),
            )
        ],
    )
    passes = 0

    def _progress(message: str) -> None:
        nonlocal passes
        if message.startswith("resolving string values"):
            passes += 1

    engine = ExactStringInferenceEngine(
        base_picture,
        capacities=STANDARD_STRING_CAPACITIES,
        progress_callback=_progress,
    )
    engine.infer("Counter", module_path=("Root",))

    assert passes == 1


def test_configured_string_capacity_decides_copy_overflow() -> None:
    """A 25-character copy fits a 40-character string but not a 20-character one."""
    text = "x" * 25

    def overflow_operations(string_capacity: int) -> tuple[str, ...]:
        base_picture = _base_picture(
            variables=[
                Variable(name="Source", datatype=ScalarDatatype.STRING, init_value=text),
                Variable(name="Target", datatype=ScalarDatatype.STRING),
            ],
            code=[
                _func("CopyString", _varref("Source"), _varref("Target")),
            ],
        )
        capacities = StringCapacities(
            identstring=15,
            tagstring=30,
            string=string_capacity,
            linestring=80,
            maxstring=140,
        )
        result = _engine(base_picture, capacities).infer("Target", module_path=("Root",))
        return result.overflow_operations

    assert overflow_operations(STANDARD_STRING_CAPACITIES.string) == ()
    assert overflow_operations(20) == ("CopyString",)
