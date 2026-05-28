from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = REPO_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from sattlint.devtools import coordination_lock_state  # noqa: E402
from sattlint.devtools._portable_command_text import pytest_command  # noqa: E402

TASK_TEMPLATE_PATH = REPO_ROOT / ".ai" / "tasks" / "task-contract.example.json"
HANDOFF_TEMPLATE_PATH = REPO_ROOT / ".ai" / "handoffs" / "handoff.example.json"
TASK_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
VALID_STAGE_VALUES = {"executor", "test", "review"}
VALID_LEDGER_STATUSES = {"planned", "active", "blocked", "ready-for-merge", "done"}
VALID_REQUEST_KINDS = {"implement-plan", "review-artifact", "chat-review"}
STRUCTURAL_DEBT_REDUCTION_HINTS = (
    "decompose",
    "decomposition",
    "extract",
    "split",
    "shrink",
    "reduce",
    "breakdown",
)


class BootstrapError(RuntimeError):
    pass


GitRunner = Callable[[Path, Sequence[str]], subprocess.CompletedProcess[str]]
InputFunc = Callable[[str], str]


@dataclass(frozen=True)
class BootstrapConfig:
    repo_root: Path
    task_id: str
    title: str
    owner: str
    summary: str
    files: tuple[str, ...]
    validation: tuple[str, ...]
    branch: str
    worktree: str
    base_branch: str
    source_ref: str
    stage: str
    ledger_status: str
    notes: str
    task_contract_path: str
    handoff_path: str
    request_kind: str | None = None
    request_artifact: str | None = None


@dataclass(frozen=True)
class WorktreeInfo:
    path: Path
    branch: str | None


def _run_git(repo_root: Path, args: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo_root,
        check=False,
        text=True,
        capture_output=True,
    )


def _normalize_rel_path(raw_path: str) -> str:
    return coordination_lock_state.normalize_relative_path(raw_path)


def _humanize_task_id(task_id: str) -> str:
    parts = [part.upper() if part.isdigit() else part.capitalize() for part in task_id.split("-") if part]
    return " ".join(parts) or task_id


def _split_csv(raw_value: str, *, repo_root: Path) -> tuple[str, ...]:
    return tuple(coordination_lock_state.unique_claim_paths(raw_value.split(","), repo_root=repo_root))


def _prompt_value(
    input_func: InputFunc,
    prompt: str,
    *,
    default: str | None = None,
    normalize: Callable[[str], str] | None = None,
) -> str:
    while True:
        suffix = f" [{default}]" if default else ""
        raw_value = input_func(f"{prompt}{suffix}: ").strip()
        value = raw_value or (default or "")
        if normalize is not None:
            value = normalize(value)
        if value:
            return value
        print(f"{prompt} is required.", file=sys.stderr)


def _require_valid_task_id(task_id: str) -> str:
    if not TASK_ID_RE.fullmatch(task_id):
        raise BootstrapError("task_id must be lower-kebab-case.")
    return task_id


def _normalize_stage(stage: str) -> str:
    normalized = stage.strip().casefold()
    if normalized not in VALID_STAGE_VALUES:
        raise BootstrapError(f"stage must be one of {sorted(VALID_STAGE_VALUES)}.")
    return normalized


def _normalize_ledger_status(status: str) -> str:
    normalized = status.strip().casefold()
    if normalized not in VALID_LEDGER_STATUSES:
        raise BootstrapError(f"ledger status must be one of {sorted(VALID_LEDGER_STATUSES)}.")
    return normalized


def _normalize_request_kind(request_kind: str) -> str:
    normalized = request_kind.strip().casefold()
    if normalized not in VALID_REQUEST_KINDS:
        raise BootstrapError(f"request kind must be one of {sorted(VALID_REQUEST_KINDS)}.")
    return normalized


def _default_branch(stage: str, task_id: str) -> str:
    if stage == "review":
        return f"review/task-{task_id}"
    if stage == "test":
        return f"test/task-{task_id}"
    return f"ai/task-{task_id}"


def _default_worktree(stage: str, task_id: str) -> str:
    if stage == "review":
        return f"../SattLint-review-{task_id}"
    if stage == "test":
        return f"../SattLint-test-{task_id}"
    return f"../SattLint-ai-{task_id}"


def _source_ref_from_handoff(repo_root: Path, raw_path: str) -> str:
    handoff_path = _resolve_repo_path(repo_root, raw_path)
    payload = _load_json_object(handoff_path)
    commit = str(payload.get("commit") or "").strip()
    if commit and commit != "pending":
        return commit
    branch = str(payload.get("branch") or "").strip()
    if branch:
        return branch
    raise BootstrapError(
        f"Handoff {coordination_lock_state.display_path(handoff_path, repo_root)} must contain a branch or commit."
    )


