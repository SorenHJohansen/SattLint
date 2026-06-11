"""Check whether a repo-audit artifact directory is complete and safe to read."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, cast

from sattlint.devtools.artifact_registry import AUDIT_ARTIFACTS
from sattlint.devtools.json_helpers import json_mapping as _json_mapping

READINESS_SCHEMA_KIND = "sattlint.artifact_readiness"
READINESS_SCHEMA_VERSION = 1


class ReadinessError(RuntimeError):
    """Raised when an artifact directory is missing or still unsafe to read."""


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload_dict = _json_mapping(payload)
    if payload_dict is None:
        raise ValueError(f"{path.name} must contain a JSON object.")
    return payload_dict


def _contains_incomplete_stage(progress_payload: dict[str, Any]) -> bool:
    overall_status = str(progress_payload.get("overall_status") or "").casefold()
    if overall_status in {"pending", "running"}:
        return True
    if progress_payload.get("completed_at") is None:
        return True
    stages = progress_payload.get("stages")
    if not isinstance(stages, list):
        return False
    return any(
        (stage := _json_mapping(stage_obj)) is not None
        and str(stage.get("status") or "").casefold() in {"pending", "running"}
        for stage_obj in cast(list[object], stages)
    )


def _required_root_artifacts() -> list[str]:
    return [artifact.filename for artifact in AUDIT_ARTIFACTS if not artifact.optional]


def _required_pipeline_artifacts(summary_payload: dict[str, Any]) -> tuple[list[str], str | None]:
    if summary_payload.get("pipeline_ran") is not True:
        return [], None
    pipeline_summary = _json_mapping(summary_payload.get("pipeline_summary"))
    if pipeline_summary is None:
        return [], "pipeline summary missing from completed audit"
    artifact_registry = _json_mapping(pipeline_summary.get("artifact_registry"))
    if artifact_registry is None:
        return [], "pipeline artifact registry missing from completed audit"
    artifacts = artifact_registry.get("artifacts")
    if not isinstance(artifacts, list):
        return [], "pipeline artifact registry is malformed"
    required: list[str] = []
    for artifact_obj in cast(list[object], artifacts):
        artifact = _json_mapping(artifact_obj)
        if artifact is None:
            continue
        artifact_id = artifact.get("artifact_id")
        filename = artifact.get("filename")
        if not isinstance(filename, str) or not filename:
            continue
        if not artifact.get("enabled"):
            continue
        if artifact.get("blocking") or artifact_id == "progress":
            required.append(f"pipeline/{filename}")
    return sorted(dict.fromkeys(required)), None


def build_artifact_readiness_report(artifact_dir: Path) -> dict[str, Any]:  # noqa: PLR0915
    resolved_dir = artifact_dir.resolve()
    report: dict[str, Any] = {
        "kind": READINESS_SCHEMA_KIND,
        "schema_version": READINESS_SCHEMA_VERSION,
        "artifact_dir": resolved_dir.as_posix(),
        "state": "missing",
        "ready": False,
        "message": "artifact directory does not exist",
        "required_files": [],
        "missing_files": [],
        "profile": None,
        "overall_status": None,
        "pipeline_ran": None,
    }
    if not resolved_dir.exists() or not resolved_dir.is_dir():
        return report

    required_files = _required_root_artifacts()
    report["required_files"] = required_files.copy()

    payload_errors: list[str] = []
    progress_payload: dict[str, Any] | None = None
    summary_payload: dict[str, Any] | None = None
    status_payload: dict[str, Any] | None = None

    progress_path = resolved_dir / "progress.json"
    summary_path = resolved_dir / "summary.json"
    status_path = resolved_dir / "status.json"

    for path, label in ((progress_path, "progress.json"), (summary_path, "summary.json"), (status_path, "status.json")):
        if not path.exists():
            continue
        try:
            payload = _load_json(path)
        except (OSError, ValueError, json.JSONDecodeError) as error:
            payload_errors.append(f"{label} unreadable: {error}")
            continue
        if label == "progress.json":
            progress_payload = payload
        elif label == "summary.json":
            summary_payload = payload
        else:
            status_payload = payload

    report["profile"] = summary_payload.get("profile") if isinstance(summary_payload, dict) else None
    report["overall_status"] = (
        status_payload.get("overall_status")
        if isinstance(status_payload, dict)
        else progress_payload.get("overall_status")
        if isinstance(progress_payload, dict)
        else None
    )
    report["pipeline_ran"] = summary_payload.get("pipeline_ran") if isinstance(summary_payload, dict) else None

    pipeline_required: list[str] = []
    pipeline_contract_error: str | None = None
    if isinstance(summary_payload, dict):
        pipeline_required, pipeline_contract_error = _required_pipeline_artifacts(summary_payload)
        report["required_files"].extend(pipeline_required)

    missing_files = [relative for relative in report["required_files"] if not (resolved_dir / relative).exists()]
    report["missing_files"] = missing_files

    progress_pending = isinstance(progress_payload, dict) and _contains_incomplete_stage(progress_payload)
    report["progress_pending"] = progress_pending

    summary_error: object = cast(object, summary_payload.get("error")) if isinstance(summary_payload, dict) else None
    status_error: object = cast(object, status_payload.get("error")) if isinstance(status_payload, dict) else None

    if payload_errors:
        report["state"] = "incomplete"
        report["message"] = payload_errors[0]
        return report
    if missing_files:
        report["state"] = "incomplete"
        report["message"] = f"required file missing: {missing_files[0]}"
        return report
    if pipeline_contract_error is not None:
        report["state"] = "incomplete"
        report["message"] = pipeline_contract_error
        return report
    if progress_pending:
        report["state"] = "incomplete"
        report["message"] = "progress pending"
        return report
    summary_error_payload = cast(dict[str, Any], summary_error) if isinstance(summary_error, dict) else None
    status_error_payload = cast(dict[str, Any], status_error) if isinstance(status_error, dict) else None
    if summary_error_payload is not None or status_error_payload is not None:
        report["state"] = "incomplete"
        error_payload = summary_error_payload or status_error_payload or {}
        error_message = str(error_payload.get("message") or "audit failed before publication")
        report["message"] = f"audit failed before completion: {error_message}"
        return report

    report["state"] = "complete"
    report["ready"] = True
    report["message"] = "artifact directory is complete and safe to read"
    return report


def assert_artifact_dir_ready(artifact_dir: Path) -> dict[str, Any]:
    report = build_artifact_readiness_report(artifact_dir)
    if not report["ready"]:
        raise ReadinessError(str(report["message"]))
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check whether a repo-audit artifact directory is complete.")
    parser.add_argument("--artifact-dir", required=True, help="Repo-audit artifact directory to validate")
    args = parser.parse_args(argv)
    report = build_artifact_readiness_report(Path(args.artifact_dir))
    print(json.dumps(report, indent=2, sort_keys=True))
    if report["ready"]:
        return 0
    print(str(report["message"]), file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
