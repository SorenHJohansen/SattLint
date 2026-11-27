"""Profiler log bounds and bottleneck selection."""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path

import pytest

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


def _emit_events(recorder: profiling.ProfileRecorder, count: int, *, padding: int = 80) -> None:
    for index in range(count):
        recorder.emit(
            operation="analyze",
            target_name=f"Target{index}",
            duration_ms=1.0,
            payload={"padding": "x" * padding},
        )


def test_profile_log_and_directory_are_owner_only(tmp_path: Path) -> None:
    log_path = tmp_path / "profile" / "profile.jsonl"
    recorder = profiling.ProfileRecorder(log_path)

    _emit_events(recorder, 1)

    assert stat.S_IMODE(log_path.parent.stat().st_mode) == 0o700
    assert stat.S_IMODE(log_path.stat().st_mode) == 0o600


def test_profile_directory_is_narrowed_when_it_exists_broader(tmp_path: Path) -> None:
    profile_dir = tmp_path / "profile"
    profile_dir.mkdir()
    profile_dir.chmod(0o755)
    recorder = profiling.ProfileRecorder(profile_dir / "profile.jsonl")

    _emit_events(recorder, 1)

    assert stat.S_IMODE(profile_dir.stat().st_mode) == 0o700


def test_profile_log_rotates_before_exceeding_the_cap(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(profiling, "PROFILE_LOG_MAX_BYTES", 700)
    log_path = tmp_path / "profile" / "profile.jsonl"
    recorder = profiling.ProfileRecorder(log_path)

    _emit_events(recorder, 30)

    rotated = log_path.with_name("profile.jsonl.1")
    assert rotated.exists()
    assert log_path.stat().st_size <= 700
    original_lines = rotated.read_text(encoding="utf-8").splitlines()
    current_lines = log_path.read_text(encoding="utf-8").splitlines()
    assert original_lines and current_lines
    assert json.loads(current_lines[-1])["target_name"] == "Target29"


def test_profile_events_larger_than_the_cap_are_dropped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(profiling, "PROFILE_LOG_MAX_BYTES", 20)
    log_path = tmp_path / "profile" / "profile.jsonl"
    recorder = profiling.ProfileRecorder(log_path)

    _emit_events(recorder, 1)

    assert not log_path.exists()


def test_profile_log_does_not_follow_a_symlink(tmp_path: Path) -> None:
    if not hasattr(os, "O_NOFOLLOW"):
        pytest.skip("O_NOFOLLOW is not available on this platform")
    target = tmp_path / "outside.jsonl"
    target.write_text("untouched\n", encoding="utf-8")
    log_path = tmp_path / "profile" / "profile.jsonl"
    log_path.parent.mkdir()
    log_path.symlink_to(target)
    recorder = profiling.ProfileRecorder(log_path)

    _emit_events(recorder, 1)

    assert log_path.is_symlink()
    assert target.read_text(encoding="utf-8") == "untouched\n"
    assert not log_path.with_name("profile.jsonl.1").exists()
