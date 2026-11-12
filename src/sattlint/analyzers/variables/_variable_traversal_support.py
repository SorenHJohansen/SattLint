"""Shared traversal support helpers for the variable usage analyzer."""

# pyright: reportPrivateUsage=false, reportUnusedFunction=false

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, cast

from sattlint.parser_api import (
    BinOp,
    BoolOp,
    Compare,
    FloatLiteral,
    FuncCall,
    IntLiteral,
    LitStringTail,
    NotOp,
    TernaryOp,
    UnaryOp,
    Variable,
    VarRef,
    VarTail,
    get_function_signature,
)

from ...reporting.variables_report import IssueKind, VariableIssue
from ...resolution import AccessKind
from ...resolution.scope import ScopeContext
from ...utils.casefolding import is_anytype_name
from ..shared._array_builtins import get_dynamic_array_builtin_spec
from ._variable_traversal_objects import (
    _walk_graph_object,
    _walk_header_enable,
    _walk_header_groupconn,
    _walk_header_invoke_tails,
    _walk_interact_object,
    _walk_moduledef,
    _walk_typedef_groupconn,
)

if TYPE_CHECKING:
    from . import VariablesAnalyzer

log = logging.getLogger("SattLint")

_IGNORED_BOOLEAN_CONSTANT_BASENAMES = {
    "off",
    "on",
}

_IGNORED_INTERACT_TAIL_BASENAMES = {
    "bool_value",
    "resetaction",
    "setaction",
    "setval_",
    "string_value",
    "toggleaction",
    "togglewindow",
    "windowcontent",
}

_IGNORED_GRAPHICS_TAIL_BASENAMES = {
    "abs_",
    "bool_value",
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
    *_IGNORED_BOOLEAN_CONSTANT_BASENAMES,
    *_IGNORED_INTERACT_TAIL_BASENAMES,
}

_POSITIONAL_RECORD_COMPONENT_BUILTINS: dict[str, str] = {
    "getrecordcomponent": "reads",
    "getrecordcompnosort": "reads",
    "putrecordcomponent": "writes",
    "putrecordcompnosort": "writes",
}


def _var_name_of(value: Any) -> str | None:
    if isinstance(value, VarRef):
        return value.name or None
    return None


def _repath_context(
    self: VariablesAnalyzer,
    context: ScopeContext,
    module_path: list[str],
    display_module_path: list[str],
) -> ScopeContext:
    return ScopeContext(
        env=context.env,
        param_mappings={},
        module_path=module_path,
        display_module_path=display_module_path,
        moduleparameter_keys=context.moduleparameter_keys,
        current_library=context.current_library,
        parent_context=context,
    )


def _handle_status_argument(
    self: VariablesAnalyzer,
    status: Any,
    context: ScopeContext,
    path: list[str],
    *,
    is_ui_read: bool,
) -> None:
    status_name = _var_name_of(status)
    if status_name is not None:
        self._mark_ref_access(
            status_name,
            context,
            path,
            AccessKind.WRITE,
            is_ui_read=is_ui_read,
        )
        return
    self._walk_stmt_or_expr(status, context, path, is_ui_read=is_ui_read)


def _walk_extra_call_arguments(
    self: VariablesAnalyzer,
    args: list[Any],
    context: ScopeContext,
    path: list[str],
    *,
    start_index: int,
    is_ui_read: bool,
) -> None:
    for extra in args[start_index:]:
        self._walk_stmt_or_expr(extra, context, path, is_ui_read=is_ui_read)


def _literal_component_index(value: Any) -> int | None:
    if isinstance(value, IntLiteral | int) and not isinstance(value, bool):
        return int(value)
    return None


