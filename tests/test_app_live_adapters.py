from __future__ import annotations

import runpy
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from sattline_parser.models.ast_model import BasePicture
from sattlint import _app_startup_from_app, app, app_graphics
from sattlint.models.project_graph import ProjectGraph


def test_analysis_menu_routes_through_live_app_adapter(monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = app.DEFAULT_CONFIG.copy()
    calls: list[tuple[str, object, object]] = []

    def fake_analysis_menu_from_app(local_cfg: object, *, app_module: object) -> None:
        calls.append(("analysis", local_cfg, app_module))
        cast(Any, app_module).variable_usage_submenu(local_cfg)

    def fake_variable_usage_submenu_from_app(local_cfg: object, *, app_module: object) -> None:
        calls.append(("variables", local_cfg, app_module))

    monkeypatch.setattr(
        app.app_analysis_from_app_module,
        "analysis_menu_from_app",
        fake_analysis_menu_from_app,
    )
    monkeypatch.setattr(
        app.app_analysis_from_app_module,
        "variable_usage_submenu_from_app",
        fake_variable_usage_submenu_from_app,
    )
    monkeypatch.setattr(
        app.app_analysis,
        "analysis_menu",
        lambda *_args, **_kwargs: pytest.fail("app.analysis_menu should use the live app adapter"),
    )
    monkeypatch.setattr(
        app.app_analysis,
        "variable_usage_submenu",
        lambda *_args, **_kwargs: pytest.fail("app.variable_usage_submenu should use the live app adapter"),
    )

    app.analysis_menu(cfg)

    assert [name for name, _cfg, _module in calls] == ["analysis", "variables"]
    assert all(local_cfg is cfg for _name, local_cfg, _module in calls)
    assert all(app_module is app for _name, _cfg, app_module in calls)


def test_remaining_interactive_menus_route_through_live_app_adapters(monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = app.DEFAULT_CONFIG.copy()
    calls: list[tuple[str, object, object]] = []

    monkeypatch.setattr(
        app.app_menus_from_app_module,
        "dump_menu_from_app",
        lambda local_cfg, *, app_module: calls.append(("dump", local_cfg, app_module)),
    )
    monkeypatch.setattr(
        app.app_menus_from_app_module,
        "config_menu_from_app",
        lambda local_cfg, *, app_module: calls.append(("config", local_cfg, app_module)) or True,
    )
    monkeypatch.setattr(
        app.app_menus_from_app_module,
        "tools_menu_from_app",
        lambda local_cfg, *, app_module: calls.append(("tools", local_cfg, app_module)),
    )
    monkeypatch.setattr(
        app.app_docs_from_app_module,
        "documentation_menu_from_app",
        lambda local_cfg, *, app_module: calls.append(("docs", local_cfg, app_module)) or True,
    )
    monkeypatch.setattr(
        app.app_graphics_from_app_module,
        "graphics_rules_menu_from_app",
        lambda local_cfg, *, app_module: calls.append(("graphics", local_cfg, app_module)),
    )
    monkeypatch.setattr(
        app.app_startup_module,
        "dump_menu_from_app",
        lambda *_args, **_kwargs: pytest.fail("app.dump_menu should use the live app adapter"),
    )
    monkeypatch.setattr(
        app.app_startup_module,
        "config_menu_from_app",
        lambda *_args, **_kwargs: pytest.fail("app.config_menu should use the live app adapter"),
    )
    monkeypatch.setattr(
        app.app_startup_module,
        "tools_menu_from_app",
        lambda *_args, **_kwargs: pytest.fail("app.tools_menu should use the live app adapter"),
    )
    monkeypatch.setattr(
        app.app_startup_module,
        "documentation_menu_from_app",
        lambda *_args, **_kwargs: pytest.fail("app.documentation_menu should use the live app adapter"),
    )
    monkeypatch.setattr(
        app.app_startup_module,
        "graphics_rules_menu_from_app",
        lambda *_args, **_kwargs: pytest.fail("app.graphics_rules_menu should use the live app adapter"),
    )

    app.dump_menu(cfg)
    assert app.config_menu(cfg) is True
    app.tools_menu(cfg)
    assert app.documentation_menu(cfg) is True
    app.graphics_rules_menu(cfg)

    assert [name for name, _cfg, _module in calls] == ["dump", "config", "tools", "docs", "graphics"]
    assert all(local_cfg is cfg for _name, local_cfg, _module in calls)
    assert all(app_module is app for _name, _cfg, app_module in calls)


def test_basic_app_wrappers_delegate_to_owner_modules(monkeypatch: pytest.MonkeyPatch) -> None:
    printed: list[tuple[list[str], int]] = []
    target_warning_calls: list[tuple[str, list[str]]] = []
    validation_calls: list[dict[str, object]] = []
    clear_calls: list[str] = []
    clear_screen_calls: list[dict[str, object]] = []
    pause_calls: list[str] = []
    target_exists_calls: list[tuple[str, dict[str, object]]] = []

    monkeypatch.setattr(
        app.app_support,
        "print_validation_warnings",
        lambda warnings, *, print_fn, limit: printed.append((list(warnings), limit)),
    )
    monkeypatch.setattr(
        app.app_support,
        "target_validation_warnings",
        lambda target_name, warnings: target_warning_calls.append((target_name, list(warnings))) or ["filtered"],
    )
    monkeypatch.setattr(
        app._config_module,
        "validate_effective_config",
        lambda cfg: validation_calls.append(cfg) or SimpleNamespace(ok=True),
    )
    monkeypatch.setattr(app.app_base, "clear_windows_console", lambda: clear_calls.append("clear"))
    monkeypatch.setattr(app.app_base, "pause", lambda: pause_calls.append("pause"))
    monkeypatch.setattr(
        app.app_base,
        "clear_screen",
        lambda **kwargs: clear_screen_calls.append(kwargs),
    )
    monkeypatch.setattr(
        app.app_base,
        "target_exists",
        lambda target, cfg: target_exists_calls.append((target, cfg)) or True,
    )

    cfg = {"mode": "draft"}
    app._print_validation_warnings(["warn"], limit=3)
    assert app._target_validation_warnings("Target", ["warn"]) == ["filtered"]
    assert app.validate_effective_config(cfg).ok is True
    app._clear_windows_console()
    app.clear_screen()
    app.pause()
    assert app.target_exists("Root", cfg) is True

    assert printed == [(["warn"], 3)]
    assert target_warning_calls == [("Target", ["warn"])]
    assert validation_calls == [cfg]
    assert clear_calls == ["clear"]
    assert clear_screen_calls[0]["clear_windows_console"] is app._clear_windows_console
    assert pause_calls == ["pause"]
    assert target_exists_calls == [("Root", cfg)]


def test_graphics_and_documentation_wrappers_delegate(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    rules_path = tmp_path / "graphics_rules.json"
    cfg = app.DEFAULT_CONFIG.copy()
    emitted: list[str] = []
    graphics_calls: list[tuple[str, object, object]] = []
    docs_calls: list[tuple[str, object, object]] = []

    monkeypatch.setattr(
        app.app_graphics,
        "load_graphics_rules",
        lambda config_path, path=None: (
            graphics_calls.append(("load-rules", config_path, path)) or ({"rules": []}, False)
        ),
    )
    monkeypatch.setattr(
        app.app_graphics,
        "save_graphics_rules",
        lambda path, rules: graphics_calls.append(("save-rules", path, rules)),
    )
    monkeypatch.setattr(app, "emit_output", emitted.append)
    monkeypatch.setattr(
        app.app_startup_module,
        "run_icf_formatter_from_app",
        lambda local_cfg, *, app_module: graphics_calls.append(("icf", local_cfg, app_module)),
    )
    monkeypatch.setattr(
        app.app_graphics_from_app_module,
        "prompt_graphics_rule_definition_with_config_from_app",
        lambda local_cfg, *, app_module: (
            graphics_calls.append(("prompt-rule", local_cfg, app_module)) or {"name": "Rule"}
        ),
    )
    monkeypatch.setattr(
        app.app_graphics_from_app_module,
        "collect_graphics_layout_entries_for_target_from_app",
        lambda target_name, project_bp, graph, *, app_module: (
            graphics_calls.append(("collect-layout", (target_name, project_bp, graph), app_module))
            or [{"target": target_name}]
        ),
    )
    monkeypatch.setattr(
        app.app_docs_from_app_module,
        "get_documentation_unit_selection_from_app",
        lambda *, app_module: docs_calls.append(("selection", None, app_module)) or SimpleNamespace(scope="all"),
    )
    monkeypatch.setattr(
        app.app_docs_from_app_module,
        "preview_documentation_unit_candidates_from_app",
        lambda local_cfg, *, app_module: docs_calls.append(("preview", local_cfg, app_module)),
    )
    monkeypatch.setattr(
        app.app_docs_from_app_module,
        "configure_documentation_scope_by_moduletype_from_app",
        lambda *, app_module: docs_calls.append(("moduletype", None, app_module)) or True,
    )
    monkeypatch.setattr(
        app.app_docs_from_app_module,
        "configure_documentation_scope_by_instance_path_from_app",
        lambda *, app_module: docs_calls.append(("instance-path", None, app_module)) or False,
    )
    monkeypatch.setattr(
        app.app_docs_from_app_module,
        "reset_documentation_scope_from_app",
        lambda *, app_module: docs_calls.append(("reset", None, app_module)) or True,
    )
    monkeypatch.setattr(
        app.app_docs_from_app_module,
        "run_generate_documentation_from_app",
        lambda local_cfg, *, app_module: docs_calls.append(("generate", local_cfg, app_module)),
    )

    assert app.load_graphics_rules(rules_path) == ({"rules": []}, False)
    app.save_graphics_rules(rules_path, {"rules": [1]})
    app.run_icf_formatter(cfg)
    assert app._prompt_graphics_rule_definition_with_config(cfg) == {"name": "Rule"}
    project_bp = cast(BasePicture, SimpleNamespace())
    graph = cast(ProjectGraph, SimpleNamespace())
    assert app._collect_graphics_layout_entries_for_target("Root", project_bp, graph) == [{"target": "Root"}]
    assert app._get_documentation_unit_selection().scope == "all"
    app.preview_documentation_unit_candidates(cfg)
    assert app.configure_documentation_scope_by_moduletype(cfg) is True
    assert app.configure_documentation_scope_by_instance_path(cfg) is False
    assert app.reset_documentation_scope(cfg) is True
    app.run_generate_documentation(cfg)

    assert emitted == ["Graphics rules saved"]
    assert graphics_calls[0] == ("load-rules", app.CONFIG_PATH, rules_path)
    assert graphics_calls[1] == ("save-rules", rules_path, {"rules": [1]})
    assert graphics_calls[2] == ("icf", cfg, app)
    assert graphics_calls[3] == ("prompt-rule", cfg, app)
    assert graphics_calls[4] == ("collect-layout", ("Root", project_bp, graph), app)
    assert docs_calls == [
        ("selection", None, app),
        ("preview", cfg, app),
        ("moduletype", None, app),
        ("instance-path", None, app),
        ("reset", None, app),
        ("generate", cfg, app),
    ]


def test_load_graphics_rules_wrapper_falls_back_to_defaults_on_invalid_rules(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rules_path = tmp_path / "graphics_rules.json"
    rules_path.write_text("{bad-json", encoding="utf-8")

    loaded, created = app_graphics.load_graphics_rules(tmp_path / "config.toml", rules_path)

    out = capsys.readouterr().out
    assert created is False
    assert loaded == {"schema_version": 1, "rules": []}
    assert f"Graphics rules unavailable at {rules_path}" in out


def test_simulation_and_analysis_wrappers_delegate(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    cfg = app.DEFAULT_CONFIG.copy()
    snapshot = object()
    project_bp = cast(BasePicture, SimpleNamespace())
    graph = cast(ProjectGraph, SimpleNamespace())
    analysis_calls: list[tuple[str, tuple[object, ...], dict[str, object]]] = []

    monkeypatch.setattr(app, "load_workspace_snapshot", lambda path, **kwargs: snapshot)
    import sattlint.simulation as simulation_module

    monkeypatch.setattr(
        simulation_module,
        "simulate_snapshot_target",
        lambda loaded_snapshot, **kwargs: (
            analysis_calls.append(("simulate", (loaded_snapshot,), kwargs)) or "simulated"
        ),
    )
    monkeypatch.setattr(
        app.app_analysis,
        "source_paths_for_current_target",
        lambda local_bp, local_graph: (
            analysis_calls.append(("source-paths", (local_bp, local_graph), {})) or {Path("file.s")}
        ),
    )
    monkeypatch.setattr(
        app.app_analysis,
        "load_program_ast",
        lambda local_cfg, program_name, *, force_dependency_resolution=False: (
            analysis_calls.append(
                (
                    "load-program-ast",
                    (local_cfg, program_name),
                    {"force_dependency_resolution": force_dependency_resolution},
                )
            )
            or (project_bp, graph)
        ),
    )
    monkeypatch.setattr(
        app.app_analysis,
        "run_variable_analysis",
        lambda local_cfg, kinds, **kwargs: analysis_calls.append(("variable", (local_cfg, kinds), kwargs)),
    )
    monkeypatch.setattr(
        app.app_analysis,
        "run_datatype_usage_analysis",
        lambda local_cfg, **kwargs: analysis_calls.append(("datatype", (local_cfg,), kwargs)),
    )
    monkeypatch.setattr(
        app.app_analysis,
        "run_module_duplicates_analysis",
        lambda local_cfg, **kwargs: analysis_calls.append(("duplicates", (local_cfg,), kwargs)),
    )
    monkeypatch.setattr(
        app.app_analysis,
        "run_module_find_by_name",
        lambda local_cfg, **kwargs: analysis_calls.append(("find", (local_cfg,), kwargs)),
    )
    monkeypatch.setattr(
        app.app_analysis,
        "run_module_tree_debug",
        lambda local_cfg, **kwargs: analysis_calls.append(("tree", (local_cfg,), kwargs)),
    )
    monkeypatch.setattr(
        app.app_analysis,
        "run_analysis_menu",
        lambda local_cfg, **kwargs: analysis_calls.append(("analysis-menu", (local_cfg,), kwargs)),
    )
    monkeypatch.setattr(
        app.app_analysis,
        "variable_analysis_menu",
        lambda local_cfg, **kwargs: analysis_calls.append(("variable-menu", (local_cfg,), kwargs)),
    )
    monkeypatch.setattr(
        app.app_analysis,
        "run_module_localvar_analysis",
        lambda local_cfg, **kwargs: analysis_calls.append(("localvar", (local_cfg,), kwargs)),
    )
    monkeypatch.setattr(
        app.app_analysis,
        "run_checks_menu",
        lambda local_cfg, **kwargs: analysis_calls.append(("checks-menu", (local_cfg,), kwargs)),
    )
    monkeypatch.setattr(
        app.app_analysis,
        "run_mms_interface_analysis",
        lambda local_cfg, **kwargs: analysis_calls.append(("mms", (local_cfg,), kwargs)),
    )
    monkeypatch.setattr(
        app.app_analysis,
        "run_debug_variable_usage",
        lambda local_cfg, **kwargs: analysis_calls.append(("debug", (local_cfg,), kwargs)),
    )
    monkeypatch.setattr(
        app.app_analysis,
        "run_comment_code_analysis",
        lambda local_cfg, **kwargs: analysis_calls.append(("comment", (local_cfg,), kwargs)),
    )
    monkeypatch.setattr(
        app.app_analysis,
        "run_advanced_datatype_analysis",
        lambda local_cfg, **kwargs: analysis_calls.append(("advanced", (local_cfg,), kwargs)),
    )

    assert (
        app._simulate_target(
            cfg,
            target_path=str(tmp_path / "Root.s"),
            module_name="Worker",
            mode="steady-state",
            max_scans=3,
            use_cache=False,
        )
        == "simulated"
    )
    assert app._source_paths_for_current_target(project_bp, graph) == {Path("file.s")}
    assert app.load_program_ast(cfg, "Worker", force_dependency_resolution=True) == (project_bp, graph)
    kinds = {app.IssueKind.UI_ONLY}
    app.run_variable_analysis(cfg, kinds)
    app.run_datatype_usage_analysis(cfg)
    app.run_module_duplicates_analysis(cfg)
    app.run_module_find_by_name(cfg)
    app.run_module_tree_debug(cfg)
    app.run_analysis_menu(cfg)
    app.variable_analysis_menu(cfg)
    app.run_module_localvar_analysis(cfg)
    app.run_checks_menu(cfg)
    app.run_mms_interface_analysis(cfg)
    app.run_debug_variable_usage(cfg)
    app.run_comment_code_analysis(cfg)
    app.run_advanced_datatype_analysis(cfg)

    analysis_by_name = {name: (args, kwargs) for name, args, kwargs in analysis_calls}
    assert analysis_by_name["simulate"][0] == (snapshot,)
    assert analysis_by_name["simulate"][1]["module_name"] == "Worker"
    assert analysis_by_name["simulate"][1]["mode"] == "steady-state"
    assert analysis_by_name["source-paths"][0] == (project_bp, graph)
    assert analysis_by_name["load-program-ast"][0] == (cfg, "Worker")
    assert analysis_by_name["load-program-ast"][1]["force_dependency_resolution"] is True
    assert analysis_by_name["variable"][0] == (cfg, kinds)
    assert analysis_by_name["variable"][1]["pause_fn"] is app.pause
    assert analysis_by_name["datatype"][1]["pause_fn"] is app.pause
    assert analysis_by_name["duplicates"][1]["pause_fn"] is app.pause
    assert analysis_by_name["find"][1]["pause_fn"] is app.pause
    assert analysis_by_name["tree"][1]["prompt_fn"] is app.prompt
    assert analysis_by_name["analysis-menu"][1]["analysis_menu_fn"] is app.analysis_menu
    assert analysis_by_name["variable-menu"][1]["analysis_menu_fn"] is app.analysis_menu
    assert analysis_by_name["localvar"][1]["pause_fn"] is app.pause
    assert analysis_by_name["checks-menu"][1]["run_checks_fn"] is app._run_checks
    assert analysis_by_name["mms"][1]["pause_fn"] is app.pause
    assert analysis_by_name["debug"][1]["pause_fn"] is app.pause
    assert analysis_by_name["comment"][1]["source_paths_for_current_target_fn"] is app._source_paths_for_current_target
    assert analysis_by_name["advanced"][1]["pause_fn"] is app.pause


def test_running_app_as_main_raises_system_exit_from_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        _app_startup_from_app,
        "main_from_app",
        lambda argv, *, app_module: 17,
    )
    monkeypatch.setattr(sys, "argv", ["sattlint", "--help"])

    with pytest.raises(SystemExit) as exc_info:
        runpy.run_module("sattlint.app", run_name="__main__")

    assert exc_info.value.code == 17
