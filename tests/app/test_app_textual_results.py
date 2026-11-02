# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportPrivateUsage=false, reportAttributeAccessIssue=false
from types import SimpleNamespace
from typing import Any

from sattlint.application.findings import AnalysisFinding
from sattlint.runs import RunAnalyzerRecord, RunRecord, RunTargetRecord
from sattlint.ui import _app_textual_results as app_textual_results_module
from sattlint.ui import _app_textual_settings as app_textual_settings_module


def _settings_app(cfg: object) -> SimpleNamespace:
    seen_messages: list[str] = []

    app_instance = SimpleNamespace(
        _cfg=cfg,
        _dirty=False,
        _active_request=None,
        _active_view="settings",
    )
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

    app_textual_settings_module._toggle_app_section_flag(app_instance, "run_history", "enabled", label="run history")

    assert cfg["run_history"]["enabled"] is False


def test_toggle_app_debug_updates_config() -> None:
    cfg = {"debug": False}
    app_instance = _settings_app(cfg)

    app_textual_settings_module._toggle_app_debug(app_instance)

    assert cfg["debug"] is True


def test_prompt_app_int_applies_valid_response() -> None:
    cfg = {"output": {"retention_lines": 4000}}
    app_instance = _settings_app(cfg)

    def _fake_present(request: object, on_response_fn: Any = None) -> None:
        assert on_response_fn is not None
        on_response_fn("8000")

    app_instance.present_request = _fake_present

    app_textual_settings_module._prompt_app_int(app_instance, "output", "retention_lines", label="retention")

    assert cfg["output"]["retention_lines"] == 8000


def test_prompt_app_int_rejects_invalid_response() -> None:
    cfg = {"output": {"retention_lines": 4000}}
    app_instance = _settings_app(cfg)

    def _fake_present(request: object, on_response_fn: Any = None) -> None:
        assert on_response_fn is not None
        on_response_fn("nope")

    app_instance.present_request = _fake_present

    app_textual_settings_module._prompt_app_int(app_instance, "output", "retention_lines", label="retention")

    assert cfg["output"]["retention_lines"] == 4000
    assert any("positive integer" in message for message in app_instance._seen_messages)


def test_results_tree_builds_run_hierarchy() -> None:
    record = RunRecord(
        run_id="r1",
        started_at="2026-09-06T10:00:00Z",
        finished_at="2026-09-06T10:05:00Z",
        project_tag="RootProgram",
        targets=(
            RunTargetRecord(
                target_name="RootProgram",
                is_library=False,
                analyzers=(
                    RunAnalyzerRecord(
                        key="variables",
                        name="Variable issues",
                        status="completed",
                        findings=(
                            AnalysisFinding(
                                kind="unused",
                                message="declared but never read",
                                module_path=("RootProgram", "StartMaster"),
                            ),
                        ),
                    ),
                ),
            ),
        ),
    )

    tree = app_textual_results_module._build_run_tree(record)

    assert tree is not None
    root_children = list(tree.root.children)
    assert len(root_children) == 1
    target_node = root_children[0]
    assert target_node.data is record.targets[0]
    analyzer_node = next(iter(target_node.children))
    assert analyzer_node.data is record.targets[0].analyzers[0]
    kind_node = next(iter(analyzer_node.children))
    assert kind_node.data is None
    module_node = next(iter(kind_node.children))
    assert module_node.data == "RootProgram.StartMaster"
    assert module_node.label.plain == "RootProgram.StartMaster"
    finding_node = next(iter(module_node.children))
    assert finding_node.data == record.targets[0].analyzers[0].findings[0]


