from __future__ import annotations

from dataclasses import dataclass, field

from sattline_parser.models.ast_model import BasePicture

from ..reporting.variables_report import IssueKind, VariableIssue
from .framework import empty_issues, format_report_header
from .variables import analyze_variables

INTERFACE_CONTRACT_ISSUE_KINDS: frozenset[IssueKind] = frozenset(
    {
        IssueKind.UNKNOWN_PARAMETER_TARGET,
        IssueKind.REQUIRED_PARAMETER_CONNECTION,
        IssueKind.CONTRACT_MISMATCH,
        IssueKind.STRING_MAPPING_MISMATCH,
    }
)

_SUMMARY_KIND_ORDER: tuple[IssueKind, ...] = (
    IssueKind.UNKNOWN_PARAMETER_TARGET,
    IssueKind.REQUIRED_PARAMETER_CONNECTION,
    IssueKind.CONTRACT_MISMATCH,
    IssueKind.STRING_MAPPING_MISMATCH,
)

_SECTION_TITLES: dict[IssueKind, str] = {
    IssueKind.UNKNOWN_PARAMETER_TARGET: "Unknown parameter mapping targets",
    IssueKind.REQUIRED_PARAMETER_CONNECTION: "Missing required parameter connections",
    IssueKind.CONTRACT_MISMATCH: "Cross-module contract mismatches",
    IssueKind.STRING_MAPPING_MISMATCH: "String mapping type mismatches",
}


def _sentence_case(text: str | None) -> str:
    if not text:
        return "Issue details unavailable."
    normalized = text.rstrip(".")
    return f"{normalized[:1].upper()}{normalized[1:]}."


def _format_issue_message(issue: VariableIssue) -> str:
    if issue.role:
        return _sentence_case(issue.role)

    target_name = issue.variable.name if issue.variable is not None else "<unknown>"
    if issue.kind is IssueKind.STRING_MAPPING_MISMATCH and issue.source_variable is not None:
        return f"String mapping type mismatch for {target_name!r} from {issue.source_variable.name!r}."
    if issue.kind is IssueKind.CONTRACT_MISMATCH and issue.source_variable is not None:
        return f"Contract mismatch for {target_name!r} from {issue.source_variable.name!r}."
    if issue.kind is IssueKind.REQUIRED_PARAMETER_CONNECTION:
        return f"Required parameter connection missing for {target_name!r}."
    if issue.kind is IssueKind.UNKNOWN_PARAMETER_TARGET:
        return f"Unknown parameter mapping target for {target_name!r}."
    return str(issue)


@dataclass
class InterfaceContractsReport:
    name: str
    issues: list[VariableIssue] = field(default_factory=empty_issues)

    def summary(self) -> str:
        if not self.issues:
            lines = format_report_header("Interface contracts", self.name, status="ok")
            lines.append("No interface contract issues found.")
            return "\n".join(lines)

        lines = format_report_header("Interface contracts", self.name, status="issues")
        lines.append(f"Issues: {len(self.issues)}")
        lines.append("Sections:")
        for kind in _SUMMARY_KIND_ORDER:
            count = sum(1 for issue in self.issues if issue.kind is kind)
            if count:
                lines.append(f"  - {_SECTION_TITLES[kind]}: {count}")

        for kind in _SUMMARY_KIND_ORDER:
            kind_issues = [issue for issue in self.issues if issue.kind is kind]
            if not kind_issues:
                continue
            lines.append("")
            lines.append(f"{_SECTION_TITLES[kind]}:")
            for issue in kind_issues:
                location = ".".join(issue.module_path or [self.name])
                lines.append(f"  - [{location}] {_format_issue_message(issue)}")

        return "\n".join(lines)


def analyze_interface_contracts(
    base_picture: BasePicture,
    debug: bool = False,
    unavailable_libraries: set[str] | None = None,
    analyzed_target_is_library: bool = False,
) -> InterfaceContractsReport:
    report = analyze_variables(
        base_picture,
        debug=debug,
        unavailable_libraries=unavailable_libraries,
        analyzed_target_is_library=analyzed_target_is_library,
        selected_issue_kinds=INTERFACE_CONTRACT_ISSUE_KINDS,
    )
    return InterfaceContractsReport(
        name=base_picture.header.name,
        issues=[issue for issue in report.issues if issue.kind in INTERFACE_CONTRACT_ISSUE_KINDS],
    )
