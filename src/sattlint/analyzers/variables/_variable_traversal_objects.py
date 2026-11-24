"""Header and object traversal helpers for variable analysis."""

# pyright: reportPrivateUsage=false, reportUnusedFunction=false

from __future__ import annotations

from typing import TYPE_CHECKING

from sattlint.parser_api import (
    AssignClause,
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


#: Interactors that display the state they write. Each one reads its bound value
#: back to render the widget, so the binding is a read as well as a write.
#: A momentary button without a toggle action still shows its state.
_STATE_BINDING_INTERACT_TYPES = frozenset({"textbox_", "checkbox_", "optbut_", "combut_"})

#: The interactor property that binds a widget's state variable.
_STATE_BINDING_PROPERTY = "variable"


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
        _mark_reference_read(self, text_var.name, context, path, is_ui_read=True)
    for tail in properties.get("tails", []) or []:
        self._walk_tail(tail, context, path, is_ui_read=True)


def _state_binding_tail(interact_object: InteractObject) -> VarTail | None:
    """The output tail bound to a value widget's state variable.

    Only the ``Variable`` property carries the state a value widget displays;
    event flags such as ``Value_Changed`` and procedure arguments stay
    write-only. Widgets that do not display their state are left alone.
    """
    if interact_object.type.casefold() not in _STATE_BINDING_INTERACT_TYPES:
        return None
    properties = interact_object.properties
    body = properties.get("body") or ()
    assigns = properties.get("assigns") or ()
    for clause in (*body, *assigns):
        if not isinstance(clause, AssignClause):
            continue
        if clause.name.casefold() != _STATE_BINDING_PROPERTY:
            continue
        tail = clause.tail
        if isinstance(tail, VarTail) and tail.direction == "out":
            return tail
    return None


def _walk_interact_object(self: VariablesAnalyzer, io: InteractObject, context: ScopeContext, path: list[str]) -> None:
    state_tail = _state_binding_tail(io)
    if state_tail is not None:
        _mark_reference_read(self, state_tail.bound_name, context, path, is_ui_read=True)

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
