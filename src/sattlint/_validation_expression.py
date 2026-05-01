"""Expression semantics validation and builtin call type checking for SattLine."""

from __future__ import annotations

from lark import Tree

from sattline_parser.models.ast_model import (
    FloatLiteral,
    IntLiteral,
    Simple_DataType,
    Variable,
)

from ._validation_shared import StructuralValidationError, _ref_span, _span_kwargs
from ._validation_type_helpers import (
    _builtin_type_matches,
    _expression_is_zero_literal,
    _format_datatype,
    _is_anytype_datatype,
    _is_boolean_datatype,
    _is_numeric_datatype,
    _merge_compatible_types,
    _merge_numeric_types,
    _normalize_builtin_datatype,
    _resolve_ref_datatype,
    _resolve_root_variable,
)
from .analyzers.sattline_builtins import SATTLINE_BUILTINS
from .grammar import constants as const
from .resolution.type_graph import TypeGraph

_EQUALITY_COMPARISON_OPERATORS = {"==", "=", "!=", "<>"}


def _is_variable_ref_node(node: object) -> bool:
    return isinstance(node, dict) and const.KEY_VAR_NAME in node


def _validate_expression_semantics(
    node: object,
    env: dict[str, Variable],
    type_graph: TypeGraph,
    context: str,
) -> None:
    if isinstance(node, Tree):
        for child in node.children:
            _validate_expression_semantics(child, env, type_graph, context)
        return

    if isinstance(node, list):
        for item in node:
            _validate_expression_semantics(item, env, type_graph, context)
        return

    if isinstance(node, dict):
        for value in node.values():
            _validate_expression_semantics(value, env, type_graph, context)
        return

    if not isinstance(node, tuple) or not node:
        return

    tag = node[0]
    if not isinstance(tag, str):
        for item in node:
            _validate_expression_semantics(item, env, type_graph, context)
        return

    if tag == const.KEY_ASSIGN and len(node) == 3:
        _validate_expression_semantics(node[2], env, type_graph, context)
        return

    if tag == const.KEY_FUNCTION_CALL and len(node) == 3:
        for argument in node[2] or []:
            _validate_expression_semantics(argument, env, type_graph, context)
        return

    if tag == const.KEY_COMPARE and len(node) == 3:
        left_type = _infer_expression_datatype(node[1], env, type_graph)
        _validate_expression_semantics(node[1], env, type_graph, context)
        for op, rhs in node[2]:
            operator = str(op)
            right_type = _infer_expression_datatype(rhs, env, type_graph)
            if operator in _EQUALITY_COMPARISON_OPERATORS:
                if (
                    left_type is not None
                    and right_type is not None
                    and not _is_anytype_datatype(left_type)
                    and not _is_anytype_datatype(right_type)
                    and _merge_compatible_types((left_type, right_type)) is None
                ):
                    raise StructuralValidationError(
                        f"{context} comparison operator {operator!r} expects compatible operands but got "
                        f"{_format_datatype(left_type)!r} and {_format_datatype(right_type)!r}"
                    )
            else:
                if (
                    left_type is not None
                    and not _is_anytype_datatype(left_type)
                    and not _is_numeric_datatype(left_type)
                ):
                    raise StructuralValidationError(
                        f"{context} comparison expects numeric operands but left side has datatype {_format_datatype(left_type)!r}"
                    )
                if (
                    right_type is not None
                    and not _is_anytype_datatype(right_type)
                    and not _is_numeric_datatype(right_type)
                ):
                    raise StructuralValidationError(
                        f"{context} comparison expects numeric operands but right side has datatype {_format_datatype(right_type)!r}"
                    )
            _validate_expression_semantics(rhs, env, type_graph, context)
            left_type = right_type if right_type is not None else left_type
        return

    if tag in {const.GRAMMAR_VALUE_AND, const.GRAMMAR_VALUE_OR} and len(node) == 2:
        operands = node[1] if isinstance(node[1], list) else [node[1]]
        for operand in operands:
            operand_type = _infer_expression_datatype(operand, env, type_graph)
            if operand_type is not None and not _is_boolean_datatype(operand_type):
                raise StructuralValidationError(
                    f"{context} logical operator {str(tag)!r} expects boolean operands but got {_format_datatype(operand_type)!r}"
                )
            _validate_expression_semantics(operand, env, type_graph, context)
        return

    if tag == const.GRAMMAR_VALUE_NOT and len(node) == 2:
        operand = node[1]
        operand_type = _infer_expression_datatype(operand, env, type_graph)
        if operand_type is not None and not _is_boolean_datatype(operand_type):
            raise StructuralValidationError(
                f"{context} logical operator {str(tag)!r} expects a boolean operand but got {_format_datatype(operand_type)!r}"
            )
        _validate_expression_semantics(operand, env, type_graph, context)
        return

    if tag in {const.KEY_ADD, const.KEY_MUL} and len(node) == 3:
        base_type = _infer_expression_datatype(node[1], env, type_graph)
        if base_type is not None and not _is_anytype_datatype(base_type) and not _is_numeric_datatype(base_type):
            raise StructuralValidationError(
                f"{context} arithmetic expression expects numeric operands but got {_format_datatype(base_type)!r}"
            )
        _validate_expression_semantics(node[1], env, type_graph, context)
        for op, rhs in node[2]:
            rhs_type = _infer_expression_datatype(rhs, env, type_graph)
            if rhs_type is not None and not _is_anytype_datatype(rhs_type) and not _is_numeric_datatype(rhs_type):
                raise StructuralValidationError(
                    f"{context} arithmetic operator {str(op)!r} expects numeric operands but got {_format_datatype(rhs_type)!r}"
                )
            if str(op) == "/" and _expression_is_zero_literal(rhs):
                raise StructuralValidationError(f"{context} division by zero is not allowed")
            _validate_expression_semantics(rhs, env, type_graph, context)
        return

    if tag in {const.KEY_PLUS, const.KEY_MINUS} and len(node) == 2:
        operand = node[1]
        operand_type = _infer_expression_datatype(operand, env, type_graph)
        if (
            operand_type is not None
            and not _is_anytype_datatype(operand_type)
            and not _is_numeric_datatype(operand_type)
        ):
            raise StructuralValidationError(
                f"{context} unary operator {str(tag)!r} expects a numeric operand but got {_format_datatype(operand_type)!r}"
            )
        _validate_expression_semantics(operand, env, type_graph, context)
        return

    if tag == const.KEY_TERNARY and len(node) == 3:
        branch_types: list[Simple_DataType | str | None] = []
        for branch in node[1]:
            if isinstance(branch, tuple) and len(branch) == 2:
                _validate_expression_semantics(branch[0], env, type_graph, context)
                _validate_expression_semantics(branch[1], env, type_graph, context)
                branch_types.append(_infer_expression_datatype(branch[1], env, type_graph))
        _validate_expression_semantics(node[2], env, type_graph, context)
        branch_types.append(_infer_expression_datatype(node[2], env, type_graph))

        known_types = [datatype for datatype in branch_types if datatype is not None]
        if len(known_types) >= 2 and _merge_compatible_types(known_types) is None:
            joined = ", ".join(sorted({_format_datatype(datatype) for datatype in known_types}))
            raise StructuralValidationError(
                f"{context} IF-expression branches must have compatible datatypes; got {joined}"
            )
        return

    for item in node[1:]:
        _validate_expression_semantics(item, env, type_graph, context)


