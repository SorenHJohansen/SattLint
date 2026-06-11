from __future__ import annotations

import re
from dataclasses import dataclass, field

from sattline_parser.models.ast_model import BasePicture, Variable

from ._wave2_support import as_numeric_literal, iter_assignment_events, iter_statement_sites, walk_module_scopes
from .framework import Issue
from .shared._report_defaults import empty_int_summary_data, empty_issue_list


@dataclass(frozen=True)
class _NumericConstraint:
    display_name: str
    minimum: int | float | None = None
    maximum: int | float | None = None


@dataclass
class NumericConstraintsReport:
    name: str
    issues: list[Issue] = field(default_factory=empty_issue_list)
    summary_data: dict[str, int] = field(default_factory=empty_int_summary_data)

    def summary(self) -> str:
        lines = ["Report: Numeric constraints", f"Target: {self.name}"]
        lines.append("Status: issues" if self.issues else "Status: ok")
        lines.append(
            "Summary: "
            f"{self.summary_data.get('checked_assignment_count', 0)} checked assignments, "
            f"{self.summary_data.get('violation_count', 0)} violations"
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


class NumericConstraintsAnalyzer:
    def __init__(self, base_picture: BasePicture) -> None:
        self._base_picture = base_picture
        self._issues: list[Issue] = []
        self._checked_assignment_count = 0
        self._violation_count = 0

    def run(self) -> NumericConstraintsReport:
        for scope in walk_module_scopes(self._base_picture):
            if scope.modulecode is None:
                continue
            constraints = self._collect_constraints(scope.env)
            if not constraints:
                continue
            for site in iter_statement_sites(scope.modulecode):
                for event in iter_assignment_events(site.statement):
                    key = event.target_name.casefold()
                    if key not in constraints:
                        continue
                    value = as_numeric_literal(event.expr)
                    if value is None:
                        continue
                    self._checked_assignment_count += 1
                    constraint = constraints[key]
                    if constraint.minimum is not None and value < constraint.minimum:
                        self._emit_violation(scope.module_path, event.target_name, value, constraint, site.label)
                        continue
                    if constraint.maximum is not None and value > constraint.maximum:
                        self._emit_violation(scope.module_path, event.target_name, value, constraint, site.label)

        return NumericConstraintsReport(
            name=self._base_picture.header.name,
            issues=self._issues,
            summary_data={
                "checked_assignment_count": self._checked_assignment_count,
                "violation_count": self._violation_count,
            },
        )

    def _collect_constraints(self, env: dict[str, Variable]) -> dict[str, _NumericConstraint]:
        constraints: dict[str, _NumericConstraint] = {}
        for variable in env.values():
            value = as_numeric_literal(variable.init_value)
            if value is None:
                continue
            binding = _limit_binding(variable.name)
            if binding is None:
                continue
            bound_kind, target_name = binding
            key = target_name.casefold()
            current = constraints.get(key)
            if current is None:
                current = _NumericConstraint(display_name=target_name)
            if bound_kind == "min":
                constraints[key] = _NumericConstraint(
                    display_name=current.display_name,
                    minimum=value,
                    maximum=current.maximum,
                )
            else:
                constraints[key] = _NumericConstraint(
                    display_name=current.display_name,
                    minimum=current.minimum,
                    maximum=value,
                )
        return constraints

    def _emit_violation(
        self,
        module_path: tuple[str, ...],
        target_name: str,
        value: int | float,
        constraint: _NumericConstraint,
        site_label: str,
    ) -> None:
        self._violation_count += 1
        self._issues.append(
            Issue(
                kind="numeric_constraints.limit_violation",
                message=(
                    f"Assignment to {target_name!r} in {site_label} resolves to {value!r}, outside the visible range "
                    f"[{constraint.minimum!r}, {constraint.maximum!r}]."
                ),
                module_path=list(module_path),
                data={
                    "variable": target_name,
                    "value": value,
                    "minimum": constraint.minimum,
                    "maximum": constraint.maximum,
                    "site": site_label,
                },
            )
        )


def _limit_binding(name: str) -> tuple[str, str] | None:
    normalized = name.strip()
    prefix_match = re.match(r"^(min(?:imum)?|max(?:imum)?)[_\-]?(?P<body>.+)$", normalized, flags=re.IGNORECASE)
    if prefix_match:
        kind = "min" if prefix_match.group(1).casefold().startswith("min") else "max"
        body = prefix_match.group("body").strip("_-")
        if body:
            return kind, body

    suffix_match = re.match(r"^(?P<body>.+?)[_\-]?(min(?:imum)?|max(?:imum)?)$", normalized, flags=re.IGNORECASE)
    if suffix_match:
        suffix = suffix_match.group(2)
        kind = "min" if suffix.casefold().startswith("min") else "max"
        body = suffix_match.group("body").strip("_-")
        if body:
            return kind, body

    return None


def analyze_numeric_constraints(base_picture: BasePicture) -> NumericConstraintsReport:
    return NumericConstraintsAnalyzer(base_picture).run()
