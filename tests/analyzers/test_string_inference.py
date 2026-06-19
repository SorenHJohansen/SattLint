from sattline_parser.grammar import constants as const
from sattline_parser.models.ast_model import (
    BasePicture,
    Equation,
    ModuleCode,
    ModuleDef,
    ModuleHeader,
    Simple_DataType,
    Variable,
)
from sattlint.string_inference import ExactStringInferenceEngine


def _varref(name: str) -> dict[str, str]:
    return {"var_name": name}


def _func(name: str, *args: object) -> tuple[str, str, list[object]]:
    return (const.KEY_FUNCTION_CALL, name, list(args))


def _base_picture(*, variables: list[Variable], code: list[object]) -> BasePicture:
    return BasePicture(
        header=ModuleHeader(name="Root", invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0)),
        name="Root",
        localvariables=variables,
        moduledef=ModuleDef(),
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Main",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=code,
                )
            ]
        ),
    )


def test_exact_string_inference_putblanks_inserts_blanks_and_fills_gap() -> None:
    base_picture = _base_picture(
        variables=[
            Variable(name="Tag", datatype=Simple_DataType.STRING),
            Variable(name="Status", datatype=Simple_DataType.INTEGER),
        ],
        code=[
            _func("ClearString", _varref("Tag")),
            _func("SetStringPos", _varref("Tag"), 3, _varref("Status")),
            _func("PutBlanks", _varref("Tag"), 2, _varref("Status")),
        ],
    )

    result = ExactStringInferenceEngine(base_picture).infer("Tag", module_path=("Root",))

    assert result.texts == ("    ",)
    assert result.cursor_positions == (5,)


def test_exact_string_inference_maxstringlength_drives_result_capacity() -> None:
    base_picture = _base_picture(
        variables=[
            Variable(name="Tag", datatype=Simple_DataType.STRING),
            Variable(name="Status", datatype=Simple_DataType.INTEGER),
        ],
        code=[
            _func("ClearString", _varref("Tag")),
            _func("PutBlanks", _varref("Tag"), _func("MaxStringLength", _varref("Tag")), _varref("Status")),
        ],
    )

    result = ExactStringInferenceEngine(base_picture).infer("Tag", module_path=("Root",))

    assert result.texts == (" " * 40,)
    assert result.cursor_positions == (41,)
    assert result.max_length == 40


def test_exact_string_inference_extractstring_uses_source_cursor_and_resets_destination_cursor() -> None:
    base_picture = _base_picture(
        variables=[
            Variable(name="Dest", datatype=Simple_DataType.STRING, init_value="DummyString"),
            Variable(name="Source", datatype=Simple_DataType.STRING, init_value="1234567890"),
            Variable(name="Status", datatype=Simple_DataType.INTEGER),
        ],
        code=[
            _func("SetStringPos", _varref("Source"), 4, _varref("Status")),
            _func("ExtractString", _varref("Dest"), _varref("Source"), 3, _varref("Status")),
        ],
    )

    engine = ExactStringInferenceEngine(base_picture)
    dest_result = engine.infer("Dest", module_path=("Root",))
    source_result = engine.infer("Source", module_path=("Root",))

    assert dest_result.texts == ("456",)
    assert dest_result.cursor_positions == (1,)
    assert source_result.texts == ("1234567890",)
    assert source_result.cursor_positions == (4,)


def test_exact_string_inference_concatenate_reads_from_source_and_result_positions() -> None:
    base_picture = _base_picture(
        variables=[
            Variable(name="Str1", datatype=Simple_DataType.STRING, init_value="uuuuHello"),
            Variable(name="Str2", datatype=Simple_DataType.STRING, init_value=" there "),
            Variable(name="Result", datatype=Simple_DataType.STRING),
            Variable(name="Status", datatype=Simple_DataType.INTEGER),
        ],
        code=[
            _func("SetStringPos", _varref("Str1"), 5, _varref("Status")),
            _func("SetStringPos", _varref("Str2"), 1, _varref("Status")),
            _func("SetStringPos", _varref("Result"), 3, _varref("Status")),
            _func("Concatenate", _varref("Str1"), _varref("Str2"), _varref("Result"), _varref("Status")),
        ],
    )

    result = ExactStringInferenceEngine(base_picture).infer("Result", module_path=("Root",))

    assert result.texts == ("  Hello there ",)
    assert result.cursor_positions == (15,)


