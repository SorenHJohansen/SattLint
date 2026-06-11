# pyright: reportMissingImports=false, reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportUnknownLambdaType=false, reportGeneralTypeIssues=false, reportInvalidTypeForm=false, reportConstantRedefinition=false, reportPrivateUsage=false, reportUnusedClass=false, reportUnusedFunction=false, reportUnknownArgumentType=false

from __future__ import annotations

import ctypes
import re
import threading
from contextlib import redirect_stderr, redirect_stdout, suppress
from typing import Any, cast

try:
    from rich.rule import Rule as _RichRule  # type: ignore[import-untyped]
    from rich.text import Text as _RichText  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover - optional dependency path
    _RichRule = None
    _RichText = None

from ._app_textual_shared import (
    _ANALYZE_PLANNER_LIST_ID_PREFIX,
    _TEXTUAL_BUTTON,
    _TEXTUAL_HORIZONTAL,
    _TEXTUAL_QUERY_ERRORS,
    _TEXTUAL_SELECTION_LIST,
    _TEXTUAL_STATIC,
    _TEXTUAL_VERTICAL,
    InteractionRequest,
    _TextualOutput,
)
from ._app_textual_widgets import _InteractionPane

_TARGET_HEADER_RE = re.compile(r"^===\s*Target:\s*(?P<name>.+?)\s*===\s*$")
_PHASE_HEADER_RE = re.compile(r"^\[(?P<index>\d+)/(?P<total>\d+)\]\s+(?P<label>.+)$")
_NUMBERED_ITEM_RE = re.compile(r"^(?P<indent>\s*)(?P<number>\d+)\.\s+(?P<label>.+)$")

_OUTPUT_ACCENT = "#001ba3"
_OUTPUT_MUTED = "#24505f"
_OUTPUT_RULE = "#0077b3"
_OUTPUT_WARNING = "#8a5a00"
_OUTPUT_SUCCESS = "#236d36"
_OUTPUT_DANGER = "#8a3b12"


def _styled_output_text(*segments: tuple[str, str]) -> object:
    if _RichText is None:
        return "".join(text for text, _style in segments)
    text = _RichText()
    for segment, style in segments:
        text.append(segment, style=style)
    return text


def _label_value_renderable(label: str, value: str, *, value_style: str = _OUTPUT_ACCENT) -> object:
    return _styled_output_text((f"{label}: ", f"bold {_OUTPUT_MUTED}"), (value, value_style))


