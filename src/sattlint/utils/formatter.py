"""formatting helpers for AST models."""
from __future__ import annotations
from typing import Any, TYPE_CHECKING
import textwrap
from ..grammar import constants as const

if TYPE_CHECKING:
    from ..models.ast_model import (
        Variable,
        SFCStep,
        SFCTransition,
        SFCAlternative,
        SFCParallel,
        SFCSubsequence,
        SFCTransitionSub,
        SFCFork,
        SFCBreak
    )


def format_list(
    items: list[Any],
    indent: str = "    ",
    align_variables: bool = True,
    inline_if_singleline: bool = False,
) -> str:
    # Need to check for Variable type. We use string check or delayed import to allow circular ref
    # Ideally structure should be cleaner, but for now:

    first = items[0] if items else None
    is_variable = first and type(first).__name__ == "Variable"

    if not items:
        return "[]"

    # Aligned rendering for Variable lists.
    # We duck-type or use basic name check to avoid importing Variable at top level
    if align_variables and is_variable:
        # Compute column widths across the list
        name_w = max(len(repr(v.name)) for v in items)
        dtype_w = max(len(repr(v.datatype)) for v in items)
        global_w = max(len(str(v.global_var)) for v in items)
        const_w = max(len(str(v.const)) for v in items)
        state_w = max(len(str(v.state)) for v in items)
        init_w = max(len(repr(v.init_value)) for v in items)
        desc_w = max(len(repr(v.description)) for v in items)

        lines = []
        for v in items:
            lines.append(
                indent + f"Name: {repr(v.name):<{name_w}} , "
                f"Datatype: {repr(v.datatype):<{dtype_w}}, "
                f"Global: {str(v.global_var):<{global_w}}, "
                f"Const: {str(v.const):<{const_w}}, "
                f"State: {str(v.state):<{state_w}}, "
                f"Init_value : {repr(v.init_value):<{init_w}}, "
                f"Description: {repr(v.description):<{desc_w}}"
            )
        return "[\n" + "\n".join(lines) + "]"
    # Generic rendering for any other items.
    strs = [str(obj) for obj in items]
    if inline_if_singleline and all("\n" not in s for s in strs):
        return "[" + ", ".join(strs) + "]"
    indented = [textwrap.indent(s, indent) for s in strs]
    return "[\n" + "\n".join(indented) + "]"


def format_optional(obj: Any) -> str:
    return "None" if obj is None else str(obj)


def format_expr(expr, indent="    "):
    """
    Pretty-print nested expressions and statements (assign/IF/AND/OR/compare/add/mul/function).
    Produces SattLine-like multi-line formatting where appropriate.
    """

    # 0) Unwrap a Statement tree anywhere (so nested IFs also render pretty)
    if hasattr(expr, "data") and getattr(expr, "data") == const.KEY_STATEMENT:
        children = getattr(expr, "children", [])
        if children:
            return format_expr(children[0], indent)

    # 1) Variable reference dict
    if isinstance(expr, dict) and const.KEY_VAR_NAME in expr:
        return expr[const.KEY_VAR_NAME]

    # 2) Literals
    if isinstance(expr, (int, float, bool, str)):
        return repr(expr) if isinstance(expr, str) else str(expr)

    # 3) Lists = block of expressions/statements
    if isinstance(expr, list):
        return "\n".join(format_expr(e, indent) for e in expr)

    # 4) Tuples = operators or structured statements
    if isinstance(expr, tuple):
        op = expr[0]

        # assignment: ('assign', targetdict, valueexpr)
        if op == const.KEY_ASSIGN:
            _, target, value = expr
            lhs = (
                target[const.KEY_VAR_NAME]
                if isinstance(target, dict) and const.KEY_VAR_NAME in target
                else str(target)
            )
            rhs = format_expr(value, indent)
            return f"{lhs} = {rhs}"

        # IF statement: ('IF', branches, else_block)
        # branches: list of (condition, [statements...])
        if op == const.GRAMMAR_VALUE_IF:
            _, branches, else_block = expr
            out_lines = []
            for i, (cond, stmts) in enumerate(branches):
                head = "IF" if i == 0 else "ELSIF"
                cond_str = format_expr(cond, indent)
                out_lines.append(f"{head} {cond_str}")
                out_lines.append("THEN")
                # Each stmt can itself be a tuple or a Statement tree; format recursively
                for s in stmts:
                    out_lines.append(textwrap.indent(format_expr(s, indent), indent))
            if else_block:
                out_lines.append("ELSE")
                for s in else_block:
                    out_lines.append(textwrap.indent(format_expr(s, indent), indent))
            out_lines.append("ENDIF")
            return "\n".join(out_lines)

        # ('Ternary', [(cond, then_expr), (cond2, then_expr2), ...], else_expr)
        if op == const.KEY_TERNARY or op == "Ternary":
            _, branches, else_expr = expr
            out_lines = []
            for i, (cond, then_expr) in enumerate(branches):
                head = "IF" if i == 0 else "ELSIF"
                out_lines.append(f"{head} {format_expr(cond, indent)}")
                out_lines.append("THEN")
                out_lines.append(
                    textwrap.indent(format_expr(then_expr, indent), indent)
                )
            if else_expr is not None:
                out_lines.append("ELSE")
                out_lines.append(
                    textwrap.indent(format_expr(else_expr, indent), indent)
                )
            out_lines.append("ENDIF")
            return "\n".join(out_lines)

        # Boolean OR
        if op == const.GRAMMAR_VALUE_OR:
            parts = [format_expr(x, indent) for x in expr[1]]
            return (" OR \n").join(parts)

        # Boolean AND
        if op == const.GRAMMAR_VALUE_AND:
            parts = [format_expr(x, indent) for x in expr[1]]
            return (" AND \n").join(parts)

        # NOT
        if op == const.GRAMMAR_VALUE_NOT:
            return "NOT(" + format_expr(expr[1], indent) + ")"

        # compare: ('compare', left, [(symbol, right), ...])
        if op == const.KEY_COMPARE or op == "compare":
            _, left, pairs = expr
            left_str = format_expr(left, indent)
            if not pairs:
                return left_str
            parts = [
                f"{left_str} {sym} {format_expr(rhs, indent)}" for sym, rhs in pairs
            ]
            return " AND ".join(parts)

        # add: ('add', left, [(op, right), ...])
        if op == const.KEY_ADD:
            _, left, parts = expr
            base = format_expr(left, indent)
            tail = " ".join(f"{opval} {format_expr(r, indent)}" for opval, r in parts)
            return f"({base} {tail})"

        # mul/div: ('mul', left, [(op, right), ...])
        if op == const.KEY_MUL:
            _, left, parts = expr
            base = format_expr(left, indent)
            tail = " ".join(f"{opval} {format_expr(r, indent)}" for opval, r in parts)
            return f"({base} {tail})"

        # function call: ('FunctionCall', name, [args...])
        if op == const.KEY_FUNCTION_CALL:
            _, fn_name, args = expr
            arg_str = ", ".join(format_expr(a, indent) for a in (args or []))
            return f"{fn_name}({arg_str})"

        # Fallback: safe repr for anything unhandled
        import pprint

        return pprint.pformat(expr)

    # 5) Default
    return str(expr)


