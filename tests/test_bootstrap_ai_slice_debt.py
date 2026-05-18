from __future__ import annotations

import json
import subprocess
from pathlib import Path

from tests.test_bootstrap_ai_slice import _write_templates, bootstrap_ai_slice


def test_bootstrap_slice_rejects_oversized_structural_debt_claim_without_reduction_intent(tmp_path):
    _write_templates(tmp_path)
    (tmp_path / "artifacts" / "analysis").mkdir(parents=True, exist_ok=True)
    (tmp_path / "artifacts" / "analysis" / "file_debt_ratchet.json").write_text(
        json.dumps(
            {
                "kind": "sattlint.file_debt_ratchet",
                "schema_version": 1,
                "files": {
                    "src/sattlint/app.py": {
                        "structural": {
                            "current_baseline": 891,
                            "target": 500,
                            "touch_rule": "must_shrink",
                            "reason": "Owner file must shrink before more feature work lands.",
                        }
                    }
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    config = bootstrap_ai_slice.BootstrapConfig(
        repo_root=tmp_path,
        task_id="app-menu-followup",
        title="App Menu Followup",
        owner="Planner",
        summary="Add one more CLI flow to the app owner file.",
        files=("src/sattlint/app.py",),
        validation=(
            '& ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_bootstrap_ai_slice.py -x -q --tb=short',
        ),
        branch="ai/task-app-menu-followup",
        worktree="../SattLint-ai-app-menu-followup",
        base_branch="main",
        source_ref="main",
        stage="executor",
        ledger_status="planned",
        notes="Bootstrapped from planning output.",
        task_contract_path=".ai/tasks/app-menu-followup.json",
        handoff_path=".ai/handoffs/app-menu-followup.json",
    )

    try:
        bootstrap_ai_slice.bootstrap_slice(config)
    except bootstrap_ai_slice.BootstrapError as exc:
        message = str(exc)
    else:
        raise AssertionError("Expected oversized structural debt bootstrap rejection.")

    assert "explicit decomposition or shrink slice" in message
    assert "src/sattlint/app.py (891 -> 500, touch rule: must_shrink)" in message


def test_bootstrap_slice_allows_oversized_structural_debt_claim_for_extraction_slice(tmp_path):
    _write_templates(tmp_path)
    (tmp_path / "artifacts" / "analysis").mkdir(parents=True, exist_ok=True)
    (tmp_path / "artifacts" / "analysis" / "file_debt_ratchet.json").write_text(
        json.dumps(
            {
                "kind": "sattlint.file_debt_ratchet",
                "schema_version": 1,
                "files": {
                    "src/sattlint/app.py": {
                        "structural": {
                            "current_baseline": 891,
                            "target": 500,
                            "touch_rule": "must_shrink",
                            "reason": "Owner file must shrink before more feature work lands.",
                        }
                    }
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    config = bootstrap_ai_slice.BootstrapConfig(
        repo_root=tmp_path,
        task_id="app-menu-extract",
        title="Extract App Menu Helpers",
        owner="Planner",
        summary="Extract app menu helpers into sibling modules so the owner file shrinks.",
        files=("src/sattlint/app.py",),
        validation=(
            '& ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_bootstrap_ai_slice.py -x -q --tb=short',
        ),
        branch="ai/task-app-menu-extract",
        worktree="../SattLint-ai-app-menu-extract",
        base_branch="main",
        source_ref="main",
        stage="executor",
        ledger_status="planned",
        notes="Decomposition slice for structural debt reduction.",
        task_contract_path=".ai/tasks/app-menu-extract.json",
        handoff_path=".ai/handoffs/app-menu-extract.json",
    )

    commands: list[tuple[str, ...]] = []

    def fake_git(repo_root: Path, args: tuple[str, ...]) -> subprocess.CompletedProcess[str]:
        commands.append(args)
        if args == ("worktree", "list", "--porcelain"):
            return subprocess.CompletedProcess(["git", *args], 0, stdout="", stderr="")
        if args == ("rev-parse", "--verify", "--quiet", "refs/heads/ai/task-app-menu-extract"):
            return subprocess.CompletedProcess(["git", *args], 1, stdout="", stderr="")
        if args == ("rev-parse", "--short", "HEAD"):
            return subprocess.CompletedProcess(["git", *args], 0, stdout="abc1234\n", stderr="")
        if args[0:2] == ("worktree", "add"):
            return subprocess.CompletedProcess(["git", *args], 0, stdout="", stderr="")
        raise AssertionError(f"Unexpected git command: {args!r}")

    result = bootstrap_ai_slice.bootstrap_slice(config, git_runner=fake_git)

    assert result["branch"] == "ai/task-app-menu-extract"
    assert commands[0] == ("worktree", "list", "--porcelain")


def test_bootstrap_slice_emits_request_contract_and_prompt_for_implement_plan(tmp_path):
    _write_templates(tmp_path)
    config = bootstrap_ai_slice.BootstrapConfig(
        repo_root=tmp_path,
        task_id="request-contract-bootstrap",
        title="Request Contract Bootstrap",
        owner="Planner",
        summary="Create an implement-plan contract that starts from the plan artifact.",
        files=("scripts/bootstrap_ai_slice.py", "tests/test_bootstrap_ai_slice.py"),
        validation=("pytest tests/test_bootstrap_ai_slice.py -x -q --tb=short",),
        branch="ai/task-request-contract-bootstrap",
        worktree="../SattLint-ai-request-contract-bootstrap",
        base_branch="main",
        source_ref="main",
        stage="executor",
        ledger_status="planned",
        notes="Bootstrapped from request contract output.",
        task_contract_path=".ai/tasks/request-contract-bootstrap.json",
        handoff_path=".ai/handoffs/request-contract-bootstrap.json",
        request_kind="implement-plan",
        request_artifact="docs/exec-plans/active/49-t-wave-7-ai-request-contracts-and-guidance-hardening.md",
    )

    def fake_git(repo_root: Path, args: tuple[str, ...]) -> subprocess.CompletedProcess[str]:
        if args == ("worktree", "list", "--porcelain"):
            return subprocess.CompletedProcess(["git", *args], 0, stdout="", stderr="")
        if args == ("rev-parse", "--verify", "--quiet", "refs/heads/ai/task-request-contract-bootstrap"):
            return subprocess.CompletedProcess(["git", *args], 1, stdout="", stderr="")
        if args == ("rev-parse", "--short", "HEAD"):
            return subprocess.CompletedProcess(["git", *args], 0, stdout="abc1234\n", stderr="")
        if args[0:2] == ("worktree", "add"):
            return subprocess.CompletedProcess(["git", *args], 0, stdout="", stderr="")
        raise AssertionError(f"Unexpected git command: {args!r}")

    result = bootstrap_ai_slice.bootstrap_slice(config, git_runner=fake_git)

    request_contract = json.loads(result["request_contract"])
    assert request_contract == {
        "request_kind": "implement-plan",
        "controlling_artifact": "docs/exec-plans/active/49-t-wave-7-ai-request-contracts-and-guidance-hardening.md",
        "requested_files": ["scripts/bootstrap_ai_slice.py", "tests/test_bootstrap_ai_slice.py"],
        "first_validation": "pytest tests/test_bootstrap_ai_slice.py -x -q --tb=short",
        "expected_outcome": "Create an implement-plan contract that starts from the plan artifact.",
        "success_criteria": [
            "Start from the controlling plan docs/exec-plans/active/49-t-wave-7-ai-request-contracts-and-guidance-hardening.md before broader repo exploration.",
            "Keep the scope anchored to the requested files: scripts/bootstrap_ai_slice.py, tests/test_bootstrap_ai_slice.py.",
            "Run the first validation command: pytest tests/test_bootstrap_ai_slice.py -x -q --tb=short.",
            "Deliver the expected outcome: Create an implement-plan contract that starts from the plan artifact..",
        ],
    }
    assert (
        "Start from: docs/exec-plans/active/49-t-wave-7-ai-request-contracts-and-guidance-hardening.md"
        in result["request_prompt"]
    )
    assert (
        "Expected outcome: Create an implement-plan contract that starts from the plan artifact."
        in result["request_prompt"]
    )

    task_contract = json.loads(
        (tmp_path / ".ai" / "tasks" / "request-contract-bootstrap.json").read_text(encoding="utf-8")
    )
    assert task_contract["acceptance_criteria"] == request_contract["success_criteria"]
