"""Doc-gardening agent: scans for stale docs, validates links, updates tracking files.

Runs on CI or manual trigger. Updates quality-score.md and tech-debt-tracker.md.
Opens fix-up PRs when issues found (optional).

Based on OpenAI harness engineering: "A recurring doc-gardening agent scans for
stale or obsolete documentation that does not reflect the real code behavior
and opens fix-up pull requests."
"""

import hashlib
import re
import subprocess
from collections import Counter
from collections.abc import Iterator, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, NamedTuple

# Constants
REPO_ROOT = Path(__file__).resolve().parents[3]
DOCS_DIR = REPO_ROOT / "docs"
AGENTS_MD = REPO_ROOT / "AGENTS.md"
QUALITY_SCORE = DOCS_DIR / "quality-score.md"
TECH_DEBT = DOCS_DIR / "exec-plans" / "tech-debt-tracker.md"
CURRENT_WORK = REPO_ROOT / ".github" / "coordination" / "current-work.md"
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
    "â†’",
    "â€”",
    "â€“",
    "â€˜",
    "â€™",
    "â€œ",
    "â€�",
    "Â ",
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


class DocFinding(NamedTuple):
    """A finding from doc-gardening scan."""

    file: str
    line: int
    severity: str  # "Critical", "High", "Medium", "Low"
    category: str  # "stale", "dead_link", "too_long", "missing", "structure"
    message: str


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


def _parse_current_work_statuses(text: str) -> dict[str, str]:
    statuses: dict[str, str] = {}
    current_workstream_id: str | None = None

    for line in text.splitlines():
        if line.startswith("### Workstream "):
            current_workstream_id = _normalize_workstream_id(line.removeprefix("### Workstream ").strip())
            continue
        if current_workstream_id is None or not line.startswith("- Status:"):
            continue
        statuses[current_workstream_id] = _normalize_status(line.partition(":")[2].strip())
        current_workstream_id = None

    return statuses


def _source_sync_digest(path: Path) -> str:
    content = _read_text(path).replace("\r\n", "\n").strip()
    return hashlib.sha1(content.encode("utf-8")).hexdigest()[:12]


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
        except Exception:
            pass

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
    """Compare refactor-lane statuses in the canonical tech debt tracker against current-work."""
    findings = []
    if not AI_FIRST_DEBT.exists() or not CURRENT_WORK.exists():
        return findings

    current_statuses = _parse_current_work_statuses(_read_text(CURRENT_WORK))
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
                f"{debt_id} status is '{row.get('Status', '')}' but current-work tracks '{current_status}'.",
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
        result = subprocess.run(
            ["git", "log", "-1", "--format=%H", "--", "src/"],
            capture_output=True,
            text=True,
            cwd=DOCS_DIR.parent,
        )
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
            doc_result = subprocess.run(
                ["git", "log", "-1", "--format=%ct", "--", str(rel_path)],
                capture_output=True,
                text=True,
                cwd=DOCS_DIR.parent,
            )
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
                                ref_result = subprocess.run(
                                    ["git", "log", "-1", "--format=%ct", "--", str(ref)],
                                    capture_output=True,
                                    text=True,
                                    cwd=DOCS_DIR.parent,
                                )
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
        pass

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


def update_quality_score(findings: Sequence[DocFinding]) -> None:
    """Update docs/quality-score.md with latest scan results."""
    if not QUALITY_SCORE.exists():
        return

    # Simple update: append scan log entry
    content = _read_text(QUALITY_SCORE)

    # Add trend entry
    date_str = datetime.now(UTC).strftime("%Y-%m-%d")
    total = len(findings)

    if "## Trend" in content:
        parts = content.split("## Trend")
        parts[1] = parts[1].replace("|---", f"| {date_str} | B | {total} findings | Scan |\n|---")
        QUALITY_SCORE.write_text(parts[0] + "## Trend" + parts[1], encoding="utf-8")


