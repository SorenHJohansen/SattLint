from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from sattlint.parser_api import (
    Assignment,
    BasePicture,
    FuncCallStmt,
    IfStmt,
    ModuleCode,
    ModuleTypeDef,
    SFCAlternative,
    SFCParallel,
    SFCStep,
    SFCSubsequence,
    SFCTransition,
    SFCTransitionSub,
    VarRef,
    get_function_signature,
    walk,
)

from ...resolution.scope import ScopeContext
from .._dependency_usage_scope_support import DependencyUsageScopeSupportMixin


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


class DependencyUsageFactCollector(DependencyUsageScopeSupportMixin):
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
        for equation in modulecode.equationblocks or []:
            site = f"equation block {equation.name!r}"
            for statement in equation.code or []:
                self._append_statement_fact(statement, context, module_path, site)
        for sequence in modulecode.sequences or []:
            self._walk_sequence_nodes(sequence.code or [], context, module_path, sequence.name or "")

    def _walk_sequence_nodes(
        self,
        nodes: Sequence[object],
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
        node: object,
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

    def _collect_node_facts(
        self,
        node: object,
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

        if isinstance(node, IfStmt):
            for condition, branch_statements in node.branches:
                self._collect_node_facts(
                    condition,
                    context,
                    reads=reads,
                    writes=writes,
                    calls=calls,
                    seen_reads=seen_reads,
                    seen_writes=seen_writes,
                )
                for statement in branch_statements:
                    self._collect_node_facts(
                        statement,
                        context,
                        reads=reads,
                        writes=writes,
                        calls=calls,
                        seen_reads=seen_reads,
                        seen_writes=seen_writes,
                    )
            for statement in node.else_block or ():
                self._collect_node_facts(
                    statement,
                    context,
                    reads=reads,
                    writes=writes,
                    calls=calls,
                    seen_reads=seen_reads,
                    seen_writes=seen_writes,
                )
            return

        if isinstance(node, Assignment):
            self._collect_node_facts(
                node.value,
                context,
                reads=reads,
                writes=writes,
                calls=calls,
                seen_reads=seen_reads,
                seen_writes=seen_writes,
            )
            resolved = self._resolve_ref(node.target, context)
            if resolved is not None and resolved.key not in seen_writes:
                seen_writes.add(resolved.key)
                writes.append(resolved)
            return

        if isinstance(node, FuncCallStmt):
            call_name = node.call.name
            args = list(node.call.args) if node.call.args else []
            signature = get_function_signature(call_name)
            resolved_args: list[FactRef | None] = []
            for index, argument in enumerate(args):
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

        for event in walk(node):
            reference = event.node
            if not isinstance(reference, VarRef):
                continue
            resolved = self._resolve_ref(reference, context)
            if resolved is not None and resolved.key not in seen_reads:
                seen_reads.add(resolved.key)
                reads.append(resolved)

    def _resolve_ref(self, expr: object, context: ScopeContext) -> FactRef | None:
        if not isinstance(expr, VarRef):
            return None
        full_name = expr.name
        variable, field_path, decl_path, _decl_display_path = context.resolve_variable(full_name)
        if variable is None:
            return None
        declaring_context = self._find_declaring_context(context, decl_path)
        state_access = expr.state if isinstance(expr.state, str) else None
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
