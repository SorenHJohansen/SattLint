# pyright: reportMissingImports=false, reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportUnknownLambdaType=false, reportGeneralTypeIssues=false, reportInvalidTypeForm=false, reportConstantRedefinition=false, reportPrivateUsage=false, reportUnusedClass=false, reportUnusedFunction=false, reportUnknownArgumentType=false

from __future__ import annotations

from typing import Any, cast

from . import _app_analysis_catalog as analysis_catalog
from . import _app_analysis_planner as analysis_planner
from ._app_textual_shared import (
    _ANALYZE_PLANNER_LIST_ID_PREFIX,
    _TEXTUAL_SELECTION_LIST,
    _TEXTUAL_STATIC,
    _TEXTUAL_VERTICAL,
    _stringify_value,
)


def on_selection_list_selection_toggled(self: Any, event: Any) -> None:
    if self._suppress_analyze_planner_events:
        return
    selection_list = getattr(event, "selection_list", None)
    if selection_list is None:
        return
    if not self._sync_analyze_selection_from_selection_list(selection_list):
        return
    highlighted_entry_id = self._selection_list_highlighted_entry_id(selection_list)
    if highlighted_entry_id is not None:
        self._analyze_focused_entry_id = highlighted_entry_id
    self._refresh_analyze_planner_summary_widgets()
    self._refresh_shell_state()


def on_selection_list_selection_highlighted(self: Any, event: Any) -> None:
    if self._suppress_analyze_planner_events:
        return
    selection_list = getattr(event, "selection_list", None)
    if selection_list is None:
        return
    if not bool(getattr(selection_list, "has_focus", False)):
        return
    highlighted_entry_id = self._selection_list_highlighted_entry_id(selection_list)
    if highlighted_entry_id is None or highlighted_entry_id == self._analyze_focused_entry_id:
        return
    self._analyze_focused_entry_id = highlighted_entry_id
    self._refresh_analyze_planner_summary_widgets()
    self._refresh_shell_state()


def _available_analyzer_specs(self: Any) -> tuple[Any, ...]:
    app_module = self._app_module
    get_analyzers_fn = getattr(app_module, "_get_enabled_analyzers", None) if app_module is not None else None
    if not callable(get_analyzers_fn):
        return ()
    analyzers_obj = get_analyzers_fn()
    if isinstance(analyzers_obj, list):
        return cast(tuple[Any, ...], tuple(cast(list[object], analyzers_obj)))
    if isinstance(analyzers_obj, tuple):
        return cast(tuple[Any, ...], analyzers_obj)
    return ()


def _planner_section_groups(
    self: Any,
) -> tuple[tuple[analysis_catalog.AnalysisSectionSpec, tuple[analysis_catalog.AnalysisCatalogEntry, ...]], ...]:
    analyzer_specs = self._available_analyzer_specs()
    groups: list[tuple[analysis_catalog.AnalysisSectionSpec, tuple[analysis_catalog.AnalysisCatalogEntry, ...]]] = []
    for section in analysis_catalog.analysis_section_specs():
        if section.section_id == analysis_catalog.SECTION_CATALOG_SUITE:
            continue
        entries = analysis_catalog.analysis_entries_for_section(
            section.section_id,
            analyzer_specs=analyzer_specs,
        )
        if not entries:
            continue
        groups.append((section, entries))
    return tuple(groups)


def _planner_entry_ids(self: Any) -> tuple[str, ...]:
    return tuple(entry.entry_id for _section, entries in self._planner_section_groups() for entry in entries)


def _planner_entry(self: Any, entry_id: str | None) -> analysis_catalog.AnalysisCatalogEntry | None:
    if entry_id is None:
        return None
    return analysis_catalog.analysis_catalog_entry(
        entry_id,
        analyzer_specs=self._available_analyzer_specs(),
    )


def _normalize_analyze_planner_state(self: Any) -> None:
    valid_entry_ids = self._planner_entry_ids()
    valid_entry_id_set = set(valid_entry_ids)
    self._analyze_selected_entry_ids.intersection_update(valid_entry_id_set)
    if self._analyze_focused_entry_id not in valid_entry_id_set:
        self._analyze_focused_entry_id = valid_entry_ids[0] if valid_entry_ids else None


