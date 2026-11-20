"""Original-source text extraction for the Change Review.

Source snippets are sliced from the *original* file text using ``SourceSpan``
character offsets, preserving exact SattLine source. Files are read lazily and
cached once per project version.

The text must be the text the parser read: ``SourceSpan`` offsets point into the
parse input, not into the decoded plain text. SattLine files come in three
on-disk flavors (byte-coded streams, marker-compressed text and plain
Windows-1252), so the provider reads through ``source_text_for_parse``. Reading
the raw bytes as Windows-1252 instead would fail on byte-coded files whose
stream holds bytes undefined in that encoding, and would silently shift every
offset for marker-compressed files.

A file is addressed by library and name, because two libraries may each contain
a ``DiluteLib.s``. A bare name still resolves when it is unique across the
project, which keeps single-library projects and fixtures simple.
"""

from __future__ import annotations

from pathlib import Path

from sattlint.parser_api import source_text_for_parse

#: ``(library.casefold(), file_name.casefold())``. The empty library means the
#: caller did not know one.
SourceKey = tuple[str, str]


def source_key(file_name: str, library: str | None) -> SourceKey:
    """Return the provider key for a source file."""
    return ((library or "").casefold(), file_name.casefold())


class SourceTextProvider:
    def __init__(self, source_files: dict[SourceKey, Path]):
        self._source_files = dict(source_files)
        self._cache: dict[SourceKey, str] = {}
        by_name: dict[str, list[SourceKey]] = {}
        for key in self._source_files:
            by_name.setdefault(key[1], []).append(key)
        self._unique_by_name = {name: keys[0] for name, keys in by_name.items() if len(keys) == 1}

    def _key(self, file_name: str, library: str | None) -> SourceKey | None:
        exact = source_key(file_name, library)
        if exact in self._source_files:
            return exact
        if library:
            return None
        return self._unique_by_name.get(file_name.casefold())

    def file_path(self, file_name: str | None, *, library: str | None = None) -> Path | None:
        if file_name is None:
            return None
        key = self._key(file_name, library)
        if key is None:
            return None
        return self._source_files.get(key)

    def text(self, file_name: str | None, *, library: str | None = None) -> str | None:
        if file_name is None:
            return None
        key = self._key(file_name, library)
        if key is None:
            return None
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        path = self._source_files[key]
        try:
            content = source_text_for_parse(path)
        except OSError:
            return None
        self._cache[key] = content
        return content

    def snippet(
        self,
        file_name: str | None,
        start: int | None,
        end: int | None,
        *,
        library: str | None = None,
    ) -> str | None:
        if file_name is None or start is None or end is None or end <= start:
            return None
        text = self.text(file_name, library=library)
        if text is None or start < 0 or end > len(text):
            return None
        return text[start:end]

    def line_count(self, file_name: str | None, *, library: str | None = None) -> int | None:
        text = self.text(file_name, library=library)
        if text is None:
            return None
        return text.count("\n") + (1 if text and not text.endswith("\n") else 0)

    def lines(
        self,
        file_name: str | None,
        start_line: int,
        end_line: int,
        *,
        library: str | None = None,
    ) -> str | None:
        """Return original source lines ``start_line``..``end_line`` inclusive."""
        if file_name is None:
            return None
        text = self.text(file_name, library=library)
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
        *,
        library: str | None = None,
    ) -> str | None:
        if file_name is None:
            return None
        snippet = self.snippet(file_name, start, end, library=library)
        if snippet is not None:
            return snippet
        if line is None:
            return None
        return self.lines(file_name, line, line, library=library)
