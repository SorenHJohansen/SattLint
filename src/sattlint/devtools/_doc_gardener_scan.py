from __future__ import annotations

import hashlib
import re
from collections import Counter
from collections.abc import Callable, Iterator, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any


def relative_path(path: Path, *, repo_root: Path) -> str:
    try:
        return path.relative_to(repo_root).as_posix()
    except ValueError:
        return path.as_posix()


def should_skip_path(path: Path) -> bool:
    return any(part.startswith(".venv") or part == "__pycache__" for part in path.parts)


def iter_markdown_files(
    *,
    repo_root: Path,
    markdown_suffixes: set[str],
    should_skip_path_fn: Callable[[Path], bool],
) -> Iterator[Path]:
    for path in repo_root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.casefold() not in markdown_suffixes:
            continue
        if should_skip_path_fn(path):
            continue
        yield path


def parse_markdown_table(lines: list[str], section_heading: str) -> list[tuple[int, dict[str, str]]]:
    in_section = False
    headers: list[str] | None = None
    rows: list[tuple[int, dict[str, str]]] = []

    for line_no, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped == section_heading:
            in_section = True
            headers = None
            continue
        if not in_section:
            continue
        if headers is not None and stripped.startswith("## "):
            break
        if not stripped:
            if headers is not None:
                break
            continue
        if not stripped.startswith("|"):
            if headers is not None:
                break
            continue

        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if headers is None:
            headers = cells
            continue
        if all(set(cell) <= {"-", ":"} for cell in cells):
            continue
        if len(cells) != len(headers):
            continue
        rows.append((line_no, dict(zip(headers, cells, strict=False))))

    return rows


def normalize_workstream_id(label: str) -> str | None:
    normalized = label.strip().casefold()
    for pattern in (r"^b-w(\d+)$", r"^w(\d+)(?:-|$)"):
        match = re.match(pattern, normalized)
        if match is not None:
            return f"W{match.group(1)}"
    return None


def normalize_status(status: str) -> str:
    normalized = status.strip().casefold()
    mapping = {
        "active": "In progress",
        "in progress": "In progress",
        "open": "Open",
        "planned": "Open",
        "blocked": "Blocked",
        "done": "Done",
        "partial": "Partial",
        "ready-for-merge": "In progress",
    }
    return mapping.get(normalized, status.strip())


def load_active_workstream_statuses(
    repo_root: Path,
    *,
    load_lock_state_fn: Callable[[Path], Sequence[Any]],
    normalize_workstream_id_fn: Callable[[str], str | None],
    normalize_status_fn: Callable[[str], str],
) -> dict[str, str]:
    statuses: dict[str, str] = {}

    for entry in load_lock_state_fn(repo_root):
        current_workstream_id = normalize_workstream_id_fn(entry["workstream_id"])
        if current_workstream_id is None:
            continue
        statuses[current_workstream_id] = normalize_status_fn(entry["status"])

    return statuses


def source_sync_digest(path: Path, *, read_text_fn: Callable[[Path], str]) -> str:
    content = read_text_fn(path).replace("\r\n", "\n").strip()
    return hashlib.sha1(content.encode("utf-8"), usedforsecurity=False).hexdigest()[:12]


def scan_agents_md(
    *,
    doc_finding_cls: type[Any],
    agents_md: Path,
    max_agents_lines: int,
    read_text_fn: Callable[[Path], str],
) -> Sequence[Any]:
    findings: list[Any] = []
    if not agents_md.exists():
        findings.append(doc_finding_cls("AGENTS.md", 0, "Critical", "missing", "AGENTS.md not found"))
        return findings

    lines = read_text_fn(agents_md).splitlines(keepends=True)
    line_count = len(lines)

    if line_count > max_agents_lines:
        findings.append(
            doc_finding_cls(
                "AGENTS.md",
                line_count,
                "High",
                "too_long",
                f"AGENTS.md has {line_count} lines (max {max_agents_lines})",
            )
        )

    content = "".join(lines)
    required = ["Quick Reference", "Repo Map", "Key Docs", "Critical Invariants"]
    for section in required:
        if section not in content:
            findings.append(doc_finding_cls("AGENTS.md", 0, "Medium", "structure", f"Missing section: {section}"))

    return findings