def test_results_tree_groups_findings_by_kind() -> None:
    record = RunRecord(
        run_id="r1",
        started_at="s",
        finished_at="f",
        project_tag="RootProgram",
        targets=(
            RunTargetRecord(
                target_name="RootProgram",
                is_library=False,
                analyzers=(
                    RunAnalyzerRecord(
                        key="variables",
                        name="Variable issues",
                        status="completed",
                        findings=(
                            AnalysisFinding(
                                kind="unused",
                                message="declared but never read",
                                module_path=("RootProgram", "A"),
                            ),
                            AnalysisFinding(
                                kind="unused",
                                message="assigned but never read",
                                module_path=("RootProgram", "B"),
                            ),
                            AnalysisFinding(
                                kind="shadowed",
                                message="shadows an outer variable",
                                module_path=("RootProgram", "B"),
                            ),
                        ),
                    ),
                ),
            ),
        ),
    )

    tree = app_textual_results_module._build_run_tree(record)

    assert tree is not None
    analyzer_node = next(iter(tree.root.children[0].children))
    kind_nodes = list(analyzer_node.children)
    assert [node.label.plain for node in kind_nodes] == ["Unused variable (2)", "Shadowed (1)"]

    unused_kind, shadowed_kind = kind_nodes
    unused_root = next(iter(unused_kind.children))
    assert unused_root.data == "RootProgram"
    unused_modules = list(unused_root.children)
    assert [node.data for node in unused_modules] == ["RootProgram.A", "RootProgram.B"]
    shadow_module = next(iter(shadowed_kind.children))
    assert shadow_module.data == "RootProgram.B"
    assert shadow_module.label.plain == "RootProgram.B"
    assert len(list(unused_modules[0].children)) == 1
    assert len(list(unused_modules[1].children)) == 1
    assert len(list(shadow_module.children)) == 1


def test_results_tree_collapses_identical_findings_to_one_path() -> None:
    record = RunRecord(
        run_id="r1",
        started_at="s",
        finished_at="f",
        project_tag="RootProgram",
        targets=(
            RunTargetRecord(
                target_name="RootProgram",
                is_library=False,
                analyzers=(
                    RunAnalyzerRecord(
                        key="variables",
                        name="Variable issues",
                        status="completed",
                        findings=(
                            AnalysisFinding(
                                kind="typedef",
                                message="never used",
                                module_path=("RootProgram", "A", "Pump_1"),
                            ),
                            AnalysisFinding(
                                kind="typedef",
                                message="never used",
                                module_path=("RootProgram", "A", "Pump_2"),
                            ),
                            AnalysisFinding(
                                kind="typedef",
                                message="never used",
                                module_path=("RootProgram", "A", "Pump_3"),
                            ),
                        ),
                    ),
                ),
            ),
        ),
    )

    tree = app_textual_results_module._build_run_tree(record)

    assert tree is not None
    analyzer_node = next(iter(tree.root.children[0].children))
    kind_node = next(iter(analyzer_node.children))
    assert kind_node.label.plain == "Typedef (3)"
    root_branch = next(iter(kind_node.children))
    assert root_branch.data == "RootProgram.A.Pump_1"
    assert root_branch.label.plain == "RootProgram.A.Pump_1"
    leaf = next(iter(root_branch.children))
    assert leaf.data.kind == "typedef"
    assert "3 occurrences" in leaf.label.plain


def test_results_tree_keeps_identical_findings_at_distinct_sites() -> None:
    first = AnalysisFinding(
        kind="dataflow.condition_always_false",
        message="Condition 'False' is always false at this point.",
        module_path=("RootProgram", "MixingAfl", "PhaseLogic"),
        data={"site": "SQ:PhaseSequence > TRANS:Tr12"},
    )
    second = AnalysisFinding(
        kind="dataflow.condition_always_false",
        message="Condition 'False' is always false at this point.",
        module_path=("RootProgram", "MixingAfl", "PhaseLogic"),
        data={"site": "SQ:PhaseSequence > TRANS:Tr47"},
    )
    record = RunRecord(
        run_id="r1",
        started_at="s",
        finished_at="f",
        project_tag="RootProgram",
        targets=(
            RunTargetRecord(
                target_name="RootProgram",
                is_library=False,
                analyzers=(
                    RunAnalyzerRecord(
                        key="dataflow",
                        name="Dataflow",
                        status="completed",
                        findings=(first, second),
                    ),
                ),
            ),
        ),
    )

    tree = app_textual_results_module._build_run_tree(record)

    assert tree is not None
    analyzer_node = next(iter(tree.root.children[0].children))
    kind_node = next(iter(analyzer_node.children))
    module_node = next(iter(kind_node.children))
    assert module_node.data == "RootProgram.MixingAfl.PhaseLogic"
    site_nodes = list(module_node.children)
    assert [node.label.plain for node in site_nodes] == [
        "SQ:PhaseSequence > TRANS:Tr12",
        "SQ:PhaseSequence > TRANS:Tr47",
    ]
    assert [next(iter(node.children)).data for node in site_nodes] == [first, second]


