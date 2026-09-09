"""Shared semantic-fact model for the Change Review.

These types are the canonical representation of *why* context was selected and
what SattLint already knows about each relevant symbol. They are imported by
the semantic diff (per-change context), the relevance analysis, and the review
model, so there is a single source of truth for semantic facts.
"""

from __future__ import annotations

from dataclasses import dataclass

PRIORITY_CHANGED = 100
PRIORITY_REFERENCED = 90
PRIORITY_PRODUCED = 90
PRIORITY_CONSUMER = 85
PRIORITY_PRODUCER = 85
PRIORITY_CALLEE = 80
PRIORITY_CALLER = 80
PRIORITY_S88 = 70
PRIORITY_DEPENDENCY = 60
PRIORITY_CONTAINING = 60


@dataclass(frozen=True)
class SymbolFact:
    """A semantic fact about one relevant symbol and why it was selected.

    Relationship terminology is precise and limited to what the semantic model
    actually knows:

    - ``declared_by``   — the module that declares the variable
    - ``written_by``    — the exact blocks/sequences that assign the variable
    - ``read_by``       — the exact blocks/sequences that read the variable
    - ``declaration_source`` — the variable's declaration line(s)
    - ``definition_source``  — the statement that assigns/defines the value
    """

    symbol: str
    name: str
    role: str
    reason: str
    priority: int
    kind: str | None = None
    datatype: str | None = None
    declared_by: str | None = None
    written_by: tuple[str, ...] = ()
    read_by: tuple[str, ...] = ()
    containing_object: str | None = None
    declaration_source: str | None = None
    official_definition_source: str | None = None
    draft_definition_source: str | None = None


@dataclass(frozen=True)
class BlockContext:
    """One complete equation block or sequence selected as review context."""

    module_path: tuple[str, ...]
    kind: str  # "equation" | "sequence"
    name: str
    role: str  # "changed" | "related"
    reasons: tuple[str, ...]
    reads: tuple[str, ...]
    writes: tuple[str, ...]
    sequence_name: str | None = None
    previous_state: str | None = None
    next_state: str | None = None

    @property
    def symbol(self) -> str:
        module = ".".join(self.module_path)
        return f"{module} ({self.kind} {self.name})"


@dataclass(frozen=True)
class ChangeSemanticContext:
    """The semantic context surrounding one code change."""

    reads: tuple[SymbolFact, ...] = ()
    produces: tuple[SymbolFact, ...] = ()
    callers: tuple[SymbolFact, ...] = ()
    callees: tuple[SymbolFact, ...] = ()
    containing_object: str | None = None
    sequence_name: str | None = None
    previous_state: str | None = None
    next_state: str | None = None
    containing_state: str | None = None
    block_kind: str | None = None
    block_name: str | None = None
    containing_block: BlockContext | None = None
    related_blocks: tuple[BlockContext, ...] = ()


@dataclass(frozen=True)
class RelevanceResult:
    """Ranked semantic context for all changes in a review.

    ``change_contexts`` maps each change index to its per-change context;
    ``relevant_blocks`` are the complete equation blocks/sequences selected
    (deduplicated across changes, with all reasons); ``relevant_variables`` are
    the definitions of every variable touched by the selected blocks.
    """

    change_contexts: tuple[tuple[int, ChangeSemanticContext], ...]
    relevant_blocks: tuple[BlockContext, ...]
    relevant_variables: tuple[SymbolFact, ...]
