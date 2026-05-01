from __future__ import annotations

import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import TypedDict

WORKSTREAM_RE = re.compile(r"^### Workstream\s+(?P<id>.+?)\s*$")
FIELD_RE = re.compile(r"^-\s+(?P<field>[A-Za-z][A-Za-z\-/ ]+):\s*(?P<value>.*)$")
BACKTICK_ITEM_RE = re.compile(r"`([^`]+)`")
TOKEN_RE = re.compile(r"[a-z0-9_./-]{3,}")
LEDGER_TEMPLATE_NAME = "current-work.template.md"
SUMMARY_FILE_NAME = "current_work_summary.json"
PATH_SUFFIXES = {".md", ".py", ".yml", ".yaml", ".json", ".toml", ".txt"}
PATH_KEYS = {"path", "filepath", "file", "currentfile", "activefile", "editorfile", "selectionpath"}
TEXT_KEYS = {"prompt", "message", "query", "task", "goal", "title", "description"}
NON_SIGNAL_KEYS = {"cwd", "hookeventname"}
STATUS_BONUS = {
    "active": 3,
    "ready-for-merge": 2,
    "planned": 1,
    "blocked": 0,
}


class ClaimInfo(TypedDict):
    raw: str
    path: Path
    is_directory: bool


class WorkstreamEntry(TypedDict):
    id: str
    owner: str
    goal: str
    claims: str
    status: str
    notes: str
    index: int
    claim_paths: list[ClaimInfo]


class PayloadSignals(TypedDict):
    paths: list[Path]
    keywords: set[str]
    text: str


class PlanningContextPayload(TypedDict):
    changed_files: list[str]
    selected_surface: str | None
    primary_agent: str | None
    instruction_names: list[str]
    owner_test_targets: list[str]
    first_validation_commands: list[str]


class RankedWorkstream(TypedDict):
    entry: WorkstreamEntry
    score: int
    matched_claims: list[str]
    matched_keywords: list[str]


def _load_payload() -> dict:
    raw = sys.stdin.read()
    if not raw.strip():
        return {}
    return json.loads(raw)


def _ensure_local_ledger(ledger_path: Path) -> Path:
    if ledger_path.exists():
        return ledger_path
    template_path = ledger_path.with_name(LEDGER_TEMPLATE_NAME)
    if not template_path.exists():
        return ledger_path
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    ledger_path.write_text(template_path.read_text(encoding="utf-8"), encoding="utf-8")
    return ledger_path


def _normalize_relative(raw_path: str) -> str:
    cleaned = raw_path.strip().strip("`'\"")
    cleaned = cleaned.replace("\\", "/")
    while cleaned.startswith("./"):
        cleaned = cleaned[2:]
    return cleaned.rstrip("/")


def _resolve_workspace_path(raw_path: str, cwd: Path) -> Path:
    path = Path(_normalize_relative(raw_path))
    if not path.is_absolute():
        path = cwd / path
    return path.resolve()


def _split_claims(raw_claims: str) -> list[str]:
    backtick_items = BACKTICK_ITEM_RE.findall(raw_claims)
    if backtick_items:
        return backtick_items
    return [part.strip() for part in raw_claims.split(",") if part.strip()]


def _load_active_workstreams(ledger_path: Path, cwd: Path) -> list[WorkstreamEntry]:
    ledger_path = _ensure_local_ledger(ledger_path)
    if not ledger_path.exists():
        return []

    text = ledger_path.read_text(encoding="utf-8")

    entries: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        workstream_match = WORKSTREAM_RE.match(line)
        if workstream_match:
            if current is not None:
                entries.append(current)
            current = {"id": workstream_match.group("id").strip()}
            continue
        if current is None:
            continue
        field_match = FIELD_RE.match(line.lstrip())
        if not field_match:
            continue
        field = field_match.group("field").strip().casefold()
        value = field_match.group("value").strip()
        current[field] = value
    if current is not None:
        entries.append(current)

    normalized: list[WorkstreamEntry] = []
    for index, entry in enumerate(entries):
        status = entry.get("status", "active").strip().casefold()
        if status == "done":
            continue
        raw_claims = entry.get("claims", "")
        claim_paths: list[ClaimInfo] = []
        for item in _split_claims(raw_claims):
            normalized_relative = _normalize_relative(item)
            if not normalized_relative:
                continue
            resolved = _resolve_workspace_path(normalized_relative, cwd)
            is_directory = item.rstrip().endswith(("/", "\\")) or resolved.is_dir()
            claim_paths.append({"raw": normalized_relative, "path": resolved, "is_directory": is_directory})
        normalized.append(
            {
                "id": entry.get("id", "unknown"),
                "owner": entry.get("owner", "unknown"),
                "goal": entry.get("goal", "no goal"),
                "claims": raw_claims,
                "status": status,
                "notes": entry.get("notes", ""),
                "index": index,
                "claim_paths": claim_paths,
            }
        )
    return normalized


