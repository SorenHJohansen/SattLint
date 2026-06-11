# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportArgumentType=false, reportIndexIssue=false
"""CLI behavior tests for SattLint."""

import runpy
from collections.abc import Mapping
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

import sattlint
from sattlint import _app_startup, app, app_base, engine
from sattlint.cli import entry as cli_entry
from sattlint.models import IssueKind
from sattlint.models.project_graph import ProjectGraph


def _run_base_cli(argv: list[str], **overrides) -> int:
    kwargs = {
        "config_path": app.CONFIG_PATH,
        "load_config_fn": lambda path: ({"debug": False}, False),
        "apply_debug_fn": lambda _cfg: None,
        "run_validate_config_command_fn": lambda cfg, *, config_path, default_used: app_base.EXIT_SUCCESS,
        "run_analyze_command_fn": lambda cfg, *, selected_keys, selected_issue_kinds=None, use_cache: (
            app_base.EXIT_SUCCESS
        ),
        "run_simulate_command_fn": (
            lambda cfg, *, target_path, module_name, mode, max_scans, output_format, output_path, use_cache: (
                app_base.EXIT_SUCCESS
            )
        ),
        "run_docgen_command_fn": lambda cfg, *, use_cache, output_dir, output_path: app_base.EXIT_SUCCESS,
        "run_cache_prune_command_fn": lambda *, cache_dir: app_base.EXIT_SUCCESS,
        "run_telemetry_summary_command_fn": (
            lambda cfg, *, config_path, output_format, output_path: app_base.EXIT_SUCCESS
        ),
        "run_format_icf_command_fn": lambda cfg, *, check: app_base.EXIT_SUCCESS,
    }
    kwargs.update(overrides)
    return app_base.run_cli(list(argv), **kwargs)


def test_build_cli_parser_has_descriptions():
    parser = app_base.build_cli_parser()

    assert parser.description
    action = next(action for action in parser._actions if isinstance(getattr(action, "choices", None), Mapping))
    choices = cast(dict[str, object], action.choices)
    syntax_parser = choices["syntax-check"]
    assert {
        "syntax-check",
        "analyze",
        "simulate",
        "docgen",
        "cache-prune",
        "telemetry-summary",
        "validate-config",
        "format-icf",
        "source-diff",
        "repo-audit",
    } <= set(choices)
    assert getattr(syntax_parser, "description", None)


def test_build_cli_parser_repo_audit_includes_dedicated_options():
    parser = app_base.build_cli_parser()

    action = next(action for action in parser._actions if isinstance(getattr(action, "choices", None), Mapping))
    choices = cast(dict[str, object], action.choices)
    repo_audit_parser = cast(Any, choices["repo-audit"])
    option_strings = {
        option
        for parser_action in repo_audit_parser._actions
        for option in getattr(parser_action, "option_strings", [])
    }

    assert {"--profile", "--fail-on", "--list-checks", "--planning-context"} <= option_strings


def test_build_cli_parser_exposes_interactive_ui_override():
    parser = app_base.build_cli_parser()

    option_strings = {
        option for parser_action in parser._actions for option in getattr(parser_action, "option_strings", [])
    }

    assert "--ui" in option_strings


def test_run_cli_without_command_returns_usage_error():
    assert _run_base_cli([]) == app_base.EXIT_USAGE_ERROR


def test_startup_main_routes_cli_argv_to_run_cli() -> None:
    seen: dict[str, object] = {}

    exit_code = _app_startup.main(
        ["analyze", "--check", "variables"],
        run_cli_fn=lambda argv: seen.update({"argv": argv}) or 13,
        load_config_fn=lambda _path: pytest.fail("load_config should not run for CLI argv"),
        config_path=Path("config.toml"),
        apply_debug_fn=lambda _cfg: None,
        emit_output_fn=lambda *_args: None,
        pause_fn=lambda: None,
        self_check_fn=lambda _cfg: True,
        confirm_fn=lambda _message: True,
        has_analyzed_targets_fn=lambda _cfg: False,
        ensure_ast_cache_fn=lambda _cfg: True,
        run_main_loop_fn=lambda *_args, **_kwargs: pytest.fail("interactive loop should not run for CLI argv"),
        clear_screen_fn=lambda: None,
        print_menu_fn=lambda *_args, **_kwargs: None,
        menu_option_factory=lambda key, label, description: (key, label, description),
        summarize_targets_fn=lambda _cfg: "targets",
        require_targets_for_menu_action_fn=lambda _cfg, _action: True,
        analysis_menu_fn=lambda _cfg: None,
        documentation_menu_fn=lambda _cfg: True,
        config_menu_fn=lambda _cfg: True,
        tools_menu_fn=lambda _cfg: None,
        show_help_fn=lambda _cfg: None,
        save_config_fn=lambda _path, _cfg: None,
        quit_app_fn=lambda: None,
        quit_app_error=RuntimeError,
    )

    assert exit_code == 13
    assert seen == {"argv": ["analyze", "--check", "variables"]}


def test_startup_main_routes_debug_only_cli_argv_to_interactive_loop() -> None:
    seen: dict[str, object] = {}
    cfg = {"debug": False}
    parser = _FakeParser(
        args=SimpleNamespace(command=None, config=None, no_cache=False, quiet=False, debug=True),
    )

    exit_code = _app_startup.main(
        ["--debug"],
        run_cli_fn=lambda _argv: pytest.fail("run_cli should not run for interactive debug-only argv"),
        build_cli_parser_fn=lambda: parser,
        load_config_fn=lambda _path: (cfg, False),
        config_path=Path("config.toml"),
        apply_debug_fn=lambda local_cfg: seen.update({"apply_debug_cfg": dict(local_cfg)}),
        emit_output_fn=lambda *_args: None,
        pause_fn=lambda: None,
        self_check_fn=lambda _cfg: True,
        confirm_fn=lambda _message: True,
        has_analyzed_targets_fn=lambda _cfg: False,
        ensure_ast_cache_fn=lambda _cfg: True,
        run_main_loop_fn=lambda local_cfg, **kwargs: seen.update(
            {"main_loop_cfg": dict(local_cfg), "main_loop_kwargs": kwargs}
        ),
        clear_screen_fn=lambda: None,
        print_menu_fn=lambda *_args, **_kwargs: None,
        menu_option_factory=lambda key, label, description: (key, label, description),
        summarize_targets_fn=lambda _cfg: "targets",
        require_targets_for_menu_action_fn=lambda _cfg, _action: True,
        analysis_menu_fn=lambda _cfg: None,
        documentation_menu_fn=lambda _cfg: True,
        config_menu_fn=lambda _cfg: True,
        tools_menu_fn=lambda _cfg: None,
        show_help_fn=lambda _cfg: None,
        save_config_fn=lambda _path, _cfg: None,
        quit_app_fn=lambda: None,
        quit_app_error=RuntimeError,
    )

    assert exit_code == 0
    assert seen["apply_debug_cfg"] == {"debug": True}
    assert seen["main_loop_cfg"] == {"debug": True}
    assert seen["main_loop_kwargs"]["config_path"] == Path("config.toml")
    assert "choose_menu_option_fn" not in cast(dict[str, object], seen["main_loop_kwargs"])
    assert "interaction" not in cast(dict[str, object], seen["main_loop_kwargs"])


