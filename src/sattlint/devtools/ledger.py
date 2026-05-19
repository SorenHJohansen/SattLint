"""Shared helpers for repo-audit report writing and run history."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import time
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any, TypedDict, cast

from sattlint.devtools.pipeline_artifacts import write_json_artifact
from sattlint.path_sanitizer import sanitize_path_for_report

AUDIT_RUN_HISTORY_FILENAME = "run_history.json"
AUDIT_RUN_HISTORY_DIRNAME = "history"
AUDIT_RUN_HISTORY_LIMIT = 10
AUDIT_RUN_HISTORY_SCHEMA_KIND = "sattlint.audit_run_history"
AUDIT_RUN_HISTORY_SCHEMA_VERSION = 1


class FailurePatternGroup(TypedDict):
    signature: str
    occurrence_count: int
    latest_run_id: str
    latest_captured_at: str
    report_kind: Any
    selected_surface: Any
    finish_gate_status: Any
    top_failure_ids: list[str]
    top_failure_messages: list[str]
    run_ids: list[str]


def _json_mapping(value: object) -> dict[str, Any] | None:
    return cast(dict[str, Any], value) if isinstance(value, dict) else None


def _mapping_entries(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    entries: list[dict[str, Any]] = []
    for item in cast(list[object], value):
        entry = _json_mapping(item)
        if entry is not None:
            entries.append(entry)
    return entries


def _string_entries(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item_text for item in cast(list[object], value) if (item_text := str(item)).strip()]


def _cleanup_temp_path(path: Path) -> None:
    path.unlink(missing_ok=True)


def write_text_artifact(
    path: Path,
    content: str,
    *,
    replace_fn: Callable[[Path, Path], None] = os.replace,
    sleep_fn: Callable[[float], None] = time.sleep,
    temp_file_factory: Any = tempfile.NamedTemporaryFile,
    range_factory: Callable[[int], Iterable[int]] = range,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    last_error: PermissionError | None = None
    for _ in range_factory(5):
        temp_path: Path | None = None
        try:
            with temp_file_factory(
                mode="w",
                encoding="utf-8",
                newline="",
                dir=path.parent,
                prefix=f".{path.name}.",
                suffix=".tmp",
                delete=False,
            ) as handle:
                handle.write(content)
                temp_path = Path(handle.name)
            replace_fn(temp_path, path)
            return
        except PermissionError as exc:
            last_error = exc
            if temp_path is not None:
                _cleanup_temp_path(temp_path)
            sleep_fn(0.1)
    if last_error is not None:
        raise last_error
    raise RuntimeError(f"Failed to write {path}")


def write_markdown(
    path: Path,
    findings: list[Any],
    summary: dict[str, Any],
    *,
    write_text_artifact_fn: Callable[[Path, str], None] = write_text_artifact,
) -> None:
    lines = ["# Repository Audit", "", "## Summary", ""]
    for severity in ("critical", "high", "medium", "low"):
        lines.append(f"- {severity.title()}: {summary['severity_counts'].get(severity, 0)}")
    lines.extend(["", "## Findings", ""])
    if not findings:
        lines.append("- No findings.")
    else:
        for finding in findings:
            location = finding.path or "<repo>"
            if finding.line is not None:
                location = f"{location}:{finding.line}"
            lines.append(f"- [{finding.severity.upper()}] {finding.category}: {finding.message} ({location})")
            if finding.detail:
                lines.append(f"  Detail: {finding.detail}")
    write_text_artifact_fn(path, "\n".join(lines) + "\n")


def mirror_latest_reports(
    source_dir: Path,
    latest_output_dir: Path | None,
    *,
    copy2_fn: Callable[[Path, Path], Any] = shutil.copy2,
) -> None:
    if latest_output_dir is None:
        return
    if source_dir.resolve() == latest_output_dir.resolve():
        return
    latest_output_dir.mkdir(parents=True, exist_ok=True)
    for source_path in source_dir.rglob("*"):
        relative_path = source_path.relative_to(source_dir)
        target_path = latest_output_dir / relative_path
        if source_path.is_dir():
            target_path.mkdir(parents=True, exist_ok=True)
            continue
        target_path.parent.mkdir(parents=True, exist_ok=True)
        copy2_fn(source_path, target_path)


def sanitize_report_path(path: Path, *, repo_root: Path) -> str:
    return sanitize_path_for_report(path.resolve(), repo_root=repo_root) or path.resolve().as_posix()


def load_audit_run_history(
    path: Path,
    *,
    read_text: Callable[[Path], str],
) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        payload = _json_mapping(json.loads(read_text(path)))
    except (OSError, ValueError, json.JSONDecodeError):
        return []
    if payload is None:
        return []
    return [entry for entry in _mapping_entries(payload.get("runs")) if isinstance(entry.get("run_id"), str)]


def build_audit_run_id() -> str:
    epoch_seconds = time.time()
    millis = int((epoch_seconds % 1) * 1000)
    return f"{time.strftime('%Y%m%dT%H%M%S', time.gmtime(epoch_seconds))}-{millis:03d}Z"


def collect_audit_git_state(
    root: Path,
    *,
    git_which: Callable[[str], str | None],
    run_command: Callable[..., Any],
) -> dict[str, Any]:
    git_executable = git_which("git")
    if git_executable is None:
        return {"head": None, "dirty": None}

    try:
        head_completed = run_command(  # nosec B603 - fixed git executable with controlled arguments
            [git_executable, "rev-parse", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
        dirty_completed = run_command(  # nosec B603 - fixed git executable with controlled arguments
            [git_executable, "status", "--porcelain"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return {"head": None, "dirty": None}

    head = None
    if head_completed.returncode == 0:
        candidate = head_completed.stdout.strip()
        head = candidate or None

    dirty = None
    if dirty_completed.returncode == 0:
        dirty = bool(dirty_completed.stdout.strip())

    return {"head": head, "dirty": dirty}


def copy_audit_snapshot(
    source_dir: Path,
    snapshot_dir: Path,
    *,
    history_dirname: str,
    history_filename: str,
    copy2_fn: Callable[[Path, Path], Any] = shutil.copy2,
) -> None:
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    for source_path in source_dir.rglob("*"):
        relative_path = source_path.relative_to(source_dir)
        if relative_path.parts and relative_path.parts[0] == history_dirname:
            continue
        if relative_path.name == history_filename:
            continue
        target_path = snapshot_dir / relative_path
        if source_path.is_dir():
            target_path.mkdir(parents=True, exist_ok=True)
            continue
        target_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            copy2_fn(source_path, target_path)
        except FileNotFoundError:
            continue


def history_stale_reasons(entry: dict[str, Any], *, latest: bool) -> list[str]:
    reasons = [str(reason) for reason in entry.get("base_stale_reasons", []) if str(reason)]
    if not latest and "superseded-by-newer-run" not in reasons:
        reasons.append("superseded-by-newer-run")
    return reasons


def failure_signature(entry: dict[str, Any]) -> str | None:
    if entry.get("overall_status") == "pass":
        return None
    components: list[str] = [str(entry.get("report_kind", "audit"))]
    selected_surface = entry.get("selected_surface")
    if isinstance(selected_surface, str) and selected_surface:
        components.append(selected_surface)
    finish_gate_status = entry.get("finish_gate_status")
    if isinstance(finish_gate_status, str) and finish_gate_status:
        components.append(f"finish:{finish_gate_status}")
    top_failure_ids = _string_entries(entry.get("top_failure_ids"))
    if top_failure_ids:
        components.extend(top_failure_ids[:5])
    else:
        selected_checks = _string_entries(entry.get("selected_checks"))
        if selected_checks:
            components.extend(selected_checks[:5])
    if len(components) == 1:
        return None
    return "|".join(components)


def build_failure_patterns(runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, FailurePatternGroup] = {}
    for entry in runs:
        signature = failure_signature(entry)
        if signature is None:
            continue
        group: FailurePatternGroup | None = grouped.get(signature)
        if group is None:
            group = {
                "signature": signature,
                "occurrence_count": 0,
                "latest_run_id": entry["run_id"],
                "latest_captured_at": entry["captured_at"],
                "report_kind": entry.get("report_kind"),
                "selected_surface": entry.get("selected_surface"),
                "finish_gate_status": entry.get("finish_gate_status"),
                "top_failure_ids": _string_entries(entry.get("top_failure_ids"))[:5],
                "top_failure_messages": _string_entries(entry.get("top_failure_messages"))[:3],
                "run_ids": [],
            }
            grouped[signature] = group
        group["occurrence_count"] += 1
        group["run_ids"].append(entry["run_id"])
    return cast(
        list[dict[str, Any]],
        sorted(
            grouped.values(),
            key=lambda item: (-int(item["occurrence_count"]), str(item["latest_captured_at"])),
        ),
    )


def build_audit_run_entry(
    *,
    run_id: str,
    captured_at: str,
    snapshot_dir: Path,
    history_base: Path,
    source_dir: Path,
    report_kind: str,
    primary_payload: dict[str, Any],
    status_payload: dict[str, Any] | None,
    summary_payload: dict[str, Any] | None,
    collect_git_state: Callable[[], dict[str, Any]],
    sanitize_report_path: Callable[[Path], str],
) -> dict[str, Any]:
    git_state = collect_git_state()
    top_findings: list[dict[str, Any]] = []
    if status_payload is not None:
        top_findings = _mapping_entries(status_payload.get("top_findings"))
    if not top_findings:
        top_findings = _mapping_entries(primary_payload.get("top_findings"))

    selected_checks: list[str] = []
    if summary_payload is not None:
        selected_checks = _string_entries(summary_payload.get("selected_checks"))
    if not selected_checks:
        selected_checks = _string_entries(primary_payload.get("selected_checks"))
    recommendation = _json_mapping(primary_payload.get("recommendation"))
    if not selected_checks and recommendation is not None:
        selected_checks = _string_entries(recommendation.get("recommended_check_ids"))

    changed_files = _string_entries(primary_payload.get("changed_files"))

    base_stale_reasons: list[str] = []
    if git_state["dirty"] is True:
        base_stale_reasons.append("workspace-dirty-at-run-time")
    if git_state["head"] is None:
        base_stale_reasons.append("git-head-unavailable")

    profile = None
    if isinstance(primary_payload.get("profile"), str):
        profile = primary_payload["profile"]
    elif isinstance(status_payload, dict) and isinstance(status_payload.get("profile"), str):
        profile = status_payload["profile"]
    elif isinstance(summary_payload, dict) and isinstance(summary_payload.get("profile"), str):
        profile = summary_payload["profile"]

    fail_on = None
    if isinstance(primary_payload.get("fail_on"), str):
        fail_on = primary_payload["fail_on"]
    elif isinstance(status_payload, dict) and isinstance(status_payload.get("fail_on"), str):
        fail_on = status_payload["fail_on"]

    overall_status = None
    if isinstance(primary_payload.get("overall_status"), str):
        overall_status = primary_payload["overall_status"]
    elif isinstance(status_payload, dict) and isinstance(status_payload.get("overall_status"), str):
        overall_status = status_payload["overall_status"]

    canonical_command = None
    if isinstance(primary_payload.get("selected_command"), str):
        canonical_command = primary_payload["selected_command"]
    elif isinstance(summary_payload, dict) and isinstance(summary_payload.get("canonical_command"), str):
        canonical_command = summary_payload["canonical_command"]
    elif isinstance(status_payload, dict) and isinstance(status_payload.get("canonical_command"), str):
        canonical_command = status_payload["canonical_command"]

    return {
        "run_id": run_id,
        "captured_at": captured_at,
        "report_kind": report_kind,
        "profile": profile,
        "fail_on": fail_on,
        "overall_status": overall_status,
        "finish_gate_status": primary_payload.get("finish_gate_status")
        if isinstance(primary_payload.get("finish_gate_status"), str)
        else None,
        "canonical_command": canonical_command,
        "selected_surface": primary_payload.get("selected_surface")
        if isinstance(primary_payload.get("selected_surface"), str)
        else None,
        "selected_checks": selected_checks,
        "changed_files": changed_files,
        "finding_count": (
            status_payload.get("finding_count")
            if isinstance(status_payload, dict) and isinstance(status_payload.get("finding_count"), int)
            else summary_payload.get("finding_count")
            if isinstance(summary_payload, dict) and isinstance(summary_payload.get("finding_count"), int)
            else None
        ),
        "blocking_finding_count": (
            status_payload.get("blocking_finding_count")
            if isinstance(status_payload, dict) and isinstance(status_payload.get("blocking_finding_count"), int)
            else None
        ),
        "max_severity": (
            status_payload.get("max_severity")
            if isinstance(status_payload, dict) and isinstance(status_payload.get("max_severity"), str)
            else summary_payload.get("max_severity")
            if isinstance(summary_payload, dict) and isinstance(summary_payload.get("max_severity"), str)
            else None
        ),
        "top_failure_ids": [str(item.get("id")) for item in top_findings if isinstance(item.get("id"), str)][:5],
        "top_failure_messages": [
            str(item.get("message")) for item in top_findings if isinstance(item.get("message"), str)
        ][:5],
        "reports": dict(primary_payload.get("reports", {})) if isinstance(primary_payload.get("reports"), dict) else {},
        "output_dir": sanitize_report_path(source_dir),
        "history_base": sanitize_report_path(history_base),
        "history_path": sanitize_report_path(snapshot_dir),
        "snapshot_dir_name": snapshot_dir.name,
        "git_head": git_state["head"],
        "git_dirty": git_state["dirty"],
        "base_stale_reasons": base_stale_reasons,
    }


def write_audit_run_history(
    source_dir: Path,
    *,
    latest_output_dir: Path | None,
    report_kind: str,
    primary_payload: dict[str, Any],
    status_payload: dict[str, Any] | None,
    summary_payload: dict[str, Any] | None,
    history_filename: str,
    history_dirname: str,
    history_limit: int,
    schema_kind: str,
    schema_version: int,
    build_run_id: Callable[[], str],
    copy_snapshot: Callable[[Path, Path], None],
    load_history: Callable[[Path], list[dict[str, Any]]],
    build_entry: Callable[..., dict[str, Any]],
    history_stale_reasons: Callable[..., list[str]],
    build_failure_patterns: Callable[[list[dict[str, Any]]], list[dict[str, Any]]],
    sanitize_report_path: Callable[[Path], str],
    write_json: Callable[[Path, dict[str, Any]], Any] = write_json_artifact,
    repo_root: Path,
) -> dict[str, Any]:
    history_base = source_dir.resolve() if latest_output_dir is None else latest_output_dir.resolve()
    history_base.mkdir(parents=True, exist_ok=True)
    history_dir = history_base / history_dirname
    history_dir.mkdir(parents=True, exist_ok=True)

    run_id = build_run_id()
    snapshot_dir = history_dir / run_id
    copy_snapshot(source_dir, snapshot_dir)

    history_index_path = history_base / history_filename
    existing_runs = load_history(history_index_path)
    captured_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    current_entry = build_entry(
        run_id=run_id,
        captured_at=captured_at,
        snapshot_dir=snapshot_dir,
        history_base=history_base,
        source_dir=source_dir,
        report_kind=report_kind,
        primary_payload=primary_payload,
        status_payload=status_payload,
        summary_payload=summary_payload,
    )

    runs = [current_entry, *existing_runs]
    removed_runs = runs[history_limit:]
    runs = runs[:history_limit]

    for removed_entry in removed_runs:
        snapshot_dir_name = removed_entry.get("snapshot_dir_name")
        if isinstance(snapshot_dir_name, str) and snapshot_dir_name:
            snapshot_path = history_dir / snapshot_dir_name
        else:
            history_path_text = removed_entry.get("history_path")
            if not isinstance(history_path_text, str) or not history_path_text:
                continue
            snapshot_path = Path(history_path_text)
            if not snapshot_path.is_absolute():
                snapshot_path = repo_root / snapshot_path
        if snapshot_path.exists():
            shutil.rmtree(snapshot_path, ignore_errors=True)

    for index, entry in enumerate(runs):
        latest = index == 0
        stale_reasons = history_stale_reasons(entry, latest=latest)
        entry["latest"] = latest
        entry["likely_stale"] = bool(stale_reasons)
        entry["likely_stale_reasons"] = stale_reasons
        entry.pop("base_stale_reasons", None)

    payload = {
        "kind": schema_kind,
        "schema_version": schema_version,
        "generated_at": captured_at,
        "latest_output_dir": sanitize_report_path(history_base),
        "latest_run_id": runs[0]["run_id"],
        "retained_run_limit": history_limit,
        "run_count": len(runs),
        "reuse_guidance": {
            "prefer_latest_run_id": runs[0]["run_id"],
            "safe_to_reuse_when": [
                "the entry is latest",
                "likely_stale is false",
                "git_head still matches the current workspace HEAD",
                "the command and changed_files still match the question being answered",
            ],
        },
        "failure_patterns": build_failure_patterns(runs),
        "runs": runs,
    }
    write_json(history_base / history_filename, payload)
    write_json(source_dir / history_filename, payload)
    return payload


def write_repo_audit_run_history(
    source_dir: Path,
    *,
    latest_output_dir: Path | None,
    report_kind: str,
    primary_payload: dict[str, Any],
    status_payload: dict[str, Any] | None,
    summary_payload: dict[str, Any] | None,
    history_filename: str,
    history_dirname: str,
    history_limit: int,
    schema_kind: str,
    schema_version: int,
    build_run_id: Callable[[], str],
    copy_snapshot: Callable[[Path, Path], None],
    load_history_fn: Callable[[Path], list[dict[str, Any]]],
    collect_git_state_fn: Callable[[], dict[str, Any]],
    history_stale_reasons: Callable[..., list[str]],
    build_failure_patterns: Callable[[list[dict[str, Any]]], list[dict[str, Any]]],
    sanitize_report_path_fn: Callable[[Path], str],
    repo_root: Path,
    write_json: Callable[[Path, dict[str, Any]], Any] = write_json_artifact,
) -> dict[str, Any]:
    def _build_entry(**kwargs: Any) -> dict[str, Any]:
        return build_audit_run_entry(
            **kwargs,
            collect_git_state=collect_git_state_fn,
            sanitize_report_path=sanitize_report_path_fn,
        )

    return write_audit_run_history(
        source_dir,
        latest_output_dir=latest_output_dir,
        report_kind=report_kind,
        primary_payload=primary_payload,
        status_payload=status_payload,
        summary_payload=summary_payload,
        history_filename=history_filename,
        history_dirname=history_dirname,
        history_limit=history_limit,
        schema_kind=schema_kind,
        schema_version=schema_version,
        build_run_id=build_run_id,
        copy_snapshot=copy_snapshot,
        load_history=load_history_fn,
        build_entry=_build_entry,
        history_stale_reasons=history_stale_reasons,
        build_failure_patterns=build_failure_patterns,
        sanitize_report_path=sanitize_report_path_fn,
        write_json=write_json,
        repo_root=repo_root,
    )
