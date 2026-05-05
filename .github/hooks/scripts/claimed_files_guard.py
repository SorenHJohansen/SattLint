from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SRC_PATH = REPO_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from sattlint.devtools import coordination_lock_state  # noqa: E402

EDIT_TOOL_NAMES = {
    "apply_patch",
    "create_file",
    "edit_notebook_file",
    "multi_replace_string_in_file",
    "replace_string_in_file",
    "vscode_renamesymbol",
    "mcp_pylance_mcp_s_pylanceinvokerefactoring",
}
PATCH_PATH_RE = re.compile(r"^\*\*\* (?:Add|Update|Delete) File: (?P<path>.+?)(?: -> .+)?$", re.MULTILINE)
SKIP_RELATIVE_PATHS = {
    ".github/coordination/current-work.md",
    f".github/coordination/{coordination_lock_state.LOCK_STATE_FILE_NAME}",
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
    return coordination_lock_state.normalize_relative_path(raw_path)


def _resolve_workspace_path(raw_path: str, cwd: Path) -> Path:
    return coordination_lock_state.resolve_workspace_path(raw_path, cwd)


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


def _load_active_claims(repo_root: Path, cwd: Path) -> list[dict[str, object]]:
    entries = coordination_lock_state.load_lock_state(repo_root)
    normalized_claims: list[dict[str, object]] = []
    for entry in entries:
        claim_patterns = coordination_lock_state.resolve_claim_patterns(entry["claimed_paths"], cwd)
        if not claim_patterns:
            continue
        normalized_claims.append(
            {
                "id": entry["workstream_id"],
                "owner": entry["owner"],
                "status": entry["status"],
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
        "Claimed-file guard detected an overlap with `.git/sattlint-ai-coordination/current_work_lock.json`. "
        "Update the JSON lock state or coordinate before proceeding. "
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

        claims = _load_active_claims(cwd, cwd)
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
                "additionalContext": (
                    "Claimed-file guard failed open. Review "
                    ".github/hooks/scripts/claimed_files_guard.py if this repeats."
                ),
            },
        }
        sys.stdout.write(json.dumps(fallback))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
