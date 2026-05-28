"""Doc-gardening agent: scans for stale docs, validates links, updates tracking files.

Runs on CI or manual trigger. Updates quality-score.md and tech-debt-tracker.md.
Opens fix-up PRs when issues found (optional).

Based on OpenAI harness engineering: "A recurring doc-gardening agent scans for
stale or obsolete documentation that does not reflect the real code behavior
and opens fix-up pull requests."
"""

import argparse
import shutil

# Internal doc-gardener intentionally invokes trusted git and gh CLIs.
import subprocess  # nosec B404
import sys
from collections.abc import Iterator, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, NamedTuple

from sattlint.devtools import coordination_lock_state

from . import _doc_gardener_scan as doc_gardener_scan_module
from . import _doc_gardener_updates as doc_gardener_updates_module

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
    return doc_gardener_scan_module.relative_path(path, repo_root=REPO_ROOT)


def _read_text(path: Path) -> str:
    raw = path.read_bytes()
    for encoding in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _load_json_mapping(path: Path) -> dict[str, Any]:
    return doc_gardener_updates_module.load_json_mapping(path, read_text_fn=_read_text)


def _load_pipeline_finding_count(output_dir: Path) -> int | None:
    return doc_gardener_updates_module.load_pipeline_finding_count(
        output_dir,
        load_json_mapping_fn=_load_json_mapping,
    )


def load_pipeline_snapshot(output_dir: Path) -> tuple[PipelineSnapshot | None, str | None]:
    return doc_gardener_updates_module.load_pipeline_snapshot(
        output_dir,
        pipeline_snapshot_cls=PipelineSnapshot,
        load_json_mapping_fn=_load_json_mapping,
        load_pipeline_finding_count_fn=_load_pipeline_finding_count,
    )


def _should_skip_path(path: Path) -> bool:
    return doc_gardener_scan_module.should_skip_path(path)


def _iter_markdown_files() -> Iterator[Path]:
    return doc_gardener_scan_module.iter_markdown_files(
        repo_root=REPO_ROOT,
        markdown_suffixes=MARKDOWN_SUFFIXES,
        should_skip_path_fn=_should_skip_path,
    )


def _parse_markdown_table(lines: list[str], section_heading: str) -> list[tuple[int, dict[str, str]]]:
    return doc_gardener_scan_module.parse_markdown_table(lines, section_heading)


def _normalize_workstream_id(label: str) -> str | None:
    return doc_gardener_scan_module.normalize_workstream_id(label)


def _normalize_status(status: str) -> str:
    return doc_gardener_scan_module.normalize_status(status)


def _load_active_workstream_statuses(repo_root: Path = REPO_ROOT) -> dict[str, str]:
    return doc_gardener_scan_module.load_active_workstream_statuses(
        repo_root,
        load_lock_state_fn=coordination_lock_state.load_lock_state,
        normalize_workstream_id_fn=_normalize_workstream_id,
        normalize_status_fn=_normalize_status,
    )


def _source_sync_digest(path: Path) -> str:
    return doc_gardener_scan_module.source_sync_digest(path, read_text_fn=_read_text)


def scan_agents_md() -> Sequence[DocFinding]:
    """Check AGENTS.md is under 100 lines and well-structured."""
    return doc_gardener_scan_module.scan_agents_md(
        doc_finding_cls=DocFinding,
        agents_md=AGENTS_MD,
        max_agents_lines=MAX_AGENTS_LINES,
        read_text_fn=_read_text,
    )


def scan_dead_links() -> Sequence[DocFinding]:
    """Check for dead links in markdown files under docs/."""
    return doc_gardener_scan_module.scan_dead_links(
        doc_finding_cls=DocFinding,
        docs_dir=DOCS_DIR,
        read_text_fn=_read_text,
        relative_path_fn=_relative_path,
    )


def scan_docs_structure() -> Sequence[DocFinding]:
    """Validate docs/ directory structure matches harness-engineering layout."""
    return doc_gardener_scan_module.scan_docs_structure(doc_finding_cls=DocFinding, docs_dir=DOCS_DIR)


def scan_markdown_encoding_artifacts() -> Sequence[DocFinding]:
    """Flag likely mojibake sequences in tracked markdown and text files."""
    return doc_gardener_scan_module.scan_markdown_encoding_artifacts(
        doc_finding_cls=DocFinding,
        iter_markdown_files_fn=_iter_markdown_files,
        read_text_fn=_read_text,
        mojibake_tokens=MOJIBAKE_TOKENS,
        relative_path_fn=_relative_path,
    )


