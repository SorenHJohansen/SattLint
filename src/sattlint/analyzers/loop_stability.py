from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from sattline_parser.models.ast_model import BasePicture

from ._report_defaults import empty_int_summary_data, empty_issue_list
from ._wave2_support import as_scalar_literal, iter_assignment_events, iter_statement_sites, walk_module_scopes
from .framework import Issue


@dataclass
class LoopStabilityReport:
    name: str
    issues: list[Issue] = field(default_factory=empty_issue_list)
    summary_data: dict[str, int] = field(default_factory=empty_int_summary_data)

    def summary(self) -> str:
        lines = ["Report: Loop stability", f"Target: {self.name}"]
        lines.append("Status: issues" if self.issues else "Status: ok")
        lines.append(
            "Summary: "
            f"{self.summary_data.get('conflict_count', 0)} conflicting setpoint patterns across "
            f"{self.summary_data.get('scanned_scope_count', 0)} scopes"
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


class LoopStabilityAnalyzer:
    def __init__(self, base_picture: BasePicture) -> None:
        self._base_picture = base_picture
        self._issues: list[Issue] = []
        self._conflict_count = 0
        self._scanned_scope_count = 0

    def run(self) -> LoopStabilityReport:
        for scope in walk_module_scopes(self._base_picture):
            if scope.modulecode is None:
                continue
            self._scanned_scope_count += 1
            literal_writes: dict[str, list[tuple[str, object]]] = defaultdict(list)
            display_names: dict[str, str] = {}
            for site in iter_statement_sites(scope.modulecode):
                for event in iter_assignment_events(site.statement):
                    value = as_scalar_literal(event.expr)
                    if value is None:
                        continue
                    key = event.target_name.casefold()
                    display_names.setdefault(key, event.target_name)
                    literal_writes[key].append((site.label, value))

            for key, writes in sorted(literal_writes.items()):
                distinct_values = {repr(value) for _site, value in writes}
                if len(distinct_values) < 2:
                    continue
                self._conflict_count += 1
                variable_name = display_names.get(key, key)
                self._issues.append(
                    Issue(
                        kind="loop_stability.conflicting_setpoint",
                        message=(
                            f"Variable {variable_name!r} receives conflicting literal assignments in this scope: "
                            f"{', '.join(f'{site}={value!r}' for site, value in writes)}."
                        ),
                        module_path=list(scope.module_path),
                        data={
                            "variable": variable_name,
                            "writes": [{"site": site, "value": value} for site, value in writes],
                            "distinct_values": sorted(distinct_values),
                        },
                    )
                )

        return LoopStabilityReport(
            name=self._base_picture.header.name,
            issues=self._issues,
            summary_data={
                "conflict_count": self._conflict_count,
                "scanned_scope_count": self._scanned_scope_count,
            },
        )


def analyze_loop_stability(base_picture: BasePicture) -> LoopStabilityReport:
    return LoopStabilityAnalyzer(base_picture).run()
