from __future__ import annotations

from contextlib import suppress
from pathlib import Path
from typing import Any, cast

from ._app_textual_setup_display import (
    _configured_target_names,
    _setup_candidate_display_paths,
    _setup_filter_value,
    _setup_mode_text,
    _setup_other_dirs_text,
    _setup_path_text,
    _setup_toggle_text,
    _visible_configured_target_names,
)
from ._app_textual_shared import (
    _TEXTUAL_BUTTON,
    _TEXTUAL_DIRECTORY_TREE,
    _TEXTUAL_LIST_ITEM,
    _TEXTUAL_LIST_VIEW,
    _TEXTUAL_QUERY_ERRORS,
    _TEXTUAL_STATIC,
    _config_directory_paths,
    _stringify_list_values,
    _stringify_value,
)
from ._app_textual_widgets import _FileBrowserScreen, _HelpScreen


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
    filter_text = _setup_filter_value(self)
    visible_targets = _visible_configured_target_names(self)
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

    configured_targets = list(_visible_configured_target_names(self))
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
            _configured_target_names(self)
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
    return bool(_configured_target_names(self))


def _targets_action_allowed(self: Any, action_text: str) -> bool:
    if self._setup_has_targets():
        return True
    self._write_output(f"No configured analysis targets are available for {action_text}.")
    return False
