"""Canonical, presentation-independent ``ChangeReview`` model.

The review is organized around equation blocks and sequences as the units of
behavioural context: for every change it includes the complete containing
block, the related blocks that read/write the changed variables, and the
definitions of all variables involved. It never depends on how it will be
presented (TUI, JSON, Markdown, or an AI consumer).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from datetime import UTC, datetime

from ..core._semantic_snapshot import SymbolDefinition
from ._code_model import BlockModel
from .facts import BlockContext, RelevanceResult, SymbolFact
from .loader import VersionSnapshot
from .semantic_diff import ChangeChange
from .source import SourceTextProvider


@dataclass(frozen=True)
class ReviewMetadata:
    project: str
    official_revision: str
    draft_revision: str
    generated_at: str


@dataclass(frozen=True)
class ReviewSizeStats:
    total_project_source_size: int
    selected_source_size: int
    metadata_size: int
    artifact_size: int
    source_reduction_percent: float
    semantic_change_count: int
    relevant_block_count: int
    relevant_variable_count: int
    contextual_block_count: int


@dataclass(frozen=True)
class ReviewContextBlock:
    """One complete equation block or sequence selected as review context."""

    symbol: str
    module_path: tuple[str, ...]
    kind: str
    name: str
    role: str
    reasons: tuple[str, ...]
    reads: tuple[str, ...]
    writes: tuple[str, ...]
    file: str | None
    line_start: int | None
    line_end: int | None
    official_source: str | None = None
    draft_source: str | None = None
    source: str | None = None
    sequence_name: str | None = None
    previous_state: str | None = None
    next_state: str | None = None


@dataclass(frozen=True)
class ChangeReview:
    metadata: ReviewMetadata
    changes: tuple[ChangeChange, ...]
    context: tuple[ReviewContextBlock, ...]
    variable_definitions: tuple[SymbolFact, ...]
    size_stats: ReviewSizeStats


def _end_line_for_span(
    provider: SourceTextProvider,
    file_name: str | None,
    span_line: int | None,
    start: int | None,
    end: int | None,
) -> int | None:
    if span_line is None:
        return None
    if start is None or end is None or end <= start:
        return span_line
    text = provider.text(file_name)
    if text is None or start < 0 or end > len(text):
        return span_line
    return span_line + text[start:end].count("\n")


_HEADER_PATTERN = re.compile(r"(EQUATIONBLOCK|SEQUENCE)\s+(\S+)")


def _expand_block_start(
    provider: SourceTextProvider,
    block: BlockModel,
) -> int:
    """Walk up from the first code line to include the block header line.

    The parser does not attach spans to ``EQUATIONBLOCK``/``SEQUENCE`` headers,
    so the block source is anchored to its first statement. If the keyword
    header appears within a few lines above, the slice is extended to include it
    so the complete block is preserved. This is source-presentation only, never
    semantic detection.
    """
    start_line = block.line_start
    if start_line is None or block.source_file is None or block.kind not in {"equation", "sequence"}:
        return start_line or 1
    for candidate in range(max(1, start_line - 8), start_line):
        line = provider.lines(block.source_file, candidate, candidate)
        if line is None:
            break
        match = _HEADER_PATTERN.search(line)
        if match is not None and match.group(2).casefold() == block.name.casefold():
            return candidate
    return start_line


def _block_source(
    provider: SourceTextProvider,
    block: BlockModel,
) -> tuple[str | None, str | None, int | None, int | None]:
    if block.source_file is None or block.line_start is None:
        return None, None, None, None
    end_line = None
    if block.last_span is not None:
        end_line = _end_line_for_span(
            provider,
            block.source_file,
            block.last_span.line,
            block.last_span.start,
            block.last_span.end,
        )
    if end_line is None:
        return None, None, None, None
    start_line = _expand_block_start(provider, block)
    source = provider.lines(block.source_file, start_line, end_line)
    if source is None:
        return None, None, None, None
    return source, block.source_file, start_line, end_line


def _version_block(version: VersionSnapshot, identity: tuple[tuple[str, ...], str, str]) -> BlockModel | None:
    return version.code_model.blocks_by_key.get(identity)


def _definition_for_key(version: VersionSnapshot, key: tuple[str, ...]) -> SymbolDefinition | None:
    for definition in version.snapshot.definitions:
        if tuple(segment.casefold() for segment in definition.canonical_path.split(".")) == key:
            return definition
    return None


def _variable_declaration_source(
    provider: SourceTextProvider,
    fact: SymbolFact,
    official: VersionSnapshot,
    draft: VersionSnapshot,
) -> str | None:
    """Return the actual declaration line(s) of a variable, if available.

    The declaration is the line that declares the variable (``Level: integer;``),
    distinct from the statements that assign its value.
    """
    key = tuple(segment.casefold() for segment in fact.symbol.split("."))
    for version in (draft, official):
        definition = _definition_for_key(version, key)
        if definition is None or definition.declaration_span is None:
            continue
        line = definition.declaration_span.line
        if definition.source_file:
            source = provider.lines(definition.source_file, line, line)
            if source:
                return source
        source = provider.snippet(
            definition.source_file,
            definition.declaration_span.start,
            definition.declaration_span.end,
        )
        if source:
            return source
    return None


def _definition_source_in_version(
    provider: SourceTextProvider,
    fact: SymbolFact,
    version: VersionSnapshot,
) -> str | None:
    """Return the statement that assigns the variable in one project version."""
    key = tuple(segment.casefold() for segment in fact.symbol.split("."))
    for block in version.code_model.blocks_by_key.values():
        if key not in block.writes_keys:
            continue
        for statement in block.statements:
            if key in statement.produced_keys and statement.span is not None and statement.source_file:
                source = provider.snippet(
                    statement.source_file,
                    statement.span.start,
                    statement.span.end,
                )
                if source:
                    return source
    return None


def _attach_variable_sources(
    variables: tuple[SymbolFact, ...],
    *,
    official: VersionSnapshot,
    draft: VersionSnapshot,
    provider: SourceTextProvider,
) -> tuple[SymbolFact, ...]:
    enriched: list[SymbolFact] = []
    for fact in variables:
        if fact.declaration_source is None:
            source = _variable_declaration_source(provider, fact, official, draft)
            if source is not None:
                fact = replace(fact, declaration_source=source)
        if fact.official_definition_source is None:
            source = _definition_source_in_version(provider, fact, official)
            if source is not None:
                fact = replace(fact, official_definition_source=source)
        if fact.draft_definition_source is None:
            source = _definition_source_in_version(provider, fact, draft)
            if source is not None:
                fact = replace(fact, draft_definition_source=source)
        enriched.append(fact)
    return tuple(enriched)


def _context_block_for(
    context: BlockContext,
    *,
    official: VersionSnapshot,
    draft: VersionSnapshot,
    provider: SourceTextProvider,
) -> ReviewContextBlock | None:
    identity = (context.module_path, context.kind, context.name)
    official_block = _version_block(official, identity)
    draft_block = _version_block(draft, identity)
    if official_block is None and draft_block is None:
        return None

    official_source = None
    draft_source = None
    source = None
    file_name = None
    line_start = None
    line_end = None

    if context.role == "changed":
        if official_block is not None:
            official_source, file_name, line_start, line_end = _block_source(provider, official_block)
        if draft_block is not None:
            draft_source, draft_file, draft_start, draft_end = _block_source(provider, draft_block)
            if file_name is None:
                file_name = draft_file
            if line_start is None:
                line_start = draft_start
            if line_end is None:
                line_end = draft_end
    else:
        preferred = draft_block if draft_block is not None else official_block
        if preferred is not None:
            source, file_name, line_start, line_end = _block_source(provider, preferred)

    if official_source is None and draft_source is None and source is None:
        return None

    return ReviewContextBlock(
        symbol=context.symbol,
        module_path=context.module_path,
        kind=context.kind,
        name=context.name,
        role=context.role,
        reasons=context.reasons,
        reads=context.reads,
        writes=context.writes,
        file=file_name,
        line_start=line_start,
        line_end=line_end,
        official_source=official_source,
        draft_source=draft_source,
        source=source,
        sequence_name=context.sequence_name,
        previous_state=context.previous_state,
        next_state=context.next_state,
    )


def _attach_contexts(
    changes: list[ChangeChange],
    relevance: RelevanceResult,
) -> tuple[ChangeChange, ...]:
    context_by_index = dict(relevance.change_contexts)
    enriched: list[ChangeChange] = []
    for index, change in enumerate(changes):
        context = context_by_index.get(index)
        enriched.append(replace(change, semantic_context=context) if context is not None else change)
    return tuple(enriched)


def build_change_review(
    official: VersionSnapshot,
    draft: VersionSnapshot,
    changes: list[ChangeChange],
    relevance: RelevanceResult,
    *,
    snippet_provider: SourceTextProvider,
) -> ChangeReview:
    """Assemble the canonical review from the semantic diff and relevance sets."""
    enriched_changes = _attach_contexts(changes, relevance)

    context: list[ReviewContextBlock] = []
    for block_context in relevance.relevant_blocks:
        block = _context_block_for(
            block_context,
            official=official,
            draft=draft,
            provider=snippet_provider,
        )
        if block is not None:
            context.append(block)

    total_size = official.total_source_size + draft.total_source_size
    selected_source_size = sum(
        len(block.source or "") + len(block.official_source or "") + len(block.draft_source or "") for block in context
    )
    reduction = 1.0 - (selected_source_size / total_size) if total_size else 0.0

    variable_definitions = _attach_variable_sources(
        relevance.relevant_variables,
        official=official,
        draft=draft,
        provider=snippet_provider,
    )

    changed_count = sum(1 for block in context if block.role == "changed")
    contextual_count = len(context) - changed_count

    metadata = ReviewMetadata(
        project=official.snapshot.entry_file.stem or official.snapshot.base_picture.name,
        official_revision=official.label,
        draft_revision=draft.label,
        generated_at=datetime.now(UTC).isoformat(timespec="seconds"),
    )
    size_stats = ReviewSizeStats(
        total_project_source_size=total_size,
        selected_source_size=selected_source_size,
        metadata_size=0,
        artifact_size=0,
        source_reduction_percent=round(reduction * 100.0, 2),
        semantic_change_count=len(changes),
        relevant_block_count=len(relevance.relevant_blocks),
        relevant_variable_count=len(relevance.relevant_variables),
        contextual_block_count=contextual_count,
    )

    return ChangeReview(
        metadata=metadata,
        changes=enriched_changes,
        context=tuple(context),
        variable_definitions=variable_definitions,
        size_stats=size_stats,
    )
