from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


def _load_bootstrap_module():
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "bootstrap_ai_slice.py"
    spec = importlib.util.spec_from_file_location("bootstrap_ai_slice", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


bootstrap_ai_slice = _load_bootstrap_module()


def _write_templates(tmp_path: Path) -> None:
    (tmp_path / ".ai" / "tasks").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".ai" / "handoffs").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".github" / "coordination").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".ai" / "tasks" / "task-contract.example.json").write_text(
        json.dumps(
            {
                "task_id": "example",
                "title": "Example",
                "owner": "Example Agent",
                "stage": "executor",
                "branch": "ai/task-example",
                "worktree": "../SattLint-ai-example",
                "summary": "Example summary for one slice.",
                "files": ["src/example.py"],
                "acceptance_criteria": ["Replace me"],
                "risks": ["Replace me"],
                "validation": ["pytest tests/test_example.py -x -q --tb=short"],
                "status": "draft",
                "handoff_path": ".ai/handoffs/example.json",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / ".ai" / "handoffs" / "handoff.example.json").write_text(
        json.dumps(
            {
                "task_id": "example",
                "stage": "executor",
                "branch": "ai/task-example",
                "commit": "abc1234",
                "files_changed": ["src/example.py"],
                "summary": "Example handoff summary.",
                "known_risks": ["Replace me"],
                "required_tests": ["pytest tests/test_example.py -x -q --tb=short"],
                "validation_status": {
                    "state": "pending",
                    "commands": ["pytest tests/test_example.py -x -q --tb=short"],
                    "notes": ["Replace me"],
                },
                "reviewer_notes": [],
                "status": "draft",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / ".github" / "coordination" / "current-work.template.md").write_text(
        "# Coverage Campaign Progress\n\n## Active Workstreams\n",
        encoding="utf-8",
    )


def test_bootstrap_slice_creates_worktree_stubs_and_ledger_from_templates(tmp_path):
    _write_templates(tmp_path)
    config = bootstrap_ai_slice.BootstrapConfig(
        repo_root=tmp_path,
        task_id="phase-3-bootstrap",
        title="Phase 3 Bootstrap",
        owner="Planner",
        summary="Bootstrap one explicit slice from planning output.",
        files=("scripts/bootstrap_ai_slice.py", ".vscode/tasks.json"),
        validation=(
            '& ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_bootstrap_ai_slice.py -x -q --tb=short',
        ),
        branch="ai/task-phase-3-bootstrap",
        worktree="../SattLint-ai-phase-3-bootstrap",
        base_branch="main",
        stage="executor",
        ledger_status="planned",
        notes="Bootstrapped from planning output.",
        task_contract_path=".ai/tasks/phase-3-bootstrap.json",
        handoff_path=".ai/handoffs/phase-3-bootstrap.json",
    )

    commands: list[tuple[str, ...]] = []

    def fake_git(repo_root: Path, args: tuple[str, ...]) -> subprocess.CompletedProcess[str]:
        commands.append(args)
        if args == ("worktree", "list", "--porcelain"):
            return subprocess.CompletedProcess(["git", *args], 0, stdout="", stderr="")
        if args == ("rev-parse", "--verify", "--quiet", "refs/heads/ai/task-phase-3-bootstrap"):
            return subprocess.CompletedProcess(["git", *args], 1, stdout="", stderr="")
        if args == ("rev-parse", "--short", "HEAD"):
            return subprocess.CompletedProcess(["git", *args], 0, stdout="abc1234\n", stderr="")
        if args[0:2] == ("worktree", "add"):
            return subprocess.CompletedProcess(["git", *args], 0, stdout="", stderr="")
        raise AssertionError(f"Unexpected git command: {args!r}")

    result = bootstrap_ai_slice.bootstrap_slice(config, git_runner=fake_git)

    assert result["branch"] == "ai/task-phase-3-bootstrap"
    assert result["task_contract"] == ".ai/tasks/phase-3-bootstrap.json"
    assert result["handoff"] == ".ai/handoffs/phase-3-bootstrap.json"
    assert commands == [
        ("worktree", "list", "--porcelain"),
        ("rev-parse", "--verify", "--quiet", "refs/heads/ai/task-phase-3-bootstrap"),
        (
            "worktree",
            "add",
            (tmp_path.parent / "SattLint-ai-phase-3-bootstrap").resolve().as_posix(),
            "-b",
            "ai/task-phase-3-bootstrap",
            "main",
        ),
        ("rev-parse", "--short", "HEAD"),
    ]

    task_contract = json.loads((tmp_path / ".ai" / "tasks" / "phase-3-bootstrap.json").read_text(encoding="utf-8"))
    assert task_contract == {
        "task_id": "phase-3-bootstrap",
        "title": "Phase 3 Bootstrap",
        "owner": "Planner",
        "stage": "executor",
        "branch": "ai/task-phase-3-bootstrap",
        "worktree": "../SattLint-ai-phase-3-bootstrap",
        "summary": "Bootstrap one explicit slice from planning output.",
        "files": ["scripts/bootstrap_ai_slice.py", ".vscode/tasks.json"],
        "acceptance_criteria": [],
        "risks": [],
        "validation": [
            '& ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_bootstrap_ai_slice.py -x -q --tb=short'
        ],
        "status": "draft",
        "handoff_path": ".ai/handoffs/phase-3-bootstrap.json",
    }

    handoff = json.loads((tmp_path / ".ai" / "handoffs" / "phase-3-bootstrap.json").read_text(encoding="utf-8"))
    assert handoff == {
        "task_id": "phase-3-bootstrap",
        "stage": "executor",
        "branch": "ai/task-phase-3-bootstrap",
        "commit": "abc1234",
        "files_changed": ["scripts/bootstrap_ai_slice.py", ".vscode/tasks.json"],
        "summary": "Scoped executor handoff stub for Phase 3 Bootstrap.",
        "known_risks": [],
        "required_tests": [
            '& ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_bootstrap_ai_slice.py -x -q --tb=short'
        ],
        "validation_status": {
            "state": "pending",
            "commands": [
                '& ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_bootstrap_ai_slice.py -x -q --tb=short'
            ],
            "notes": [
                "Replace placeholder scope, files_changed, and validation commands before handing off to Test Agent or Reviewer Agent."
            ],
        },
        "reviewer_notes": [],
        "status": "draft",
    }

    ledger = (tmp_path / ".github" / "coordination" / "current-work.md").read_text(encoding="utf-8")
    assert "### Workstream phase-3-bootstrap" in ledger
    assert "- Owner: Planner" in ledger
    assert "- Status: planned" in ledger
    assert "`.ai/tasks/phase-3-bootstrap.json`" in ledger
    assert "`.ai/handoffs/phase-3-bootstrap.json`" in ledger


def test_bootstrap_slice_updates_existing_entry_and_skips_worktree_add_when_present(tmp_path):
    _write_templates(tmp_path)
    ledger_path = tmp_path / ".github" / "coordination" / "current-work.md"
    ledger_path.write_text(
        "# Coverage Campaign Progress\n\n## Active Workstreams\n\n### Workstream phase-3-bootstrap\n\n- Owner: Old Owner\n- Goal: Old summary\n- Claims: `old/file.py`\n- First validation: pytest old\n- Status: blocked\n- Notes: stale\n",
        encoding="utf-8",
    )
    existing_task_path = tmp_path / ".ai" / "tasks" / "phase-3-bootstrap.json"
    existing_task_path.write_text(
        json.dumps(
            {
                "task_id": "phase-3-bootstrap",
                "title": "Old Title",
                "owner": "Old Owner",
                "stage": "executor",
                "branch": "ai/task-phase-3-bootstrap",
                "worktree": "../SattLint-ai-phase-3-bootstrap",
                "summary": "Old summary for one slice.",
                "files": ["old/file.py"],
                "acceptance_criteria": ["Keep me"],
                "risks": ["Keep me"],
                "validation": ["pytest old"],
                "status": "active",
                "handoff_path": ".ai/handoffs/phase-3-bootstrap.json",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    existing_handoff_path = tmp_path / ".ai" / "handoffs" / "phase-3-bootstrap.json"
    existing_handoff_path.write_text(
        json.dumps(
            {
                "task_id": "phase-3-bootstrap",
                "stage": "executor",
                "branch": "ai/task-phase-3-bootstrap",
                "commit": "deadbee",
                "files_changed": ["old/file.py"],
                "summary": "Old handoff summary.",
                "known_risks": ["Keep me"],
                "required_tests": ["pytest old"],
                "validation_status": {"state": "failed", "commands": ["pytest old"], "notes": ["Keep me"]},
                "reviewer_notes": ["Keep me"],
                "status": "validated",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    config = bootstrap_ai_slice.BootstrapConfig(
        repo_root=tmp_path,
        task_id="phase-3-bootstrap",
        title="Phase 3 Bootstrap",
        owner="Planner",
        summary="Bootstrap one explicit slice from planning output.",
        files=("scripts/bootstrap_ai_slice.py", ".vscode/tasks.json"),
        validation=(
            '& ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_bootstrap_ai_slice.py -x -q --tb=short',
        ),
        branch="ai/task-phase-3-bootstrap",
        worktree="../SattLint-ai-phase-3-bootstrap",
        base_branch="main",
        stage="executor",
        ledger_status="planned",
        notes="Bootstrapped from planning output.",
        task_contract_path=".ai/tasks/phase-3-bootstrap.json",
        handoff_path=".ai/handoffs/phase-3-bootstrap.json",
    )

    expected_worktree = (tmp_path.parent / "SattLint-ai-phase-3-bootstrap").resolve().as_posix()

    def fake_git(repo_root: Path, args: tuple[str, ...]) -> subprocess.CompletedProcess[str]:
        if args == ("worktree", "list", "--porcelain"):
            return subprocess.CompletedProcess(
                ["git", *args],
                0,
                stdout=(f"worktree {expected_worktree}\nbranch refs/heads/ai/task-phase-3-bootstrap\n\n"),
                stderr="",
            )
        if args == ("rev-parse", "--short", "HEAD"):
            return subprocess.CompletedProcess(["git", *args], 0, stdout="abc1234\n", stderr="")
        raise AssertionError(f"Unexpected git command: {args!r}")

    bootstrap_ai_slice.bootstrap_slice(config, git_runner=fake_git)

    task_contract = json.loads(existing_task_path.read_text(encoding="utf-8"))
    assert task_contract["acceptance_criteria"] == ["Keep me"]
    assert task_contract["risks"] == ["Keep me"]
    assert task_contract["status"] == "draft"
    assert task_contract["files"] == ["scripts/bootstrap_ai_slice.py", ".vscode/tasks.json"]

    handoff = json.loads(existing_handoff_path.read_text(encoding="utf-8"))
    assert handoff["known_risks"] == ["Keep me"]
    assert handoff["reviewer_notes"] == ["Keep me"]
    assert handoff["validation_status"]["notes"] == ["Keep me"]
    assert handoff["status"] == "draft"

    ledger = ledger_path.read_text(encoding="utf-8")
    assert ledger.count("### Workstream phase-3-bootstrap") == 1
    assert "- Owner: Planner" in ledger
    assert "- Status: planned" in ledger
