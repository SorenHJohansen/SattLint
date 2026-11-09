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
    intermediate, empty = root.children
    assert intermediate.label.plain == "InlineLager.L1 (FrameModule)"
    assert intermediate.data.path == ("Root", "InlineLager", "L1")
    assert intermediate.children[0].label.plain == "L2 (FrameModule)"
    assert empty.label.plain == "Empty (SingleModule)"

    assert "Variable issues (variables)" in results_module._module_findings_report(
        intermediate.data, show_empty_analyzers=False
    )
    assert (
        results_module._module_findings_report(empty.data, show_empty_analyzers=False) == "No findings for this module"
    )

    empty_record = replace(record, targets=(replace(record.targets[0], analyzers=()),))
    results_module._populate_module_navigation(tree, empty_record)
    assert tree.root.children[0].children[0].label.plain == "InlineLager.L1.L2 (FrameModule)"


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
    assert "Variable issues (variables)\n  Unused variable (2)" in report
    assert "Spare (VAR-1) (2 occurrences)" in report
    assert "Site: EQ:Control" in report
    assert "never read" in report
    assert "Why it matters: Unused declaration." in report
    assert "Suggested fix: Delete it." in report


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
    assert report.startswith("Variable issues (variables)\n  Unused datatype field (3)")
    assert "    DeliveryFail\n" in report
    assert "    NotEmpty\n" in report
    assert report.endswith("    PrepareMix\n      datatype 'MixStepTextType'.PrepareMix")


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
    assert start_master.label.plain == "StartMaster (FrameModule)"
    assert [child.label.plain for child in tree.root.children[0].children] == ["StartMaster (FrameModule)"]
    inline = start_master.children[1]
    assert inline.label.plain == "InlineLager.L1.L2 (FrameModule)"
    report = results_module._module_findings_report(inline.data, show_empty_analyzers=False)
    assert "    a\n" in report
    assert report.endswith("    b")

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

    assert "Variable issues (variables)" in results_module._module_findings_report(
        root.children[0].data, show_empty_analyzers=False
    )


def test_show_empty_analyzers_only_at_target_root() -> None:
    record = _record()
    tree = results_module._new_results_tree()
    selection = results_module._populate_module_navigation(tree, record)
    assert selection is not None
    assert results_module._module_findings_report(selection, show_empty_analyzers=True) == (
        "SFC checks (sfc)\n  No findings"
    )
    assert (
        results_module._module_findings_report(tree.root.children[0].children[1].data, show_empty_analyzers=True)
        == "No findings for this module"
    )


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
