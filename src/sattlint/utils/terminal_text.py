"""Sanitize untrusted project text before it reaches a human-facing sink.

Analyzer output, target names, module paths, and messages come from project
files and therefore from whoever wrote those files. A terminal and a rich-text
widget will act on control characters, so text that is printed verbatim can
move the cursor, change colors, or hide characters through a bidirectional
override. JSON and NDJSON are a machine contract and stay untouched.

The replacement is always a single ``?``: it is printable everywhere, keeps the
text length predictable, and makes an escape sequence visible instead of
letting it execute.
"""

from __future__ import annotations

import unicodedata

__all__ = ["sanitize_terminal_label", "sanitize_terminal_text"]

_REPLACEMENT = "?"

_C0_LIMIT = 0x1F
_DEL = 0x7F
_C1_START = 0x80
_C1_END = 0x9F


def _is_removed(char: str, *, keep_newlines: bool, keep_tabs: bool) -> bool:
    if char == "\n":
        return not keep_newlines
    if char == "\t":
        return not keep_tabs
    code = ord(char)
    if code <= _C0_LIMIT or code == _DEL:
        return True
    if _C1_START <= code <= _C1_END:
        return True
    return unicodedata.category(char) == "Cf"


def sanitize_terminal_text(
    text: str,
    *,
    keep_newlines: bool = False,
    keep_tabs: bool = False,
) -> str:
    """Return ``text`` with control and Unicode format characters neutralized.

    By default the result is a single line: C0 controls (including newline and
    tab), DEL, C1 controls, and Unicode format characters such as U+202E are
    replaced with ``?``. ``keep_newlines`` and ``keep_tabs`` preserve those two
    whitespace controls for a sink that expects them; every other character is
    still sanitized. Ordinary printable Unicode is unchanged.
    """
    if not text:
        return text
    return "".join(
        _REPLACEMENT if _is_removed(char, keep_newlines=keep_newlines, keep_tabs=keep_tabs) else char for char in text
    )


def sanitize_terminal_label(text: str) -> str:
    """Sanitize a single-line label such as a target, module, or finding name."""
    return sanitize_terminal_text(text)
