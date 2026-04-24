from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ACTIVE_SECTION = "## Active Workstreams"
RECENT_SECTION = "## Recent Handoffs"
WORKSTREAM_RE = re.compile(r"^### Workstream\s+(?P<id>.+?)\s*$")
FIELD_RE = re.compile(r"^-\s+(?P<field>[A-Za-z][A-Za-z\-/ ]+):\s*(?P<value>.*)$")


def _load_payload() -> dict:
    raw = sys.stdin.read()
    if not raw.strip():
        return {}
    return json.loads(raw)


def _load_active_workstreams(ledger_path: Path) -> list[dict[str, str]]:
    if not ledger_path.exists():
        return []

    text = ledger_path.read_text(encoding="utf-8")
    if ACTIVE_SECTION not in text:
        return []

    active_text = text.split(ACTIVE_SECTION, 1)[1]
    if RECENT_SECTION in active_text:
        active_text = active_text.split(RECENT_SECTION, 1)[0]

    entries: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for raw_line in active_text.splitlines():
        line = raw_line.rstrip()
        workstream_match = WORKSTREAM_RE.match(line)
        if workstream_match:
            if current is not None:
                entries.append(current)
            current = {"id": workstream_match.group("id").strip()}
            continue
        if current is None:
            continue
        field_match = FIELD_RE.match(line)
        if not field_match:
            continue
        field = field_match.group("field").strip().casefold()
        value = field_match.group("value").strip()
        current[field] = value
    if current is not None:
        entries.append(current)

    normalized = []
    for entry in entries:
        if entry.get("status", "active").strip().casefold() == "done":
            continue
        normalized.append(entry)
    return normalized


def _format_context(entries: list[dict[str, str]]) -> str | None:
    if not entries:
        return None
    parts = []
    for entry in entries[:3]:
        parts.append(
            f"{entry.get('id', 'unknown')}: {entry.get('goal', 'no goal')} | "
            f"owner={entry.get('owner', 'unknown')} | status={entry.get('status', 'active')}"
        )
    joined = "; ".join(parts)
    return (
        "Active SattLint workstreams from .github/coordination/current-work.md: "
        f"{joined}. Check the ledger before editing claimed files."
    )


def main() -> int:
    try:
        payload = _load_payload()
        if payload.get("hookEventName") != "SessionStart":
            return 0
        cwd = Path(payload.get("cwd") or ".").resolve()
        ledger_path = cwd / ".github" / "coordination" / "current-work.md"
        entries = _load_active_workstreams(ledger_path)
        context = _format_context(entries)
        if not context:
            return 0
        sys.stdout.write(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "SessionStart",
                        "additionalContext": context,
                    }
                }
            )
        )
        return 0
    except Exception:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
