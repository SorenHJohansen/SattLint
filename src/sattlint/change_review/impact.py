"""Semantic relevance analysis: which facts a reviewer needs for each change.

Unlike a blind dependency-hop traversal, relevance is determined by the
*semantic role* of each entity in understanding the change. Every contextual
entity carries an explicit reason and priority; the result is ranked and capped
by a context-size budget so the review never grows to the size of the project.

The semantic relationships used here all come from the existing snapshot and
code model: referenced/produced definition keys, the consumer index (who
references a symbol), the producer index (who assigns a symbol), call
signatures (callers/callees), and the module/S88 parent chain.
"""

from __future__ import annotations

from ..core._semantic_snapshot import SymbolDefinition
from .facts import (
    PRIORITY_CALLEE,
    PRIORITY_CALLER,
    PRIORITY_CHANGED,
    PRIORITY_CONSUMER,
    PRIORITY_PRODUCED,
    PRIORITY_PRODUCER,
    PRIORITY_REFERENCED,
    PRIORITY_S88,
    ChangeSemanticContext,
    RelevanceResult,
    SymbolFact,
)
from .loader import VersionSnapshot
from .semantic_diff import ChangeChange

DEFAULT_MAX_SYMBOLS = 60


def _module_symbol(module_path: tuple[str, ...]) -> str:
    return ".".join(module_path)


def _key_to_definition(snapshot: VersionSnapshot) -> dict[tuple[str, ...], SymbolDefinition]:
    return {
        tuple(segment.casefold() for segment in definition.canonical_path.split(".")): definition
        for definition in snapshot.snapshot.definitions
    }


def _dedupe_facts(facts: list[SymbolFact]) -> tuple[SymbolFact, ...]:
    seen: set[str] = set()
    unique: list[SymbolFact] = []
    for fact in facts:
        key = fact.symbol.casefold()
        if key in seen:
            continue
        seen.add(key)
        unique.append(fact)
    return tuple(unique)


