from __future__ import annotations

from contextlib import nullcontext
from pathlib import Path

from sattlint.devtools import repo_audit
from tests import test_repo_audit as repo_audit_tests


def test_doc_gardener_flags_markdown_mojibake(tmp_path):
    repo_audit_tests.test_doc_gardener_flags_markdown_mojibake(tmp_path)


def test_doc_gardener_scan_agents_md_reports_missing_and_structure_findings(tmp_path):
    repo_audit_tests.test_doc_gardener_scan_agents_md_reports_missing_and_structure_findings(tmp_path)


def test_doc_gardener_scan_dead_links_and_structure_findings(tmp_path):
    repo_audit_tests.test_doc_gardener_scan_dead_links_and_structure_findings(tmp_path)


def test_doc_gardener_scan_ai_first_source_drift_reports_missing_ledger_section(tmp_path):
    repo_audit_tests.test_doc_gardener_scan_ai_first_source_drift_reports_missing_ledger_section(tmp_path)


def test_doc_gardener_scan_ai_first_status_drift_reports_mismatch(tmp_path):
    repo_audit_tests.test_doc_gardener_scan_ai_first_status_drift_reports_mismatch(tmp_path)


def test_doc_gardener_run_scan_aggregates_findings(monkeypatch):
    repo_audit_tests.test_doc_gardener_run_scan_aggregates_findings(monkeypatch)


def test_doc_gardener_main_reports_findings_without_opening_pr_by_default(monkeypatch, capsys):
    repo_audit_tests.test_doc_gardener_main_reports_findings_without_opening_pr_by_default(monkeypatch, capsys)


def test_update_quality_score_creates_trend_section_from_pipeline_snapshot(tmp_path):
    repo_audit_tests.test_update_quality_score_creates_trend_section_from_pipeline_snapshot(tmp_path)


def test_load_pipeline_snapshot_returns_message_when_artifacts_missing(tmp_path):
    repo_audit_tests.test_load_pipeline_snapshot_returns_message_when_artifacts_missing(tmp_path)


def test_load_pipeline_snapshot_falls_back_to_findings_json_count(tmp_path):
    repo_audit_tests.test_load_pipeline_snapshot_falls_back_to_findings_json_count(tmp_path)


def test_doc_gardener_main_uses_pipeline_output_dir(monkeypatch, capsys, tmp_path):
    repo_audit_tests.test_doc_gardener_main_uses_pipeline_output_dir(monkeypatch, capsys, tmp_path)


def test_run_harness_freshness_check_translates_ai_and_doc_findings(monkeypatch, tmp_path):
    repo_audit_tests.test_run_harness_freshness_check_translates_ai_and_doc_findings(monkeypatch, tmp_path)


def test_patch_doc_gardener_paths_delegates_to_compat(monkeypatch, tmp_path):
    sentinel = nullcontext()
    observed: dict[str, object] = {}

    def fake_patch(root: Path, *, doc_gardener_module: object):
        observed["root"] = root
        observed["doc_gardener_module"] = doc_gardener_module
        return sentinel

    monkeypatch.setattr(repo_audit._repo_audit_compat_module, "patch_doc_gardener_paths", fake_patch)

    result = repo_audit._patch_doc_gardener_paths(tmp_path)

    assert result is sentinel
    assert observed == {
        "root": tmp_path,
        "doc_gardener_module": repo_audit._doc_gardener_module,
    }