def _infer_expression_datatype(
    node: object,
    env: dict[str, Variable],
    type_graph: TypeGraph,
) -> Simple_DataType | str | None:
    if isinstance(node, bool):
        return Simple_DataType.BOOLEAN
    if isinstance(node, IntLiteral | int) and not isinstance(node, bool):
        return Simple_DataType.INTEGER
    if isinstance(node, FloatLiteral | float):
        return Simple_DataType.REAL
    if isinstance(node, str):
        return Simple_DataType.STRING

    if isinstance(node, dict):
        if const.KEY_VAR_NAME in node:
            return _resolve_ref_datatype(node, env, type_graph)
        return None

    if not isinstance(node, tuple) or not node:
        return None

    tag = node[0]
    if tag == const.KEY_FUNCTION_CALL and len(node) == 3:
        builtin = SATTLINE_BUILTINS.get(str(node[1]).casefold())
        if builtin is None or builtin.return_type is None:
            return None
        return _normalize_builtin_datatype(builtin.return_type)

    if tag in (const.KEY_COMPARE, const.GRAMMAR_VALUE_OR, const.GRAMMAR_VALUE_AND, const.GRAMMAR_VALUE_NOT):
        return Simple_DataType.BOOLEAN

    if tag in (const.KEY_ADD, const.KEY_MUL) and len(node) == 3:
        datatypes = [_infer_expression_datatype(node[1], env, type_graph)]
        datatypes.extend(
            _infer_expression_datatype(item[1], env, type_graph)
            for item in node[2]
            if isinstance(item, tuple) and len(item) == 2
        )
        return _merge_numeric_types(datatypes)

    if tag in (const.KEY_PLUS, const.KEY_MINUS) and len(node) == 2:
        dtype = _infer_expression_datatype(node[1], env, type_graph)
        return _merge_numeric_types([dtype])

    if tag == const.KEY_TERNARY and len(node) == 3:
        branch_types = [
            _infer_expression_datatype(branch[1], env, type_graph)
            for branch in node[1]
            if isinstance(branch, tuple) and len(branch) == 2
        ]
        branch_types.append(_infer_expression_datatype(node[2], env, type_graph))
        return _merge_compatible_types(branch_types)

    return None


