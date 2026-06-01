from types import SimpleNamespace

from lark import Tree

from sattlint import _validation_expression as validation_expression_module
from sattlint import _validation_type_helpers as type_helpers_module

# ruff: noqa: F403, F405
from ._parser_validation_test_support import *


def _validation_expression_graph() -> TypeGraph:
    return TypeGraph.from_datatypes(
        [
            DataType(
                name="InnerRecord",
                description=None,
                datecode=1,
                var_list=[
                    Variable(name="Leaf", datatype=Simple_DataType.BOOLEAN, state=True),
                    Variable(name="Weight", datatype=Simple_DataType.REAL),
                ],
            ),
            DataType(
                name="OuterRecord",
                description=None,
                datecode=1,
                var_list=[
                    Variable(name="Inner", datatype="InnerRecord"),
                    Variable(name="Counter", datatype=Simple_DataType.INTEGER),
                ],
            ),
        ]
    )


def _validation_expression_env() -> dict[str, Variable]:
    return {
        "count": Variable(name="Count", datatype=Simple_DataType.INTEGER),
        "flag": Variable(name="Flag", datatype=Simple_DataType.BOOLEAN),
        "ratio": Variable(name="Ratio", datatype=Simple_DataType.REAL),
        "stamp": Variable(name="Stamp", datatype=Simple_DataType.TIME),
        "config": Variable(name="Config", datatype="OuterRecord", state=True),
        "consttext": Variable(name="ConstText", datatype=Simple_DataType.STRING, const=True),
    }


def _builtin_parameter(name: str, direction: str, datatype: str) -> SimpleNamespace:
    return SimpleNamespace(name=name, direction=direction, datatype=datatype)


def _builtin(*parameters: SimpleNamespace, return_type: str | None = None) -> SimpleNamespace:
    return SimpleNamespace(parameters=list(parameters), return_type=return_type)


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


