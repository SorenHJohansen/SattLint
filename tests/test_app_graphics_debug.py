from __future__ import annotations

import logging
from collections.abc import Callable, Iterator
from pathlib import Path
from types import SimpleNamespace, TracebackType
from typing import Any, cast

import pytest

from sattline_parser.models.ast_model import BasePicture
from sattlint import app
from sattlint.models.project_graph import ProjectGraph


def test_run_graphics_rules_validation_logs_debug_traceback_for_target_failure(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    outputs: list[str] = []
    pauses: list[str] = []
    cfg = app.DEFAULT_CONFIG.copy()
    cfg["debug"] = True

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

    def get_graphics_rules_path() -> Path:
        return Path("graphics_rules.json")

    def load_graphics_rules(_path: Path) -> tuple[dict[str, Any], bool]:
        return ({"rules": [{"selector_value": "Area.UnitControl"}]}, False)

    def iter_loaded_projects(_cfg: dict[str, object]) -> Iterator[tuple[str, BasePicture, ProjectGraph]]:
        yield (
            "TargetB",
            cast(BasePicture, SimpleNamespace(name="bp")),
            cast(ProjectGraph, SimpleNamespace(name="graph")),
        )

    def fail_collect(
        _target_name: str,
        _project_bp: BasePicture,
        _graph: ProjectGraph,
    ) -> list[dict[str, Any]]:
        raise RuntimeError("boom")

    def pause() -> None:
        pauses.append("pause")

    monkeypatch.setattr(app.app_graphics_module, "emit_output", outputs.append)
    monkeypatch.setattr(app.app_graphics_module.console_module, "live_status_line", _StatusLine)

    with caplog.at_level(logging.ERROR, logger="SattLint"):
        app.app_graphics_module.run_graphics_rules_validation(
            cfg,
            get_graphics_rules_path_fn=get_graphics_rules_path,
            load_graphics_rules_fn=load_graphics_rules,
            iter_loaded_projects_fn=iter_loaded_projects,
            collect_graphics_layout_entries_for_target_fn=fail_collect,
            pause_fn=pause,
        )

    assert any("Error during graphics rules validation for TargetB: boom" in output for output in outputs)
    assert any("Graphics rules validation failed for 'TargetB'" in message for message in caplog.messages)
    assert "Traceback (most recent call last)" in caplog.text
    assert pauses == ["pause"]
