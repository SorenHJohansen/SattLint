"""Access, effect-flow, and datatype helpers for variable analysis."""

from __future__ import annotations

import difflib
from typing import TYPE_CHECKING, Any

from sattline_parser.models.ast_model import ParameterMapping, Simple_DataType, Variable

from ..casefolding import is_anytype_name
from ..grammar import constants as const
from ..resolution import AccessKind, CanonicalPath
from ..resolution.scope import ScopeContext
from .variable_utils import matches_root_origin

if TYPE_CHECKING:
    from .variables import VariablesAnalyzer


def _canonical_path(
    self: VariablesAnalyzer,
    module_path: list[str],
    variable: Variable,
    field_path: str | None,
) -> CanonicalPath:
    segments = [*list(module_path), variable.name]
    if field_path:
        segments.extend([part for part in field_path.split(".") if part])
    return CanonicalPath(tuple(segments))


def _record_access(
    self: VariablesAnalyzer,
    kind: AccessKind,
    canonical_path: CanonicalPath,
    context: ScopeContext,
    syntactic_ref: str,
) -> None:
    self.usage_tracker.record_access(
        kind=kind,
        canonical_path=canonical_path,
        context=context,
        syntactic_ref=syntactic_ref,
    )


def _mark_ref_access(
    self: VariablesAnalyzer,
    full_ref: str,
    context: ScopeContext,
    path: list[str],
    kind: AccessKind,
    *,
    is_ui_read: bool = False,
) -> None:
    base = full_ref.split(".", 1)[0].lower()
    local_field_path = full_ref.split(".", 1)[1] if "." in full_ref else ""
    local_var = context.env.get(base)
    if local_var is not None and base in context.param_mappings:
        self.usage_tracker.mark_ref_access(
            variable=local_var,
            field_path=local_field_path,
            decl_module_path=context.module_path,
            context=context,
            path=path,
            kind=kind,
            syntactic_ref=full_ref,
            ui_read=is_ui_read,
        )

    variable, field_path, decl_module_path, _decl_display = context.resolve_variable(full_ref)
    if variable is None:
        return

    self.usage_tracker.mark_ref_access(
        variable=variable,
        field_path=field_path,
        decl_module_path=decl_module_path,
        context=context,
        path=path,
        kind=kind,
        syntactic_ref=full_ref,
        ui_read=is_ui_read,
    )


def _effect_key_for_variable(
    self: VariablesAnalyzer,
    variable: Variable,
    decl_module_path: list[str],
) -> tuple[str, ...]:
    return self.effect_flow_tracker.effect_key_for_variable(variable, decl_module_path)


def _resolve_effect_key(
    self: VariablesAnalyzer,
    full_ref: str,
    context: ScopeContext,
) -> tuple[str, ...] | None:
    return self.effect_flow_tracker.resolve_effect_key(full_ref, context)


def _mapping_source_effect_key(
    self: VariablesAnalyzer,
    pm: ParameterMapping,
    *,
    parent_env: dict[str, Variable],
    parent_context: ScopeContext | None,
) -> tuple[str, ...] | None:
    return self.effect_flow_tracker.mapping_source_effect_key(
        pm,
        parent_env=parent_env,
        parent_context=parent_context,
    )


def _resolve_local_effect_key(
    self: VariablesAnalyzer,
    full_ref: str,
    context: ScopeContext,
) -> tuple[str, ...] | None:
    return self.effect_flow_tracker.resolve_local_effect_key(full_ref, context)


def _resolve_mapped_effect_source_key(
    self: VariablesAnalyzer,
    full_ref: str,
    context: ScopeContext,
) -> tuple[str, ...] | None:
    return self.effect_flow_tracker.resolve_mapped_effect_source_key(full_ref, context)


def _record_effect_flow(
    self: VariablesAnalyzer,
    source_key: tuple[str, ...] | None,
    target_key: tuple[str, ...] | None,
) -> None:
    self.effect_flow_tracker.record_effect_flow(source_key, target_key)


def _collect_function_input_effect_keys(
    self: VariablesAnalyzer,
    fn_name: str | None,
    args: list[Any],
    context: ScopeContext,
) -> set[tuple[str, ...]]:
    return self.effect_flow_tracker.collect_function_input_effect_keys(fn_name, args, context)


