# pyright: reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportPrivateUsage=false
from __future__ import annotations

import subprocess
from pathlib import Path

from scripts import run_actionlint


def test_resolve_command_prefers_native_actionlint(monkeypatch) -> None:
    monkeypatch.setattr(run_actionlint.shutil, "which", lambda name: "actionlint.exe" if name == "actionlint" else None)

    command, cwd = run_actionlint._resolve_command([".github/workflows/ci.yml"])

    assert command == ["actionlint", "-color", ".github/workflows/ci.yml"]
    assert cwd == run_actionlint.REPO_ROOT


def test_resolve_command_uses_wsl_actionlint(monkeypatch) -> None:
    monkeypatch.setattr(run_actionlint.sys, "platform", "win32")
    monkeypatch.setattr(
        run_actionlint.shutil,
        "which",
        lambda name: "wsl.exe" if name == "wsl" else None,
    )
    monkeypatch.setattr(run_actionlint, "_wsl_has_command", lambda command_name: command_name == "actionlint")
    monkeypatch.setattr(run_actionlint, "_find_actionlint", lambda: None)

    command, cwd = run_actionlint._resolve_command([r".github\workflows\ci.yml"])

    assert command == [
        "wsl",
        "--cd",
        run_actionlint._windows_path_to_wsl(run_actionlint.REPO_ROOT),
        "actionlint",
        "-color",
        ".github/workflows/ci.yml",
    ]
    assert cwd is None


def test_main_returns_tool_exit_code(monkeypatch) -> None:
    monkeypatch.setattr(
        run_actionlint,
        "_resolve_command",
        lambda tool_args: (["actionlint", *tool_args], Path("repo-root")),
    )
    monkeypatch.setattr(
        run_actionlint.subprocess,
        "run",
        lambda command, cwd, check: subprocess.CompletedProcess(command, 1),
    )

    result = run_actionlint.main([".github/workflows/ci.yml"])

    assert result == 1


def test_resolve_command_falls_back_to_local_bin(monkeypatch) -> None:
    monkeypatch.setattr(run_actionlint.shutil, "which", lambda name: None)
    local_bin = run_actionlint.Path.home() / ".local" / "bin" / "actionlint"
    monkeypatch.setattr(run_actionlint.Path, "is_file", lambda self: str(self) == str(local_bin))

    command, cwd = run_actionlint._resolve_command([".github/workflows/ci.yml"])

    assert command == [str(local_bin), "-color", ".github/workflows/ci.yml"]
    assert cwd == run_actionlint.REPO_ROOT


def test_main_returns_2_when_unavailable(monkeypatch, capsys) -> None:
    monkeypatch.setattr(run_actionlint, "_resolve_command", lambda tool_args: ([], None))

    result = run_actionlint.main([".github/workflows/ci.yml"])

    assert result == 2
    assert capsys.readouterr().err == ""