def _resolve_source_ref(args: argparse.Namespace, *, repo_root: Path, stage: str, task_id: str) -> str:
    from_branch = str(args.from_branch or "").strip()
    from_handoff = str(args.from_handoff or "").strip()
    if from_branch and from_handoff:
        raise BootstrapError("Use only one of --from-branch or --from-handoff.")
    if from_branch:
        return from_branch
    if from_handoff:
        return _source_ref_from_handoff(repo_root, from_handoff)
    if stage in {"review", "test"}:
        return f"ai/task-{task_id}"
    return args.base_branch.strip()


def _display_path(raw_path: str, *, repo_root: Path) -> str:
    candidate = Path(raw_path)
    resolved = (repo_root / candidate).resolve() if not candidate.is_absolute() else candidate.resolve()
    try:
        return resolved.relative_to(repo_root).as_posix()
    except ValueError:
        return resolved.as_posix()


def _resolve_chat_review_artifact(raw_path: str, *, repo_root: Path) -> str:
    candidate = Path(raw_path)
    resolved = (repo_root / candidate).resolve() if not candidate.is_absolute() else candidate.resolve()

    if resolved.name == "transcripts":
        target = resolved
    elif resolved.name == "debug-logs":
        target = resolved.parent / "transcripts"
    elif resolved.suffix == ".jsonl" and resolved.parent.name == "transcripts":
        target = resolved.parent
    elif resolved.suffix == ".jsonl" and resolved.parent.name == "debug-logs":
        target = resolved.parent.parent / "transcripts"
    elif resolved.name == "GitHub.copilot-chat":
        target = resolved / "transcripts"
    else:
        target = resolved / "GitHub.copilot-chat" / "transcripts"

    try:
        return target.relative_to(repo_root).as_posix()
    except ValueError:
        return target.as_posix()


def _resolve_request_artifact(args: argparse.Namespace, *, repo_root: Path) -> tuple[str | None, str | None]:
    raw_request_kind = str(args.from_request_kind or "").strip()
    plan_file = str(args.plan_file or "").strip()
    artifact_path = str(args.artifact_path or "").strip()

    if not raw_request_kind:
        if plan_file or artifact_path:
            raise BootstrapError("Use --from-request-kind before providing --plan-file or --artifact-path.")
        return None, None

    request_kind = _normalize_request_kind(raw_request_kind)
    if request_kind == "implement-plan":
        if not plan_file:
            raise BootstrapError("implement-plan requires --plan-file.")
        if artifact_path:
            raise BootstrapError("implement-plan uses --plan-file, not --artifact-path.")
        return request_kind, _display_path(plan_file, repo_root=repo_root)

    if plan_file:
        raise BootstrapError(f"{request_kind} does not accept --plan-file.")
    if not artifact_path:
        raise BootstrapError(f"{request_kind} requires --artifact-path.")
    if request_kind == "chat-review":
        return request_kind, _resolve_chat_review_artifact(artifact_path, repo_root=repo_root)
    return request_kind, _display_path(artifact_path, repo_root=repo_root)


def _unique_paths(values: Sequence[str], *, repo_root: Path | None = None) -> tuple[str, ...]:
    return tuple(coordination_lock_state.unique_claim_paths(list(values), repo_root=repo_root))


def _is_structural_debt_reduction_slice(config: BootstrapConfig) -> bool:
    haystack = " ".join((config.task_id, config.title, config.summary, config.notes)).casefold()
    return any(hint in haystack for hint in STRUCTURAL_DEBT_REDUCTION_HINTS)


def _reject_disallowed_structural_debt_claims(config: BootstrapConfig) -> None:
    oversized_entries = coordination_lock_state.claimed_oversized_structural_debt_entries(
        config.repo_root,
        config.files,
    )
    if not oversized_entries or _is_structural_debt_reduction_slice(config):
        return

    claimed = "; ".join(
        (
            f"{entry['path']} ({entry['structural_current_baseline']} -> {entry['structural_target']}, "
            f"touch rule: {entry['structural_touch_rule']})"
        )
        for entry in oversized_entries
    )
    raise BootstrapError(
        "Claimed oversized structural debt files require an explicit decomposition or shrink slice before bootstrap: "
        f"{claimed}. Mark the task metadata with one of {', '.join(STRUCTURAL_DEBT_REDUCTION_HINTS)} "
        "or narrow the claims to files that are not under oversized structural debt."
    )


