from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

OUTPUT_DIR = Path("artifacts") / "audit-precommit"
MAX_CHANGED_FILE_PREVIEW = 8


def _log(message: str) -> None:
    print(f"[repo-audit-slice] {message}", flush=True)


def _normalize_changed_files(argv: list[str], repo_root: Path) -> list[str]:
    changed_files: list[str] = []
    seen: set[str] = set()
    for raw_path in argv:
        path_text = raw_path.strip().replace("\\", "/")
        if not path_text:
            continue
        path = Path(path_text)
        if path.is_absolute():
            try:
                normalized = path.resolve().relative_to(repo_root.resolve()).as_posix()
            except ValueError:
                normalized = path.name
        else:
            normalized = path.as_posix()
        normalized = normalized.replace("\\", "/")
        if normalized in seen:
            continue
        seen.add(normalized)
        changed_files.append(normalized)
    return changed_files


def _describe_changed_files(changed_files: list[str]) -> str:
    if not changed_files:
        return "changed files: none supplied; repo-audit will fall back to git diff detection"

    preview = ", ".join(changed_files[:MAX_CHANGED_FILE_PREVIEW])
    remaining = len(changed_files) - min(len(changed_files), MAX_CHANGED_FILE_PREVIEW)
    if remaining > 0:
        preview += f", ... (+{remaining} more)"
    return f"changed files: {len(changed_files)} [{preview}]"


def _changed_file_args(changed_files: list[str]) -> list[str]:
    args: list[str] = []
    for changed_file in changed_files:
        args.extend(["--changed-file", changed_file])
    return args


def _build_recommend_command(changed_files: list[str]) -> list[str]:
    return [
        sys.executable,
        "-u",
        "-m",
        "sattlint.devtools.repo_audit",
        "--profile",
        "quick",
        "--recommend-checks",
        "--fail-on",
        "high",
        "--output-dir",
        OUTPUT_DIR.as_posix(),
        *_changed_file_args(changed_files),
    ]


def _build_selected_check_command(changed_files: list[str], check_ids: list[str]) -> list[str]:
    command = [
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
        OUTPUT_DIR.as_posix(),
    ]
    for check_id in check_ids:
        command.extend(["--check", check_id])
    command.extend(_changed_file_args(changed_files))
    return command


def _run_command(command: list[str], *, repo_root: Path, capture_output: bool) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    return subprocess.run(
        command,
        cwd=repo_root,
        env=env,
        check=False,
        text=True,
        capture_output=capture_output,
    )


def _load_recommendation_payload(stdout: str) -> dict[str, Any]:
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as error:
        raise ValueError("repo-audit --recommend-checks did not return valid JSON") from error
    if not isinstance(payload, dict):
        raise ValueError("repo-audit --recommend-checks returned a non-object payload")
    return payload


def _recommended_repo_audit_check_ids(payload: dict[str, Any]) -> list[str]:
    raw_ids = payload.get("recommended_repo_audit_check_ids")
    if not isinstance(raw_ids, list):
        return []
    return [str(check_id) for check_id in raw_ids if isinstance(check_id, str) and check_id.strip()]


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    changed_files = _normalize_changed_files(sys.argv[1:], repo_root)
    _log(_describe_changed_files(changed_files))
    _log("recommending repo-audit-specific checks")

    recommendation_run = _run_command(_build_recommend_command(changed_files), repo_root=repo_root, capture_output=True)
    if recommendation_run.returncode != 0:
        if recommendation_run.stdout:
            print(recommendation_run.stdout, end="")
        if recommendation_run.stderr:
            print(recommendation_run.stderr, file=sys.stderr, end="")
        _log(f"recommendation failed with exit code {recommendation_run.returncode}")
        return recommendation_run.returncode

    recommendation = _load_recommendation_payload(recommendation_run.stdout)
    recommended_check_ids = _recommended_repo_audit_check_ids(recommendation)
    if not recommended_check_ids:
        _log("no repo-audit custom checks recommended; skipping")
        return 0

    _log(f"recommended repo-audit checks: {', '.join(recommended_check_ids)}")
    _log("running repo-audit custom checks without pipeline")
    selected_check_run = _run_command(
        _build_selected_check_command(changed_files, recommended_check_ids),
        repo_root=repo_root,
        capture_output=False,
    )
    _log(f"completed with exit code {selected_check_run.returncode}")
    return selected_check_run.returncode


if __name__ == "__main__":
    raise SystemExit(main())