def format_seq_nodes(nodes: list[Any], indent: str = "    ") -> str:
    # Pretty-print a list of SFC nodes recursively
    lines: list[str] = []

    # Delayed import to avoid circular dependency
    from ..models import ast_model

    def _fmt_stmt_list(stmts: list[Any], level: int = 2):
        for s in stmts:
            lines.append(indent * level + format_expr(s, indent))

    for n in nodes:
        if isinstance(n, ast_model.SFCStep):
            header = "InitStep" if n.kind == "init" else "Step"
            lines.append(f"{header} {n.name}")
            if n.code.enter:
                lines.append(indent + "Enter:")
                _fmt_stmt_list(n.code.enter)
            if n.code.active:
                lines.append(indent + "Active:")
                _fmt_stmt_list(n.code.active)
            if n.code.exit:
                lines.append(indent + "Exit:")
                _fmt_stmt_list(n.code.exit)

        elif isinstance(n, ast_model.SFCTransition):
            nm = f" {n.name}" if n.name else ""
            cond = format_expr(n.condition, indent)
            lines.append(f"Transition{nm} WAIT_FOR {cond}")

        elif isinstance(n, ast_model.SFCAlternative):
            lines.append("Alternative:")
            for i, branch in enumerate(n.branches, start=1):
                lines.append(indent + f"Branch {i}:")
                branch_str = format_seq_nodes(branch, indent)
                for ln in branch_str.splitlines():
                    lines.append(indent * 2 + ln)
            lines.append("EndAlternative")

        elif isinstance(n, ast_model.SFCParallel):
            lines.append("Parallel:")
            for i, branch in enumerate(n.branches, start=1):
                lines.append(indent + f"Branch {i}:")
                branch_str = format_seq_nodes(branch, indent)
                for ln in branch_str.splitlines():
                    lines.append(indent * 2 + ln)
            lines.append("EndParallel")

        elif isinstance(n, ast_model.SFCSubsequence):
            lines.append(f"Subsequence {n.name}:")
            sub_str = format_seq_nodes(n.body, indent)
            for ln in sub_str.splitlines():
                lines.append(indent + ln)
            lines.append("EndSubsequence")

        elif isinstance(n, ast_model.SFCTransitionSub):
            lines.append(f"TransitionSub {n.name}:")
            ts_str = format_seq_nodes(n.body, indent)
            for ln in ts_str.splitlines():
                lines.append(indent + ln)
            lines.append("EndTransitionSub")

        elif isinstance(n, ast_model.SFCFork):
            lines.append(f"Fork to {n.target}")

        elif isinstance(n, ast_model.SFCBreak):
            lines.append("Break")

        else:
            # fallback for any unhandled node
            lines.append(str(n))

    return "\n".join(lines)
