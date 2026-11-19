# pyright: reportPrivateUsage=false, reportUnknownLambdaType=false, reportUnusedImport=false
"""Analyzer selection and the Analyze view."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from sattlint import ui as app_textual
from sattlint.ui import _app_textual_analyze as app_textual_analyze_module
from tests.helpers.app_textual_support import (  # noqa: F401  (autouse fixtures)
    isolate_app_config_path,
    isolate_textual_projects,
    make_textual_app,
)


def test_textual_select_all_analyzers_selects_all_visible() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = make_textual_app(
            cfg={"analyzed_programs_and_libraries": ["TargetA"]},
            get_enabled_analyzers_fn=lambda: [
                SimpleNamespace(key="comment-code", name="Commented out code", description="", category="code-quality"),
                SimpleNamespace(
                    key="timing", name="Timing", description="Scan-cycle timing hazards.", category="correctness"
                ),
            ],
        )

        async with app_instance.run_test() as pilot:
            await pilot.pause()

            app_instance.on_button_pressed(SimpleNamespace(button=SimpleNamespace(id="analyze-select-all")))
            await pilot.pause()

            assert app_instance._analyze_selected_entry_ids == {"comment-code", "timing"}
            selection_list = app_instance.query_one("#analyze-section-analyzers")
            assert set(selection_list.selected) == {"comment-code", "timing"}
            assert app_instance.query_one("#analyze-run-selected").disabled is False

    asyncio.run(_run())


def test_textual_select_all_analyzers_is_noop_without_analyzers() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = make_textual_app(
            cfg={"analyzed_programs_and_libraries": ["TargetA"]},
            get_enabled_analyzers_fn=lambda: [],
        )

        async with app_instance.run_test() as pilot:
            await pilot.pause()

            app_instance.on_button_pressed(SimpleNamespace(button=SimpleNamespace(id="analyze-select-all")))
            await pilot.pause()

            assert app_instance._analyze_selected_entry_ids == set()
            output_text = getattr(app_instance.query_one("#output"), "text", "")
            assert "No analyzers are available to select" in output_text

    asyncio.run(_run())


def test_textual_analyze_filter_section_title_and_clear_filter_button() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = make_textual_app(
            cfg={"analyzed_programs_and_libraries": ["TargetA"]},
            get_enabled_analyzers_fn=lambda: [
                SimpleNamespace(key="comment-code", name="Commented out code", description="", category="code-quality"),
                SimpleNamespace(
                    key="timing", name="Timing", description="Scan-cycle timing hazards.", category="correctness"
                ),
            ],
        )

        async with app_instance.run_test() as pilot:
            await pilot.pause()

            app_instance.on_button_pressed(SimpleNamespace(button=SimpleNamespace(id="analyze-select-all")))
            await pilot.pause()
            assert app_instance._analyze_selected_entry_ids == {"comment-code", "timing"}

            app_instance._set_analyze_filter_text("timing")
            await pilot.pause()

            title_text = str(app_instance.query_one("#analyze-section-title").renderable)
            assert 'Filter: "timing"' in title_text
            assert app_instance.query_one("#analyze-clear-filter") is not None
            assert app_instance._analyzer_entry_ids() == ("timing",)
            # Filtering changes what is visible, not what is selected.
            assert app_instance._analyze_selected_entry_ids == {"comment-code", "timing"}
            assert app_instance._selected_analyzer_keys() == ("comment-code", "timing")

            app_instance.on_button_pressed(SimpleNamespace(button=SimpleNamespace(id="analyze-clear-filter")))
            await pilot.pause()

            assert app_instance._analyze_filter_text == ""
            assert "Filter:" not in str(app_instance.query_one("#analyze-section-title").renderable)
            assert len(list(app_instance.query("#analyze-clear-filter"))) == 0
            assert set(app_instance._analyzer_entry_ids()) == {"comment-code", "timing"}
            assert set(app_instance.query_one("#analyze-section-analyzers").selected) == {"comment-code", "timing"}

    asyncio.run(_run())


def test_textual_startup_focuses_analyzer_list_when_project_loaded() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = make_textual_app(
            cfg={"analyzed_programs_and_libraries": ["TargetA"]},
            get_enabled_analyzers_fn=lambda: [
                SimpleNamespace(key="comment-code", name="Commented out code", description="", category="code-quality"),
            ],
        )

        async with app_instance.run_test() as pilot:
            await pilot.pause()

            focused = getattr(app_instance, "focused", None)
            assert focused is not None
            assert getattr(focused, "id", None) == "analyze-section-analyzers"

    asyncio.run(_run())


def test_textual_analyze_view_shows_analyzer_controls() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = make_textual_app(cfg={"analyzed_programs_and_libraries": []})

        async with app_instance.run_test() as pilot:
            await pilot.pause()

            workspace_host = app_instance.query_one("#workspace-host")
            view_title = app_instance.query_one("#view-title")
            view_host = app_instance.query_one("#view-host")
            output_pane = app_instance.query_one("#output-pane")
            output_widget = app_instance.query_one("#output")
            analyze_left = app_instance.query_one("#analyze-browser-left")

            assert app_instance._active_view == "analyze"
            assert workspace_host.has_class("analyze-split")
            assert workspace_host.has_class("no-output") is False
            assert str(view_title.renderable) == "Analyze"
            assert view_title.region.bottom <= view_host.region.y
            assert view_host.size.height > 0
            assert output_pane.size.height > 0
            assert output_widget.size.height > 0
            assert analyze_left.size.height > 0
            assert output_pane.region.x > app_instance.query_one("#analyze-browser").region.x
            assert output_pane.region.width > 0
            assert getattr(output_widget, "read_only", False) is True
            assert getattr(output_widget, "show_line_numbers", True) is False
            assert "Welcome to SattLint." in getattr(output_widget, "text", "")
            assert app_instance.query_one("#analyze-actions-primary").has_class("is-hidden") is False
            assert app_instance.query_one("#analyze-browser").has_class("is-hidden") is False
            assert app_instance.query_one("#view-side-actions") is not None
            assert getattr(app_instance.query_one("#analyze-run-selected"), "disabled", False) is True
            assert getattr(app_instance.query_one("#analyze-clear-selection"), "disabled", False) is True
            assert str(app_instance.query_one("#view-note").renderable) == (
                "No analysis targets are configured yet. Add one in Setup first. Press / to filter the analyzers."
            )
            assert len(list(app_instance.query("#analyze-section-top-level"))) == 0
            assert len(list(app_instance.query("#analyze-section-variable-suite"))) == 0
            assert str(app_instance.query_one("#output-title").renderable) == "Session output"

            assert len(list(app_instance.query("#analyze-detail"))) == 0

    asyncio.run(_run())


def test_textual_analyze_view_keeps_analyzer_panes_visible_on_small_terminal() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = make_textual_app(cfg={"analyzed_programs_and_libraries": []})

        async with app_instance.run_test(size=(80, 20)) as pilot:
            await pilot.pause()

            analyze_left = app_instance.query_one("#analyze-browser-left")
            output_widget = app_instance.query_one("#output")

            assert analyze_left.size.height >= 2
            assert output_widget.size.height > 0

    asyncio.run(_run())


def test_textual_analyze_selection_lists_expand_instead_of_scrolling_individually() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = make_textual_app(
            cfg={"analyzed_programs_and_libraries": ["TargetA"]},
            get_enabled_analyzers_fn=lambda: [
                SimpleNamespace(
                    key=f"analyzer-{index}",
                    name=f"Analyzer {index}",
                    description=f"Description {index}",
                    category="correctness",
                )
                for index in range(12)
            ],
        )

        async with app_instance.run_test(size=(80, 18)) as pilot:
            await pilot.pause()

            analyze_left = app_instance.query_one("#analyze-browser-left")
            analyzers_list = app_instance.query_one("#analyze-section-analyzers")

            assert analyze_left.virtual_size.height > analyze_left.size.height
            assert analyzers_list.size.height >= analyzers_list.virtual_size.height

    asyncio.run(_run())


def test_textual_analyze_header_buttons_fit_without_clipping() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = make_textual_app(cfg={"analyzed_programs_and_libraries": ["TargetA"]})

        async with app_instance.run_test(size=(80, 24)) as pilot:
            await pilot.pause()

            run_button = app_instance.query_one("#analyze-run-selected")
            clear_button = app_instance.query_one("#analyze-clear-selection")

            assert run_button.region.width >= run_button.virtual_size.width
            assert clear_button.region.width >= clear_button.virtual_size.width

    asyncio.run(_run())


def test_textual_analyze_selection_styles_hide_unselected_marker_and_highlight_current_row() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = make_textual_app(
            cfg={"analyzed_programs_and_libraries": ["TargetA"]},
            get_enabled_analyzers_fn=lambda: [
                SimpleNamespace(
                    key="comment-code",
                    name="Commented-out code",
                    description="Detect commented-out code.",
                    category="code-quality",
                )
            ],
        )

        async with app_instance.run_test() as pilot:
            await pilot.pause()

            selection_list = app_instance.query_one("#analyze-section-analyzers")
            option_style = selection_list.get_component_rich_style("option-list--option")
            option_highlighted_style = selection_list.get_component_rich_style("option-list--option-highlighted")
            unselected_button_style = selection_list.get_component_rich_style("selection-list--button")
            highlighted_button_style = selection_list.get_component_rich_style("selection-list--button-highlighted")
            selected_button_style = selection_list.get_component_rich_style("selection-list--button-selected")
            selected_highlighted_button_style = selection_list.get_component_rich_style(
                "selection-list--button-selected-highlighted"
            )

            assert unselected_button_style.color is not None
            assert unselected_button_style.bgcolor is not None
            assert highlighted_button_style.color is not None
            assert highlighted_button_style.bgcolor is not None
            assert option_style.color is not None
            assert option_style.bgcolor is not None
            assert option_highlighted_style.color is not None
            assert option_highlighted_style.bgcolor is not None
            assert selected_button_style.color is not None
            assert selected_button_style.bgcolor is not None
            assert selected_highlighted_button_style.color is not None
            assert selected_highlighted_button_style.bgcolor is not None

            assert unselected_button_style.color.triplet == option_style.bgcolor.triplet
            assert unselected_button_style.bgcolor.triplet == option_style.bgcolor.triplet
            assert highlighted_button_style.color.triplet == option_highlighted_style.bgcolor.triplet
            assert highlighted_button_style.bgcolor.triplet == option_highlighted_style.bgcolor.triplet
            assert selected_button_style.color.triplet == option_style.color.triplet
            assert selected_button_style.bgcolor.triplet == option_style.bgcolor.triplet
            assert selected_highlighted_button_style.color.triplet == option_style.color.triplet
            assert selected_highlighted_button_style.bgcolor.triplet == option_highlighted_style.bgcolor.triplet
            assert option_highlighted_style.color.triplet == option_style.color.triplet
            assert option_highlighted_style.bgcolor.triplet != option_style.bgcolor.triplet

    asyncio.run(_run())


def test_textual_analyze_renders_single_section_and_detail() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = make_textual_app(
            get_enabled_analyzers_fn=lambda: [
                SimpleNamespace(
                    key="timing",
                    name="Timing",
                    description="Scan-cycle timing hazards",
                    category="correctness",
                ),
            ],
            analysis_handlers={"_run_checks": lambda _cfg, _selected_keys: None},
        )

        async with app_instance.run_test() as pilot:
            await pilot.pause()

            assert len(list(app_instance.query("#analyze-section-top-level"))) == 0
            assert len(list(app_instance.query("#analyze-section-variable-suite"))) == 0
            assert len(list(app_instance.query("#analyze-section-investigation"))) == 0
            assert app_instance.query_one("#analyze-section-analyzers") is not None
            assert len(list(app_instance.query("#analyze-section-catalog-issue-checks"))) == 0
            assert len(list(app_instance.query("#analyze-section-catalog-analyzers"))) == 0
            assert "timing" in app_instance._analyzer_entry_ids()

            app_instance._analyze_focused_entry_id = "timing"
            app_instance._write_focused_entry_to_output()
            await pilot.pause()
            output_text = getattr(app_instance.query_one("#output"), "text", "")
            assert "Analyzer: Timing" in output_text
            assert "Description:" in output_text

    asyncio.run(_run())


def test_textual_analyze_selection_updates_summary_and_enables_run() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = make_textual_app(
            get_enabled_analyzers_fn=lambda: [
                SimpleNamespace(
                    key="timing",
                    name="Timing",
                    description="Scan-cycle timing hazards",
                    category="correctness",
                ),
                SimpleNamespace(
                    key="state-inference",
                    name="State inference",
                    description="Detect incorrect state inference.",
                    category="correctness",
                ),
            ],
            analysis_handlers={"_run_checks": lambda _cfg, _selected_keys: None},
        )

        async with app_instance.run_test() as pilot:
            await pilot.pause()

            analyzers_list = app_instance.query_one("#analyze-section-analyzers")

            analyzers_list.select("timing")
            analyzers_list.select("state-inference")
            app_instance._sync_analyze_selection_from_selection_list(analyzers_list)
            app_instance._write_focused_entry_to_output()
            app_instance._refresh_shell_state()
            await pilot.pause()

            output_text = getattr(app_instance.query_one("#output"), "text", "")
            assert "Analyzer:" in output_text
            assert "Description:" in output_text
            assert getattr(app_instance.query_one("#analyze-run-selected"), "disabled", True) is False

    asyncio.run(_run())


def test_textual_analyze_clear_selection_resets_analyze_state() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = make_textual_app(
            get_enabled_analyzers_fn=lambda: [
                SimpleNamespace(
                    key="comment-code",
                    name="Commented-out code",
                    description="Detect commented-out code.",
                    category="code-quality",
                ),
            ],
            analysis_handlers={"run_checks_result": lambda _cfg: None},
        )

        async with app_instance.run_test() as pilot:
            await pilot.pause()

            analyzers_list = app_instance.query_one("#analyze-section-analyzers")
            analyzers_list.select("comment-code")
            app_instance._sync_analyze_selection_from_selection_list(analyzers_list)
            app_instance._write_focused_entry_to_output()
            app_instance._refresh_shell_state()
            await pilot.pause()

            assert app_instance._analyze_selected_entry_ids == {"comment-code"}
            assert getattr(app_instance.query_one("#analyze-clear-selection"), "disabled", True) is False

            app_instance.on_button_pressed(SimpleNamespace(button=SimpleNamespace(id="analyze-clear-selection")))
            await pilot.pause()

            assert app_instance._analyze_selected_entry_ids == set()
            assert getattr(app_instance.query_one("#analyze-clear-selection"), "disabled", False) is True

    asyncio.run(_run())


def test_textual_analyze_clear_output_clears_session_log_only() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = make_textual_app(
            get_enabled_analyzers_fn=lambda: [
                SimpleNamespace(
                    key="comment-code",
                    name="Commented-out code",
                    description="Detect commented-out code.",
                    category="code-quality",
                ),
            ],
            analysis_handlers={"run_checks_result": lambda _cfg: None},
        )

        async with app_instance.run_test() as pilot:
            await pilot.pause()

            analyzers_list = app_instance.query_one("#analyze-section-analyzers")
            analyzers_list.select("comment-code")
            app_instance._sync_analyze_selection_from_selection_list(analyzers_list)
            app_instance._write_focused_entry_to_output()
            app_instance._refresh_shell_state()
            app_instance._write_output("extra output")
            await pilot.pause()

            assert "comment-code" in app_instance._analyze_selected_entry_ids
            assert "Analyzer: Commented-out code" in getattr(app_instance.query_one("#output"), "text", "")

            app_instance.on_button_pressed(SimpleNamespace(button=SimpleNamespace(id="analyze-clear-output")))
            await pilot.pause()

            assert getattr(app_instance.query_one("#output"), "text", "") == ""
            assert "comment-code" in app_instance._analyze_selected_entry_ids
            assert str(app_instance.query_one("#output-title").renderable) == "Session output"

    asyncio.run(_run())


def test_textual_analyze_clear_selection_also_clears_output() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = make_textual_app(
            get_enabled_analyzers_fn=lambda: [
                SimpleNamespace(
                    key="comment-code",
                    name="Commented-out code",
                    description="Detect commented-out code.",
                    category="code-quality",
                ),
            ],
            analysis_handlers={"run_checks_result": lambda _cfg: None},
        )

        async with app_instance.run_test() as pilot:
            await pilot.pause()

            analyzers_list = app_instance.query_one("#analyze-section-analyzers")
            analyzers_list.select("comment-code")
            app_instance._sync_analyze_selection_from_selection_list(analyzers_list)
            app_instance._write_focused_entry_to_output()
            app_instance._refresh_shell_state()
            app_instance._write_output("extra output")
            await pilot.pause()

            assert "comment-code" in app_instance._analyze_selected_entry_ids
            assert getattr(app_instance.query_one("#output"), "text", "") != ""

            app_instance.on_button_pressed(SimpleNamespace(button=SimpleNamespace(id="analyze-clear-selection")))
            await pilot.pause()

            assert app_instance._analyze_selected_entry_ids == set()
            output_text = getattr(app_instance.query_one("#output"), "text", "")
            assert "Analyzer: Commented-out code" not in output_text
            assert "extra output" not in output_text
            assert "Cleared the analyzer selection" in output_text

    asyncio.run(_run())


def test_textual_analyze_view_does_not_compose_secondary_actions_row() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = make_textual_app(cfg={"analyzed_programs_and_libraries": ["TargetA"]})

        async with app_instance.run_test(size=(80, 24)) as pilot:
            await pilot.pause()

            assert app_instance.query_one("#analyze-actions-primary") is not None
            assert len(list(app_instance.query("#analyze-actions-secondary"))) == 0

    asyncio.run(_run())


def test_textual_unchanged_analyzer_options_keep_the_list_scroll() -> None:
    app_instance = make_textual_app()
    items = (app_textual_analyze_module._AnalyzerItem("a", "A", "", "correctness"),)

    class ListStub:
        highlighted = 0

        def __init__(self) -> None:
            self.clear_count = 0

        def clear_options(self) -> None:
            self.clear_count += 1

        def add_options(self, _options: object) -> None:
            return None

    stub = ListStub()

    app_instance._update_analyze_selection_list(stub, items)
    app_instance._update_analyze_selection_list(stub, items)

    assert stub.clear_count == 1
