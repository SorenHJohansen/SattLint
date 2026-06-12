from __future__ import annotations

import importlib
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import NotRequired, TypedDict

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

REPO_ROOT = Path(__file__).resolve().parents[3]
SRC_PATH = REPO_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from hook_path_compat import normalize_payload_path_text, resolve_payload_cwd  # noqa: E402

from sattlint.devtools import coordination_lock_state  # noqa: E402

FAIL_OPEN_EXCEPTIONS = (
    ImportError,
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
)

TOKEN_RE = re.compile(r"[a-z0-9_./-]{3,}")
SUMMARY_FILE_NAME = coordination_lock_state.SUMMARY_FILE_NAME
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
PRIMARY_AGENT_BY_INSTRUCTION = {
    "CLI App Instructions": "CLI App Menu",
}


class ClaimInfo(TypedDict):
    raw: NotRequired[str]
    path: Path
    is_directory: bool


class WorkstreamEntry(TypedDict):
    id: str
    owner: str
    status: str
    claims: str
    first_validation: str
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
    semantic_suggestion_paths: NotRequired[list[str]]


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


def _load_active_workstreams(repo_root: Path, cwd: Path) -> list[WorkstreamEntry]:
    entries = coordination_lock_state.load_lock_state(repo_root)
    normalized: list[WorkstreamEntry] = []
    for index, entry in enumerate(entries):
        resolved_claim_paths = coordination_lock_state.resolve_claim_patterns(entry["claimed_paths"], cwd)
        claim_paths: list[ClaimInfo] = []
        for claim_index, claim in enumerate(resolved_claim_paths):
            claim_paths.append(
                {
                    "raw": claim.get("raw") or entry["claimed_paths"][claim_index],
                    "path": claim["path"],
                    "is_directory": bool(claim.get("is_directory")),
                }
            )
        normalized.append(
            {
                "id": entry["workstream_id"],
                "owner": entry["owner"],
                "status": entry["status"],
                "claims": ", ".join(entry["claimed_paths"]),
                "first_validation": entry["first_validation"],
                "notes": "",
                "index": index,
                "claim_paths": claim_paths,
            }
        )
    return normalized


def _collect_payload_signals(payload: object, cwd: Path) -> PayloadSignals:
    path_signals: dict[str, Path] = {}
    text_fragments: list[str] = []

    def add_path(raw_path: str) -> None:
        normalized = coordination_lock_state.normalize_relative_path(normalize_payload_path_text(raw_path))
        if not normalized:
            return
        try:
            resolved = coordination_lock_state.resolve_workspace_path(normalized, cwd)
        except (OSError, RuntimeError):
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
        candidate = coordination_lock_state.normalize_relative_path(stripped)
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
        claim_raw = claim.get("raw") or claim_path.name
        is_directory = bool(claim.get("is_directory"))
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

    for field_value in (
        entry["id"],
        entry["owner"],
        entry.get("first_validation", ""),
        entry.get("goal", ""),
        entry.get("notes", ""),
        entry["claims"],
    ):
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


def _summary_path(repo_root: Path) -> Path:
    return coordination_lock_state.summary_path(repo_root)


def _signal_changed_files(signals: PayloadSignals, cwd: Path) -> list[str]:
    changed_files: list[str] = []
    for path in signals["paths"]:
        if path == cwd or not path.is_relative_to(cwd):
            continue
        relative = path.relative_to(cwd).as_posix()
        if relative not in changed_files:
            changed_files.append(relative)
    return changed_files


def _resolve_primary_agent(planning_context: dict[str, object]) -> str | None:
    primary_agent = planning_context.get("primary_agent")
    if isinstance(primary_agent, str) and primary_agent.strip():
        return primary_agent
    for item in planning_context.get("instruction_files", []):
        if not isinstance(item, dict):
            continue
        instruction_name = str(item.get("name", "")).strip()
        fallback_agent = PRIMARY_AGENT_BY_INSTRUCTION.get(instruction_name)
        if fallback_agent:
            return fallback_agent
    return None


def _load_ai_work_map_module():
    return importlib.import_module("sattlint.devtools.ai.ai_work_map")


def _compact_string_entries(value: object, *, limit: int) -> list[str]:
    if not isinstance(value, list):
        return []
    compacted: list[str] = []
    for item in value:
        item_text = str(item).strip()
        if not item_text or item_text in compacted:
            continue
        compacted.append(item_text)
        if len(compacted) >= limit:
            break
    return compacted


