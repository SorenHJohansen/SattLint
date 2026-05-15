"""Doc-gardening agent: scans for stale docs, validates links, updates tracking files.

Runs on CI or manual trigger. Updates quality-score.md and tech-debt-tracker.md.
Opens fix-up PRs when issues found (optional).

Based on OpenAI harness engineering: "A recurring doc-gardening agent scans for
stale or obsolete documentation that does not reflect the real code behavior
and opens fix-up pull requests."
"""

import argparse
import hashlib
import json
import re
import shutil

# Internal doc-gardener intentionally invokes trusted git and gh CLIs.
import subprocess  # nosec B404
import sys
from collections import Counter
from collections.abc import Iterator, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, NamedTuple

from sattlint.devtools import coordination_lock_state

# Constants
REPO_ROOT = Path(__file__).resolve().parents[3]
DOCS_DIR = REPO_ROOT / "docs"
AGENTS_MD = REPO_ROOT / "AGENTS.md"
QUALITY_SCORE = DOCS_DIR / "quality-score.md"
TECH_DEBT = DOCS_DIR / "exec-plans" / "tech-debt-tracker.md"
DEFAULT_PIPELINE_OUTPUT_DIR = REPO_ROOT / "artifacts" / "analysis"
CURRENT_WORK = REPO_ROOT / ".github" / "coordination" / coordination_lock_state.LOCK_STATE_FILE_NAME
CURRENT_WORK_TEMPLATE = REPO_ROOT / ".github" / "coordination" / "current-work.template.md"
AI_FIRST_PLAN = DOCS_DIR / "exec-plans" / "completed" / "ai-first-repo-hardening.md"
AI_FIRST_DEBT = TECH_DEBT
MAX_AGENTS_LINES = 100
AI_FIRST_SOURCE_FILES = (
    "TODO_GUI.md",
    "TODO_REFACTOR.md",
    "TODO_SATTLINT.md",
    "TODO_TOOLS.md",
)
MARKDOWN_SUFFIXES = {".md", ".txt"}
MOJIBAKE_TOKENS = (
    "\ufffd",
    "\u00e2\u20ac\u201c",
    "\u00e2\u20ac\u201d",
    "\u00e2\u20ac\u2122",
    "\u00e2\u20ac\u0153",
    "\u00e2\u20ac\u009d",
    "\u00c2 ",
)
SEVERITY_ORDER = ("Critical", "High", "Medium", "Low")
CATEGORY_ORDER = (
    "stale",
    "dead_link",
    "too_long",
    "missing",
    "structure",
    "encoding",
    "drift",
    "stale_status",
)


def _resolve_cli(tool_name: str) -> str:
    resolved = shutil.which(tool_name)
    if resolved is None:
        raise FileNotFoundError(tool_name)
    return resolved


def _run_repo_cli(tool_name: str, args: Sequence[str]) -> subprocess.CompletedProcess[str]:
    # Commands are fixed internal git/gh invocations with explicit argv lists.
    return subprocess.run(  # nosec B603
        [_resolve_cli(tool_name), *args],
        capture_output=True,
        text=True,
        cwd=DOCS_DIR.parent,
        check=False,
    )


class DocFinding(NamedTuple):
    """A finding from doc-gardening scan."""

    file: str
    line: int
    severity: str  # "Critical", "High", "Medium", "Low"
    category: str  # "stale", "dead_link", "too_long", "missing", "structure"
    message: str


class PipelineSnapshot(NamedTuple):
    output_dir: Path
    profile: str | None
    overall_status: str
    normalized_findings: int | None
    coverage_total_line_rate: float | None


def _relative_path(path: Path) -> str:
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _read_text(path: Path) -> str:
    raw = path.read_bytes()
    for encoding in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _load_json_mapping(path: Path) -> dict[str, Any]:
    payload = json.loads(_read_text(path))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object in {path.as_posix()}")
    return payload


def _load_pipeline_finding_count(output_dir: Path) -> int | None:
    findings_path = output_dir / "findings.json"
    if not findings_path.exists():
        return None
    try:
        findings_payload = _load_json_mapping(findings_path)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError):
        return None
    finding_count = findings_payload.get("finding_count")
    return finding_count if isinstance(finding_count, int) else None


