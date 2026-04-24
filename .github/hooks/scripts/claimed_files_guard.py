from __future__ import annotations

import json
import re
import sys
from pathlib import Path

EDIT_TOOL_NAMES = {
    "apply_patch",
    "create_file",
    "edit_notebook_file",
    "multi_replace_string_in_file",
    "replace_string_in_file",
    "vscode_renamesymbol",
    "mcp_pylance_mcp_s_pylanceinvokerefactoring",
}
ACTIVE_SECTION = "## Active Workstreams"
RECENT_SECTION = "## Recent Handoffs"
WORKSTREAM_RE = re.compile(r"^### Workstream\s+(?P<id>.+?)\s*$")
FIELD_RE = re.compile(r"^-\s+(?P<field>[A-Za-z][A-Za-z\-/ ]+):\s*(?P<value>.*)$")
PATCH_PATH_RE = re.compile(r"^\*\*\* (?:Add|Update|Delete) File: (?P<path>.+?)(?: -> .+)?$", re.MULTILINE)
BACKTICK_ITEM_RE = re.compile(r"`([^`]+)`")
SKIP_RELATIVE_PATHS = {
    ".github/coordination/current-work.md",
}
ESCALATE_TO_ASK = {"ready-for-merge"}
ESCALATE_TO_DENY = {"blocked"}


def _load_payload() -> dict:
    raw = sys.stdin.read()
    if not raw.strip():
        return {}
    return json.loads(raw)


def _normalize_tool_name(tool_name: str) -> str:
    return tool_name.rsplit(".", 1)[-1].casefold()


def _normalize_relative(raw_path: str) -> str:
    cleaned = raw_path.strip().strip("`'")
    cleaned = cleaned.replace("\\", "/")
    while cleaned.startswith("./"):
        cleaned = cleaned[2:]
    return cleaned.rstrip("/")


def _resolve_workspace_path(raw_path: str, cwd: Path) -> Path:
    path = Path(_normalize_relative(raw_path))
    if not path.is_absolute():
        path = cwd / path
    return path.resolve()


def _extract_patch_paths(patch_text: str) -> list[str]:
    return [match.group("path") for match in PATCH_PATH_RE.finditer(patch_text)]


def _extract_tool_paths(tool_name: str, tool_input: object, cwd: Path) -> list[Path]:
    normalized_tool_name = _normalize_tool_name(tool_name)
    if normalized_tool_name not in EDIT_TOOL_NAMES:
        return []

    seen: dict[str, Path] = {}

    def add_raw(raw_path: str) -> None:
        relative = _normalize_relative(raw_path)
        if not relative or relative in SKIP_RELATIVE_PATHS:
            return
        seen[relative.casefold()] = _resolve_workspace_path(relative, cwd)

    def walk(value: object) -> None:
        if isinstance(value, dict):
            for key, nested in value.items():
                lowered = key.casefold()
                if lowered in {"filepath", "dirpath", "path", "old_path", "new_path"} and isinstance(nested, str):
                    add_raw(nested)
                    continue
                if lowered in {"filepaths", "files", "paths"} and isinstance(nested, list):
                    for item in nested:
                        if isinstance(item, str):
                            add_raw(item)
                    continue
                if lowered == "input" and isinstance(nested, str) and normalized_tool_name == "apply_patch":
                    for item in _extract_patch_paths(nested):
                        add_raw(item)
                    continue
                walk(nested)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(tool_input)
    return list(seen.values())


def _split_claims(raw_claims: str) -> list[str]:
    backtick_items = BACKTICK_ITEM_RE.findall(raw_claims)
    if backtick_items:
        return backtick_items
    return [part.strip() for part in raw_claims.split(",") if part.strip()]


