# pyright: reportMissingImports=false, reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportUnknownLambdaType=false, reportGeneralTypeIssues=false, reportInvalidTypeForm=false, reportConstantRedefinition=false, reportPrivateUsage=false, reportUnusedClass=false, reportUnusedFunction=false, reportUnknownArgumentType=false

from __future__ import annotations

import re
import time
from contextlib import suppress
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from ._app_textual_shared import (
    _TEXTUAL_BUTTON,
    _TEXTUAL_DIRECTORY_TREE,
    _TEXTUAL_LIST_ITEM,
    _TEXTUAL_LIST_VIEW,
    _TEXTUAL_QUERY_ERRORS,
    _TEXTUAL_STATIC,
    InteractionRequest,
    _config_directory_paths,
    _SetupTargetCandidate,
    _stringify_list_values,
    _stringify_value,
    discover_setup_target_candidates,
)
from ._app_textual_widgets import _FileBrowserScreen, _HelpScreen

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
        return f"{filter_suffix.lstrip()}" if filter_text else ""
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


def _is_target_configured(self: Any, target_name: str) -> bool:
    return any(existing.casefold() == target_name.casefold() for existing in self._configured_target_names())


def _set_setup_candidate_by_name(self: Any, target_name: str) -> None:
    for index, candidate in enumerate(self._setup_candidates()):
        if candidate.name.casefold() == target_name.casefold():
            self._setup_candidate_index = index
            return


def _mark_setup_changed(self: Any, message: str, *, reset_candidate_selection: bool = False) -> None:
    self._dirty = True
    if reset_candidate_selection:
        self._setup_candidate_index = 0
    self._refresh_summary()
    self._refresh_view()
    self._set_active_action(None)
    self._refresh_shell_state()
    self._write_output(message)


def _replace_setup_list_value(
    self: Any,
    field_key: str,
    values: list[str],
    *,
    message: str,
    reset_candidate_selection: bool = False,
) -> None:
    if _stringify_list_values(self._cfg.get(field_key)) == tuple(values):
        return
    self._cfg[field_key] = list(values)
    self._mark_setup_changed(message, reset_candidate_selection=reset_candidate_selection)


def _setup_note_text(self: Any) -> str:
    filter_text = self._setup_filter_value()
    visible_targets = self._visible_configured_target_names()
    if filter_text and not visible_targets:
        return f'No configured targets match "{filter_text}". Press / to change or clear the filter.'
    base_text = (
        "Click a target in the list to select it, then use Remove to delete it. "
        "Use Add from file to add a new target. Settings on the right update immediately."
    )
    if filter_text:
        return f'{base_text} Filter: "{filter_text}". Press / to change or clear it.'
    return f"{base_text} Press / to filter configured targets."


def _refresh_setup_target_list(self: Any) -> None:
    try:
        lv = self.query_one("#setup-target-listview", _TEXTUAL_LIST_VIEW)
    except _TEXTUAL_QUERY_ERRORS:
        return

    configured_targets = list(self._visible_configured_target_names())
    if self._selected_configured_target is not None and not any(
        t.casefold() == self._selected_configured_target.casefold() for t in configured_targets
    ):
        self._selected_configured_target = None

    self._setup_target_names_list = configured_targets
    lv.clear()
    for target in configured_targets:
        lv.append(_TEXTUAL_LIST_ITEM(_TEXTUAL_STATIC(target)))

    if self._selected_configured_target is not None:
        for i, name in enumerate(configured_targets):
            if name.casefold() == self._selected_configured_target.casefold():
                lv.index = i
                break

    has_selection = self._selected_configured_target is not None and bool(configured_targets)
    with suppress(*_TEXTUAL_QUERY_ERRORS):
        self.query_one("#setup-target-remove", _TEXTUAL_BUTTON).disabled = not has_selection


