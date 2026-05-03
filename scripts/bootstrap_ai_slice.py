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
TASK_TEMPLATE_PATH = REPO_ROOT / ".ai" / "tasks" / "task-contract.example.json"
HANDOFF_TEMPLATE_PATH = REPO_ROOT / ".ai" / "handoffs" / "handoff.example.json"
LEDGER_PATH = REPO_ROOT / ".github" / "coordination" / "current-work.md"
LEDGER_TEMPLATE_PATH = REPO_ROOT / ".github" / "coordination" / "current-work.template.md"
WORKSTREAM_RE = re.compile(r"^### Workstream\s+(?P<id>.+?)\s*$")
TASK_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
VALID_STAGE_VALUES = {"executor", "test", "review"}
VALID_LEDGER_STATUSES = {"planned", "active", "blocked", "ready-for-merge", "done"}


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
    stage: str
    ledger_status: str
    notes: str
    task_contract_path: str
    handoff_path: str


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
    normalized = raw_path.strip().replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized.rstrip("/")


def _humanize_task_id(task_id: str) -> str:
    parts = [part.upper() if part.isdigit() else part.capitalize() for part in task_id.split("-") if part]
    return " ".join(parts) or task_id


def _split_csv(raw_value: str) -> tuple[str, ...]:
    return tuple(item for item in (_normalize_rel_path(part) for part in raw_value.split(",")) if item)


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


def _unique_paths(values: Sequence[str]) -> tuple[str, ...]:
    normalized: list[str] = []
    seen: set[str] = set()
    for raw_value in values:
        value = _normalize_rel_path(raw_value)
        if not value or value in seen:
            continue
        seen.add(value)
        normalized.append(value)
    return tuple(normalized)


def _ensure_templates_exist(repo_root: Path) -> None:
    required = [
        repo_root / ".ai" / "tasks" / "task-contract.example.json",
        repo_root / ".ai" / "handoffs" / "handoff.example.json",
        repo_root / ".github" / "coordination" / "current-work.template.md",
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
    default_title = _humanize_task_id(task_id)
    title = args.title or _prompt_value(input_func, "Title", default=default_title)
    owner = args.owner or _prompt_value(input_func, "Owner", default="Copilot")
    summary = args.summary or _prompt_value(
        input_func,
        "Summary",
        default=f"Scoped slice for {default_title.lower()}.",
    )
    files = _unique_paths(args.file)
    if not files:
        files = _split_csv(_prompt_value(input_func, "Claimed files (comma-separated relative paths)"))
    if not files:
        raise BootstrapError("At least one claimed file is required.")

    validation = tuple(command.strip() for command in args.validation if command.strip())
    if not validation:
        validation = (
            _prompt_value(
                input_func,
                "First validation command",
                default=f'& ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_{task_id.replace("-", "_")}.py -x -q --tb=short',
            ),
        )

    stage = _normalize_stage(args.stage)
    ledger_status = _normalize_ledger_status(args.ledger_status)
    branch = args.branch or f"ai/task-{task_id}"
    worktree = args.worktree or f"../SattLint-ai-{task_id}"
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
        stage=stage,
        ledger_status=ledger_status,
        notes=notes.strip(),
        task_contract_path=_normalize_rel_path(task_contract_path),
        handoff_path=_normalize_rel_path(handoff_path),
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
        add_args = ("worktree", "add", worktree_path.as_posix(), "-b", config.branch, config.base_branch)

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
            "acceptance_criteria": list(payload.get("acceptance_criteria", [])) if existing else [],
            "risks": list(payload.get("risks", [])) if existing else [],
        }
    )
    return payload


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


def _ensure_ledger(repo_root: Path) -> Path:
    ledger_path = repo_root / ".github" / "coordination" / "current-work.md"
    if ledger_path.exists():
        return ledger_path
    template_path = repo_root / ".github" / "coordination" / "current-work.template.md"
    if not template_path.exists():
        raise BootstrapError("Missing .github/coordination/current-work.template.md.")
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    ledger_path.write_text(template_path.read_text(encoding="utf-8"), encoding="utf-8")
    return ledger_path


