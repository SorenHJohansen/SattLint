"""Aggregation helpers for AI chat observability artifacts."""

from __future__ import annotations

import sqlite3
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from sattlint.path_sanitizer import sanitize_path_for_report

_TABLE_COUNT_QUERIES = {
    "sessions": "SELECT COUNT(*) FROM sessions",
    "turns": "SELECT COUNT(*) FROM turns",
    "session_files": "SELECT COUNT(*) FROM session_files",
}
_SESSION_METADATA_COUNT_QUERIES = {
    "repo": "SELECT COUNT(*) FROM sessions WHERE TRIM(COALESCE(repo, '')) != ''",
    "cwd": "SELECT COUNT(*) FROM sessions WHERE TRIM(COALESCE(cwd, '')) != ''",
    "branch": "SELECT COUNT(*) FROM sessions WHERE TRIM(COALESCE(branch, '')) != ''",
    "agent": "SELECT COUNT(*) FROM sessions WHERE TRIM(COALESCE(agent, '')) != ''",
}


def probe_session_store(session_db: Path | None, *, repo_root: Path) -> dict[str, Any]:
    if session_db is None:
        return {
            "status": "not_requested",
            "database_path": None,
            "explanation": "No session database path was provided, so transcript JSONL is the only data source.",
        }

    resolved = session_db.resolve()
    sanitized_path = sanitize_path_for_report(resolved, repo_root=repo_root)
    if not resolved.exists() or not resolved.is_file():
        return {
            "status": "degraded",
            "database_path": sanitized_path,
            "error": "session database path is missing",
            "explanation": "The requested session database could not be opened, so turn-level session-store data is unavailable.",
        }

    try:
        connection = sqlite3.connect(resolved)
    except sqlite3.Error as exc:
        return {
            "status": "degraded",
            "database_path": sanitized_path,
            "error": str(exc),
            "explanation": "The session database could not be opened, so transcript JSONL remains the source of truth.",
        }

    try:
        with connection:
            tables = _existing_tables(connection)
            session_count = _table_count(connection, "sessions") if "sessions" in tables else 0
            turn_count = _table_count(connection, "turns") if "turns" in tables else 0
            session_file_count = _table_count(connection, "session_files") if "session_files" in tables else 0
            metadata_counts = _session_metadata_counts(connection) if "sessions" in tables else {}
    finally:
        connection.close()

    if turn_count > 0 and session_file_count > 0 and any(metadata_counts.values()):
        status = "usable"
        explanation = "The session database contains turn-level rows and non-empty workspace metadata."
    elif session_count == 0 and turn_count == 0 and session_file_count == 0:
        status = "empty"
        explanation = "The session database is present but contains no indexed session, turn, or file rows."
    else:
        status = "degraded"
        explanation = (
            "The session database exists, but it lacks turn-level rows, file rows, or populated workspace metadata."
        )

    return {
        "status": status,
        "database_path": sanitized_path,
        "session_count": session_count,
        "turn_count": turn_count,
        "session_file_count": session_file_count,
        "metadata_counts": metadata_counts,
        "explanation": explanation,
    }


