# pyright: reportMissingImports=false, reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportUnknownLambdaType=false, reportGeneralTypeIssues=false, reportInvalidTypeForm=false, reportConstantRedefinition=false, reportPrivateUsage=false, reportUnusedClass=false, reportUnusedFunction=false, reportUnknownArgumentType=false

from __future__ import annotations

import io
import re
import sys
import threading
from contextlib import redirect_stderr, redirect_stdout, suppress
from pathlib import Path
from typing import Any, cast

from ._app_textual_shared import (
    _TEXTUAL_BUTTON,
    _TEXTUAL_DIRECTORY_TREE,
    _TEXTUAL_LIST_ITEM,
    _TEXTUAL_LIST_VIEW,
    _TEXTUAL_STATIC,
    InteractionRequest,
    _config_directory_paths,
    _SetupTargetCandidate,
    _stringify_list_values,
    _stringify_value,
    _TextualOutput,
    discover_setup_target_candidates,
)
from ._app_textual_widgets import _FileBrowserScreen, _HelpScreen


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


def _configured_target_names(self: Any) -> tuple[str, ...]:
    return _stringify_list_values(self._cfg.get("analyzed_programs_and_libraries", []))


def _summary_text(self: Any) -> str:
    configured_targets = self._configured_target_names()
    if not configured_targets:
        return str(self._summarize_targets_fn(self._cfg))

    target_count = len(configured_targets)
    target_label = "target" if target_count == 1 else "targets"
    target_names = ", ".join(configured_targets)
    return f"{target_count} {target_label} configured\n{target_names}"


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


def _output_title_text(self: Any) -> str:
    active_job_text = self._active_job_text()
    if active_job_text is None:
        return "Session output"
    return f"Session output - {active_job_text} in progress"


def _analyze_note_text(self: Any) -> str:
    if self._busy and self._active_job_action_id == "action-analyze":
        return "Selected analyses are running. Live output is shown in Session output below."
    if not self._setup_has_targets():
        return "No analysis targets are configured yet. Add one in Setup to enable the planner queue runner."
    plan = self._analyze_plan()
    if not self._ordered_selected_analyze_entry_ids():
        return "Select one or more analyses below. Suites collapse overlapping leaf checks when the queue is planned."
    if plan.missing_handlers:
        return "Some selected analyses are unavailable in the current Textual session. Review the queue summary before running anything."
    return (
        f"{len(plan.executable_steps)} queued step(s) are ready to run. "
        "Use Run selected analyses to execute the normalized plan in catalog order."
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


def _setup_note_text(self: Any) -> str:
    return (
        "Click a target in the list to select it, then use Remove to delete it. "
        "Use Add from file to add a new target. Settings on the right update immediately."
    )


def _refresh_setup_target_list(self: Any) -> None:
    try:
        lv = self.query_one("#setup-target-listview", _TEXTUAL_LIST_VIEW)
    except Exception:
        return

    configured_targets = list(self._configured_target_names())
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
    with suppress(Exception):
        self.query_one("#setup-target-remove", _TEXTUAL_BUTTON).disabled = not has_selection


def _refresh_setup_settings_labels(self: Any) -> None:
    program_dir = _stringify_value(cast(object | None, self._cfg.get("program_dir", "")))
    abb_dir = _stringify_value(cast(object | None, self._cfg.get("ABB_lib_dir", "")))
    other_dirs = self._cfg.get("other_lib_dirs", [])
    other_dirs_str = (
        ", ".join(_stringify_value(d) for d in cast(list[object], other_dirs))
        if isinstance(other_dirs, list)
        else _stringify_value(cast(object | None, other_dirs))
    )
    icf_dir = _stringify_value(cast(object | None, self._cfg.get("icf_dir", "")))
    mode = _stringify_value(cast(object | None, self._cfg.get("mode", "official"))) or "official"
    scan_root_only = "on" if bool(self._cfg.get("scan_root_only", False)) else "off"
    fast_cache = "on" if bool(self._cfg.get("fast_cache_validation", False)) else "off"
    debug = "on" if bool(self._cfg.get("debug", False)) else "off"
    telemetry = self._cfg.get("telemetry")
    telemetry_enabled = (
        bool(cast(object | None, telemetry.get("enabled", False))) if isinstance(telemetry, dict) else False
    )
    telemetry_str = "on" if telemetry_enabled else "off"

    def _safe_update(widget_id: str, text: str) -> None:
        with suppress(Exception):
            self.query_one(f"#{widget_id}", _TEXTUAL_STATIC).update(text)

    _safe_update("setup-label-program-dir", program_dir or "(not set)")
    _safe_update("setup-label-abb-dir", abb_dir or "(not set)")
    _safe_update("setup-label-other-dirs", other_dirs_str or "(none)")
    _safe_update("setup-label-icf-dir", icf_dir or "(not set)")
    _safe_update("setup-label-mode", mode)
    _safe_update("setup-label-scan-root-only", scan_root_only)
    _safe_update("setup-label-fast-cache", fast_cache)
    _safe_update("setup-label-debug", debug)
    _safe_update("setup-label-telemetry", telemetry_str)


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
    with suppress(Exception):
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
        f"fast_cache_validation: {bool(self._cfg.get('fast_cache_validation', False))}",
    ]
    if candidate is None:
        lines.append("Target: none")
    else:
        lines.append(f"Target: {candidate.name}")
        lines.append(f"Status: {self._setup_candidate_status(candidate)}")
        lines.append("Files:")
        lines.extend(f"- {path}" for path in candidate.files)

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

    targets = self._cfg.setdefault("analyzed_programs_and_libraries", [])
    if not isinstance(targets, list):
        self._write_output("Configured targets are not editable in the current config state.")
        return
    target_values = cast(list[object], targets)
    if any(_stringify_value(existing).casefold() == candidate.name.casefold() for existing in target_values):
        self._write_output(f"Target '{candidate.name}' is already configured.")
        return
    if not candidate.available:
        self._write_output(
            f"Target '{candidate.name}' is not available for the current mode '{self._cfg.get('mode', 'official')}'."
        )
        return

    target_values.append(candidate.name)
    self._mark_setup_changed(f"Added analysis target '{candidate.name}' from the Setup view.")


