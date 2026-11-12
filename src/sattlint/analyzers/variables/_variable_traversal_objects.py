"""Header and object traversal helpers for variable analysis."""

# pyright: reportPrivateUsage=false, reportUnusedFunction=false

from __future__ import annotations

from typing import TYPE_CHECKING

from sattlint.parser_api import (
    GraphObject,
    InteractObject,
    ModuleDef,
    ModuleHeader,
    ModuleTypeDef,
    ProcedureCall,
    VarRef,
    VarTail,
    walk,
)

from ...resolution import AccessKind
from ...resolution.scope import ScopeContext

if TYPE_CHECKING:
    from . import VariablesAnalyzer


def _walk_header_enable(self: VariablesAnalyzer, header: ModuleHeader, context: ScopeContext, path: list[str]) -> None:
    arguments = header.arguments
    if arguments.enable is not None and arguments.enable.tail is not None:
        self._walk_tail(arguments.enable.tail, context, path, is_ui_read=True)
    if arguments.module_in_view is not None and arguments.module_in_view.tail is not None:
        self._walk_tail(arguments.module_in_view.tail, context, path, is_ui_read=True)
    for assign in arguments.assigns:
        if assign.tail is not None:
            self._walk_tail(assign.tail, context, path, is_ui_read=True)


def _walk_header_invoke_tails(
    self: VariablesAnalyzer, header: ModuleHeader, context: ScopeContext, path: list[str]
) -> None:
    for tail in header.invoke_coord_tails or []:
        self._walk_tail(tail, context, path, is_ui_read=True)


def _walk_header_groupconn(
    self: VariablesAnalyzer, header: ModuleHeader, context: ScopeContext, path: list[str]
) -> None:
    groupconn = header.groupconn
    if not isinstance(groupconn, VarRef):
        return
    base = groupconn.name
    if not base:
        return
    local_var = context.env.get(base.casefold())
    if local_var is not None:
        self._get_usage(local_var).mark_read(path)
        return
    var, _field_prefix, _decl_path, _decl_display = context.resolve_variable(base)
    if var is not None:
        self._mark_ref_access(base, context, path, AccessKind.READ)
        return
    var = self._lookup_env_var_from_varname_dict(base, context.env)
    if var is not None:
        self._get_usage(var).mark_read(path)


def _walk_typedef_groupconn(self: VariablesAnalyzer, mt: ModuleTypeDef, context: ScopeContext, path: list[str]) -> None:
    groupconn = mt.groupconn
    if not isinstance(groupconn, VarRef):
        return
    base = groupconn.name
    if not base:
        return
    local_var = context.env.get(base.casefold())
    if local_var is not None:
        self._get_usage(local_var).mark_read(path)
        return
    var, _field_prefix, _decl_path, _decl_display = context.resolve_variable(base)
    if var is not None:
        self._mark_ref_access(base, context, path, AccessKind.READ)


def _walk_moduledef(
    self: VariablesAnalyzer,
    mdef: ModuleDef | None,
    context: ScopeContext,
    path: list[str],
) -> None:
    if mdef is None:
        return
    for graph_object in mdef.graph_objects or []:
        self._walk_graph_object(graph_object, context, path)
    for interact_object in mdef.interact_objects or []:
        self._walk_interact_object(interact_object, context, path)

    clipping = mdef.clipping
    if clipping is not None:
        for tail in clipping.tails:
            self._walk_tail(tail, context, path, is_ui_read=True)


def _mark_reference_read(
    self: VariablesAnalyzer,
    name: str | None,
    context: ScopeContext,
    path: list[str],
    *,
    is_ui_read: bool,
) -> None:
    if not name:
        return
    resolved_var, _field_path, _decl_path, _decl_display = context.resolve_variable(name)
    if resolved_var is not None:
        self._mark_ref_access(name, context, path, AccessKind.READ, is_ui_read=is_ui_read)
        return
    self._mark_var_by_basename(name.split(".", 1)[0], context.env, path, is_ui_read=is_ui_read)


def _walk_graph_object(self: VariablesAnalyzer, go: GraphObject, context: ScopeContext, path: list[str]) -> None:
    properties = go.properties
    for text_var in properties.get("text_vars", []) or []:
        base = text_var.name.split(".", 1)[0] if text_var.name else None
        self._mark_var_by_basename(base, context.env, path, is_ui_read=True)
    for tail in properties.get("tails", []) or []:
        self._walk_tail(tail, context, path, is_ui_read=True)


def _walk_interact_object(self: VariablesAnalyzer, io: InteractObject, context: ScopeContext, path: list[str]) -> None:
    for event in walk(io, prune=lambda node: isinstance(node, ProcedureCall)):
        node = event.node
        if isinstance(node, VarRef):
            _mark_reference_read(self, node.name, context, path, is_ui_read=True)
            continue
        if isinstance(node, VarTail):
            self._walk_tail(node, context, path, is_ui_read=True)

    procedure = io.properties.get("procedure")
    if isinstance(procedure, ProcedureCall):
        self._handle_function_call(
            procedure.name,
            list(procedure.args),
            context,
            path,
            is_ui_read=True,
        )


__all__ = [
    "_walk_graph_object",
    "_walk_header_enable",
    "_walk_header_groupconn",
    "_walk_header_invoke_tails",
    "_walk_interact_object",
    "_walk_moduledef",
    "_walk_typedef_groupconn",
]
