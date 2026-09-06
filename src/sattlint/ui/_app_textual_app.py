# pyright: reportMissingImports=false, reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportUnknownLambdaType=false, reportGeneralTypeIssues=false, reportInvalidTypeForm=false, reportConstantRedefinition=false, reportPrivateUsage=false, reportUnusedClass=false, reportUnusedFunction=false, reportUnknownArgumentType=false

from __future__ import annotations

import asyncio
import threading
from collections.abc import Callable
from typing import Any, ClassVar

from ..config.types import ConfigDict
from ._app_textual_actions import _TextualActionsMixin
from ._app_textual_analyze import _TextualAnalyzeMixin
from ._app_textual_results import _TextualResultsMixin
from ._app_textual_settings import _TextualSettingsMixin
from ._app_textual_setup import _TextualSetupMixin
from ._app_textual_shared import (
    _TEXTUAL_APP,
    _TEXTUAL_BUTTON,
    _TEXTUAL_COMPOSE_RESULT,
    _TEXTUAL_FOOTER,
    _TEXTUAL_HORIZONTAL,
    _TEXTUAL_LIST_VIEW,
    _TEXTUAL_STATIC,
    _TEXTUAL_VERTICAL,
    APP_SHELL_BINDINGS,
    DEFAULT_SHELL_TITLE,
    MENU_DEFINITIONS,
    TEXTUAL_SHELL_CSS,
    TextualInteractionBridge,
    _SessionOutputLog,
    _ShellViewState,
)
from ._app_textual_widgets import _MenubarWidget

_DEFAULT_VIEW_REGISTRY: dict[str, _ShellViewState] = {
    "analyze": _ShellViewState(
        action_id="action-analyze",
        title="Analyze",
        description="",
        note="",
        launch_label="Open Analyze Planner",
    ),
    "settings": _ShellViewState(
        action_id="action-settings",
        title="App Settings",
        description="App-level settings shared across every configuration.",
        note="App settings are saved to your user config (config.toml).",
        launch_label="Open Settings",
    ),
    "results": _ShellViewState(
        action_id="action-results",
        title="Results",
        description="Browse previous analysis runs and inspect their results.",
        note="Select a run on the left, then switch between the results tree and the raw output.",
        launch_label="Open Results",
    ),
    "setup": _ShellViewState(
        action_id="action-setup",
        title="Configuration Settings",
        description="Click targets to add or remove them, then adjust directories and runtime settings inline.",
        note="Changes are saved automatically to the configuration file.",
        launch_label="Open Setup Flow",
    ),
    "help": _ShellViewState(
        action_id="action-help",
        title="Help",
        description="See first-run guidance and the recommended workflow for setup and analysis.",
        note="Open the guide to review the recommended setup and analysis workflow.",
        launch_label="Open Help Guide",
    ),
}