def test_startup_main_routes_ui_only_cli_argv_to_interactive_loop() -> None:
    seen: dict[str, object] = {}
    cfg = {"debug": False}
    parser = _FakeParser(
        args=SimpleNamespace(command=None, config=None, no_cache=False, quiet=False, debug=False, ui="textual"),
    )

    exit_code = _app_startup.main(
        ["--ui", "textual"],
        run_cli_fn=lambda _argv: pytest.fail("run_cli should not run for interactive ui-only argv"),
        build_cli_parser_fn=lambda: parser,
        load_config_fn=lambda _path: (cfg, False),
        config_path=Path("config.toml"),
        apply_debug_fn=lambda local_cfg: seen.update({"apply_debug_cfg": dict(local_cfg)}),
        emit_output_fn=lambda *_args: None,
        pause_fn=lambda: None,
        self_check_fn=lambda _cfg: True,
        confirm_fn=lambda _message: True,
        has_analyzed_targets_fn=lambda _cfg: False,
        ensure_ast_cache_fn=lambda _cfg: True,
        run_main_loop_fn=lambda local_cfg, **kwargs: seen.update(
            {"main_loop_cfg": dict(local_cfg), "main_loop_kwargs": kwargs}
        ),
        clear_screen_fn=lambda: None,
        print_menu_fn=lambda *_args, **_kwargs: None,
        menu_option_factory=lambda key, label, description: (key, label, description),
        summarize_targets_fn=lambda _cfg: "targets",
        require_targets_for_menu_action_fn=lambda _cfg, _action: True,
        analysis_menu_fn=lambda _cfg: None,
        documentation_menu_fn=lambda _cfg: True,
        config_menu_fn=lambda _cfg: True,
        tools_menu_fn=lambda _cfg: None,
        show_help_fn=lambda _cfg: None,
        save_config_fn=lambda _path, _cfg: None,
        quit_app_fn=lambda: None,
        quit_app_error=RuntimeError,
    )

    assert exit_code == 0
    assert seen["apply_debug_cfg"] == {"debug": False}
    assert seen["main_loop_cfg"] == {"debug": False}
    assert seen["main_loop_kwargs"]["config_path"] == Path("config.toml")


def test_startup_main_defaults_plain_interactive_session_to_textual() -> None:
    seen: dict[str, object] = {}
    cfg = {"debug": False}

    exit_code = _app_startup.main(
        None,
        run_cli_fn=lambda _argv: pytest.fail("run_cli should not run for plain interactive startup"),
        load_config_fn=lambda _path: (cfg, False),
        config_path=Path("config.toml"),
        apply_debug_fn=lambda local_cfg: seen.update({"apply_debug_cfg": dict(local_cfg)}),
        resolve_interactive_ui_mode_fn=lambda _cfg, override: seen.update({"resolved_override": override}) or "textual",
        set_interactive_ui_mode_fn=lambda mode: seen.update({"ui_mode": mode}),
        reset_interactive_ui_mode_fn=lambda: seen.update({"reset_called": True}),
        emit_output_fn=lambda *_args: None,
        pause_fn=lambda: None,
        self_check_fn=lambda _cfg: pytest.fail("textual startup should skip terminal self-check preflight"),
        confirm_fn=lambda _message: pytest.fail("textual startup should not prompt for self-check confirmation"),
        has_analyzed_targets_fn=lambda _cfg: False,
        ensure_ast_cache_fn=lambda _cfg: pytest.fail("textual startup should skip terminal AST cache refresh"),
        run_main_loop_fn=lambda local_cfg, **kwargs: seen.update(
            {"main_loop_cfg": dict(local_cfg), "main_loop_kwargs": kwargs}
        ),
        clear_screen_fn=lambda: None,
        print_menu_fn=lambda *_args, **_kwargs: None,
        menu_option_factory=lambda key, label, description: (key, label, description),
        summarize_targets_fn=lambda _cfg: "targets",
        require_targets_for_menu_action_fn=lambda _cfg, _action: True,
        analysis_menu_fn=lambda _cfg: None,
        documentation_menu_fn=lambda _cfg: True,
        config_menu_fn=lambda _cfg: True,
        tools_menu_fn=lambda _cfg: None,
        show_help_fn=lambda _cfg: None,
        save_config_fn=lambda _path, _cfg: None,
        quit_app_fn=lambda: None,
        quit_app_error=RuntimeError,
    )

    assert exit_code == 0
    assert seen["apply_debug_cfg"] == {"debug": False}
    assert seen["resolved_override"] is None
    assert seen["ui_mode"] == "textual"
    assert seen["reset_called"] is True
    assert seen["main_loop_cfg"] == {"debug": False}
    assert seen["main_loop_kwargs"]["config_path"] == Path("config.toml")
    assert seen["main_loop_kwargs"]["quit_app_error"] is RuntimeError


def test_startup_main_textual_launch_skips_terminal_preflight_for_targets() -> None:
    seen: dict[str, object] = {}
    cfg = {"debug": False}

    exit_code = _app_startup.main(
        None,
        run_cli_fn=lambda _argv: pytest.fail("run_cli should not run for plain interactive startup"),
        load_config_fn=lambda _path: (cfg, False),
        config_path=Path("config.toml"),
        apply_debug_fn=lambda _cfg: None,
        resolve_interactive_ui_mode_fn=lambda _cfg, _override: "textual",
        set_interactive_ui_mode_fn=lambda mode: seen.update({"ui_mode": mode}),
        reset_interactive_ui_mode_fn=lambda: seen.update({"reset_called": True}),
        emit_output_fn=lambda *_args: None,
        pause_fn=lambda: pytest.fail("textual startup should not pause for AST cache preflight"),
        self_check_fn=lambda _cfg: pytest.fail("textual startup should skip terminal self-check preflight"),
        confirm_fn=lambda _message: pytest.fail("textual startup should not prompt before launch"),
        has_analyzed_targets_fn=lambda _cfg: True,
        ensure_ast_cache_fn=lambda _cfg: pytest.fail("textual startup should skip terminal AST cache refresh"),
        run_main_loop_fn=lambda local_cfg, **kwargs: seen.update(
            {"main_loop_cfg": dict(local_cfg), "main_loop_kwargs": kwargs}
        ),
        clear_screen_fn=lambda: None,
        print_menu_fn=lambda *_args, **_kwargs: None,
        menu_option_factory=lambda key, label, description: (key, label, description),
        summarize_targets_fn=lambda _cfg: "targets",
        require_targets_for_menu_action_fn=lambda _cfg, _action: True,
        analysis_menu_fn=lambda _cfg: None,
        documentation_menu_fn=lambda _cfg: True,
        config_menu_fn=lambda _cfg: True,
        tools_menu_fn=lambda _cfg: None,
        show_help_fn=lambda _cfg: None,
        save_config_fn=lambda _path, _cfg: None,
        quit_app_fn=lambda: None,
        quit_app_error=RuntimeError,
    )

    assert exit_code == 0
    assert seen["ui_mode"] == "textual"
    assert seen["reset_called"] is True
    assert seen["main_loop_cfg"] == {"debug": False}


