"""Console interaction primitives degrade on closed input."""

from __future__ import annotations

import builtins

import pytest

from sattlint.core import interaction


def test_pause_returns_when_stdin_is_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    def _closed(_prompt: str = "") -> str:
        raise EOFError

    monkeypatch.setattr(builtins, "input", _closed)

    interaction.pause()
