"""Shared text indexing helpers for editor-facing document operations."""

from __future__ import annotations

from dataclasses import dataclass


def _utf16_units(char: str) -> int:
    return 2 if ord(char) > 0xFFFF else 1


def utf16_index_to_codepoint_offset(text: str, utf16_index: int) -> int:
    if utf16_index <= 0:
        return 0

    units = 0
    for index, char in enumerate(text):
        units += _utf16_units(char)
        if units >= utf16_index:
            return index + 1
    return len(text)


def _build_line_starts(text: str) -> tuple[int, ...]:
    starts = [0]
    for index, char in enumerate(text):
        if char == "\n":
            starts.append(index + 1)
    return tuple(starts)


@dataclass(frozen=True, slots=True)
class LineIndex:
    text: str
    line_starts: tuple[int, ...]

    @classmethod
    def from_text(cls, text: str) -> LineIndex:
        return cls(text=text, line_starts=_build_line_starts(text))

    def line_start_offset(self, zero_based_line: int) -> int:
        if zero_based_line <= 0:
            return 0
        if zero_based_line >= len(self.line_starts):
            return len(self.text)
        return self.line_starts[zero_based_line]

    def line_text(self, zero_based_line: int) -> str:
        if zero_based_line < 0:
            return ""
        start = self.line_start_offset(zero_based_line)
        end = self.line_starts[zero_based_line + 1] if zero_based_line + 1 < len(self.line_starts) else len(self.text)
        line_text = self.text[start:end]
        if line_text.endswith("\r\n"):
            return line_text[:-2]
        if line_text.endswith("\n") or line_text.endswith("\r"):
            return line_text[:-1]
        return line_text

    def position_to_offset(self, line: int, character: int) -> int:
        target_line = max(line, 0)
        if not self.line_starts:
            return 0
        if target_line >= len(self.line_starts):
            return len(self.text)
        offset = self.line_start_offset(target_line)
        line_body = self.line_text(target_line)
        return offset + utf16_index_to_codepoint_offset(line_body, character)
