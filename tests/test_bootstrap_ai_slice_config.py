from __future__ import annotations

import json
import subprocess
from pathlib import Path

from . import test_bootstrap_ai_slice as original

bootstrap_ai_slice = original.bootstrap_ai_slice
_write_templates = original._write_templates


def test_collect_config_uses_stage_defaults_and_handoff_commit_for_review(tmp_path):
    _write_templates(tmp_path)
    handoff_path = tmp_path / ".ai" / "handoffs" / "phase-3-bootstrap.json"
    handoff_path.write_text(
        json.dumps(
            {
                "task_id": "phase-3-bootstrap",
                "stage": "executor",
                "branch": "ai/task-phase-3-bootstrap",
                "commit": "feed123",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    args = bootstrap_ai_slice.build_parser().parse_args(
        [
            "--repo-root",
            str(tmp_path),
            "--task-id",
            "phase-3-bootstrap",
            "--title",
            "Phase 3 Bootstrap",
            "--owner",
            "Reviewer Agent",
            "--summary",
            "Review the executor slice.",
            "--file",
            "scripts/bootstrap_ai_slice.py",
            "--validation",
            "pytest tests/test_bootstrap_ai_slice.py -x -q --tb=short",
            "--stage",
            "review",
            "--from-handoff",
            ".ai/handoffs/phase-3-bootstrap.json",
        ]
    )

    config = bootstrap_ai_slice._collect_config(args)

    assert config.branch == "review/task-phase-3-bootstrap"
    assert config.worktree == "../SattLint-review-phase-3-bootstrap"
    assert config.source_ref == "feed123"


def test_bootstrap_slice_uses_stage_source_ref_for_review_branch(tmp_path):
    _write_templates(tmp_path)
    config = bootstrap_ai_slice.BootstrapConfig(
        repo_root=tmp_path,
        task_id="phase-3-bootstrap",
        title="Phase 3 Bootstrap",
        owner="Reviewer Agent",
        summary="Review the executor slice.",
        files=("scripts/bootstrap_ai_slice.py",),
        validation=("pytest tests/test_bootstrap_ai_slice.py -x -q --tb=short",),
        branch="review/task-phase-3-bootstrap",
        worktree="../SattLint-review-phase-3-bootstrap",
        base_branch="main",
        source_ref="ai/task-phase-3-bootstrap",
        stage="review",
        ledger_status="planned",
        notes="Bootstrapped from executor handoff.",
        task_contract_path=".ai/tasks/phase-3-bootstrap.json",
        handoff_path=".ai/handoffs/phase-3-bootstrap.json",
    )

    commands: list[tuple[str, ...]] = []

    def fake_git(repo_root: Path, args: tuple[str, ...]) -> subprocess.CompletedProcess[str]:
        commands.append(args)
        if args == ("worktree", "list", "--porcelain"):
            return subprocess.CompletedProcess(["git", *args], 0, stdout="", stderr="")
        if args == ("rev-parse", "--verify", "--quiet", "refs/heads/review/task-phase-3-bootstrap"):
            return subprocess.CompletedProcess(["git", *args], 1, stdout="", stderr="")
        if args == ("rev-parse", "--short", "HEAD"):
            return subprocess.CompletedProcess(["git", *args], 0, stdout="feed123\n", stderr="")
        if args[0:2] == ("worktree", "add"):
            return subprocess.CompletedProcess(["git", *args], 0, stdout="", stderr="")
        raise AssertionError(f"Unexpected git command: {args!r}")

    bootstrap_ai_slice.bootstrap_slice(config, git_runner=fake_git)

    assert commands[2] == (
        "worktree",
        "add",
        (tmp_path.parent / "SattLint-review-phase-3-bootstrap").resolve().as_posix(),
        "-b",
        "review/task-phase-3-bootstrap",
        "ai/task-phase-3-bootstrap",
    )


def test_bootstrap_slice_promotes_review_and_test_from_generated_executor_handoff(tmp_path):
    _write_templates(tmp_path)

    calls: list[tuple[Path, tuple[str, ...]]] = []

    def fake_git(repo_root: Path, args: tuple[str, ...]) -> subprocess.CompletedProcess[str]:
        calls.append((repo_root, args))
        if args == ("worktree", "list", "--porcelain"):
            return subprocess.CompletedProcess(["git", *args], 0, stdout="", stderr="")
        if args[:3] == ("rev-parse", "--verify", "--quiet"):
            return subprocess.CompletedProcess(["git", *args], 1, stdout="", stderr="")
        if args == ("rev-parse", "--short", "HEAD"):
            if repo_root.name == "SattLint-review-phase-3-bootstrap-review":
                return subprocess.CompletedProcess(["git", *args], 0, stdout="review123\n", stderr="")
            if repo_root.name == "SattLint-test-phase-3-bootstrap-test":
                return subprocess.CompletedProcess(["git", *args], 0, stdout="test123\n", stderr="")
            return subprocess.CompletedProcess(["git", *args], 0, stdout="abc1234\n", stderr="")
        if args[:2] == ("worktree", "add"):
            return subprocess.CompletedProcess(["git", *args], 0, stdout="", stderr="")
        raise AssertionError(f"Unexpected git command: {args!r}")

    executor_config = bootstrap_ai_slice.BootstrapConfig(
        repo_root=tmp_path,
        task_id="phase-3-bootstrap",
        title="Phase 3 Bootstrap",
        owner="Executor Agent",
        summary="Implement the executor slice.",
        files=("scripts/bootstrap_ai_slice.py",),
        validation=("pytest tests/test_bootstrap_ai_slice.py -x -q --tb=short",),
        branch="ai/task-phase-3-bootstrap",
        worktree="../SattLint-ai-phase-3-bootstrap",
        base_branch="main",
        source_ref="main",
        stage="executor",
        ledger_status="planned",
        notes="Executor bootstrap.",
        task_contract_path=".ai/tasks/phase-3-bootstrap.json",
        handoff_path=".ai/handoffs/phase-3-bootstrap.json",
    )

    bootstrap_ai_slice.bootstrap_slice(executor_config, git_runner=fake_git)

    review_args = bootstrap_ai_slice.build_parser().parse_args(
        [
            "--repo-root",
            str(tmp_path),
            "--task-id",
            "phase-3-bootstrap-review",
            "--title",
            "Phase 3 Bootstrap Review",
            "--owner",
            "Reviewer Agent",
            "--summary",
            "Review the executor slice.",
            "--file",
            "scripts/bootstrap_ai_slice.py",
            "--validation",
            "pytest tests/test_bootstrap_ai_slice.py -x -q --tb=short",
            "--stage",
            "review",
            "--from-handoff",
            ".ai/handoffs/phase-3-bootstrap.json",
        ]
    )
    review_config = bootstrap_ai_slice._collect_config(review_args)

    test_args = bootstrap_ai_slice.build_parser().parse_args(
        [
            "--repo-root",
            str(tmp_path),
            "--task-id",
            "phase-3-bootstrap-test",
            "--title",
            "Phase 3 Bootstrap Test",
            "--owner",
            "Test Agent",
            "--summary",
            "Validate the executor slice.",
            "--file",
            "tests/test_bootstrap_ai_slice.py",
            "--validation",
            "pytest tests/test_bootstrap_ai_slice.py -x -q --tb=short",
            "--stage",
            "test",
            "--from-handoff",
            ".ai/handoffs/phase-3-bootstrap.json",
        ]
    )
    test_config = bootstrap_ai_slice._collect_config(test_args)

    assert review_config.source_ref == "abc1234"
    assert test_config.source_ref == "abc1234"

    bootstrap_ai_slice.bootstrap_slice(review_config, git_runner=fake_git)
    bootstrap_ai_slice.bootstrap_slice(test_config, git_runner=fake_git)

    worktree_adds = [args for _, args in calls if args[:2] == ("worktree", "add")]
    assert worktree_adds == [
        (
            "worktree",
            "add",
            (tmp_path.parent / "SattLint-ai-phase-3-bootstrap").resolve().as_posix(),
            "-b",
            "ai/task-phase-3-bootstrap",
            "main",
        ),
        (
            "worktree",
            "add",
            (tmp_path.parent / "SattLint-review-phase-3-bootstrap-review").resolve().as_posix(),
            "-b",
            "review/task-phase-3-bootstrap-review",
            "abc1234",
        ),
        (
            "worktree",
            "add",
            (tmp_path.parent / "SattLint-test-phase-3-bootstrap-test").resolve().as_posix(),
            "-b",
            "test/task-phase-3-bootstrap-test",
            "abc1234",
        ),
    ]

    review_handoff = json.loads(
        (tmp_path / ".ai" / "handoffs" / "phase-3-bootstrap-review.json").read_text(encoding="utf-8")
    )
    test_handoff = json.loads(
        (tmp_path / ".ai" / "handoffs" / "phase-3-bootstrap-test.json").read_text(encoding="utf-8")
    )

    assert review_handoff["stage"] == "review"
    assert review_handoff["branch"] == "review/task-phase-3-bootstrap-review"
    assert review_handoff["commit"] == "review123"
    assert test_handoff["stage"] == "test"
    assert test_handoff["branch"] == "test/task-phase-3-bootstrap-test"
    assert test_handoff["commit"] == "test123"