def _refresh_setup_settings_labels(self: Any) -> None:
    program_dir = _stringify_value(cast(object | None, self._cfg.get("program_dir", "")))
    abb_dir = _stringify_value(cast(object | None, self._cfg.get("ABB_lib_dir", "")))
    other_dirs = self._cfg.get("other_lib_dirs", [])
    icf_dir = _stringify_value(cast(object | None, self._cfg.get("icf_dir", "")))
    mode = _stringify_value(cast(object | None, self._cfg.get("mode", "official"))) or "official"
    scan_root_only = bool(self._cfg.get("scan_root_only", False))
    fast_cache_validation = bool(self._cfg.get("use_file_ast_cache", False))
    debug = bool(self._cfg.get("debug", False))
    telemetry = self._cfg.get("telemetry")
    telemetry_enabled = (
        bool(cast(object | None, telemetry.get("enabled", False))) if isinstance(telemetry, dict) else False
    )

    def _safe_update(widget_id: str, text: object) -> None:
        with suppress(*_TEXTUAL_QUERY_ERRORS):
            self.query_one(f"#{widget_id}", _TEXTUAL_STATIC).update(text)

    _safe_update("setup-label-program-dir", _setup_path_text(program_dir))
    _safe_update("setup-label-abb-dir", _setup_path_text(abb_dir))
    _safe_update("setup-label-other-dirs", _setup_other_dirs_text(other_dirs))
    _safe_update("setup-label-icf-dir", _setup_path_text(icf_dir))
    _safe_update("setup-label-mode", _setup_mode_text(mode))
    _safe_update(
        "setup-label-scan-root-only",
        _setup_toggle_text(
            scan_root_only,
            enabled_detail="Only configured roots are scanned",
            disabled_detail="Nested folders are also scanned",
        ),
    )
    _safe_update(
        "setup-label-fast-cache",
        _setup_toggle_text(
            fast_cache_validation,
            enabled_detail="Fast cache validation is active",
            disabled_detail="Full cache validation is active",
        ),
    )
    _safe_update(
        "setup-label-debug",
        _setup_toggle_text(
            debug,
            enabled_detail="Verbose runtime logging",
            disabled_detail="Standard runtime logging",
        ),
    )
    _safe_update(
        "setup-label-telemetry",
        _setup_toggle_text(
            telemetry_enabled,
            enabled_detail="Anonymous telemetry is allowed",
            disabled_detail="Telemetry stays off",
        ),
    )


def on_list_view_highlighted(self: Any, event: Any) -> None:
    lv = getattr(event, "list_view", None)
    if lv is None or getattr(lv, "id", None) != "setup-target-listview":
        return
    index = getattr(lv, "index", None)
    if index is not None and 0 <= index < len(self._setup_target_names_list):
        self._selected_configured_target = self._setup_target_names_list[index]
    else:
        self._selected_configured_target = None
    has_selection = self._selected_configured_target is not None
    with suppress(*_TEXTUAL_QUERY_ERRORS):
        self.query_one("#setup-target-remove", _TEXTUAL_BUTTON).disabled = not has_selection or not bool(
            self._configured_target_names()
        )


def _setup_browser_detail_text(self: Any) -> str:
    candidate = self._selected_setup_candidate()
    directories = _config_directory_paths(self._cfg)
    lines = [
        "Selected Target Detail",
        f"Mode: {self._cfg.get('mode', 'official')}",
        f"scan_root_only: {bool(self._cfg.get('scan_root_only', False))}",
    ]
    if candidate is None:
        lines.append("Target: none")
    else:
        lines.append(f"Target: {candidate.name}")
        lines.append(f"Status: {self._setup_candidate_status(candidate)}")
        lines.append("Locations:")
        lines.extend(f"- {path}" for path in _setup_candidate_display_paths(candidate))

    lines.append("")
    lines.append("Directories")
    if directories:
        lines.extend(f"- {path}" for path in directories)
    else:
        lines.append("(none configured)")
    telemetry = self._cfg.get("telemetry")
    telemetry_enabled = (
        bool(cast(object | None, telemetry.get("enabled", False))) if isinstance(telemetry, dict) else False
    )
    lines.append("")
    lines.append("Runtime")
    lines.append(f"debug: {bool(self._cfg.get('debug', False))}")
    lines.append(f"telemetry: {telemetry_enabled}")
    return "\n".join(lines)