def test_startup_main_warns_and_pauses_for_default_config() -> None:
    seen: dict[str, object] = {"paused": 0}
    cfg = {"debug": False}

    exit_code = _app_startup.main(
        None,
        run_cli_fn=lambda _argv: 99,
        load_config_fn=lambda _path: (cfg, True),
        config_path=Path("config.toml"),
        apply_debug_fn=lambda local_cfg: seen.update({"debug_cfg": local_cfg}),
        emit_output_fn=lambda message: seen.update({"message": message}),
        pause_fn=lambda: seen.update({"paused": cast(int, seen["paused"]) + 1}),
        self_check_fn=lambda _cfg: pytest.fail("self-check should not run for default config"),
        confirm_fn=lambda _message: True,
        has_analyzed_targets_fn=lambda _cfg: False,
        ensure_ast_cache_fn=lambda _cfg: True,
        run_main_loop_fn=lambda local_cfg, **kwargs: seen.update(
            {"main_loop_cfg": local_cfg, "main_loop_kwargs": kwargs}
        ),
        clear_screen_fn=lambda: None,
        print_menu_fn=lambda *_args, **_kwargs: None,
        menu_option_factory=lambda key, label, description: (key, label, description),
        summarize_targets_fn=lambda _cfg: "targets",
        require_targets_for_menu_action_fn=lambda _cfg, _action: True,
        analysis_menu_fn=lambda _cfg: None,
        documentation_menu_fn=lambda _cfg: True,
        config_menu_fn=lambda _cfg: True,
        tools_menu_fn=lambda _cfg: None,
        show_help_fn=lambda _cfg: None,
        save_config_fn=lambda _path, _cfg: None,
        quit_app_fn=lambda: None,
        quit_app_error=RuntimeError,
    )

    assert exit_code == 0
    assert seen["debug_cfg"] is cfg
    assert seen["message"] == "Warning: Default config created. Open Setup before running analysis."
    assert seen["paused"] == 1
    assert seen["main_loop_cfg"] is cfg
    assert "choose_menu_option_fn" not in cast(dict[str, object], seen["main_loop_kwargs"])
    assert "interaction" not in cast(dict[str, object], seen["main_loop_kwargs"])


def test_startup_main_handles_quit_app_error() -> None:
    class QuitSignalError(Exception):
        pass

    exit_code = _app_startup.main(
        None,
        run_cli_fn=lambda _argv: 99,
        load_config_fn=lambda _path: ({"debug": False}, False),
        config_path=Path("config.toml"),
        apply_debug_fn=lambda _cfg: None,
        emit_output_fn=lambda *_args: None,
        pause_fn=lambda: None,
        self_check_fn=lambda _cfg: True,
        confirm_fn=lambda _message: True,
        has_analyzed_targets_fn=lambda _cfg: False,
        ensure_ast_cache_fn=lambda _cfg: True,
        run_main_loop_fn=lambda *_args, **_kwargs: (_ for _ in ()).throw(QuitSignalError()),
        clear_screen_fn=lambda: None,
        print_menu_fn=lambda *_args, **_kwargs: None,
        menu_option_factory=lambda key, label, description: (key, label, description),
        summarize_targets_fn=lambda _cfg: "targets",
        require_targets_for_menu_action_fn=lambda _cfg, _action: True,
        analysis_menu_fn=lambda _cfg: None,
        documentation_menu_fn=lambda _cfg: True,
        config_menu_fn=lambda _cfg: True,
        tools_menu_fn=lambda _cfg: None,
        show_help_fn=lambda _cfg: None,
        save_config_fn=lambda _path, _cfg: None,
        quit_app_fn=lambda: None,
        quit_app_error=QuitSignalError,
    )

    assert exit_code == 0


