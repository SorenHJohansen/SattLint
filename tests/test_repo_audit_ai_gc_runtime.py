import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from sattlint.devtools import _repo_audit_ai_gc as repo_audit_ai_gc
from sattlint.devtools import ai_gc, repo_audit


def _artifact_path(*parts: str) -> str:
    return "/".join(("<external>", *parts))


def test_audit_repository_ignores_active_output_dir_ai_gc_manifest_drift(tmp_path):
    output_dir = tmp_path / "artifacts" / "audit"
    output_dir_path = (
        repo_audit.sanitize_path_for_report(output_dir, repo_root=repo_audit.REPO_ROOT) or output_dir.as_posix()
    )
    stale_finding = repo_audit.Finding(
        "stale-generated-output-manifest",
        "maintenance",
        "medium",
        "high",
        "Generated output drifted from its source-digest manifest.",
        path=output_dir_path,
        source="ai-gc",
    )
    ai_gc_report = {
        "kind": "sattlint.ai_gc",
        "schema_version": 1,
        "generated_by": "sattlint.devtools.ai_gc",
        "mode": "report",
        "root": ".",
        "stale_after_days": 14,
        "max_ledger_lines": 500,
        "status": "needs-attention",
        "summary": {
            "candidate_count": 1,
            "artifact_candidate_count": 1,
            "manifest_drift_candidate_count": 1,
            "ledger_candidate_count": 0,
            "applied_count": 0,
            "failure_count": 0,
            "total_candidate_bytes": 1,
        },
        "candidates": [
            {
                "candidate_id": "stale-generated-output-manifest",
                "path": output_dir_path,
                "kind": "directory",
                "action": "delete",
                "safe_to_apply": True,
                "reason": "Generated output drifted from its source-digest manifest.",
                "manifest_count": 1,
                "drifted_sources": ["src/sattlint/devtools/ai_gc.py"],
                "missing_sources": [],
                "invalid_manifests": [],
                "applied": False,
            }
        ],
        "applied_actions": [],
        "failures": [],
    }
    pipeline_summary = {
        "profile": "quick",
        "output_dir": "<external>/audit/pipeline",
        "status": {"overall_status": "pass", "tool_statuses": {}},
    }

    with (
        patch.object(repo_audit, "collect_custom_findings", return_value=[stale_finding]),
        patch.object(repo_audit, "_find_pipeline_findings", return_value=[]),
        patch.object(repo_audit.pipeline_module, "_run_pipeline", return_value=pipeline_summary),
        patch.object(repo_audit, "build_ai_gc_report", return_value=ai_gc_report),
    ):
        summary = repo_audit.audit_repository(
            output_dir,
            profile="quick",
            fail_on="high",
            include_generated=False,
            leaks_only=False,
            suspicious_identifiers=["SQHJ"],
            skip_pipeline=False,
            skip_vulture=False,
            skip_bandit=False,
        )

    assert summary["finding_count"] == 0
    assert summary["findings"] == []
    ai_gc_payload = json.loads((output_dir / "ai_gc.json").read_text(encoding="utf-8"))
    assert ai_gc_payload["status"] == "pass"
    assert ai_gc_payload["summary"]["candidate_count"] == 0


