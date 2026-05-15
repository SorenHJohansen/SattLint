"""Transcript loading and normalization helpers for AI chat observability."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sattlint.path_sanitizer import sanitize_path_for_report

DISCOVERY_TOOL_NAMES = {
    "fetch_webpage",
    "file_search",
    "get_errors",
    "grep_search",
    "list_dir",
    "memory",
    "read_file",
    "semantic_search",
    "session_store_sql",
    "tool_search_tool",
    "view_image",
    "vscode_listCodeUsages",
    "codegraph_search",
    "codegraph_callers",
    "codegraph_callees",
    "codegraph_impact",
    "codegraph_node",
}


class AiChatInputError(ValueError):
    """Raised when the caller provides an invalid transcript input path."""


@dataclass(frozen=True, slots=True)
class TranscriptParseFailure:
    transcript_path: str
    line_number: int
    error: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "transcript_path": self.transcript_path,
            "line_number": self.line_number,
            "error": self.error,
        }


def resolve_transcripts_input(
    *,
    transcripts_dir: Path | None,
    workspace_storage: Path | None,
    repo_root: Path,
) -> dict[str, Any]:
    if (transcripts_dir is None) == (workspace_storage is None):
        raise AiChatInputError("Provide exactly one of --transcripts-dir or --workspace-storage.")

    if transcripts_dir is not None:
        resolved = transcripts_dir.resolve()
        if not resolved.exists() or not resolved.is_dir():
            raise AiChatInputError(f"Transcript directory not found: {transcripts_dir}")
        return {
            "input_kind": "transcripts-dir",
            "input_path": sanitize_path_for_report(resolved, repo_root=repo_root),
            "transcripts_dir": sanitize_path_for_report(resolved, repo_root=repo_root),
            "resolved_transcripts_dir": resolved,
            "wrong_log_seam_risk": resolved.name == "debug-logs",
        }

    assert workspace_storage is not None
    resolved_root = workspace_storage.resolve()
    if not resolved_root.exists() or not resolved_root.is_dir():
        raise AiChatInputError(f"Workspace storage directory not found: {workspace_storage}")
    transcripts_child = resolved_root / "transcripts"
    if not transcripts_child.exists() or not transcripts_child.is_dir():
        raise AiChatInputError(
            "Workspace storage must contain a transcripts child directory under GitHub.copilot-chat. "
            f"Missing: {transcripts_child}"
        )
    return {
        "input_kind": "workspace-storage",
        "input_path": sanitize_path_for_report(resolved_root, repo_root=repo_root),
        "transcripts_dir": sanitize_path_for_report(transcripts_child, repo_root=repo_root),
        "resolved_transcripts_dir": transcripts_child,
        "wrong_log_seam_risk": resolved_root.name == "debug-logs",
    }


def load_transcript_corpus(*, resolved_input: dict[str, Any], repo_root: Path) -> dict[str, Any]:
    transcript_paths = tuple(sorted(resolved_input["resolved_transcripts_dir"].glob("*.jsonl")))
    sessions: list[dict[str, Any]] = []
    parse_failures: list[TranscriptParseFailure] = []

    for transcript_path in transcript_paths:
        session_summary, transcript_failures = _summarize_transcript(transcript_path, repo_root=repo_root)
        sessions.append(session_summary)
        parse_failures.extend(transcript_failures)

    return {
        "input_kind": resolved_input["input_kind"],
        "input_path": resolved_input["input_path"],
        "transcripts_dir": resolved_input["transcripts_dir"],
        "wrong_log_seam_risk": bool(resolved_input["wrong_log_seam_risk"]),
        "transcript_count": len(transcript_paths),
        "sessions": sessions,
        "parse_failures": [failure.to_dict() for failure in parse_failures],
    }


def _summarize_transcript(
    transcript_path: Path, *, repo_root: Path
) -> tuple[dict[str, Any], list[TranscriptParseFailure]]:
    parse_failures: list[TranscriptParseFailure] = []
    user_message_count = 0
    assistant_message_count = 0
    empty_assistant_message_count = 0
    tool_call_count = 0
    failed_tool_call_count = 0
    codegraph_failure_count = 0
    same_tool_retry_count = 0
    event_count = 0
    prompt_preview: str | None = None
    tool_counts: Counter[str] = Counter()
    failed_tool_counts: Counter[str] = Counter()
    active_tool_calls: dict[str, str] = {}
    discovery_before_action_count = 0
    first_action_tool: str | None = None
    last_failed_tool_name: str | None = None

    for line_number, raw_line in enumerate(transcript_path.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw_line.strip():
            continue
        try:
            event = json.loads(raw_line)
        except json.JSONDecodeError as exc:
            parse_failures.append(
                TranscriptParseFailure(
                    transcript_path=sanitize_path_for_report(transcript_path, repo_root=repo_root)
                    or transcript_path.name,
                    line_number=line_number,
                    error=str(exc),
                )
            )
            continue

        event_count += 1
        event_type = _event_type(event)
        data = event.get("data") if isinstance(event.get("data"), dict) else {}

        if event_type == "user.message":
            user_message_count += 1
            content = _extract_text(data.get("content"))
            if prompt_preview is None and content:
                prompt_preview = content
            continue

        if event_type == "assistant.message":
            assistant_message_count += 1
            content = _extract_text(data.get("content"))
            if not content.strip():
                empty_assistant_message_count += 1
            continue

        if event_type == "tool.execution_start":
            tool_call_count += 1
            tool_name = _tool_name(data)
            tool_counts[tool_name] += 1
            tool_call_id = _tool_call_id(data)
            if tool_call_id is not None:
                active_tool_calls[tool_call_id] = tool_name

            if first_action_tool is None:
                if _is_discovery_tool(tool_name):
                    discovery_before_action_count += 1
                else:
                    first_action_tool = tool_name

            if last_failed_tool_name is not None and tool_name == last_failed_tool_name:
                same_tool_retry_count += 1
                last_failed_tool_name = None
            elif last_failed_tool_name is not None and tool_name != last_failed_tool_name:
                last_failed_tool_name = None
            continue

        if event_type == "tool.execution_complete":
            tool_call_id = _tool_call_id(data)
            tool_name = (
                active_tool_calls.pop(tool_call_id, _tool_name(data)) if tool_call_id is not None else _tool_name(data)
            )
            if _tool_success(data) is False:
                failed_tool_call_count += 1
                failed_tool_counts[tool_name] += 1
                if "codegraph" in tool_name.casefold():
                    codegraph_failure_count += 1
                last_failed_tool_name = tool_name

    sanitized_path = sanitize_path_for_report(transcript_path, repo_root=repo_root) or transcript_path.name
    return {
        "session_id": transcript_path.stem,
        "transcript_path": sanitized_path,
        "event_count": event_count,
        "user_message_count": user_message_count,
        "assistant_message_count": assistant_message_count,
        "empty_assistant_message_count": empty_assistant_message_count,
        "tool_call_count": tool_call_count,
        "failed_tool_call_count": failed_tool_call_count,
        "codegraph_failure_count": codegraph_failure_count,
        "same_tool_retry_count": same_tool_retry_count,
        "prompt_preview": prompt_preview,
        "prompt_bucket": _prompt_bucket(prompt_preview),
        "discovery_before_action_count": (discovery_before_action_count if first_action_tool is not None else None),
        "first_action_tool": first_action_tool,
        "tool_counts": dict(sorted(tool_counts.items())),
        "failed_tool_counts": dict(sorted(failed_tool_counts.items())),
        "malformed_line_count": len(parse_failures),
    }, parse_failures


def _event_type(event: dict[str, Any]) -> str:
    raw = event.get("type") or event.get("event") or event.get("eventName")
    return str(raw or "")


def _tool_call_id(data: dict[str, Any]) -> str | None:
    tool_call_id = data.get("toolCallId") or data.get("tool_call_id")
    return str(tool_call_id) if tool_call_id else None


def _tool_name(data: dict[str, Any]) -> str:
    tool_name = data.get("toolName") or data.get("tool_name") or data.get("name")
    return str(tool_name or "unknown")


def _tool_success(data: dict[str, Any]) -> bool | None:
    success = data.get("success")
    if isinstance(success, bool):
        return success
    status = data.get("status")
    if isinstance(status, str):
        normalized = status.casefold()
        if normalized in {"ok", "pass", "passed", "success", "succeeded"}:
            return True
        if normalized in {"error", "fail", "failed"}:
            return False
    return None


def _extract_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return " ".join(part for part in (_extract_text(item) for item in value) if part)
    if isinstance(value, dict):
        for key in ("content", "text", "value", "message", "reasoningText"):
            if key in value:
                text = _extract_text(value[key])
                if text:
                    return text
        return " ".join(part for part in (_extract_text(item) for item in value.values()) if part)
    return str(value)


def _is_discovery_tool(tool_name: str) -> bool:
    normalized = tool_name.casefold()
    return normalized in DISCOVERY_TOOL_NAMES or normalized.startswith("codegraph_")


def _prompt_bucket(prompt_preview: str | None) -> str:
    if not prompt_preview:
        return "other"
    normalized = prompt_preview.casefold()
    if "implement this plan" in normalized or "implement plan" in normalized:
        return "implement-this-plan"
    if "review" in normalized:
        return "review"
    if "audit" in normalized:
        return "audit"
    if "revalidate" in normalized or "validate" in normalized:
        return "validate"
    return "other"


__all__ = [
    "DISCOVERY_TOOL_NAMES",
    "AiChatInputError",
    "load_transcript_corpus",
    "resolve_transcripts_input",
]
