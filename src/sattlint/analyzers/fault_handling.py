from __future__ import annotations

from dataclasses import dataclass, field

from sattline_parser.models.ast_model import BasePicture, Simple_DataType

from ._report_defaults import empty_int_summary_data, empty_issue_list
from ._wave2_support import (
    as_bool_literal,
    iter_assignment_events,
    iter_read_variable_names,
    iter_statement_sites,
    walk_module_scopes,
)
from .framework import Issue


@dataclass
class FaultHandlingReport:
    name: str
    issues: list[Issue] = field(default_factory=empty_issue_list)
    summary_data: dict[str, int] = field(default_factory=empty_int_summary_data)

    def summary(self) -> str:
        lines = ["Report: Fault handling", f"Target: {self.name}"]
        lines.append("Status: issues" if self.issues else "Status: ok")
        lines.append(
            "Summary: "
            f"{self.summary_data.get('missing_recovery_count', 0)} missing recovery paths, "
            f"{self.summary_data.get('unhandled_fault_count', 0)} unhandled fault paths"
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


class FaultHandlingAnalyzer:
    def __init__(self, base_picture: BasePicture) -> None:
        self._base_picture = base_picture
        self._issues: list[Issue] = []
        self._missing_recovery_count = 0
        self._unhandled_fault_count = 0

    def run(self) -> FaultHandlingReport:
        for scope in walk_module_scopes(self._base_picture):
            if scope.modulecode is None:
                continue

            candidates = {
                name: variable
                for name, variable in scope.env.items()
                if variable.datatype == Simple_DataType.BOOLEAN
                and ("fault" in variable.name.casefold() or "alarm" in variable.name.casefold())
            }
            if not candidates:
                continue

            writes_true: set[str] = set()
            writes_false: set[str] = set()
            reads: set[str] = set()

            for site in iter_statement_sites(scope.modulecode):
                for event in iter_assignment_events(site.statement):
                    key = event.target_name.casefold()
                    if key not in candidates:
                        continue
                    value = as_bool_literal(event.expr)
                    if value is True:
                        writes_true.add(key)
                    elif value is False:
                        writes_false.add(key)
                for name in iter_read_variable_names(site.statement):
                    key = name.casefold()
                    if key in candidates:
                        reads.add(key)

            for key, variable in sorted(candidates.items()):
                if key in writes_true and key not in writes_false:
                    self._missing_recovery_count += 1
                    self._issues.append(
                        Issue(
                            kind="fault_handling.missing_recovery",
                            message=(
                                f"Fault path {variable.name!r} is raised but never explicitly cleared or acknowledged in this scope."
                            ),
                            module_path=list(scope.module_path),
                            data={"fault": variable.name},
                        )
                    )
                if key in writes_true and key not in reads:
                    self._unhandled_fault_count += 1
                    self._issues.append(
                        Issue(
                            kind="fault_handling.unhandled_fault",
                            message=(
                                f"Fault path {variable.name!r} is raised but no reachable logic consumes it in this scope."
                            ),
                            module_path=list(scope.module_path),
                            data={"fault": variable.name},
                        )
                    )

        return FaultHandlingReport(
            name=self._base_picture.header.name,
            issues=self._issues,
            summary_data={
                "missing_recovery_count": self._missing_recovery_count,
                "unhandled_fault_count": self._unhandled_fault_count,
            },
        )


def analyze_fault_handling(base_picture: BasePicture) -> FaultHandlingReport:
    return FaultHandlingAnalyzer(base_picture).run()
