from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


def _load_repo_audit_precommit_module():
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "run_repo_audit_precommit.py"
    spec = importlib.util.spec_from_file_location("run_repo_audit_precommit", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


repo_audit_precommit = _load_repo_audit_precommit_module()


def test_describe_changed_files_truncates_preview():
    changed_files = [f"src/module_{index}.py" for index in range(repo_audit_precommit.MAX_CHANGED_FILE_PREVIEW + 2)]

    description = repo_audit_precommit._describe_changed_files(changed_files)

    assert description.startswith("changed files: 10 [src/module_0.py")
    assert "(+2 more)" in description


def test_main_skips_when_no_repo_audit_checks_are_recommended(monkeypatch, tmp_path, capsys):
    fake_script = tmp_path / "scripts" / "run_repo_audit_precommit.py"
    fake_script.parent.mkdir(parents=True)
    fake_script.write_text("# test stub\n", encoding="utf-8")
    monkeypatch.setattr(repo_audit_precommit, "__file__", str(fake_script))

    calls: list[dict[str, Any]] = []

    def fake_run(
        command: list[str],
        *,
        cwd: Path,
        env: dict[str, str],
        check: bool,
        text: bool,
        capture_output: bool,
    ):
        calls.append(
            {
                "command": command,
                "cwd": cwd,
                "env": env,
                "check": check,
                "text": text,
                "capture_output": capture_output,
            }
        )
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=json.dumps({"recommended_repo_audit_check_ids": []}),
            stderr="",
        )

    monkeypatch.setattr(repo_audit_precommit.subprocess, "run", fake_run)
    monkeypatch.setattr(
        repo_audit_precommit.sys,
        "argv",
        ["run_repo_audit_precommit.py", "src/sattlint/app.py", "tests/test_repo_audit_part1.py"],
    )

    exit_code = repo_audit_precommit.main()

    assert exit_code == 0
    assert len(calls) == 1
    assert calls[0]["cwd"] == tmp_path
    assert calls[0]["env"]["PYTHONUNBUFFERED"] == "1"
    assert calls[0]["capture_output"] is True
    assert calls[0]["command"][:4] == [
        sys.executable,
        "-u",
        "-m",
        "sattlint.devtools.repo_audit",
    ]
    assert calls[0]["command"][-4:] == [
        "--changed-file",
        "src/sattlint/app.py",
        "--changed-file",
        "tests/test_repo_audit_part1.py",
    ]

    output = capsys.readouterr().out
    assert "[repo-audit-slice] changed files: 2 [src/sattlint/app.py, tests/test_repo_audit_part1.py]" in output
    assert "[repo-audit-slice] recommending repo-audit-specific checks" in output
    assert "[repo-audit-slice] no repo-audit custom checks recommended; skipping" in output


def test_main_runs_only_recommended_repo_audit_checks(monkeypatch, tmp_path, capsys):
    fake_script = tmp_path / "scripts" / "run_repo_audit_precommit.py"
    fake_script.parent.mkdir(parents=True)
    fake_script.write_text("# test stub\n", encoding="utf-8")
    monkeypatch.setattr(repo_audit_precommit, "__file__", str(fake_script))

    calls: list[dict[str, Any]] = []

    def fake_run(
        command: list[str],
        *,
        cwd: Path,
        env: dict[str, str],
        check: bool,
        text: bool,
        capture_output: bool,
    ):
        calls.append(
            {
                "command": command,
                "cwd": cwd,
                "env": env,
                "check": check,
                "text": text,
                "capture_output": capture_output,
            }
        )
        if len(calls) == 1:
            return subprocess.CompletedProcess(
                command,
                0,
                stdout=json.dumps({"recommended_repo_audit_check_ids": ["cli-consistency", "documented-commands"]}),
                stderr="",
            )
        return subprocess.CompletedProcess(command, 1, stdout="", stderr="")

    monkeypatch.setattr(repo_audit_precommit.subprocess, "run", fake_run)
    monkeypatch.setattr(
        repo_audit_precommit.sys,
        "argv",
        ["run_repo_audit_precommit.py", "docs/references/cli-commands.md"],
    )

    exit_code = repo_audit_precommit.main()

    assert exit_code == 1
    assert len(calls) == 2
    assert calls[0]["capture_output"] is True
    assert calls[1]["capture_output"] is False
    assert calls[1]["command"] == [
        sys.executable,
        "-u",
        "-m",
        "sattlint.devtools.repo_audit",
        "--profile",
        "quick",
        "--fail-on",
        "high",
        "--skip-pipeline",
        "--output-dir",
        repo_audit_precommit.OUTPUT_DIR.as_posix(),
        "--check",
        "cli-consistency",
        "--check",
        "documented-commands",
        "--changed-file",
        "docs/references/cli-commands.md",
    ]

    output = capsys.readouterr().out
    assert "[repo-audit-slice] recommended repo-audit checks: cli-consistency, documented-commands" in output
    assert "[repo-audit-slice] running repo-audit custom checks without pipeline" in output
    assert "[repo-audit-slice] completed with exit code 1" in output
