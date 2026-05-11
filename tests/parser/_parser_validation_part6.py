# ruff: noqa: F403, F405
from ._parser_validation_test_support import *


def test_validate_single_file_syntax_rejects_builtin_arity_mismatch(tmp_path):
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    Name1: string;
    Name2: string;
    Match: boolean := False;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
        Match = EqualStrings(Name1, Name2);
ENDDEF (*BasePicture*);
"""
    source_file = tmp_path / "BuiltinArityMismatch.s"
    source_file.write_text(code, encoding="utf-8")

    result = validate_single_file_syntax(source_file)

    assert result.ok is False
    assert result.stage == "validation"
    assert result.message is not None
    assert "call 'EqualStrings' has 2 arguments but builtin expects 3" in result.message


def test_validate_single_file_syntax_rejects_builtin_in_var_expression(tmp_path):
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    SourceTime: time;
    DestinationTime: time;
    UseSource: boolean := False;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
        CopyTime(IF UseSource THEN SourceTime ELSE SourceTime ENDIF, DestinationTime);
ENDDEF (*BasePicture*);
"""
    source_file = tmp_path / "BuiltinInVarExpression.s"
    source_file.write_text(code, encoding="utf-8")

    result = validate_single_file_syntax(source_file)

    assert result.ok is False
    assert result.stage == "validation"
    assert result.message is not None
    assert "call 'CopyTime' argument 1 must be a variable reference" in result.message
    assert "is 'in var'" in result.message


def test_validate_single_file_syntax_rejects_builtin_out_expression(tmp_path):
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    SourceTime: time;
    DestinationTime: time;
    UseDestination: boolean := False;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
        CopyTime(SourceTime, IF UseDestination THEN DestinationTime ELSE DestinationTime ENDIF);
ENDDEF (*BasePicture*);
"""
    source_file = tmp_path / "BuiltinOutExpression.s"
    source_file.write_text(code, encoding="utf-8")

    result = validate_single_file_syntax(source_file)

    assert result.ok is False
    assert result.stage == "validation"
    assert result.message is not None
    assert "call 'CopyTime' argument 2 must be a variable reference" in result.message
    assert "is 'out'" in result.message


def test_validate_single_file_syntax_rejects_string_assignment(tmp_path):
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    StrA: string := "Hello";
    StrB: string := "World";
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
        StrA = StrB;
ENDDEF (*BasePicture*);
"""
    source_file = tmp_path / "StringAssignment.s"
    source_file.write_text(code, encoding="utf-8")

    result = validate_single_file_syntax(source_file)

    assert result.ok is False
    assert result.stage == "validation"
    assert result.message is not None
    assert "assignment to string variable 'StrA' is not allowed" in result.message
    assert "CopyString" in result.message


def test_validate_single_file_syntax_rejects_real_assignment_to_integer(tmp_path):
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    OperatorSetpoint: real := 50.0;
    Output: integer := 0;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
        Output = OperatorSetpoint;
ENDDEF (*BasePicture*);
"""
    source_file = tmp_path / "RealToIntegerAssignment.s"
    source_file.write_text(code, encoding="utf-8")

    result = validate_single_file_syntax(source_file)

    assert result.ok is False
    assert result.stage == "validation"
    assert result.message is not None
    assert (
        "assigns 'OperatorSetpoint' with datatype 'real' to target 'Output' with datatype 'integer'" in result.message
    )


def test_validate_single_file_syntax_rejects_arithmetic_with_boolean_operand(tmp_path):
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    Count: integer := 0;
    Flag: boolean := False;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
        Count = Count + Flag;
ENDDEF (*BasePicture*);
"""
    source_file = tmp_path / "ArithmeticBooleanOperand.s"
    source_file.write_text(code, encoding="utf-8")

    result = validate_single_file_syntax(source_file)

    assert result.ok is False
    assert result.stage == "validation"
    assert result.message is not None
    assert "arithmetic operator '+' expects numeric operands" in result.message


def test_validate_single_file_syntax_rejects_logical_with_integer_operand(tmp_path):
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    Count: integer := 0;
    Flag: boolean := False;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
        Flag = Count AND True;
ENDDEF (*BasePicture*);
"""
    source_file = tmp_path / "LogicalIntegerOperand.s"
    source_file.write_text(code, encoding="utf-8")

    result = validate_single_file_syntax(source_file)

    assert result.ok is False
    assert result.stage == "validation"
    assert result.message is not None
    assert "logical operator 'AND' expects boolean operands" in result.message


def test_validate_single_file_syntax_rejects_comparison_with_boolean_operand(tmp_path):
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    Left: boolean := False;
    Right: boolean := True;
    Flag: boolean := False;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
        Flag = Left < Right;
ENDDEF (*BasePicture*);
"""
    source_file = tmp_path / "ComparisonBooleanOperand.s"
    source_file.write_text(code, encoding="utf-8")

    result = validate_single_file_syntax(source_file)

    assert result.ok is False
    assert result.stage == "validation"
    assert result.message is not None
    assert "comparison expects numeric operands" in result.message


def test_validate_single_file_syntax_rejects_division_by_zero_literal(tmp_path):
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    Count: integer := 0;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
        Count = Count / 0;
ENDDEF (*BasePicture*);
"""
    source_file = tmp_path / "DivisionByZeroLiteral.s"
    source_file.write_text(code, encoding="utf-8")

    result = validate_single_file_syntax(source_file)

    assert result.ok is False
    assert result.stage == "validation"
    assert result.message is not None
    assert "division by zero is not allowed" in result.message


def test_validate_single_file_syntax_rejects_if_expression_with_incompatible_branches(tmp_path):
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    Count: integer := 0;
    Flag: boolean := False;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
        Count = IF Flag THEN Count ELSE Flag ENDIF;
ENDDEF (*BasePicture*);
"""
    source_file = tmp_path / "IfBranchTypeMismatch.s"
    source_file.write_text(code, encoding="utf-8")

    result = validate_single_file_syntax(source_file)

    assert result.ok is False
    assert result.stage == "validation"
    assert result.message is not None
    assert "IF-expression branches must have compatible datatypes" in result.message


def test_validate_single_file_syntax_allows_copystring_for_string_copy(tmp_path):
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    StrA: string := "Hello";
    StrB: string := "World";
    Status: integer := 0;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
        CopyString(StrB, StrA, Status);
ENDDEF (*BasePicture*);
"""
    source_file = tmp_path / "CopyStringAllowed.s"
    source_file.write_text(code, encoding="utf-8")

    result = validate_single_file_syntax(source_file)

    assert result.ok is True
    assert result.stage == "ok"
