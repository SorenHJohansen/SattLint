# pyright: reportMissingImports=false, reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportUnknownLambdaType=false, reportGeneralTypeIssues=false, reportInvalidTypeForm=false, reportConstantRedefinition=false, reportPrivateUsage=false, reportUnusedClass=false, reportUnusedFunction=false, reportUnknownArgumentType=false

from __future__ import annotations

import threading
from contextlib import redirect_stderr, redirect_stdout, suppress
from typing import Any

from ._app_textual_shared import (
    _ANALYZE_PLANNER_LIST_ID_PREFIX,
    _TEXTUAL_BUTTON,
    _TEXTUAL_HORIZONTAL,
    _TEXTUAL_LOG,
    _TEXTUAL_QUERY_ERRORS,
    _TEXTUAL_SELECTION_LIST,
    _TEXTUAL_STATIC,
    _TEXTUAL_VERTICAL,
    InteractionRequest,
    _TextualOutput,
)
from ._app_textual_widgets import _InteractionPane


def present_request(self: Any, request: InteractionRequest, on_response_fn: Any | None = None) -> None:
    if self._active_request is not None:
        self._complete_request(request, None)
        return

    interaction_host = self.query_one("#interaction-host", _TEXTUAL_VERTICAL)

    def _resolve_response(response: object) -> None:
        self._resolve_request(request, response)

    pane = _InteractionPane(request, submit_response_fn=_resolve_response)
    self._active_request = request
    self._active_request_callback = on_response_fn
    self._interaction_pane = pane
    interaction_host.mount(pane)
    self._refresh_shell_state()


def _complete_request(self: Any, request: InteractionRequest, response: object) -> None:
    request.response = response
    request.completed.set()


def _resolve_request(self: Any, request: InteractionRequest, response: object) -> None:
    if request is not self._active_request:
        return

    pane = self._interaction_pane
    request_callback = self._active_request_callback
    self._active_request = None
    self._active_request_callback = None
    self._interaction_pane = None
    if pane is not None:
        pane.remove()
    self._refresh_shell_state()
    self._complete_request(request, response)
    if request_callback is not None:
        request_callback(response)


def _refresh_summary(self: Any) -> None:
    summary = self._summary_text()
    active_job_text = self._active_job_text()
    running_suffix = f"\n\nRunning: {active_job_text}" if active_job_text is not None else ""
    dirty_suffix = "\n\nUnsaved configuration changes pending." if self._dirty else ""
    summary_widget = self.query_one("#summary", _TEXTUAL_STATIC)
    summary_widget.update(f"{summary}{running_suffix}{dirty_suffix}")
    summary_widget.set_class(self._dirty, "attention")


def _set_active_action(self: Any, action_id: str | None) -> None:
    self._active_job_action_id = action_id
    try:
        summary_widget = self.query_one("#summary", _TEXTUAL_STATIC)
        output_widget = self.query_one("#output", _TEXTUAL_LOG)
    except Exception:
        return

    active_view = self._view_state(self._active_view)
    highlighted_action_id = self._active_job_action_id or active_view.action_id
    config_mode = active_view.action_id == "action-setup"
    summary_widget.set_class(config_mode, "config-mode")
    output_widget.set_class(config_mode, "config-mode")
    for button_id in self._ACTION_IDS:
        button = self.query_one(f"#{button_id}", _TEXTUAL_BUTTON)
        button.set_class(button_id == highlighted_action_id, "action-active")
        button.set_class(config_mode and button_id == active_view.action_id, "config-active")


def _write_output(self: Any, text: str) -> None:
    log_widget = self.query_one("#output", _TEXTUAL_LOG)
    for line in text.splitlines() or [text]:
        if line:
            log_widget.write_line(line)


def _emit_output_from_thread(self: Any, text: str) -> None:
    self.call_from_thread(self._write_output, text.rstrip("\n"))


def _finish_action(self: Any, dirty: bool = False, *, clear_dirty_on_success: bool = False) -> None:
    self._busy = False
    self._active_job_label = None
    if clear_dirty_on_success:
        self._dirty = False
    else:
        self._dirty = self._dirty or dirty
    self._set_active_action(None)
    self._refresh_summary()
    self._refresh_shell_state()
    self._refresh_view()


def _interaction_screen_active(self: Any) -> bool:
    return self._active_request is not None