def scan_dead_links(
    *,
    doc_finding_cls: type[Any],
    docs_dir: Path,
    read_text_fn: Callable[[Path], str],
    relative_path_fn: Callable[[Path], str],
) -> Sequence[Any]:
    findings: list[Any] = []
    if not docs_dir.exists():
        return findings

    md_files = list(docs_dir.rglob("*.md")) + list(docs_dir.rglob("*.txt"))
    link_pattern = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")

    for md_file in md_files:
        try:
            lines = read_text_fn(md_file).splitlines(keepends=True)
        except Exception:
            lines = None
        if lines is None:
            continue

        for line_num, line in enumerate(lines, 1):
            for match in link_pattern.finditer(line):
                link = match.group(2)
                if link.startswith(("http", "#", "mailto")):
                    continue
                target = (md_file.parent / link).resolve()
                if not target.exists():
                    findings.append(
                        doc_finding_cls(
                            relative_path_fn(md_file),
                            line_num,
                            "Medium",
                            "dead_link",
                            f"Broken link: {link}",
                        )
                    )

    return findings


def scan_docs_structure(*, doc_finding_cls: type[Any], docs_dir: Path) -> Sequence[Any]:
    findings: list[Any] = []
    required_dirs = ["design-docs", "references"]
    required_files = [
        "quality-score.md",
        "design-docs/core-beliefs.md",
        "design-docs/index.md",
    ]

    for directory in required_dirs:
        if not (docs_dir / directory).exists():
            findings.append(doc_finding_cls("docs/", 0, "High", "structure", f"Missing directory: docs/{directory}"))

    for file_name in required_files:
        if not (docs_dir / file_name).exists():
            findings.append(doc_finding_cls("docs/", 0, "High", "missing", f"Missing file: docs/{file_name}"))

    return findings


def scan_markdown_encoding_artifacts(
    *,
    doc_finding_cls: type[Any],
    iter_markdown_files_fn: Callable[[], Iterator[Path]],
    read_text_fn: Callable[[Path], str],
    mojibake_tokens: Sequence[str],
    relative_path_fn: Callable[[Path], str],
) -> Sequence[Any]:
    findings: list[Any] = []

    for markdown_file in iter_markdown_files_fn():
        lines = read_text_fn(markdown_file).splitlines()
        for line_no, line in enumerate(lines, 1):
            tokens = [token for token in mojibake_tokens if token in line]
            if not tokens:
                continue
            findings.append(
                doc_finding_cls(
                    relative_path_fn(markdown_file),
                    line_no,
                    "Medium",
                    "encoding",
                    f"Possible mojibake tokens in markdown content: {', '.join(tokens)}",
                )
            )

    return findings