def _compact_instruction_names(planning_context: dict[str, object], *, limit: int) -> list[str]:
    instruction_files = planning_context.get("instruction_files")
    if not isinstance(instruction_files, list):
        return []
    instruction_names: list[str] = []
    for item in instruction_files:
        if not isinstance(item, dict):
            continue
        instruction_name = str(item.get("name", "")).strip()
        if not instruction_name or instruction_name in instruction_names:
            continue
        instruction_names.append(instruction_name)
        if len(instruction_names) >= limit:
            break
    return instruction_names


def _compact_semantic_suggestion_paths(planning_context: dict[str, object], *, limit: int) -> list[str]:
    semantic_owner_suggestions = planning_context.get("semantic_owner_suggestions")
    if not isinstance(semantic_owner_suggestions, dict):
        return []
    suggestions = semantic_owner_suggestions.get("suggestions")
    if not isinstance(suggestions, list):
        return []
    semantic_paths: list[str] = []
    for item in suggestions:
        if not isinstance(item, dict):
            continue
        file_path = str(item.get("file_path", "")).strip()
        if not file_path or file_path in semantic_paths:
            continue
        semantic_paths.append(file_path)
        if len(semantic_paths) >= limit:
            break
    return semantic_paths


def _build_planning_context_payload(signals: PayloadSignals, cwd: Path) -> PlanningContextPayload | None:
    changed_files = _signal_changed_files(signals, cwd)
    if not changed_files:
        return None
    src_path = cwd / "src"
    if src_path.exists():
        src_text = str(src_path)
        if src_text not in sys.path:
            sys.path.insert(0, src_text)
    ai_work_map = _load_ai_work_map_module()

    session_context_map = ai_work_map.load_session_context_map()
    if ("generated_by" in session_context_map or "generated_from" in session_context_map) and (
        not session_context_map.get("agents") or not session_context_map.get("agent_routing")
    ):
        session_context_map = dict(session_context_map)
        session_context_map["agents"] = ai_work_map._collect_agent_metadata(ai_work_map.AGENTS_DIR)
        session_context_map["agent_routing"] = list(ai_work_map.AGENT_ROUTING_RULES)
    planning_context = ai_work_map.build_planning_context(
        changed_files=changed_files,
        recommended_check_ids=None,
        selected_surface="session-start",
        semantic_query=signals["text"] or None,
        work_map=session_context_map,
    )
    primary_agent = _resolve_primary_agent(planning_context)
    return {
        "changed_files": changed_files,
        "selected_surface": "session-start",
        "primary_agent": primary_agent,
        "instruction_names": _compact_instruction_names(planning_context, limit=3),
        "owner_test_targets": _compact_string_entries(planning_context.get("owner_test_targets"), limit=3),
        "first_validation_commands": _compact_string_entries(
            planning_context.get("first_validation_commands"),
            limit=3,
        ),
        "semantic_suggestion_paths": _compact_semantic_suggestion_paths(planning_context, limit=3),
    }


def _write_summary(
    repo_root: Path,
    signals: PayloadSignals,
    ranked: list[RankedWorkstream],
    active_count: int,
    cwd: Path,
    planning: PlanningContextPayload | None,
) -> None:
    summary_path = _summary_path(repo_root)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    top_items = ranked[:3]
    payload = {
        "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "source": f".github/coordination/{coordination_lock_state.LOCK_STATE_FILE_NAME}",
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
                "first_validation": item["entry"]["first_validation"],
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
            validation = entry.get("first_validation") or "n/a"
            parts.append(
                f"{entry['id']}: owner={entry['owner']} | status={entry['status']} | validation={validation}{reason}"
            )
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
        semantic_paths = planning.get("semantic_suggestion_paths", [])
        if semantic_paths:
            planning_bits.append(f"semantic-paths={','.join(semantic_paths[:2])}")
        if planning_bits:
            segments.append(f"Planning context: {' | '.join(planning_bits)}.")
    segments.append("Use the compact session summary first. Check the JSON lock state before editing claimed files.")
    return " ".join(segments)


def main() -> int:
    try:
        payload = _load_payload()
        if payload.get("hookEventName") != "SessionStart":
            return 0
        cwd = resolve_payload_cwd(str(payload.get("cwd") or "."))
        entries = _load_active_workstreams(cwd, cwd)
        signals = _collect_payload_signals(payload, cwd)
        ranked = _rank_workstreams(entries, signals)
        planning = _build_planning_context_payload(signals, cwd)
        _write_summary(cwd, signals, ranked, len(entries), cwd, planning)
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
    except FAIL_OPEN_EXCEPTIONS:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
