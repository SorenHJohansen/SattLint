from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def update_tech_debt_scan_log(
    findings: Sequence[Any],
    *,
    tech_debt_path: Path,
    read_text: Callable[[Path], str],
    date_str: str,
) -> None:
    if not tech_debt_path.exists():
        return

    content = read_text(tech_debt_path)
    finding_summary = f"{len(findings)} findings"
    new_log = f"| {date_str} | {finding_summary} | Doc-gardening scan |"

    if "## Scan Log" not in content:
        return

    parts = content.split("## Scan Log")
    if "|---" not in parts[1]:
        return

    lines = parts[1].split("\n")
    for index, line in enumerate(lines):
        if "|---" in line and index + 1 < len(lines):
            lines.insert(index + 1, new_log)
            break
    parts[1] = "\n".join(lines)
    tech_debt_path.write_text(parts[0] + "## Scan Log" + parts[1], encoding="utf-8")


def open_fixup_pr(
    findings: Sequence[Any],
    *,
    run_repo_cli: Callable[[str, Sequence[str]], Any],
) -> bool:
    if not findings:
        return False

    try:
        result = run_repo_cli("gh", ["--version"])
        if result.returncode != 0:
            print("  gh CLI not available, skipping PR creation")
            return False
    except Exception:
        print("  gh CLI not available, skipping PR creation")
        return False

    branch = f"doc-gardener-fixup-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}"
    run_repo_cli("git", ["checkout", "-b", branch])
    run_repo_cli("git", ["add", "docs/", "AGENTS.md"])

    commit_msg = f"docs: doc-gardener fixup ({len(findings)} findings)\n\n"
    for finding in findings[:5]:
        commit_msg += f"- [{finding.severity}] {finding.file}: {finding.message}\n"
    if len(findings) > 5:
        commit_msg += f"- ... and {len(findings) - 5} more\n"

    result = run_repo_cli("git", ["commit", "-m", commit_msg])
    if result.returncode != 0:
        print(f"  No changes to commit: {result.stderr}")
        run_repo_cli("git", ["checkout", "main"])
        run_repo_cli("git", ["branch", "-D", branch])
        return False

    run_repo_cli("git", ["push", "-u", "origin", branch])

    pr_body = f"""## Doc-Gardening Fix-Up PR

Automated PR from doc-gardening scan.

### Findings ({len(findings)} total)

| File | Line | Severity | Category | Message |
|------|------|----------|----------|---------|
"""
    for finding in findings[:10]:
        pr_body += (
            f"| {finding.file} | {finding.line} | {finding.severity} | {finding.category} | {finding.message} |\n"
        )
    if len(findings) > 10:
        pr_body += f"\n... and {len(findings) - 10} more findings.\n"

    result = run_repo_cli(
        "gh",
        [
            "pr",
            "create",
            "--title",
            f"docs: doc-gardener fixup ({len(findings)} findings)",
            "--body",
            pr_body,
            "--label",
            "automated,documentation",
        ],
    )

    if result.returncode == 0:
        print(f"  Created PR: {result.stdout.strip()}")
        run_repo_cli("git", ["checkout", "main"])
        return True

    print(f"  Failed to create PR: {result.stderr}")
    run_repo_cli("git", ["checkout", "main"])
    return False