def _collect_payload_signals(payload: object, cwd: Path) -> PayloadSignals:
    path_signals: dict[str, Path] = {}
    text_fragments: list[str] = []

    def add_path(raw_path: str) -> None:
        normalized = _normalize_relative(raw_path)
        if not normalized:
            return
        try:
            resolved = _resolve_workspace_path(normalized, cwd)
        except Exception:
            return
        path_signals[resolved.as_posix().casefold()] = resolved

    def visit(value: object, parent_key: str = "") -> None:
        lowered_key = parent_key.casefold()
        if isinstance(value, dict):
            for key, nested in value.items():
                visit(nested, str(key))
            return
        if isinstance(value, list):
            for item in value:
                visit(item, parent_key)
            return
        if not isinstance(value, str):
            return

        stripped = value.strip()
        if not stripped:
            return
        if lowered_key not in PATH_KEYS and lowered_key not in NON_SIGNAL_KEYS and len(stripped) <= 240:
            text_fragments.append(stripped)
        if lowered_key in PATH_KEYS:
            add_path(stripped)
            return
        if lowered_key in NON_SIGNAL_KEYS:
            return
        if lowered_key in TEXT_KEYS:
            return
        candidate = _normalize_relative(stripped)
        if "/" in candidate or "\\" in stripped or Path(candidate).suffix.casefold() in PATH_SUFFIXES:
            add_path(candidate)

    visit(payload)

    keywords = {
        token
        for fragment in text_fragments
        for token in TOKEN_RE.findall(fragment.casefold())
        if "/" not in token and "." not in token and len(token) >= 4
    }
    return {
        "paths": list(path_signals.values()),
        "keywords": keywords,
        "text": " ".join(text_fragments),
    }


def _score_workstream(entry: WorkstreamEntry, signals: PayloadSignals) -> RankedWorkstream:
    signal_paths = signals["paths"]
    signal_keywords = signals["keywords"]

    score = STATUS_BONUS.get(entry["status"], 0)
    matched_claims: list[str] = []
    matched_keywords: list[str] = []

    for claim in entry["claim_paths"]:
        claim_path = claim["path"]
        claim_raw = claim["raw"] or claim_path.name
        is_directory = claim["is_directory"]
        for signal_path in signal_paths:
            if signal_path == claim_path:
                score += 80
                matched_claims.append(claim_raw)
                continue
            if is_directory and claim_path in signal_path.parents:
                score += 50
                matched_claims.append(claim_raw)
                continue
            if signal_path.is_relative_to(claim_path) if is_directory else False:
                score += 50
                matched_claims.append(claim_raw)

    for field_value in (entry["id"], entry["goal"], entry["notes"], entry["claims"]):
        field_value = field_value.casefold()
        local_matches = sorted(token for token in signal_keywords if token in field_value)
        if not local_matches:
            continue
        score += min(len(local_matches) * 4, 16)
        matched_keywords.extend(local_matches[:4])

    unique_claims = list(dict.fromkeys(matched_claims))
    unique_keywords = list(dict.fromkeys(matched_keywords))
    return {
        "entry": entry,
        "score": score,
        "matched_claims": unique_claims,
        "matched_keywords": unique_keywords,
    }


def _rank_workstreams(entries: list[WorkstreamEntry], signals: PayloadSignals) -> list[RankedWorkstream]:
    ranked = [_score_workstream(entry, signals) for entry in entries]
    ranked.sort(key=lambda item: (-item["score"], item["entry"]["index"]))
    return ranked


def _summary_path(ledger_path: Path) -> Path:
    return ledger_path.with_name(SUMMARY_FILE_NAME)


def _signal_changed_files(signals: PayloadSignals, cwd: Path) -> list[str]:
    changed_files: list[str] = []
    for path in signals["paths"]:
        if path == cwd or not path.is_relative_to(cwd):
            continue
        relative = path.relative_to(cwd).as_posix()
        if relative not in changed_files:
            changed_files.append(relative)
    return changed_files