def _record_component_field_name(
    self: VariablesAnalyzer,
    *,
    variable: Variable,
    field_path: str,
    component_index: int,
    fn_name: str,
    syntactic_ref: str,
    path: list[str],
) -> str | None:
    if component_index <= 0:
        return None

    current_type: object = variable.datatype
    if field_path:
        try:
            current_type = self._strict_datatype_at_field_prefix(
                variable.datatype,
                field_path,
                fn_name=fn_name,
                syntactic_ref=syntactic_ref,
                resolved_var_name=variable.name,
                use_path=path,
            )
        except ValueError:
            return None

    if isinstance(current_type, str) and is_anytype_name(current_type):
        return None
    if not isinstance(current_type, str):
        return None

    record_type = self.type_graph.record(current_type)
    if record_type is None:
        return None

    fields = list(record_type.fields_by_key.values())
    if component_index > len(fields):
        return None
    return fields[component_index - 1].name


def _append_record_component_order_issue(
    self: VariablesAnalyzer,
    fn_name: str,
    args: list[Any],
    context: ScopeContext,
    path: list[str],
) -> None:
    if len(args) < 2:
        return

    record_ref = _var_name_of(args[0])
    if record_ref is None:
        return

    variable, field_path, _decl_module_path, _decl_display = context.resolve_variable(record_ref)
    if variable is None:
        return

    fn_key = fn_name.casefold()
    action = _POSITIONAL_RECORD_COMPONENT_BUILTINS.get(fn_key)
    if action is None:
        return

    role = f"{fn_name} {action} record components by numeric position; reordering datatype fields can change behavior"
    datatype_name: str | None = None
    if isinstance(variable.datatype, str) and not is_anytype_name(variable.datatype):
        datatype_name = variable.datatype
    if datatype_name is None:
        return

    datatype_key = datatype_name.casefold()
    if datatype_key in self._record_component_order_datatypes_seen:
        return

    component_index = _literal_component_index(args[1])
    if component_index is not None:
        field_name = _record_component_field_name(
            self,
            variable=variable,
            field_path=field_path,
            component_index=component_index,
            fn_name=fn_name,
            syntactic_ref=record_ref,
            path=path,
        )
        if field_name is None:
            role = f"{role} (index {component_index})"
        else:
            role = f"{role} (index {component_index} => field '{field_name}')"

    self._record_component_order_datatypes_seen.add(datatype_key)
    self.append_issue(
        VariableIssue(
            kind=IssueKind.RECORD_COMPONENT_ORDER_DEPENDENCE,
            module_path=path.copy(),
            variable=variable,
            datatype_name=datatype_name,
            role=role,
            site=self._site_str() or None,
            field_path=field_path or None,
        )
    )