def _collect_expression_effect_sources(
    self: VariablesAnalyzer,
    obj: Any,
    context: ScopeContext,
) -> set[tuple[str, ...]]:
    return self.effect_flow_tracker.collect_expression_effect_sources(obj, context)


def _record_assignment_effect_flow(
    self: VariablesAnalyzer,
    target_ref: str,
    expr: Any,
    context: ScopeContext,
) -> None:
    self.effect_flow_tracker.record_assignment_effect_flow(target_ref, expr, context)


def _record_function_call_effect_flow(
    self: VariablesAnalyzer,
    fn_name: str | None,
    args: list[Any],
    context: ScopeContext,
) -> None:
    self.effect_flow_tracker.record_function_call_effect_flow(fn_name, args, context)


def _collect_effect_sink_keys(self: VariablesAnalyzer) -> set[tuple[str, ...]]:
    return self.effect_flow_tracker.collect_effect_sink_keys(
        self.bp,
        self.analyzed_target_is_library,
        self.is_from_root_origin,
    )


def _compute_effective_output_keys(self: VariablesAnalyzer) -> set[tuple[str, ...]]:
    sink_keys = _collect_effect_sink_keys(self)
    return self.effect_flow_tracker.compute_effective_output_keys(sink_keys)


def _has_output_effect(self: VariablesAnalyzer, variable: Variable, decl_path: list[str]) -> bool:
    return self.effect_flow_tracker.effect_key_for_variable(variable, decl_path) in self.effective_output_keys


def _site_str(self: VariablesAnalyzer) -> str:
    if not self.site_stack:
        return ""
    return " > ".join(self.site_stack)


def _push_site(self: VariablesAnalyzer, label: str) -> None:
    if label:
        self.site_stack.append(label)


def _pop_site(self: VariablesAnalyzer) -> None:
    if self.site_stack:
        self.site_stack.pop()


def _strict_datatype_at_field_prefix(
    self: VariablesAnalyzer,
    root_type: Simple_DataType | str,
    field_prefix: str,
    *,
    fn_name: str,
    syntactic_ref: str,
    resolved_var_name: str,
    use_path: list[str],
) -> Simple_DataType | str:
    segments = [segment for segment in (field_prefix or "").split(".") if segment]
    current: Simple_DataType | str = root_type

    for segment in segments:
        if isinstance(current, Simple_DataType):
            site = _site_str(self)
            if self.fail_loudly:
                raise ValueError(
                    f"{fn_name}: at {' -> '.join(use_path)}"
                    f"{(' [' + site + ']') if site else ''}: reference {syntactic_ref!r} resolves to {resolved_var_name!r} and "
                    f"cannot access field {segment!r} on scalar datatype {current.value!r}."
                )
            self.warn(
                f"{fn_name}: at {' -> '.join(use_path)}"
                f"{(' [' + site + ']') if site else ''}: reference {syntactic_ref!r} resolves to {resolved_var_name!r} and "
                f"cannot access field {segment!r} on scalar datatype {current.value!r}. Treating as leaf."
            )
            return current

        if current.casefold() in self.opaque_builtin_types:
            return current

        record_type = self.type_graph.record(str(current))
        if record_type is None:
            site = _site_str(self)
            if self.unavailable_libraries or not self.fail_loudly:
                self.warn(
                    f"{fn_name}: at {' -> '.join(use_path)}"
                    f"{(' [' + site + ']') if site else ''}: reference {syntactic_ref!r} resolves to {resolved_var_name!r} and "
                    f"uses unknown record datatype {str(current)!r}. Treating as leaf."
                )
                return current
            raise ValueError(
                f"{fn_name}: at {' -> '.join(use_path)}"
                f"{(' [' + site + ']') if site else ''}: reference {syntactic_ref!r} resolves to {resolved_var_name!r} and "
                f"uses unknown record datatype {str(current)!r}."
            )

        field_def = record_type.fields_by_key.get(segment.casefold())
        if field_def is None:
            available = sorted({field.name for field in record_type.fields_by_key.values()})
            close = difflib.get_close_matches(segment, available, n=5, cutoff=0.6)
            site = _site_str(self)
            if self.unavailable_libraries or not self.fail_loudly:
                self.warn(
                    f"{fn_name}: at {' -> '.join(use_path)}"
                    f"{(' [' + site + ']') if site else ''}: reference {syntactic_ref!r} resolves to {resolved_var_name!r} and "
                    f"uses unknown field {segment!r} in record datatype {record_type.name!r}. "
                    f"Available fields: {available[:50]}"
                    + (f". Close matches: {close}" if close else "")
                    + " Treating as leaf."
                )
                return str(current)
            raise ValueError(
                f"{fn_name}: at {' -> '.join(use_path)}"
                f"{(' [' + site + ']') if site else ''}: reference {syntactic_ref!r} resolves to {resolved_var_name!r} and "
                f"uses unknown field {segment!r} in record datatype {record_type.name!r}. "
                f"Available fields: {available[:50]}" + (f". Close matches: {close}" if close else "")
            )

        current = field_def.datatype

    return current