class _RelevanceBuilder:
    def __init__(self, official: VersionSnapshot, draft: VersionSnapshot):
        self._official = official
        self._draft = draft
        self._key_to_def = {**_key_to_definition(official), **_key_to_definition(draft)}
        self._consumers: dict[tuple[str, ...], tuple[tuple[str, ...], ...]] = {}
        self._producers: dict[tuple[str, ...], tuple[tuple[str, ...], ...]] = {}
        for version in (official, draft):
            self._consumers.update(version.code_model.consumers_by_key)
            self._producers.update(version.code_model.producers_by_key)
        self._registry: dict[str, SymbolFact] = {}

    def _register(self, fact: SymbolFact) -> None:
        key = fact.symbol.casefold()
        existing = self._registry.get(key)
        if existing is None:
            self._registry[key] = fact
            return
        if fact.priority < existing.priority:
            return
        merged_produced = tuple(dict.fromkeys((*existing.produced_by, *fact.produced_by)))
        merged_consumed = tuple(dict.fromkeys((*existing.consumed_by, *fact.consumed_by)))
        self._registry[key] = SymbolFact(
            symbol=fact.symbol,
            name=fact.name,
            role=fact.role if fact.priority > existing.priority else existing.role,
            reason=fact.reason if fact.priority >= existing.priority else existing.reason,
            priority=fact.priority,
            kind=fact.kind or existing.kind,
            datatype=fact.datatype or existing.datatype,
            defined_by=fact.defined_by or existing.defined_by,
            produced_by=merged_produced,
            consumed_by=merged_consumed,
            containing_object=fact.containing_object or existing.containing_object,
        )

    def _fact_for_key(
        self,
        key: tuple[str, ...],
        *,
        role: str,
        reason: str,
        priority: int,
    ) -> SymbolFact:
        definition = self._key_to_def.get(key)
        symbol = definition.canonical_path if definition is not None else ".".join(key)
        return SymbolFact(
            symbol=symbol,
            name=symbol.split(".")[-1],
            role=role,
            reason=reason,
            priority=priority,
            kind=definition.kind if definition is not None else None,
            datatype=definition.datatype if definition is not None else None,
            defined_by=".".join(definition.declaration_module_path) if definition is not None else None,
            produced_by=tuple(_module_symbol(path) for path in self._producers.get(key, ())),
            consumed_by=tuple(_module_symbol(path) for path in self._consumers.get(key, ())),
        )

    def _module_consumers_of(self, key: tuple[str, ...], label: str) -> tuple[SymbolFact, ...]:
        owners = self._consumers.get(key, ())
        return tuple(
            SymbolFact(
                symbol=_module_symbol(path),
                name=_module_symbol(path),
                role="consumer",
                reason=f"Consumes {label}",
                priority=PRIORITY_CONSUMER,
            )
            for path in sorted(owners)
        )

    def _module_producers_of(self, key: tuple[str, ...], label: str) -> tuple[SymbolFact, ...]:
        producers = self._producers.get(key, ())
        return tuple(
            SymbolFact(
                symbol=_module_symbol(path),
                name=_module_symbol(path),
                role="producer",
                reason=f"Produces {label}",
                priority=PRIORITY_PRODUCER,
            )
            for path in sorted(producers)
        )

    def _callees_for(self, module_path: tuple[str, ...]) -> tuple[SymbolFact, ...]:
        names: set[str] = set()
        for version in (self._official, self._draft):
            for occurrence in version.snapshot.call_signatures:
                if tuple(occurrence.module_path) == module_path:
                    names.add(occurrence.name)
        module_symbol = _module_symbol(module_path)
        return tuple(
            SymbolFact(
                symbol=name,
                name=name,
                role="callee",
                reason=f"Called by {module_symbol}",
                priority=PRIORITY_CALLEE,
                kind="call",
            )
            for name in sorted(names)
        )

    def _callers_for(self, change: ChangeChange) -> tuple[SymbolFact, ...]:
        target_name = change.module_path[-1].casefold()
        callers: set[str] = set()
        for version in (self._official, self._draft):
            for occurrence in version.snapshot.call_signatures:
                if occurrence.name.casefold() == target_name:
                    callers.add(_module_symbol(tuple(occurrence.module_path)))
        return tuple(
            SymbolFact(
                symbol=caller,
                name=caller,
                role="caller",
                reason=f"Calls {change.symbol}",
                priority=PRIORITY_CALLER,
            )
            for caller in sorted(callers)
        )

    def _s88_parents(self, change: ChangeChange) -> tuple[SymbolFact, ...]:
        return tuple(
            SymbolFact(
                symbol=_module_symbol(change.module_path[:length]),
                name=_module_symbol(change.module_path[:length]),
                role="s88",
                reason="Contains changed code",
                priority=PRIORITY_S88,
            )
            for length in range(len(change.module_path) - 1, 0, -1)
        )

    def _context_for_change(self, change: ChangeChange) -> ChangeSemanticContext:
        module_symbol = _module_symbol(change.module_path)
        reads: list[SymbolFact] = []
        produces: list[SymbolFact] = []
        producers: list[SymbolFact] = []
        consumers: list[SymbolFact] = []

        for key in change.read_keys:
            fact = self._fact_for_key(
                key,
                role="read",
                reason=f"Referenced by changed code in {module_symbol}",
                priority=PRIORITY_REFERENCED,
            )
            reads.append(fact)
            self._register(fact)
            for producer in self._module_producers_of(key, fact.symbol):
                producers.append(producer)
                self._register(producer)

        for key in change.produced_keys:
            fact = self._fact_for_key(
                key,
                role="produced",
                reason=f"Produced by changed code in {module_symbol}",
                priority=PRIORITY_PRODUCED,
            )
            produces.append(fact)
            self._register(fact)
            for consumer in self._module_consumers_of(key, fact.symbol):
                consumers.append(consumer)
                self._register(consumer)

        callees = self._callees_for(change.module_path)
        callers = self._callers_for(change)
        for fact in (*callees, *callers):
            self._register(fact)

        return ChangeSemanticContext(
            reads=_dedupe_facts(reads),
            produces=_dedupe_facts(produces),
            producers=_dedupe_facts(producers),
            consumers=_dedupe_facts(consumers),
            callers=callers,
            callees=callees,
            containing_object=module_symbol,
            sequence_name=change.sequence_name,
            previous_state=change.previous_state,
            next_state=change.next_state,
            containing_state=change.containing_state,
        )

    def build(self, changes: list[ChangeChange], *, max_symbols: int) -> RelevanceResult:
        change_contexts: list[tuple[int, ChangeSemanticContext]] = []
        for index, change in enumerate(changes):
            context = self._context_for_change(change)
            if context != ChangeSemanticContext():
                change_contexts.append((index, context))
            self._register(
                SymbolFact(
                    symbol=change.symbol,
                    name=change.symbol,
                    role="changed",
                    reason="Directly changed",
                    priority=PRIORITY_CHANGED,
                    containing_object=_module_symbol(change.module_path),
                )
            )
            for parent in self._s88_parents(change):
                self._register(parent)

        ranked = sorted(self._registry.values(), key=lambda fact: (-fact.priority, fact.symbol.casefold()))
        return RelevanceResult(
            change_contexts=tuple(change_contexts),
            relevant_symbols=tuple(ranked[:max_symbols]),
        )


def compute_relevance(
    official: VersionSnapshot,
    draft: VersionSnapshot,
    changes: list[ChangeChange],
    *,
    max_symbols: int = DEFAULT_MAX_SYMBOLS,
) -> RelevanceResult:
    """Rank the semantic context needed to understand the given changes."""
    return _RelevanceBuilder(official, draft).build(changes, max_symbols=max_symbols)
