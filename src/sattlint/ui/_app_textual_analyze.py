# pyright: reportMissingImports=false, reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportUnknownLambdaType=false, reportGeneralTypeIssues=false, reportInvalidTypeForm=false, reportConstantRedefinition=false, reportPrivateUsage=false, reportUnusedClass=false, reportUnusedFunction=false, reportUnknownArgumentType=false

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

from ._app_textual_actions import _label_value_renderable
from ._app_textual_shared import (
    _ANALYZE_PLANNER_LIST_ID_PREFIX,
    _TEXTUAL_OPTION_LIST_ERRORS,
    _TEXTUAL_SELECTION_LIST,
    _TEXTUAL_STATIC,
    _TEXTUAL_VERTICAL,
    NO_PROJECT_NOTICE,
    InteractionRequest,
    _query_required,
    _stringify_value,
)


@dataclass(frozen=True)
class _AnalyzerItem:
    """A single selectable analyzer sourced straight from the registry."""

    entry_id: str
    label: str
    description: str
    category: str


@dataclass(frozen=True)
class _AnalyzeRunPlan:
    """The direct run request for the currently selected analyzers."""

    selected_analyzer_keys: tuple[str, ...]

    @property
    def is_runnable(self) -> bool:
        return bool(self.selected_analyzer_keys)


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
    self._write_focused_entry_to_output()
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
    self._write_focused_entry_to_output()
    self._refresh_shell_state()


def _available_analyzer_items(self: Any) -> tuple[_AnalyzerItem, ...]:
    get_analyzers_fn = getattr(self, "_get_enabled_analyzers_fn", None)
    if get_analyzers_fn is None or not callable(get_analyzers_fn):
        return ()
    analyzers_obj = get_analyzers_fn()
    raw_items: list[object]
    if isinstance(analyzers_obj, list):
        raw_items = analyzers_obj
    elif isinstance(analyzers_obj, tuple):
        raw_items = list(analyzers_obj)
    else:
        return ()
    items: list[_AnalyzerItem] = []
    for raw in raw_items:
        key = str(getattr(raw, "key", "") or "").strip()
        if not key:
            continue
        name = str(getattr(raw, "name", "") or "").strip() or _pretty_analyzer_key(key)
        description = str(getattr(raw, "description", "") or "").strip()
        category = str(getattr(raw, "category", "") or "correctness").strip()
        items.append(_AnalyzerItem(key, name, description, category))
    return tuple(items)


def _pretty_analyzer_key(key: str) -> str:
    return key.replace("-", " ").title()


def _analyze_filter_value(self: Any) -> str:
    return str(getattr(self, "_analyze_filter_text", "") or "").strip()


def _item_matches_filter(self: Any, item: _AnalyzerItem) -> bool:
    filter_text = self._analyze_filter_value().casefold()
    if not filter_text:
        return True
    search_text = " ".join((item.entry_id, item.label, item.description)).casefold()
    return filter_text in search_text


def _planner_items(self: Any) -> tuple[_AnalyzerItem, ...]:
    return tuple(item for item in self._available_analyzer_items() if self._item_matches_filter(item))


def _planner_section_groups(
    self: Any,
) -> tuple[tuple[Any, tuple[_AnalyzerItem, ...]], ...]:
    items = self._planner_items()
    if not items:
        return ()
    ordered: list[_AnalyzerItem] = list(items)
    ordered.sort(key=lambda item: (item.category, item.label.casefold()))
    return ((_analyzers_section_spec(), tuple(ordered)),)


def _analyzers_section_spec() -> Any:
    return type(
        "SectionSpec",
        (),
        {"section_id": "analyzers", "label": "Analyzers", "description": "Select one or more analyzers to run."},
    )()


def _planner_entry_ids(self: Any) -> tuple[str, ...]:
    return tuple(item.entry_id for _section, items in self._planner_section_groups() for item in items)


def _planner_entry(self: Any, entry_id: str | None) -> _AnalyzerItem | None:
    if entry_id is None:
        return None
    for item in self._available_analyzer_items():
        if item.entry_id == entry_id:
            return item
    return None


