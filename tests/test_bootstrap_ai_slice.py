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


def test_bootstrap_slice_creates_worktree_stubs_and_lock_state_from_templates(tmp_path):
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
        source_ref="main",
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
    assert result["lock_state"] == ".git/sattlint-ai-coordination/current_work_lock.json"
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

    assert not (tmp_path / ".github" / "coordination" / "current-work.md").exists()

    lock_state = json.loads(
        bootstrap_ai_slice.coordination_lock_state.lock_state_path(tmp_path).read_text(encoding="utf-8")
    )
    assert list(lock_state) == ["workstreams"]
    assert lock_state["workstreams"] == [
        {
            "workstream_id": "phase-3-bootstrap",
            "owner": "Planner",
            "status": "planned",
            "claimed_paths": [
                "scripts/bootstrap_ai_slice.py",
                ".vscode/tasks.json",
                ".ai/tasks/phase-3-bootstrap.json",
                ".ai/handoffs/phase-3-bootstrap.json",
            ],
            "updated_at": lock_state["workstreams"][0]["updated_at"],
            "first_validation": '& ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_bootstrap_ai_slice.py -x -q --tb=short',
        }
    ]
    assert lock_state["workstreams"][0]["updated_at"].endswith("Z")


def test_bootstrap_slice_updates_existing_entry_skips_worktree_add_and_removes_legacy_ledger(tmp_path):
    _write_templates(tmp_path)
    legacy_ledger_path = tmp_path / ".github" / "coordination" / "current-work.md"
    legacy_ledger_path.write_text(
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
        source_ref="main",
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

    assert not legacy_ledger_path.exists()

    lock_state = json.loads(
        bootstrap_ai_slice.coordination_lock_state.lock_state_path(tmp_path).read_text(encoding="utf-8")
    )
    assert lock_state["workstreams"][0]["workstream_id"] == "phase-3-bootstrap"
    assert lock_state["workstreams"][0]["status"] == "planned"
    assert lock_state["workstreams"][0]["claimed_paths"] == [
        "scripts/bootstrap_ai_slice.py",
        ".vscode/tasks.json",
        ".ai/tasks/phase-3-bootstrap.json",
        ".ai/handoffs/phase-3-bootstrap.json",
    ]


def test_bootstrap_main_returns_failure_when_bootstrap_write_fails(monkeypatch, capsys):
    monkeypatch.setattr(bootstrap_ai_slice, "_collect_config", lambda _args: object())
    monkeypatch.setattr(
        bootstrap_ai_slice,
        "bootstrap_slice",
        lambda _config: (_ for _ in ()).throw(PermissionError("read-only filesystem")),
    )

    exit_code = bootstrap_ai_slice.main([])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.out == ""
    assert "bootstrap-ai-slice: read-only filesystem" in captured.err


def test_load_lock_state_prunes_stale_entries_without_artifacts_or_worktrees(tmp_path):
    _write_templates(tmp_path)
    supported_task_path = tmp_path / ".ai" / "tasks" / "supported-entry.json"
    supported_task_path.write_text("{}\n", encoding="utf-8")

    lock_state_path = bootstrap_ai_slice.coordination_lock_state.lock_state_path(tmp_path)
    lock_state_path.parent.mkdir(parents=True, exist_ok=True)
    lock_state_path.write_text(
        json.dumps(
            {
                "workstreams": [
                    {
                        "workstream_id": "stale-legacy-entry",
                        "owner": "Copilot",
                        "status": "active",
                        "claimed_paths": [
                            ".github/coordination/current_work_lock.json",
                            "src/stale_legacy.py",
                        ],
                        "updated_at": "2026-05-01T00:00:00Z",
                        "first_validation": "pytest stale legacy",
                    },
                    {
                        "workstream_id": "stale-unbacked-entry",
                        "owner": "Copilot",
                        "status": "active",
                        "claimed_paths": ["src/stale_unbacked.py"],
                        "updated_at": "2026-05-01T00:00:00Z",
                        "first_validation": "pytest stale unbacked",
                    },
                    {
                        "workstream_id": "supported-entry",
                        "owner": "Copilot",
                        "status": "active",
                        "claimed_paths": ["src/supported.py"],
                        "updated_at": "2026-05-01T00:00:00Z",
                        "first_validation": "pytest supported",
                    },
                ]
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    entries = bootstrap_ai_slice.coordination_lock_state.load_lock_state(tmp_path)

    assert [entry["workstream_id"] for entry in entries] == ["supported-entry"]
    persisted = json.loads(lock_state_path.read_text(encoding="utf-8"))
    assert [entry["workstream_id"] for entry in persisted["workstreams"]] == ["supported-entry"]


def test_load_lock_state_keeps_recent_unbacked_entry(tmp_path):
    _write_templates(tmp_path)
    lock_state_path = bootstrap_ai_slice.coordination_lock_state.lock_state_path(tmp_path)
    lock_state_path.parent.mkdir(parents=True, exist_ok=True)
    lock_state_path.write_text(
        json.dumps(
            {
                "workstreams": [
                    {
                        "workstream_id": "recent-manual-entry",
                        "owner": "Copilot",
                        "status": "active",
                        "claimed_paths": ["src/recent_manual.py"],
                        "updated_at": bootstrap_ai_slice.coordination_lock_state.utc_now_timestamp(),
                        "first_validation": "pytest recent manual",
                    }
                ]
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    entries = bootstrap_ai_slice.coordination_lock_state.load_lock_state(tmp_path)

    assert [entry["workstream_id"] for entry in entries] == ["recent-manual-entry"]


def test_load_lock_state_returns_empty_for_malformed_json(tmp_path):
    _write_templates(tmp_path)
    lock_state_path = bootstrap_ai_slice.coordination_lock_state.lock_state_path(tmp_path)
    lock_state_path.parent.mkdir(parents=True, exist_ok=True)
    lock_state_path.write_text("{bad-json", encoding="utf-8")

    assert bootstrap_ai_slice.coordination_lock_state.load_lock_state(tmp_path) == []