def test_startup_wrapper_helpers_delegate_to_owner_functions() -> None:
    run_cli_seen: dict[str, object] = {}
    telemetry_seen: dict[str, object] = {}
    validate_seen: dict[str, object] = {}
    analyze_seen: dict[str, object] = {}
    simulate_seen: dict[str, object] = {}
    docgen_seen: dict[str, object] = {}
    misc_seen: dict[str, object] = {}
    cfg = {"debug": False}
    project = ("Root", cast(Any, object()), ProjectGraph())

    assert (
        _app_startup.run_cli(
            ["analyze"],
            run_cli_owner_fn=lambda argv, **kwargs: run_cli_seen.update({"argv": argv, **kwargs}) or 17,
            config_path=Path("config.toml"),
            build_cli_parser_fn=lambda: object(),
            run_syntax_check_command_fn=lambda _path: 0,
            load_config_fn=lambda _path: (cfg, False),
            apply_debug_fn=lambda _cfg: None,
            run_validate_config_command_fn=lambda *_args, **_kwargs: 0,
            run_analyze_command_fn=lambda *_args, **_kwargs: 0,
            run_simulate_command_fn=lambda *_args, **_kwargs: 0,
            run_docgen_command_fn=lambda *_args, **_kwargs: 0,
            run_telemetry_summary_command_fn=lambda *_args, **_kwargs: 0,
            run_format_icf_command_fn=lambda *_args, **_kwargs: 0,
            exit_success=0,
            exit_usage_error=2,
        )
        == 17
    )
    assert run_cli_seen["argv"] == ["analyze"]

    assert (
        _app_startup.run_telemetry_summary_command(
            cfg,
            config_path=Path("config.toml"),
            output_format="json",
            output_path="summary.json",
            run_telemetry_summary_command_fn=lambda local_cfg, **kwargs: (
                telemetry_seen.update({"cfg": local_cfg, **kwargs}) or 19
            ),
            telemetry_output_path_fn=lambda path: path.with_suffix(".telemetry.json"),
            summarize_telemetry_fn=lambda _path: {"events": 1},
            render_text_summary_fn=lambda summary: str(summary),
            exit_success=0,
            exit_usage_error=2,
        )
        == 19
    )
    assert telemetry_seen["cfg"] is cfg

    assert (
        _app_startup.run_validate_config_command(
            cfg,
            config_path=Path("config.toml"),
            default_used=True,
            run_validate_config_command_fn=lambda local_cfg, **kwargs: (
                validate_seen.update({"cfg": local_cfg, **kwargs}) or 23
            ),
            validate_config_fn=lambda _cfg: SimpleNamespace(passed=True),
            exit_success=0,
            exit_usage_error=2,
        )
        == 23
    )
    assert validate_seen["cfg"] is cfg

    assert (
        _app_startup.run_analyze_command(
            cfg,
            selected_keys=["variables"],
            use_cache=False,
            run_analyze_command_fn=lambda local_cfg, **kwargs: analyze_seen.update({"cfg": local_cfg, **kwargs}) or 29,
            run_checks_owner_fn=lambda local_cfg, selected_keys, **kwargs: analyze_seen.update(
                {
                    "run_checks_cfg": local_cfg,
                    "run_checks_selected_keys": selected_keys,
                    "nested_projects": list(kwargs["iter_loaded_projects_fn"]({"debug": False})),
                    "enabled_keys": kwargs["get_enabled_analyzers_fn"](),
                }
            ),
            iter_loaded_projects_fn=lambda _cfg, use_cache: iter([project] if not use_cache else []),
            get_selectable_analyzers_fn=lambda: ["selected"],
            get_enabled_analyzers_fn=lambda: ["enabled"],
            target_is_library_fn=lambda _cfg, _bp, _graph: False,
            exit_success=0,
        )
        == 29
    )
    cast(Any, analyze_seen["run_checks_fn"])(cfg, ["variables"], False)
    assert analyze_seen["run_checks_selected_keys"] == ["variables"]
    assert analyze_seen["nested_projects"] == [project]
    assert analyze_seen["enabled_keys"] == ["selected"]

    assert (
        _app_startup.run_simulate_command(
            cfg,
            target_path="program.s",
            module_name="Main",
            mode="steady-state",
            max_scans=5,
            output_format="json",
            output_path="simulation.json",
            use_cache=True,
            run_simulate_command_fn=lambda local_cfg, **kwargs: (
                simulate_seen.update({"cfg": local_cfg, **kwargs}) or 31
            ),
            simulate_fn=lambda *_args, **_kwargs: object(),
            exit_success=0,
            exit_usage_error=2,
        )
        == 31
    )
    assert simulate_seen["module_name"] == "Main"

    assert (
        _app_startup.run_docgen_command(
            cfg,
            use_cache=False,
            output_dir="docs",
            output_path=None,
            run_docgen_command_fn=lambda local_cfg, **kwargs: docgen_seen.update({"cfg": local_cfg, **kwargs}) or 37,
            iter_loaded_projects_fn=lambda _cfg, use_cache: iter([project] if not use_cache else []),
            documentation_unit_selection_fn=lambda: {"mode": "all"},
            exit_success=0,
            exit_usage_error=2,
        )
        == 37
    )
    assert list(cast(Any, docgen_seen["iter_loaded_projects_fn"])(cfg, False)) == [project]

    _app_startup.run_icf_formatter(
        cfg,
        run_format_icf_command_fn=lambda local_cfg: misc_seen.update({"icf_cfg": local_cfg}) or 0,
        pause_fn=lambda: misc_seen.update({"paused": True}),
    )
    _app_startup.show_config(
        cfg,
        show_config_fn=lambda local_cfg, **kwargs: misc_seen.update({"show_config_cfg": local_cfg, **kwargs}),
        get_graphics_rules_path_fn=lambda: Path("graphics.json"),
        load_graphics_rules_fn=lambda path=None: ({"rules": []}, False),
        graphics_rule_config_line_fn=lambda _rule: "line",
    )
    _app_startup.print_menu(
        "Menu",
        [("1", "One")],
        intro="Intro",
        note="Note",
        print_menu_owner_fn=lambda title, options, **kwargs: misc_seen.update(
            {"menu_title": title, "menu_options": options, **kwargs}
        ),
        print_fn=lambda *_args: None,
    )
    assert (
        _app_startup.summarize_targets(
            cfg,
            summarize_targets_fn=lambda local_cfg, **kwargs: (
                misc_seen.update({"summarize_cfg": local_cfg, **kwargs}) or "targets"
            ),
            get_analyzed_targets_fn=lambda _cfg: ["Root"],
        )
        == "targets"
    )
    _app_startup.show_help(
        cfg,
        show_help_fn=lambda local_cfg, **kwargs: misc_seen.update({"show_help_cfg": local_cfg, **kwargs}),
        clear_screen_fn=lambda: None,
        get_analyzed_targets_fn=lambda _cfg: ["Root"],
        summarize_targets_fn=lambda _cfg: "targets",
        print_fn=lambda *_args: None,
        pause_fn=lambda: None,
    )

    def dump_target_is_library(_cfg: object, _project_bp: object, _graph: object) -> bool:
        return False

    _app_startup.dump_menu(
        cfg,
        dump_menu_fn=lambda local_cfg, **kwargs: misc_seen.update({"dump_cfg": local_cfg, **kwargs}),
        clear_screen_fn=lambda: None,
        print_menu_fn=lambda *_args, **_kwargs: None,
        menu_option_factory=lambda key, label, description: (key, label, description),
        quit_app_fn=lambda: None,
        confirm_fn=lambda _message: True,
        iter_loaded_projects_fn=lambda *_args, **_kwargs: iter([project]),
        target_is_library_fn=dump_target_is_library,
        analyze_variables_fn=lambda *_args, **_kwargs: None,
    )
    assert (
        _app_startup.config_menu(
            cfg,
            config_menu_fn=lambda local_cfg, **kwargs: misc_seen.update({"config_cfg": local_cfg, **kwargs}) or True,
            config_path=Path("config.toml"),
            clear_screen_fn=lambda: None,
            show_config_fn=lambda _cfg: None,
            print_menu_fn=lambda *_args, **_kwargs: None,
            menu_option_factory=lambda key, label, description: (key, label, description),
            prompt_fn=lambda _message, default=None: default or "value",
            pause_fn=lambda: None,
            confirm_fn=lambda _message: True,
            target_exists_fn=lambda _target, _cfg: True,
            save_config_fn=lambda _path, _cfg: None,
            apply_debug_fn=lambda _cfg: None,
            graphics_rules_menu_fn=lambda _cfg: None,
            quit_app_fn=lambda: None,
        )
        is True
    )

    def run_source_diff_report(_cfg: object) -> None:
        return None

    _app_startup.tools_menu(
        cfg,
        tools_menu_fn=lambda local_cfg, **kwargs: misc_seen.update({"tools_cfg": local_cfg, **kwargs}),
        clear_screen_fn=lambda: None,
        print_menu_fn=lambda *_args, **_kwargs: None,
        menu_option_factory=lambda key, label, description: (key, label, description),
        quit_app_fn=lambda: None,
        self_check_fn=lambda _cfg: True,
        pause_fn=lambda: None,
        require_targets_for_menu_action_fn=lambda _cfg, _action: True,
        dump_menu_fn=lambda _cfg: None,
        run_source_diff_report_fn=run_source_diff_report,
        confirm_fn=lambda _message: True,
        force_refresh_ast_fn=lambda _cfg: None,
    )

    assert misc_seen["icf_cfg"] is cfg
    assert misc_seen["paused"] is True
    assert misc_seen["menu_title"] == "Menu"
    assert misc_seen["summarize_cfg"] is cfg
    assert misc_seen["target_is_library_fn"] is dump_target_is_library
    assert misc_seen["run_source_diff_report_fn"] is run_source_diff_report


