# pyright: reportPrivateUsage=false, reportUnknownLambdaType=false, reportUnknownArgumentType=false
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from rich.style import Style

from sattlint.application.findings import AnalysisFinding
from sattlint.runs import (
    RunAnalyzerRecord,
    RunModuleRecord,
    RunRecord,
    RunTargetRecord,
    finding_acknowledgement_key,
)
from sattlint.ui import _app_textual_results as results_module
from sattlint.ui import _app_textual_settings as settings_module
from sattlint.ui import _app_textual_setup_targets as app_textual_setup_targets_module


def _record() -> RunRecord:
    return RunRecord(
        run_id="r1",
        started_at="s",
        finished_at="f",
        project_tag="Root",
        targets=(
            RunTargetRecord(
                target_name="Root",
                module=RunModuleRecord(
                    name="Lib:Root",
                    kind="SingleModule",
                    children=(
                        RunModuleRecord(
                            name="InlineLager",
                            moduletype_name="InlineLager",
                            children=(
                                RunModuleRecord(
                                    name="L1",
                                    kind="FrameModule",
                                    children=(RunModuleRecord(name="L2", kind="FrameModule"),),
                                ),
                            ),
                        ),
                        RunModuleRecord(name="Empty", kind="SingleModule"),
                    ),
                ),
                analyzers=(
                    RunAnalyzerRecord(
                        key="variables",
                        name="Variable issues",
                        status="completed",
                        findings=(
                            AnalysisFinding(kind="unused", message="m", module_path=("Root", "InlineLager", "L1")),
                        ),
                    ),
                    RunAnalyzerRecord(key="sfc", name="SFC checks", status="completed"),
                ),
            ),
        ),
    )


def test_module_navigation_includes_project_level_analyzers() -> None:
    record = replace(
        _record(),
        targets=(),
        project_analyzers=(
            RunAnalyzerRecord(
                key="icf",
                name="ICF configuration",
                status="completed",
                findings=(AnalysisFinding(kind="icf.unresolved_path", message="m", module_path=("Prog",)),),
            ),
        ),
    )
    tree = results_module._new_results_tree()

    selection = results_module._populate_module_navigation(tree, record).first_selection

    assert selection is not None
    assert selection.target.target_name == "Project"
    assert tree.root.children[0].label.plain == "Project:Prog"


def test_module_navigation_merges_single_child_chains_but_keeps_findings_selectable() -> None:
    record = _record()
    tree = results_module._new_results_tree()
    selection = results_module._populate_module_navigation(tree, record).first_selection

    assert selection is not None
    root = tree.root.children[0]
    assert root.label.plain == "Lib:Root (SingleModule)"
    assert len(root.children) == 1
    intermediate = root.children[0]
    assert intermediate.label.plain == "InlineLager.L1 (FrameModule)"
    assert intermediate.data.path == ("Root", "InlineLager", "L1")
    assert list(intermediate.children) == []

    assert (
        "Variable issues" in results_module._module_findings_report(intermediate.data, show_empty_analyzers=False).plain
    )
    empty_record = replace(record, targets=(replace(record.targets[0], analyzers=()),))
    assert results_module._populate_module_navigation(tree, empty_record).first_selection is None
    assert list(tree.root.children) == []


