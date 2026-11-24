"""The interactive analysis path runs in a child process.

The child returns the run to history; the long-lived app never holds the
parsed project graphs or analyzer indexes that produced it.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import cast

import pytest

from sattlint.application.subprocess_analysis import run_checks_result_in_subprocess
from sattlint.config.defaults import DEFAULT_CONFIG
from sattlint.config.types import ConfigDict
from sattlint.runs import load_run


def test_subprocess_run_streams_output_and_returns_a_saved_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    fixture_dir = Path(__file__).resolve().parents[1] / "fixtures" / "corpus" / "valid"
    cfg = cast(
        ConfigDict,
        {
            **deepcopy(DEFAULT_CONFIG),
            "analyzed_programs_and_libraries": ["MinimalProgram"],
            "program_dir": str(fixture_dir),
            "ABB_lib_dir": str(fixture_dir),
            "icf_dir": "",
            "other_lib_dirs": [],
            "mode": "draft",
        },
    )

    lines: list[str] = []
    result = run_checks_result_in_subprocess(cfg, ["comment-code"], emit_output=lines.append)

    assert result.cancelled is False
    assert result.failures == ()
    assert result.run_id is not None
    assert any("MinimalProgram" in line for line in lines)

    # The child resolves XDG_CACHE_HOME itself; the test fixture patches the
    # parent's resolver to a different path, so point at the child's directory.
    record = load_run(result.run_id, runs_dir=tmp_path / "cache" / "sattlint" / "runs")
    assert record is not None
    assert [target.target_name for target in record.targets] == ["MinimalProgram"]