def scan_ai_first_source_drift(
    *,
    doc_finding_cls: type[Any],
    ai_first_debt: Path,
    repo_root: Path,
    read_text_fn: Callable[[Path], str],
    parse_markdown_table_fn: Callable[[list[str], str], list[tuple[int, dict[str, str]]]],
    source_sync_digest_fn: Callable[[Path], str],
    relative_path_fn: Callable[[Path], str],
) -> Sequence[Any]:
    findings: list[Any] = []
    if not ai_first_debt.exists():
        return findings

    lines = read_text_fn(ai_first_debt).splitlines()
    source_rows = parse_markdown_table_fn(lines, "## Consolidation Source Ledger")
    if not source_rows:
        return [
            doc_finding_cls(
                relative_path_fn(ai_first_debt),
                1,
                "High",
                "structure",
                "Missing consolidation source ledger in the canonical tech debt tracker.",
            )
        ]

    for line_no, row in source_rows:
        source_name = row.get("Source", "").strip()
        if not source_name:
            findings.append(
                doc_finding_cls(
                    relative_path_fn(ai_first_debt),
                    line_no,
                    "High",
                    "structure",
                    "Source-ledger row is missing a Source value.",
                )
            )
            continue

        raw_state = row.get("State", "").strip()
        if not raw_state:
            findings.append(
                doc_finding_cls(
                    relative_path_fn(ai_first_debt),
                    line_no,
                    "High",
                    "structure",
                    f"Source-ledger row for {source_name} is missing a State value.",
                )
            )
            continue

        source_path = repo_root / source_name
        state = raw_state.casefold()
        sync_basis = row.get("Sync Basis", "").strip()

        if state == "retired":
            if source_path.exists():
                findings.append(
                    doc_finding_cls(
                        relative_path_fn(ai_first_debt),
                        line_no,
                        "High",
                        "drift",
                        f"{source_name} exists but the source ledger marks it retired.",
                    )
                )
            continue

        if state != "active":
            findings.append(
                doc_finding_cls(
                    relative_path_fn(ai_first_debt),
                    line_no,
                    "Medium",
                    "structure",
                    f"Unsupported source-ledger state '{raw_state}' for {source_name}.",
                )
            )
            continue

        if not source_path.exists():
            findings.append(
                doc_finding_cls(
                    relative_path_fn(ai_first_debt),
                    line_no,
                    "High",
                    "drift",
                    f"{source_name} is marked active in the source ledger but the file is missing.",
                )
            )
            continue

        if not sync_basis.startswith("sha1:"):
            findings.append(
                doc_finding_cls(
                    relative_path_fn(ai_first_debt),
                    line_no,
                    "Medium",
                    "drift",
                    f"{source_name} is active but has no sha1 sync basis in the source ledger.",
                )
            )
            continue

        actual_digest = f"sha1:{source_sync_digest_fn(source_path)}"
        if actual_digest != sync_basis:
            findings.append(
                doc_finding_cls(
                    relative_path_fn(ai_first_debt),
                    line_no,
                    "High",
                    "drift",
                    f"{source_name} drifted from the source-ledger sync basis ({sync_basis} != {actual_digest}).",
                )
            )

    return findings


def scan_ai_first_status_drift(
    *,
    doc_finding_cls: type[Any],
    ai_first_debt: Path,
    repo_root: Path,
    read_text_fn: Callable[[Path], str],
    parse_markdown_table_fn: Callable[[list[str], str], list[tuple[int, dict[str, str]]]],
    load_active_workstream_statuses_fn: Callable[[Path], dict[str, str]],
    normalize_workstream_id_fn: Callable[[str], str | None],
    normalize_status_fn: Callable[[str], str],
    relative_path_fn: Callable[[Path], str],
) -> Sequence[Any]:
    findings: list[Any] = []
    if not ai_first_debt.exists():
        return findings

    current_statuses = load_active_workstream_statuses_fn(repo_root)
    if not current_statuses:
        return findings
    debt_rows = parse_markdown_table_fn(
        read_text_fn(ai_first_debt).splitlines(),
        "## Program B: Refactor And Architecture Debt",
    )

    for line_no, row in debt_rows:
        debt_id = row.get("Debt ID", "")
        workstream_id = normalize_workstream_id_fn(debt_id)
        if workstream_id is None:
            continue
        current_status = current_statuses.get(workstream_id)
        if current_status is None:
            continue
        debt_status = normalize_status_fn(row.get("Status", ""))
        if debt_status == current_status:
            continue
        findings.append(
            doc_finding_cls(
                relative_path_fn(ai_first_debt),
                line_no,
                "Medium",
                "stale_status",
                f"{debt_id} status is '{row.get('Status', '')}' but the active coordination lock state tracks '{current_status}'.",
            )
        )

    return findings