def _render_output_line(line_text: str) -> object:
    stripped = line_text.strip()
    if not stripped:
        return ""

    target_match = _TARGET_HEADER_RE.match(stripped)
    if target_match is not None:
        target_name = target_match.group("name")
        if _RichRule is None:
            return f"Target: {target_name}"
        return _RichRule(
            cast(
                Any, _styled_output_text(("Library ", f"bold {_OUTPUT_MUTED}"), (target_name, f"bold {_OUTPUT_ACCENT}"))
            ),
            style=_OUTPUT_RULE,
        )

    phase_match = _PHASE_HEADER_RE.match(stripped)
    if phase_match is not None:
        if _RichRule is None:
            return stripped
        return _RichRule(
            cast(
                Any,
                _styled_output_text(
                    (
                        f"[{phase_match.group('index')}/{phase_match.group('total')}] ",
                        f"bold {_OUTPUT_MUTED}",
                    ),
                    (phase_match.group("label"), f"bold {_OUTPUT_ACCENT}"),
                ),
            ),
            style=_OUTPUT_MUTED,
        )

    if stripped in {"Analyze planner queue", "Execution order"}:
        return _styled_output_text((stripped, f"bold {_OUTPUT_ACCENT}"))

    if stripped.startswith("Validation warnings"):
        return _styled_output_text((stripped, f"bold {_OUTPUT_WARNING}"))

    if stripped.startswith("Report:"):
        return _styled_output_text((stripped, f"bold {_OUTPUT_MUTED}"))

    if stripped.startswith("Status:"):
        status_value = stripped.partition(":")[2].strip()
        status_style = _OUTPUT_SUCCESS if status_value.casefold() == "ok" else _OUTPUT_DANGER
        return _label_value_renderable("Status", status_value, value_style=f"bold {status_style}")

    if stripped.startswith("Issues:"):
        count_text = stripped.partition(":")[2].strip()
        count_style = _OUTPUT_SUCCESS if count_text == "0" else _OUTPUT_DANGER
        return _label_value_renderable("Issues", count_text, value_style=f"bold {count_style}")

    for label in ("Target", "Version", "Last changed", "Selected issue kinds", "Selected entries", "Planned steps"):
        prefix = f"{label}:"
        if stripped.startswith(prefix):
            return _label_value_renderable(label, stripped.partition(":")[2].strip())

    if stripped in {"Moduletype:", "SingleModule:"}:
        return _styled_output_text((line_text, f"bold {_OUTPUT_MUTED}"))

    numbered_match = _NUMBERED_ITEM_RE.match(line_text)
    if numbered_match is not None:
        return _styled_output_text(
            (numbered_match.group("indent"), _OUTPUT_ACCENT),
            (f"{numbered_match.group('number')}. ", f"bold {_OUTPUT_MUTED}"),
            (numbered_match.group("label"), _OUTPUT_ACCENT),
        )

    if stripped.startswith("No ") and stripped.endswith(" found."):
        return _styled_output_text((line_text, f"bold {_OUTPUT_SUCCESS}"))

    stripped_with_indent = line_text.lstrip()
    indent = line_text[: len(line_text) - len(stripped_with_indent)]
    if stripped_with_indent.startswith("- "):
        warning_style = _OUTPUT_WARNING if stripped_with_indent.startswith("- [") else _OUTPUT_MUTED
        body_style = _OUTPUT_WARNING if warning_style == _OUTPUT_WARNING else _OUTPUT_ACCENT
        return _styled_output_text(
            (indent, _OUTPUT_ACCENT),
            ("- ", f"bold {warning_style}"),
            (stripped_with_indent[2:], body_style),
        )

    if stripped_with_indent.startswith("* "):
        return _styled_output_text(
            (indent, _OUTPUT_ACCENT),
            ("* ", f"bold {_OUTPUT_RULE}"),
            (stripped_with_indent[2:], _OUTPUT_ACCENT),
        )

    if line_text.startswith("    "):
        return _styled_output_text((line_text, _OUTPUT_MUTED))

    return _styled_output_text((line_text, _OUTPUT_ACCENT))


def _output_line_needs_gap(line_text: str) -> bool:
    stripped = line_text.strip()
    return bool(_TARGET_HEADER_RE.match(stripped) or _PHASE_HEADER_RE.match(stripped))


def _interrupt_worker_thread(thread: Any, exception_type: type[BaseException]) -> bool:
    thread_id = getattr(thread, "ident", None)
    if not isinstance(thread_id, int):
        return False

    is_alive_fn = getattr(thread, "is_alive", None)
    if callable(is_alive_fn) and not bool(is_alive_fn()):
        return False

    try:
        set_async_exc = ctypes.pythonapi.PyThreadState_SetAsyncExc
        result = int(set_async_exc(ctypes.c_ulong(thread_id), ctypes.py_object(exception_type)))
    except Exception:  # noqa: BLE001
        return False

    if result == 1:
        return True
    if result > 1:
        with suppress(Exception):
            set_async_exc(ctypes.c_ulong(thread_id), 0)
    return False


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
    try:
        summary_widget = self.query_one("#summary", _TEXTUAL_STATIC)
    except Exception:  # noqa: BLE001
        return
    summary_widget.update(f"{summary}{running_suffix}{dirty_suffix}")
    summary_widget.set_class(self._dirty, "attention")


