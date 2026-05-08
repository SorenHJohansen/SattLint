"""Sequence and statement walkers for the variable usage analyzer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from lark import Tree

from sattline_parser.models.ast_model import (
    FloatLiteral,
    IntLiteral,
    ModuleCode,
    Sequence,
    SFCAlternative,
    SFCBreak,
    SFCFork,
    SFCParallel,
    SFCStep,
    SFCSubsequence,
    SFCTransition,
    SFCTransitionSub,
    Variable,
)

from ..grammar import constants as const
from ..resolution import AccessKind
from ..resolution.common import varname_base
from ..resolution.scope import ScopeContext
from ._variable_traversal_support import (
    _AssignTuple,
    _BinaryOpTuple,
    _children_of,
    _CompareTuple,
    _FunctionCallTuple,
    _IfTuple,
    _LogicalTuple,
    _TernaryTuple,
    _UnaryTuple,
    _var_name_of,
)

if TYPE_CHECKING:
    from .variables import VariablesAnalyzer


def _walk_module_code(
    self: VariablesAnalyzer,
    mc: ModuleCode | None,
    context: ScopeContext,
    path: list[str],
) -> None:
    if mc is None:
        return

    for eq in mc.equations or []:
        for stmt in eq.code or []:
            self._walk_stmt_or_expr(stmt, context, path)

    for seq in mc.sequences or []:
        self._walk_sequence(seq, context, path)


def _walk_sequence(
    self: VariablesAnalyzer,
    seq: Sequence,
    context: ScopeContext,
    path: list[str],
) -> None:
    if seq.name:
        self._push_site(f"seq:{seq.name}")
    try:
        self._walk_seq_nodes(seq.code or [], context.env, path, context)
    finally:
        if seq.name:
            self._pop_site()


def _walk_seq_nodes(
    self: VariablesAnalyzer,
    nodes: list[Any],
    env: dict[str, Variable],
    path: list[str],
    context: ScopeContext,
) -> None:
    for node in nodes or []:
        if isinstance(node, SFCStep):
            for stmt in node.code.enter or []:
                self._walk_stmt_or_expr(stmt, context, path)
            for stmt in node.code.active or []:
                self._walk_stmt_or_expr(stmt, context, path)
            for stmt in node.code.exit or []:
                self._walk_stmt_or_expr(stmt, context, path)
            continue
        if isinstance(node, SFCTransition):
            self._walk_stmt_or_expr(node.condition, context, path)
            continue
        if isinstance(node, SFCAlternative):
            for branch in node.branches or []:
                self._walk_seq_nodes(branch or [], env, path, context)
            continue
        if isinstance(node, SFCParallel):
            for branch in node.branches or []:
                self._walk_seq_nodes(branch or [], env, path, context)
            continue
        if isinstance(node, SFCSubsequence):
            self._walk_seq_nodes(node.body or [], env, path, context)
            continue
        if isinstance(node, SFCTransitionSub):
            self._walk_seq_nodes(node.body or [], env, path, context)
            continue
        if isinstance(node, (SFCFork, SFCBreak)):
            continue


def _walk_stmt_or_expr(
    self: VariablesAnalyzer,
    obj: Any,
    context: ScopeContext,
    path: list[str],
    *,
    is_ui_read: bool = False,
) -> None:
    if hasattr(obj, "data") and obj.data == const.KEY_STATEMENT:
        for child in _children_of(obj) or []:
            self._walk_stmt_or_expr(child, context, path, is_ui_read=is_ui_read)
        return

    if obj is None:
        return

    if isinstance(obj, IntLiteral | FloatLiteral):
        span = getattr(obj, "span", None)
        value = int(obj) if isinstance(obj, IntLiteral) else float(obj)
        self._add_magic_number_issue(path, value, span)
        return

    if isinstance(obj, tuple) and obj and obj[0] == const.GRAMMAR_VALUE_IF:
        _, branches, else_block = cast(_IfTuple, obj)
        for cond, stmts in branches or []:
            self._walk_stmt_or_expr(cond, context, path, is_ui_read=is_ui_read)
            for stmt in stmts or []:
                self._walk_stmt_or_expr(stmt, context, path, is_ui_read=is_ui_read)
        for stmt in else_block or []:
            self._walk_stmt_or_expr(stmt, context, path, is_ui_read=is_ui_read)
        return

    if isinstance(obj, tuple) and obj and obj[0] in (const.KEY_TERNARY, "Ternary"):
        _, branches, else_expr = cast(_TernaryTuple, obj)
        for cond, then_expr in branches or []:
            self._walk_stmt_or_expr(cond, context, path, is_ui_read=is_ui_read)
            self._walk_stmt_or_expr(then_expr, context, path, is_ui_read=is_ui_read)
        if else_expr is not None:
            self._walk_stmt_or_expr(else_expr, context, path, is_ui_read=is_ui_read)
        return

    if isinstance(obj, tuple) and obj and obj[0] == const.KEY_FUNCTION_CALL:
        _, fn_name, args = cast(_FunctionCallTuple, obj)
        self._handle_function_call(
            fn_name,
            args or [],
            context,
            path,
            is_ui_read=is_ui_read,
        )
        return

    if isinstance(obj, tuple) and obj and obj[0] in (const.GRAMMAR_VALUE_OR, const.GRAMMAR_VALUE_AND):
        for sub in cast(_LogicalTuple, obj)[1] or []:
            self._walk_stmt_or_expr(sub, context, path, is_ui_read=is_ui_read)
        return

    if isinstance(obj, tuple) and obj and obj[0] == const.GRAMMAR_VALUE_NOT:
        self._walk_stmt_or_expr(cast(_UnaryTuple, obj)[1], context, path, is_ui_read=is_ui_read)
        return

    if isinstance(obj, tuple) and obj and obj[0] in (const.KEY_COMPARE, "compare"):
        _, left, pairs = cast(_CompareTuple, obj)
        self._walk_stmt_or_expr(left, context, path, is_ui_read=is_ui_read)
        for _symbol, rhs in pairs or []:
            self._walk_stmt_or_expr(rhs, context, path, is_ui_read=is_ui_read)
        return

    if isinstance(obj, tuple) and obj and obj[0] in (const.KEY_ADD, const.KEY_MUL):
        _, left, parts = cast(_BinaryOpTuple, obj)
        self._walk_stmt_or_expr(left, context, path, is_ui_read=is_ui_read)
        for _operator_value, rhs in parts or []:
            self._walk_stmt_or_expr(rhs, context, path, is_ui_read=is_ui_read)
        return

    if isinstance(obj, tuple) and obj and obj[0] in (const.KEY_PLUS, const.KEY_MINUS):
        _, inner = cast(_UnaryTuple, obj)
        if isinstance(inner, IntLiteral | FloatLiteral):
            span = getattr(inner, "span", None)
            value = int(inner) if isinstance(inner, IntLiteral) else float(inner)
            if obj[0] == const.KEY_MINUS:
                value = -value
            self._add_magic_number_issue(path, value, span)
            return
        self._walk_stmt_or_expr(inner, context, path, is_ui_read=is_ui_read)
        return

    if isinstance(obj, dict) and const.KEY_ENABLE_EXPRESSION in obj:
        tail = cast(dict[str, Any], obj).get(const.KEY_ENABLE_EXPRESSION)
        self._walk_stmt_or_expr(tail, context, path, is_ui_read=is_ui_read)
        return

    if isinstance(obj, Tree):
        if obj.data == const.KEY_ENABLE_EXPRESSION:
            for child in _children_of(obj) or []:
                self._walk_stmt_or_expr(child, context, path, is_ui_read=is_ui_read)
            return
        if obj.data == const.GRAMMAR_VALUE_INVAR_PREFIX:
            for child in _children_of(obj) or []:
                self._walk_stmt_or_expr(child, context, path, is_ui_read=is_ui_read)
            return

    if isinstance(obj, list):
        for item in cast(list[Any], obj):
            self._walk_stmt_or_expr(item, context, path, is_ui_read=is_ui_read)
        return

    if isinstance(obj, dict) and const.KEY_VAR_NAME in obj:
        full_name = _var_name_of(obj)
        if full_name is not None:
            self._mark_ref_access(
                full_name,
                context,
                path,
                AccessKind.READ,
                is_ui_read=is_ui_read,
            )
        return

    if isinstance(obj, tuple) and obj and obj[0] == const.KEY_ASSIGN:
        _, target, expr = cast(_AssignTuple, obj)

        full_name = _var_name_of(target)
        if full_name is not None:
            self._mark_ref_access(full_name, context, path, AccessKind.WRITE)
            self._record_assignment_effect_flow(full_name, expr, context)
        self._walk_stmt_or_expr(expr, context, path, is_ui_read=is_ui_read)
        return

    if isinstance(obj, str):
        token = obj.strip()
        if not token:
            return
        base_name = varname_base(token)
        if base_name and base_name.casefold() in context.env:
            self._mark_var_by_basename(base_name, context.env, path, is_ui_read=is_ui_read)


__all__ = [
    "_walk_module_code",
    "_walk_seq_nodes",
    "_walk_sequence",
    "_walk_stmt_or_expr",
]
