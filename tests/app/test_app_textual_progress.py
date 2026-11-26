# pyright: reportPrivateUsage=false
"""Live analysis progress in the shell's status bar."""

from __future__ import annotations

import asyncio
import time

import pytest

from sattlint import ui as app_textual
from sattlint.core.progress import AnalysisProgressEvent, ProgressPhase
from sattlint.ui import _app_textual_progress as progress_module
from tests.helpers.app_textual_support import (
    isolate_app_config_path,
    isolate_textual_projects,
    make_textual_app,
)

# Re-export the autouse fixtures so pytest registers them for this module.
__all__ = [
    "isolate_app_config_path",
    "isolate_textual_projects",
]


def _state(**kwargs: object) -> progress_module._AnalysisProgressState:
    return progress_module._AnalysisProgressState(**kwargs)  # type: ignore[arg-type]


def test_percent_counts_completed_analyzers_and_targets() -> None:
    def state(**kwargs: object) -> progress_module._AnalysisProgressState:
        return _state(**{"target_total": 2, "analyzer_total": 2, **kwargs})

    assert progress_module._analysis_progress_percent(state(phase=ProgressPhase.START)) == 0
    assert (
        progress_module._analysis_progress_percent(
            state(phase=ProgressPhase.ANALYZING, target_index=1, analyzer_index=2)
        )
        == 25
    )
    assert (
        progress_module._analysis_progress_percent(
            state(
                phase=ProgressPhase.TARGET_COMPLETE,
                target_index=1,
                completed_target_seconds=(4.0,),
            )
        )
        == 50
    )
    assert (
        progress_module._analysis_progress_percent(
            state(
                phase=ProgressPhase.ANALYZING,
                target_index=2,
                analyzer_index=2,
                completed_target_seconds=(4.0,),
            )
        )
        == 75
    )


def test_percent_includes_project_wide_analyzers() -> None:
    state = _state(
        phase=ProgressPhase.ANALYZING,
        target_total=2,
        analyzer_total=2,
        project_wide_total=1,
        completed_target_seconds=(4.0, 5.0),
        analyzer_index=1,
        project_wide=True,
    )

    assert progress_module._analysis_progress_percent(state) == 80


def test_eta_averages_the_targets_that_already_finished() -> None:
    state = _state(
        phase=ProgressPhase.LOADING,
        target_total=3,
        analyzer_total=2,
        target_started_at=100.0,
        target_index=2,
        completed_target_seconds=(10.0,),
    )

    assert progress_module._analysis_eta_seconds(state, now=102.0, run_started_at=50.0) == 18.0


def test_eta_estimates_the_first_target_from_analyzer_progress() -> None:
    state = _state(
        phase=ProgressPhase.ANALYZING,
        target_total=2,
        analyzer_total=4,
        target_started_at=70.0,
        target_index=1,
        analyzer_index=3,
    )

    assert progress_module._analysis_eta_seconds(state, now=100.0, run_started_at=70.0) == 90.0


def test_eta_is_unknown_until_progress_can_be_measured() -> None:
    state = _state(
        phase=ProgressPhase.ANALYZING,
        target_total=1,
        analyzer_total=4,
        target_started_at=70.0,
        analyzer_index=1,
    )

    assert progress_module._analysis_eta_seconds(state, now=100.0, run_started_at=70.0) is None


def test_eta_is_zero_once_every_target_finished() -> None:
    state = _state(
        phase=ProgressPhase.TARGET_COMPLETE,
        target_total=1,
        analyzer_total=1,
        completed_target_seconds=(10.0,),
    )

    assert progress_module._analysis_eta_seconds(state, now=100.0, run_started_at=90.0) == 0.0


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [
        (0, "0:00"),
        (5, "0:05"),
        (65, "1:05"),
        (3661, "1:01:01"),
    ],
)
def test_duration_formatting(seconds: float, expected: str) -> None:
    assert progress_module._format_duration_seconds(seconds) == expected


def test_status_bar_renders_the_live_analysis_phase() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = make_textual_app(
            cfg={"analyzed_programs_and_libraries": ["TargetA", "TargetB"]},
        )

        async with app_instance.run_test() as pilot:
            await pilot.pause()

            app_instance._busy = True
            app_instance._active_job_started_at = time.monotonic() - 12
            app_instance._reset_analysis_progress()
            app_instance._apply_analysis_progress(
                AnalysisProgressEvent(
                    phase=ProgressPhase.START,
                    target_total=2,
                    analyzer_total=2,
                )
            )
            app_instance._apply_analysis_progress(
                AnalysisProgressEvent(
                    phase=ProgressPhase.LOADING,
                    target_total=2,
                    target_index=1,
                    target_name="TargetA",
                )
            )
            app_instance._apply_analysis_progress(
                AnalysisProgressEvent(
                    phase=ProgressPhase.ANALYZING,
                    target_name="TargetA",
                    analyzer_index=1,
                    analyzer_total=2,
                    analyzer_name="Comment code",
                )
            )
            await pilot.pause()

            text = str(app_instance.query_one("#status-progress").renderable)
            assert "0%" in text
            assert "Target 1/2 TargetA" in text
            assert "analyzer 1/2 Comment code" in text
            assert "elapsed" in text
            assert "estimating" in text

    asyncio.run(_run())


def test_status_bar_shows_a_plain_job_label_outside_analysis() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = make_textual_app()

        async with app_instance.run_test() as pilot:
            await pilot.pause()

            app_instance._busy = True
            app_instance._active_job_label = "Generate Change Review"
            app_instance._active_job_started_at = time.monotonic() - 3
            app_instance._reset_analysis_progress()
            app_instance._refresh_status_progress()
            await pilot.pause()

            text = str(app_instance.query_one("#status-progress").renderable)
            assert "Running: Generate Change Review" in text
            assert "elapsed" in text

    asyncio.run(_run())


def test_status_bar_progress_is_empty_when_idle() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = make_textual_app()

        async with app_instance.run_test() as pilot:
            await pilot.pause()

            assert str(app_instance.query_one("#status-progress").renderable) == ""

    asyncio.run(_run())
