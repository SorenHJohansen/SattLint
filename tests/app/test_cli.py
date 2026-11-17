# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportArgumentType=false, reportIndexIssue=false
"""CLI behavior tests for SattLint startup and interactive routing.

No-argument startup launches the Textual TUI. Non-empty argv is routed to the
headless CLI; these tests cover that routing boundary and the interactive
launch path. Headless command behavior lives in ``test_cli_headless.py``.
"""

import runpy
from pathlib import Path
from typing import Any, cast

import pytest

import sattlint
from sattlint.__version__ import __version__ as package_version
from sattlint.cli import menu as cli_menu_module
from sattlint.cli import startup as startup_application


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
        run_main_loop_fn=lambda *_args, **_kwargs: pytest.fail("interactive loop should not run for CLI argv"),
        summarize_targets_fn=lambda _cfg: "targets",
        save_config_fn=lambda _path, _cfg: None,
        quit_app_error=RuntimeError,
    )

    assert exit_code == 13
    assert seen == {"argv": ["analyze", "--check", "variables"]}


def test_startup_main_configures_logging_for_the_interactive_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configured: list[str] = []
    monkeypatch.setattr(startup_application, "configure_logging", lambda: configured.append("configured"))

    exit_code = startup_application.main(
        None,
        run_cli_fn=lambda _argv: pytest.fail("run_cli should not run for plain interactive startup"),
        load_config_fn=lambda _path: ({"debug": False}, False),
        config_path=Path("config.toml"),
        apply_debug_fn=lambda _cfg: None,
        resolve_interactive_ui_mode_fn=lambda _cfg, _override: "textual",
        set_interactive_ui_mode_fn=lambda _mode: None,
        reset_interactive_ui_mode_fn=lambda: None,
        emit_output_fn=lambda *_args: None,
        pause_fn=lambda: None,
        run_main_loop_fn=lambda *_args, **_kwargs: None,
        summarize_targets_fn=lambda _cfg: "targets",
        save_config_fn=lambda _path, _cfg: None,
        quit_app_error=RuntimeError,
    )

    assert exit_code == 0
    assert configured == ["configured"]


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
        run_main_loop_fn=lambda local_cfg, **kwargs: seen.update(
            {"main_loop_cfg": dict(local_cfg), "main_loop_kwargs": kwargs}
        ),
        summarize_targets_fn=lambda _cfg: "targets",
        save_config_fn=lambda _path, _cfg: None,
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
        run_main_loop_fn=lambda local_cfg, **kwargs: seen.update(
            {"main_loop_cfg": dict(local_cfg), "main_loop_kwargs": kwargs}
        ),
        summarize_targets_fn=lambda _cfg: "targets",
        save_config_fn=lambda _path, _cfg: None,
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
        run_main_loop_fn=lambda local_cfg, **kwargs: seen.update(
            {"main_loop_cfg": local_cfg, "main_loop_kwargs": kwargs}
        ),
        summarize_targets_fn=lambda _cfg: "targets",
        save_config_fn=lambda _path, _cfg: None,
        quit_app_error=RuntimeError,
    )

    assert exit_code == 0
    assert seen["debug_cfg"] is cfg
    assert seen["message"] == "Warning: Default config created. Open Setup before running analysis."
    assert seen["paused"] == 1
    assert seen["main_loop_cfg"] is cfg
    assert "choose_menu_option_fn" not in cast(dict[str, Any], seen["main_loop_kwargs"])
    assert "interaction" not in cast(dict[str, Any], seen["main_loop_kwargs"])


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
        run_main_loop_fn=lambda *_args, **_kwargs: (_ for _ in ()).throw(QuitSignalError()),
        summarize_targets_fn=lambda _cfg: "targets",
        save_config_fn=lambda _path, _cfg: None,
        quit_app_error=QuitSignalError,
    )

    assert exit_code == 0


