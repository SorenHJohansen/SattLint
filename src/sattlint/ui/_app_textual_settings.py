from __future__ import annotations

from contextlib import suppress
from typing import TYPE_CHECKING, Any, cast

from ._app_textual_setup_display import (
    _setup_toggle_text,
    _setup_value_text,
)
from ._app_textual_shared import (
    _TEXTUAL_QUERY_ERRORS,
    _TEXTUAL_STATIC,
    InteractionRequest,
)

_DEFAULT_RUN_HISTORY_LIMIT = 50
_DEFAULT_OUTPUT_RETENTION_LINES = 4000


def _section_value(self: Any, key: str, subkey: str, default: object) -> object:
    section = self._cfg.get(key)
    if isinstance(section, dict):
        mapping = cast(dict[str, object], section)
        return mapping.get(subkey, default)
    return default


def _refresh_settings_labels(self: Any) -> None:
    run_history_enabled = bool(_section_value(self, "run_history", "enabled", True))
    run_history_limit = _section_value(self, "run_history", "limit", _DEFAULT_RUN_HISTORY_LIMIT)
    retention = _section_value(self, "output", "retention_lines", _DEFAULT_OUTPUT_RETENTION_LINES)
    debug = bool(self._cfg.get("debug", False))
    review_output_dir = _section_value(self, "review", "output_dir", "")

    def _safe_update(widget_id: str, text: object) -> None:
        with suppress(*_TEXTUAL_QUERY_ERRORS):
            self.query_one(f"#{widget_id}", _TEXTUAL_STATIC).update(text)

    _safe_update(
        "settings-label-run-history",
        _setup_toggle_text(
            run_history_enabled,
            enabled_detail="Completed runs are saved",
            disabled_detail="Runs are not saved",
        ),
    )
    _safe_update(
        "settings-label-run-history-limit",
        _setup_value_text(str(run_history_limit), f"Keep the most recent {run_history_limit} runs"),
    )
    _safe_update(
        "settings-label-debug",
        _setup_toggle_text(
            debug,
            enabled_detail="Verbose runtime logging",
            disabled_detail="Standard runtime logging",
        ),
    )
    _safe_update(
        "settings-label-output-retention",
        _setup_value_text(f"{retention} lines", "Live session output cap"),
    )
    review_label = str(review_output_dir).strip() or "Default directory"
    _safe_update(
        "settings-label-review-output-dir",
        _setup_value_text(review_label, "Where Change Review artifacts are written"),
    )


def _settings_note_text(self: Any) -> str:
    return (
        "App-level settings are saved to your user config (config.toml) and apply to every configuration. "
        "Configuration settings stay in the Setup view and are saved automatically. Press Ctrl+S to save app settings."
    )


def _mark_settings_changed(self: Any, message: str) -> None:
    self._dirty = True
    for key in ("debug", "run_history", "output", "review"):
        if key in self._cfg:
            self._app_only_cfg[key] = self._cfg[key]
    self._refresh_summary()
    self._refresh_view()
    self._set_active_action(None)
    self._refresh_shell_state()
    self._write_output(message)


def _toggle_app_section_flag(self: Any, key: str, subkey: str, *, label: str) -> None:
    section = cast(object, self._cfg.get(key))
    section_map: dict[str, object]
    if isinstance(section, dict):
        section_map = cast(dict[str, object], section)
    else:
        section_map = {}
        self._cfg[key] = section_map
    section_map[subkey] = not bool(section_map.get(subkey, False))
    self._mark_settings_changed(f"Updated {label}.")


def _toggle_app_debug(self: Any) -> None:
    self._cfg["debug"] = not bool(self._cfg.get("debug", False))
    self._mark_settings_changed("Updated debug logging.")


def _prompt_app_int(self: Any, key: str, subkey: str, *, label: str) -> None:
    if self._active_request is not None:
        return
    current = _section_value(self, key, subkey, "")
    request = InteractionRequest(
        kind="prompt",
        title=f"Set {label}",
        message=f"Enter a positive integer for {label}.",
        default="" if current is None else str(current),
    )

    def _apply_response(response: object) -> None:
        raw_value = str(response or "").strip()
        try:
            value = int(raw_value)
        except ValueError:
            self._report_error("Invalid value", f"{label} must be a positive integer.")
            return
        if value <= 0:
            self._report_error("Invalid value", f"{label} must be a positive integer.")
            return
        section = cast(object, self._cfg.get(key))
        section_map: dict[str, object]
        if isinstance(section, dict):
            section_map = cast(dict[str, object], section)
        else:
            section_map = {}
            self._cfg[key] = section_map
        section_map[subkey] = value
        self._mark_settings_changed(f"Updated {label} to {value}.")

    self.present_request(request, on_response_fn=_apply_response)


