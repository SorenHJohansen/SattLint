from __future__ import annotations

from dataclasses import dataclass, field

from sattline_parser.models.ast_model import BasePicture

from .framework import Issue, format_report_header
from .initial_values import analyze_initial_values
from .unsafe_defaults import analyze_unsafe_defaults

_POWERUP_SECTION_ORDER: tuple[str, ...] = (
    "initial-values.missing_required_default",
    "unsafe_defaults.true_boolean_default",
)

_POWERUP_SECTION_TITLES: dict[str, str] = {
    "initial-values.missing_required_default": "Missing startup values",
    "unsafe_defaults.true_boolean_default": "Unsafe startup defaults",
}


def _empty_issues() -> list[Issue]:
    return []


@dataclass
class PowerupReport:
    name: str
    issues: list[Issue] = field(default_factory=_empty_issues)

    def summary(self) -> str:
        if not self.issues:
            lines = format_report_header("Power-up", self.name, status="ok")
            lines.append("No power-up issues found.")
            return "\n".join(lines)

        lines = format_report_header("Power-up", self.name, status="issues")
        lines.append(f"Issues: {len(self.issues)}")
        lines.append("Sections:")
        for kind in _POWERUP_SECTION_ORDER:
            count = sum(1 for issue in self.issues if issue.kind == kind)
            if count:
                lines.append(f"  - {_POWERUP_SECTION_TITLES[kind]}: {count}")

        for kind in _POWERUP_SECTION_ORDER:
            kind_issues = [issue for issue in self.issues if issue.kind == kind]
            if not kind_issues:
                continue
            lines.append("")
            lines.append(f"{_POWERUP_SECTION_TITLES[kind]}:")
            for issue in kind_issues:
                location = ".".join(issue.module_path or [self.name])
                lines.append(f"  - [{location}] {issue.message}")

        return "\n".join(lines)


def analyze_powerup(
    base_picture: BasePicture,
    debug: bool = False,
    unavailable_libraries: set[str] | None = None,
) -> PowerupReport:
    initial_values_report = analyze_initial_values(
        base_picture,
        debug=debug,
        unavailable_libraries=unavailable_libraries,
    )
    unsafe_defaults_report = analyze_unsafe_defaults(base_picture)
    return PowerupReport(
        name=base_picture.header.name,
        issues=[*initial_values_report.issues, *unsafe_defaults_report.issues],
    )
