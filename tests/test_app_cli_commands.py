# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportPrivateUsage=false, reportArgumentType=false, reportMissingTypeArgument=false
"""Focused CLI command delegation tests for the app module."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

from sattline_parser.models.ast_model import BasePicture
from sattlint import _app_startup, _app_startup_from_app, app
from sattlint import config as config_module
from sattlint.models.project_graph import ProjectGraph


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


def test_run_docgen_command_delegates_to_cli_owner(monkeypatch):
    seen: dict[str, object] = {}

    def fake_run_docgen_command(
        cfg: dict,
        *,
        use_cache: bool,
        output_dir: str | None,
        output_path: str | None,
        iter_loaded_projects_fn,
        documentation_unit_selection_fn,
        exit_success: int,
        exit_usage_error: int,
    ) -> int:
        seen["cfg"] = cfg
        seen["use_cache"] = use_cache
        seen["output_dir"] = output_dir
        seen["output_path"] = output_path
        seen["iter_loaded_projects_fn"] = iter_loaded_projects_fn
        seen["documentation_unit_selection_fn"] = documentation_unit_selection_fn
        seen["exit_success"] = exit_success
        seen["exit_usage_error"] = exit_usage_error
        return 79

    monkeypatch.setattr(
        app.app_cli_commands_module,
        "run_docgen_command",
        fake_run_docgen_command,
    )

    cfg = {"debug": False}
    result = app.run_docgen_command(
        cfg,
        use_cache=False,
        output_dir="docs-out",
        output_path=None,
    )

    assert result == 79
    assert seen["cfg"] is cfg
    assert seen["use_cache"] is False
    assert seen["output_dir"] == "docs-out"
    assert seen["output_path"] is None
    assert callable(seen["iter_loaded_projects_fn"])
    assert seen["documentation_unit_selection_fn"] is app._get_documentation_unit_selection
    assert seen["exit_success"] == app.EXIT_SUCCESS
    assert seen["exit_usage_error"] == app.EXIT_USAGE_ERROR


def test_run_cache_prune_command_delegates_to_cli_owner(monkeypatch):
    seen: dict[str, object] = {}

    def fake_run_cache_prune_command(
        *,
        cache_dir: str | None,
        prune_cache_dir_fn,
        get_cache_dir_fn,
        exit_success: int,
        exit_usage_error: int,
    ) -> int:
        seen["cache_dir"] = cache_dir
        seen["prune_cache_dir_fn"] = prune_cache_dir_fn
        seen["get_cache_dir_fn"] = get_cache_dir_fn
        seen["exit_success"] = exit_success
        seen["exit_usage_error"] = exit_usage_error
        return 80

    monkeypatch.setattr(app.app_cli_commands_module, "run_cache_prune_command", fake_run_cache_prune_command)

    result = app.run_cache_prune_command(cache_dir="custom-cache")

    assert result == 80
    assert seen["cache_dir"] == "custom-cache"
    assert seen["prune_cache_dir_fn"] is app.cache.prune_cache_dir
    assert seen["get_cache_dir_fn"] is app.get_cache_dir
    assert seen["exit_success"] == app.EXIT_SUCCESS
    assert seen["exit_usage_error"] == app.EXIT_USAGE_ERROR


def test_run_telemetry_summary_command_delegates_to_cli_owner(monkeypatch):
    seen: dict[str, object] = {}

    def fake_run_telemetry_summary_command(
        cfg: dict,
        *,
        config_path: Path,
        output_format: str,
        output_path: str | None,
        telemetry_output_path_fn,
        summarize_telemetry_fn,
        render_text_summary_fn,
        exit_success: int,
        exit_usage_error: int,
    ) -> int:
        seen["cfg"] = cfg
        seen["config_path"] = config_path
        seen["output_format"] = output_format
        seen["output_path"] = output_path
        seen["telemetry_output_path_fn"] = telemetry_output_path_fn
        seen["summarize_telemetry_fn"] = summarize_telemetry_fn
        seen["render_text_summary_fn"] = render_text_summary_fn
        seen["exit_success"] = exit_success
        seen["exit_usage_error"] = exit_usage_error
        return 81

    monkeypatch.setattr(
        app.app_cli_commands_module,
        "run_telemetry_summary_command",
        fake_run_telemetry_summary_command,
    )

    cfg = {"debug": False}
    result = app.run_telemetry_summary_command(
        cfg,
        config_path=Path("custom.toml"),
        output_format="json",
        output_path="summary.json",
    )

    assert result == 81
    assert seen["cfg"] is cfg
    assert seen["config_path"] == Path("custom.toml")
    assert seen["output_format"] == "json"
    assert seen["output_path"] == "summary.json"
    assert callable(seen["telemetry_output_path_fn"])
    assert callable(seen["summarize_telemetry_fn"])
    assert callable(seen["render_text_summary_fn"])
    assert seen["exit_success"] == app.EXIT_SUCCESS
    assert seen["exit_usage_error"] == app.EXIT_USAGE_ERROR


def test_run_simulate_command_delegates_to_cli_owner(monkeypatch):
    seen: dict[str, object] = {}

    def fake_run_simulate_command(
        cfg: dict,
        *,
        target_path: str,
        module_name: str,
        mode: str,
        max_scans: int,
        output_format: str,
        output_path: str | None,
        use_cache: bool,
        simulate_fn,
        exit_success: int,
        exit_usage_error: int,
    ) -> int:
        seen["cfg"] = cfg
        seen["target_path"] = target_path
        seen["module_name"] = module_name
        seen["mode"] = mode
        seen["max_scans"] = max_scans
        seen["output_format"] = output_format
        seen["output_path"] = output_path
        seen["use_cache"] = use_cache
        seen["simulate_fn"] = simulate_fn
        seen["exit_success"] = exit_success
        seen["exit_usage_error"] = exit_usage_error
        return 80

    monkeypatch.setattr(
        app.app_cli_commands_module,
        "run_simulate_command",
        fake_run_simulate_command,
    )

    cfg = {"debug": False}
    result = app.run_simulate_command(
        cfg,
        target_path="program.s",
        module_name="Main",
        mode="steady-state",
        max_scans=25,
        output_format="json",
        output_path="simulation.json",
        use_cache=False,
    )

    assert result == 80
    assert seen["cfg"] is cfg
    assert seen["target_path"] == "program.s"
    assert seen["module_name"] == "Main"
    assert seen["mode"] == "steady-state"
    assert seen["max_scans"] == 25
    assert seen["output_format"] == "json"
    assert seen["output_path"] == "simulation.json"
    assert seen["use_cache"] is False
    assert callable(seen["simulate_fn"])
    assert seen["exit_success"] == app.EXIT_SUCCESS
    assert seen["exit_usage_error"] == app.EXIT_USAGE_ERROR


def test_cli_owner_run_docgen_command_rejects_empty_project_set(capsys):
    cfg = {"documentation": {}}
    empty_projects: tuple[tuple[str, BasePicture, ProjectGraph], ...] = ()

    def iter_projects(_cfg: dict[Any, Any], _use_cache: bool) -> Iterator[tuple[str, BasePicture, ProjectGraph]]:
        return iter(empty_projects)

    exit_code = cast(Any, app.app_cli_commands_module.run_docgen_command)(
        cfg,
        use_cache=True,
        output_dir=None,
        output_path=None,
        iter_loaded_projects_fn=iter_projects,
        documentation_unit_selection_fn=lambda: {"mode": "all", "instance_paths": [], "moduletype_names": []},
        exit_success=app.EXIT_SUCCESS,
        exit_usage_error=app.EXIT_USAGE_ERROR,
    )

    out = capsys.readouterr().out
    assert exit_code == app.EXIT_USAGE_ERROR
    assert "No analyzed targets configured" in out


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


def test_cli_owner_run_telemetry_summary_command_prints_text(capsys):
    exit_code = app.app_cli_commands_module.run_telemetry_summary_command(
        {"debug": False},
        config_path=Path("config.toml"),
        output_format="text",
        output_path=None,
        telemetry_output_path_fn=lambda config_path: config_path.with_suffix(".telemetry.json"),
        summarize_telemetry_fn=lambda path: {"path": str(path), "events": 2},
        render_text_summary_fn=lambda summary: f"events={summary['events']}",
        exit_success=app.EXIT_SUCCESS,
        exit_usage_error=app.EXIT_USAGE_ERROR,
    )

    out = capsys.readouterr().out
    assert exit_code == app.EXIT_SUCCESS
    assert "events=2" in out


def test_cli_owner_run_telemetry_summary_command_writes_json_output(tmp_path):
    output_path = tmp_path / "reports" / "telemetry.json"

    exit_code = app.app_cli_commands_module.run_telemetry_summary_command(
        {"debug": False},
        config_path=Path("config.toml"),
        output_format="json",
        output_path=str(output_path),
        telemetry_output_path_fn=lambda config_path: config_path.with_suffix(".telemetry.json"),
        summarize_telemetry_fn=lambda _path: {"events": 3},
        render_text_summary_fn=lambda summary: f"events={summary['events']}",
        exit_success=app.EXIT_SUCCESS,
        exit_usage_error=app.EXIT_USAGE_ERROR,
    )

    assert exit_code == app.EXIT_SUCCESS
    assert '"events": 3' in output_path.read_text(encoding="utf-8")


def test_cli_owner_run_telemetry_summary_command_reports_missing_file(capsys):
    exit_code = app.app_cli_commands_module.run_telemetry_summary_command(
        {"debug": False},
        config_path=Path("config.toml"),
        output_format="text",
        output_path=None,
        telemetry_output_path_fn=lambda config_path: config_path.with_suffix(".telemetry.json"),
        summarize_telemetry_fn=lambda _path: (_ for _ in ()).throw(FileNotFoundError()),
        render_text_summary_fn=lambda summary: str(summary),
        exit_success=app.EXIT_SUCCESS,
        exit_usage_error=app.EXIT_USAGE_ERROR,
    )

    out = capsys.readouterr().out
    assert exit_code == app.EXIT_USAGE_ERROR
    assert "Telemetry file not found:" in out


def test_cli_owner_run_telemetry_summary_command_reports_write_failures(capsys, tmp_path):
    output_path = tmp_path / "telemetry"
    output_path.mkdir()

    exit_code = app.app_cli_commands_module.run_telemetry_summary_command(
        {"debug": False},
        config_path=Path("config.toml"),
        output_format="text",
        output_path=str(output_path),
        telemetry_output_path_fn=lambda config_path: config_path.with_suffix(".telemetry.json"),
        summarize_telemetry_fn=lambda _path: {"events": 4},
        render_text_summary_fn=lambda summary: f"events={summary['events']}",
        exit_success=app.EXIT_SUCCESS,
        exit_usage_error=app.EXIT_USAGE_ERROR,
    )

    out = capsys.readouterr().out
    assert exit_code == app.EXIT_USAGE_ERROR
    assert "Failed to write telemetry summary" in out


def test_cli_owner_run_telemetry_summary_command_reports_summary_errors(capsys):
    def fail_summary(_path: Path) -> dict[str, Any]:
        raise ValueError("bad telemetry")

    exit_code = app.app_cli_commands_module.run_telemetry_summary_command(
        {"debug": False},
        config_path=Path("config.toml"),
        output_format="text",
        output_path=None,
        telemetry_output_path_fn=lambda config_path: config_path.with_suffix(".telemetry.json"),
        summarize_telemetry_fn=fail_summary,
        render_text_summary_fn=lambda summary: str(summary),
        exit_success=app.EXIT_SUCCESS,
        exit_usage_error=app.EXIT_USAGE_ERROR,
    )

    out = capsys.readouterr().out
    assert exit_code == app.EXIT_USAGE_ERROR
    assert "Telemetry summary failed: bad telemetry" in out


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


def test_cli_owner_run_docgen_command_rejects_output_path_for_multiple_targets(capsys):
    cfg = {"documentation": {}}
    target_a_bp: BasePicture = cast(Any, object())
    target_a_graph = ProjectGraph()
    target_b_bp: BasePicture = cast(Any, object())
    target_b_graph = ProjectGraph()
    projects: list[tuple[str, BasePicture, ProjectGraph]] = [
        ("TargetA", target_a_bp, target_a_graph),
        ("TargetB", target_b_bp, target_b_graph),
    ]

    def iter_projects(_cfg: dict[Any, Any], _use_cache: bool) -> Iterator[tuple[str, BasePicture, ProjectGraph]]:
        return iter(projects)

    exit_code = cast(Any, app.app_cli_commands_module.run_docgen_command)(
        cfg,
        use_cache=True,
        output_dir=None,
        output_path="single.docx",
        iter_loaded_projects_fn=cast(Any, iter_projects),
        documentation_unit_selection_fn=lambda: {"mode": "all", "instance_paths": [], "moduletype_names": []},
        exit_success=app.EXIT_SUCCESS,
        exit_usage_error=app.EXIT_USAGE_ERROR,
    )

    out = capsys.readouterr().out
    assert exit_code == app.EXIT_USAGE_ERROR
    assert "output_path requires exactly one configured target" in out


def test_cli_owner_run_docgen_command_uses_explicit_output_path(monkeypatch):
    generated: list[str] = []

    monkeypatch.setattr(
        app.app_cli_commands_module,
        "generate_docx",
        lambda _bp, out_name, documentation_config, unavailable_libraries: generated.append(out_name),
    )

    cfg = {"documentation": {"classifications": {}}}
    target_bp: BasePicture = cast(Any, object())
    target_graph = ProjectGraph()
    projects: list[tuple[str, BasePicture, ProjectGraph]] = [("TargetA", target_bp, target_graph)]

    def iter_projects(_cfg: dict[Any, Any], _use_cache: bool) -> Iterator[tuple[str, BasePicture, ProjectGraph]]:
        return iter(projects)

    exit_code = app.app_cli_commands_module.run_docgen_command(
        cfg,
        use_cache=True,
        output_dir=None,
        output_path="custom.docx",
        iter_loaded_projects_fn=cast(Any, iter_projects),
        documentation_unit_selection_fn=lambda: {"mode": "all", "instance_paths": [], "moduletype_names": []},
        exit_success=app.EXIT_SUCCESS,
        exit_usage_error=app.EXIT_USAGE_ERROR,
    )

    assert exit_code == app.EXIT_SUCCESS
    assert generated == ["custom.docx"]


def test_cli_owner_run_docgen_command_creates_parent_dirs_for_output_path(tmp_path, monkeypatch):
    generated: list[str] = []

    monkeypatch.setattr(
        app.app_cli_commands_module,
        "generate_docx",
        lambda _bp, out_name, documentation_config, unavailable_libraries: generated.append(out_name),
    )

    cfg = {"documentation": {"classifications": {}}}
    target_bp: BasePicture = cast(Any, object())
    target_graph = ProjectGraph()
    output_path = tmp_path / "nested" / "docs" / "custom.docx"
    projects: list[tuple[str, BasePicture, ProjectGraph]] = [("TargetA", target_bp, target_graph)]

    def iter_projects(_cfg: dict[Any, Any], _use_cache: bool) -> Iterator[tuple[str, BasePicture, ProjectGraph]]:
        return iter(projects)

    exit_code = app.app_cli_commands_module.run_docgen_command(
        cfg,
        use_cache=True,
        output_dir=None,
        output_path=str(output_path),
        iter_loaded_projects_fn=cast(Any, iter_projects),
        documentation_unit_selection_fn=lambda: {"mode": "all", "instance_paths": [], "moduletype_names": []},
        exit_success=app.EXIT_SUCCESS,
        exit_usage_error=app.EXIT_USAGE_ERROR,
    )

    assert exit_code == app.EXIT_SUCCESS
    assert output_path.parent.exists()
    assert generated == [str(output_path)]


def test_cli_owner_run_docgen_command_writes_output_dir_file(tmp_path, monkeypatch):
    generated: list[tuple[str, set[str]]] = []

    monkeypatch.setattr(
        app.app_cli_commands_module,
        "generate_docx",
        lambda _bp, out_name, documentation_config, unavailable_libraries: generated.append(
            (out_name, set(unavailable_libraries))
        ),
    )

    cfg = {"documentation": {"classifications": {}}}
    output_dir = tmp_path / "docs"
    target_bp: BasePicture = cast(Any, object())
    target_graph = ProjectGraph()
    target_graph.unavailable_libraries = {"ControlLib"}
    projects: list[tuple[str, BasePicture, ProjectGraph]] = [("TargetA", target_bp, target_graph)]

    def iter_projects(_cfg: dict[Any, Any], _use_cache: bool) -> Iterator[tuple[str, BasePicture, ProjectGraph]]:
        return iter(projects)

    exit_code = app.app_cli_commands_module.run_docgen_command(
        cfg,
        use_cache=True,
        output_dir=str(output_dir),
        output_path=None,
        iter_loaded_projects_fn=cast(Any, iter_projects),
        documentation_unit_selection_fn=lambda: {"mode": "all", "instance_paths": [], "moduletype_names": []},
        exit_success=app.EXIT_SUCCESS,
        exit_usage_error=app.EXIT_USAGE_ERROR,
    )

    assert exit_code == app.EXIT_SUCCESS
    assert output_dir.exists()
    assert generated == [(str(output_dir / "TargetA_FS.docx"), {"ControlLib"})]


def test_cli_owner_run_docgen_command_uses_default_filename(monkeypatch):
    generated: list[str] = []

    monkeypatch.setattr(
        app.app_cli_commands_module,
        "generate_docx",
        lambda _bp, out_name, documentation_config, unavailable_libraries: generated.append(out_name),
    )

    cfg = {"documentation": {"classifications": {}}}
    target_bp: BasePicture = cast(Any, object())
    target_graph = ProjectGraph()
    projects: list[tuple[str, BasePicture, ProjectGraph]] = [("TargetA", target_bp, target_graph)]

    def iter_projects(_cfg: dict[Any, Any], _use_cache: bool) -> Iterator[tuple[str, BasePicture, ProjectGraph]]:
        return iter(projects)

    exit_code = app.app_cli_commands_module.run_docgen_command(
        cfg,
        use_cache=True,
        output_dir=None,
        output_path=None,
        iter_loaded_projects_fn=cast(Any, iter_projects),
        documentation_unit_selection_fn=lambda: {"mode": "all", "instance_paths": [], "moduletype_names": []},
        exit_success=app.EXIT_SUCCESS,
        exit_usage_error=app.EXIT_USAGE_ERROR,
    )

    assert exit_code == app.EXIT_SUCCESS
    assert generated == ["TargetA_FS.docx"]


def test_cli_owner_run_docgen_command_updates_live_status(monkeypatch):
    updates: list[str] = []

    class FakeLiveStatusLine:
        def __enter__(self):
            return updates.append

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(app.app_cli_commands_module.console_module, "live_status_line", lambda: FakeLiveStatusLine())
    monkeypatch.setattr(
        app.app_cli_commands_module,
        "generate_docx",
        lambda _bp, out_name, documentation_config, unavailable_libraries: None,
    )

    cfg = {"documentation": {"classifications": {}}}
    target_bp: BasePicture = cast(Any, object())
    target_graph = ProjectGraph()
    projects: list[tuple[str, BasePicture, ProjectGraph]] = [("TargetA", target_bp, target_graph)]

    def iter_projects(_cfg: dict[Any, Any], _use_cache: bool) -> Iterator[tuple[str, BasePicture, ProjectGraph]]:
        return iter(projects)

    exit_code = app.app_cli_commands_module.run_docgen_command(
        cfg,
        use_cache=True,
        output_dir=None,
        output_path=None,
        iter_loaded_projects_fn=cast(Any, iter_projects),
        documentation_unit_selection_fn=lambda: {"mode": "all", "instance_paths": [], "moduletype_names": []},
        exit_success=app.EXIT_SUCCESS,
        exit_usage_error=app.EXIT_USAGE_ERROR,
    )

    assert exit_code == app.EXIT_SUCCESS
    assert updates == ["Generating documentation for TargetA"]


def test_cli_owner_run_docgen_command_reports_write_errors(capsys, tmp_path, monkeypatch):
    def fail_docgen(_bp, out_name, documentation_config, unavailable_libraries):
        raise PermissionError(f"permission denied: {out_name}")

    monkeypatch.setattr(app.app_cli_commands_module, "generate_docx", fail_docgen)

    cfg = {"documentation": {"classifications": {}}}
    target_bp: BasePicture = cast(Any, object())
    target_graph = ProjectGraph()
    output_path = tmp_path / "protected" / "custom.docx"
    projects: list[tuple[str, BasePicture, ProjectGraph]] = [("TargetA", target_bp, target_graph)]

    def iter_projects(_cfg: dict[Any, Any], _use_cache: bool) -> Iterator[tuple[str, BasePicture, ProjectGraph]]:
        return iter(projects)

    exit_code = app.app_cli_commands_module.run_docgen_command(
        cfg,
        use_cache=True,
        output_dir=None,
        output_path=str(output_path),
        iter_loaded_projects_fn=cast(Any, iter_projects),
        documentation_unit_selection_fn=lambda: {"mode": "all", "instance_paths": [], "moduletype_names": []},
        exit_success=app.EXIT_SUCCESS,
        exit_usage_error=app.EXIT_USAGE_ERROR,
    )

    out = capsys.readouterr().out
    assert exit_code == app.EXIT_USAGE_ERROR
    assert f"Documentation generation failed for {output_path}" in out
    assert "permission denied" in out


def test_cli_owner_run_simulate_command_writes_json_output(tmp_path):
    output_path = tmp_path / "simulation.json"

    class _FakeResult:
        def to_dict(self):
            return {
                "target": "Main",
                "mode": "steady-state",
                "steady_state_reached": True,
                "cycle_detected": False,
                "scan_budget_exhausted": False,
                "outcome": "steady-state",
                "total_scans": 2,
                "cycle_start_scan": None,
                "cycle_length": None,
                "snapshots": [{"scan": 1, "active_steps": ["Init"], "state": {"Counter": 1}}],
            }

        def render_summary(self):
            return "steady state reached after 2 scans"

    exit_code = app.app_cli_commands_module.run_simulate_command(
        {"debug": False},
        target_path="program.s",
        module_name="Main",
        mode="steady-state",
        max_scans=25,
        output_format="json",
        output_path=str(output_path),
        use_cache=False,
        simulate_fn=lambda cfg, **kwargs: _FakeResult(),
        exit_success=app.EXIT_SUCCESS,
        exit_usage_error=app.EXIT_USAGE_ERROR,
    )

    assert exit_code == app.EXIT_SUCCESS
    payload = output_path.read_text(encoding="utf-8")
    assert '"target": "Main"' in payload
    assert '"steady_state_reached": true' in payload


def test_cli_owner_run_simulate_command_prints_text_summary(capsys):
    class _FakeResult:
        def to_dict(self):
            return {"ignored": True}

        def render_summary(self):
            return "steady state reached after 2 scans"

    exit_code = app.app_cli_commands_module.run_simulate_command(
        {"debug": False},
        target_path="program.s",
        module_name="Main",
        mode="steady-state",
        max_scans=25,
        output_format="text",
        output_path=None,
        use_cache=False,
        simulate_fn=lambda cfg, **kwargs: _FakeResult(),
        exit_success=app.EXIT_SUCCESS,
        exit_usage_error=app.EXIT_USAGE_ERROR,
    )

    out = capsys.readouterr().out
    assert exit_code == app.EXIT_SUCCESS
    assert "steady state reached after 2 scans" in out


def test_cli_owner_run_simulate_command_prints_json_output(capsys):
    class _FakeResult:
        def to_dict(self):
            return {"target": "Main", "steady_state_reached": True}

        def render_summary(self):
            return "ignored"

    exit_code = app.app_cli_commands_module.run_simulate_command(
        {"debug": False},
        target_path="program.s",
        module_name="Main",
        mode="steady-state",
        max_scans=25,
        output_format="json",
        output_path=None,
        use_cache=False,
        simulate_fn=lambda cfg, **kwargs: _FakeResult(),
        exit_success=app.EXIT_SUCCESS,
        exit_usage_error=app.EXIT_USAGE_ERROR,
    )

    out = capsys.readouterr().out
    assert exit_code == app.EXIT_SUCCESS
    assert '"target": "Main"' in out


def test_cli_owner_run_simulate_command_reports_unexpected_failures(capsys):
    def fail_simulation(cfg: dict[str, Any], **kwargs: object) -> object:
        raise RuntimeError("boom")

    exit_code = app.app_cli_commands_module.run_simulate_command(
        {"debug": False},
        target_path="program.s",
        module_name="Main",
        mode="steady-state",
        max_scans=25,
        output_format="text",
        output_path=None,
        use_cache=False,
        simulate_fn=fail_simulation,
        exit_success=app.EXIT_SUCCESS,
        exit_usage_error=app.EXIT_USAGE_ERROR,
    )

    out = capsys.readouterr().out
    assert exit_code == app.EXIT_USAGE_ERROR
    assert "Simulation failed: boom" in out


def test_cli_owner_run_simulate_command_writes_text_output(tmp_path):
    output_path = tmp_path / "simulation.txt"

    class _FakeResult:
        def to_dict(self):
            return {"ignored": True}

        def render_summary(self):
            return "steady state reached after 2 scans"

    exit_code = app.app_cli_commands_module.run_simulate_command(
        {"debug": False},
        target_path="program.s",
        module_name="Main",
        mode="steady-state",
        max_scans=25,
        output_format="text",
        output_path=str(output_path),
        use_cache=False,
        simulate_fn=lambda cfg, **kwargs: _FakeResult(),
        exit_success=app.EXIT_SUCCESS,
        exit_usage_error=app.EXIT_USAGE_ERROR,
    )

    assert exit_code == app.EXIT_SUCCESS
    assert output_path.read_text(encoding="utf-8") == "steady state reached after 2 scans\n"


def test_cli_owner_run_simulate_command_reports_text_write_failures(capsys, tmp_path):
    output_path = tmp_path / "simulation-dir"
    output_path.mkdir()

    class _FakeResult:
        def to_dict(self):
            return {"ignored": True}

        def render_summary(self):
            return "steady state reached after 2 scans"

    exit_code = app.app_cli_commands_module.run_simulate_command(
        {"debug": False},
        target_path="program.s",
        module_name="Main",
        mode="steady-state",
        max_scans=25,
        output_format="text",
        output_path=str(output_path),
        use_cache=False,
        simulate_fn=lambda cfg, **kwargs: _FakeResult(),
        exit_success=app.EXIT_SUCCESS,
        exit_usage_error=app.EXIT_USAGE_ERROR,
    )

    out = capsys.readouterr().out
    assert exit_code == app.EXIT_USAGE_ERROR
    assert "Failed to write simulation output" in out


def test_cli_owner_run_simulate_command_updates_live_status(monkeypatch):
    updates: list[str] = []

    class FakeLiveStatusLine:
        def __enter__(self):
            return updates.append

        def __exit__(self, exc_type, exc, tb):
            return False

    class _FakeResult:
        def to_dict(self):
            return {"target": "Main"}

        def render_summary(self):
            return "steady state reached"

    monkeypatch.setattr(app.app_cli_commands_module.console_module, "live_status_line", lambda: FakeLiveStatusLine())
    monkeypatch.setattr(app.app_cli_commands_module, "emit_output", lambda *_args, **_kwargs: None)

    exit_code = app.app_cli_commands_module.run_simulate_command(
        {"debug": False},
        target_path="program.s",
        module_name="Main",
        mode="steady-state",
        max_scans=25,
        output_format="text",
        output_path=None,
        use_cache=False,
        simulate_fn=lambda cfg, **kwargs: _FakeResult(),
        exit_success=app.EXIT_SUCCESS,
        exit_usage_error=app.EXIT_USAGE_ERROR,
    )

    assert exit_code == app.EXIT_SUCCESS
    assert updates == ["Simulating Main from program.s"]


def test_cli_owner_run_simulate_command_reports_output_write_errors(capsys, tmp_path):
    output_path = tmp_path / "protected" / "simulation.json"

    class _FakeResult:
        def to_dict(self):
            return {"target": "Main"}

        def render_summary(self):
            return "steady state reached"

    original_write_text = Path.write_text

    def fail_write_text(self: Path, *args: object, **kwargs: object) -> int:
        if self == output_path:
            raise PermissionError("locked")
        return original_write_text(self, *args, **kwargs)

    from pathlib import Path as _Path  # noqa: PLC0415

    # Monkeypatch the concrete Path type used by app_cli_commands.
    _Path.write_text = fail_write_text
    try:
        exit_code = app.app_cli_commands_module.run_simulate_command(
            {"debug": False},
            target_path="program.s",
            module_name="Main",
            mode="steady-state",
            max_scans=25,
            output_format="json",
            output_path=str(output_path),
            use_cache=False,
            simulate_fn=lambda cfg, **kwargs: _FakeResult(),
            exit_success=app.EXIT_SUCCESS,
            exit_usage_error=app.EXIT_USAGE_ERROR,
        )
    finally:
        _Path.write_text = original_write_text

    out = capsys.readouterr().out
    assert exit_code == app.EXIT_USAGE_ERROR
    assert f"Failed to write simulation output to {output_path}" in out
    assert "locked" in out


def test_cli_owner_run_simulate_command_reports_usage_errors(capsys):
    exit_code = app.app_cli_commands_module.run_simulate_command(
        {"debug": False},
        target_path="program.s",
        module_name="Main",
        mode="steady-state",
        max_scans=0,
        output_format="text",
        output_path=None,
        use_cache=False,
        simulate_fn=lambda cfg, **kwargs: (_ for _ in ()).throw(ValueError("max_scans must be positive")),
        exit_success=app.EXIT_SUCCESS,
        exit_usage_error=app.EXIT_USAGE_ERROR,
    )

    out = capsys.readouterr().out
    assert exit_code == app.EXIT_USAGE_ERROR
    assert "max_scans must be positive" in out