def test_module_findings_keep_sites_duplicates_and_details() -> None:
    first = AnalysisFinding(
        kind="unused",
        message="[Root.InlineLager.L1] never read",
        module_path=("Root", "InlineLager", "L1"),
        rule_id="VAR-1",
        data={"site": "EQ:Control", "context": "Spare"},
        explanation="Unused declaration.",
        suggestion="Delete it.",
    )
    record = _record()
    analyzer = replace(record.targets[0].analyzers[0], findings=(first, first))
    record = replace(record, targets=(replace(record.targets[0], analyzers=(analyzer,)),))
    tree = results_module._new_results_tree()
    results_module._populate_module_navigation(tree, record)
    selected_module = tree.root.children[0].children[0]
    report = results_module._module_findings_report(selected_module.data, show_empty_analyzers=False)
    assert report.spans
    assert any(span.style == "bold #001ba3" for span in report.spans)
    assert any(span.style == "bold #674600" for span in report.spans)
    report = report.plain
    assert "Variable issues\nUnused variable (2)" in report
    assert "Spare \u00d72" in report
    assert "VAR-1" not in report
    assert "(variables)" not in report
    assert "Equation Control" in report
    assert "never read" not in report
    expanded = results_module._module_findings_report(
        selected_module.data, show_empty_analyzers=False, expanded_details=frozenset({0})
    ).plain
    assert "never read" in expanded
    assert "Why it matters:" not in report
    assert "Suggested fix:" not in report
    assert first.explanation is not None
    assert first.suggestion is not None
    assert first.explanation not in report
    assert first.suggestion not in report


def test_module_navigation_prunes_empty_subtrees_before_merging_paths() -> None:
    root_module = RunModuleRecord(
        name="Root",
        children=(
            RunModuleRecord(
                name="Parent",
                children=(
                    RunModuleRecord(name="EmptyBranch", children=(RunModuleRecord(name="EmptyLeaf"),)),
                    RunModuleRecord(name="Active", children=(RunModuleRecord(name="Leaf"),)),
                ),
            ),
        ),
    )
    finding = AnalysisFinding(kind="unused", message="unused field", module_path=("root", "parent", "active", "leaf"))
    target = RunTargetRecord(
        target_name="Root",
        module=root_module,
        analyzers=(
            RunAnalyzerRecord(key="variables", name="Variable issues", status="completed", findings=(finding,)),
        ),
    )
    tree = results_module._new_results_tree()
    results_module._populate_module_navigation(
        tree, RunRecord(run_id="r1", started_at="s", finished_at="f", project_tag="Root", targets=(target,))
    )

    branches = list(tree.root.children[0].children)
    assert len(branches) == 1
    assert branches[0].label.plain == "Parent.Active.Leaf"
    assert list(branches[0].children) == []
    assert "unused field" in results_module._module_findings_report(branches[0].data, show_empty_analyzers=False).plain


def test_datatype_field_findings_show_each_field_and_omit_completed_status() -> None:
    findings = tuple(
        AnalysisFinding(
            kind="unused_datatype_field",
            message=f"[BasePicture.DataType:MixStepTextType] datatype 'MixStepTextType'.{field}",
            module_path=("BasePicture", "DataType:MixStepTextType"),
            data={"context": "datatype field"},
        )
        for field in ("DeliveryFail", "NotEmpty", "PrepareMix")
    )
    target = RunTargetRecord(
        target_name="KaHCBInlineLib",
        analyzers=(RunAnalyzerRecord(key="variables", name="Variable issues", status="completed", findings=findings),),
    )
    tree = results_module._new_results_tree()
    results_module._populate_module_navigation(
        tree, RunRecord(run_id="r1", started_at="s", finished_at="f", project_tag="", targets=(target,))
    )
    report = results_module._module_findings_report(tree.root.children[0].children[0].data, show_empty_analyzers=False)
    report = report.plain
    assert report.startswith("Variable issues\nUnused datatype field (3)")
    assert "  DeliveryFail\n" in report
    assert "  NotEmpty\n" in report
    assert "  PrepareMix\n  Acknowledge" in report
    assert "datatype 'MixStepTextType'" not in report


def test_read_only_field_label_preserves_field_name() -> None:
    finding = AnalysisFinding(
        kind="field_read_only",
        message="[Root] localvariable 'InletInit'.Plant.Boolean1 (TransferInfoType)",
        data={"context": "InletInit", "variable_name": "InletInit", "field_path": "Plant.Boolean1"},
    )
    assert results_module._context_label(finding) == "InletInit.Plant.Boolean1"
    legacy = replace(finding, data={"context": "InletInit"})
    assert "Plant.Boolean1" in results_module._context_label(legacy)


