"""Shared traversal support helpers for the variable usage analyzer."""

# pyright: reportPrivateUsage=false, reportUnusedFunction=false

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, cast

from sattline_parser.models.ast_model import FloatLiteral, IntLiteral, Variable

from ..casefolding import is_anytype_name
from ..grammar import constants as const
from ..reporting.variables_report import IssueKind, VariableIssue
from ..resolution import AccessKind
from ..resolution.scope import ScopeContext
from ._variable_traversal_objects import (
    _walk_graph_object,
    _walk_header_enable,
    _walk_header_groupconn,
    _walk_header_invoke_tails,
    _walk_interact_object,
    _walk_moduledef,
    _walk_typedef_groupconn,
)
from .sattline_builtins import get_function_signature

if TYPE_CHECKING:
    from .variables import VariablesAnalyzer

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

_POSITIONAL_RECORD_COMPONENT_BUILTINS: dict[str, str] = {
    "getrecordcomponent": "reads",
    "getrecordcompnosort": "reads",
    "putrecordcomponent": "writes",
    "putrecordcompnosort": "writes",
}

type _StmtBranch = tuple[Any, list[Any]]
type _IfTuple = tuple[str, list[_StmtBranch] | None, list[Any] | None]
type _TernaryBranch = tuple[Any, Any]
type _TernaryTuple = tuple[str, list[_TernaryBranch] | None, Any | None]
type _FunctionCallTuple = tuple[str, str | None, list[Any] | None]
type _LogicalTuple = tuple[str, list[Any] | None]
type _ComparePair = tuple[Any, Any]
type _CompareTuple = tuple[str, Any, list[_ComparePair] | None]
type _BinaryOpPart = tuple[Any, Any]
type _BinaryOpTuple = tuple[str, Any, list[_BinaryOpPart] | None]
type _UnaryTuple = tuple[str, Any]
type _AssignTuple = tuple[str, Any, Any]


def _children_of(value: Any) -> list[Any] | None:
    children = getattr(value, "children", None)
    return cast(list[Any], children) if isinstance(children, list) else None


def _var_name_of(value: Any) -> str | None:
    if not isinstance(value, dict) or const.KEY_VAR_NAME not in value:
        return None
    full_name = cast(dict[str, object], value).get(const.KEY_VAR_NAME)
    return full_name if isinstance(full_name, str) and full_name else None


def _mapping_of(value: object) -> dict[str, Any] | None:
    return cast(dict[str, Any], value) if isinstance(value, dict) else None


def _repath_context(
    self: VariablesAnalyzer,
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

    self.append_issue(
        VariableIssue(
            kind=IssueKind.RECORD_COMPONENT_ORDER_DEPENDENCE,
            module_path=path.copy(),
            variable=variable,
            role=role,
            site=self._site_str() or None,
            field_path=field_path or None,
        )
    )


def _handle_function_call(
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


def _scan_for_varrefs(
    self: VariablesAnalyzer,
    obj: Any,
    context: ScopeContext,
    path: list[str],
    *,
    is_ui_read: bool = False,
) -> None:
    if obj is None:
        return
    if isinstance(obj, list):
        for item in cast(list[Any], obj):
            self._scan_for_varrefs(item, context, path, is_ui_read=is_ui_read)
        return
    if isinstance(obj, dict):
        mapping = cast(dict[str, Any], obj)
        if const.TREE_TAG_ENABLE in mapping and const.KEY_TAIL in mapping:
            self._walk_tail(mapping[const.KEY_TAIL], context, path, is_ui_read=is_ui_read)
        if const.KEY_TAIL in mapping and mapping[const.KEY_TAIL] is not None:
            self._walk_tail(mapping[const.KEY_TAIL], context, path, is_ui_read=is_ui_read)
        if const.KEY_ASSIGN in mapping:
            tail_owner = _mapping_of(mapping.get(const.KEY_ASSIGN))
            tail = tail_owner.get(const.KEY_TAIL) if tail_owner is not None else None
            if tail is not None:
                self._walk_tail(tail, context, path, is_ui_read=is_ui_read)
        for value in mapping.values():
            self._scan_for_varrefs(value, context, path, is_ui_read=is_ui_read)
        return
    if hasattr(obj, "data"):
        if obj.data in {
            const.KEY_TAIL,
            const.KEY_ENABLE_EXPRESSION,
            const.GRAMMAR_VALUE_INVAR_PREFIX,
            "plain_value",
            "value_or_invar",
        }:
            self._walk_tail(obj, context, path, is_ui_read=is_ui_read)
            return
        for child in _children_of(obj) or []:
            self._scan_for_varrefs(child, context, path, is_ui_read=is_ui_read)


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

    if isinstance(tail, IntLiteral | FloatLiteral | int | float | bool):
        return

    if isinstance(tail, tuple):
        self._walk_stmt_or_expr(tail, context, path, is_ui_read=is_ui_read)
        return

    if isinstance(tail, str):
        base_name = tail.split(".", 1)[0]
        self._mark_var_by_basename(base_name, context.env, path, is_ui_read=is_ui_read)
        return

    mapped_ref = _var_name_of(tail)
    if mapped_ref is not None:
        self._mark_ref_access(
            mapped_ref,
            context,
            path,
            AccessKind.READ,
            is_ui_read=is_ui_read,
        )
        return

    if _children_of(tail) is not None:
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
    self: VariablesAnalyzer,
    node: Any,
    allow_single_ident: bool = False,
) -> set[str]:
    names: set[str] = set()

    def visit(value: Any) -> None:
        if value is None:
            return
        full = _var_name_of(value)
        if full is not None:
            names.add(full.split(".", 1)[0])
            return
        if isinstance(value, str):
            stripped = value.strip()
            if stripped and allow_single_ident and all(char.isalnum() or char == "_" for char in stripped):
                names.add(stripped)
            return
        if isinstance(value, list):
            for item in cast(list[Any], value):
                visit(item)
            return
        children = _children_of(value)
        if children is not None:
            for child in children:
                visit(child)

    visit(node)
    return names


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
        log.debug(
            "Variable not found in scope: %s (env size=%d, path=%s)",
            base_name,
            len(env),
            " -> ".join(path),
        )


__all__ = [
    "_IGNORED_GRAPHICS_TAIL_BASENAMES",
    "_AssignTuple",
    "_BinaryOpTuple",
    "_CompareTuple",
    "_FunctionCallTuple",
    "_IfTuple",
    "_LogicalTuple",
    "_TernaryTuple",
    "_UnaryTuple",
    "_children_of",
    "_extract_var_basenames_from_tree",
    "_handle_function_call",
    "_mapping_of",
    "_mark_var_by_basename",
    "_repath_context",
    "_scan_for_varrefs",
    "_var_name_of",
    "_walk_graph_object",
    "_walk_header_enable",
    "_walk_header_groupconn",
    "_walk_header_invoke_tails",
    "_walk_interact_object",
    "_walk_moduledef",
    "_walk_tail",
    "_walk_typedef_groupconn",
]