def load_pipeline_snapshot(output_dir: Path) -> tuple[PipelineSnapshot | None, str | None]:
    summary_path = output_dir / "summary.json"
    status_path = output_dir / "status.json"
    missing_paths = [path.name for path in (summary_path, status_path) if not path.exists()]
    if missing_paths:
        missing = ", ".join(sorted(missing_paths))
        return None, f"missing pipeline artifacts: {missing}"

    try:
        summary_payload = _load_json_mapping(summary_path)
        status_payload = _load_json_mapping(status_path)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        return None, f"unable to read pipeline artifacts from {output_dir.as_posix()}: {exc}"

    overall_status = status_payload.get("overall_status")
    if not isinstance(overall_status, str) or not overall_status:
        return None, f"invalid pipeline status in {status_path.as_posix()}"

    counts = summary_payload.get("counts")
    normalized_findings = counts.get("normalized_findings") if isinstance(counts, dict) else None
    if not isinstance(normalized_findings, int):
        normalized_findings = _load_pipeline_finding_count(output_dir)

    reports = summary_payload.get("reports")
    coverage_total_line_rate: float | None = None
    coverage_report = reports.get("coverage_summary") if isinstance(reports, dict) else None
    if isinstance(coverage_report, str) and coverage_report:
        coverage_path = output_dir / coverage_report
        if coverage_path.exists():
            try:
                coverage_payload = _load_json_mapping(coverage_path)
            except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError):
                coverage_payload = {}
            coverage_summary = coverage_payload.get("summary")
            total_line_rate = coverage_summary.get("total_line_rate") if isinstance(coverage_summary, dict) else None
            if isinstance(total_line_rate, int | float):
                coverage_total_line_rate = float(total_line_rate)

    profile = summary_payload.get("profile")
    return (
        PipelineSnapshot(
            output_dir=output_dir,
            profile=profile if isinstance(profile, str) and profile else None,
            overall_status=overall_status,
            normalized_findings=normalized_findings,
            coverage_total_line_rate=coverage_total_line_rate,
        ),
        None,
    )


def _format_coverage_percent(line_rate: float | None) -> str:
    if line_rate is None:
        return "coverage n/a"
    return f"{line_rate * 100:.1f}% coverage"


def _grade_from_pipeline_snapshot(snapshot: PipelineSnapshot) -> str:
    if snapshot.overall_status == "fail":
        return "D"

    coverage = snapshot.coverage_total_line_rate
    if coverage is None:
        return "C" if snapshot.overall_status == "pass_with_notes" else "B"

    if coverage >= 0.80:
        grade = "A"
    elif coverage >= 0.30:
        grade = "B"
    elif coverage >= 0.15:
        grade = "C"
    else:
        grade = "D"

    if snapshot.overall_status == "pass_with_notes":
        return {"A": "B", "B": "C", "C": "D", "D": "D"}[grade]
    return grade


def _build_quality_trend_entry(
    findings: Sequence[DocFinding],
    *,
    pipeline_snapshot: PipelineSnapshot | None,
) -> tuple[str, str, str, str]:
    date_str = datetime.now(UTC).strftime("%Y-%m-%d")
    if pipeline_snapshot is None:
        return date_str, "B", f"{len(findings)} findings", "Scan"

    pipeline_findings = pipeline_snapshot.normalized_findings
    findings_summary = (
        f"{pipeline_findings} pipeline findings" if pipeline_findings is not None else "pipeline findings n/a"
    )
    notes = "; ".join(
        (
            pipeline_snapshot.overall_status,
            findings_summary,
            f"{len(findings)} doc findings",
            _format_coverage_percent(pipeline_snapshot.coverage_total_line_rate),
        )
    )
    return date_str, _grade_from_pipeline_snapshot(pipeline_snapshot), notes, "Pipeline"