def _handle_toolbar_action(self: Any, button_id: str) -> None:
    if self._interaction_screen_active():
        return
    view_name = self._VIEW_ACTIONS.get(button_id)
    if view_name is not None:
        self._activate_view(view_name)
    elif button_id == "setup-save":
        self._start_action(
            "Save configuration",
            lambda: self._save_config_fn(self._config_path, self._cfg),
            action_id="action-setup",
            clear_dirty_on_success=True,
        )
    elif button_id == "action-help":
        self._open_help_popup()
    elif button_id == "action-quit":
        if self._busy:
            self._write_output("An action is still running. Wait for it to finish before quitting.")
            return
        self._set_active_action(button_id)
        self.exit()


def action_show_analyze(self: Any) -> None:
    self._handle_toolbar_action("action-analyze")


def action_show_documentation(self: Any) -> None:
    self._handle_toolbar_action("action-documentation")


def action_show_setup(self: Any) -> None:
    self._handle_toolbar_action("action-setup")


def action_show_tools(self: Any) -> None:
    self._handle_toolbar_action("action-tools")


def action_show_help(self: Any) -> None:
    self._handle_toolbar_action("action-help")


def action_quit_shell(self: Any) -> None:
    self._handle_toolbar_action("action-quit")


def action_focus_next_control(self: Any) -> None:
    self.focus_next()


def action_focus_previous_control(self: Any) -> None:
    self.focus_previous()


def _start_action(
    self: Any,
    label: str,
    action_fn: Any,
    *,
    action_id: str,
    marks_dirty: bool = False,
    clear_dirty_on_success: bool = False,
) -> None:
    if self._busy:
        self._write_output("Another action is still running. Wait for it to finish first.")
        return

    self._busy = True
    self._active_job_label = label
    self._set_active_action(action_id)
    self._refresh_summary()
    self._refresh_shell_state()
    self._refresh_view()
    self._write_output(f"Starting {label}... Live output is shown in this panel.")

    def _run() -> None:
        output_stream = _TextualOutput(emit_text_fn=self._emit_output_from_thread)
        dirty = False
        clear_dirty = False
        try:
            with redirect_stdout(output_stream), redirect_stderr(output_stream):
                result = action_fn()
                dirty = marks_dirty and bool(result)
                clear_dirty = clear_dirty_on_success
        except self._quit_app_error:
            self.call_from_thread(self.exit)
            return
        except Exception as exc:  # pragma: no cover - runtime-only fallback
            self._emit_output_from_thread(f"{label} failed: {exc}")
        finally:
            self.call_from_thread(lambda: self._finish_action(dirty, clear_dirty_on_success=clear_dirty))

    threading.Thread(target=_run, daemon=True).start()


def _refresh_view(self: Any) -> None:
    try:
        view_host = self.query_one("#view-host", _TEXTUAL_VERTICAL)
        title_widget = self.query_one("#view-title", _TEXTUAL_STATIC)
        description_widget = self.query_one("#view-description", _TEXTUAL_STATIC)
        note_widget = self.query_one("#view-note", _TEXTUAL_STATIC)
        view_actions = self.query_one("#view-actions", _TEXTUAL_HORIZONTAL)
        launch_button = self.query_one("#view-primary-action", _TEXTUAL_BUTTON)
        analyze_actions_primary = self.query_one("#analyze-actions-primary", _TEXTUAL_HORIZONTAL)
        analyze_browser = self.query_one("#analyze-browser", _TEXTUAL_HORIZONTAL)
        analyze_right_widget = self.query_one("#analyze-browser-right", _TEXTUAL_STATIC)
        documentation_actions = self.query_one("#documentation-actions", _TEXTUAL_HORIZONTAL)
        setup_browser = self.query_one("#setup-browser", _TEXTUAL_HORIZONTAL)
        tools_actions = self.query_one("#tools-actions", _TEXTUAL_HORIZONTAL)
    except Exception:
        return

    view = self._view_state(self._active_view)
    analyze_view = self._active_view == "analyze"
    documentation_view = self._active_view == "documentation"
    setup_view = self._active_view == "setup"
    tools_view = self._active_view == "tools"

    title_widget.update(view.title)
    description_widget.update(view.description)
    if analyze_view:
        note_widget.update(self._analyze_note_text())
    elif documentation_view:
        note_widget.update(self._documentation_note_text())
    elif setup_view:
        note_widget.update(self._setup_note_text())
    else:
        note_widget.update(view.note)
    launch_button.label = view.launch_label
    view_host.set_class(view.action_id == "action-setup", "config-mode")
    note_widget.set_class(False, "is-hidden")
    view_actions.set_class(self._active_view not in ("help",), "is-hidden")
    analyze_actions_primary.set_class(not analyze_view, "is-hidden")
    analyze_browser.set_class(not analyze_view, "is-hidden")
    documentation_actions.set_class(not documentation_view, "is-hidden")
    setup_browser.set_class(not setup_view, "is-hidden")
    tools_actions.set_class(not tools_view, "is-hidden")

    if analyze_view:
        self._refresh_analyze_planner()
        analyze_right_widget.update(self._analyze_browser_detail_text())
    else:
        analyze_right_widget.update("")

    if setup_view:
        self._refresh_setup_target_list()
        self._refresh_setup_settings_labels()