def test_validation_type_helpers_cover_predicates_literals_and_matching() -> None:
    graph = _validation_expression_graph()
    env = _validation_expression_env()
    time_literal = {validation_module.const.GRAMMAR_VALUE_TIME_VALUE: "2024-01-02-03:04:05.006"}

    assert type_helpers_module._is_duration_datatype(Simple_DataType.DURATION) is True
    assert type_helpers_module._is_duration_datatype("duration") is True
    assert type_helpers_module._is_duration_datatype(Simple_DataType.TIME) is False
    assert type_helpers_module._is_time_datatype(Simple_DataType.TIME) is True
    assert type_helpers_module._is_time_datatype("time") is True
    assert type_helpers_module._is_time_datatype(None) is False

    assert type_helpers_module._is_valid_duration_literal("15") is True
    assert type_helpers_module._is_valid_duration_literal("+1d2h3m4.5s6ms") is True
    assert type_helpers_module._is_valid_duration_literal(object()) is False
    assert type_helpers_module._is_valid_duration_literal("   ") is False
    assert type_helpers_module._is_valid_duration_literal("+") is False
    assert type_helpers_module._is_valid_duration_literal("bad") is False
    assert type_helpers_module._has_time_literal_marker(time_literal) is True
    assert type_helpers_module._has_time_literal_marker({}) is False
    assert type_helpers_module._extract_time_literal(time_literal) == "2024-01-02-03:04:05.006"
    assert type_helpers_module._extract_time_literal("bad") is None
    assert type_helpers_module._extract_time_literal({validation_module.const.GRAMMAR_VALUE_TIME_VALUE: 1}) is None
    assert type_helpers_module._is_valid_time_literal(" 2024-01-02-03:04:05.006 ") is True
    assert type_helpers_module._is_valid_time_literal("bad") is False

    assert type_helpers_module._bounded_levenshtein("Time", "time") == 0
    assert type_helpers_module._bounded_levenshtein("abc", "abcdef", max_distance=1) is None
    assert type_helpers_module._bounded_levenshtein("abc", "xyz", max_distance=1) is None
    assert type_helpers_module._bounded_levenshtein("intege", "integer") == 1
    assert type_helpers_module._suggest_datatype_name("Intege", ("integer", "real")) == "integer"
    assert type_helpers_module._suggest_datatype_name("Timer", ("time", "timerx")) == "timerx"
    assert type_helpers_module._split_dotted_name(".") == ("", ())
    assert type_helpers_module._split_dotted_name("Config.Inner.Leaf") == ("Config", ("Inner", "Leaf"))

    assert (
        type_helpers_module._resolve_variable_field_datatype(env["config"], ("Inner", "Weight"), graph)
        == Simple_DataType.REAL
    )
    assert type_helpers_module._resolve_variable_field_datatype(env["config"], ("Counter", "Leaf"), graph) is None
    assert type_helpers_module._resolve_variable_field_datatype(env["config"], ("Missing",), graph) is None
    assert type_helpers_module._infer_literal_datatype(True) == Simple_DataType.BOOLEAN
    assert type_helpers_module._infer_literal_datatype(1) == Simple_DataType.INTEGER
    assert type_helpers_module._infer_literal_datatype(1.5) == Simple_DataType.REAL
    assert type_helpers_module._infer_literal_datatype("1.5s", is_duration=True) == Simple_DataType.DURATION
    assert type_helpers_module._infer_literal_datatype("text", is_duration=True) == Simple_DataType.STRING
    assert type_helpers_module._infer_literal_datatype(time_literal) == validation_module.const.GRAMMAR_VALUE_TIME_VALUE
    assert type_helpers_module._infer_literal_datatype(object()) is None
    assert type_helpers_module._literal_matches_expected_datatype("1.5s", Simple_DataType.DURATION) is True
    assert (
        type_helpers_module._literal_matches_expected_datatype("2024-01-02-03:04:05.006", Simple_DataType.TIME) is True
    )
    assert (
        type_helpers_module._literal_matches_expected_datatype(
            {validation_module.const.GRAMMAR_VALUE_TIME_VALUE: "bad"},
            Simple_DataType.TIME,
        )
        is False
    )

    assert type_helpers_module._format_datatype(None) == "unknown"
    assert type_helpers_module._format_datatype(Simple_DataType.INTEGER) == "integer"
    assert type_helpers_module._format_datatype("CustomType") == "CustomType"
    assert type_helpers_module._is_string_simple_type(Simple_DataType.STRING) is True
    assert type_helpers_module._is_string_simple_type(Simple_DataType.INTEGER) is False
    assert type_helpers_module._normalize_builtin_datatype("integer") == Simple_DataType.INTEGER
    assert type_helpers_module._normalize_builtin_datatype("CustomType") == "CustomType"
    assert (
        type_helpers_module._resolve_ref_datatype(_var_ref("Config.Inner.Leaf"), env, graph) == Simple_DataType.BOOLEAN
    )
    assert type_helpers_module._resolve_ref_datatype(_var_ref("Config.Inner.Missing"), env, graph) is None
    assert type_helpers_module._resolve_ref_datatype(_var_ref("Config.Counter.Leaf"), env, graph) is None
    assert type_helpers_module._resolve_ref_datatype(_var_ref("Missing"), env, graph) is None
    assert type_helpers_module._resolve_ref_datatype(_var_ref("."), env, graph) is None
    assert type_helpers_module._resolve_root_variable(_var_ref("Config.Inner.Leaf"), env) == env["config"]
    assert type_helpers_module._resolve_root_variable(_var_ref("."), env) is None

    assert type_helpers_module._merge_numeric_types(()) is None
    assert (
        type_helpers_module._merge_numeric_types((Simple_DataType.INTEGER, Simple_DataType.REAL))
        == Simple_DataType.REAL
    )
    assert type_helpers_module._merge_numeric_types((Simple_DataType.INTEGER, "CustomType")) is None
    assert type_helpers_module._is_numeric_datatype(Simple_DataType.REAL) is True
    assert type_helpers_module._is_numeric_datatype(Simple_DataType.BOOLEAN) is False
    assert type_helpers_module._is_boolean_datatype(Simple_DataType.BOOLEAN) is True
    assert type_helpers_module._is_boolean_datatype("boolean") is False
    assert type_helpers_module._merge_compatible_types(()) is None
    assert (
        type_helpers_module._merge_compatible_types((None, Simple_DataType.INTEGER, Simple_DataType.INTEGER))
        == Simple_DataType.INTEGER
    )
    assert (
        type_helpers_module._merge_compatible_types((Simple_DataType.INTEGER, Simple_DataType.REAL))
        == Simple_DataType.REAL
    )
    assert (
        type_helpers_module._merge_compatible_types((Simple_DataType.STRING, Simple_DataType.TAGSTRING))
        == Simple_DataType.STRING
    )
    assert type_helpers_module._merge_compatible_types((Simple_DataType.BOOLEAN, "CustomType")) is None
    assert type_helpers_module._expression_is_zero_literal(0) is True
    assert type_helpers_module._expression_is_zero_literal((validation_module.const.KEY_MINUS, 0.0)) is True
    assert type_helpers_module._expression_is_zero_literal(("OTHER", 0)) is False
    assert type_helpers_module._expression_is_zero_literal(1) is False

    assert type_helpers_module._builtin_type_matches(Simple_DataType.INTEGER, "AnyType", direction="out") is True
    assert (
        type_helpers_module._builtin_type_matches(Simple_DataType.TAGSTRING, Simple_DataType.STRING, direction="in")
        is True
    )
    assert (
        type_helpers_module._builtin_type_matches(Simple_DataType.INTEGER, Simple_DataType.REAL, direction="in") is True
    )
    assert (
        type_helpers_module._builtin_type_matches(Simple_DataType.INTEGER, Simple_DataType.REAL, direction="out")
        is False
    )
    assert type_helpers_module._builtin_type_matches("CustomType", "customtype", direction="in") is True
    assert type_helpers_module._builtin_type_matches("CustomType", Simple_DataType.INTEGER, direction="in") is False
    assert type_helpers_module._builtin_type_matches(Simple_DataType.INTEGER, "customtype", direction="in") is False

    assert type_helpers_module._assignment_type_matches(None, Simple_DataType.INTEGER) is True
    assert type_helpers_module._assignment_type_matches("AnyType", Simple_DataType.INTEGER) is True
    assert type_helpers_module._assignment_type_matches(Simple_DataType.INTEGER, "AnyType") is True
    assert (
        type_helpers_module._assignment_type_matches(
            validation_module.const.GRAMMAR_VALUE_TIME_VALUE, Simple_DataType.TIME
        )
        is True
    )
    assert (
        type_helpers_module._assignment_type_matches(
            validation_module.const.GRAMMAR_VALUE_TIME_VALUE, Simple_DataType.INTEGER
        )
        is False
    )
    assert type_helpers_module._assignment_type_matches("CustomType", Simple_DataType.INTEGER) is False
    assert type_helpers_module._assignment_type_matches(Simple_DataType.INTEGER, "CustomType") is False
    assert type_helpers_module._assignment_type_matches("CustomType", "customtype") is True


