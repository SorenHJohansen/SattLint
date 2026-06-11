# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from sattlint import app

from ._app_menus_support import INVALID_SINGLE_FILE, VALID_SINGLE_FILE
from .helpers import named_object


@pytest.fixture
def noop_screen(monkeypatch):
    monkeypatch.setenv("SATTLINT_UI", "classic")
    monkeypatch.setattr(app, "clear_screen", lambda: None)
    monkeypatch.setattr(app, "pause", lambda: None)


def test_run_source_diff_report_aggregates_all_analysis_targets(noop_screen, monkeypatch, tmp_path):
    cfg = deepcopy(app.DEFAULT_CONFIG)
    cfg["program_dir"] = str(tmp_path)
    cfg["analyzed_programs_and_libraries"] = ["TargetA", "TargetB"]

    target_a_s = tmp_path / "TargetA.s"
    target_a_x = tmp_path / "TargetA.x"
    target_b_s = tmp_path / "TargetB.s"
    target_b_x = tmp_path / "TargetB.x"
    for path in (target_a_s, target_a_x, target_b_s, target_b_x):
        path.write_text("content", encoding="utf-8")

    target_a_bp = named_object("TargetA", origin_file="TargetA.s")
    target_b_bp = named_object("TargetB", origin_file="TargetB.x")
    graph = SimpleNamespace()

    monkeypatch.setattr(
        app,
        "_iter_loaded_projects",
        lambda _cfg: iter(
            [
                ("TargetA", target_a_bp, graph),
                ("TargetB", target_b_bp, graph),
            ]
        ),
    )

    def _source_paths(project_bp, _graph):
        if project_bp is target_a_bp:
            return {target_a_s}
        return {target_b_x}

    monkeypatch.setattr(app, "_source_paths_for_current_target", _source_paths)

    pair_calls: list[tuple[Path, Path]] = []

    def _build_pair_report(draft_file: Path, official_file: Path, *, workspace_root: Path):
        pair_calls.append((draft_file, official_file))
        return {
            "pair_name": draft_file.stem,
            "draft_file": draft_file.name,
            "official_file": official_file.name,
            "status": "ok",
            "classification": "structural",
            "changed": True,
            "parse_checks": {"draft_parse_ok": True, "official_parse_ok": True},
            "summary": {"addition_count": 1, "deletion_count": 1, "changed_line_count": 2},
            "diff": [f"--- {draft_file.name}", f"+++ {official_file.name}"],
            "errors": [],
        }

    rendered_reports: list[dict[str, Any]] = []

    monkeypatch.setattr(app.source_diff_report_module, "build_pair_report", _build_pair_report)
    monkeypatch.setattr(
        app.source_diff_report_module,
        "render_markdown",
        lambda report: rendered_reports.append(report) or "rendered source diff",
    )

    outputs: list[str] = []
    monkeypatch.setattr(app, "emit_output", lambda message: outputs.append(message))

    app.run_source_diff_report(cfg)

    assert pair_calls == [(target_a_s, target_a_x), (target_b_s, target_b_x)]
    assert rendered_reports[0]["summary"] == {
        "compared_pair_count": 2,
        "changed_pair_count": 2,
        "identical_pair_count": 0,
        "layout_only_pair_count": 0,
        "structural_pair_count": 2,
        "error_count": 0,
    }
    assert [pair["pair_name"] for pair in rendered_reports[0]["pairs"]] == ["TargetA", "TargetB"]
    assert outputs == ["rendered source diff"]