def _launch_active_view(self: Any) -> None:
    view = self._view_state(self._active_view)
    if view.action_id == "action-documentation":
        self._write_output("Documentation actions are available directly in the Documentation view.")
        return
    if view.action_id == "action-analyze":
        self._write_output("The analyze planner is available directly in the Analyze view.")
        return
    if view.action_id == "action-setup":
        self._write_output("Setup actions are available directly in the Setup view.")
        return
    if view.action_id == "action-tools":
        self._write_output("Tool actions are available directly in the Tools view.")
        return
    if view.action_id == "action-help":
        self._open_help_popup()
        return
    self._start_action("Analyze", lambda: self._analysis_menu_fn(self._cfg), action_id=view.action_id)


def _refresh_shell_state(self: Any) -> None:
    try:
        output_title_widget = self.query_one("#output-title", _TEXTUAL_STATIC)
        output_widget = self.query_one("#output", _TEXTUAL_LOG)
        interaction_host = self.query_one("#interaction-host", _TEXTUAL_VERTICAL)
        launch_button = self.query_one("#view-primary-action", _TEXTUAL_BUTTON)
        analyze_run_selected_button = self.query_one("#analyze-run-selected", _TEXTUAL_BUTTON)
        analyze_clear_selection_button = self.query_one("#analyze-clear-selection", _TEXTUAL_BUTTON)
        documentation_generate_button = self.query_one("#documentation-generate", _TEXTUAL_BUTTON)
        documentation_preview_button = self.query_one("#documentation-preview-candidates", _TEXTUAL_BUTTON)
        documentation_scope_all_button = self.query_one("#documentation-scope-all", _TEXTUAL_BUTTON)
        documentation_scope_moduletype_button = self.query_one("#documentation-scope-moduletype", _TEXTUAL_BUTTON)
        documentation_scope_instance_button = self.query_one("#documentation-scope-instance-path", _TEXTUAL_BUTTON)
        tools_self_check_button = self.query_one("#tools-self-check", _TEXTUAL_BUTTON)
        tools_dumps_button = self.query_one("#tools-dumps", _TEXTUAL_BUTTON)
        tools_source_diff_button = self.query_one("#tools-source-diff", _TEXTUAL_BUTTON)
        tools_refresh_ast_button = self.query_one("#tools-refresh-ast", _TEXTUAL_BUTTON)
    except Exception:
        return

    output_title_widget.update(self._output_title_text())
    interaction_active = self._active_request is not None
    output_widget.set_class(interaction_active, "interaction-active")
    interaction_host.set_class(interaction_active, "active")
    toolbar_disabled = self._busy or interaction_active
    launch_button.disabled = toolbar_disabled
    analyze_view = self._active_view == "analyze"
    documentation_view = self._active_view == "documentation"
    setup_view = self._active_view == "setup"
    tools_view = self._active_view == "tools"
    analyze_plan = self._analyze_plan()

    analyze_run_selected_button.disabled = (
        toolbar_disabled or not analyze_view or not self._setup_has_targets() or not analyze_plan.is_runnable
    )
    analyze_clear_selection_button.disabled = (
        toolbar_disabled or not analyze_view or not bool(self._analyze_selected_entry_ids)
    )
    for selection_list in self.query(_TEXTUAL_SELECTION_LIST):
        widget_id = str(getattr(selection_list, "id", "") or "")
        if widget_id.startswith(_ANALYZE_PLANNER_LIST_ID_PREFIX):
            selection_list.disabled = toolbar_disabled or not analyze_view

    documentation_buttons = (
        documentation_generate_button,
        documentation_preview_button,
        documentation_scope_all_button,
        documentation_scope_moduletype_button,
        documentation_scope_instance_button,
    )
    for button in documentation_buttons:
        button.disabled = toolbar_disabled or not documentation_view or not self._setup_has_targets()
    for btn_id in (
        "setup-edit-program-dir",
        "setup-edit-abb-dir",
        "setup-edit-other-lib-dirs",
        "setup-edit-icf-dir",
        "setup-toggle-mode",
        "setup-toggle-scan-root-only",
        "setup-toggle-fast-cache-validation",
        "setup-toggle-debug",
        "setup-toggle-telemetry",
        "setup-target-browse",
    ):
        with suppress(Exception):
            self.query_one(f"#{btn_id}", _TEXTUAL_BUTTON).disabled = toolbar_disabled or not setup_view
    with suppress(Exception):
        self.query_one("#setup-save", _TEXTUAL_BUTTON).disabled = toolbar_disabled or not setup_view or not self._dirty
    with suppress(Exception):
        self.query_one("#setup-target-remove", _TEXTUAL_BUTTON).disabled = (
            toolbar_disabled
            or not setup_view
            or not bool(self._configured_target_names())
            or self._selected_configured_target is None
        )
    if setup_view:
        self._refresh_setup_settings_labels()
    tools_self_check_button.disabled = toolbar_disabled or not tools_view
    tools_dumps_button.disabled = toolbar_disabled or not tools_view or not self._setup_has_targets()
    tools_source_diff_button.disabled = toolbar_disabled or not tools_view or not self._setup_has_targets()
    tools_refresh_ast_button.disabled = toolbar_disabled or not tools_view or not self._setup_has_targets()
    for button_id in self._ACTION_IDS:
        with suppress(*_TEXTUAL_QUERY_ERRORS):
            self.query_one(f"#{button_id}", _TEXTUAL_BUTTON).disabled = toolbar_disabled