def test_validation_expression_helpers_cover_iterators_and_type_inference(monkeypatch) -> None:
    graph = _validation_expression_graph()
    env = _validation_expression_env()
    monkeypatch.setattr(
        validation_expression_module,
        "SATTLINE_BUILTINS",
        {
            "compute": _builtin(return_type="integer"),
            "sink": _builtin(return_type=None),
        },
    )

    assert validation_expression_module._is_variable_ref_node(_var_ref("Count")) is True
    assert validation_expression_module._is_variable_ref_node({"other": "Count"}) is False
    assert validation_expression_module._as_expression_tuple(("tag", 1)) == ("tag", 1)
    assert validation_expression_module._as_expression_tuple([]) is None
    assert validation_expression_module._iter_tree_children(Tree("expr", [1, 2])) == (1, 2)
    assert validation_expression_module._iter_tree_children("expr") == ()
    assert validation_expression_module._iter_list_items([1, 2]) == (1, 2)
    assert validation_expression_module._iter_list_items("expr") == ()
    assert validation_expression_module._iter_mapping_values({"a": 1, "b": 2}) == (1, 2)
    assert validation_expression_module._iter_mapping_values("expr") == ()
    assert validation_expression_module._iter_expression_pairs([("=", 1), ("broken",), 3]) == (("=", 1),)

    assert validation_expression_module._infer_expression_datatype(True, env, graph) == Simple_DataType.BOOLEAN
    assert validation_expression_module._infer_expression_datatype(1, env, graph) == Simple_DataType.INTEGER
    assert validation_expression_module._infer_expression_datatype(1.5, env, graph) == Simple_DataType.REAL
    assert validation_expression_module._infer_expression_datatype("text", env, graph) == Simple_DataType.STRING
    assert (
        validation_expression_module._infer_expression_datatype(_var_ref("Config.Inner.Leaf"), env, graph)
        == Simple_DataType.BOOLEAN
    )
    assert validation_expression_module._infer_expression_datatype({"wrapped": 1}, env, graph) is None
    assert (
        validation_expression_module._infer_expression_datatype(
            (validation_module.const.KEY_FUNCTION_CALL, "Compute", []),
            env,
            graph,
        )
        == Simple_DataType.INTEGER
    )
    assert (
        validation_expression_module._infer_expression_datatype(
            (validation_module.const.KEY_FUNCTION_CALL, "Sink", []),
            env,
            graph,
        )
        is None
    )
    assert (
        validation_expression_module._infer_expression_datatype(
            (validation_module.const.KEY_COMPARE, _var_ref("Count"), [("<", 1)]),
            env,
            graph,
        )
        == Simple_DataType.BOOLEAN
    )
    assert (
        validation_expression_module._infer_expression_datatype(
            (validation_module.const.GRAMMAR_VALUE_AND, [_var_ref("Flag"), True]),
            env,
            graph,
        )
        == Simple_DataType.BOOLEAN
    )
    assert (
        validation_expression_module._infer_expression_datatype(
            (validation_module.const.KEY_ADD, _var_ref("Count"), [("+", 1.5)]),
            env,
            graph,
        )
        == Simple_DataType.REAL
    )
    assert (
        validation_expression_module._infer_expression_datatype(
            (validation_module.const.KEY_PLUS, _var_ref("Count")),
            env,
            graph,
        )
        == Simple_DataType.INTEGER
    )
    assert (
        validation_expression_module._infer_expression_datatype(
            (validation_module.const.KEY_TERNARY, [(_var_ref("Flag"), 1), (_var_ref("Flag"), 2.5)], 3),
            env,
            graph,
        )
        == Simple_DataType.REAL
    )
    assert validation_expression_module._infer_expression_datatype(("unknown",), env, graph) is None


