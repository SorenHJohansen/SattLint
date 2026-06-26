# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownLambdaType=false, reportPrivateUsage=false, reportUnknownArgumentType=false, reportOptionalCall=false

from __future__ import annotations

import asyncio
import io
import re
import threading
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from rich.console import Console
from rich.rule import Rule
from rich.text import Text

from sattlint import _app_textual_actions as app_textual_actions_module
from sattlint import _app_textual_app as app_textual_module
from sattlint import _app_textual_setup as app_textual_setup_module
from sattlint import _app_textual_shared as app_textual_shared_module
from sattlint import _app_textual_widgets as app_textual_widgets_module
from sattlint import app, app_textual
from sattlint.config_types import ConfigDict


def _typed_cfg(value: dict[str, Any]) -> ConfigDict:
    return cast(ConfigDict, value)


def _query_any_screen(app_instance: Any, selector: str) -> Any:
    try:
        return app_instance.query_one(selector)
    except app_textual_shared_module._TEXTUAL_QUERY_ERRORS as exc:
        last_error: BaseException = exc

    screen_stack = getattr(app_instance, "screen_stack", None)
    if screen_stack is None:
        screen_stack = getattr(app_instance, "_screen_stack", ())

    for screen in reversed(tuple(screen_stack)):
        query_one = getattr(screen, "query_one", None)
        if not callable(query_one):
            continue
        try:
            return query_one(selector)
        except app_textual_shared_module._TEXTUAL_QUERY_ERRORS as exc:
            last_error = exc

    raise last_error


def _renderable_text(renderable: object) -> str:
    if isinstance(renderable, str):
        return renderable
    if isinstance(renderable, Text):
        return renderable.plain
    buffer = io.StringIO()
    console = Console(file=buffer, force_terminal=False, color_system=None, width=120)
    console.print(renderable)
    return buffer.getvalue()


def test_textual_interaction_bridge_returns_responses() -> None:
    seen_kinds: list[str] = []

    def _submit(request: app_textual_shared_module.InteractionRequest) -> None:
        seen_kinds.append(request.kind)
        if request.kind == "menu":
            request.result_future.set_result("2")
        elif request.kind == "prompt":
            request.result_future.set_result("value")
        elif request.kind == "confirm":
            request.result_future.set_result(True)
        else:
            request.result_future.set_result(None)

    bridge = app_textual.TextualInteractionBridge(submit_request_fn=_submit)

    assert bridge.choose_menu_option("Menu", []) == "2"
    assert bridge.prompt("Name") == "value"
    assert bridge.confirm("Confirm?") is True
    bridge.pause()
    assert seen_kinds == ["menu", "prompt", "confirm"]


def test_textual_interaction_bridge_async_returns_responses() -> None:
    seen_kinds: list[str] = []

    def _submit(request: app_textual_shared_module.InteractionRequest) -> None:
        seen_kinds.append(request.kind)
        if request.kind == "menu":
            request.result_future.set_result("2")
        elif request.kind == "prompt":
            request.result_future.set_result("value")
        elif request.kind == "confirm":
            request.result_future.set_result(True)
        else:
            request.result_future.set_result(None)

    bridge = app_textual.TextualInteractionBridge(submit_request_fn=_submit)

    async def _run() -> None:
        assert await bridge.choose_menu_option_async("Menu", []) == "2"
        assert await bridge.prompt_async("Name") == "value"
        assert await bridge.confirm_async("Confirm?") is True
        await bridge.pause_async()

    asyncio.run(_run())

    assert seen_kinds == ["menu", "prompt", "confirm"]


def test_app_input_wrappers_use_textual_interaction_bridge() -> None:
    calls: list[tuple[str, object, object]] = []

    interaction = SimpleNamespace(
        pause=lambda: calls.append(("pause", None, None)),
        prompt=lambda message, default=None: calls.append(("prompt", message, default)) or "value",
        confirm=lambda message: calls.append(("confirm", message, None)) or True,
    )

    app.set_interactive_ui_mode("textual")
    app.set_textual_menu_interaction(interaction)
    try:
        app.pause()
        assert app.prompt("Name", "default") == "value"
        assert app.confirm("Continue?") is True
    finally:
        app.reset_interactive_ui_mode()

    assert calls == [
        ("pause", None, None),
        ("prompt", "Name", "default"),
        ("confirm", "Continue?", None),
    ]


def test_app_clear_screen_is_noop_with_textual_interaction(monkeypatch: pytest.MonkeyPatch) -> None:
    clear_calls: list[str] = []

    monkeypatch.setattr(app.app_base, "clear_screen", lambda **_kwargs: clear_calls.append("clear"))

    app.set_interactive_ui_mode("textual")
    app.set_textual_menu_interaction(SimpleNamespace())
    try:
        app.clear_screen()
    finally:
        app.reset_interactive_ui_mode()

    assert clear_calls == []


def test_run_interactive_session_dispatches_to_textual_shell(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}
    app.set_interactive_ui_mode("textual")

    def _fake_run_textual_shell(cfg: dict[str, Any], *, app_module: Any, **kwargs: Any) -> None:
        seen.update({"cfg": cfg, "app_module": app_module, **kwargs})

    def _summarize_targets(_cfg: dict[str, Any]) -> str:
        return "targets"

    monkeypatch.setattr(
        app_textual,
        "run_textual_shell",
        _fake_run_textual_shell,
    )

    try:
        app.run_interactive_session(_typed_cfg({"debug": False}), summarize_targets_fn=_summarize_targets)
    finally:
        app.reset_interactive_ui_mode()

    assert seen["cfg"] == {"debug": False}
    assert seen["app_module"] is app


def test_run_textual_shell_refreshes_ast_cache_before_main_app(monkeypatch: pytest.MonkeyPatch) -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    seen: list[tuple[str, object]] = []

    class FakeLoadingApp:
        def __init__(self, *, refresh_ast_cache_fn: Any) -> None:
            seen.append(("loading-init", refresh_ast_cache_fn is not None))
            self._refresh_ast_cache_fn = refresh_ast_cache_fn

        def run(self) -> None:
            seen.append(("loading-run", True))
            self._refresh_ast_cache_fn(lambda message: seen.append(("loading-status", message)))

    class FakeMainApp:
        def __init__(self, **kwargs: Any) -> None:
            seen.append(("main-init", kwargs["cfg"]))

        def call_from_thread(self, callback: Any, request: Any) -> None:
            callback(request)

        def run(self) -> None:
            seen.append(("main-run", True))

    app_module = SimpleNamespace(
        self_check=lambda _cfg: True,
        dump_menu=lambda _cfg: None,
        run_source_diff_report=lambda _cfg, _pause_fn=None: None,
        force_refresh_ast=lambda _cfg: None,
        refresh_analysis_caches=lambda _cfg: None,
        _has_analyzed_targets=lambda _cfg: True,
        ensure_ast_cache=lambda _cfg, *, emit_output_fn=None: (
            (emit_output_fn("Checking AST cache for Demo") if emit_output_fn is not None else None) or True
        ),
        set_textual_menu_interaction=lambda interaction: seen.append(("set-interaction", interaction is not None)),
        clear_textual_menu_interaction=lambda: seen.append(("clear-interaction", True)),
    )

    monkeypatch.setattr(app_textual_module, "_AstRefreshTextualApp", FakeLoadingApp)
    monkeypatch.setattr(app_textual_module, "SattLintTextualApp", FakeMainApp)

    app_textual.run_textual_shell(
        _typed_cfg({"debug": False}),
        app_module=app_module,
        summarize_targets_fn=lambda _cfg: "targets",
        show_help_fn=lambda _cfg: None,
        save_config_fn=lambda _path, _cfg: None,
        config_path=Path("config.toml"),
        quit_app_error=RuntimeError,
    )

    assert seen[:4] == [
        ("loading-init", True),
        ("loading-run", True),
        ("loading-status", "Checking AST cache for Demo"),
        ("main-init", {"debug": False}),
    ]
    assert ("main-run", True) in seen
    assert any(event == "set-interaction" for event, _value in seen)
    assert seen[-1] == ("clear-interaction", True)


def test_textual_ast_refresh_screen_records_exception_and_allows_continue(monkeypatch: pytest.MonkeyPatch) -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    status_updates: list[str] = []
    exited: list[str] = []

    loading_app = app_textual_module._AstRefreshTextualApp(
        refresh_ast_cache_fn=lambda _emit_status: (_ for _ in ()).throw(RuntimeError("boom"))
    )

    monkeypatch.setattr(
        loading_app,
        "query_one",
        lambda *_args, **_kwargs: SimpleNamespace(update=lambda text: status_updates.append(str(text))),
    )
    monkeypatch.setattr(loading_app, "call_from_thread", lambda callback, *args, **kwargs: callback(*args, **kwargs))
    monkeypatch.setattr(loading_app, "exit", lambda: exited.append("exit"))

    loading_app._run_refresh()

    assert exited == []
    assert loading_app._refresh_failed is True
    assert isinstance(loading_app._refresh_exception, RuntimeError)
    assert "AST cache refresh failed: boom" in status_updates[-1]
    assert "Press Enter or Escape to continue into the shell." in status_updates[-1]

    loading_app.on_key(SimpleNamespace(key="enter", prevent_default=lambda: None))

    assert exited == ["exit"]


def test_textual_ast_refresh_screen_propagates_type_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    loading_app = app_textual_module._AstRefreshTextualApp(
        refresh_ast_cache_fn=lambda _emit_status: (_ for _ in ()).throw(TypeError("bad refresh wiring"))
    )

    monkeypatch.setattr(
        loading_app,
        "query_one",
        lambda *_args, **_kwargs: SimpleNamespace(update=lambda _text: None),
    )
    monkeypatch.setattr(loading_app, "call_from_thread", lambda callback, *args, **kwargs: callback(*args, **kwargs))

    with pytest.raises(TypeError, match="bad refresh wiring"):
        loading_app._run_refresh()

    assert loading_app._refresh_failed is True
    assert loading_app._refresh_exception is None


def test_run_textual_shell_preserves_ast_cache_failure_log(monkeypatch: pytest.MonkeyPatch) -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    seen: dict[str, Any] = {}

    class FakeLoadingApp:
        def __init__(self, *, refresh_ast_cache_fn: Any) -> None:
            self._refresh_ast_cache_fn = refresh_ast_cache_fn
            self._status_lines: list[str] = ["Starting cached AST refresh..."]
            self._refresh_failed = False

        def run(self) -> None:
            collected_lines: list[str] = []

            def _collect(message: str) -> None:
                normalized = message.replace("\r\n", "\n").replace("\r", "\n")
                collected_lines.extend(normalized.split("\n"))

            refresh_ok = bool(self._refresh_ast_cache_fn(_collect))
            self._status_lines.extend(collected_lines)
            self._refresh_failed = not refresh_ok

    class FakeMainApp:
        def __init__(self, **kwargs: Any) -> None:
            seen["startup_output"] = kwargs["startup_output"]
            seen["startup_output_is_warning"] = kwargs["startup_output_is_warning"]

        def call_from_thread(self, callback: Any, request: Any) -> None:
            callback(request)

        def run(self) -> None:
            seen["main_run"] = True

    app_module = SimpleNamespace(
        self_check=lambda _cfg: True,
        dump_menu=lambda _cfg: None,
        run_source_diff_report=lambda _cfg, _pause_fn=None: None,
        force_refresh_ast=lambda _cfg: None,
        refresh_analysis_caches=lambda _cfg: None,
        _has_analyzed_targets=lambda _cfg: True,
        ensure_ast_cache=lambda _cfg, *, emit_output_fn=None: (
            [emit_output_fn(f"line {index}") for index in range(1, 7)] and False
        ),
        set_textual_menu_interaction=lambda _interaction: None,
        clear_textual_menu_interaction=lambda: None,
    )

    monkeypatch.setattr(app_textual_module, "_AstRefreshTextualApp", FakeLoadingApp)
    monkeypatch.setattr(app_textual_module, "SattLintTextualApp", FakeMainApp)

    app_textual.run_textual_shell(
        _typed_cfg({"debug": False}),
        app_module=app_module,
        summarize_targets_fn=lambda _cfg: "targets",
        show_help_fn=lambda _cfg: None,
        save_config_fn=lambda _path, _cfg: None,
        config_path=Path("config.toml"),
        quit_app_error=RuntimeError,
    )

    assert seen["startup_output_is_warning"] is True
    assert "line 1" in seen["startup_output"]
    assert "line 6" in seen["startup_output"]
    assert seen["main_run"] is True