def _set_active_action(self: Any, action_id: str | None) -> None:
    self._active_job_action_id = action_id
    try:
        output_widget = self.query_one("#output")
    except Exception:  # noqa: BLE001
        return

    active_view = self._view_state(self._active_view)
    highlighted_action_id = self._active_job_action_id or active_view.action_id
    config_mode = active_view.action_id == "action-setup"
    with suppress(Exception):
        self.query_one("#summary", _TEXTUAL_STATIC).set_class(config_mode, "config-mode")
    output_widget.set_class(config_mode, "config-mode")
    for button_id in self._ACTION_IDS:
        button = self.query_one(f"#{button_id}", _TEXTUAL_BUTTON)
        button.set_class(button_id == highlighted_action_id, "action-active")
        button.set_class(config_mode and button_id == active_view.action_id, "config-active")


def _write_output(self: Any, text: str) -> None:
    output_widget = self.query_one("#output")
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    if not normalized:
        return

    rich_output = hasattr(output_widget, "write") and hasattr(output_widget, "scroll_end")
    follow_output = bool(getattr(output_widget, "is_vertical_scroll_end", True)) if rich_output else True
    for chunk in normalized.splitlines(keepends=True):
        line_text = chunk[:-1] if chunk.endswith("\n") else chunk
        rendered = f"{line_text}\n"
        if rich_output:
            if hasattr(output_widget, "append_plain_text"):
                output_widget.append_plain_text(rendered)
            if _output_line_needs_gap(line_text) and getattr(self, "_last_output_line", None) not in (None, ""):
                output_widget.write("", scroll_end=False)
            output_widget.write(_render_output_line(line_text), scroll_end=False)
        else:
            if _output_line_needs_gap(line_text) and getattr(self, "_last_output_line", None) not in (None, ""):
                output_widget.insert("\n", output_widget.document.end, maintain_selection_offset=False)
            output_widget.insert(rendered, output_widget.document.end, maintain_selection_offset=False)
        self._last_output_line = line_text
    if rich_output:
        if follow_output:
            output_widget.scroll_end(animate=False)
    else:
        output_widget.scroll_cursor_visible(animate=False)


def _emit_output_from_thread(self: Any, text: str) -> None:
    self.call_from_thread(self._write_output, text.rstrip("\n"))


def _finish_action(self: Any, dirty: bool = False, *, clear_dirty_on_success: bool = False) -> None:
    self._busy = False
    self._active_job_label = None
    self._active_job_cancel_event = None
    self._active_job_cancel_requested = False
    self._active_job_thread = None
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
    if self._busy:
        if button_id == "action-quit":
            self._write_output("An action is still running. Wait for it to finish before quitting.")
        else:
            self._write_output("Another action is still running. Wait for it to finish first.")
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


def action_copy_output(self: Any) -> None:
    try:
        output_widget = self.query_one("#output")
    except Exception:  # noqa: BLE001
        return

    selected_text = str(getattr(output_widget, "selected_text", "") or "")
    text_to_copy = selected_text or str(getattr(output_widget, "text", "") or "")
    if not text_to_copy:
        self._write_output("Nothing is available in Session output yet.")
        return

    self.copy_to_clipboard(text_to_copy)
    if selected_text:
        self._write_output(f"Copied {len(selected_text)} character(s) from Session output.")
    else:
        self._write_output("Copied all Session output because no text was selected.")


