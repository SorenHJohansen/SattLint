"""Check module clipping geometry and grid alignment."""

from __future__ import annotations

from typing import Any

from sattlint.parser_api import BasePicture

from ..config.analysis import module_grid, module_grid_tolerance
from ..graphics.module_geometry import diagnose_module_layout
from .framework import Issue, SimpleReport
from .shared.target_origin import build_target_origin_filter_for_basepicture


def analyze_module_layout(
    base_picture: BasePicture,
    *,
    config: dict[str, Any] | None = None,
    analyzed_target_is_library: bool = False,
) -> SimpleReport:
    findings = diagnose_module_layout(
        base_picture,
        grid=module_grid(config),
        tolerance=module_grid_tolerance(config),
        module_type_filter=build_target_origin_filter_for_basepicture(
            base_picture,
            analyzed_target_is_library=analyzed_target_is_library,
        ),
    )
    issues: list[Issue] = []
    for finding in findings:
        data = dict(finding.details)
        if finding.line is not None:
            data["line"] = finding.line
        issues.append(
            Issue(
                kind=finding.kind,
                message=finding.message,
                module_path=list(finding.module_path),
                data=data,
            )
        )
    return SimpleReport(name=base_picture.header.name, issues=issues)


__all__ = ["analyze_module_layout"]