def _upsert_trend_section(content: str, *, row: str) -> str:
    header = "## Trend\n\n| Date | Grade | Notes | Source |\n|---|---|---|---|"
    section_re = re.compile(r"(?ms)^## Trend\n.*?(?=^## |\Z)")
    row_cells = [cell.strip() for cell in row.strip().strip("|").split("|")]

    def build_section(existing_section: str | None) -> str:
        existing_rows: list[str] = []
        if existing_section is not None:
            for line in existing_section.splitlines():
                stripped = line.strip()
                if not stripped.startswith("|"):
                    continue
                if stripped.startswith("| Date ") or stripped.startswith("|---"):
                    continue
                cells = [cell.strip() for cell in stripped.strip("|").split("|")]
                if len(cells) != 4:
                    continue
                if cells[0] == row_cells[0] and cells[3] == row_cells[3]:
                    continue
                existing_rows.append(stripped)
        lines = [header, row, *existing_rows, ""]
        return "\n".join(lines)

    existing_match = section_re.search(content)
    if existing_match is not None:
        return (
            content[: existing_match.start()] + build_section(existing_match.group(0)) + content[existing_match.end() :]
        )

    new_section = build_section(None)
    grading_scale_heading = "## Grading Scale"
    if grading_scale_heading in content:
        before, after = content.split(grading_scale_heading, 1)
        before = before.rstrip() + "\n\n"
        return before + new_section + grading_scale_heading + after
    return content.rstrip() + "\n\n" + new_section


def _should_skip_path(path: Path) -> bool:
    return any(part.startswith(".venv") or part == "__pycache__" for part in path.parts)


def _iter_markdown_files() -> Iterator[Path]:
    for path in REPO_ROOT.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.casefold() not in MARKDOWN_SUFFIXES:
            continue
        if _should_skip_path(path):
            continue
        yield path


def _parse_markdown_table(lines: list[str], section_heading: str) -> list[tuple[int, dict[str, str]]]:
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


def _normalize_workstream_id(label: str) -> str | None:
    normalized = label.strip().casefold()
    for pattern in (r"^b-w(\d+)$", r"^w(\d+)(?:-|$)"):
        match = re.match(pattern, normalized)
        if match is not None:
            return f"W{match.group(1)}"
    return None


def _normalize_status(status: str) -> str:
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


def _load_active_workstream_statuses(repo_root: Path = REPO_ROOT) -> dict[str, str]:
    statuses: dict[str, str] = {}

    for entry in coordination_lock_state.load_lock_state(repo_root):
        current_workstream_id = _normalize_workstream_id(entry["workstream_id"])
        if current_workstream_id is None:
            continue
        statuses[current_workstream_id] = _normalize_status(entry["status"])

    return statuses


def _source_sync_digest(path: Path) -> str:
    content = _read_text(path).replace("\r\n", "\n").strip()
    return hashlib.sha1(content.encode("utf-8"), usedforsecurity=False).hexdigest()[:12]


def scan_agents_md() -> Sequence[DocFinding]:
    """Check AGENTS.md is under 100 lines and well-structured."""
    findings = []
    if not AGENTS_MD.exists():
        findings.append(DocFinding("AGENTS.md", 0, "Critical", "missing", "AGENTS.md not found"))
        return findings

    lines = _read_text(AGENTS_MD).splitlines(keepends=True)
    line_count = len(lines)

    if line_count > MAX_AGENTS_LINES:
        findings.append(
            DocFinding(
                "AGENTS.md",
                line_count,
                "High",
                "too_long",
                f"AGENTS.md has {line_count} lines (max {MAX_AGENTS_LINES})",
            )
        )

    # Check for required sections
    content = "".join(lines)
    required = ["Quick Reference", "Repo Map", "Key Docs", "Critical Invariants"]
    for section in required:
        if section not in content:
            findings.append(DocFinding("AGENTS.md", 0, "Medium", "structure", f"Missing section: {section}"))

    return findings


def scan_dead_links() -> Sequence[DocFinding]:
    """Check for dead links in markdown files under docs/."""
    findings = []
    if not DOCS_DIR.exists():
        return findings

    md_files = list(DOCS_DIR.rglob("*.md")) + list(DOCS_DIR.rglob("*.txt"))
    link_pattern = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")

    for md_file in md_files:
        try:
            lines = _read_text(md_file).splitlines(keepends=True)
        except Exception:
            lines = None
        if lines is None:
            continue

        for line_num, line in enumerate(lines, 1):
            for match in link_pattern.finditer(line):
                link = match.group(2)
                # Skip external links, anchors, mailto
                if link.startswith(("http", "#", "mailto")):
                    continue
                # Resolve relative to docs dir
                target = (md_file.parent / link).resolve()
                if not target.exists():
                    findings.append(
                        DocFinding(
                            _relative_path(md_file),
                            line_num,
                            "Medium",
                            "dead_link",
                            f"Broken link: {link}",
                        )
                    )

    return findings


