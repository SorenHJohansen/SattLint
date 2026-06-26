# pyright: reportMissingImports=false, reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportUnknownLambdaType=false, reportGeneralTypeIssues=false, reportInvalidTypeForm=false, reportConstantRedefinition=false, reportPrivateUsage=false, reportUnusedClass=false, reportUnusedFunction=false, reportUnknownArgumentType=false

from __future__ import annotations

import asyncio
import ctypes
import re
import threading
import time
from contextlib import redirect_stderr, redirect_stdout, suppress
from typing import TYPE_CHECKING, Any, cast

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
    _query_required,
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
_SESSION_OUTPUT_MAX_LINES = 4000


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
    except (AttributeError, TypeError, ValueError, ctypes.ArgumentError):
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

    interaction_host = _query_required(self, "#interaction-host", _TEXTUAL_VERTICAL)

    def _resolve_response(response: object) -> None:
        self._resolve_request(request, response)

    pane = _InteractionPane(request, submit_response_fn=_resolve_response)
    self._active_request = request
    self._active_request_callback = on_response_fn
    self._interaction_pane = pane
    interaction_host.mount(pane)
    self._refresh_shell_state()


async def present_request_async(self: Any, request: InteractionRequest) -> object:
    self.present_request(request)
    return await asyncio.wrap_future(request.result_future)


def _track_ui_task(self: Any, task: asyncio.Task[object]) -> None:
    pending_ui_tasks = getattr(self, "_pending_ui_tasks", None)
    if pending_ui_tasks is None:
        pending_ui_tasks = set()
        self._pending_ui_tasks = pending_ui_tasks
    pending_ui_tasks.add(task)
    task.add_done_callback(pending_ui_tasks.discard)


def _schedule_ui_coroutine(self: Any, coroutine_factory: Any, *, fallback_fn: Any | None = None) -> None:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        if fallback_fn is not None:
            fallback_fn()
        return
    task = loop.create_task(coroutine_factory())
    _track_ui_task(self, task)


def _complete_request(self: Any, request: InteractionRequest, response: object) -> None:
    request.response = response
    if not request.result_future.done():
        request.result_future.set_result(response)


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
    if not tuple(getattr(self, "children", ())):
        return
    summary = self._summary_text()
    active_job_text = self._active_job_text()
    running_suffix = f"\n\nRunning: {active_job_text}" if active_job_text is not None else ""
    dirty_suffix = "\n\nUnsaved configuration changes pending." if self._dirty else ""
    try:
        summary_widget = self.query_one("#summary", _TEXTUAL_STATIC)
    except _TEXTUAL_QUERY_ERRORS:
        return
    summary_widget.update(f"{summary}{running_suffix}{dirty_suffix}")
    summary_widget.set_class(self._dirty, "attention")


def _set_active_action(self: Any, action_id: str | None) -> None:
    self._active_job_action_id = action_id
    if not tuple(getattr(self, "children", ())):
        return
    output_widget = _query_required(self, "#output")

    active_view = self._view_state(self._active_view)
    highlighted_action_id = self._active_job_action_id or active_view.action_id
    config_mode = active_view.action_id == "action-setup"
    with suppress(*_TEXTUAL_QUERY_ERRORS):
        self.query_one("#summary", _TEXTUAL_STATIC).set_class(config_mode, "config-mode")
    output_widget.set_class(config_mode, "config-mode")
    for button_id in self._ACTION_IDS:
        button = _query_required(self, f"#{button_id}", _TEXTUAL_BUTTON)
        button.set_class(button_id == highlighted_action_id, "action-active")
        button.set_class(config_mode and button_id == active_view.action_id, "config-active")


def _clear_output_widget(self: Any, output_widget: Any) -> None:
    if hasattr(output_widget, "clear"):
        with suppress(Exception):
            output_widget.clear()
    if hasattr(output_widget, "load_text"):
        with suppress(Exception):
            output_widget.load_text("")
    plain_text_parts = getattr(output_widget, "_plain_text_parts", None)
    if isinstance(plain_text_parts, list):
        plain_text_parts.clear()