def _ensure_templates_exist(repo_root: Path) -> None:
    required = [
        repo_root / ".ai" / "tasks" / "task-contract.example.json",
        repo_root / ".ai" / "handoffs" / "handoff.example.json",
    ]
    missing = [path for path in required if not path.exists()]
    if missing:
        joined = ", ".join(path.relative_to(repo_root).as_posix() for path in missing)
        raise BootstrapError(f"Missing bootstrap template files: {joined}.")


def _collect_config(args: argparse.Namespace, input_func: InputFunc = input) -> BootstrapConfig:
    repo_root = Path(args.repo_root).resolve()
    _ensure_templates_exist(repo_root)

    task_id = args.task_id or _prompt_value(input_func, "Task ID", normalize=_normalize_rel_path)
    task_id = _require_valid_task_id(task_id)
    request_kind, request_artifact = _resolve_request_artifact(args, repo_root=repo_root)
    default_title = _humanize_task_id(task_id)
    title = args.title or _prompt_value(input_func, "Title", default=default_title)
    owner = args.owner or _prompt_value(input_func, "Owner", default="Copilot")
    summary = args.summary or _prompt_value(
        input_func,
        "Summary",
        default=f"Scoped slice for {default_title.lower()}.",
    )
    files = _unique_paths(args.file, repo_root=repo_root)
    if not files:
        files = _split_csv(
            _prompt_value(input_func, "Claimed files (comma-separated relative paths)"),
            repo_root=repo_root,
        )
    if not files:
        raise BootstrapError("At least one claimed file is required.")

    validation = tuple(command.strip() for command in args.validation if command.strip())
    if not validation:
        validation = (
            _prompt_value(
                input_func,
                "First validation command",
                default=pytest_command(
                    "--no-cov",
                    f"tests/test_{task_id.replace('-', '_')}.py",
                    "-x",
                    "-q",
                    "--tb=short",
                ),
            ),
        )

    stage = _normalize_stage(args.stage)
    ledger_status = _normalize_ledger_status(args.ledger_status)
    branch = args.branch or _default_branch(stage, task_id)
    worktree = args.worktree or _default_worktree(stage, task_id)
    source_ref = _resolve_source_ref(args, repo_root=repo_root, stage=stage, task_id=task_id)
    notes = args.notes or (
        "Bootstrapped from planning output. Replace stub placeholders before implementation or handoff."
    )
    task_contract_path = args.task_contract_path or f".ai/tasks/{task_id}.json"
    handoff_path = args.handoff_path or f".ai/handoffs/{task_id}.json"

    return BootstrapConfig(
        repo_root=repo_root,
        task_id=task_id,
        title=title.strip(),
        owner=owner.strip(),
        summary=summary.strip(),
        files=files,
        validation=validation,
        branch=branch.strip(),
        worktree=worktree.strip(),
        base_branch=args.base_branch.strip(),
        source_ref=source_ref,
        stage=stage,
        ledger_status=ledger_status,
        notes=notes.strip(),
        task_contract_path=_normalize_rel_path(task_contract_path),
        handoff_path=_normalize_rel_path(handoff_path),
        request_kind=request_kind,
        request_artifact=request_artifact,
    )


def _load_json_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise BootstrapError(f"Expected JSON object in {path}.")
    return payload


def _relative_path(path: Path, repo_root: Path) -> str:
    return path.relative_to(repo_root).as_posix()


def _resolve_repo_path(repo_root: Path, raw_path: str) -> Path:
    return (repo_root / _normalize_rel_path(raw_path)).resolve()


def _resolve_worktree_path(repo_root: Path, raw_path: str) -> Path:
    path = Path(raw_path)
    if not path.is_absolute():
        path = (repo_root / path).resolve()
    return path.resolve()


def _parse_worktree_list(output: str) -> list[WorktreeInfo]:
    worktrees: list[WorktreeInfo] = []
    current_path: Path | None = None
    current_branch: str | None = None
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line:
            if current_path is not None:
                worktrees.append(WorktreeInfo(current_path.resolve(), current_branch))
            current_path = None
            current_branch = None
            continue
        if line.startswith("worktree "):
            current_path = Path(line.removeprefix("worktree ").strip())
            continue
        if line.startswith("branch refs/heads/"):
            current_branch = line.removeprefix("branch refs/heads/").strip()
    if current_path is not None:
        worktrees.append(WorktreeInfo(current_path.resolve(), current_branch))
    return worktrees