def test_results_tree_renders_site_node_and_finding_leaf() -> None:
    record = RunRecord(
        run_id="r1",
        started_at="s",
        finished_at="f",
        project_tag="RootProgram",
        targets=(
            RunTargetRecord(
                target_name="RootProgram",
                is_library=False,
                analyzers=(
                    RunAnalyzerRecord(
                        key="variables",
                        name="Variable issues",
                        status="completed",
                        findings=(
                            AnalysisFinding(
                                kind="string_mapping_mismatch",
                                message="[RootProgram.Child] parameter mapping type mismatch",
                                module_path=("RootProgram", "Child"),
                                data={"site": "Child : ChildType", "context": "TargetVal => SourceVal"},
                            ),
                        ),
                    ),
                ),
            ),
        ),
    )

    tree = app_textual_results_module._build_run_tree(record)

    assert tree is not None
    analyzer_node = next(iter(tree.root.children[0].children))
    kind_node = next(iter(analyzer_node.children))
    module_node = next(iter(kind_node.children))
    assert module_node.data == "RootProgram.Child"
    site_node = next(iter(module_node.children))
    assert site_node.label.plain == "Child : ChildType"
    leaf = next(iter(site_node.children))
    assert leaf.data.kind == "string_mapping_mismatch"
    assert "TargetVal => SourceVal" in leaf.label.plain
    assert "[RootProgram.Child]" not in leaf.label.plain
    assert not list(leaf.children)
    assert leaf.allow_expand is False


def test_results_tree_finding_node_is_leaf_preserving_detail_data() -> None:
    record = RunRecord(
        run_id="r1",
        started_at="s",
        finished_at="f",
        project_tag="RootProgram",
        targets=(
            RunTargetRecord(
                target_name="RootProgram",
                is_library=False,
                analyzers=(
                    RunAnalyzerRecord(
                        key="variables",
                        name="Variable issues",
                        status="completed",
                        findings=(
                            AnalysisFinding(
                                kind="unused",
                                message="declared but never read",
                                module_path=("RootProgram",),
                                data={"context": "Spare"},
                                explanation="Stale declarations add noise.",
                                suggestion="Delete the declaration.",
                            ),
                        ),
                    ),
                ),
            ),
        ),
    )

    tree = app_textual_results_module._build_run_tree(record)

    assert tree is not None
    analyzer_node = next(iter(tree.root.children[0].children))
    kind_node = next(iter(analyzer_node.children))
    root_branch = next(iter(kind_node.children))
    finding_node = next(iter(root_branch.children))
    assert finding_node.data.kind == "unused"
    assert finding_node.data.explanation == "Stale declarations add noise."
    assert finding_node.data.suggestion == "Delete the declaration."
    assert not list(finding_node.children)
    assert finding_node.allow_expand is False