def _ordered_selected_analyze_entry_ids(self: Any) -> tuple[str, ...]:
    self._normalize_analyze_planner_state()
    return tuple(entry_id for entry_id in self._planner_entry_ids() if entry_id in self._analyze_selected_entry_ids)


def _analyze_plan(self: Any) -> analysis_planner.AnalysisPlan:
    return analysis_planner.plan_analysis_entries(
        self._ordered_selected_analyze_entry_ids(),
        analyzer_specs=self._available_analyzer_specs(),
        available_handler_names=analysis_planner.available_handler_names(self._app_module),
    )


def _analyze_section_list_id(self: Any, section_id: str) -> str:
    return f"{_ANALYZE_PLANNER_LIST_ID_PREFIX}{section_id}"


def _analyze_section_id_from_list(self: Any, selection_list: Any) -> str | None:
    widget_id = str(getattr(selection_list, "id", "") or "")
    if not widget_id.startswith(_ANALYZE_PLANNER_LIST_ID_PREFIX):
        return None
    return widget_id[len(_ANALYZE_PLANNER_LIST_ID_PREFIX) :]


def _selection_list_highlighted_entry_id(self: Any, selection_list: Any) -> str | None:
    section_id = self._analyze_section_id_from_list(selection_list)
    if section_id is None:
        return None
    highlighted_index = getattr(selection_list, "highlighted", None)
    if not isinstance(highlighted_index, int) or highlighted_index < 0:
        return None
    try:
        option = selection_list.get_option_at_index(highlighted_index)
    except Exception:
        return None
    value = _stringify_value(cast(object | None, getattr(option, "value", None))).strip()
    entry = self._planner_entry(value)
    return entry.entry_id if entry is not None else None


def _sync_analyze_selection_from_selection_list(self: Any, selection_list: Any) -> bool:
    section_id = self._analyze_section_id_from_list(selection_list)
    if section_id is None:
        return False
    section_entry_ids = {
        entry.entry_id
        for entry in analysis_catalog.analysis_entries_for_section(
            section_id,
            analyzer_specs=self._available_analyzer_specs(),
        )
    }
    selected_ids = {
        _stringify_value(cast(object | None, value)).strip()
        for value in cast(list[object], getattr(selection_list, "selected", []))
    }
    selected_ids.discard("")
    self._analyze_selected_entry_ids.difference_update(section_entry_ids)
    self._analyze_selected_entry_ids.update(selected_ids)
    return True


def _update_analyze_planner_selection_list(
    self: Any,
    selection_list: Any,
    entries: tuple[analysis_catalog.AnalysisCatalogEntry, ...],
) -> None:
    selection_list.clear_options()
    selection_list.add_options(
        [(entry.label, entry.entry_id, entry.entry_id in self._analyze_selected_entry_ids) for entry in entries]
    )
    if entries:
        highlighted_index = 0
        if self._analyze_focused_entry_id is not None:
            for index, entry in enumerate(entries):
                if entry.entry_id == self._analyze_focused_entry_id:
                    highlighted_index = index
                    break
        selection_list.highlighted = highlighted_index


