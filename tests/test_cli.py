"""CLI behavior tests for SattLint."""

import runpy
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

import sattlint
from sattlint import app, app_base, engine
from sattlint.cli import entry as cli_entry


def _run_base_cli(argv: list[str], **overrides) -> int:
    kwargs = {
        "config_path": app.CONFIG_PATH,
        "load_config_fn": lambda path: ({"debug": False}, False),
        "apply_debug_fn": lambda _cfg: None,
        "run_validate_config_command_fn": lambda cfg, *, config_path, default_used: app_base.EXIT_SUCCESS,
        "run_analyze_command_fn": lambda cfg, *, selected_keys, use_cache: app_base.EXIT_SUCCESS,
        "run_simulate_command_fn": (
            lambda cfg, *, target_path, module_name, mode, max_scans, output_format, output_path, use_cache: (
                app_base.EXIT_SUCCESS
            )
        ),
        "run_docgen_command_fn": lambda cfg, *, use_cache, output_dir, output_path: app_base.EXIT_SUCCESS,
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
    assert {"syntax-check", "analyze", "simulate", "docgen", "validate-config", "format-icf", "repo-audit"} <= set(
        choices
    )
    assert getattr(syntax_parser, "description", None)


def test_build_cli_parser_repo_audit_includes_dedicated_options():
    parser = app_base.build_cli_parser()

    action = next(action for action in parser._actions if getattr(action, "choices", None))
    choices = cast(dict[str, object], action.choices)
    repo_audit_parser = cast(Any, choices["repo-audit"])
    option_strings = {
        option
        for parser_action in repo_audit_parser._actions
        for option in getattr(parser_action, "option_strings", [])
    }

    assert {"--profile", "--fail-on", "--list-checks", "--planning-context"} <= option_strings


def test_run_cli_without_command_returns_usage_error():
    assert _run_base_cli([]) == app_base.EXIT_USAGE_ERROR


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


def test_run_cli_analyze_passes_opt_in_state_inference_key():
    seen = {}

    exit_code = cli_entry.run_cli(
        ["analyze", "--check", "state_inference"],
        config_path=app.CONFIG_PATH,
        load_config_fn=lambda path: ({"debug": False}, False),
        apply_debug_fn=lambda _cfg: None,
        run_validate_config_command_fn=lambda cfg, *, config_path, default_used: app_base.EXIT_SUCCESS,
        run_analyze_command_fn=lambda cfg, *, selected_keys, use_cache: (
            seen.update({"cfg": cfg, "selected_keys": selected_keys, "use_cache": use_cache}) or app_base.EXIT_SUCCESS
        ),
        run_docgen_command_fn=lambda cfg, *, use_cache, output_dir, output_path: app_base.EXIT_SUCCESS,
        run_format_icf_command_fn=lambda cfg, *, check: app_base.EXIT_SUCCESS,
    )

    assert exit_code == app_base.EXIT_SUCCESS
    assert seen["selected_keys"] == ["state_inference"]
    assert seen["use_cache"] is True


def test_run_cli_analyze_list_checks_prints_available_keys(monkeypatch, capsys):
    monkeypatch.setattr(
        "sattlint.analyzers.registry.get_default_analyzers",
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
