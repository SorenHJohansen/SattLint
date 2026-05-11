"""Tests for R2.1: strict expression and assignment semantics."""

from pathlib import Path

from sattlint.engine import SyntaxValidationResult, validate_single_file_syntax


def _program(*, declarations: str, statement: str) -> str:
    return f""""SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
{declarations}
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
   EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      {statement}
ENDDEF (*BasePicture*);
"""


def _write_and_validate(tmp_path: Path, filename: str, code: str) -> SyntaxValidationResult:
    source_file = tmp_path / filename
    source_file.write_text(code, encoding="utf-8")
    return validate_single_file_syntax(source_file)


def _assert_validation_error(result: SyntaxValidationResult, *expected_fragments: str) -> None:
    assert result.ok is False
    assert result.stage == "validation"
    assert result.message is not None
    lowered_message = result.message.lower()
    for fragment in expected_fragments:
        assert fragment in lowered_message


def test_int_to_real_coercion_allowed_in_assignment(tmp_path):
    code = _program(
        declarations="   IntValue: integer := 42;\n   RealValue: real := 0.0;",
        statement="RealValue = IntValue;",
    )

    result = _write_and_validate(tmp_path, "IntToRealCoercion.s", code)

    assert result.ok is True, f"Expected ok but got: {result.message}"


def test_real_to_int_assignment_rejected(tmp_path):
    code = _program(
        declarations="   RealValue: real := 42.5;\n   IntValue: integer := 0;",
        statement="IntValue = RealValue;",
    )

    result = _write_and_validate(tmp_path, "RealToIntAssignment.s", code)

    _assert_validation_error(result, "real", "integer")


def test_anytype_expression_assignment_to_real_allowed(tmp_path):
    code = _program(
        declarations="   Flag: boolean := True;\n   Wildcard: AnyType;\n   RealValue: real := 0.0;",
        statement="RealValue = IF Flag THEN Wildcard ELSE Wildcard ENDIF;",
    )

    result = _write_and_validate(tmp_path, "AnyTypeExpressionToReal.s", code)

    assert result.ok is True, result.message


def test_int_plus_real_arithmetic_expression(tmp_path):
    code = _program(
        declarations="   IntValue: integer := 5;\n   RealValue: real := 2.5;\n   Result: real := 0.0;",
        statement="Result = IntValue + RealValue;",
    )

    result = _write_and_validate(tmp_path, "IntPlusRealArithmetic.s", code)

    assert result.ok is True, result.message


def test_string_plus_int_arithmetic_rejected(tmp_path):
    code = _program(
        declarations='   StringValue: string := "hello";\n   IntValue: integer := 5;\n   Result: string := "";',
        statement="Result = StringValue + IntValue;",
    )

    result = _write_and_validate(tmp_path, "StringPlusIntArithmetic.s", code)

    _assert_validation_error(result, "arithmetic", "string")


def test_boolean_plus_int_arithmetic_rejected(tmp_path):
    code = _program(
        declarations="   BoolValue: boolean := True;\n   IntValue: integer := 5;\n   Result: integer := 0;",
        statement="Result = BoolValue + IntValue;",
    )

    result = _write_and_validate(tmp_path, "BoolPlusIntArithmetic.s", code)

    _assert_validation_error(result, "arithmetic", "boolean")


def test_int_div_real_arithmetic_expression(tmp_path):
    code = _program(
        declarations="   IntValue: integer := 10;\n   RealValue: real := 2.5;\n   Result: real := 0.0;",
        statement="Result = IntValue / RealValue;",
    )

    result = _write_and_validate(tmp_path, "IntDivRealArithmetic.s", code)

    assert result.ok is True, result.message


def test_string_concat_assignment_rejected(tmp_path):
    code = _program(
        declarations='   StringValue: string := "";\n   IntValue: integer := 42;',
        statement="StringValue = IntValue;",
    )

    result = _write_and_validate(tmp_path, "StringConcatRejected.s", code)

    _assert_validation_error(result, "assignment to string", "copystring")


def test_int_comparison_with_real(tmp_path):
    code = _program(
        declarations="   IntValue: integer := 5;\n   RealValue: real := 5.0;\n   Result: boolean := False;",
        statement="Result = IntValue > RealValue;",
    )

    result = _write_and_validate(tmp_path, "IntCompareReal.s", code)

    assert result.ok is True, result.message


def test_string_comparison_with_int_rejected(tmp_path):
    code = _program(
        declarations='   StringValue: string := "5";\n   IntValue: integer := 5;\n   Result: boolean := False;',
        statement="Result = StringValue == IntValue;",
    )

    result = _write_and_validate(tmp_path, "StringCompareInt.s", code)

    _assert_validation_error(result, "comparison")