def _refresh_analyze_planner(self: Any) -> None:
    try:
        container = self.query_one("#analyze-browser-left", _TEXTUAL_VERTICAL)
    except Exception:
        return

    self._suppress_analyze_planner_events = True
    try:
        self._normalize_analyze_planner_state()
        section_groups = self._planner_section_groups()
        if not section_groups:
            if not list(getattr(container, "children", [])):
                container.mount(
                    _TEXTUAL_STATIC(
                        "No analysis planner entries are available in the current Textual session.",
                        classes="browser-empty-state",
                    )
                )
            return

        expected_list_ids = tuple(
            self._analyze_section_list_id(section.section_id) for section, _entries in section_groups
        )
        children = tuple(cast(tuple[Any, ...], getattr(container, "children", ())))
        current_list_ids: list[str] = []
        for child_widget in children:
            child_id = getattr(child_widget, "id", None)
            if child_id is None:
                continue
            child_id_str = str(child_id)
            if child_id_str.startswith(_ANALYZE_PLANNER_LIST_ID_PREFIX):
                current_list_ids.append(child_id_str)
        if tuple(current_list_ids) == expected_list_ids and children:
            for section, entries in section_groups:
                selection_list = self.query_one(
                    f"#{self._analyze_section_list_id(section.section_id)}",
                    _TEXTUAL_SELECTION_LIST,
                )
                self._update_analyze_planner_selection_list(selection_list, entries)
            return

        for child in list(getattr(container, "children", [])):
            child.remove()

        for section, entries in section_groups:
            container.mount(_TEXTUAL_STATIC(section.label, classes="browser-section-title"))
            if section.description:
                container.mount(_TEXTUAL_STATIC(section.description, classes="planner-section-note"))
            selection_list = _TEXTUAL_SELECTION_LIST(
                *[
                    (entry.label, entry.entry_id, entry.entry_id in self._analyze_selected_entry_ids)
                    for entry in entries
                ],
                id=self._analyze_section_list_id(section.section_id),
                classes="analyze-planner-list",
            )
            if entries:
                highlighted_index = 0
                if self._analyze_focused_entry_id is not None:
                    for index, entry in enumerate(entries):
                        if entry.entry_id == self._analyze_focused_entry_id:
                            highlighted_index = index
                            break
                selection_list.highlighted = highlighted_index
            container.mount(selection_list)
    finally:
        self._suppress_analyze_planner_events = False


def _entry_family_label(self: Any, entry: analysis_catalog.AnalysisCatalogEntry) -> str:
    return analysis_catalog.top_level_analysis_family(entry.family_id).label


def _entry_section_label(self: Any, entry: analysis_catalog.AnalysisCatalogEntry) -> str:
    for section in analysis_catalog.analysis_section_specs():
        if section.section_id == entry.section_id:
            return section.label
    return entry.section_id


def _entry_issue_kind_summary(self: Any, entry: analysis_catalog.AnalysisCatalogEntry) -> str | None:
    issue_kinds = entry.execution.variable_issue_kinds
    if not issue_kinds:
        return None
    return ", ".join(kind.name.casefold().replace("_", " ") for kind in sorted(issue_kinds, key=lambda item: item.name))


def _refresh_analyze_planner_summary_widgets(self: Any) -> None:
    try:
        self.query_one("#view-note", _TEXTUAL_STATIC).update(self._analyze_note_text())
        self.query_one("#analyze-browser-right", _TEXTUAL_STATIC).update(self._analyze_browser_detail_text())
    except Exception:
        return


def _analyze_browser_detail_text(self: Any) -> str:
    self._normalize_analyze_planner_state()
    focused_entry = self._planner_entry(self._analyze_focused_entry_id)
    plan = self._analyze_plan()
    if self._busy and self._active_job_action_id == "action-analyze":
        status_text = "Status: Running selected analyses. Live output is shown in Session output below."
    elif not self._setup_has_targets():
        status_text = "Status: Configure a target in Setup to enable the planner runner."
    elif not self._ordered_selected_analyze_entry_ids():
        status_text = "Status: Select one or more analyses to build a queue."
    elif plan.missing_handlers:
        status_text = "Status: Queue blocked by unavailable handlers in the current Textual session."
    else:
        status_text = "Status: Ready to run."
    lines = [
        "Analyze planner",
        status_text,
        f"Selected entries: {len(self._ordered_selected_analyze_entry_ids())}",
        f"Runnable steps: {len(plan.executable_steps)}",
    ]
    if focused_entry is not None:
        lines.extend(
            [
                "",
                f"Focused entry: {focused_entry.label}",
                f"Family: {self._entry_family_label(focused_entry)}",
                f"Section: {self._entry_section_label(focused_entry)}",
                f"Description: {focused_entry.description}",
                f"Action: {focused_entry.execution.action_text}",
            ]
        )
        if focused_entry.execution.selected_analyzer_keys:
            lines.append("Analyzer keys: " + ", ".join(focused_entry.execution.selected_analyzer_keys))
        issue_kind_summary = self._entry_issue_kind_summary(focused_entry)
        if issue_kind_summary:
            lines.append(f"Issue kinds: {issue_kind_summary}")
    lines.extend(["", "Queue summary", analysis_planner.render_analysis_plan_summary(plan)])
    return "\n".join(lines)


