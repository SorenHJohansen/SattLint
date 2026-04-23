"""Shared analysis framework primitives."""

from __future__ import annotations

import importlib
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

from ..models.ast_model import BasePicture


class Report(Protocol):
    issues: list[Any]

    def summary(self) -> str: ...


@dataclass(frozen=True)
class Issue:
    kind: str
    message: str
    module_path: list[str] | None = None
    data: dict[str, Any] | None = None
    rule_id: str | None = None
    severity: str | None = None
    confidence: str | None = None
    explanation: str | None = None
    suggestion: str | None = None


def format_report_header(report_type: str, target: str, status: str | None = None) -> list[str]:
    lines = [f"Report: {report_type}", f"Target: {target}"]
    if status:
        lines.append(f"Status: {status}")
    return lines


@dataclass
class SimpleReport:
    name: str
    issues: list[Issue] = field(default_factory=list)
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
        materialize_issue_metadata = importlib.import_module(
            "sattlint.analyzers.rule_profiles"
        ).materialize_issue_metadata

        for issue in sorted(
            [materialize_issue_metadata(issue) for issue in self.issues],
            key=lambda item: (
                item.severity or "",
                item.kind,
                item.module_path or [],
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
    run: Callable[[AnalysisContext], Report]
    enabled: bool = True
    supports_live_diagnostics: bool = False


@dataclass(frozen=True)
class AnalysisResult:
    analyzer: AnalyzerSpec
    report: Report
