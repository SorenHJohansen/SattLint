"""Markdown rendering and CLI helpers for source diff reporting."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

DEFAULT_JSON_OUTPUT_FILENAME = "source_diff_report.json"
DEFAULT_MARKDOWN_OUTPUT_FILENAME = "source_diff_report.md"


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# SattLint .s/.x Diff Report",
        "",
        f"Status: {report['status']}",
        f"Compared pairs: {report['summary']['compared_pair_count']}",
        f"Changed pairs: {report['summary']['changed_pair_count']}",
        f"Identical pairs: {report['summary']['identical_pair_count']}",
        f"Layout-only pairs: {report['summary']['layout_only_pair_count']}",
        f"Structural pairs: {report['summary']['structural_pair_count']}",
        f"Errors: {report['summary']['error_count']}",
    ]

    if report["selection_errors"]:
        lines.extend(["", "## Selection Errors", ""])
        for error in report["selection_errors"]:
            lines.append(f"- {error['message']}")

    for pair in report["pairs"]:
        lines.extend(
            [
                "",
                f"## {pair['pair_name']}",
                "",
                f"Draft file: {pair['draft_file']}",
                f"Official file: {pair['official_file']}",
                f"Status: {pair['status']}",
                f"Classification: {pair['classification']}",
                f"Changed lines: {pair['summary']['changed_line_count']}",
                "",
            ]
        )
        if pair["errors"]:
            lines.append("Errors:")
            for error in pair["errors"]:
                phase = error.get("phase")
                prefix = error["side"] if not phase else f"{error['side']} {phase}"
                lines.append(f"- {prefix}: {error['error_type']}: {error['error']}")
            lines.append("")
        if pair["sections"]:
            for section in pair["sections"]:
                lines.append(f"### {section['title']}")
                for item in section["items"]:
                    lines.append(f"- {item}")
                for entry in section.get("entries", []):
                    lines.append("")
                    lines.append(f"#### {entry['name']}")
                    module_kind = entry.get("module_kind")
                    if module_kind is not None:
                        lines.append(f"- Kind: {module_kind}")
                    lines.append(f"- Change: {entry['change_kind']}")
                    for detail in entry.get("details", []):
                        lines.append(f"- {detail}")
                    for code_diff in entry.get("code_diffs", []):
                        lines.append("")
                        lines.append(f"##### {code_diff['label']}")
                        lines.append("```diff")
                        lines.extend(code_diff["diff_lines"])
                        lines.append("```")
                lines.append("")
        else:
            lines.append("No AST comparison sections available.")
    return "\n".join(lines) + "\n"


def write_report_artifacts(output_dir: Path, report: dict[str, Any]) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / DEFAULT_JSON_OUTPUT_FILENAME
    markdown_path = output_dir / DEFAULT_MARKDOWN_OUTPUT_FILENAME
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    markdown_path.write_text(render_markdown(report), encoding="utf-8")
    return json_path, markdown_path


def build_cli_parser(
    *,
    default_workspace_root: str,
    prog: str = "sattlint-source-diff-report",
    add_help: bool = True,
) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=prog,
        add_help=add_help,
        description="Build a review-friendly diff report between draft .s and official .x source pairs.",
    )
    parser.add_argument(
        "--workspace-root", default=default_workspace_root, help="Workspace root used for relative paths."
    )
    parser.add_argument("--draft-file", default=None, help="Draft .s file to compare.")
    parser.add_argument("--official-file", default=None, help="Official .x file to compare.")
    parser.add_argument(
        "--discover-pairs",
        action="store_true",
        help="Discover same-basename .s/.x pairs under the workspace root.",
    )
    parser.add_argument("--format", choices=("json", "markdown"), default="json", help="Stdout format.")
    parser.add_argument(
        "--output-dir", default=None, help="Optional directory that receives JSON and Markdown reports."
    )
    parser.add_argument("--no-progress", action="store_true", help="Suppress progress messages on stderr.")
    return parser


def parse_args(argv: Sequence[str] | None, *, default_workspace_root: str) -> argparse.Namespace:
    parser = build_cli_parser(default_workspace_root=default_workspace_root)
    return parser.parse_args(list(argv) if argv is not None else None)


def run_cli(
    argv: Sequence[str] | None,
    *,
    default_workspace_root: Path,
    emit_progress_fn: Callable[[str], None],
    build_source_diff_report_fn: Callable[..., dict[str, Any]],
    write_report_artifacts_fn: Callable[[Path, dict[str, Any]], tuple[Path, Path]],
    render_json_output_fn: Callable[[dict[str, Any]], str],
    render_markdown_fn: Callable[[dict[str, Any]], str],
) -> int:
    args = parse_args(argv, default_workspace_root=str(default_workspace_root))
    progress_callback = None if args.no_progress else emit_progress_fn
    report = build_source_diff_report_fn(
        Path(args.workspace_root).resolve(),
        draft_file=None if args.draft_file is None else str(args.draft_file),
        official_file=None if args.official_file is None else str(args.official_file),
        discover_pairs=bool(args.discover_pairs),
        progress_callback=progress_callback,
    )
    output_error: OSError | None = None
    if args.output_dir:
        try:
            write_report_artifacts_fn(Path(args.output_dir).resolve(), report)
        except OSError as exc:
            output_error = exc

    if args.format == "markdown":
        print(render_markdown_fn(report))
    else:
        print(render_json_output_fn(report))

    if output_error is not None:
        print(f"source diff output error: {output_error}", file=sys.stderr, flush=True)
        return 1
    return 0 if report["status"] in {"ok", "partial"} else 2