def action_cancel_running_analysis(self: Any) -> None:
    if not self._busy or self._active_job_action_id != "action-analyze":
        self._write_output("No selected analysis run is active.")
        return

    worker_thread = getattr(self, "_active_job_thread", None)
    cancel_event = getattr(self, "_active_job_cancel_event", None)
    if cancel_event is None or worker_thread is None:
        self._write_output("The running analysis queue does not currently support cancellation.")
        return
    if self._active_job_cancel_requested:
        self._write_output("Cancellation is already pending for the running analysis queue.")
        return

    self._active_job_cancel_requested = True
    cancel_event.set()
    interrupted = _interrupt_worker_thread(worker_thread, KeyboardInterrupt)
    self._refresh_view()
    self._refresh_shell_state()
    if interrupted:
        self._write_output("Cancellation requested. Interrupting the running analysis immediately.")
        return

    self._write_output(
        "Immediate interruption was unavailable. The running analysis will stop after the current safe checkpoint."
    )


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
    self._active_job_cancel_event = threading.Event()
    self._active_job_cancel_requested = False
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
        except KeyboardInterrupt:
            if action_id == "action-analyze" and self._active_job_cancel_requested:
                self._emit_output_from_thread("Selected analyses canceled.")
            else:
                self._emit_output_from_thread(f"{label} interrupted.")
        except Exception as exc:  # pragma: no cover - runtime-only fallback  # noqa: BLE001
            self._emit_output_from_thread(f"{label} failed: {exc}")
        finally:
            self.call_from_thread(lambda: self._finish_action(dirty, clear_dirty_on_success=clear_dirty))

    worker_thread = threading.Thread(target=_run, daemon=True)
    self._active_job_thread = worker_thread
    worker_thread.start()


def _refresh_view(self: Any) -> None:  # noqa: PLR0915
    try:
        workspace_host = self.query_one("#workspace-host", _TEXTUAL_VERTICAL)
        view_host = self.query_one("#view-host", _TEXTUAL_VERTICAL)
        output_pane = self.query_one("#output-pane", _TEXTUAL_VERTICAL)
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
    except Exception:  # noqa: BLE001
        return

    view = self._view_state(self._active_view)
    analyze_view = self._active_view == "analyze"
    documentation_view = self._active_view == "documentation"
    setup_view = self._active_view == "setup"
    tools_view = self._active_view == "tools"
    docs_tools_split_view = documentation_view or tools_view

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
    workspace_host.set_class(analyze_view, "analyze-split")
    workspace_host.set_class(docs_tools_split_view, "docs-tools-split")
    workspace_host.set_class(setup_view, "no-output")
    view_host.set_class(view.action_id == "action-setup", "config-mode")
    output_pane.set_class(setup_view, "is-hidden")
    description_widget.set_class(False, "is-hidden")
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
    self._write_output(f"{view.title} is not available as a standalone action in the Textual shell.")


def _refresh_shell_state(self: Any) -> None:  # noqa: PLR0915
    try:
        output_title_widget = self.query_one("#output-title", _TEXTUAL_STATIC)
        output_widget = self.query_one("#output")
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
        tools_datatype_usage_button = self.query_one("#tools-datatype-usage", _TEXTUAL_BUTTON)
        tools_variable_trace_button = self.query_one("#tools-variable-trace", _TEXTUAL_BUTTON)
        tools_module_locals_button = self.query_one("#tools-module-locals", _TEXTUAL_BUTTON)
    except Exception:  # noqa: BLE001
        return

    self._sync_output_title_spinner()
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
    tools_datatype_usage_button.disabled = toolbar_disabled or not tools_view or not self._setup_has_targets()
    tools_variable_trace_button.disabled = toolbar_disabled or not tools_view or not self._setup_has_targets()
    tools_module_locals_button.disabled = toolbar_disabled or not tools_view or not self._setup_has_targets()
    for button_id in self._ACTION_IDS:
        with suppress(*_TEXTUAL_QUERY_ERRORS):
            self.query_one(f"#{button_id}", _TEXTUAL_BUTTON).disabled = toolbar_disabled


def on_button_pressed(self: Any, event: Any) -> None:  # noqa: PLR0915
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
    if button_id == "tools-datatype-usage":
        self._run_tool_datatype_usage()
        return
    if button_id == "tools-variable-trace":
        self._run_tool_variable_trace()
        return
    if button_id == "tools-module-locals":
        self._run_tool_module_locals()
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
    action_copy_output,
    action_cancel_running_analysis,
    action_quit_shell,
    action_focus_next_control,
    action_focus_previous_control,
    _start_action,
    _refresh_view,
    _launch_active_view,
    _refresh_shell_state,
    on_button_pressed,
)
