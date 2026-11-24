"""Result records for the application checks pipeline."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from ..core.timings import NamedTimings, PhaseTiming, TimingBottleneck
from ..runs import RunModuleRecord
from .findings import AnalysisFinding

__all__ = [
    "AnalyzerFailure",
    "ChecksAnalyzerResult",
    "ChecksRunResult",
    "ChecksTargetResult",
    "LoadFailureLog",
    "TargetLoadFailure",
    "build_run_result",
]


@dataclass(frozen=True, slots=True)
class ChecksAnalyzerResult:
    key: str
    name: str
    status: str
    summary: str | None = None
    report_kind: str | None = None
    issue_count: int | None = None
    findings: tuple[AnalysisFinding, ...] = ()
    duration_ms: float | None = None
    phase_timings_ms: tuple[PhaseTiming, ...] = ()
    skip_reason: str | None = None


@dataclass(frozen=True, slots=True)
class ChecksTargetResult:
    target_name: str
    is_library: bool
    analyzers: tuple[ChecksAnalyzerResult, ...]
    stage_timings_ms: NamedTimings | None = None
    graphics_timings_ms: NamedTimings | None = None
    analyzer_bottleneck: TimingBottleneck | None = None
    analyzer_phase_bottleneck: TimingBottleneck | None = None
    shared_artifact_profile: str | None = None
    is_pseudo: bool = False
    module: RunModuleRecord | None = None
    load_duration_ms: float | None = None


@dataclass(frozen=True, slots=True)
class TargetLoadFailure:
    target_name: str
    message: str


@dataclass(frozen=True, slots=True)
class AnalyzerFailure:
    analyzer_name: str
    target_name: str
    message: str


@dataclass(frozen=True, slots=True)
class ChecksRunResult:
    output_lines: tuple[str, ...]
    targets: tuple[ChecksTargetResult, ...] = ()
    selected_analyzers: tuple[str, ...] = ()
    cancelled: bool = False
    run_id: str | None = None
    failures: tuple[TargetLoadFailure, ...] = ()

    @property
    def analyzer_failures(self) -> tuple[AnalyzerFailure, ...]:
        """Analyzers that raised during this run, across loaded targets and per-run analyzers."""
        return tuple(
            AnalyzerFailure(
                analyzer_name=analyzer.name,
                target_name=target.target_name,
                message=analyzer.summary or "Analyzer failed without a message.",
            )
            for target in self.targets
            for analyzer in target.analyzers
            if analyzer.status == "failed"
        )


@dataclass(slots=True)
class LoadFailureLog:
    """Collects target load failures while a run is streaming."""

    entries: list[TargetLoadFailure] = field(default_factory=list[TargetLoadFailure])

    def record(self, target_name: str, message: str) -> None:
        self.entries.append(TargetLoadFailure(target_name=target_name, message=message))

    def snapshot(self) -> tuple[TargetLoadFailure, ...]:
        return tuple(self.entries)


def build_run_result(
    *,
    output_lines: Iterable[str],
    targets: Iterable[ChecksTargetResult],
    selected_analyzers: tuple[str, ...],
    cancelled: bool = False,
    failures: tuple[TargetLoadFailure, ...] = (),
) -> ChecksRunResult:
    return ChecksRunResult(
        output_lines=tuple(output_lines),
        targets=tuple(targets),
        selected_analyzers=selected_analyzers,
        cancelled=cancelled,
        failures=failures,
    )
