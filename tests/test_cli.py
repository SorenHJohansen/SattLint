"""CLI behavior tests for SattLint."""

from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

import sattlint
from sattlint import app, app_base
from sattlint.cli import entry as cli_entry


def _run_base_cli(argv: list[str], **overrides) -> int:
    kwargs = {
        "config_path": app.CONFIG_PATH,
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


def test_run_cli_quiet_suppresses_stdout(monkeypatch, capsys):
    monkeypatch.setattr(app_base, "run_syntax_check_command", lambda _path: print("visible") or app_base.EXIT_SUCCESS)

    exit_code = _run_base_cli(["--quiet", "syntax-check", "dummy.s"])

    captured = capsys.readouterr()
    assert exit_code == app_base.EXIT_SUCCESS
    assert captured.out == ""


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