def _add_selected_setup_target(self: Any, target_name: str | None = None) -> None:
    if target_name is not None:
        self._set_setup_candidate_by_name(target_name)
    candidate = self._selected_setup_candidate()
    if candidate is None:
        self._write_output("No discovered target is available to add from the Setup view.")
        return
    if target_name is not None and candidate.name.casefold() != target_name.casefold():
        self._write_output(f"Target '{target_name}' is not currently discovered in the Setup view.")
        return

    target_values = list(_stringify_list_values(self._cfg.get("analyzed_programs_and_libraries")))
    if any(existing.casefold() == candidate.name.casefold() for existing in target_values):
        self._write_output(f"Target '{candidate.name}' is already configured.")
        return
    if not candidate.available:
        self._write_output(
            f"Target '{candidate.name}' is not available for the current mode '{self._cfg.get('mode', 'official')}'."
        )
        return

    self._replace_setup_list_value(
        "analyzed_programs_and_libraries",
        [*target_values, candidate.name],
        message=f"Added analysis target '{candidate.name}' from the Setup view.",
    )


def _remove_selected_setup_target(self: Any, target_name: str | None = None) -> None:
    candidate = self._selected_setup_candidate()
    selected_name = target_name or (candidate.name if candidate is not None else None)
    if selected_name is None:
        self._write_output("No discovered target is selected in the Setup view.")
        return

    if target_name is not None:
        self._set_setup_candidate_by_name(target_name)

    target_values = list(_stringify_list_values(self._cfg.get("analyzed_programs_and_libraries")))

    remove_index = next(
        (index for index, existing in enumerate(target_values) if existing.casefold() == selected_name.casefold()),
        None,
    )
    if remove_index is None:
        self._write_output(f"Target '{selected_name}' is not currently configured.")
        return

    updated_targets = list(target_values)
    removed_name = updated_targets.pop(remove_index)
    self._selected_configured_target = None
    self._replace_setup_list_value(
        "analyzed_programs_and_libraries",
        updated_targets,
        message=f"Removed analysis target '{removed_name}' from the Setup view.",
    )


def _add_target_from_path(self: Any, selected_path: Path) -> None:
    if selected_path.is_dir():
        target_dir = selected_path
        stem: str | None = None
    else:
        target_dir = selected_path.parent
        stem = selected_path.stem

    configured_dirs = {d.resolve() for d in _config_directory_paths(self._cfg)}
    if target_dir.resolve() not in configured_dirs:
        other_dirs = list(_stringify_list_values(self._cfg.get("other_lib_dirs")))
        self._cfg["other_lib_dirs"] = [*other_dirs, str(target_dir)]

    if stem is not None:
        target_values = list(_stringify_list_values(self._cfg.get("analyzed_programs_and_libraries")))
        if any(existing.casefold() == stem.casefold() for existing in target_values):
            self._write_output(f"Target '{stem}' is already configured.")
            return
        self._replace_setup_list_value(
            "analyzed_programs_and_libraries",
            [*target_values, stem],
            message=f"Added '{stem}' as analysis target from file browser.",
        )
        return
    else:
        self._mark_setup_changed("Updated directory configuration from file browser.", reset_candidate_selection=True)


def _open_file_browser(self: Any) -> None:
    self._open_raw_file_browser()