def test_package_exports_version():
    assert sattlint.__version__ == "0.1.1"


def test_package_root_exports_forward_workspace_helpers(monkeypatch):
    discovery = SimpleNamespace(tag="discovery")
    snapshot = SimpleNamespace(tag="snapshot")
    seen = {}

    def fake_discover_workspace_sources(workspace_root):
        seen["workspace_root"] = workspace_root
        return discovery

    def fake_load_workspace_snapshot(entry_file, **kwargs):
        seen["entry_file"] = entry_file
        seen["kwargs"] = kwargs
        return snapshot

    monkeypatch.setattr(sattlint, "_discover_workspace_sources", fake_discover_workspace_sources)
    monkeypatch.setattr(sattlint, "_load_workspace_snapshot", fake_load_workspace_snapshot)

    workspace_root = Path("workspace")
    entry_file = Path("program.s")
    result_discovery = sattlint.discover_workspace_sources(workspace_root)
    result_snapshot = sattlint.load_workspace_snapshot(
        entry_file,
        workspace_root=workspace_root,
        discovery=cast(Any, discovery),
        mode="strict",
        other_lib_dirs=[Path("lib")],
        abb_lib_dir=Path("abb"),
        scan_root_only=True,
        debug=True,
        collect_variable_diagnostics=False,
    )

    assert result_discovery is discovery
    assert result_snapshot is snapshot
    assert seen["workspace_root"] == workspace_root
    assert seen["entry_file"] == entry_file
    assert seen["kwargs"]["workspace_root"] == workspace_root
    assert seen["kwargs"]["discovery"] is discovery
    assert seen["kwargs"]["mode"] == "strict"
    assert seen["kwargs"]["other_lib_dirs"] == [Path("lib")]
    assert seen["kwargs"]["abb_lib_dir"] == Path("abb")
    assert seen["kwargs"]["scan_root_only"] is True
    assert seen["kwargs"]["debug"] is True
    assert seen["kwargs"]["collect_variable_diagnostics"] is False
    assert seen["kwargs"]["_analysis_provider"] is sattlint.build_variable_semantic_artifacts


def test_module_entrypoint_exits_with_cli_status(monkeypatch):
    monkeypatch.setattr(app, "cli", lambda: 7)

    with pytest.raises(SystemExit, match="7") as exc_info:
        runpy.run_module("sattlint.__main__", run_name="__main__")

    assert exc_info.value.code == 7


def test_run_cli_version_flag(capsys):
    assert _run_base_cli(["--version"]) == app_base.EXIT_SUCCESS

    captured = capsys.readouterr()
    assert captured.out.strip() == f"sattlint {sattlint.__version__}"
    assert captured.err == ""


def test_run_cli_validate_config_uses_custom_path(monkeypatch):
    seen = {}

    exit_code = _run_base_cli(
        ["--config", "custom.toml", "validate-config"],
        load_config_fn=lambda path: ({"debug": False}, False),
        apply_debug_fn=lambda _cfg: None,
        run_validate_config_command_fn=lambda cfg, *, config_path, default_used: (
            seen.update({"cfg": cfg, "config_path": config_path, "default_used": default_used}) or app_base.EXIT_SUCCESS
        ),
    )

    assert exit_code == app_base.EXIT_SUCCESS
    assert str(seen["config_path"]).endswith("custom.toml")
    assert seen["default_used"] is False


def test_run_cli_analyze_passes_flags():
    seen = {}

    exit_code = _run_base_cli(
        [
            "--debug",
            "--no-cache",
            "analyze",
            "--check",
            "variables",
            "--check",
            "shadowing",
            "--issue-kind",
            "unused",
            "--issue-kind",
            "shadowing",
        ],
        load_config_fn=lambda path: ({"debug": False}, False),
        apply_debug_fn=lambda _cfg: None,
        run_analyze_command_fn=lambda cfg, *, selected_keys, selected_issue_kinds, use_cache: (
            seen.update(
                {
                    "cfg": cfg,
                    "selected_keys": selected_keys,
                    "selected_issue_kinds": selected_issue_kinds,
                    "use_cache": use_cache,
                }
            )
            or app_base.EXIT_SUCCESS
        ),
    )

    assert exit_code == app_base.EXIT_SUCCESS
    assert seen["selected_keys"] == ["variables", "shadowing"]
    assert seen["selected_issue_kinds"] == frozenset({"unused", "shadowing"})
    assert seen["use_cache"] is False
    assert cast(dict[str, Any], seen["cfg"])["debug"] is True


def test_run_cli_analyze_passes_opt_in_state_inference_key():
    seen = {}

    exit_code = cli_entry.run_cli(
        ["analyze", "--check", "state-inference"],
        config_path=app.CONFIG_PATH,
        load_config_fn=lambda path: ({"debug": False}, False),
        apply_debug_fn=lambda _cfg: None,
        run_validate_config_command_fn=lambda cfg, *, config_path, default_used: app_base.EXIT_SUCCESS,
        run_analyze_command_fn=lambda cfg, *, selected_keys, selected_issue_kinds=None, use_cache: (
            seen.update(
                {
                    "cfg": cfg,
                    "selected_keys": selected_keys,
                    "selected_issue_kinds": selected_issue_kinds,
                    "use_cache": use_cache,
                }
            )
            or app_base.EXIT_SUCCESS
        ),
        run_docgen_command_fn=lambda cfg, *, use_cache, output_dir, output_path: app_base.EXIT_SUCCESS,
        run_format_icf_command_fn=lambda cfg, *, check: app_base.EXIT_SUCCESS,
    )

    assert exit_code == app_base.EXIT_SUCCESS
    assert seen["selected_keys"] == ["state-inference"]
    assert seen["selected_issue_kinds"] is None
    assert seen["use_cache"] is True


