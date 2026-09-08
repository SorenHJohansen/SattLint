"""SattLint Change Review: semantic diff and impact analysis capability.

The Change Review turns an official (baseline) project version and a draft
(modified) version into a single compact, self-contained review artifact that
is equally useful to humans and external AI reviewers.

The review is organized around *understanding the consequences* of each change:
for every semantic change it exposes the referenced symbols, their definitions
and data origins, the outputs and their consumers, callers/callees, and the
surrounding sequence/S88 structure — each with an explicit reason for inclusion.

This capability is intentionally independent of static analysis: no analyzers
run, no diagnostics are collected, and the review never depends on analyzer
results. It reuses SattLint's existing ``SemanticSnapshot`` and per-module
semantic code model as the source of truth.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from ..config.types import ConfigDict
from .artifacts import write_review_artifacts
from .facts import ChangeSemanticContext, RelevanceResult, SymbolFact
from .impact import DEFAULT_MAX_SYMBOLS, compute_relevance
from .loader import VersionSnapshot, load_version_snapshot
from .review import ChangeReview, ReviewContextBlock, build_change_review
from .semantic_diff import ChangeChange, ChangeKind, SourceLocation, compute_semantic_diff
from .source import SourceTextProvider

__all__ = [
    "ChangeChange",
    "ChangeKind",
    "ChangeReview",
    "ChangeSemanticContext",
    "RelevanceResult",
    "ReviewContextBlock",
    "SourceLocation",
    "SymbolFact",
    "VersionSnapshot",
    "build_change_review",
    "compute_relevance",
    "compute_semantic_diff",
    "generate_change_review",
    "load_version_snapshot",
    "write_review_artifacts",
]


@dataclass(frozen=True)
class ChangeReviewResult:
    review: ChangeReview
    json_path: Path
    markdown_path: Path


def _build_snippet_provider(official: VersionSnapshot, draft: VersionSnapshot) -> SourceTextProvider:
    source_files = dict(official.source_files)
    source_files.update(draft.source_files)
    return SourceTextProvider(source_files)


def _snippet_fn(provider: SourceTextProvider) -> Callable[[str | None, object], str | None]:
    def snippet(source_file: str | None, span: object) -> str | None:
        start = getattr(span, "start", None)
        end = getattr(span, "end", None)
        if not isinstance(start, int) or not isinstance(end, int):
            return None
        return provider.snippet(source_file, start, end)

    return snippet


def generate_change_review(
    cfg: ConfigDict,
    program_name: str,
    *,
    output_dir: Path,
    max_symbols: int = DEFAULT_MAX_SYMBOLS,
) -> ChangeReviewResult:
    """Load both versions, diff them semantically, and write the artifacts.

    Official and draft snapshots are each parsed once and reused for the
    semantic diff, relevance analysis, and context extraction. No static
    analyzers are invoked.
    """
    official = load_version_snapshot(cfg, program_name, mode="official")
    draft = load_version_snapshot(cfg, program_name, mode="draft")
    provider = _build_snippet_provider(official, draft)
    snippet_fn = _snippet_fn(provider)

    changes = compute_semantic_diff(official, draft, snippet_fn=snippet_fn)
    relevance = compute_relevance(official, draft, changes, max_symbols=max_symbols)
    review = build_change_review(
        official,
        draft,
        changes,
        relevance,
        snippet_provider=provider,
    )
    json_path, markdown_path = write_review_artifacts(review, output_dir)
    return ChangeReviewResult(review=review, json_path=json_path, markdown_path=markdown_path)