def test_module_navigation_shows_only_invoked_type_and_keeps_its_findings() -> None:
    root = RunModuleRecord(
        name="Lib:BasePicture",
        kind="SingleModule",
        children=(
            RunModuleRecord(
                name="StartMaster",
                kind="FrameModule",
                children=(
                    RunModuleRecord(name="ChangeLog", kind="SingleModule"),
                    RunModuleRecord(
                        name="InlineLager",
                        moduletype_name="InlineLager",
                        children=(
                            RunModuleRecord(
                                name="L1",
                                kind="FrameModule",
                                children=(RunModuleRecord(name="L2", kind="FrameModule"),),
                            ),
                        ),
                    ),
                ),
            ),
        ),
    )
    direct = AnalysisFinding(kind="unused", message="a", module_path=("BasePicture", "InlineLager", "L1", "L2"))
    invoked = AnalysisFinding(
        kind="unused", message="b", module_path=("BasePicture", "StartMaster", "InlineLager", "L1", "L2")
    )
    target = RunTargetRecord(
        target_name="Lib",
        module=root,
        analyzers=(
            RunAnalyzerRecord(key="variables", name="Variable issues", status="completed", findings=(direct, invoked)),
        ),
    )
    record = RunRecord(run_id="r1", started_at="s", finished_at="f", project_tag="", targets=(target,))
    tree = results_module._new_results_tree()
    results_module._populate_module_navigation(tree, record)

    start_master = tree.root.children[0].children[0]
    assert start_master.label.plain == "StartMaster.InlineLager.L1.L2 (FrameModule)"
    assert len(tree.root.children[0].children) == 1
    inline = start_master
    report = results_module._module_findings_report(inline.data, show_empty_analyzers=False)
    assert "  a\n" in report
    assert "  b\n" in report

    legacy = replace(record, targets=(replace(target, module=None),))
    results_module._populate_module_navigation(tree, legacy)
    assert [child.label.plain for child in tree.root.children[0].children] == ["StartMaster.InlineLager.L1.L2"]
    assert tree.root.children[0].children[0].data.path == inline.data.path


def test_legacy_run_builds_navigation_from_finding_paths() -> None:
    record = replace(
        _record(),
        targets=(
            RunTargetRecord(
                target_name="Root",
                analyzers=(
                    RunAnalyzerRecord(
                        key="variables",
                        name="Variable issues",
                        status="completed",
                        findings=(AnalysisFinding(kind="unused", message="m", module_path=("Root", "A", "B")),),
                    ),
                ),
            ),
        ),
    )
    tree = results_module._new_results_tree()
    results_module._populate_module_navigation(tree, record)
    root = tree.root.children[0]
    assert root.label.plain == "Root"
    assert root.children[0].data.path == ("Root", "A", "B")

    assert "Variable issues" in results_module._module_findings_report(
        root.children[0].data, show_empty_analyzers=False
    )


def test_show_empty_analyzers_only_at_target_root() -> None:
    record = _record()
    tree = results_module._new_results_tree()
    selection = results_module._populate_module_navigation(tree, record).first_selection
    assert selection is not None
    assert results_module._module_findings_report(selection, show_empty_analyzers=True).plain == (
        "SFC checks\n  No findings"
    )
    empty_selection = results_module._ModuleSelection(record.targets[0], ("Root", "Empty"), {})
    assert (
        results_module._module_findings_report(empty_selection, show_empty_analyzers=True).plain
        == "No findings for this module"
    )


def test_findings_rich_formatting_preserves_literal_brackets() -> None:
    finding = AnalysisFinding(
        kind="unused",
        message="[Root] expression is unused",
        module_path=("Root",),
        data={"context": "Values[Index] [bold]literal[/bold]"},
    )
    target = RunTargetRecord(
        target_name="Root",
        analyzers=(
            RunAnalyzerRecord(key="variables", name="Variable issues", status="completed", findings=(finding,)),
        ),
    )
    selection = results_module._ModuleSelection(target, ("Root",), {})

    report = results_module._module_findings_report(selection, show_empty_analyzers=False)

    assert "Values[Index] [bold]literal[/bold]" in report.plain