def test_resolve_interactive_ui_mode_requires_textual(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(app_textual, "has_textual", lambda: False)

    with pytest.raises(RuntimeError, match="Textual is required"):
        app.resolve_interactive_ui_mode(_typed_cfg({}), "textual")


def test_resolve_interactive_ui_mode_rejects_non_textual_override() -> None:
    with pytest.raises(ValueError, match="Textual-only"):
        app.resolve_interactive_ui_mode(_typed_cfg({}), "rich")


def test_resolve_interactive_ui_mode_defaults_to_textual_when_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SATTLINT_UI", raising=False)
    monkeypatch.setattr(app_textual, "has_textual", lambda: True)

    assert app.resolve_interactive_ui_mode(_typed_cfg({}), None) == "textual"


def test_advance_menu_choice_buffer_waits_for_enter_on_ambiguous_single_digit() -> None:
    option_keys = ("2", "23", "24", "b")

    choice_buffer, resolved = app_textual.advance_menu_choice_buffer("", "2", option_keys)

    assert choice_buffer == "2"
    assert resolved is None


def test_advance_menu_choice_buffer_resolves_unique_multi_digit_choice() -> None:
    option_keys = ("2", "23", "24", "b")

    choice_buffer, resolved = app_textual.advance_menu_choice_buffer("2", "3", option_keys)

    assert choice_buffer == ""
    assert resolved == "23"


def test_discover_setup_target_candidates_collects_preview_files(tmp_path: Path) -> None:
    program_dir = tmp_path / "programs"
    abb_dir = tmp_path / "abb"
    program_dir.mkdir()
    abb_dir.mkdir()
    (program_dir / "TargetA.s").write_text("draft")
    (program_dir / "TargetA.l").write_text("deps")
    (abb_dir / "TargetA.x").write_text("official")
    (abb_dir / "TargetB.s").write_text("draft-only")

    candidates = app_textual.discover_setup_target_candidates(
        _typed_cfg(
            {
                "program_dir": str(program_dir),
                "ABB_lib_dir": str(abb_dir),
                "other_lib_dirs": [],
                "mode": "official",
            }
        )
    )

    assert [candidate.name for candidate in candidates] == ["TargetA", "TargetB"]
    assert [path.name for path in candidates[0].files] == ["TargetA.l", "TargetA.s", "TargetA.x"]
    assert candidates[0].available is True
    assert candidates[1].available is False


def test_interaction_ledger_text_mentions_multi_digit_entry() -> None:
    request = app_textual_shared_module.InteractionRequest(
        kind="menu",
        title="Variable issues",
        options=(SimpleNamespace(key="23", label="Datatype usage analysis", description=""),),
    )

    ledger = app_textual.interaction_ledger_text(request, "2")

    assert "Type a menu key and press Enter" in ledger
    assert "Current choice: 2" in ledger


def test_resolve_shell_title_prefers_runtime_title() -> None:
    assert app_textual.resolve_shell_title("Custom title") == "Custom title"
    assert app_textual.resolve_shell_title(SimpleNamespace(title="LIRA")) == "LIRA"


def test_resolve_shell_title_falls_back_to_default_banner_title() -> None:
    assert app_textual.resolve_shell_title(None) == app_textual.DEFAULT_SHELL_TITLE
    assert app_textual.resolve_shell_title(SimpleNamespace(title="")) == app_textual.DEFAULT_SHELL_TITLE


def test_textual_shell_css_mentions_banner_and_full_width_menu_buttons() -> None:
    css = app_textual.TEXTUAL_SHELL_CSS

    assert "#actions" in app_textual.TEXTUAL_SHELL_CSS
    assert "#view-header" in app_textual.TEXTUAL_SHELL_CSS
    assert "#view-copy" in app_textual.TEXTUAL_SHELL_CSS
    assert "#view-side-actions" in app_textual.TEXTUAL_SHELL_CSS
    assert "overflow-y: auto;" in app_textual.TEXTUAL_SHELL_CSS
    assert "#content-host" in app_textual.TEXTUAL_SHELL_CSS
    assert "#workspace-host" in app_textual.TEXTUAL_SHELL_CSS
    assert "#view-pane" in app_textual.TEXTUAL_SHELL_CSS
    assert "#view-host" in app_textual.TEXTUAL_SHELL_CSS
    assert "#output-pane" in app_textual.TEXTUAL_SHELL_CSS
    assert "#analyze-browser" in app_textual.TEXTUAL_SHELL_CSS
    assert "#analyze-actions-primary" in app_textual.TEXTUAL_SHELL_CSS
    assert "#documentation-actions" in app_textual.TEXTUAL_SHELL_CSS
    assert "#setup-browser" in app_textual.TEXTUAL_SHELL_CSS
    assert "#interaction-host" in app_textual.TEXTUAL_SHELL_CSS
    assert "#interaction-screen" in app_textual.TEXTUAL_SHELL_CSS
    assert "Button.raised-button" in app_textual.TEXTUAL_SHELL_CSS
    assert "#interaction-options Button.raised-button" in app_textual.TEXTUAL_SHELL_CSS
    assert "#actions Button.toolbar-button" in app_textual.TEXTUAL_SHELL_CSS
    assert ".selection-list--button-selected" in app_textual.TEXTUAL_SHELL_CSS
    assert "outline: none;" in app_textual.TEXTUAL_SHELL_CSS
    assert "width: 100%;" in app_textual.TEXTUAL_SHELL_CSS
    assert "}Screen {" not in css

    for selector in (
        "Screen",
        "Footer",
        "#content-host",
        "#workspace-host",
        "#view-pane",
        "#view-header",
        "#view-host",
        "#output-pane",
        "#analyze-browser",
        "#setup-browser",
        "#interaction-screen",
    ):
        assert len(re.findall(rf"(?m)^\s*{re.escape(selector)} " + r"\{", css)) == 1

    assert re.search(r"(?ms)^\s*#view-host \{.*?^\s*padding: 1 2;.*?^\s*\}", css)
    assert re.search(
        r"(?ms)^\s*#workspace-host\.analyze-split,\n\s*#workspace-host\.docs-tools-split \{.*?^\s*layout: horizontal;.*?^\s*\}",
        css,
    )
    assert re.search(
        r"(?ms)^\s*#workspace-host\.analyze-split #view-pane,\n\s*#workspace-host\.docs-tools-split #view-pane \{.*?^\s*width: 1fr;.*?^\s*\}",
        css,
    )
    assert re.search(
        r"(?ms)^\s*#workspace-host\.analyze-split #output-pane,\n\s*#workspace-host\.docs-tools-split #output-pane \{.*?^\s*width: 2fr;.*?^\s*\}",
        css,
    )
    assert "wide-output-split" not in css
    assert re.search(r"(?ms)^\s*Screen \{.*?^\s*scrollbar-background: #b9d9df;.*?^\s*\}", css)
    assert re.search(
        r"(?ms)^\s*#workspace-host\.docs-tools-split #view-side-actions \{.*?^\s*overflow-y: auto;.*?^\s*\}", css
    )
    assert re.search(r"(?ms)^\s*#analyze-browser \{.*?^\s*margin-top: 1;.*?^\s*\}", css)
    assert re.search(r"(?ms)^\s*#setup-browser \{.*?^\s*margin-top: 1;.*?^\s*\}", css)
    assert re.search(r"(?ms)^\s*#analyze-planner-detail \{.*?^\s*padding: 1 2;.*?^\s*\}", css)
    assert re.search(r"(?ms)^\s*#analyze-browser-left \{.*?^\s*padding: 1 2;.*?^\s*\}", css)
    assert re.search(r"(?ms)^\s*#setup-targets-col \{.*?^\s*padding: 1 2;.*?^\s*\}", css)
    assert re.search(r"(?ms)^\s*#setup-settings-col \{.*?^\s*padding: 1 2;.*?^\s*\}", css)
    assert re.search(r"(?ms)^\s*#output \{.*?^\s*padding: 1 2;.*?^\s*\}", css)


def test_textual_app_title_defaults_to_banner_title() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    assert app_textual.SattLintTextualApp.TITLE == app_textual.DEFAULT_SHELL_TITLE


def test_textual_top_chrome_removes_banner_and_summary_boxes() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = app_textual.SattLintTextualApp(
            cfg={},
            summarize_targets_fn=lambda _cfg: "targets",
            analysis_menu_fn=lambda _cfg: None,
            documentation_menu_fn=lambda _cfg: None,
            config_menu_fn=lambda _cfg: None,
            tools_menu_fn=lambda _cfg: None,
            show_help_fn=lambda _cfg: None,
            save_config_fn=lambda _path, _cfg: None,
            config_path=None,
            quit_app_error=RuntimeError,
        )

        async with app_instance.run_test() as pilot:
            await pilot.pause()

            assert len(list(app_instance.query("#shell-banner"))) == 0
            assert len(list(app_instance.query("#summary"))) == 0
            assert app_instance.query_one("#action-analyze") is not None

    asyncio.run(_run())


def test_textual_toolbar_is_available_without_summary_box() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = app_textual.SattLintTextualApp(
            cfg={"analyzed_programs_and_libraries": ["Target1", "Target2"]},
            summarize_targets_fn=lambda _cfg: "targets",
            analysis_menu_fn=lambda _cfg: None,
            documentation_menu_fn=lambda _cfg: None,
            config_menu_fn=lambda _cfg: None,
            tools_menu_fn=lambda _cfg: None,
            show_help_fn=lambda _cfg: None,
            save_config_fn=lambda _path, _cfg: None,
            config_path=None,
            quit_app_error=RuntimeError,
        )

        async with app_instance.run_test() as pilot:
            await pilot.pause()

            assert len(list(app_instance.query("#summary"))) == 0
            assert app_instance.query_one("#actions") is not None
            quit_button = app_instance.query_one("#action-quit")
            output_pane = app_instance.query_one("#output-pane")

            assert output_pane.region.right > quit_button.region.x
            assert output_pane.size.width >= 40

    asyncio.run(_run())


def test_textual_quit_keybinding_does_not_crash() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = app_textual.SattLintTextualApp(
            cfg={},
            summarize_targets_fn=lambda _cfg: "targets",
            analysis_menu_fn=lambda _cfg: None,
            documentation_menu_fn=lambda _cfg: None,
            config_menu_fn=lambda _cfg: None,
            tools_menu_fn=lambda _cfg: None,
            show_help_fn=lambda _cfg: None,
            save_config_fn=lambda _path, _cfg: None,
            config_path=None,
            quit_app_error=RuntimeError,
        )

        async with app_instance.run_test() as pilot:
            await pilot.press("q")
            await pilot.pause()

    asyncio.run(_run())


def test_textual_quit_keybinding_prompts_when_setup_is_dirty() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = _make_textual_app()

        async with app_instance.run_test() as pilot:
            await pilot.pause()

            app_instance._dirty = True
            app_instance._refresh_shell_state()
            await pilot.pause()

            await pilot.press("q")
            await pilot.pause()

            assert app_instance.query_one("#interaction-host").has_class("active") is True
            ledger = str(app_instance.query_one("#interaction-ledger").renderable)
            assert "Press Y for yes, N or Esc for no" in ledger

            await pilot.press("n")
            await pilot.pause()

            assert app_instance.query_one("#interaction-host").has_class("active") is False
            assert app_instance._dirty is True
            assert "Quit canceled. Unsaved configuration changes are still pending." in getattr(
                app_instance.query_one("#output"), "text", ""
            )

    asyncio.run(_run())


def test_textual_ctrl_c_copy_binding_copies_session_output() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        copied: list[str] = []
        app_instance = app_textual.SattLintTextualApp(
            cfg={},
            summarize_targets_fn=lambda _cfg: "targets",
            analysis_menu_fn=lambda _cfg: None,
            documentation_menu_fn=lambda _cfg: None,
            config_menu_fn=lambda _cfg: None,
            tools_menu_fn=lambda _cfg: None,
            show_help_fn=lambda _cfg: None,
            save_config_fn=lambda _path, _cfg: None,
            config_path=None,
            quit_app_error=RuntimeError,
        )
        app_instance.copy_to_clipboard = lambda text: copied.append(text)

        async with app_instance.run_test() as pilot:
            await pilot.pause()
            await pilot.press("ctrl+c")
            await pilot.pause()

            output_text = getattr(app_instance.query_one("#output"), "text", "")
            assert copied
            assert "Welcome to SattLint Analyze." in copied[-1]
            assert copied[-1] in getattr(app_instance.query_one("#output"), "text", "")
            assert "Copied all Session output because no text was selected." in output_text

    asyncio.run(_run())


def test_textual_ctrl_l_clear_binding_clears_session_output() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = _make_textual_app()

        async with app_instance.run_test() as pilot:
            await pilot.pause()

            app_instance._write_output("Extra output")
            await pilot.pause()
            assert "Extra output" in getattr(app_instance.query_one("#output"), "text", "")

            await pilot.press("ctrl+l")
            await pilot.pause()

            assert getattr(app_instance.query_one("#output"), "text", "") == ""
            assert app_instance._session_output_lines == []

    asyncio.run(_run())


def test_textual_question_mark_binding_opens_help() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = _make_textual_app()

        async with app_instance.run_test() as pilot:
            await pilot.pause()

            await pilot.press("?")
            await pilot.pause()

            help_dialog = _query_any_screen(app_instance, "#help-dialog")
            help_body = str(_query_any_screen(app_instance, "#help-dialog-body").renderable)
            assert "Keyboard shortcuts" in help_body
            assert "/ filters Analyze and Setup lists" in help_body
            assert "Ctrl+L clears Session output" in help_body
            assert "Ctrl+G cancels a running analysis" in help_body
            assert help_dialog.region.x > 0
            assert help_dialog.region.y > 0
            assert help_dialog.size.width < app_instance.size.width
            assert help_dialog.size.height < app_instance.size.height

    asyncio.run(_run())


def test_textual_pause_requests_are_noop() -> None:
    seen_kinds: list[str] = []

    def _submit(request: app_textual_shared_module.InteractionRequest) -> None:
        seen_kinds.append(request.kind)
        request.result_future.set_result(None)

    bridge = app_textual.TextualInteractionBridge(submit_request_fn=_submit)

    bridge.pause()
    asyncio.run(bridge.pause_async())

    assert seen_kinds == []


def test_textual_slash_binding_filters_analyze_planner() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = _make_textual_app(cfg={"analyzed_programs_and_libraries": ["TargetA"]})

        async with app_instance.run_test() as pilot:
            await pilot.pause()

            await pilot.press("/")
            await pilot.pause()

            assert app_instance.query_one("#interaction-host").has_class("active") is True

            await pilot.press("c", "o", "m", "m", "e", "n", "t", "enter")
            await pilot.pause()

            assert app_instance.query_one("#interaction-host").has_class("active") is False
            assert app_instance._analyze_filter_text == "comment"
            assert app_instance._planner_entry_ids() == (app_textual.analysis_catalog.ENTRY_COMMENTED_OUT_CODE,)
            assert 'Filter: "comment"' not in str(app_instance.query_one("#view-note").renderable)

    asyncio.run(_run())


def test_textual_slash_binding_filters_setup_targets() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = _make_textual_app(cfg={"analyzed_programs_and_libraries": ["Alpha", "Beta", "Gamma"]})

        async with app_instance.run_test() as pilot:
            await pilot.press("3")
            await pilot.pause()

            await pilot.press("/")
            await pilot.pause()

            assert app_instance.query_one("#interaction-host").has_class("active") is True

            await pilot.press("b", "e", "t", "a", "enter")
            await pilot.pause()

            assert app_instance.query_one("#interaction-host").has_class("active") is False
            assert app_instance._setup_filter_text == "beta"
            assert app_instance._setup_target_names_list == ["Beta"]
            assert 'Filter: "beta"' in str(app_instance.query_one("#view-note").renderable)

    asyncio.run(_run())


def test_textual_session_output_preserves_manual_scroll_position_on_new_output() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = app_textual.SattLintTextualApp(
            cfg={},
            summarize_targets_fn=lambda _cfg: "targets",
            analysis_menu_fn=lambda _cfg: None,
            documentation_menu_fn=lambda _cfg: None,
            config_menu_fn=lambda _cfg: None,
            tools_menu_fn=lambda _cfg: None,
            show_help_fn=lambda _cfg: None,
            save_config_fn=lambda _path, _cfg: None,
            config_path=None,
            quit_app_error=RuntimeError,
        )

        async with app_instance.run_test() as pilot:
            await pilot.pause()

            output = app_instance.query_one("#output")
            for index in range(40):
                app_instance._write_output(f"line {index}")
            await pilot.pause()

            output.scroll_to(y=0, animate=False, force=True)
            await pilot.pause()
            scrolled_y = output.scroll_y

            app_instance._write_output("line after manual scroll")
            await pilot.pause()

            assert output.scroll_y == scrolled_y
            assert output.max_scroll_y > output.scroll_y

    asyncio.run(_run())


def test_textual_session_output_keeps_following_when_already_at_bottom() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = app_textual.SattLintTextualApp(
            cfg={},
            summarize_targets_fn=lambda _cfg: "targets",
            analysis_menu_fn=lambda _cfg: None,
            documentation_menu_fn=lambda _cfg: None,
            config_menu_fn=lambda _cfg: None,
            tools_menu_fn=lambda _cfg: None,
            show_help_fn=lambda _cfg: None,
            save_config_fn=lambda _path, _cfg: None,
            config_path=None,
            quit_app_error=RuntimeError,
        )

        async with app_instance.run_test() as pilot:
            await pilot.pause()

            output = app_instance.query_one("#output")
            for index in range(40):
                app_instance._write_output(f"line {index}")
            await pilot.pause()

            output.scroll_end(animate=False)
            await pilot.pause()

            app_instance._write_output("line at bottom")
            await pilot.pause()

            assert output.scroll_y == output.max_scroll_y

    asyncio.run(_run())


def test_textual_present_request_uses_inline_host_and_preserves_shell_chrome() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = app_textual.SattLintTextualApp(
            cfg={},
            summarize_targets_fn=lambda _cfg: "targets",
            analysis_menu_fn=lambda _cfg: None,
            documentation_menu_fn=lambda _cfg: None,
            config_menu_fn=lambda _cfg: None,
            tools_menu_fn=lambda _cfg: None,
            show_help_fn=lambda _cfg: None,
            save_config_fn=lambda _path, _cfg: None,
            config_path=None,
            quit_app_error=RuntimeError,
        )
        request = app_textual_shared_module.InteractionRequest(
            kind="menu",
            title="Analyze",
            options=(
                SimpleNamespace(key="1", label="Run analysis", description=""),
                SimpleNamespace(key="b", label="Back", description=""),
            ),
        )

        async with app_instance.run_test() as pilot:
            app_instance.present_request(request)
            await pilot.pause()

            assert len(list(app_instance.query("#shell-banner"))) == 0
            assert len(list(app_instance.query("#summary"))) == 0
            assert app_instance.query_one("#interaction-host").has_class("active")
            assert app_instance.query_one("#output").has_class("interaction-active")
            assert getattr(app_instance.query_one("#action-analyze"), "disabled", False) is True

            await pilot.press("escape")
            await pilot.pause()

            assert request.result_future.done() is True
            assert request.result_future.result() == "b"
            assert request.response == "b"
            assert app_instance.query_one("#interaction-host").has_class("active") is False
            assert app_instance.query_one("#output").has_class("interaction-active") is False
            assert getattr(app_instance.query_one("#action-analyze"), "disabled", True) is False

    asyncio.run(_run())


def test_textual_toolbar_navigation_switches_view_without_starting_action(monkeypatch: pytest.MonkeyPatch) -> None:
    app_instance = app_textual.SattLintTextualApp(
        cfg={},
        summarize_targets_fn=lambda _cfg: "targets",
        analysis_menu_fn=lambda _cfg: None,
        documentation_menu_fn=lambda _cfg: None,
        config_menu_fn=lambda _cfg: None,
        tools_menu_fn=lambda _cfg: None,
        show_help_fn=lambda _cfg: None,
        save_config_fn=lambda _path, _cfg: None,
        config_path=None,
        quit_app_error=RuntimeError,
    )
    started: list[str] = []

    monkeypatch.setattr(app_instance, "_start_action", lambda *args, **kwargs: started.append("started"))

    app_instance._handle_toolbar_action("action-setup")

    assert app_instance._active_view == "setup"
    assert app_instance._busy is False
    assert started == []


def test_textual_view_primary_action_launches_active_view(monkeypatch: pytest.MonkeyPatch) -> None:
    app_instance = app_textual.SattLintTextualApp(
        cfg={},
        summarize_targets_fn=lambda _cfg: "targets",
        analysis_menu_fn=lambda _cfg: None,
        documentation_menu_fn=lambda _cfg: None,
        config_menu_fn=lambda _cfg: None,
        tools_menu_fn=lambda _cfg: None,
        show_help_fn=lambda _cfg: None,
        save_config_fn=lambda _path, _cfg: None,
        config_path=None,
        quit_app_error=RuntimeError,
    )
    launched: list[tuple[str, str, bool]] = []

    monkeypatch.setattr(
        app_instance,
        "_start_action",
        lambda label, _action_fn, *, action_id, marks_dirty=False, clear_dirty_on_success=False: launched.append(
            (label, action_id, marks_dirty or clear_dirty_on_success)
        ),
    )
    popups: list[str] = []
    monkeypatch.setattr(app_instance, "_open_help_popup", lambda: popups.append("help"))

    app_instance._handle_toolbar_action("action-help")

    assert popups == ["help"]
    assert launched == []


def _make_textual_app(
    *,
    cfg: dict[str, Any] | None = None,
    app_module: Any | None = None,
    startup_output: str = "",
    startup_output_is_warning: bool = False,
) -> Any:
    return app_textual.SattLintTextualApp(
        cfg=cfg or {"analyzed_programs_and_libraries": ["TargetA"]},
        summarize_targets_fn=lambda _cfg: "targets",
        analysis_menu_fn=lambda _cfg: None,
        documentation_menu_fn=lambda _cfg: None,
        config_menu_fn=lambda _cfg: None,
        tools_menu_fn=lambda _cfg: None,
        show_help_fn=lambda _cfg: None,
        get_help_text_fn=lambda _cfg: "Help text",
        save_config_fn=lambda _path, _cfg: None,
        config_path=None,
        quit_app_error=RuntimeError,
        app_module=app_module,
        startup_output=startup_output,
        startup_output_is_warning=startup_output_is_warning,
    )


def test_textual_shell_defaults_to_truecolor_console() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    app_instance = _make_textual_app(cfg={"analyzed_programs_and_libraries": []})

    assert app_instance.console.color_system == "truecolor"


def test_textual_analyze_view_shows_planner_controls() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = _make_textual_app(cfg={"analyzed_programs_and_libraries": []})

        async with app_instance.run_test() as pilot:
            await pilot.pause()

            workspace_host = app_instance.query_one("#workspace-host")
            view_title = app_instance.query_one("#view-title")
            view_host = app_instance.query_one("#view-host")
            output_pane = app_instance.query_one("#output-pane")
            output_widget = app_instance.query_one("#output")
            analyze_left = app_instance.query_one("#analyze-browser-left")
            analyze_right = app_instance.query_one("#analyze-planner-detail")

            assert app_instance._active_view == "analyze"
            assert workspace_host.has_class("analyze-split")
            assert workspace_host.has_class("docs-tools-split") is False
            assert str(view_title.renderable) == "Analyze"
            assert view_title.region.bottom <= view_host.region.y
            assert view_host.size.height > 0
            assert output_pane.size.height > 0
            assert output_widget.size.height > 0
            assert analyze_left.size.height > 0
            assert analyze_right.size.height > 0
            assert output_pane.size.width > view_host.size.width
            assert getattr(output_widget, "read_only", False) is True
            assert getattr(output_widget, "show_line_numbers", True) is False
            assert "Welcome to SattLint Analyze." in getattr(output_widget, "text", "")
            assert app_instance.query_one("#view-actions").has_class("is-hidden") is True
            assert app_instance.query_one("#analyze-actions-primary").has_class("is-hidden") is False
            assert app_instance.query_one("#analyze-browser").has_class("is-hidden") is False
            assert app_instance.query_one("#view-side-actions") is not None
            assert getattr(app_instance.query_one("#analyze-run-selected"), "disabled", False) is True
            assert getattr(app_instance.query_one("#analyze-clear-selection"), "disabled", False) is True
            assert str(app_instance.query_one("#view-note").renderable) == ""
            assert len(list(app_instance.query("#analyze-planner-section-top-level"))) == 0
            assert len(list(app_instance.query("#analyze-planner-section-variable-suite"))) == 0
            assert str(app_instance.query_one("#output-title").renderable) == "Session output"

            detail_renderable = app_instance.query_one("#analyze-planner-detail").renderable
            detail_text = _renderable_text(detail_renderable)
            assert "Focused analysis" in detail_text
            assert "Focused entry: Unused variables" in detail_text
            assert "Description:" in detail_text
            assert "Session output" not in detail_text

    asyncio.run(_run())


def test_textual_analyze_view_keeps_planner_panes_visible_on_small_terminal() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = _make_textual_app(cfg={"analyzed_programs_and_libraries": []})

        async with app_instance.run_test(size=(80, 20)) as pilot:
            await pilot.pause()

            analyze_left = app_instance.query_one("#analyze-browser-left")
            analyze_right = app_instance.query_one("#analyze-planner-detail")
            output_widget = app_instance.query_one("#output")

            assert analyze_left.size.height >= 2
            assert analyze_right.size.height >= 2
            assert output_widget.size.height > 0

    asyncio.run(_run())


def test_textual_analyze_selection_lists_expand_instead_of_scrolling_individually() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = _make_textual_app(cfg={"analyzed_programs_and_libraries": ["TargetA"]})

        async with app_instance.run_test(size=(80, 18)) as pilot:
            await pilot.pause()

            analyze_left = app_instance.query_one("#analyze-browser-left")
            high_confidence = app_instance.query_one("#analyze-planner-section-variable-high-confidence")

            assert analyze_left.virtual_size.height > analyze_left.size.height
            assert high_confidence.size.height >= high_confidence.virtual_size.height

    asyncio.run(_run())


def test_textual_analyze_header_buttons_fit_without_clipping() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = _make_textual_app(cfg={"analyzed_programs_and_libraries": ["TargetA"]})

        async with app_instance.run_test(size=(80, 24)) as pilot:
            await pilot.pause()

            run_button = app_instance.query_one("#analyze-run-selected")
            clear_button = app_instance.query_one("#analyze-clear-selection")

            assert run_button.size.width >= run_button.virtual_size.width
            assert clear_button.size.width >= clear_button.virtual_size.width

    asyncio.run(_run())


def test_textual_analyze_selection_styles_hide_unselected_marker_and_highlight_current_row() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = _make_textual_app(cfg={"analyzed_programs_and_libraries": ["TargetA"]})

        async with app_instance.run_test() as pilot:
            await pilot.pause()

            selection_list = app_instance.query_one("#analyze-planner-section-variable-high-confidence")
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


def test_textual_analyze_planner_renders_grouped_sections_and_detail() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = _make_textual_app(
            app_module=SimpleNamespace(
                _get_enabled_analyzers=lambda: [
                    SimpleNamespace(
                        key="comment-code",
                        name="Commented-out code",
                        description="Scan comments for code-like content",
                    ),
                    SimpleNamespace(
                        key="timing",
                        name="Timing",
                        description="Scan-cycle timing hazards",
                    ),
                ],
                _run_checks=lambda _cfg, _selected_keys: None,
            )
        )

        async with app_instance.run_test() as pilot:
            await pilot.pause()

            assert len(list(app_instance.query("#analyze-planner-section-top-level"))) == 0
            assert len(list(app_instance.query("#analyze-planner-section-variable-suite"))) == 0
            assert app_instance.query_one("#analyze-planner-section-investigation") is not None
            assert app_instance.query_one("#analyze-planner-section-variable-high-confidence") is not None
            assert app_instance.query_one("#analyze-planner-section-catalog-issue-checks") is not None
            assert app_instance.query_one("#analyze-planner-section-catalog-analyzers") is not None
            assert "catalog.analyzer.comment-code" not in app_instance._planner_entry_ids()
            assert "catalog.issue.comment_code" in app_instance._planner_entry_ids()
            assert "catalog.analyzer.timing" in app_instance._planner_entry_ids()
            assert app_textual.analysis_catalog.ENTRY_DATATYPE_USAGE in app_instance._planner_entry_ids()

            detail_text = _renderable_text(app_instance.query_one("#analyze-planner-detail").renderable)
            assert "Focused entry: Unused variables" in detail_text
            assert (
                "Detection: Variables declared but never read or written anywhere in the analyzed target."
                in detail_text
            )
            assert (
                "How: Tracks per-variable read and write flags and reports declarations with neither flag set."
                in detail_text
            )
            app_instance._analyze_focused_entry_id = "catalog.issue.comment_code"
            app_instance._refresh_analyze_planner_summary_widgets()
            await pilot.pause()

            issue_detail_text = _renderable_text(app_instance.query_one("#analyze-planner-detail").renderable)
            assert "Focused entry: Commented-out code: Code-like comments" in issue_detail_text
            assert "Detection: Comment blocks that look like inactive code fragments." in issue_detail_text
            assert (
                "How: Reads the source files for the selected target and applies the comment-code heuristics to each comment block."
                in issue_detail_text
            )

    asyncio.run(_run())


def test_textual_analyze_planner_selection_updates_summary_and_enables_run() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = _make_textual_app(
            app_module=SimpleNamespace(
                run_variable_analysis=lambda _cfg, _kinds: None,
            )
        )

        async with app_instance.run_test() as pilot:
            await pilot.pause()

            high_list = app_instance.query_one("#analyze-planner-section-variable-high-confidence")

            high_list.select("variables.issue.2")
            high_list.select("variables.issue.6")
            app_instance._sync_analyze_selection_from_selection_list(high_list)
            app_instance._refresh_analyze_planner_summary_widgets()
            app_instance._refresh_shell_state()
            await pilot.pause()

            detail_text = _renderable_text(app_instance.query_one("#analyze-planner-detail").renderable)
            assert "Focused entry: Unused variables" in detail_text
            assert "Description:" in detail_text
            assert getattr(app_instance.query_one("#analyze-run-selected"), "disabled", True) is False

    asyncio.run(_run())


def test_textual_analyze_run_selected_executes_planned_steps_in_catalog_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[object] = []
    launched: list[tuple[str, str]] = []

    app_instance = _make_textual_app(
        app_module=SimpleNamespace(
            _run_checks=lambda _cfg, selected_keys: calls.append(
                ("checks", None if selected_keys is None else tuple(selected_keys))
            ),
            run_variable_analysis=lambda _cfg, kinds: calls.append(
                ("variable-analysis", None if kinds is None else tuple(sorted(kind.value for kind in kinds)))
            ),
            run_comment_code_analysis=lambda _cfg: calls.append(("comment-code", None)),
        )
    )
    app_instance._analyze_selected_entry_ids = {
        "variables.issue.6",
        app_textual.analysis_catalog.ENTRY_COMMENTED_OUT_CODE,
    }
    app_instance._analyze_focused_entry_id = "variables.issue.6"

    monkeypatch.setattr(
        app_instance,
        "_start_action",
        lambda label, action_fn, *, action_id, marks_dirty=False, clear_dirty_on_success=False: (
            launched.append((label, action_id)),
            action_fn(),
        ),
    )
    monkeypatch.setattr(app_instance, "_emit_output_from_thread", lambda _text: None)

    app_instance._run_selected_analysis_plan()

    assert launched == [("Run selected analyses", "action-analyze")]
    assert calls == [
        ("variable-analysis", ("unknown_parameter_target",)),
        ("comment-code", None),
    ]
    assert app_instance._analyze_selected_entry_ids == {
        "variables.issue.6",
        app_textual.analysis_catalog.ENTRY_COMMENTED_OUT_CODE,
    }


def test_textual_analyze_run_selected_passes_catalog_issue_kind_subsets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[object] = []
    launched: list[tuple[str, str]] = []

    app_instance = _make_textual_app(
        app_module=SimpleNamespace(
            _get_enabled_analyzers=lambda: [
                SimpleNamespace(
                    key="dataflow",
                    name="Dataflow",
                    description="Scan dataflow hazards",
                )
            ],
            _run_checks=lambda _cfg, selected_keys, *, selected_issue_kinds=None: calls.append(
                (
                    "checks",
                    None if selected_keys is None else tuple(selected_keys),
                    None if selected_issue_kinds is None else frozenset(selected_issue_kinds),
                )
            ),
        )
    )
    app_instance._analyze_selected_entry_ids = {
        "catalog.issue.dataflow.read_before_write",
        "catalog.issue.dataflow.dead_overwrite",
    }
    app_instance._analyze_focused_entry_id = "catalog.issue.dataflow.read_before_write"

    monkeypatch.setattr(
        app_instance,
        "_start_action",
        lambda label, action_fn, *, action_id, marks_dirty=False, clear_dirty_on_success=False: (
            launched.append((label, action_id)),
            action_fn(),
        ),
    )
    monkeypatch.setattr(app_instance, "_emit_output_from_thread", lambda _text: None)

    app_instance._run_selected_analysis_plan()

    assert launched == [("Run selected analyses", "action-analyze")]
    assert calls == [
        (
            "checks",
            ("dataflow",),
            frozenset({"dataflow.read_before_write", "dataflow.dead_overwrite"}),
        )
    ]


def test_textual_analyze_run_selected_surfaces_variable_issue_output_from_real_app(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    seen_kinds: list[set[app.IssueKind] | None] = []

    def _fake_run_variable_analysis(local_cfg: Any, kinds: set[app.IssueKind] | None, **kwargs: Any) -> None:
        del local_cfg
        seen_kinds.append(None if kinds is None else set(kinds))
        app.app_analysis.emit_output("\n=== Target: ProgramA ===")
        app.app_analysis.emit_output("Report: Variable issues")
        pause_fn = kwargs.get("pause_fn")
        if callable(pause_fn):
            pause_fn()

    monkeypatch.setattr(app.app_analysis, "run_variable_analysis", _fake_run_variable_analysis)

    async def _run() -> None:
        app_instance = _make_textual_app(app_module=app)
        bridge = app_textual.TextualInteractionBridge(
            submit_request_fn=lambda request: app_instance.call_from_thread(app_instance.present_request, request)
        )

        app.set_interactive_ui_mode("textual")
        app.set_textual_menu_interaction(bridge.as_menu_interaction())
        try:
            async with app_instance.run_test() as pilot:
                await pilot.pause()

                high_list = app_instance.query_one("#analyze-planner-section-variable-high-confidence")
                high_list.select("variables.issue.2")
                app_instance._sync_analyze_selection_from_selection_list(high_list)
                app_instance._refresh_analyze_planner_summary_widgets()
                app_instance._refresh_shell_state()
                await pilot.pause()

                app_instance.on_button_pressed(SimpleNamespace(button=app_instance.query_one("#analyze-run-selected")))
                await pilot.pause()
                await pilot.pause()

                output_text = str(getattr(app_instance.query_one("#output"), "text", ""))
                assert "Analyze planner queue" in output_text
                assert "=== Target: ProgramA ===" in output_text
                assert "Report: Variable issues" in output_text
                assert app_instance.query_one("#interaction-host").has_class("active") is False
                assert app_instance._busy is False
        finally:
            app.reset_interactive_ui_mode()

    asyncio.run(_run())

    assert seen_kinds == [{app.IssueKind.UNUSED}]


def test_textual_analyze_running_state_calls_out_output_location(monkeypatch: pytest.MonkeyPatch) -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    current_time = 100.0
    monkeypatch.setattr(app_textual_setup_module, "_output_title_spinner_timestamp", lambda: current_time)

    async def _run() -> None:
        nonlocal current_time
        app_instance = _make_textual_app(
            app_module=SimpleNamespace(
                run_comment_code_analysis=lambda _cfg: None,
            )
        )

        async with app_instance.run_test() as pilot:
            await pilot.pause()

            quality_list = app_instance.query_one("#analyze-planner-section-code-quality-actions")
            quality_list.select(app_textual.analysis_catalog.ENTRY_COMMENTED_OUT_CODE)
            app_instance._sync_analyze_selection_from_selection_list(quality_list)
            app_instance._busy = True
            app_instance._active_job_action_id = "action-analyze"
            app_instance._active_job_label = "Run selected analyses"
            app_instance._refresh_summary()
            app_instance._refresh_analyze_planner_summary_widgets()
            app_instance._refresh_shell_state()

            assert str(app_instance.query_one("#view-note").renderable) == ""
            assert str(app_instance.query_one("#output-title").renderable) == (
                "Session output ⠋ - Run selected analyses in progress"
            )

            current_time += (1.0 / 60.0) + 0.001
            app_instance._advance_output_title_spinner()
            assert str(app_instance.query_one("#output-title").renderable) == (
                "Session output ⠙ - Run selected analyses in progress"
            )

            detail_text = _renderable_text(app_instance.query_one("#analyze-planner-detail").renderable)
            assert "Focused analysis" in detail_text
            assert "Description:" in detail_text

    asyncio.run(_run())


def test_textual_analyze_running_state_uses_60fps_output_title_spinner(monkeypatch: pytest.MonkeyPatch) -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    captured: dict[str, object] = {}
    timer_calls = {"resume": 0, "pause": 0}
    timer = SimpleNamespace(
        resume=lambda: timer_calls.__setitem__("resume", timer_calls["resume"] + 1),
        pause=lambda: timer_calls.__setitem__("pause", timer_calls["pause"] + 1),
    )
    app_instance = _make_textual_app(
        app_module=SimpleNamespace(
            run_comment_code_analysis=lambda _cfg: None,
        )
    )
    app_instance._busy = True
    app_instance._active_job_action_id = "action-analyze"
    app_instance._active_job_label = "Run selected analyses"

    monkeypatch.setattr(
        app_instance,
        "set_interval",
        lambda interval, callback, *, pause=False: (
            captured.update({"interval": interval, "callback": callback, "pause": pause}) or timer
        ),
    )

    app_instance._sync_output_title_spinner()

    assert captured["interval"] == pytest.approx(1.0 / 60.0)
    assert captured["callback"] == app_instance._advance_output_title_spinner
    assert captured["pause"] is False
    assert timer_calls == {"resume": 0, "pause": 0}

    app_instance._sync_output_title_spinner()
    assert timer_calls == {"resume": 0, "pause": 0}

    app_instance._busy = False
    app_instance._sync_output_title_spinner()
    assert timer_calls == {"resume": 0, "pause": 1}

    app_instance._busy = True
    app_instance._sync_output_title_spinner()
    assert timer_calls == {"resume": 1, "pause": 1}


def test_textual_analyze_buttons_unlock_after_finish_action() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = _make_textual_app(
            cfg={"analyzed_programs_and_libraries": ["DemoTarget.s"]},
            app_module=SimpleNamespace(
                run_comment_code_analysis=lambda _cfg: None,
            ),
        )

        async with app_instance.run_test() as pilot:
            await pilot.pause()

            quality_list = app_instance.query_one("#analyze-planner-section-code-quality-actions")
            quality_list.select(app_textual.analysis_catalog.ENTRY_COMMENTED_OUT_CODE)
            app_instance._sync_analyze_selection_from_selection_list(quality_list)
            app_instance._refresh_analyze_planner_summary_widgets()
            app_instance._refresh_shell_state()
            await pilot.pause()

            assert getattr(app_instance.query_one("#analyze-run-selected"), "disabled", True) is False
            assert getattr(app_instance.query_one("#analyze-clear-selection"), "disabled", True) is False

            app_instance._busy = True
            app_instance._active_job_action_id = "action-analyze"
            app_instance._active_job_label = "Run selected analyses"
            app_instance._refresh_summary()
            app_instance._refresh_analyze_planner_summary_widgets()
            app_instance._refresh_shell_state()
            await pilot.pause()

            assert getattr(app_instance.query_one("#analyze-run-selected"), "disabled", False) is True
            assert getattr(app_instance.query_one("#analyze-clear-selection"), "disabled", False) is True

            app_instance._finish_action()
            await pilot.pause()

            assert getattr(app_instance.query_one("#analyze-run-selected"), "disabled", True) is False
            assert getattr(app_instance.query_one("#analyze-clear-selection"), "disabled", True) is False
            assert str(app_instance.query_one("#output-title").renderable) == "Session output"
            assert "Selected analyses are running." not in str(app_instance.query_one("#view-note").renderable)

    asyncio.run(_run())


def test_textual_analyze_cancel_button_enables_for_running_queue() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = _make_textual_app(
            cfg={"analyzed_programs_and_libraries": ["DemoTarget.s"]},
            app_module=SimpleNamespace(
                run_comment_code_analysis=lambda _cfg: None,
            ),
        )

        async with app_instance.run_test() as pilot:
            await pilot.pause()

            app_instance._busy = True
            app_instance._active_job_action_id = "action-analyze"
            app_instance._active_job_label = "Run selected analyses"
            app_instance._active_job_cancel_event = threading.Event()
            app_instance._active_job_thread = SimpleNamespace(ident=None, is_alive=lambda: True)
            app_instance._refresh_shell_state()
            await pilot.pause()

            assert getattr(app_instance.query_one("#analyze-cancel-running"), "disabled", True) is False

    asyncio.run(_run())


def test_textual_analyze_run_selected_reports_missing_handlers(monkeypatch: pytest.MonkeyPatch) -> None:
    lines: list[str] = []

    app_instance = _make_textual_app(app_module=SimpleNamespace())
    app_instance._analyze_selected_entry_ids = {"variables.issue.6"}

    monkeypatch.setattr(app_instance, "_write_output", lambda text: lines.extend(text.splitlines()))
    monkeypatch.setattr(app_instance, "_start_action", lambda *_args, **_kwargs: pytest.fail("should not start"))

    app_instance._run_selected_analysis_plan()

    assert any("Missing handlers" in line for line in lines)
    assert any("run_variable_analysis" in line for line in lines)


def test_textual_execute_analyze_plan_emits_progress_lines(monkeypatch: pytest.MonkeyPatch) -> None:
    emitted: list[str] = []
    executed: list[str] = []

    app_instance = _make_textual_app(app_module=SimpleNamespace())
    plan = SimpleNamespace(
        executable_steps=[
            SimpleNamespace(label="Run full suite", source_labels=("Full suite", "Toolbar")),
            SimpleNamespace(label="Commented out code", source_labels=("Code quality",)),
        ]
    )

    monkeypatch.setattr(app_textual.analysis_planner, "render_analysis_plan_summary", lambda _plan: "Plan summary")
    monkeypatch.setattr(app_instance, "_emit_output_from_thread", lambda text: emitted.append(text))
    monkeypatch.setattr(
        app_instance,
        "_execute_planned_analysis_step",
        lambda step: executed.append(str(step.label)),
    )

    app_instance._execute_analyze_plan(plan)

    assert emitted == [
        "Analyze planner queue",
        "Plan summary",
        "[1/2] Run full suite",
        "Merged selections: Full suite, Toolbar",
        "[2/2] Commented out code",
        "Selected analyses completed.",
    ]
    assert executed == ["Run full suite", "Commented out code"]


def test_textual_execute_analyze_plan_stops_after_cancel_request(monkeypatch: pytest.MonkeyPatch) -> None:
    emitted: list[str] = []
    executed: list[str] = []

    app_instance = _make_textual_app(app_module=SimpleNamespace())
    plan = SimpleNamespace(
        executable_steps=[
            SimpleNamespace(label="Run full suite", source_labels=("Full suite",)),
            SimpleNamespace(label="Commented out code", source_labels=("Code quality",)),
        ]
    )

    monkeypatch.setattr(app_textual.analysis_planner, "render_analysis_plan_summary", lambda _plan: "Plan summary")
    monkeypatch.setattr(app_instance, "_emit_output_from_thread", lambda text: emitted.append(text))

    def _execute(step: Any) -> None:
        executed.append(str(step.label))
        app_instance._active_job_cancel_requested = True

    monkeypatch.setattr(app_instance, "_execute_planned_analysis_step", _execute)

    app_instance._busy = True
    app_instance._active_job_action_id = "action-analyze"
    app_instance._active_job_cancel_event = threading.Event()
    app_instance._active_job_cancel_requested = False

    app_instance._execute_analyze_plan(plan)

    assert executed == ["Run full suite"]
    assert emitted == [
        "Analyze planner queue",
        "Plan summary",
        "[1/2] Run full suite",
        "Cancellation requested. Remaining queued analyses were not started.",
    ]


def test_textual_start_action_tracks_active_worker_thread(monkeypatch: pytest.MonkeyPatch) -> None:
    created_workers: list[object] = []

    class FakeWorker:
        def cancel(self) -> None:
            return None

    class FakeTextualApp(app_textual.SattLintTextualApp):
        def _start_managed_action_worker(self, _work: Any, *, label: str, action_id: str) -> object:
            assert label == "Run selected analyses"
            assert action_id == "action-analyze"
            worker = FakeWorker()
            created_workers.append(worker)
            return worker

    app_instance = FakeTextualApp(
        cfg={"analyzed_programs_and_libraries": ["TargetA"]},
        summarize_targets_fn=lambda _cfg: "targets",
        analysis_menu_fn=lambda _cfg: None,
        documentation_menu_fn=lambda _cfg: None,
        config_menu_fn=lambda _cfg: None,
        tools_menu_fn=lambda _cfg: None,
        show_help_fn=lambda _cfg: None,
        get_help_text_fn=lambda _cfg: "Help text",
        save_config_fn=lambda _path, _cfg: None,
        config_path=None,
        quit_app_error=RuntimeError,
        app_module=SimpleNamespace(),
    )

    monkeypatch.setattr(app_instance, "_refresh_summary", lambda: None)
    monkeypatch.setattr(app_instance, "_refresh_shell_state", lambda: None)
    monkeypatch.setattr(app_instance, "_refresh_view", lambda: None)
    monkeypatch.setattr(
        app_instance, "_set_active_action", lambda action_id: setattr(app_instance, "_active_job_action_id", action_id)
    )
    monkeypatch.setattr(app_instance, "_write_output", lambda _text: None)
    monkeypatch.setattr(app_instance, "_clear_session_output", lambda: None)

    app_instance._start_action("Run selected analyses", lambda: None, action_id="action-analyze")

    assert len(created_workers) == 1
    assert app_instance._active_job_worker is created_workers[0]
    assert app_instance._active_job_thread is None
    assert app_instance._active_job_cancel_event is not None


def test_textual_schedule_ui_coroutine_tracks_pending_task(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeTask:
        def __init__(self) -> None:
            self._callbacks: list[Any] = []

        def add_done_callback(self, callback: Any) -> None:
            self._callbacks.append(callback)

        def finish(self) -> None:
            for callback in tuple(self._callbacks):
                callback(self)

    class FakeLoop:
        def __init__(self, task: FakeTask) -> None:
            self.task = task
            self.created: list[object] = []

        def create_task(self, coroutine: object) -> FakeTask:
            self.created.append(coroutine)
            return self.task

    fake_task = FakeTask()
    fake_loop = FakeLoop(fake_task)
    app_instance = _make_textual_app()

    monkeypatch.setattr(asyncio, "get_running_loop", lambda: fake_loop)

    app_instance._schedule_ui_coroutine(lambda: "scheduled work")

    assert fake_loop.created == ["scheduled work"]
    assert fake_task in app_instance._pending_ui_tasks

    fake_task.finish()

    assert fake_task not in app_instance._pending_ui_tasks


def test_textual_start_action_reports_type_errors_from_action(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeTextualApp(app_textual.SattLintTextualApp):
        def _start_managed_action_worker(self, work: Any, *, label: str, action_id: str) -> object:
            assert label == "Run selected analyses"
            assert action_id == "action-analyze"
            work()
            return SimpleNamespace(cancel=lambda: None)

    app_instance = FakeTextualApp(
        cfg={"analyzed_programs_and_libraries": ["TargetA"]},
        summarize_targets_fn=lambda _cfg: "targets",
        analysis_menu_fn=lambda _cfg: None,
        documentation_menu_fn=lambda _cfg: None,
        config_menu_fn=lambda _cfg: None,
        tools_menu_fn=lambda _cfg: None,
        show_help_fn=lambda _cfg: None,
        get_help_text_fn=lambda _cfg: "Help text",
        save_config_fn=lambda _path, _cfg: None,
        config_path=None,
        quit_app_error=RuntimeError,
        app_module=SimpleNamespace(),
    )

    monkeypatch.setattr(app_instance, "_refresh_summary", lambda: None)
    monkeypatch.setattr(app_instance, "_refresh_shell_state", lambda: None)
    monkeypatch.setattr(app_instance, "_refresh_view", lambda: None)
    monkeypatch.setattr(
        app_instance, "_set_active_action", lambda action_id: setattr(app_instance, "_active_job_action_id", action_id)
    )
    emitted: list[str] = []
    monkeypatch.setattr(app_instance, "_write_output", lambda text: emitted.append(str(text)))
    monkeypatch.setattr(app_instance, "_clear_session_output", lambda: None)
    monkeypatch.setattr(app_instance, "call_from_thread", lambda callback, *args, **kwargs: callback(*args, **kwargs))

    app_instance._start_action(
        "Run selected analyses",
        lambda: (_ for _ in ()).throw(TypeError("bad action wiring")),
        action_id="action-analyze",
    )

    assert app_instance._busy is False
    assert emitted == [
        "Starting Run selected analyses... Live output is shown in this panel.",
        "Run selected analyses failed: bad action wiring",
    ]


def test_textual_open_help_popup_propagates_type_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    app_instance = _make_textual_app()
    app_instance._get_help_text_fn = lambda _cfg: (_ for _ in ()).throw(TypeError("bad help wiring"))
    shown_help: list[str] = []

    monkeypatch.setattr(app_instance, "_show_help_modal", lambda text: shown_help.append(text))

    with pytest.raises(TypeError, match="bad help wiring"):
        app_instance._open_help_popup()

    assert shown_help == []


def test_textual_ctrl_g_cancel_binding_requests_stop_for_running_analysis(monkeypatch: pytest.MonkeyPatch) -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        interrupted: list[tuple[object, object]] = []
        fake_thread = SimpleNamespace(ident=321, is_alive=lambda: True)
        app_instance = _make_textual_app(
            cfg={"analyzed_programs_and_libraries": ["DemoTarget.s"]},
            app_module=SimpleNamespace(
                run_comment_code_analysis=lambda _cfg: None,
            ),
        )

        monkeypatch.setattr(
            app_textual_actions_module,
            "_interrupt_worker_thread",
            lambda thread, exception_type: interrupted.append((thread, exception_type)) or True,
        )

        async with app_instance.run_test() as pilot:
            await pilot.pause()

            quality_list = app_instance.query_one("#analyze-planner-section-code-quality-actions")
            quality_list.select(app_textual.analysis_catalog.ENTRY_COMMENTED_OUT_CODE)
            app_instance._sync_analyze_selection_from_selection_list(quality_list)
            app_instance._refresh_analyze_planner_summary_widgets()
            app_instance._busy = True
            app_instance._active_job_action_id = "action-analyze"
            app_instance._active_job_label = "Run selected analyses"
            app_instance._active_job_cancel_event = threading.Event()
            app_instance._active_job_cancel_requested = False
            app_instance._active_job_worker = SimpleNamespace(cancel=lambda: None)
            app_instance._active_job_thread = fake_thread
            app_instance._refresh_summary()
            app_instance._refresh_shell_state()
            app_instance._refresh_view()
            await pilot.pause()

            assert ("ctrl+g", "cancel_running_analysis", "Cancel Analysis") in app_textual.SattLintTextualApp.BINDINGS
            app_instance.action_cancel_running_analysis()

            output_text = getattr(app_instance.query_one("#output"), "text", "")
            detail_text = _renderable_text(app_instance.query_one("#analyze-planner-detail").renderable)

            assert app_instance._active_job_cancel_requested is True
            assert app_instance._active_job_cancel_event is not None
            assert app_instance._active_job_cancel_event.is_set() is True
            assert interrupted == [(fake_thread, KeyboardInterrupt)]
            assert "Cancellation requested. Interrupting the running analysis immediately." in output_text
            assert str(app_instance.query_one("#view-note").renderable) == ""
            assert "Focused analysis" in detail_text

    asyncio.run(_run())


def test_textual_analyze_clear_selection_resets_planner_state() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = _make_textual_app(
            app_module=SimpleNamespace(
                run_comment_code_analysis=lambda _cfg: None,
            )
        )

        async with app_instance.run_test() as pilot:
            await pilot.pause()

            quality_list = app_instance.query_one("#analyze-planner-section-code-quality-actions")
            quality_list.select(app_textual.analysis_catalog.ENTRY_COMMENTED_OUT_CODE)
            app_instance._sync_analyze_selection_from_selection_list(quality_list)
            app_instance._refresh_analyze_planner_summary_widgets()
            app_instance._refresh_shell_state()
            await pilot.pause()

            assert app_instance._analyze_selected_entry_ids == {app_textual.analysis_catalog.ENTRY_COMMENTED_OUT_CODE}
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
        app_instance = _make_textual_app(
            app_module=SimpleNamespace(
                run_comment_code_analysis=lambda _cfg: None,
            )
        )

        async with app_instance.run_test() as pilot:
            await pilot.pause()

            quality_list = app_instance.query_one("#analyze-planner-section-code-quality-actions")
            quality_list.select(app_textual.analysis_catalog.ENTRY_COMMENTED_OUT_CODE)
            app_instance._sync_analyze_selection_from_selection_list(quality_list)
            app_instance._refresh_analyze_planner_summary_widgets()
            app_instance._refresh_shell_state()
            app_instance._write_output("extra output")
            await pilot.pause()

            assert app_textual.analysis_catalog.ENTRY_COMMENTED_OUT_CODE in app_instance._analyze_selected_entry_ids
            assert "Welcome to SattLint Analyze." in getattr(app_instance.query_one("#output"), "text", "")

            app_instance.on_button_pressed(SimpleNamespace(button=SimpleNamespace(id="analyze-clear-output")))
            await pilot.pause()

            assert getattr(app_instance.query_one("#output"), "text", "") == ""
            assert app_textual.analysis_catalog.ENTRY_COMMENTED_OUT_CODE in app_instance._analyze_selected_entry_ids
            assert str(app_instance.query_one("#output-title").renderable) == "Session output"

    asyncio.run(_run())


def test_textual_toolbar_key_switches_routed_view() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = app_textual.SattLintTextualApp(
            cfg={},
            summarize_targets_fn=lambda _cfg: "targets",
            analysis_menu_fn=lambda _cfg: None,
            documentation_menu_fn=lambda _cfg: None,
            config_menu_fn=lambda _cfg: None,
            tools_menu_fn=lambda _cfg: None,
            show_help_fn=lambda _cfg: None,
            save_config_fn=lambda _path, _cfg: None,
            config_path=None,
            quit_app_error=RuntimeError,
        )

        async with app_instance.run_test() as pilot:
            assert str(app_instance.query_one("#view-title").renderable) == "Analyze"

            await pilot.press("3")
            await pilot.pause()

            assert app_instance._active_view == "setup"
            assert str(app_instance.query_one("#view-title").renderable) == "Setup"
            assert app_instance.query_one("#view-actions").has_class("is-hidden") is True
            assert getattr(app_instance.query_one("#action-setup"), "disabled", True) is False

    asyncio.run(_run())


def test_textual_toolbar_keys_respect_busy_guard() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = app_textual.SattLintTextualApp(
            cfg={},
            summarize_targets_fn=lambda _cfg: "targets",
            analysis_menu_fn=lambda _cfg: None,
            documentation_menu_fn=lambda _cfg: None,
            config_menu_fn=lambda _cfg: None,
            tools_menu_fn=lambda _cfg: None,
            show_help_fn=lambda _cfg: None,
            save_config_fn=lambda _path, _cfg: None,
            config_path=None,
            quit_app_error=RuntimeError,
        )
        opened_help: list[str] = []
        app_instance._open_help_popup = lambda: opened_help.append("help")  # type: ignore[method-assign]

        async with app_instance.run_test() as pilot:
            await pilot.pause()

            app_instance._busy = True
            app_instance._active_job_action_id = "action-analyze"
            app_instance._active_job_label = "Analyzer checks"
            app_instance._refresh_shell_state()
            await pilot.pause()

            await pilot.press("5")
            await pilot.press("3")
            await pilot.pause()

            output_text = getattr(app_instance.query_one("#output"), "text", "")
            assert app_instance._active_view == "analyze"
            assert opened_help == []
            assert output_text.count("Another action is still running. Wait for it to finish first.") == 2

    asyncio.run(_run())


def test_textual_analyze_view_does_not_compose_secondary_actions_row() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = _make_textual_app(cfg={"analyzed_programs_and_libraries": ["TargetA"]})

        async with app_instance.run_test(size=(80, 24)) as pilot:
            await pilot.pause()

            assert app_instance.query_one("#analyze-actions-primary") is not None
            assert len(list(app_instance.query("#analyze-actions-secondary"))) == 0

    asyncio.run(_run())


def test_textual_setup_view_shows_selected_target_preview(tmp_path: Path) -> None:  # noqa: PLR0915
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:  # noqa: PLR0915
        program_dir = tmp_path / "programs"
        abb_dir = tmp_path / "abb"
        program_dir.mkdir()
        abb_dir.mkdir()
        (program_dir / "TargetA.s").write_text("draft")
        (program_dir / "TargetA.l").write_text("deps")
        (abb_dir / "TargetA.x").write_text("official")

        cfg = {
            "analyzed_programs_and_libraries": [],
            "program_dir": str(program_dir),
            "ABB_lib_dir": str(abb_dir),
            "other_lib_dirs": [],
            "mode": "draft",
        }
        app_instance = app_textual.SattLintTextualApp(
            cfg=cfg,
            summarize_targets_fn=lambda _cfg: "targets",
            analysis_menu_fn=lambda _cfg: None,
            documentation_menu_fn=lambda _cfg: None,
            config_menu_fn=lambda _cfg: None,
            tools_menu_fn=lambda _cfg: None,
            show_help_fn=lambda _cfg: None,
            save_config_fn=lambda _path, _cfg: None,
            config_path=None,
            quit_app_error=RuntimeError,
        )

        async with app_instance.run_test() as pilot:
            await pilot.press("3")
            await pilot.pause()

            workspace_host = app_instance.query_one("#workspace-host")
            view_title = app_instance.query_one("#view-title")
            output_pane = app_instance.query_one("#output-pane")
            view_host = app_instance.query_one("#view-host")
            browse_button = app_instance.query_one("#setup-target-browse")
            remove_button = app_instance.query_one("#setup-target-remove")
            program_button = app_instance.query_one("#setup-edit-program-dir")
            mode_button = app_instance.query_one("#setup-toggle-mode")
            debug_button = app_instance.query_one("#setup-toggle-debug")
            save_button = app_instance.query_one("#setup-save")
            targets_col = app_instance.query_one("#setup-targets-col")
            settings_col = app_instance.query_one("#setup-settings-col")
            assert app_instance._active_view == "setup"
            assert workspace_host.has_class("no-output")
            assert str(view_title.renderable) == "Setup"
            assert view_title.region.bottom <= view_host.region.y
            assert output_pane.has_class("is-hidden") is True
            assert app_instance.query_one("#setup-browser").has_class("is-hidden") is False
            assert app_instance.query_one("#view-actions").has_class("is-hidden") is True
            assert str(getattr(browse_button, "label", "")) == "Add from file..."
            assert str(getattr(program_button, "label", "")) == "Program folder"
            assert targets_col is not None
            assert settings_col is not None
            assert (
                len(
                    {program_button.size.width, mode_button.size.width, debug_button.size.width, save_button.size.width}
                )
                == 1
            )
            assert str(app_instance.query_one("#setup-label-program-dir").renderable) == (
                f"{program_dir.name}\n{program_dir}"
            )
            assert str(app_instance.query_one("#setup-label-abb-dir").renderable) == f"{abb_dir.name}\n{abb_dir}"
            assert str(app_instance.query_one("#setup-label-other-dirs").renderable) == "No extra libraries"
            assert str(app_instance.query_one("#setup-label-icf-dir").renderable) == "Not configured"
            assert str(app_instance.query_one("#setup-label-mode").renderable) == "Draft mode\n.s and .l files"
            assert str(app_instance.query_one("#setup-label-scan-root-only").renderable) == (
                "Disabled\nNested folders are also scanned"
            )
            assert str(app_instance.query_one("#setup-label-fast-cache").renderable) == (
                "Disabled\nFull cache validation is active"
            )
            assert str(app_instance.query_one("#setup-label-debug").renderable) == (
                "Disabled\nStandard runtime logging"
            )
            assert str(app_instance.query_one("#setup-label-telemetry").renderable) == ("Disabled\nTelemetry stays off")

            assert targets_col.region.x < settings_col.region.x
            assert targets_col.region.width > 0
            assert settings_col.region.width > 0
            assert browse_button.region.x >= targets_col.region.x
            assert browse_button.region.x < settings_col.region.x
            assert save_button.region.x >= settings_col.region.x
            # Remove is disabled when nothing is selected
            assert getattr(remove_button, "disabled", False) is True

    asyncio.run(_run())


def test_textual_setup_browse_shows_discovered_targets_once(tmp_path: Path) -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        program_dir = tmp_path / "programs"
        abb_dir = tmp_path / "abb"
        program_dir.mkdir()
        abb_dir.mkdir()
        (program_dir / "TargetA.s").write_text("draft")
        (program_dir / "TargetA.l").write_text("deps")
        (abb_dir / "TargetA.x").write_text("official")

        app_instance = _make_textual_app(
            cfg={
                "analyzed_programs_and_libraries": [],
                "program_dir": str(program_dir),
                "ABB_lib_dir": str(abb_dir),
                "other_lib_dirs": [],
                "mode": "draft",
            }
        )

        async with app_instance.run_test() as pilot:
            await pilot.press("3")
            await pilot.pause()

            browse_button = app_instance.query_one("#setup-target-browse")
            app_instance.on_button_pressed(SimpleNamespace(button=browse_button))
            await pilot.pause()

            target_list = _query_any_screen(app_instance, "#file-browser-targets")
            list_items = list(target_list.query("ListItem"))
            selection_text = str(_query_any_screen(app_instance, "#file-browser-selection").renderable)

            assert _query_any_screen(app_instance, "#file-browser-dialog") is not None
            assert len(list_items) == 1
            assert "TargetA" in str(getattr(list_items[0].query_one("Static"), "renderable", ""))
            assert "TargetA.s" not in selection_text
            assert "TargetA.l" not in selection_text
            assert "TargetA.x" not in selection_text
            assert "TargetA" in selection_text
            assert (
                str(getattr(_query_any_screen(app_instance, "#file-browser-browse-filesystem"), "label", ""))
                == "Browse filesystem"
            )

    asyncio.run(_run())


def test_textual_startup_output_is_written_for_successful_ast_refresh_logs() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = _make_textual_app(startup_output="Checking AST cache for Demo")

        async with app_instance.run_test() as pilot:
            await pilot.pause()

            output_text = getattr(app_instance.query_one("#output"), "text", "")
            assert "Initial AST loading log:" not in output_text
            assert "Checking AST cache for Demo" not in output_text
            assert "Welcome to SattLint Analyze." in output_text

    asyncio.run(_run())


def test_textual_documentation_view_shows_direct_actions() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = app_textual.SattLintTextualApp(
            cfg={"analyzed_programs_and_libraries": ["TargetA"]},
            summarize_targets_fn=lambda _cfg: "targets",
            analysis_menu_fn=lambda _cfg: None,
            documentation_menu_fn=lambda _cfg: None,
            config_menu_fn=lambda _cfg: None,
            tools_menu_fn=lambda _cfg: None,
            show_help_fn=lambda _cfg: None,
            save_config_fn=lambda _path, _cfg: None,
            config_path=None,
            quit_app_error=RuntimeError,
            app_module=SimpleNamespace(
                _get_documentation_unit_selection=lambda: {
                    "mode": "moduletype_names",
                    "instance_paths": [],
                    "moduletype_names": ["ApplTank"],
                }
            ),
        )

        async with app_instance.run_test(size=(80, 28)) as pilot:
            await pilot.press("2")
            await pilot.pause()

            workspace_host = app_instance.query_one("#workspace-host")
            documentation_actions = app_instance.query_one("#documentation-actions")
            view_side_actions = app_instance.query_one("#view-side-actions")
            view_title = app_instance.query_one("#view-title")
            view_host = app_instance.query_one("#view-host")
            output_pane = app_instance.query_one("#output-pane")
            generate_button = app_instance.query_one("#documentation-generate")
            preview_button = app_instance.query_one("#documentation-preview-candidates")
            scope_all_button = app_instance.query_one("#documentation-scope-all")
            scope_moduletype_button = app_instance.query_one("#documentation-scope-moduletype")
            scope_instance_button = app_instance.query_one("#documentation-scope-instance-path")
            assert app_instance._active_view == "documentation"
            assert workspace_host.has_class("docs-tools-split")
            assert workspace_host.has_class("analyze-split") is False
            assert str(view_title.renderable) == "Documentation"
            assert view_title.region.bottom <= view_host.region.y
            assert output_pane.has_class("is-hidden") is False
            assert output_pane.size.width > view_host.size.width
            assert app_instance.query_one("#view-actions").has_class("is-hidden") is True
            assert app_instance.query_one("#documentation-actions").has_class("is-hidden") is False
            assert getattr(generate_button, "disabled", True) is False
            assert workspace_host.has_class("wide-output-split") is False
            assert view_side_actions.size.height > 0
            for button in (
                generate_button,
                preview_button,
                scope_all_button,
                scope_moduletype_button,
                scope_instance_button,
            ):
                assert button.size.width > 0
                assert button.region.x >= documentation_actions.region.x
                assert button.region.right <= documentation_actions.region.right
            assert generate_button.region.y < preview_button.region.y
            assert preview_button.region.y < scope_all_button.region.y
            assert scope_all_button.region.y < scope_moduletype_button.region.y
            assert scope_moduletype_button.region.y < scope_instance_button.region.y
            assert "Current scope: moduletype: ApplTank" in str(app_instance.query_one("#view-note").renderable)

    asyncio.run(_run())


@pytest.mark.parametrize(
    ("button_id", "handler_name", "expected_call"),
    [
        ("documentation-generate", "_run_documentation_generate", "generate"),
        ("documentation-preview-candidates", "_run_documentation_preview_candidates", "preview"),
        ("documentation-scope-all", "_run_documentation_scope_all", "scope-all"),
        ("documentation-scope-moduletype", "_run_documentation_scope_moduletype", "scope-moduletype"),
        ("documentation-scope-instance-path", "_run_documentation_scope_instance_path", "scope-instance"),
        ("tools-self-check", "_run_tool_self_check", "self-check"),
        ("tools-dumps", "_run_tool_dumps", "dumps"),
        ("tools-source-diff", "_run_tool_source_diff", "source-diff"),
        ("tools-refresh-ast", "_run_tool_refresh_ast", "refresh-ast"),
        ("tools-datatype-usage", "_run_tool_datatype_usage", "datatype-usage"),
        ("tools-variable-trace", "_run_tool_variable_trace", "variable-trace"),
        ("tools-module-locals", "_run_tool_module_locals", "module-locals"),
    ],
)
def test_textual_docs_and_tools_buttons_dispatch_direct_actions(
    monkeypatch: pytest.MonkeyPatch,
    button_id: str,
    handler_name: str,
    expected_call: str,
) -> None:
    app_instance = _make_textual_app()
    seen: list[str] = []

    monkeypatch.setattr(app_instance, handler_name, lambda: seen.append(expected_call))

    app_instance.on_button_pressed(SimpleNamespace(button=SimpleNamespace(id=button_id)))

    assert seen == [expected_call]


def test_textual_tools_dumps_button_opens_menu_without_ansi_clear() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = app_textual.SattLintTextualApp(
            cfg={"analyzed_programs_and_libraries": ["TargetA"]},
            summarize_targets_fn=lambda _cfg: "targets",
            analysis_menu_fn=lambda _cfg: None,
            documentation_menu_fn=lambda _cfg: None,
            config_menu_fn=lambda _cfg: None,
            tools_menu_fn=lambda _cfg: None,
            show_help_fn=lambda _cfg: None,
            save_config_fn=lambda _path, _cfg: None,
            config_path=None,
            quit_app_error=RuntimeError,
            app_module=app,
            self_check_fn=lambda _cfg: True,
            dump_menu_fn=app.dump_menu,
            source_diff_fn=lambda _cfg: None,
            force_refresh_ast_fn=lambda _cfg: None,
        )
        bridge = app_textual.TextualInteractionBridge(
            submit_request_fn=lambda request: app_instance.call_from_thread(app_instance.present_request, request)
        )

        app.set_interactive_ui_mode("textual")
        app.set_textual_menu_interaction(bridge.as_menu_interaction())
        try:
            async with app_instance.run_test(size=(80, 28)) as pilot:
                await pilot.press("4")
                await pilot.pause()

                app_instance.on_button_pressed(SimpleNamespace(button=app_instance.query_one("#tools-dumps")))
                await pilot.pause()
                await pilot.pause()

                output_text = str(getattr(app_instance.query_one("#output"), "text", ""))
                assert "\x1b[2J" not in output_text
                assert "\x1b[H" not in output_text
                assert app_instance.query_one("#interaction-host").has_class("active")

                await pilot.press("escape")
                await pilot.pause()
                await pilot.pause()

                assert app_instance.query_one("#interaction-host").has_class("active") is False
                assert app_instance._busy is False
        finally:
            app.reset_interactive_ui_mode()

    asyncio.run(_run())


def test_textual_setup_target_button_click_adds_and_removes_target(tmp_path: Path) -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        program_dir = tmp_path / "programs"
        program_dir.mkdir()
        (program_dir / "TargetA.s").write_text("draft")

        cfg = {
            "analyzed_programs_and_libraries": [],
            "program_dir": str(program_dir),
            "ABB_lib_dir": "",
            "other_lib_dirs": [],
            "mode": "draft",
        }
        app_instance = app_textual.SattLintTextualApp(
            cfg=cfg,
            summarize_targets_fn=lambda _cfg: "targets",
            analysis_menu_fn=lambda _cfg: None,
            documentation_menu_fn=lambda _cfg: None,
            config_menu_fn=lambda _cfg: None,
            tools_menu_fn=lambda _cfg: None,
            show_help_fn=lambda _cfg: None,
            save_config_fn=lambda _path, _cfg: None,
            config_path=None,
            quit_app_error=RuntimeError,
        )

        async with app_instance.run_test() as pilot:
            await pilot.press("3")
            await pilot.pause()

            # Add target programmatically (file browser not testable in headless mode)
            app_instance._add_selected_setup_target("TargetA")
            await pilot.pause()

            assert cfg["analyzed_programs_and_libraries"] == ["TargetA"]

            # Select target via _selected_configured_target (simulating ListView highlight)
            app_instance._selected_configured_target = "TargetA"
            await pilot.pause()

            assert app_instance._selected_configured_target == "TargetA"

            # Click remove to remove the selected target
            remove_button = app_instance.query_one("#setup-target-remove")
            app_instance.on_button_pressed(SimpleNamespace(button=remove_button))
            await pilot.pause()

            assert cfg["analyzed_programs_and_libraries"] == []
            assert app_instance._selected_configured_target is None

    asyncio.run(_run())


def test_textual_tools_view_shows_direct_actions() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = app_textual.SattLintTextualApp(
            cfg={"analyzed_programs_and_libraries": []},
            summarize_targets_fn=lambda _cfg: "targets",
            analysis_menu_fn=lambda _cfg: None,
            documentation_menu_fn=lambda _cfg: None,
            config_menu_fn=lambda _cfg: None,
            tools_menu_fn=lambda _cfg: None,
            show_help_fn=lambda _cfg: None,
            save_config_fn=lambda _path, _cfg: None,
            config_path=None,
            quit_app_error=RuntimeError,
        )

        async with app_instance.run_test(size=(80, 28)) as pilot:
            await pilot.press("4")
            await pilot.pause()

            workspace_host = app_instance.query_one("#workspace-host")
            tools_actions = app_instance.query_one("#tools-actions")
            view_side_actions = app_instance.query_one("#view-side-actions")
            view_title = app_instance.query_one("#view-title")
            view_host = app_instance.query_one("#view-host")
            output_pane = app_instance.query_one("#output-pane")
            self_check_button = app_instance.query_one("#tools-self-check")
            dumps_button = app_instance.query_one("#tools-dumps")
            source_diff_button = app_instance.query_one("#tools-source-diff")
            refresh_ast_button = app_instance.query_one("#tools-refresh-ast")
            datatype_usage_button = app_instance.query_one("#tools-datatype-usage")
            variable_trace_button = app_instance.query_one("#tools-variable-trace")
            module_locals_button = app_instance.query_one("#tools-module-locals")
            assert app_instance._active_view == "tools"
            assert workspace_host.has_class("docs-tools-split")
            assert workspace_host.has_class("analyze-split") is False
            assert str(view_title.renderable) == "Tools"
            assert view_title.region.bottom <= view_host.region.y
            assert output_pane.has_class("is-hidden") is False
            assert output_pane.size.width > view_host.size.width
            assert app_instance.query_one("#view-actions").has_class("is-hidden") is True
            assert app_instance.query_one("#tools-actions").has_class("is-hidden") is False
            assert getattr(self_check_button, "disabled", True) is False
            assert getattr(dumps_button, "disabled", False) is True
            assert getattr(source_diff_button, "disabled", False) is True
            assert getattr(refresh_ast_button, "disabled", False) is True
            assert getattr(datatype_usage_button, "disabled", False) is True
            assert getattr(variable_trace_button, "disabled", False) is True
            assert getattr(module_locals_button, "disabled", False) is True
            assert str(getattr(refresh_ast_button, "label", "")) == "Refresh all caches"
            assert workspace_host.has_class("wide-output-split") is False
            assert view_side_actions.size.height > 0
            for button in (
                self_check_button,
                dumps_button,
                source_diff_button,
                refresh_ast_button,
                datatype_usage_button,
                variable_trace_button,
                module_locals_button,
            ):
                assert button.size.width > 0
                assert button.region.x >= tools_actions.region.x
                assert button.region.right <= tools_actions.region.right
            assert self_check_button.region.y < dumps_button.region.y
            assert dumps_button.region.y < source_diff_button.region.y
            assert source_diff_button.region.y < refresh_ast_button.region.y
            assert refresh_ast_button.region.y < datatype_usage_button.region.y
            assert datatype_usage_button.region.y < variable_trace_button.region.y
            assert variable_trace_button.region.y < module_locals_button.region.y
            assert "targeted tracing tools" in str(app_instance.query_one("#view-description").renderable)

    asyncio.run(_run())


def test_textual_setup_add_selected_target_marks_dirty(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    program_dir = tmp_path / "programs"
    program_dir.mkdir()
    (program_dir / "TargetA.s").write_text("draft")

    cfg: dict[str, Any] = {
        "analyzed_programs_and_libraries": [],
        "program_dir": str(program_dir),
        "ABB_lib_dir": "",
        "other_lib_dirs": [],
        "mode": "draft",
    }
    app_instance = app_textual.SattLintTextualApp(
        cfg=cfg,
        summarize_targets_fn=lambda _cfg: "targets",
        analysis_menu_fn=lambda _cfg: None,
        documentation_menu_fn=lambda _cfg: None,
        config_menu_fn=lambda _cfg: None,
        tools_menu_fn=lambda _cfg: None,
        show_help_fn=lambda _cfg: None,
        save_config_fn=lambda _path, _cfg: None,
        config_path=None,
        quit_app_error=RuntimeError,
    )
    messages: list[str] = []

    monkeypatch.setattr(app_instance, "_refresh_summary", lambda: None)
    monkeypatch.setattr(app_instance, "_refresh_view", lambda: None)
    monkeypatch.setattr(app_instance, "_set_active_action", lambda _action_id: None)
    monkeypatch.setattr(app_instance, "_refresh_shell_state", lambda: None)
    monkeypatch.setattr(app_instance, "_write_output", lambda text: messages.append(text))
    app_instance._active_view = "setup"
    original_targets = cfg["analyzed_programs_and_libraries"]

    app_instance._add_selected_setup_target()

    assert cfg["analyzed_programs_and_libraries"] == ["TargetA"]
    assert cfg["analyzed_programs_and_libraries"] is not original_targets
    assert app_instance._dirty is True
    assert messages == ["Added analysis target 'TargetA' from the Setup view."]


def test_textual_setup_remove_selected_target_marks_dirty(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    program_dir = tmp_path / "programs"
    program_dir.mkdir()
    (program_dir / "TargetA.s").write_text("draft")

    cfg: dict[str, Any] = {
        "analyzed_programs_and_libraries": ["TargetA"],
        "program_dir": str(program_dir),
        "ABB_lib_dir": "",
        "other_lib_dirs": [],
        "mode": "draft",
    }
    app_instance = app_textual.SattLintTextualApp(
        cfg=cfg,
        summarize_targets_fn=lambda _cfg: "targets",
        analysis_menu_fn=lambda _cfg: None,
        documentation_menu_fn=lambda _cfg: None,
        config_menu_fn=lambda _cfg: None,
        tools_menu_fn=lambda _cfg: None,
        show_help_fn=lambda _cfg: None,
        save_config_fn=lambda _path, _cfg: None,
        config_path=None,
        quit_app_error=RuntimeError,
    )
    messages: list[str] = []

    monkeypatch.setattr(app_instance, "_refresh_summary", lambda: None)
    monkeypatch.setattr(app_instance, "_refresh_view", lambda: None)
    monkeypatch.setattr(app_instance, "_set_active_action", lambda _action_id: None)
    monkeypatch.setattr(app_instance, "_refresh_shell_state", lambda: None)
    monkeypatch.setattr(app_instance, "_write_output", lambda text: messages.append(text))
    app_instance._active_view = "setup"
    original_targets = cfg["analyzed_programs_and_libraries"]

    app_instance._remove_selected_setup_target()

    assert cfg["analyzed_programs_and_libraries"] == []
    assert cfg["analyzed_programs_and_libraries"] is not original_targets
    assert app_instance._dirty is True
    assert messages == ["Removed analysis target 'TargetA' from the Setup view."]


def test_textual_setup_prompt_updates_program_dir(monkeypatch: pytest.MonkeyPatch) -> None:
    cfg: dict[str, Any] = {
        "analyzed_programs_and_libraries": [],
        "program_dir": "/old/programs",
        "ABB_lib_dir": "",
        "other_lib_dirs": [],
        "mode": "draft",
    }
    app_instance = app_textual.SattLintTextualApp(
        cfg=cfg,
        summarize_targets_fn=lambda _cfg: "targets",
        analysis_menu_fn=lambda _cfg: None,
        documentation_menu_fn=lambda _cfg: None,
        config_menu_fn=lambda _cfg: None,
        tools_menu_fn=lambda _cfg: None,
        show_help_fn=lambda _cfg: None,
        save_config_fn=lambda _path, _cfg: None,
        config_path=None,
        quit_app_error=RuntimeError,
    )
    captured: dict[str, object] = {}
    messages: list[str] = []

    monkeypatch.setattr(app_instance, "_refresh_summary", lambda: None)
    monkeypatch.setattr(app_instance, "_refresh_view", lambda: None)
    monkeypatch.setattr(app_instance, "_set_active_action", lambda _action_id: None)
    monkeypatch.setattr(app_instance, "_refresh_shell_state", lambda: None)
    monkeypatch.setattr(app_instance, "_write_output", lambda text: messages.append(text))

    def _capture_request(
        request: app_textual_shared_module.InteractionRequest, on_response_fn: object | None = None
    ) -> None:
        captured["request"] = request
        captured["callback"] = on_response_fn

    monkeypatch.setattr(app_instance, "present_request", _capture_request)

    app_instance._prompt_setup_value("program_dir", label="program_dir")

    request = captured["request"]
    assert isinstance(request, app_textual_shared_module.InteractionRequest)
    assert request.kind == "prompt"
    assert request.default == "/old/programs"

    callback = captured["callback"]
    assert callable(callback)
    callback("/new/programs")

    assert cfg["program_dir"] == "/new/programs"
    assert app_instance._dirty is True
    assert messages == ["Updated program_dir from the Setup view."]


def test_textual_setup_prompt_replaces_whole_other_lib_dirs_list(monkeypatch: pytest.MonkeyPatch) -> None:
    original_other_dirs = ["/old/lib-a", "/old/lib-b"]
    cfg: dict[str, Any] = {
        "analyzed_programs_and_libraries": [],
        "program_dir": "/old/programs",
        "ABB_lib_dir": "",
        "other_lib_dirs": original_other_dirs,
        "mode": "draft",
    }
    app_instance = app_textual.SattLintTextualApp(
        cfg=cfg,
        summarize_targets_fn=lambda _cfg: "targets",
        analysis_menu_fn=lambda _cfg: None,
        documentation_menu_fn=lambda _cfg: None,
        config_menu_fn=lambda _cfg: None,
        tools_menu_fn=lambda _cfg: None,
        show_help_fn=lambda _cfg: None,
        save_config_fn=lambda _path, _cfg: None,
        config_path=None,
        quit_app_error=RuntimeError,
    )
    captured: dict[str, object] = {}
    messages: list[str] = []

    monkeypatch.setattr(app_instance, "_refresh_summary", lambda: None)
    monkeypatch.setattr(app_instance, "_refresh_view", lambda: None)
    monkeypatch.setattr(app_instance, "_set_active_action", lambda _action_id: None)
    monkeypatch.setattr(app_instance, "_refresh_shell_state", lambda: None)
    monkeypatch.setattr(app_instance, "_write_output", lambda text: messages.append(text))

    def _capture_request(
        request: app_textual_shared_module.InteractionRequest, on_response_fn: object | None = None
    ) -> None:
        captured["request"] = request
        captured["callback"] = on_response_fn

    monkeypatch.setattr(app_instance, "present_request", _capture_request)

    app_instance._prompt_setup_value("other_lib_dirs", label="other_lib_dirs", is_list=True)

    request = captured["request"]
    assert isinstance(request, app_textual_shared_module.InteractionRequest)
    assert request.kind == "prompt"
    assert request.message == "Enter the full comma-separated list for other_lib_dirs. Leave blank to clear the list."
    assert request.default == "/old/lib-a, /old/lib-b"

    callback = captured["callback"]
    assert callable(callback)
    callback("/new/lib-a, /new/lib-b")

    assert cfg["other_lib_dirs"] == ["/new/lib-a", "/new/lib-b"]
    assert cfg["other_lib_dirs"] is not original_other_dirs
    assert app_instance._dirty is True
    assert messages == ["Updated other_lib_dirs from the Setup view."]


def test_textual_save_action_does_not_clear_dirty_before_completion(monkeypatch: pytest.MonkeyPatch) -> None:
    app_instance = app_textual.SattLintTextualApp(
        cfg={},
        summarize_targets_fn=lambda _cfg: "targets",
        analysis_menu_fn=lambda _cfg: None,
        documentation_menu_fn=lambda _cfg: None,
        config_menu_fn=lambda _cfg: None,
        tools_menu_fn=lambda _cfg: None,
        show_help_fn=lambda _cfg: None,
        get_help_text_fn=lambda _cfg: "Help text",
        save_config_fn=lambda _path, _cfg: None,
        config_path=None,
        quit_app_error=RuntimeError,
    )
    app_instance._dirty = True
    started: list[str] = []
    refreshed: list[str] = []

    monkeypatch.setattr(app_instance, "_start_action", lambda *args, **kwargs: started.append("save"))
    monkeypatch.setattr(app_instance, "_refresh_summary", lambda: refreshed.append("refresh"))

    app_instance._handle_toolbar_action("setup-save")

    assert started == ["save"]
    assert app_instance._dirty is True
    assert refreshed == []


def test_textual_activate_view_leaves_dirty_setup_changes_unsaved(monkeypatch: pytest.MonkeyPatch) -> None:
    app_instance = _make_textual_app()
    app_instance._active_view = "setup"
    app_instance._dirty = True
    started: list[str] = []

    monkeypatch.setattr(app_instance, "_start_action", lambda *args, **kwargs: started.append("save"))
    monkeypatch.setattr(app_instance, "_refresh_view", lambda: None)
    monkeypatch.setattr(app_instance, "_set_active_action", lambda _action_id: None)
    monkeypatch.setattr(app_instance, "_refresh_shell_state", lambda: None)

    app_instance._activate_view("documentation")

    assert started == []
    assert app_instance._active_view == "documentation"
    assert app_instance._dirty is True


def test_textual_finish_action_clears_dirty_after_success() -> None:
    app_instance = app_textual.SattLintTextualApp(
        cfg={},
        summarize_targets_fn=lambda _cfg: "targets",
        analysis_menu_fn=lambda _cfg: None,
        documentation_menu_fn=lambda _cfg: None,
        config_menu_fn=lambda _cfg: None,
        tools_menu_fn=lambda _cfg: None,
        show_help_fn=lambda _cfg: None,
        save_config_fn=lambda _path, _cfg: None,
        config_path=None,
        quit_app_error=RuntimeError,
    )
    app_instance._dirty = True
    app_instance._set_active_action = lambda _action_id: None  # type: ignore[method-assign]
    app_instance._refresh_summary = lambda: None  # type: ignore[method-assign]

    app_instance._finish_action(clear_dirty_on_success=True)

    assert app_instance._dirty is False


def test_textual_quit_action_respects_busy_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    app_instance = app_textual.SattLintTextualApp(
        cfg={},
        summarize_targets_fn=lambda _cfg: "targets",
        analysis_menu_fn=lambda _cfg: None,
        documentation_menu_fn=lambda _cfg: None,
        config_menu_fn=lambda _cfg: None,
        tools_menu_fn=lambda _cfg: None,
        show_help_fn=lambda _cfg: None,
        save_config_fn=lambda _path, _cfg: None,
        config_path=None,
        quit_app_error=RuntimeError,
    )
    messages: list[str] = []
    exited: list[str] = []
    app_instance._busy = True

    monkeypatch.setattr(app_instance, "_write_output", lambda text: messages.append(text))
    monkeypatch.setattr(app_instance, "exit", lambda: exited.append("exit"))

    app_instance._handle_toolbar_action("action-quit")

    assert exited == []
    assert messages == ["An action is still running. Wait for it to finish before quitting."]


def test_textual_write_output_preserves_blank_lines(monkeypatch: pytest.MonkeyPatch) -> None:
    app_instance = app_textual.SattLintTextualApp(
        cfg={},
        summarize_targets_fn=lambda _cfg: "targets",
        analysis_menu_fn=lambda _cfg: None,
        documentation_menu_fn=lambda _cfg: None,
        config_menu_fn=lambda _cfg: None,
        tools_menu_fn=lambda _cfg: None,
        show_help_fn=lambda _cfg: None,
        save_config_fn=lambda _path, _cfg: None,
        config_path=None,
        quit_app_error=RuntimeError,
    )
    inserted: list[str] = []
    scrolled: list[bool] = []
    fake_widget = SimpleNamespace(
        document=SimpleNamespace(end=object()),
        insert=lambda text, *_args, **_kwargs: inserted.append(text),
        scroll_cursor_visible=lambda animate=False: scrolled.append(bool(animate)),
    )

    monkeypatch.setattr(app_instance, "query_one", lambda *_args, **_kwargs: fake_widget)

    app_instance._write_output("Summary\n\nDetails")

    assert "".join(inserted) == "Summary\n\nDetails\n"
    assert scrolled == [False]


def test_textual_write_output_inserts_spacing_before_target_headers(monkeypatch: pytest.MonkeyPatch) -> None:
    app_instance = app_textual.SattLintTextualApp(
        cfg={},
        summarize_targets_fn=lambda _cfg: "targets",
        analysis_menu_fn=lambda _cfg: None,
        documentation_menu_fn=lambda _cfg: None,
        config_menu_fn=lambda _cfg: None,
        tools_menu_fn=lambda _cfg: None,
        show_help_fn=lambda _cfg: None,
        save_config_fn=lambda _path, _cfg: None,
        config_path=None,
        quit_app_error=RuntimeError,
    )
    written: list[object] = []
    scrolled: list[bool] = []

    class FakeRichOutput:
        def __init__(self) -> None:
            self.text = ""

        def append_plain_text(self, text: str) -> None:
            self.text += text

        def write(self, renderable: object, **_kwargs: Any) -> None:
            written.append(renderable)

        def scroll_end(self, animate: bool = False) -> None:
            scrolled.append(bool(animate))

    fake_widget = FakeRichOutput()

    monkeypatch.setattr(app_instance, "query_one", lambda *_args, **_kwargs: fake_widget)

    app_instance._write_output("Analyze planner queue")
    app_instance._write_output("=== Target: DemoLib ===")

    assert fake_widget.text == "Analyze planner queue\n=== Target: DemoLib ===\n"
    assert isinstance(written[0], Text)
    assert str(written[0]) == "Analyze planner queue"
    assert written[1] == ""
    assert isinstance(written[2], Rule)


def test_textual_write_output_caps_retained_lines(monkeypatch: pytest.MonkeyPatch) -> None:
    app_instance = app_textual.SattLintTextualApp(
        cfg={},
        summarize_targets_fn=lambda _cfg: "targets",
        analysis_menu_fn=lambda _cfg: None,
        documentation_menu_fn=lambda _cfg: None,
        config_menu_fn=lambda _cfg: None,
        tools_menu_fn=lambda _cfg: None,
        show_help_fn=lambda _cfg: None,
        save_config_fn=lambda _path, _cfg: None,
        config_path=None,
        quit_app_error=RuntimeError,
    )

    class FakeRichOutput:
        def __init__(self) -> None:
            self.text = ""
            self._plain_text_parts: list[str] = []

        def clear(self) -> None:
            self.text = ""

        def append_plain_text(self, text: str) -> None:
            self._plain_text_parts.append(text)
            self.text += text

        def write(self, _renderable: object, **_kwargs: Any) -> None:
            return None

        def scroll_end(self, animate: bool = False) -> None:
            return None

    fake_widget = FakeRichOutput()

    monkeypatch.setattr(app_instance, "query_one", lambda *_args, **_kwargs: fake_widget)

    app_instance._write_output("\n".join(f"line {index}" for index in range(4005)))

    assert len(app_instance._session_output_lines) == 4000
    assert app_instance._session_output_lines[0] == "line 5"
    assert app_instance._session_output_dropped_line_count == 5
    assert app_instance._output_title_text() == "Session output - retaining last 4000 lines"
    assert fake_widget.text.startswith("line 5\n")
    assert "line 4\n" not in fake_widget.text


def test_textual_app_uses_explicit_mixins() -> None:
    assert issubclass(app_textual_module.SattLintTextualApp, app_textual_actions_module._TextualActionsMixin)
    assert issubclass(app_textual_module.SattLintTextualApp, app_textual_setup_module._TextualSetupMixin)
    assert issubclass(app_textual_module.SattLintTextualApp, app_textual_module._TextualAnalyzeMixin)


def test_textual_refresh_view_raises_when_required_widget_is_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = _make_textual_app()

        async with app_instance.run_test() as pilot:
            await pilot.pause()

            def _raise_missing(*_args: Any, **_kwargs: Any) -> object:
                raise app_textual_actions_module._TEXTUAL_QUERY_ERRORS[0]("missing view host")

            monkeypatch.setattr(app_instance, "query_exactly_one", _raise_missing, raising=False)
            monkeypatch.setattr(app_instance, "query_one", _raise_missing)

            with pytest.raises(app_textual_actions_module._TEXTUAL_QUERY_ERRORS[0], match="missing view host"):
                app_instance._refresh_view()

    asyncio.run(_run())


def test_textual_file_browser_selection_raises_when_required_widgets_are_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    browser = app_textual_widgets_module._FileBrowserScreen(
        start_paths=[Path(".")],
        candidates=(("demo", ("demo.x",)),),
    )

    def _raise_missing(*_args: Any, **_kwargs: Any) -> object:
        raise LookupError("missing file browser widget")

    monkeypatch.setattr(browser, "query_exactly_one", _raise_missing, raising=False)
    monkeypatch.setattr(browser, "query_one", _raise_missing)

    with pytest.raises(LookupError, match="missing file browser widget"):
        browser._set_candidate_selection(None)


def test_textual_toolbar_actions_are_ignored_while_interaction_screen_is_open(monkeypatch: pytest.MonkeyPatch) -> None:
    app_instance = app_textual.SattLintTextualApp(
        cfg={},
        summarize_targets_fn=lambda _cfg: "targets",
        analysis_menu_fn=lambda _cfg: None,
        documentation_menu_fn=lambda _cfg: None,
        config_menu_fn=lambda _cfg: None,
        tools_menu_fn=lambda _cfg: None,
        show_help_fn=lambda _cfg: None,
        save_config_fn=lambda _path, _cfg: None,
        config_path=None,
        quit_app_error=RuntimeError,
    )
    started: list[str] = []

    monkeypatch.setattr(app_instance, "_interaction_screen_active", lambda: True)
    monkeypatch.setattr(app_instance, "_start_action", lambda *args, **kwargs: started.append("started"))

    app_instance._handle_toolbar_action("action-analyze")

    assert started == []