def scan_docs_structure() -> Sequence[DocFinding]:
    """Validate docs/ directory structure matches harness-engineering layout."""
    findings = []
    required_dirs = ["design-docs", "exec-plans", "references"]
    required_files = [
        "quality-score.md",
        "design-docs/core-beliefs.md",
        "design-docs/index.md",
        "exec-plans/completed/ai-first-repo-hardening.md",
        "exec-plans/tech-debt-tracker.md",
    ]

    for d in required_dirs:
        if not (DOCS_DIR / d).exists():
            findings.append(DocFinding("docs/", 0, "High", "structure", f"Missing directory: docs/{d}"))

    for f in required_files:
        if not (DOCS_DIR / f).exists():
            findings.append(DocFinding("docs/", 0, "High", "missing", f"Missing file: docs/{f}"))

    return findings


def scan_markdown_encoding_artifacts() -> Sequence[DocFinding]:
    """Flag likely mojibake sequences in tracked markdown and text files."""
    findings = []

    for markdown_file in _iter_markdown_files():
        lines = _read_text(markdown_file).splitlines()
        for line_no, line in enumerate(lines, 1):
            tokens = [token for token in MOJIBAKE_TOKENS if token in line]
            if not tokens:
                continue
            findings.append(
                DocFinding(
                    _relative_path(markdown_file),
                    line_no,
                    "Medium",
                    "encoding",
                    f"Possible mojibake tokens in markdown content: {', '.join(tokens)}",
                )
            )

    return findings


def scan_ai_first_source_drift() -> Sequence[DocFinding]:
    """Validate the AI-first source ledger against the presence of legacy TODO files."""
    findings = []
    if not AI_FIRST_DEBT.exists():
        return findings

    lines = _read_text(AI_FIRST_DEBT).splitlines()
    source_rows = _parse_markdown_table(lines, "## Consolidation Source Ledger")
    if not source_rows:
        return [
            DocFinding(
                _relative_path(AI_FIRST_DEBT),
                1,
                "High",
                "structure",
                "Missing consolidation source ledger in the canonical tech debt tracker.",
            )
        ]

    row_by_source = {row["Source"]: (line_no, row) for line_no, row in source_rows if row.get("Source")}

    for source_name in AI_FIRST_SOURCE_FILES:
        source_path = REPO_ROOT / source_name
        ledger_row = row_by_source.get(source_name)
        if ledger_row is None:
            findings.append(
                DocFinding(
                    _relative_path(AI_FIRST_DEBT),
                    1,
                    "High",
                    "drift",
                    f"Canonical tech debt tracker is missing a source-ledger row for {source_name}.",
                )
            )
            continue

        line_no, row = ledger_row
        state = row.get("State", "").strip().casefold()
        sync_basis = row.get("Sync Basis", "").strip()

        if state == "retired":
            if source_path.exists():
                findings.append(
                    DocFinding(
                        _relative_path(AI_FIRST_DEBT),
                        line_no,
                        "High",
                        "drift",
                        f"{source_name} exists but the source ledger marks it retired.",
                    )
                )
            continue

        if state != "active":
            findings.append(
                DocFinding(
                    _relative_path(AI_FIRST_DEBT),
                    line_no,
                    "Medium",
                    "structure",
                    f"Unsupported source-ledger state '{row.get('State', '')}' for {source_name}.",
                )
            )
            continue

        if not source_path.exists():
            findings.append(
                DocFinding(
                    _relative_path(AI_FIRST_DEBT),
                    line_no,
                    "High",
                    "drift",
                    f"{source_name} is marked active in the source ledger but the file is missing.",
                )
            )
            continue

        if not sync_basis.startswith("sha1:"):
            findings.append(
                DocFinding(
                    _relative_path(AI_FIRST_DEBT),
                    line_no,
                    "Medium",
                    "drift",
                    f"{source_name} is active but has no sha1 sync basis in the source ledger.",
                )
            )
            continue

        actual_digest = f"sha1:{_source_sync_digest(source_path)}"
        if actual_digest != sync_basis:
            findings.append(
                DocFinding(
                    _relative_path(AI_FIRST_DEBT),
                    line_no,
                    "High",
                    "drift",
                    f"{source_name} drifted from the source-ledger sync basis ({sync_basis} != {actual_digest}).",
                )
            )

    return findings