def _open_raw_file_browser(self: Any) -> None:
    if _TEXTUAL_DIRECTORY_TREE is None:
        self._prompt_setup_value("other_lib_dirs", label="other_lib_dirs", is_list=True)
        return

    start_paths: list[Path] = []
    seen: set[Path] = set()
    program_dir = _stringify_value(cast(object | None, self._cfg.get("program_dir", ""))).strip()
    if program_dir:
        p = Path(program_dir)
        if p.exists() and p not in seen:
            start_paths.append(p)
            seen.add(p)
    other_lib_dirs = self._cfg.get("other_lib_dirs", [])
    if isinstance(other_lib_dirs, list):
        for d in cast(list[object], other_lib_dirs):
            ds = _stringify_value(d).strip()
            if ds:
                p = Path(ds)
                if p.exists() and p not in seen:
                    start_paths.append(p)
                    seen.add(p)
    if not start_paths:
        start_paths = [Path.home()]

    candidates = tuple(
        (candidate.name, tuple(str(path) for path in _setup_candidate_display_paths(candidate)))
        for candidate in self._setup_candidates()
    )

    def _on_browser_result(result: object) -> None:
        if isinstance(result, str):
            self._add_selected_setup_target(result)
        elif isinstance(result, Path):
            self._add_target_from_path(result)

    self.push_screen(_FileBrowserScreen(start_paths=start_paths, candidates=candidates), _on_browser_result)


def _open_help_popup(self: Any) -> None:
    get_help_text_fn = getattr(self, "_get_help_text_fn", None)
    if not callable(get_help_text_fn):
        self._show_help_modal("No help content available.")
        return

    help_text = str(get_help_text_fn(self._cfg)).strip() or "No help content available."
    help_text = (
        f"{help_text}\n\nKeyboard shortcuts\n"
        "1-5 switch views\n"
        "/ filters Analyze and Setup lists\n"
        "? / Ctrl+H open help\n"
        "Esc goes back to Analyze from other views\n"
        "Ctrl+C copies Session output\n"
        "Ctrl+G cancels a running analysis\n"
        "Ctrl+L clears Session output\n"
        "Tab / Shift+Tab move focus\n"
        "Q quits the shell"
    )
    self._show_help_modal(help_text)


def _show_help_modal(self: Any, help_text: str) -> None:
    self.push_screen(_HelpScreen(help_text=help_text))


def _toggle_setup_flag(self: Any, key: str, *, label: str) -> None:
    self._cfg[key] = not bool(self._cfg.get(key, False))
    self._mark_setup_changed(f"Updated {label} from the Setup view.")


def _toggle_setup_mode(self: Any) -> None:
    current_mode = _stringify_value(cast(object | None, self._cfg.get("mode", "official"))).strip().casefold()
    self._cfg["mode"] = "draft" if current_mode == "official" else "official"
    self._mark_setup_changed("Updated mode from the Setup view.", reset_candidate_selection=True)


def _toggle_setup_telemetry(self: Any) -> None:
    telemetry = self._cfg.get("telemetry")
    if not isinstance(telemetry, dict):
        telemetry = {"enabled": False}
        self._cfg["telemetry"] = telemetry
    telemetry["enabled"] = not bool(cast(object | None, telemetry.get("enabled", False)))
    self._mark_setup_changed("Updated telemetry from the Setup view.")


def _setup_has_targets(self: Any) -> bool:
    return bool(self._configured_target_names())


def _targets_action_allowed(self: Any, action_text: str) -> bool:
    if self._setup_has_targets():
        return True
    self._write_output(f"No configured analysis targets are available for {action_text}.")
    return False


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
        label, lambda action_fn=action_fn: action_fn(self._cfg), action_id=action_id, marks_dirty=marks_dirty
    )


def _run_analyze_checks(self: Any) -> None:
    self._run_app_module_cfg_action(
        "run_checks_menu",
        "Analyzer checks",
        action_id="action-analyze",
        require_targets=True,
        action_text="analysis checks",
    )


def _run_documentation_generate(self: Any) -> None:
    self._run_app_module_cfg_action(
        "run_generate_documentation",
        "Generate DOCX",
        action_id="action-documentation",
        require_targets=True,
        action_text="documentation generation",
    )


def _run_documentation_preview_candidates(self: Any) -> None:
    self._run_app_module_cfg_action(
        "preview_documentation_unit_candidates",
        "Preview candidates",
        action_id="action-documentation",
        require_targets=True,
        action_text="documentation preview",
    )


def _run_documentation_scope_all(self: Any) -> None:
    self._run_app_module_cfg_action(
        "reset_documentation_scope",
        "Use all detected units",
        action_id="action-documentation",
        require_targets=True,
        action_text="documentation scope reset",
        marks_dirty=True,
    )


