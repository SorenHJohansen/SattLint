from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, cast

from sattlint.devtools._ai_chat_findings import should_update_known_failure_patterns

JsonObject = dict[str, Any]


def _load_json(path: Path) -> JsonObject:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return cast(JsonObject, payload)


def _mapping(value: Any) -> JsonObject | None:
    if isinstance(value, dict):
        return cast(JsonObject, value)
    return None


def _string_value(mapping: JsonObject, key: str, default: str = "") -> str:
    value = mapping.get(key, default)
    return str(value)


def _int_value(mapping: JsonObject, key: str, default: int = 0) -> int:
    value = mapping.get(key, default)
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return default
    return default


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    sequence = cast(list[Any], value)
    return [str(item) for item in sequence]


def _finding_session_text(finding: JsonObject, summary: JsonObject) -> str:
    data = _mapping(finding.get("data"))
    if data is not None:
        session_ids = _string_list(data.get("session_ids"))
        if session_ids:
            return ", ".join(session_ids)
    transcript_corpus = _mapping(summary.get("transcript_corpus"))
    if transcript_corpus is not None:
        count = _int_value(transcript_corpus, "session_count", _int_value(transcript_corpus, "transcript_count", 0))
        return f"{count} session(s) scanned"
    return "Unknown"


def _covered_by_plan(finding_id: str) -> str:
    coverage_map = {
        "high-discovery-before-action": "46 (completed), 75 (active)",
        "wrong-log-seam-risk": "46 (completed), 75 (active)",
        "high-empty-assistant-output-rate": "46 (completed)",
        "session-store-empty": "46 (completed)",
        "session-store-degraded": "46 (completed)",
        "malformed-transcript-line": "46 (completed)",
        "repeated-tool-retries": "75 (active)",
    }
    return coverage_map.get(finding_id, "NOT COVERED")


def _render_report(
    *,
    summary: JsonObject,
    findings_payload: JsonObject,
    output_path: Path,
    prompt_path: str,
    failure_patterns_path: str,
    source_label: str,
) -> None:
    findings_value = findings_payload.get("findings")
    if not isinstance(findings_value, list):
        raise ValueError("findings.json must contain a findings list")
    findings_list = cast(list[Any], findings_value)
    findings = [cast(JsonObject, entry) for entry in findings_list if isinstance(entry, dict)]

    transcript_corpus = _mapping(summary.get("transcript_corpus"))
    session_store = _mapping(summary.get("session_store"))
    health_summary = _mapping(summary.get("health_summary"))

    transcript_count = 0
    if transcript_corpus is not None:
        transcript_count = _int_value(
            transcript_corpus, "session_count", _int_value(transcript_corpus, "transcript_count", 0)
        )
    session_store_status = "unknown"
    if session_store is not None:
        session_store_status = _string_value(session_store, "status", "unknown")
    highest_churn_bucket = "unknown"
    if health_summary is not None:
        highest_churn_bucket = _string_value(health_summary, "highest_churn_bucket", "unknown")

    should_update = should_update_known_failure_patterns(findings)
    lines = [
        "# AI Session Review",
        "",
        f"Prompt reference: `{prompt_path}`",
        f"Failure patterns doc: `{failure_patterns_path}`",
        f"Transcript source: `{source_label}`",
        "",
        "## Summary",
        "",
        f"- Transcript sessions scanned: {transcript_count}",
        f"- Session store status: {session_store_status}",
        f"- Highest churn bucket: {highest_churn_bucket}",
        f"- Finding count: {len(findings)}",
        "",
        "## Findings",
        "",
    ]

    for finding in findings[:5]:
        label = _string_value(finding, "id", "unknown").replace("-", " ").title()
        detail = _string_value(finding, "detail")
        evidence = detail or _string_value(finding, "message", "No evidence recorded.")
        suggestion = _string_value(finding, "suggestion", "Review the finding and tighten the owning seam.")
        finding_id = _string_value(finding, "id")
        lines.extend(
            [
                f"[PATTERN] {label}",
                f"Sessions: {_finding_session_text(finding, summary)}",
                f"Evidence: {evidence}",
                f"Covered by plan: {_covered_by_plan(finding_id)}",
                f"Recommended action: {suggestion}",
                "",
            ]
        )

    lines.extend(
        [
            "## Follow-up",
            "",
            (
                "Should `known-failure-patterns.md` be updated? YES"
                if should_update
                else "Should `known-failure-patterns.md` be updated? NO"
            ),
            "",
            "Copilot prompt execution is still a TODO in GitHub Actions. This workflow currently uses the repo-owned observability CLI and Markdown renderer so the run produces a review artifact instead of a silent no-op.",
            "",
        ]
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render a Markdown review summary from AI chat observability artifacts."
    )
    parser.add_argument("--summary-json", type=Path, required=True)
    parser.add_argument("--findings-json", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--prompt-path", required=True)
    parser.add_argument("--known-failure-patterns-path", required=True)
    parser.add_argument("--source-label", required=True)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    summary = _load_json(args.summary_json)
    findings_payload = _load_json(args.findings_json)
    _render_report(
        summary=summary,
        findings_payload=findings_payload,
        output_path=args.output,
        prompt_path=args.prompt_path,
        failure_patterns_path=args.known_failure_patterns_path,
        source_label=args.source_label,
    )
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