def test_run_cli_analyze_list_checks_prints_selectable_keys(monkeypatch, capsys):
    monkeypatch.setattr(
        "sattlint.analyzers.registry.get_selectable_analyzers",
        lambda: [SimpleNamespace(key="variables"), SimpleNamespace(key="timing")],
    )

    exit_code = cli_entry.run_cli(
        ["analyze", "--list-checks"],
        config_path=Path("config.toml"),
    )

    captured = capsys.readouterr()
    assert exit_code == app_base.EXIT_SUCCESS
    assert captured.out.splitlines() == ["variables", "timing"]
    assert captured.err == ""


def test_run_cli_analyze_list_issue_kinds_prints_values_without_loading_config(capsys):
    exit_code = cli_entry.run_cli(
        ["analyze", "--list-issue-kinds"],
        config_path=Path("config.toml"),
        load_config_fn=lambda _path: pytest.fail("load_config should not run for --list-issue-kinds"),
        apply_debug_fn=lambda _cfg: pytest.fail("apply_debug should not run for --list-issue-kinds"),
    )

    captured = capsys.readouterr()
    assert exit_code == app_base.EXIT_SUCCESS
    assert captured.out.splitlines() == [issue_kind.value for issue_kind in IssueKind]
    assert captured.err == ""


def test_run_cli_simulate_passes_flags():
    seen = {}

    exit_code = _run_base_cli(
        [
            "--no-cache",
            "simulate",
            "tests/fixtures/sample_sattline_files/Program/Main.s",
            "--module",
            "Main",
            "--mode",
            "steady-state",
            "--max-scans",
            "25",
            "--format",
            "json",
            "--output",
            "simulation.json",
        ],
        load_config_fn=lambda path: ({"debug": False}, False),
        apply_debug_fn=lambda _cfg: None,
        run_simulate_command_fn=lambda cfg, *, target_path, module_name, mode, max_scans, output_format, output_path, use_cache: (
            seen.update(
                {
                    "cfg": cfg,
                    "target_path": target_path,
                    "module_name": module_name,
                    "mode": mode,
                    "max_scans": max_scans,
                    "output_format": output_format,
                    "output_path": output_path,
                    "use_cache": use_cache,
                }
            )
            or app_base.EXIT_SUCCESS
        ),
    )

    assert exit_code == app_base.EXIT_SUCCESS
    assert seen["target_path"] == "tests/fixtures/sample_sattline_files/Program/Main.s"
    assert seen["module_name"] == "Main"
    assert seen["mode"] == "steady-state"
    assert seen["max_scans"] == 25
    assert seen["output_format"] == "json"
    assert seen["output_path"] == "simulation.json"
    assert seen["use_cache"] is False


def test_run_cli_format_icf_passes_check_flag():
    seen = {}

    exit_code = _run_base_cli(
        ["format-icf", "--check"],
        load_config_fn=lambda path: ({"debug": False, "icf_dir": "icf"}, False),
        apply_debug_fn=lambda _cfg: None,
        run_format_icf_command_fn=lambda cfg, *, check: (
            seen.update({"cfg": cfg, "check": check}) or app_base.EXIT_SUCCESS
        ),
    )

    assert exit_code == app_base.EXIT_SUCCESS
    assert seen["check"] is True


def test_run_cli_docgen_passes_output_flags():
    seen = {}

    exit_code = _run_base_cli(
        ["docgen", "--output-dir", "docs-out", "--output-path", "report.docx"],
        load_config_fn=lambda path: ({"debug": False}, False),
        apply_debug_fn=lambda _cfg: None,
        run_docgen_command_fn=lambda cfg, *, use_cache, output_dir, output_path: (
            seen.update(
                {
                    "cfg": cfg,
                    "use_cache": use_cache,
                    "output_dir": output_dir,
                    "output_path": output_path,
                }
            )
            or app_base.EXIT_SUCCESS
        ),
    )

    assert exit_code == app_base.EXIT_SUCCESS
    assert seen["use_cache"] is True
    assert seen["output_dir"] == "docs-out"
    assert seen["output_path"] == "report.docx"


def test_run_cli_telemetry_summary_passes_output_flags():
    seen = {}

    exit_code = _run_base_cli(
        ["--config", "custom.toml", "telemetry-summary", "--format", "json", "--output", "summary.json"],
        load_config_fn=lambda path: ({"debug": False}, False),
        apply_debug_fn=lambda _cfg: None,
        run_telemetry_summary_command_fn=lambda cfg, *, config_path, output_format, output_path: (
            seen.update(
                {
                    "cfg": cfg,
                    "config_path": config_path,
                    "output_format": output_format,
                    "output_path": output_path,
                }
            )
            or app_base.EXIT_SUCCESS
        ),
    )

    assert exit_code == app_base.EXIT_SUCCESS
    assert str(seen["config_path"]).endswith("custom.toml")
    assert seen["output_format"] == "json"
    assert seen["output_path"] == "summary.json"


def test_run_cli_cache_prune_passes_cache_dir_without_loading_config():
    seen = {}

    exit_code = cli_entry.run_cli(
        ["cache-prune", "--cache-dir", "custom-cache"],
        config_path=Path("config.toml"),
        load_config_fn=lambda _path: (_ for _ in ()).throw(AssertionError("config should not be loaded")),
        apply_debug_fn=lambda _cfg: (_ for _ in ()).throw(AssertionError("debug should not be applied")),
        run_cache_prune_command_fn=lambda *, cache_dir: seen.update({"cache_dir": cache_dir}) or app_base.EXIT_SUCCESS,
    )

    assert exit_code == app_base.EXIT_SUCCESS
    assert seen == {"cache_dir": "custom-cache"}


def test_run_cli_repo_audit_passes_through_args(monkeypatch):
    seen = {}

    def mock_repo_audit_main(argv=None):
        seen.update({"argv": argv})
        return app_base.EXIT_SUCCESS

    monkeypatch.setattr("sattlint.devtools.repo_audit.main", mock_repo_audit_main)

    exit_code = _run_base_cli(
        ["repo-audit", "--profile", "quick", "--fail-on", "high"],
    )

    assert exit_code == app_base.EXIT_SUCCESS
    assert seen["argv"] == ["--profile", "quick", "--fail-on", "high"]


def test_run_cli_source_diff_passes_through_args(monkeypatch):
    seen = {}

    def mock_source_diff_main(argv=None):
        seen.update({"argv": argv})
        return app_base.EXIT_SUCCESS

    monkeypatch.setattr("sattlint.devtools.source_diff_report.main", mock_source_diff_main)

    exit_code = _run_base_cli(
        [
            "source-diff",
            "--workspace-root",
            "tests/fixtures/source_diff",
            "--draft-file",
            "WidgetReview.s",
            "--official-file",
            "WidgetReview.x",
        ],
    )

    assert exit_code == app_base.EXIT_SUCCESS
    assert seen["argv"] == [
        "--workspace-root",
        "tests/fixtures/source_diff",
        "--draft-file",
        "WidgetReview.s",
        "--official-file",
        "WidgetReview.x",
    ]


