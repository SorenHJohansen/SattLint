# pyright: reportPrivateUsage=false, reportUnusedFunction=false
from __future__ import annotations

from collections.abc import Callable
from functools import partial
from typing import Any, cast

from ._app_textual_shared import InteractionRequest, _stringify_list_values, _stringify_value


def _run_app_module_cfg_action(
    self: Any,
    attr_name: str,
    label: str,
    *,
    action_id: str,
    require_targets: bool = False,
    action_text: str | None = None,
    marks_dirty: bool = False,
) -> None:
    if require_targets and not self._targets_action_allowed(action_text or label.casefold()):
        return
    app_module = self._app_module
    action_fn = getattr(app_module, attr_name, None) if app_module is not None else None
    if not callable(action_fn):
        self._write_output(f"{label} is unavailable in the current Textual session.")
        return
    self._start_action(
        label,
        partial(cast(Callable[[Any], Any], action_fn), self._cfg),
        action_id=action_id,
        marks_dirty=marks_dirty,
    )


def _run_analyze_checks(self: Any) -> None:
    self._run_app_module_cfg_action(
        "run_checks_menu",
        "Analyzer checks",
        action_id="action-analyze",
        require_targets=True,
        action_text="analysis checks",
    )


def _run_tool_self_check(self: Any) -> None:
    self._start_action("Self-check diagnostics", lambda: self._self_check_fn(self._cfg), action_id="action-tools")


def _run_tool_dumps(self: Any) -> None:
    if not self._targets_action_allowed("diagnostics and dumps"):
        return
    self._start_action("Diagnostics & dumps", lambda: self._dump_menu_fn(self._cfg), action_id="action-tools")


def _run_tool_refresh_ast(self: Any) -> None:
    if not self._targets_action_allowed("all cache refresh"):
        return
    self._start_action(
        "Refresh all caches",
        lambda: self._force_refresh_ast_fn(self._cfg),
        action_id="action-tools",
    )


def _run_tool_datatype_usage(self: Any) -> None:
    self._run_app_module_cfg_action(
        "run_datatype_usage_analysis",
        "Datatype field trace",
        action_id="action-tools",
        require_targets=True,
        action_text="datatype usage tracing",
    )


def _run_tool_variable_trace(self: Any) -> None:
    self._run_app_module_cfg_action(
        "run_debug_variable_usage",
        "Variable usage trace",
        action_id="action-tools",
        require_targets=True,
        action_text="variable usage tracing",
    )


def _run_tool_module_locals(self: Any) -> None:
    self._run_app_module_cfg_action(
        "run_module_localvar_analysis",
        "Module local usage",
        action_id="action-tools",
        require_targets=True,
        action_text="module local-variable tracing",
    )


def _prompt_setup_value(self: Any, field_key: str, *, label: str, is_list: bool = False) -> None:
    if self._active_request is not None:
        return

    current_value = self._cfg.get(field_key)
    default_text = (
        ", ".join(_stringify_list_values(current_value))
        if is_list
        else _stringify_value(cast(object | None, current_value))
    )
    message = (
        f"Enter the full comma-separated list for {label}. Leave blank to clear the list."
        if is_list
        else f"Enter a new path for {label}."
    )
    request = InteractionRequest(kind="prompt", message=message, default=default_text)

    def _apply_response(response: object) -> None:
        raw_value = str(response or "").strip()
        new_value: list[str] | str = (
            [part.strip() for part in raw_value.split(",") if part.strip()] if is_list else raw_value
        )
        if is_list:
            if _stringify_list_values(self._cfg.get(field_key)) == tuple(cast(list[str], new_value)):
                return
            self._cfg[field_key] = list(cast(list[str], new_value))
        else:
            if self._cfg.get(field_key) == new_value:
                return
            self._cfg[field_key] = new_value
        self._dirty = True
        self._setup_candidate_index = 0
        self._refresh_summary()
        self._refresh_view()
        self._set_active_action(None)
        self._refresh_shell_state()
        self._write_output(f"Updated {label} from the Setup view.")

    self.present_request(request, on_response_fn=_apply_response)


async def _prompt_setup_value_async(self: Any, field_key: str, *, label: str, is_list: bool = False) -> None:
    if self._active_request is not None:
        return

    current_value = self._cfg.get(field_key)
    default_text = (
        ", ".join(_stringify_list_values(current_value))
        if is_list
        else _stringify_value(cast(object | None, current_value))
    )
    message = (
        f"Enter the full comma-separated list for {label}. Leave blank to clear the list."
        if is_list
        else f"Enter a new path for {label}."
    )
    response = await self.present_request_async(
        InteractionRequest(kind="prompt", message=message, default=default_text)
    )

    raw_value = str(response or "").strip()
    new_value: list[str] | str = (
        [part.strip() for part in raw_value.split(",") if part.strip()] if is_list else raw_value
    )
    if is_list:
        if _stringify_list_values(self._cfg.get(field_key)) == tuple(cast(list[str], new_value)):
            return
        self._cfg[field_key] = list(cast(list[str], new_value))
    else:
        if self._cfg.get(field_key) == new_value:
            return
        self._cfg[field_key] = new_value
    self._dirty = True
    self._setup_candidate_index = 0
    self._refresh_summary()
    self._refresh_view()
    self._set_active_action(None)
    self._refresh_shell_state()
    self._write_output(f"Updated {label} from the Setup view.")


def _queue_setup_value_prompt(self: Any, field_key: str, *, label: str, is_list: bool = False) -> None:
    self._schedule_ui_coroutine(
        lambda: self._prompt_setup_value_async(field_key, label=label, is_list=is_list),
        fallback_fn=lambda: self._prompt_setup_value(field_key, label=label, is_list=is_list),
    )


def _set_setup_filter_text(self: Any, raw_text: object) -> None:
    filter_text = str(raw_text or "").strip()
    if filter_text == self._setup_filter_value():
        return
    self._setup_filter_text = filter_text
    self._selected_configured_target = None
    self._refresh_view()
    self._set_active_action(None)
    self._refresh_shell_state()
    if filter_text:
        self._write_output(f'Setup target filter: "{filter_text}".')
    else:
        self._write_output("Cleared the Setup target filter.")


def _prompt_setup_filter(self: Any) -> None:
    if self._active_request is not None:
        return
    request = InteractionRequest(
        kind="prompt",
        title="Filter setup targets",
        message="Type text to filter configured target names. Leave blank to clear the filter.",
        default=self._setup_filter_value(),
    )
    self.present_request(request, on_response_fn=self._set_setup_filter_text)


def _activate_view(self: Any, view_name: str) -> None:
    self._active_view = view_name
    self._refresh_view()
    self._set_active_action(None)
    self._refresh_shell_state()
