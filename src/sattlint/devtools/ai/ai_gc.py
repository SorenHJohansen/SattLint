"""Safe AI garbage-collection report and apply helpers."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess  # nosec
import time
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from sattlint.devtools.artifact_registry import AI_GC_REPORT_FILENAME, AI_GC_SCHEMA_KIND, AI_GC_SCHEMA_VERSION
from sattlint.devtools.shared.pipeline_artifacts import artifact_source_manifest_path
from sattlint.path_sanitizer import sanitize_path_for_report

DEFAULT_STALE_AFTER_DAYS = 14
ALLOWLIST_ROOTS = (
    Path("artifacts"),
    Path("docs") / "generated",
)
SOURCE_MANIFEST_SUFFIX = ".sources.json"


def _normalize_rel_path(path: str) -> str:
    return path.strip().replace("\\", "/").strip("/")


def _list_tracked_paths(root: Path) -> tuple[str, ...]:
    git_executable = shutil.which("git")
    if git_executable is None:
        return ()
    try:
        # Fixed local git command for tracked-path discovery.
        completed = subprocess.run(  # nosec
            [git_executable, "ls-files", "-z"],
            cwd=root,
            capture_output=True,
            check=False,
        )
    except OSError:
        return ()
    if completed.returncode != 0:
        return ()
    return tuple(
        _normalize_rel_path(item)
        for item in completed.stdout.decode("utf-8", errors="ignore").split("\x00")
        if item.strip()
    )


def _candidate_has_tracked_descendants(candidate_rel_path: str, tracked_paths: tuple[str, ...]) -> bool:
    prefix = f"{candidate_rel_path}/"
    return any(path == candidate_rel_path or path.startswith(prefix) for path in tracked_paths)


def _path_size_bytes(path: Path) -> int:
    if path.is_file():
        return path.stat().st_size
    total = 0
    for child in path.rglob("*"):
        if child.is_file():
            try:
                total += child.stat().st_size
            except OSError:
                continue
    return total


def _path_mtime(path: Path) -> float:
    latest = path.stat().st_mtime
    if path.is_dir():
        for child in path.rglob("*"):
            try:
                child_mtime = child.stat().st_mtime
            except OSError:
                continue
            if child_mtime > latest:
                latest = child_mtime
    return latest


def _file_sha1(path: Path) -> str:
    digest = hashlib.sha1(usedforsecurity=False)
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return f"sha1:{digest.hexdigest()}"


def _iter_candidate_manifest_paths(candidate_path: Path) -> list[Path]:
    if candidate_path.is_dir():
        return sorted(path for path in candidate_path.rglob(f"*{SOURCE_MANIFEST_SUFFIX}") if path.is_file())
    manifest_path = artifact_source_manifest_path(candidate_path)
    return [manifest_path] if manifest_path.exists() else []


def _resolve_manifest_source_path(root: Path, raw_path: str) -> Path:
    source_path = Path(raw_path)
    return source_path if source_path.is_absolute() else root / source_path


def _manifest_drift_details(root: Path, candidate_path: Path) -> dict[str, Any] | None:
    manifest_paths = _iter_candidate_manifest_paths(candidate_path)
    if not manifest_paths:
        return None

    drifted_sources: list[str] = []
    missing_sources: list[str] = []
    invalid_manifests: list[str] = []
    for manifest_path in manifest_paths:
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            invalid_manifests.append(manifest_path.as_posix())
            continue
        for source_entry in payload.get("sources", []):
            source_name = str(source_entry.get("path") or "")
            if not source_name:
                continue
            resolved_source_path = _resolve_manifest_source_path(root, source_name)
            if not resolved_source_path.exists():
                missing_sources.append(source_name)
                continue
            expected_digest = source_entry.get("digest")
            if (
                expected_digest
                and resolved_source_path.is_file()
                and _file_sha1(resolved_source_path) != expected_digest
            ):
                drifted_sources.append(source_name)

    if not drifted_sources and not missing_sources and not invalid_manifests:
        return None

    reason_parts: list[str] = []
    if drifted_sources:
        reason_parts.append(f"changed sources: {', '.join(sorted(set(drifted_sources))[:3])}")
    if missing_sources:
        reason_parts.append(f"missing sources: {', '.join(sorted(set(missing_sources))[:3])}")
    if invalid_manifests:
        reason_parts.append(f"invalid manifests: {', '.join(Path(path).name for path in invalid_manifests[:3])}")
    return {
        "manifest_count": len(manifest_paths),
        "drifted_sources": sorted(set(drifted_sources)),
        "missing_sources": sorted(set(missing_sources)),
        "invalid_manifests": sorted(set(invalid_manifests)),
        "reason": "; ".join(reason_parts),
    }


def _iter_allowlisted_candidates(root: Path, tracked_paths: tuple[str, ...]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for rel_root in ALLOWLIST_ROOTS:
        base_path = root / rel_root
        if not base_path.exists():
            continue
        for child in sorted(base_path.iterdir(), key=lambda item: item.as_posix()):
            if child.is_file() and child.name.endswith(SOURCE_MANIFEST_SUFFIX):
                continue
            rel_path = child.relative_to(root).as_posix()
            if _candidate_has_tracked_descendants(rel_path, tracked_paths):
                continue
            candidates.append(
                {
                    "path_obj": child,
                    "path": rel_path,
                    "kind": "directory" if child.is_dir() else "file",
                    "action": "delete",
                    "safe_to_apply": True,
                }
            )
    return candidates


def build_ai_gc_report(
    root: Path,
    *,
    tracked_paths: Iterable[str] | None = None,
    stale_after_days: int = DEFAULT_STALE_AFTER_DAYS,
    now_ts: float | None = None,
    apply: bool = False,
) -> dict[str, Any]:
    resolved_root = root.resolve()
    normalized_tracked_paths = (
        tuple(_normalize_rel_path(path) for path in tracked_paths)
        if tracked_paths is not None
        else _list_tracked_paths(resolved_root)
    )
    effective_now = time.time() if now_ts is None else now_ts
    stale_cutoff_seconds = stale_after_days * 24 * 60 * 60

    candidates: list[dict[str, Any]] = []
    for candidate in _iter_allowlisted_candidates(resolved_root, normalized_tracked_paths):
        age_seconds = max(effective_now - _path_mtime(candidate["path_obj"]), 0)
        manifest_drift = _manifest_drift_details(resolved_root, candidate["path_obj"])
        if manifest_drift is None and age_seconds < stale_cutoff_seconds:
            continue
        age_days = int(age_seconds // (24 * 60 * 60))
        candidate_id = "stale-generated-output-manifest" if manifest_drift is not None else "stale-ai-artifact"
        candidates.append(
            {
                "candidate_id": candidate_id,
                "path": candidate["path"],
                "kind": candidate["kind"],
                "action": candidate["action"],
                "safe_to_apply": candidate["safe_to_apply"],
                "age_days": age_days,
                "size_bytes": _path_size_bytes(candidate["path_obj"]),
                "reason": (
                    f"Generated output drifted from its source-digest manifest ({manifest_drift['reason']})."
                    if manifest_drift is not None
                    else f"Untracked allowlisted artifact is older than {stale_after_days} days."
                ),
                "manifest_count": 0 if manifest_drift is None else manifest_drift["manifest_count"],
                "drifted_sources": [] if manifest_drift is None else manifest_drift["drifted_sources"],
                "missing_sources": [] if manifest_drift is None else manifest_drift["missing_sources"],
                "invalid_manifests": [] if manifest_drift is None else manifest_drift["invalid_manifests"],
                "applied": False,
            }
        )

    applied_actions: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    if apply:
        for candidate in candidates:
            target_path = resolved_root / candidate["path"]
            try:
                if candidate["action"] == "delete":
                    if target_path.is_dir():
                        shutil.rmtree(target_path)
                    elif target_path.exists():
                        target_path.unlink()
                        artifact_source_manifest_path(target_path).unlink(missing_ok=True)
                candidate["applied"] = True
                applied_actions.append(
                    {
                        "path": candidate["path"],
                        "action": candidate["action"],
                    }
                )
            except OSError as exc:
                failures.append(
                    {
                        "path": candidate["path"],
                        "action": candidate["action"],
                        "error": str(exc),
                        "error_type": type(exc).__name__,
                    }
                )

    total_candidate_bytes = sum(int(candidate.get("size_bytes", 0) or 0) for candidate in candidates)
    status = "pass"
    if failures:
        status = "fail"
    elif candidates and not apply:
        status = "needs-attention"

    return {
        "kind": AI_GC_SCHEMA_KIND,
        "schema_version": AI_GC_SCHEMA_VERSION,
        "generated_by": "sattlint.devtools.ai.ai_gc",
        "mode": "apply" if apply else "report",
        "root": sanitize_path_for_report(resolved_root, repo_root=resolved_root) or resolved_root.as_posix(),
        "stale_after_days": stale_after_days,
        "status": status,
        "summary": {
            "candidate_count": len(candidates),
            "artifact_candidate_count": sum(
                1
                for candidate in candidates
                if candidate["candidate_id"] in {"stale-ai-artifact", "stale-generated-output-manifest"}
            ),
            "manifest_drift_candidate_count": sum(
                1 for candidate in candidates if candidate["candidate_id"] == "stale-generated-output-manifest"
            ),
            "applied_count": len(applied_actions),
            "failure_count": len(failures),
            "total_candidate_bytes": total_candidate_bytes,
        },
        "candidates": candidates,
        "applied_actions": applied_actions,
        "failures": failures,
    }


__all__ = [
    "AI_GC_REPORT_FILENAME",
    "AI_GC_SCHEMA_KIND",
    "AI_GC_SCHEMA_VERSION",
    "DEFAULT_STALE_AFTER_DAYS",
    "build_ai_gc_report",
]
