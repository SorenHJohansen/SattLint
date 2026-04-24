"""CLI behavior tests for SattLint."""

from typing import cast

import sattlint
from sattlint import app


def test_build_cli_parser_has_descriptions():
    parser = app.build_cli_parser()

    assert parser.description
    action = next(action for action in parser._actions if getattr(action, "choices", None))
    choices = cast(dict[str, object], action.choices)
    syntax_parser = cast(object, choices["syntax-check"])
    assert {"syntax-check", "analyze", "docgen", "validate-config", "repo-audit"} <= set(choices)
    assert getattr(syntax_parser, "description", None)


def test_run_cli_without_command_returns_usage_error():
    assert app.run_cli([]) == app.EXIT_USAGE_ERROR


def test_package_exports_version():
    assert sattlint.__version__ == "0.1.1"


def test_run_cli_version_flag(capsys):
    assert app.run_cli(["--version"]) == 0

    captured = capsys.readouterr()
    assert captured.out.strip() == f"sattlint {sattlint.__version__}"
    assert captured.err == ""


def test_run_cli_validate_config_uses_custom_path(monkeypatch):
    seen = {}

    monkeypatch.setattr(app, "load_config", lambda path: ({"debug": False}, False))
    monkeypatch.setattr(app, "apply_debug", lambda _cfg: None)
    monkeypatch.setattr(
        app,
        "run_validate_config_command",
        lambda cfg, *, config_path, default_used: seen.update(
            {"cfg": cfg, "config_path": config_path, "default_used": default_used}
        )
        or app.EXIT_SUCCESS,
    )

    exit_code = app.run_cli(["--config", "custom.toml", "validate-config"])

    assert exit_code == app.EXIT_SUCCESS
    assert str(seen["config_path"]).endswith("custom.toml")
    assert seen["default_used"] is False


def test_run_cli_analyze_passes_flags(monkeypatch):
    seen = {}

    monkeypatch.setattr(app, "load_config", lambda path: ({"debug": False}, False))
    monkeypatch.setattr(app, "apply_debug", lambda _cfg: None)
    monkeypatch.setattr(
        app,
        "run_analyze_command",
        lambda cfg, *, selected_keys, use_cache: seen.update(
            {"cfg": cfg, "selected_keys": selected_keys, "use_cache": use_cache}
        )
        or app.EXIT_SUCCESS,
    )

    exit_code = app.run_cli(["--no-cache", "analyze", "--check", "variables", "--check", "shadowing"])

    assert exit_code == app.EXIT_SUCCESS
    assert seen["selected_keys"] == ["variables", "shadowing"]
    assert seen["use_cache"] is False


def test_run_cli_repo_audit_passes_through_args(monkeypatch):
    seen = {}

    monkeypatch.setattr(
        app.repo_audit_module,
        "main",
        lambda argv=None: seen.update({"argv": argv}) or app.EXIT_SUCCESS,
    )

    exit_code = app.run_cli(["repo-audit", "--profile", "quick", "--fail-on", "high"])

    assert exit_code == app.EXIT_SUCCESS
    assert seen["argv"] == ["--profile", "quick", "--fail-on", "high"]


def test_run_cli_quiet_suppresses_stdout(monkeypatch, capsys):
    monkeypatch.setattr(app, "run_syntax_check_command", lambda _path: print("visible") or app.EXIT_SUCCESS)

    exit_code = app.run_cli(["--quiet", "syntax-check", "dummy.s"])

    captured = capsys.readouterr()
    assert exit_code == app.EXIT_SUCCESS
    assert captured.out == ""