def _ensure_worktree(config: BootstrapConfig, git_runner: GitRunner) -> Path:
    worktree_path = _resolve_worktree_path(config.repo_root, config.worktree)
    listed = git_runner(config.repo_root, ("worktree", "list", "--porcelain"))
    if listed.returncode != 0:
        message = listed.stderr.strip() or "Failed to inspect git worktrees."
        raise BootstrapError(message)
    worktrees = _parse_worktree_list(listed.stdout)

    matching_path = next((entry for entry in worktrees if entry.path == worktree_path), None)
    if matching_path is not None:
        if matching_path.branch not in {None, config.branch}:
            raise BootstrapError(
                f"Requested worktree {worktree_path} is already attached to branch {matching_path.branch}."
            )
        return worktree_path

    matching_branch = next((entry for entry in worktrees if entry.branch == config.branch), None)
    if matching_branch is not None:
        raise BootstrapError(
            f"Branch {config.branch} is already checked out in worktree {matching_branch.path.as_posix()}."
        )

    if worktree_path.exists():
        raise BootstrapError(f"Path already exists and is not a git worktree: {worktree_path.as_posix()}.")

    branch_check = git_runner(config.repo_root, ("rev-parse", "--verify", "--quiet", f"refs/heads/{config.branch}"))
    if branch_check.returncode == 0:
        add_args: tuple[str, ...] = ("worktree", "add", worktree_path.as_posix(), config.branch)
    else:
        add_args = ("worktree", "add", worktree_path.as_posix(), "-b", config.branch, config.source_ref)

    added = git_runner(config.repo_root, add_args)
    if added.returncode != 0:
        message = added.stderr.strip() or f"Failed to create worktree {worktree_path.as_posix()}."
        raise BootstrapError(message)
    return worktree_path


def _git_head_commit(repo_root: Path, git_runner: GitRunner) -> str:
    completed = git_runner(repo_root, ("rev-parse", "--short", "HEAD"))
    if completed.returncode != 0:
        return "pending"
    value = completed.stdout.strip()
    return value or "pending"


