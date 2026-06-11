"""Parser-core text preprocessing helpers."""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass

__all__ = ["CommentStrippedText", "strip_sl_comments", "strip_sl_comments_with_mapping"]


def _line_starts(text: str) -> tuple[int, ...]:
    starts = [0]
    index = 0
    length = len(text)
    while index < length:
        ch = text[index]
        if ch == "\r":
            index += 2 if index + 1 < length and text[index + 1] == "\n" else 1
            starts.append(index)
            continue
        if ch == "\n":
            index += 1
            starts.append(index)
            continue
        index += 1
    return tuple(starts)


@dataclass(frozen=True, slots=True)
class CommentStrippedText:
    text: str
    cleaned_offsets_to_original: tuple[int, ...]
    original_line_starts: tuple[int, ...]
    cleaned_line_starts: tuple[int, ...]

    def map_line_column(self, line: int | None, column: int | None) -> tuple[int | None, int | None]:
        if line is None or column is None or line < 1 or column < 1:
            return line, column
        if line > len(self.cleaned_line_starts):
            return line, column

        line_start = self.cleaned_line_starts[line - 1]
        line_limit = self.cleaned_line_starts[line] - 1 if line < len(self.cleaned_line_starts) else len(self.text)
        cleaned_offset = min(max(line_start + column - 1, line_start), line_limit)
        original_offset = self.cleaned_offsets_to_original[
            min(cleaned_offset, len(self.cleaned_offsets_to_original) - 1)
        ]

        original_line_index = bisect_right(self.original_line_starts, original_offset) - 1
        if original_line_index < 0:
            return line, column
        original_line = original_line_index + 1
        original_column = original_offset - self.original_line_starts[original_line_index] + 1
        return original_line, original_column


def strip_sl_comments_with_mapping(text: str) -> CommentStrippedText:  # noqa: PLR0915
    """
    Remove nested comments of the form (* ... *) from the input text while
    preserving a mapping from cleaned-text offsets back to the original source.
    """
    n = len(text)
    i = 0
    depth = 0
    in_string = False
    string_quote = ""
    out: list[str] = []
    cleaned_offsets_to_original: list[int] = [0]

    def append_char(ch: str, original_offset: int) -> None:
        out.append(ch)
        cleaned_offsets_to_original.append(original_offset + 1)

    while i < n:
        ch = text[i]

        if depth == 0:
            if not in_string:
                if ch == '"' or ch == "'":
                    in_string = True
                    string_quote = ch
                    append_char(ch, i)
                    i += 1
                    continue
                if ch == "(" and i + 1 < n and text[i + 1] == "*":
                    depth = 1
                    i += 2
                    continue
                append_char(ch, i)
                i += 1
            else:
                if ch == "\n" or ch == "\r":
                    append_char(ch, i)
                    in_string = False
                    string_quote = ""
                    i += 1
                elif ch == string_quote:
                    if i + 1 < n and text[i + 1] == string_quote:
                        append_char(string_quote, i)
                        append_char(string_quote, i + 1)
                        i += 2
                    else:
                        append_char(string_quote, i)
                        i += 1
                        in_string = False
                        string_quote = ""
                elif ch == "\\":
                    append_char("\\", i)
                    if i + 1 < n:
                        append_char(text[i + 1], i + 1)
                        i += 2
                    else:
                        i += 1
                else:
                    append_char(ch, i)
                    i += 1
        else:
            if ch == "(" and i + 1 < n and text[i + 1] == "*":
                depth += 1
                i += 2
            elif ch == "*" and i + 1 < n and text[i + 1] == ")":
                depth -= 1
                i += 2
                if depth == 0:
                    j = i
                    while j < n and text[j] in (" ", "\t", "\r", "\n"):
                        append_char(text[j], j)
                        j += 1
                    if j < n and text[j] == ";":
                        j += 1
                    i = j
            else:
                if ch == "\n" or ch == "\r":
                    append_char(ch, i)
                i += 1

    cleaned_offsets_to_original[-1] = n
    cleaned_text = "".join(out)
    return CommentStrippedText(
        text=cleaned_text,
        cleaned_offsets_to_original=tuple(cleaned_offsets_to_original),
        original_line_starts=_line_starts(text),
        cleaned_line_starts=_line_starts(cleaned_text),
    )


def strip_sl_comments(text: str) -> str:
    """
    Remove nested comments of the form (* ... *) from the input text.
    Preserves original line numbers by emitting newline characters
    encountered inside comments and in the whitespace after a comment.
    Also removes a single semicolon that immediately follows a comment
    (allowing intervening whitespace/newlines), while preserving those
    whitespace/newlines.

    Additionally:
    - Does NOT treat (* or *) as comment delimiters when they appear inside
      single- or double-quoted strings.
    - Inside strings, supports doubled quotes ("" and '') and backslash escapes.
    - A newline ends a string if it hasn't been closed yet. Both LF and CR will
      terminate the string; CRLF is preserved as-is.

    Assumptions:
    - Comments can be nested and may contain newlines.
    - Every comment is closed before EOF.
    """
    return strip_sl_comments_with_mapping(text).text
