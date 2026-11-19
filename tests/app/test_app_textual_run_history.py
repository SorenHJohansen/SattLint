# pyright: reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportUnusedImport=false
"""Results view and stored run history."""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest

from sattlint import ui as app_textual
from sattlint.application.findings import AnalysisFinding
from sattlint.runs import RunAnalyzerRecord, RunModuleRecord, RunRecord, RunSummary, RunTargetRecord
from sattlint.ui import _app_textual_results as app_textual_results_module
from tests.helpers.app_textual_support import (  # noqa: F401  (autouse fixtures)
    isolate_app_config_path,
    isolate_textual_projects,
    make_textual_app,
)


def test_textual_results_view_lists_runs_and_renders_tree(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    record = RunRecord(
        run_id="run1",
        started_at="2026-09-06T10:00:00Z",
        finished_at="2026-09-06T10:05:00Z",
        project_tag="TargetA",
        project_path=str(tmp_path / "sattlint-test.slproj"),
        selected_analyzers=("variables",),
        targets=(
            RunTargetRecord(
                target_name="TargetA",
                is_library=False,
                analyzers=(
                    RunAnalyzerRecord(
                        key="variables",
                        name="Variable issues",
                        status="completed",
                        findings=(
                            AnalysisFinding(
                                kind="unused",
                                message="declared but never read",
                                module_path=("TargetA",),
                            ),
                        ),
                    ),
                ),
            ),
        ),
        output_lines=("=== Target: TargetA ===", "state inference summary"),
    )
    summary = RunSummary.from_record(record)

    async def _run() -> None:
        app_instance = make_textual_app(cfg={"analyzed_programs_and_libraries": ["TargetA"]})
        app_instance._project_path = tmp_path / "sattlint-test.slproj"
        monkeypatch.setattr(app_textual_results_module, "list_runs", lambda: (summary,))
        monkeypatch.setattr(app_textual_results_module, "load_run", lambda run_id: record if run_id == "run1" else None)

        async with app_instance.run_test() as pilot:
            await pilot.press("ctrl+2")
            await pilot.pause()

            assert app_instance._active_view == "results"
            results_browser = app_instance.query_one("#results-browser")
            assert results_browser.has_class("is-hidden") is False
            assert app_instance.query_one("#results-tree-host .results-pane-title").renderable == "Modules"
            assert app_instance.query_one("#results-findings-host .results-pane-title").renderable == "Findings"
            assert (
                app_instance.query_one("#results-tree-host").size.width
                > app_instance.query_one("#results-runs-section").size.width
            )

            tree = app_instance._results_tree_widget
            assert tree is not None
            assert tree.root.is_expanded is True
            target_node = tree.root.children[0]
            assert target_node.label.plain == "TargetA"
            assert not list(target_node.children)
            findings_report = app_instance._results_findings_widget
            assert findings_report.id == "results-findings-report"
            assert not list(app_instance.query("#results-findings-host Tree"))
            assert "Unused variable (1)" in findings_report.renderable
            assert "declared but never read" in findings_report.renderable

            app_instance._collapse_all_results()
            await pilot.pause()
            assert tree.root.is_expanded is True
            assert target_node.is_expanded is False

            app_instance._expand_all_results()
            await pilot.pause()
            assert tree.root.is_expanded is True
            assert target_node.is_expanded is True

    asyncio.run(_run())


def test_textual_results_module_selection_updates_findings_pane(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    record = RunRecord(
        run_id="run1",
        started_at="2026-09-06T10:00:00Z",
        finished_at="2026-09-06T10:05:00Z",
        project_tag="TargetA",
        project_path=str(tmp_path / "sattlint-test.slproj"),
        targets=(
            RunTargetRecord(
                target_name="TargetA",
                is_library=False,
                module=RunModuleRecord(
                    name="TargetA",
                    kind="SingleModule",
                    children=(
                        RunModuleRecord(name="Charging", kind="FrameModule"),
                        RunModuleRecord(name="Idle", kind="SingleModule"),
                    ),
                ),
                analyzers=(
                    RunAnalyzerRecord(
                        key="variables",
                        name="Variable issues",
                        status="completed",
                        findings=(
                            AnalysisFinding(
                                kind="unused",
                                message="declared but never read",
                                module_path=("TargetA", "Charging"),
                                data={"context": "Spare", "previous_sites": ["SQ:Run > STEP:Start:ENTER"]},
                            ),
                        ),
                    ),
                    RunAnalyzerRecord(
                        key="patterns",
                        name="Pattern checks",
                        status="completed",
                        findings=(
                            AnalysisFinding(
                                kind="magic_number",
                                message="magic number 2",
                                module_path=("TargetA", "Charging"),
                            ),
                        ),
                    ),
                ),
            ),
        ),
    )
    summary = RunSummary.from_record(record)

    async def _run() -> None:
        app_instance = make_textual_app(cfg={"analyzed_programs_and_libraries": ["TargetA"]})
        app_instance._project_path = tmp_path / "sattlint-test.slproj"
        monkeypatch.setattr(app_textual_results_module, "list_runs", lambda: (summary,))
        monkeypatch.setattr(app_textual_results_module, "load_run", lambda run_id: record if run_id == "run1" else None)

        async with app_instance.run_test() as pilot:
            await pilot.press("ctrl+2")
            await pilot.pause()

            tree = app_instance._results_tree_widget
            assert tree is not None
            findings_report = app_instance._results_findings_widget
            assert findings_report.id == "results-findings-report"
            root = tree.root.children[0]
            assert [node.label.plain for node in root.children] == ["Charging (FrameModule)"]
            assert findings_report.renderable.plain == "No findings for this module"

            await pilot.resize_terminal(140, 50)
            tree.select_node(root.children[0])
            await pilot.pause()
            assert "Variable issues\nUnused variable (1)" in findings_report.renderable
            assert "Pattern checks\nMagic number (1)" in findings_report.renderable
            assert findings_report.renderable.spans
            assert "declared but never read" not in findings_report.renderable.plain
            detail_line = findings_report.renderable.plain.splitlines().index("  Details")
            assert await pilot.click(findings_report, offset=(4, detail_line))
            await pilot.pause()
            assert "declared but never read" in findings_report.renderable.plain
            assert "Previous write: Run \u203a Start \u203a Enter" in findings_report.renderable.plain
            await pilot.click(findings_report, offset=(4, detail_line))
            await pilot.pause()
            assert "declared but never read" not in findings_report.renderable.plain

            tree.select_node(root)
            await pilot.pause()
            assert findings_report.renderable.plain == "No findings for this module"

    asyncio.run(_run())


def test_textual_analysis_completion_switches_to_results_view(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    record = RunRecord(
        run_id="run9",
        started_at="s",
        finished_at="f",
        project_tag="TargetA",
        project_path=str(tmp_path / "sattlint-test.slproj"),
    )
    summary = RunSummary.from_record(record)

    async def _run() -> None:
        app_instance = make_textual_app(cfg={"analyzed_programs_and_libraries": ["TargetA"]})
        app_instance._project_path = tmp_path / "sattlint-test.slproj"
        monkeypatch.setattr(app_textual_results_module, "list_runs", lambda: (summary,))
        monkeypatch.setattr(app_textual_results_module, "load_run", lambda _run_id: record)

        async with app_instance.run_test() as pilot:
            assert app_instance._active_view == "analyze"

            result = SimpleNamespace(
                output_lines=("=== Target: TargetA ===", "state inference summary"),
                targets=(),
                selected_analyzers=("state-inference",),
                run_id="run9",
            )
            app_instance._finish_analysis_run(result)
            await pilot.pause()

            assert app_instance._active_view == "results"
            assert app_instance._selected_run_record is not None
            assert app_instance._selected_run_record.run_id == "run9"

    asyncio.run(_run())
