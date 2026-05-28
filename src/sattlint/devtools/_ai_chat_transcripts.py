"""Transcript loading and normalization helpers for AI chat observability."""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from sattlint.path_sanitizer import sanitize_path_for_report

type JsonDict = dict[str, object]

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
}
_PATCH_FILE_RE = re.compile(r"^\*\*\* (?:Add|Update|Delete) File: (.+)$", re.MULTILINE)


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

    if workspace_storage is None:
        raise AiChatInputError("Workspace storage directory not found.")
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
    same_tool_retry_count = 0
    event_count = 0
    prompt_preview: str | None = None
    tool_counts: Counter[str] = Counter()
    failed_tool_counts: Counter[str] = Counter()
    active_tool_calls: dict[str, str] = {}
    discovery_before_action_count = 0
    first_action_tool: str | None = None
    last_failed_tool_name: str | None = None
    file_reference_paths: set[str] = set()
    sanitized_path = sanitize_path_for_report(transcript_path, repo_root=repo_root) or transcript_path.name

    try:
        transcript_lines = transcript_path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        parse_failures.append(
            TranscriptParseFailure(
                transcript_path=sanitized_path,
                line_number=0,
                error=str(exc),
            )
        )
        return {
            "session_id": transcript_path.stem,
            "transcript_path": sanitized_path,
            "event_count": 0,
            "user_message_count": 0,
            "assistant_message_count": 0,
            "empty_assistant_message_count": 0,
            "tool_call_count": 0,
            "failed_tool_call_count": 0,
            "same_tool_retry_count": 0,
            "prompt_preview": None,
            "prompt_bucket": _prompt_bucket(None),
            "discovery_before_action_count": None,
            "first_action_tool": None,
            "tool_counts": {},
            "failed_tool_counts": {},
            "file_reference_paths": [],
            "malformed_line_count": len(parse_failures),
        }, parse_failures

    for line_number, raw_line in enumerate(transcript_lines, start=1):
        if not raw_line.strip():
            continue
        try:
            raw_event = json.loads(raw_line)
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

        if not isinstance(raw_event, dict):
            parse_failures.append(
                TranscriptParseFailure(
                    transcript_path=sanitize_path_for_report(transcript_path, repo_root=repo_root)
                    or transcript_path.name,
                    line_number=line_number,
                    error="Transcript line is not a JSON object.",
                )
            )
            continue

        event = cast(JsonDict, raw_event)

        event_count += 1
        event_type = _event_type(event)
        data = _json_object(event.get("data")) or {}

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
            for file_path in _tool_file_paths(data, repo_root=repo_root):
                file_reference_paths.add(file_path)
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
                last_failed_tool_name = tool_name
    return {
        "session_id": transcript_path.stem,
        "transcript_path": sanitized_path,
        "event_count": event_count,
        "user_message_count": user_message_count,
        "assistant_message_count": assistant_message_count,
        "empty_assistant_message_count": empty_assistant_message_count,
        "tool_call_count": tool_call_count,
        "failed_tool_call_count": failed_tool_call_count,
        "same_tool_retry_count": same_tool_retry_count,
        "prompt_preview": prompt_preview,
        "prompt_bucket": _prompt_bucket(prompt_preview),
        "discovery_before_action_count": (discovery_before_action_count if first_action_tool is not None else None),
        "first_action_tool": first_action_tool,
        "tool_counts": dict(sorted(tool_counts.items())),
        "failed_tool_counts": dict(sorted(failed_tool_counts.items())),
        "file_reference_paths": sorted(file_reference_paths, key=str.casefold),
        "malformed_line_count": len(parse_failures),
    }, parse_failures


def _json_object(value: object) -> JsonDict | None:
    return cast(JsonDict, value) if isinstance(value, dict) else None


def _event_type(event: JsonDict) -> str:
    raw = event.get("type") or event.get("event") or event.get("eventName")
    return str(raw or "")


def _tool_call_id(data: JsonDict) -> str | None:
    tool_call_id = data.get("toolCallId") or data.get("tool_call_id")
    return str(tool_call_id) if tool_call_id else None


def _tool_name(data: JsonDict) -> str:
    tool_name = data.get("toolName") or data.get("tool_name") or data.get("name")
    return str(tool_name or "unknown")


def _tool_success(data: JsonDict) -> bool | None:
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


def _tool_file_paths(data: JsonDict, *, repo_root: Path) -> list[str]:
    arguments = _json_object(data.get("arguments"))
    if arguments is None:
        return []
    discovered: list[str] = []
    for key in ("filePath", "file_path", "old_path", "new_path"):
        path_text = _normalize_tool_path(arguments.get(key), repo_root=repo_root)
        if path_text and path_text not in discovered:
            discovered.append(path_text)
    for key in ("filePaths", "files"):
        value = arguments.get(key)
        if not isinstance(value, list):
            continue
        for item in cast(list[object], value):
            path_text = _normalize_tool_path(item, repo_root=repo_root)
            if path_text and path_text not in discovered:
                discovered.append(path_text)
    patch_input = arguments.get("input")
    if isinstance(patch_input, str):
        for raw_match in _PATCH_FILE_RE.findall(patch_input):
            path_text = _normalize_tool_path(raw_match, repo_root=repo_root)
            if path_text and path_text not in discovered:
                discovered.append(path_text)
    return discovered


def _normalize_tool_path(value: object, *, repo_root: Path) -> str:
    if not isinstance(value, str):
        return ""
    path_text = value.strip().replace("\\", "/")
    if not path_text:
        return ""
    candidate = Path(path_text)
    if candidate.is_absolute():
        sanitized = sanitize_path_for_report(candidate.resolve(), repo_root=repo_root)
        return "" if sanitized is None else sanitized
    return path_text.lstrip("./")


def _extract_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        items = cast(list[object], value)
        parts: list[str] = []
        for item in items:
            part = _extract_text(item)
            if part:
                parts.append(part)
        return " ".join(parts)
    if isinstance(value, dict):
        payload = cast(JsonDict, value)
        for key in ("content", "text", "value", "message", "reasoningText"):
            if key in payload:
                text = _extract_text(payload[key])
                if text:
                    return text
        parts: list[str] = []
        for item in payload.values():
            part = _extract_text(item)
            if part:
                parts.append(part)
        return " ".join(parts)
    return str(value)


def _is_discovery_tool(tool_name: str) -> bool:
    normalized = tool_name.casefold()
    return normalized in DISCOVERY_TOOL_NAMES


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
