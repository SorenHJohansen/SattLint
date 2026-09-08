"""Markdown serialization of a ``ChangeReview``.

Renders the same canonical model the JSON serializer uses, so humans and AI
consumers always see the identical review. The document is organized around
*understanding the consequences* of each change: original source code plus the
semantic facts SattLint already knows (reads, produces, consumers, callers/
callees, sequence/state context). Navigation is by module path; code-file line
numbers are not used.
"""

from __future__ import annotations

from ..facts import SymbolFact
from ..review import ChangeReview
from ..semantic_diff import ChangeChange

_RELEVANT_DEFINITION_ROLES = {"read", "produced"}


def _code_block(source: str | None) -> str:
    if source is None:
        return "_(no source selected)_"
    return "\n```\n" + source.rstrip("\n") + "\n```\n"


def _kind_label(kind: str) -> str:
    return kind.replace("_", " ").capitalize()


def _fact_annotation(fact: SymbolFact) -> str:
    parts: list[str] = []
    if fact.datatype:
        parts.append(f"Type: {fact.datatype}")
    if fact.defined_by:
        parts.append(f"defined by {fact.defined_by}")
    if fact.produced_by:
        parts.append(f"produced by {', '.join(fact.produced_by)}")
    if fact.consumed_by:
        parts.append(f"consumed by {', '.join(fact.consumed_by)}")
    if not parts:
        return ""
    return f" ({'; '.join(parts)})"


def _render_summary(review: ChangeReview) -> list[str]:
    stats = review.size_stats
    added = sum(1 for change in review.changes if change.kind.value == "added")
    removed = sum(1 for change in review.changes if change.kind.value == "removed")
    lines = [
        "## Summary",
        "",
        f"- **Project:** {review.metadata.project}",
        f"- **Official revision:** {review.metadata.official_revision}",
        f"- **Draft revision:** {review.metadata.draft_revision}",
        "",
        f"- **Semantic changes:** {stats.semantic_change_count}",
    ]
    if added or removed:
        lines.append(f"  - Added: {added}, Removed: {removed}")
    lines.extend(
        [
            f"- **Relevant symbols:** {stats.relevant_symbol_count}",
            f"- **Contextual symbols:** {stats.contextual_symbol_count}",
            "",
        ]
    )
    return lines


def _render_semantic_context(change: ChangeChange) -> list[str]:
    context = change.semantic_context
    if context is None:
        return []
    lines: list[str] = ["#### Semantic context", ""]
    if context.containing_object:
        lines.extend([f"**Containing object:** `{context.containing_object}`", ""])
    if context.sequence_name:
        lines.extend([f"**Sequence:** `{context.sequence_name}`", ""])
        if context.previous_state:
            lines.extend([f"**Previous state:** `{context.previous_state}`", ""])
        if context.next_state:
            lines.extend([f"**Next state:** `{context.next_state}`", ""])
        if context.containing_state:
            lines.extend([f"**State:** `{context.containing_state}`", ""])
    for label, facts in (
        ("Reads", context.reads),
        ("Produces", context.produces),
        ("Producers", context.producers),
        ("Consumers", context.consumers),
        ("Callers", context.callers),
        ("Callees", context.callees),
    ):
        if not facts:
            continue
        lines.append(f"**{label}:**")
        lines.append("")
        for fact in facts:
            lines.append(f"- `{fact.symbol}`{_fact_annotation(fact)}")
        lines.append("")
    return lines


def _render_change_entry(review: ChangeReview, change: ChangeChange, number: int) -> list[str]:
    lines = [f"### Change {number} — {change.symbol}", ""]
    lines.append(f"**{_kind_label(change.kind.value)}** — {change.detail}")
    if change.statement_context:
        lines.append("")
        lines.append(f"*Context: {change.statement_context}*")
    if change.containing_symbol:
        lines.append("")
        lines.append(f"*Contained in: `{change.containing_symbol}`*")
    if change.official is not None or change.draft is not None:
        lines.append("")
        if change.official is not None:
            lines.extend(["#### Official", "", _code_block(str(change.official))])
        if change.draft is not None:
            lines.extend(["#### Draft", "", _code_block(str(change.draft))])
    lines.append("")
    lines.extend(_render_semantic_context(change))
    lines.append("---")
    lines.append("")
    return lines


def _render_relevant_definitions(review: ChangeReview) -> list[str]:
    lines: list[str] = []
    definitions = [
        fact for fact in review.relevant_symbols if fact.role in _RELEVANT_DEFINITION_ROLES and fact.kind is not None
    ]
    if not definitions:
        return lines
    lines.extend(["## Relevant Definitions", ""])
    for fact in definitions:
        lines.append(f"### {fact.symbol}")
        lines.append("")
        lines.append(f"Relevant because: {fact.reason}")
        if fact.datatype:
            lines.append("")
            lines.append(f"- **Type:** {fact.datatype}")
        if fact.kind:
            lines.append(f"- **Kind:** {fact.kind}")
        if fact.defined_by:
            lines.append(f"- **Defined by:** `{fact.defined_by}`")
        if fact.produced_by:
            lines.append(f"- **Produced by:** {', '.join(f'`{p}`' for p in fact.produced_by)}")
        if fact.consumed_by:
            lines.append(f"- **Consumed by:** {', '.join(f'`{c}`' for c in fact.consumed_by)}")
        lines.append("")
    return lines


def _render_relevant_code(review: ChangeReview) -> list[str]:
    lines: list[str] = []
    blocks = [block for block in review.context if block.role != "changed"]
    if not blocks:
        return lines
    lines.extend(["## Relevant Code", ""])
    for block in blocks:
        lines.append(f"### {block.symbol} ({block.role})")
        lines.append("")
        if block.reason:
            lines.append(f"Relevant because: {block.reason}")
            lines.append("")
        lines.append(_code_block(block.source))
        lines.append("")
    return lines


def _render_scope(review: ChangeReview) -> list[str]:
    stats = review.size_stats
    return [
        "## Review Scope",
        "",
        f"- **Selected symbols:** {stats.relevant_symbol_count}",
        f"- **Contextual source blocks:** {stats.contextual_symbol_count}",
        f"- **Context reduction:** {stats.reduction_percent}% "
        f"(project {stats.total_project_source_size} bytes -> selected {stats.selected_context_size} bytes)",
        "",
    ]


def review_to_markdown(review: ChangeReview) -> str:
    """Render the review as a self-contained Markdown document."""
    lines: list[str] = ["# SattLint Change Review", ""]
    lines.extend(_render_summary(review))
    lines.extend(["## Changes", ""])
    for number, change in enumerate(review.changes, start=1):
        lines.extend(_render_change_entry(review, change, number))
    lines.extend(_render_relevant_definitions(review))
    lines.extend(_render_relevant_code(review))
    lines.extend(_render_scope(review))
    return "\n".join(lines).rstrip() + "\n"
