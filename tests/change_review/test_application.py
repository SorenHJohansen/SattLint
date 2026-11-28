# pyright: reportPrivateUsage=false
"""Application-seam tests for the structured Change Review result."""

from __future__ import annotations

import os
import stat
from pathlib import Path
from typing import Any, cast

import pytest

from sattlint.application import change_review as change_review_application
from sattlint.application.change_review import (
    ChangeReviewNoTargetsError,
    ChangeReviewOutputError,
    run_change_review,
)
from sattlint.config.types import ConfigDict
from tests.helpers.change_review_support import build_cfg

pytestmark = pytest.mark.unit


def test_run_change_review_returns_structured_per_target_detail(tmp_path: Path) -> None:
    output_dir = tmp_path / "configured-review"
    cfg = build_cfg(tmp_path, review_output_dir=str(output_dir))

    outcome = run_change_review(cfg, ["Demo"])

    assert outcome.output_dir == output_dir
    assert output_dir.is_dir()
    assert outcome.generated_targets == 1
    assert outcome.failed_targets == 0
    generated = outcome.generated[0]
    assert generated.target == "Demo"
    assert generated.json_path.exists()
    assert generated.markdown_path.exists()
    assert generated.json_path.parent == output_dir
    if os.name == "posix":
        assert stat.S_IMODE(output_dir.stat().st_mode) == 0o700


def test_run_change_review_collects_every_target_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = build_cfg(tmp_path)

    def fake_run_review(_cfg: ConfigDict, target: str, *, output_dir: Path) -> Any:
        raise ValueError(f"{target} is stale")

    monkeypatch.setattr(change_review_application, "run_review", fake_run_review)

    outcome = run_change_review(cfg, ["Bad", "Worse"], output_dir=tmp_path / "out")

    assert outcome.generated == ()
    assert outcome.generated_targets == 0
    assert outcome.failed_targets == 2
    assert [(failure.target, failure.message) for failure in outcome.failures] == [
        ("Bad", "Bad is stale"),
        ("Worse", "Worse is stale"),
    ]


def test_run_change_review_requires_a_target(tmp_path: Path) -> None:
    cfg = cast(ConfigDict, {**build_cfg(tmp_path), "analyzed_programs_and_libraries": []})

    with pytest.raises(ChangeReviewNoTargetsError):
        run_change_review(cfg, [])


def test_run_change_review_reports_an_unusable_output_directory(tmp_path: Path) -> None:
    cfg = build_cfg(tmp_path)
    blocked = tmp_path / "blocked"
    blocked.write_text("not a directory", encoding="utf-8")

    with pytest.raises(ChangeReviewOutputError):
        run_change_review(cfg, ["Demo"], output_dir=blocked)