def _handle_function_call(  # noqa: PLR0915
    self: VariablesAnalyzer,
    fn_name: str | None,
    args: list[Any],
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
    self._record_ignorable_output_bindings(fn_name, args or [], context)
    fn_key = fn_name.casefold()
    if fn_key in _POSITIONAL_RECORD_COMPONENT_BUILTINS:
        _append_record_component_order_issue(self, fn_name, args or [], context, path)

    if fn_key in ("copyvariable", "copyvarnosort"):
        if len(args or []) < 2:
            raise ValueError(f"{fn_name}: expected at least 2 arguments (Source, Destination)")

        src = args[0]
        dst = args[1]
        src_name = _var_name_of(src)
        dst_name = _var_name_of(dst)
        if src_name is None:
            raise ValueError(f"{fn_name}: Source must be a variable reference")
        if dst_name is None:
            raise ValueError(f"{fn_name}: Destination must be a variable reference")

        self._mark_record_wide_builtin_access(
            src_name,
            kind=AccessKind.READ,
            fn_name=fn_name,
            context=context,
            path=path,
            is_ui_read=is_ui_read,
        )
        self._mark_record_wide_builtin_access(
            dst_name,
            kind=AccessKind.WRITE,
            fn_name=fn_name,
            context=context,
            path=path,
            is_ui_read=is_ui_read,
        )

        if len(args) >= 3:
            _handle_status_argument(self, args[2], context, path, is_ui_read=is_ui_read)

        if len(args) > 3:
            _walk_extra_call_arguments(self, args, context, path, start_index=3, is_ui_read=is_ui_read)
        self._record_function_call_effect_flow(fn_name, args or [], context)
        return

    if fn_key == "initvariable":
        if len(args or []) < 1:
            raise ValueError(f"{fn_name}: expected at least 1 argument (Rec)")

        rec = args[0]
        rec_name = _var_name_of(rec)
        if rec_name is None:
            raise ValueError(f"{fn_name}: Rec must be a variable reference")

        self._mark_record_wide_builtin_access(
            rec_name,
            kind=AccessKind.WRITE,
            fn_name=fn_name,
            context=context,
            path=path,
            is_ui_read=is_ui_read,
        )

        if len(args) >= 2:
            init_rec = args[1]
            init_rec_name = _var_name_of(init_rec)
            if init_rec_name is not None:
                resolved_init_rec, _field_prefix, _decl_path, _decl_display = context.resolve_variable(init_rec_name)
                if resolved_init_rec is not None:
                    self._mark_record_wide_builtin_access(
                        init_rec_name,
                        kind=AccessKind.READ,
                        fn_name=fn_name,
                        context=context,
                        path=path,
                        is_ui_read=is_ui_read,
                    )
                else:
                    self._walk_stmt_or_expr(init_rec, context, path, is_ui_read=is_ui_read)
            else:
                self._walk_stmt_or_expr(init_rec, context, path, is_ui_read=is_ui_read)

        if len(args) >= 3:
            _handle_status_argument(self, args[2], context, path, is_ui_read=is_ui_read)

        if len(args) > 3:
            _walk_extra_call_arguments(self, args, context, path, start_index=3, is_ui_read=is_ui_read)
        self._record_function_call_effect_flow(fn_name, args or [], context)
        return

    array_spec = get_dynamic_array_builtin_spec(fn_name)
    if array_spec is not None:
        handled_indexes: set[int] = set()

        if len(args or []) > array_spec.array_index:
            array_arg = args[array_spec.array_index]
            array_name = _var_name_of(array_arg)
            handled_indexes.add(array_spec.array_index)
            if array_name is not None:
                for access_kind in array_spec.array_accesses:
                    self._mark_ref_access(
                        array_name,
                        context,
                        path,
                        access_kind,
                        is_ui_read=is_ui_read,
                    )
            else:
                self._walk_stmt_or_expr(array_arg, context, path, is_ui_read=is_ui_read)
        else:
            array_name = None

        if len(args or []) > array_spec.element_index:
            element_arg = args[array_spec.element_index]
            element_name = _var_name_of(element_arg)
            handled_indexes.add(array_spec.element_index)
            if element_name is not None:
                self._mark_record_wide_builtin_access(
                    element_name,
                    kind=array_spec.element_access,
                    fn_name=fn_name,
                    context=context,
                    path=path,
                    is_ui_read=is_ui_read,
                )
            else:
                self._walk_stmt_or_expr(element_arg, context, path, is_ui_read=is_ui_read)
        else:
            element_name = None

        if array_spec.status_index is not None and len(args or []) > array_spec.status_index:
            handled_indexes.add(array_spec.status_index)
            _handle_status_argument(
                self,
                args[array_spec.status_index],
                context,
                path,
                is_ui_read=is_ui_read,
            )

        for idx, arg in enumerate(args or []):
            if idx in handled_indexes:
                continue
            self._walk_stmt_or_expr(arg, context, path, is_ui_read=is_ui_read)

        self._record_function_call_effect_flow(fn_name, args or [], context)
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

        full_name = _var_name_of(arg)
        if full_name is not None:
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
        else:
            self._walk_stmt_or_expr(arg, context, path, is_ui_read=is_ui_read)

    self._record_function_call_effect_flow(fn_name, args or [], context)


def _walk_output_tail(
    self: VariablesAnalyzer,
    tail: Any,
    context: ScopeContext,
    path: list[str],
    *,
    is_ui_read: bool = False,
) -> None:
    if tail is None:
        return

    if isinstance(tail, VarTail):
        name = tail.bound_name
        if name:
            self._mark_ref_access(name, context, path, AccessKind.WRITE, is_ui_read=is_ui_read)
        return

    if isinstance(tail, LitStringTail | IntLiteral | FloatLiteral | int | float | bool):
        return

    if isinstance(tail, BinOp | BoolOp | Compare | FuncCall | NotOp | TernaryOp | UnaryOp | VarRef):
        self._walk_stmt_or_expr(tail, context, path, is_ui_read=is_ui_read)
        return

    raise ValueError(f"_walk_output_tail: unexpected tail type {type(tail).__name__}: {tail}")


def _walk_tail(
    self: VariablesAnalyzer,
    tail: Any,
    context: ScopeContext,
    path: list[str],
    *,
    is_ui_read: bool = False,
) -> None:
    if tail is None:
        return

    if isinstance(tail, VarTail):
        name = tail.bound_name
        if not name:
            return
        if tail.direction == "out":
            self._walk_output_tail(tail, context, path, is_ui_read=is_ui_read)
            return
        resolved_var, _field_path, _decl_path, _decl_display = context.resolve_variable(name)
        if resolved_var is not None:
            self._mark_ref_access(name, context, path, AccessKind.READ, is_ui_read=is_ui_read)
            return
        self._mark_var_by_basename(name.split(".", 1)[0], context.env, path, is_ui_read=is_ui_read)
        return

    if isinstance(tail, LitStringTail | IntLiteral | FloatLiteral | int | float | bool):
        return

    if isinstance(tail, BinOp | BoolOp | Compare | FuncCall | NotOp | TernaryOp | UnaryOp | VarRef):
        self._walk_stmt_or_expr(tail, context, path, is_ui_read=is_ui_read)
        return

    raise ValueError(f"_walk_tail: unexpected tail type {type(tail).__name__}: {tail}")


def _mark_var_by_basename(
    self: VariablesAnalyzer,
    base_name: str | None,
    env: dict[str, Variable],
    path: list[str],
    *,
    is_ui_read: bool = False,
) -> None:
    if not base_name:
        return
    normalized = base_name.casefold()
    if normalized in _IGNORED_GRAPHICS_TAIL_BASENAMES:
        return
    variable = env.get(normalized)
    if variable is None:
        variable = self._lookup_global_variable(normalized)
    if variable is not None:
        usage = self._get_usage(variable)
        if is_ui_read:
            usage.mark_ui_read(path)
        else:
            usage.mark_read(path)
        return
    if self.debug:
        self._unresolved_variable_lookup_total = getattr(self, "_unresolved_variable_lookup_total", 0) + 1
        unresolved_counts = cast(dict[str, int] | None, getattr(self, "_unresolved_variable_lookup_counts", None))
        if unresolved_counts is not None:
            unresolved_counts[base_name] = int(unresolved_counts.get(base_name, 0)) + 1
        unresolved_examples = cast(
            dict[str, tuple[int, str]] | None,
            getattr(self, "_unresolved_variable_lookup_examples", None),
        )
        if unresolved_examples is not None:
            unresolved_examples.setdefault(base_name, (len(env), " -> ".join(path)))


__all__ = [
    "_IGNORED_GRAPHICS_TAIL_BASENAMES",
    "_handle_function_call",
    "_mark_var_by_basename",
    "_repath_context",
    "_var_name_of",
    "_walk_graph_object",
    "_walk_header_enable",
    "_walk_header_groupconn",
    "_walk_header_invoke_tails",
    "_walk_interact_object",
    "_walk_moduledef",
    "_walk_output_tail",
    "_walk_tail",
    "_walk_typedef_groupconn",
]
