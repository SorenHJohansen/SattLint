# pyright: reportMissingImports=false, reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportUnknownLambdaType=false, reportGeneralTypeIssues=false, reportInvalidTypeForm=false, reportConstantRedefinition=false, reportPrivateUsage=false, reportUnusedClass=false, reportUnusedFunction=false, reportUnknownArgumentType=false

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from ._app_textual_setup_actions import (
    _activate_view,
    _prompt_setup_filter,
    _prompt_setup_value,
    _prompt_setup_value_async,
    _queue_setup_value_prompt,
    _run_analyze_checks,
    _run_app_module_cfg_action,
    _run_tool_datatype_usage,
    _run_tool_dumps,
    _run_tool_module_locals,
    _run_tool_refresh_ast,
    _run_tool_self_check,
    _run_tool_variable_trace,
    _set_setup_filter_text,
)
from ._app_textual_setup_display import (
    _OUTPUT_TITLE_SPINNER_FRAMES,
    _OUTPUT_TITLE_SPINNER_INTERVAL_SECONDS,
    _active_job_elapsed_text,
    _active_job_text,
    _analyze_note_text,
    _configured_target_names,
    _output_retention_note,
    _output_title_spinner_timestamp,
    _selected_setup_candidate,
    _setup_candidate_display_paths,
    _setup_candidate_status,
    _setup_candidates,
    _setup_filter_value,
    _summary_text,
    _visible_configured_target_names,
)
from ._app_textual_setup_targets import (
    _add_selected_setup_target,
    _add_target_from_path,
    _is_target_configured,
    _mark_setup_changed,
    _open_file_browser,
    _open_help_popup,
    _open_raw_file_browser,
    _refresh_setup_settings_labels,
    _refresh_setup_target_list,
    _remove_selected_setup_target,
    _replace_setup_list_value,
    _set_setup_candidate_by_name,
    _setup_browser_detail_text,
    _setup_has_targets,
    _setup_note_text,
    _show_help_modal,
    _targets_action_allowed,
    _toggle_setup_flag,
    _toggle_setup_mode,
    _toggle_setup_telemetry,
    on_list_view_highlighted,
)
from ._app_textual_shared import _TEXTUAL_QUERY_ERRORS, _TEXTUAL_STATIC, _SetupTargetCandidate


def _output_title_spinner_frame(self: Any) -> str | None:
    if not self._busy or self._active_job_action_id != "action-analyze":
        return None
    spinner_started_at = getattr(self, "_output_title_spinner_started_at", None)
    if spinner_started_at is None:
        return _OUTPUT_TITLE_SPINNER_FRAMES[0]
    elapsed_seconds = max(0.0, _output_title_spinner_timestamp() - float(spinner_started_at))
    spinner_index = int(elapsed_seconds / _OUTPUT_TITLE_SPINNER_INTERVAL_SECONDS)
    return _OUTPUT_TITLE_SPINNER_FRAMES[spinner_index % len(_OUTPUT_TITLE_SPINNER_FRAMES)]


def _output_title_text(self: Any) -> str:
    active_job_text = self._active_job_text()
    if active_job_text is None:
        return f"Session output{self._output_retention_note()}"
    spinner_frame = self._output_title_spinner_frame()
    elapsed_text = self._active_job_elapsed_text()
    elapsed_suffix = f" ({elapsed_text})" if elapsed_text is not None else ""
    if spinner_frame is None:
        return f"Session output - {active_job_text} in progress{elapsed_suffix}{self._output_retention_note()}"
    return (
        f"Session output {spinner_frame} - {active_job_text} in progress{elapsed_suffix}{self._output_retention_note()}"
    )


def _advance_output_title_spinner(self: Any) -> None:
    if not self._busy or self._active_job_action_id != "action-analyze":
        return
    spinner_frame = self._output_title_spinner_frame()
    if spinner_frame is None:
        return
    if spinner_frame == getattr(self, "_output_title_spinner_last_frame", None):
        return
    self._output_title_spinner_last_frame = spinner_frame
    try:
        self.query_one("#output-title", _TEXTUAL_STATIC).update(self._output_title_text())
    except _TEXTUAL_QUERY_ERRORS:
        return


