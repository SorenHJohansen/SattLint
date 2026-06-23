# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false
from __future__ import annotations

import json
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import cast

from sattlint.devtools import release_smoke


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_run_release_smoke_writes_success_reports(tmp_path: Path) -> None:
    wheel_path = tmp_path / "dist" / "sattlint-2026.5-py3-none-any.whl"
    sample_path = tmp_path / "tests" / "fixtures" / "sample.s"
    output_dir = tmp_path / "artifacts" / "release-smoke"
    wheel_path.parent.mkdir(parents=True, exist_ok=True)
    sample_path.parent.mkdir(parents=True, exist_ok=True)
    wheel_path.write_bytes(b"wheel")
    sample_path.write_text("sample", encoding="utf-8")

    commands: list[tuple[str, ...]] = []

    def fake_create_virtualenv(venv_dir: Path) -> None:
        (venv_dir / "bin").mkdir(parents=True, exist_ok=True)

    def fake_run(
        command: Sequence[str],
        *,
        cwd: Path,
        env: Mapping[str, str],
        text: bool,
        capture_output: bool,
        check: bool,
        timeout: float | None,
    ) -> subprocess.CompletedProcess[str]:
        assert cwd == tmp_path.resolve()
        assert env["PIP_DISABLE_PIP_VERSION_CHECK"] == "1"
        assert text is True
        assert capture_output is True
        assert check is False
        commands.append(tuple(command))
        if Path(command[0]).stem == "sattlint-lsp":
            raise subprocess.TimeoutExpired(command, timeout if timeout is not None else 1.0)
        return subprocess.CompletedProcess(list(command), 0, stdout="ok", stderr="")

    exit_code = release_smoke.run_release_smoke(
        wheel=wheel_path,
        sample_file=sample_path,
        output_dir=output_dir,
        repo_root=tmp_path,
        run_command=fake_run,
        create_virtualenv=fake_create_virtualenv,
    )

    assert exit_code == 0
    assert [command[1:4] for command in commands[:1]] == [("-m", "pip", "install")]
    assert commands[1][-1] == release_smoke.LSP_RUNTIME_DEPENDENCIES[0]
    assert commands[2][-1] == "--version"
    assert commands[3][-2:] == ("syntax-check", str(sample_path.resolve()))
    assert commands[4][-3:] == ("--profile", "full", "--list-checks")
    assert commands[4][1] == "repo-audit"
    assert Path(commands[5][0]).stem == "sattlint-lsp"

    status_report = _read_json(output_dir / "status.json")
    summary_report = _read_json(output_dir / "summary.json")

    assert status_report["overall_status"] == "pass"
    assert status_report["failing_steps"] == []
    assert status_report["pending_steps"] == []
    step_statuses = cast(dict[str, object], status_report["step_statuses"])
    lsp_status = cast(dict[str, object], step_statuses["lsp_boot"])
    assert lsp_status["timed_out"] is True
    assert summary_report["status"] == {
        "overall_status": "pass",
        "failing_steps": [],
        "pending_steps": [],
    }
    steps = cast(list[object], summary_report["steps"])
    assert isinstance(steps, list)
    assert len(steps) == 6


def test_run_release_smoke_stops_after_first_failure(tmp_path: Path) -> None:
    wheel_path = tmp_path / "dist" / "sattlint-2026.5-py3-none-any.whl"
    sample_path = tmp_path / "tests" / "fixtures" / "sample.s"
    output_dir = tmp_path / "artifacts" / "release-smoke"
    wheel_path.parent.mkdir(parents=True, exist_ok=True)
    sample_path.parent.mkdir(parents=True, exist_ok=True)
    wheel_path.write_bytes(b"wheel")
    sample_path.write_text("sample", encoding="utf-8")

    step_index = 0

    def fake_create_virtualenv(venv_dir: Path) -> None:
        (venv_dir / "bin").mkdir(parents=True, exist_ok=True)

    def fake_run(
        command: Sequence[str],
        *,
        cwd: Path,
        env: Mapping[str, str],
        text: bool,
        capture_output: bool,
        check: bool,
        timeout: float | None,
    ) -> subprocess.CompletedProcess[str]:
        nonlocal step_index
        step_index += 1
        exit_code = 0 if step_index < 3 else 1
        return subprocess.CompletedProcess(list(command), exit_code, stdout="", stderr="failed")

    exit_code = release_smoke.run_release_smoke(
        wheel=wheel_path,
        sample_file=sample_path,
        output_dir=output_dir,
        repo_root=tmp_path,
        run_command=fake_run,
        create_virtualenv=fake_create_virtualenv,
    )

    assert exit_code == 1

    status_report = _read_json(output_dir / "status.json")
    summary_report = _read_json(output_dir / "summary.json")

    assert status_report["overall_status"] == "fail"
    assert status_report["failing_steps"] == ["cli_version"]
    assert status_report["pending_steps"] == ["syntax_check", "repo_audit_boot", "lsp_boot"]
    steps = cast(list[object], summary_report["steps"])
    assert isinstance(steps, list)
    assert len(steps) == 3


def test_run_release_smoke_returns_failure_when_output_dir_cannot_be_created(tmp_path: Path, capsys) -> None:
    wheel_path = tmp_path / "dist" / "sattlint-2026.5-py3-none-any.whl"
    sample_path = tmp_path / "tests" / "fixtures" / "sample.s"
    blocked_parent = tmp_path / "artifacts"
    output_dir = blocked_parent / "release-smoke"
    wheel_path.parent.mkdir(parents=True, exist_ok=True)
    sample_path.parent.mkdir(parents=True, exist_ok=True)
    wheel_path.write_bytes(b"wheel")
    sample_path.write_text("sample", encoding="utf-8")
    blocked_parent.write_text("not-a-directory", encoding="utf-8")

    exit_code = release_smoke.run_release_smoke(
        wheel=wheel_path,
        sample_file=sample_path,
        output_dir=output_dir,
        repo_root=tmp_path,
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "release smoke output error" in captured.err
    assert not (output_dir / "status.json").exists()