def scan_ai_first_status_drift() -> Sequence[DocFinding]:
    """Compare refactor-lane statuses in the canonical tech debt tracker against active workstreams."""
    findings = []
    if not AI_FIRST_DEBT.exists():
        return findings

    current_statuses = _load_active_workstream_statuses(REPO_ROOT)
    if not current_statuses:
        return findings
    debt_rows = _parse_markdown_table(
        _read_text(AI_FIRST_DEBT).splitlines(),
        "## Program B: Refactor And Architecture Debt",
    )

    for line_no, row in debt_rows:
        debt_id = row.get("Debt ID", "")
        workstream_id = _normalize_workstream_id(debt_id)
        if workstream_id is None:
            continue
        current_status = current_statuses.get(workstream_id)
        if current_status is None:
            continue
        debt_status = _normalize_status(row.get("Status", ""))
        if debt_status == current_status:
            continue
        findings.append(
            DocFinding(
                _relative_path(AI_FIRST_DEBT),
                line_no,
                "Medium",
                "stale_status",
                f"{debt_id} status is '{row.get('Status', '')}' but the active coordination lock state tracks '{current_status}'.",
            )
        )

    return findings


def scan_completed_exec_plans_still_active() -> Sequence[DocFinding]:
    """Flag exec plans whose Progress section is complete but that still live in active/."""
    from sattlint.devtools import ai_work_map as _ai_work_map_module

    findings = []
    active_exec_plans_dir = DOCS_DIR / "exec-plans" / "active"
    if not active_exec_plans_dir.exists():
        return findings

    for plan_path in sorted(active_exec_plans_dir.glob("*.md")):
        if not _ai_work_map_module._is_completed_exec_plan(plan_path):
            continue
        findings.append(
            DocFinding(
                _relative_path(plan_path),
                1,
                "High",
                "stale",
                "ExecPlan Progress is fully complete but the file still lives under docs/exec-plans/active/. Move it to docs/exec-plans/completed/.",
            )
        )

    return findings


def scan_stale_docs() -> Sequence[DocFinding]:
    """Check if docs are stale compared to code changes (git-based heuristic)."""
    findings = []
    try:
        # Get timestamp for 30 days ago
        thirty_days_ago = datetime.now(UTC) - timedelta(days=30)

        # Find docs modified more than 30 days ago but code changed recently
        result = _run_repo_cli("git", ["log", "-1", "--format=%H", "--", "src/"])
        if result.returncode != 0:
            return findings

        code_commit = result.stdout.strip()
        if not code_commit:
            return findings

        # Check each doc file's last modification vs code changes
        md_files = list(DOCS_DIR.rglob("*.md")) + list(DOCS_DIR.rglob("*.txt"))
        for doc in md_files:
            rel_path = doc.relative_to(DOCS_DIR.parent)
            # Get doc's last commit timestamp
            doc_result = _run_repo_cli("git", ["log", "-1", "--format=%ct", "--", str(rel_path)])
            if doc_result.returncode == 0 and doc_result.stdout.strip():
                try:
                    doc_timestamp = float(doc_result.stdout.strip())
                    doc_date = datetime.fromtimestamp(doc_timestamp, UTC)

                    # Only check docs older than 30 days
                    if doc_date < thirty_days_ago:
                        # Check if doc references code that has changed since doc was last updated
                        content = _read_text(doc)

                        # Look for code file references
                        code_refs = re.findall(r"`([^`]+\.(?:py|toml|json|yaml|yml))`", content)
                        stale_refs = []
                        for ref in code_refs:
                            ref_path = DOCS_DIR.parent / ref
                            if ref_path.exists():
                                # Get when this code file was last modified
                                ref_result = _run_repo_cli("git", ["log", "-1", "--format=%ct", "--", str(ref)])
                                if ref_result.returncode == 0 and ref_result.stdout.strip():
                                    try:
                                        ref_timestamp = float(ref_result.stdout.strip())
                                        ref_date = datetime.fromtimestamp(ref_timestamp, UTC)
                                        # If code was modified after doc was last updated, it's potentially stale
                                        if ref_date > doc_date:
                                            stale_refs.append(ref)
                                    except ValueError:
                                        pass

                        if stale_refs:
                            stale_summary = ", ".join(stale_refs[:3])
                            if len(stale_refs) > 3:
                                stale_summary += "..."
                            findings.append(
                                DocFinding(
                                    _relative_path(doc),
                                    1,
                                    "Medium",
                                    "stale",
                                    f"Documentation references {len(stale_refs)} files modified "
                                    f"since last doc update: {stale_summary}",
                                )
                            )
                except ValueError:
                    pass

    except Exception:
        # Don't fail the entire scan if stale detection fails
        return findings

    return findings


