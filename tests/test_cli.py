"""CLI behavior tests for SattLint."""

from types import SimpleNamespace
from typing import cast

import sattlint
from sattlint import app, app_base


def _run_base_cli(argv: list[str], **overrides) -> int:
    kwargs = {
        "config_path": app.CONFIG_PATH,
        "repo_audit_module": SimpleNamespace(main=lambda argv=None: app_base.EXIT_SUCCESS),
        "load_config_fn": lambda path: ({"debug": False}, False),
        "apply_debug_fn": lambda _cfg: None,
        "run_validate_config_command_fn": lambda cfg, *, config_path, default_used: app_base.EXIT_SUCCESS,
        "run_analyze_command_fn": lambda cfg, *, selected_keys, use_cache: app_base.EXIT_SUCCESS,
        "run_docgen_command_fn": lambda cfg, *, use_cache: app_base.EXIT_SUCCESS,
        "run_format_icf_command_fn": lambda cfg, *, check: app_base.EXIT_SUCCESS,
    }
    kwargs.update(overrides)
    return app_base.run_cli(list(argv), **kwargs)


def test_build_cli_parser_has_descriptions():
    parser = app_base.build_cli_parser()

    assert parser.description
    action = next(action for action in parser._actions if getattr(action, "choices", None))
    choices = cast(dict[str, object], action.choices)
    syntax_parser = cast(object, choices["syntax-check"])
    assert {"syntax-check", "analyze", "docgen", "validate-config", "format-icf", "repo-audit"} <= set(choices)
    assert getattr(syntax_parser, "description", None)


def test_run_cli_without_command_returns_usage_error():
    assert _run_base_cli([]) == app_base.EXIT_USAGE_ERROR


def test_package_exports_version():
    assert sattlint.__version__ == "0.1.1"


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
        ["--no-cache", "analyze", "--check", "variables", "--check", "shadowing"],
        load_config_fn=lambda path: ({"debug": False}, False),
        apply_debug_fn=lambda _cfg: None,
        run_analyze_command_fn=lambda cfg, *, selected_keys, use_cache: (
            seen.update({"cfg": cfg, "selected_keys": selected_keys, "use_cache": use_cache}) or app_base.EXIT_SUCCESS
        ),
    )

    assert exit_code == app_base.EXIT_SUCCESS
    assert seen["selected_keys"] == ["variables", "shadowing"]
    assert seen["use_cache"] is False


def test_run_cli_format_icf_passes_check_flag():
    seen = {}

    exit_code = _run_base_cli(
        ["format-icf", "--check"],
        load_config_fn=lambda path: ({"debug": False, "icf_dir": "icf"}, False),
        apply_debug_fn=lambda _cfg: None,
        run_format_icf_command_fn=lambda cfg, *, check: seen.update({"cfg": cfg, "check": check})
        or app_base.EXIT_SUCCESS,
    )

    assert exit_code == app_base.EXIT_SUCCESS
    assert seen["check"] is True


def test_run_cli_repo_audit_passes_through_args():
    seen = {}

    exit_code = _run_base_cli(
        ["repo-audit", "--profile", "quick", "--fail-on", "high"],
        repo_audit_module=SimpleNamespace(main=lambda argv=None: seen.update({"argv": argv}) or app_base.EXIT_SUCCESS),
    )

    assert exit_code == app_base.EXIT_SUCCESS
    assert seen["argv"] == ["--profile", "quick", "--fail-on", "high"]


def test_run_cli_quiet_suppresses_stdout(monkeypatch, capsys):
    monkeypatch.setattr(app_base, "run_syntax_check_command", lambda _path: print("visible") or app_base.EXIT_SUCCESS)

    exit_code = _run_base_cli(["--quiet", "syntax-check", "dummy.s"])

    captured = capsys.readouterr()
    assert exit_code == app_base.EXIT_SUCCESS
    assert captured.out == ""