def _run_documentation_scope_moduletype(self: Any) -> None:
    self._run_app_module_cfg_action(
        "configure_documentation_scope_by_moduletype",
        "Scope by moduletype",
        action_id="action-documentation",
        require_targets=True,
        action_text="documentation moduletype scoping",
        marks_dirty=True,
    )


def _run_documentation_scope_instance_path(self: Any) -> None:
    self._run_app_module_cfg_action(
        "configure_documentation_scope_by_instance_path",
        "Scope by instance path",
        action_id="action-documentation",
        require_targets=True,
        action_text="documentation instance-path scoping",
        marks_dirty=True,
    )


def _run_tool_self_check(self: Any) -> None:
    self._start_action("Self-check diagnostics", lambda: self._self_check_fn(self._cfg), action_id="action-tools")


def _run_tool_dumps(self: Any) -> None:
    if not self._targets_action_allowed("diagnostics and dumps"):
        return
    self._start_action("Diagnostics & dumps", lambda: self._dump_menu_fn(self._cfg), action_id="action-tools")


def _run_tool_source_diff(self: Any) -> None:
    if not self._targets_action_allowed("source diff reports"):
        return
    self._start_action("Source diff report", lambda: self._source_diff_fn(self._cfg), action_id="action-tools")


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
        def _documentation_selection(self) -> dict[str, Any]: ...
        def _documentation_scope_summary_text(self) -> str: ...
        def _active_job_text(self) -> str | None: ...
        def _active_job_elapsed_text(self) -> str | None: ...
        def _output_title_spinner_frame(self) -> str | None: ...
        def _output_title_text(self) -> str: ...
        def _output_retention_note(self) -> str: ...
        def _advance_output_title_spinner(self) -> None: ...
        def _sync_output_title_spinner(self) -> None: ...
        def _analyze_note_text(self) -> str: ...
        def _documentation_note_text(self) -> str: ...
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
        def _show_help_modal(self) -> None: ...
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
        def _run_documentation_generate(self) -> None: ...
        def _run_documentation_preview_candidates(self) -> None: ...
        def _run_documentation_scope_all(self) -> None: ...
        def _run_documentation_scope_moduletype(self) -> None: ...
        def _run_documentation_scope_instance_path(self) -> None: ...
        def _run_tool_self_check(self) -> None: ...
        def _run_tool_dumps(self) -> None: ...
        def _run_tool_source_diff(self) -> None: ...
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
        """Provides Setup view state, inline editing flows, and documentation/tool launch helpers."""

        _setup_candidates = _setup_candidates
        _selected_setup_candidate = _selected_setup_candidate
        _setup_candidate_status = _setup_candidate_status
        _setup_candidate_display_paths = _setup_candidate_display_paths
        _configured_target_names = _configured_target_names
        _setup_filter_value = _setup_filter_value
        _visible_configured_target_names = _visible_configured_target_names
        _summary_text = _summary_text
        _documentation_selection = _documentation_selection
        _documentation_scope_summary_text = _documentation_scope_summary_text
        _active_job_text = _active_job_text
        _active_job_elapsed_text = _active_job_elapsed_text
        _output_title_spinner_frame = _output_title_spinner_frame
        _output_title_text = _output_title_text
        _output_retention_note = _output_retention_note
        _advance_output_title_spinner = _advance_output_title_spinner
        _sync_output_title_spinner = _sync_output_title_spinner
        _analyze_note_text = _analyze_note_text
        _documentation_note_text = _documentation_note_text
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
        _run_documentation_generate = _run_documentation_generate
        _run_documentation_preview_candidates = _run_documentation_preview_candidates
        _run_documentation_scope_all = _run_documentation_scope_all
        _run_documentation_scope_moduletype = _run_documentation_scope_moduletype
        _run_documentation_scope_instance_path = _run_documentation_scope_instance_path
        _run_tool_self_check = _run_tool_self_check
        _run_tool_dumps = _run_tool_dumps
        _run_tool_source_diff = _run_tool_source_diff
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
