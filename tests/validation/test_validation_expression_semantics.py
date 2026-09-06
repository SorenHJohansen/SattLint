# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportPrivateUsage=false, reportArgumentType=false, reportIndexIssue=false
"""Expression semantics validation tests for ``validation/expression.py``.

Covers logical-operand typing, arithmetic and comparison typing,
division-by-zero rejection, and builtin call signature / string-literal rules.
"""

from __future__ import annotations

import pytest
from sattline_parser.models.ast_model import IntLiteral, Simple_DataType, Variable
from sattline_parser.models.expressions import BinOp, BoolOp, Compare, FuncCall, NotOp, VarRef

from sattlint.resolution.type_graph import TypeGraph
from sattlint.validation.expression import (
    _validate_builtin_call_signature,
    _validate_call_arg_node,
    _validate_expression_semantics,
    _validate_no_string_literals_in_calls,
)
from sattlint.validation.shared import StructuralValidationError

CONTEXT = "test equation"

BOOL_VAR = Variable(name="Flag", datatype=Simple_DataType.BOOLEAN)
INT_VAR = Variable(name="Counter", datatype=Simple_DataType.INTEGER)
REAL_VAR = Variable(name="Rate", datatype=Simple_DataType.REAL)
STR_VAR = Variable(name="Label", datatype=Simple_DataType.IDENTSTRING)

TYPE_GRAPH = TypeGraph.from_datatypes([])


def _env(*variables: Variable) -> dict[str, Variable]:
    return {variable.name.casefold(): variable for variable in variables}


def test_boolop_rejects_non_boolean_operand() -> None:
    node = BoolOp(op="AND", operands=(VarRef("Counter"), VarRef("Flag")))
    with pytest.raises(StructuralValidationError, match="logical operator"):
        _validate_expression_semantics(node, _env(INT_VAR, BOOL_VAR), TYPE_GRAPH, CONTEXT)


def test_boolop_accepts_boolean_operands() -> None:
    node = BoolOp(op="AND", operands=(VarRef("Flag"), NotOp(operand=VarRef("Flag"))))
    _validate_expression_semantics(node, _env(BOOL_VAR), TYPE_GRAPH, CONTEXT)


def test_notop_rejects_non_boolean_operand() -> None:
    node = NotOp(operand=VarRef("Counter"))
    with pytest.raises(StructuralValidationError, match="boolean operand"):
        _validate_expression_semantics(node, _env(INT_VAR), TYPE_GRAPH, CONTEXT)


def test_compare_rejects_incompatible_operand_types() -> None:
    node = Compare(left=VarRef("Label"), op="==", right=VarRef("Counter"))
    with pytest.raises(StructuralValidationError, match="compatible operands"):
        _validate_expression_semantics(node, _env(STR_VAR, INT_VAR), TYPE_GRAPH, CONTEXT)


def test_ordering_compare_rejects_non_numeric_operand() -> None:
    node = Compare(left=VarRef("Label"), op="<", right=VarRef("Label"))
    with pytest.raises(StructuralValidationError, match="numeric operands"):
        _validate_expression_semantics(node, _env(STR_VAR), TYPE_GRAPH, CONTEXT)


def test_binop_rejects_non_numeric_operand() -> None:
    node = BinOp(left=VarRef("Label"), op="+", right=VarRef("Label"))
    with pytest.raises(StructuralValidationError, match="numeric operands"):
        _validate_expression_semantics(node, _env(STR_VAR), TYPE_GRAPH, CONTEXT)


def test_binop_rejects_division_by_zero() -> None:
    node = BinOp(left=VarRef("Counter"), op="/", right=IntLiteral(0))
    with pytest.raises(StructuralValidationError, match="division by zero"):
        _validate_expression_semantics(node, _env(INT_VAR), TYPE_GRAPH, CONTEXT)


def test_valid_numeric_arithmetic_passes() -> None:
    node = BinOp(left=VarRef("Counter"), op="+", right=VarRef("Rate"))
    _validate_expression_semantics(node, _env(INT_VAR, REAL_VAR), TYPE_GRAPH, CONTEXT)


def test_builtin_call_arity_mismatch_raises() -> None:
    with pytest.raises(StructuralValidationError, match="arguments"):
        _validate_builtin_call_signature(
            "abs",
            [VarRef("Counter"), VarRef("Rate")],
            _env(INT_VAR, REAL_VAR),
            TYPE_GRAPH,
            CONTEXT,
        )


def test_builtin_call_matches_arity() -> None:
    _validate_builtin_call_signature("abs", [VarRef("Counter")], _env(INT_VAR), TYPE_GRAPH, CONTEXT)


def test_builtin_inout_parameter_requires_variable_ref() -> None:
    args = [1, True, True, True, True, VarRef("Counter")]
    with pytest.raises(StructuralValidationError, match="variable reference"):
        _validate_builtin_call_signature("acof1", args, _env(INT_VAR), TYPE_GRAPH, CONTEXT)


def test_string_literal_in_call_arg_raises() -> None:
    with pytest.raises(StructuralValidationError, match="string literal"):
        _validate_call_arg_node("Hello", "ctx")


def test_call_arg_varref_passes() -> None:
    _validate_call_arg_node(VarRef("Counter"), "ctx")


def test_func_call_with_string_literal_raises() -> None:
    call = FuncCall(name="SetSomething", args=(VarRef("Counter"), "literal"))
    with pytest.raises(StructuralValidationError, match="string literal"):
        _validate_no_string_literals_in_calls(call, CONTEXT)
