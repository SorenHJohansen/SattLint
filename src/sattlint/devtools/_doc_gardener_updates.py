from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any


def load_json_mapping(path: Path, *, read_text_fn: Callable[[Path], str]) -> dict[str, Any]:
    payload = json.loads(read_text_fn(path))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object in {path.as_posix()}")
    return payload


def load_pipeline_finding_count(
    output_dir: Path,
    *,
    load_json_mapping_fn: Callable[[Path], dict[str, Any]],
) -> int | None:
    findings_path = output_dir / "findings.json"
    if not findings_path.exists():
        return None
    try:
        findings_payload = load_json_mapping_fn(findings_path)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError):
        return None
    finding_count = findings_payload.get("finding_count")
    return finding_count if isinstance(finding_count, int) else None


def load_pipeline_snapshot(
    output_dir: Path,
    *,
    pipeline_snapshot_cls: type[Any],
    load_json_mapping_fn: Callable[[Path], dict[str, Any]],
    load_pipeline_finding_count_fn: Callable[[Path], int | None],
) -> tuple[Any | None, str | None]:
    summary_path = output_dir / "summary.json"
    status_path = output_dir / "status.json"
    missing_paths = [path.name for path in (summary_path, status_path) if not path.exists()]
    if missing_paths:
        missing = ", ".join(sorted(missing_paths))
        return None, f"missing pipeline artifacts: {missing}"

    try:
        summary_payload = load_json_mapping_fn(summary_path)
        status_payload = load_json_mapping_fn(status_path)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        return None, f"unable to read pipeline artifacts from {output_dir.as_posix()}: {exc}"

    overall_status = status_payload.get("overall_status")
    if not isinstance(overall_status, str) or not overall_status:
        return None, f"invalid pipeline status in {status_path.as_posix()}"

    counts = summary_payload.get("counts")
    normalized_findings = counts.get("normalized_findings") if isinstance(counts, dict) else None
    if not isinstance(normalized_findings, int):
        normalized_findings = load_pipeline_finding_count_fn(output_dir)

    reports = summary_payload.get("reports")
    coverage_total_line_rate: float | None = None
    coverage_report = reports.get("coverage_summary") if isinstance(reports, dict) else None
    if isinstance(coverage_report, str) and coverage_report:
        coverage_path = output_dir / coverage_report
        if coverage_path.exists():
            try:
                coverage_payload = load_json_mapping_fn(coverage_path)
            except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError):
                coverage_payload = {}
            coverage_summary = coverage_payload.get("summary")
            total_line_rate = coverage_summary.get("total_line_rate") if isinstance(coverage_summary, dict) else None
            if isinstance(total_line_rate, int | float):
                coverage_total_line_rate = float(total_line_rate)

    profile = summary_payload.get("profile")
    return (
        pipeline_snapshot_cls(
            output_dir=output_dir,
            profile=profile if isinstance(profile, str) and profile else None,
            overall_status=overall_status,
            normalized_findings=normalized_findings,
            coverage_total_line_rate=coverage_total_line_rate,
        ),
        None,
    )


def format_coverage_percent(line_rate: float | None) -> str:
    if line_rate is None:
        return "coverage n/a"
    return f"{line_rate * 100:.1f}% coverage"


def grade_from_pipeline_snapshot(snapshot: Any) -> str:
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


def build_quality_trend_entry(
    findings: Sequence[Any],
    *,
    pipeline_snapshot: Any | None,
    date_str: str,
) -> tuple[str, str, str, str]:
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
            format_coverage_percent(pipeline_snapshot.coverage_total_line_rate),
        )
    )
    return date_str, grade_from_pipeline_snapshot(pipeline_snapshot), notes, "Pipeline"


def upsert_trend_section(content: str, *, row: str) -> str:
    import re

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


def update_quality_score(
    findings: Sequence[Any],
    *,
    quality_score_path: Path,
    read_text_fn: Callable[[Path], str],
    pipeline_snapshot: Any | None,
    date_str: str,
) -> None:
    if not quality_score_path.exists():
        return

    content = read_text_fn(quality_score_path)
    date_str, grade, notes, source = build_quality_trend_entry(
        findings,
        pipeline_snapshot=pipeline_snapshot,
        date_str=date_str,
    )
    row = f"| {date_str} | {grade} | {notes} | {source} |"
    updated = upsert_trend_section(content, row=row)
    quality_score_path.write_text(updated, encoding="utf-8")


def update_tech_debt_scan_log(
    findings: Sequence[Any],
    *,
    tech_debt_path: Path,
    read_text_fn: Callable[[Path], str],
    date_str: str,
) -> None:
    from ._doc_gardener_fixup import update_tech_debt_scan_log as _update_tech_debt_scan_log

    _update_tech_debt_scan_log(
        findings,
        tech_debt_path=tech_debt_path,
        read_text=read_text_fn,
        date_str=date_str,
    )


def open_fixup_pr(
    findings: Sequence[Any],
    *,
    run_repo_cli_fn: Callable[[str, Sequence[str]], Any],
) -> bool:
    from ._doc_gardener_fixup import open_fixup_pr as _open_fixup_pr

    return _open_fixup_pr(findings, run_repo_cli=run_repo_cli_fn)
