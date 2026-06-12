from __future__ import annotations

import sys
from pathlib import Path

import pytest

from scripts._python_runtime import resolve_repo_python


def test_resolve_repo_python_prefers_windows_venv(tmp_path: Path) -> None:
    windows_python = tmp_path / ".venv" / "Scripts" / "python.exe"
    windows_python.parent.mkdir(parents=True, exist_ok=True)
    windows_python.write_text("", encoding="utf-8")

    assert resolve_repo_python(tmp_path) == windows_python


def test_resolve_repo_python_prefers_posix_venv_when_windows_missing(tmp_path: Path) -> None:
    posix_python = tmp_path / ".venv" / "bin" / "python"
    posix_python.parent.mkdir(parents=True, exist_ok=True)
    posix_python.write_text("", encoding="utf-8")

    assert resolve_repo_python(tmp_path) == posix_python


def test_resolve_repo_python_falls_back_to_host_python(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(sys, "executable", "/usr/bin/host-python")

    assert resolve_repo_python(tmp_path) == Path("/usr/bin/host-python")