@pytest.mark.parametrize(
    ("node", "expected_message"),
    [
        (
            (validation_module.const.KEY_COMPARE, _var_ref("Count"), [("=", _var_ref("Flag"))]),
            "expects compatible operands",
        ),
        (
            (validation_module.const.KEY_COMPARE, _var_ref("Flag"), [("<", _var_ref("Count"))]),
            "left side has datatype 'boolean'",
        ),
        (
            (validation_module.const.KEY_COMPARE, _var_ref("Count"), [("<", _var_ref("Flag"))]),
            "right side has datatype 'boolean'",
        ),
        (
            (validation_module.const.GRAMMAR_VALUE_AND, [_var_ref("Count")]),
            "logical operator 'AND' expects boolean operands",
        ),
        (
            (validation_module.const.GRAMMAR_VALUE_NOT, _var_ref("Count")),
            "logical operator 'NOT' expects a boolean operand",
        ),
        (
            (validation_module.const.KEY_ADD, _var_ref("Flag"), [("+", 1)]),
            "arithmetic expression expects numeric operands",
        ),
        (
            (validation_module.const.KEY_ADD, _var_ref("Count"), [("+", _var_ref("Flag"))]),
            r"arithmetic operator '\+' expects numeric operands",
        ),
        (
            (validation_module.const.KEY_MUL, _var_ref("Count"), [("/", 0)]),
            "division by zero is not allowed",
        ),
        (
            (validation_module.const.KEY_MINUS, _var_ref("Flag")),
            "unary operator 'MINUS' expects a numeric operand",
        ),
        (
            (validation_module.const.KEY_TERNARY, [(_var_ref("Flag"), 1)], _var_ref("Flag")),
            "IF-expression branches must have compatible datatypes",
        ),
    ],
)
def test_validation_expression_semantics_reports_expected_errors(node: object, expected_message: str) -> None:
    with pytest.raises(StructuralValidationError, match=expected_message):
        validation_expression_module._validate_expression_semantics(
            node,
            _validation_expression_env(),
            _validation_expression_graph(),
            "test expression",
        )


def test_validation_expression_semantics_walks_supported_nested_shapes() -> None:
    validation_expression_module._validate_expression_semantics(
        Tree(
            "root",
            [
                [
                    {"expr": (1, _var_ref("Count"))},
                    (validation_module.const.KEY_ASSIGN, _var_ref("Count"), 1),
                    (validation_module.const.KEY_FUNCTION_CALL, "NoOp", [_var_ref("Count")]),
                    ("fallback", Tree("leaf", [True]), [False], {"nested": _var_ref("Flag")}),
                    (validation_module.const.GRAMMAR_VALUE_OR, _var_ref("Flag")),
                ]
            ],
        ),
        _validation_expression_env(),
        _validation_expression_graph(),
        "test expression",
    )


def test_validation_expression_semantics_accepts_valid_compare_not_and_arithmetic_paths() -> None:
    env = _validation_expression_env()
    graph = _validation_expression_graph()

    validation_expression_module._validate_expression_semantics(
        (validation_module.const.KEY_COMPARE, _var_ref("Count"), [("<", 1), ("<", 2)]),
        env,
        graph,
        "test expression",
    )
    validation_expression_module._validate_expression_semantics(
        (validation_module.const.GRAMMAR_VALUE_NOT, _var_ref("Flag")),
        env,
        graph,
        "test expression",
    )
    validation_expression_module._validate_expression_semantics(
        (validation_module.const.KEY_ADD, _var_ref("Count"), [("+", 1)]),
        env,
        graph,
        "test expression",
    )
    validation_expression_module._validate_expression_semantics(
        (validation_module.const.KEY_PLUS, _var_ref("Count")),
        env,
        graph,
        "test expression",
    )

    assert validation_expression_module._infer_expression_datatype((), env, graph) is None


