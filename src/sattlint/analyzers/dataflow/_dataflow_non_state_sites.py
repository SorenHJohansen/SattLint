"""Non-STATE cross-site access collection inside the dataflow analyzer.

A non-STATE variable that is read and written across two or more distinct
continuous scan sites (equation blocks and active step phases) within one scan
is a scan-order hazard. This mirrors the former ``same-cycle`` check, now owned
by dataflow alongside the other scan-cycle semantics.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from collections.abc import Sequence as SequenceABC
from dataclasses import dataclass
from typing import Any, cast

from sattline_parser.models.ast_model import (
    BasePicture,
    ModuleCode,
    ModuleTypeDef,
    ModuleTypeInstance,
    Sequence,
    SFCAlternative,
    SFCBreak,
    SFCFork,
    SFCParallel,
    SFCStep,
    SFCSubsequence,
    SFCTransition,
    SFCTransitionSub,
    SingleModule,
)
from sattline_parser.models.expressions import Assignment, FuncCallStmt, VarRef

from ...grammar import constants as const
from ...resolution.common import resolve_moduletype_def_strict
from ...resolution.scope import ScopeContext
from ..sattline_builtins import get_function_signature
from ..shared.ast_node_helpers import object_tuple as _object_tuple
from ..shared.ast_node_helpers import sequence_as_list as _sequence_as_list
from ..shared.ast_node_helpers import statement_children as _statement_children

_READ = "read"
_WRITE = "write"


@dataclass(frozen=True)
class _SiteAccess:
    module_path: tuple[str, ...]
    symbol_key: tuple[str, ...]
    symbol_display: str
    decl_module_path: tuple[str, ...]
    is_state_variable: bool
    continuous_site: str | None
    kind: str
    site: str


def _prefix_conflict(left: tuple[str, ...], right: tuple[str, ...]) -> bool:
    if len(left) <= len(right):
        return right[: len(left)] == left
    return left[: len(right)] == right


def _conflict_rep(left: tuple[str, ...], right: tuple[str, ...]) -> tuple[str, ...]:
    return left if len(left) <= len(right) else right


def collect_non_state_multi_site_issues(self: Any) -> None:
    """Append ``dataflow.non_state_multi_site`` issues for cross-site access."""
    accesses: list[_SiteAccess] = []
    _walk_root_scope(self, accesses)
    for moduletype in self._iter_root_typedefs():
        _walk_typedef(self, moduletype, accesses)

    grouped: dict[
        tuple[str, ...],
        tuple[
            tuple[str, ...],
            tuple[str, ...],
            dict[tuple[tuple[str, ...], str], set[str]],
            dict[tuple[tuple[str, ...], str], set[str]],
        ],
    ] = {}

    display_by_key: dict[tuple[str, ...], str] = {}

    for index, left in enumerate(accesses):
        if left.is_state_variable or left.continuous_site is None:
            continue
        for right in accesses[index + 1 :]:
            if right.is_state_variable or right.continuous_site is None:
                continue
            if left.module_path != right.module_path:
                continue
            if not _prefix_conflict(left.symbol_key, right.symbol_key):
                continue
            representative = _conflict_rep(left.symbol_key, right.symbol_key)
            key = representative
            if key not in grouped:
                grouped[key] = (representative, left.decl_module_path, defaultdict(set), defaultdict(set))
                shorter = left if len(left.symbol_key) <= len(right.symbol_key) else right
                display_by_key[key] = shorter.symbol_display
            _representative, _decl_path, actions, sites = grouped[key]
            for event in (left, right):
                site_key = (event.module_path, str(event.continuous_site))
                actions[site_key].add(event.kind)
                if event.site:
                    sites[site_key].add(event.site)

    for representative, decl_module_path, actions, sites in sorted(grouped.values(), key=lambda item: str(item[0])):
        if len(actions) < 2:
            continue
        if not any(_READ in kinds for kinds in actions.values()):
            continue
        if not any(_WRITE in kinds for kinds in actions.values()):
            continue

        ordered_site_keys = sorted(actions, key=lambda key: (len(key[0]), tuple(s.casefold() for s in key[0]), key[1]))
        summaries = [_format_site_summary(site_key, actions[site_key]) for site_key in ordered_site_keys]
        display = display_by_key.get(representative, ".".join(representative))
        self._add_issue(
            kind="dataflow.non_state_multi_site",
            message=(
                f"Non-STATE variable {display!r} is read and written across multiple "
                f"continuous scan sites: {'; '.join(summaries)}"
            ),
            module_path=list(decl_module_path),
            data={
                "symbol": display,
                "decl_module_path": list(decl_module_path),
                "continuous_sites": [
                    {
                        "module_path": list(site_key[0]),
                        "site": site_key[1],
                        "kinds": sorted(actions[site_key]),
                        "evidence_sites": sorted(site for site in sites[site_key] if site),
                    }
                    for site_key in ordered_site_keys
                ],
                "site": ":".join([*ordered_site_keys[0][0], ordered_site_keys[0][1]]),
                "context": display,
            },
        )


def _format_site_summary(site_key: tuple[tuple[str, ...], str], kinds: set[str]) -> str:
    module_path, site_label = site_key
    if len(module_path) == 1:
        location = module_path[0]
    elif module_path:
        location = ".".join(module_path[1:])
    else:
        location = ""
    return f"{location} [{site_label}] ({'/'.join(sorted(kinds))})"


def _typed_bp(self: Any) -> BasePicture:
    return cast(BasePicture, self.bp)


def _walk_root_scope(self: Any, accesses: list[_SiteAccess]) -> None:
    bp = _typed_bp(self)
    root_path = [bp.header.name]
    root_variables = list(bp.localvariables or [])
    context = self._build_scope_context(
        root_variables,
        param_mappings={},
        module_path=root_path,
        current_library=getattr(bp, "origin_lib", None),
        parent_context=None,
    )
    _walk_module_code(self, bp.modulecode, context, root_path, accesses)
    _walk_modules(self, bp.submodules or [], context, root_path, accesses)


def _walk_typedef(self: Any, moduletype: ModuleTypeDef, accesses: list[_SiteAccess]) -> None:
    bp = _typed_bp(self)
    path = [bp.header.name, f"TypeDef:{moduletype.name}"]
    context, _state = self._build_typedef_seed(moduletype, path)
    _walk_module_code(self, moduletype.modulecode, context, path, accesses)
    _walk_modules(self, moduletype.submodules or [], context, path, accesses)


def _walk_modules(
    self: Any,
    children: list[SingleModule | ModuleTypeInstance | Any],
    parent_context: ScopeContext,
    parent_path: list[str],
    accesses: list[_SiteAccess],
) -> None:
    for child in children:
        child_path = [*parent_path, child.header.name]
        if isinstance(child, SingleModule):
            context = self._build_single_context(child, parent_context, child_path)
            _walk_module_code(self, child.modulecode, context, child_path, accesses)
            _walk_modules(self, child.submodules or [], context, child_path, accesses)
            continue
        if isinstance(child, ModuleTypeInstance):
            _walk_moduletype_instance(self, child, parent_context, child_path, accesses)
            continue
        # FrameModule and other transparent containers.
        _walk_module_code(self, getattr(child, "modulecode", None), parent_context, child_path, accesses)
        _walk_modules(self, getattr(child, "submodules", None) or [], parent_context, child_path, accesses)


def _walk_moduletype_instance(
    self: Any,
    instance: ModuleTypeInstance,
    parent_context: ScopeContext,
    child_path: list[str],
    accesses: list[_SiteAccess],
) -> None:
    try:
        moduletype = resolve_moduletype_def_strict(
            _typed_bp(self),
            instance.moduletype_name,
            current_library=parent_context.current_library,
            unavailable_libraries=getattr(self, "_unavailable_libraries", None) or set(),
        )
    except ValueError:
        return
    if not self._is_from_root_origin(
        getattr(moduletype, "origin_file", None),
        getattr(moduletype, "origin_lib", None),
    ):
        return
    context = self._build_typedef_context(moduletype, instance, parent_context, child_path)
    _walk_module_code(self, moduletype.modulecode, context, child_path, accesses)
    _walk_modules(self, moduletype.submodules or [], context, child_path, accesses)


def _walk_module_code(
    self: Any,
    modulecode: ModuleCode | None,
    context: ScopeContext,
    module_path: list[str],
    accesses: list[_SiteAccess],
) -> None:
    if modulecode is None:
        return
    for equation in modulecode.equations or []:
        label = f"EQ:{getattr(equation, 'name', '<unnamed>')}"
        for statement in equation.code or []:
            _record_statement(self, statement, context, module_path, label, accesses)
    for sequence in modulecode.sequences or []:
        _walk_sequence(self, sequence, context, module_path, accesses)


def _walk_sequence(
    self: Any,
    sequence: Sequence,
    context: ScopeContext,
    module_path: list[str],
    accesses: list[_SiteAccess],
) -> None:
    _walk_sequence_nodes(self, sequence.code or [], context, module_path, accesses)


def _walk_sequence_nodes(
    self: Any,
    nodes: SequenceABC[object],
    context: ScopeContext,
    module_path: list[str],
    accesses: list[_SiteAccess],
) -> None:
    for index, node in enumerate(nodes):
        if isinstance(node, SFCStep):
            _walk_step(
                self, node, context, module_path, accesses, direct_self_loop=_step_has_direct_self_loop(nodes, index)
            )
            continue
        if isinstance(node, SFCTransition):
            loop_step = _transition_loop_step_name(nodes, index)
            label = None if loop_step is None else f"STEP:{loop_step}:TRANS:{node.name or '<unnamed>'}"
            _record_expression(self, node.condition, context, module_path, label, accesses)
            continue
        if isinstance(node, SFCAlternative | SFCParallel):
            for branch in node.branches or []:
                _walk_sequence_nodes(self, branch or [], context, module_path, accesses)
            continue
        if isinstance(node, SFCSubsequence | SFCTransitionSub):
            _walk_sequence_nodes(self, node.body or [], context, module_path, accesses)
            continue
        if isinstance(node, (SFCFork, SFCBreak)):
            continue


def _walk_step(
    self: Any,
    step: SFCStep,
    context: ScopeContext,
    module_path: list[str],
    accesses: list[_SiteAccess],
    *,
    direct_self_loop: bool,
) -> None:
    base = f"STEP:{step.name}"
    for phase, statements in (
        ("ENTER", step.code.enter or []),
        ("ACTIVE", step.code.active or []),
        ("EXIT", step.code.exit or []),
    ):
        label = f"{base}:{phase}" if (phase == "ACTIVE" or direct_self_loop) else None
        for statement in statements:
            _record_statement(self, statement, context, module_path, label, accesses)


def _collect_entry_step_names(nodes: SequenceABC[object]) -> set[str]:
    for node in nodes:
        if isinstance(node, SFCStep):
            return {(node.name or "").casefold()}
        if isinstance(node, SFCParallel | SFCAlternative):
            active: set[str] = set()
            for branch in node.branches or []:
                active.update(_collect_entry_step_names(branch or []))
            if active:
                return active
            continue
        if isinstance(node, SFCSubsequence | SFCTransitionSub):
            active = _collect_entry_step_names(node.body or [])
            if active:
                return active
    return set()


def _step_has_direct_self_loop(nodes: SequenceABC[object], index: int) -> bool:
    node = nodes[index]
    if not isinstance(node, SFCStep) or index + 1 >= len(nodes):
        return False
    step_key = (node.name or "").casefold()
    next_node = nodes[index + 1]
    if isinstance(next_node, SFCFork):
        return any(target.casefold() == step_key for target in next_node.targets)
    if not isinstance(next_node, SFCTransition):
        return False
    tail = nodes[index + 2 :]
    if not tail:
        return True
    first_tail = tail[0]
    if isinstance(first_tail, SFCFork):
        return any(target.casefold() == step_key for target in first_tail.targets)
    return not _collect_entry_step_names(tail)


def _transition_loop_step_name(nodes: SequenceABC[object], index: int) -> str | None:
    if index == 0 or not isinstance(nodes[index], SFCTransition):
        return None
    previous_node = nodes[index - 1]
    if not isinstance(previous_node, SFCStep):
        return None
    if not _step_has_direct_self_loop(nodes, index - 1):
        return None
    return previous_node.name


def _record_statement(
    self: Any,
    statement: object,
    context: ScopeContext,
    module_path: list[str],
    continuous_site: str | None,
    accesses: list[_SiteAccess],
) -> None:
    statement_children = _statement_children(statement)
    if statement_children is not None:
        for child in statement_children:
            _record_statement(self, child, context, module_path, continuous_site, accesses)
        return

    if isinstance(statement, Assignment):
        _record_expression(self, statement.value, context, module_path, continuous_site, accesses)
        _record_ref(self, statement.target, _WRITE, context, module_path, continuous_site, accesses)
        return

    if isinstance(statement, FuncCallStmt):
        args = _sequence_as_list(statement.call.args)
        _record_call_arguments(self, statement.call.name, args, context, module_path, continuous_site, accesses)
        return

    tuple_node = _object_tuple(statement)
    if tuple_node is not None and tuple_node:
        tag = tuple_node[0]
        if tag == const.KEY_ASSIGN and len(tuple_node) >= 3:
            _record_expression(self, tuple_node[2], context, module_path, continuous_site, accesses)
            _record_ref(self, tuple_node[1], _WRITE, context, module_path, continuous_site, accesses)
            return
        if tag == const.KEY_FUNCTION_CALL and len(tuple_node) >= 3:
            function_name = tuple_node[1]
            args = _sequence_as_list(tuple_node[2])
            _record_call_arguments(
                self,
                function_name if isinstance(function_name, str) else None,
                args,
                context,
                module_path,
                continuous_site,
                accesses,
            )
            return

    _record_expression(self, statement, context, module_path, continuous_site, accesses)


def _record_call_arguments(
    self: Any,
    function_name: str | None,
    args: list[Any],
    context: ScopeContext,
    module_path: list[str],
    continuous_site: str | None,
    accesses: list[_SiteAccess],
) -> None:
    signature = get_function_signature(function_name) if function_name else None
    for index, argument in enumerate(args):
        direction = "in"
        if signature is not None and index < len(signature.parameters):
            direction = signature.parameters[index].direction
        if direction in {"in", "in var", "inout"}:
            _record_expression(self, argument, context, module_path, continuous_site, accesses)
        if direction in {"out", "inout"}:
            _record_ref(self, argument, _WRITE, context, module_path, continuous_site, accesses)


def _record_expression(
    self: Any,
    node: object,
    context: ScopeContext,
    module_path: list[str],
    continuous_site: str | None,
    accesses: list[_SiteAccess],
) -> None:
    for ref in _iter_ref_nodes(node):
        _record_ref(self, ref, _READ, context, module_path, continuous_site, accesses)


def _iter_ref_nodes(node: object) -> Iterable[object]:
    if node is None:
        return
    if isinstance(node, VarRef):
        yield node
        return
    if isinstance(node, Mapping):
        mapping = cast(Mapping[object, object], node)
        if const.KEY_VAR_NAME in mapping:
            yield node
            return
        for value in mapping.values():
            yield from _iter_ref_nodes(value)
        return
    if isinstance(node, tuple):
        sequence = cast(tuple[object, ...], node)
        if const.KEY_VAR_NAME in sequence:
            yield node
            return
        for value in sequence:
            yield from _iter_ref_nodes(value)
        return
    children = getattr(node, "children", None)
    if isinstance(children, list | tuple):
        for child in cast(list[object] | tuple[object, ...], children):
            yield from _iter_ref_nodes(child)
        return


def _record_ref(
    self: Any,
    ref: object,
    kind: str,
    context: ScopeContext,
    module_path: list[str],
    continuous_site: str | None,
    accesses: list[_SiteAccess],
) -> None:
    resolved = self._resolve_ref(ref, context)
    if resolved is None:
        return
    decl_module_path = _decl_path_from_symbol_key(resolved.symbol_root_key)
    display_path = str(getattr(resolved, "base_display_name", "") or "")
    full_name = _ref_full_name(ref)
    if full_name is not None:
        variable, field_path, decl_path, _display = context.resolve_variable(full_name)
        if variable is not None:
            decl_module_path = tuple(decl_path)
            parts = [*decl_path, variable.name, *(segment for segment in field_path.split(".") if segment)]
            display_path = ".".join(parts)
    accesses.append(
        _SiteAccess(
            module_path=tuple(module_path),
            symbol_key=resolved.symbol_root_key,
            symbol_display=display_path,
            decl_module_path=decl_module_path,
            is_state_variable=bool(resolved.is_state_variable),
            continuous_site=continuous_site,
            kind=kind,
            site=continuous_site or "",
        )
    )


def _ref_full_name(ref: object) -> str | None:
    if isinstance(ref, VarRef):
        return ref.name
    if isinstance(ref, dict):
        name = cast(dict[str, object], ref).get(const.KEY_VAR_NAME)
        return name if isinstance(name, str) else None
    return None


def _decl_path_from_symbol_key(symbol_root_key: tuple[str, ...]) -> tuple[str, ...]:
    return symbol_root_key[:-1]


__all__ = ["collect_non_state_multi_site_issues"]
