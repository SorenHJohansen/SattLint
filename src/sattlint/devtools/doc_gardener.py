"""Doc-gardening agent: scans for stale docs, validates links, updates tracking files.

Runs on CI or manual trigger. Updates quality-score.md and tech-debt-tracker.md.
Opens fix-up PRs when issues found (optional).

Based on OpenAI harness engineering: "A recurring doc-gardening agent scans for
stale or obsolete documentation that does not reflect the real code behavior
and opens fix-up pull requests."
"""

import os
import re
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, NamedTuple

# Constants
DOCS_DIR = Path(__file__).parent.parent.parent.parent / "docs"
AGENTS_MD = Path(__file__).parent.parent.parent.parent / "AGENTS.md"
QUALITY_SCORE = DOCS_DIR / "quality-score.md"
TECH_DEBT = DOCS_DIR / "exec-plans" / "tech-debt-tracker.md"
MAX_AGENTS_LINES = 100


class DocFinding(NamedTuple):
    """A finding from doc-gardening scan."""

    file: str
    line: int
    severity: str  # "Critical", "High", "Medium", "Low"
    category: str  # "stale", "dead_link", "too_long", "missing", "structure"
    message: str


def scan_agents_md() -> List[DocFinding]:
    """Check AGENTS.md is under 100 lines and well-structured."""
    findings = []
    if not AGENTS_MD.exists():
        findings.append(
            DocFinding("AGENTS.md", 0, "Critical", "missing", "AGENTS.md not found")
        )
        return findings

    with open(AGENTS_MD) as f:
        lines = f.readlines()
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
            findings.append(
                DocFinding(
                    "AGENTS.md", 0, "Medium", "structure", f"Missing section: {section}"
                )
            )

    return findings


def scan_dead_links() -> List[DocFinding]:
    """Check for dead links in markdown files under docs/."""
    findings = []
    if not DOCS_DIR.exists():
        return findings

    md_files = list(DOCS_DIR.rglob("*.md")) + list(DOCS_DIR.rglob("*.txt"))
    link_pattern = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")

    for md_file in md_files:
        try:
            with open(md_file) as f:
                lines = f.readlines()
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
                                str(md_file.relative_to(DOCS_DIR.parent)),
                                line_num,
                                "Medium",
                                "dead_link",
                                f"Broken link: {link}",
                            )
                        )
        except Exception:
            pass

    return findings


def scan_docs_structure() -> List[DocFinding]:
    """Validate docs/ directory structure matches harness-engineering layout."""
    findings = []
    required_dirs = ["design-docs", "exec-plans", "references"]
    required_files = [
        "quality-score.md",
        "design-docs/core-beliefs.md",
        "design-docs/index.md",
        "exec-plans/tech-debt-tracker.md",
    ]

    for d in required_dirs:
        if not (DOCS_DIR / d).exists():
            findings.append(
                DocFinding(
                    "docs/", 0, "High", "structure", f"Missing directory: docs/{d}"
                )
            )

    for f in required_files:
        if not (DOCS_DIR / f).exists():
            findings.append(
                DocFinding(
                    "docs/", 0, "High", "missing", f"Missing file: docs/{f}"
                )
            )

    return findings


def scan_stale_docs() -> List[DocFinding]:
    """Check if docs are stale compared to code changes (git-based heuristic)."""
    findings = []
    try:
        # Get timestamp for 30 days ago
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        
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
                    doc_date = datetime.utcfromtimestamp(doc_timestamp)
                    
                    # Only check docs older than 30 days
                    if doc_date < thirty_days_ago:
                        # Check if doc references code that has changed since doc was last updated
                        with open(doc, encoding='utf-8') as f:
                            content = f.read()
                        
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
                                        ref_date = datetime.utcfromtimestamp(ref_timestamp)
                                        # If code was modified after doc was last updated, it's potentially stale
                                        if ref_date > doc_date:
                                            stale_refs.append(ref)
                                    except ValueError:
                                        pass
                        
                        if stale_refs:
                            findings.append(
                                DocFinding(
                                    str(doc.relative_to(DOCS_DIR.parent)),
                                    1,
                                    "Medium",
                                    "stale",
                                    f"Documentation references {len(stale_refs)} files modified since last doc update: {', '.join(stale_refs[:3])}{'...' if len(stale_refs) > 3 else ''}",
                                )
                            )
                except ValueError:
                    pass

    except Exception as e:
        # Don't fail the entire scan if stale detection fails
        pass

    return findings