def _remove_selected_setup_target(self: Any, target_name: str | None = None) -> None:
    candidate = self._selected_setup_candidate()
    selected_name = target_name or (candidate.name if candidate is not None else None)
    if selected_name is None:
        self._write_output("No discovered target is selected in the Setup view.")
        return

    if target_name is not None:
        self._set_setup_candidate_by_name(target_name)

    targets = self._cfg.get("analyzed_programs_and_libraries", [])
    if not isinstance(targets, list):
        self._write_output("Configured targets are not editable in the current config state.")
        return
    target_values = cast(list[object], targets)

    remove_index = next(
        (
            index
            for index, existing in enumerate(target_values)
            if _stringify_value(existing).casefold() == selected_name.casefold()
        ),
        None,
    )
    if remove_index is None:
        self._write_output(f"Target '{selected_name}' is not currently configured.")
        return

    removed_name = _stringify_value(target_values.pop(remove_index))
    self._selected_configured_target = None
    self._mark_setup_changed(f"Removed analysis target '{removed_name}' from the Setup view.")


def _add_target_from_path(self: Any, selected_path: Path) -> None:
    if selected_path.is_dir():
        target_dir = selected_path
        stem: str | None = None
    else:
        target_dir = selected_path.parent
        stem = selected_path.stem

    configured_dirs = {d.resolve() for d in _config_directory_paths(self._cfg)}
    if target_dir.resolve() not in configured_dirs:
        other_dirs = self._cfg.get("other_lib_dirs", [])
        if not isinstance(other_dirs, list):
            other_dirs = []
        other_dirs.append(str(target_dir))
        self._cfg["other_lib_dirs"] = other_dirs

    if stem is not None:
        targets = self._cfg.setdefault("analyzed_programs_and_libraries", [])
        if isinstance(targets, list):
            target_values = cast(list[object], targets)
            if any(_stringify_value(t).casefold() == stem.casefold() for t in target_values):
                self._write_output(f"Target '{stem}' is already configured.")
                return
            target_values.append(stem)
            self._mark_setup_changed(f"Added '{stem}' as analysis target from file browser.")
            return
        self._write_output("Configured targets are not editable in the current config state.")
    else:
        self._mark_setup_changed("Updated directory configuration from file browser.", reset_candidate_selection=True)


