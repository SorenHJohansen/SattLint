# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportArgumentType=false, reportIndexIssue=false
"""CLI behavior tests for SattLint."""

import json
import runpy
from collections.abc import Mapping
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

import sattlint
from sattlint import _config_display as config_display_module
from sattlint import app, engine
from sattlint.__version__ import __version__ as package_version
from sattlint._exit_codes import EXIT_FAILURE, EXIT_SUCCESS, EXIT_USAGE_ERROR
from sattlint.cli import app_commands as commands_application
from sattlint.cli import command_handlers as cli_command_handlers
from sattlint.cli import entry as cli_entry
from sattlint.cli import menu as cli_menu_module
from sattlint.cli import startup as startup_application
from sattlint.cli import syntax_check as cli_syntax_check
from sattlint.models import IssueKind


def _command_handlers(**overrides: Any) -> dict[str, Any]:
    return cast(
        dict[str, Any],
        cli_command_handlers.build_command_handlers(
            overrides=cast(
                cli_entry.CommandHandlers,
                {
                    "syntax_check": lambda file_path, *, output_format="text": (
                        cli_syntax_check.run_syntax_check_command(
                            file_path,
                            output_format=output_format,
                        )
                    ),
                    "validate_config": lambda cfg, *, config_path, default_used: EXIT_SUCCESS,
                    "analyze": lambda cfg, *, selected_keys, selected_issue_kinds=None, use_cache, output_format="text": (
                        EXIT_SUCCESS
                    ),
                    "docgen": lambda cfg, *, use_cache, output_format="text", output_dir, output_path: EXIT_SUCCESS,
                    "cache_prune": lambda *, cache_dir, output_format="text": EXIT_SUCCESS,
                }
                | overrides,
            ),
        ),
    )


def _run_base_cli(argv: list[str], **overrides) -> int:
    command_handler_overrides = cast(dict[str, Any], overrides.pop("command_handlers", {}))
    kwargs = {
        "config_path": app.CONFIG_PATH,
        "build_cli_parser_fn": cli_entry.build_cli_parser,
        "load_config_fn": lambda path: ({"debug": False}, False),
        "apply_debug_fn": lambda _cfg: None,
        "command_handlers": _command_handlers(**command_handler_overrides),
    }
    kwargs.update(overrides)
    return cli_entry.run_cli(list(argv), **kwargs)


def test_build_cli_parser_has_descriptions():
    parser = cli_entry.build_cli_parser()

    assert parser.description
    action = next(action for action in parser._actions if isinstance(getattr(action, "choices", None), Mapping))
    choices = cast(dict[str, object], action.choices)
    syntax_parser = choices["syntax-check"]
    assert {
        "syntax-check",
        "analyze",
        "cache-prune",
        "validate-config",
    } <= set(choices)
    assert getattr(syntax_parser, "description", None)


def test_build_cli_parser_syntax_check_includes_output_format():
    parser = cli_entry.build_cli_parser()

    action = next(action for action in parser._actions if isinstance(getattr(action, "choices", None), Mapping))
    choices = cast(dict[str, object], action.choices)
    syntax_parser = cast(Any, choices["syntax-check"])
    option_strings = {
        option for parser_action in syntax_parser._actions for option in getattr(parser_action, "option_strings", [])
    }

    assert {"--format", "--output-format"} <= option_strings


def test_build_cli_parser_validate_config_includes_output_format():
    parser = cli_entry.build_cli_parser()

    action = next(action for action in parser._actions if isinstance(getattr(action, "choices", None), Mapping))
    choices = cast(dict[str, object], action.choices)
    validate_parser = cast(Any, choices["validate-config"])
    option_strings = {
        option for parser_action in validate_parser._actions for option in getattr(parser_action, "option_strings", [])
    }

    assert {"--format", "--output-format"} <= option_strings


def test_build_cli_parser_analyze_includes_output_format():
    parser = cli_entry.build_cli_parser()

    action = next(action for action in parser._actions if isinstance(getattr(action, "choices", None), Mapping))
    choices = cast(dict[str, object], action.choices)
    analyze_parser = cast(Any, choices["analyze"])
    option_strings = {
        option for parser_action in analyze_parser._actions for option in getattr(parser_action, "option_strings", [])
    }

    assert {"--format", "--output-format"} <= option_strings