def _prompt_app_int_async(self: Any, key: str, subkey: str, *, label: str) -> None:
    if self._active_request is not None:
        return
    current = _section_value(self, key, subkey, "")

    async def _apply_async() -> None:
        response = await self.present_request_async(
            InteractionRequest(
                kind="prompt",
                title=f"Set {label}",
                message=f"Enter a positive integer for {label}.",
                default="" if current is None else str(current),
            )
        )
        raw_value = str(response or "").strip()
        try:
            value = int(raw_value)
        except ValueError:
            self._report_error("Invalid value", f"{label} must be a positive integer.")
            return
        if value <= 0:
            self._report_error("Invalid value", f"{label} must be a positive integer.")
            return
        section = self._cfg.get(key)
        section_map: dict[str, object]
        if isinstance(section, dict):
            section_map = cast(dict[str, object], section)
        else:
            section_map = {}
            self._cfg[key] = section_map
        section_map[subkey] = value
        self._mark_settings_changed(f"Updated {label} to {value}.")

    self._schedule_ui_coroutine(_apply_async, fallback_fn=lambda: self._prompt_app_int(key, subkey, label=label))


def _queue_app_int_prompt(self: Any, key: str, subkey: str, *, label: str) -> None:
    self._schedule_ui_coroutine(
        lambda: self._prompt_app_int_async(key, subkey, label=label),
        fallback_fn=lambda: self._prompt_app_int(key, subkey, label=label),
    )


def _prompt_app_text(self: Any, key: str, subkey: str, *, label: str, message: str) -> None:
    if self._active_request is not None:
        return
    current = _section_value(self, key, subkey, "")
    request = InteractionRequest(
        kind="prompt",
        title=f"Set {label}",
        message=message,
        default="" if current is None else str(current),
    )

    def _apply_response(response: object) -> None:
        value = str(response or "").strip()
        section = cast(object, self._cfg.get(key))
        section_map: dict[str, object]
        if isinstance(section, dict):
            section_map = cast(dict[str, object], section)
        else:
            section_map = {}
            self._cfg[key] = section_map
        section_map[subkey] = value
        self._mark_settings_changed(f"Updated {label}.")

    self.present_request(request, on_response_fn=_apply_response)


def _prompt_app_text_async(self: Any, key: str, subkey: str, *, label: str, message: str) -> None:
    if self._active_request is not None:
        return
    current = _section_value(self, key, subkey, "")

    async def _apply_async() -> None:
        response = await self.present_request_async(
            InteractionRequest(
                kind="prompt",
                title=f"Set {label}",
                message=message,
                default="" if current is None else str(current),
            )
        )
        value = str(response or "").strip()
        section = cast(object, self._cfg.get(key))
        section_map: dict[str, object]
        if isinstance(section, dict):
            section_map = cast(dict[str, object], section)
        else:
            section_map = {}
            self._cfg[key] = section_map
        section_map[subkey] = value
        self._mark_settings_changed(f"Updated {label}.")

    self._schedule_ui_coroutine(
        _apply_async, fallback_fn=lambda: self._prompt_app_text(key, subkey, label=label, message=message)
    )


def _queue_app_text_prompt(self: Any, key: str, subkey: str, *, label: str, message: str) -> None:
    self._schedule_ui_coroutine(
        lambda: self._prompt_app_text_async(key, subkey, label=label, message=message),
        fallback_fn=lambda: self._prompt_app_text(key, subkey, label=label, message=message),
    )


if TYPE_CHECKING:

    class _TextualSettingsMixin:
        def _refresh_settings_labels(self) -> None: ...
        def _settings_note_text(self) -> str: ...
        def _mark_settings_changed(self, message: str) -> None: ...
        def _toggle_app_section_flag(self, key: str, subkey: str, *, label: str) -> None: ...
        def _toggle_app_debug(self) -> None: ...
        def _prompt_app_int(self, key: str, subkey: str, *, label: str) -> None: ...
        async def _prompt_app_int_async(self, key: str, subkey: str, *, label: str) -> None: ...
        def _queue_app_int_prompt(self, key: str, subkey: str, *, label: str) -> None: ...
        def _prompt_app_text(self, key: str, subkey: str, *, label: str, message: str) -> None: ...
        async def _prompt_app_text_async(self, key: str, subkey: str, *, label: str, message: str) -> None: ...
        def _queue_app_text_prompt(self, key: str, subkey: str, *, label: str, message: str) -> None: ...
else:

    class _TextualSettingsMixin:
        """Provides the app-level Settings view editing behavior."""

        _refresh_settings_labels = _refresh_settings_labels
        _settings_note_text = _settings_note_text
        _mark_settings_changed = _mark_settings_changed
        _toggle_app_section_flag = _toggle_app_section_flag
        _toggle_app_debug = _toggle_app_debug
        _prompt_app_int = _prompt_app_int
        _prompt_app_int_async = _prompt_app_int_async
        _queue_app_int_prompt = _queue_app_int_prompt
        _prompt_app_text = _prompt_app_text
        _prompt_app_text_async = _prompt_app_text_async
        _queue_app_text_prompt = _queue_app_text_prompt