def _append_output_line_to_widget(self: Any, output_widget: Any, line_text: str, *, previous_line: str | None) -> str:
    rendered = f"{line_text}\n"
    rich_output = hasattr(output_widget, "write") and hasattr(output_widget, "scroll_end")
    if rich_output:
        if hasattr(output_widget, "append_plain_text"):
            output_widget.append_plain_text(rendered)
        if _output_line_needs_gap(line_text) and previous_line not in (None, ""):
            output_widget.write("", scroll_end=False)
        output_widget.write(_render_output_line(line_text), scroll_end=False)
        return line_text

    if _output_line_needs_gap(line_text) and previous_line not in (None, ""):
        output_widget.insert("\n", output_widget.document.end, maintain_selection_offset=False)
    output_widget.insert(rendered, output_widget.document.end, maintain_selection_offset=False)
    return line_text


def _trim_session_output_lines(self: Any) -> bool:
    retained_lines = getattr(self, "_session_output_lines", None)
    if not isinstance(retained_lines, list):
        return False
    overflow = len(retained_lines) - _SESSION_OUTPUT_MAX_LINES
    if overflow <= 0:
        return False
    del retained_lines[:overflow]
    self._session_output_dropped_line_count = int(getattr(self, "_session_output_dropped_line_count", 0)) + overflow
    return True


def _rebuild_output_widget(self: Any, output_widget: Any) -> None:
    self._clear_output_widget(output_widget)
    previous_line: str | None = None
    for line_text in getattr(self, "_session_output_lines", []):
        previous_line = self._append_output_line_to_widget(output_widget, line_text, previous_line=previous_line)
    self._last_output_line = previous_line


def _write_output(self: Any, text: str) -> None:
    output_widget = self.query_one("#output")
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    if not normalized:
        return

    rich_output = hasattr(output_widget, "write") and hasattr(output_widget, "scroll_end")
    follow_output = bool(getattr(output_widget, "is_vertical_scroll_end", True)) if rich_output else True
    line_texts = [chunk[:-1] if chunk.endswith("\n") else chunk for chunk in normalized.splitlines(keepends=True)]
    self._session_output_lines.extend(line_texts)
    trimmed = self._trim_session_output_lines()
    if trimmed:
        self._rebuild_output_widget(output_widget)
    else:
        previous_line = getattr(self, "_last_output_line", None)
        for line_text in line_texts:
            previous_line = self._append_output_line_to_widget(output_widget, line_text, previous_line=previous_line)
        self._last_output_line = previous_line
    if rich_output:
        if follow_output:
            output_widget.scroll_end(animate=False)
    else:
        output_widget.scroll_cursor_visible(animate=False)


def _emit_output_from_thread(self: Any, text: str) -> None:
    self.call_from_thread(self._write_output, text.rstrip("\n"))


def _clear_session_output(self: Any) -> None:
    output_widget = _query_required(self, "#output")

    self._clear_output_widget(output_widget)
    self._session_output_lines.clear()
    self._session_output_dropped_line_count = 0
    self._last_output_line = None
    _query_required(self, "#output-title", _TEXTUAL_STATIC).update(self._output_title_text())


def _finish_action(self: Any, dirty: bool = False, *, clear_dirty_on_success: bool = False) -> None:
    self._busy = False
    self._active_job_label = None
    self._active_job_started_at = None
    self._active_job_worker = None
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
        self._request_quit_shell()


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


def action_prompt_view_filter(self: Any) -> None:
    if self._interaction_screen_active():
        return
    if self._busy:
        self._write_output("Wait for the current action to finish before filtering lists.")
        return
    if self._active_view == "analyze":
        self._prompt_analyze_filter()
        return
    if self._active_view == "setup":
        self._prompt_setup_filter()
        return
    self._write_output("Filtering is available only in the Analyze and Setup views.")