def _sync_output_title_spinner(self: Any) -> None:
    spinner_timer = getattr(self, "_output_title_spinner_timer", None)
    animate_spinner = self._busy and self._active_job_action_id == "action-analyze"
    created_timer = spinner_timer is None
    if spinner_timer is None:
        spinner_timer = self.set_interval(
            _OUTPUT_TITLE_SPINNER_INTERVAL_SECONDS,
            self._advance_output_title_spinner,
            pause=not animate_spinner,
        )
        self._output_title_spinner_timer = spinner_timer
    was_animating = bool(getattr(self, "_output_title_spinner_running", False))
    if animate_spinner:
        if not was_animating:
            self._output_title_spinner_started_at = _output_title_spinner_timestamp()
            self._output_title_spinner_last_frame = None
            if not created_timer:
                spinner_timer.resume()
        self._output_title_spinner_running = True
        return
    self._output_title_spinner_started_at = None
    self._output_title_spinner_last_frame = None
    self._output_title_spinner_running = False
    if was_animating:
        spinner_timer.pause()


if TYPE_CHECKING:

    class _TextualSetupMixin:
        def _setup_candidates(self) -> tuple[_SetupTargetCandidate, ...]: ...
        def _selected_setup_candidate(self) -> _SetupTargetCandidate | None: ...
        def _setup_candidate_status(self, candidate: _SetupTargetCandidate) -> str: ...
        def _setup_candidate_display_paths(self, candidate: _SetupTargetCandidate) -> tuple[Path, ...]: ...
        def _configured_target_names(self) -> tuple[str, ...]: ...
        def _setup_filter_value(self) -> str: ...
        def _visible_configured_target_names(self) -> tuple[str, ...]: ...
        def _summary_text(self) -> str: ...
        def _active_job_text(self) -> str | None: ...
        def _active_job_elapsed_text(self) -> str | None: ...
        def _output_title_spinner_timestamp(self) -> float: ...
        def _output_title_spinner_frame(self) -> str | None: ...
        def _output_title_text(self) -> str: ...
        def _output_retention_note(self) -> str: ...
        def _advance_output_title_spinner(self) -> None: ...
        def _sync_output_title_spinner(self) -> None: ...
        def _analyze_note_text(self) -> str: ...
        def _is_target_configured(self, target_name: str) -> bool: ...
        def _set_setup_candidate_by_name(self, target_name: str) -> None: ...
        def _mark_setup_changed(self, message: str, *, reset_candidate_selection: bool = False) -> None: ...
        def _replace_setup_list_value(
            self,
            field_key: str,
            values: list[str],
            *,
            message: str,
            reset_candidate_selection: bool = False,
        ) -> None: ...
        def _setup_note_text(self) -> str: ...
        def _refresh_setup_target_list(self) -> None: ...
        def _refresh_setup_settings_labels(self) -> None: ...
        def on_list_view_highlighted(self, event: Any) -> None: ...
        def _setup_browser_detail_text(self) -> str: ...
        def _add_selected_setup_target(self, target_name: str | None) -> None: ...
        def _remove_selected_setup_target(self, target_name: str | None) -> None: ...
        def _add_target_from_path(self, _selected_path: object) -> None: ...
        def _open_file_browser(self) -> None: ...
        def _open_raw_file_browser(self) -> None: ...
        def _open_help_popup(self) -> None: ...
        def _show_help_modal(self, help_text: str) -> None: ...
        def _toggle_setup_flag(self, field_key: str, *, label: str) -> None: ...
        def _toggle_setup_mode(self) -> None: ...
        def _toggle_setup_telemetry(self) -> None: ...
        def _setup_has_targets(self) -> bool: ...
        def _targets_action_allowed(self, _action_text: str) -> bool: ...
        def _run_app_module_cfg_action(
            self,
            _attr_name: str,
            _label: str,
            *,
            action_id: str,
            require_targets: bool = False,
            action_text: str | None = None,
            marks_dirty: bool = False,
        ) -> None: ...
        def _run_analyze_checks(self) -> None: ...
        def _run_tool_self_check(self) -> None: ...
        def _run_tool_dumps(self) -> None: ...
        def _run_tool_refresh_ast(self) -> None: ...
        def _run_tool_datatype_usage(self) -> None: ...
        def _run_tool_variable_trace(self) -> None: ...
        def _run_tool_module_locals(self) -> None: ...
        def _prompt_setup_value(self, field_key: str, *, label: str, is_list: bool = False) -> None: ...
        async def _prompt_setup_value_async(self, field_key: str, *, label: str, is_list: bool = False) -> None: ...
        def _queue_setup_value_prompt(self, field_key: str, *, label: str, is_list: bool = False) -> None: ...
        def _set_setup_filter_text(self, raw_text: object) -> None: ...
        def _prompt_setup_filter(self) -> None: ...
        def _activate_view(self, view_name: str) -> None: ...