@pytest.mark.parametrize(
    ("command_name", "expected_options"),
    [
        ("cache-prune", {"--format", "--output-format"}),
    ],
)
def test_build_cli_parser_commands_include_output_format_aliases(command_name: str, expected_options: set[str]):
    parser = cli_entry.build_cli_parser()

    action = next(action for action in parser._actions if isinstance(getattr(action, "choices", None), Mapping))
    choices = cast(dict[str, object], action.choices)
    command_parser = cast(Any, choices[command_name])
    option_strings = {
        option for parser_action in command_parser._actions for option in getattr(parser_action, "option_strings", [])
    }

    assert expected_options <= option_strings


def test_build_cli_parser_exposes_interactive_ui_override():
    parser = cli_entry.build_cli_parser()

    option_strings = {
        option for parser_action in parser._actions for option in getattr(parser_action, "option_strings", [])
    }

    assert "--ui" in option_strings


def test_run_cli_without_command_returns_usage_error():
    assert _run_base_cli([]) == EXIT_USAGE_ERROR


def test_startup_main_routes_cli_argv_to_run_cli() -> None:
    seen: dict[str, object] = {}

    exit_code = startup_application.main(
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

    exit_code = startup_application.main(
        ["--debug"],
        run_cli_fn=lambda _argv: pytest.fail("run_cli should not run for interactive debug-only argv"),
        build_cli_parser_fn=lambda: pytest.fail("interactive override detection should not use the full CLI parser"),
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

    exit_code = startup_application.main(
        ["--ui", "textual"],
        run_cli_fn=lambda _argv: pytest.fail("run_cli should not run for interactive ui-only argv"),
        build_cli_parser_fn=lambda: pytest.fail("interactive override detection should not use the full CLI parser"),
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
        show_help_fn=lambda _cfg: None,
        save_config_fn=lambda _path, _cfg: None,
        quit_app_fn=lambda: None,
        quit_app_error=RuntimeError,
    )

    assert exit_code == 0
    assert seen["apply_debug_cfg"] == {"debug": False}
    assert seen["main_loop_cfg"] == {"debug": False}
    assert seen["main_loop_kwargs"]["config_path"] == Path("config.toml")


def test_startup_main_routes_config_only_cli_argv_to_interactive_loop() -> None:
    seen: dict[str, object] = {}
    cfg = {"debug": False}

    exit_code = startup_application.main(
        ["--config", "custom.toml"],
        run_cli_fn=lambda _argv: pytest.fail("run_cli should not run for interactive config-only argv"),
        build_cli_parser_fn=lambda: pytest.fail("interactive override detection should not use the full CLI parser"),
        load_config_fn=lambda path: (seen.update({"loaded_config_path": path}) or cfg, False),
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
        show_help_fn=lambda _cfg: None,
        save_config_fn=lambda _path, _cfg: None,
        quit_app_fn=lambda: None,
        quit_app_error=RuntimeError,
    )

    assert exit_code == 0
    assert seen["loaded_config_path"] == Path("custom.toml")
    assert seen["apply_debug_cfg"] == {"debug": False}
    assert seen["main_loop_cfg"] == {"debug": False}
    assert seen["main_loop_kwargs"]["config_path"] == Path("custom.toml")


def test_startup_main_defaults_plain_interactive_session_to_textual() -> None:
    seen: dict[str, object] = {}
    cfg = {"debug": False}

    exit_code = startup_application.main(
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

    exit_code = startup_application.main(
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

    exit_code = startup_application.main(
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

    exit_code = startup_application.main(
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
        show_help_fn=lambda _cfg: None,
        save_config_fn=lambda _path, _cfg: None,
        quit_app_fn=lambda: None,
        quit_app_error=QuitSignalError,
    )

    assert exit_code == 0


def test_startup_menu_helpers_reach_owner_functions(monkeypatch) -> None:
    seen: dict[str, object] = {}
    cfg = {"debug": False}

    monkeypatch.setattr(
        cli_menu_module,
        "print_menu",
        lambda title, options, **kwargs: seen.update({"menu_title": title, "menu_options": options, **kwargs}),
    )
    startup_application.print_menu("Menu", [("1", "One")], intro="Intro", note="Note")
    assert seen["menu_title"] == "Menu"
    assert seen["menu_options"] == [("1", "One")]
    assert seen["intro"] == "Intro"

    monkeypatch.setattr(
        cli_menu_module,
        "summarize_targets",
        lambda local_cfg, **kwargs: seen.update({"summarize_cfg": local_cfg, **kwargs}) or "targets",
    )
    assert startup_application.summarize_targets(cfg) == "targets"
    assert seen["summarize_cfg"] is cfg

    monkeypatch.setattr(
        cli_menu_module,
        "show_help",
        lambda local_cfg, **kwargs: seen.update({"show_help_cfg": local_cfg, **kwargs}),
    )
    startup_application.show_help(cfg)
    assert seen["show_help_cfg"] is cfg
    assert callable(cast(Any, seen["pause_fn"]))
    assert callable(cast(Any, seen["clear_screen_fn"]))

    monkeypatch.setattr(
        cli_menu_module,
        "get_help_text",
        lambda local_cfg, **kwargs: seen.update({"help_text_cfg": local_cfg, **kwargs}) or "help-text",
    )
    assert startup_application.get_help_text(cfg) == "help-text"
    assert seen["help_text_cfg"] is cfg


def test_show_config_command_reaches_config_display_owner(monkeypatch) -> None:
    seen: dict[str, object] = {}
    cfg = {"debug": False}

    monkeypatch.setattr(
        config_display_module,
        "show_config",
        lambda local_cfg, **kwargs: seen.update({"show_config_cfg": local_cfg, **kwargs}),
    )
    commands_application.show_config(cfg)

    assert seen["show_config_cfg"] is cfg


def test_package_exports_version():
    assert sattlint.__version__ == package_version


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
    assert seen["kwargs"]["debug"] is True
    assert seen["kwargs"]["collect_variable_diagnostics"] is False
    assert seen["kwargs"]["_analysis_provider"] is sattlint.build_variable_semantic_artifacts


def test_module_entrypoint_exits_with_cli_status(monkeypatch):
    monkeypatch.setattr(app, "cli", lambda: 7)

    with pytest.raises(SystemExit, match="7") as exc_info:
        runpy.run_module("sattlint.__main__", run_name="__main__")

    assert exc_info.value.code == 7


def test_run_cli_version_flag(capsys):
    assert _run_base_cli(["--version"]) == EXIT_SUCCESS

    captured = capsys.readouterr()
    assert captured.out.strip() == f"sattlint {sattlint.__version__}"
    assert captured.err == ""


def test_run_cli_version_flag_skips_full_parser_build(capsys):
    exit_code = _run_base_cli(
        ["--version"],
        build_cli_parser_fn=lambda: pytest.fail("--version should not build the full CLI parser"),
    )

    assert exit_code == EXIT_SUCCESS
    captured = capsys.readouterr()
    assert captured.out.strip() == f"sattlint {sattlint.__version__}"
    assert captured.err == ""


def test_run_cli_validate_config_uses_custom_path(monkeypatch):
    seen = {}

    exit_code = _run_base_cli(
        ["--config", "custom.toml", "validate-config"],
        load_config_fn=lambda path: ({"debug": False}, False),
        apply_debug_fn=lambda _cfg: None,
        command_handlers={
            "validate_config": lambda cfg, *, config_path, default_used: (
                seen.update({"cfg": cfg, "config_path": config_path, "default_used": default_used}) or EXIT_SUCCESS
            )
        },
    )

    assert exit_code == EXIT_SUCCESS
    assert str(seen["config_path"]).endswith("custom.toml")
    assert seen["default_used"] is False


def test_run_cli_validate_config_passes_json_output_format():
    seen = {}

    exit_code = _run_base_cli(
        ["validate-config", "--format", "json"],
        load_config_fn=lambda path: ({"debug": False}, False),
        apply_debug_fn=lambda _cfg: None,
        command_handlers={
            "validate_config": lambda cfg, *, config_path, default_used, output_format: (
                seen.update(
                    {
                        "cfg": cfg,
                        "config_path": config_path,
                        "default_used": default_used,
                        "output_format": output_format,
                    }
                )
                or EXIT_SUCCESS
            )
        },
    )

    assert exit_code == EXIT_SUCCESS
    assert seen["output_format"] == "json"


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
        command_handlers={
            "analyze": lambda cfg, *, selected_keys, selected_issue_kinds, use_cache, output_format="text": (
                seen.update(
                    {
                        "cfg": cfg,
                        "selected_keys": selected_keys,
                        "selected_issue_kinds": selected_issue_kinds,
                        "use_cache": use_cache,
                        "output_format": output_format,
                    }
                )
                or EXIT_SUCCESS
            )
        },
    )

    assert exit_code == EXIT_SUCCESS
    assert seen["selected_keys"] == ["variables", "shadowing"]
    assert seen["selected_issue_kinds"] == frozenset({"unused", "shadowing"})
    assert seen["use_cache"] is False
    assert seen["output_format"] == "text"
    assert cast(dict[str, Any], seen["cfg"])["debug"] is True


def test_run_cli_analyze_passes_opt_in_state_inference_key():
    seen = {}

    exit_code = cli_entry.run_cli(
        ["analyze", "--check", "state-inference"],
        config_path=app.CONFIG_PATH,
        load_config_fn=lambda path: ({"debug": False}, False),
        apply_debug_fn=lambda _cfg: None,
        command_handlers=_command_handlers(
            analyze=lambda cfg, *, selected_keys, selected_issue_kinds=None, use_cache, output_format="text": (
                seen.update(
                    {
                        "cfg": cfg,
                        "selected_keys": selected_keys,
                        "selected_issue_kinds": selected_issue_kinds,
                        "use_cache": use_cache,
                        "output_format": output_format,
                    }
                )
                or EXIT_SUCCESS
            )
        ),
    )

    assert exit_code == EXIT_SUCCESS
    assert seen["selected_keys"] == ["state-inference"]
    assert seen["selected_issue_kinds"] is None
    assert seen["use_cache"] is True
    assert seen["output_format"] == "text"


def test_run_cli_analyze_passes_json_output_format():
    seen = {}

    exit_code = cli_entry.run_cli(
        ["analyze", "--check", "variables", "--format", "json"],
        config_path=app.CONFIG_PATH,
        load_config_fn=lambda path: ({"debug": False}, False),
        apply_debug_fn=lambda _cfg: None,
        command_handlers=_command_handlers(
            analyze=lambda cfg, *, selected_keys, selected_issue_kinds=None, use_cache, output_format="text": (
                seen.update(
                    {
                        "cfg": cfg,
                        "selected_keys": selected_keys,
                        "selected_issue_kinds": selected_issue_kinds,
                        "use_cache": use_cache,
                        "output_format": output_format,
                    }
                )
                or EXIT_SUCCESS
            )
        ),
    )

    assert exit_code == EXIT_SUCCESS
    assert seen["selected_keys"] == ["variables"]
    assert seen["selected_issue_kinds"] is None
    assert seen["use_cache"] is True
    assert seen["output_format"] == "json"


def test_run_cli_analyze_requires_at_least_one_check_without_loading_config(capsys):
    exit_code = cli_entry.run_cli(
        ["analyze"],
        config_path=Path("config.toml"),
        load_config_fn=lambda _path: pytest.fail("load_config should not run when --check is missing"),
        apply_debug_fn=lambda _cfg: pytest.fail("apply_debug should not run when --check is missing"),
    )

    captured = capsys.readouterr()
    assert exit_code == cli_entry.EXIT_USAGE_ERROR
    assert "at least one --check KEY is required" in captured.err
    assert captured.out == ""


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
    assert exit_code == EXIT_SUCCESS
    assert captured.out.splitlines() == ["variables", "timing"]
    assert captured.err == ""


def test_run_cli_analyze_list_checks_supports_json_output(monkeypatch, capsys):
    monkeypatch.setattr(
        "sattlint.analyzers.registry.get_selectable_analyzers",
        lambda: [SimpleNamespace(key="variables"), SimpleNamespace(key="timing")],
    )

    exit_code = cli_entry.run_cli(
        ["analyze", "--list-checks", "--format", "json"],
        config_path=Path("config.toml"),
    )

    captured = capsys.readouterr()
    assert exit_code == EXIT_SUCCESS
    assert json.loads(captured.out) == {"checks": ["variables", "timing"]}
    assert captured.err == ""


def test_run_cli_analyze_list_issue_kinds_prints_values_without_loading_config(capsys):
    exit_code = cli_entry.run_cli(
        ["analyze", "--list-issue-kinds"],
        config_path=Path("config.toml"),
        load_config_fn=lambda _path: pytest.fail("load_config should not run for --list-issue-kinds"),
        apply_debug_fn=lambda _cfg: pytest.fail("apply_debug should not run for --list-issue-kinds"),
    )

    captured = capsys.readouterr()
    assert exit_code == EXIT_SUCCESS
    assert captured.out.splitlines() == [issue_kind.value for issue_kind in IssueKind]
    assert captured.err == ""


def test_run_cli_analyze_list_issue_kinds_supports_json_without_loading_config(capsys):
    exit_code = cli_entry.run_cli(
        ["analyze", "--list-issue-kinds", "--format", "json"],
        config_path=Path("config.toml"),
        load_config_fn=lambda _path: pytest.fail("load_config should not run for --list-issue-kinds"),
        apply_debug_fn=lambda _cfg: pytest.fail("apply_debug should not run for --list-issue-kinds"),
    )

    captured = capsys.readouterr()
    assert exit_code == EXIT_SUCCESS
    assert json.loads(captured.out) == {"issue_kinds": [issue_kind.value for issue_kind in IssueKind]}
    assert captured.err == ""


def test_run_cli_cache_prune_passes_cache_dir_without_loading_config():
    seen = {}

    exit_code = cli_entry.run_cli(
        ["cache-prune", "--output-format", "json", "--cache-dir", "custom-cache"],
        config_path=Path("config.toml"),
        load_config_fn=lambda _path: (_ for _ in ()).throw(AssertionError("config should not be loaded")),
        apply_debug_fn=lambda _cfg: (_ for _ in ()).throw(AssertionError("debug should not be applied")),
        command_handlers={
            "cache_prune": lambda *, cache_dir, output_format="text": (
                seen.update({"cache_dir": cache_dir, "output_format": output_format}) or EXIT_SUCCESS
            )
        },
    )

    assert exit_code == EXIT_SUCCESS
    assert seen == {"cache_dir": "custom-cache", "output_format": "json"}


def test_run_cli_quiet_suppresses_stdout(monkeypatch, capsys):
    monkeypatch.setattr(
        cli_syntax_check,
        "run_syntax_check_command",
        lambda _path, *, output_format="text": print("visible") or EXIT_SUCCESS,
    )

    exit_code = _run_base_cli(["--quiet", "syntax-check", "dummy.s"])

    captured = capsys.readouterr()
    assert exit_code == EXIT_SUCCESS
    assert captured.out == ""


def test_run_syntax_check_command_prints_ok_for_valid_file(monkeypatch, tmp_path, capsys):
    source_path = tmp_path / "Program.s"
    source_path.write_text("BasePicture\n", encoding="utf-8")

    monkeypatch.setattr(
        engine,
        "validate_single_file_syntax",
        lambda _path: engine.SyntaxValidationResult(file_path=source_path, ok=True, stage="validation"),
    )

    exit_code = cli_syntax_check.run_syntax_check_command(str(source_path))

    captured = capsys.readouterr()
    assert exit_code == EXIT_SUCCESS
    assert captured.out == "OK\n"
    assert captured.err == ""


def test_run_syntax_check_command_prints_json_for_valid_file(monkeypatch, tmp_path, capsys):
    source_path = tmp_path / "Program.s"
    source_path.write_text("BasePicture\n", encoding="utf-8")

    monkeypatch.setattr(
        engine,
        "validate_single_file_syntax",
        lambda _path: engine.SyntaxValidationResult(
            file_path=source_path,
            ok=True,
            stage="validation",
            warnings=("legacy warning",),
        ),
    )

    exit_code = cli_syntax_check.run_syntax_check_command(str(source_path), output_format="json")

    captured = capsys.readouterr()
    assert exit_code == EXIT_SUCCESS
    assert captured.err == ""
    assert json.loads(captured.out) == {
        "column": None,
        "file_path": str(source_path),
        "line": None,
        "message": None,
        "ok": True,
        "stage": "validation",
        "warnings": ["legacy warning"],
    }


def test_run_syntax_check_command_returns_domain_failure_for_invalid_file(monkeypatch, tmp_path, capsys):
    source_path = tmp_path / "Broken.s"
    source_path.write_text("BasePicture\n", encoding="utf-8")

    monkeypatch.setattr(
        engine,
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

    exit_code = cli_syntax_check.run_syntax_check_command(str(source_path))

    captured = capsys.readouterr()
    assert exit_code == EXIT_FAILURE
    assert "ERROR [validation]" in captured.err
    assert "bad syntax" in captured.err


def test_run_syntax_check_command_prints_json_for_invalid_file(monkeypatch, tmp_path, capsys):
    source_path = tmp_path / "Broken.s"
    source_path.write_text("BasePicture\n", encoding="utf-8")

    monkeypatch.setattr(
        engine,
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

    exit_code = cli_syntax_check.run_syntax_check_command(str(source_path), output_format="json")

    captured = capsys.readouterr()
    assert exit_code == EXIT_FAILURE
    assert captured.err == ""
    assert json.loads(captured.out) == {
        "column": 3,
        "file_path": str(source_path),
        "line": 7,
        "message": "bad syntax",
        "ok": False,
        "stage": "validation",
        "warnings": [],
    }


def test_run_syntax_check_command_returns_usage_error_for_missing_file(capsys, tmp_path):
    missing_path = tmp_path / "Missing.s"

    exit_code = cli_syntax_check.run_syntax_check_command(str(missing_path))

    captured = capsys.readouterr()
    assert exit_code == EXIT_USAGE_ERROR
    assert "ERROR [io]" in captured.err


def test_run_syntax_check_command_prints_json_for_missing_file(capsys, tmp_path):
    missing_path = tmp_path / "Missing.s"

    exit_code = cli_syntax_check.run_syntax_check_command(str(missing_path), output_format="json")

    captured = capsys.readouterr()
    assert exit_code == EXIT_USAGE_ERROR
    assert captured.err == ""
    assert json.loads(captured.out) == {
        "column": None,
        "file_path": str(missing_path),
        "line": None,
        "message": "File not found",
        "ok": False,
        "stage": "io",
        "warnings": [],
    }


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
        load_config_fn=lambda _path: (_ for _ in ()).throw(ValueError("bad config")),
        apply_debug_fn=lambda _cfg: None,
    )

    captured = capsys.readouterr()
    assert exit_code == cli_entry.EXIT_USAGE_ERROR
    assert "ERROR [config]" in captured.err


def test_cli_entry_reraises_unexpected_config_load_exceptions() -> None:
    parser = _FakeParser(
        args=SimpleNamespace(command="validate-config", checks=[], config=None, no_cache=False, quiet=False),
    )

    with pytest.raises(RuntimeError, match="bad config"):
        cli_entry.run_cli(
            ["validate-config"],
            config_path=Path("config.toml"),
            build_cli_parser_fn=lambda: parser,
            load_config_fn=lambda _path: (_ for _ in ()).throw(RuntimeError("bad config")),
            apply_debug_fn=lambda _cfg: None,
        )


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


def test_cli_entry_syntax_check_passes_json_output_format():
    seen: dict[str, object] = {}
    parser = _FakeParser(
        args=SimpleNamespace(
            command="syntax-check",
            file="prog.s",
            config=None,
            no_cache=False,
            quiet=False,
            format="json",
        )
    )

    exit_code = cli_entry.run_cli(
        ["syntax-check", "prog.s", "--format", "json"],
        config_path=Path("config.toml"),
        build_cli_parser_fn=lambda: parser,
        command_handlers={
            "syntax_check": lambda file_path, *, output_format="text": (
                seen.update({"file_path": file_path, "output_format": output_format}) or 0
            )
        },
    )

    assert exit_code == cli_entry.EXIT_SUCCESS
    assert seen == {"file_path": "prog.s", "output_format": "json"}


def test_cli_entry_analyze_requires_handler():
    parser = _FakeParser(
        args=SimpleNamespace(command="analyze", checks=["variables"], config=None, no_cache=False, quiet=False),
    )

    with pytest.raises(RuntimeError, match="analyze handler is required"):
        cli_entry.run_cli(
            ["analyze", "--check", "variables"],
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


def test_cli_entry_reraises_when_config_handlers_are_missing():
    parser = _FakeParser(
        args=SimpleNamespace(
            command="analyze",
            checks=["variables"],
            list_checks=False,
            config=None,
            no_cache=False,
            quiet=False,
        ),
    )

    with pytest.raises(RuntimeError, match="CLI config handlers are required for this command"):
        cli_entry.run_cli(
            ["analyze", "--check", "variables"],
            config_path=Path("config.toml"),
            build_cli_parser_fn=lambda: parser,
        )
