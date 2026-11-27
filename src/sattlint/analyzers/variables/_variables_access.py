"""Access, effect-flow, and datatype helpers for variable analysis."""

# pyright: reportPrivateUsage=false

from __future__ import annotations

import difflib
from typing import TYPE_CHECKING, Any

from sattlint.parser_api import ParameterMapping, ScalarDatatype, Variable

from ...resolution import AccessKind, AmbiguousRecordError, CanonicalPath, resolve_record
from ...resolution.common import varname_full
from ...resolution.scope import ScopeContext, find_nearest_declaration
from ...resolution.type_graph import LeafExpansionIssue, LeafExpansionPolicy
from ...utils.casefolding import is_anytype_name
from ..shared.variable_utils import matches_root_origin

if TYPE_CHECKING:
    from . import VariablesAnalyzer


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


def _record_secure_candidate_access(
    self: VariablesAnalyzer,
    variable: Variable,
    field_path: str,
    decl_module_path: list[str],
    decl_display: list[str],
    kind: AccessKind,
) -> None:
    """Record the step writes and transition reads the Secure heuristic uses."""
    facts = getattr(self, "_secure_candidate_facts", None)
    if facts is None or field_path:
        return
    site = _site_str(self)
    if kind is AccessKind.WRITE and getattr(self, "_secure_in_step", False):
        step_name = getattr(self, "_secure_step_name", None)
        if step_name:
            site = f"{site} > STEP:{step_name}"
        facts.record_write(variable, decl_module_path, decl_display, site)
        return
    if kind is AccessKind.READ and getattr(self, "_secure_in_transition", False):
        transition_name = getattr(self, "_secure_transition_name", None)
        if transition_name:
            site = f"{site} > TRANSITION:{transition_name}"
        facts.record_transition_read(variable, decl_module_path, decl_display, site)


def _mark_ref_access(
    self: VariablesAnalyzer,
    full_ref: str,
    context: ScopeContext,
    path: list[str],
    kind: AccessKind,
    *,
    is_ui_read: bool = False,
) -> None:
    base = full_ref.split(".", 1)[0].casefold()
    local_field_path = full_ref.split(".", 1)[1] if "." in full_ref else ""
    declaration = find_nearest_declaration(context, base)
    variable, field_path, decl_module_path, decl_display = context.resolve_variable(full_ref)

    # A reference names the declaration nearest to it even when a parameter
    # mapping forwards the value to an outer variable. Resolving through the
    # mapping would skip that declaration, so credit it explicitly; alias
    # propagation then carries the usage on to the mapped source.
    if declaration is not None:
        declared_var, declared_path, _declared_display = declaration
        if declared_var is not variable:
            self.usage_tracker.mark_ref_access(
                variable=declared_var,
                field_path=local_field_path,
                decl_module_path=declared_path,
                context=context,
                path=path,
                kind=kind,
                syntactic_ref=full_ref,
                ui_read=is_ui_read,
            )

    if variable is None:
        return

    _record_secure_candidate_access(self, variable, field_path, decl_module_path, decl_display, kind)

    if kind is AccessKind.WRITE:
        self.effect_flow_tracker.record_controlled_write(full_ref, context)
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
    for context in self.contexts_by_module_path.values():
        for variable in context.env.values():
            if self.get_usage(variable).ui_read:
                key = self.effect_flow_tracker.resolve_local_effect_key(variable.name, context)
                if key is not None:
                    sink_keys.add(key)
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


def _reference_library(context: ScopeContext) -> str | None:
    """Library whose code references a variable, or ``None`` when unknown.

    A parser ``Variable`` carries no declaration library, so the referencing
    scope is the only evidence available. A record name shared by several
    libraries therefore resolves only when it is unique, the graph's root
    library declares it, or the scope's library declares it.
    """
    return getattr(context, "current_library", None)


def _strict_datatype_at_field_prefix(
    self: VariablesAnalyzer,
    root_type: ScalarDatatype | str,
    field_prefix: str,
    *,
    fn_name: str,
    syntactic_ref: str,
    resolved_var_name: str,
    use_path: list[str],
    library: str | None = None,
) -> ScalarDatatype | str:
    segments = [segment for segment in (field_prefix or "").split(".") if segment]
    current: ScalarDatatype | str = root_type
    # A field's type belongs to the library that declares the record holding it,
    # so each resolved record supplies the library for the next segment.
    field_library = library

    for segment in segments:
        if isinstance(current, ScalarDatatype):
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

        ambiguity: list[AmbiguousRecordError] = []
        record_type = resolve_record(
            self.type_graph,
            str(current),
            library=field_library,
            on_ambiguity=ambiguity.append,
        )
        if ambiguity:
            exc = ambiguity[0]
            site = _site_str(self)
            detail = (
                f"{fn_name}: at {' -> '.join(use_path)}"
                f"{(' [' + site + ']') if site else ''}: reference {syntactic_ref!r} resolves to {resolved_var_name!r} and "
                f"uses an ambiguous record datatype {str(current)!r}. {exc}"
            )
            if self.fail_loudly:
                raise ValueError(detail) from exc
            self._warn_ambiguous_record(exc)
            return current

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
        field_library = record_type.library

    return current


