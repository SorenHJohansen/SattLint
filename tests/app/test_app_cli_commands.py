# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportPrivateUsage=false, reportArgumentType=false, reportMissingTypeArgument=false
"""Focused CLI command delegation tests for the app module."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

from sattlint import cache as cache_module
from sattlint import config as config_module
from sattlint.application import checks as checks_module
from sattlint.application import project as project_application
from sattlint.cli import _command_implementations as app_cli_commands_module
from sattlint.cli import commands as commands_application
from sattlint.cli._exit_codes import EXIT_SUCCESS, EXIT_USAGE_ERROR


def test_run_validate_config_command_delegates_to_cli_owner(monkeypatch, capsys) -> None:
    seen: dict[str, object] = {}

    def fake_validate_effective_config(local_cfg):
        seen["cfg"] = local_cfg
        return config_module.ConfigValidationResult(
            passed=False,
            errors=[
                config_module.ConfigValidationError(
                    key_path="analyzed_programs_and_libraries[0]",
                    message="MissingTarget (not found)",
                )
            ],
        )

    monkeypatch.setattr(commands_application, "validate_effective_config", fake_validate_effective_config)

    cfg = {"debug": False}
    result = commands_application.run_validate_config_command(
        cfg,
        config_path=Path("custom.toml"),
        default_used=True,
        output_format="json",
    )

    out = json.loads(capsys.readouterr().out)
    assert result == EXIT_USAGE_ERROR
    assert commands_application.run_validate_config_command is commands_application.run_validate_config_command
    assert seen["cfg"] is cfg
    assert out["config_path"] == "custom.toml"
    assert out["default_used"] is True
    assert out["passed"] is False


def test_run_analyze_command_delegates_to_cli_owner(monkeypatch) -> None:
    seen: dict[str, object] = {}

    def fake_run_analyze_command(
        cfg: dict,
        *,
        selected_keys: list[str] | None,
        selected_issue_kinds: frozenset[str] | None = None,
        output_format: str,
        collect_analyze_result_fn,
        exit_success: int,
    ) -> int:
        seen["cfg"] = cfg
        seen["selected_keys"] = selected_keys
        seen["selected_issue_kinds"] = selected_issue_kinds
        seen["output_format"] = output_format
        seen["collect_analyze_result_fn"] = collect_analyze_result_fn
        seen["exit_success"] = exit_success
        return 78

    monkeypatch.setattr(app_cli_commands_module, "run_analyze_command", fake_run_analyze_command)

    cfg = {"debug": False}
    result = commands_application.run_analyze_command(
        cfg,
        selected_keys=["variables"],
        selected_issue_kinds=frozenset({"unused"}),
        use_cache=False,
        output_format="json",
    )

    assert result == 78
    assert commands_application.run_analyze_command is commands_application.run_analyze_command
    assert seen["cfg"] is cfg
    assert seen["selected_keys"] == ["variables"]
    assert seen["selected_issue_kinds"] == frozenset({"unused"})
    assert seen["output_format"] == "json"
    assert seen["exit_success"] == EXIT_SUCCESS


def test_run_analyze_command_allows_opt_in_analyzer_keys(monkeypatch) -> None:
    seen: dict[str, object] = {}

    def fake_collect_run_checks_result(
        cfg: dict,
        selected_keys: list[str] | None,
        selected_issue_kinds: frozenset[str] | None = None,
        *,
        use_cache: bool = True,
        persist_run: bool = False,
        iter_loaded_projects_fn,
        get_enabled_analyzers_fn,
        target_is_library_fn,
    ) -> object:
        del cfg, iter_loaded_projects_fn, target_is_library_fn
        seen["selected_keys"] = selected_keys
        seen["selected_issue_kinds"] = selected_issue_kinds
        seen["use_cache"] = use_cache
        seen["persist_run"] = persist_run
        seen["analyzer_keys"] = [spec.key for spec in get_enabled_analyzers_fn()]
        return SimpleNamespace(output_lines=(), cancelled=False)

    monkeypatch.setattr(checks_module, "collect_run_checks_result", fake_collect_run_checks_result)
    monkeypatch.setattr(project_application, "iter_loaded_projects", lambda _cfg, *, use_cache: iter(()))

    result = commands_application.run_analyze_command(
        {"debug": False},
        selected_keys=["timing"],
        selected_issue_kinds=frozenset({"unused"}),
        use_cache=False,
        output_format="json",
    )

    assert result == 0
    assert seen["selected_keys"] == ["timing"]
    assert seen["selected_issue_kinds"] == frozenset({"unused"})
    assert "timing" in cast(list[str], seen["analyzer_keys"])


def test_run_cache_prune_command_delegates_to_cli_owner(monkeypatch):
    seen: dict[str, object] = {}

    def fake_run_cache_prune_command(
        *,
        cache_dir: str | None,
        output_format: str,
        prune_cache_dir_fn,
        get_cache_dir_fn,
        exit_success: int,
        exit_usage_error: int,
    ) -> int:
        seen["cache_dir"] = cache_dir
        seen["output_format"] = output_format
        seen["prune_cache_dir_fn"] = prune_cache_dir_fn
        seen["get_cache_dir_fn"] = get_cache_dir_fn
        seen["exit_success"] = exit_success
        seen["exit_usage_error"] = exit_usage_error
        return 80

    monkeypatch.setattr(app_cli_commands_module, "run_cache_prune_command", fake_run_cache_prune_command)

    result = commands_application.run_cache_prune_command(cache_dir="custom-cache", output_format="json")

    assert result == 80
    assert seen["cache_dir"] == "custom-cache"
    assert seen["output_format"] == "json"
    assert seen["prune_cache_dir_fn"] is cache_module.prune_cache_dir
    assert seen["get_cache_dir_fn"] is cache_module.get_cache_dir
    assert seen["exit_success"] == EXIT_SUCCESS
    assert seen["exit_usage_error"] == EXIT_USAGE_ERROR


def test_cli_owner_run_cache_prune_command_prints_json_output(capsys):
    exit_code = app_cli_commands_module.run_cache_prune_command(
        cache_dir="custom-cache",
        output_format="json",
        prune_cache_dir_fn=lambda _path: cache_module.CachePruneResult(
            file_lookup_entries=1,
            file_ast_entries=1,
            ast_payload_entries=0,
            ast_manifest_entries=0,
            analysis_report_entries=0,
        ),
        get_cache_dir_fn=lambda: Path("unused"),
        exit_success=EXIT_SUCCESS,
        exit_usage_error=EXIT_USAGE_ERROR,
    )

    out = capsys.readouterr().out
    assert exit_code == EXIT_SUCCESS
    assert json.loads(out) == {
        "status": "ok",
        "cache_dir": "custom-cache",
        "removed_entries": 2,
        "details": {
            "lookup": 1,
            "file_ast": 1,
            "ast_payload": 0,
            "ast_manifest": 0,
            "analysis_report": 0,
        },
    }


def test_startup_run_validate_config_command_warns_on_default_config(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        commands_application,
        "validate_effective_config",
        lambda _cfg: config_module.ConfigValidationResult(
            passed=False,
            errors=[
                config_module.ConfigValidationError(
                    key_path="analyzed_programs_and_libraries[0]",
                    message="MissingTarget (not found)",
                )
            ],
        ),
    )

    exit_code = commands_application.run_validate_config_command(
        {"debug": False},
        config_path=Path("default.toml"),
        default_used=True,
    )

    out = capsys.readouterr().out
    assert exit_code == EXIT_USAGE_ERROR
    assert "Warning: default config loaded from default.toml" in out
    assert "MissingTarget (not found)" in out


def test_startup_run_validate_config_command_prints_json(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        commands_application,
        "validate_effective_config",
        lambda _cfg: config_module.ConfigValidationResult(
            passed=False,
            errors=[
                config_module.ConfigValidationError(
                    key_path="analyzed_programs_and_libraries[0]",
                    message="MissingTarget (not found)",
                )
            ],
        ),
    )

    exit_code = commands_application.run_validate_config_command(
        {"debug": False},
        config_path=Path("default.toml"),
        default_used=True,
        output_format="json",
    )

    out = capsys.readouterr().out
    assert exit_code == EXIT_USAGE_ERROR
    assert json.loads(out) == {
        "config_path": "default.toml",
        "default_used": True,
        "errors": [
            {
                "key_path": "analyzed_programs_and_libraries[0]",
                "message": "MissingTarget (not found)",
            }
        ],
        "passed": False,
    }


def test_startup_run_analyze_command_delegates_and_returns_success(monkeypatch) -> None:
    seen: dict[str, object] = {}

    def fake_run_analyze_command(
        cfg: dict,
        *,
        selected_keys: list[str] | None,
        selected_issue_kinds: frozenset[str] | None = None,
        output_format: str,
        collect_analyze_result_fn,
        exit_success: int,
    ) -> int:
        seen.update(
            {
                "cfg": cfg,
                "selected_keys": selected_keys,
                "selected_issue_kinds": selected_issue_kinds,
                "output_format": output_format,
                "collected": collect_analyze_result_fn(
                    cfg,
                    selected_keys=selected_keys,
                    selected_issue_kinds=selected_issue_kinds,
                ),
                "exit_success": exit_success,
            }
        )
        return exit_success

    monkeypatch.setattr(app_cli_commands_module, "run_analyze_command", fake_run_analyze_command)
    monkeypatch.setattr(
        checks_module,
        "collect_run_checks_result",
        lambda cfg, selected_keys, *, selected_issue_kinds=None, use_cache=True, **_kwargs: SimpleNamespace(
            output_lines=(str(use_cache), str(selected_keys), str(selected_issue_kinds)),
            cancelled=False,
        ),
    )
    monkeypatch.setattr(project_application, "iter_loaded_projects", lambda _cfg, *, use_cache: iter(()))

    exit_code = commands_application.run_analyze_command(
        {"debug": False},
        selected_keys=["variables"],
        selected_issue_kinds=frozenset({"unused"}),
        use_cache=False,
    )

    assert exit_code == EXIT_SUCCESS
    assert seen["cfg"] == {"debug": False}
    assert seen["selected_keys"] == ["variables"]
    assert seen["selected_issue_kinds"] == frozenset({"unused"})
    assert seen["output_format"] == "text"
    assert cast(Any, seen["collected"]).output_lines == ("False", "['variables']", "frozenset({'unused'})")
    assert seen["exit_success"] == EXIT_SUCCESS


def test_cli_owner_run_analyze_command_renders_collected_output(capsys) -> None:
    exit_code = app_cli_commands_module.run_analyze_command(
        {"debug": False},
        selected_keys=["variables"],
        selected_issue_kinds=frozenset({"unused"}),
        output_format="text",
        collect_analyze_result_fn=lambda _cfg, *, selected_keys, selected_issue_kinds=None: SimpleNamespace(
            output_lines=(f"checks={selected_keys}", f"issues={selected_issue_kinds}"),
            cancelled=False,
        ),
        exit_success=EXIT_SUCCESS,
    )

    out = capsys.readouterr().out.splitlines()
    assert exit_code == EXIT_SUCCESS
    assert out == ["checks=['variables']", "issues=frozenset({'unused'})"]


def test_cli_owner_run_analyze_command_prints_json_output(capsys) -> None:
    exit_code = app_cli_commands_module.run_analyze_command(
        {"debug": False},
        selected_keys=["variables"],
        selected_issue_kinds=frozenset({"unused"}),
        output_format="json",
        collect_analyze_result_fn=lambda _cfg, *, selected_keys, selected_issue_kinds=None: SimpleNamespace(
            output_lines=(f"checks={selected_keys}", f"issues={selected_issue_kinds}"),
            cancelled=False,
            selected_analyzers=("variables",),
            targets=(
                SimpleNamespace(
                    target_name="TargetA",
                    is_library=False,
                    analyzers=(
                        SimpleNamespace(
                            key="variables",
                            name="Variable issues",
                            status="completed",
                            summary="variables summary",
                            report_kind="VariablesReport",
                            issue_count=2,
                            duration_ms=12.5,
                            phase_timings_ms=({"phase": "scan", "duration_ms": 1.5},),
                            selected_issue_kinds=("unused",),
                            skip_reason=None,
                        ),
                    ),
                    stage_timings_ms={"load_or_parse": 500.0},
                    graphics_timings_ms={"correlate-picture-display": 125.0},
                    ast_cache_counts={"ast_requests": 1, "parses": 1},
                    stage_timings_by_program_ms={"TargetA": {"load_or_parse": 500.0}},
                    loaded_from_cache=False,
                    analyzer_bottleneck={"kind": "analyzer", "name": "variables", "duration_ms": 12.5},
                    analyzer_phase_bottleneck={"kind": "analyzer-phase", "duration_ms": 1.5},
                    shared_artifact_profile=None,
                ),
            ),
        ),
        exit_success=EXIT_SUCCESS,
    )

    out = capsys.readouterr().out
    assert exit_code == EXIT_SUCCESS
    assert json.loads(out) == {
        "cancelled": False,
        "selected_checks": ["variables"],
        "selected_issue_kinds": ["unused"],
        "selected_analyzers": ["variables"],
        "targets": [
            {
                "target_name": "TargetA",
                "is_library": False,
                "analyzers": [
                    {
                        "key": "variables",
                        "name": "Variable issues",
                        "status": "completed",
                        "summary": "variables summary",
                        "report_kind": "VariablesReport",
                        "issue_count": 2,
                        "findings": [],
                        "duration_ms": 12.5,
                        "phase_timings_ms": [{"phase": "scan", "duration_ms": 1.5}],
                        "selected_issue_kinds": ["unused"],
                        "skip_reason": None,
                    }
                ],
                "stage_timings_ms": {"load_or_parse": 500.0},
                "graphics_timings_ms": {"correlate-picture-display": 125.0},
                "ast_cache_counts": {"ast_requests": 1, "parses": 1},
                "stage_timings_by_program_ms": {"TargetA": {"load_or_parse": 500.0}},
                "loaded_from_cache": False,
                "analyzer_bottleneck": {"kind": "analyzer", "name": "variables", "duration_ms": 12.5},
                "analyzer_phase_bottleneck": {"kind": "analyzer-phase", "duration_ms": 1.5},
                "shared_artifact_profile": None,
            }
        ],
    }
