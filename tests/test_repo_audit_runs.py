from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from sattlint.devtools.artifact_readiness import ReadinessError
from sattlint.devtools.audit.repo_audit_runs import run_staged_repo_audit


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_complete_staged_audit(staged_output_dir: Path) -> None:
    _write_json(
        staged_output_dir / "progress.json",
        {
            "kind": "sattlint.repo_audit.progress",
            "overall_status": "pass",
            "completed_at": 1.0,
            "stages": [{"key": "write_reports", "status": "completed"}],
        },
    )
    _write_json(staged_output_dir / "status.json", {"kind": "sattlint.repo_audit.status", "overall_status": "pass"})
    _write_json(
        staged_output_dir / "summary.json",
        {
            "generated_by": "tests",
            "profile": "quick",
            "pipeline_ran": False,
            "pipeline_summary": None,
        },
    )
    _write_json(
        staged_output_dir / "findings.json",
        {
            "kind": "sattlint.findings",
            "schema_version": 1,
            "findings": [],
        },
    )


def test_run_staged_repo_audit_publishes_completed_directory(tmp_path):
    final_output_dir = tmp_path / "audit-quick-current"
    audit_calls: list[list[str]] = []

    def audit_main(argv: list[str] | None) -> int:
        assert argv is not None
        audit_calls.append(argv)
        staged_output_dir = Path(argv[argv.index("--output-dir") + 1])
        _write_complete_staged_audit(staged_output_dir)
        return 0

    result = run_staged_repo_audit(
        final_output_dir=final_output_dir,
        forwarded_args=["--profile", "quick"],
        audit_main=audit_main,
    )

    assert result.audit_exit_code == 0
    assert final_output_dir.exists()
    assert (final_output_dir / "summary.json").exists()
    assert result.staged_output_dir != final_output_dir
    assert audit_calls == [["--profile", "quick", "--output-dir", str(result.staged_output_dir)]]


def test_run_staged_repo_audit_keeps_previous_history_when_requested(tmp_path):
    final_output_dir = tmp_path / "audit-full-current"
    keep_history_dir = tmp_path / "history"
    _write_complete_staged_audit(final_output_dir)
    (final_output_dir / "marker.txt").write_text("previous", encoding="utf-8")

    def audit_main(argv: list[str] | None) -> int:
        assert argv is not None
        staged_output_dir = Path(argv[argv.index("--output-dir") + 1])
        _write_complete_staged_audit(staged_output_dir)
        (staged_output_dir / "marker.txt").write_text("current", encoding="utf-8")
        return 1

    result = run_staged_repo_audit(
        final_output_dir=final_output_dir,
        forwarded_args=["--profile", "full"],
        keep_history_dir=keep_history_dir,
        audit_main=audit_main,
    )

    assert result.audit_exit_code == 1
    assert (final_output_dir / "marker.txt").read_text(encoding="utf-8") == "current"
    archived_outputs = list(keep_history_dir.iterdir())
    assert len(archived_outputs) == 1
    assert (archived_outputs[0] / "marker.txt").read_text(encoding="utf-8") == "previous"


def test_run_staged_repo_audit_rejects_incomplete_results_without_replacing_existing_output(tmp_path):
    final_output_dir = tmp_path / "audit-full-current"
    _write_complete_staged_audit(final_output_dir)
    (final_output_dir / "marker.txt").write_text("stable", encoding="utf-8")

    def audit_main(argv: list[str] | None) -> int:
        assert argv is not None
        staged_output_dir = Path(argv[argv.index("--output-dir") + 1])
        _write_json(
            staged_output_dir / "progress.json",
            {
                "kind": "sattlint.repo_audit.progress",
                "overall_status": "running",
                "completed_at": None,
                "stages": [{"key": "write_reports", "status": "running"}],
            },
        )
        return 0

    with pytest.raises(ReadinessError, match=r"required file missing: status\.json"):
        run_staged_repo_audit(
            final_output_dir=final_output_dir,
            forwarded_args=["--profile", "full"],
            audit_main=audit_main,
        )

    assert (final_output_dir / "marker.txt").read_text(encoding="utf-8") == "stable"


def test_run_staged_repo_audit_cleans_staging_dir_when_readiness_check_fails(tmp_path):
    final_output_dir = tmp_path / "audit-full-current"
    seen: dict[str, Path] = {}

    def audit_main(argv: list[str] | None) -> int:
        assert argv is not None
        staged_output_dir = Path(argv[argv.index("--output-dir") + 1])
        seen["staged_output_dir"] = staged_output_dir
        _write_complete_staged_audit(staged_output_dir)
        return 0

    def readiness_check(staged_output_dir: Path) -> dict[str, object]:
        raise ReadinessError(f"staged output not ready: {staged_output_dir}")

    with pytest.raises(ReadinessError, match="staged output not ready"):
        run_staged_repo_audit(
            final_output_dir=final_output_dir,
            forwarded_args=["--profile", "full"],
            audit_main=audit_main,
            readiness_check=readiness_check,
        )

    assert seen["staged_output_dir"].exists() is False


def test_run_staged_repo_audit_rejects_forwarded_output_dir_override(tmp_path):
    with pytest.raises(ValueError, match="controls --output-dir"):
        run_staged_repo_audit(
            final_output_dir=tmp_path / "audit-full-current",
            forwarded_args=["--output-dir", "somewhere-else"],
        )


def test_run_staged_repo_audit_keeps_archived_output_when_cleanup_fails(monkeypatch, tmp_path):
    final_output_dir = tmp_path / "audit-quick-current"
    _write_complete_staged_audit(final_output_dir)
    (final_output_dir / "marker.txt").write_text("previous", encoding="utf-8")

    def audit_main(argv: list[str] | None) -> int:
        assert argv is not None
        staged_output_dir = Path(argv[argv.index("--output-dir") + 1])
        _write_complete_staged_audit(staged_output_dir)
        (staged_output_dir / "marker.txt").write_text("current", encoding="utf-8")
        return 0

    def fail_rmtree(path: Path, ignore_errors: bool = False, onerror=None) -> None:
        raise OSError(f"cleanup failed for {path}")

    monkeypatch.setattr(shutil, "rmtree", fail_rmtree)

    result = run_staged_repo_audit(
        final_output_dir=final_output_dir,
        forwarded_args=["--profile", "quick"],
        audit_main=audit_main,
    )

    assert result.audit_exit_code == 0
    assert (final_output_dir / "marker.txt").read_text(encoding="utf-8") == "current"
    assert result.archived_output_dir is not None
    assert result.archived_output_dir.exists()
    assert (result.archived_output_dir / "marker.txt").read_text(encoding="utf-8") == "previous"
