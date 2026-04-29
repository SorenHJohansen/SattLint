"""Effect flow tracking and mapping resolution for variable usage analysis."""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, Any

from sattline_parser.models.ast_model import ParameterMapping, Variable
from sattlint.resolution import AccessKind, decorate_segment
from sattlint.resolution.common import varname_base
from sattlint.resolution.scope import ScopeContext

from ..grammar import constants as const
from .sattline_builtins import get_function_signature

if TYPE_CHECKING:
    pass


class EffectFlowTracker:
    """Helper for tracking variable effect flows and mapping propagation."""

    def __init__(
        self,
        effect_flow_edges: dict[tuple[str, ...], set[tuple[str, ...]]],
        effect_flow_display_names: dict[tuple[str, ...], str],
        external_effect_sinks: set[tuple[str, ...]],
        effective_output_keys: set[tuple[str, ...]],
        lookup_global_variable_fn,
        get_usage_fn,
        canonical_path_fn,
        record_access_fn,
    ):
        """Initialize with references to analyzer's data structures and methods."""
        self._effect_flow_edges = effect_flow_edges
        self._effect_flow_display_names = effect_flow_display_names
        self._external_effect_sinks = external_effect_sinks
        self._effective_output_keys = effective_output_keys
        self._lookup_global_variable = lookup_global_variable_fn
        self._get_usage = get_usage_fn
        self._canonical_path = canonical_path_fn
        self._record_access = record_access_fn

    def effect_key_for_variable(
        self,
        variable: Variable,
        decl_module_path: list[str],
    ) -> tuple[str, ...]:
        """Get the canonical effect key for a variable declaration."""
        display_segments = (*decl_module_path, variable.name)
        key = tuple(segment.casefold() for segment in display_segments)
        self._effect_flow_display_names.setdefault(key, ".".join(display_segments))
        return key

    def resolve_effect_key(
        self,
        full_ref: str,
        context: ScopeContext,
    ) -> tuple[str, ...] | None:
        """Resolve an effect key from a variable reference and context."""
        base_name = varname_base(full_ref)
        if base_name:
            local_var = context.env.get(base_name.casefold())
            if local_var is not None:
                return self.effect_key_for_variable(local_var, context.module_path)
        variable, _field_path, decl_module_path, _decl_display = context.resolve_variable(full_ref)
        if variable is None:
            return None
        return self.effect_key_for_variable(variable, decl_module_path)

    def mapping_source_effect_key(
        self,
        pm: ParameterMapping,
        *,
        parent_env: dict[str, Variable],
        parent_context: ScopeContext | None,
    ) -> tuple[str, ...] | None:
        """Get the effect key for a parameter mapping's source."""
        if pm.is_source_global:
            full_source = None
            if isinstance(pm.source, dict) and const.KEY_VAR_NAME in pm.source:
                full_source = pm.source[const.KEY_VAR_NAME]
            elif isinstance(pm.source, str):
                full_source = pm.source
            if not full_source:
                return None
            source_base = full_source.split(".", 1)[0]
            if parent_context is not None:
                source_var, decl_path, _decl_display = parent_context.resolve_global_name(source_base)
            else:
                source_var = parent_env.get(source_base.casefold())
                decl_path = []
                if source_var is None:
                    source_var = self._lookup_global_variable(source_base)
                    decl_path = [source_base] if source_var is not None else []
            if source_var is None:
                return None
            return self.effect_key_for_variable(source_var, decl_path)

        if isinstance(pm.source, dict) and const.KEY_VAR_NAME in pm.source:
            full_source = pm.source[const.KEY_VAR_NAME]
        elif isinstance(pm.source, str):
            full_source = pm.source
        else:
            return None

        if parent_context is not None:
            return self.resolve_effect_key(full_source, parent_context)

        source_base = varname_base(full_source)
        if not source_base:
            return None
        source_var = parent_env.get(source_base.casefold()) or self._lookup_global_variable(source_base)
        if source_var is None:
            return None
        return self.effect_key_for_variable(source_var, [source_base])

    def resolve_local_effect_key(
        self,
        full_ref: str,
        context: ScopeContext,
    ) -> tuple[str, ...] | None:
        """Resolve an effect key for a local variable reference."""
        base = full_ref.split(".", 1)[0].lower()
        variable = context.env.get(base)
        if variable is None:
            return None
        return self.effect_key_for_variable(variable, context.module_path)

    def resolve_mapped_effect_source_key(
        self,
        full_ref: str,
        context: ScopeContext,
    ) -> tuple[str, ...] | None:
        """Resolve effect key for a mapped parameter's source."""
        base = full_ref.split(".", 1)[0].lower()
        mapping = context.param_mappings.get(base)
        if mapping is None:
            return None
        source_var, _field_prefix, source_decl_path, _source_decl_display_path = mapping
        return self.effect_key_for_variable(source_var, source_decl_path)

    def record_effect_flow(
        self,
        source_key: tuple[str, ...] | None,
        target_key: tuple[str, ...] | None,
    ) -> None:
        """Record a flow edge from source to target key."""
        if source_key is None or target_key is None:
            return
        self._effect_flow_edges[source_key].add(target_key)

    def collect_function_input_effect_keys(
        self,
        fn_name: str | None,
        args: list[Any],
        context: ScopeContext,
    ) -> set[tuple[str, ...]]:
        """Collect effect keys for function inputs based on signature."""
        if not fn_name:
            input_sources: set[tuple[str, ...]] = set()
            for arg in args:
                input_sources.update(self.collect_expression_effect_sources(arg, context))
            return input_sources

        fn_key = fn_name.casefold()
        if fn_key in {"copyvariable", "copyvarnosort"}:
            if args and isinstance(args[0], dict) and const.KEY_VAR_NAME in args[0]:
                key = self.resolve_effect_key(args[0][const.KEY_VAR_NAME], context)
                return {key} if key is not None else set()
            return set()

        if fn_key == "initvariable":
            return set()

        sig = get_function_signature(fn_name)
        if sig is None:
            fallback_sources: set[tuple[str, ...]] = set()
            for arg in args:
                fallback_sources.update(self.collect_expression_effect_sources(arg, context))
            return fallback_sources

        signature_sources: set[tuple[str, ...]] = set()
        for idx, arg in enumerate(args):
            direction = "in"
            if idx < len(sig.parameters):
                direction = sig.parameters[idx].direction
            if direction not in {"in", "in var", "inout"}:
                continue
            signature_sources.update(self.collect_expression_effect_sources(arg, context))
        return signature_sources

    def collect_expression_effect_sources(
        self,
        obj: Any,
        context: ScopeContext,
    ) -> set[tuple[str, ...]]:
        """Recursively collect effect keys from an expression."""
        sources: set[tuple[str, ...]] = set()

        if obj is None:
            return sources

        if isinstance(obj, dict):
            if const.KEY_VAR_NAME in obj:
                full_ref = obj[const.KEY_VAR_NAME]
                key = self.resolve_effect_key(full_ref, context)
                if key is not None:
                    sources.add(key)
                return sources
            for value in obj.values():
                sources.update(self.collect_expression_effect_sources(value, context))
            return sources

        if isinstance(obj, list):
            for item in obj:
                sources.update(self.collect_expression_effect_sources(item, context))
            return sources

        if hasattr(obj, "data"):
            for child in getattr(obj, "children", []):
                sources.update(self.collect_expression_effect_sources(child, context))
            return sources

        if isinstance(obj, tuple):
            if obj and obj[0] == const.KEY_FUNCTION_CALL:
                _, fn_name, args = obj
                return self.collect_function_input_effect_keys(fn_name, args or [], context)
            for item in obj[1:] if obj and isinstance(obj[0], str) else obj:
                sources.update(self.collect_expression_effect_sources(item, context))
            return sources

        return sources

    def record_assignment_effect_flow(
        self,
        target_ref: str,
        expr: Any,
        context: ScopeContext,
    ) -> None:
        """Record effect flow from an expression to an assignment target."""
        target_key = self.resolve_effect_key(target_ref, context)
        for source_key in self.collect_expression_effect_sources(expr, context):
            self.record_effect_flow(source_key, target_key)

    def record_function_call_effect_flow(
        self,
        fn_name: str | None,
        args: list[Any],
        context: ScopeContext,
    ) -> None:
        """Record effect flows for a function call based on parameter directions."""
        if not fn_name:
            return

        fn_key = fn_name.casefold()
        if fn_key in {"copyvariable", "copyvarnosort"}:
            if len(args) < 2:
                return
            if not (
                isinstance(args[0], dict)
                and const.KEY_VAR_NAME in args[0]
                and isinstance(args[1], dict)
                and const.KEY_VAR_NAME in args[1]
            ):
                return
            source_key = self.resolve_effect_key(args[0][const.KEY_VAR_NAME], context)
            target_key = self.resolve_effect_key(args[1][const.KEY_VAR_NAME], context)
            self.record_effect_flow(source_key, target_key)
            return

        if fn_key == "initvariable":
            return

        sig = get_function_signature(fn_name)
        if sig is None:
            return

        input_keys: set[tuple[str, ...]] = set()
        output_keys: set[tuple[str, ...]] = set()
        for idx, arg in enumerate(args):
            direction = "in"
            if idx < len(sig.parameters):
                direction = sig.parameters[idx].direction

            if direction in {"in", "in var", "inout"}:
                input_keys.update(self.collect_expression_effect_sources(arg, context))

            if direction in {"out", "inout"} and isinstance(arg, dict) and const.KEY_VAR_NAME in arg:
                key = self.resolve_effect_key(arg[const.KEY_VAR_NAME], context)
                if key is not None:
                    output_keys.add(key)

        for output_key in output_keys:
            for input_key in input_keys:
                self.record_effect_flow(input_key, output_key)

    def collect_effect_sink_keys(
        self, bp, analyzed_target_is_library: bool, is_from_root_origin_fn
    ) -> set[tuple[str, ...]]:
        """Collect all variables that should be treated as effect sinks."""
        sink_keys = set(self._external_effect_sinks)

        if not analyzed_target_is_library:
            for variable in bp.localvariables or []:
                sink_keys.add(self.effect_key_for_variable(variable, [bp.header.name]))

        if analyzed_target_is_library:
            for moduletype in bp.moduletype_defs or []:
                if not is_from_root_origin_fn(getattr(moduletype, "origin_file", None)):
                    continue
                decl_path = [bp.header.name, f"TypeDef:{moduletype.name}"]
                for variable in moduletype.moduleparameters or []:
                    sink_keys.add(self.effect_key_for_variable(variable, decl_path))

        return sink_keys

    def compute_effective_output_keys(self, sink_keys: set[tuple[str, ...]]) -> set[tuple[str, ...]]:
        """Compute all variables that have effect flows reaching the sinks."""
        if not sink_keys:
            return set()

        incoming_edges: dict[tuple[str, ...], set[tuple[str, ...]]] = defaultdict(set)
        for source_key, target_keys in self._effect_flow_edges.items():
            for target_key in target_keys:
                incoming_edges[target_key].add(source_key)

        effective_keys = set(sink_keys)
        pending = list(sink_keys)
        while pending:
            target_key = pending.pop()
            for source_key in incoming_edges.get(target_key, set()):
                if source_key in effective_keys:
                    continue
                effective_keys.add(source_key)
                pending.append(source_key)
        return effective_keys

    def propagate_mapping_to_parent(
        self,
        pm: ParameterMapping,
        child_used_reads: set[str] | None,
        child_used_writes: set[str] | None,
        parent_env: dict[str, Variable],
        parent_path: list[str],
        external_typename: str | None,
        parent_context: ScopeContext | None = None,
        child_context: ScopeContext | None = None,
    ) -> None:
        """Propagate mapping effects to parent scope."""
        target_name = varname_base(pm.target)

        if child_context is not None and target_name is not None:
            target_var = child_context.env.get(target_name.casefold())
            source_key = self.mapping_source_effect_key(
                pm,
                parent_env=parent_env,
                parent_context=parent_context,
            )
            if target_var is not None and source_key is not None:
                target_key = self.effect_key_for_variable(target_var, child_context.module_path)
                if child_used_reads is not None and target_name in child_used_reads:
                    self.record_effect_flow(source_key, target_key)
                if child_used_writes is not None and target_name in child_used_writes:
                    self.record_effect_flow(target_key, source_key)

        # GLOBAL: resolve by walking up scopes, and only mark if parameter is used
        if pm.is_source_global:
            full_source = None
            if isinstance(pm.source, dict) and const.KEY_VAR_NAME in pm.source:
                full_source = pm.source[const.KEY_VAR_NAME]
            elif isinstance(pm.source, str):
                full_source = pm.source

            if not full_source:
                return

            source_parts = full_source.split(".", 1)
            source_base = source_parts[0]
            source_field_path = source_parts[1] if len(source_parts) > 1 else ""

            if parent_context is not None:
                src_var, _decl_path, _decl_display = parent_context.resolve_global_name(source_base)
            else:
                src_var = parent_env.get(source_base.lower())
                if src_var is None:
                    src_var = self._lookup_global_variable(source_base)

            if src_var is None:
                return

            # External types: conservatively treat mapping as read+written
            if external_typename is not None:
                if parent_context is not None:
                    source_key = self.resolve_effect_key(full_source, parent_context)
                    if source_key is not None:
                        self._external_effect_sinks.add(source_key)
                external_display_path: list[str] = []
                if parent_path:
                    external_display_path.append(decorate_segment(parent_path[0], "BP"))
                    external_display_path.extend(parent_path[1:])
                use_context = ScopeContext(
                    env=parent_env,
                    param_mappings={},
                    module_path=parent_path.copy(),
                    display_module_path=external_display_path,
                    parent_context=None,
                )

                if source_field_path:
                    self._get_usage(src_var).mark_field_read(source_field_path, parent_path)
                    self._get_usage(src_var).mark_field_written(source_field_path, parent_path)

                    cp = self._canonical_path(parent_path, src_var, source_field_path)
                    self._record_access(AccessKind.READ, cp, use_context, full_source)
                    self._record_access(AccessKind.WRITE, cp, use_context, full_source)
                else:
                    self._get_usage(src_var).mark_read(parent_path)
                    self._get_usage(src_var).mark_written(parent_path)

                    cp = self._canonical_path(parent_path, src_var, "")
                    self._record_access(AccessKind.READ, cp, use_context, full_source)
                    self._record_access(AccessKind.WRITE, cp, use_context, full_source)
                return

            if target_name is not None:
                if child_used_reads is not None and target_name in child_used_reads:
                    if source_field_path:
                        self._get_usage(src_var).mark_field_read(source_field_path, parent_path)
                    else:
                        self._get_usage(src_var).mark_read(parent_path)

                if child_used_writes is not None and target_name in child_used_writes:
                    if source_field_path:
                        self._get_usage(src_var).mark_field_written(source_field_path, parent_path)
                    else:
                        self._get_usage(src_var).mark_written(parent_path)
            return

        # Extract full source path with fields
        if isinstance(pm.source, dict) and const.KEY_VAR_NAME in pm.source:
            full_source = pm.source[const.KEY_VAR_NAME]
        elif isinstance(pm.source, str):
            full_source = pm.source
        else:
            return

        # Parse the source to get base and field path
        source_parts = full_source.split(".", 1)
        source_base = source_parts[0].lower()
        source_field_path = source_parts[1] if len(source_parts) > 1 else ""

        # Resolve the actual source variable
        src_var = parent_env.get(source_base)
        if src_var is None:
            src_var = self._lookup_global_variable(source_base)

        if src_var is None:
            return

        # External types: conservatively treat mapping as read+written
        if external_typename is not None:
            if parent_context is not None:
                source_key = self.resolve_effect_key(full_source, parent_context)
                if source_key is not None:
                    self._external_effect_sinks.add(source_key)
            external_mapping_display_path: list[str] = []
            if parent_path:
                external_mapping_display_path.append(decorate_segment(parent_path[0], "BP"))
                external_mapping_display_path.extend(parent_path[1:])
            use_context = ScopeContext(
                env=parent_env,
                param_mappings={},
                module_path=parent_path.copy(),
                display_module_path=external_mapping_display_path,
                parent_context=None,
            )

            if source_field_path:
                self._get_usage(src_var).mark_field_read(source_field_path, parent_path)
                self._get_usage(src_var).mark_field_written(source_field_path, parent_path)

                cp = self._canonical_path(parent_path, src_var, source_field_path)
                self._record_access(AccessKind.READ, cp, use_context, full_source)
                self._record_access(AccessKind.WRITE, cp, use_context, full_source)
            else:
                self._get_usage(src_var).mark_read(parent_path)
                self._get_usage(src_var).mark_written(parent_path)

                cp = self._canonical_path(parent_path, src_var, "")
                self._record_access(AccessKind.READ, cp, use_context, full_source)
                self._record_access(AccessKind.WRITE, cp, use_context, full_source)
            return

        # Internal types with field-aware propagation
        if target_name is not None:
            # If the child used the parameter for reading
            if child_used_reads is not None and target_name in child_used_reads:
                if source_field_path:
                    self._get_usage(src_var).mark_field_read(source_field_path, parent_path)
                else:
                    self._get_usage(src_var).mark_read(parent_path)

            # If the child used the parameter for writing
            if child_used_writes is not None and target_name in child_used_writes:
                if source_field_path:
                    self._get_usage(src_var).mark_field_written(source_field_path, parent_path)
                else:
                    self._get_usage(src_var).mark_written(parent_path)