def test_run_cli_quiet_suppresses_forwarded_repo_audit_stdout(monkeypatch, capsys):
    monkeypatch.setattr(
        "sattlint.devtools.repo_audit.main",
        lambda argv=None: print("visible") or app_base.EXIT_SUCCESS,
    )

    exit_code = _run_base_cli(["--quiet", "repo-audit", "--list-checks"])

    captured = capsys.readouterr()
    assert exit_code == app_base.EXIT_SUCCESS
    assert captured.out == ""
    assert captured.err == ""


def test_run_cli_quiet_suppresses_forwarded_source_diff_stdout(monkeypatch, capsys):
    monkeypatch.setattr(
        "sattlint.devtools.source_diff_report.main",
        lambda argv=None: print("visible") or app_base.EXIT_SUCCESS,
    )

    exit_code = _run_base_cli(["--quiet", "source-diff", "--discover-pairs"])

    captured = capsys.readouterr()
    assert exit_code == app_base.EXIT_SUCCESS
    assert captured.out == ""
    assert captured.err == ""


def test_run_cli_quiet_suppresses_stdout(monkeypatch, capsys):
    monkeypatch.setattr(app_base, "run_syntax_check_command", lambda _path: print("visible") or app_base.EXIT_SUCCESS)

    exit_code = _run_base_cli(["--quiet", "syntax-check", "dummy.s"])

    captured = capsys.readouterr()
    assert exit_code == app_base.EXIT_SUCCESS
    assert captured.out == ""


def test_run_syntax_check_command_prints_ok_for_valid_file(monkeypatch, tmp_path, capsys):
    source_path = tmp_path / "Program.s"
    source_path.write_text("BasePicture\n", encoding="utf-8")

    monkeypatch.setattr(
        app_base.engine_module,
        "validate_single_file_syntax",
        lambda _path: engine.SyntaxValidationResult(file_path=source_path, ok=True, stage="validation"),
    )

    exit_code = app_base.run_syntax_check_command(str(source_path))

    captured = capsys.readouterr()
    assert exit_code == app_base.EXIT_SUCCESS
    assert captured.out == "OK\n"
    assert captured.err == ""


def test_run_syntax_check_command_returns_domain_failure_for_invalid_file(monkeypatch, tmp_path, capsys):
    source_path = tmp_path / "Broken.s"
    source_path.write_text("BasePicture\n", encoding="utf-8")

    monkeypatch.setattr(
        app_base.engine_module,
        "validate_single_file_syntax",
        lambda _path: engine.SyntaxValidationResult(
            file_path=source_path,
            ok=False,
            stage="validation",
            message="bad syntax",
            line=7,
            column=3,
        ),
    )

    exit_code = app_base.run_syntax_check_command(str(source_path))

    captured = capsys.readouterr()
    assert exit_code == app_base.EXIT_FAILURE
    assert "ERROR [validation]" in captured.err
    assert "bad syntax" in captured.err


def test_run_syntax_check_command_returns_usage_error_for_missing_file(capsys, tmp_path):
    missing_path = tmp_path / "Missing.s"

    exit_code = app_base.run_syntax_check_command(str(missing_path))

    captured = capsys.readouterr()
    assert exit_code == app_base.EXIT_USAGE_ERROR
    assert "ERROR [io]" in captured.err


class _FakeParser:
    def __init__(self, args=None, leftover=None, *, raises=None):
        self._args = args
        self._leftover = leftover or []
        self._raises = raises
        self.usage_stream = None

    def parse_known_args(self, _argv):
        if self._raises is not None:
            raise self._raises
        return self._args, self._leftover

    def print_usage(self, stream):
        self.usage_stream = stream


def test_cli_entry_returns_parser_system_exit_code():
    parser = _FakeParser(raises=SystemExit(2))

    exit_code = cli_entry.run_cli(
        ["--bad"],
        config_path=Path("config.toml"),
        build_cli_parser_fn=lambda: parser,
    )

    assert exit_code == 2


def test_cli_entry_syntax_check_requires_handler():
    parser = _FakeParser(
        args=SimpleNamespace(command="syntax-check", file="prog.s", config=None, no_cache=False, quiet=False)
    )

    with pytest.raises(RuntimeError, match="syntax-check handler is required"):
        cli_entry.run_cli(
            ["syntax-check", "prog.s"],
            config_path=Path("config.toml"),
            build_cli_parser_fn=lambda: parser,
        )


def test_cli_entry_reports_leftover_arguments(capsys):
    parser = _FakeParser(
        args=SimpleNamespace(command="analyze", checks=[], config=None, no_cache=False, quiet=False),
        leftover=["--unknown"],
    )

    exit_code = cli_entry.run_cli(
        ["analyze", "--unknown"],
        config_path=Path("config.toml"),
        build_cli_parser_fn=lambda: parser,
    )

    captured = capsys.readouterr()
    assert exit_code == cli_entry.EXIT_USAGE_ERROR
    assert "unrecognized arguments" in captured.err


def test_cli_entry_returns_usage_error_when_config_load_fails(capsys):
    parser = _FakeParser(
        args=SimpleNamespace(command="validate-config", checks=[], config=None, no_cache=False, quiet=False),
    )

    exit_code = cli_entry.run_cli(
        ["validate-config"],
        config_path=Path("config.toml"),
        build_cli_parser_fn=lambda: parser,
        load_config_fn=lambda _path: (_ for _ in ()).throw(RuntimeError("bad config")),
        apply_debug_fn=lambda _cfg: None,
    )

    captured = capsys.readouterr()
    assert exit_code == cli_entry.EXIT_USAGE_ERROR
    assert "ERROR [config]" in captured.err


def test_cli_entry_validate_config_requires_handler():
    parser = _FakeParser(
        args=SimpleNamespace(command="validate-config", checks=[], config=None, no_cache=False, quiet=False),
    )

    with pytest.raises(RuntimeError, match="validate-config handler is required"):
        cli_entry.run_cli(
            ["validate-config"],
            config_path=Path("config.toml"),
            build_cli_parser_fn=lambda: parser,
            load_config_fn=lambda _path: ({"debug": False}, False),
            apply_debug_fn=lambda _cfg: None,
        )


def test_cli_entry_analyze_requires_handler():
    parser = _FakeParser(
        args=SimpleNamespace(command="analyze", checks=[], config=None, no_cache=False, quiet=False),
    )

    with pytest.raises(RuntimeError, match="analyze handler is required"):
        cli_entry.run_cli(
            ["analyze"],
            config_path=Path("config.toml"),
            build_cli_parser_fn=lambda: parser,
            load_config_fn=lambda _path: ({"debug": False}, False),
            apply_debug_fn=lambda _cfg: None,
        )