def _split_workstream_blocks(text: str) -> tuple[list[str], list[list[str]]]:
    prefix: list[str] = []
    blocks: list[list[str]] = []
    current: list[str] | None = None
    for raw_line in text.splitlines(keepends=True):
        if WORKSTREAM_RE.match(raw_line.rstrip()):
            if current is not None:
                blocks.append(current)
            current = [raw_line]
            continue
        if current is None:
            prefix.append(raw_line)
            continue
        current.append(raw_line)
    if current is not None:
        blocks.append(current)
    return prefix, blocks


def _render_workstream_block(config: BootstrapConfig) -> list[str]:
    claims = [*config.files, config.task_contract_path, config.handoff_path]
    rendered_claims = ", ".join(f"`{claim}`" for claim in _unique_paths(claims))
    lines = [
        f"### Workstream {config.task_id}\n",
        "\n",
        f"- Owner: {config.owner}\n",
        f"- Goal: {config.summary}\n",
        f"- Claims: {rendered_claims}\n",
        f"- First validation: {config.validation[0]}\n",
        f"- Status: {config.ledger_status}\n",
        f"- Notes: {config.notes}\n",
        "\n",
    ]
    return lines


def _upsert_ledger_entry(config: BootstrapConfig) -> Path:
    ledger_path = _ensure_ledger(config.repo_root)
    text = ledger_path.read_text(encoding="utf-8")
    prefix, blocks = _split_workstream_blocks(text)
    rendered = _render_workstream_block(config)
    updated_blocks: list[list[str]] = []
    replaced = False
    for block in blocks:
        heading = block[0].rstrip()
        match = WORKSTREAM_RE.match(heading)
        if match is not None and match.group("id").strip() == config.task_id:
            updated_blocks.append(rendered)
            replaced = True
            continue
        updated_blocks.append(block)
    if not replaced:
        updated_blocks.insert(0, rendered)
    updated_text = "".join(prefix + [line for block in updated_blocks for line in block]).rstrip() + "\n"
    ledger_path.write_text(updated_text, encoding="utf-8")
    return ledger_path


def bootstrap_slice(config: BootstrapConfig, git_runner: GitRunner = _run_git) -> dict[str, str]:
    worktree_path = _ensure_worktree(config, git_runner)
    commit = _git_head_commit(config.repo_root, git_runner)

    task_contract_path = _resolve_repo_path(config.repo_root, config.task_contract_path)
    existing_task = _load_json_object(task_contract_path) if task_contract_path.exists() else None
    _write_json(task_contract_path, _task_contract_payload(config, existing_task))

    handoff_path = _resolve_repo_path(config.repo_root, config.handoff_path)
    existing_handoff = _load_json_object(handoff_path) if handoff_path.exists() else None
    _write_json(handoff_path, _handoff_payload(config, commit, existing_handoff))

    ledger_path = _upsert_ledger_entry(config)
    return {
        "branch": config.branch,
        "worktree": worktree_path.as_posix(),
        "task_contract": _relative_path(task_contract_path, config.repo_root),
        "handoff": _relative_path(handoff_path, config.repo_root),
        "ledger": _relative_path(ledger_path, config.repo_root),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Bootstrap one explicit AI slice from planning output.")
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--task-id")
    parser.add_argument("--title")
    parser.add_argument("--owner")
    parser.add_argument("--summary")
    parser.add_argument("--file", action="append", default=[])
    parser.add_argument("--validation", action="append", default=[])
    parser.add_argument("--branch")
    parser.add_argument("--worktree")
    parser.add_argument("--base-branch", default="main")
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
    except BootstrapError as error:
        print(f"bootstrap-ai-slice: {error}", file=sys.stderr)
        return 1

    print(f"Branch: {result['branch']}")
    print(f"Worktree: {result['worktree']}")
    print(f"Task contract: {result['task_contract']}")
    print(f"Handoff: {result['handoff']}")
    print(f"Ledger: {result['ledger']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
