"""Bundled static assets for SattLint (e.g. the SQHJ banner).

Assets are read on first use with a fallback: a packaging fault must not stop
the shell from starting, because the text is decoration, not data.
"""

from __future__ import annotations

from importlib.resources import files

_NO_BREAK_SPACE = "\u00a0"


def text_asset(name: str) -> str:
    """Return a bundled text asset, normalized for terminal display.

    A missing or unreadable asset yields an empty string so callers can render
    the surrounding content without special casing.
    """
    try:
        raw = files(__package__ or "sattlint.assets").joinpath(name).read_text(encoding="utf-8")
    except (OSError, ModuleNotFoundError):
        return ""
    return raw.replace(_NO_BREAK_SPACE, " ").strip("\n")


def sqhj_banner() -> str:
    """The ASCII banner shown in the shell's about text."""
    return text_asset("sqhj")


__all__ = ["sqhj_banner", "text_asset"]
