from __future__ import annotations

from dataclasses import dataclass, field

from sattline_parser.models.ast_model import BasePicture

from .framework import Issue, empty_issues, format_report_header
from .unsafe_defaults import analyze_unsafe_defaults

_POWERUP_SECTION_ORDER: tuple[str, ...] = ("unsafe_defaults.true_boolean_default",)

_POWERUP_SECTION_TITLES: dict[str, str] = {
    "unsafe_defaults.true_boolean_default": "Unsafe startup defaults",
}


@dataclass
class PowerupReport:
    name: str
    issues: list[Issue] = field(default_factory=empty_issues)

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
    analyzed_target_is_library: bool = False,
) -> PowerupReport:
    unsafe_defaults_report = analyze_unsafe_defaults(
        base_picture,
        analyzed_target_is_library=analyzed_target_is_library,
    )
    return PowerupReport(
        name=base_picture.header.name,
        issues=unsafe_defaults_report.issues,
    )
