"""Shared analysis framework primitives."""

from __future__ import annotations

from collections.abc import Callable, Collection, Mapping, Set
from dataclasses import dataclass, field
from time import perf_counter
from typing import Any, Protocol

from sattline_parser.models.ast_model import BasePicture

from ._shared_analysis import AnalysisSharedArtifacts, VariableAnalysisArtifacts
from .issue import Findings, Issue, format_report_header

__all__ = [
    "AnalysisContext",
    "AnalysisResult",
    "AnalysisSharedArtifacts",
    "Analyzer",
    "AnalyzerLifecycleMixin",
    "AnalyzerSpec",
    "BasePictureAnalyzer",
    "Findings",
    "Issue",
    "Report",
    "SimpleReport",
    "VariableAnalysisArtifacts",
    "build_analysis_context",
    "empty_issues",
    "format_report_header",
    "register_issue_metadata_materializer",
]


def empty_issues() -> list[Any]:
    return []


class BasePictureAnalyzer:
    """Default owner for class-backed analyzers.

    New analyzers should expose a thin module-level ``analyze_*`` wrapper for
    registry wiring and keep the implementation on a class. When a class grows
    beyond one file, split behavior into underscore-prefixed helper or mixin
    modules and compose them with inheritance instead of module-level re-export
    chains.
    """

    def __init__(self, base_picture: BasePicture) -> None:
        self.bp = base_picture

    @property
    def root_path(self) -> list[str]:
        return [self.bp.header.name]


class AnalyzerLifecycleMixin:
    def _initialize_lifecycle(
        self,
        *,
        trace_namespace: str,
        trace_recorder: Any | None = None,
        status_update_fn: Callable[[str], None] | None = None,
        status_prefix: str | None = None,
    ) -> None:
        self._trace_namespace = trace_namespace
        self._trace_recorder = trace_recorder
        self._status_update_fn = status_update_fn
        self._status_prefix = status_prefix or f"Analyzing {trace_namespace}"
        self._last_status_message = None
        self._phase_timings: list[dict[str, str | float]] = []

    def trace(self, action: str, **data: Any) -> None:
        self._trace(action, **data)

    def _trace(self, action: str, **data: Any) -> None:
        trace_recorder = getattr(self, "_trace_recorder", None)
        if trace_recorder is None:
            return
        trace_recorder.event(getattr(self, "_trace_namespace", "analyzer"), action, **data)

    @property
    def phase_timings(self) -> list[dict[str, str | float]]:
        return [dict(phase) for phase in getattr(self, "_phase_timings", [])]

    def _record_phase_timing(self, phase: str, started_at: float, ended_at: float | None = None) -> None:
        completed_at = perf_counter() if ended_at is None else ended_at
        duration_ms = round((completed_at - started_at) * 1000, 3)
        self._phase_timings.append({"phase": phase, "duration_ms": duration_ms})
        self._trace("phase-complete", phase_name=phase, duration_ms=duration_ms)

    def _update_status(self, detail: str) -> None:
        status_update_fn = getattr(self, "_status_update_fn", None)
        if status_update_fn is None:
            return
        base_picture = getattr(self, "bp", None)
        target_name = getattr(getattr(base_picture, "header", None), "name", None)
        prefix = getattr(self, "_status_prefix", "Analyzing")
        text = f"{prefix} for {target_name}: {detail}" if target_name else f"{prefix}: {detail}"
        if text == getattr(self, "_last_status_message", None):
            return
        self._last_status_message = text
        status_update_fn(text)


def _identity_issue_metadata(issue: Issue) -> Issue:
    return issue


_issue_metadata_materializer: Callable[[Issue], Issue] = _identity_issue_metadata


def register_issue_metadata_materializer(materializer: Callable[[Issue], Issue]) -> None:
    global _issue_metadata_materializer
    _issue_metadata_materializer = materializer


class Report(Protocol):
    issues: Findings[Any]

    def summary(self) -> str: ...


class Analyzer(Protocol):
    """Callable protocol for analyzer functions registered in AnalyzerSpec."""

    def __call__(self, context: AnalysisContext) -> Report: ...


@dataclass
class SimpleReport:
    name: str
    issues: Findings[Issue] = field(default_factory=empty_issues)
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
        materialized_issues: list[Issue] = [_issue_metadata_materializer(issue) for issue in self.issues]

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
    selected_issue_kinds: Set[str] | None = None
    config: dict[str, Any] | None = None
    shared_artifacts: AnalysisSharedArtifacts | None = None

    @property
    def unavailable_libraries(self) -> set[str]:
        return getattr(self.graph, "unavailable_libraries", set())


def build_analysis_context(
    base_picture: BasePicture,
    *,
    graph: Any | None = None,
    debug: bool = False,
    target_is_library: bool = False,
    selected_issue_kinds: Collection[str] | None = None,
    config: Mapping[str, Any] | None = None,
    shared_artifacts: AnalysisSharedArtifacts | None = None,
    create_shared_artifacts: bool = False,
) -> AnalysisContext:
    resolved_shared_artifacts = shared_artifacts
    if resolved_shared_artifacts is None and create_shared_artifacts:
        resolved_shared_artifacts = AnalysisSharedArtifacts()
        resolved_shared_artifacts.counters.shared_artifact_holders_created += 1

    return AnalysisContext(
        base_picture=base_picture,
        graph=graph,
        debug=debug,
        target_is_library=target_is_library,
        selected_issue_kinds=(None if selected_issue_kinds is None else frozenset(selected_issue_kinds)),
        config={} if config is None else dict(config),
        shared_artifacts=resolved_shared_artifacts,
    )


@dataclass(frozen=True)
class AnalyzerSpec:
    key: str
    name: str
    description: str
    run: Analyzer
    requires: tuple[str, ...] = ()
    enabled: bool = True
    supports_live_diagnostics: bool = False
    analyzer_attr: str = ""
    context_kwargs: tuple[str, ...] = ()
    direct_context: bool = False
    semantic_mapping_kind: str | None = None
    semantic_rule_source: str | None = None

    @property
    def supports_selected_issue_kinds(self) -> bool:
        return "selected_issue_kinds" in self.context_kwargs


@dataclass(frozen=True)
class AnalysisResult:
    analyzer: AnalyzerSpec
    report: Report
