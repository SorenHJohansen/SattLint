"""Semantic relevance analysis: block-centric context selection.

Equation blocks and sequences are the primary units of behavioural context.
For each change the algorithm selects, bounded to one expansion level:

1. the variables directly read/written by the changed statement/expression,
2. the complete containing equation block or sequence,
3. every other equation block/sequence that reads or writes any directly
   involved variable,
4. the definitions of all variables used by the selected blocks,
5. deduplicated across changes.

Direct reads/writes come from the changed statement itself (scope-resolved
against the module that declares the code). Variables used by selected blocks
are broader context, never reported as direct reads/writes. All relationships
come from the existing semantic code model — no text searches.
"""

from __future__ import annotations

from ..core._semantic_snapshot import SymbolDefinition
from ._code_model import BlockModel
from .facts import (
    PRIORITY_CALLEE,
    PRIORITY_DEPENDENCY,
    PRIORITY_REFERENCED,
    BlockContext,
    ChangeSemanticContext,
    RelevanceResult,
    SymbolFact,
)
from .loader import VersionSnapshot
from .semantic_diff import ChangeChange

_BlockIdentity = tuple[tuple[str, ...], str, str]


def _module_symbol(module_path: tuple[str, ...]) -> str:
    return ".".join(module_path)


def _block_symbol(block: BlockModel) -> str:
    return f"{_module_symbol(block.module_path)} ({block.kind} {block.name})"


def _key_to_definition(snapshot: VersionSnapshot) -> dict[tuple[str, ...], SymbolDefinition]:
    return {
        tuple(segment.casefold() for segment in definition.canonical_path.split(".")): definition
        for definition in snapshot.snapshot.definitions
    }


def _touch_reason(block: BlockModel, key: tuple[str, ...], symbol: str) -> str | None:
    reads = key in block.reads_keys
    writes = key in block.writes_keys
    if reads and writes:
        return f"Reads and writes {symbol}"
    if writes:
        return f"Writes {symbol}"
    if reads:
        return f"Reads {symbol}"
    return None


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


def _dedupe_blocks(blocks: list[BlockContext]) -> tuple[BlockContext, ...]:
    seen: set[tuple[tuple[str, ...], str, str]] = set()
    unique: list[BlockContext] = []
    for block in blocks:
        key = (block.module_path, block.kind, block.name)
        if key in seen:
            continue
        seen.add(key)
        unique.append(block)
    return tuple(unique)