def _task_contract_payload(config: BootstrapConfig, existing: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = dict(existing or _load_json_object(config.repo_root / ".ai" / "tasks" / "task-contract.example.json"))
    acceptance_criteria = (
        list(payload.get("acceptance_criteria", [])) if existing else _default_acceptance_criteria(config)
    )
    payload.update(
        {
            "task_id": config.task_id,
            "title": config.title,
            "owner": config.owner,
            "stage": config.stage,
            "branch": config.branch,
            "worktree": config.worktree,
            "summary": config.summary,
            "files": list(config.files),
            "validation": list(config.validation),
            "status": "draft",
            "handoff_path": config.handoff_path,
            "acceptance_criteria": acceptance_criteria,
            "risks": list(payload.get("risks", [])) if existing else [],
        }
    )
    return payload


def _default_acceptance_criteria(config: BootstrapConfig) -> list[str]:
    if config.request_kind is None or config.request_artifact is None:
        return []

    if config.request_kind == "implement-plan":
        starting_rule = f"Start from the controlling plan {config.request_artifact} before broader repo exploration."
    elif config.request_kind == "review-artifact":
        starting_rule = (
            f"Start from the controlling artifact {config.request_artifact} before opening unrelated repo surfaces."
        )
    else:
        starting_rule = (
            f"Start from transcript JSONL files under {config.request_artifact}; use debug logs only as metadata."
        )

    return [
        starting_rule,
        f"Keep the scope anchored to the requested files: {', '.join(config.files)}.",
        f"Run the first validation command: {config.validation[0]}.",
        f"Deliver the expected outcome: {config.summary}.",
    ]


def _request_contract_payload(config: BootstrapConfig) -> dict[str, Any] | None:
    if config.request_kind is None or config.request_artifact is None:
        return None
    return {
        "request_kind": config.request_kind,
        "controlling_artifact": config.request_artifact,
        "requested_files": list(config.files),
        "first_validation": config.validation[0],
        "expected_outcome": config.summary,
        "success_criteria": _default_acceptance_criteria(config),
    }


def _request_prompt_payload(config: BootstrapConfig) -> str | None:
    contract = _request_contract_payload(config)
    if contract is None:
        return None

    requested_files = "\n".join(f"- {path}" for path in contract["requested_files"])
    success_criteria = "\n".join(f"- {item}" for item in contract["success_criteria"])
    return "\n".join(
        [
            f"Request kind: {contract['request_kind']}",
            f"Start from: {contract['controlling_artifact']}",
            "Requested files:",
            requested_files,
            f"First validation: {contract['first_validation']}",
            f"Expected outcome: {contract['expected_outcome']}",
            "Success criteria:",
            success_criteria,
        ]
    )


def _handoff_payload(
    config: BootstrapConfig,
    commit: str,
    existing: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = dict(existing or _load_json_object(config.repo_root / ".ai" / "handoffs" / "handoff.example.json"))
    payload.update(
        {
            "task_id": config.task_id,
            "stage": config.stage,
            "branch": config.branch,
            "commit": commit,
            "files_changed": list(config.files),
            "summary": f"Scoped {config.stage} handoff stub for {config.title}.",
            "known_risks": list(payload.get("known_risks", [])) if existing else [],
            "required_tests": list(config.validation),
            "validation_status": {
                "state": "pending",
                "commands": list(config.validation),
                "notes": list(payload.get("validation_status", {}).get("notes", []))
                if existing and isinstance(payload.get("validation_status"), dict)
                else [
                    "Replace placeholder scope, files_changed, and validation commands before handing off to Test Agent or Reviewer Agent."
                ],
            },
            "reviewer_notes": list(payload.get("reviewer_notes", [])) if existing else [],
            "status": "draft",
        }
    )
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _upsert_ledger_entry(config: BootstrapConfig) -> Path:
    coordination_lock_state.upsert_workstream(
        config.repo_root,
        workstream_id=config.task_id,
        owner=config.owner,
        status=config.ledger_status,
        claimed_paths=_unique_paths(
            (*config.files, config.task_contract_path, config.handoff_path),
            repo_root=config.repo_root,
        ),
        first_validation=config.validation[0],
    )
    return coordination_lock_state.lock_state_path(config.repo_root)


def bootstrap_slice(config: BootstrapConfig, git_runner: GitRunner = _run_git) -> dict[str, str]:
    _reject_disallowed_structural_debt_claims(config)
    worktree_path = _ensure_worktree(config, git_runner)
    commit = _git_head_commit(worktree_path, git_runner)

    task_contract_path = _resolve_repo_path(config.repo_root, config.task_contract_path)
    existing_task = _load_json_object(task_contract_path) if task_contract_path.exists() else None
    _write_json(task_contract_path, _task_contract_payload(config, existing_task))

    handoff_path = _resolve_repo_path(config.repo_root, config.handoff_path)
    existing_handoff = _load_json_object(handoff_path) if handoff_path.exists() else None
    _write_json(handoff_path, _handoff_payload(config, commit, existing_handoff))

    ledger_path = _upsert_ledger_entry(config)
    result = {
        "branch": config.branch,
        "worktree": worktree_path.as_posix(),
        "task_contract": _relative_path(task_contract_path, config.repo_root),
        "handoff": _relative_path(handoff_path, config.repo_root),
        "lock_state": coordination_lock_state.display_path(ledger_path, config.repo_root),
    }
    request_contract = _request_contract_payload(config)
    request_prompt = _request_prompt_payload(config)
    if request_contract is not None and request_prompt is not None:
        result["request_contract"] = json.dumps(request_contract, indent=2)
        result["request_prompt"] = request_prompt
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Bootstrap one explicit AI slice or request contract from planning output."
    )
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--task-id")
    parser.add_argument("--title")
    parser.add_argument("--owner")
    parser.add_argument("--summary")
    parser.add_argument("--from-request-kind", choices=sorted(VALID_REQUEST_KINDS))
    parser.add_argument("--plan-file")
    parser.add_argument("--artifact-path")
    parser.add_argument("--file", action="append", default=[])
    parser.add_argument("--validation", action="append", default=[])
    parser.add_argument("--branch")
    parser.add_argument("--worktree")
    parser.add_argument("--base-branch", default="main")
    parser.add_argument(
        "--from-branch", help="Create the stage branch from an existing branch instead of --base-branch."
    )
    parser.add_argument(
        "--from-handoff", help="Create the stage branch from the branch or commit recorded in a handoff JSON file."
    )
    parser.add_argument("--stage", default="executor")
    parser.add_argument("--ledger-status", default="planned")
    parser.add_argument("--notes")
    parser.add_argument("--task-contract-path")
    parser.add_argument("--handoff-path")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        config = _collect_config(args)
        result = bootstrap_slice(config)
    except (BootstrapError, OSError) as error:
        print(f"bootstrap-ai-slice: {error}", file=sys.stderr)
        return 1

    print(f"Branch: {result['branch']}")
    print(f"Worktree: {result['worktree']}")
    print(f"Task contract: {result['task_contract']}")
    print(f"Handoff: {result['handoff']}")
    print(f"Lock state: {result['lock_state']}")
    if "request_contract" in result and "request_prompt" in result:
        print("Request contract:")
        print(result["request_contract"])
        print("Prompt payload:")
        print(result["request_prompt"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