def test_finding_locations_use_readable_names_without_losing_branches() -> None:
    assert (
        results_module._readable_site("SQ:PhaseSequence > STEP:Stop:ENTER") == "PhaseSequence \u203a Stop \u203a Enter"
    )
    assert (
        results_module._readable_site("SQ:Run > ALT:BRANCH:0 > TRANS:Ready")
        == "Run \u203a Alternative 1 \u203a Transition Ready"
    )
    assert results_module._readable_site("PAR:BRANCH:1") == "Parallel branch 2"
    assert results_module._readable_site("Custom site") == "Custom site"


def test_finding_details_preserve_previous_writes_and_mapping_endpoints() -> None:
    finding = AnalysisFinding(
        kind="unused",
        message="Spare is unused",
        data={
            "context": "Spare",
            "previous_sites": ["SQ:Run > STEP:Start:ENTER"],
            "target_display_name": "Target.Field",
            "source_display_name": "Source.Field",
        },
    )
    assert results_module._finding_details(finding) == [
        "Previous write: Run \u203a Start \u203a Enter",
        "Target: Target.Field",
        "Source: Source.Field",
    ]


def test_generic_finding_context_does_not_repeat_category() -> None:
    finding = AnalysisFinding(
        kind="min_max_mapping_mismatch",
        message="[Root] maximum mapped to minimum",
        data={"context": "Min/Max mapping mismatch"},
    )

    assert results_module._finding_label(finding) == "maximum mapped to minimum"
    assert results_module._finding_details(finding) == []


def _settings_app(cfg: object) -> SimpleNamespace:
    seen_messages: list[str] = []
    app_instance = SimpleNamespace(_cfg=cfg, _dirty=False, _active_request=None, _active_view="settings")
    app_instance._write_output = lambda text: seen_messages.append(str(text))
    app_instance._report_error = lambda title, message: seen_messages.append(str(message))
    app_instance._mark_settings_changed = lambda message: seen_messages.append(str(message))
    app_instance._refresh_summary = lambda: None
    app_instance._refresh_view = lambda: None
    app_instance._refresh_shell_state = lambda: None
    app_instance._set_active_action = lambda _action_id: None
    app_instance._schedule_ui_coroutine = lambda _fn, *, fallback_fn=None: fallback_fn() if fallback_fn else None
    app_instance._seen_messages = seen_messages
    return app_instance


def test_toggle_app_section_flag_updates_nested_config() -> None:
    cfg = {"run_history": {"enabled": True, "limit": 50}}
    app_instance = _settings_app(cfg)

    settings_module._toggle_app_section_flag(app_instance, "run_history", "enabled", label="run history")

    assert cfg["run_history"]["enabled"] is False


def test_toggle_app_debug_updates_config() -> None:
    cfg = {"debug": False}
    app_instance = _settings_app(cfg)

    settings_module._toggle_app_debug(app_instance)

    assert cfg["debug"] is True


def test_prompt_app_int_applies_valid_response() -> None:
    cfg = {"output": {"retention_lines": 4000}}
    app_instance = _settings_app(cfg)

    def _fake_present(request: object, on_response_fn: Any = None) -> None:
        assert on_response_fn is not None
        on_response_fn("8000")

    app_instance.present_request = _fake_present

    settings_module._prompt_app_int(app_instance, "output", "retention_lines", label="retention")

    assert cfg["output"]["retention_lines"] == 8000


def test_prompt_app_int_rejects_invalid_response() -> None:
    cfg = {"output": {"retention_lines": 4000}}
    app_instance = _settings_app(cfg)

    def _fake_present(request: object, on_response_fn: Any = None) -> None:
        assert on_response_fn is not None
        on_response_fn("nope")

    app_instance.present_request = _fake_present

    settings_module._prompt_app_int(app_instance, "output", "retention_lines", label="retention")

    assert cfg["output"]["retention_lines"] == 4000
    assert any("positive integer" in message for message in app_instance._seen_messages)


