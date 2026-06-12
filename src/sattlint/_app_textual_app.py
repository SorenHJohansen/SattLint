# pyright: reportMissingImports=false, reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportUnknownLambdaType=false, reportGeneralTypeIssues=false, reportInvalidTypeForm=false, reportConstantRedefinition=false, reportPrivateUsage=false, reportUnusedClass=false, reportUnusedFunction=false, reportUnknownArgumentType=false

from __future__ import annotations

import asyncio
import threading
from contextlib import suppress
from dataclasses import dataclass
from typing import Any, ClassVar

from ._app_textual_actions import _TextualActionsMixin
from ._app_textual_analyze import _TextualAnalyzeMixin
from ._app_textual_setup import _TextualSetupMixin
from ._app_textual_shared import (
    _TEXTUAL_APP,
    _TEXTUAL_BUTTON,
    _TEXTUAL_COMPOSE_RESULT,
    _TEXTUAL_FOOTER,
    _TEXTUAL_HORIZONTAL,
    _TEXTUAL_LIST_VIEW,
    _TEXTUAL_RICH_LOG,
    _TEXTUAL_STATIC,
    _TEXTUAL_TEXT_AREA,
    _TEXTUAL_VERTICAL,
    DEFAULT_SHELL_TITLE,
    TEXTUAL_SHELL_CSS,
    TextualInteractionBridge,
    _SessionOutputLog,
    _ShellViewState,
)
from .config_types import ConfigDict


@dataclass(frozen=True)
class _AstRefreshStartupResult:
    ok: bool
    output: str


_DEFAULT_VIEW_REGISTRY: dict[str, _ShellViewState] = {
    "analyze": _ShellViewState(
        action_id="action-analyze",
        title="Analyze",
        description="Plan one or more analyses, inspect the normalized queue, and run the selected steps directly.",
        note="Build an analysis queue in this view and run the shared planner directly.",
        launch_label="Open Analyze Planner",
    ),
    "documentation": _ShellViewState(
        action_id="action-documentation",
        title="Documentation",
        description="Preview unit candidates, adjust scope, and generate DOCX output directly from this screen.",
        note="Documentation actions are available directly in this view.",
        launch_label="Open Documentation Flow",
    ),
    "setup": _ShellViewState(
        action_id="action-setup",
        title="Setup",
        description="Click targets to add or remove them, then adjust directories and runtime settings inline.",
        note="Changes happen directly in this view and remain unsaved until you use Save.",
        launch_label="Open Setup Flow",
    ),
    "tools": _ShellViewState(
        action_id="action-tools",
        title="Tools",
        description=(
            "Run diagnostics, dumps, source diffs, cache refreshes, and targeted tracing tools directly from this "
            "screen."
        ),
        note=(
            "Use the upper actions for setup and cache troubleshooting, then use the trace tools when an analysis "
            "report needs source-level follow-up."
        ),
        launch_label="Open Tools Flow",
    ),
    "help": _ShellViewState(
        action_id="action-help",
        title="Help",
        description="See first-run guidance and the recommended workflow for setup, analysis, and documentation.",
        note="Open the guide to review the recommended setup, analysis, and documentation workflow.",
        launch_label="Open Help Guide",
    ),
}


