"""SattLint Change Review: semantic diff and block-centric context capability.

The Change Review turns an official (baseline) project version and a draft
(modified) version into a single compact, self-contained review artifact that
is equally useful to humans and external AI reviewers.

The review is organized around equation blocks and sequences as units of
behavioural context: for every semantic change it includes the complete
containing block, the related blocks/sequences that read or write the changed
variables, and the definitions of every variable involved — each with an
explicit reason for inclusion.

This capability is intentionally independent of static analysis: no analyzers
run, no diagnostics are collected, and the review never depends on analyzer
results. It reuses SattLint's existing ``SemanticSnapshot`` and per-module
semantic code model as the source of truth.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path

from ..config.types import ConfigDict
from .artifacts import write_review_artifacts
from .facts import BlockContext, ChangeSemanticContext, RelevanceResult, SymbolFact
from .impact import compute_relevance
from .loader import VersionSnapshot, load_version_snapshot
from .review import ChangeReview, ReviewContextBlock, build_change_review
from .semantic_diff import ChangeChange, ChangeKind, SourceLocation, compute_semantic_diff
from .serialization.json_serializer import review_to_json
from .serialization.markdown_serializer import review_to_markdown
from .source import SourceTextProvider

__all__ = [
    "BlockContext",
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


def _with_artifact_sizes(review: ChangeReview) -> ChangeReview:
    json_text = review_to_json(review)
    markdown_text = review_to_markdown(review)
    artifact_size = len(json_text.encode("utf-8")) + len(markdown_text.encode("utf-8"))
    metadata_size = max(0, artifact_size - review.size_stats.selected_source_size)
    return replace(
        review,
        size_stats=replace(
            review.size_stats,
            artifact_size=artifact_size,
            metadata_size=metadata_size,
        ),
    )


def generate_change_review(
    cfg: ConfigDict,
    program_name: str,
    *,
    output_dir: Path,
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
    relevance = compute_relevance(official, draft, changes)
    review = build_change_review(
        official,
        draft,
        changes,
        relevance,
        snippet_provider=provider,
    )
    review = _with_artifact_sizes(review)
    json_path, markdown_path = write_review_artifacts(review, output_dir)
    return ChangeReviewResult(review=review, json_path=json_path, markdown_path=markdown_path)