def _open_file_browser(self: Any) -> None:
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

    def _on_browser_result(result: object) -> None:
        if isinstance(result, Path):
            self._add_target_from_path(result)

    self.push_screen(_FileBrowserScreen(start_paths=start_paths), _on_browser_result)


def _open_help_popup(self: Any) -> None:
    def _run() -> None:
        lines: list[str] = []

        def _append_help_text(text: object) -> None:
            lines.append(str(text))

        output_stream = _TextualOutput(emit_text_fn=_append_help_text)
        _fake_stdin = io.StringIO("")
        _saved_stdin = sys.stdin
        sys.stdin = _fake_stdin
        try:
            with redirect_stdout(output_stream), redirect_stderr(output_stream):
                self._show_help_fn(self._cfg)
        except Exception as exc:
            lines.append(f"Error generating help: {exc}")
        finally:
            sys.stdin = _saved_stdin
            raw = "".join(lines)
            help_text = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", raw).strip()
            help_text = help_text or "No help content available."
            self.call_from_thread(self._show_help_modal, help_text)

    threading.Thread(target=_run, daemon=True).start()


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
    if not self._targets_action_allowed("cached AST refresh"):
        return
    self._start_action("Refresh cached ASTs", lambda: self._force_refresh_ast_fn(self._cfg), action_id="action-tools")


def _prompt_setup_value(self: Any, field_key: str, *, label: str, is_list: bool = False) -> None:
    if self._active_request is not None:
        return

    current_value = self._cfg.get(field_key)
    current_items = cast(list[object], current_value) if isinstance(current_value, list) else []
    default_text = (
        ", ".join(_stringify_value(item) for item in current_items)
        if is_list
        else _stringify_value(cast(object | None, current_value))
    )
    message = (
        f"Enter comma-separated paths for {label}. Leave blank to clear the list."
        if is_list
        else f"Enter a new path for {label}."
    )
    request = InteractionRequest(kind="prompt", message=message, default=default_text)

    def _apply_response(response: object) -> None:
        raw_value = str(response or "").strip()
        new_value: list[str] | str = (
            [part.strip() for part in raw_value.split(",") if part.strip()] if is_list else raw_value
        )
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


def _activate_view(self: Any, view_name: str) -> None:
    if self._active_view == "setup" and view_name != "setup" and self._dirty:
        self._start_action(
            "Save configuration",
            lambda: self._save_config_fn(self._config_path, self._cfg),
            action_id="action-setup",
            clear_dirty_on_success=True,
        )
    self._active_view = view_name
    self._refresh_view()
    self._set_active_action(None)
    self._refresh_shell_state()


SETUP_METHODS = (
    _setup_candidates,
    _selected_setup_candidate,
    _setup_candidate_status,
    _configured_target_names,
    _summary_text,
    _documentation_selection,
    _documentation_scope_summary_text,
    _active_job_text,
    _output_title_text,
    _analyze_note_text,
    _documentation_note_text,
    _is_target_configured,
    _set_setup_candidate_by_name,
    _mark_setup_changed,
    _setup_note_text,
    _refresh_setup_target_list,
    _refresh_setup_settings_labels,
    on_list_view_highlighted,
    _setup_browser_detail_text,
    _add_selected_setup_target,
    _remove_selected_setup_target,
    _add_target_from_path,
    _open_file_browser,
    _open_help_popup,
    _show_help_modal,
    _toggle_setup_flag,
    _toggle_setup_mode,
    _toggle_setup_telemetry,
    _setup_has_targets,
    _targets_action_allowed,
    _run_app_module_cfg_action,
    _run_analyze_checks,
    _run_documentation_generate,
    _run_documentation_preview_candidates,
    _run_documentation_scope_all,
    _run_documentation_scope_moduletype,
    _run_documentation_scope_instance_path,
    _run_tool_self_check,
    _run_tool_dumps,
    _run_tool_source_diff,
    _run_tool_refresh_ast,
    _prompt_setup_value,
    _activate_view,
)
