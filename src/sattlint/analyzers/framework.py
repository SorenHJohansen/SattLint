"""Shared analysis framework primitives."""

from __future__ import annotations

import importlib
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol, cast

from sattline_parser.models.ast_model import BasePicture

from .issue import Issue, format_report_header

__all__ = [
    "AnalysisContext",
    "AnalysisResult",
    "Analyzer",
    "AnalyzerSpec",
    "Issue",
    "Report",
    "SimpleReport",
    "empty_issues",
    "format_report_header",
]


def empty_issues() -> list[Any]:
    return []


class Report(Protocol):
    issues: list[Any]

    def summary(self) -> str: ...


class Analyzer(Protocol):
    """Callable protocol for analyzer functions registered in AnalyzerSpec."""

    def __call__(self, context: AnalysisContext) -> Report: ...


@dataclass
class SimpleReport:
    name: str
    issues: list[Issue] = field(default_factory=empty_issues)
    note: str | None = None

    def summary(self) -> str:
        if self.note:
            lines = format_report_header("Simple", self.name, status="info")
            lines.append(self.note)
            return "\n".join(lines)
        if not self.issues:
            lines = format_report_header("Simple", self.name, status="ok")
            lines.append("No issues found.")
            return "\n".join(lines)
        lines = format_report_header("Simple", self.name, status="issues")
        lines.append(f"Issues: {len(self.issues)}")
        lines.append("")
        lines.append("Findings:")
        materialize_issue_metadata = cast(
            Callable[[Issue], Issue],
            importlib.import_module("sattlint.analyzers.rule_profiles").materialize_issue_metadata,
        )
        materialized_issues: list[Issue] = [materialize_issue_metadata(issue) for issue in self.issues]

        for issue in sorted(
            materialized_issues,
            key=lambda item: (
                item.severity or "",
                item.kind,
                tuple(item.module_path or ()),
                item.message,
            ),
        ):
            location = ".".join(issue.module_path or [self.name])
            metadata: list[str] = []
            if issue.severity:
                metadata.append(issue.severity)
            if issue.confidence:
                metadata.append(issue.confidence)
            if issue.rule_id:
                metadata.append(issue.rule_id)
            metadata_text = f" [{' | '.join(metadata)}]" if metadata else ""
            lines.append(f"  - [{location}] {issue.message}{metadata_text}")
            if issue.explanation:
                lines.append(f"      Why it matters: {issue.explanation}")
            if issue.suggestion:
                lines.append(f"      Suggested fix: {issue.suggestion}")
        return "\n".join(lines)


@dataclass(frozen=True)
class AnalysisContext:
    base_picture: BasePicture
    graph: Any | None = None
    debug: bool = False
    target_is_library: bool = False
    config: dict[str, Any] | None = None

    @property
    def unavailable_libraries(self) -> set[str]:
        return getattr(self.graph, "unavailable_libraries", set())


@dataclass(frozen=True)
class AnalyzerSpec:
    key: str
    name: str
    description: str
    run: Analyzer
    enabled: bool = True
    supports_live_diagnostics: bool = False


@dataclass(frozen=True)
class AnalysisResult:
    analyzer: AnalyzerSpec
    report: Report