def build_summary_report(
    *,
    transcript_report: dict[str, Any],
    session_store: dict[str, Any],
    semantic_grounding: dict[str, Any],
    findings: list[dict[str, Any]],
    output_dir: Path,
    repo_root: Path,
) -> dict[str, Any]:
    sessions = list(transcript_report["sessions"])
    parse_failures = list(transcript_report["parse_failures"])
    assistant_message_count = sum(int(session["assistant_message_count"]) for session in sessions)
    empty_assistant_message_count = sum(int(session["empty_assistant_message_count"]) for session in sessions)
    tool_call_count = sum(int(session["tool_call_count"]) for session in sessions)
    failed_tool_call_count = sum(int(session["failed_tool_call_count"]) for session in sessions)
    same_tool_retry_count = sum(int(session["same_tool_retry_count"]) for session in sessions)
    malformed_line_count = len(parse_failures)

    tool_counter: Counter[str] = Counter()
    bucket_accumulator: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "session_count": 0,
            "assistant_message_count": 0,
            "empty_assistant_message_count": 0,
            "failed_tool_call_count": 0,
            "discovery_counts": [],
        }
    )
    for session in sessions:
        for tool_name, count in dict(session["tool_counts"]).items():
            tool_counter[str(tool_name)] += int(count)
        bucket = str(session["prompt_bucket"])
        bucket_stats = bucket_accumulator[bucket]
        bucket_stats["session_count"] += 1
        bucket_stats["assistant_message_count"] += int(session["assistant_message_count"])
        bucket_stats["empty_assistant_message_count"] += int(session["empty_assistant_message_count"])
        bucket_stats["failed_tool_call_count"] += int(session["failed_tool_call_count"])
        discovery_count = session.get("discovery_before_action_count")
        if isinstance(discovery_count, int):
            bucket_stats["discovery_counts"].append(discovery_count)

    task_buckets = sorted(
        (
            {
                "bucket": bucket,
                "session_count": stats["session_count"],
                "assistant_message_count": stats["assistant_message_count"],
                "empty_assistant_message_rate": _ratio(
                    stats["empty_assistant_message_count"],
                    stats["assistant_message_count"],
                ),
                "failed_tool_call_count": stats["failed_tool_call_count"],
                "average_discovery_before_action": _average(stats["discovery_counts"]),
                "max_discovery_before_action": max(stats["discovery_counts"], default=0),
            }
            for bucket, stats in bucket_accumulator.items()
        ),
        key=lambda item: (
            float(item["average_discovery_before_action"]),
            float(item["empty_assistant_message_rate"]),
            int(item["failed_tool_call_count"]),
            item["bucket"],
        ),
        reverse=True,
    )
    top_tools = [
        {"tool_name": tool_name, "count": count}
        for tool_name, count in sorted(tool_counter.items(), key=lambda item: (-item[1], item[0]))[:10]
    ]

    transcript_status = _transcript_corpus_status(
        transcript_count=int(transcript_report["transcript_count"]),
        malformed_line_count=malformed_line_count,
    )
    overall_status = "ok"
    if transcript_status != "ok" or session_store["status"] not in {"usable", "not_requested"} or findings:
        overall_status = "degraded"
    if transcript_status == "empty" and not findings and session_store["status"] == "not_requested":
        overall_status = "empty"

    return {
        "kind": "sattlint.ai_chat.summary",
        "schema_version": 1,
        "generated_by": "sattlint.devtools.ai_chat_observability",
        "output_dir": sanitize_path_for_report(output_dir.resolve(), repo_root=repo_root),
        "entry_report": "status.json",
        "canonical_command": "python -m sattlint.devtools.ai_chat_observability",
        "overall_status": overall_status,
        "transcript_corpus": {
            "status": transcript_status,
            "input_kind": transcript_report["input_kind"],
            "input_path": transcript_report["input_path"],
            "transcripts_dir": transcript_report["transcripts_dir"],
            "transcript_count": transcript_report["transcript_count"],
            "session_count": len(sessions),
            "malformed_line_count": malformed_line_count,
            "explanation": _transcript_explanation(
                transcript_count=int(transcript_report["transcript_count"]),
                malformed_line_count=malformed_line_count,
            ),
        },
        "session_store": session_store,
        "semantic_grounding": {
            "status": semantic_grounding["status"],
            "backend": semantic_grounding.get("backend"),
            "queryable_session_count": semantic_grounding["queryable_session_count"],
            "searchable_session_count": semantic_grounding["searchable_session_count"],
            "grounded_session_count": semantic_grounding["grounded_session_count"],
            "grounding_match_rate": semantic_grounding["grounding_match_rate"],
            "average_candidate_match_ratio": semantic_grounding["average_candidate_match_ratio"],
            "ungrounded_session_ids": list(semantic_grounding.get("ungrounded_session_ids", [])),
            "explanation": semantic_grounding["explanation"],
        },
        "top_metrics": {
            "assistant_message_count": assistant_message_count,
            "empty_assistant_message_count": empty_assistant_message_count,
            "empty_assistant_message_rate": _ratio(empty_assistant_message_count, assistant_message_count),
            "tool_call_count": tool_call_count,
            "failed_tool_call_count": failed_tool_call_count,
            "same_tool_retry_count": same_tool_retry_count,
        },
        "task_buckets": task_buckets,
        "top_tools": top_tools,
        "health_summary": {
            "transcript_corpus_health": transcript_status,
            "session_store_health": session_store["status"],
            "semantic_grounding_health": semantic_grounding["status"],
            "highest_churn_bucket": task_buckets[0]["bucket"] if task_buckets else None,
            "action_required_finding_ids": [finding["id"] for finding in findings[:5]],
        },
    }


