# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportMissingParameterType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportPrivateUsage=false, reportAttributeAccessIssue=false
from dataclasses import replace
from types import SimpleNamespace
from typing import Any

from sattlint.application.findings import AnalysisFinding
from sattlint.runs import RunAnalyzerRecord, RunModuleRecord, RunRecord, RunTargetRecord
from sattlint.ui import _app_textual_results as results_module
from sattlint.ui import _app_textual_settings as settings_module


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


def test_module_navigation_merges_single_child_chains_but_keeps_findings_selectable() -> None:
    record = _record()
    tree = results_module._new_results_tree()
    selection = results_module._populate_module_navigation(tree, record)

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
    assert results_module._populate_module_navigation(tree, empty_record) is None
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
    assert report.endswith("  PrepareMix")
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
    assert report.plain.endswith("  b")

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
    selection = results_module._populate_module_navigation(tree, record)
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