def _iter_leaf_field_paths_strict(
    self: VariablesAnalyzer,
    root_type: Simple_DataType | str,
    *,
    fn_name: str,
    syntactic_ref: str,
    resolved_var_name: str,
) -> list[tuple[str, ...]]:
    if isinstance(root_type, Simple_DataType):
        return [()]
    if is_anytype_name(root_type):
        return [()]

    start = str(root_type)
    results: list[tuple[str, ...]] = []
    stack: list[tuple[str, tuple[str, ...], tuple[str, ...]]] = [(start, (), ())]

    while stack:
        type_name, prefix, chain = stack.pop()
        key = type_name.casefold()

        if key in {entry.casefold() for entry in chain}:
            raise ValueError(
                f"{fn_name}: datatype cycle detected while expanding {resolved_var_name!r} "
                f"(ref {syntactic_ref!r}) at record datatype {type_name!r}."
            )

        record_type = self.type_graph.record(type_name)
        if record_type is None:
            if key in self.opaque_builtin_types:
                results.append(prefix)
                continue
            if self.unavailable_libraries:
                self.warn(
                    f"{fn_name}: reference {syntactic_ref!r} resolves to {resolved_var_name!r} and "
                    f"uses unknown record datatype {type_name!r}. Treating as leaf due to unavailable libraries."
                )
                results.append(prefix)
                continue
            if is_anytype_name(type_name):
                results.append(prefix)
                continue
            if self.fail_loudly:
                raise ValueError(
                    f"{fn_name}: reference {syntactic_ref!r} resolves to {resolved_var_name!r} and "
                    f"uses unknown record datatype {type_name!r}."
                )
            self.warn(
                f"{fn_name}: reference {syntactic_ref!r} resolves to {resolved_var_name!r} and "
                f"uses unknown record datatype {type_name!r}. Treating as leaf."
            )
            results.append(prefix)
            continue

        if not record_type.fields_by_key:
            results.append(prefix)
            continue

        next_chain = (*chain, type_name)
        for field in record_type.fields_by_key.values():
            new_prefix = (*prefix, field.name)
            if isinstance(field.datatype, Simple_DataType):
                results.append(new_prefix)
            else:
                stack.append((str(field.datatype), new_prefix, next_chain))

    return results