if _TEXTUAL_APP is not None:
    _SessionOutputWidget: Any = _SessionOutputLog

    class SattLintTextualAppImpl(
        _TextualSetupMixin,
        _TextualActionsMixin,
        _TextualAnalyzeMixin,
        _TextualSettingsMixin,
        _TextualResultsMixin,
        _TEXTUAL_APP,
    ):
        """Owns the main Textual shell by composing the setup, actions, analyze, settings, and results mixins."""

        TITLE = DEFAULT_SHELL_TITLE

        BINDINGS: ClassVar[list[tuple[str, str, str]]] = APP_SHELL_BINDINGS

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
            show_help_fn: Any,
            get_help_text_fn: Any | None = None,
            save_config_fn: Any,
            config_path: Any,
            quit_app_error: type[BaseException],
            analysis_handlers: dict[str, Callable[..., Any]] | None = None,
            get_enabled_analyzers_fn: Any | None = None,
            ensure_ast_cache_fn: Any | None = None,
        ) -> None:
            super().__init__()
            self._analysis_handlers = analysis_handlers or {}
            self._get_enabled_analyzers_fn = get_enabled_analyzers_fn
            self._ensure_ast_cache_fn = ensure_ast_cache_fn
            self._cfg = cfg
            self._summarize_targets_fn = summarize_targets_fn
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
            self._project: Any | None = None
            self._ast_refresh_pending = False
            self._analyze_focused_entry_id: str | None = None
            self._analyze_selected_entry_ids: set[str] = set()
            self._analyze_filter_text = ""
            self._analyze_help_shown = False
            self._suppress_analyze_planner_events = False
            self._selected_run_record = None
            self._results_run_summaries: list[object] = []
            self._results_tree_widget = None
            self._setup_candidate_index = 0
            self._setup_filter_text = ""
            self._setup_target_names_list: list[str] = []
            self._selected_configured_target: str | None = None
            self._active_request = None
            self._active_request_callback: Any = None
            self._interaction_pane: Any = None
            self._pending_ui_tasks: set[asyncio.Task[Any]] = set()
            self._welcome_shown = False
            self._last_output_line: str | None = None
            self._session_output_lines: list[str] = []
            self._session_output_dropped_line_count = 0

        def compose(self) -> _TEXTUAL_COMPOSE_RESULT:  # noqa: PLR0915
            with _TEXTUAL_VERTICAL(id="top-bar"):
                yield _MenubarWidget(menus=MENU_DEFINITIONS)
                with _TEXTUAL_HORIZONTAL(id="nav-tabs"):
                    yield _TEXTUAL_STATIC("  Analyze  ", id="nav-tab-analyze", classes="nav-tab")
                    yield _TEXTUAL_STATIC("  Results  ", id="nav-tab-results", classes="nav-tab")
                    yield _TEXTUAL_STATIC("  Configuration Settings  ", id="nav-tab-setup", classes="nav-tab")
                    yield _TEXTUAL_STATIC("  App Settings  ", id="nav-tab-settings", classes="nav-tab")
            with _TEXTUAL_VERTICAL(id="content-host"):
                with _TEXTUAL_VERTICAL(id="workspace-host"):  # noqa: SIM117
                    with _TEXTUAL_VERTICAL(id="view-pane"):
                        yield _TEXTUAL_STATIC("", id="view-title")
                        with _TEXTUAL_VERTICAL(id="view-host"):
                            with _TEXTUAL_HORIZONTAL(id="view-header"):
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
                                with _TEXTUAL_VERTICAL(id="view-copy"):
                                    yield _TEXTUAL_STATIC("", id="view-description")
                                    yield _TEXTUAL_STATIC("", id="view-note")
                            with _TEXTUAL_HORIZONTAL(id="analyze-split-body"):
                                with _TEXTUAL_VERTICAL(id="analyze-browser", classes="is-hidden"):  # noqa: SIM117
                                    with _TEXTUAL_VERTICAL(id="analyze-browser-left"):
                                        pass
                                with _TEXTUAL_VERTICAL(id="output-pane"):
                                    yield _TEXTUAL_STATIC("Session output", id="output-title")
                                    yield _SessionOutputWidget(id="output")
                        with _TEXTUAL_HORIZONTAL(id="setup-browser", classes="is-hidden"):
                            with _TEXTUAL_VERTICAL(id="setup-targets-section"):
                                yield _TEXTUAL_STATIC("Analysis Targets", id="setup-targets-title")
                                with _TEXTUAL_VERTICAL(id="setup-targets-col"):
                                    with _TEXTUAL_VERTICAL(id="setup-target-inner"):
                                        yield _TEXTUAL_LIST_VIEW(id="setup-target-listview")
                                    with _TEXTUAL_HORIZONTAL(id="setup-target-actions"):
                                        yield _TEXTUAL_BUTTON(
                                            "Remove", id="setup-target-remove", classes="raised-button", disabled=True
                                        )
                                        yield _TEXTUAL_BUTTON(
                                            "Add from file...", id="setup-target-browse", classes="raised-button"
                                        )
                            with _TEXTUAL_VERTICAL(id="setup-settings-section"):
                                yield _TEXTUAL_STATIC("Configuration", id="setup-config-title")
                                with _TEXTUAL_VERTICAL(id="setup-settings-col"):
                                    with _TEXTUAL_VERTICAL(id="setup-group-dirs", classes="setup-group-box"):
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
                                            yield _TEXTUAL_STATIC(
                                                "", id="setup-label-abb-dir", classes="setup-row-label"
                                            )
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
                                                "Remove...",
                                                id="setup-edit-other-lib-dirs-remove",
                                                classes="raised-button setup-row-button-compact",
                                            )
                                        with _TEXTUAL_HORIZONTAL(classes="setup-row"):
                                            yield _TEXTUAL_BUTTON(
                                                "ICF folder",
                                                id="setup-edit-icf-dir",
                                                classes="raised-button setup-row-button",
                                            )
                                            yield _TEXTUAL_STATIC(
                                                "", id="setup-label-icf-dir", classes="setup-row-label"
                                            )
                                    with _TEXTUAL_VERTICAL(id="setup-group-mode", classes="setup-group-box"):
                                        yield _TEXTUAL_STATIC("Mode & Config", classes="setup-group-title")
                                        with _TEXTUAL_HORIZONTAL(classes="setup-row"):
                                            yield _TEXTUAL_BUTTON(
                                                "Mode", id="setup-toggle-mode", classes="raised-button setup-row-button"
                                            )
                                            yield _TEXTUAL_STATIC("", id="setup-label-mode", classes="setup-row-label")
                        with _TEXTUAL_HORIZONTAL(id="settings-browser", classes="is-hidden"):  # noqa: SIM117
                            with _TEXTUAL_VERTICAL(id="settings-settings-section"):
                                yield _TEXTUAL_STATIC("App Settings", id="settings-config-title")
                                with _TEXTUAL_VERTICAL(id="settings-settings-col"):
                                    with _TEXTUAL_VERTICAL(id="settings-group-run-history", classes="setup-group-box"):
                                        yield _TEXTUAL_STATIC("Run History", classes="setup-group-title")
                                        with _TEXTUAL_HORIZONTAL(classes="setup-row"):
                                            yield _TEXTUAL_BUTTON(
                                                "Save run history",
                                                id="settings-toggle-run-history",
                                                classes="raised-button setup-row-button",
                                            )
                                            yield _TEXTUAL_STATIC(
                                                "", id="settings-label-run-history", classes="setup-row-label"
                                            )
                                        with _TEXTUAL_HORIZONTAL(classes="setup-row"):
                                            yield _TEXTUAL_BUTTON(
                                                "Keep last N runs",
                                                id="settings-edit-run-history-limit",
                                                classes="raised-button setup-row-button",
                                            )
                                            yield _TEXTUAL_STATIC(
                                                "", id="settings-label-run-history-limit", classes="setup-row-label"
                                            )
                                    with _TEXTUAL_VERTICAL(id="settings-group-output", classes="setup-group-box"):
                                        yield _TEXTUAL_STATIC("Output & Logging", classes="setup-group-title")
                                        with _TEXTUAL_HORIZONTAL(classes="setup-row"):
                                            yield _TEXTUAL_BUTTON(
                                                "Debug logging",
                                                id="settings-toggle-debug",
                                                classes="raised-button setup-row-button",
                                            )
                                            yield _TEXTUAL_STATIC(
                                                "", id="settings-label-debug", classes="setup-row-label"
                                            )
                                        with _TEXTUAL_HORIZONTAL(classes="setup-row"):
                                            yield _TEXTUAL_BUTTON(
                                                "Session output retention",
                                                id="settings-edit-output-retention",
                                                classes="raised-button setup-row-button",
                                            )
                                            yield _TEXTUAL_STATIC(
                                                "", id="settings-label-output-retention", classes="setup-row-label"
                                            )
                        with _TEXTUAL_HORIZONTAL(id="results-browser", classes="is-hidden"):
                            with _TEXTUAL_VERTICAL(id="results-runs-section"):
                                yield _TEXTUAL_STATIC("Previous Runs", id="results-runs-title")
                                with _TEXTUAL_VERTICAL(id="results-runs-col"):
                                    yield _TEXTUAL_LIST_VIEW(id="results-runs-list")
                            with _TEXTUAL_VERTICAL(id="results-detail-section"):
                                with _TEXTUAL_HORIZONTAL(id="results-tabs"):
                                    yield _TEXTUAL_BUTTON(
                                        "Expand all",
                                        id="results-expand-all",
                                        classes="raised-button results-tab-button",
                                    )
                                    yield _TEXTUAL_BUTTON(
                                        "Collapse all",
                                        id="results-collapse-all",
                                        classes="raised-button results-tab-button",
                                    )
                                with _TEXTUAL_VERTICAL(id="results-tree-host"):
                                    pass
                with _TEXTUAL_VERTICAL(id="interaction-host"):
                    pass
            yield _TEXTUAL_FOOTER()

        def on_mount(self) -> None:
            self._refresh_summary()
            self._refresh_view()
            self._refresh_shell_state()
            self._clear_session_output()
            self._write_output(
                "Welcome to SattLint.\n\n"
                "No configuration is open yet. Use Open Configuration or New Configuration from the File menu "
                "to load or create a configuration, then configure its setup and run analyses."
            )
            self._analyze_help_shown = True

        def _view_state(self, view_name: str) -> _ShellViewState:
            return self._VIEW_REGISTRY.get(view_name, self._VIEW_REGISTRY["analyze"])

        def _show_welcome(self) -> None:
            welcome = (
                "Welcome to SattLint!\n\n"
                "This is your first session. Here is a quick orientation:\n\n"
                "1. Open Configuration or New Configuration — Load or create a configuration.\n"
                "2. Setup — Add analysis targets in the Setup view (Ctrl+4).\n"
                "3. Analyze — Select analyses to run in the Analyze view (Ctrl+1).\n\n"
                "Tip: Configuration changes are saved automatically to the configuration file."
            )
            self._show_help_modal(welcome)

    SattLintTextualAppImpl.__name__ = "SattLintTextualApp"
    SattLintTextualAppImpl.__qualname__ = "SattLintTextualApp"
    SattLintTextualApp = SattLintTextualAppImpl
