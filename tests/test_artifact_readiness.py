from __future__ import annotations

import json
from pathlib import Path

import pytest

from sattlint.devtools.artifact_readiness import assert_artifact_dir_ready, build_artifact_readiness_report
from sattlint.devtools.compare_audit_findings import build_audit_findings_comparison


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _finding(finding_id: str, *, path: str, line: int, fingerprint: str) -> dict[str, object]:
    return {
        "id": finding_id,
        "rule_id": finding_id,
        "message": f"{finding_id} message",
        "severity": "medium",
        "confidence": "high",
        "source": "repo-audit",
        "location": {
            "path": path,
            "line": line,
            "column": None,
            "end_line": None,
            "end_column": None,
            "symbol": None,
        },
        "fingerprint": fingerprint,
        "data": {},
    }


def _pipeline_artifact_registry() -> dict[str, object]:
    return {
        "artifacts": [
            {"artifact_id": "progress", "filename": "progress.json", "enabled": True, "blocking": False},
            {"artifact_id": "status", "filename": "status.json", "enabled": True, "blocking": True},
            {"artifact_id": "summary", "filename": "summary.json", "enabled": True, "blocking": True},
            {"artifact_id": "findings", "filename": "findings.json", "enabled": True, "blocking": True},
            {"artifact_id": "ruff", "filename": "ruff.json", "enabled": True, "blocking": True},
            {"artifact_id": "pyright", "filename": "pyright.json", "enabled": True, "blocking": True},
            {"artifact_id": "pytest", "filename": "pytest.json", "enabled": True, "blocking": True},
        ]
    }


def _write_ready_audit_dir(root: Path, *, findings: list[dict[str, object]] | None = None) -> None:
    findings_payload = {
        "kind": "sattlint.findings",
        "schema_version": 1,
        "findings": findings or [],
    }
    _write_json(
        root / "progress.json",
        {
            "kind": "sattlint.repo_audit.progress",
            "overall_status": "pass",
            "completed_at": 1.0,
            "stages": [{"key": "write_reports", "status": "completed"}],
        },
    )
    _write_json(
        root / "status.json",
        {
            "kind": "sattlint.repo_audit.status",
            "overall_status": "pass",
        },
    )
    _write_json(
        root / "summary.json",
        {
            "generated_by": "tests",
            "profile": "full",
            "pipeline_ran": True,
            "pipeline_summary": {"artifact_registry": _pipeline_artifact_registry()},
        },
    )
    _write_json(root / "findings.json", findings_payload)
    _write_json(
        root / "pipeline/progress.json",
        {
            "kind": "sattlint.pipeline.progress",
            "overall_status": "pass",
            "completed_at": 1.0,
            "stages": [{"key": "pytest", "status": "completed"}],
        },
    )
    for filename in ("status.json", "summary.json", "findings.json", "ruff.json", "pyright.json", "pytest.json"):
        _write_json(root / "pipeline" / filename, {"kind": filename.removesuffix(".json")})


def test_artifact_readiness_accepts_completed_repo_audit_directory(tmp_path):
    artifact_dir = tmp_path / "audit-full-current"
    _write_ready_audit_dir(artifact_dir)

    report = build_artifact_readiness_report(artifact_dir)

    assert report["ready"] is True
    assert report["state"] == "complete"
    assert report["missing_files"] == []
    assert "pipeline/pytest.json" in report["required_files"]
    assert_artifact_dir_ready(artifact_dir)


def test_artifact_readiness_rejects_pending_progress_and_missing_pipeline_files(tmp_path):
    artifact_dir = tmp_path / "audit-full-current"
    _write_ready_audit_dir(artifact_dir)
    _write_json(
        artifact_dir / "progress.json",
        {
            "kind": "sattlint.repo_audit.progress",
            "overall_status": "running",
            "completed_at": None,
            "stages": [{"key": "write_reports", "status": "running"}],
        },
    )
    (artifact_dir / "pipeline" / "pytest.json").unlink()

    report = build_artifact_readiness_report(artifact_dir)

    assert report["ready"] is False
    assert report["state"] == "incomplete"
    assert report["message"] == "required file missing: pipeline/pytest.json"


def test_artifact_readiness_rejects_incomplete_failed_run(tmp_path):
    artifact_dir = tmp_path / "audit-full-current"
    _write_ready_audit_dir(artifact_dir)
    _write_json(
        artifact_dir / "summary.json",
        {
            "generated_by": "tests",
            "profile": "full",
            "pipeline_ran": True,
            "pipeline_summary": None,
            "error": {"message": "pipeline crashed"},
        },
    )

    report = build_artifact_readiness_report(artifact_dir)

    assert report["ready"] is False
    assert report["message"] == "pipeline summary missing from completed audit"


def test_compare_audit_findings_reports_resolved_new_and_unchanged(tmp_path):
    before_dir = tmp_path / "before"
    after_dir = tmp_path / "after"
    shared = _finding("shared", path="src/shared.py", line=1, fingerprint="shared-fp")
    resolved = _finding("resolved", path="src/old.py", line=2, fingerprint="resolved-fp")
    new = _finding("new", path="src/new.py", line=3, fingerprint="new-fp")
    _write_ready_audit_dir(before_dir, findings=[shared, resolved])
    _write_ready_audit_dir(after_dir, findings=[shared, new])

    report = build_audit_findings_comparison(before_dir, after_dir)

    assert report["summary"] == {
        "new_count": 1,
        "resolved_count": 1,
        "changed_count": 0,
        "unchanged_count": 1,
    }
    assert report["findings"]["new"] == [
        {
            "id": "new",
            "path": "src/new.py",
            "line": 3,
            "symbol": None,
            "fingerprint": "new-fp",
        }
    ]
    assert report["findings"]["resolved"] == [
        {
            "id": "resolved",
            "path": "src/old.py",
            "line": 2,
            "symbol": None,
            "fingerprint": "resolved-fp",
        }
    ]


def test_artifact_readiness_reports_missing_directory(tmp_path):
    report = build_artifact_readiness_report(tmp_path / "missing-audit")

    assert report["ready"] is False
    assert report["state"] == "missing"
    assert report["message"] == "artifact directory does not exist"

    with pytest.raises(RuntimeError, match="artifact directory does not exist"):
        assert_artifact_dir_ready(tmp_path / "missing-audit")