def _validate_builtin_call_signature(
    fn_name: str | None,
    args: list[object],
    env: dict[str, Variable],
    type_graph: TypeGraph,
    context: str,
) -> None:
    if not fn_name:
        return

    builtin = SATTLINE_BUILTINS.get(fn_name.casefold())
    if builtin is None:
        return

    expected_arg_count = len(builtin.parameters)
    actual_arg_count = len(args)
    if actual_arg_count != expected_arg_count:
        raise StructuralValidationError(
            f"{context} call {fn_name!r} has {actual_arg_count} arguments but builtin expects {expected_arg_count}"
        )

    for index, parameter in enumerate(builtin.parameters, start=1):
        argument = args[index - 1]

        if parameter.direction in {"in var", "out", "inout"} and not _is_variable_ref_node(argument):
            raise StructuralValidationError(
                f"{context} call {fn_name!r} argument {index} must be a variable reference because builtin parameter {parameter.name!r} is {parameter.direction!r}"
            )

        if parameter.direction in {"out", "inout"} and isinstance(argument, dict) and _is_variable_ref_node(argument):
            variable = _resolve_root_variable(argument, env)
            if variable is not None and variable.const:
                if fn_name.casefold() in {"setstringpos", "getstringpos"} and index == 1:
                    continue
                raise StructuralValidationError(
                    f"{context} call {fn_name!r} argument {index} writes to CONST variable {variable.name!r}",
                    **_span_kwargs(_ref_span(argument)),
                )

        actual = _infer_expression_datatype(argument, env, type_graph)
        if actual is None:
            continue

        expected = _normalize_builtin_datatype(parameter.datatype)
        if _builtin_type_matches(actual, expected, direction=parameter.direction):
            continue

        raise StructuralValidationError(
            f"{context} call {fn_name!r} argument {index} has datatype {_format_datatype(actual)!r} "
            f"but builtin parameter {parameter.name!r} expects {_format_datatype(expected)!r}"
        )


def _validate_call_arg_node(node: object, context: str) -> None:
    if isinstance(node, str):
        raise StructuralValidationError(
            f"{context} uses string literal {node!r}; string literals are only allowed in parameter connections"
        )

    if isinstance(node, Tree):
        for child in node.children:
            _validate_call_arg_node(child, context)
        return

    if isinstance(node, list):
        for item in node:
            _validate_call_arg_node(item, context)
        return

    if isinstance(node, dict):
        if const.KEY_VAR_NAME in node:
            return

        for value in node.values():
            _validate_call_arg_node(value, context)
        return

    if isinstance(node, tuple):
        if len(node) == 3 and node[0] == const.KEY_FUNCTION_CALL:
            fn_name = node[1]
            args = node[2] or []
            for index, arg in enumerate(args, start=1):
                _validate_call_arg_node(
                    arg,
                    f"{context} call {fn_name!r} argument {index}",
                )
            return

        items = node[1:] if node and isinstance(node[0], str) else node
        for item in items:
            _validate_call_arg_node(item, context)


def _validate_no_string_literals_in_calls(node: object, context: str) -> None:
    if isinstance(node, Tree):
        for child in node.children:
            _validate_no_string_literals_in_calls(child, context)
        return

    if isinstance(node, list):
        for item in node:
            _validate_no_string_literals_in_calls(item, context)
        return

    if isinstance(node, dict):
        if const.KEY_VAR_NAME in node:
            return

        for value in node.values():
            _validate_no_string_literals_in_calls(value, context)
        return

    if isinstance(node, tuple):
        if len(node) == 3 and node[0] == const.KEY_FUNCTION_CALL:
            fn_name = node[1]
            args = node[2] or []
            for index, arg in enumerate(args, start=1):
                _validate_call_arg_node(
                    arg,
                    f"{context} call {fn_name!r} argument {index}",
                )
            return

        for item in node:
            _validate_no_string_literals_in_calls(item, context)


def _validate_builtin_call_types(
    node: object,
    env: dict[str, Variable],
    type_graph: TypeGraph,
    context: str,
) -> None:
    if isinstance(node, Tree):
        for child in node.children:
            _validate_builtin_call_types(child, env, type_graph, context)
        return

    if isinstance(node, list):
        for item in node:
            _validate_builtin_call_types(item, env, type_graph, context)
        return

    if isinstance(node, dict):
        if const.KEY_VAR_NAME in node:
            return

        for value in node.values():
            _validate_builtin_call_types(value, env, type_graph, context)
        return

    if isinstance(node, tuple):
        if len(node) == 3 and node[0] == const.KEY_FUNCTION_CALL:
            fn_name = node[1]
            args = node[2] or []
            _validate_builtin_call_signature(fn_name, args, env, type_graph, context)
            for arg in args:
                _validate_builtin_call_types(arg, env, type_graph, context)
            return

        for item in node:
            _validate_builtin_call_types(item, env, type_graph, context)
