import json
from unittest.mock import patch

from sattlint.devtools import repo_audit


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