else:

    class _TextualSetupMixin:
        """Provides Setup view state and inline editing/tool launch helpers."""

        _setup_candidates = _setup_candidates
        _selected_setup_candidate = _selected_setup_candidate
        _setup_candidate_status = _setup_candidate_status
        _setup_candidate_display_paths = _setup_candidate_display_paths
        _configured_target_names = _configured_target_names
        _setup_filter_value = _setup_filter_value
        _visible_configured_target_names = _visible_configured_target_names
        _summary_text = _summary_text
        _active_job_text = _active_job_text
        _active_job_elapsed_text = _active_job_elapsed_text
        _output_title_spinner_timestamp = staticmethod(_output_title_spinner_timestamp)
        _output_title_spinner_frame = _output_title_spinner_frame
        _output_title_text = _output_title_text
        _output_retention_note = _output_retention_note
        _advance_output_title_spinner = _advance_output_title_spinner
        _sync_output_title_spinner = _sync_output_title_spinner
        _analyze_note_text = _analyze_note_text
        _is_target_configured = _is_target_configured
        _set_setup_candidate_by_name = _set_setup_candidate_by_name
        _mark_setup_changed = _mark_setup_changed
        _replace_setup_list_value = _replace_setup_list_value
        _setup_note_text = _setup_note_text
        _refresh_setup_target_list = _refresh_setup_target_list
        _refresh_setup_settings_labels = _refresh_setup_settings_labels
        on_list_view_highlighted = on_list_view_highlighted
        _setup_browser_detail_text = _setup_browser_detail_text
        _add_selected_setup_target = _add_selected_setup_target
        _remove_selected_setup_target = _remove_selected_setup_target
        _add_target_from_path = _add_target_from_path
        _open_file_browser = _open_file_browser
        _open_raw_file_browser = _open_raw_file_browser
        _open_help_popup = _open_help_popup
        _show_help_modal = _show_help_modal
        _toggle_setup_flag = _toggle_setup_flag
        _toggle_setup_mode = _toggle_setup_mode
        _toggle_setup_telemetry = _toggle_setup_telemetry
        _setup_has_targets = _setup_has_targets
        _targets_action_allowed = _targets_action_allowed
        _run_app_module_cfg_action = _run_app_module_cfg_action
        _run_analyze_checks = _run_analyze_checks
        _run_tool_self_check = _run_tool_self_check
        _run_tool_dumps = _run_tool_dumps
        _run_tool_refresh_ast = _run_tool_refresh_ast
        _run_tool_datatype_usage = _run_tool_datatype_usage
        _run_tool_variable_trace = _run_tool_variable_trace
        _run_tool_module_locals = _run_tool_module_locals
        _prompt_setup_value = _prompt_setup_value
        _prompt_setup_value_async = _prompt_setup_value_async
        _queue_setup_value_prompt = _queue_setup_value_prompt
        _set_setup_filter_text = _set_setup_filter_text
        _prompt_setup_filter = _prompt_setup_filter
        _activate_view = _activate_view