def _tree_render_app(messages: list[str]) -> SimpleNamespace:
    findings_report = SimpleNamespace(
        update=lambda *_args, **_kwargs: None,
        set_selection=lambda *_args, **_kwargs: None,
    )
    app_instance = SimpleNamespace(
        _selected_run_record=None,
        _results_tree_widget=SimpleNamespace(),
        _results_tree_render_key=None,
        _results_tree_run_id=None,
        _results_pending_run_id=None,
        _results_findings_widget=findings_report,
        _results_show_empty_analyzers_flag=False,
        _selected_results_module=None,
    )
    app_instance._write_output = lambda text: messages.append(str(text))
    app_instance._report_error = lambda title, message: messages.append(str(message))
    app_instance._refresh_shell_state = lambda: None
    app_instance._results_show_empty_analyzers = lambda: False
    return app_instance


def _run_record(run_id: str) -> RunRecord:
    return RunRecord(
        run_id=run_id,
        started_at="2026-09-06T10:00:00Z",
        finished_at="2026-09-06T10:05:00Z",
        project_tag="RootProgram",
    )


def test_results_tree_announces_shown_results_only_when_the_run_changes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    messages: list[str] = []
    populated: list[str] = []
    app_instance = _tree_render_app(messages)

    def record_populated(_tree: object, record: RunRecord, **_kwargs: object) -> Any:
        populated.append(record.run_id)
        return results_module._ModuleNavigation()

    monkeypatch.setattr(results_module, "_populate_module_navigation", record_populated)
    monkeypatch.setattr(results_module, "load_run_acknowledgements", lambda _run_id: frozenset())
    announcement = "Select a module to inspect its findings."

    results_module._render_results_tree(app_instance, _run_record("r1"))

    assert populated == ["r1"]
    assert messages == [announcement]

    results_module._render_results_tree(app_instance, _run_record("r1"))

    assert populated == ["r1"]
    assert messages == [announcement]

    results_module._render_results_tree(app_instance, _run_record("r2"))

    assert populated == ["r1", "r2"]
    assert messages == [announcement, announcement]


def test_results_highlight_defers_and_coalesces_run_loads(monkeypatch: pytest.MonkeyPatch) -> None:
    summaries = [SimpleNamespace(run_id="r1"), SimpleNamespace(run_id="r2")]
    deferred: list[Any] = []
    loaded: list[str] = []
    rendered: list[str] = []
    app_instance = SimpleNamespace(
        _results_run_summaries=summaries,
        _results_tree_run_id=None,
        _results_pending_run_id=None,
    )
    app_instance.call_after_refresh = lambda callback: deferred.append(callback)
    app_instance._render_selected_run = lambda: rendered.append(app_instance._selected_run_record.run_id)
    app_instance._apply_pending_results_run_selection = lambda: results_module._apply_pending_results_run_selection(
        app_instance
    )
    app_instance._request_results_run_selection = lambda run_id: results_module._request_results_run_selection(
        app_instance, run_id
    )
    monkeypatch.setattr(
        results_module,
        "load_run",
        lambda run_id: loaded.append(run_id) or SimpleNamespace(run_id=run_id),
    )

    app_textual_setup_targets_module.on_results_runs_list_highlighted(
        app_instance, SimpleNamespace(list_view=SimpleNamespace(index=0))
    )
    app_textual_setup_targets_module.on_results_runs_list_highlighted(
        app_instance, SimpleNamespace(list_view=SimpleNamespace(index=1))
    )

    assert loaded == []
    assert len(deferred) == 2

    for callback in deferred:
        callback()

    assert loaded == ["r2"]
    assert rendered == ["r2"]


