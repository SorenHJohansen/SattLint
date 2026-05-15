"""Compare two published repo-audit findings directories."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from sattlint.devtools.artifact_readiness import ReadinessError, assert_artifact_dir_ready
from sattlint.devtools.baselines import build_analysis_diff_report, load_finding_collection

COMPARE_SCHEMA_KIND = "sattlint.audit_findings_comparison"
COMPARE_SCHEMA_VERSION = 1


def _compact_finding(finding: dict[str, Any]) -> dict[str, Any]:
    location = finding.get("location") or {}
    return {
        "id": finding.get("id") or finding.get("rule_id"),
        "path": location.get("path"),
        "line": location.get("line"),
        "symbol": location.get("symbol"),
        "fingerprint": finding.get("fingerprint"),
    }


def _compact_changed_finding(finding: dict[str, Any]) -> dict[str, Any]:
    current = finding.get("current") or {}
    change = finding.get("change") or {}
    compact = _compact_finding(current)
    compact["changed_fields"] = change.get("changed_fields")
    compact["baseline_fingerprint"] = change.get("baseline_fingerprint")
    compact["current_fingerprint"] = change.get("current_fingerprint")
    return compact


def build_audit_findings_comparison(before_dir: Path, after_dir: Path) -> dict[str, Any]:
    before_report = assert_artifact_dir_ready(before_dir)
    after_report = assert_artifact_dir_ready(after_dir)
    before_findings = before_dir.resolve() / "findings.json"
    after_findings = after_dir.resolve() / "findings.json"
    diff_report = build_analysis_diff_report(
        baseline=load_finding_collection(before_findings),
        current=load_finding_collection(after_findings),
        baseline_label=before_dir.resolve().as_posix(),
        current_label=after_dir.resolve().as_posix(),
    )
    findings = diff_report["findings"]
    return {
        "kind": COMPARE_SCHEMA_KIND,
        "schema_version": COMPARE_SCHEMA_VERSION,
        "before_artifact_dir": before_dir.resolve().as_posix(),
        "after_artifact_dir": after_dir.resolve().as_posix(),
        "before_findings": before_findings.as_posix(),
        "after_findings": after_findings.as_posix(),
        "summary": diff_report["summary"],
        "findings": {
            "new": [_compact_finding(finding) for finding in findings["new"]],
            "resolved": [_compact_finding(finding) for finding in findings["resolved"]],
            "unchanged": [_compact_finding(finding) for finding in findings["unchanged"]],
            "changed": [_compact_changed_finding(finding) for finding in findings["changed"]],
        },
        "readiness": {
            "before": {"state": before_report["state"], "message": before_report["message"]},
            "after": {"state": after_report["state"], "message": after_report["message"]},
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compare two published repo-audit findings directories.")
    parser.add_argument("--before", required=True, help="Published audit directory to compare from")
    parser.add_argument("--after", required=True, help="Published audit directory to compare to")
    args = parser.parse_args(argv)
    try:
        report = build_audit_findings_comparison(Path(args.before), Path(args.after))
    except (FileNotFoundError, ReadinessError, OSError, ValueError, json.JSONDecodeError) as error:
        print(str(error), file=sys.stderr)
        return 1
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
