from __future__ import annotations

from collections.abc import Callable
from functools import partial
from typing import Any, cast

from ._app_textual_shared import InteractionRequest, _MenuOption, _stringify_list_values, _stringify_value


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
    handlers = getattr(self, "_analysis_handlers", None)
    action_fn = cast(dict[str, Callable[..., Any]], handlers).get(attr_name) if isinstance(handlers, dict) else None
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
        self._persist_project()
        self._dirty = self._dirty or not self._project_loaded()
        self._setup_candidate_index = 0
        self._refresh_summary()
        self._refresh_view()
        self._set_active_action(None)
        self._refresh_shell_state()
        self._write_output(f"Updated {label} from the Setup view.")

    self.present_request(request, on_response_fn=_apply_response)


def _remove_other_lib_dir(self: Any) -> None:
    if self._active_request is not None:
        return
    entries = _stringify_list_values(self._cfg.get("other_lib_dirs"))
    if not entries:
        self._write_output("No extra library folders are configured to remove.")
        return
    options = tuple(
        _MenuOption(key=str(index), label=value, description="") for index, value in enumerate(entries, start=1)
    )
    request = InteractionRequest(
        kind="menu",
        title="Remove extra library folder",
        message="Choose which extra library folder to remove.",
        options=options,
    )

    def _apply_response(response: object) -> None:
        if response is None:
            return
        try:
            selected_index = int(str(response)) - 1
        except (TypeError, ValueError):
            return
        if not (0 <= selected_index < len(entries)):
            return
        removed = entries[selected_index]
        updated = [value for index, value in enumerate(entries) if index != selected_index]
        self._replace_setup_list_value(
            "other_lib_dirs",
            updated,
            message=f"Removed extra library folder '{removed}' from the Setup view.",
            reset_candidate_selection=True,
        )

    self.present_request(request, on_response_fn=_apply_response)


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