def test_delete_selected_run_asks_before_removing_the_run(monkeypatch: pytest.MonkeyPatch) -> None:
    messages: list[str] = []
    deleted: list[str] = []
    presented: list[tuple[object, Any]] = []
    app_instance = SimpleNamespace(_selected_run_record=_run_record("r1"), _active_request=None)
    app_instance._write_output = lambda text: messages.append(str(text))
    app_instance._refresh_results_view = lambda: None
    app_instance._refresh_shell_state = lambda: None

    def _present(request: object, on_response_fn: Any = None) -> None:
        presented.append((request, on_response_fn))

    app_instance.present_request = _present
    monkeypatch.setattr(
        results_module,
        "delete_run",
        lambda run_id: deleted.append(run_id) or True,
    )

    results_module._delete_selected_run(app_instance)

    assert deleted == []
    assert len(presented) == 1
    request, callback = presented[0]
    assert getattr(request, "kind", None) == "confirm"
    assert "cannot be undone" in getattr(request, "message", "")

    callback(False)

    assert deleted == []
    assert messages == ["Delete canceled."]
    assert app_instance._selected_run_record is not None

    callback(True)

    assert deleted == ["r1"]
    assert app_instance._selected_run_record is None
    assert messages[-1] == "Deleted run 2026-09-06 10:05:00."


def test_results_run_summaries_match_the_project_path_and_drop_legacy_runs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    summaries = [
        SimpleNamespace(run_id="same-path", project_path="/p/a.slproj", project_tag="RootProgram"),
        SimpleNamespace(run_id="other-path", project_path="/p/b.slproj", project_tag="RootProgram"),
        SimpleNamespace(run_id="legacy", project_path="", project_tag="RootProgram"),
        SimpleNamespace(run_id="legacy-other", project_path="", project_tag="AnotherProgram"),
    ]
    monkeypatch.setattr(results_module, "list_runs", lambda: list(summaries))
    app_instance = SimpleNamespace(
        _cfg={"analyzed_programs_and_libraries": ["RootProgram"]},
        _project_path=Path("/p/a.slproj"),
    )
    app_instance._current_project_path = lambda: results_module._current_project_path(app_instance)

    assert [summary.run_id for summary in results_module._results_run_summaries(app_instance)] == [
        "same-path",
    ]

    app_instance._project_path = None
    assert results_module._results_run_summaries(app_instance) == ()


