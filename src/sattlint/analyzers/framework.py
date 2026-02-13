"""Shared analysis framework primitives."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Protocol

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
        return "\n".join(lines)


@dataclass(frozen=True)
class AnalysisContext:
    base_picture: BasePicture
    graph: Any | None = None
    debug: bool = False

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


@dataclass(frozen=True)
class AnalysisResult:
    analyzer: AnalyzerSpec
    report: Report
