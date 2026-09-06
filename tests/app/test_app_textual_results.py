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
                                module_path=("RootProgram",),
                                severity="warning",
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
    finding_node = next(iter(analyzer_node.children))
    assert finding_node.data == record.targets[0].analyzers[0].findings[0]


def test_results_tree_returns_none_without_textual() -> None:
    original = app_textual_results_module._TEXTUAL_TREE
    app_textual_results_module._TEXTUAL_TREE = None
    try:
        record = RunRecord(run_id="r1", started_at="s", finished_at="f", project_tag="")
        assert app_textual_results_module._build_run_tree(record) is None
    finally:
        app_textual_results_module._TEXTUAL_TREE = original


def test_run_tree_title_includes_counts() -> None:
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

    title = app_textual_results_module._run_tree_title(record)

    assert "RootProgram" in title
    assert "1 targets" in title
    assert "1 issues" in title