def test_results_tree_merges_identical_site_nodes_for_separate_findings() -> None:
    record = RunRecord(
        run_id="r1",
        started_at="s",
        finished_at="f",
        project_tag="RootProgram",
        targets=(
            RunTargetRecord(
                target_name="RootProgram",
                is_library=False,
                analyzers=(
                    RunAnalyzerRecord(
                        key="variables",
                        name="Variable issues",
                        status="completed",
                        findings=(
                            AnalysisFinding(
                                kind="magic_number",
                                message="[RootProgram.LoopLogic] magic number 1",
                                module_path=("RootProgram", "LoopLogic"),
                                data={"site": "EQ:Control", "context": "Output = 1"},
                            ),
                            AnalysisFinding(
                                kind="magic_number",
                                message="[RootProgram.LoopLogic] magic number 2",
                                module_path=("RootProgram", "LoopLogic"),
                                data={"site": "EQ:Control", "context": "Output = 2"},
                            ),
                        ),
                    ),
                ),
            ),
        ),
    )

    tree = app_textual_results_module._build_run_tree(record)

    assert tree is not None
    analyzer_node = next(iter(tree.root.children[0].children))
    kind_node = next(iter(analyzer_node.children))
    module_node = next(iter(kind_node.children))
    assert module_node.label.plain == "RootProgram.LoopLogic"
    site_nodes = list(module_node.children)
    assert len(site_nodes) == 1
    assert site_nodes[0].label.plain == "EQ:Control"
    assert len(list(site_nodes[0].children)) == 2


def test_results_tree_hides_empty_analyzers_by_default() -> None:
    record = RunRecord(
        run_id="r1",
        started_at="s",
        finished_at="f",
        project_tag="RootProgram",
        targets=(
            RunTargetRecord(
                target_name="RootProgram",
                is_library=False,
                analyzers=(
                    RunAnalyzerRecord(
                        key="variables",
                        name="Variable issues",
                        status="completed",
                        findings=(AnalysisFinding(kind="unused", message="m", module_path=("RootProgram",)),),
                    ),
                    RunAnalyzerRecord(key="sfc", name="SFC checks", status="completed", findings=()),
                ),
            ),
        ),
    )

    hidden = app_textual_results_module._build_run_tree(record)
    assert hidden is not None
    target_node = hidden.root.children[0]
    assert [child.data.key for child in target_node.children] == ["variables"]

    shown = app_textual_results_module._build_run_tree(record, show_empty_analyzers=True)
    assert shown is not None
    target_node = shown.root.children[0]
    assert [child.data.key for child in target_node.children] == ["variables", "sfc"]


def test_results_tree_returns_none_without_textual() -> None:
    original = app_textual_results_module._TEXTUAL_TREE
    app_textual_results_module._TEXTUAL_TREE = None
    try:
        record = RunRecord(run_id="r1", started_at="s", finished_at="f", project_tag="")
        assert app_textual_results_module._build_run_tree(record) is None
    finally:
        app_textual_results_module._TEXTUAL_TREE = original


def test_run_tree_top_level_is_one_node_per_target() -> None:
    record = RunRecord(
        run_id="r1",
        started_at="s",
        finished_at="2026-09-06T10:05:00Z",
        project_tag="RootProgram",
        targets=(
            RunTargetRecord(
                target_name="RootProgram",
                is_library=False,
                analyzers=(
                    RunAnalyzerRecord(
                        key="variables",
                        name="Variable issues",
                        status="completed",
                        findings=(AnalysisFinding(kind="unused", message="msg", module_path=("RootProgram",)),),
                    ),
                ),
            ),
        ),
    )

    tree = app_textual_results_module._build_run_tree(record)
    assert tree is not None
    assert str(tree.root.label) == ""
    assert [child.data.target_name for child in tree.root.children] == ["RootProgram"]


def test_results_tree_keeps_branch_points_when_merging_module_chains() -> None:
    record = RunRecord(
        run_id="r1",
        started_at="s",
        finished_at="f",
        project_tag="RootProgram",
        targets=(
            RunTargetRecord(
                target_name="RootProgram",
                is_library=False,
                analyzers=(
                    RunAnalyzerRecord(
                        key="variables",
                        name="Variable issues",
                        status="completed",
                        findings=(
                            AnalysisFinding(kind="unused", message="first", module_path=("RootProgram", "A", "One")),
                            AnalysisFinding(kind="unused", message="second", module_path=("RootProgram", "A", "Two")),
                        ),
                    ),
                ),
            ),
        ),
    )

    tree = app_textual_results_module._build_run_tree(record)

    assert tree is not None
    kind_node = next(iter(next(iter(tree.root.children[0].children)).children))
    root_branch = next(iter(kind_node.children))
    assert root_branch.label.plain == "RootProgram.A"
    assert [node.label.plain for node in root_branch.children] == ["One", "Two"]


