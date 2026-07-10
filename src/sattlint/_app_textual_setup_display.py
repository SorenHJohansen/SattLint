from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any, cast

from ._app_textual_shared import (
    _TEXTUAL_QUERY_ERRORS,
    _TEXTUAL_STATIC,
    _SetupTargetCandidate,
    _stringify_list_values,
    _stringify_value,
    discover_setup_target_candidates,
)

_OUTPUT_TITLE_SPINNER_FRAMES = ("⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏")
_OUTPUT_TITLE_SPINNER_INTERVAL_SECONDS = 1.0 / 60.0


def _output_title_spinner_timestamp() -> float:
    return time.monotonic()


def _setup_value_text(primary: str, secondary: str | None = None) -> str:
    primary_text = primary.strip()
    secondary_text = secondary.strip() if secondary is not None else ""
    if not secondary_text:
        return primary_text
    return f"{primary_text}\n{secondary_text}"


def _setup_path_text(value: str, *, empty_label: str = "Not configured") -> str:
    stripped = value.strip()
    if not stripped:
        return empty_label
    normalized = stripped.rstrip("\\/")
    folder_name = re.split(r"[\\/]", normalized)[-1] if normalized else stripped
    return _setup_value_text(folder_name or stripped, stripped)


def _setup_other_dirs_text(values: object) -> str:
    entries = _stringify_list_values(values)
    if not entries:
        return "No extra libraries"
    folder_word = "folder" if len(entries) == 1 else "folders"
    return _setup_value_text(f"{len(entries)} {folder_word} configured", ", ".join(entries))


def _setup_mode_text(mode: str) -> str:
    normalized_mode = mode.strip().casefold()
    if normalized_mode == "draft":
        return _setup_value_text("Draft mode", ".s and .l files")
    if normalized_mode == "official" or not normalized_mode:
        return _setup_value_text("Official mode", ".x and .z files")
    return _setup_value_text(mode.strip().replace("_", " ").title(), "Custom mode")


def _setup_toggle_text(enabled: bool, *, enabled_detail: str, disabled_detail: str) -> str:
    return _setup_value_text(
        "Enabled" if enabled else "Disabled",
        enabled_detail if enabled else disabled_detail,
    )


def _setup_candidates(self: Any) -> tuple[_SetupTargetCandidate, ...]:
    return discover_setup_target_candidates(self._cfg)


def _selected_setup_candidate(self: Any) -> _SetupTargetCandidate | None:
    candidates = self._setup_candidates()
    if not candidates:
        self._setup_candidate_index = 0
        return None
    self._setup_candidate_index %= len(candidates)
    return candidates[self._setup_candidate_index]


def _setup_candidate_status(self: Any, candidate: _SetupTargetCandidate) -> str:
    if not candidate.available:
        return "not valid for current mode"
    if self._is_target_configured(candidate.name):
        return "already configured"
    return "available"


def _setup_candidate_display_paths(candidate: _SetupTargetCandidate) -> tuple[Path, ...]:
    display_paths: list[Path] = []
    seen: set[tuple[str, str]] = set()
    for path in candidate.files:
        resolved = path.resolve()
        display_path = resolved.parent / candidate.name
        key = (resolved.parent.as_posix().casefold(), candidate.name.casefold())
        if key in seen:
            continue
        seen.add(key)
        display_paths.append(display_path)
    return tuple(sorted(display_paths, key=lambda path: path.as_posix().casefold()))


def _configured_target_names(self: Any) -> tuple[str, ...]:
    return _stringify_list_values(self._cfg.get("analyzed_programs_and_libraries", []))


def _setup_filter_value(self: Any) -> str:
    return str(getattr(self, "_setup_filter_text", "") or "").strip()


def _visible_configured_target_names(self: Any) -> tuple[str, ...]:
    configured_targets = self._configured_target_names()
    filter_text = self._setup_filter_value().casefold()
    if not filter_text:
        return configured_targets
    return tuple(target for target in configured_targets if filter_text in target.casefold())