def _mark_record_wide_builtin_access(
    self: VariablesAnalyzer,
    syntactic_ref: str,
    *,
    kind: AccessKind,
    fn_name: str,
    context: ScopeContext,
    path: list[str],
    is_ui_read: bool = False,
) -> None:
    resolved_var, resolved_field_prefix, _decl_path, _decl_display = context.resolve_variable(syntactic_ref)
    if resolved_var is None:
        site = _site_str(self)
        raise ValueError(
            f"{fn_name}: at {' -> '.join(path)}"
            f"{(' [' + site + ']') if site else ''}: cannot resolve variable reference {syntactic_ref!r} for record-wide access."
        )

    dtype_at_prefix = _strict_datatype_at_field_prefix(
        self,
        resolved_var.datatype,
        resolved_field_prefix,
        fn_name=fn_name,
        syntactic_ref=syntactic_ref,
        resolved_var_name=resolved_var.name,
        use_path=path,
    )

    leaf_paths = _iter_leaf_field_paths_strict(
        self,
        dtype_at_prefix,
        fn_name=fn_name,
        syntactic_ref=syntactic_ref,
        resolved_var_name=resolved_var.name,
    )

    for leaf in leaf_paths:
        if not leaf:
            _mark_ref_access(
                self,
                syntactic_ref,
                context,
                path,
                kind,
                is_ui_read=is_ui_read,
            )
            continue
        _mark_ref_access(
            self,
            f"{syntactic_ref}.{'.'.join(leaf)}",
            context,
            path,
            kind,
            is_ui_read=is_ui_read,
        )


def _lookup_global_variable(self: VariablesAnalyzer, base_name: str | None) -> Variable | None:
    if not base_name:
        return None
    normalized = base_name.lower()
    variable = self.root_env.get(normalized)
    if variable:
        return variable
    variables = self.any_var_index.get(normalized)
    return variables[0] if variables else None


def is_from_root_origin(
    self: VariablesAnalyzer,
    origin_file: str | None,
    origin_lib: str | None = None,
) -> bool:
    return matches_root_origin(
        origin_file,
        getattr(self.bp, "origin_file", None),
        analyzed_target_is_library=self.analyzed_target_is_library,
        origin_lib=origin_lib,
        root_origin_lib=getattr(self.bp, "origin_lib", None),
    )


def _extract_field_path(self: VariablesAnalyzer, var_dict: dict[str, Any]) -> tuple[str | None, str | None]:
    if const.KEY_VAR_NAME not in var_dict:
        return None, None

    full_name = var_dict[const.KEY_VAR_NAME]
    if not isinstance(full_name, str) or not full_name:
        return None, None
    if "." not in full_name:
        return full_name.lower(), None

    parts = full_name.split(".", 1)
    base = parts[0].lower()
    field_path = parts[1] if len(parts) > 1 else None
    return base, field_path


canonical_path = _canonical_path
collect_effect_sink_keys = _collect_effect_sink_keys
collect_expression_effect_sources = _collect_expression_effect_sources
collect_function_input_effect_keys = _collect_function_input_effect_keys
compute_effective_output_keys = _compute_effective_output_keys
effect_key_for_variable = _effect_key_for_variable
extract_field_path = _extract_field_path
has_output_effect = _has_output_effect
iter_leaf_field_paths_strict = _iter_leaf_field_paths_strict
lookup_global_variable = _lookup_global_variable
mapping_source_effect_key = _mapping_source_effect_key
mark_record_wide_builtin_access = _mark_record_wide_builtin_access
mark_ref_access = _mark_ref_access
pop_site = _pop_site
push_site = _push_site
record_access = _record_access
record_assignment_effect_flow = _record_assignment_effect_flow
record_effect_flow = _record_effect_flow
record_function_call_effect_flow = _record_function_call_effect_flow
resolve_effect_key = _resolve_effect_key
resolve_local_effect_key = _resolve_local_effect_key
resolve_mapped_effect_source_key = _resolve_mapped_effect_source_key
site_str = _site_str
strict_datatype_at_field_prefix = _strict_datatype_at_field_prefix

__all__ = [
    "canonical_path",
    "collect_effect_sink_keys",
    "collect_expression_effect_sources",
    "collect_function_input_effect_keys",
    "compute_effective_output_keys",
    "effect_key_for_variable",
    "extract_field_path",
    "has_output_effect",
    "is_from_root_origin",
    "iter_leaf_field_paths_strict",
    "lookup_global_variable",
    "mapping_source_effect_key",
    "mark_record_wide_builtin_access",
    "mark_ref_access",
    "pop_site",
    "push_site",
    "record_access",
    "record_assignment_effect_flow",
    "record_effect_flow",
    "record_function_call_effect_flow",
    "resolve_effect_key",
    "resolve_local_effect_key",
    "resolve_mapped_effect_source_key",
    "site_str",
    "strict_datatype_at_field_prefix",
]
