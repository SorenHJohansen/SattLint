from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

from sattline_parser.models.ast_model import (
    BasePicture,
    ModuleCode,
    ModuleTypeDef,
    SFCAlternative,
    SFCParallel,
    SFCStep,
    SFCSubsequence,
    SFCTransition,
    SFCTransitionSub,
)

from ..grammar import constants as const
from ..resolution.scope import ScopeContext
from ._dependency_usage_scope_support import _DependencyUsageScopeSupportMixin
from .sattline_builtins import get_function_signature


@dataclass(frozen=True)
class FactRef:
    key: tuple[str, ...]
    root_key: tuple[str, ...]
    display_name: str
    base_display_name: str
    field_path: str
    state_access: str | None
    decl_module_path: tuple[str, ...]
    has_initializer: bool
    is_moduleparameter: bool


@dataclass(frozen=True)
class CallFact:
    function_name: str
    args: tuple[FactRef | None, ...]


@dataclass(frozen=True)
class StatementFact:
    module_path: tuple[str, ...]
    site: str
    reads: tuple[FactRef, ...]
    writes: tuple[FactRef, ...]
    calls: tuple[CallFact, ...]


class DependencyUsageFactCollector(_DependencyUsageScopeSupportMixin):
    def __init__(
        self,
        base_picture: BasePicture,
        *,
        unavailable_libraries: set[str] | None = None,
        analyzed_target_is_library: bool = False,
    ) -> None:
        self.bp = base_picture
        self._unavailable_libraries = unavailable_libraries or set()
        self._analyzed_target_is_library = analyzed_target_is_library
        self._facts: list[StatementFact] = []
        self._active_typedefs: set[str] = set()
        self._moduleparameter_keys_by_context: dict[int, set[str]] = {}

    def collect(self) -> list[StatementFact]:
        self._walk_root_scope()
        for moduletype in self._iter_root_typedefs():
            module_path = [self.bp.header.name, f"TypeDef:{moduletype.name}"]
            context = self._build_scope_context(
                [*(moduletype.moduleparameters or []), *(moduletype.localvariables or [])],
                moduleparameters=moduletype.moduleparameters or [],
                param_mappings={},
                module_path=module_path,
                current_library=moduletype.origin_lib or getattr(self.bp, "origin_lib", None),
                parent_context=None,
            )
            self._walk_typedef(moduletype, context, module_path)
        return self._facts

    def _walk_root_scope(self) -> None:
        module_path = [self.bp.header.name]
        context = self._build_scope_context(
            list(self.bp.localvariables or []),
            moduleparameters=None,
            param_mappings={},
            module_path=module_path,
            current_library=getattr(self.bp, "origin_lib", None),
            parent_context=None,
        )
        self._walk_module_code(self.bp.modulecode, context, module_path)
        self._walk_modules(self.bp.submodules or [], context, module_path)

    def _walk_typedef(
        self,
        moduletype: ModuleTypeDef,
        context: ScopeContext,
        module_path: list[str],
    ) -> None:
        typedef_key = moduletype.name.casefold()
        if typedef_key in self._active_typedefs:
            return
        self._active_typedefs.add(typedef_key)
        try:
            self._walk_module_code(moduletype.modulecode, context, module_path)
            self._walk_modules(moduletype.submodules or [], context, module_path)
        finally:
            self._active_typedefs.discard(typedef_key)

    def _walk_module_code(
        self,
        modulecode: ModuleCode | None,
        context: ScopeContext,
        module_path: list[str],
    ) -> None:
        if modulecode is None:
            return
        for equation in modulecode.equations or []:
            site = f"equation block {equation.name!r}"
            for statement in equation.code or []:
                self._append_statement_fact(statement, context, module_path, site)
        for sequence in modulecode.sequences or []:
            self._walk_sequence_nodes(sequence.code or [], context, module_path, sequence.name)

    def _walk_sequence_nodes(
        self,
        nodes: list[Any],
        context: ScopeContext,
        module_path: list[str],
        sequence_name: str,
    ) -> None:
        for node in nodes:
            if isinstance(node, SFCStep):
                for phase, statements in (
                    ("ENTER", node.code.enter or []),
                    ("ACTIVE", node.code.active or []),
                    ("EXIT", node.code.exit or []),
                ):
                    site = f"sequence {sequence_name!r} step {node.name!r} {phase}"
                    for statement in statements:
                        self._append_statement_fact(statement, context, module_path, site)
                continue
            if isinstance(node, SFCTransition) and node.condition is not None:
                site = f"sequence {sequence_name!r} transition {node.name!r} condition"
                self._append_statement_fact(node.condition, context, module_path, site)
                continue
            if isinstance(node, SFCAlternative | SFCParallel):
                for branch in node.branches or []:
                    self._walk_sequence_nodes(branch, context, module_path, sequence_name)
                continue
            if isinstance(node, SFCSubsequence | SFCTransitionSub):
                self._walk_sequence_nodes(node.body or [], context, module_path, sequence_name)

    def _append_statement_fact(
        self,
        node: Any,
        context: ScopeContext,
        module_path: list[str],
        site: str,
    ) -> None:
        reads: list[FactRef] = []
        writes: list[FactRef] = []
        calls: list[CallFact] = []
        seen_reads: set[tuple[str, ...]] = set()
        seen_writes: set[tuple[str, ...]] = set()
        self._collect_node_facts(
            node,
            context,
            reads=reads,
            writes=writes,
            calls=calls,
            seen_reads=seen_reads,
            seen_writes=seen_writes,
        )
        if not reads and not writes and not calls:
            return
        self._facts.append(
            StatementFact(
                module_path=tuple(module_path),
                site=site,
                reads=tuple(reads),
                writes=tuple(writes),
                calls=tuple(calls),
            )
        )

    def _collect_fact_items(
        self,
        items: Any,
        context: ScopeContext,
        *,
        reads: list[FactRef],
        writes: list[FactRef],
        calls: list[CallFact],
        seen_reads: set[tuple[str, ...]],
        seen_writes: set[tuple[str, ...]],
    ) -> None:
        for item in items:
            self._collect_node_facts(
                item,
                context,
                reads=reads,
                writes=writes,
                calls=calls,
                seen_reads=seen_reads,
                seen_writes=seen_writes,
            )

    def _collect_node_facts(
        self,
        node: Any,
        context: ScopeContext,
        *,
        reads: list[FactRef],
        writes: list[FactRef],
        calls: list[CallFact],
        seen_reads: set[tuple[str, ...]],
        seen_writes: set[tuple[str, ...]],
    ) -> None:
        if node is None:
            return

        if isinstance(node, dict) and const.KEY_VAR_NAME in node:
            resolved = self._resolve_ref(node, context)
            if resolved is not None and resolved.key not in seen_reads:
                seen_reads.add(resolved.key)
                reads.append(resolved)
            return

        if hasattr(node, "data") and getattr(node, "data", None) == const.KEY_STATEMENT:
            self._collect_fact_items(
                getattr(node, "children", []),
                context,
                reads=reads,
                writes=writes,
                calls=calls,
                seen_reads=seen_reads,
                seen_writes=seen_writes,
            )
            return

        if isinstance(node, tuple) and node:
            tag = node[0]
            if tag == const.KEY_ASSIGN and len(node) >= 3:
                _assign, target, expr = node[:3]
                self._collect_node_facts(
                    expr,
                    context,
                    reads=reads,
                    writes=writes,
                    calls=calls,
                    seen_reads=seen_reads,
                    seen_writes=seen_writes,
                )
                resolved = self._resolve_ref(target, context)
                if resolved is not None and resolved.key not in seen_writes:
                    seen_writes.add(resolved.key)
                    writes.append(resolved)
                return

            if tag == const.KEY_FUNCTION_CALL and len(node) == 3:
                _call, function_name, args = node
                call_name = str(function_name)
                signature = get_function_signature(call_name)
                resolved_args: list[FactRef | None] = []
                for index, argument in enumerate(args or []):
                    direction = "in"
                    if signature is not None and index < len(signature.parameters):
                        direction = signature.parameters[index].direction
                    if direction in {"in", "in var", "inout"}:
                        self._collect_node_facts(
                            argument,
                            context,
                            reads=reads,
                            writes=writes,
                            calls=calls,
                            seen_reads=seen_reads,
                            seen_writes=seen_writes,
                        )
                    resolved = self._resolve_ref(argument, context)
                    resolved_args.append(resolved)
                    if direction in {"out", "inout"} and resolved is not None and resolved.key not in seen_writes:
                        seen_writes.add(resolved.key)
                        writes.append(resolved)
                calls.append(CallFact(function_name=call_name, args=tuple(resolved_args)))
                return

            if tag == const.GRAMMAR_VALUE_IF and len(node) == 3:
                _if_tag, branches, else_block = node
                for condition, branch_statements in branches or []:
                    self._collect_node_facts(
                        condition,
                        context,
                        reads=reads,
                        writes=writes,
                        calls=calls,
                        seen_reads=seen_reads,
                        seen_writes=seen_writes,
                    )
                    self._collect_fact_items(
                        branch_statements or [],
                        context,
                        reads=reads,
                        writes=writes,
                        calls=calls,
                        seen_reads=seen_reads,
                        seen_writes=seen_writes,
                    )
                self._collect_fact_items(
                    else_block or [],
                    context,
                    reads=reads,
                    writes=writes,
                    calls=calls,
                    seen_reads=seen_reads,
                    seen_writes=seen_writes,
                )
                return

            self._collect_fact_items(
                node[1:],
                context,
                reads=reads,
                writes=writes,
                calls=calls,
                seen_reads=seen_reads,
                seen_writes=seen_writes,
            )
            return

        if isinstance(node, list):
            self._collect_fact_items(
                node,
                context,
                reads=reads,
                writes=writes,
                calls=calls,
                seen_reads=seen_reads,
                seen_writes=seen_writes,
            )
            return

        children = getattr(node, "children", None)
        if children is not None:
            self._collect_fact_items(
                children,
                context,
                reads=reads,
                writes=writes,
                calls=calls,
                seen_reads=seen_reads,
                seen_writes=seen_writes,
            )
            return

        node_dict = getattr(node, "__dict__", None)
        if node_dict is not None:
            self._collect_fact_items(
                node_dict.values(),
                context,
                reads=reads,
                writes=writes,
                calls=calls,
                seen_reads=seen_reads,
                seen_writes=seen_writes,
            )

    def _resolve_ref(self, expr: Any, context: ScopeContext) -> FactRef | None:
        if not (isinstance(expr, dict) and const.KEY_VAR_NAME in expr):
            return None
        expr_map = cast(dict[str, object], expr)
        full_name = expr_map.get(const.KEY_VAR_NAME)
        if not isinstance(full_name, str):
            return None
        variable, field_path, decl_path, _decl_display_path = context.resolve_variable(full_name)
        if variable is None:
            return None
        declaring_context = self._find_declaring_context(context, decl_path)
        raw_state_access = expr_map.get("state")
        state_access = raw_state_access if isinstance(raw_state_access, str) else None
        key = self._state_key(decl_path, variable.name, field_path, state_access)
        root_key = self._state_key(decl_path, variable.name, "", state_access)
        display_name = full_name if not state_access else f"{full_name}:{state_access.title()}"
        return FactRef(
            key=key,
            root_key=root_key,
            display_name=display_name,
            base_display_name=full_name,
            field_path=field_path,
            state_access=state_access,
            decl_module_path=tuple(decl_path),
            has_initializer=variable.init_value is not None,
            is_moduleparameter=variable.name.casefold()
            in self._moduleparameter_keys_by_context.get(id(declaring_context), set()),
        )

    def _find_declaring_context(
        self,
        context: ScopeContext,
        decl_path: list[str],
    ) -> ScopeContext:
        current: ScopeContext | None = context
        while current is not None:
            if current.module_path == decl_path:
                return current
            current = current.parent_context
        return context

    def _state_key(
        self,
        module_path: list[str],
        variable_name: str,
        field_path: str,
        state_access: str | None,
    ) -> tuple[str, ...]:
        segments = [segment.casefold() for segment in module_path]
        segments.append(variable_name.casefold())
        if field_path:
            segments.extend(segment.casefold() for segment in field_path.split(".") if segment)
        if state_access:
            segments.append(f"__state__:{state_access.casefold()}")
        return tuple(segments)


def collect_statement_facts(
    base_picture: BasePicture,
    *,
    unavailable_libraries: set[str] | None = None,
    analyzed_target_is_library: bool = False,
) -> list[StatementFact]:
    return DependencyUsageFactCollector(
        base_picture,
        unavailable_libraries=unavailable_libraries,
        analyzed_target_is_library=analyzed_target_is_library,
    ).collect()
