"""Original-source text extraction for the Change Review.

Source snippets are sliced from the *original* file text using ``SourceSpan``
character offsets, preserving exact SattLine source. Files are read lazily and
cached once per project version.
"""

from __future__ import annotations

from pathlib import Path

from sattline_parser.api import read_text_with_fallback


class SourceTextProvider:
    def __init__(self, source_files: dict[str, Path]):
        self._source_files = dict(source_files)
        self._cache: dict[str, str] = {}

    def file_path(self, file_name: str | None) -> Path | None:
        if file_name is None:
            return None
        return self._source_files.get(file_name.casefold())

    def text(self, file_name: str | None) -> str | None:
        if file_name is None:
            return None
        path = self.file_path(file_name)
        if path is None:
            return None
        cached = self._cache.get(file_name.casefold())
        if cached is not None:
            return cached
        try:
            content = read_text_with_fallback(path)
        except OSError:
            return None
        self._cache[file_name.casefold()] = content
        return content

    def snippet(self, file_name: str | None, start: int | None, end: int | None) -> str | None:
        if file_name is None or start is None or end is None or end <= start:
            return None
        text = self.text(file_name)
        if text is None or start < 0 or end > len(text):
            return None
        return text[start:end]

    def line_count(self, file_name: str | None) -> int | None:
        text = self.text(file_name)
        if text is None:
            return None
        return text.count("\n") + (1 if text and not text.endswith("\n") else 0)

    def lines(self, file_name: str | None, start_line: int, end_line: int) -> str | None:
        """Return original source lines ``start_line``..``end_line`` inclusive."""
        if file_name is None:
            return None
        text = self.text(file_name)
        if text is None:
            return None
        all_lines = text.splitlines()
        if not all_lines:
            return ""
        start = max(1, start_line)
        end = min(len(all_lines), end_line)
        if start > end:
            return ""
        return "\n".join(all_lines[start - 1 : end])

    def declaration_snippet(
        self,
        file_name: str | None,
        start: int | None,
        end: int | None,
        line: int | None,
    ) -> str | None:
        if file_name is None:
            return None
        snippet = self.snippet(file_name, start, end)
        if snippet is not None:
            return snippet
        if line is None:
            return None
        return self.lines(file_name, line, line)
