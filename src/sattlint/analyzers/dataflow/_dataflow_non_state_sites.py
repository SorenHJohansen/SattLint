"""Non-STATE cross-site write conflict collection inside the dataflow analyzer.

A non-STATE variable written from two or more continuous scan sites that can be
active in the same scan is an unordered write conflict. Equation blocks run
every scan. Steps run in their own sequence, so two steps in one sequence are
mutually exclusive while steps in different sequences are concurrent. This
mirrors the former ``same-cycle`` check, now owned by dataflow alongside the
other scan-cycle semantics.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from collections.abc import Sequence as SequenceABC
from dataclasses import dataclass
from typing import Any, cast

from sattlint.parser_api import (
    Assignment,
    BasePicture,
    BoolOp,
    FuncCall,
    FuncCallStmt,
    IfStmt,
    ModuleCode,
    ModuleTypeDef,
    ModuleTypeInstance,
    NotOp,
    Sequence,
    SFCAlternative,
    SFCFork,
    SFCParallel,
    SFCStep,
    SFCSubsequence,
    SFCTransition,
    SFCTransitionSub,
    SingleModule,
    VarRef,
    walk,
)

from ...core.call_signatures import resolve_call_signature
from ...resolution.common import resolve_moduletype_def_strict
from ...resolution.scope import ScopeContext
from ..shared.ast_node_helpers import sequence_as_list as _sequence_as_list
from ..shared.instance_paths import collect_instance_paths

_READ = "read"
_WRITE = "write"

# A write site is one continuous site in one module. ``sequence_key`` is the
# sequence that owns a step site, or ``None`` for an equation block, which is
# active in every scan.
type _SiteKey = tuple[tuple[str, ...], tuple[str, ...] | None, str]


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
    sequence_key: tuple[str, ...] | None = None
    active_sequence: tuple[str, ...] | None = None


@dataclass(slots=True)
class _SiteGroup:
    """Every access that shares a conflicting symbol path within one module."""

    representative: tuple[str, ...]
    decl_module_path: tuple[str, ...]
    display: str
    actions: dict[_SiteKey, set[str]]
    sites: dict[_SiteKey, set[str]]
    active_sequences: dict[_SiteKey, tuple[str, ...] | None]


def _group_site_accesses(accesses: list[_SiteAccess]) -> list[_SiteGroup]:
    """Group accesses by the symbol path a prefix conflict would report.

    Two accesses conflict when one symbol path is a prefix of the other inside
    the same module, so every access joins the group of each of its own
    prefixes that another eligible access also uses. That is the same relation
    the pairwise scan applied, without comparing every access with every other.
    """
    eligible = [access for access in accesses if not access.is_state_variable and access.continuous_site is not None]

    keys_by_module: dict[tuple[str, ...], set[tuple[str, ...]]] = defaultdict(set)
    first_by_key: dict[tuple[str, ...], _SiteAccess] = {}
    for access in eligible:
        keys_by_module[access.module_path].add(access.symbol_key)
        first_by_key.setdefault(access.symbol_key, access)

    groups: dict[tuple[str, ...], _SiteGroup] = {}
    for access in eligible:
        module_keys = keys_by_module[access.module_path]
        for size in range(1, len(access.symbol_key) + 1):
            prefix = access.symbol_key[:size]
            if prefix not in module_keys:
                continue
            group = groups.get(prefix)
            if group is None:
                group = _SiteGroup(
                    representative=prefix,
                    decl_module_path=access.decl_module_path,
                    display=first_by_key[prefix].symbol_display,
                    actions=defaultdict(set),
                    sites=defaultdict(set),
                    active_sequences={},
                )
                groups[prefix] = group
            site_key: _SiteKey = (access.module_path, access.sequence_key, str(access.continuous_site))
            group.actions[site_key].add(access.kind)
            group.active_sequences.setdefault(site_key, access.active_sequence)
            if access.site:
                group.sites[site_key].add(access.site)

    comparable: dict[tuple[tuple[str, ...], tuple[str, ...]], _SiteGroup] = {}
    for group in groups.values():
        key = (group.representative, group.decl_module_path)
        existing = comparable.get(key)
        if existing is None:
            comparable[key] = group
            continue
        for site_key, kinds in group.actions.items():
            existing.actions[site_key] |= kinds
        for site_key, sites in group.sites.items():
            existing.sites[site_key] |= sites
        for site_key, marker in group.active_sequences.items():
            existing.active_sequences.setdefault(site_key, marker)

    return sorted(comparable.values(), key=lambda group: str(group.representative))


def _sites_can_share_a_scan(
    left: _SiteKey,
    right: _SiteKey,
    active_sequences: dict[_SiteKey, tuple[str, ...] | None],
) -> bool:
    """Whether two write sites can both be active in one scan.

    An equation block is active in every scan unless its guard names an
    operation sequence that is not reset. A step site belongs to one sequence,
    and SattLine runs the steps of a sequence one at a time, so two sites in
    the same sequence are never compared. Different sequences run concurrently,
    so their step sites are.
    """
    if left == right:
        return False
    left_marker = active_sequences.get(left)
    right_marker = active_sequences.get(right)
    if left_marker is not None and right_marker is not None and left_marker != right_marker:
        # Sibling operation equations guarded by different ``NOT <Seq>.Reset``
        # flags belong to different operations; only one operation is active.
        return False
    left_sequence = left[1]
    right_sequence = right[1]
    if left_sequence is None or right_sequence is None:
        return True
    return left_sequence != right_sequence


def _ordered_site_keys(site_keys: Iterable[_SiteKey]) -> list[_SiteKey]:
    return sorted(
        site_keys,
        key=lambda key: (len(key[0]), tuple(segment.casefold() for segment in key[0]), key[1] or (), key[2]),
    )


def _conflicting_write_sites(
    actions: dict[_SiteKey, set[str]],
    active_sequences: dict[_SiteKey, tuple[str, ...] | None],
) -> list[_SiteKey]:
    """The write sites that share a scan with at least one other write site."""
    write_sites = [site_key for site_key, kinds in actions.items() if _WRITE in kinds]
    participating: set[_SiteKey] = set()
    for index, left in enumerate(write_sites):
        for right in write_sites[index + 1 :]:
            if _sites_can_share_a_scan(left, right, active_sequences):
                participating.add(left)
                participating.add(right)
    return _ordered_site_keys(participating)


def collect_non_state_multi_site_issues(self: Any) -> None:
    """Append ``dataflow.non_state_multi_site`` issues for write conflicts."""
    accesses: list[_SiteAccess] = []
    _walk_root_scope(self, accesses)
    # A moduletype that the picture already invokes was walked through that
    # instance. Walking its root definition again would key the same logical
    # sites under a second ``TypeDef:`` spelling, and path rewriting later
    # collapses both spellings onto the first invocation.
    invoked_typedefs = set(collect_instance_paths(_typed_bp(self)))
    for moduletype in self._iter_root_typedefs():
        if moduletype.name.casefold() in invoked_typedefs:
            continue
        _walk_typedef(self, moduletype, accesses)

    for group in _group_site_accesses(accesses):
        decl_module_path = group.decl_module_path
        actions = group.actions
        sites = group.sites
        conflicting_sites = _conflicting_write_sites(actions, group.active_sequences)
        if len(conflicting_sites) < 2:
            continue

        summaries = [_format_site_summary(site_key, actions[site_key]) for site_key in conflicting_sites]
        display = group.display
        self._add_issue(
            kind="dataflow.non_state_multi_site",
            message=(
                f"Non-STATE variable {display!r} is written from multiple continuous "
                f"scan sites that can be active in the same scan: {'; '.join(summaries)}"
            ),
            module_path=list(decl_module_path),
            data={
                "symbol": display,
                "decl_module_path": list(decl_module_path),
                "continuous_sites": [
                    {
                        "module_path": list(site_key[0]),
                        "site": site_key[2],
                        "kinds": sorted(actions[site_key]),
                        "evidence_sites": sorted(site for site in sites[site_key] if site),
                    }
                    for site_key in conflicting_sites
                ],
                "site": ":".join([*conflicting_sites[0][0], conflicting_sites[0][2]]),
                "context": display,
            },
        )


def _format_site_summary(site_key: _SiteKey, kinds: set[str]) -> str:
    module_path, _sequence_key, site_label = site_key
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
    typedef_key = moduletype.name.casefold()
    if typedef_key in self._active_typedefs:
        return
    self._active_typedefs.add(typedef_key)
    try:
        context = self._build_typedef_context(moduletype, instance, parent_context, child_path)
        _walk_module_code(self, moduletype.modulecode, context, child_path, accesses)
        _walk_modules(self, moduletype.submodules or [], context, child_path, accesses)
    finally:
        self._active_typedefs.discard(typedef_key)


def _walk_module_code(
    self: Any,
    modulecode: ModuleCode | None,
    context: ScopeContext,
    module_path: list[str],
    accesses: list[_SiteAccess],
) -> None:
    if modulecode is None:
        return
    for equation in modulecode.equationblocks or []:
        label = f"EQ:{getattr(equation, 'name', '<unnamed>')}"
        for statement in equation.code or []:
            _record_statement(self, statement, context, module_path, label, None, None, accesses)
    for sequence_index, sequence in enumerate(modulecode.sequences or []):
        sequence_name = getattr(sequence, "name", "<unnamed>")
        sequence_key = (*module_path, f"SQ:{sequence_index}:{sequence_name}")
        _walk_sequence(self, sequence, context, module_path, sequence_key, accesses)


def _walk_sequence(
    self: Any,
    sequence: Sequence,
    context: ScopeContext,
    module_path: list[str],
    sequence_key: tuple[str, ...],
    accesses: list[_SiteAccess],
) -> None:
    _walk_sequence_nodes(self, sequence.code or [], context, module_path, sequence_key, accesses)


def _walk_sequence_nodes(
    self: Any,
    nodes: SequenceABC[object],
    context: ScopeContext,
    module_path: list[str],
    sequence_key: tuple[str, ...],
    accesses: list[_SiteAccess],
) -> None:
    for index, node in enumerate(nodes):
        if isinstance(node, SFCStep):
            _walk_step(
                self,
                node,
                context,
                module_path,
                sequence_key,
                accesses,
                direct_self_loop=_step_has_direct_self_loop(nodes, index),
            )
            continue
        if isinstance(node, SFCTransition):
            loop_step = _transition_loop_step_name(nodes, index)
            label = None if loop_step is None else f"STEP:{loop_step}:TRANS:{node.name or '<unnamed>'}"
            _record_expression(self, node.condition, context, module_path, label, sequence_key, None, accesses)
            continue
        if isinstance(node, SFCAlternative | SFCParallel):
            for branch in node.branches or []:
                _walk_sequence_nodes(self, branch or [], context, module_path, sequence_key, accesses)
            continue
        if isinstance(node, SFCSubsequence | SFCTransitionSub):
            _walk_sequence_nodes(self, node.body or [], context, module_path, sequence_key, accesses)
            continue


def _walk_step(
    self: Any,
    step: SFCStep,
    context: ScopeContext,
    module_path: list[str],
    sequence_key: tuple[str, ...],
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
            _record_statement(self, statement, context, module_path, label, sequence_key, None, accesses)


def _step_has_direct_self_loop(nodes: SequenceABC[object], index: int) -> bool:
    """Whether an explicit ``SFCFork`` targets this step.

    A terminal step is not a loop: a transition with no fork ends the sequence
    and its ENTER/EXIT code runs once. Only a fork that names the step itself
    makes those phases continuous.
    """
    node = nodes[index]
    if not isinstance(node, SFCStep):
        return False
    step_key = (node.name or "").casefold()
    if isinstance(node.fork, SFCFork) and any(target.casefold() == step_key for target in node.fork.targets):
        return True
    if index + 1 >= len(nodes):
        return False
    next_node = nodes[index + 1]
    if not isinstance(next_node, SFCTransition):
        return False
    if next_node.condition is False:
        return False
    if isinstance(next_node.fork, SFCFork):
        return any(target.casefold() == step_key for target in next_node.fork.targets)
    return False


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
    sequence_key: tuple[str, ...] | None,
    active_sequence: tuple[str, ...] | None,
    accesses: list[_SiteAccess],
) -> None:
    if isinstance(statement, IfStmt):
        for condition, branch_statements in statement.branches:
            _record_expression(
                self, condition, context, module_path, continuous_site, sequence_key, active_sequence, accesses
            )
            branch_active = active_sequence or _active_sequence_from_condition(condition, module_path)
            for branch_statement in branch_statements:
                _record_statement(
                    self, branch_statement, context, module_path, continuous_site, sequence_key, branch_active, accesses
                )
        for else_statement in statement.else_block or ():
            _record_statement(
                self, else_statement, context, module_path, continuous_site, sequence_key, active_sequence, accesses
            )
        return

    if isinstance(statement, Assignment):
        _record_expression(
            self, statement.value, context, module_path, continuous_site, sequence_key, active_sequence, accesses
        )
        _record_ref(
            self,
            statement.target,
            _WRITE,
            context,
            module_path,
            continuous_site,
            sequence_key,
            active_sequence,
            accesses,
        )
        return

    if isinstance(statement, FuncCallStmt):
        args = _sequence_as_list(statement.call.args)
        _record_call_arguments(
            self,
            statement.call.name,
            args,
            context,
            module_path,
            continuous_site,
            sequence_key,
            active_sequence,
            accesses,
        )
        return

    _record_expression(self, statement, context, module_path, continuous_site, sequence_key, active_sequence, accesses)


def _active_sequence_from_condition(
    condition: object,
    module_path: list[str],
) -> tuple[str, ...] | None:
    """Return the operation sequence a ``NOT <Seq>.Reset`` guard activates.

    The marker is qualified by the module path, so two sibling operations that
    both guard on their own ``PhaseSequence.Reset`` produce different markers
    and are treated as mutually exclusive.
    """
    if isinstance(condition, NotOp):
        operand = condition.operand
        if isinstance(operand, VarRef) and operand.name and operand.name.casefold().endswith(".reset"):
            owner = operand.name.rsplit(".", 1)[0]
            if owner:
                return (*module_path, owner.casefold())
    if isinstance(condition, BoolOp) and str(condition.op).upper() == "AND":
        for operand in condition.operands:
            marker = _active_sequence_from_condition(operand, module_path)
            if marker is not None:
                return marker
    return None


def _record_call_arguments(
    self: Any,
    function_name: str | None,
    args: list[Any],
    context: ScopeContext,
    module_path: list[str],
    continuous_site: str | None,
    sequence_key: tuple[str, ...] | None,
    active_sequence: tuple[str, ...] | None,
    accesses: list[_SiteAccess],
) -> None:
    signature = resolve_call_signature(function_name)
    for index, argument in enumerate(args):
        parameter = signature.parameters[index] if signature is not None and index < len(signature.parameters) else None
        if parameter is None or parameter.is_input:
            _record_expression(
                self, argument, context, module_path, continuous_site, sequence_key, active_sequence, accesses
            )
        if parameter is not None and parameter.is_output:
            _record_ref(
                self, argument, _WRITE, context, module_path, continuous_site, sequence_key, active_sequence, accesses
            )


def _record_expression(
    self: Any,
    node: object,
    context: ScopeContext,
    module_path: list[str],
    continuous_site: str | None,
    sequence_key: tuple[str, ...] | None,
    active_sequence: tuple[str, ...] | None,
    accesses: list[_SiteAccess],
) -> None:
    for event in walk(node, prune=lambda current: isinstance(current, FuncCall)):
        current = event.node
        if isinstance(current, FuncCall):
            _record_call_arguments(
                self,
                current.name,
                _sequence_as_list(current.args),
                context,
                module_path,
                continuous_site,
                sequence_key,
                active_sequence,
                accesses,
            )
            continue
        if isinstance(current, VarRef):
            _record_ref(
                self, current, _READ, context, module_path, continuous_site, sequence_key, active_sequence, accesses
            )


def _record_ref(
    self: Any,
    ref: object,
    kind: str,
    context: ScopeContext,
    module_path: list[str],
    continuous_site: str | None,
    sequence_key: tuple[str, ...] | None,
    active_sequence: tuple[str, ...] | None,
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
            symbol_key=resolved.symbol_key,
            symbol_display=display_path,
            decl_module_path=decl_module_path,
            is_state_variable=bool(resolved.is_state_variable),
            continuous_site=continuous_site,
            kind=kind,
            site=continuous_site or "",
            sequence_key=sequence_key,
            active_sequence=active_sequence,
        )
    )


def _ref_full_name(ref: object) -> str | None:
    if isinstance(ref, VarRef):
        return ref.name
    return None


def _decl_path_from_symbol_key(symbol_root_key: tuple[str, ...]) -> tuple[str, ...]:
    return symbol_root_key[:-1]


__all__ = ["collect_non_state_multi_site_issues"]