def _summary_text(self: Any) -> str:
    configured_targets = self._configured_target_names()
    if not configured_targets:
        return str(self._summarize_targets_fn(self._cfg))
    return "\n".join(configured_targets)


def _documentation_selection(self: Any) -> dict[str, Any]:
    app_module = self._app_module
    if app_module is None:
        return {"mode": "all", "instance_paths": [], "moduletype_names": []}
    selection_fn = getattr(app_module, "_get_documentation_unit_selection", None)
    if not callable(selection_fn):
        return {"mode": "all", "instance_paths": [], "moduletype_names": []}
    selection = selection_fn()
    if not isinstance(selection, dict):
        return {"mode": "all", "instance_paths": [], "moduletype_names": []}
    return cast(dict[str, Any], selection)


def _documentation_scope_summary_text(self: Any) -> str:
    selection = self._documentation_selection()
    mode = _stringify_value(cast(object | None, selection.get("mode", "all"))).strip().casefold() or "all"
    if mode == "all":
        return "all units"
    if mode == "moduletype_names":
        values = _stringify_list_values(selection.get("moduletype_names"))
        return "moduletype: " + ", ".join(values) if values else "moduletype filter not set"
    if mode == "instance_paths":
        values = _stringify_list_values(selection.get("instance_paths"))
        return "instance path: " + ", ".join(values) if values else "instance-path filter not set"
    return mode


def _active_job_text(self: Any) -> str | None:
    if not self._busy:
        return None
    label = (self._active_job_label or "").strip()
    return label or None


def _active_job_elapsed_text(self: Any) -> str | None:
    started_at = getattr(self, "_active_job_started_at", None)
    if started_at is None:
        return None
    elapsed_seconds = max(0, int(time.monotonic() - float(started_at)))
    minutes, seconds = divmod(elapsed_seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


def _output_retention_note(self: Any) -> str:
    dropped_line_count = int(getattr(self, "_session_output_dropped_line_count", 0) or 0)
    if dropped_line_count <= 0:
        return ""
    return " - retaining last 4000 lines"


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


def _analyze_note_text(self: Any) -> str:
    filter_text = str(getattr(self, "_analyze_filter_text", "") or "").strip()
    filter_suffix = (
        f' Filter: "{filter_text}". Press / to change or clear it.'
        if filter_text
        else " Press / to filter the planner."
    )
    if self._busy and self._active_job_action_id == "action-analyze":
        if self._active_job_cancel_requested:
            return "Stopping selected analyses now. Live output remains in Session output below."
        return (
            "Selected analyses are running. Live output is shown in Session output below. "
            "Use Cancel running or Ctrl+G to stop."
        )
    if not self._setup_has_targets():
        return f"No analysis targets are configured yet. Add one in Setup to enable the planner queue runner.{filter_suffix}"
    if filter_text and not self._planner_entry_ids():
        return f'No analyses match "{filter_text}". Press / to change or clear the filter.'
    plan = self._analyze_plan()
    if not self._ordered_selected_analyze_entry_ids():
        return (
            "Select one or more analyses below. Suites collapse overlapping leaf checks when the queue is planned."
            f"{filter_suffix}"
        )
    if plan.missing_handlers:
        return (
            "Some selected analyses are unavailable in the current Textual session. Review the queue summary before running anything."
            f"{filter_suffix}"
        )
    return (
        f"{len(plan.executable_steps)} queued step(s) are ready to run. "
        "Use Run selected analyses to execute the normalized plan in catalog order."
        f"{filter_suffix}"
    )


def _documentation_note_text(self: Any) -> str:
    scope_summary = self._documentation_scope_summary_text()
    if not self._setup_has_targets():
        return "No analysis targets are configured yet. Add one in Setup before previewing units or generating documentation."
    return (
        f"Current scope: {scope_summary}. Preview candidates before narrowing scope if you need a smaller DOCX output."
    )