def action_copy_output(self: Any) -> None:
    try:
        output_widget = self.query_one("#output")
    except _TEXTUAL_QUERY_ERRORS:
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

    worker = getattr(self, "_active_job_worker", None)
    worker_thread = getattr(self, "_active_job_thread", None)
    cancel_event = getattr(self, "_active_job_cancel_event", None)
    if cancel_event is None or (worker is None and worker_thread is None):
        self._write_output("The running analysis queue does not currently support cancellation.")
        return
    if self._active_job_cancel_requested:
        self._write_output("Cancellation is already pending for the running analysis queue.")
        return

    self._active_job_cancel_requested = True
    cancel_event.set()
    if worker is not None:
        with suppress(Exception):
            worker.cancel()
    interrupted = _interrupt_worker_thread(worker_thread, KeyboardInterrupt) if worker_thread is not None else False
    self._refresh_view()
    self._refresh_shell_state()
    if interrupted:
        self._write_output("Cancellation requested. Interrupting the running analysis immediately.")
        return

    self._write_output(
        "Immediate interruption was unavailable. The running analysis will stop after the current safe checkpoint."
    )


def action_quit_shell(self: Any) -> None:
    self._request_quit_shell()


def action_clear_output(self: Any) -> None:
    self._clear_session_output()


def action_back(self: Any) -> None:
    if self._interaction_screen_active():
        return
    if self._active_view != "analyze":
        self._activate_view("analyze")


def _request_quit_shell(self: Any) -> None:
    if self._dirty:
        self._schedule_ui_coroutine(
            self._request_quit_shell_async,
            fallback_fn=lambda: self.present_request(
                InteractionRequest(
                    kind="confirm",
                    title="Unsaved configuration changes",
                    message="Quit and discard the pending Setup changes?",
                    note="Choose No to stay in the shell and use Save config from Setup.",
                ),
                on_response_fn=lambda response: self._handle_quit_confirmation(bool(response)),
            ),
        )
        return
    self._set_active_action("action-quit")
    self.exit()


async def _request_quit_shell_async(self: Any) -> None:
    confirmed = await self.present_request_async(
        InteractionRequest(
            kind="confirm",
            title="Unsaved configuration changes",
            message="Quit and discard the pending Setup changes?",
            note="Choose No to stay in the shell and use Save config from Setup.",
        )
    )
    self._handle_quit_confirmation(bool(confirmed))


def _handle_quit_confirmation(self: Any, confirmed: bool) -> None:
    if confirmed:
        self._set_active_action("action-quit")
        self.exit()
        return
    self._set_active_action(None)
    self._write_output("Quit canceled. Unsaved configuration changes are still pending.")


def action_focus_next_control(self: Any) -> None:
    self.focus_next()


def action_focus_previous_control(self: Any) -> None:
    self.focus_previous()


def _start_managed_action_worker(self: Any, work: Any, *, label: str, action_id: str) -> Any:
    return self.run_worker(
        work,
        name=f"textual-action-{action_id}",
        group="textual-shell-action",
        description=label,
        exit_on_error=False,
        exclusive=True,
        thread=True,
    )


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

    def _register_action_thread(worker_thread: threading.Thread) -> None:
        self._active_job_thread = worker_thread

    self._busy = True
    self._active_job_label = label
    self._active_job_started_at = time.monotonic()
    self._active_job_worker = None
    self._active_job_cancel_event = threading.Event()
    self._active_job_cancel_requested = False
    self._active_job_thread = None
    self._set_active_action(action_id)
    self._refresh_summary()
    self._refresh_shell_state()
    self._refresh_view()
    if action_id in ("action-analyze",):
        self._clear_session_output()
    self._write_output(f"Starting {label}... Live output is shown in this panel.")

    def _run() -> None:
        self.call_from_thread(_register_action_thread, threading.current_thread())
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

    self._active_job_worker = self._start_managed_action_worker(_run, label=label, action_id=action_id)


