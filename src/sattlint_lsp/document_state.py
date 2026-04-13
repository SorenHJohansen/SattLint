"""Mutable document-state helpers for LSP edit tracking."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from sattlint.editor_api import SemanticSnapshot
    from .local_parser import DocumentParseResult


def _utf16_units(char: str) -> int:
    return 2 if ord(char) > 0xFFFF else 1


def _utf16_index_to_codepoint_offset(text: str, utf16_index: int) -> int:
    if utf16_index <= 0:
        return 0

    units = 0
    for index, char in enumerate(text):
        units += _utf16_units(char)
        if units >= utf16_index:
            return index + 1
    return len(text)


def _position_to_offset(text: str, line: int, character: int) -> int:
    target_line = max(line, 0)
    lines = text.splitlines(keepends=True)
    if not lines:
        return 0
    if target_line >= len(lines):
        return len(text)

    offset = sum(len(lines[index]) for index in range(target_line))
    line_text = lines[target_line]
    if line_text.endswith("\r\n"):
        line_body = line_text[:-2]
    elif line_text.endswith("\n") or line_text.endswith("\r"):
        line_body = line_text[:-1]
    else:
        line_body = line_text
    return offset + _utf16_index_to_codepoint_offset(line_body, character)


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


def apply_content_changes(text: str, content_changes: list[Any]) -> tuple[str, tuple[tuple[int, int], ...]]:
    if not content_changes:
        return text, ()

    updated = text
    changed_line_ranges: list[tuple[int, int]] = []
    for change in content_changes:
        change_text = str(getattr(change, "text", ""))
        range_ = getattr(change, "range", None)
        if range_ is None:
            updated = change_text
            changed_line_ranges.append((0, max(change_text.count("\n"), 0)))
            continue

        start_line = max(int(range_.start.line), 0)
        end_line = max(int(range_.end.line), start_line)
        start_offset = _position_to_offset(updated, start_line, int(range_.start.character))
        end_offset = _position_to_offset(updated, end_line, int(range_.end.character))
        updated = updated[:start_offset] + change_text + updated[end_offset:]
        changed_line_ranges.append((start_line, max(end_line, start_line + change_text.count("\n"))))

    return updated, _merge_line_ranges(changed_line_ranges)


@dataclass(slots=True)
class DocumentState:
    uri: str
    path: Path
    version: int
    text: str
    changed_line_ranges: tuple[tuple[int, int], ...] = ()
    syntax_diagnostics: tuple[Any, ...] = ()
    local_snapshot: SemanticSnapshot | None = None
    local_snapshot_version: int = -1
    analysis_result: DocumentParseResult | None = None
    previous_analysis_result: DocumentParseResult | None = None
    analysis_version: int = -1
    analysis_includes_comment_validation: bool = False
    analysis_has_snapshot: bool = False

    def preserve_analysis_result(self) -> None:
        if self.analysis_result is not None and self.analysis_version == self.version:
            self.previous_analysis_result = self.analysis_result

    def replace_text(self, *, version: int, text: str) -> None:
        self.preserve_analysis_result()
        self.version = version
        self.text = text
        self.changed_line_ranges = ()
        self.syntax_diagnostics = ()
        self.clear_analysis()

    def apply_changes(self, *, version: int, content_changes: list[Any], fallback_text: str | None = None) -> None:
        try:
            updated, changed_ranges = apply_content_changes(self.text, content_changes)
        except Exception:
            updated = fallback_text if fallback_text is not None else self.text
            changed_ranges = ()

        self.preserve_analysis_result()
        self.version = version
        self.text = updated
        self.changed_line_ranges = changed_ranges
        self.syntax_diagnostics = ()
        self.clear_analysis()

    def has_analysis(self, *, include_comment_validation: bool, require_snapshot: bool = False) -> bool:
        if self.analysis_version != self.version:
            return False
        if self.analysis_includes_comment_validation != include_comment_validation:
            return False
        if require_snapshot and not self.analysis_has_snapshot:
            return False
        return True

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
        self.analysis_result = DocumentParseResult(syntax_diagnostics=tuple(self.syntax_diagnostics), local_snapshot=snapshot)
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
