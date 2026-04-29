"""Tests for R2.1: Complete strict expression and assignment semantics.

Covers:
- INT -> REAL coercion (allowed as implicit widening)
- REAL -> INT assignment (must be rejected)
- INT/REAL mixing in arithmetic (lenient for legacy code)
- INT/REAL mixing in comparison (lenient for legacy code)
- String arithmetic operations (rejected)
- Expression type inference consistency
"""

from pathlib import Path

import pytest

from sattlint.engine import (
    StructuralValidationError,
    validate_single_file_syntax,
)


def _write_and_validate(tmp_path: Path, filename: str, code: str) -> object:
    """Helper to write code and run validation, returning result or raising."""
    source_file = tmp_path / filename
    source_file.write_text(code)
    return validate_single_file_syntax(source_file)


def test_int_to_real_coercion_allowed_in_assignment(tmp_path):
    """INT -> REAL coercion should be allowed (implicit widening for legacy compatibility)."""
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0, 0.0, 0.0, 1.0, 1.0) : MODULEDEFINITION Test_ 1
LOCALVARIABLES
    IntValue: integer := 42;
    RealValue: real := 0.0;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
        RealValue = IntValue;
ENDDEF (*BasePicture*);
"""
    source_file = tmp_path / "IntToRealCoercion.s"
    source_file.write_text(code, encoding="utf-8")
    # Should NOT raise - INT -> REAL is allowed
    result = validate_single_file_syntax(source_file)
    assert result.ok is True, f"Expected ok but got: {result.message}"


def test_real_to_int_assignment_rejected(tmp_path):
    """REAL -> INT assignment should be rejected (requires explicit conversion)."""
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0, 0.0, 0.0, 1.0, 1.0) : MODULEDEFINITION Test_ 1
LOCALVARIABLES
    RealValue: real := 42.5;
    IntValue: integer := 0;
ModuleDef
ClippingBounds = (-1.0, -1.0) (1.0, 1.0)
ModuleCode
EQUATIONBLOCK
    IntValue := RealValue;
ENDBLOCK
ENDCODE
ENDDEF
"""
    # Should raise - REAL -> INT requires explicit Round()
    with pytest.raises(StructuralValidationError) as exc_info:
        _write_and_validate(tmp_path, "RealToIntAssignment.s", code)
    assert "real" in str(exc_info.value).lower() and "integer" in str(exc_info.value).lower()


def test_int_plus_real_arithmetic_expression(tmp_path):
    """INT + REAL mixing in arithmetic (lenient for legacy code but should track intent)."""
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0, 0.0, 0.0, 1.0, 1.0) : MODULEDEFINITION Test_ 1
LOCALVARIABLES
    IntValue: integer := 5;
    RealValue: real := 2.5;
    Result: real := 0.0;
ModuleDef
ClippingBounds = (-1.0, -1.0) (1.0, 1.0)
ModuleCode
EQUATIONBLOCK
    Result := IntValue + RealValue;
ENDBLOCK
ENDCODE
ENDDEF
"""
    # Should pass - INT/REAL mixing in arithmetic allowed for legacy code
    result = _write_and_validate(tmp_path, "IntPlusRealArithmetic.s", code)
    assert result is None


def test_string_plus_int_arithmetic_rejected(tmp_path):
    """STRING + INT arithmetic should be rejected (no string arithmetic)."""
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0, 0.0, 0.0, 1.0, 1.0) : MODULEDEFINITION Test_ 1
LOCALVARIABLES
    StringValue: string := "hello";
    IntValue: integer := 5;
    Result: string := "";
ModuleDef
ClippingBounds = (-1.0, -1.0) (1.0, 1.0)
ModuleCode
EQUATIONBLOCK
    Result := StringValue + IntValue;
ENDBLOCK
ENDCODE
ENDDEF
"""
    # Should raise - STRING arithmetic not supported
    with pytest.raises(StructuralValidationError) as exc_info:
        _write_and_validate(tmp_path, "StringPlusIntArithmetic.s", code)
    assert "arithmetic" in str(exc_info.value).lower() or "string" in str(exc_info.value).lower()


