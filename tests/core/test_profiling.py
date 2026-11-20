"""Profiler bottleneck selection uses the recorded phase durations."""

from __future__ import annotations

from sattlint.core import profiling
from sattlint.core.timings import PhaseTiming


def test_phase_bottleneck_reports_the_recorded_duration() -> None:
    bottleneck = profiling.bottleneck_from_phase_timings(
        [PhaseTiming(phase="collect", duration_ms=1.2345)],
        kind="analyzer-phase",
    )

    assert bottleneck is not None
    assert bottleneck.duration_ms == 1.2345


def test_phase_bottleneck_compares_durations_before_rounding() -> None:
    bottleneck = profiling.bottleneck_from_phase_timings(
        [
            PhaseTiming(phase="zeta", duration_ms=1.0003),
            PhaseTiming(phase="alpha", duration_ms=1.0004),
        ],
        kind="analyzer-phase",
    )

    assert bottleneck is not None
    assert (bottleneck.name, bottleneck.duration_ms) == ("alpha", 1.0004)
