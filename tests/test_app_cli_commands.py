# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportPrivateUsage=false, reportArgumentType=false, reportMissingTypeArgument=false
"""Focused CLI command delegation tests for the app module."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

from sattlint import _app_startup, _app_startup_from_app, app
from sattlint import config as config_module


def test_run_validate_config_command_delegates_to_startup_core(monkeypatch):
    seen: dict[str, object] = {}

    def fake_run_validate_config_command(
        cfg: dict,
        *,
        config_path: Path,
        default_used: bool,
        validate_config_fn,
        output_format: str,
        exit_success: int,
        exit_usage_error: int,
    ) -> int:
        seen["cfg"] = cfg
        seen["config_path"] = config_path
        seen["default_used"] = default_used
        seen["validate_config_fn"] = validate_config_fn
        seen["output_format"] = output_format
        seen["exit_success"] = exit_success
        seen["exit_usage_error"] = exit_usage_error
        return 77

    monkeypatch.setattr(
        _app_startup_from_app.startup_core,
        "run_validate_config_command",
        fake_run_validate_config_command,
    )

    cfg = {"debug": False}
    result = app.run_validate_config_command(
        cfg,
        config_path=Path("custom.toml"),
        default_used=True,
        output_format="json",
    )

    assert result == 77
    assert seen["cfg"] is cfg
    assert seen["config_path"] == Path("custom.toml")
    assert seen["default_used"] is True
    assert seen["validate_config_fn"] is app.validate_effective_config
    assert seen["output_format"] == "json"
    assert seen["exit_success"] == app.EXIT_SUCCESS
    assert seen["exit_usage_error"] == app.EXIT_USAGE_ERROR


def test_run_analyze_command_delegates_to_startup_core(monkeypatch):
    seen: dict[str, object] = {}

    def fake_run_analyze_command(
        cfg: dict,
        *,
        selected_keys: list[str] | None,
        selected_issue_kinds: frozenset[str] | None = None,
        use_cache: bool,
        output_format: str,
        run_analyze_command_fn,
        iter_loaded_projects_fn,
        collect_run_checks_result_fn,
        get_selectable_analyzers_fn,
        get_enabled_analyzers_fn,
        target_is_library_fn,
        exit_success: int,
    ) -> int:
        seen["cfg"] = cfg
        seen["selected_keys"] = selected_keys
        seen["selected_issue_kinds"] = selected_issue_kinds
        seen["use_cache"] = use_cache
        seen["output_format"] = output_format
        seen["run_analyze_command_fn"] = run_analyze_command_fn
        seen["iter_loaded_projects_fn"] = iter_loaded_projects_fn
        seen["collect_run_checks_result_fn"] = collect_run_checks_result_fn
        seen["get_selectable_analyzers_fn"] = get_selectable_analyzers_fn
        seen["get_enabled_analyzers_fn"] = get_enabled_analyzers_fn
        seen["target_is_library_fn"] = target_is_library_fn
        seen["exit_success"] = exit_success
        return 78

    monkeypatch.setattr(
        _app_startup_from_app.startup_core,
        "run_analyze_command",
        fake_run_analyze_command,
    )

    cfg = {"debug": False}
    result = app.run_analyze_command(
        cfg,
        selected_keys=["variables"],
        selected_issue_kinds=frozenset({"unused"}),
        use_cache=False,
        output_format="json",
    )

    assert result == 78
    assert seen["cfg"] is cfg
    assert seen["selected_keys"] == ["variables"]
    assert seen["selected_issue_kinds"] == frozenset({"unused"})
    assert seen["use_cache"] is False
    assert seen["output_format"] == "json"
    assert seen["run_analyze_command_fn"] is app.app_cli_commands.run_analyze_command
    assert seen["iter_loaded_projects_fn"] is app._iter_loaded_projects
    assert seen["collect_run_checks_result_fn"] is app.app_analysis_checks.collect_run_checks_result
    assert seen["get_selectable_analyzers_fn"] is app._get_selectable_analyzers
    assert seen["get_enabled_analyzers_fn"] is app._get_enabled_analyzers
    assert seen["target_is_library_fn"] is app._target_is_library
    assert seen["exit_success"] == app.EXIT_SUCCESS


def test_run_analyze_command_allows_opt_in_analyzer_keys(monkeypatch) -> None:
    seen: dict[str, object] = {}

    def fake_collect_run_checks_result(
        cfg: dict,
        selected_keys: list[str] | None,
        selected_issue_kinds: frozenset[str] | None = None,
        *,
        iter_loaded_projects_fn,
        get_enabled_analyzers_fn,
        target_is_library_fn,
    ) -> object:
        del cfg, iter_loaded_projects_fn, target_is_library_fn
        seen["selected_keys"] = selected_keys
        seen["selected_issue_kinds"] = selected_issue_kinds
        seen["analyzer_keys"] = [spec.key for spec in get_enabled_analyzers_fn()]
        return SimpleNamespace(output_lines=(), cancelled=False)

    monkeypatch.setattr(app.app_analysis_checks, "collect_run_checks_result", fake_collect_run_checks_result)

    result = _app_startup.run_analyze_command(
        {"debug": False},
        selected_keys=["timing"],
        selected_issue_kinds=frozenset({"unused"}),
        use_cache=False,
        output_format="json",
        run_analyze_command_fn=app.app_cli_commands_module.run_analyze_command,
        iter_loaded_projects_fn=lambda _cfg, *, use_cache: iter(()),
        collect_run_checks_result_fn=app.app_analysis_checks.collect_run_checks_result,
        get_selectable_analyzers_fn=app._get_selectable_analyzers,
        get_enabled_analyzers_fn=app._get_enabled_analyzers,
        target_is_library_fn=app._target_is_library,
        exit_success=0,
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

    monkeypatch.setattr(app.app_cli_commands_module, "run_cache_prune_command", fake_run_cache_prune_command)

    result = app.run_cache_prune_command(cache_dir="custom-cache", output_format="json")

    assert result == 80
    assert seen["cache_dir"] == "custom-cache"
    assert seen["output_format"] == "json"
    assert seen["prune_cache_dir_fn"] is app.cache.prune_cache_dir
    assert seen["get_cache_dir_fn"] is app.get_cache_dir
    assert seen["exit_success"] == app.EXIT_SUCCESS
    assert seen["exit_usage_error"] == app.EXIT_USAGE_ERROR


def test_cli_owner_run_cache_prune_command_prints_json_output(capsys):
    exit_code = app.app_cli_commands_module.run_cache_prune_command(
        cache_dir="custom-cache",
        output_format="json",
        prune_cache_dir_fn=lambda _path: app.cache.CachePruneResult(
            file_lookup_entries=1,
            file_ast_entries=1,
            ast_payload_entries=0,
            ast_manifest_entries=0,
            analysis_report_entries=0,
        ),
        get_cache_dir_fn=lambda: Path("unused"),
        exit_success=app.EXIT_SUCCESS,
        exit_usage_error=app.EXIT_USAGE_ERROR,
    )

    out = capsys.readouterr().out
    assert exit_code == app.EXIT_SUCCESS
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


def test_startup_run_validate_config_command_warns_on_default_config(capsys):
    exit_code = _app_startup.run_validate_config_command(
        {"debug": False},
        config_path=Path("default.toml"),
        default_used=True,
        validate_config_fn=lambda _cfg: config_module.ConfigValidationResult(
            passed=False,
            errors=(
                config_module.ConfigValidationError(
                    key_path="analyzed_programs_and_libraries[0]",
                    message="MissingTarget (not found)",
                ),
            ),
        ),
        exit_success=app.EXIT_SUCCESS,
        exit_usage_error=app.EXIT_USAGE_ERROR,
    )

    out = capsys.readouterr().out
    assert exit_code == app.EXIT_USAGE_ERROR
    assert "Warning: default config loaded from default.toml" in out
    assert "MissingTarget (not found)" in out


def test_startup_run_validate_config_command_prints_json(capsys):
    exit_code = _app_startup.run_validate_config_command(
        {"debug": False},
        config_path=Path("default.toml"),
        default_used=True,
        validate_config_fn=lambda _cfg: config_module.ConfigValidationResult(
            passed=False,
            errors=(
                config_module.ConfigValidationError(
                    key_path="analyzed_programs_and_libraries[0]",
                    message="MissingTarget (not found)",
                ),
            ),
        ),
        output_format="json",
        exit_success=app.EXIT_SUCCESS,
        exit_usage_error=app.EXIT_USAGE_ERROR,
    )

    out = capsys.readouterr().out
    assert exit_code == app.EXIT_USAGE_ERROR
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


def test_startup_run_analyze_command_delegates_and_returns_success():
    seen: dict[str, object] = {}

    exit_code = _app_startup.run_analyze_command(
        {"debug": False},
        selected_keys=["variables"],
        selected_issue_kinds=frozenset({"unused"}),
        use_cache=False,
        run_analyze_command_fn=lambda cfg, *, selected_keys, selected_issue_kinds=None, use_cache, output_format, collect_analyze_result_fn, exit_success: (
            seen.update(
                {
                    "cfg": cfg,
                    "selected_keys": selected_keys,
                    "selected_issue_kinds": selected_issue_kinds,
                    "use_cache": use_cache,
                    "output_format": output_format,
                    "collected": collect_analyze_result_fn(
                        cfg,
                        selected_keys=selected_keys,
                        selected_issue_kinds=selected_issue_kinds,
                    ),
                    "exit_success": exit_success,
                }
            )
            or exit_success
        ),
        iter_loaded_projects_fn=lambda _cfg, *, use_cache: iter(()),
        collect_run_checks_result_fn=lambda cfg, selected_keys, *, selected_issue_kinds=None, **_kwargs: (
            SimpleNamespace(
                output_lines=(str(cfg.get("use_cache")), str(selected_keys), str(selected_issue_kinds)),
                cancelled=False,
            )
        ),
        get_selectable_analyzers_fn=lambda: [],
        get_enabled_analyzers_fn=lambda: [],
        target_is_library_fn=lambda _cfg, _bp, _graph: False,
        exit_success=app.EXIT_SUCCESS,
    )

    assert exit_code == app.EXIT_SUCCESS
    assert seen["cfg"] == {"debug": False}
    assert seen["selected_keys"] == ["variables"]
    assert seen["selected_issue_kinds"] == frozenset({"unused"})
    assert seen["use_cache"] is False
    assert seen["output_format"] == "text"
    assert cast(Any, seen["collected"]).output_lines == ("False", "['variables']", "frozenset({'unused'})")
    assert seen["exit_success"] == app.EXIT_SUCCESS


def test_cli_owner_run_analyze_command_renders_collected_output(capsys) -> None:
    exit_code = app.app_cli_commands_module.run_analyze_command(
        {"debug": False},
        selected_keys=["variables"],
        selected_issue_kinds=frozenset({"unused"}),
        use_cache=False,
        output_format="text",
        collect_analyze_result_fn=lambda _cfg, *, selected_keys, selected_issue_kinds=None: SimpleNamespace(
            output_lines=(f"checks={selected_keys}", f"issues={selected_issue_kinds}"),
            cancelled=False,
        ),
        exit_success=app.EXIT_SUCCESS,
    )

    out = capsys.readouterr().out.splitlines()
    assert exit_code == app.EXIT_SUCCESS
    assert out == ["checks=['variables']", "issues=frozenset({'unused'})"]


def test_cli_owner_run_analyze_command_prints_json_output(capsys) -> None:
    exit_code = app.app_cli_commands_module.run_analyze_command(
        {"debug": False},
        selected_keys=["variables"],
        selected_issue_kinds=frozenset({"unused"}),
        use_cache=False,
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
                    analyzer_bottleneck={"kind": "analyzer", "name": "variables", "duration_ms": 12.5},
                    analyzer_phase_bottleneck={"kind": "analyzer-phase", "duration_ms": 1.5},
                    shared_artifact_profile=None,
                ),
            ),
        ),
        exit_success=app.EXIT_SUCCESS,
    )

    out = capsys.readouterr().out
    assert exit_code == app.EXIT_SUCCESS
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
                        "duration_ms": 12.5,
                        "phase_timings_ms": [{"phase": "scan", "duration_ms": 1.5}],
                        "selected_issue_kinds": ["unused"],
                        "skip_reason": None,
                    }
                ],
                "stage_timings_ms": {"load_or_parse": 500.0},
                "graphics_timings_ms": {"correlate-picture-display": 125.0},
                "analyzer_bottleneck": {"kind": "analyzer", "name": "variables", "duration_ms": 12.5},
                "analyzer_phase_bottleneck": {"kind": "analyzer-phase", "duration_ms": 1.5},
                "shared_artifact_profile": None,
            }
        ],
    }
