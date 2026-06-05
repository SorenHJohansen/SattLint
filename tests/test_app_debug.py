from __future__ import annotations

import logging
from collections.abc import Callable, Iterator
from types import SimpleNamespace, TracebackType
from typing import Any, cast

import pytest

from sattline_parser.models.ast_model import BasePicture
from sattlint import app_analysis
from sattlint.models.project_graph import ProjectGraph


def test_run_debug_variable_usage_logs_debug_traceback_for_target_failure(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    outputs: list[str] = []

    class _StatusLine:
        def __enter__(self) -> Callable[[str], None]:
            def _update(_text: str) -> None:
                return None

            return _update

        def __exit__(
            self,
            exc_type: type[BaseException] | None,
            exc: BaseException | None,
            tb: TracebackType | None,
        ) -> bool:
            del exc_type, exc, tb
            return False

    def fail_debug(_project_bp: object, _var_name: str, *, debug: bool = False) -> object:
        del debug
        raise RuntimeError("boom")

    def fake_input(_prompt: str = "") -> str:
        return "Valve"

    def iter_loaded_projects(_cfg: dict[str, object]) -> Iterator[tuple[str, BasePicture, ProjectGraph]]:
        yield (
            "TargetA",
            cast(BasePicture, SimpleNamespace(name="bp")),
            cast(ProjectGraph, SimpleNamespace(name="graph")),
        )

    monkeypatch.setattr(app_analysis, "emit_output", outputs.append)
    monkeypatch.setattr(app_analysis.console_module, "live_status_line", _StatusLine)
    monkeypatch.setattr(app_analysis, "debug_variable_usage", cast(Any, fail_debug))
    monkeypatch.setattr("builtins.input", fake_input)

    with caplog.at_level(logging.ERROR, logger="SattLint"):
        app_analysis.run_debug_variable_usage(
            {"debug": True},
            iter_loaded_projects_fn=iter_loaded_projects,
            pause_fn=None,
        )

    assert any("Error during debug for TargetA: boom" in output for output in outputs)
    assert any(
        "Variable usage debug failed for target 'TargetA' and variable 'Valve'" in message
        for message in caplog.messages
    )
    assert "Traceback (most recent call last)" in caplog.text
