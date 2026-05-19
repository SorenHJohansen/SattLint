"""Formatting helpers for AST models."""

from __future__ import annotations

import pprint
import textwrap
from collections.abc import Sequence
from typing import Any, Protocol, TypeGuard, cast

from lark import Tree

from ..grammar import constants as const

_DEFAULT_INDENT = "    "

__all__ = ["format_expr", "format_list", "format_optional", "format_seq_nodes"]


class _VariableLike(Protocol):
    name: object
    datatype: object
    global_var: object
    const: object
    state: object
    init_value: object
    description: object


def _is_variable_like(value: object) -> TypeGuard[_VariableLike]:
    required_attrs = (
        "name",
        "datatype",
        "global_var",
        "const",
        "state",
        "init_value",
        "description",
    )
    return type(value).__name__ == "Variable" and all(hasattr(value, attr) for attr in required_attrs)


def _statement_children(expr: object) -> list[object] | None:
    if isinstance(expr, Tree) and expr.data == const.KEY_STATEMENT:
        return cast(list[object], cast(Tree[Any], expr).children)
    return None


def _var_name(expr: object) -> str | None:
    if not isinstance(expr, dict) or const.KEY_VAR_NAME not in expr:
        return None
    name = cast(dict[str, object], expr).get(const.KEY_VAR_NAME)
    return name if isinstance(name, str) else None


def _object_list(raw: object) -> list[object]:
    return cast(list[object], raw) if isinstance(raw, list) else []


def _object_list_or_none(raw: object) -> list[object] | None:
    return cast(list[object], raw) if isinstance(raw, list) else None


def _statement_branches(raw: object) -> list[tuple[object, list[object]]]:
    branches: list[tuple[object, list[object]]] = []
    for item in _object_list(raw):
        if not isinstance(item, tuple):
            continue
        branch = cast(tuple[object, ...], item)
        if len(branch) != 2:
            continue
        branches.append((branch[0], _object_list(branch[1])))
    return branches


def _ternary_branches(raw: object) -> list[tuple[object, object]]:
    branches: list[tuple[object, object]] = []
    for item in _object_list(raw):
        if not isinstance(item, tuple):
            continue
        branch = cast(tuple[object, ...], item)
        if len(branch) != 2:
            continue
        branches.append((branch[0], branch[1]))
    return branches


def _comparison_pairs(raw: object) -> list[tuple[str, object]]:
    pairs: list[tuple[str, object]] = []
    for item in _object_list(raw):
        if not isinstance(item, tuple):
            continue
        pair = cast(tuple[object, ...], item)
        if len(pair) != 2 or not isinstance(pair[0], str):
            continue
        pairs.append((pair[0], pair[1]))
    return pairs


def format_list(
    items: Sequence[object],
    indent: str = _DEFAULT_INDENT,
    align_variables: bool = True,
    inline_if_singleline: bool = False,
) -> str:
    if not items:
        return "[]"

    if align_variables:
        variable_items = [item for item in items if _is_variable_like(item)]
        if len(variable_items) == len(items):
            name_w = max(len(repr(item.name)) for item in variable_items)
            dtype_w = max(len(repr(item.datatype)) for item in variable_items)
            global_w = max(len(str(item.global_var)) for item in variable_items)
            const_w = max(len(str(item.const)) for item in variable_items)
            state_w = max(len(str(item.state)) for item in variable_items)
            init_w = max(len(repr(item.init_value)) for item in variable_items)
            desc_w = max(len(repr(item.description)) for item in variable_items)

            lines: list[str] = []
            for item in variable_items:
                lines.append(
                    indent + f"Name: {item.name!r:<{name_w}} , "
                    f"Datatype: {item.datatype!r:<{dtype_w}}, "
                    f"Global: {item.global_var!s:<{global_w}}, "
                    f"Const: {item.const!s:<{const_w}}, "
                    f"State: {item.state!s:<{state_w}}, "
                    f"Init_value : {item.init_value!r:<{init_w}}, "
                    f"Description: {item.description!r:<{desc_w}}"
                )
            return "[\n" + "\n".join(lines) + "]"

    rendered_items = [str(item) for item in items]
    if inline_if_singleline and all("\n" not in item for item in rendered_items):
        return "[" + ", ".join(rendered_items) + "]"
    indented = [textwrap.indent(item, indent) for item in rendered_items]
    return "[\n" + "\n".join(indented) + "]"


def format_optional(obj: object) -> str:
    return "None" if obj is None else str(obj)


