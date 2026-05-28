"""Focused CLI command delegation tests for the app module."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast

from sattline_parser.models.ast_model import BasePicture
from sattlint import app
from sattlint import config as config_module
from sattlint.models.project_graph import ProjectGraph


def test_run_validate_config_command_delegates_to_cli_owner(monkeypatch):
    seen: dict[str, object] = {}

    def fake_run_validate_config_command(
        cfg: dict,
        *,
        config_path: Path,
        default_used: bool,
        validate_config_fn,
        exit_success: int,
        exit_usage_error: int,
    ) -> int:
        seen["cfg"] = cfg
        seen["config_path"] = config_path
        seen["default_used"] = default_used
        seen["validate_config_fn"] = validate_config_fn
        seen["exit_success"] = exit_success
        seen["exit_usage_error"] = exit_usage_error
        return 77

    monkeypatch.setattr(
        app.app_cli_commands_module,
        "run_validate_config_command",
        fake_run_validate_config_command,
    )

    cfg = {"debug": False}
    result = app.run_validate_config_command(cfg, config_path=Path("custom.toml"), default_used=True)

    assert result == 77
    assert seen["cfg"] is cfg
    assert seen["config_path"] == Path("custom.toml")
    assert seen["default_used"] is True
    assert seen["validate_config_fn"] is app.validate_effective_config
    assert seen["exit_success"] == app.EXIT_SUCCESS
    assert seen["exit_usage_error"] == app.EXIT_USAGE_ERROR


def test_run_analyze_command_delegates_to_cli_owner(monkeypatch):
    seen: dict[str, object] = {}

    def fake_run_analyze_command(
        cfg: dict,
        *,
        selected_keys: list[str] | None,
        use_cache: bool,
        run_checks_fn,
        exit_success: int,
    ) -> int:
        seen["cfg"] = cfg
        seen["selected_keys"] = selected_keys
        seen["use_cache"] = use_cache
        seen["run_checks_fn"] = run_checks_fn
        seen["exit_success"] = exit_success
        return 78

    monkeypatch.setattr(
        app.app_cli_commands_module,
        "run_analyze_command",
        fake_run_analyze_command,
    )

    cfg = {"debug": False}
    result = app.run_analyze_command(cfg, selected_keys=["variables"], use_cache=False)

    assert result == 78
    assert seen["cfg"] is cfg
    assert seen["selected_keys"] == ["variables"]
    assert seen["use_cache"] is False
    assert callable(seen["run_checks_fn"])
    assert seen["exit_success"] == app.EXIT_SUCCESS


def test_run_analyze_command_allows_opt_in_analyzer_keys(monkeypatch) -> None:
    seen: dict[str, object] = {}

    def fake_run_checks(
        cfg: dict,
        selected_keys: list[str] | None,
        *,
        iter_loaded_projects_fn,
        get_enabled_analyzers_fn,
        target_is_library_fn,
        pause_fn,
    ) -> None:
        del cfg, iter_loaded_projects_fn, target_is_library_fn, pause_fn
        seen["selected_keys"] = selected_keys
        seen["analyzer_keys"] = [spec.key for spec in get_enabled_analyzers_fn()]

    def fake_run_analyze_command(
        cfg: dict,
        *,
        selected_keys: list[str] | None,
        use_cache: bool,
        run_checks_fn,
        exit_success: int,
    ) -> int:
        del use_cache, exit_success
        run_checks_fn(cfg, selected_keys, False)
        return 0

    monkeypatch.setattr(app.app_analysis, "run_checks", fake_run_checks)
    monkeypatch.setattr(app.app_cli_commands_module, "run_analyze_command", fake_run_analyze_command)

    result = app.run_analyze_command({"debug": False}, selected_keys=["timing"], use_cache=False)

    assert result == 0
    assert seen["selected_keys"] == ["timing"]
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


def test_cli_owner_run_validate_config_command_warns_on_default_config(capsys):
    exit_code = app.app_cli_commands_module.run_validate_config_command(
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


def test_cli_owner_run_analyze_command_delegates_and_returns_success():
    seen: dict[str, object] = {}

    exit_code = app.app_cli_commands_module.run_analyze_command(
        {"debug": False},
        selected_keys=["variables"],
        use_cache=False,
        run_checks_fn=lambda cfg, selected_keys, use_cache: seen.update(
            {"cfg": cfg, "selected_keys": selected_keys, "use_cache": use_cache}
        ),
        exit_success=app.EXIT_SUCCESS,
    )

    assert exit_code == app.EXIT_SUCCESS
    assert seen["selected_keys"] == ["variables"]
    assert seen["use_cache"] is False


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

    from pathlib import Path as _Path

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
