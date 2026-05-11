from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sattline_parser.models.ast_model import BasePicture

from ._dataflow_common import _OLD_PREFIX, _is_scalar_value
from .dataflow import DataflowAnalyzer
from .framework import Issue


def _build_state_inference_summary(analyzer: DataflowAnalyzer) -> dict[str, Any]:
    boolean_states: list[dict[str, Any]] = []
    numeric_ranges: list[dict[str, Any]] = []
    string_states: list[dict[str, Any]] = []

    current_scalars = {
        key: value
        for key, value in analyzer._final_root_state.items()
        if not analyzer._is_pending_state_key(key)
        and key[: len(_OLD_PREFIX)] != _OLD_PREFIX
        and _is_scalar_value(value)
    }
    for key, value in sorted(current_scalars.items()):
        path = ".".join(key)
        if isinstance(value, bool):
            boolean_states.append({"symbol": path, "value": value})
        elif isinstance(value, int | float) and not isinstance(value, bool):
            numeric_ranges.append({"symbol": path, "minimum": value, "maximum": value})
        elif isinstance(value, str):
            string_states.append({"symbol": path, "value": value})

    return {
        "kind": "sattlint.state_inference_summary",
        "schema_version": 1,
        "summary": {
            "boolean_state_count": len(boolean_states),
            "numeric_range_count": len(numeric_ranges),
            "string_state_count": len(string_states),
        },
        "boolean_states": boolean_states,
        "numeric_ranges": numeric_ranges,
        "string_states": string_states,
    }


def _as_state_inference_issue(issue: Issue) -> Issue | None:
    if issue.kind == "dataflow.condition_always_true":
        issue_kind = "state_inference.condition_always_true"
    elif issue.kind == "dataflow.condition_always_false":
        issue_kind = "state_inference.condition_always_false"
    elif issue.kind == "dataflow.unreachable_branch":
        issue_kind = "state_inference.unreachable_branch"
    else:
        return None

    return Issue(
        kind=issue_kind,
        message=issue.message,
        module_path=issue.module_path,
        data=issue.data,
        rule_id=issue.rule_id,
        severity=issue.severity,
        confidence=issue.confidence,
        explanation=issue.explanation,
        suggestion=issue.suggestion,
    )


def collect_state_inference(
    base_picture: BasePicture,
    *,
    unavailable_libraries: set[str] | None = None,
    analyzed_target_is_library: bool = False,
) -> tuple[list[Issue], dict[str, Any]]:
    analyzer = DataflowAnalyzer(
        base_picture,
        unavailable_libraries=unavailable_libraries,
        analyzed_target_is_library=analyzed_target_is_library,
    )
    analyzer.run()

    inference_issues: list[Issue] = []
    for issue in analyzer.issues:
        mapped_issue = _as_state_inference_issue(issue)
        if mapped_issue is not None:
            inference_issues.append(mapped_issue)

    return inference_issues, _build_state_inference_summary(analyzer)


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
    analyzed_target_is_library: bool = False,
) -> StateInferenceReport:
    issues, summary_data = collect_state_inference(
        base_picture,
        unavailable_libraries=unavailable_libraries,
        analyzed_target_is_library=analyzed_target_is_library,
    )
    return StateInferenceReport(
        name=base_picture.header.name,
        issues=issues,
        summary_data=summary_data,
    )