def _normalize_analyze_planner_state(self: Any) -> None:
    valid_entry_ids = self._planner_entry_ids()
    valid_entry_id_set = set(valid_entry_ids)
    self._analyze_selected_entry_ids.intersection_update(valid_entry_id_set)
    if self._analyze_focused_entry_id not in valid_entry_id_set:
        self._analyze_focused_entry_id = valid_entry_ids[0] if valid_entry_ids else None


def _ordered_selected_analyze_entry_ids(self: Any) -> tuple[str, ...]:
    self._normalize_analyze_planner_state()
    return tuple(entry_id for entry_id in self._planner_entry_ids() if entry_id in self._analyze_selected_entry_ids)


def _analyze_plan(self: Any) -> _AnalyzeRunPlan:
    return _AnalyzeRunPlan(tuple(self._ordered_selected_analyze_entry_ids()))


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
    return value or None


def _sync_analyze_selection_from_selection_list(self: Any, selection_list: Any) -> bool:
    section_id = self._analyze_section_id_from_list(selection_list)
    if section_id is None:
        return False
    section_entry_ids = {item.entry_id for item in self._planner_items()}
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
    items: tuple[_AnalyzerItem, ...],
) -> None:
    selection_list.clear_options()
    selection_list.add_options(
        [(item.label, item.entry_id, item.entry_id in self._analyze_selected_entry_ids) for item in items]
    )
    if items:
        highlighted_index = 0
        if self._analyze_focused_entry_id is not None:
            for index, item in enumerate(items):
                if item.entry_id == self._analyze_focused_entry_id:
                    highlighted_index = index
                    break
        selection_list.highlighted = highlighted_index


def _refresh_analyze_planner(self: Any) -> None:
    container = _query_required(self, "#analyze-browser-left", _TEXTUAL_VERTICAL)

    if not self._project_loaded():
        for child in list(getattr(container, "children", [])):
            child.remove()
        container.mount(_TEXTUAL_STATIC(NO_PROJECT_NOTICE, classes="browser-empty-state"))
        return

    self._suppress_analyze_planner_events = True
    try:
        self._normalize_analyze_planner_state()
        section_groups = self._planner_section_groups()
        if not section_groups:
            for child in list(getattr(container, "children", [])):
                child.remove()
            empty_text = (
                f'No analyzers match "{self._analyze_filter_value()}".'
                if self._analyze_filter_value()
                else "No analyzers are available in the current Textual session."
            )
            container.mount(_TEXTUAL_STATIC(empty_text, classes="browser-empty-state"))
            return

        section, items = section_groups[0]
        expected_list_id = self._analyze_section_list_id(section.section_id)
        children = tuple(cast(tuple[Any, ...], getattr(container, "children", ())))
        existing_matching = [child for child in children if str(getattr(child, "id", "") or "") == expected_list_id]
        selection_list: Any = None
        if existing_matching:
            selection_list = _query_required(self, f"#{expected_list_id}", _TEXTUAL_SELECTION_LIST)
            self._update_analyze_planner_selection_list(selection_list, items)
        else:
            for child in list(getattr(container, "children", [])):
                child.remove()
            container.mount(_TEXTUAL_STATIC(section.label, classes="browser-section-title"))
            if getattr(section, "description", ""):
                container.mount(_TEXTUAL_STATIC(section.description, classes="planner-section-note"))
            selection_list = _TEXTUAL_SELECTION_LIST(
                *[(item.label, item.entry_id, item.entry_id in self._analyze_selected_entry_ids) for item in items],
                id=expected_list_id,
                classes="analyze-planner-list",
            )
            if items:
                highlighted_index = 0
                if self._analyze_focused_entry_id is not None:
                    for index, item in enumerate(items):
                        if item.entry_id == self._analyze_focused_entry_id:
                            highlighted_index = index
                            break
                selection_list.highlighted = highlighted_index
            container.mount(selection_list)
    finally:
        self._suppress_analyze_planner_events = False


def _planner_entry_description(self: Any, item: _AnalyzerItem | None) -> str:
    if item is None:
        return "Select an analyzer on the left to see what it reports."
    return item.description or "No description available."