if _TEXTUAL_APP is not None:
    _SessionOutputWidget: Any = _SessionOutputLog if _TEXTUAL_RICH_LOG is not None else None

    class _AstRefreshTextualAppImpl(_TEXTUAL_APP):
        """Shows startup AST-cache progress before the main Textual shell opens."""

        CSS = """
        Screen {
            background: #f4efde;
            color: #001ba3;
        }

        #ast-refresh-host {
            width: 100%;
            height: 1fr;
            align: center middle;
        }

        #ast-refresh-card {
            width: 72;
            max-width: 90%;
            padding: 1 2;
            background: #e6decb;
            color: #000000;
            border: tall #0077b3;
        }

        #ast-refresh-title {
            text-style: bold;
        }

        #ast-refresh-body {
            margin-top: 1;
        }

        #ast-refresh-status {
            margin-top: 1;
            color: #58787e;
        }
        """

        def __init__(self, *, refresh_ast_cache_fn: Any) -> None:
            super().__init__()
            self._refresh_ast_cache_fn = refresh_ast_cache_fn
            self._status_lines: list[str] = ["Starting cached AST refresh..."]
            self._failure_prompt: str | None = None
            self._refresh_failed = False
            self._refresh_exception: BaseException | None = None

        def compose(self) -> _TEXTUAL_COMPOSE_RESULT:
            with _TEXTUAL_VERTICAL(id="ast-refresh-host"), _TEXTUAL_VERTICAL(id="ast-refresh-card"):
                yield _TEXTUAL_STATIC("Refreshing cached ASTs", id="ast-refresh-title")
                yield _TEXTUAL_STATIC(
                    "Checking the cached project graphs before opening the main Textual shell.",
                    id="ast-refresh-body",
                )
                yield _TEXTUAL_STATIC("\n".join(self._status_lines), id="ast-refresh-status")

        def on_mount(self) -> None:
            threading.Thread(target=self._run_refresh, daemon=True).start()

        def _render_status_text(self) -> str:
            lines = list(self._status_lines)
            if self._failure_prompt is not None:
                if lines:
                    lines.append("")
                lines.append(self._failure_prompt)
            return "\n".join(lines)

        def _update_status(self, message: str) -> None:
            normalized = message.replace("\r\n", "\n").replace("\r", "\n")
            if not normalized:
                return
            self._status_lines.extend(normalized.split("\n"))
            self.query_one("#ast-refresh-status", _TEXTUAL_STATIC).update(self._render_status_text())

        def _set_failure_prompt(self) -> None:
            self._failure_prompt = (
                "AST cache startup reported issues. Press Enter or Escape to continue into the shell."
            )
            self.query_one("#ast-refresh-status", _TEXTUAL_STATIC).update(self._render_status_text())

        def _emit_status(self, *parts: object) -> None:
            rendered_parts = [str(part) for part in parts if part is not None]
            if not rendered_parts:
                return
            if len(rendered_parts) == 1:
                message = rendered_parts[0]
            else:
                message = " ".join(part.strip() for part in rendered_parts)
            if not message:
                return
            if not message.strip():
                return
            self.call_from_thread(self._update_status, message)

        def _finish_refresh(self, *, ok: bool, exc: BaseException | None = None) -> None:
            self._refresh_failed = not ok
            self._refresh_exception = exc
            if ok:
                self.exit()
                return
            self._set_failure_prompt()

        def on_key(self, event: Any) -> None:
            if self._failure_prompt is None:
                return
            if str(getattr(event, "key", "")) not in {"enter", "escape"}:
                return
            with suppress(Exception):
                event.prevent_default()
            self.exit()

        def _run_refresh(self) -> None:
            refresh_ok = False
            refresh_exception: BaseException | None = None
            try:
                refresh_ok = bool(self._refresh_ast_cache_fn(self._emit_status))
            except (
                OSError,
                RuntimeError,
                ValueError,
            ) as exc:  # pragma: no cover - exercised through direct method test
                refresh_ok = False
                refresh_exception = exc
                self.call_from_thread(self._update_status, f"AST cache refresh failed: {exc}")
            finally:
                self.call_from_thread(self._finish_refresh, ok=refresh_ok, exc=refresh_exception)

    class SattLintTextualAppImpl(_TextualSetupMixin, _TextualActionsMixin, _TextualAnalyzeMixin, _TEXTUAL_APP):
        """Owns the main Textual shell by composing the setup, actions, and analyze mixins."""

        TITLE = DEFAULT_SHELL_TITLE

        BINDINGS: ClassVar[list[tuple[str, str, str]]] = [
            ("1", "show_analyze", "Analyze"),
            ("2", "show_documentation", "Docs"),
            ("3", "show_setup", "Setup"),
            ("4", "show_tools", "Tools"),
            ("5", "show_help", "Help"),
            ("slash", "prompt_view_filter", "Filter"),
            ("question_mark", "show_help", "Help"),
            ("ctrl+h", "show_help", "Help"),
            ("ctrl+c", "copy_output", "Copy Output"),
            ("ctrl+g", "cancel_running_analysis", "Cancel Analysis"),
            ("ctrl+l", "clear_output", "Clear Output"),
            ("escape", "back", "Back"),
            ("q", "quit_shell", "Quit"),
            ("tab", "focus_next_control", "Next"),
            ("shift+tab", "focus_previous_control", "Prev"),
        ]

        _ACTION_IDS = (
            "action-analyze",
            "action-documentation",
            "action-setup",
            "action-tools",
            "action-help",
            "action-quit",
        )

        _VIEW_REGISTRY: ClassVar[dict[str, _ShellViewState]] = _DEFAULT_VIEW_REGISTRY
        _VIEW_ACTIONS: ClassVar[dict[str, str]] = {
            state.action_id: view_name for view_name, state in _DEFAULT_VIEW_REGISTRY.items() if view_name != "help"
        }

        CSS = TEXTUAL_SHELL_CSS

        def __init__(
            self,
            *,
            cfg: ConfigDict,
            summarize_targets_fn: Any,
            analysis_menu_fn: Any,
            documentation_menu_fn: Any,
            config_menu_fn: Any,
            tools_menu_fn: Any,
            show_help_fn: Any,
            get_help_text_fn: Any | None = None,
            save_config_fn: Any,
            config_path: Any,
            quit_app_error: type[BaseException],
            app_module: Any | None = None,
            self_check_fn: Any | None = None,
            dump_menu_fn: Any | None = None,
            source_diff_fn: Any | None = None,
            force_refresh_ast_fn: Any | None = None,
            startup_output: str = "",
            startup_output_is_warning: bool = False,
        ) -> None:
            super().__init__()
            self._app_module = app_module
            self._cfg = cfg
            self._summarize_targets_fn = summarize_targets_fn
            self._analysis_menu_fn = analysis_menu_fn
            self._documentation_menu_fn = documentation_menu_fn
            self._config_menu_fn = config_menu_fn
            self._tools_menu_fn = tools_menu_fn
            self._show_help_fn = show_help_fn
            self._get_help_text_fn = get_help_text_fn
            self._save_config_fn = save_config_fn
            self._config_path = config_path
            self._quit_app_error = quit_app_error
            self._busy = False
            self._dirty = False
            self._active_view = "analyze"
            self._active_job_action_id: str | None = None
            self._active_job_label: str | None = None
            self._active_job_started_at: float | None = None
            self._active_job_cancel_event: threading.Event | None = None
            self._active_job_cancel_requested = False
            self._active_job_thread: threading.Thread | None = None
            self._active_job_worker: Any | None = None
            self._analyze_focused_entry_id: str | None = None
            self._analyze_selected_entry_ids: set[str] = set()
            self._analyze_filter_text = ""
            self._suppress_analyze_planner_events = False
            self._setup_candidate_index = 0
            self._setup_filter_text = ""
            self._setup_target_names_list: list[str] = []
            self._selected_configured_target: str | None = None
            self._active_request = None
            self._active_request_callback: Any = None
            self._interaction_pane: Any = None
            self._pending_ui_tasks: set[asyncio.Task[Any]] = set()
            self._self_check_fn = self_check_fn or (lambda _cfg: None)
            self._dump_menu_fn = dump_menu_fn or (lambda _cfg: None)
            self._source_diff_fn = source_diff_fn or (lambda _cfg: None)
            self._force_refresh_ast_fn = force_refresh_ast_fn or (lambda _cfg: None)
            self._startup_output = startup_output.strip("\n")
            self._startup_output_is_warning = startup_output_is_warning
            self._last_output_line: str | None = None
            self._session_output_lines: list[str] = []
            self._session_output_dropped_line_count = 0

        def compose(self) -> _TEXTUAL_COMPOSE_RESULT:  # noqa: PLR0915
            with _TEXTUAL_HORIZONTAL(id="actions"):
                yield _TEXTUAL_BUTTON("Analyze", id="action-analyze", classes="raised-button toolbar-button")
                yield _TEXTUAL_BUTTON("Docs", id="action-documentation", classes="raised-button toolbar-button")
                yield _TEXTUAL_BUTTON("Tools", id="action-tools", classes="raised-button toolbar-button")
                yield _TEXTUAL_STATIC("", id="actions-spacer")
                yield _TEXTUAL_BUTTON("Setup", id="action-setup", classes="raised-button toolbar-button")
                yield _TEXTUAL_BUTTON("Help & Guide", id="action-help", classes="raised-button toolbar-button")
                yield _TEXTUAL_BUTTON("Quit", id="action-quit", classes="raised-button toolbar-button")
            with _TEXTUAL_VERTICAL(id="content-host"):
                with _TEXTUAL_VERTICAL(id="workspace-host"):
                    with _TEXTUAL_VERTICAL(id="view-pane"):
                        yield _TEXTUAL_STATIC("", id="view-title")
                        with _TEXTUAL_VERTICAL(id="view-host"):
                            with _TEXTUAL_HORIZONTAL(id="view-header"):
                                with _TEXTUAL_VERTICAL(id="view-copy"):
                                    yield _TEXTUAL_STATIC("", id="view-description")
                                    yield _TEXTUAL_STATIC("", id="view-note")
                                with _TEXTUAL_VERTICAL(id="view-side-actions"):
                                    with _TEXTUAL_HORIZONTAL(id="view-actions"):
                                        yield _TEXTUAL_BUTTON(
                                            "", id="view-primary-action", classes="raised-button toolbar-button"
                                        )
                                    with _TEXTUAL_HORIZONTAL(id="analyze-actions-primary", classes="is-hidden"):
                                        yield _TEXTUAL_BUTTON(
                                            "Run selected analyses",
                                            id="analyze-run-selected",
                                            classes="raised-button toolbar-button",
                                        )
                                        yield _TEXTUAL_BUTTON(
                                            "Cancel running",
                                            id="analyze-cancel-running",
                                            classes="raised-button toolbar-button",
                                        )
                                        yield _TEXTUAL_BUTTON(
                                            "Clear selection",
                                            id="analyze-clear-selection",
                                            classes="raised-button toolbar-button",
                                        )
                                        yield _TEXTUAL_BUTTON(
                                            "Clear output",
                                            id="analyze-clear-output",
                                            classes="raised-button toolbar-button",
                                        )
                                    with _TEXTUAL_HORIZONTAL(id="documentation-actions", classes="is-hidden"):
                                        yield _TEXTUAL_BUTTON(
                                            "Generate DOCX",
                                            id="documentation-generate",
                                            classes="raised-button toolbar-button",
                                        )
                                        yield _TEXTUAL_BUTTON(
                                            "Preview candidates",
                                            id="documentation-preview-candidates",
                                            classes="raised-button toolbar-button",
                                        )
                                        yield _TEXTUAL_BUTTON(
                                            "Use all detected units",
                                            id="documentation-scope-all",
                                            classes="raised-button toolbar-button",
                                        )
                                        yield _TEXTUAL_BUTTON(
                                            "Scope by moduletype",
                                            id="documentation-scope-moduletype",
                                            classes="raised-button toolbar-button",
                                        )
                                        yield _TEXTUAL_BUTTON(
                                            "Scope by instance path",
                                            id="documentation-scope-instance-path",
                                            classes="raised-button toolbar-button",
                                        )
                                    with _TEXTUAL_HORIZONTAL(id="tools-actions", classes="is-hidden"):
                                        yield _TEXTUAL_BUTTON(
                                            "Self-check diagnostics",
                                            id="tools-self-check",
                                            classes="raised-button toolbar-button",
                                        )
                                        yield _TEXTUAL_BUTTON(
                                            "Diagnostics & dumps",
                                            id="tools-dumps",
                                            classes="raised-button toolbar-button",
                                        )
                                        yield _TEXTUAL_BUTTON(
                                            "Source diff report",
                                            id="tools-source-diff",
                                            classes="raised-button toolbar-button",
                                        )
                                        yield _TEXTUAL_BUTTON(
                                            "Refresh all caches",
                                            id="tools-refresh-ast",
                                            classes="raised-button toolbar-button",
                                        )
                                        yield _TEXTUAL_BUTTON(
                                            "Datatype field trace",
                                            id="tools-datatype-usage",
                                            classes="raised-button toolbar-button",
                                        )
                                        yield _TEXTUAL_BUTTON(
                                            "Variable usage trace",
                                            id="tools-variable-trace",
                                            classes="raised-button toolbar-button",
                                        )
                                        yield _TEXTUAL_BUTTON(
                                            "Module local usage",
                                            id="tools-module-locals",
                                            classes="raised-button toolbar-button",
                                        )
                            with _TEXTUAL_HORIZONTAL(id="analyze-browser", classes="is-hidden"):
                                with _TEXTUAL_VERTICAL(id="analyze-browser-left"):
                                    pass
                                yield _TEXTUAL_STATIC("", id="analyze-browser-right")
                            with _TEXTUAL_HORIZONTAL(id="setup-browser", classes="is-hidden"):
                                with _TEXTUAL_VERTICAL(id="setup-targets-col"):
                                    yield _TEXTUAL_STATIC("Analysis Targets", classes="setup-section-title")
                                    yield _TEXTUAL_LIST_VIEW(id="setup-target-listview")
                                    with _TEXTUAL_HORIZONTAL(id="setup-target-actions"):
                                        yield _TEXTUAL_BUTTON(
                                            "Remove", id="setup-target-remove", classes="raised-button", disabled=True
                                        )
                                        yield _TEXTUAL_BUTTON(
                                            "Add from file...", id="setup-target-browse", classes="raised-button"
                                        )
                                with _TEXTUAL_VERTICAL(id="setup-settings-col"):
                                    yield _TEXTUAL_STATIC("Configuration", classes="setup-section-title")
                                    yield _TEXTUAL_STATIC("Directories", classes="setup-group-title")
                                    with _TEXTUAL_HORIZONTAL(classes="setup-row"):
                                        yield _TEXTUAL_BUTTON(
                                            "Program folder",
                                            id="setup-edit-program-dir",
                                            classes="raised-button setup-row-button",
                                        )
                                        yield _TEXTUAL_STATIC(
                                            "", id="setup-label-program-dir", classes="setup-row-label"
                                        )
                                    with _TEXTUAL_HORIZONTAL(classes="setup-row"):
                                        yield _TEXTUAL_BUTTON(
                                            "ABB library",
                                            id="setup-edit-abb-dir",
                                            classes="raised-button setup-row-button",
                                        )
                                        yield _TEXTUAL_STATIC("", id="setup-label-abb-dir", classes="setup-row-label")
                                    with _TEXTUAL_HORIZONTAL(classes="setup-row"):
                                        yield _TEXTUAL_BUTTON(
                                            "Other libraries",
                                            id="setup-edit-other-lib-dirs",
                                            classes="raised-button setup-row-button",
                                        )
                                        yield _TEXTUAL_STATIC(
                                            "", id="setup-label-other-dirs", classes="setup-row-label"
                                        )
                                    with _TEXTUAL_HORIZONTAL(classes="setup-row"):
                                        yield _TEXTUAL_BUTTON(
                                            "ICF folder",
                                            id="setup-edit-icf-dir",
                                            classes="raised-button setup-row-button",
                                        )
                                        yield _TEXTUAL_STATIC("", id="setup-label-icf-dir", classes="setup-row-label")
                                    yield _TEXTUAL_STATIC("Mode & Config", classes="setup-group-title")
                                    with _TEXTUAL_HORIZONTAL(classes="setup-row"):
                                        yield _TEXTUAL_BUTTON(
                                            "Mode", id="setup-toggle-mode", classes="raised-button setup-row-button"
                                        )
                                        yield _TEXTUAL_STATIC("", id="setup-label-mode", classes="setup-row-label")
                                    with _TEXTUAL_HORIZONTAL(classes="setup-row"):
                                        yield _TEXTUAL_BUTTON(
                                            "Scan root only",
                                            id="setup-toggle-scan-root-only",
                                            classes="raised-button setup-row-button",
                                        )
                                        yield _TEXTUAL_STATIC(
                                            "", id="setup-label-scan-root-only", classes="setup-row-label"
                                        )
                                    with _TEXTUAL_HORIZONTAL(classes="setup-row"):
                                        yield _TEXTUAL_BUTTON(
                                            "Fast cache",
                                            id="setup-toggle-fast-cache-validation",
                                            classes="raised-button setup-row-button",
                                        )
                                        yield _TEXTUAL_STATIC(
                                            "", id="setup-label-fast-cache", classes="setup-row-label"
                                        )
                                    yield _TEXTUAL_STATIC("Runtime", classes="setup-group-title")
                                    with _TEXTUAL_HORIZONTAL(classes="setup-row"):
                                        yield _TEXTUAL_BUTTON(
                                            "Debug logging",
                                            id="setup-toggle-debug",
                                            classes="raised-button setup-row-button",
                                        )
                                        yield _TEXTUAL_STATIC("", id="setup-label-debug", classes="setup-row-label")
                                    with _TEXTUAL_HORIZONTAL(classes="setup-row"):
                                        yield _TEXTUAL_BUTTON(
                                            "Telemetry",
                                            id="setup-toggle-telemetry",
                                            classes="raised-button setup-row-button",
                                        )
                                        yield _TEXTUAL_STATIC("", id="setup-label-telemetry", classes="setup-row-label")
                                    yield _TEXTUAL_STATIC("Save", classes="setup-group-title")
                                    yield _TEXTUAL_BUTTON(
                                        "Save config", id="setup-save", classes="raised-button setup-row-button"
                                    )
                    with _TEXTUAL_VERTICAL(id="output-pane"):
                        yield _TEXTUAL_STATIC("Session output", id="output-title")
                        if _SessionOutputWidget is None:
                            yield _TEXTUAL_TEXT_AREA(
                                "",
                                id="output",
                                read_only=True,
                                soft_wrap=True,
                                show_line_numbers=False,
                            )
                        else:
                            yield _SessionOutputWidget(id="output")
                with _TEXTUAL_VERTICAL(id="interaction-host"):
                    pass
            yield _TEXTUAL_FOOTER()

        def on_mount(self) -> None:
            self._refresh_summary()
            self._refresh_view()
            self._set_active_action(None)
            self._refresh_shell_state()
            self.query_one("#action-analyze", _TEXTUAL_BUTTON).focus()
            self._write_output("Textual shell ready. Use the action bar to move between native TUI views and actions.")
            if self._startup_output:
                if self._startup_output_is_warning:
                    self._write_output(
                        "AST cache startup checks reported issues before the shell opened. Review the preserved log below."
                    )
                else:
                    self._write_output("Initial AST loading log:")
                self._write_output(self._startup_output)

        def _view_state(self, view_name: str) -> _ShellViewState:
            return self._VIEW_REGISTRY.get(view_name, self._VIEW_REGISTRY["analyze"])

    _AstRefreshTextualAppImpl.__name__ = "_AstRefreshTextualApp"
    _AstRefreshTextualAppImpl.__qualname__ = "_AstRefreshTextualApp"
    _AstRefreshTextualApp = _AstRefreshTextualAppImpl
    SattLintTextualAppImpl.__name__ = "SattLintTextualApp"
    SattLintTextualAppImpl.__qualname__ = "SattLintTextualApp"
    SattLintTextualApp = SattLintTextualAppImpl