def test_cli_entry_docgen_requires_handler():
    parser = _FakeParser(
        args=SimpleNamespace(command="docgen", checks=[], config=None, no_cache=False, quiet=False),
    )

    with pytest.raises(RuntimeError, match="docgen handler is required"):
        cli_entry.run_cli(
            ["docgen"],
            config_path=Path("config.toml"),
            build_cli_parser_fn=lambda: parser,
            load_config_fn=lambda _path: ({"debug": False}, False),
            apply_debug_fn=lambda _cfg: None,
        )


def test_cli_entry_telemetry_summary_requires_handler():
    parser = _FakeParser(
        args=SimpleNamespace(
            command="telemetry-summary",
            checks=[],
            config=None,
            no_cache=False,
            quiet=False,
            format="text",
            output=None,
        ),
    )

    with pytest.raises(RuntimeError, match="telemetry-summary handler is required"):
        cli_entry.run_cli(
            ["telemetry-summary"],
            config_path=Path("config.toml"),
            build_cli_parser_fn=lambda: parser,
            load_config_fn=lambda _path: ({"debug": False}, False),
            apply_debug_fn=lambda _cfg: None,
        )


def test_cli_entry_cache_prune_requires_handler():
    parser = _FakeParser(
        args=SimpleNamespace(
            command="cache-prune",
            checks=[],
            config=None,
            cache_dir=None,
            no_cache=False,
            quiet=False,
        ),
    )

    with pytest.raises(RuntimeError, match="cache-prune handler is required"):
        cli_entry.run_cli(
            ["cache-prune"],
            config_path=Path("config.toml"),
            build_cli_parser_fn=lambda: parser,
        )


def test_cli_entry_telemetry_summary_skips_config_loading():
    parser = _FakeParser(
        args=SimpleNamespace(
            command="telemetry-summary",
            checks=[],
            config="broken.toml",
            no_cache=False,
            quiet=False,
            format="json",
            output="summary.json",
        ),
    )
    seen: dict[str, Any] = {}

    exit_code = cli_entry.run_cli(
        ["--config", "broken.toml", "telemetry-summary", "--format", "json", "--output", "summary.json"],
        config_path=Path("config.toml"),
        build_cli_parser_fn=lambda: parser,
        load_config_fn=lambda _path: (_ for _ in ()).throw(AssertionError("config should not be loaded")),
        apply_debug_fn=lambda _cfg: (_ for _ in ()).throw(AssertionError("debug should not be applied")),
        run_telemetry_summary_command_fn=lambda cfg, *, config_path, output_format, output_path: (
            seen.update(
                {
                    "cfg": cfg,
                    "config_path": config_path,
                    "output_format": output_format,
                    "output_path": output_path,
                }
            )
            or cli_entry.EXIT_SUCCESS
        ),
    )

    assert exit_code == cli_entry.EXIT_SUCCESS
    assert seen == {
        "cfg": {},
        "config_path": Path("broken.toml"),
        "output_format": "json",
        "output_path": "summary.json",
    }


def test_cli_entry_simulate_requires_handler():
    parser = _FakeParser(
        args=SimpleNamespace(
            command="simulate",
            target_path="program.s",
            module="Main",
            mode="steady-state",
            max_scans=25,
            format="json",
            output=None,
            config=None,
            no_cache=False,
            quiet=False,
        ),
    )

    with pytest.raises(RuntimeError, match="simulate handler is required"):
        cli_entry.run_cli(
            ["simulate", "program.s", "--module", "Main"],
            config_path=Path("config.toml"),
            build_cli_parser_fn=lambda: parser,
            load_config_fn=lambda _path: ({"debug": False}, False),
            apply_debug_fn=lambda _cfg: None,
        )


def test_cli_entry_format_icf_requires_handler():
    parser = _FakeParser(
        args=SimpleNamespace(command="format-icf", checks=[], config=None, no_cache=False, quiet=False),
    )

    with pytest.raises(RuntimeError, match="format-icf handler is required"):
        cli_entry.run_cli(
            ["format-icf"],
            config_path=Path("config.toml"),
            build_cli_parser_fn=lambda: parser,
            load_config_fn=lambda _path: ({"debug": False}, False),
            apply_debug_fn=lambda _cfg: None,
        )


def test_cli_entry_prints_usage_when_no_command_selected():
    parser = _FakeParser(
        args=SimpleNamespace(command=None, checks=[], config=None, no_cache=False, quiet=False),
    )

    exit_code = cli_entry.run_cli(
        [],
        config_path=Path("config.toml"),
        build_cli_parser_fn=lambda: parser,
    )

    assert exit_code == cli_entry.EXIT_USAGE_ERROR
    assert parser.usage_stream is not None


def test_cli_entry_repo_audit_without_token_uses_empty_remaining_args(monkeypatch):
    seen: dict[str, Any] = {}
    parser = _FakeParser(
        args=SimpleNamespace(command="repo-audit", checks=[], config=None, no_cache=False, quiet=False),
    )
    monkeypatch.setattr("sattlint.devtools.repo_audit.main", lambda argv=None: seen.update({"argv": argv}) or 0)

    exit_code = cli_entry.run_cli(
        [],
        config_path=Path("config.toml"),
        build_cli_parser_fn=lambda: parser,
    )

    assert exit_code == cli_entry.EXIT_SUCCESS
    assert seen["argv"] == []


def test_cli_entry_source_diff_without_token_uses_empty_remaining_args(monkeypatch):
    seen: dict[str, Any] = {}
    parser = _FakeParser(
        args=SimpleNamespace(command="source-diff", checks=[], config=None, no_cache=False, quiet=False),
    )
    monkeypatch.setattr(
        "sattlint.devtools.source_diff_report.main",
        lambda argv=None: seen.update({"argv": argv}) or 0,
    )

    exit_code = cli_entry.run_cli(
        [],
        config_path=Path("config.toml"),
        build_cli_parser_fn=lambda: parser,
    )

    assert exit_code == cli_entry.EXIT_SUCCESS
    assert seen["argv"] == []


def test_cli_entry_returns_usage_error_when_config_handlers_are_missing(capsys):
    parser = _FakeParser(
        args=SimpleNamespace(command="analyze", checks=[], list_checks=False, config=None, no_cache=False, quiet=False),
    )

    exit_code = cli_entry.run_cli(
        ["analyze"],
        config_path=Path("config.toml"),
        build_cli_parser_fn=lambda: parser,
    )

    captured = capsys.readouterr()
    assert exit_code == cli_entry.EXIT_USAGE_ERROR
    assert "CLI config handlers are required for this command" in captured.err
