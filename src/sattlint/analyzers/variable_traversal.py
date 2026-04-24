"""Traversal helpers for the variable usage analyzer."""

from __future__ import annotations

import logging
from typing import Any

from lark import Tree

from ..grammar import constants as const
from ..models.ast_model import (
    FloatLiteral,
    IntLiteral,
    ModuleCode,
    ModuleDef,
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
from ..resolution import AccessKind, decorate_segment
from ..resolution.common import varname_base
from ..resolution.scope import ScopeContext
from .sattline_builtins import get_function_signature

log = logging.getLogger("SattLint")

_IGNORED_GRAPHICS_TAIL_BASENAMES = {
    "abs_",
    "centeraligned",
    "decimal_",
    "digits_",
    "duration_value",
    "int_value",
    "leftaligned",
    "real_value",
    "relative_",
    "rightaligned",
    "setapp_",
}


def _repath_context(
    self,
    context: ScopeContext,
    module_path: list[str],
    display_module_path: list[str],
) -> ScopeContext:
    return ScopeContext(
        env=context.env,
        param_mappings=context.param_mappings,
        module_path=module_path,
        display_module_path=display_module_path,
        current_library=context.current_library,
        parent_context=context.parent_context,
    )


def _handle_function_call(
    self,
    fn_name: str | None,
    args: list,
    context: ScopeContext,
    path: list[str],
    *,
    is_ui_read: bool = False,
) -> None:
    """Handle function calls with proper parameter direction tracking."""
    if not fn_name:
        for argument in args or []:
            self._walk_stmt_or_expr(argument, context, path, is_ui_read=is_ui_read)
        return

    self._record_procedure_status_bindings(fn_name, args or [], context)
    fn_key = fn_name.casefold()
    if fn_key in ("copyvariable", "copyvarnosort"):
        if len(args or []) < 2:
            raise ValueError(f"{fn_name}: expected at least 2 arguments (Source, Destination)")

        src = args[0]
        dst = args[1]
        if not (isinstance(src, dict) and const.KEY_VAR_NAME in src):
            raise ValueError(f"{fn_name}: Source must be a variable reference")
        if not (isinstance(dst, dict) and const.KEY_VAR_NAME in dst):
            raise ValueError(f"{fn_name}: Destination must be a variable reference")

        self._mark_record_wide_builtin_access(
            src[const.KEY_VAR_NAME],
            kind=AccessKind.READ,
            fn_name=fn_name,
            context=context,
            path=path,
            is_ui_read=is_ui_read,
        )
        self._mark_record_wide_builtin_access(
            dst[const.KEY_VAR_NAME],
            kind=AccessKind.WRITE,
            fn_name=fn_name,
            context=context,
            path=path,
            is_ui_read=is_ui_read,
        )

        if len(args) >= 3:
            status = args[2]
            if isinstance(status, dict) and const.KEY_VAR_NAME in status:
                self._mark_ref_access(
                    status[const.KEY_VAR_NAME],
                    context,
                    path,
                    AccessKind.WRITE,
                    is_ui_read=is_ui_read,
                )
            else:
                self._walk_stmt_or_expr(status, context, path, is_ui_read=is_ui_read)

        for extra in args[3:] if len(args) > 3 else []:
            self._walk_stmt_or_expr(extra, context, path, is_ui_read=is_ui_read)
        self._record_function_call_effect_flow(fn_name, args or [], context)
        return

    if fn_key == "initvariable":
        if len(args or []) < 1:
            raise ValueError(f"{fn_name}: expected at least 1 argument (Rec)")

        rec = args[0]
        if not (isinstance(rec, dict) and const.KEY_VAR_NAME in rec):
            raise ValueError(f"{fn_name}: Rec must be a variable reference")

        self._mark_record_wide_builtin_access(
            rec[const.KEY_VAR_NAME],
            kind=AccessKind.WRITE,
            fn_name=fn_name,
            context=context,
            path=path,
            is_ui_read=is_ui_read,
        )

        if len(args) >= 3:
            status = args[2]
            if isinstance(status, dict) and const.KEY_VAR_NAME in status:
                self._mark_ref_access(
                    status[const.KEY_VAR_NAME],
                    context,
                    path,
                    AccessKind.WRITE,
                    is_ui_read=is_ui_read,
                )
            else:
                self._walk_stmt_or_expr(status, context, path, is_ui_read=is_ui_read)

        for extra in args[3:] if len(args) > 3 else []:
            self._walk_stmt_or_expr(extra, context, path, is_ui_read=is_ui_read)
        return

    sig = get_function_signature(fn_name)
    if sig is None:
        for argument in args or []:
            self._walk_stmt_or_expr(argument, context, path, is_ui_read=is_ui_read)
        return

    for idx, arg in enumerate(args or []):
        direction = "in"
        if idx < len(sig.parameters):
            direction = sig.parameters[idx].direction

        if isinstance(arg, dict) and const.KEY_VAR_NAME in arg:
            full_name = arg[const.KEY_VAR_NAME]
            if direction == "out":
                self._mark_ref_access(
                    full_name,
                    context,
                    path,
                    AccessKind.WRITE,
                    is_ui_read=is_ui_read,
                )
            elif direction == "inout":
                self._mark_ref_access(
                    full_name,
                    context,
                    path,
                    AccessKind.READ,
                    is_ui_read=is_ui_read,
                )
                self._mark_ref_access(
                    full_name,
                    context,
                    path,
                    AccessKind.WRITE,
                    is_ui_read=is_ui_read,
                )
            else:
                self._mark_ref_access(
                    full_name,
                    context,
                    path,
                    AccessKind.READ,
                    is_ui_read=is_ui_read,
                )
            continue

        self._walk_stmt_or_expr(arg, context, path, is_ui_read=is_ui_read)

    self._record_function_call_effect_flow(fn_name, args or [], context)


def _walk_header_enable(self, header: Any, context: ScopeContext, path: list[str]) -> None:
    tail = getattr(header, "enable_tail", None)
    if tail is not None:
        self._walk_tail(tail, context, path, is_ui_read=True)


def _walk_header_invoke_tails(self, header: Any, context: ScopeContext, path: list[str]) -> None:
    for tail in getattr(header, "invoke_coord_tails", []) or []:
        self._walk_tail(tail, context, path, is_ui_read=True)


def _walk_header_groupconn(self, header: Any, context: ScopeContext, path: list[str]) -> None:
    var_dict = getattr(header, "groupconn", None)
    if not isinstance(var_dict, dict):
        return

    base = varname_base(var_dict)
    if not base:
        return

    is_global = bool(getattr(header, "groupconn_global", False))
    var = self._lookup_global_variable(base) if is_global else context.env.get(base)
    if var is not None:
        self._get_usage(var).mark_read(path)


def _walk_typedef_groupconn(self, mt: Any, context: ScopeContext, path: list[str]) -> None:
    var_dict = getattr(mt, "groupconn", None)
    if not isinstance(var_dict, dict):
        return
    base = varname_base(var_dict)
    if not base:
        return
    is_global = bool(getattr(mt, "groupconn_global", False))
    var = self._lookup_global_variable(base) if is_global else context.env.get(base)
    if var is not None:
        self._get_usage(var).mark_read(path)


def _walk_moduledef(
    self,
    mdef: ModuleDef | None,
    context: ScopeContext,
    path: list[str],
) -> None:
    """Walk ModuleDef with scope context."""
    if mdef is None:
        return

    for graph_object in mdef.graph_objects or []:
        self._walk_graph_object(graph_object, context, path)

    for interact_object in mdef.interact_objects or []:
        self._walk_interact_object(interact_object, context, path)

    props = getattr(mdef, "properties", {}) or {}
    for tail in props.get(const.KEY_TAILS, []) or []:
        self._walk_tail(tail, context, path, is_ui_read=True)


def _walk_graph_object(self, go: Any, context: ScopeContext, path: list[str]) -> None:
    props = getattr(go, "properties", {}) or {}
    for text_var in props.get("text_vars", []) or []:
        base = text_var.split(".", 1)[0] if isinstance(text_var, str) else None
        self._mark_var_by_basename(base, context.env, path, is_ui_read=True)
    for tail in props.get(const.KEY_TAILS, []) or []:
        self._walk_tail(tail, context, path, is_ui_read=True)


def _walk_interact_object(self, io: Any, context: ScopeContext, path: list[str]) -> None:
    props = getattr(io, "properties", {}) or {}
    for tail in props.get(const.KEY_TAILS, []) or []:
        self._walk_tail(tail, context, path, is_ui_read=True)
    self._scan_for_varrefs(props.get(const.KEY_BODY), context, path, is_ui_read=True)

    proc = props.get(const.KEY_PROCEDURE)
    if isinstance(proc, dict) and const.KEY_PROCEDURE_CALL in proc:
        call = proc[const.KEY_PROCEDURE_CALL]
        fn_name = call.get(const.KEY_NAME)
        args = call.get(const.KEY_ARGS) or []
        self._handle_function_call(fn_name, args, context, path, is_ui_read=True)


def _scan_for_varrefs(
    self,
    obj: Any,
    context: ScopeContext,
    path: list[str],
    *,
    is_ui_read: bool = False,
) -> None:
    if obj is None:
        return
    if isinstance(obj, list):
        for item in obj:
            self._scan_for_varrefs(item, context, path, is_ui_read=is_ui_read)
        return
    if isinstance(obj, dict):
        if const.TREE_TAG_ENABLE in obj and const.KEY_TAIL in obj:
            self._walk_tail(obj[const.KEY_TAIL], context, path, is_ui_read=is_ui_read)
        if const.KEY_TAIL in obj and obj[const.KEY_TAIL] is not None:
            self._walk_tail(obj[const.KEY_TAIL], context, path, is_ui_read=is_ui_read)
        if const.KEY_ASSIGN in obj:
            tail = (obj[const.KEY_ASSIGN] or {}).get(const.KEY_TAIL)
            if tail is not None:
                self._walk_tail(tail, context, path, is_ui_read=is_ui_read)
        for value in obj.values():
            self._scan_for_varrefs(value, context, path, is_ui_read=is_ui_read)
        return
    if hasattr(obj, "data"):
        data = obj.data
        if data in (
            const.KEY_ENABLE_EXPRESSION,
            const.GRAMMAR_VALUE_INVAR_PREFIX,
            "invar_tail",
        ):
            self._walk_tail(obj, context, path, is_ui_read=is_ui_read)
            return
        for child in getattr(obj, "children", []):
            self._scan_for_varrefs(child, context, path, is_ui_read=is_ui_read)


def _walk_tail(
    self,
    tail: Any,
    context: ScopeContext,
    path: list[str],
    *,
    is_ui_read: bool = False,
) -> None:
    if tail is None:
        return

    if isinstance(tail, IntLiteral | FloatLiteral | int | float | bool):
        return

    if isinstance(tail, tuple):
        self._walk_stmt_or_expr(tail, context, path, is_ui_read=is_ui_read)
        return

    if isinstance(tail, str):
        base_name = tail.split(".", 1)[0].lower()
        self._mark_var_by_basename(base_name, context.env, path, is_ui_read=is_ui_read)
        return

    if isinstance(tail, dict) and const.KEY_VAR_NAME in tail:
        mapped_ref = tail[const.KEY_VAR_NAME]
        if isinstance(mapped_ref, str):
            self._mark_ref_access(
                mapped_ref,
                context,
                path,
                AccessKind.READ,
                is_ui_read=is_ui_read,
            )
        return

    if hasattr(tail, "children"):
        for base_name in self._extract_var_basenames_from_tree(tail, allow_single_ident=True):
            self._mark_var_by_basename(
                base_name,
                context.env,
                path,
                is_ui_read=is_ui_read,
            )
        return

    raise ValueError(f"_walk_tail: unexpected tail type {type(tail).__name__}: {tail}")


def _extract_var_basenames_from_tree(
    self,
    node: Any,
    allow_single_ident: bool = False,
) -> set[str]:
    names: set[str] = set()

    def looks_like_varpath(value: str) -> bool:
        return "." in value and value.split(".", 1)[0].strip() != ""

    def looks_like_ident(value: str) -> bool:
        return bool(value) and value[0].isalpha()

    def visit(value: Any) -> None:
        if value is None:
            return
        if isinstance(value, dict) and const.KEY_VAR_NAME in value:
            full = value[const.KEY_VAR_NAME]
            if isinstance(full, str) and full:
                names.add(full.split(".", 1)[0])
            return
        if isinstance(value, str):
            stripped = value.strip()
            if looks_like_varpath(stripped):
                names.add(stripped.split(".", 1)[0])
            elif allow_single_ident and looks_like_ident(stripped):
                names.add(stripped)
            return
        if isinstance(value, list):
            for item in value:
                visit(item)
            return
        if hasattr(value, "children"):
            for child in getattr(value, "children", []):
                visit(child)

    visit(node)
    return names


def _mark_var_by_basename(
    self,
    base_name: str | None,
    env: dict[str, Variable],
    path: list[str],
    *,
    is_ui_read: bool = False,
) -> None:
    if not base_name:
        return
    normalized = base_name.lower()
    if normalized in _IGNORED_GRAPHICS_TAIL_BASENAMES:
        return
    var = env.get(normalized)
    if var is None:
        var = self._lookup_global_variable(normalized)
    if var is not None:
        if is_ui_read:
            self._get_usage(var).mark_ui_read(path)
        else:
            self._get_usage(var).mark_read(path)
    elif self.debug:
        log.debug(
            "Variable not found in scope: %s (env size=%d, path=%s)",
            base_name,
            len(env),
            " -> ".join(path),
        )


def _walk_module_code(
    self,
    mc: ModuleCode | None,
    context: ScopeContext,
    path: list[str],
) -> None:
    """Walk ModuleCode with scope context."""
    if mc is None:
        return

    for sequence in mc.sequences or []:
        label = f"SEQ:{getattr(sequence, 'name', '<unnamed>')}"
        self._push_site(label)
        try:
            self._walk_sequence(sequence, context, path)
        finally:
            self._pop_site()

    for equation in mc.equations or []:
        label = f"EQ:{getattr(equation, 'name', '<unnamed>')}"
        self._push_site(label)
        try:
            for stmt in equation.code or []:
                self._walk_stmt_or_expr(stmt, context, path)
        finally:
            self._pop_site()


def _walk_sequence(
    self,
    seq: Sequence,
    context: ScopeContext,
    path: list[str],
) -> None:
    """Walk Sequence with scope context."""
    for node in seq.code or []:
        if isinstance(node, SFCStep):
            base = f"STEP:{node.name}"
            self._push_site(f"{base}:ENTER")
            try:
                for stmt in node.code.enter or []:
                    self._walk_stmt_or_expr(stmt, context, path)
            finally:
                self._pop_site()

            self._push_site(f"{base}:ACTIVE")
            try:
                for stmt in node.code.active or []:
                    self._walk_stmt_or_expr(stmt, context, path)
            finally:
                self._pop_site()

            self._push_site(f"{base}:EXIT")
            try:
                for stmt in node.code.exit or []:
                    self._walk_stmt_or_expr(stmt, context, path)
            finally:
                self._pop_site()

        elif isinstance(node, SFCTransition):
            label = f"TRANS:{node.name or '<unnamed>'}"
            self._push_site(label)
            try:
                self._walk_stmt_or_expr(node.condition, context, path)
            finally:
                self._pop_site()

        elif isinstance(node, SFCAlternative):
            for index, branch in enumerate(node.branches or []):
                self._push_site(f"ALT:BRANCH:{index}")
                try:
                    self._walk_seq_nodes(branch, context.env, path)
                finally:
                    self._pop_site()

        elif isinstance(node, SFCParallel):
            for index, branch in enumerate(node.branches or []):
                self._push_site(f"PAR:BRANCH:{index}")
                try:
                    self._walk_seq_nodes(branch, context.env, path)
                finally:
                    self._pop_site()

        elif isinstance(node, SFCSubsequence):
            self._push_site(f"SUBSEQ:{getattr(node, 'name', '<unnamed>')}")
            try:
                self._walk_seq_nodes(node.body, context.env, path)
            finally:
                self._pop_site()

        elif isinstance(node, SFCTransitionSub):
            self._push_site(f"TRANS-SUB:{getattr(node, 'name', '<unnamed>')}")
            try:
                self._walk_seq_nodes(node.body, context.env, path)
            finally:
                self._pop_site()

        elif isinstance(node, SFCFork | SFCBreak):
            continue


def _walk_seq_nodes(
    self,
    nodes: list[Any],
    env: dict[str, Variable],
    path: list[str],
) -> None:
    display_path: list[str] = []
    if path:
        display_path.append(decorate_segment(path[0], "BP"))
        display_path.extend(path[1:])
    context = ScopeContext(
        env=env,
        param_mappings={},
        module_path=path.copy(),
        display_module_path=display_path,
        parent_context=None,
    )
    for node in nodes:
        if isinstance(node, SFCStep):
            for stmt in node.code.enter or []:
                self._walk_stmt_or_expr(stmt, context, path)
            for stmt in node.code.active or []:
                self._walk_stmt_or_expr(stmt, context, path)
            for stmt in node.code.exit or []:
                self._walk_stmt_or_expr(stmt, context, path)
        elif isinstance(node, SFCTransition):
            self._walk_stmt_or_expr(node.condition, context, path)
        elif isinstance(node, SFCAlternative | SFCParallel):
            for branch in node.branches:
                self._walk_seq_nodes(branch, env, path)
        elif isinstance(node, SFCSubsequence | SFCTransitionSub):
            self._walk_seq_nodes(node.body, env, path)


def _walk_stmt_or_expr(
    self,
    obj: Any,
    context: ScopeContext,
    path: list[str],
    *,
    is_ui_read: bool = False,
) -> None:
    if hasattr(obj, "data") and obj.data == const.KEY_STATEMENT:
        for child in getattr(obj, "children", []):
            self._walk_stmt_or_expr(child, context, path, is_ui_read=is_ui_read)
        return

    if isinstance(obj, IntLiteral | FloatLiteral):
        span = getattr(obj, "span", None)
        value = int(obj) if isinstance(obj, IntLiteral) else float(obj)
        self._add_magic_number_issue(path, value, span)
        return

    if isinstance(obj, tuple) and obj and obj[0] == const.GRAMMAR_VALUE_IF:
        _, branches, else_block = obj
        for cond, stmts in branches or []:
            self._walk_stmt_or_expr(cond, context, path, is_ui_read=is_ui_read)
            for stmt in stmts or []:
                self._walk_stmt_or_expr(stmt, context, path, is_ui_read=is_ui_read)
        for stmt in else_block or []:
            self._walk_stmt_or_expr(stmt, context, path, is_ui_read=is_ui_read)
        return

    if isinstance(obj, tuple) and obj and obj[0] in (const.KEY_TERNARY, "Ternary"):
        _, branches, else_expr = obj
        for cond, then_expr in branches or []:
            self._walk_stmt_or_expr(cond, context, path, is_ui_read=is_ui_read)
            self._walk_stmt_or_expr(then_expr, context, path, is_ui_read=is_ui_read)
        if else_expr is not None:
            self._walk_stmt_or_expr(else_expr, context, path, is_ui_read=is_ui_read)
        return

    if isinstance(obj, tuple) and obj and obj[0] == const.KEY_FUNCTION_CALL:
        _, fn_name, args = obj
        self._handle_function_call(
            fn_name,
            args or [],
            context,
            path,
            is_ui_read=is_ui_read,
        )
        return

    if isinstance(obj, tuple) and obj and obj[0] in (const.GRAMMAR_VALUE_OR, const.GRAMMAR_VALUE_AND):
        for sub in obj[1] or []:
            self._walk_stmt_or_expr(sub, context, path, is_ui_read=is_ui_read)
        return

    if isinstance(obj, tuple) and obj and obj[0] == const.GRAMMAR_VALUE_NOT:
        self._walk_stmt_or_expr(obj[1], context, path, is_ui_read=is_ui_read)
        return

    if isinstance(obj, tuple) and obj and obj[0] in (const.KEY_COMPARE, "compare"):
        _, left, pairs = obj
        self._walk_stmt_or_expr(left, context, path, is_ui_read=is_ui_read)
        for _symbol, rhs in pairs or []:
            self._walk_stmt_or_expr(rhs, context, path, is_ui_read=is_ui_read)
        return

    if isinstance(obj, tuple) and obj and obj[0] in (const.KEY_ADD, const.KEY_MUL):
        _, left, parts = obj
        self._walk_stmt_or_expr(left, context, path, is_ui_read=is_ui_read)
        for _operator_value, rhs in parts or []:
            self._walk_stmt_or_expr(rhs, context, path, is_ui_read=is_ui_read)
        return

    if isinstance(obj, tuple) and obj and obj[0] in (const.KEY_PLUS, const.KEY_MINUS):
        _, inner = obj
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
        tail = obj[const.KEY_ENABLE_EXPRESSION]
        self._walk_stmt_or_expr(tail, context, path, is_ui_read=is_ui_read)
        return

    if isinstance(obj, Tree):
        if obj.data == const.KEY_ENABLE_EXPRESSION:
            for child in obj.children:
                self._walk_stmt_or_expr(child, context, path, is_ui_read=is_ui_read)
            return
        if obj.data == const.GRAMMAR_VALUE_INVAR_PREFIX:
            for child in obj.children:
                self._walk_stmt_or_expr(child, context, path, is_ui_read=is_ui_read)
            return

    if isinstance(obj, list):
        for item in obj:
            self._walk_stmt_or_expr(item, context, path, is_ui_read=is_ui_read)
        return

    if isinstance(obj, dict) and const.KEY_VAR_NAME in obj:
        full_name = obj[const.KEY_VAR_NAME]
        self._mark_ref_access(
            full_name,
            context,
            path,
            AccessKind.READ,
            is_ui_read=is_ui_read,
        )
        return

    if isinstance(obj, tuple) and obj and obj[0] == const.KEY_ASSIGN:
        _, target, expr = obj

        if isinstance(target, dict) and const.KEY_VAR_NAME in target:
            full_name = target[const.KEY_VAR_NAME]
            self._mark_ref_access(full_name, context, path, AccessKind.WRITE)
            self._record_assignment_effect_flow(full_name, expr, context)

        self._walk_stmt_or_expr(expr, context, path, is_ui_read=is_ui_read)
        return
