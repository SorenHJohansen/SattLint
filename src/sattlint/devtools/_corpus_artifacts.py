from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from sattlint.contracts import FindingCollection, FindingLocation, FindingRecord
from sattlint.path_sanitizer import sanitize_path_for_report


@dataclass(frozen=True, slots=True)
class CorpusExecutionArtifacts:
    findings: FindingCollection
    status: dict[str, Any]
    summary: dict[str, Any]


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def collect_artifact_fragment_failures(
    expected_fragments: Mapping[str, object],
    artifact_dir: Path,
) -> tuple[str, ...]:
    failures: list[str] = []
    for artifact_name, expected_fragment in sorted(expected_fragments.items()):
        artifact_path = artifact_dir / artifact_name
        if not artifact_path.exists():
            failures.append(f"{artifact_name}: expected artifact fragment but file was not found")
            continue
        try:
            actual_payload = json.loads(artifact_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            failures.append(f"{artifact_name}: invalid JSON ({exc.msg})")
            continue
        failures.extend(_collect_fragment_mismatches(expected_fragment, actual_payload, path=artifact_name))
    return tuple(failures)


def _collect_fragment_mismatches(
    expected: object,
    actual: object,
    *,
    path: str,
) -> tuple[str, ...]:
    if isinstance(expected, Mapping):
        if not isinstance(actual, Mapping):
            return (f"{path}: expected object, got {type(actual).__name__}",)
        failures: list[str] = []
        actual_mapping = cast(Mapping[str, object], actual)
        for key, expected_value in expected.items():
            key_str = str(key)
            if key_str not in actual_mapping:
                failures.append(f"{path}.{key_str}: missing key")
                continue
            failures.extend(
                _collect_fragment_mismatches(expected_value, actual_mapping[key_str], path=f"{path}.{key_str}")
            )
        return tuple(failures)

    if actual != expected:
        return (f"{path}: expected {expected!r}, got {actual!r}",)
    return ()


def write_case_artifacts(
    artifact_dir: Path,
    artifacts: CorpusExecutionArtifacts,
    *,
    findings_filename: str = "findings.json",
    status_filename: str = "status.json",
    summary_filename: str = "summary.json",
) -> None:
    write_json(artifact_dir / findings_filename, artifacts.findings.to_dict())
    write_json(artifact_dir / status_filename, artifacts.status)
    write_json(artifact_dir / summary_filename, artifacts.summary)


def build_execution_error_artifacts(
    *,
    case_id: str,
    mode: str,
    target_path: Path,
    repo_root: Path,
    error_message: str,
) -> CorpusExecutionArtifacts:
    target_file = sanitize_path_for_report(target_path, repo_root=repo_root)
    finding = FindingRecord(
        id="corpus.execution-error",
        rule_id="corpus.execution-error",
        category="runner",
        severity="high",
        confidence="high",
        message=error_message,
        source="corpus-runner",
        analyzer="corpus-runner",
        artifact="findings",
        location=FindingLocation(path=target_file),
        data={"mode": mode},
    )
    findings = FindingCollection((finding,))
    status = {
        "kind": "sattlint.corpus.case_status",
        "case_id": case_id,
        "mode": mode,
        "execution_status": "error",
        "target_file": target_file,
        "finding_count": 1,
        "findings_schema": findings.schema_metadata,
        "error": error_message,
    }
    summary = {
        "kind": "sattlint.corpus.case_summary",
        "case_id": case_id,
        "mode": mode,
        "target_file": target_file,
        "finding_count": 1,
        "findings_schema": findings.schema_metadata,
        "error": error_message,
    }
    return CorpusExecutionArtifacts(findings=findings, status=status, summary=summary)
