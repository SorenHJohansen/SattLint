# pyright: reportMissingImports=false, reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportUnknownLambdaType=false, reportGeneralTypeIssues=false, reportInvalidTypeForm=false, reportConstantRedefinition=false, reportPrivateUsage=false, reportUnusedClass=false, reportUnusedFunction=false, reportUnknownArgumentType=false

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

try:
    from rich import box as _rich_box  # type: ignore[import-untyped]
    from rich.panel import Panel as _RichPanel  # type: ignore[import-untyped]
    from rich.table import Table as _RichTable  # type: ignore[import-untyped]
    from rich.text import Text as _RichText  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover - optional dependency path
    _rich_box = None
    _RichPanel = None
    _RichTable = None
    _RichText = None

from . import _app_analysis_catalog as analysis_catalog
from . import _app_analysis_catalog_metadata as analysis_catalog_metadata
from . import _app_analysis_planner as analysis_planner
from ._app_textual_shared import (
    _ANALYZE_PLANNER_LIST_ID_PREFIX,
    _TEXTUAL_OPTION_LIST_ERRORS,
    _TEXTUAL_SELECTION_LIST,
    _TEXTUAL_STATIC,
    _TEXTUAL_VERTICAL,
    InteractionRequest,
    _query_required,
    _stringify_value,
)

_DETAIL_HEADING_STYLE = "bold #16323b"
_DETAIL_LABEL_STYLE = "bold #24505f"
_DETAIL_VALUE_STYLE = "#001ba3"
_DETAIL_MUTED_STYLE = "#58787e"
_DETAIL_SUCCESS_STYLE = "bold #236d36"
_DETAIL_WARNING_STYLE = "bold #8a5a00"
_DETAIL_DANGER_STYLE = "bold #8a3b12"
_DETAIL_PANEL_BORDER = "#8fb6bf"
_DETAIL_PANEL_ACCENT = "#0077b3"


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


def _analyze_filter_value(self: Any) -> str:
    return str(getattr(self, "_analyze_filter_text", "") or "").strip()


def _planner_entry_matches_filter(self: Any, entry: analysis_catalog.AnalysisCatalogEntry) -> bool:
    filter_text = self._analyze_filter_value().casefold()
    if not filter_text:
        return True
    search_text = " ".join((entry.entry_id, entry.label, entry.description)).casefold()
    return filter_text in search_text


def _planner_base_entries_for_section(
    self: Any,
    section_id: str,
) -> tuple[analysis_catalog.AnalysisCatalogEntry, ...]:
    analyzer_specs = self._available_analyzer_specs()
    removed_entry_ids = {
        analysis_catalog.ENTRY_ANALYZE_FULL_SUITE,
        analysis_catalog.ENTRY_VARIABLE_HIGH_CONFIDENCE_SUITE,
    }
    planner_hidden_analyzer_keys = {"comment-code", "mms-interface", "shadowing", "variables"}
    return tuple(
        entry
        for entry in analysis_catalog.analysis_entries_for_section(
            section_id,
            analyzer_specs=analyzer_specs,
        )
        if entry.entry_id not in removed_entry_ids
        and not (
            section_id == analysis_catalog.SECTION_CATALOG_ANALYZERS
            and entry.execution.selected_analyzer_keys is not None
            and any(key in planner_hidden_analyzer_keys for key in entry.execution.selected_analyzer_keys)
        )
    )


def _planner_entries_for_section(
    self: Any,
    section_id: str,
) -> tuple[analysis_catalog.AnalysisCatalogEntry, ...]:
    return tuple(
        entry
        for entry in self._planner_base_entries_for_section(section_id)
        if self._planner_entry_matches_filter(entry)
    )


def _planner_section_groups(
    self: Any,
) -> tuple[tuple[analysis_catalog.AnalysisSectionSpec, tuple[analysis_catalog.AnalysisCatalogEntry, ...]], ...]:
    groups: list[tuple[analysis_catalog.AnalysisSectionSpec, tuple[analysis_catalog.AnalysisCatalogEntry, ...]]] = []
    filter_active = bool(self._analyze_filter_value())
    for section in analysis_catalog.analysis_section_specs():
        if section.section_id in {
            analysis_catalog.SECTION_CATALOG_SUITE,
        }:
            continue
        base_entries = self._planner_base_entries_for_section(section.section_id)
        if not base_entries:
            continue
        entries = self._planner_entries_for_section(section.section_id)
        if not entries and not filter_active:
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
    except _TEXTUAL_OPTION_LIST_ERRORS:
        return None
    value = _stringify_value(cast(object | None, getattr(option, "value", None))).strip()
    entry = self._planner_entry(value)
    return entry.entry_id if entry is not None else None


