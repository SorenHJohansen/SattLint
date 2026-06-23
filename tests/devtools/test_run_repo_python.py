from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

from scripts import run_repo_python


def _resolved_python(repo_root: Path) -> Path:
    del repo_root
    return Path("/tmp/repo-python")


def test_main_preserves_passthrough_mode(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    recorded: dict[str, object] = {}

    def fake_run(
        command: list[str],
        cwd: Path,
        check: bool,
        capture_output: bool = False,
        text: bool = False,
    ) -> subprocess.CompletedProcess[Any]:
        recorded["command"] = command
        recorded["cwd"] = cwd
        recorded["check"] = check
        recorded["capture_output"] = capture_output
        recorded["text"] = text
        return subprocess.CompletedProcess(command, 7)

    monkeypatch.setattr(run_repo_python, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(run_repo_python, "_resolve_python", _resolved_python)
    monkeypatch.setattr(run_repo_python.subprocess, "run", fake_run)

    exit_code = run_repo_python.main(["-m", "pytest"], env={})

    assert exit_code == 7
    assert recorded == {
        "command": [str(_resolved_python(tmp_path)), "-m", "pytest"],
        "cwd": tmp_path,
        "check": False,
        "capture_output": False,
        "text": False,
    }


def test_main_capture_mode_writes_stdout_stderr_and_exit(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    artifact_dir = tmp_path / "artifacts"

    def fake_run(
        command: list[str],
        cwd: Path,
        capture_output: bool,
        text: bool,
        check: bool,
    ) -> subprocess.CompletedProcess[str]:
        del cwd, capture_output, text, check
        return subprocess.CompletedProcess(command, 0, stdout="hello\n", stderr="warning\n")

    monkeypatch.setattr(run_repo_python, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(run_repo_python, "_resolve_python", _resolved_python)
    monkeypatch.setattr(run_repo_python.subprocess, "run", fake_run)

    exit_code = run_repo_python.main(
        ["-c", "print('hello')"],
        env={
            run_repo_python.ARTIFACT_DIR_ENV: str(artifact_dir),
            run_repo_python.ARTIFACT_PREFIX_ENV: "capture",
        },
    )

    assert exit_code == 0
    assert (artifact_dir / "capture.stdout").read_text(encoding="utf-8") == "hello\n"
    assert (artifact_dir / "capture.stderr").read_text(encoding="utf-8") == "warning\n"
    assert (artifact_dir / "capture.exit").read_text(encoding="utf-8") == "0\n"


def test_main_capture_mode_preserves_nonzero_child_exit(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    artifact_dir = tmp_path / "artifacts"

    def fake_run(
        command: list[str],
        cwd: Path,
        capture_output: bool,
        text: bool,
        check: bool,
    ) -> subprocess.CompletedProcess[str]:
        del cwd, capture_output, text, check
        return subprocess.CompletedProcess(command, 5, stdout="failed-output\n", stderr="failed-error\n")

    monkeypatch.setattr(run_repo_python, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(run_repo_python, "_resolve_python", _resolved_python)
    monkeypatch.setattr(run_repo_python.subprocess, "run", fake_run)

    exit_code = run_repo_python.main(
        ["-c", "raise SystemExit(5)"],
        env={
            run_repo_python.ARTIFACT_DIR_ENV: str(artifact_dir),
            run_repo_python.ARTIFACT_PREFIX_ENV: "failed-run",
        },
    )

    assert exit_code == 5
    assert (artifact_dir / "failed-run.stdout").read_text(encoding="utf-8") == "failed-output\n"
    assert (artifact_dir / "failed-run.stderr").read_text(encoding="utf-8") == "failed-error\n"
    assert (artifact_dir / "failed-run.exit").read_text(encoding="utf-8") == "5\n"


def test_main_rejects_invalid_capture_env_without_spawning_child(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(run_repo_python, "REPO_ROOT", tmp_path)

    def fail_run(*args: object, **kwargs: object) -> None:
        raise AssertionError("subprocess.run should not be called")

    monkeypatch.setattr(run_repo_python.subprocess, "run", fail_run)

    exit_code = run_repo_python.main(
        ["-m", "pytest"],
        env={run_repo_python.ARTIFACT_DIR_ENV: "captured-artifacts"},
    )

    captured = capsys.readouterr()
    assert exit_code == 2
    assert run_repo_python.ARTIFACT_PREFIX_ENV in captured.err


def test_main_reports_artifact_write_failures(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:

    def fake_run(
        command: list[str],
        cwd: Path,
        capture_output: bool,
        text: bool,
        check: bool,
    ) -> subprocess.CompletedProcess[str]:
        del cwd, capture_output, text, check
        return subprocess.CompletedProcess(command, 0, stdout="hello\n", stderr="warning")

    monkeypatch.setattr(run_repo_python, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(run_repo_python, "_resolve_python", _resolved_python)
    monkeypatch.setattr(run_repo_python.subprocess, "run", fake_run)

    def fail_write(path: Path, content: str) -> None:
        raise OSError(f"disk full for {path.name}")

    monkeypatch.setattr(run_repo_python, "write_text_artifact", fail_write)

    exit_code = run_repo_python.main(
        ["-c", "print('hello')"],
        env={
            run_repo_python.ARTIFACT_DIR_ENV: str(tmp_path / "artifacts"),
            run_repo_python.ARTIFACT_PREFIX_ENV: "capture",
        },
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.out == "hello\n"
    assert "warning" in captured.err
    assert "failed to write capture artifacts" in captured.err
    assert "capture" in captured.err