def _load_active_claims(ledger_path: Path, cwd: Path) -> list[dict[str, object]]:
    if not ledger_path.exists():
        return []

    text = ledger_path.read_text(encoding="utf-8")
    if ACTIVE_SECTION not in text:
        return []

    active_text = text.split(ACTIVE_SECTION, 1)[1]
    if RECENT_SECTION in active_text:
        active_text = active_text.split(RECENT_SECTION, 1)[0]

    claims: list[dict[str, object]] = []
    current: dict[str, object] | None = None
    for raw_line in active_text.splitlines():
        line = raw_line.rstrip()
        workstream_match = WORKSTREAM_RE.match(line)
        if workstream_match:
            if current is not None:
                claims.append(current)
            current = {
                "id": workstream_match.group("id").strip(),
            }
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
        claims.append(current)

    normalized_claims: list[dict[str, object]] = []
    for claim in claims:
        status = str(claim.get("status", "active")).strip().casefold()
        if status == "done":
            continue
        raw_claim_text = str(claim.get("claims", "")).strip()
        if not raw_claim_text:
            continue
        claim_patterns = []
        for item in _split_claims(raw_claim_text):
            normalized_relative = _normalize_relative(item)
            if not normalized_relative:
                continue
            absolute_path = _resolve_workspace_path(normalized_relative, cwd)
            is_directory = item.rstrip().endswith(("/", "\\")) or absolute_path.is_dir()
            claim_patterns.append(
                {
                    "raw": normalized_relative,
                    "path": absolute_path,
                    "is_directory": is_directory,
                }
            )
        if not claim_patterns:
            continue
        normalized_claims.append(
            {
                "id": claim.get("id", "unknown"),
                "owner": claim.get("owner", "unknown"),
                "status": status,
                "patterns": claim_patterns,
            }
        )
    return normalized_claims


def _match_conflicts(targets: list[Path], claims: list[dict[str, object]], cwd: Path) -> list[dict[str, str]]:
    conflicts: list[dict[str, str]] = []
    for target in targets:
        target_relative = target.resolve().relative_to(cwd.resolve()).as_posix()
        for claim in claims:
            patterns = claim.get("patterns")
            if not isinstance(patterns, list):
                continue
            for pattern in patterns:
                if not isinstance(pattern, dict):
                    continue
                claimed_path = pattern.get("path")
                if not isinstance(claimed_path, Path):
                    continue
                is_directory = bool(pattern.get("is_directory"))
                matches = target == claimed_path or (is_directory and claimed_path in target.parents)
                if not matches:
                    continue
                conflicts.append(
                    {
                        "target": target_relative,
                        "workstream": str(claim["id"]),
                        "owner": str(claim["owner"]),
                        "status": str(claim["status"]),
                        "claim": str(pattern["raw"]),
                    }
                )
    return conflicts


def _decision_for(conflicts: list[dict[str, str]]) -> tuple[str, str]:
    statuses = {conflict["status"] for conflict in conflicts}
    if statuses & ESCALATE_TO_DENY:
        return "deny", "Claimed-file guard blocked edit because a conflicting workstream is marked blocked."
    if statuses & ESCALATE_TO_ASK:
        return "ask", "Claimed-file guard requires confirmation because a conflicting workstream is ready for merge."
    return "allow", "Claimed-file guard warning: target overlaps with an active claimed path."


def _build_message(conflicts: list[dict[str, str]]) -> str:
    details = "; ".join(
        f"{item['target']} claimed by {item['workstream']} ({item['owner']}, {item['status']}) via {item['claim']}"
        for item in conflicts
    )
    return (
        "Claimed-file guard detected an overlap with `.github/coordination/current-work.md`. "
        "Update the ledger or coordinate before proceeding. "
        f"Conflicts: {details}"
    )


def main() -> int:
    try:
        payload = _load_payload()
        if payload.get("hookEventName") != "PreToolUse":
            return 0

        cwd = Path(payload.get("cwd") or ".").resolve()
        tool_name = str(payload.get("tool_name") or "")
        tool_input = payload.get("tool_input")
        targets = _extract_tool_paths(tool_name, tool_input, cwd)
        if not targets:
            return 0

        ledger_path = cwd / ".github" / "coordination" / "current-work.md"
        claims = _load_active_claims(ledger_path, cwd)
        if not claims:
            return 0

        conflicts = _match_conflicts(targets, claims, cwd)
        if not conflicts:
            return 0

        decision, reason = _decision_for(conflicts)
        message = _build_message(conflicts)
        response = {
            "systemMessage": message,
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": decision,
                "permissionDecisionReason": reason,
                "additionalContext": message,
            },
        }
        sys.stdout.write(json.dumps(response))
        return 0
    except Exception as exc:  # pragma: no cover - hook failures should not block work by default
        fallback = {
            "systemMessage": f"Claimed-file guard warning: hook failed open with {type(exc).__name__}: {exc}",
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "additionalContext": "Claimed-file guard failed open. Review .github/hooks/scripts/claimed_files_guard.py if this repeats.",
            },
        }
        sys.stdout.write(json.dumps(fallback))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
