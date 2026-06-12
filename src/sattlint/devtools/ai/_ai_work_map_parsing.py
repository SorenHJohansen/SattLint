"""Parsing and archive helpers for the AI work map."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

REFERENCE_UPDATE_SUFFIXES = {".json", ".md", ".py", ".toml", ".txt", ".yaml", ".yml"}
REFERENCE_UPDATE_SKIP_ROOTS = {".git", ".venv", "artifacts", "htmlcov", "__pycache__"}

BACKTICK_RE = re.compile(r"`([^`]+)`")
VALIDATION_ROUTE_RE = re.compile(r"^- (?P<surface>.+):\s*$")
QUOTED_ITEM_RE = re.compile(r'"([^"]+)"')
SECTION_HEADING_RE = re.compile(r"^##\s+")
PROGRESS_HEADING_RE = re.compile(r"^##\s+Progress\s*$", re.IGNORECASE)
CHECKBOX_RE = re.compile(r"^\s*-\s+\[(?P<state>[ xX])\]\s+")
OWNER_SUITE_HEADINGS = (
    "Primary owner suites for this plan:",
    "Existing owner suites that this plan may reuse instead of creating new suites when the fit is real:",
)
FIRST_VALIDATION_HEADING = "Per-slice first validations:"

type JsonDict = dict[str, object]


def dict_entries(value: object) -> list[JsonDict]:
    if not isinstance(value, list):
        return []
    items = cast(list[object], value)
    entries: list[JsonDict] = []
    for item in items:
        if isinstance(item, dict):
            entries.append(cast(JsonDict, item))
    return entries


def _read_lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines()


def _extract_backtick_items(text: str) -> list[str]:
    return [item.strip() for item in BACKTICK_RE.findall(text) if item.strip()]


def _strip_quotes(value: str) -> str:
    stripped = value.strip()
    if stripped.startswith(('"', "'")) and stripped.endswith(('"', "'")) and len(stripped) >= 2:
        return stripped[1:-1]
    return stripped


def _parse_progress_checkbox_states(plan_path: Path) -> list[bool]:
    lines = _read_lines(plan_path)
    in_progress = False
    states: list[bool] = []

    for line in lines:
        stripped = line.strip()
        if not in_progress:
            if PROGRESS_HEADING_RE.match(stripped):
                in_progress = True
            continue
        if SECTION_HEADING_RE.match(stripped):
            break
        match = CHECKBOX_RE.match(line)
        if match is None:
            continue
        states.append(match.group("state").casefold() == "x")

    return states


def _is_completed_exec_plan(plan_path: Path) -> bool:
    states = _parse_progress_checkbox_states(plan_path)
    return bool(states) and all(states)


def _iter_reference_update_files(repo_root: Path) -> list[Path]:
    files: list[Path] = []
    for path in repo_root.rglob("*"):
        if not path.is_file() or path.suffix.casefold() not in REFERENCE_UPDATE_SUFFIXES:
            continue
        try:
            relative_path = path.relative_to(repo_root)
        except ValueError:
            continue
        if any(part in REFERENCE_UPDATE_SKIP_ROOTS or part.startswith(".venv") for part in relative_path.parts):
            continue
        files.append(path)
    return files


def rewrite_exec_plan_references(
    archived: list[dict[str, str]],
    *,
    repo_root: Path,
    iter_reference_update_files: Callable[[Path], list[Path]],
) -> None:
    if not archived:
        return
    replacements = [(entry["from"], entry["to"]) for entry in archived]
    for path in iter_reference_update_files(repo_root):
        try:
            original = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        updated = original
        for old_path, new_path in replacements:
            updated = updated.replace(old_path, new_path)
        if updated != original:
            path.write_text(updated, encoding="utf-8")


def exec_plan_repo_root(active_dir: Path, completed_dir: Path) -> Path:
    shared_plans_dir = active_dir.parent
    if (
        active_dir.name == "active"
        and completed_dir.name == "completed"
        and shared_plans_dir == completed_dir.parent
        and shared_plans_dir.name == "exec-plans"
        and shared_plans_dir.parent.name == "docs"
    ):
        return shared_plans_dir.parent.parent

    shared_parts: list[str] = []
    for active_part, completed_part in zip(active_dir.parts, completed_dir.parts, strict=False):
        if active_part != completed_part:
            break
        shared_parts.append(active_part)

    return Path(*shared_parts) if shared_parts else active_dir.parent


def archive_completed_exec_plans(
    active_dir: Path,
    completed_dir: Path,
    *,
    repo_root: Path | None = None,
    is_completed_exec_plan: Callable[[Path], bool],
    rewrite_exec_plan_references: Callable[[list[dict[str, str]], Path], None],
) -> list[dict[str, str]]:
    archived: list[dict[str, str]] = []
    resolved_repo_root = repo_root if repo_root is not None else exec_plan_repo_root(active_dir, completed_dir)
    completed_dir.mkdir(parents=True, exist_ok=True)

    for plan_path in sorted(active_dir.glob("*.md")):
        if not is_completed_exec_plan(plan_path):
            continue
        destination = completed_dir / plan_path.name
        if destination.exists():
            raise FileExistsError(f"Completed exec plan already exists: {destination}")
        plan_path.replace(destination)
        archived.append(
            {
                "from": plan_path.relative_to(resolved_repo_root).as_posix(),
                "to": destination.relative_to(resolved_repo_root).as_posix(),
            }
        )

    rewrite_exec_plan_references(archived, resolved_repo_root)
    return archived


def _parse_frontmatter(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return {}
    _, _, remainder = text.partition("---\n")
    frontmatter_text, _, _ = remainder.partition("\n---\n")
    data: dict[str, Any] = {}
    for raw_line in frontmatter_text.splitlines():
        line = raw_line.strip()
        if not line or ":" not in line:
            continue
        key, raw_value = line.split(":", 1)
        value = raw_value.strip()
        if value.startswith("[") and value.endswith("]"):
            quoted_items = QUOTED_ITEM_RE.findall(value)
            if quoted_items:
                data[key] = quoted_items
            else:
                inner = value[1:-1].strip()
                data[key] = [] if not inner else [_strip_quotes(item) for item in inner.split(",") if item.strip()]
            continue
        if value.casefold() in {"true", "false"}:
            data[key] = value.casefold() == "true"
            continue
        data[key] = _strip_quotes(value)
    return data


def _parse_validation_routes(path: Path) -> list[dict[str, Any]]:
    routes: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None

    for raw_line in _read_lines(path):
        line = raw_line.rstrip()
        route_match = VALIDATION_ROUTE_RE.match(line)
        if route_match is not None:
            if current is not None:
                routes.append(current)
            current = {
                "surface": route_match.group("surface").strip(),
                "commands": [],
                "notes": [],
            }
            continue
        if current is None:
            continue
        stripped = line.strip()
        if not stripped:
            continue
        commands = _extract_backtick_items(stripped)
        if commands:
            current["commands"].extend(commands)
            note_text = BACKTICK_RE.sub("", stripped).strip()
            if note_text:
                current["notes"].append(note_text)
            continue
        current["notes"].append(stripped)

    if current is not None:
        routes.append(current)
    return routes


def _parse_owner_suites(path: Path) -> list[dict[str, Any]]:
    lines = _read_lines(path)
    suites: list[dict[str, Any]] = []
    collecting = False

    for raw_line in lines:
        line = raw_line.rstrip()
        if line in OWNER_SUITE_HEADINGS:
            collecting = True
            continue
        if not collecting:
            continue
        stripped = line.strip()
        if not stripped:
            if suites:
                break
            continue
        if not stripped.startswith("- "):
            if suites:
                break
            continue
        body = stripped[2:]
        tests_part, separator, targets_part = body.partition("->")
        suites.append(
            {
                "tests": _extract_backtick_items(tests_part),
                "targets": _extract_backtick_items(targets_part),
                "target_summary": targets_part.strip() if separator else tests_part.strip(),
            }
        )
    return suites


def _parse_first_validation_commands(path: Path) -> list[str]:
    lines = _read_lines(path)
    commands: list[str] = []
    collecting = False

    for raw_line in lines:
        line = raw_line.rstrip("\n")
        if line.rstrip() == FIRST_VALIDATION_HEADING:
            collecting = True
            continue
        if not collecting:
            continue
        if not line.strip():
            if commands:
                break
            continue
        if not line.startswith("    "):
            if commands:
                break
            continue
        commands.append(line.strip())
    return commands


def collect_owner_suite_plans(exec_plans_dir: Path, *, repo_root: Path) -> list[dict[str, Any]]:
    plans: list[dict[str, Any]] = []
    for path in sorted(exec_plans_dir.glob("*.md")):
        suites = _parse_owner_suites(path)
        if not suites:
            continue
        plans.append(
            {
                "plan_path": path.relative_to(repo_root).as_posix(),
                "owner_heading": next(
                    (heading for heading in OWNER_SUITE_HEADINGS if heading in path.read_text(encoding="utf-8")),
                    OWNER_SUITE_HEADINGS[0],
                ),
                "suites": suites,
                "first_validation_commands": _parse_first_validation_commands(path),
            }
        )
    return plans


def collect_instruction_metadata(instructions_dir: Path, *, repo_root: Path) -> list[dict[str, Any]]:
    metadata: list[dict[str, Any]] = []
    for path in sorted(instructions_dir.glob("*.instructions.md")):
        frontmatter = _parse_frontmatter(path)
        metadata.append(
            {
                "file_path": path.relative_to(repo_root).as_posix(),
                "name": frontmatter.get("name", path.stem),
                "description": frontmatter.get("description", ""),
                "apply_to": list(frontmatter.get("applyTo", [])),
            }
        )
    return metadata


def collect_agent_metadata(agents_dir: Path, *, repo_root: Path) -> list[dict[str, Any]]:
    metadata: list[dict[str, Any]] = []
    for path in sorted(agents_dir.glob("*.agent.md")):
        frontmatter = _parse_frontmatter(path)
        metadata.append(
            {
                "file_path": path.relative_to(repo_root).as_posix(),
                "name": frontmatter.get("name", path.stem),
                "description": frontmatter.get("description", ""),
                "user_invocable": bool(frontmatter.get("user-invocable", False)),
            }
        )
    return metadata


def render_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def read_lines(path: Path) -> list[str]:
    return _read_lines(path)


def extract_backtick_items(text: str) -> list[str]:
    return _extract_backtick_items(text)


def strip_quotes(value: str) -> str:
    return _strip_quotes(value)


def parse_progress_checkbox_states(plan_path: Path) -> list[bool]:
    return _parse_progress_checkbox_states(plan_path)


def is_completed_exec_plan(plan_path: Path) -> bool:
    return _is_completed_exec_plan(plan_path)


def iter_reference_update_files(repo_root: Path) -> list[Path]:
    return _iter_reference_update_files(repo_root)


def parse_frontmatter(path: Path) -> dict[str, Any]:
    return _parse_frontmatter(path)


def parse_validation_routes(path: Path) -> list[dict[str, Any]]:
    return _parse_validation_routes(path)


def parse_owner_suites(path: Path) -> list[dict[str, Any]]:
    return _parse_owner_suites(path)


def parse_first_validation_commands(path: Path) -> list[str]:
    return _parse_first_validation_commands(path)