def _refresh_view(self: Any) -> None:  # noqa: PLR0915
    if not tuple(getattr(self, "children", ())):
        return
    workspace_host = _query_required(self, "#workspace-host", _TEXTUAL_VERTICAL)
    view_host = _query_required(self, "#view-host", _TEXTUAL_VERTICAL)
    output_pane = _query_required(self, "#output-pane", _TEXTUAL_VERTICAL)
    title_widget = _query_required(self, "#view-title", _TEXTUAL_STATIC)
    description_widget = _query_required(self, "#view-description", _TEXTUAL_STATIC)
    note_widget = _query_required(self, "#view-note", _TEXTUAL_STATIC)
    view_actions = _query_required(self, "#view-actions", _TEXTUAL_HORIZONTAL)
    launch_button = _query_required(self, "#view-primary-action", _TEXTUAL_BUTTON)
    analyze_actions_primary = _query_required(self, "#analyze-actions-primary", _TEXTUAL_HORIZONTAL)
    analyze_browser = _query_required(self, "#analyze-browser", _TEXTUAL_VERTICAL)
    analyze_right_widget = _query_required(self, "#analyze-planner-detail", _TEXTUAL_STATIC)
    documentation_actions = _query_required(self, "#documentation-actions", _TEXTUAL_HORIZONTAL)
    setup_browser = _query_required(self, "#setup-browser", _TEXTUAL_HORIZONTAL)
    tools_actions = _query_required(self, "#tools-actions", _TEXTUAL_HORIZONTAL)

    view = self._view_state(self._active_view)
    analyze_view = self._active_view == "analyze"
    documentation_view = self._active_view == "documentation"
    setup_view = self._active_view == "setup"
    tools_view = self._active_view == "tools"
    docs_tools_split_view = documentation_view or tools_view

    title_widget.update(view.title)
    description_widget.update(view.description)
    if analyze_view:
        note_widget.update("")
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
        analyze_right_widget.update(self._analyze_browser_detail_renderable())
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
    if not tuple(getattr(self, "children", ())):
        return
    output_title_widget = _query_required(self, "#output-title", _TEXTUAL_STATIC)
    output_widget = _query_required(self, "#output")
    interaction_host = _query_required(self, "#interaction-host", _TEXTUAL_VERTICAL)
    launch_button = _query_required(self, "#view-primary-action", _TEXTUAL_BUTTON)
    analyze_run_selected_button = _query_required(self, "#analyze-run-selected", _TEXTUAL_BUTTON)
    analyze_cancel_running_button = _query_required(self, "#analyze-cancel-running", _TEXTUAL_BUTTON)
    analyze_clear_selection_button = _query_required(self, "#analyze-clear-selection", _TEXTUAL_BUTTON)
    analyze_clear_output_button = _query_required(self, "#analyze-clear-output", _TEXTUAL_BUTTON)
    documentation_generate_button = _query_required(self, "#documentation-generate", _TEXTUAL_BUTTON)
    documentation_preview_button = _query_required(self, "#documentation-preview-candidates", _TEXTUAL_BUTTON)
    documentation_scope_all_button = _query_required(self, "#documentation-scope-all", _TEXTUAL_BUTTON)
    documentation_scope_moduletype_button = _query_required(self, "#documentation-scope-moduletype", _TEXTUAL_BUTTON)
    documentation_scope_instance_button = _query_required(self, "#documentation-scope-instance-path", _TEXTUAL_BUTTON)
    tools_self_check_button = _query_required(self, "#tools-self-check", _TEXTUAL_BUTTON)
    tools_dumps_button = _query_required(self, "#tools-dumps", _TEXTUAL_BUTTON)
    tools_source_diff_button = _query_required(self, "#tools-source-diff", _TEXTUAL_BUTTON)
    tools_refresh_ast_button = _query_required(self, "#tools-refresh-ast", _TEXTUAL_BUTTON)
    tools_datatype_usage_button = _query_required(self, "#tools-datatype-usage", _TEXTUAL_BUTTON)
    tools_variable_trace_button = _query_required(self, "#tools-variable-trace", _TEXTUAL_BUTTON)
    tools_module_locals_button = _query_required(self, "#tools-module-locals", _TEXTUAL_BUTTON)

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
    analyze_cancel_running_button.disabled = not (
        self._busy and self._active_job_action_id == "action-analyze" and analyze_view
    )
    analyze_clear_selection_button.disabled = (
        toolbar_disabled or not analyze_view or not bool(self._analyze_selected_entry_ids)
    )
    analyze_clear_output_button.disabled = toolbar_disabled or not analyze_view
    for selection_list in self.query(_TEXTUAL_SELECTION_LIST):
        widget_id = str(getattr(selection_list, "id", "") or "")
        if widget_id.startswith(_ANALYZE_PLANNER_LIST_ID_PREFIX):
            selection_list.disabled = toolbar_disabled or not analyze_view
    focused_widget = getattr(self, "focused", None)
    if (
        analyze_view
        and self._busy
        and self._active_job_action_id == "action-analyze"
        and bool(getattr(focused_widget, "disabled", False))
    ):
        analyze_cancel_running_button.focus()

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
        _query_required(self, f"#{btn_id}", _TEXTUAL_BUTTON).disabled = toolbar_disabled or not setup_view
    _query_required(self, "#setup-save", _TEXTUAL_BUTTON).disabled = (
        toolbar_disabled or not setup_view or not self._dirty
    )
    _query_required(self, "#setup-target-remove", _TEXTUAL_BUTTON).disabled = (
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
        _query_required(self, f"#{button_id}", _TEXTUAL_BUTTON).disabled = toolbar_disabled


def on_button_pressed(self: Any, event: Any) -> None:
    button_id = event.button.id or ""
    button_actions: dict[str, Any] = {
        "setup-target-remove": lambda: self._remove_selected_setup_target(self._selected_configured_target),
        "setup-target-browse": self._open_file_browser,
        "view-primary-action": self._launch_active_view,
        "analyze-run-selected": self._run_selected_analysis_plan,
        "analyze-cancel-running": self.action_cancel_running_analysis,
        "analyze-clear-selection": self._clear_selected_analysis_plan,
        "analyze-clear-output": self._clear_session_output,
        "documentation-generate": self._run_documentation_generate,
        "documentation-preview-candidates": self._run_documentation_preview_candidates,
        "documentation-scope-all": self._run_documentation_scope_all,
        "documentation-scope-moduletype": self._run_documentation_scope_moduletype,
        "documentation-scope-instance-path": self._run_documentation_scope_instance_path,
        "setup-edit-program-dir": lambda: self._queue_setup_value_prompt("program_dir", label="program_dir"),
        "setup-edit-abb-dir": lambda: self._queue_setup_value_prompt("ABB_lib_dir", label="ABB_lib_dir"),
        "setup-edit-other-lib-dirs": lambda: self._queue_setup_value_prompt(
            "other_lib_dirs", label="other_lib_dirs", is_list=True
        ),
        "setup-toggle-mode": self._toggle_setup_mode,
        "setup-toggle-scan-root-only": lambda: self._toggle_setup_flag("scan_root_only", label="scan_root_only"),
        "setup-edit-icf-dir": lambda: self._queue_setup_value_prompt("icf_dir", label="icf_dir"),
        "setup-toggle-debug": lambda: self._toggle_setup_flag("debug", label="debug"),
        "setup-toggle-telemetry": self._toggle_setup_telemetry,
        "tools-self-check": self._run_tool_self_check,
        "tools-dumps": self._run_tool_dumps,
        "tools-source-diff": self._run_tool_source_diff,
        "tools-refresh-ast": self._run_tool_refresh_ast,
        "tools-datatype-usage": self._run_tool_datatype_usage,
        "tools-variable-trace": self._run_tool_variable_trace,
        "tools-module-locals": self._run_tool_module_locals,
    }
    action = button_actions.get(button_id)
    if action is not None:
        action()
        return
    self._handle_toolbar_action(button_id)


if TYPE_CHECKING:

    class _TextualActionsMixin:
        def present_request(self, request: InteractionRequest, on_response_fn: Any | None = None) -> None: ...
        async def present_request_async(self, request: InteractionRequest) -> object: ...
        def _schedule_ui_coroutine(self, coroutine_factory: Any, *, fallback_fn: Any | None = None) -> None: ...
        def _complete_request(self, request: InteractionRequest, response: object) -> None: ...
        def _resolve_request(self, request: InteractionRequest, response: object) -> None: ...
        def _refresh_summary(self) -> None: ...
        def _set_active_action(self, action_id: str | None) -> None: ...
        def _clear_output_widget(self, output_widget: Any) -> None: ...
        def _append_output_line_to_widget(
            self, output_widget: Any, line_text: str, *, previous_line: str | None
        ) -> str: ...
        def _trim_session_output_lines(self) -> bool: ...
        def _rebuild_output_widget(self, output_widget: Any) -> None: ...
        def _write_output(self, text: str) -> None: ...
        def _emit_output_from_thread(self, text: str) -> None: ...
        def _clear_session_output(self) -> None: ...
        def _finish_action(self, dirty: bool = False, *, clear_dirty_on_success: bool = False) -> None: ...
        def _interaction_screen_active(self) -> bool: ...
        def _handle_toolbar_action(self, button_id: str) -> None: ...
        def action_show_analyze(self) -> None: ...
        def action_show_documentation(self) -> None: ...
        def action_show_setup(self) -> None: ...
        def action_show_tools(self) -> None: ...
        def action_show_help(self) -> None: ...
        def action_prompt_view_filter(self) -> None: ...
        def action_copy_output(self) -> None: ...
        def action_cancel_running_analysis(self) -> None: ...
        def action_quit_shell(self) -> None: ...
        def action_clear_output(self) -> None: ...
        def action_back(self) -> None: ...
        def _request_quit_shell(self) -> None: ...
        async def _request_quit_shell_async(self) -> None: ...
        def _handle_quit_confirmation(self, confirmed: bool) -> None: ...
        def action_focus_next_control(self) -> None: ...
        def action_focus_previous_control(self) -> None: ...
        def _start_managed_action_worker(self, work: Any, *, label: str, action_id: str) -> Any: ...
        def _start_action(
            self,
            label: str,
            action_fn: Any,
            *,
            action_id: str,
            marks_dirty: bool = False,
            clear_dirty_on_success: bool = False,
        ) -> None: ...
        def _refresh_view(self) -> None: ...
        def _launch_active_view(self) -> None: ...
        def _refresh_shell_state(self) -> None: ...
        def on_button_pressed(self, event: Any) -> None: ...
else:

    class _TextualActionsMixin:
        """Binds shared action helpers and event handlers onto the main Textual shell."""

        present_request = present_request
        present_request_async = present_request_async
        _schedule_ui_coroutine = _schedule_ui_coroutine
        _complete_request = _complete_request
        _resolve_request = _resolve_request
        _refresh_summary = _refresh_summary
        _set_active_action = _set_active_action
        _clear_output_widget = _clear_output_widget
        _append_output_line_to_widget = _append_output_line_to_widget
        _trim_session_output_lines = _trim_session_output_lines
        _rebuild_output_widget = _rebuild_output_widget
        _write_output = _write_output
        _emit_output_from_thread = _emit_output_from_thread
        _clear_session_output = _clear_session_output
        _finish_action = _finish_action
        _interaction_screen_active = _interaction_screen_active
        _handle_toolbar_action = _handle_toolbar_action
        action_show_analyze = action_show_analyze
        action_show_documentation = action_show_documentation
        action_show_setup = action_show_setup
        action_show_tools = action_show_tools
        action_show_help = action_show_help
        action_prompt_view_filter = action_prompt_view_filter
        action_copy_output = action_copy_output
        action_cancel_running_analysis = action_cancel_running_analysis
        action_quit_shell = action_quit_shell
        action_clear_output = action_clear_output
        action_back = action_back
        _request_quit_shell = _request_quit_shell
        _request_quit_shell_async = _request_quit_shell_async
        _handle_quit_confirmation = _handle_quit_confirmation
        action_focus_next_control = action_focus_next_control
        action_focus_previous_control = action_focus_previous_control
        _start_managed_action_worker = _start_managed_action_worker
        _start_action = _start_action
        _refresh_view = _refresh_view
        _launch_active_view = _launch_active_view
        _refresh_shell_state = _refresh_shell_state
        on_button_pressed = on_button_pressed