def test_results_run_summaries_match_the_project_path_case_insensitively(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    summaries = [
        SimpleNamespace(run_id="different-case", project_path="/P/A.SLPROJ", project_tag="RootProgram"),
        SimpleNamespace(run_id="other-path", project_path="/p/b.slproj", project_tag="RootProgram"),
    ]
    monkeypatch.setattr(results_module, "list_runs", lambda: list(summaries))
    app_instance = SimpleNamespace(
        _cfg={"analyzed_programs_and_libraries": ["RootProgram"]},
        _project_path=Path("/p/a.slproj"),
    )
    app_instance._current_project_path = lambda: results_module._current_project_path(app_instance)

    assert [summary.run_id for summary in results_module._results_run_summaries(app_instance)] == [
        "different-case",
    ]


def test_results_empty_state_is_reported_once_per_open_project(monkeypatch: pytest.MonkeyPatch) -> None:
    messages: list[str] = []
    app_instance = SimpleNamespace(
        _results_run_summaries=[],
        _results_empty_state_written=False,
        _selected_run_record=None,
        _selected_results_module=None,
        _results_tree_run_id=None,
        _results_tree_render_key=None,
    )
    app_instance._refresh_results_runs_list = lambda: None
    app_instance._write_output = lambda text: messages.append(str(text))

    results_module._refresh_results_view(app_instance)
    results_module._refresh_results_view(app_instance)

    assert messages == ["No saved runs for this configuration. Run analyses from the Analyze view."]


def test_results_tree_expand_and_collapse_use_public_node_state() -> None:
    tree = results_module._new_results_tree()
    child = tree.root.add("child")
    grandchild = child.add("grandchild")

    app_instance = SimpleNamespace(_results_tree_widget=tree, _write_output=lambda _text: None)

    results_module._expand_all_results(app_instance)
    assert child.is_expanded is True
    assert grandchild.is_expanded is True

    results_module._collapse_all_results(app_instance)
    assert child.is_expanded is False
    assert grandchild.is_expanded is False
    assert tree.root.is_expanded is True


def test_results_tree_label_width_is_cached_per_label() -> None:
    tree = results_module._new_results_tree()
    node = tree.root.add("A module label")

    first = tree.get_label_width(node)
    second = tree.get_label_width(node)

    assert first == second
    assert first >= len("A module label")


def test_results_tree_does_not_toggle_expansion_when_selecting_a_node() -> None:
    tree = results_module._new_results_tree()
    parent = tree.root.add("parent")
    parent.add("child")
    parent.expand()

    assert tree.auto_expand is False
    tree._expand_node_on_select(SimpleNamespace(node=parent))  # pyright: ignore[reportPrivateUsage]
    assert parent.is_expanded is True


def test_results_tree_accents_nodes_that_own_findings() -> None:
    tree = results_module._new_results_tree()
    results_module._populate_module_navigation(tree, _record())

    root = tree.root.children[0]
    intermediate = root.children[0]

    assert root.label.style == ""
    assert intermediate.label.style == "bold #674600"


def test_results_tree_marks_a_module_green_when_all_its_findings_are_acknowledged() -> None:
    record = _record()
    finding = record.targets[0].analyzers[0].findings[0]
    key = finding_acknowledgement_key(target_name="Root", analyzer_key="variables", finding=finding)
    tree = results_module._new_results_tree()

    navigation = results_module._populate_module_navigation(tree, record, acknowledged=frozenset({key}))

    module_key = ("root", "inlinelager", "l1")
    assert navigation.nodes[module_key].label.style == "bold #1b7f3a"
    assert navigation.nodes[("root",)].label.style == ""


def test_refresh_results_module_colors_recolors_after_acknowledgement() -> None:
    record = _record()
    finding = record.targets[0].analyzers[0].findings[0]
    key = finding_acknowledgement_key(target_name="Root", analyzer_key="variables", finding=finding)
    tree = results_module._new_results_tree()
    navigation = results_module._populate_module_navigation(tree, record)
    app = SimpleNamespace(_results_navigation=navigation, _selected_run_record=record)

    results_module._refresh_results_module_colors(app, frozenset({key}))

    assert navigation.nodes[("root", "inlinelager", "l1")].label.style == "bold #1b7f3a"

    results_module._refresh_results_module_colors(app, frozenset())

    assert navigation.nodes[("root", "inlinelager", "l1")].label.style == "bold #674600"


def test_results_tree_disallows_expanding_childless_nodes() -> None:
    tree = results_module._new_results_tree()
    results_module._populate_module_navigation(tree, _record())

    root = tree.root.children[0]
    leaf = root.children[0]

    assert list(leaf.children) == []
    assert root.allow_expand is True
    assert leaf.allow_expand is False


def test_results_tree_renders_a_dot_for_leaf_nodes() -> None:
    tree = results_module._new_results_tree()
    branch = tree.root.add("branch")
    leaf = branch.add("leaf")
    results_module._mark_leaf_nodes(tree.root)

    leaf_label = tree.render_label(leaf, Style(), Style()).plain
    branch_label = tree.render_label(branch, Style(), Style()).plain

    assert leaf_label == "\u2022 leaf"
    assert branch_label == f"{tree.ICON_NODE}branch"
    assert tree.get_label_width(leaf) == len("leaf") + 2


def test_finding_groups_split_local_variables_and_module_parameters() -> None:
    findings = tuple(
        AnalysisFinding(
            kind="unused",
            message="declaration",
            module_path=("Root",),
            data={"context": context, "declaration_role": role} if role is not None else {"context": context},
        )
        for context, role in (
            ("Param", "moduleparameter"),
            ("Local", "localvariable"),
            ("Unknown", None),
        )
    )
    target = RunTargetRecord(
        target_name="Root",
        analyzers=(RunAnalyzerRecord(key="variables", name="Variable issues", status="completed", findings=findings),),
    )
    selection = results_module._ModuleSelection(target, ("Root",), {})

    report = results_module._module_findings_report(selection, show_empty_analyzers=False).plain

    assert "Unused module parameter (1)\n  Param" in report
    assert "Unused local variable (1)\n  Local" in report
    assert "Unused variable (1)\n  Unknown" in report


def test_finding_groups_keep_distinct_data_payloads() -> None:
    findings = (
        AnalysisFinding(
            kind="dataflow.dead_overwrite",
            message="overwritten",
            module_path=("Root",),
            data={"site": "EQ:Main", "previous_sites": ["EQ:A"]},
        ),
        AnalysisFinding(
            kind="dataflow.dead_overwrite",
            message="overwritten",
            module_path=("Root",),
            data={"site": "EQ:Main", "previous_sites": ["EQ:B"]},
        ),
    )
    analyzer = RunAnalyzerRecord(
        key="dataflow",
        name="Dataflow",
        status="completed",
        findings=findings,
    )

    groups = results_module._finding_groups(analyzer)

    assert len(groups) == 1
    assert len(groups[0][2]) == 2


def test_finding_role_without_recorded_data_has_no_group() -> None:
    finding = AnalysisFinding(
        kind="unused",
        message="[Root] localvariable  'Legacy' (integer)",
        module_path=("Root",),
        data={"context": "Legacy"},
    )

    assert results_module._finding_declaration_role(finding) is None


def test_acknowledged_finding_is_marked_without_changing_counts() -> None:
    finding = AnalysisFinding(
        kind="unused",
        message="declaration",
        module_path=("Root",),
        data={"context": "Param", "declaration_role": "moduleparameter"},
    )
    target = RunTargetRecord(
        target_name="Root",
        analyzers=(
            RunAnalyzerRecord(key="variables", name="Variable issues", status="completed", findings=(finding,)),
        ),
    )
    selection = results_module._ModuleSelection(target, ("Root",), {})
    key = finding_acknowledgement_key(
        target_name="Root",
        analyzer_key="variables",
        finding=finding,
        declaration_role="moduleparameter",
    )

    report, keys = results_module._build_module_findings_report(
        selection,
        show_empty_analyzers=False,
        acknowledged=frozenset({key}),
    )

    assert keys == (key,)
    assert "Unused module parameter (1)" in report.plain
    assert "\u2713 Param" in report.plain
    assert any(span.style == "dim bold" for span in report.spans)


def test_toggle_results_acknowledgement_updates_state_and_persists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    messages: list[str] = []
    saved: list[tuple[str, frozenset[str]]] = []
    selections: list[dict[str, object]] = []
    monkeypatch.setattr(
        results_module,
        "save_run_acknowledgements",
        lambda run_id, keys: saved.append((run_id, keys)) or True,
    )
    app_instance = SimpleNamespace(
        _results_tree_run_id="r1",
        _results_acknowledged=frozenset(),
        _selected_results_module=SimpleNamespace(),
        _results_findings_widget=SimpleNamespace(
            set_acknowledged=lambda acknowledged, *, run_id: selections.append(
                {"acknowledged": acknowledged, "run_id": run_id}
            )
        ),
    )
    app_instance._write_output = lambda text: messages.append(str(text))

    results_module._toggle_results_acknowledgement(app_instance, "r1", "key")

    assert app_instance._results_acknowledged == frozenset({"key"})
    assert saved == [("r1", frozenset({"key"}))]
    assert selections[-1]["acknowledged"] == frozenset({"key"})
    assert messages == ["Acknowledged finding."]

    results_module._toggle_results_acknowledgement(app_instance, "r1", "key")

    assert app_instance._results_acknowledged == frozenset()
    assert saved[-1] == ("r1", frozenset())
    assert messages[-1] == "Acknowledgement cleared."
