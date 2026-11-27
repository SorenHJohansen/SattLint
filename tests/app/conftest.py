"""Shared fixtures for the Textual app tests."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from sattlint.cli import startup as app_startup


@pytest.fixture
def noop_screen(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep terminal clears and pauses out of the app test output."""
    monkeypatch.setattr(app_startup, "clear_screen", lambda: None)
    monkeypatch.setattr(app_startup, "pause", lambda: None)


@pytest.fixture(autouse=True)
def _isolate_working_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Run each app test inside its own directory.

    Several tests hand the analysis paths a relative cache root; without this
    they create ``cache-dir`` style directories inside the checkout.
    """
    monkeypatch.chdir(tmp_path)
    yield