else:  # pragma: no cover - optional dependency path
    SattLintTextualApp: Any = None


def run_textual_shell(
    cfg: ConfigDict,
    *,
    summarize_targets_fn: Any,
    show_help_fn: Any,
    get_help_text_fn: Any | None = None,
    save_config_fn: Any,
    config_path: Any,
    quit_app_error: type[BaseException],
    analysis_handler_fns: dict[str, Callable[..., Any]] | None = None,
    get_enabled_analyzers_fn: Any | None = None,
    has_analyzed_targets_fn: Any | None = None,
    ensure_ast_cache_fn: Any | None = None,
    set_textual_menu_interaction_fn: Any | None = None,
    clear_textual_menu_interaction_fn: Any | None = None,
) -> None:
    if _TEXTUAL_APP is None:
        raise RuntimeError("Textual UI requested, but textual is not installed")

    textual_app = SattLintTextualApp(
        cfg=cfg,
        summarize_targets_fn=summarize_targets_fn,
        analysis_handlers=analysis_handler_fns,
        get_enabled_analyzers_fn=get_enabled_analyzers_fn,
        ensure_ast_cache_fn=ensure_ast_cache_fn,
        show_help_fn=show_help_fn,
        get_help_text_fn=get_help_text_fn,
        save_config_fn=save_config_fn,
        config_path=config_path,
        quit_app_error=quit_app_error,
    )
    bridge = TextualInteractionBridge(
        submit_request_fn=lambda request: textual_app.call_from_thread(textual_app.present_request, request)
    )
    if set_textual_menu_interaction_fn is not None:
        set_textual_menu_interaction_fn(bridge.as_menu_interaction())
    try:
        textual_app.run()
    finally:
        if clear_textual_menu_interaction_fn is not None:
            clear_textual_menu_interaction_fn()
