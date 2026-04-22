"""Shared assertions for machine-readable artifact contracts."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

EXPECTED_FINDINGS_SCHEMA = {
    "kind": "sattlint.findings",
    "schema_version": 1,
}
EXPECTED_ANALYSIS_DIFF_SCHEMA = {
    "kind": "sattlint.analysis_diff",
    "schema_version": 1,
}
EXPECTED_CORPUS_RESULTS_SCHEMA = {
    "kind": "sattlint.corpus_results",
    "schema_version": 1,
}


def load_golden_payload(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def assert_matches_golden(payload: Any, golden_path: str | Path) -> None:
    assert payload == load_golden_payload(golden_path)


def assert_findings_schema(payload: Mapping[str, Any], *, key: str = "findings_schema") -> None:
    assert payload.get(key) == EXPECTED_FINDINGS_SCHEMA


def assert_findings_collection(
    payload: Mapping[str, Any],
    *,
    finding_count: int | None = None,
    rule_ids: Sequence[str] | None = None,
) -> None:
    assert payload["kind"] == EXPECTED_FINDINGS_SCHEMA["kind"]
    assert payload["schema_version"] == EXPECTED_FINDINGS_SCHEMA["schema_version"]
    if finding_count is not None:
        assert payload["finding_count"] == finding_count
    if rule_ids is not None:
        assert [finding["rule_id"] for finding in payload["findings"]] == list(rule_ids)


def assert_analysis_diff_report(
    payload: Mapping[str, Any],
    *,
    summary: Mapping[str, Any] | None = None,
    baseline_label: str | None = None,
    current_label: str | None = None,
    new_rule_ids: Sequence[str] | None = None,
    resolved_rule_ids: Sequence[str] | None = None,
    unchanged_rule_ids: Sequence[str] | None = None,
    changed_rule_ids: Sequence[str] | None = None,
    changed_fields_by_rule_id: Mapping[str, Sequence[str]] | None = None,
) -> None:
    assert payload["kind"] == EXPECTED_ANALYSIS_DIFF_SCHEMA["kind"]
    assert payload["schema_version"] == EXPECTED_ANALYSIS_DIFF_SCHEMA["schema_version"]
    if summary is not None:
        assert payload["summary"] == dict(summary)
    if baseline_label is not None:
        assert payload["baseline"]["label"] == baseline_label
    if current_label is not None:
        assert payload["current"]["label"] == current_label
    if new_rule_ids is not None:
        assert [finding["rule_id"] for finding in payload["findings"]["new"]] == list(new_rule_ids)
    if resolved_rule_ids is not None:
        assert [finding["rule_id"] for finding in payload["findings"]["resolved"]] == list(resolved_rule_ids)
    if unchanged_rule_ids is not None:
        assert [finding["rule_id"] for finding in payload["findings"]["unchanged"]] == list(unchanged_rule_ids)
    if changed_rule_ids is not None:
        assert [finding["current"]["rule_id"] for finding in payload["findings"]["changed"]] == list(changed_rule_ids)
    if changed_fields_by_rule_id is not None:
        assert {
            finding["current"]["rule_id"]: finding["change"]["changed_fields"]
            for finding in payload["findings"]["changed"]
        } == {rule_id: list(changed_fields) for rule_id, changed_fields in changed_fields_by_rule_id.items()}


def assert_corpus_results_report(
    payload: Mapping[str, Any],
    *,
    case_count: int | None = None,
    failed_case_ids: Sequence[str] | None = None,
    expect_findings_schema: bool = True,
) -> None:
    assert payload["kind"] == EXPECTED_CORPUS_RESULTS_SCHEMA["kind"]
    assert payload["schema_version"] == EXPECTED_CORPUS_RESULTS_SCHEMA["schema_version"]
    if expect_findings_schema:
        assert_findings_schema(payload)
    if case_count is not None:
        assert payload["summary"]["case_count"] == case_count
    if failed_case_ids is not None:
        assert payload["failed_case_ids"] == list(failed_case_ids)


def assert_artifact_registry_report(
    payload: Mapping[str, Any],
    *,
    generated_by: str | None = None,
    profile: str | None = None,
    enabled_artifact_ids: Sequence[str] | None = None,
    disabled_artifact_ids: Sequence[str] | None = None,
) -> None:
    artifact_by_id = {
        artifact["artifact_id"]: artifact
        for artifact in payload["artifacts"]
    }
    if generated_by is not None:
        assert payload["generated_by"] == generated_by
    if profile is not None:
        assert payload["profile"] == profile
    if enabled_artifact_ids is not None:
        for artifact_id in enabled_artifact_ids:
            assert artifact_by_id[artifact_id]["enabled"] is True
    if disabled_artifact_ids is not None:
        for artifact_id in disabled_artifact_ids:
            assert artifact_by_id[artifact_id]["enabled"] is False
