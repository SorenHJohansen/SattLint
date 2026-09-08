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
PRIORITY_CONTAINING = 60


@dataclass(frozen=True)
class SymbolFact:
    """A semantic fact about one relevant symbol/module and why it was selected."""

    symbol: str
    name: str
    role: str
    reason: str
    priority: int
    kind: str | None = None
    datatype: str | None = None
    defined_by: str | None = None
    produced_by: tuple[str, ...] = ()
    consumed_by: tuple[str, ...] = ()
    containing_object: str | None = None


@dataclass(frozen=True)
class ChangeSemanticContext:
    """The semantic context surrounding one code change."""

    reads: tuple[SymbolFact, ...] = ()
    produces: tuple[SymbolFact, ...] = ()
    producers: tuple[SymbolFact, ...] = ()
    consumers: tuple[SymbolFact, ...] = ()
    callers: tuple[SymbolFact, ...] = ()
    callees: tuple[SymbolFact, ...] = ()
    containing_object: str | None = None
    sequence_name: str | None = None
    previous_state: str | None = None
    next_state: str | None = None
    containing_state: str | None = None


@dataclass(frozen=True)
class RelevanceResult:
    """Ranked semantic context for all changes in a review."""

    change_contexts: tuple[tuple[int, ChangeSemanticContext], ...]
    relevant_symbols: tuple[SymbolFact, ...]