def run_scan() -> dict[str, Any]:
    """Run full doc-gardening scan. Returns findings + metadata."""
    findings = []
    findings.extend(scan_agents_md())
    findings.extend(scan_dead_links())
    findings.extend(scan_docs_structure())
    findings.extend(scan_markdown_encoding_artifacts())
    findings.extend(scan_ai_first_source_drift())
    findings.extend(scan_ai_first_status_drift())
    findings.extend(scan_completed_exec_plans_still_active())
    findings.extend(scan_stale_docs())

    severity_counts = Counter(finding.severity for finding in findings)
    category_counts = Counter(finding.category for finding in findings)

    return {
        "timestamp": datetime.now(UTC).isoformat() + "Z",
        "total_findings": len(findings),
        "by_severity": {severity: severity_counts.get(severity, 0) for severity in SEVERITY_ORDER},
        "by_category": {category: category_counts.get(category, 0) for category in CATEGORY_ORDER},
        "findings": [f._asdict() for f in findings],
    }


def update_quality_score(
    findings: Sequence[DocFinding],
    pipeline_snapshot: PipelineSnapshot | None = None,
) -> None:
    """Update docs/quality-score.md with latest scan results."""
    if not QUALITY_SCORE.exists():
        return

    content = _read_text(QUALITY_SCORE)
    date_str, grade, notes, source = _build_quality_trend_entry(
        findings,
        pipeline_snapshot=pipeline_snapshot,
    )
    row = f"| {date_str} | {grade} | {notes} | {source} |"
    updated = _upsert_trend_section(content, row=row)
    QUALITY_SCORE.write_text(updated, encoding="utf-8")


def update_tech_debt_scan_log(findings: Sequence[DocFinding]) -> None:
    """Update docs/exec-plans/tech-debt-tracker.md scan log."""
    from ._doc_gardener_fixup import update_tech_debt_scan_log as _update_tech_debt_scan_log

    _update_tech_debt_scan_log(
        findings,
        tech_debt_path=TECH_DEBT,
        read_text=_read_text,
        date_str=datetime.now(UTC).strftime("%Y-%m-%d"),
    )


def open_fixup_pr(findings: Sequence[DocFinding]) -> bool:
    """Open a fix-up PR with doc-gardening changes. Returns True if PR opened."""
    from ._doc_gardener_fixup import open_fixup_pr as _open_fixup_pr

    return _open_fixup_pr(findings, run_repo_cli=_run_repo_cli)


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run doc-gardening checks and optional tracking updates.")
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Report findings and fail on them without updating tracking files or opening a PR.",
    )
    parser.add_argument(
        "--open-fixup-pr",
        action="store_true",
        help="Attempt to open a fix-up PR when findings exist.",
    )
    parser.add_argument(
        "--pipeline-output-dir",
        type=Path,
        default=DEFAULT_PIPELINE_OUTPUT_DIR,
        help="Pipeline artifact directory to read for quality-score trend updates.",
    )
    return parser.parse_args(list(argv) if argv is not None else [])


def main(argv: Sequence[str] | None = None) -> int:
    """Run doc-gardening scan and return a process exit code."""
    args = _parse_args(argv)
    result = run_scan()
    findings = [DocFinding(**f) for f in result["findings"]]

    print(f"Doc-gardening scan complete: {result['total_findings']} findings")
    print(f"  By severity: {result['by_severity']}")
    print(f"  By category: {result['by_category']}")

    if findings:
        print("\nFindings:")
        for f in findings:
            print(f"  [{f.severity}] {f.file}:{f.line} - {f.message}")

    if args.check_only:
        print("\nCheck-only mode: tracking files not updated.")
    else:
        pipeline_snapshot, pipeline_message = load_pipeline_snapshot(args.pipeline_output_dir)
        if pipeline_message is not None:
            print(f"\nPipeline snapshot unavailable: {pipeline_message}")
        update_quality_score(findings, pipeline_snapshot)
        update_tech_debt_scan_log(findings)
        print("\nTracking files updated.")

    if findings:
        if args.open_fixup_pr and not args.check_only:
            print("\nAttempting to open fix-up PR...")
            open_fixup_pr(findings)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