def test_exact_string_inference_overflow_leaves_target_unchanged() -> None:
    base_picture = _base_picture(
        variables=[
            Variable(name="Tag", datatype=Simple_DataType.IDENTSTRING, init_value="OK"),
            Variable(name="Status", datatype=Simple_DataType.INTEGER),
        ],
        code=[
            _func("SetStringPos", _varref("Tag"), 2, _varref("Status")),
            _func("PutBlanks", _varref("Tag"), 20, _varref("Status")),
        ],
    )

    result = ExactStringInferenceEngine(base_picture).infer("Tag", module_path=("Root",))

    assert result.texts == ("OK",)
    assert result.cursor_positions == (2,)


def test_exact_string_inference_records_concatenate_overflow_attempt() -> None:
    base_picture = _base_picture(
        variables=[
            Variable(name="Left", datatype=Simple_DataType.IDENTSTRING, init_value="Test"),
            Variable(name="Right", datatype=Simple_DataType.IDENTSTRING, init_value="AnotherIdent"),
            Variable(name="Result", datatype=Simple_DataType.IDENTSTRING),
            Variable(name="Status", datatype=Simple_DataType.INTEGER),
        ],
        code=[
            _func("ClearString", _varref("Result")),
            _func("SetStringPos", _varref("Left"), 1, _varref("Status")),
            _func("SetStringPos", _varref("Right"), 1, _varref("Status")),
            _func("Concatenate", _varref("Left"), _varref("Right"), _varref("Result"), _varref("Status")),
        ],
    )

    result = ExactStringInferenceEngine(base_picture).infer("Result", module_path=("Root",))

    assert result.texts == ("",)
    assert result.cursor_positions == (1,)
    assert result.overflow_operations == ("Concatenate",)
    assert "TestAnotherIdent" in result.overflow_examples


def test_exact_string_inference_records_insertstring_overflow_attempt() -> None:
    base_picture = _base_picture(
        variables=[
            Variable(name="Result", datatype=Simple_DataType.IDENTSTRING, init_value="Test"),
            Variable(name="Source", datatype=Simple_DataType.IDENTSTRING, init_value="AnotherIdent"),
            Variable(name="Status", datatype=Simple_DataType.INTEGER),
        ],
        code=[
            _func("SetStringPos", _varref("Result"), 5, _varref("Status")),
            _func("InsertString", _varref("Result"), _varref("Source"), 12, _varref("Status")),
        ],
    )

    result = ExactStringInferenceEngine(base_picture).infer("Result", module_path=("Root",))

    assert result.texts == ("Test",)
    assert result.cursor_positions == (5,)
    assert result.overflow_operations == ("InsertString",)
    assert "TestAnotherIdent" in result.overflow_examples


def test_exact_string_inference_nationaluppercase_transforms_destination() -> None:
    base_picture = _base_picture(
        variables=[
            Variable(name="Source", datatype=Simple_DataType.STRING, init_value="abz"),
            Variable(name="Dest", datatype=Simple_DataType.STRING),
            Variable(name="NationCode", datatype=Simple_DataType.INTEGER, init_value=1),
            Variable(name="Status", datatype=Simple_DataType.INTEGER),
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

    result = ExactStringInferenceEngine(base_picture).infer("Dest", module_path=("Root",))

    assert result.texts == ("ABZ",)
    assert result.cursor_positions == (4,)


def test_exact_string_inference_invalid_setstringpos_leaves_state_unchanged() -> None:
    base_picture = _base_picture(
        variables=[
            Variable(name="Tag", datatype=Simple_DataType.IDENTSTRING),
            Variable(name="Status", datatype=Simple_DataType.INTEGER),
        ],
        code=[
            _func("ClearString", _varref("Tag")),
            _func("SetStringPos", _varref("Tag"), 16, _varref("Status")),
        ],
    )

    result = ExactStringInferenceEngine(base_picture).infer("Tag", module_path=("Root",))

    assert result.texts == ("",)
    assert result.cursor_positions == (1,)