def test_ai_gc_helpers_build_findings_and_filter_reports():
    assert repo_audit_ai_gc._repo_audit_ai_gc_module().Finding is repo_audit.Finding

    findings = repo_audit_ai_gc._ai_gc_report_findings(
        {
            "candidates": [
                {"candidate_id": "skip-me", "applied": True},
                {
                    "candidate_id": "stale-generated-output-manifest",
                    "path": _artifact_path("audit"),
                    "reason": "digest drift",
                    "applied": False,
                },
                {
                    "candidate_id": "stale-ai-artifact",
                    "path": _artifact_path("tmp.json"),
                    "age_days": 45,
                    "size_bytes": 128,
                    "applied": False,
                },
                {
                    "path": _artifact_path("other.json"),
                    "reason": "manual cleanup",
                    "applied": False,
                },
            ]
        }
    )

    assert [(finding.id, finding.severity) for finding in findings] == [
        ("stale-generated-output-manifest", "medium"),
        ("stale-ai-artifact", "medium"),
        ("ai-gc", "low"),
    ]
    assert findings[0].detail == "digest drift"
    assert findings[1].detail == "age_days=45 size_bytes=128"
    assert findings[2].detail == "manual cleanup"
    assert all(finding.source == "ai-gc" for finding in findings)

    output_path = _artifact_path("audit")
    report = {
        "mode": "report",
        "summary": {
            "candidate_count": 2,
            "artifact_candidate_count": 2,
            "manifest_drift_candidate_count": 1,
        },
        "candidates": [
            {"candidate_id": "stale-generated-output-manifest", "path": output_path},
            {"candidate_id": "stale-ai-artifact", "path": _artifact_path("old.json")},
        ],
        "failures": [],
    }

    filtered = repo_audit_ai_gc._filter_ai_gc_report_for_output_dir(report, output_dir_path=output_path)

    assert filtered["candidates"] == [{"candidate_id": "stale-ai-artifact", "path": _artifact_path("old.json")}]
    assert filtered["summary"] == {
        "candidate_count": 1,
        "artifact_candidate_count": 1,
        "manifest_drift_candidate_count": 0,
    }
    assert filtered["status"] == "needs-attention"

    failed = repo_audit_ai_gc._filter_ai_gc_report_for_output_dir(
        {**report, "failures": ["still broken"]},
        output_dir_path=output_path,
    )
    assert failed["status"] == "fail"

    applied = repo_audit_ai_gc._filter_ai_gc_report_for_output_dir(
        {
            **report,
            "mode": "apply",
            "candidates": [{"candidate_id": "stale-generated-output-manifest", "path": output_path}],
        },
        output_dir_path=output_path,
    )
    assert applied["status"] == "pass"


def test_ai_gc_helpers_passthrough_path_matching_and_findings_filtering():
    output_path = _artifact_path("audit")
    assert repo_audit_ai_gc._is_active_output_ai_gc_path(None, output_dir_path=output_path) is False
    assert repo_audit_ai_gc._is_active_output_ai_gc_path(f"{output_path}/", output_dir_path=output_path) is True

    passthrough = {"candidates": "not-a-list"}
    assert repo_audit_ai_gc._filter_ai_gc_report_for_output_dir(passthrough, output_dir_path=output_path) is passthrough

    unchanged = {"candidates": [{"candidate_id": "stale-ai-artifact", "path": _artifact_path("old.json")}]}
    assert repo_audit_ai_gc._filter_ai_gc_report_for_output_dir(unchanged, output_dir_path=output_path) is unchanged

    findings = [
        repo_audit.Finding(
            id="stale-generated-output-manifest",
            category="maintenance",
            severity="medium",
            confidence="high",
            message="Generated output drifted from its source-digest manifest.",
            path=output_path,
            source="ai-gc",
        ),
        repo_audit.Finding(
            id="stale-ai-artifact",
            category="maintenance",
            severity="low",
            confidence="high",
            message="Stale AI-generated artifact can be collected.",
            path=_artifact_path("old.json"),
            source="ai-gc",
        ),
        SimpleNamespace(id="other", path=output_path, source="custom"),
    ]

    filtered_findings = repo_audit_ai_gc._filter_ai_gc_findings_for_output_dir(
        findings,
        output_dir_path=output_path,
    )

    assert [finding.id for finding in filtered_findings] == ["stale-ai-artifact", "other"]


def test_path_size_bytes_skips_children_that_disappear_during_stat(monkeypatch, tmp_path):
    present_child = tmp_path / "present.json"
    present_child.write_text("1234", encoding="utf-8")

    class _MissingChild:
        def is_file(self) -> bool:
            return True

        def stat(self):
            raise FileNotFoundError("gone")

    monkeypatch.setattr(Path, "rglob", lambda self, pattern: [present_child, _MissingChild()])

    assert ai_gc._path_size_bytes(tmp_path) == 4
