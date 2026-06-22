"""Finding classification for AI chat observability."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from sattlint.contracts import FindingCollection, FindingLocation, FindingRecord

DISCOVERY_ALERT_THRESHOLD = 5
EMPTY_ASSISTANT_OUTPUT_THRESHOLD = 0.2


def _string_value(mapping: dict[str, Any], key: str, default: str = "") -> str:
    value = mapping.get(key, default)
    return str(value)


def _session_id_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    sequence = cast(list[Any], value)
    return [str(item) for item in sequence]


def build_findings(
    *,
    transcript_report: dict[str, Any],
    session_store: dict[str, Any],
    summary: dict[str, Any],
    repo_root: Path,
) -> FindingCollection:
    del repo_root
    findings: list[FindingRecord] = []
    sessions = list(transcript_report["sessions"])
    parse_failures = list(transcript_report["parse_failures"])
    top_metrics = dict(summary["top_metrics"])

    if transcript_report.get("wrong_log_seam_risk"):
        findings.append(
            _finding(
                finding_id="wrong-log-seam-risk",
                severity="medium",
                message="The selected log seam points at debug logs instead of transcript JSONL.",
                detail="Use the GitHub.copilot-chat/transcripts directory or the GitHub.copilot-chat workspace-storage root.",
                suggestion="Re-run the observability command against the transcripts source of truth.",
            )
        )

    if parse_failures:
        findings.append(
            _finding(
                finding_id="malformed-transcript-line",
                severity="medium",
                message=f"Skipped {len(parse_failures)} malformed transcript line(s) while building the observability report.",
                detail=str(parse_failures[0]),
                suggestion="Inspect the malformed transcript lines and keep the reader tolerant to partial corruption.",
                location=FindingLocation(
                    path=parse_failures[0]["transcript_path"], line=parse_failures[0]["line_number"]
                ),
                data={"parse_failures": parse_failures[:5]},
            )
        )

    if session_store["status"] in {"degraded", "empty"}:
        finding_id = "session-store-empty"
        if session_store.get("error"):
            finding_id = "session-store-degraded"
        findings.append(
            _finding(
                finding_id=finding_id,
                severity="medium",
                message="The local session index is not reliable for workspace chat review.",
                detail=session_store["explanation"],
                suggestion="Treat transcript JSONL as the source of truth until turns, session_files, and workspace metadata populate in the session store.",
                data=session_store,
            )
        )

    empty_output_rate = float(top_metrics["empty_assistant_message_rate"])
    if top_metrics["assistant_message_count"] and empty_output_rate >= EMPTY_ASSISTANT_OUTPUT_THRESHOLD:
        findings.append(
            _finding(
                finding_id="high-empty-assistant-output-rate",
                severity="medium",
                message="Assistant messages contain a high rate of empty output.",
                detail=(
                    f"{top_metrics['empty_assistant_message_count']} of {top_metrics['assistant_message_count']} "
                    "assistant.message events had empty content."
                ),
                suggestion="Review empty assistant.message events and tighten the chat loop so progress updates contain usable information.",
                data={
                    "empty_assistant_message_count": top_metrics["empty_assistant_message_count"],
                    "assistant_message_count": top_metrics["assistant_message_count"],
                    "empty_assistant_message_rate": empty_output_rate,
                },
            )
        )

    risky_bucket = next(
        (
            bucket
            for bucket in summary["task_buckets"]
            if float(bucket["average_discovery_before_action"]) >= DISCOVERY_ALERT_THRESHOLD
        ),
        None,
    )
    if risky_bucket is not None:
        findings.append(
            _finding(
                finding_id="high-discovery-before-action",
                severity="medium",
                message="One task bucket shows high discovery churn before the first non-discovery action.",
                detail=(
                    f"Bucket {risky_bucket['bucket']} averaged {risky_bucket['average_discovery_before_action']:.1f} "
                    f"discovery steps before first action, with a max of {risky_bucket['max_discovery_before_action']}."
                ),
                suggestion="Route implement and review prompts to the owning seam sooner and validate immediately after the first edit.",
                data=risky_bucket,
            )
        )

    if int(top_metrics["same_tool_retry_count"]) > 0:
        retried_sessions = [session["session_id"] for session in sessions if int(session["same_tool_retry_count"]) > 0]
        findings.append(
            _finding(
                finding_id="repeated-tool-retries",
                severity="low",
                message="The same failing tool was retried in consecutive attempts.",
                detail=f"Repeated retries were observed in {len(retried_sessions)} session(s).",
                suggestion="After the first tool failure, switch to the controlling seam or inspect the error before repeating the same tool call.",
                data={
                    "same_tool_retry_count": top_metrics["same_tool_retry_count"],
                    "session_ids": retried_sessions,
                },
            )
        )

    semantic_grounding = dict(summary.get("semantic_grounding", {}))
    searchable_session_count = int(semantic_grounding.get("searchable_session_count", 0))
    grounding_match_rate = float(semantic_grounding.get("grounding_match_rate", 0.0))
    if searchable_session_count > 0 and grounding_match_rate < 0.5:
        findings.append(
            _finding(
                finding_id="low-semantic-grounding",
                severity="medium",
                message="Prompt search hits overlap weakly with the files referenced during the session.",
                detail=(
                    f"Only {semantic_grounding.get('grounded_session_count', 0)} of {searchable_session_count} "
                    "searchable sessions had any overlap between Semble hits and referenced files."
                ),
                suggestion="Route to the owning seam sooner or tighten prompt wording so discovery targets the files that actually get read or edited.",
                data=semantic_grounding,
            )
        )

    return FindingCollection(tuple(findings))


def _finding(
    *,
    finding_id: str,
    severity: str,
    message: str,
    detail: str,
    suggestion: str,
    location: FindingLocation | None = None,
    data: dict[str, Any] | None = None,
) -> FindingRecord:
    return FindingRecord(
        id=finding_id,
        rule_id=finding_id,
        category="observability",
        severity=severity,
        confidence="high",
        message=message,
        source="custom",
        analyzer="ai-chat-observability",
        artifact="findings",
        location=location or FindingLocation(),
        detail=detail,
        suggestion=suggestion,
        data=data or {},
    )


__all__ = [
    "build_findings",
]
