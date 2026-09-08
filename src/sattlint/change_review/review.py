"""Canonical, presentation-independent ``ChangeReview`` model.

The review model separates what changed, what semantic facts are relevant, what
context was selected, and project metadata. It never depends on how it will be
presented (TUI, JSON, Markdown, or an AI consumer).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime

from ._code_model import ModuleModel
from .facts import RelevanceResult, SymbolFact
from .loader import VersionSnapshot
from .semantic_diff import ChangeChange, SourceLocation
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
    selected_context_size: int
    reduction_percent: float
    semantic_change_count: int
    relevant_symbol_count: int
    contextual_symbol_count: int


@dataclass(frozen=True)
class ReviewContextBlock:
    symbol: str
    role: str
    reason: str | None
    file: str | None
    line_start: int | None
    line_end: int | None
    official_source: str | None = None
    draft_source: str | None = None
    source: str | None = None


@dataclass(frozen=True)
class ChangeReview:
    metadata: ReviewMetadata
    changes: tuple[ChangeChange, ...]
    relevant_symbols: tuple[SymbolFact, ...]
    context: tuple[ReviewContextBlock, ...]
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


def _source_for_location(
    provider: SourceTextProvider,
    location: SourceLocation | None,
) -> str | None:
    if location is None:
        return None
    snippet = provider.snippet(location.file, location.start, location.end)
    if snippet is not None:
        return snippet
    return provider.lines(location.file, location.line or 0, location.line or 0) if location.line else None


def _module_source_block(
    provider: SourceTextProvider,
    module: ModuleModel,
) -> tuple[str | None, str | None, int | None, int | None]:
    if not module.statements or module.origin_file is None:
        return None, None, None, None
    first = module.statements[0]
    last = module.statements[-1]
    file_name = module.origin_file
    start_line = first.span.line if first.span is not None else None
    start_offset = first.span.start if first.span is not None else None
    end_offset = last.span.end if last.span is not None else None
    end_line = _end_line_for_span(provider, file_name, start_line, start_offset, end_offset)
    if start_line is None or end_line is None:
        return None, None, None, None
    source = provider.lines(file_name, start_line, end_line)
    return source, file_name, start_line, end_line


def _changed_block(
    provider: SourceTextProvider,
    change: ChangeChange,
) -> ReviewContextBlock | None:
    official_source = _source_for_location(provider, change.location)
    draft_source = _source_for_location(provider, change.draft_location)
    if official_source is None and draft_source is None:
        return None
    return ReviewContextBlock(
        symbol=change.symbol,
        role="changed",
        reason=change.detail,
        file=change.location.file if change.location is not None else None,
        line_start=change.location.line if change.location is not None else None,
        line_end=_end_line_for_span(
            provider,
            change.location.file if change.location is not None else None,
            change.location.line if change.location is not None else None,
            change.location.start if change.location is not None else None,
            change.location.end if change.location is not None else None,
        ),
        official_source=official_source,
        draft_source=draft_source,
    )


def _merged_modules(
    official: VersionSnapshot,
    draft: VersionSnapshot,
) -> dict[tuple[str, ...], ModuleModel]:
    merged: dict[tuple[str, ...], ModuleModel] = {}
    for version in (official, draft):
        for module in version.code_model.modules:
            merged[module.module_path] = module
    return merged


def _attach_contexts(
    changes: list[ChangeChange],
    relevance: RelevanceResult,
) -> tuple[ChangeChange, ...]:
    context_by_index = dict(relevance.change_contexts)
    enriched: list[ChangeChange] = []
    for index, change in enumerate(changes):
        context = context_by_index.get(index)
        if context is None:
            enriched.append(change)
        else:
            enriched.append(replace(change, semantic_context=context))
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
    modules_by_path = _merged_modules(official, draft)

    context: list[ReviewContextBlock] = []
    seen_symbols: set[str] = set()
    seen_code_sources: set[int] = set()

    for change in enriched_changes:
        block = _changed_block(snippet_provider, change)
        if block is None:
            continue
        key = block.symbol.casefold()
        if key in seen_symbols:
            continue
        seen_symbols.add(key)
        context.append(block)

    for fact in relevance.relevant_symbols:
        symbol_key = fact.symbol.casefold()
        if symbol_key in seen_symbols:
            continue
        if fact.role == "changed":
            seen_symbols.add(symbol_key)
            continue
        module = modules_by_path.get(tuple(segment for segment in fact.symbol.split(".")))
        if module is None:
            continue
        if module.code_source_id in seen_code_sources:
            seen_symbols.add(symbol_key)
            continue
        source, file_name, start_line, end_line = _module_source_block(snippet_provider, module)
        if source is None:
            continue
        seen_symbols.add(symbol_key)
        seen_code_sources.add(module.code_source_id)
        context.append(
            ReviewContextBlock(
                symbol=fact.symbol,
                role=fact.role,
                reason=fact.reason,
                file=file_name,
                line_start=start_line,
                line_end=end_line,
                source=source,
            )
        )

    context.sort(key=lambda block: (block.role, block.symbol.casefold()))

    total_size = official.total_source_size + draft.total_source_size
    selected_size = sum(
        len(block.source or "") + len(block.official_source or "") + len(block.draft_source or "") for block in context
    )
    reduction = 1.0 - (selected_size / total_size) if total_size else 0.0

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
        selected_context_size=selected_size,
        reduction_percent=round(reduction * 100.0, 2),
        semantic_change_count=len(changes),
        relevant_symbol_count=len(relevance.relevant_symbols),
        contextual_symbol_count=contextual_count,
    )

    return ChangeReview(
        metadata=metadata,
        changes=enriched_changes,
        relevant_symbols=relevance.relevant_symbols,
        context=tuple(context),
        size_stats=size_stats,
    )