def _build_planning_context_payload(signals: PayloadSignals, cwd: Path) -> PlanningContextPayload | None:
    changed_files = _signal_changed_files(signals, cwd)
    if not changed_files:
        return None
    src_path = cwd / "src"
    if src_path.exists():
        src_text = str(src_path)
        if src_text not in sys.path:
            sys.path.insert(0, src_text)
    from sattlint.devtools import ai_work_map

    session_context_map = ai_work_map.load_session_context_map()
    planning_context = ai_work_map.build_planning_context(
        changed_files=changed_files,
        recommended_check_ids=None,
        selected_surface="session-start",
        work_map=session_context_map,
    )
    owner_test_targets: list[str] = []
    for suite in planning_context.get("nearest_owner_suites", []):
        tests = suite.get("tests", []) if isinstance(suite, dict) else []
        for test_path in tests[:2]:
            test_text = str(test_path)
            if test_text and test_text not in owner_test_targets:
                owner_test_targets.append(test_text)
    first_validation_commands = [
        str(command) for command in planning_context.get("first_validation_commands", []) if str(command).strip()
    ]
    return {
        "changed_files": changed_files,
        "selected_surface": "session-start",
        "primary_agent": planning_context.get("primary_agent"),
        "instruction_names": [
            str(item.get("name", ""))
            for item in planning_context.get("instruction_files", [])
            if isinstance(item, dict) and item.get("name")
        ][:3],
        "owner_test_targets": owner_test_targets[:3],
        "first_validation_commands": first_validation_commands[:2],
    }


def _write_summary(
    ledger_path: Path,
    signals: PayloadSignals,
    ranked: list[RankedWorkstream],
    active_count: int,
    cwd: Path,
    planning: PlanningContextPayload | None,
) -> None:
    summary_path = _summary_path(ledger_path)
    top_items = ranked[:3]
    payload = {
        "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "source": ".github/coordination/current-work.md",
        "active_workstream_count": active_count,
        "signal_paths": [
            path.relative_to(cwd).as_posix() for path in signals["paths"] if path != cwd and path.is_relative_to(cwd)
        ][:5],
        "signal_keywords": sorted(signals["keywords"])[:8],
        "planning": planning,
        "top_workstreams": [
            {
                "id": item["entry"]["id"],
                "owner": item["entry"]["owner"],
                "status": item["entry"]["status"],
                "goal": item["entry"]["goal"],
                "matched_claims": item["matched_claims"][:3],
                "matched_keywords": item["matched_keywords"][:4],
                "score": item["score"],
            }
            for item in top_items
        ],
    }
    summary_path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")


def _format_context(ranked: list[RankedWorkstream], planning: PlanningContextPayload | None) -> str | None:
    if not ranked and planning is None:
        return None

    segments: list[str] = []
    if ranked:
        parts: list[str] = []
        for item in ranked[:3]:
            entry = item["entry"]
            reason_parts: list[str] = []
            if item["matched_claims"]:
                reason_parts.append(f"claims={','.join(item['matched_claims'][:2])}")
            if item["matched_keywords"]:
                reason_parts.append(f"keywords={','.join(item['matched_keywords'][:2])}")
            reason = f" | match={' ; '.join(reason_parts)}" if reason_parts else ""
            parts.append(f"{entry['id']}: {entry['goal']} | owner={entry['owner']} | status={entry['status']}{reason}")
        joined = "; ".join(parts)
        segments.append(f"Relevant SattLint workstreams: {joined}.")
    if planning is not None:
        planning_bits: list[str] = []
        if planning["selected_surface"]:
            planning_bits.append(f"surface={planning['selected_surface']}")
        if planning["primary_agent"]:
            planning_bits.append(f"agent={planning['primary_agent']}")
        if planning["instruction_names"]:
            planning_bits.append(f"instructions={','.join(planning['instruction_names'][:2])}")
        if planning["owner_test_targets"]:
            planning_bits.append(f"owner-tests={','.join(planning['owner_test_targets'][:2])}")
        if planning["first_validation_commands"]:
            planning_bits.append(f"first-validation={planning['first_validation_commands'][0]}")
        if planning_bits:
            segments.append(f"Planning context: {' | '.join(planning_bits)}.")
    segments.append("Use the compact session summary first. Check the ledger before editing claimed files.")
    return " ".join(segments)


def main() -> int:
    try:
        payload = _load_payload()
        if payload.get("hookEventName") != "SessionStart":
            return 0
        cwd = Path(payload.get("cwd") or ".").resolve()
        ledger_path = cwd / ".github" / "coordination" / "current-work.md"
        entries = _load_active_workstreams(ledger_path, cwd)
        signals = _collect_payload_signals(payload, cwd)
        ranked = _rank_workstreams(entries, signals)
        planning = _build_planning_context_payload(signals, cwd)
        _write_summary(ledger_path, signals, ranked, len(entries), cwd, planning)
        context = _format_context(ranked, planning)
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
