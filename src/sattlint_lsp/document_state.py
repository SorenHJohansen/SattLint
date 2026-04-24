"""Mutable document-state helpers for LSP edit tracking."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sattlint.core.document import LineIndex

if TYPE_CHECKING:
    from sattlint.core.semantic import SemanticSnapshot

    from .local_parser import DocumentParseResult


def _merge_line_ranges(ranges: list[tuple[int, int]]) -> tuple[tuple[int, int], ...]:
    if not ranges:
        return ()

    ordered = sorted((max(0, start), max(0, end)) for start, end in ranges)
    merged: list[tuple[int, int]] = []
    for start, end in ordered:
        if not merged:
            merged.append((start, end))
            continue
        prev_start, prev_end = merged[-1]
        if start <= (prev_end + 1):
            merged[-1] = (prev_start, max(prev_end, end))
            continue
        merged.append((start, end))
    return tuple(merged)


def apply_content_changes(
    text: str,
    content_changes: list[Any],
    *,
    line_index: LineIndex | None = None,
) -> tuple[str, tuple[tuple[int, int], ...]]:
    if not content_changes:
        return text, ()

    updated = text
    current_index = line_index if line_index is not None and line_index.text == text else LineIndex.from_text(text)
    changed_line_ranges: list[tuple[int, int]] = []
    for change in content_changes:
        change_text = str(getattr(change, "text", ""))
        range_ = getattr(change, "range", None)
        if range_ is None:
            updated = change_text
            current_index = LineIndex.from_text(updated)
            changed_line_ranges.append((0, max(change_text.count("\n"), 0)))
            continue

        start_line = max(int(range_.start.line), 0)
        end_line = max(int(range_.end.line), start_line)
        start_offset = current_index.position_to_offset(start_line, int(range_.start.character))
        end_offset = current_index.position_to_offset(end_line, int(range_.end.character))
        updated = updated[:start_offset] + change_text + updated[end_offset:]
        current_index = LineIndex.from_text(updated)
        changed_line_ranges.append((start_line, max(end_line, start_line + change_text.count("\n"))))

    return updated, _merge_line_ranges(changed_line_ranges)


@dataclass(slots=True)
class DocumentState:
    uri: str
    path: Path
    version: int
    text: str
    is_dirty: bool = False
    changed_line_ranges: tuple[tuple[int, int], ...] = ()
    syntax_diagnostics: tuple[Any, ...] = ()
    local_snapshot: SemanticSnapshot | None = None
    local_snapshot_version: int = -1
    analysis_result: DocumentParseResult | None = None
    previous_analysis_result: DocumentParseResult | None = None
    analysis_version: int = -1
    analysis_includes_comment_validation: bool = False
    analysis_has_snapshot: bool = False
    line_index: LineIndex = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.line_index = LineIndex.from_text(self.text)

    def preserve_analysis_result(self) -> None:
        if self.analysis_result is not None and self.analysis_version == self.version:
            self.previous_analysis_result = self.analysis_result

    def replace_text(self, *, version: int, text: str, is_dirty: bool = False) -> None:
        self.preserve_analysis_result()
        self.version = version
        self.text = text
        self.line_index = LineIndex.from_text(text)
        self.is_dirty = is_dirty
        self.changed_line_ranges = ()
        self.syntax_diagnostics = ()
        self.clear_analysis()

    def apply_changes(self, *, version: int, content_changes: list[Any], fallback_text: str | None = None) -> None:
        try:
            updated, changed_ranges = apply_content_changes(
                self.text,
                content_changes,
                line_index=self.line_index,
            )
        except (ValueError, IndexError, TypeError):  # LSP content-change apply
            updated = fallback_text if fallback_text is not None else self.text
            changed_ranges = ()

        self.preserve_analysis_result()
        self.version = version
        self.text = updated
        self.line_index = LineIndex.from_text(updated)
        self.is_dirty = True
        self.changed_line_ranges = changed_ranges
        self.syntax_diagnostics = ()
        self.clear_analysis()

    def has_analysis(self, *, include_comment_validation: bool, require_snapshot: bool = False) -> bool:
        if self.analysis_version != self.version:
            return False
        if self.analysis_includes_comment_validation != include_comment_validation:
            return False
        return not (require_snapshot and not self.analysis_has_snapshot)

    def remember_analysis(self, result: DocumentParseResult, *, include_comment_validation: bool) -> None:
        self.syntax_diagnostics = tuple(result.syntax_diagnostics)
        self.local_snapshot = result.local_snapshot
        self.local_snapshot_version = self.version if result.local_snapshot is not None else -1
        self.analysis_result = result
        self.analysis_version = self.version
        self.analysis_includes_comment_validation = include_comment_validation
        self.analysis_has_snapshot = result.local_snapshot is not None

    def remember_local_snapshot(self, snapshot: SemanticSnapshot) -> None:
        self.local_snapshot = snapshot
        self.local_snapshot_version = self.version
        self.analysis_result = DocumentParseResult(
            syntax_diagnostics=tuple(self.syntax_diagnostics), local_snapshot=snapshot
        )
        self.analysis_version = self.version
        self.analysis_has_snapshot = True

    def clear_local_snapshot(self) -> None:
        self.local_snapshot = None
        self.local_snapshot_version = -1

    def clear_analysis(self) -> None:
        self.clear_local_snapshot()
        self.analysis_result = None
        self.analysis_version = -1
        self.analysis_includes_comment_validation = False
        self.analysis_has_snapshot = False