def on_button_pressed(self: Any, event: Any) -> None:
    button_id = event.button.id or ""
    if button_id == "setup-target-remove":
        self._remove_selected_setup_target(self._selected_configured_target)
        return
    if button_id == "setup-target-browse":
        self._open_file_browser()
        return
    if button_id == "view-primary-action":
        self._launch_active_view()
        return
    if button_id == "analyze-run-selected":
        self._run_selected_analysis_plan()
        return
    if button_id == "analyze-clear-selection":
        self._clear_selected_analysis_plan()
        return
    if button_id == "documentation-generate":
        self._run_documentation_generate()
        return
    if button_id == "documentation-preview-candidates":
        self._run_documentation_preview_candidates()
        return
    if button_id == "documentation-scope-all":
        self._run_documentation_scope_all()
        return
    if button_id == "documentation-scope-moduletype":
        self._run_documentation_scope_moduletype()
        return
    if button_id == "documentation-scope-instance-path":
        self._run_documentation_scope_instance_path()
        return
    if button_id == "setup-edit-program-dir":
        self._prompt_setup_value("program_dir", label="program_dir")
        return
    if button_id == "setup-edit-abb-dir":
        self._prompt_setup_value("ABB_lib_dir", label="ABB_lib_dir")
        return
    if button_id == "setup-edit-other-lib-dirs":
        self._prompt_setup_value("other_lib_dirs", label="other_lib_dirs", is_list=True)
        return
    if button_id == "setup-toggle-mode":
        self._toggle_setup_mode()
        return
    if button_id == "setup-toggle-scan-root-only":
        self._toggle_setup_flag("scan_root_only", label="scan_root_only")
        return
    if button_id == "setup-toggle-fast-cache-validation":
        self._toggle_setup_flag("fast_cache_validation", label="fast_cache_validation")
        return
    if button_id == "setup-edit-icf-dir":
        self._prompt_setup_value("icf_dir", label="icf_dir")
        return
    if button_id == "setup-toggle-debug":
        self._toggle_setup_flag("debug", label="debug")
        return
    if button_id == "setup-toggle-telemetry":
        self._toggle_setup_telemetry()
        return
    if button_id == "tools-self-check":
        self._run_tool_self_check()
        return
    if button_id == "tools-dumps":
        self._run_tool_dumps()
        return
    if button_id == "tools-source-diff":
        self._run_tool_source_diff()
        return
    if button_id == "tools-refresh-ast":
        self._run_tool_refresh_ast()
        return
    self._handle_toolbar_action(button_id)


ACTIONS_METHODS = (
    present_request,
    _complete_request,
    _resolve_request,
    _refresh_summary,
    _set_active_action,
    _write_output,
    _emit_output_from_thread,
    _finish_action,
    _interaction_screen_active,
    _handle_toolbar_action,
    action_show_analyze,
    action_show_documentation,
    action_show_setup,
    action_show_tools,
    action_show_help,
    action_quit_shell,
    action_focus_next_control,
    action_focus_previous_control,
    _start_action,
    _refresh_view,
    _launch_active_view,
    _refresh_shell_state,
    on_button_pressed,
)