def _iter_leaf_field_paths_strict(
    self: VariablesAnalyzer,
    root_type: ScalarDatatype | str,
    *,
    fn_name: str,
    syntactic_ref: str,
    resolved_var_name: str,
    library: str | None = None,
) -> list[tuple[str, ...]]:
    def _on_issue(issue: LeafExpansionIssue) -> None:
        if issue.kind == "cycle":
            raise ValueError(
                f"{fn_name}: datatype cycle detected while expanding {resolved_var_name!r} "
                f"(ref {syntactic_ref!r}) at record datatype {issue.type_name!r}."
            )
        if issue.kind == "ambiguous_record":
            if library is None:
                decision = "no library is available to decide it."
            else:
                decision = f"library {library!r} does not decide it."
            detail = (
                f"{fn_name}: reference {syntactic_ref!r} resolves to {resolved_var_name!r} and "
                f"uses record datatype {issue.type_name!r}, which several libraries declare; {decision}"
            )
            if self.fail_loudly:
                raise ValueError(detail)
            self._warn_ambiguous_record(AmbiguousRecordError(issue.type_name, issue.libraries))
            return
        if self.unavailable_libraries:
            self.warn(
                f"{fn_name}: reference {syntactic_ref!r} resolves to {resolved_var_name!r} and "
                f"uses unknown record datatype {issue.type_name!r}. Treating as leaf due to unavailable libraries."
            )
            return
        if self.fail_loudly:
            raise ValueError(
                f"{fn_name}: reference {syntactic_ref!r} resolves to {resolved_var_name!r} and "
                f"uses unknown record datatype {issue.type_name!r}."
            )
        self.warn(
            f"{fn_name}: reference {syntactic_ref!r} resolves to {resolved_var_name!r} and "
            f"uses unknown record datatype {issue.type_name!r}. Treating as leaf."
        )

    def _is_opaque(type_name: str) -> bool:
        return type_name.casefold() in self.opaque_builtin_types or is_anytype_name(type_name)

    return list(
        self.type_graph.expand_leaf_paths(
            root_type,
            library=library,
            policy=LeafExpansionPolicy(is_opaque=_is_opaque, on_issue=_on_issue),
        )
    )


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
        library=_reference_library(context),
    )

    leaf_paths = _iter_leaf_field_paths_strict(
        self,
        dtype_at_prefix,
        fn_name=fn_name,
        syntactic_ref=syntactic_ref,
        resolved_var_name=resolved_var.name,
        library=_reference_library(context),
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
    normalized = base_name.casefold()
    variable = self.root_env.get(normalized)
    if variable:
        return variable
    candidates = {id(candidate): candidate for candidate in self.any_var_index.get(normalized, ())}
    if len(candidates) == 1:
        return next(iter(candidates.values()))
    # Several declarations share the name and none of them is the root
    # variable, so any pick would attribute usage to the wrong declaration.
    return None


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


def _extract_field_path(self: VariablesAnalyzer, var_ref: object) -> tuple[str | None, str | None]:
    full_name = varname_full(var_ref)
    if not full_name:
        return None, None
    if "." not in full_name:
        return full_name.casefold(), None

    base, field_path = full_name.split(".", 1)
    return base.casefold(), field_path


class VariablesAccessMixin:
    def _canonical_path(
        self: Any,
        module_path: list[str],
        variable: Variable,
        field_path: str | None,
    ) -> CanonicalPath:
        return _canonical_path(self, module_path, variable, field_path)

    def _record_access(
        self: Any,
        kind: AccessKind,
        canonical_path: CanonicalPath,
        context: ScopeContext,
        syntactic_ref: str,
    ) -> None:
        _record_access(self, kind, canonical_path, context, syntactic_ref)

    def _mark_ref_access(
        self: Any,
        full_ref: str,
        context: ScopeContext,
        path: list[str],
        kind: AccessKind,
        *,
        is_ui_read: bool = False,
    ) -> None:
        _mark_ref_access(self, full_ref, context, path, kind, is_ui_read=is_ui_read)

    def _effect_key_for_variable(
        self: Any,
        variable: Variable,
        decl_module_path: list[str],
    ) -> tuple[str, ...]:
        return _effect_key_for_variable(self, variable, decl_module_path)

    def _resolve_effect_key(
        self: Any,
        full_ref: str,
        context: ScopeContext,
    ) -> tuple[str, ...] | None:
        return _resolve_effect_key(self, full_ref, context)

    def _mapping_source_effect_key(
        self: Any,
        pm: ParameterMapping,
        *,
        parent_env: dict[str, Variable],
        parent_context: ScopeContext | None,
    ) -> tuple[str, ...] | None:
        return _mapping_source_effect_key(
            self,
            pm,
            parent_env=parent_env,
            parent_context=parent_context,
        )

    def _resolve_local_effect_key(
        self: Any,
        full_ref: str,
        context: ScopeContext,
    ) -> tuple[str, ...] | None:
        return _resolve_local_effect_key(self, full_ref, context)

    def _resolve_mapped_effect_source_key(
        self: Any,
        full_ref: str,
        context: ScopeContext,
    ) -> tuple[str, ...] | None:
        return _resolve_mapped_effect_source_key(self, full_ref, context)

    def _record_effect_flow(
        self: Any,
        source_key: tuple[str, ...] | None,
        target_key: tuple[str, ...] | None,
    ) -> None:
        _record_effect_flow(self, source_key, target_key)

    def _collect_function_input_effect_keys(
        self: Any,
        fn_name: str | None,
        args: list[Any],
        context: ScopeContext,
    ) -> set[tuple[str, ...]]:
        return _collect_function_input_effect_keys(self, fn_name, args, context)

    def _collect_expression_effect_sources(
        self: Any,
        obj: Any,
        context: ScopeContext,
    ) -> set[tuple[str, ...]]:
        return _collect_expression_effect_sources(self, obj, context)

    def _record_assignment_effect_flow(
        self: Any,
        target_ref: str,
        expr: Any,
        context: ScopeContext,
    ) -> None:
        _record_assignment_effect_flow(self, target_ref, expr, context)

    def _record_function_call_effect_flow(
        self: Any,
        fn_name: str | None,
        args: list[Any],
        context: ScopeContext,
    ) -> None:
        _record_function_call_effect_flow(self, fn_name, args, context)

    def _collect_effect_sink_keys(self: Any) -> set[tuple[str, ...]]:
        return _collect_effect_sink_keys(self)

    def _compute_effective_output_keys(self: Any) -> set[tuple[str, ...]]:
        return _compute_effective_output_keys(self)

    def _has_output_effect(self: Any, variable: Variable, decl_path: list[str]) -> bool:
        return _has_output_effect(self, variable, decl_path)

    def _site_str(self: Any) -> str:
        return _site_str(self)

    def _push_site(self: Any, label: str) -> None:
        _push_site(self, label)

    def _pop_site(self: Any) -> None:
        _pop_site(self)

    def _strict_datatype_at_field_prefix(
        self: Any,
        root_type: ScalarDatatype | str,
        field_prefix: str,
        *,
        fn_name: str,
        syntactic_ref: str,
        resolved_var_name: str,
        use_path: list[str],
        library: str | None = None,
    ) -> ScalarDatatype | str:
        return _strict_datatype_at_field_prefix(
            self,
            root_type,
            field_prefix,
            fn_name=fn_name,
            syntactic_ref=syntactic_ref,
            resolved_var_name=resolved_var_name,
            use_path=use_path,
            library=library,
        )

    def _iter_leaf_field_paths_strict(
        self: Any,
        root_type: ScalarDatatype | str,
        *,
        fn_name: str,
        syntactic_ref: str,
        resolved_var_name: str,
        library: str | None = None,
    ) -> list[tuple[str, ...]]:
        return _iter_leaf_field_paths_strict(
            self,
            root_type,
            fn_name=fn_name,
            syntactic_ref=syntactic_ref,
            resolved_var_name=resolved_var_name,
            library=library,
        )

    def _mark_record_wide_builtin_access(
        self: Any,
        syntactic_ref: str,
        *,
        kind: AccessKind,
        fn_name: str,
        context: ScopeContext,
        path: list[str],
        is_ui_read: bool = False,
    ) -> None:
        _mark_record_wide_builtin_access(
            self,
            syntactic_ref,
            kind=kind,
            fn_name=fn_name,
            context=context,
            path=path,
            is_ui_read=is_ui_read,
        )

    def _lookup_global_variable(self: Any, base_name: str | None) -> Variable | None:
        return _lookup_global_variable(self, base_name)

    def _is_from_root_origin(
        self: Any,
        origin_file: str | None,
        origin_lib: str | None = None,
    ) -> bool:
        return is_from_root_origin(self, origin_file, origin_lib)

    def _extract_field_path(
        self: Any,
        var_ref: object,
    ) -> tuple[str | None, str | None]:
        return _extract_field_path(self, var_ref)


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
    "VariablesAccessMixin",
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