def test_startup_main_reports_unreadable_config_without_traceback() -> None:
    messages: list[str] = []

    def fail_load(_path: Path) -> tuple[dict[str, object], bool]:
        raise ValueError("config is malformed")

    exit_code = startup_application.main(
        None,
        run_cli_fn=lambda _argv: pytest.fail("run_cli should not run for interactive startup"),
        load_config_fn=cast(Any, fail_load),
        config_path=Path("config.toml"),
        apply_debug_fn=lambda _cfg: None,
        emit_output_fn=lambda message: messages.append(str(message)),
        pause_fn=lambda: None,
        run_main_loop_fn=lambda *_args, **_kwargs: pytest.fail("the interactive loop must not start"),
        summarize_targets_fn=lambda _cfg: "targets",
        save_config_fn=lambda _path, _cfg: None,
        quit_app_error=RuntimeError,
    )

    assert exit_code == 1
    assert messages == ["Failed to load configuration from config.toml: config is malformed"]


def test_startup_main_reports_unavailable_ui_mode_without_traceback() -> None:
    messages: list[str] = []

    exit_code = startup_application.main(
        None,
        run_cli_fn=lambda _argv: pytest.fail("run_cli should not run for interactive startup"),
        load_config_fn=lambda _path: ({"debug": False}, False),
        config_path=Path("config.toml"),
        apply_debug_fn=lambda _cfg: None,
        resolve_interactive_ui_mode_fn=lambda _cfg, _override: (_ for _ in ()).throw(
            RuntimeError("Textual is unavailable")
        ),
        emit_output_fn=lambda message: messages.append(str(message)),
        pause_fn=lambda: None,
        run_main_loop_fn=lambda *_args, **_kwargs: pytest.fail("the interactive loop must not start"),
        summarize_targets_fn=lambda _cfg: "targets",
        save_config_fn=lambda _path, _cfg: None,
        quit_app_error=RuntimeError,
    )

    assert exit_code == 1
    assert messages == ["Interactive startup failed: Textual is unavailable"]


def test_startup_menu_helpers_reach_owner_functions(monkeypatch) -> None:
    seen: dict[str, object] = {}
    cfg = {"debug": False}

    monkeypatch.setattr(
        cli_menu_module,
        "summarize_targets",
        lambda local_cfg, **kwargs: seen.update({"summarize_cfg": local_cfg, **kwargs}) or "targets",
    )
    assert startup_application.summarize_targets(cfg) == "targets"
    assert seen["summarize_cfg"] is cfg

    monkeypatch.setattr(
        cli_menu_module,
        "get_help_text",
        lambda local_cfg, **kwargs: seen.update({"help_text_cfg": local_cfg, **kwargs}) or "help-text",
    )
    assert startup_application.get_help_text(cfg) == "help-text"
    assert seen["help_text_cfg"] is cfg


def test_package_exports_version():
    assert sattlint.__version__ == package_version


def test_module_entrypoint_exits_with_cli_status(monkeypatch):
    monkeypatch.setattr(startup_application, "cli", lambda: 7)

    with pytest.raises(SystemExit, match="7") as exc_info:
        runpy.run_module("sattlint.__main__", run_name="__main__")

    assert exc_info.value.code == 7


def test_startup_headless_argv_never_resolves_the_config_directory(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        startup_application.config_module,
        "get_config_path",
        lambda: (_ for _ in ()).throw(OSError("unwritable")),
    )

    exit_code = startup_application.main(
        ["version"],
        run_cli_fn=lambda _argv: 0,
        apply_debug_fn=lambda _cfg: None,
        emit_output_fn=lambda *_args: None,
        pause_fn=lambda: None,
        run_main_loop_fn=lambda *_args, **_kwargs: pytest.fail("interactive loop should not run for CLI argv"),
        summarize_targets_fn=lambda _cfg: "targets",
        save_config_fn=lambda _path, _cfg: None,
        quit_app_error=RuntimeError,
    )

    assert exit_code == 0


def test_startup_reports_an_unresolvable_config_directory_as_a_user_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        startup_application.config_module,
        "get_config_path",
        lambda: (_ for _ in ()).throw(OSError("unwritable")),
    )
    messages: list[str] = []

    exit_code = startup_application.main(
        [],
        apply_debug_fn=lambda _cfg: None,
        emit_output_fn=lambda *args: messages.append(str(args[0])),
        pause_fn=lambda: None,
        run_main_loop_fn=lambda *_args, **_kwargs: pytest.fail("interactive loop should not run"),
        summarize_targets_fn=lambda _cfg: "targets",
        save_config_fn=lambda _path, _cfg: None,
        quit_app_error=RuntimeError,
    )

    assert exit_code == 2
    assert messages == ["Failed to resolve the configuration directory: unwritable"]