def scan_ai_first_source_drift() -> Sequence[DocFinding]:
    """Validate the AI-first source ledger against the presence of legacy TODO files."""
    return doc_gardener_scan_module.scan_ai_first_source_drift(
        doc_finding_cls=DocFinding,
        ai_first_debt=AI_FIRST_DEBT,
        repo_root=REPO_ROOT,
        read_text_fn=_read_text,
        parse_markdown_table_fn=_parse_markdown_table,
        source_sync_digest_fn=_source_sync_digest,
        relative_path_fn=_relative_path,
    )


def scan_ai_first_status_drift() -> Sequence[DocFinding]:
    """Compare refactor-lane statuses in the canonical tech debt tracker against active workstreams."""
    return doc_gardener_scan_module.scan_ai_first_status_drift(
        doc_finding_cls=DocFinding,
        ai_first_debt=AI_FIRST_DEBT,
        repo_root=REPO_ROOT,
        read_text_fn=_read_text,
        parse_markdown_table_fn=_parse_markdown_table,
        load_active_workstream_statuses_fn=_load_active_workstream_statuses,
        normalize_workstream_id_fn=_normalize_workstream_id,
        normalize_status_fn=_normalize_status,
        relative_path_fn=_relative_path,
    )


def scan_completed_exec_plans_still_active() -> Sequence[DocFinding]:
    """Flag exec plans whose Progress section is complete but that still live in active/."""
    return doc_gardener_scan_module.scan_completed_exec_plans_still_active(
        doc_finding_cls=DocFinding,
        docs_dir=DOCS_DIR,
        relative_path_fn=_relative_path,
    )


def scan_stale_docs() -> Sequence[DocFinding]:
    """Check if docs are stale compared to code changes (git-based heuristic)."""
    return doc_gardener_scan_module.scan_stale_docs(
        doc_finding_cls=DocFinding,
        docs_dir=DOCS_DIR,
        read_text_fn=_read_text,
        relative_path_fn=_relative_path,
        run_repo_cli_fn=_run_repo_cli,
    )


def run_scan() -> dict[str, Any]:
    """Run full doc-gardening scan. Returns findings + metadata."""
    findings: list[DocFinding] = []
    findings.extend(scan_agents_md())
    findings.extend(scan_dead_links())
    findings.extend(scan_docs_structure())
    findings.extend(scan_markdown_encoding_artifacts())
    findings.extend(scan_ai_first_source_drift())
    findings.extend(scan_ai_first_status_drift())
    findings.extend(scan_completed_exec_plans_still_active())
    findings.extend(scan_stale_docs())
    return doc_gardener_scan_module.build_scan_result(
        findings,
        severity_order=SEVERITY_ORDER,
        category_order=CATEGORY_ORDER,
        timestamp=datetime.now(UTC).isoformat() + "Z",
    )


def update_quality_score(
    findings: Sequence[DocFinding],
    pipeline_snapshot: PipelineSnapshot | None = None,
) -> None:
    """Update docs/quality-score.md with latest scan results."""
    doc_gardener_updates_module.update_quality_score(
        findings,
        quality_score_path=QUALITY_SCORE,
        read_text_fn=_read_text,
        pipeline_snapshot=pipeline_snapshot,
        date_str=datetime.now(UTC).strftime("%Y-%m-%d"),
    )


def update_tech_debt_scan_log(findings: Sequence[DocFinding]) -> None:
    """Update docs/exec-plans/tech-debt-tracker.md scan log."""
    doc_gardener_updates_module.update_tech_debt_scan_log(
        findings,
        tech_debt_path=TECH_DEBT,
        read_text_fn=_read_text,
        date_str=datetime.now(UTC).strftime("%Y-%m-%d"),
    )


def open_fixup_pr(findings: Sequence[DocFinding]) -> bool:
    """Open a fix-up PR with doc-gardening changes. Returns True if PR opened."""
    return doc_gardener_updates_module.open_fixup_pr(findings, run_repo_cli_fn=_run_repo_cli)


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
        try:
            update_quality_score(findings, pipeline_snapshot)
            update_tech_debt_scan_log(findings)
        except OSError as exc:
            print(f"\nTracking file update error: {exc}")
            return 1
        print("\nTracking files updated.")

    if findings:
        if args.open_fixup_pr and not args.check_only:
            print("\nAttempting to open fix-up PR...")
            open_fixup_pr(findings)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
