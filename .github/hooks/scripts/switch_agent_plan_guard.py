from __future__ import annotations

import json
import sys

FAIL_OPEN_EXCEPTIONS = (
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
)


def _load_payload() -> dict:
    raw = sys.stdin.read()
    if not raw.strip():
        return {}
    return json.loads(raw)


def _normalize_tool_name(tool_name: str) -> str:
    return tool_name.rsplit(".", 1)[-1].casefold()


def _requested_agent_name(tool_input: object) -> str:
    if not isinstance(tool_input, dict):
        return ""
    requested = tool_input.get("agentName") or tool_input.get("agentname")
    if not isinstance(requested, str):
        return ""
    return requested.casefold()


def _deny_payload(message: str) -> dict[str, object]:
    return {
        "systemMessage": message,
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": "Workspace guard blocked switching to Plan to avoid getting stuck in plan mode.",
            "additionalContext": message,
        },
    }


def _warning_payload(message: str) -> dict[str, object]:
    return {
        "systemMessage": message,
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
            "additionalContext": message,
        },
    }


def main() -> int:
    try:
        payload = _load_payload()
        if payload.get("hookEventName") != "PreToolUse":
            return 0

        tool_name = _normalize_tool_name(str(payload.get("tool_name") or ""))
        if tool_name != "switch_agent":
            return 0

        requested_agent = _requested_agent_name(payload.get("tool_input"))
        if requested_agent != "plan":
            return 0

        message = (
            "Workspace guard blocked `switch_agent` to `Plan`. "
            "Stay in the current agent and continue with a local edit or a focused check instead. "
            "If the user explicitly wants a plan-only response, ask them in chat rather than switching agents."
        )
        sys.stdout.write(json.dumps(_deny_payload(message)))
        return 0
    except FAIL_OPEN_EXCEPTIONS as exc:  # pragma: no cover - hook failures should not block work by default
        message = f"Switch-agent guard warning: hook failed open with {type(exc).__name__}: {exc}"
        sys.stdout.write(json.dumps(_warning_payload(message)))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