def run_scan() -> Dict[str, any]:
    """Run full doc-gardening scan. Returns findings + metadata."""
    findings = []
    findings.extend(scan_agents_md())
    findings.extend(scan_dead_links())
    findings.extend(scan_docs_structure())
    findings.extend(scan_stale_docs())

    return {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "total_findings": len(findings),
        "by_severity": {
            "Critical": len([f for f in findings if f.severity == "Critical"]),
            "High": len([f for f in findings if f.severity == "High"]),
            "Medium": len([f for f in findings if f.severity == "Medium"]),
            "Low": len([f for f in findings if f.severity == "Low"]),
        },
        "by_category": {
            "stale": len([f for f in findings if f.category == "stale"]),
            "dead_link": len([f for f in findings if f.category == "dead_link"]),
            "too_long": len([f for f in findings if f.category == "too_long"]),
            "missing": len([f for f in findings if f.category == "missing"]),
            "structure": len([f for f in findings if f.category == "structure"]),
        },
        "findings": [f._asdict() for f in findings],
    }


def update_quality_score(findings: List[DocFinding]) -> None:
    """Update docs/quality-score.md with latest scan results."""
    if not QUALITY_SCORE.exists():
        return

    # Simple update: append scan log entry
    with open(QUALITY_SCORE) as f:
        content = f.read()

    # Add trend entry
    date_str = datetime.utcnow().strftime("%Y-%m-%d")
    total = len(findings)
    new_entry = f"| {date_str} | B | Scan: {total} findings | Auto-update |"

    if "## Trend" in content:
        parts = content.split("## Trend")
        parts[1] = parts[1].replace(
            "|---", f"| {date_str} | B | {total} findings | Scan |\n|---"
        )
        with open(QUALITY_SCORE, "w") as f:
            f.write(parts[0] + "## Trend" + parts[1])


def update_tech_debt_scan_log(findings: List[DocFinding]) -> None:
    """Update docs/exec-plans/tech-debt-tracker.md scan log."""
    if not TECH_DEBT.exists():
        return

    with open(TECH_DEBT) as f:
        content = f.read()

    date_str = datetime.utcnow().strftime("%Y-%m-%d")
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
            with open(TECH_DEBT, "w") as f:
                f.write(parts[0] + "## Scan Log" + parts[1])


def open_fixup_pr(findings: List[DocFinding]) -> bool:
    """Open a fix-up PR with doc-gardening changes. Returns True if PR opened."""
    if not findings:
        return False
    
    # Check if gh CLI is available
    try:
        result = subprocess.run(
            ["gh", "--version"],
            capture_output=True, text=True, cwd=DOCS_DIR.parent,
        )
        if result.returncode != 0:
            print("  gh CLI not available, skipping PR creation")
            return False
    except Exception:
        print("  gh CLI not available, skipping PR creation")
        return False
    
    branch = f"doc-gardener-fixup-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"
    
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
        capture_output=True, text=True, cwd=DOCS_DIR.parent,
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
        ["gh", "pr", "create", "--title", f"docs: doc-gardener fixup ({len(findings)} findings)", 
         "--body", pr_body, "--label", "automated,documentation"],
        capture_output=True, text=True, cwd=DOCS_DIR.parent,
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


if __name__ == "__main__":
    main()
