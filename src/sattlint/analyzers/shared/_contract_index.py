"""Immutable, snapshot-scoped contract summaries for ModuleTypeDef definitions.

A :class:`ModuleTypeContract` is a purely symbolic, per-parameter summary of how a
typedef's body uses each of its module parameters (read / ui-read / non-ui-read /
written, plus the relative field paths touched). It is derived once per resolved
``ModuleTypeDef`` definition and is independent of any particular instantiation
module path, scope context, or issue pipeline. Derived facts -- required parameter
names, ``param_reads_by_typedef``, UI / non-UI read sets, write sets, and ANYTYPE
field contracts -- are read back from this single representation.

Caching is keyed by the resolved definition identity (``id(owner)``), never by a
lowercased typename, because resolution depends on the originating library and two
libraries can otherwise be conflated. To keep ``id(owner)`` valid for the lifetime
of the index, each :class:`ContractEntry` holds a strong reference to its owner node.

The index is deeply immutable: both the per-owner mapping and each owner's parameter
mapping are published through :class:`MappingProxyType` so callers cannot mutate the
stored summaries.

Scope / lifecycle
-----------------
The index lives in :class:`AnalysisSharedArtifacts` and is scoped to one AST /
resolution snapshot generation. It is built at most once per :class:`ContractIndexKey`
(which encodes the analysis-policy inputs that can change the symbolic result) and is
never shared across snapshots or processes (``id`` keys are process-local).

For the initial parity implementation the summaries are harvested from the existing
walker via a single issue-suppressed provider instance in the ``variables`` package.
Self-recursive and mutually recursive components are routed to the legacy per-typedef
extraction path so their summaries are never frozen from an incomplete fixed point
(see ``cyclic_owner_ids`` and :func:`compute_cyclic_owner_ids`).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType

from sattline_parser.models.ast_model import (
    BasePicture,
    ModuleTypeDef,
    ModuleTypeInstance,
    Variable,
)

from ...models.usage import VariableUsage
from ...resolution.common import resolve_moduletype_def_strict
from ...utils.casefolding import casefold_key
from ._walk_utils import iter_nested_modules


@dataclass(frozen=True, slots=True)
class ParameterEffect:
    """Symbolic, definition-level usage of a single module parameter.

    ``field_reads`` / ``field_writes`` hold dotted field-path *strings* (e.g.
    ``"Inner.Value"``) matching the walker's ``VariableUsage.field_*`` keys, so ANYTYPE
    field-contract extraction preserves the current spelling exactly.
    """

    read: bool
    ui_read: bool
    non_ui_read: bool
    written: bool
    field_reads: frozenset[str]
    field_writes: frozenset[str]

    @property
    def is_unused(self) -> bool:
        return not (self.read or self.written)

    @property
    def is_display_only(self) -> bool:
        return self.ui_read and not self.non_ui_read

    @property
    def required(self) -> bool:
        return self.read or self.written


@dataclass(frozen=True, slots=True)
class ModuleTypeContract:
    """Per-parameter effect summary for one resolved ModuleTypeDef definition.

    ``effects_by_parameter`` is keyed by casefolded parameter name and is published
    through a :class:`MappingProxyType` so the stored summary is immutable.
    """

    effects_by_parameter: Mapping[str, ParameterEffect]

    def effect(self, parameter_name: str) -> ParameterEffect | None:
        return self.effects_by_parameter.get(casefold_key(parameter_name))


@dataclass(frozen=True, slots=True)
class ContractIndexKey:
    """Keys one immutable contract index on every policy input that can change its result."""

    unavailable_libraries: frozenset[str]
    analyzed_target_is_library: bool
    include_dependency_moduletype_usage: bool
    semantics_flavor: str
    schema_version: int = 1


@dataclass(frozen=True, slots=True)
class ContractEntry:
    """One resolved typedef's contract, holding a strong owner reference.

    The strong ``owner`` reference prevents the ``id(owner)`` from being recycled by
    the allocator while the entry is alive, which would make the identity key invalid
    or -- worse -- point at an unrelated object.
    """

    owner: ModuleTypeDef
    contract: ModuleTypeContract


@dataclass(frozen=True, slots=True)
class ContractIndex:
    """A deeply immutable, snapshot-scoped collection of contract summaries.

    ``entries_by_owner_id`` is keyed by ``id(owner)`` and published through a
    :class:`MappingProxyType`. ``cyclic_owner_ids`` records the resolved identities of
    typedefs that are part of a recursive component and were routed through the legacy
    extraction path.
    """

    snapshot_generation: int
    entries_by_owner_id: Mapping[int, ContractEntry]
    cyclic_owner_ids: frozenset[int]

    def get(self, owner: ModuleTypeDef) -> ModuleTypeContract | None:
        entry = self.entries_by_owner_id.get(id(owner))
        if entry is None or entry.owner is not owner:
            return None
        return entry.contract

    def get_effect(self, owner: ModuleTypeDef, parameter_name: str) -> ParameterEffect | None:
        contract = self.get(owner)
        if contract is None:
            return None
        return contract.effect(parameter_name)

    def required_parameter_names(self, owner: ModuleTypeDef) -> dict[str, str]:
        """Return ``{casefolded_name: original_name}`` for parameters that need connecting.

        Original spelling is recovered from the owner typedef's own parameter list, so
        the derived mapping is not stored redundantly on the frozen effects.
        """
        contract = self.get(owner)
        if contract is None:
            return {}
        original_by_key: dict[str, str] = {}
        for parameter in owner.moduleparameters or []:
            original_by_key.setdefault(casefold_key(parameter.name), parameter.name)
        required: dict[str, str] = {}
        for key, effect in contract.effects_by_parameter.items():
            if effect.required:
                required[key] = original_by_key.get(key, key)
        return required


def _freeze_entries(
    entries: Mapping[int, ContractEntry],
) -> Mapping[int, ContractEntry]:
    return MappingProxyType(dict(entries))


def build_contract_index(
    *,
    snapshot_generation: int,
    entries_by_owner_id: Mapping[int, ContractEntry],
    cyclic_owner_ids: frozenset[int],
) -> ContractIndex:
    """Assemble a deeply immutable :class:`ContractIndex` from mutable build inputs."""
    return ContractIndex(
        snapshot_generation=snapshot_generation,
        entries_by_owner_id=_freeze_entries(entries_by_owner_id),
        cyclic_owner_ids=frozenset(cyclic_owner_ids),
    )


def project_parameter_effect(
    variable: Variable,
    usage: VariableUsage,
) -> ParameterEffect:
    """Project a :class:`ParameterEffect` from a walker's :class:`VariableUsage`.

    Stateless projection: ``ui_read`` / ``non_ui_read`` / ``written`` / ``field_*``
    flags are derived purely from the usage object. Field paths keep their original
    spelling (each entry is a dotted path string); deterministic ordering is applied
    by callers when deriving ANYTYPE or diagnostic sets.
    """
    reads: frozenset[str] = frozenset(usage.field_reads or {})
    writes: frozenset[str] = frozenset(usage.field_writes or {})
    return ParameterEffect(
        read=bool(usage.read),
        ui_read=bool(usage.ui_read),
        non_ui_read=bool(usage.non_ui_read),
        written=bool(usage.written),
        field_reads=reads,
        field_writes=writes,
    )


def _iter_instances_in_subtree(
    root: ModuleTypeDef,
) -> Iterable[tuple[ModuleTypeInstance, list[str]]]:
    """Yield every ModuleTypeInstance leaf within a typedef's own physical subtree.

    Does not descend into referenced typedef bodies (``iter_nested_modules`` without a
    resolver only walks the physical submodule tree, and ``ModuleTypeInstance`` is a
    physical leaf).
    """
    for module, module_path in iter_nested_modules(root.submodules or [], parent_path=[]):
        if isinstance(module, ModuleTypeInstance):
            yield module, module_path


def _build_typedef_index(
    typedefs: Sequence[ModuleTypeDef],
) -> dict[str, list[ModuleTypeDef]]:
    index: dict[str, list[ModuleTypeDef]] = {}
    for typedef in typedefs:
        index.setdefault(casefold_key(typedef.name), []).append(typedef)
    return index


def _resolve_child(
    bp: BasePicture,
    instance: ModuleTypeInstance,
    owner: ModuleTypeDef,
    *,
    index: dict[str, list[ModuleTypeDef]],
    unavailable_libraries: frozenset[str] | None,
) -> ModuleTypeDef | None:
    try:
        return resolve_moduletype_def_strict(
            bp,
            instance.moduletype_name,
            current_library=owner.origin_lib,
            current_file=owner.origin_file,
            unavailable_libraries=set(unavailable_libraries or frozenset()),
            moduletype_index=index,
        )
    except ValueError:
        return None


def compute_cyclic_owner_ids(
    bp: BasePicture,
    typedefs: Sequence[ModuleTypeDef],
    *,
    unavailable_libraries: frozenset[str] | None = None,
) -> frozenset[int]:
    """Return owner identities belonging to a recursive component (size > 1 SCC or self edge).

    These typedefs are routed through the legacy extraction path in Step 1, because a
    walker-based summary of a recursive component could otherwise be frozen from an
    incomplete fixed point (the current ``{}`` in-progress placeholder in the legacy
    required-parameter extraction).
    """
    if not typedefs:
        return frozenset()

    index = _build_typedef_index(typedefs)
    adjacency: dict[int, set[int]] = {id(t): set() for t in typedefs}
    for owner in typedefs:
        for instance, _path in _iter_instances_in_subtree(owner):
            child = _resolve_child(
                bp,
                instance,
                owner,
                index=index,
                unavailable_libraries=unavailable_libraries,
            )
            if child is not None:
                adjacency[id(owner)].add(id(child))

    if not adjacency:
        return frozenset()

    index_counter = 0
    stack: list[int] = []
    on_stack: set[int] = set()
    lowlink: dict[int, int] = {}
    index_map: dict[int, int] = {}
    components: list[set[int]] = []

    def strongconnect(vertex: int) -> None:
        nonlocal index_counter
        index_map[vertex] = index_counter
        lowlink[vertex] = index_counter
        index_counter += 1
        stack.append(vertex)
        on_stack.add(vertex)

        for successor in adjacency.get(vertex, ()):
            if successor not in index_map:
                strongconnect(successor)
                lowlink[vertex] = min(lowlink[vertex], lowlink[successor])
            elif successor in on_stack:
                lowlink[vertex] = min(lowlink[vertex], index_map[successor])

        if lowlink[vertex] == index_map[vertex]:
            component: set[int] = set()
            while True:
                member = stack.pop()
                on_stack.discard(member)
                component.add(member)
                if member == vertex:
                    break
            components.append(component)

    for vertex in adjacency:
        if vertex not in index_map:
            strongconnect(vertex)

    cyclic: set[int] = set()
    for component in components:
        if len(component) > 1:
            cyclic.update(component)
            continue
        (only,) = component
        if only in adjacency.get(only, ()):
            cyclic.add(only)
    return frozenset(cyclic)


__all__ = [
    "ContractEntry",
    "ContractIndex",
    "ContractIndexKey",
    "ModuleTypeContract",
    "ParameterEffect",
    "build_contract_index",
    "compute_cyclic_owner_ids",
    "project_parameter_effect",
]
