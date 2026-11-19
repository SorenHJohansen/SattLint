"""Shared fixtures for the Textual app tests."""

from __future__ import annotations

import pytest

from sattlint.cli import startup as app_startup


@pytest.fixture
def noop_screen(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep terminal clears and pauses out of the app test output."""
    monkeypatch.setattr(app_startup, "clear_screen", lambda: None)
    monkeypatch.setattr(app_startup, "pause", lambda: None)