def _write_focused_entry_to_output(self: Any) -> None:
    self._normalize_analyze_planner_state()
    focused_entry = self._planner_entry(self._analyze_focused_entry_id)
    self._analyze_help_shown = True
    self._clear_session_output()
    if focused_entry is None:
        self._write_output("Select an analyzer on the left to see what it reports.")
        return
    description = self._planner_entry_description(focused_entry)
    segments: list[tuple[str, str]] = [
        ("Analyzer", focused_entry.label),
    ]
    if focused_entry.category:
        segments.append(("Category", focused_entry.category))
    if description:
        segments.append(("", ""))
        segments.append(("Description", description))
    plain_lines = []
    for label, value in segments:
        if not label:
            plain_lines.append("")
        elif "\n" not in value:
            plain_lines.append(f"{label}: {value}")
        else:
            lines = value.split("\n")
            plain_lines.append(f"{label}: {lines[0]}")
            plain_lines.extend(f"  {line}" for line in lines[1:])
    self._session_output_lines.extend(plain_lines)
    output_widget = self.query_one("#output")
    for label, value in segments:
        if not label:
            if hasattr(output_widget, "append_plain_text"):
                output_widget.append_plain_text("\n")
            output_widget.write("", scroll_end=False)
            continue
        if "\n" not in value:
            if hasattr(output_widget, "append_plain_text"):
                output_widget.append_plain_text(f"{label}: {value}\n")
            output_widget.write(
                _label_value_renderable(label, value),
                scroll_end=False,
            )
        else:
            lines = value.split("\n")
            if hasattr(output_widget, "append_plain_text"):
                output_widget.append_plain_text(f"{label}: {lines[0]}\n")
            output_widget.write(
                _label_value_renderable(label, lines[0]),
                scroll_end=False,
            )
            for line in lines[1:]:
                if hasattr(output_widget, "append_plain_text"):
                    output_widget.append_plain_text(f"  {line}\n")
                output_widget.write(f"  {line}", scroll_end=False)


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
        self._write_output(f'Analyzer filter: "{filter_text}".')
    else:
        self._write_output("Cleared the analyzer filter.")


def _prompt_analyze_filter(self: Any) -> None:
    if self._active_request is not None:
        return
    request = InteractionRequest(
        kind="prompt",
        title="Filter analyzers",
        message="Type text to filter analyzers by name or description. Leave blank to clear the filter.",
        default=self._analyze_filter_value(),
    )
    self.present_request(request, on_response_fn=self._set_analyze_filter_text)


def _run_selected_analysis_plan(self: Any) -> None:
    if not self._targets_action_allowed("analysis"):
        return
    if not self._ordered_selected_analyze_entry_ids():
        self._write_output("Select one or more analyzers in the list first.")
        return
    plan = self._analyze_plan()
    if not plan.is_runnable:
        self._write_output("No analyzers are selected to run.")
        return
    self._start_action(
        "Run selected analyzers",
        lambda plan=plan: self._execute_analyze_plan(plan),
        action_id="action-analyze",
    )


def _execute_analyze_plan(self: Any, plan: _AnalyzeRunPlan) -> None:
    self._emit_output_from_thread(f"Running {len(plan.selected_analyzer_keys)} selected analyzer(s).")
    handler = None
    if isinstance(getattr(self, "_analysis_handlers", None), dict):
        handler = self._analysis_handlers.get("run_checks_result")
        if not callable(handler):
            handler = self._analysis_handlers.get("_run_checks")
    if not callable(handler):
        self._emit_output_from_thread("The analyzer runner is unavailable in the current Textual session.")
        return
    if not self._configured_target_names():
        self._emit_output_from_thread("No configured analysis targets are available.")
        return
    result = handler(self._cfg, list(plan.selected_analyzer_keys))
    self._emit_output_from_thread("Selected analyzers completed.")
    if result is not None:
        self.call_from_thread(self._finish_analysis_run, result)


def _finish_analysis_run(self: Any, result: Any) -> None:
    del result
    self._activate_view("results")


def _clear_selected_analysis_plan(self: Any) -> None:
    self._clear_session_output()
    if not self._analyze_selected_entry_ids:
        return
    self._analyze_selected_entry_ids.clear()
    self._refresh_view()
    self._refresh_shell_state()
    self._write_output("Cleared the analyzer selection and session output.")