def build_status_report(
    *,
    transcript_report: dict[str, Any],
    session_store: dict[str, Any],
    finding_count: int,
    summary: dict[str, Any],
    output_dir: Path,
    repo_root: Path,
) -> dict[str, Any]:
    sanitized_output_dir = sanitize_path_for_report(output_dir.resolve(), repo_root=repo_root)
    return {
        "kind": "sattlint.ai_chat.status",
        "schema_version": 1,
        "generated_by": "sattlint.devtools.ai_chat_observability",
        "overall_status": summary["overall_status"],
        "output_dir": sanitized_output_dir,
        "reports": {
            "status": f"{sanitized_output_dir}/status.json",
            "summary": f"{sanitized_output_dir}/summary.json",
            "sessions": f"{sanitized_output_dir}/sessions.json",
            "findings": f"{sanitized_output_dir}/findings.json",
        },
        "transcript_source": {
            "input_kind": transcript_report["input_kind"],
            "input_path": transcript_report["input_path"],
            "transcripts_dir": transcript_report["transcripts_dir"],
            "transcript_count": transcript_report["transcript_count"],
        },
        "session_store_status": session_store["status"],
        "semantic_grounding_status": summary["semantic_grounding"]["status"],
        "finding_count": finding_count,
    }


def build_sessions_report(*, transcript_report: dict[str, Any], semantic_grounding: dict[str, Any]) -> dict[str, Any]:
    grounding_by_session_id = {
        str(session.get("session_id", "")): session for session in list(semantic_grounding.get("sessions", []))
    }
    sessions: list[dict[str, Any]] = []
    for session in list(transcript_report["sessions"]):
        session_entry = dict(session)
        grounding_entry = grounding_by_session_id.get(str(session_entry.get("session_id", "")))
        if grounding_entry is not None:
            session_entry["semantic_grounding"] = grounding_entry
        sessions.append(session_entry)
    return {
        "kind": "sattlint.ai_chat.sessions",
        "schema_version": 1,
        "session_count": len(sessions),
        "malformed_line_count": len(transcript_report["parse_failures"]),
        "sessions": sessions,
    }


def _existing_tables(connection: sqlite3.Connection) -> set[str]:
    rows = connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    return {str(row[0]) for row in rows}


def _table_count(connection: sqlite3.Connection, table_name: str) -> int:
    query = _TABLE_COUNT_QUERIES.get(table_name)
    if query is None:
        raise ValueError(f"Unsupported session-store table: {table_name}")
    row = connection.execute(query).fetchone()
    return int(row[0]) if row is not None else 0


def _session_metadata_counts(connection: sqlite3.Connection) -> dict[str, int]:
    session_columns = {str(row[1]) for row in connection.execute("PRAGMA table_info(sessions)").fetchall()}
    counts: dict[str, int] = {}
    for column, query in _SESSION_METADATA_COUNT_QUERIES.items():
        if column not in session_columns:
            counts[column] = 0
            continue
        row = connection.execute(query).fetchone()
        counts[column] = int(row[0]) if row is not None else 0
    return counts


def _average(values: list[int]) -> float:
    return float(sum(values) / len(values)) if values else 0.0


def _ratio(numerator: int, denominator: int) -> float:
    return float(numerator / denominator) if denominator else 0.0


def _transcript_corpus_status(*, transcript_count: int, malformed_line_count: int) -> str:
    if transcript_count == 0:
        return "empty"
    if malformed_line_count > 0:
        return "degraded"
    return "ok"


def _transcript_explanation(*, transcript_count: int, malformed_line_count: int) -> str:
    if transcript_count == 0:
        return "No transcript JSONL files were found under the selected transcripts directory."
    if malformed_line_count > 0:
        return "Transcript JSONL loaded, but malformed lines were skipped and recorded in findings."
    return "Transcript JSONL loaded successfully with no parse failures."


__all__ = [
    "build_sessions_report",
    "build_status_report",
    "build_summary_report",
    "probe_session_store",
]