def format_expr(expr: object, indent: str = _DEFAULT_INDENT) -> str:
    """Pretty-print nested expressions and statements in a SattLine-like format."""

    children = _statement_children(expr)
    if children:
        return format_expr(children[0], indent)

    variable_name = _var_name(expr)
    if variable_name is not None:
        return variable_name

    if isinstance(expr, int | float | bool | str):
        return repr(expr) if isinstance(expr, str) else str(expr)

    if isinstance(expr, list):
        return "\n".join(format_expr(item, indent) for item in cast(list[object], expr))

    if isinstance(expr, tuple):
        values = cast(tuple[object, ...], expr)
        if not values:
            return "()"
        op = values[0]

        if op == const.KEY_ASSIGN and len(values) == 3:
            target = values[1]
            value = values[2]
            lhs = _var_name(target) or str(target)
            rhs = format_expr(value, indent)
            return f"{lhs} = {rhs}"

        if op == const.GRAMMAR_VALUE_IF and len(values) == 3:
            branches = _statement_branches(values[1])
            else_block = _object_list_or_none(values[2])
            out_lines: list[str] = []
            for index, (condition, statements) in enumerate(branches):
                head = "IF" if index == 0 else "ELSIF"
                out_lines.append(f"{head} {format_expr(condition, indent)}")
                out_lines.append("THEN")
                for statement in statements:
                    out_lines.append(textwrap.indent(format_expr(statement, indent), indent))
            if else_block:
                out_lines.append("ELSE")
                for statement in else_block:
                    out_lines.append(textwrap.indent(format_expr(statement, indent), indent))
            out_lines.append("ENDIF")
            return "\n".join(out_lines)

        if op in (const.KEY_TERNARY, "Ternary") and len(values) == 3:
            branches = _ternary_branches(values[1])
            else_expr = values[2]
            out_lines: list[str] = []
            for index, (condition, then_expr) in enumerate(branches):
                head = "IF" if index == 0 else "ELSIF"
                out_lines.append(f"{head} {format_expr(condition, indent)}")
                out_lines.append("THEN")
                out_lines.append(textwrap.indent(format_expr(then_expr, indent), indent))
            if else_expr is not None:
                out_lines.append("ELSE")
                out_lines.append(textwrap.indent(format_expr(else_expr, indent), indent))
            out_lines.append("ENDIF")
            return "\n".join(out_lines)

        if op == const.GRAMMAR_VALUE_OR and len(values) >= 2:
            parts = [format_expr(item, indent) for item in _object_list(values[1])]
            return " OR \n".join(parts)

        if op == const.GRAMMAR_VALUE_AND and len(values) >= 2:
            parts = [format_expr(item, indent) for item in _object_list(values[1])]
            return " AND \n".join(parts)

        if op == const.GRAMMAR_VALUE_NOT and len(values) >= 2:
            return "NOT(" + format_expr(values[1], indent) + ")"

        if op in (const.KEY_COMPARE, "compare") and len(values) == 3:
            left = values[1]
            pairs = _comparison_pairs(values[2])
            left_str = format_expr(left, indent)
            if not pairs:
                return left_str
            rendered_pairs = [f"{left_str} {symbol} {format_expr(rhs, indent)}" for symbol, rhs in pairs]
            return " AND ".join(rendered_pairs)

        if op == const.KEY_ADD and len(values) == 3:
            left = values[1]
            parts = _comparison_pairs(values[2])
            base = format_expr(left, indent)
            tail = " ".join(f"{operator} {format_expr(rhs, indent)}" for operator, rhs in parts)
            return f"({base} {tail})"

        if op == const.KEY_MUL and len(values) == 3:
            left = values[1]
            parts = _comparison_pairs(values[2])
            base = format_expr(left, indent)
            tail = " ".join(f"{operator} {format_expr(rhs, indent)}" for operator, rhs in parts)
            return f"({base} {tail})"

        if op == const.KEY_FUNCTION_CALL and len(values) == 3:
            fn_name = values[1]
            args = _object_list(values[2])
            arg_str = ", ".join(format_expr(arg, indent) for arg in args)
            return f"{fn_name}({arg_str})"

        return pprint.pformat(values)

    return str(expr)


def format_seq_nodes(nodes: list[object], indent: str = _DEFAULT_INDENT) -> str:
    """Pretty-print a list of SFC nodes recursively."""
    lines: list[str] = []

    from ..models import ast_model

    def _fmt_stmt_list(statements: list[object], level: int = 2) -> None:
        for statement in statements:
            lines.append(indent * level + format_expr(statement, indent))

    for node in nodes:
        if isinstance(node, ast_model.SFCStep):
            header = "InitStep" if node.kind == "init" else "Step"
            lines.append(f"{header} {node.name}")
            if node.code.enter:
                lines.append(indent + "Enter:")
                _fmt_stmt_list(cast(list[object], node.code.enter))
            if node.code.active:
                lines.append(indent + "Active:")
                _fmt_stmt_list(cast(list[object], node.code.active))
            if node.code.exit:
                lines.append(indent + "Exit:")
                _fmt_stmt_list(cast(list[object], node.code.exit))

        elif isinstance(node, ast_model.SFCTransition):
            name_suffix = f" {node.name}" if node.name else ""
            condition = format_expr(node.condition, indent)
            lines.append(f"Transition{name_suffix} WAIT_FOR {condition}")

        elif isinstance(node, ast_model.SFCAlternative):
            lines.append("Alternative:")
            for index, branch in enumerate(node.branches, start=1):
                lines.append(indent + f"Branch {index}:")
                branch_str = format_seq_nodes(cast(list[object], branch), indent)
                for line in branch_str.splitlines():
                    lines.append(indent * 2 + line)
            lines.append("EndAlternative")

        elif isinstance(node, ast_model.SFCParallel):
            lines.append("Parallel:")
            for index, branch in enumerate(node.branches, start=1):
                lines.append(indent + f"Branch {index}:")
                branch_str = format_seq_nodes(cast(list[object], branch), indent)
                for line in branch_str.splitlines():
                    lines.append(indent * 2 + line)
            lines.append("EndParallel")

        elif isinstance(node, ast_model.SFCSubsequence):
            lines.append(f"Subsequence {node.name}:")
            sub_str = format_seq_nodes(cast(list[object], node.body), indent)
            for line in sub_str.splitlines():
                lines.append(indent + line)
            lines.append("EndSubsequence")

        elif isinstance(node, ast_model.SFCTransitionSub):
            lines.append(f"TransitionSub {node.name}:")
            sub_str = format_seq_nodes(cast(list[object], node.body), indent)
            for line in sub_str.splitlines():
                lines.append(indent + line)
            lines.append("EndTransitionSub")

        elif isinstance(node, ast_model.SFCFork):
            lines.append(f"Fork to {node.target}")

        elif isinstance(node, ast_model.SFCBreak):
            lines.append("Break")

        else:
            lines.append(str(node))

    return "\n".join(lines)