def test_run_source_diff_report_updates_live_status(noop_screen, monkeypatch, tmp_path):
    cfg = deepcopy(app.DEFAULT_CONFIG)
    cfg["program_dir"] = str(tmp_path)
    cfg["analyzed_programs_and_libraries"] = ["TargetA"]

    target_a_s = tmp_path / "TargetA.s"
    target_a_x = tmp_path / "TargetA.x"
    for path in (target_a_s, target_a_x):
        path.write_text("content", encoding="utf-8")

    target_a_bp = named_object("TargetA", origin_file="TargetA.s")
    graph = SimpleNamespace()
    updates: list[str] = []

    class FakeLiveStatusLine:
        def __enter__(self):
            return updates.append

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(app, "_iter_loaded_projects", lambda _cfg: iter([("TargetA", target_a_bp, graph)]))
    monkeypatch.setattr(app, "_source_paths_for_current_target", lambda _bp, _graph: {target_a_s})
    monkeypatch.setattr(app.console_module, "live_status_line", lambda: FakeLiveStatusLine())
    monkeypatch.setattr(
        app.source_diff_report_module,
        "build_pair_report",
        lambda draft_file, official_file, *, workspace_root: {
            "pair_name": draft_file.stem,
            "draft_file": draft_file.name,
            "official_file": official_file.name,
            "status": "ok",
            "classification": "identical",
            "changed": False,
            "parse_checks": {"draft_parse_ok": True, "official_parse_ok": True},
            "summary": {"addition_count": 0, "deletion_count": 0, "changed_line_count": 0},
            "diff": [],
            "errors": [],
        },
    )
    monkeypatch.setattr(app.source_diff_report_module, "render_markdown", lambda _report: "rendered source diff")
    monkeypatch.setattr(app, "emit_output", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(app, "pause", lambda: None)

    app.run_source_diff_report(cfg)

    assert updates == [
        "Source diff: resolving comparison pairs",
        "Source diff: collecting comparison pairs for TargetA",
        "Source diff: comparing 1/1 TargetA.s",
    ]


def test_force_refresh_ast_bypasses_file_ast_cache(monkeypatch):
    cfg = deepcopy(app.DEFAULT_CONFIG)
    cfg["analyzed_programs_and_libraries"] = ["TargetA", "TargetB"]
    cleared: list[str] = []
    load_calls: list[tuple[str | None, bool, bool, str, bool]] = []

    class _FakeCache:
        def __init__(self, *_args, **_kwargs):
            pass

        def clear(self, key: str) -> None:
            cleared.append(key)

    def fake_load_project(
        _cfg,
        target_name=None,
        *,
        use_cache=True,
        use_file_ast_cache=True,
        refresh_mode="full",
        collect_stage_timings=False,
    ):
        load_calls.append((target_name, use_cache, use_file_ast_cache, refresh_mode, collect_stage_timings))
        return ("bp", "graph")

    monkeypatch.setattr(app, "ASTCache", _FakeCache)
    monkeypatch.setattr(app, "get_cache_dir", lambda: Path("/tmp/cache"))
    monkeypatch.setattr(app, "load_project", fake_load_project)

    result = app.force_refresh_ast(cfg)

    assert len(cleared) == 2
    assert load_calls == [
        ("TargetA", False, False, "ast-only", False),
        ("TargetB", False, False, "ast-only", False),
    ]
    assert result == ("bp", "graph")


def test_refresh_analysis_caches_wrapper_passes_analysis_report_cache(monkeypatch):
    cfg = deepcopy(app.DEFAULT_CONFIG)
    seen: dict[str, object] = {}

    monkeypatch.setattr(app, "force_refresh_ast", lambda _cfg: ("bp", "graph"))
    monkeypatch.setattr(app, "get_cache_dir", lambda: Path("/tmp/cache"))

    def fake_refresh_analysis_caches(_cfg, **kwargs):
        seen.update(kwargs)
        return ("bp", "graph")

    monkeypatch.setattr(app.app_analysis, "refresh_analysis_caches", fake_refresh_analysis_caches)

    result = app.refresh_analysis_caches(cfg)

    assert seen["force_refresh_ast_fn"] is app.force_refresh_ast
    assert seen["analysis_report_cache_cls"] is app.AnalysisReportCache
    assert seen["get_cache_dir_fn"] is app.get_cache_dir
    assert seen["emit_output_fn"] is app.emit_output
    assert result == ("bp", "graph")


def test_show_help_mentions_setup_and_syntax_check(noop_screen, capsys):
    cfg = deepcopy(app.DEFAULT_CONFIG)

    app.show_help(cfg)

    out = capsys.readouterr().out
    assert "Open Setup" in out
    assert "syntax-check" in out
    assert "Tools" in out


def test_syntax_check_command_ok(tmp_path, capsys):
    source_file = tmp_path / "ValidProgram.s"
    source_file.write_text(VALID_SINGLE_FILE, encoding="utf-8")

    exit_code = app.main(["syntax-check", str(source_file)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out.strip() == "OK"
    assert captured.err == ""


def test_cli_entry_point_forwards_sys_argv_without_loading_ast(tmp_path, capsys, monkeypatch):
    source_file = tmp_path / "ValidProgram.s"
    source_file.write_text(VALID_SINGLE_FILE, encoding="utf-8")

    monkeypatch.setattr(app, "load_config", lambda *_: pytest.fail("load_config should not run"))
    monkeypatch.setattr(app, "ensure_ast_cache", lambda *_: pytest.fail("ensure_ast_cache should not run"))
    monkeypatch.setattr(app, "self_check", lambda *_: pytest.fail("self_check should not run"))
    monkeypatch.setattr(app.sys, "argv", ["sattlint", "syntax-check", str(source_file)])

    exit_code = app.cli()

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out.strip() == "OK"
    assert captured.err == ""


def test_main_starts_without_targets_and_skips_ast_cache(noop_screen, monkeypatch):
    cfg = deepcopy(app.DEFAULT_CONFIG)
    cfg["analyzed_programs_and_libraries"] = []
    calls = []

    monkeypatch.delenv("SATTLINT_UI", raising=False)
    monkeypatch.setattr(app, "load_config", lambda *_: (cfg, False))
    monkeypatch.setattr(app, "self_check", lambda *_: pytest.fail("textual startup should skip terminal self-check"))
    monkeypatch.setattr(
        app,
        "ensure_ast_cache",
        lambda *_: pytest.fail("textual startup should skip terminal AST cache preflight"),
    )
    monkeypatch.setattr(app, "run_interactive_session", lambda *_args, **_kwargs: calls.append("session"))

    exit_code = app.main()

    assert exit_code == 0
    assert calls == ["session"]


def test_main_blocks_target_dependent_menu_actions_without_targets(noop_screen, monkeypatch, capsys):
    cfg = deepcopy(app.DEFAULT_CONFIG)
    cfg["analyzed_programs_and_libraries"] = []
    calls: list[str] = []

    monkeypatch.delenv("SATTLINT_UI", raising=False)
    monkeypatch.setattr(app, "load_config", lambda *_: (cfg, False))
    monkeypatch.setattr(app, "self_check", lambda *_: pytest.fail("textual startup should skip terminal self-check"))
    monkeypatch.setattr(
        app,
        "ensure_ast_cache",
        lambda *_: pytest.fail("textual startup should skip terminal AST cache preflight"),
    )
    monkeypatch.setattr(
        app,
        "analysis_menu",
        lambda *_: pytest.fail("legacy analysis menu should not run during textual startup"),
    )
    monkeypatch.setattr(
        app,
        "dump_menu",
        lambda *_: pytest.fail("legacy dump menu should not run during textual startup"),
    )
    monkeypatch.setattr(
        app,
        "documentation_menu",
        lambda *_: pytest.fail("legacy documentation menu should not run during textual startup"),
    )
    monkeypatch.setattr(
        app,
        "force_refresh_ast",
        lambda *_: pytest.fail("legacy refresh action should not run during textual startup"),
    )
    monkeypatch.setattr(app, "run_interactive_session", lambda *_args, **_kwargs: calls.append("session"))

    exit_code = app.main()

    out = capsys.readouterr().out
    assert exit_code == 0
    assert calls == ["session"]
    assert out == ""


def test_syntax_check_command_reports_parse_error(tmp_path, capsys):
    source_file = tmp_path / "InvalidProgram.s"
    source_file.write_text(INVALID_SINGLE_FILE, encoding="utf-8")

    exit_code = app.main(["syntax-check", str(source_file)])

    captured = capsys.readouterr()
    assert exit_code != 0
    assert "ERROR [parse]" in captured.err
    assert "InvalidProgram.s" in captured.err
    assert "Expected one of:" in captured.err
    assert "^" in captured.err


def test_syntax_check_command_prints_warning_for_legacy_sequence_initstep(tmp_path, capsys):
    source_file = tmp_path / "LegacySequenceWarning.s"
    source_file.write_text(
        """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
	SEQUENCE DeleteListContent COORD 0.0, 0.0 OBJSIZE 1.0, 1.0
		SEQSTEP PutArray
		SEQTRANSITION WAIT_FOR True
		SEQSTEP ExtraScan
		ALTERNATIVESEQ
			SEQTRANSITION WAIT_FOR DeleteLineNumber <= ArrayLength
		ALTERNATIVEBRANCH
			SEQTRANSITION WAIT_FOR DeleteLineNumber > ArrayLength
			SEQINITSTEP standBy
			SEQTRANSITION WAIT_FOR DeleteListContent
		ENDALTERNATIVE
	ENDSEQUENCE
ENDDEF (*BasePicture*);
""",
        encoding="utf-8",
    )

    exit_code = app.main(["syntax-check", str(source_file)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out.strip() == "OK"
    assert "WARNING [validation]" in captured.err
    assert "must start with exactly one SEQINITSTEP" in captured.err


def test_syntax_check_command_rejects_missing_file(tmp_path, capsys):
    missing_file = tmp_path / "MissingProgram.s"

    exit_code = app.main(["syntax-check", str(missing_file)])

    captured = capsys.readouterr()
    assert exit_code != 0
    assert "File not found" in captured.err


def test_main_returns_error_for_unknown_cli_command(capsys):
    exit_code = app.main(["unknown-command"])

    captured = capsys.readouterr()
    assert exit_code != 0
    assert "usage:" in captured.err.lower()