def _run_generate_change_review(self: Any) -> None:
    if not self._targets_action_allowed("analysis"):
        return
    if not self._setup_has_targets():
        self._write_output("No configured analysis targets are available for Change Review.")
        return
    self._start_action(
        "Generate Change Review",
        lambda: self._execute_generate_change_review(),
        action_id="action-analyze",
    )


def _execute_generate_change_review(self: Any) -> None:
    self._emit_output_from_thread("Generating Change Review for the configured project...")
    handler = None
    if isinstance(getattr(self, "_analysis_handlers", None), dict):
        handler = self._analysis_handlers.get("generate_change_review")
    if not callable(handler):
        self._emit_output_from_thread("The Change Review generator is unavailable in the current Textual session.")
        return
    try:
        summary = handler(self._cfg, list(self._configured_target_names()))
    except Exception as exc:  # noqa: BLE001
        self._emit_output_from_thread(f"Change Review failed: {exc}")
        return
    self._emit_output_from_thread(str(summary))


if TYPE_CHECKING:

    class _TextualAnalyzeMixin:
        def on_selection_list_selection_toggled(self, event: Any) -> None: ...
        def on_selection_list_selection_highlighted(self, event: Any) -> None: ...
        def _available_analyzer_items(self) -> tuple[_AnalyzerItem, ...]: ...
        def _analyze_filter_value(self) -> str: ...
        def _item_matches_filter(self, item: _AnalyzerItem) -> bool: ...
        def _planner_items(self) -> tuple[_AnalyzerItem, ...]: ...
        def _planner_section_groups(self) -> tuple[tuple[Any, tuple[_AnalyzerItem, ...]], ...]: ...
        def _planner_entry_ids(self) -> tuple[str, ...]: ...
        def _planner_entry(self, entry_id: str | None) -> _AnalyzerItem | None: ...
        def _normalize_analyze_planner_state(self) -> None: ...
        def _ordered_selected_analyze_entry_ids(self) -> tuple[str, ...]: ...
        def _analyze_plan(self) -> _AnalyzeRunPlan: ...
        def _analyze_section_list_id(self, section_id: str) -> str: ...
        def _analyze_section_id_from_list(self, selection_list: Any) -> str | None: ...
        def _selection_list_highlighted_entry_id(self, selection_list: Any) -> str | None: ...
        def _sync_analyze_selection_from_selection_list(self, selection_list: Any) -> bool: ...
        def _update_analyze_planner_selection_list(
            self, selection_list: Any, items: tuple[_AnalyzerItem, ...]
        ) -> None: ...
        def _refresh_analyze_planner(self) -> None: ...
        def _planner_entry_description(self, item: _AnalyzerItem | None) -> str: ...
        def _write_focused_entry_to_output(self) -> None: ...
        def _set_analyze_filter_text(self, raw_text: object) -> None: ...
        def _prompt_analyze_filter(self) -> None: ...
        def _run_selected_analysis_plan(self) -> None: ...
        def _execute_analyze_plan(self, plan: _AnalyzeRunPlan) -> None: ...
        def _finish_analysis_run(self, result: Any) -> None: ...
        def _clear_selected_analysis_plan(self) -> None: ...
        def _run_generate_change_review(self) -> None: ...
        def _execute_generate_change_review(self) -> None: ...
else:

    class _TextualAnalyzeMixin:
        """Provides direct analyzer selection and execution behavior."""

        on_selection_list_selection_toggled = on_selection_list_selection_toggled
        on_selection_list_selection_highlighted = on_selection_list_selection_highlighted
        _available_analyzer_items = _available_analyzer_items
        _analyze_filter_value = _analyze_filter_value
        _item_matches_filter = _item_matches_filter
        _planner_items = _planner_items
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
        _write_focused_entry_to_output = _write_focused_entry_to_output
        _set_analyze_filter_text = _set_analyze_filter_text
        _prompt_analyze_filter = _prompt_analyze_filter
        _run_selected_analysis_plan = _run_selected_analysis_plan
        _execute_analyze_plan = _execute_analyze_plan
        _finish_analysis_run = _finish_analysis_run
        _clear_selected_analysis_plan = _clear_selected_analysis_plan
        _run_generate_change_review = _run_generate_change_review
        _execute_generate_change_review = _execute_generate_change_review