class _RelevanceBuilder:
    def __init__(self, official: VersionSnapshot, draft: VersionSnapshot):
        self._official = official
        self._draft = draft
        self._key_to_def = {**_key_to_definition(official), **_key_to_definition(draft)}
        self._read_sites: dict[tuple[str, ...], set[str]] = {}
        self._write_sites: dict[tuple[str, ...], set[str]] = {}
        self._blocks: dict[_BlockIdentity, BlockModel] = {}
        self._blocks_touching: dict[tuple[str, ...], set[_BlockIdentity]] = {}
        self._module_code_source: dict[tuple[str, ...], int] = {}
        for version in (official, draft):
            self._blocks.update(version.code_model.blocks_by_key)
            for key, identities in version.code_model.blocks_touching_key.items():
                self._blocks_touching.setdefault(key, set()).update(identities)
            for path, module in version.code_model.modules_by_path.items():
                self._module_code_source.setdefault(path, module.code_source_id)
            for block in version.code_model.blocks_by_key.values():
                for key in block.reads_keys:
                    self._read_sites.setdefault(key, set()).add(_block_symbol(block))
                for key in block.writes_keys:
                    self._write_sites.setdefault(key, set()).add(_block_symbol(block))
        self._block_registry: dict[tuple[int, str, str], BlockContext] = {}
        self._variable_registry: dict[str, SymbolFact] = {}

    def _symbol_for_key(self, key: tuple[str, ...]) -> str:
        definition = self._key_to_def.get(key)
        return definition.canonical_path if definition is not None else ".".join(key)

    def _register_variable(self, fact: SymbolFact) -> None:
        key = fact.symbol.casefold()
        existing = self._variable_registry.get(key)
        if existing is None:
            self._variable_registry[key] = fact
            return
        merged = SymbolFact(
            symbol=existing.symbol,
            name=existing.name,
            role=fact.role if fact.priority > existing.priority else existing.role,
            reason=_merge_reasons(existing.reason, fact.reason),
            priority=max(existing.priority, fact.priority),
            kind=fact.kind or existing.kind,
            datatype=fact.datatype or existing.datatype,
            declared_by=fact.declared_by or existing.declared_by,
            written_by=tuple(dict.fromkeys((*existing.written_by, *fact.written_by))),
            read_by=tuple(dict.fromkeys((*existing.read_by, *fact.read_by))),
            containing_object=fact.containing_object or existing.containing_object,
            declaration_source=fact.declaration_source or existing.declaration_source,
            official_definition_source=(fact.official_definition_source or existing.official_definition_source),
            draft_definition_source=fact.draft_definition_source or existing.draft_definition_source,
        )
        self._variable_registry[key] = merged

    def _fact_for_key(
        self,
        key: tuple[str, ...],
        *,
        role: str,
        reason: str,
        priority: int,
    ) -> SymbolFact:
        definition = self._key_to_def.get(key)
        symbol = self._symbol_for_key(key)
        return SymbolFact(
            symbol=symbol,
            name=symbol.split(".")[-1],
            role=role,
            reason=reason,
            priority=priority,
            kind=definition.kind if definition is not None else None,
            datatype=definition.datatype if definition is not None else None,
            declared_by=".".join(definition.declaration_module_path) if definition is not None else None,
            written_by=tuple(sorted(self._write_sites.get(key, ()))),
            read_by=tuple(sorted(self._read_sites.get(key, ()))),
        )

    def _register_block(self, block: BlockModel, *, role: str, reasons: tuple[str, ...]) -> None:
        code_source = self._module_code_source.get(block.module_path, -1)
        dedupe_key = (code_source, block.kind, block.name)
        existing = self._block_registry.get(dedupe_key)
        merged_reasons = tuple(dict.fromkeys((*(existing.reasons if existing else ()), *reasons)))
        context = BlockContext(
            module_path=block.module_path,
            kind=block.kind,
            name=block.name,
            role=existing.role if existing is not None and existing.role == "changed" else role,
            reasons=merged_reasons,
            reads=tuple(self._symbol_for_key(key) for key in sorted(block.reads_keys)),
            writes=tuple(self._symbol_for_key(key) for key in sorted(block.writes_keys)),
            sequence_name=block.name if block.kind == "sequence" else None,
        )
        self._block_registry[dedupe_key] = context

    def _block_context(self, block: BlockModel, *, role: str, reasons: tuple[str, ...]) -> BlockContext:
        self._register_block(block, role=role, reasons=reasons)
        code_source = self._module_code_source.get(block.module_path, -1)
        return self._block_registry[(code_source, block.kind, block.name)]

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

    def _context_for_change(self, change: ChangeChange, change_number: int) -> ChangeSemanticContext:
        module_symbol = _module_symbol(change.module_path)
        reads: list[SymbolFact] = []
        produces: list[SymbolFact] = []
        relevant_keys = {*change.read_keys, *change.produced_keys}

        for key in change.read_keys:
            fact = self._fact_for_key(
                key,
                role="read",
                reason=f"Directly read by Change {change_number}",
                priority=PRIORITY_REFERENCED,
            )
            reads.append(fact)
            self._register_variable(fact)

        for key in change.produced_keys:
            fact = self._fact_for_key(
                key,
                role="produced",
                reason=f"Directly written by Change {change_number}",
                priority=PRIORITY_REFERENCED,
            )
            produces.append(fact)
            self._register_variable(fact)

        callees = self._callees_for(change.module_path)
        for fact in callees:
            self._register_variable(fact)

        containing_block: BlockContext | None = None
        related_blocks: list[BlockContext] = []
        if change.block_kind is not None and change.block_name is not None:
            containing_identity = (change.module_path, change.block_kind, change.block_name)
            containing = self._blocks.get(containing_identity)
            if containing is not None:
                containing_block = self._block_context(
                    containing,
                    role="changed",
                    reasons=(f"Contains Change {change_number}",),
                )
            for key in sorted(relevant_keys):
                symbol = self._symbol_for_key(key)
                for identity in self._blocks_touching.get(key, ()):
                    if identity == containing_identity:
                        continue
                    block = self._blocks.get(identity)
                    if block is None:
                        continue
                    reason = _touch_reason(block, key, symbol)
                    if reason is None:
                        continue
                    related_blocks.append(self._block_context(block, role="related", reasons=(reason,)))

        return ChangeSemanticContext(
            reads=_dedupe_facts(reads),
            produces=_dedupe_facts(produces),
            callees=callees,
            containing_object=module_symbol,
            sequence_name=change.sequence_name,
            previous_state=change.previous_state,
            next_state=change.next_state,
            containing_state=change.containing_state,
            block_kind=change.block_kind,
            block_name=change.block_name,
            containing_block=containing_block,
            related_blocks=_dedupe_blocks(related_blocks),
        )

    def _register_variables_for_blocks(self) -> None:
        for block in self._block_registry.values():
            block_model = self._blocks.get((block.module_path, block.kind, block.name))
            if block_model is None:
                continue
            for key in (*block_model.reads_keys, *block_model.writes_keys):
                symbol = self._symbol_for_key(key)
                if symbol.casefold() in self._variable_registry:
                    continue
                self._register_variable(
                    self._fact_for_key(
                        key,
                        role="dependency",
                        reason=self._dependency_reason(block_model, key),
                        priority=PRIORITY_DEPENDENCY,
                    )
                )

    @staticmethod
    def _dependency_reason(block: BlockModel, key: tuple[str, ...]) -> str:
        writes = key in block.writes_keys
        reads = key in block.reads_keys
        site = f"selected block `{_block_symbol(block)}`"
        if writes and reads:
            return f"Read and written by {site}"
        if writes:
            return f"Written by {site}"
        if reads:
            return f"Read by {site}"
        return f"Used by {site}"

    def build(self, changes: list[ChangeChange]) -> RelevanceResult:
        change_contexts: list[tuple[int, ChangeSemanticContext]] = []
        for index, change in enumerate(changes, start=1):
            context = self._context_for_change(change, index)
            if context != ChangeSemanticContext():
                change_contexts.append((index - 1, context))
        self._register_variables_for_blocks()

        relevant_blocks = sorted(
            self._block_registry.values(),
            key=lambda block: (
                0 if block.role == "changed" else 1,
                ".".join(block.module_path).casefold(),
                block.kind,
                block.name.casefold(),
            ),
        )
        relevant_variables = sorted(
            self._variable_registry.values(),
            key=lambda fact: (-fact.priority, fact.symbol.casefold()),
        )
        return RelevanceResult(
            change_contexts=tuple(change_contexts),
            relevant_blocks=tuple(relevant_blocks),
            relevant_variables=tuple(relevant_variables),
        )


def _merge_reasons(existing: str, new: str) -> str:
    parts = [part for part in (*existing.split("; "), new) if part]
    seen: set[str] = set()
    merged: list[str] = []
    for part in parts:
        if part in seen:
            continue
        seen.add(part)
        merged.append(part)
    return "; ".join(merged)


def compute_relevance(
    official: VersionSnapshot,
    draft: VersionSnapshot,
    changes: list[ChangeChange],
) -> RelevanceResult:
    """Select the block-level context needed to understand the given changes."""
    return _RelevanceBuilder(official, draft).build(changes)
