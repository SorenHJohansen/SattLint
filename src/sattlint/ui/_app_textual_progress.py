"""Live analysis progress for the Textual status bar.

The shell receives one typed event per observable analysis step from the
child process. This module turns those events into the status-bar segment:
percentage complete, an estimated time left, the current phase, and elapsed
time. The estimate is deliberately simple and self-correcting: it averages the
targets that already finished, and falls back to the fraction of the current
target's analyzers when no target has completed yet.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any

from ..core.progress import AnalysisProgressEvent, ProgressPhase
from ._app_textual_shared import _TEXTUAL_QUERY_ERRORS, _TEXTUAL_STATIC

_STATUS_PROGRESS_SEPARATOR = "   ·   "
_STATUS_PROGRESS_INNER_SEPARATOR = " · "
_STATUS_ESTIMATING_TEXT = "estimating…"


@dataclass(frozen=True, slots=True)
class _AnalysisProgressState:
    """What the status bar knows about the run that is in progress."""

    phase: ProgressPhase
    target_total: int = 0
    analyzer_total: int = 0
    project_wide_total: int = 0
    target_index: int = 0
    target_name: str = ""
    analyzer_index: int = 0
    analyzer_name: str = ""
    project_wide: bool = False
    target_started_at: float = 0.0
    completed_target_seconds: tuple[float, ...] = ()


def _analysis_progress_steps(state: _AnalysisProgressState) -> tuple[int, int]:
    """Completed and total analyzer steps, counting finished targets as whole."""
    total = state.target_total * state.analyzer_total + state.project_wide_total
    completed = len(state.completed_target_seconds) * state.analyzer_total
    if state.phase is ProgressPhase.ANALYZING:
        completed += max(0, state.analyzer_index - 1)
    return max(0, completed), max(0, total)


def _analysis_progress_percent(state: _AnalysisProgressState) -> int | None:
    """Whole-percent completion, held at 99 until the run actually ends."""
    completed, total = _analysis_progress_steps(state)
    if total <= 0:
        return None
    return min(99, (100 * completed) // total)


def _analysis_eta_seconds(
    state: _AnalysisProgressState,
    *,
    now: float,
    run_started_at: float,
) -> float | None:
    """Rough seconds left, or ``None`` while there is not enough history."""
    completed_targets = len(state.completed_target_seconds)
    remaining_targets = max(0, state.target_total - completed_targets)
    in_target = state.phase in (ProgressPhase.LOADING, ProgressPhase.ANALYZING)
    elapsed_current = max(0.0, now - state.target_started_at) if in_target and state.target_started_at > 0 else 0.0

    if remaining_targets > 0 and state.completed_target_seconds:
        average = sum(state.completed_target_seconds) / len(state.completed_target_seconds)
        return max(0.0, average * remaining_targets - elapsed_current)
    if state.phase is ProgressPhase.TARGET_COMPLETE and remaining_targets <= 0 and state.project_wide_total == 0:
        return 0.0
    if state.phase is ProgressPhase.ANALYZING and state.analyzer_index >= 2:
        scope_total = state.project_wide_total if state.project_wide else state.analyzer_total
        scope_elapsed = (now - run_started_at) if state.project_wide else elapsed_current
        if scope_total <= 0 or scope_elapsed <= 0:
            return None
        estimated_scope = scope_elapsed * scope_total / (state.analyzer_index - 1)
        remaining = max(0.0, estimated_scope - scope_elapsed)
        if not state.project_wide:
            remaining += max(0, remaining_targets - 1) * estimated_scope
        return remaining
    return None


def _format_duration_seconds(seconds: float) -> str:
    total_seconds = max(0, int(seconds))
    minutes, seconds_part = divmod(total_seconds, 60)
    hours, minutes_part = divmod(minutes, 60)
    if hours:
        return f"{hours}:{minutes_part:02d}:{seconds_part:02d}"
    return f"{minutes}:{seconds_part:02d}"


def _analysis_phase_text(state: _AnalysisProgressState) -> str:
    if state.phase is ProgressPhase.LOADING:
        return f"Loading target {state.target_index}/{state.target_total} {state.target_name}".strip()
    if state.phase is ProgressPhase.ANALYZING:
        if state.project_wide:
            position = f"Project-wide {state.analyzer_index}/{state.project_wide_total}".strip()
            return f"{position} {state.analyzer_name}".strip()
        observation = f"Target {state.target_index}/{state.target_total} {state.target_name}".strip()
        analyzer = f"analyzer {state.analyzer_index}/{state.analyzer_total}".strip()
        if state.analyzer_name:
            analyzer = f"{analyzer} {state.analyzer_name}"
        return _STATUS_PROGRESS_INNER_SEPARATOR.join((observation, analyzer))
    if state.phase is ProgressPhase.TARGET_COMPLETE:
        return f"Completed target {state.target_index}/{state.target_total} {state.target_name}".strip()
    return "Starting analysis"


def _analysis_progress_text(self: Any) -> str:
    if not self._busy:
        return ""
    state = getattr(self, "_analysis_progress", None)
    if state is None:
        label = self._active_job_text()
        parts = [f"Running: {label}"] if label else []
        elapsed = self._active_job_elapsed_text()
        if elapsed is not None:
            parts.append(f"{elapsed} elapsed")
        return _STATUS_PROGRESS_SEPARATOR.join(parts)

    now = time.monotonic()
    run_started_at = getattr(self, "_active_job_started_at", None) or now
    parts: list[str] = []
    percent = _analysis_progress_percent(state)
    if percent is not None:
        parts.append(f"{percent}%")
    eta = _analysis_eta_seconds(state, now=now, run_started_at=run_started_at)
    if eta is None:
        parts.append(_STATUS_ESTIMATING_TEXT)
    else:
        parts.append(f"~{_format_duration_seconds(eta)} left")
    parts.append(_analysis_phase_text(state))
    parts.append(f"{_format_duration_seconds(now - run_started_at)} elapsed")
    return _STATUS_PROGRESS_SEPARATOR.join(parts)


def _apply_analysis_progress(self: Any, event: AnalysisProgressEvent) -> None:
    """Merge one worker-thread event into the UI state on the UI thread."""
    now = time.monotonic()
    current: _AnalysisProgressState | None = getattr(self, "_analysis_progress", None)
    if current is None or event.phase is ProgressPhase.START:
        self._analysis_progress = _AnalysisProgressState(
            phase=event.phase,
            target_total=event.target_total,
            analyzer_total=event.analyzer_total,
            project_wide_total=event.project_wide_total,
            target_index=event.target_index,
            target_name=event.target_name,
            analyzer_index=event.analyzer_index,
            analyzer_name=event.analyzer_name,
            project_wide=event.project_wide,
        )
    elif event.phase is ProgressPhase.LOADING:
        self._analysis_progress = replace(
            current,
            phase=event.phase,
            target_total=event.target_total or current.target_total,
            analyzer_total=event.analyzer_total or current.analyzer_total,
            project_wide_total=event.project_wide_total or current.project_wide_total,
            target_index=event.target_index,
            target_name=event.target_name,
            analyzer_index=0,
            analyzer_name="",
            project_wide=False,
            target_started_at=now,
        )
    elif event.phase is ProgressPhase.ANALYZING:
        self._analysis_progress = replace(
            current,
            phase=event.phase,
            target_total=event.target_total or current.target_total,
            analyzer_total=event.analyzer_total or current.analyzer_total,
            project_wide_total=event.project_wide_total or current.project_wide_total,
            analyzer_index=event.analyzer_index,
            analyzer_name=event.analyzer_name,
            project_wide=event.project_wide,
            target_started_at=current.target_started_at or now,
        )
    else:
        completed = current.completed_target_seconds
        if current.target_started_at > 0 and current.phase in (ProgressPhase.LOADING, ProgressPhase.ANALYZING):
            completed = (*completed, max(0.0, now - current.target_started_at))
        self._analysis_progress = replace(
            current,
            phase=event.phase,
            target_total=event.target_total or current.target_total,
            target_index=event.target_index or current.target_index,
            target_name=event.target_name or current.target_name,
            analyzer_index=0,
            analyzer_name="",
            project_wide=False,
            completed_target_seconds=completed,
        )
    self._refresh_summary()


def _reset_analysis_progress(self: Any) -> None:
    self._analysis_progress = None


def _receive_analysis_progress(self: Any, event: AnalysisProgressEvent) -> None:
    """Worker-thread entry point: marshal the event onto the UI thread."""
    self._call_on_ui(self._apply_analysis_progress, event)


def _refresh_status_progress(self: Any) -> None:
    try:
        widget = self.query_one("#status-progress", _TEXTUAL_STATIC)
    except _TEXTUAL_QUERY_ERRORS:
        return
    text = self._analysis_progress_text()
    # The spinner ticks ten times a second; the text usually changes once per
    # second, so skip the widget refresh when nothing visible changed.
    if text == getattr(self, "_status_progress_rendered", None):
        return
    self._status_progress_rendered = text
    widget.update(text)


if TYPE_CHECKING:

    class _TextualProgressMixin:
        def _analysis_progress_text(self) -> str: ...
        def _apply_analysis_progress(self, event: AnalysisProgressEvent) -> None: ...
        def _reset_analysis_progress(self) -> None: ...
        def _receive_analysis_progress(self, event: AnalysisProgressEvent) -> None: ...
        def _refresh_status_progress(self) -> None: ...

else:

    class _TextualProgressMixin:
        """Renders live analysis progress into the shell's status bar."""

        _analysis_progress_text = _analysis_progress_text
        _apply_analysis_progress = _apply_analysis_progress
        _reset_analysis_progress = _reset_analysis_progress
        _receive_analysis_progress = _receive_analysis_progress
        _refresh_status_progress = _refresh_status_progress
