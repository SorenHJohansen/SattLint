from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sattline_parser.models.ast_model import BasePicture

from .dataflow import collect_state_inference
from .framework import Issue


@dataclass
class StateInferenceReport:
    name: str
    issues: list[Issue] = field(default_factory=list)
    summary_data: dict[str, Any] = field(default_factory=dict)

    def summary(self) -> str:
        lines = ["Report: State inference", f"Target: {self.name}"]
        lines.append("Status: issues" if self.issues else "Status: ok")
        lines.append(
            "Summary: "
            f"{self.summary_data.get('summary', {}).get('boolean_state_count', 0)} boolean states, "
            f"{self.summary_data.get('summary', {}).get('numeric_range_count', 0)} numeric ranges"
        )
        if not self.issues:
            lines.append("No issues found.")
            return "\n".join(lines)

        lines.append("")
        lines.append("Findings:")
        for issue in self.issues:
            location = ".".join(issue.module_path or [self.name])
            lines.append(f"  - [{location}] {issue.message}")
        return "\n".join(lines)


def analyze_state_inference(
    base_picture: BasePicture,
    *,
    unavailable_libraries: set[str] | None = None,
) -> StateInferenceReport:
    issues, summary_data = collect_state_inference(
        base_picture,
        unavailable_libraries=unavailable_libraries,
    )
    return StateInferenceReport(
        name=base_picture.header.name,
        issues=issues,
        summary_data=summary_data,
    )