def test_validation_expression_builtin_signature_covers_edge_branches(monkeypatch) -> None:
    env = _validation_expression_env()
    graph = _validation_expression_graph()
    monkeypatch.setattr(
        validation_expression_module,
        "SATTLINE_BUILTINS",
        {
            "acceptreal": _builtin(_builtin_parameter("value", "in", "real")),
            "writeref": _builtin(_builtin_parameter("target", "out", "integer")),
            "setstringpos": _builtin(_builtin_parameter("text", "out", "string")),
            "sinkunknown": _builtin(_builtin_parameter("value", "in", "integer")),
        },
    )

    validation_expression_module._validate_builtin_call_signature(None, [], env, graph, "ctx")
    validation_expression_module._validate_builtin_call_signature("missing", [], env, graph, "ctx")

    with pytest.raises(StructuralValidationError, match="builtin expects 1"):
        validation_expression_module._validate_builtin_call_signature("acceptreal", [], env, graph, "ctx")

    with pytest.raises(StructuralValidationError, match="must be a variable reference"):
        validation_expression_module._validate_builtin_call_signature("writeref", [1], env, graph, "ctx")

    with pytest.raises(StructuralValidationError, match="writes to CONST variable"):
        validation_expression_module._validate_builtin_call_signature(
            "writeref", [_var_ref("ConstText")], env, graph, "ctx"
        )

    validation_expression_module._validate_builtin_call_signature(
        "setstringpos", [_var_ref("ConstText")], env, graph, "ctx"
    )
    validation_expression_module._validate_builtin_call_signature(
        "sinkunknown", [{"value": object()}], env, graph, "ctx"
    )
    validation_expression_module._validate_builtin_call_signature("acceptreal", [1], env, graph, "ctx")

    with pytest.raises(StructuralValidationError, match="expects 'real'"):
        validation_expression_module._validate_builtin_call_signature(
            "acceptreal", [_var_ref("Flag")], env, graph, "ctx"
        )


def test_validation_expression_string_literal_walkers_cover_nested_structures(monkeypatch) -> None:
    env = _validation_expression_env()
    graph = _validation_expression_graph()
    monkeypatch.setattr(
        validation_expression_module,
        "SATTLINE_BUILTINS",
        {
            "acceptreal": _builtin(_builtin_parameter("value", "in", "real")),
        },
    )

    with pytest.raises(StructuralValidationError, match="string literals are only allowed"):
        validation_expression_module._validate_call_arg_node("literal", "ctx")

    validation_expression_module._validate_call_arg_node({"wrapped": _var_ref("Count")}, "ctx")
    validation_expression_module._validate_call_arg_node(Tree("root", [[_var_ref("Flag")]]), "ctx")
    validation_expression_module._validate_call_arg_node(
        (
            validation_module.const.KEY_FUNCTION_CALL,
            "CopyString",
            [_var_ref("ConstText"), _var_ref("ConstText"), _var_ref("Count")],
        ),
        "ctx",
    )

    with pytest.raises(StructuralValidationError, match="call 'CopyString' argument 1"):
        validation_expression_module._validate_no_string_literals_in_calls(
            Tree(
                "root",
                [
                    {
                        "expr": [
                            (
                                validation_module.const.KEY_FUNCTION_CALL,
                                "CopyString",
                                ["literal", _var_ref("ConstText"), _var_ref("Count")],
                            )
                        ]
                    }
                ],
            ),
            "ctx",
        )

    validation_expression_module._validate_no_string_literals_in_calls(_var_ref("Count"), "ctx")
    validation_expression_module._validate_no_string_literals_in_calls(
        Tree(
            "root",
            [
                [
                    {
                        "expr": (
                            validation_module.const.KEY_FUNCTION_CALL,
                            "CopyString",
                            [_var_ref("ConstText"), _var_ref("ConstText"), _var_ref("Count")],
                        )
                    }
                ]
            ],
        ),
        "ctx",
    )
    validation_expression_module._validate_builtin_call_types(_var_ref("Count"), env, graph, "ctx")
    validation_expression_module._validate_builtin_call_types(
        Tree(
            "root",
            [
                {
                    "expr": [
                        (
                            validation_module.const.KEY_FUNCTION_CALL,
                            "AcceptReal",
                            [1],
                        )
                    ]
                }
            ],
        ),
        env,
        graph,
        "ctx",
    )
