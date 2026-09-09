"""Markdown serialization of a ``ChangeReview``.

The document preserves the information hierarchy of the review:

    changed code
      → containing block/sequence
      → related blocks/sequences
      → relevant variables
      → definitions/metadata

Direct reads/writes are only what the changed statement itself reads/writes;
variables used by related blocks appear in the broader context, never as direct
relationships. Navigation is by module path; code-file line numbers are not
used.
"""

from __future__ import annotations

from ..facts import BlockContext, SymbolFact
from ..review import ChangeReview
from ..semantic_diff import ChangeChange

_RELEVANT_DEFINITION_ROLES = {"read", "produced", "dependency"}


def _code_block(source: str | None) -> str:
    if source is None:
        return "_(no source selected)_"
    return "\n```\n" + source.rstrip("\n") + "\n```\n"


def _kind_label(kind: str) -> str:
    return kind.replace("_", " ").capitalize()


def _block_heading(block: BlockContext) -> str:
    module = ".".join(block.module_path)
    return f"`{module}` — {block.kind} `{block.name}`"


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
            f"- **Relevant blocks/sequences:** {stats.relevant_block_count}",
            f"- **Relevant variables:** {stats.relevant_variable_count}",
            "",
        ]
    )
    return lines


def _render_direct_context(change: ChangeChange) -> list[str]:
    context = change.semantic_context
    if context is None:
        return []
    lines: list[str] = ["#### Direct semantic context", ""]
    if context.sequence_name:
        lines.extend([f"**Sequence:** `{context.sequence_name}`", ""])
        if context.previous_state:
            lines.extend([f"**Previous state:** `{context.previous_state}`", ""])
        if context.next_state:
            lines.extend([f"**Next state:** `{context.next_state}`", ""])
        if context.containing_state:
            lines.extend([f"**State:** `{context.containing_state}`", ""])
    for label, facts in (
        ("Direct reads", context.reads),
        ("Direct writes", context.produces),
        ("Callees", context.callees),
    ):
        if not facts:
            continue
        lines.append(f"**{label}:**")
        lines.append("")
        for fact in facts:
            annotation = f" (Type: {fact.datatype})" if fact.datatype else ""
            lines.append(f"- `{fact.symbol}`{annotation}")
        lines.append("")
    return lines


def _render_blocks_of_change(change: ChangeChange) -> list[str]:
    context = change.semantic_context
    if context is None:
        return []
    lines: list[str] = []
    if context.containing_block is not None:
        lines.extend(
            [
                "#### Containing block/sequence",
                "",
                f"{_block_heading(context.containing_block)}",
                "",
            ]
        )
    if context.related_blocks:
        lines.append("#### Related blocks/sequences")
        lines.append("")
        for block in context.related_blocks:
            reasons = "; ".join(block.reasons)
            lines.append(f"- {_block_heading(block)} — {reasons}")
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
    lines.extend(_render_direct_context(change))
    lines.extend(_render_blocks_of_change(change))
    lines.append("---")
    lines.append("")
    return lines


def _render_relevant_blocks(review: ChangeReview) -> list[str]:
    lines: list[str] = []
    if not review.context:
        return lines
    lines.extend(["## Relevant Blocks / Sequences", ""])
    for block in review.context:
        role = "changed" if block.role == "changed" else block.role
        lines.append(f"### {block.symbol} ({role})")
        lines.append("")
        if block.reasons:
            lines.append("Relevant because:")
            lines.append("")
            for reason in block.reasons:
                lines.append(f"- {reason}")
            lines.append("")
        if block.reads or block.writes:
            if block.reads:
                lines.append(f"- **Reads:** {', '.join(f'`{r}`' for r in block.reads)}")
            if block.writes:
                lines.append(f"- **Writes:** {', '.join(f'`{w}`' for w in block.writes)}")
            lines.append("")
        if block.sequence_name:
            lines.append(f"- **Sequence:** `{block.sequence_name}`")
            if block.previous_state:
                lines.append(f"- **Previous state:** `{block.previous_state}`")
            if block.next_state:
                lines.append(f"- **Next state:** `{block.next_state}`")
            lines.append("")
        if block.official_source is not None:
            lines.extend(["#### Official", "", _code_block(block.official_source)])
        if block.draft_source is not None:
            lines.extend(["#### Draft", "", _code_block(block.draft_source)])
        if block.source is not None:
            lines.append(_code_block(block.source))
        lines.append("")
    return lines


def _render_definition_sources(fact: SymbolFact) -> list[str]:
    official = fact.official_definition_source
    draft = fact.draft_definition_source
    if not official and not draft:
        return []
    lines: list[str] = ["Definition (assignment):", ""]
    if official and draft and official != draft:
        lines.extend(["**Official:**", "", _code_block(official)])
        lines.extend(["**Draft:**", "", _code_block(draft)])
    elif official:
        lines.extend(["**Official:**", "", _code_block(official)])
    elif draft:
        lines.extend(["**Draft:**", "", _code_block(draft)])
    else:
        lines.extend([_code_block(official)])
    return lines


def _render_relevant_variables(review: ChangeReview) -> list[str]:
    lines: list[str] = []
    definitions = [fact for fact in review.variable_definitions if fact.role in _RELEVANT_DEFINITION_ROLES]
    if not definitions:
        return lines
    lines.extend(["## Relevant Variables", ""])
    for fact in definitions:
        lines.append(f"### {fact.symbol}")
        lines.append("")
        lines.append("Relevant because:")
        lines.append("")
        for part in fact.reason.split("; "):
            lines.append(f"- {part}")
        if fact.declaration_source:
            lines.extend(["", "Declaration:", "", _code_block(fact.declaration_source)])
        lines.extend(_render_definition_sources(fact))
        if fact.datatype or fact.kind or fact.declared_by or fact.written_by or fact.read_by:
            lines.extend(["", "Semantic information:", ""])
            if fact.datatype:
                lines.append(f"- **Type:** {fact.datatype}")
            if fact.kind:
                lines.append(f"- **Kind:** {fact.kind}")
            if fact.declared_by:
                lines.append(f"- **Declared by:** `{fact.declared_by}`")
            if fact.written_by:
                lines.append(f"- **Written in:** {', '.join(f'`{w}`' for w in fact.written_by)}")
            if fact.read_by:
                lines.append(f"- **Read in:** {', '.join(f'`{r}`' for r in fact.read_by)}")
        lines.append("")
    return lines


def _render_scope(review: ChangeReview) -> list[str]:
    stats = review.size_stats
    return [
        "## Review Scope",
        "",
        f"- **Project source:** {stats.total_project_source_size} bytes",
        f"- **Selected source:** {stats.selected_source_size} bytes",
        f"- **Review artifact:** {stats.artifact_size} bytes",
        f"- **Metadata:** {stats.metadata_size} bytes",
        f"- **Source reduction:** {stats.source_reduction_percent}%",
        "",
    ]


def review_to_markdown(review: ChangeReview) -> str:
    """Render the review as a self-contained Markdown document."""
    lines: list[str] = ["# SattLint Change Review", ""]
    lines.extend(_render_summary(review))
    lines.extend(["## Changes", ""])
    for number, change in enumerate(review.changes, start=1):
        lines.extend(_render_change_entry(review, change, number))
    lines.extend(_render_relevant_blocks(review))
    lines.extend(_render_relevant_variables(review))
    lines.extend(_render_scope(review))
    return "\n".join(lines).rstrip() + "\n"