def test_boolean_plus_int_arithmetic_rejected(tmp_path):
    """BOOLEAN + INT arithmetic should be rejected."""
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0, 0.0, 0.0, 1.0, 1.0) : MODULEDEFINITION Test_ 1
LOCALVARIABLES
    BoolValue: boolean := True;
    IntValue: integer := 5;
    Result: integer := 0;
ModuleDef
ClippingBounds = (-1.0, -1.0) (1.0, 1.0)
ModuleCode
EQUATIONBLOCK
    Result := BoolValue + IntValue;
ENDBLOCK
ENDCODE
ENDDEF
"""
    # Should raise - BOOLEAN arithmetic not allowed
    with pytest.raises(StructuralValidationError) as exc_info:
        _write_and_validate(tmp_path, "BoolPlusIntArithmetic.s", code)
    assert "arithmetic" in str(exc_info.value).lower() and "boolean" in str(exc_info.value).lower()


def test_int_div_real_arithmetic_expression(tmp_path):
    """INT / REAL mixing in division (lenient for legacy code)."""
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0, 0.0, 0.0, 1.0, 1.0) : MODULEDEFINITION Test_ 1
LOCALVARIABLES
    IntValue: integer := 10;
    RealValue: real := 2.5;
    Result: real := 0.0;
ModuleDef
ClippingBounds = (-1.0, -1.0) (1.0, 1.0)
ModuleCode
EQUATIONBLOCK
    Result := IntValue / RealValue;
ENDBLOCK
ENDCODE
ENDDEF
"""
    # Should pass - INT/REAL mixing in division allowed for legacy code
    result = _write_and_validate(tmp_path, "IntDivRealArithmetic.s", code)
    assert result is None


def test_string_concat_assignment_rejected(tmp_path):
    """String concatenation via assignment (assignment to STRING with non-string value)."""
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0, 0.0, 0.0, 1.0, 1.0) : MODULEDEFINITION Test_ 1
LOCALVARIABLES
    StringValue: string := "";
    IntValue: integer := 42;
ModuleDef
ClippingBounds = (-1.0, -1.0) (1.0, 1.0)
ModuleCode
EQUATIONBLOCK
    StringValue := IntValue;
ENDBLOCK
ENDCODE
ENDDEF
"""
    # Should raise - cannot assign integer to string
    with pytest.raises(StructuralValidationError) as exc_info:
        _write_and_validate(tmp_path, "StringConcatRejected.s", code)
    assert "string" in str(exc_info.value).lower()


def test_int_comparison_with_real(tmp_path):
    """INT compared with REAL (lenient for legacy code)."""
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0, 0.0, 0.0, 1.0, 1.0) : MODULEDEFINITION Test_ 1
LOCALVARIABLES
    IntValue: integer := 5;
    RealValue: real := 5.0;
    Result: boolean := False;
ModuleDef
ClippingBounds = (-1.0, -1.0) (1.0, 1.0)
ModuleCode
EQUATIONBLOCK
    Result := IntValue > RealValue;
ENDBLOCK
ENDCODE
ENDDEF
"""
    # Should pass - INT/REAL comparison allowed for legacy code
    result = _write_and_validate(tmp_path, "IntCompareReal.s", code)
    assert result is None


def test_string_comparison_with_int_rejected(tmp_path):
    """STRING compared with INT should be rejected."""
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0, 0.0, 0.0, 1.0, 1.0) : MODULEDEFINITION Test_ 1
LOCALVARIABLES
    StringValue: string := "5";
    IntValue: integer := 5;
    Result: boolean := False;
ModuleDef
ClippingBounds = (-1.0, -1.0) (1.0, 1.0)
ModuleCode
EQUATIONBLOCK
    Result := StringValue == IntValue;
ENDBLOCK
ENDCODE
ENDDEF
"""
    # Should raise - STRING/INT comparison not allowed
    with pytest.raises(StructuralValidationError) as exc_info:
        _write_and_validate(tmp_path, "StringCompareInt.s", code)
    assert "comparison" in str(exc_info.value).lower() or "compatible" in str(exc_info.value).lower()