def _execute_planned_analysis_step(self: Any, step: analysis_planner.PlannedAnalysisStep) -> None:
    if step.execution.require_targets and not self._configured_target_names():
        raise RuntimeError(f"No configured analysis targets are available for {step.execution.action_text}.")
    app_module = self._app_module
    if app_module is None:
        raise RuntimeError("Analysis actions are unavailable in the current Textual session.")

    action_fn = getattr(app_module, step.execution.handler_name, None)
    if not callable(action_fn):
        raise RuntimeError(f"{step.label} is unavailable in the current Textual session.")

    if step.execution.kind == "run_checks":
        selected_keys = (
            None if step.execution.selected_analyzer_keys is None else list(step.execution.selected_analyzer_keys)
        )
        action_fn(self._cfg, selected_keys)
        return
    if step.execution.kind == "run_variable_analysis":
        issue_kinds = None if step.execution.variable_issue_kinds is None else set(step.execution.variable_issue_kinds)
        action_fn(self._cfg, issue_kinds)
        return
    action_fn(self._cfg)


def _execute_analyze_plan(self: Any, plan: analysis_planner.AnalysisPlan) -> None:
    self._emit_output_from_thread("Analyze planner queue")
    self._emit_output_from_thread(analysis_planner.render_analysis_plan_summary(plan))
    total_steps = len(plan.executable_steps)
    for index, step in enumerate(plan.executable_steps, start=1):
        self._emit_output_from_thread(f"[{index}/{total_steps}] {step.label}")
        if len(step.source_labels) > 1:
            self._emit_output_from_thread("Merged selections: " + ", ".join(step.source_labels))
        self._execute_planned_analysis_step(step)
    self._emit_output_from_thread("Selected analyses completed.")


def _run_selected_analysis_plan(self: Any) -> None:
    if not self._targets_action_allowed("analysis planning"):
        return
    if not self._ordered_selected_analyze_entry_ids():
        self._write_output("Select one or more analyses in the planner first.")
        return
    plan = self._analyze_plan()
    if not plan.is_runnable:
        self._write_output(analysis_planner.render_analysis_plan_summary(plan))
        return
    self._start_action(
        "Run selected analyses",
        lambda plan=plan: self._execute_analyze_plan(plan),
        action_id="action-analyze",
    )


def _clear_selected_analysis_plan(self: Any) -> None:
    if not self._analyze_selected_entry_ids:
        return
    self._analyze_selected_entry_ids.clear()
    self._refresh_view()
    self._refresh_shell_state()
    self._write_output("Cleared the analyze planner selection.")


ANALYZE_METHODS = (
    on_selection_list_selection_toggled,
    on_selection_list_selection_highlighted,
    _available_analyzer_specs,
    _planner_section_groups,
    _planner_entry_ids,
    _planner_entry,
    _normalize_analyze_planner_state,
    _ordered_selected_analyze_entry_ids,
    _analyze_plan,
    _analyze_section_list_id,
    _analyze_section_id_from_list,
    _selection_list_highlighted_entry_id,
    _sync_analyze_selection_from_selection_list,
    _update_analyze_planner_selection_list,
    _refresh_analyze_planner,
    _entry_family_label,
    _entry_section_label,
    _entry_issue_kind_summary,
    _refresh_analyze_planner_summary_widgets,
    _analyze_browser_detail_text,
    _execute_planned_analysis_step,
    _execute_analyze_plan,
    _run_selected_analysis_plan,
    _clear_selected_analysis_plan,
)
