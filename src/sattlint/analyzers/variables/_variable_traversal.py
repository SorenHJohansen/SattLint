"""Traversal helpers for the variable usage analyzer."""

# pyright: reportPrivateUsage=false, reportUnusedFunction=false

from __future__ import annotations

from typing import Any

from ...resolution.scope import ScopeContext
from ._variable_traversal_support import (
    _extract_var_basenames_from_tree,
    _handle_function_call,
    _mark_var_by_basename,
    _repath_context,
    _scan_for_varrefs,
    _walk_graph_object,
    _walk_header_enable,
    _walk_header_groupconn,
    _walk_header_invoke_tails,
    _walk_interact_object,
    _walk_moduledef,
    _walk_output_tail,
    _walk_tail,
    _walk_typedef_groupconn,
)
from ._variable_traversal_walk import (
    _walk_module_code,
    _walk_seq_nodes,
    _walk_sequence,
    _walk_stmt_or_expr,
)


class VariablesTraversalMixin:
    def _repath_context(
        self: Any,
        context: ScopeContext,
        module_path: list[str],
        display_module_path: list[str],
    ) -> ScopeContext:
        return _repath_context(self, context, module_path, display_module_path)

    def _handle_function_call(
        self: Any,
        fn_name: str | None,
        args: list[Any],
        context: ScopeContext,
        path: list[str],
        *,
        is_ui_read: bool = False,
    ) -> None:
        _handle_function_call(self, fn_name, args, context, path, is_ui_read=is_ui_read)

    def _walk_header_enable(self: Any, header: Any, context: ScopeContext, path: list[str]) -> None:
        _walk_header_enable(self, header, context, path)

    def _walk_header_invoke_tails(
        self: Any,
        header: Any,
        context: ScopeContext,
        path: list[str],
    ) -> None:
        _walk_header_invoke_tails(self, header, context, path)

    def _walk_header_groupconn(
        self: Any,
        header: Any,
        context: ScopeContext,
        path: list[str],
    ) -> None:
        _walk_header_groupconn(self, header, context, path)

    def _walk_typedef_groupconn(
        self: Any,
        moduletype: Any,
        context: ScopeContext,
        path: list[str],
    ) -> None:
        _walk_typedef_groupconn(self, moduletype, context, path)

    def _walk_moduledef(self: Any, moduledef: Any, context: ScopeContext, path: list[str]) -> None:
        _walk_moduledef(self, moduledef, context, path)

    def _walk_graph_object(
        self: Any,
        graph_object: Any,
        context: ScopeContext,
        path: list[str],
    ) -> None:
        _walk_graph_object(self, graph_object, context, path)

    def _walk_interact_object(
        self: Any,
        interact_object: Any,
        context: ScopeContext,
        path: list[str],
    ) -> None:
        _walk_interact_object(self, interact_object, context, path)

    def _scan_for_varrefs(
        self: Any,
        obj: Any,
        context: ScopeContext,
        path: list[str],
        *,
        is_ui_read: bool = False,
    ) -> None:
        _scan_for_varrefs(self, obj, context, path, is_ui_read=is_ui_read)

    def _walk_output_tail(
        self: Any,
        tail: Any,
        context: ScopeContext,
        path: list[str],
        *,
        is_ui_read: bool = False,
    ) -> None:
        _walk_output_tail(self, tail, context, path, is_ui_read=is_ui_read)

    def _walk_tail(
        self: Any,
        tail: Any,
        context: ScopeContext,
        path: list[str],
        *,
        is_ui_read: bool = False,
    ) -> None:
        _walk_tail(self, tail, context, path, is_ui_read=is_ui_read)

    def _extract_var_basenames_from_tree(
        self: Any,
        node: Any,
        allow_single_ident: bool = False,
    ) -> set[str]:
        return _extract_var_basenames_from_tree(self, node, allow_single_ident)

    def _mark_var_by_basename(
        self: Any,
        base_name: str | None,
        env: dict[str, Any],
        path: list[str],
        *,
        is_ui_read: bool = False,
    ) -> None:
        _mark_var_by_basename(self, base_name, env, path, is_ui_read=is_ui_read)

    def _walk_module_code(self: Any, modulecode: Any, context: ScopeContext, path: list[str]) -> None:
        _walk_module_code(self, modulecode, context, path)

    def _walk_sequence(self: Any, sequence: Any, context: ScopeContext, path: list[str]) -> None:
        _walk_sequence(self, sequence, context, path)

    def _walk_seq_nodes(
        self: Any,
        nodes: list[Any],
        env: dict[str, Any],
        path: list[str],
        context: ScopeContext,
    ) -> None:
        _walk_seq_nodes(self, nodes, env, path, context)

    def _walk_stmt_or_expr(
        self: Any,
        obj: Any,
        context: ScopeContext,
        path: list[str],
        *,
        is_ui_read: bool = False,
    ) -> None:
        _walk_stmt_or_expr(self, obj, context, path, is_ui_read=is_ui_read)


__all__ = [
    "VariablesTraversalMixin",
    "_extract_var_basenames_from_tree",
    "_handle_function_call",
    "_mark_var_by_basename",
    "_repath_context",
    "_scan_for_varrefs",
    "_walk_graph_object",
    "_walk_header_enable",
    "_walk_header_groupconn",
    "_walk_header_invoke_tails",
    "_walk_interact_object",
    "_walk_module_code",
    "_walk_moduledef",
    "_walk_output_tail",
    "_walk_seq_nodes",
    "_walk_sequence",
    "_walk_stmt_or_expr",
    "_walk_tail",
    "_walk_typedef_groupconn",
]