else:  # pragma: no cover - optional dependency path
    _AstRefreshTextualApp: Any = None
    SattLintTextualApp: Any = None


def _run_textual_ast_refresh_screen(cfg: ConfigDict, *, app_module: Any) -> _AstRefreshStartupResult:
    has_targets_fn = getattr(app_module, "_has_analyzed_targets", None)
    ensure_ast_cache_fn = getattr(app_module, "ensure_ast_cache", None)
    if not callable(has_targets_fn) or not callable(ensure_ast_cache_fn):
        return _AstRefreshStartupResult(ok=True, output="")
    if not has_targets_fn(cfg):
        return _AstRefreshStartupResult(ok=True, output="")

    loading_app = _AstRefreshTextualApp(
        refresh_ast_cache_fn=lambda emit_status_fn: ensure_ast_cache_fn(cfg, emit_output_fn=emit_status_fn)
    )
    loading_app.run()
    status_lines = tuple(str(line) for line in getattr(loading_app, "_status_lines", ()) if str(line) or line == "")
    output = "\n".join(status_lines).strip("\n")
    refresh_failed = bool(getattr(loading_app, "_refresh_failed", False))
    return _AstRefreshStartupResult(ok=not refresh_failed, output=output)


def run_textual_shell(
    cfg: ConfigDict,
    *,
    app_module: Any,
    summarize_targets_fn: Any,
    analysis_menu_fn: Any | None = None,
    documentation_menu_fn: Any | None = None,
    config_menu_fn: Any | None = None,
    tools_menu_fn: Any | None = None,
    show_help_fn: Any,
    get_help_text_fn: Any | None = None,
    save_config_fn: Any,
    config_path: Any,
    quit_app_error: type[BaseException],
    **_unused: Any,
) -> None:
    if _TEXTUAL_APP is None:
        raise RuntimeError("Textual UI requested, but textual is not installed")

    startup_result = _run_textual_ast_refresh_screen(cfg, app_module=app_module)

    def _noop_menu_action(_cfg: ConfigDict) -> None:
        return None

    textual_app = SattLintTextualApp(
        cfg=cfg,
        summarize_targets_fn=summarize_targets_fn,
        analysis_menu_fn=analysis_menu_fn or _noop_menu_action,
        documentation_menu_fn=documentation_menu_fn or _noop_menu_action,
        config_menu_fn=config_menu_fn or _noop_menu_action,
        tools_menu_fn=tools_menu_fn or _noop_menu_action,
        app_module=app_module,
        self_check_fn=app_module.self_check,
        dump_menu_fn=app_module.dump_menu,
        source_diff_fn=lambda cfg: app_module.run_source_diff_report(cfg, _pause_fn=lambda: None),
        force_refresh_ast_fn=app_module.refresh_analysis_caches,
        show_help_fn=show_help_fn,
        get_help_text_fn=get_help_text_fn,
        save_config_fn=save_config_fn,
        config_path=config_path,
        quit_app_error=quit_app_error,
        startup_output=startup_result.output,
        startup_output_is_warning=not startup_result.ok,
    )
    bridge = TextualInteractionBridge(
        submit_request_fn=lambda request: textual_app.call_from_thread(textual_app.present_request, request)
    )
    app_module.set_textual_menu_interaction(bridge.as_menu_interaction())
    try:
        textual_app.run()
    finally:
        app_module.clear_textual_menu_interaction()
