from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


def _load_ai_edit_gate_module():
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "run_ai_edit_gate.py"
    spec = importlib.util.spec_from_file_location("run_ai_edit_gate", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


ai_edit_gate = _load_ai_edit_gate_module()


def _write_ratchet(tmp_path: Path) -> Path:
    ratchet_path = tmp_path / "metrics" / "ratchet.json"
    ratchet_path.parent.mkdir(parents=True, exist_ok=True)
    ratchet_path.write_text(
        json.dumps(
            {
                "required_paths": {
                    "docs": ["docs/repo-map.md"],
                    "vscode": [".vscode/settings.json"],
                    "ai": [".ai/tasks/task-contract.schema.json"],
                },
                "context_files": {
                    "auto_loaded": ["AGENTS.md"],
                    "scoped_globs": [".github/agents/*.agent.md"],
                },
            }
        ),
        encoding="utf-8",
    )
    return ratchet_path


def test_main_runs_ruff_fix_and_format_for_explicit_python_files(monkeypatch, tmp_path):
    python_file = tmp_path / "src" / "demo.py"
    python_file.parent.mkdir(parents=True, exist_ok=True)
    python_file.write_text("value = 1\n", encoding="utf-8")
    ratchet_path = _write_ratchet(tmp_path)

    monkeypatch.setattr(ai_edit_gate, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(ai_edit_gate, "RATCHET_PATH", ratchet_path)
    monkeypatch.setattr(ai_edit_gate, "_resolve_python", lambda _repo_root: Path("python"))

    commands: list[list[str]] = []

    def fake_run(command: list[str], cwd: Path, check: bool, **kwargs: Any):
        commands.append(command)
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(ai_edit_gate.subprocess, "run", fake_run)

    exit_code = ai_edit_gate.main(["src/demo.py"])

    assert exit_code == 0
    assert commands == [
        ["python", "-m", "ruff", "check", "--fix", "--select", "E,F,W,I", "--ignore", "E501", "src/demo.py"],
        ["python", "-m", "ruff", "format", "src/demo.py"],
        ["python", "-m", "pyright", "src/demo.py"],
        ["python", "-m", "sattlint.devtools.doc_gardener", "--check-only"],
        ["python", "-m", "sattlint.devtools.layer_linter"],
    ]


def test_main_runs_context_health_for_touched_ai_control_file(monkeypatch, tmp_path):
    ai_control_file = tmp_path / "docs" / "repo-map.md"
    ai_control_file.parent.mkdir(parents=True, exist_ok=True)
    ai_control_file.write_text("# Repo Map\n", encoding="utf-8")
    ratchet_path = _write_ratchet(tmp_path)

    monkeypatch.setattr(ai_edit_gate, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(ai_edit_gate, "RATCHET_PATH", ratchet_path)
    monkeypatch.setattr(ai_edit_gate, "_resolve_python", lambda _repo_root: Path("python"))

    commands: list[list[str]] = []

    def fake_run(command: list[str], cwd: Path, check: bool, **kwargs: Any):
        commands.append(command)
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(ai_edit_gate.subprocess, "run", fake_run)

    exit_code = ai_edit_gate.main(["docs/repo-map.md"])

    assert exit_code == 0
    assert commands == [["python", "scripts/context_health.py", "--check"]]


def test_main_syncs_exec_plans_for_touched_active_exec_plan(monkeypatch, tmp_path):
    plan_file = tmp_path / "docs" / "exec-plans" / "active" / "done.md"
    plan_file.parent.mkdir(parents=True, exist_ok=True)
    plan_file.write_text("# Done\n", encoding="utf-8")
    ratchet_path = _write_ratchet(tmp_path)

    monkeypatch.setattr(ai_edit_gate, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(ai_edit_gate, "RATCHET_PATH", ratchet_path)
    monkeypatch.setattr(ai_edit_gate, "_resolve_python", lambda _repo_root: Path("python"))

    commands: list[list[str]] = []

    def fake_run(command: list[str], cwd: Path, check: bool, **kwargs: Any):
        commands.append(command)
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(ai_edit_gate.subprocess, "run", fake_run)

    exit_code = ai_edit_gate.main(["docs/exec-plans/active/done.md"])

    assert exit_code == 0
    assert commands == [["python", "-m", "sattlint.devtools.ai_work_map", "--write"]]


def test_main_uses_git_diff_when_no_explicit_paths(monkeypatch, tmp_path):
    python_file = tmp_path / "src" / "demo.py"
    python_file.parent.mkdir(parents=True, exist_ok=True)
    python_file.write_text("value = 1\n", encoding="utf-8")
    ratchet_path = _write_ratchet(tmp_path)

    monkeypatch.setattr(ai_edit_gate, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(ai_edit_gate, "RATCHET_PATH", ratchet_path)
    monkeypatch.setattr(ai_edit_gate, "_resolve_python", lambda _repo_root: Path("python"))

    commands: list[list[str]] = []

    def fake_run(command: list[str], cwd: Path, check: bool, **kwargs: Any):
        commands.append(command)
        if command[:4] == ["git", "diff", "--name-only", "--diff-filter=ACMRTUXB"]:
            return subprocess.CompletedProcess(command, 0, stdout="src/demo.py\n", stderr="")
        if command[:4] == ["git", "ls-files", "--others", "--exclude-standard"]:
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(ai_edit_gate.subprocess, "run", fake_run)

    exit_code = ai_edit_gate.main([])

    assert exit_code == 0
    assert commands == [
        ["git", "diff", "--name-only", "--diff-filter=ACMRTUXB", "HEAD"],
        ["git", "ls-files", "--others", "--exclude-standard"],
        ["python", "-m", "ruff", "check", "--fix", "--select", "E,F,W,I", "--ignore", "E501", "src/demo.py"],
        ["python", "-m", "ruff", "format", "src/demo.py"],
        ["python", "-m", "pyright", "src/demo.py"],
        ["python", "-m", "sattlint.devtools.doc_gardener", "--check-only"],
        ["python", "-m", "sattlint.devtools.layer_linter"],
    ]
