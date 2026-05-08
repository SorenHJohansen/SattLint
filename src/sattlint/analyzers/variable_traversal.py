"""Traversal helpers for the variable usage analyzer."""

# pyright: reportPrivateUsage=false, reportUnusedFunction=false

from __future__ import annotations

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
    _walk_tail,
    _walk_typedef_groupconn,
)
from ._variable_traversal_walk import (
    _walk_module_code,
    _walk_seq_nodes,
    _walk_sequence,
    _walk_stmt_or_expr,
)

__all__ = [
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
    "_walk_seq_nodes",
    "_walk_sequence",
    "_walk_stmt_or_expr",
    "_walk_tail",
    "_walk_typedef_groupconn",
]