def scan_completed_exec_plans_still_active(
    *,
    doc_finding_cls: type[Any],
    docs_dir: Path,
    relative_path_fn: Callable[[Path], str],
) -> Sequence[Any]:
    from sattlint.devtools import ai_work_map as ai_work_map_module

    findings: list[Any] = []
    active_exec_plans_dir = docs_dir / "exec-plans" / "active"
    if not active_exec_plans_dir.exists():
        return findings

    for plan_path in sorted(active_exec_plans_dir.glob("*.md")):
        if not ai_work_map_module.is_completed_exec_plan(plan_path):
            continue
        findings.append(
            doc_finding_cls(
                relative_path_fn(plan_path),
                1,
                "High",
                "stale",
                "ExecPlan Progress is fully complete but the file still lives under docs/exec-plans/active/. Move it to docs/exec-plans/completed/.",
            )
        )

    return findings


def scan_stale_docs(
    *,
    doc_finding_cls: type[Any],
    docs_dir: Path,
    read_text_fn: Callable[[Path], str],
    relative_path_fn: Callable[[Path], str],
    run_repo_cli_fn: Callable[[str, Sequence[str]], Any],
) -> Sequence[Any]:
    findings: list[Any] = []
    try:
        thirty_days_ago = datetime.now(UTC) - timedelta(days=30)

        result = run_repo_cli_fn("git", ["log", "-1", "--format=%H", "--", "src/"])
        if result.returncode != 0:
            return findings

        code_commit = result.stdout.strip()
        if not code_commit:
            return findings

        md_files = list(docs_dir.rglob("*.md")) + list(docs_dir.rglob("*.txt"))
        for doc in md_files:
            rel_path = doc.relative_to(docs_dir.parent)
            doc_result = run_repo_cli_fn("git", ["log", "-1", "--format=%ct", "--", str(rel_path)])
            if doc_result.returncode == 0 and doc_result.stdout.strip():
                try:
                    doc_timestamp = float(doc_result.stdout.strip())
                    doc_date = datetime.fromtimestamp(doc_timestamp, UTC)

                    if doc_date < thirty_days_ago:
                        content = read_text_fn(doc)
                        code_refs = re.findall(r"`([^`]+\.(?:py|toml|json|yaml|yml))`", content)
                        stale_refs: list[str] = []
                        for ref in code_refs:
                            ref_path = docs_dir.parent / ref
                            if ref_path.exists():
                                ref_result = run_repo_cli_fn("git", ["log", "-1", "--format=%ct", "--", str(ref)])
                                if ref_result.returncode == 0 and ref_result.stdout.strip():
                                    try:
                                        ref_timestamp = float(ref_result.stdout.strip())
                                        ref_date = datetime.fromtimestamp(ref_timestamp, UTC)
                                        if ref_date > doc_date:
                                            stale_refs.append(ref)
                                    except ValueError:
                                        pass

                        if stale_refs:
                            stale_summary = ", ".join(stale_refs[:3])
                            if len(stale_refs) > 3:
                                stale_summary += "..."
                            findings.append(
                                doc_finding_cls(
                                    relative_path_fn(doc),
                                    1,
                                    "Medium",
                                    "stale",
                                    f"Documentation references {len(stale_refs)} files modified since last doc update: {stale_summary}",
                                )
                            )
                except ValueError:
                    pass

    except Exception:
        return findings

    return findings


def build_scan_result(
    findings: Sequence[Any],
    *,
    severity_order: Sequence[str],
    category_order: Sequence[str],
    timestamp: str,
) -> dict[str, Any]:
    severity_counts = Counter(finding.severity for finding in findings)
    category_counts = Counter(finding.category for finding in findings)

    return {
        "timestamp": timestamp,
        "total_findings": len(findings),
        "by_severity": {severity: severity_counts.get(severity, 0) for severity in severity_order},
        "by_category": {category: category_counts.get(category, 0) for category in category_order},
        "findings": [finding._asdict() for finding in findings],
    }