def update_tech_debt_scan_log(findings: Sequence[DocFinding]) -> None:
    """Update docs/exec-plans/tech-debt-tracker.md scan log."""
    if not TECH_DEBT.exists():
        return

    content = _read_text(TECH_DEBT)

    date_str = datetime.now(UTC).strftime("%Y-%m-%d")
    finding_summary = f"{len(findings)} findings"
    new_log = f"| {date_str} | {finding_summary} | Doc-gardening scan |"

    if "## Scan Log" in content:
        parts = content.split("## Scan Log")
        if "|---" in parts[1]:
            lines = parts[1].split("\n")
            # Insert after header row
            for i, line in enumerate(lines):
                if "|---" in line and i + 1 < len(lines):
                    lines.insert(i + 1, new_log)
                    break
            parts[1] = "\n".join(lines)
            TECH_DEBT.write_text(parts[0] + "## Scan Log" + parts[1], encoding="utf-8")


def open_fixup_pr(findings: Sequence[DocFinding]) -> bool:
    """Open a fix-up PR with doc-gardening changes. Returns True if PR opened."""
    if not findings:
        return False

    # Check if gh CLI is available
    try:
        result = subprocess.run(
            ["gh", "--version"],
            capture_output=True,
            text=True,
            cwd=DOCS_DIR.parent,
        )
        if result.returncode != 0:
            print("  gh CLI not available, skipping PR creation")
            return False
    except Exception:
        print("  gh CLI not available, skipping PR creation")
        return False

    branch = f"doc-gardener-fixup-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}"

    # Create branch and commit changes
    subprocess.run(["git", "checkout", "-b", branch], capture_output=True, cwd=DOCS_DIR.parent)
    subprocess.run(["git", "add", "docs/", "AGENTS.md"], capture_output=True, cwd=DOCS_DIR.parent)

    commit_msg = f"docs: doc-gardener fixup ({len(findings)} findings)\n\n"
    for f in findings[:5]:
        commit_msg += f"- [{f.severity}] {f.file}: {f.message}\n"
    if len(findings) > 5:
        commit_msg += f"- ... and {len(findings) - 5} more\n"

    result = subprocess.run(
        ["git", "commit", "-m", commit_msg],
        capture_output=True,
        text=True,
        cwd=DOCS_DIR.parent,
    )

    if result.returncode != 0:
        print(f"  No changes to commit: {result.stderr}")
        subprocess.run(["git", "checkout", "main"], capture_output=True, cwd=DOCS_DIR.parent)
        subprocess.run(["git", "branch", "-D", branch], capture_output=True, cwd=DOCS_DIR.parent)
        return False

    # Push and create PR
    subprocess.run(["git", "push", "-u", "origin", branch], capture_output=True, cwd=DOCS_DIR.parent)

    pr_body = f"""## Doc-Gardening Fix-Up PR

Automated PR from doc-gardening scan.

### Findings ({len(findings)} total)

| File | Line | Severity | Category | Message |
|------|------|----------|----------|---------|
"""
    for f in findings[:10]:
        pr_body += f"| {f.file} | {f.line} | {f.severity} | {f.category} | {f.message} |\n"
    if len(findings) > 10:
        pr_body += f"\n... and {len(findings) - 10} more findings.\n"

    result = subprocess.run(
        [
            "gh",
            "pr",
            "create",
            "--title",
            f"docs: doc-gardener fixup ({len(findings)} findings)",
            "--body",
            pr_body,
            "--label",
            "automated,documentation",
        ],
        capture_output=True,
        text=True,
        cwd=DOCS_DIR.parent,
    )

    if result.returncode == 0:
        print(f"  Created PR: {result.stdout.strip()}")
        # Go back to main
        subprocess.run(["git", "checkout", "main"], capture_output=True, cwd=DOCS_DIR.parent)
        return True
    else:
        print(f"  Failed to create PR: {result.stderr}")
        subprocess.run(["git", "checkout", "main"], capture_output=True, cwd=DOCS_DIR.parent)
        return False


def main() -> None:
    """Run doc-gardening scan and update tracking files."""
    result = run_scan()
    findings = [DocFinding(**f) for f in result["findings"]]

    print(f"Doc-gardening scan complete: {result['total_findings']} findings")
    print(f"  By severity: {result['by_severity']}")
    print(f"  By category: {result['by_category']}")

    if findings:
        print("\nFindings:")
        for f in findings:
            print(f"  [{f.severity}] {f.file}:{f.line} - {f.message}")

    update_quality_score(findings)
    update_tech_debt_scan_log(findings)
    print("\nTracking files updated.")

    # Open fix-up PR if there are findings
    if findings:
        print("\nAttempting to open fix-up PR...")
        open_fixup_pr(findings)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
