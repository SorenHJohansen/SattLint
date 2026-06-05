"""Header and object traversal helpers for variable analysis."""

# pyright: reportPrivateUsage=false, reportUnusedFunction=false

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from sattline_parser.models.ast_model import ModuleDef

from ..grammar import constants as const
from ..resolution import AccessKind
from ..resolution.scope import ScopeContext

if TYPE_CHECKING:
    from .variables import VariablesAnalyzer


def _object_mapping(value: object) -> dict[str, object] | None:
    return cast(dict[str, object], value) if isinstance(value, dict) else None


def _walk_header_enable(self: VariablesAnalyzer, header: Any, context: ScopeContext, path: list[str]) -> None:
    tail = getattr(header, "enable_tail", None)
    if tail is not None:
        self._walk_tail(tail, context, path, is_ui_read=True)


def _walk_header_invoke_tails(self: VariablesAnalyzer, header: Any, context: ScopeContext, path: list[str]) -> None:
    for tail in getattr(header, "invoke_coord_tails", []) or []:
        self._walk_tail(tail, context, path, is_ui_read=True)


def _walk_header_groupconn(self: VariablesAnalyzer, header: Any, context: ScopeContext, path: list[str]) -> None:
    var_dict = _object_mapping(getattr(header, "groupconn", None))
    if var_dict is None:
        return
    base = var_dict.get(const.KEY_VAR_NAME)
    if not isinstance(base, str):
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


def _walk_typedef_groupconn(self: VariablesAnalyzer, mt: Any, context: ScopeContext, path: list[str]) -> None:
    var_dict = _object_mapping(getattr(mt, "groupconn", None))
    if var_dict is None:
        return
    base = var_dict.get(const.KEY_VAR_NAME)
    if not isinstance(base, str):
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

    props = cast(dict[str, Any], getattr(mdef, "properties", {}) or {})
    for tail in cast(list[Any], props.get(const.KEY_TAILS, []) or []):
        self._walk_tail(tail, context, path, is_ui_read=True)


def _walk_graph_object(self: VariablesAnalyzer, go: Any, context: ScopeContext, path: list[str]) -> None:
    props = cast(dict[str, Any], getattr(go, "properties", {}) or {})
    for text_var in cast(list[Any], props.get("text_vars", []) or []):
        base = text_var.split(".", 1)[0] if isinstance(text_var, str) else None
        self._mark_var_by_basename(base, context.env, path, is_ui_read=True)
    for tail in cast(list[Any], props.get(const.KEY_TAILS, []) or []):
        self._walk_tail(tail, context, path, is_ui_read=True)


def _walk_interact_object(self: VariablesAnalyzer, io: Any, context: ScopeContext, path: list[str]) -> None:
    props = cast(dict[str, Any], getattr(io, "properties", {}) or {})
    for tail in cast(list[Any], props.get(const.KEY_TAILS, []) or []):
        if getattr(tail, "data", None) == const.GRAMMAR_VALUE_OUTVAR_PREFIX:
            self._walk_output_tail(tail, context, path, is_ui_read=True)
        else:
            self._walk_tail(tail, context, path, is_ui_read=True)
    self._scan_for_varrefs(props.get(const.KEY_BODY), context, path, is_ui_read=True)

    procedure = props.get(const.KEY_PROCEDURE)
    procedure_mapping = _object_mapping(procedure)
    procedure_args = procedure_mapping.get(const.KEY_ARGS) if procedure_mapping is not None else None
    if procedure_mapping is not None and (
        isinstance(procedure_mapping.get(const.KEY_NAME), str) or isinstance(procedure_args, list)
    ):
        fn_name = procedure_mapping.get(const.KEY_NAME)
        self._handle_function_call(
            fn_name if isinstance(fn_name, str) else None,
            cast(list[Any], procedure_args) if isinstance(procedure_args, list) else [],
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