def test_results_tree_groups_findings_by_module_across_analyzers() -> None:
    record = RunRecord(
        run_id="r1",
        started_at="s",
        finished_at="f",
        project_tag="RootProgram",
        targets=(
            RunTargetRecord(
                target_name="RootProgram",
                is_library=False,
                analyzers=(
                    RunAnalyzerRecord(
                        key="variables",
                        name="Variable issues",
                        status="completed",
                        findings=(
                            AnalysisFinding(kind="unused", message="m1", module_path=("RootProgram", "A")),
                            AnalysisFinding(kind="unused", message="m2", module_path=("RootProgram", "A", "Sub")),
                        ),
                    ),
                    RunAnalyzerRecord(
                        key="patterns",
                        name="Pattern checks",
                        status="completed",
                        findings=(
                            AnalysisFinding(kind="magic_number", message="m3", module_path=("RootProgram", "A")),
                        ),
                    ),
                ),
            ),
        ),
    )

    tree = app_textual_results_module._build_run_tree(record, group_by="module")

    assert tree is not None
    target_node = next(iter(tree.root.children))
    module_node = next(iter(target_node.children))
    assert module_node.data == "RootProgram.A"
    analyzer_nodes = [node for node in module_node.children if not isinstance(node.data, str)]
    assert [node.data.key for node in analyzer_nodes] == ["variables", "patterns"]
    variables_node, patterns_node = analyzer_nodes
    assert [node.label.plain for node in variables_node.children] == ["Unused variable (1)"]
    assert [node.label.plain for node in patterns_node.children] == ["Magic number (1)"]

    sub_module = next(node for node in module_node.children if node.data == "RootProgram.A.Sub")
    assert sub_module.label.plain == "Sub"
    sub_analyzers = list(sub_module.children)
    assert [node.data.key for node in sub_analyzers] == ["variables"]


def test_results_tree_module_grouping_lists_empty_analyzers_when_requested() -> None:
    record = RunRecord(
        run_id="r1",
        started_at="s",
        finished_at="f",
        project_tag="RootProgram",
        targets=(
            RunTargetRecord(
                target_name="RootProgram",
                is_library=False,
                analyzers=(
                    RunAnalyzerRecord(
                        key="variables",
                        name="Variable issues",
                        status="completed",
                        findings=(AnalysisFinding(kind="unused", message="m", module_path=("RootProgram",)),),
                    ),
                    RunAnalyzerRecord(key="sfc", name="SFC checks", status="completed", findings=()),
                ),
            ),
        ),
    )

    tree = app_textual_results_module._build_run_tree(record, group_by="module", show_empty_analyzers=True)

    assert tree is not None
    target_node = next(iter(tree.root.children))
    no_findings_node = next(node for node in target_node.children if node.label.plain == "No findings (1)")
    assert [node.data.key for node in no_findings_node.children] == ["sfc"]


def test_results_tree_module_grouping_auto_expands_single_child_chains() -> None:
    record = RunRecord(
        run_id="r1",
        started_at="s",
        finished_at="f",
        project_tag="RootProgram",
        targets=(
            RunTargetRecord(
                target_name="RootProgram",
                is_library=False,
                analyzers=(
                    RunAnalyzerRecord(
                        key="variables",
                        name="Variable issues",
                        status="completed",
                        findings=(AnalysisFinding(kind="unused", message="m", module_path=("RootProgram", "A", "B")),),
                    ),
                ),
            ),
        ),
    )

    tree = app_textual_results_module._build_run_tree(record, group_by="module")

    assert tree is not None
    target_node = next(iter(tree.root.children))
    module_node = next(iter(target_node.children))
    assert module_node.label.plain == "RootProgram.A.B"
    assert target_node.is_expanded is True
    assert module_node.is_expanded is True
