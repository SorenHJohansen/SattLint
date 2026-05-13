from __future__ import annotations

from dataclasses import dataclass, field

from sattline_parser.models.ast_model import BasePicture

from .dataflow import analyze_dataflow
from .framework import Issue, format_report_header
from .scan_loop_resource_usage import analyze_scan_loop_resource_usage

_TIMING_SECTION_ORDER: tuple[str, ...] = (
    "dataflow.scan_cycle_stale_read",
    "dataflow.scan_cycle_implicit_new",
    "dataflow.scan_cycle_temporal_misuse",
    "scan_cycle.resource_usage",
)

_TIMING_SECTION_TITLES: dict[str, str] = {
    "dataflow.scan_cycle_stale_read": "Scan-cycle stale reads",
    "dataflow.scan_cycle_implicit_new": "Implicit same-scan dependencies",
    "dataflow.scan_cycle_temporal_misuse": "Temporal state misuse",
    "scan_cycle.resource_usage": "Scan-loop resource hazards",
}


def _empty_issues() -> list[Issue]:
    return []


@dataclass
class TimingReport:
    name: str
    issues: list[Issue] = field(default_factory=_empty_issues)

    def summary(self) -> str:
        if not self.issues:
            lines = format_report_header("Timing", self.name, status="ok")
            lines.append("No timing hazards found.")
            return "\n".join(lines)

        lines = format_report_header("Timing", self.name, status="issues")
        lines.append(f"Issues: {len(self.issues)}")
        lines.append("Sections:")
        for kind in _TIMING_SECTION_ORDER:
            count = sum(1 for issue in self.issues if issue.kind == kind)
            if count:
                lines.append(f"  - {_TIMING_SECTION_TITLES[kind]}: {count}")

        for kind in _TIMING_SECTION_ORDER:
            kind_issues = [issue for issue in self.issues if issue.kind == kind]
            if not kind_issues:
                continue
            lines.append("")
            lines.append(f"{_TIMING_SECTION_TITLES[kind]}:")
            for issue in kind_issues:
                location = ".".join(issue.module_path or [self.name])
                lines.append(f"  - [{location}] {issue.message}")

        return "\n".join(lines)


def analyze_timing(
    base_picture: BasePicture,
    unavailable_libraries: set[str] | None = None,
    analyzed_target_is_library: bool = False,
) -> TimingReport:
    dataflow_report = analyze_dataflow(
        base_picture,
        unavailable_libraries=unavailable_libraries,
        analyzed_target_is_library=analyzed_target_is_library,
    )
    scan_loop_report = analyze_scan_loop_resource_usage(base_picture)
    return TimingReport(
        name=base_picture.header.name,
        issues=[
            *[issue for issue in dataflow_report.issues if issue.kind in set(_TIMING_SECTION_ORDER[:-1])],
            *[issue for issue in scan_loop_report.issues if issue.kind == "scan_cycle.resource_usage"],
        ],
    )