def _sync_analyze_selection_from_selection_list(self: Any, selection_list: Any) -> bool:
    section_id = self._analyze_section_id_from_list(selection_list)
    if section_id is None:
        return False
    section_entry_ids = {entry.entry_id for entry in self._planner_entries_for_section(section_id)}
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
    container = _query_required(self, "#analyze-browser-left", _TEXTUAL_VERTICAL)

    self._suppress_analyze_planner_events = True
    try:
        self._normalize_analyze_planner_state()
        section_groups = self._planner_section_groups()
        if not section_groups:
            for child in list(getattr(container, "children", [])):
                child.remove()
            empty_text = (
                f'No analyses match "{self._analyze_filter_value()}".'
                if self._analyze_filter_value()
                else "No analysis planner entries are available in the current Textual session."
            )
            container.mount(_TEXTUAL_STATIC(empty_text, classes="browser-empty-state"))
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
                selection_list = _query_required(
                    self,
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


def _planner_entry_description(self: Any, entry: analysis_catalog.AnalysisCatalogEntry | None) -> str:
    if entry is None:
        return "Select an analysis on the left to see what the report covers."

    description = entry.description.strip()
    return description or "No description available."


def _planner_entry_analyzer_key(
    self: Any,
    entry: analysis_catalog.AnalysisCatalogEntry | None,
) -> str | None:
    if entry is None or entry.execution.selected_analyzer_keys is None:
        return None
    if len(entry.execution.selected_analyzer_keys) != 1:
        return None
    return entry.execution.selected_analyzer_keys[0]


def _planner_entry_detection(self: Any, entry: analysis_catalog.AnalysisCatalogEntry | None) -> str:
    if entry is None:
        return "Select an analysis on the left to see what it detects."
    return analysis_catalog_metadata.planner_entry_detection(
        entry.entry_id,
        self._planner_entry_analyzer_key(entry),
        entry.description.strip(),
    )


def _planner_entry_how(self: Any, entry: analysis_catalog.AnalysisCatalogEntry | None) -> str:
    if entry is None:
        return "Select an analysis on the left to see how it works."
    return analysis_catalog_metadata.planner_entry_how(
        entry.entry_id,
        self._planner_entry_analyzer_key(entry),
        entry.description.strip(),
    )


def _refresh_analyze_planner_summary_widgets(self: Any) -> None:
    _query_required(self, "#view-note", _TEXTUAL_STATIC).update("")
    _query_required(self, "#analyze-planner-detail", _TEXTUAL_STATIC).update(self._analyze_browser_detail_renderable())


def _analyze_browser_detail_text(self: Any) -> str:
    self._normalize_analyze_planner_state()
    focused_entry = self._planner_entry(self._analyze_focused_entry_id)
    plan = self._analyze_plan()
    selected_entry_count = len(self._ordered_selected_analyze_entry_ids())
    if self._busy and self._active_job_action_id == "action-analyze":
        if self._active_job_cancel_requested:
            status_text = "Status: Stop requested. Interrupting the running analysis now."
        else:
            status_text = "Status: Running selected analyses. Live output is shown in Session output below. Use Cancel running or Ctrl+G to stop."
    elif not self._setup_has_targets():
        status_text = "Status: Configure a target in Setup to enable the planner runner."
    elif not selected_entry_count:
        status_text = "Status: Select one or more analyses to build a queue."
    elif plan.missing_handlers:
        status_text = "Status: Queue blocked by unavailable handlers in the current Textual session."
    else:
        status_text = "Status: Ready to run."
    lines = [
        status_text,
        f"Selected entries: {selected_entry_count}",
        "Focused entry: " + (focused_entry.label if focused_entry is not None else "None"),
        f"Description: {self._planner_entry_description(focused_entry)}",
        f"Detection: {self._planner_entry_detection(focused_entry)}",
        f"How: {self._planner_entry_how(focused_entry)}",
    ]
    return "\n".join(lines)


def _detail_panel_title(rich_text_cls: Any, title: str) -> Any:
    panel_title = rich_text_cls(title)
    panel_title.stylize(_DETAIL_HEADING_STYLE)
    return panel_title


def _detail_row_text(rich_text_cls: Any, value: str, *, style: str = _DETAIL_VALUE_STYLE) -> Any:
    table_text = rich_text_cls(value)
    table_text.stylize(style)
    return table_text


def _build_detail_analysis_panel(
    *,
    rich_text_cls: Any,
    rich_panel_cls: Any,
    rich_table_cls: Any,
    rich_box: Any,
    description_line: str,
    detection_line: str,
    how_line: str,
    focused_entry: analysis_catalog.AnalysisCatalogEntry | None,
) -> Any:
    analysis_body = rich_table_cls.grid(expand=True, padding=(0, 0))
    analysis_body.add_column(ratio=1)
    for label, line, value_style in (
        ("Description", description_line, _DETAIL_MUTED_STYLE),
        ("Detection", detection_line, _DETAIL_VALUE_STYLE),
        ("How", how_line, _DETAIL_MUTED_STYLE),
    ):
        body_text = rich_text_cls()
        body_text.append(f"{label}: ", style=_DETAIL_LABEL_STYLE)
        body_text.append(line.partition(":")[2].strip(), style=value_style)
        analysis_body.add_row(body_text)
        if label != "How":
            analysis_body.add_row(rich_text_cls(""))
    focused_entry_label = focused_entry.label if focused_entry is not None else "None"
    focused_subtitle = rich_text_cls(f"Focused entry: {focused_entry_label}")
    focused_subtitle.stylize(_DETAIL_VALUE_STYLE)
    return rich_panel_cls(
        analysis_body,
        title=_detail_panel_title(rich_text_cls, "Focused analysis"),
        subtitle=focused_subtitle,
        subtitle_align="left",
        border_style=_DETAIL_PANEL_ACCENT,
        box=rich_box.ROUNDED,
        padding=(1, 2),
    )


def _set_analyze_filter_text(self: Any, raw_text: object) -> None:
    filter_text = str(raw_text or "").strip()
    if filter_text == self._analyze_filter_value():
        return
    self._analyze_filter_text = filter_text
    self._normalize_analyze_planner_state()
    self._refresh_view()
    self._set_active_action(None)
    self._refresh_shell_state()
    if filter_text:
        self._write_output(f'Analyze planner filter: "{filter_text}".')
    else:
        self._write_output("Cleared the Analyze planner filter.")


def _prompt_analyze_filter(self: Any) -> None:
    if self._active_request is not None:
        return
    request = InteractionRequest(
        kind="prompt",
        title="Filter analyze planner",
        message="Type text to filter analyses by name or description. Leave blank to clear the filter.",
        default=self._analyze_filter_value(),
    )
    self.present_request(request, on_response_fn=self._set_analyze_filter_text)


def _analyze_browser_detail_renderable(self: Any) -> object:
    detail_text = self._analyze_browser_detail_text()
    if _RichText is None or _RichPanel is None or _RichTable is None or _rich_box is None:
        return detail_text

    rich_text_cls = _RichText
    rich_panel_cls = _RichPanel
    rich_table_cls = _RichTable
    rich_box = _rich_box

    _status_line, _selected_line, _focused_line, description_line, detection_line, how_line = detail_text.split("\n", 5)
    focused_entry = self._planner_entry(self._analyze_focused_entry_id)

    return _build_detail_analysis_panel(
        rich_text_cls=rich_text_cls,
        rich_panel_cls=rich_panel_cls,
        rich_table_cls=rich_table_cls,
        rich_box=rich_box,
        description_line=description_line,
        detection_line=detection_line,
        how_line=how_line,
        focused_entry=focused_entry,
    )


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
        selected_issue_kinds = step.execution.selected_issue_kind_names
        if selected_issue_kinds is None:
            action_fn(self._cfg, selected_keys)
        else:
            action_fn(self._cfg, selected_keys, selected_issue_kinds=frozenset(selected_issue_kinds))
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
        if self._active_job_cancel_requested:
            self._emit_output_from_thread("Cancellation requested. Remaining queued analyses were not started.")
            return
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


if TYPE_CHECKING:

    class _TextualAnalyzeMixin:
        def on_selection_list_selection_toggled(self, event: Any) -> None: ...
        def on_selection_list_selection_highlighted(self, event: Any) -> None: ...
        def _available_analyzer_specs(self) -> tuple[Any, ...]: ...
        def _analyze_filter_value(self) -> str: ...
        def _planner_entry_matches_filter(self, entry: analysis_catalog.AnalysisCatalogEntry) -> bool: ...
        def _planner_base_entries_for_section(
            self, section_id: str
        ) -> tuple[analysis_catalog.AnalysisCatalogEntry, ...]: ...
        def _planner_entries_for_section(
            self, section_id: str
        ) -> tuple[analysis_catalog.AnalysisCatalogEntry, ...]: ...
        def _planner_section_groups(
            self,
        ) -> tuple[
            tuple[analysis_catalog.AnalysisSectionSpec, tuple[analysis_catalog.AnalysisCatalogEntry, ...]], ...
        ]: ...
        def _planner_entry_ids(self) -> tuple[str, ...]: ...
        def _planner_entry(self, entry_id: str | None) -> analysis_catalog.AnalysisCatalogEntry | None: ...
        def _normalize_analyze_planner_state(self) -> None: ...
        def _ordered_selected_analyze_entry_ids(self) -> tuple[str, ...]: ...
        def _analyze_plan(self) -> analysis_planner.AnalysisPlan: ...
        def _analyze_section_list_id(self, section_id: str) -> str: ...
        def _analyze_section_id_from_list(self, selection_list: Any) -> str | None: ...
        def _selection_list_highlighted_entry_id(self, selection_list: Any) -> str | None: ...
        def _sync_analyze_selection_from_selection_list(self, selection_list: Any) -> bool: ...
        def _update_analyze_planner_selection_list(
            self,
            selection_list: Any,
            entries: tuple[analysis_catalog.AnalysisCatalogEntry, ...],
        ) -> None: ...
        def _refresh_analyze_planner(self) -> None: ...
        def _planner_entry_description(self, entry: analysis_catalog.AnalysisCatalogEntry | None) -> str: ...
        def _planner_entry_analyzer_key(self, entry: analysis_catalog.AnalysisCatalogEntry | None) -> str | None: ...
        def _planner_entry_detection(self, entry: analysis_catalog.AnalysisCatalogEntry | None) -> str: ...
        def _planner_entry_how(self, entry: analysis_catalog.AnalysisCatalogEntry | None) -> str: ...
        def _refresh_analyze_planner_summary_widgets(self) -> None: ...
        def _analyze_browser_detail_text(self) -> str: ...
        def _set_analyze_filter_text(self, raw_text: object) -> None: ...
        def _prompt_analyze_filter(self) -> None: ...
        def _analyze_browser_detail_renderable(self) -> object: ...
        def _execute_planned_analysis_step(self, step: Any) -> None: ...
        def _execute_analyze_plan(self, plan: analysis_planner.AnalysisPlan) -> None: ...
        def _run_selected_analysis_plan(self) -> None: ...
        def _clear_selected_analysis_plan(self) -> None: ...
else:

    class _TextualAnalyzeMixin:
        """Provides analyze-planner state, filtering, rendering, and execution behavior."""

        on_selection_list_selection_toggled = on_selection_list_selection_toggled
        on_selection_list_selection_highlighted = on_selection_list_selection_highlighted
        _available_analyzer_specs = _available_analyzer_specs
        _analyze_filter_value = _analyze_filter_value
        _planner_entry_matches_filter = _planner_entry_matches_filter
        _planner_base_entries_for_section = _planner_base_entries_for_section
        _planner_entries_for_section = _planner_entries_for_section
        _planner_section_groups = _planner_section_groups
        _planner_entry_ids = _planner_entry_ids
        _planner_entry = _planner_entry
        _normalize_analyze_planner_state = _normalize_analyze_planner_state
        _ordered_selected_analyze_entry_ids = _ordered_selected_analyze_entry_ids
        _analyze_plan = _analyze_plan
        _analyze_section_list_id = _analyze_section_list_id
        _analyze_section_id_from_list = _analyze_section_id_from_list
        _selection_list_highlighted_entry_id = _selection_list_highlighted_entry_id
        _sync_analyze_selection_from_selection_list = _sync_analyze_selection_from_selection_list
        _update_analyze_planner_selection_list = _update_analyze_planner_selection_list
        _refresh_analyze_planner = _refresh_analyze_planner
        _planner_entry_description = _planner_entry_description
        _planner_entry_analyzer_key = _planner_entry_analyzer_key
        _planner_entry_detection = _planner_entry_detection
        _planner_entry_how = _planner_entry_how
        _refresh_analyze_planner_summary_widgets = _refresh_analyze_planner_summary_widgets
        _analyze_browser_detail_text = _analyze_browser_detail_text
        _set_analyze_filter_text = _set_analyze_filter_text
        _prompt_analyze_filter = _prompt_analyze_filter
        _analyze_browser_detail_renderable = _analyze_browser_detail_renderable
        _execute_planned_analysis_step = _execute_planned_analysis_step
        _execute_analyze_plan = _execute_analyze_plan
        _run_selected_analysis_plan = _run_selected_analysis_plan
        _clear_selected_analysis_plan = _clear_selected_analysis_plan
