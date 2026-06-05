# pyright: reportMissingImports=false, reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportUnknownLambdaType=false, reportGeneralTypeIssues=false, reportInvalidTypeForm=false, reportConstantRedefinition=false, reportPrivateUsage=false, reportUnusedClass=false, reportUnusedFunction=false, reportUnknownArgumentType=false

from __future__ import annotations

from typing import Any, ClassVar, cast

from ._app_textual_actions import ACTIONS_METHODS
from ._app_textual_analyze import ANALYZE_METHODS
from ._app_textual_setup import SETUP_METHODS
from ._app_textual_shared import (
    _TEXTUAL_APP,
    _TEXTUAL_BUTTON,
    _TEXTUAL_COMPOSE_RESULT,
    _TEXTUAL_FOOTER,
    _TEXTUAL_HORIZONTAL,
    _TEXTUAL_LIST_VIEW,
    _TEXTUAL_LOG,
    _TEXTUAL_STATIC,
    _TEXTUAL_VERTICAL,
    DEFAULT_SHELL_TITLE,
    TEXTUAL_SHELL_CSS,
    TextualInteractionBridge,
    _ShellViewState,
)
from ._app_textual_widgets import _ShellBanner

if _TEXTUAL_APP is not None:

    class SattLintTextualApp(_TEXTUAL_APP):
        TITLE = DEFAULT_SHELL_TITLE

        BINDINGS: ClassVar[list[tuple[str, str, str]]] = [
            ("1", "show_analyze", "Analyze"),
            ("2", "show_documentation", "Docs"),
            ("3", "show_setup", "Setup"),
            ("4", "show_tools", "Tools"),
            ("5", "show_help", "Help"),
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

        _VIEW_ACTIONS: ClassVar[dict[str, str]] = {
            "action-analyze": "analyze",
            "action-documentation": "documentation",
            "action-setup": "setup",
            "action-tools": "tools",
        }

        CSS = TEXTUAL_SHELL_CSS

        def __init__(
            self,
            *,
            cfg: dict[str, Any],
            summarize_targets_fn: Any,
            analysis_menu_fn: Any,
            documentation_menu_fn: Any,
            config_menu_fn: Any,
            tools_menu_fn: Any,
            show_help_fn: Any,
            save_config_fn: Any,
            config_path: Any,
            quit_app_error: type[BaseException],
            app_module: Any | None = None,
            self_check_fn: Any | None = None,
            dump_menu_fn: Any | None = None,
            source_diff_fn: Any | None = None,
            force_refresh_ast_fn: Any | None = None,
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
            self._save_config_fn = save_config_fn
            self._config_path = config_path
            self._quit_app_error = quit_app_error
            self._busy = False
            self._dirty = False
            self._active_view = "analyze"
            self._active_job_action_id: str | None = None
            self._active_job_label: str | None = None
            self._analyze_focused_entry_id: str | None = None
            self._analyze_selected_entry_ids: set[str] = set()
            self._suppress_analyze_planner_events = False
            self._setup_candidate_index = 0
            self._setup_target_names_list: list[str] = []
            self._selected_configured_target: str | None = None
            self._active_request = None
            self._active_request_callback: Any = None
            self._interaction_pane: Any = None
            self._self_check_fn = self_check_fn or (lambda _cfg: None)
            self._dump_menu_fn = dump_menu_fn or (lambda _cfg: None)
            self._source_diff_fn = source_diff_fn or (lambda _cfg: None)
            self._force_refresh_ast_fn = force_refresh_ast_fn or (lambda _cfg: None)

        def compose(self) -> _TEXTUAL_COMPOSE_RESULT:
            with _TEXTUAL_HORIZONTAL(id="shell-top"):
                yield _ShellBanner()
                yield _TEXTUAL_STATIC("", id="summary")
            with _TEXTUAL_HORIZONTAL(id="actions"):
                yield _TEXTUAL_BUTTON("Analyze", id="action-analyze", classes="raised-button toolbar-button")
                yield _TEXTUAL_BUTTON("Docs", id="action-documentation", classes="raised-button toolbar-button")
                yield _TEXTUAL_BUTTON("Tools", id="action-tools", classes="raised-button toolbar-button")
                yield _TEXTUAL_STATIC("", id="actions-spacer")
                yield _TEXTUAL_BUTTON("Setup", id="action-setup", classes="raised-button toolbar-button")
                yield _TEXTUAL_BUTTON("Help", id="action-help", classes="raised-button toolbar-button")
                yield _TEXTUAL_BUTTON("Quit", id="action-quit", classes="raised-button toolbar-button")
            with _TEXTUAL_VERTICAL(id="content-host"):
                with _TEXTUAL_VERTICAL(id="view-host"):
                    yield _TEXTUAL_STATIC("", id="view-title")
                    yield _TEXTUAL_STATIC("", id="view-description")
                    yield _TEXTUAL_STATIC("", id="view-note")
                    with _TEXTUAL_HORIZONTAL(id="view-actions"):
                        yield _TEXTUAL_BUTTON("", id="view-primary-action", classes="raised-button toolbar-button")
                    with _TEXTUAL_HORIZONTAL(id="analyze-actions-primary", classes="is-hidden"):
                        yield _TEXTUAL_BUTTON(
                            "Run selected analyses", id="analyze-run-selected", classes="raised-button toolbar-button"
                        )
                        yield _TEXTUAL_BUTTON(
                            "Clear selection", id="analyze-clear-selection", classes="raised-button toolbar-button"
                        )
                    with _TEXTUAL_HORIZONTAL(id="analyze-browser", classes="is-hidden"):
                        with _TEXTUAL_VERTICAL(id="analyze-browser-left"):
                            pass
                        yield _TEXTUAL_STATIC("", id="analyze-browser-right")
                    with _TEXTUAL_HORIZONTAL(id="documentation-actions", classes="is-hidden"):
                        yield _TEXTUAL_BUTTON(
                            "Generate DOCX", id="documentation-generate", classes="raised-button toolbar-button"
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
                                    "Edit program_dir",
                                    id="setup-edit-program-dir",
                                    classes="raised-button setup-row-button",
                                )
                                yield _TEXTUAL_STATIC("", id="setup-label-program-dir", classes="setup-row-label")
                            with _TEXTUAL_HORIZONTAL(classes="setup-row"):
                                yield _TEXTUAL_BUTTON(
                                    "Edit ABB_lib_dir",
                                    id="setup-edit-abb-dir",
                                    classes="raised-button setup-row-button",
                                )
                                yield _TEXTUAL_STATIC("", id="setup-label-abb-dir", classes="setup-row-label")
                            with _TEXTUAL_HORIZONTAL(classes="setup-row"):
                                yield _TEXTUAL_BUTTON(
                                    "Edit other_lib_dirs",
                                    id="setup-edit-other-lib-dirs",
                                    classes="raised-button setup-row-button",
                                )
                                yield _TEXTUAL_STATIC("", id="setup-label-other-dirs", classes="setup-row-label")
                            with _TEXTUAL_HORIZONTAL(classes="setup-row"):
                                yield _TEXTUAL_BUTTON(
                                    "Edit icf_dir", id="setup-edit-icf-dir", classes="raised-button setup-row-button"
                                )
                                yield _TEXTUAL_STATIC("", id="setup-label-icf-dir", classes="setup-row-label")
                            yield _TEXTUAL_STATIC("Mode & Config", classes="setup-group-title")
                            with _TEXTUAL_HORIZONTAL(classes="setup-row"):
                                yield _TEXTUAL_BUTTON(
                                    "Toggle mode", id="setup-toggle-mode", classes="raised-button setup-row-button"
                                )
                                yield _TEXTUAL_STATIC("", id="setup-label-mode", classes="setup-row-label")
                            with _TEXTUAL_HORIZONTAL(classes="setup-row"):
                                yield _TEXTUAL_BUTTON(
                                    "Toggle scan_root_only",
                                    id="setup-toggle-scan-root-only",
                                    classes="raised-button setup-row-button",
                                )
                                yield _TEXTUAL_STATIC("", id="setup-label-scan-root-only", classes="setup-row-label")
                            with _TEXTUAL_HORIZONTAL(classes="setup-row"):
                                yield _TEXTUAL_BUTTON(
                                    "Toggle fast_cache_val.",
                                    id="setup-toggle-fast-cache-validation",
                                    classes="raised-button setup-row-button",
                                )
                                yield _TEXTUAL_STATIC("", id="setup-label-fast-cache", classes="setup-row-label")
                            yield _TEXTUAL_STATIC("Runtime", classes="setup-group-title")
                            with _TEXTUAL_HORIZONTAL(classes="setup-row"):
                                yield _TEXTUAL_BUTTON(
                                    "Toggle debug", id="setup-toggle-debug", classes="raised-button setup-row-button"
                                )
                                yield _TEXTUAL_STATIC("", id="setup-label-debug", classes="setup-row-label")
                            with _TEXTUAL_HORIZONTAL(classes="setup-row"):
                                yield _TEXTUAL_BUTTON(
                                    "Toggle telemetry",
                                    id="setup-toggle-telemetry",
                                    classes="raised-button setup-row-button",
                                )
                                yield _TEXTUAL_STATIC("", id="setup-label-telemetry", classes="setup-row-label")
                            yield _TEXTUAL_STATIC("Save", classes="setup-group-title")
                            yield _TEXTUAL_BUTTON(
                                "Save configuration", id="setup-save", classes="raised-button setup-row-button"
                            )
                    with _TEXTUAL_HORIZONTAL(id="tools-actions", classes="is-hidden"):
                        yield _TEXTUAL_BUTTON(
                            "Self-check diagnostics", id="tools-self-check", classes="raised-button toolbar-button"
                        )
                        yield _TEXTUAL_BUTTON(
                            "Diagnostics & dumps", id="tools-dumps", classes="raised-button toolbar-button"
                        )
                        yield _TEXTUAL_BUTTON(
                            "Source diff report", id="tools-source-diff", classes="raised-button toolbar-button"
                        )
                        yield _TEXTUAL_BUTTON(
                            "Refresh cached ASTs", id="tools-refresh-ast", classes="raised-button toolbar-button"
                        )
                yield _TEXTUAL_STATIC("Session output", id="output-title")
                yield _TEXTUAL_LOG(id="output")
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

        def _view_state(self, view_name: str) -> _ShellViewState:
            if view_name == "documentation":
                return _ShellViewState(
                    action_id="action-documentation",
                    title="Documentation",
                    description="Preview unit candidates, adjust scope, and generate DOCX output directly from this screen.",
                    note="Documentation actions are available directly in this view.",
                    launch_label="Open Documentation Flow",
                )
            if view_name == "setup":
                return _ShellViewState(
                    action_id="action-setup",
                    title="Setup",
                    description="Click targets to add or remove them, then adjust directories and runtime settings inline.",
                    note="Changes happen directly in this view and remain unsaved until you use Save.",
                    launch_label="Open Setup Flow",
                )
            if view_name == "tools":
                return _ShellViewState(
                    action_id="action-tools",
                    title="Tools",
                    description="Run diagnostics, dumps, source diffs, and cache refresh operations directly from this screen.",
                    note="These buttons are for setup validation and troubleshooting when paths or cached results look wrong.",
                    launch_label="Open Tools Flow",
                )
            if view_name == "help":
                return _ShellViewState(
                    action_id="action-help",
                    title="Help",
                    description="See first-run guidance and the recommended workflow for setup, analysis, and documentation.",
                    note="Open the help flow to print the detailed guidance into the output pane.",
                    launch_label="Show Help Output",
                )
            return _ShellViewState(
                action_id="action-analyze",
                title="Analyze",
                description="Plan one or more analyses, inspect the normalized queue, and run the selected steps directly.",
                note="Build an analysis queue in this view and run the shared planner directly.",
                launch_label="Open Analyze Planner",
            )

    for _method in (*SETUP_METHODS, *ACTIONS_METHODS, *ANALYZE_METHODS):
        setattr(SattLintTextualApp, _method.__name__, _method)
else:  # pragma: no cover - optional dependency path
    SattLintTextualApp = cast(Any, None)


def run_textual_shell(
    cfg: dict[str, Any],
    *,
    app_module: Any,
    summarize_targets_fn: Any,
    analysis_menu_fn: Any,
    documentation_menu_fn: Any,
    config_menu_fn: Any,
    tools_menu_fn: Any,
    show_help_fn: Any,
    save_config_fn: Any,
    config_path: Any,
    quit_app_error: type[BaseException],
    **_unused: Any,
) -> None:
    if _TEXTUAL_APP is None:
        raise RuntimeError("Textual UI requested, but textual is not installed")

    textual_app = SattLintTextualApp(
        cfg=cfg,
        summarize_targets_fn=summarize_targets_fn,
        analysis_menu_fn=analysis_menu_fn,
        documentation_menu_fn=documentation_menu_fn,
        config_menu_fn=config_menu_fn,
        tools_menu_fn=tools_menu_fn,
        app_module=app_module,
        self_check_fn=app_module.self_check,
        dump_menu_fn=app_module.dump_menu,
        source_diff_fn=lambda cfg: app_module.run_source_diff_report(cfg, _pause_fn=lambda: None),
        force_refresh_ast_fn=app_module.force_refresh_ast,
        show_help_fn=show_help_fn,
        save_config_fn=save_config_fn,
        config_path=config_path,
        quit_app_error=quit_app_error,
    )
    bridge = TextualInteractionBridge(
        submit_request_fn=lambda request: textual_app.call_from_thread(textual_app.present_request, request)
    )
    app_module.set_textual_menu_interaction(bridge.as_menu_interaction())
    try:
        textual_app.run()
    finally:
        app_module.clear_textual_menu_interaction()
