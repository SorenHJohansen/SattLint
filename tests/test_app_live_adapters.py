# pyright: reportUnknownLambdaType=false, reportUnknownArgumentType=false, reportPrivateUsage=false, reportUnknownVariableType=false, reportUnknownParameterType=false, reportUnknownMemberType=false
from __future__ import annotations

import runpy
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from sattline_parser.models.ast_model import BasePicture
from sattlint import (
    _app_analysis_from_app,
    _app_docs_from_app,
    _app_graphics_from_app,
    _app_menus_from_app,
    _app_startup_docs_graphics,
    _app_startup_from_app,
    app,
    app_graphics,
)
from sattlint.models.project_graph import ProjectGraph


def _build_startup_app_module() -> SimpleNamespace:
    return SimpleNamespace(
        sys=SimpleNamespace(argv=["sattlint", "analyze"]),
        app_base=SimpleNamespace(run_cli=lambda *args, **kwargs: 0),
        app_cli_commands=SimpleNamespace(
            run_validate_config_command=lambda *args, **kwargs: 0,
            run_analyze_command=lambda *args, **kwargs: 0,
            run_simulate_command=lambda *args, **kwargs: 0,
            run_docgen_command=lambda *args, **kwargs: 0,
            run_telemetry_summary_command=lambda *args, **kwargs: 0,
        ),
        app_telemetry=SimpleNamespace(telemetry_output_path_for_config=lambda path: Path("telemetry.json")),
        telemetry_summary=SimpleNamespace(
            summarize_telemetry_file=lambda path: {"path": str(path)},
            render_text_summary=lambda summary: str(summary),
        ),
        app_graphics=SimpleNamespace(
            show_config=lambda *args, **kwargs: None,
            discover_graphics_rule_selector_options=lambda *args, **kwargs: [],
            pick_or_prompt_graphics_rule_selector_value=lambda *args, **kwargs: "selector",
            annotate_graphics_entries_with_structure_paths=lambda *args, **kwargs: [],
            graphics_rules_menu=lambda *args, **kwargs: None,
            prompt_graphics_rule_definition_with_config=lambda *args, **kwargs: {"rule": "value"},
            collect_graphics_layout_entries_for_target=lambda *args, **kwargs: [],
            run_graphics_rules_validation=lambda *args, **kwargs: None,
        ),
        app_docs=SimpleNamespace(
            get_documentation_unit_selection=lambda: {"mode": "all"},
            preview_documentation_unit_candidates=lambda *args, **kwargs: None,
            configure_documentation_scope_by_moduletype=lambda *args, **kwargs: True,
            configure_documentation_scope_by_instance_path=lambda *args, **kwargs: False,
            reset_documentation_scope=lambda *args, **kwargs: True,
            run_generate_documentation=lambda *args, **kwargs: None,
            documentation_menu=lambda *args, **kwargs: True,
        ),
        app_menus=SimpleNamespace(
            dump_menu=lambda *args, **kwargs: None,
            config_menu=lambda *args, **kwargs: True,
            tools_menu=lambda *args, **kwargs: None,
            run_main_loop=lambda *args, **kwargs: None,
        ),
        app_support=SimpleNamespace(
            print_menu=lambda *args, **kwargs: None,
            summarize_targets=lambda *args, **kwargs: "targets",
            show_help=lambda *args, **kwargs: None,
        ),
        CONFIG_PATH=Path("config.toml"),
        EXIT_SUCCESS=0,
        EXIT_USAGE_ERROR=2,
        build_cli_parser=lambda: object(),
        run_syntax_check_command=lambda _path: 0,
        load_config=lambda _path: ({"debug": False}, False),
        apply_debug=lambda _cfg: None,
        run_cli=lambda _argv: 0,
        run_validate_config_command=lambda _cfg, **_kwargs: 0,
        run_analyze_command=lambda _cfg, **_kwargs: 0,
        run_simulate_command=lambda _cfg, **_kwargs: 0,
        run_docgen_command=lambda _cfg, **_kwargs: 0,
        run_telemetry_summary_command=lambda _cfg, **_kwargs: 0,
        run_format_icf_command=lambda _cfg: 0,
        pause=lambda: None,
        get_graphics_rules_path=lambda: Path("graphics.json"),
        load_graphics_rules=lambda _path=None: ({"rules": []}, False),
        save_graphics_rules=lambda _path, _rules: None,
        _graphics_rule_label=lambda _rule: "Rule",
        _graphics_rule_config_line=lambda _rule: "config-line",
        clear_screen=lambda: None,
        choose_menu_option=lambda *args, **kwargs: "b",
        build_menu_interaction=lambda: SimpleNamespace(kind="interaction"),
        _get_analyzed_targets=lambda _cfg: ["Root"],
        _summarize_targets=lambda _cfg: "targets",
        _has_analyzed_targets=lambda _cfg: True,
        _target_is_library=lambda _cfg, _target_name: False,
        ensure_ast_cache=lambda _cfg: True,
        emit_output=lambda *_args: None,
        self_check=lambda _cfg: True,
        _iter_loaded_projects=lambda _cfg, use_cache=True: iter([]),
        _collect_graphics_layout_entries_for_target=lambda *args, **kwargs: [],
        _discover_graphics_rule_selector_options=lambda *args, **kwargs: [],
        _annotate_graphics_entries_with_structure_paths=lambda entries, *_args, **_kwargs: entries,
        _prompt_graphics_rule_definition_with_config=lambda _cfg: {"rule": "value"},
        _pick_or_prompt_graphics_rule_selector_value=lambda *args, **kwargs: "selector",
        _split_csv_values=lambda raw: raw.split(","),
        _print_menu=lambda *args, **kwargs: None,
        _menu_option=lambda key, label, description: (key, label, description),
        confirm=lambda _message: True,
        prompt=lambda _message, default=None: default or "value",
        quit_app=lambda: None,
        save_config=lambda _path, _cfg: None,
        target_exists=lambda _target, _cfg: True,
        graphics_rules_menu=lambda _cfg: None,
        show_config=lambda _cfg: None,
        documentation_menu=lambda _cfg: True,
        config_menu=lambda _cfg: True,
        tools_menu=lambda _cfg: None,
        dump_menu=lambda _cfg: None,
        analysis_menu=lambda _cfg: None,
        _require_targets_for_menu_action=lambda _cfg, _action: True,
        force_refresh_ast=lambda _cfg: None,
        refresh_analysis_caches=lambda _cfg: None,
        run_source_diff_report=lambda _cfg: None,
        analyze_variables=lambda *args, **kwargs: None,
        classify_documentation_structure=lambda *args, **kwargs: [],
        discover_documentation_unit_candidates=lambda *args, **kwargs: [],
        QuitAppError=RuntimeError,
    )


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

    cfg = cast(dict[str, Any], {"mode": "draft"})
    app._print_validation_warnings(["warn"], limit=3)
    assert app._target_validation_warnings("Target", ["warn"]) == ["filtered"]
    validation_result = cast(Any, app.validate_effective_config(cfg))
    assert validation_result.ok is True
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


def test_run_cli_adapter_routes_through_startup_core(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, object] = {}

    def fake_run_cli(argv: list[str], **kwargs: object) -> int:
        seen["argv"] = argv
        seen.update(kwargs)
        return 23

    monkeypatch.setattr(_app_startup_from_app.startup_core, "run_cli", fake_run_cli)

    result = app.run_cli(["analyze", "--check", "variables"])

    assert result == 23
    assert seen["argv"] == ["analyze", "--check", "variables"]
    assert seen["run_cli_owner_fn"] is app.app_base.run_cli
    assert seen["config_path"] == app.CONFIG_PATH
    assert seen["build_cli_parser_fn"] is app.build_cli_parser
    assert seen["run_syntax_check_command_fn"] is app.run_syntax_check_command


def test_cli_live_adapter_uses_sys_argv_tail(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, object] = {}

    monkeypatch.setattr(
        _app_startup_from_app,
        "main_from_app",
        lambda argv, *, app_module: seen.update({"argv": argv, "app_module": app_module}) or 31,
    )
    monkeypatch.setattr(app.sys, "argv", ["sattlint", "validate-config", "--config", "custom.toml"])

    assert app.cli() == 31
    assert seen == {
        "argv": ["validate-config", "--config", "custom.toml"],
        "app_module": app,
    }


def test_main_from_app_routes_interactive_session_dependencies(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, object] = {}

    def fake_main(argv: list[str] | None, **kwargs: object) -> int:
        seen["argv"] = argv
        seen.update(kwargs)
        return 41

    monkeypatch.setattr(_app_startup_from_app.startup_core, "main", fake_main)

    result = _app_startup_from_app.main_from_app(["analyze"], app_module=app)

    assert result == 41
    assert seen["argv"] == ["analyze"]
    assert seen["run_cli_fn"] is app.run_cli
    assert seen["load_config_fn"] is app.load_config
    assert seen["config_path"] == app.CONFIG_PATH
    assert seen["run_main_loop_fn"] is app.run_interactive_session
    assert seen["choose_menu_option_fn"] is app.choose_menu_option
    assert seen["analysis_menu_fn"] is app.analysis_menu
    assert seen["documentation_menu_fn"] is app.documentation_menu
    assert seen["config_menu_fn"] is app.config_menu
    assert seen["tools_menu_fn"] is app.tools_menu
    assert seen["quit_app_error"] is app.QuitAppError


def test_startup_cli_command_wrappers_delegate_to_startup_core(monkeypatch: pytest.MonkeyPatch) -> None:  # noqa: PLR0915
    app_module = _build_startup_app_module()
    cfg = cast(dict[str, Any], {"debug": False})
    config_path = Path("config.toml")
    selected_keys = ["modules"]
    selected_issue_kinds = frozenset({"unused"})
    seen: list[tuple[str, tuple[object, ...], dict[str, object]]] = []

    def record(name: str, result: int):
        return lambda *args, **kwargs: seen.append((name, args, dict(kwargs))) or result

    monkeypatch.setattr(
        _app_startup_from_app.startup_core,
        "run_validate_config_command",
        record("validate", 11),
    )
    monkeypatch.setattr(
        _app_startup_from_app.startup_core,
        "run_analyze_command",
        record("analyze", 12),
    )
    monkeypatch.setattr(
        _app_startup_from_app.startup_core,
        "run_simulate_command",
        record("simulate", 13),
    )
    monkeypatch.setattr(
        _app_startup_from_app.startup_core,
        "run_docgen_command",
        record("docgen", 14),
    )
    monkeypatch.setattr(
        _app_startup_from_app.startup_core,
        "run_telemetry_summary_command",
        record("telemetry", 15),
    )

    validate_config = object()
    run_checks = object()
    iter_loaded_projects = object()
    get_selectable_analyzers = object()
    get_enabled_analyzers = object()
    target_is_library = object()
    simulate_target = object()
    get_documentation_unit_selection = object()

    app_module.validate_effective_config = validate_config
    app_module.app_analysis = SimpleNamespace(run_checks=run_checks)
    app_module._iter_loaded_projects = iter_loaded_projects
    app_module._get_selectable_analyzers = get_selectable_analyzers
    app_module._get_enabled_analyzers = get_enabled_analyzers
    app_module._target_is_library = target_is_library
    app_module._simulate_target = simulate_target
    app_module._get_documentation_unit_selection = get_documentation_unit_selection

    assert (
        _app_startup_from_app.run_validate_config_command_from_app(
            cfg,
            config_path=config_path,
            default_used=True,
            app_module=app_module,
        )
        == 11
    )
    assert (
        _app_startup_from_app.run_analyze_command_from_app(
            cfg,
            selected_keys=selected_keys,
            selected_issue_kinds=selected_issue_kinds,
            use_cache=False,
            app_module=app_module,
        )
        == 12
    )
    assert (
        _app_startup_from_app.run_simulate_command_from_app(
            cfg,
            target_path="Root.s",
            module_name="Root",
            mode="single",
            max_scans=8,
            output_format="json",
            output_path="simulation.json",
            use_cache=True,
            app_module=app_module,
        )
        == 13
    )
    assert (
        _app_startup_from_app.run_docgen_command_from_app(
            cfg,
            use_cache=True,
            output_dir="docs-out",
            output_path="docs/report.docx",
            app_module=app_module,
        )
        == 14
    )
    assert (
        _app_startup_from_app.run_telemetry_summary_command_from_app(
            cfg,
            config_path=config_path,
            output_format="json",
            output_path="telemetry.json",
            app_module=app_module,
        )
        == 15
    )

    names = [name for name, _args, _kwargs in seen]
    assert names == ["validate", "analyze", "simulate", "docgen", "telemetry"]

    seen_by_name = {name: (args, kwargs) for name, args, kwargs in seen}

    validate_args, validate_kwargs = seen_by_name["validate"]
    assert validate_args == (cfg,)
    assert validate_kwargs == {
        "config_path": config_path,
        "default_used": True,
        "run_validate_config_command_fn": app_module.app_cli_commands.run_validate_config_command,
        "validate_config_fn": validate_config,
        "exit_success": app_module.EXIT_SUCCESS,
        "exit_usage_error": app_module.EXIT_USAGE_ERROR,
    }

    analyze_args, analyze_kwargs = seen_by_name["analyze"]
    assert analyze_args == (cfg,)
    assert analyze_kwargs == {
        "selected_keys": selected_keys,
        "selected_issue_kinds": selected_issue_kinds,
        "use_cache": False,
        "run_analyze_command_fn": app_module.app_cli_commands.run_analyze_command,
        "run_checks_owner_fn": run_checks,
        "iter_loaded_projects_fn": iter_loaded_projects,
        "get_selectable_analyzers_fn": get_selectable_analyzers,
        "get_enabled_analyzers_fn": get_enabled_analyzers,
        "target_is_library_fn": target_is_library,
        "exit_success": app_module.EXIT_SUCCESS,
    }

    simulate_args, simulate_kwargs = seen_by_name["simulate"]
    assert simulate_args == (cfg,)
    assert simulate_kwargs == {
        "target_path": "Root.s",
        "module_name": "Root",
        "mode": "single",
        "max_scans": 8,
        "output_format": "json",
        "output_path": "simulation.json",
        "use_cache": True,
        "run_simulate_command_fn": app_module.app_cli_commands.run_simulate_command,
        "simulate_fn": simulate_target,
        "exit_success": app_module.EXIT_SUCCESS,
        "exit_usage_error": app_module.EXIT_USAGE_ERROR,
    }

    docgen_args, docgen_kwargs = seen_by_name["docgen"]
    assert docgen_args == (cfg,)
    assert docgen_kwargs == {
        "use_cache": True,
        "output_dir": "docs-out",
        "output_path": "docs/report.docx",
        "run_docgen_command_fn": app_module.app_cli_commands.run_docgen_command,
        "iter_loaded_projects_fn": iter_loaded_projects,
        "documentation_unit_selection_fn": get_documentation_unit_selection,
        "exit_success": app_module.EXIT_SUCCESS,
        "exit_usage_error": app_module.EXIT_USAGE_ERROR,
    }

    telemetry_args, telemetry_kwargs = seen_by_name["telemetry"]
    assert telemetry_args == (cfg,)
    assert telemetry_kwargs == {
        "config_path": config_path,
        "output_format": "json",
        "output_path": "telemetry.json",
        "run_telemetry_summary_command_fn": app_module.app_cli_commands.run_telemetry_summary_command,
        "telemetry_output_path_fn": app_module.app_telemetry.telemetry_output_path_for_config,
        "summarize_telemetry_fn": app_module.telemetry_summary.summarize_telemetry_file,
        "render_text_summary_fn": app_module.telemetry_summary.render_text_summary,
        "exit_success": app_module.EXIT_SUCCESS,
        "exit_usage_error": app_module.EXIT_USAGE_ERROR,
    }


def test_analysis_from_app_wrappers_delegate_live_dependencies(monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = cast(dict[str, Any], {"debug": False})
    build_menu_calls: list[str] = []
    interaction = SimpleNamespace(kind="interaction")
    emit_output = object()
    app_module = SimpleNamespace(
        clear_screen=object(),
        quit_app=object(),
        run_variable_analysis=object(),
        run_datatype_usage_analysis=object(),
        run_debug_variable_usage=object(),
        run_module_localvar_analysis=object(),
        pause=object(),
        app_analysis=SimpleNamespace(emit_output=emit_output),
        build_menu_interaction=lambda: build_menu_calls.append("interaction") or interaction,
        _print_menu=object(),
        _menu_option=object(),
        run_module_duplicates_analysis=object(),
        run_module_find_by_name=object(),
        run_module_tree_debug=object(),
        run_graphics_rules_validation=object(),
        run_mms_interface_analysis=object(),
        run_icf_validation=object(),
        run_icf_formatter=object(),
        run_comment_code_analysis=object(),
        _get_enabled_analyzers=object(),
        _run_checks=object(),
        variable_usage_submenu=object(),
        module_analysis_submenu=object(),
        interface_communication_submenu=object(),
        code_quality_submenu=object(),
        analyzer_catalog_menu=object(),
        advanced_analysis_menu=object(),
        _summarize_targets=object(),
    )
    calls: dict[str, tuple[object, dict[str, object]]] = {}

    def record(name: str):
        def _record(local_cfg: object, **kwargs: object) -> None:
            calls[name] = (local_cfg, dict(kwargs))

        return _record

    monkeypatch.setattr(
        _app_analysis_from_app.analysis_menus_module,
        "variable_usage_submenu",
        record("variable_usage_submenu"),
    )
    monkeypatch.setattr(
        _app_analysis_from_app.analysis_menus_module,
        "module_analysis_submenu",
        record("module_analysis_submenu"),
    )
    monkeypatch.setattr(
        _app_analysis_from_app.analysis_menus_module,
        "interface_communication_submenu",
        record("interface_communication_submenu"),
    )
    monkeypatch.setattr(
        _app_analysis_from_app.analysis_menus_module,
        "code_quality_submenu",
        record("code_quality_submenu"),
    )
    monkeypatch.setattr(
        _app_analysis_from_app.analysis_menus_module,
        "analyzer_catalog_menu",
        record("analyzer_catalog_menu"),
    )
    monkeypatch.setattr(
        _app_analysis_from_app.analysis_menus_module,
        "advanced_analysis_menu",
        record("advanced_analysis_menu"),
    )
    monkeypatch.setattr(
        _app_analysis_from_app.analysis_menus_module,
        "analysis_menu",
        record("analysis_menu"),
    )

    _app_analysis_from_app.variable_usage_submenu_from_app(cfg, app_module=app_module)
    _app_analysis_from_app.module_analysis_submenu_from_app(cfg, app_module=app_module)
    _app_analysis_from_app.interface_communication_submenu_from_app(cfg, app_module=app_module)
    _app_analysis_from_app.code_quality_submenu_from_app(cfg, app_module=app_module)
    _app_analysis_from_app.analyzer_catalog_menu_from_app(cfg, app_module=app_module)
    _app_analysis_from_app.advanced_analysis_menu_from_app(cfg, app_module=app_module)
    _app_analysis_from_app.analysis_menu_from_app(cfg, app_module=app_module)

    assert build_menu_calls == ["interaction"] * 7
    assert _app_analysis_from_app._emit_output_fn(app_module) is emit_output

    variable_cfg, variable_kwargs = calls["variable_usage_submenu"]
    assert variable_cfg is cfg
    assert variable_kwargs == {
        "clear_screen_fn": app_module.clear_screen,
        "quit_app_fn": app_module.quit_app,
        "run_variable_analysis_fn": app_module.run_variable_analysis,
        "run_datatype_usage_analysis_fn": app_module.run_datatype_usage_analysis,
        "run_debug_variable_usage_fn": app_module.run_debug_variable_usage,
        "run_module_localvar_analysis_fn": app_module.run_module_localvar_analysis,
        "pause_fn": app_module.pause,
        "emit_output_fn": emit_output,
        "interaction": interaction,
    }

    module_cfg, module_kwargs = calls["module_analysis_submenu"]
    assert module_cfg is cfg
    assert module_kwargs == {
        "clear_screen_fn": app_module.clear_screen,
        "print_menu_fn": app_module._print_menu,
        "menu_option_factory": app_module._menu_option,
        "quit_app_fn": app_module.quit_app,
        "run_module_duplicates_analysis_fn": app_module.run_module_duplicates_analysis,
        "run_module_find_by_name_fn": app_module.run_module_find_by_name,
        "run_module_tree_debug_fn": app_module.run_module_tree_debug,
        "run_graphics_rules_validation_fn": app_module.run_graphics_rules_validation,
        "pause_fn": app_module.pause,
        "emit_output_fn": emit_output,
        "interaction": interaction,
    }

    interface_cfg, interface_kwargs = calls["interface_communication_submenu"]
    assert interface_cfg is cfg
    assert interface_kwargs == {
        "clear_screen_fn": app_module.clear_screen,
        "print_menu_fn": app_module._print_menu,
        "menu_option_factory": app_module._menu_option,
        "quit_app_fn": app_module.quit_app,
        "run_mms_interface_analysis_fn": app_module.run_mms_interface_analysis,
        "run_icf_validation_fn": app_module.run_icf_validation,
        "run_icf_formatter_fn": app_module.run_icf_formatter,
        "pause_fn": app_module.pause,
        "emit_output_fn": emit_output,
        "interaction": interaction,
    }

    quality_cfg, quality_kwargs = calls["code_quality_submenu"]
    assert quality_cfg is cfg
    assert quality_kwargs == {
        "clear_screen_fn": app_module.clear_screen,
        "print_menu_fn": app_module._print_menu,
        "menu_option_factory": app_module._menu_option,
        "quit_app_fn": app_module.quit_app,
        "run_comment_code_analysis_fn": app_module.run_comment_code_analysis,
        "pause_fn": app_module.pause,
        "emit_output_fn": emit_output,
        "interaction": interaction,
    }

    catalog_cfg, catalog_kwargs = calls["analyzer_catalog_menu"]
    assert catalog_cfg is cfg
    assert catalog_kwargs == {
        "clear_screen_fn": app_module.clear_screen,
        "print_menu_fn": app_module._print_menu,
        "menu_option_factory": app_module._menu_option,
        "quit_app_fn": app_module.quit_app,
        "get_enabled_analyzers_fn": app_module._get_enabled_analyzers,
        "run_checks_fn": app_module._run_checks,
        "pause_fn": app_module.pause,
        "emit_output_fn": emit_output,
        "interaction": interaction,
    }

    advanced_cfg, advanced_kwargs = calls["advanced_analysis_menu"]
    assert advanced_cfg is cfg
    assert advanced_kwargs == {
        "clear_screen_fn": app_module.clear_screen,
        "print_menu_fn": app_module._print_menu,
        "menu_option_factory": app_module._menu_option,
        "quit_app_fn": app_module.quit_app,
        "run_datatype_usage_analysis_fn": app_module.run_datatype_usage_analysis,
        "run_debug_variable_usage_fn": app_module.run_debug_variable_usage,
        "run_module_localvar_analysis_fn": app_module.run_module_localvar_analysis,
        "pause_fn": app_module.pause,
        "emit_output_fn": emit_output,
        "interaction": interaction,
    }

    analysis_cfg, analysis_kwargs = calls["analysis_menu"]
    assert analysis_cfg is cfg
    assert analysis_kwargs == {
        "clear_screen_fn": app_module.clear_screen,
        "print_menu_fn": app_module._print_menu,
        "menu_option_factory": app_module._menu_option,
        "quit_app_fn": app_module.quit_app,
        "run_checks_fn": app_module._run_checks,
        "variable_usage_submenu_fn": app_module.variable_usage_submenu,
        "module_analysis_submenu_fn": app_module.module_analysis_submenu,
        "interface_communication_submenu_fn": app_module.interface_communication_submenu,
        "code_quality_submenu_fn": app_module.code_quality_submenu,
        "analyzer_catalog_menu_fn": app_module.analyzer_catalog_menu,
        "advanced_analysis_menu_fn": app_module.advanced_analysis_menu,
        "summarize_targets_fn": app_module._summarize_targets,
        "pause_fn": app_module.pause,
        "emit_output_fn": emit_output,
        "interaction": interaction,
    }


def test_docs_from_app_wrappers_delegate_live_dependencies() -> None:
    cfg = cast(dict[str, Any], {"debug": False})
    build_menu_calls: list[str] = []
    interaction = SimpleNamespace(kind="interaction")
    selection = {"mode": "all"}
    loaded_projects = object()
    pause = object()
    split_csv_values = object()
    clear_screen = object()
    print_menu = object()
    menu_option = object()
    quit_app = object()
    calls: list[tuple[str, tuple[object, ...], dict[str, object]]] = []

    def record(name: str, result: object):
        def _record(*args: object, **kwargs: object) -> object:
            calls.append((name, args, dict(kwargs)))
            return result

        return _record

    app_module = SimpleNamespace(
        app_docs=SimpleNamespace(
            get_documentation_unit_selection=record("selection", selection),
            preview_documentation_unit_candidates=record("preview", None),
            configure_documentation_scope_by_moduletype=record("scope-moduletype", True),
            configure_documentation_scope_by_instance_path=record("scope-instance-path", False),
            reset_documentation_scope=record("scope-reset", True),
            run_generate_documentation=record("generate", None),
            documentation_menu=record("menu", True),
        ),
        _iter_loaded_projects=loaded_projects,
        pause=pause,
        _split_csv_values=split_csv_values,
        build_menu_interaction=lambda: build_menu_calls.append("interaction") or interaction,
        clear_screen=clear_screen,
        _print_menu=print_menu,
        _menu_option=menu_option,
        quit_app=quit_app,
    )

    assert _app_docs_from_app.get_documentation_unit_selection_from_app(app_module=app_module) is selection
    _app_docs_from_app.preview_documentation_unit_candidates_from_app(cfg, app_module=app_module)
    assert _app_docs_from_app.configure_documentation_scope_by_moduletype_from_app(app_module=app_module) is True
    assert _app_docs_from_app.configure_documentation_scope_by_instance_path_from_app(app_module=app_module) is False
    assert _app_docs_from_app.reset_documentation_scope_from_app(app_module=app_module) is True
    _app_docs_from_app.run_generate_documentation_from_app(cfg, app_module=app_module)
    assert _app_docs_from_app.documentation_menu_from_app(cfg, app_module=app_module) is True

    assert build_menu_calls == ["interaction"] * 5
    assert calls == [
        ("selection", (), {}),
        (
            "preview",
            (cfg,),
            {"iter_loaded_projects_fn": loaded_projects, "pause_fn": pause},
        ),
        (
            "scope-moduletype",
            (),
            {"split_csv_values_fn": split_csv_values, "interaction": interaction},
        ),
        (
            "scope-instance-path",
            (),
            {"split_csv_values_fn": split_csv_values, "interaction": interaction},
        ),
        ("scope-reset", (), {"interaction": interaction}),
        (
            "generate",
            (cfg,),
            {"iter_loaded_projects_fn": loaded_projects, "interaction": interaction},
        ),
        (
            "menu",
            (cfg,),
            {
                "clear_screen_fn": clear_screen,
                "print_menu_fn": print_menu,
                "menu_option_factory": menu_option,
                "quit_app_fn": quit_app,
                "split_csv_values_fn": split_csv_values,
                "iter_loaded_projects_fn": loaded_projects,
                "interaction": interaction,
            },
        ),
    ]


def test_startup_docs_graphics_helpers_delegate_dependencies() -> None:  # noqa: PLR0915
    cfg = cast(dict[str, Any], {"debug": False})
    project_bp = cast(BasePicture, SimpleNamespace())
    graph = cast(ProjectGraph, SimpleNamespace())
    selector_options = [{"label": "A"}]
    selector_value = "selector"
    annotated_entries = [{"path": "A"}]
    prompted_rule = {"rule": "value"}
    layout_entries = [{"target": "Root"}]
    documentation_selection = {"mode": "all"}
    calls: list[tuple[str, tuple[object, ...], dict[str, object]]] = []

    def record(name: str, result: object):
        def _record(*args: object, **kwargs: object) -> object:
            calls.append((name, args, dict(kwargs)))
            return result

        return _record

    has_analyzed_targets = object()
    iter_loaded_projects = object()
    collect_graphics_layout_entries_for_target = object()
    pick_or_prompt_graphics_rule_selector_value = object()
    classify_documentation_structure = object()
    discover_documentation_unit_candidates = object()
    discover_selector = cast(Any, record("discover-selector", selector_options))
    pick_selector = cast(Any, record("pick-selector", selector_value))
    annotate = cast(Any, record("annotate", annotated_entries))
    graphics_rules_menu_fn = cast(Any, record("graphics-menu", None))
    get_graphics_rules_path = object()
    load_graphics_rules = object()
    save_graphics_rules = object()
    prompt_graphics_rule_definition_with_config = object()
    graphics_rule_label = object()
    clear_screen = object()
    print_menu = object()
    menu_option = object()
    confirm = object()
    prompt = object()
    quit_app = object()
    pause = object()
    split_csv_values = object()
    prompt_rule = cast(Any, record("prompt-rule", prompted_rule))
    collect_layout = cast(Any, record("collect-layout", layout_entries))
    validate_graphics = cast(Any, record("validate-graphics", None))
    get_doc_selection = cast(Any, record("get-doc-selection", documentation_selection))
    preview_docs = cast(Any, record("preview-docs", None))
    scope_moduletype = cast(Any, record("scope-moduletype", True))
    scope_instance = cast(Any, record("scope-instance", False))
    scope_reset = cast(Any, record("scope-reset", True))
    generate_docs = cast(Any, record("generate-docs", None))
    documentation_menu_fn = cast(Any, record("documentation-menu", True))

    assert (
        _app_startup_docs_graphics.discover_graphics_rule_selector_options(
            cfg,
            selector_field="module",
            module_kind="graphics",
            discover_graphics_rule_selector_options_fn=discover_selector,
            has_analyzed_targets_fn=cast(Any, has_analyzed_targets),
            iter_loaded_projects_fn=cast(Any, iter_loaded_projects),
            collect_graphics_layout_entries_for_target_fn=cast(Any, collect_graphics_layout_entries_for_target),
        )
        == selector_options
    )
    assert (
        _app_startup_docs_graphics.pick_or_prompt_graphics_rule_selector_value(
            "module",
            "graphics",
            cfg=cfg,
            pick_or_prompt_graphics_rule_selector_value_fn=pick_selector,
            discover_graphics_rule_selector_options_fn=cast(Any, collect_graphics_layout_entries_for_target),
        )
        == selector_value
    )
    assert (
        _app_startup_docs_graphics.annotate_graphics_entries_with_structure_paths(
            [{"entry": 1}],
            project_bp,
            graph,
            annotate_graphics_entries_with_structure_paths_fn=annotate,
            classify_documentation_structure_fn=cast(Any, classify_documentation_structure),
            discover_documentation_unit_candidates_fn=cast(Any, discover_documentation_unit_candidates),
        )
        == annotated_entries
    )
    _app_startup_docs_graphics.graphics_rules_menu(
        cfg,
        graphics_rules_menu_fn=graphics_rules_menu_fn,
        get_graphics_rules_path_fn=cast(Any, get_graphics_rules_path),
        load_graphics_rules_fn=cast(Any, load_graphics_rules),
        save_graphics_rules_fn=cast(Any, save_graphics_rules),
        prompt_graphics_rule_definition_with_config_fn=cast(Any, prompt_graphics_rule_definition_with_config),
        graphics_rule_label_fn=cast(Any, graphics_rule_label),
        clear_screen_fn=cast(Any, clear_screen),
        print_menu_fn=cast(Any, print_menu),
        menu_option_factory=cast(Any, menu_option),
        confirm_fn=cast(Any, confirm),
        prompt_fn=cast(Any, prompt),
        quit_app_fn=cast(Any, quit_app),
        pause_fn=cast(Any, pause),
    )
    assert (
        _app_startup_docs_graphics.prompt_graphics_rule_definition_with_config(
            cfg,
            prompt_graphics_rule_definition_with_config_fn=prompt_rule,
            prompt_fn=cast(Any, prompt),
            pause_fn=cast(Any, pause),
            pick_or_prompt_graphics_rule_selector_value_fn=cast(Any, pick_or_prompt_graphics_rule_selector_value),
            interaction="interaction",
        )
        == prompted_rule
    )
    assert (
        _app_startup_docs_graphics.collect_graphics_layout_entries_for_target(
            "Root",
            project_bp,
            graph,
            collect_graphics_layout_entries_for_target_fn=collect_layout,
            annotate_graphics_entries_with_structure_paths_fn=cast(Any, classify_documentation_structure),
        )
        == layout_entries
    )
    _app_startup_docs_graphics.run_graphics_rules_validation(
        cfg,
        run_graphics_rules_validation_fn=validate_graphics,
        get_graphics_rules_path_fn=cast(Any, get_graphics_rules_path),
        load_graphics_rules_fn=cast(Any, load_graphics_rules),
        iter_loaded_projects_fn=cast(Any, iter_loaded_projects),
        collect_graphics_layout_entries_for_target_fn=cast(Any, collect_graphics_layout_entries_for_target),
        pause_fn=cast(Any, pause),
    )
    assert (
        _app_startup_docs_graphics.get_documentation_unit_selection(
            get_documentation_unit_selection_fn=get_doc_selection
        )
        == documentation_selection
    )
    _app_startup_docs_graphics.preview_documentation_unit_candidates(
        cfg,
        preview_documentation_unit_candidates_fn=preview_docs,
        iter_loaded_projects_fn=cast(Any, iter_loaded_projects),
        pause_fn=cast(Any, pause),
    )
    assert (
        _app_startup_docs_graphics.configure_documentation_scope_by_moduletype(
            configure_documentation_scope_by_moduletype_fn=scope_moduletype,
            split_csv_values_fn=cast(Any, split_csv_values),
            pause_fn=cast(Any, pause),
        )
        is True
    )
    assert (
        _app_startup_docs_graphics.configure_documentation_scope_by_instance_path(
            configure_documentation_scope_by_instance_path_fn=scope_instance,
            split_csv_values_fn=cast(Any, split_csv_values),
            pause_fn=cast(Any, pause),
        )
        is False
    )
    assert (
        _app_startup_docs_graphics.reset_documentation_scope(
            reset_documentation_scope_fn=scope_reset,
            pause_fn=cast(Any, pause),
        )
        is True
    )
    _app_startup_docs_graphics.run_generate_documentation(
        cfg,
        run_generate_documentation_fn=generate_docs,
        iter_loaded_projects_fn=cast(Any, iter_loaded_projects),
        prompt_fn=cast(Any, prompt),
        pause_fn=cast(Any, pause),
    )
    assert (
        _app_startup_docs_graphics.documentation_menu(
            cfg,
            documentation_menu_fn=documentation_menu_fn,
            clear_screen_fn=cast(Any, clear_screen),
            print_menu_fn=cast(Any, print_menu),
            menu_option_factory=cast(Any, menu_option),
            quit_app_fn=cast(Any, quit_app),
            pause_fn=cast(Any, pause),
            split_csv_values_fn=cast(Any, split_csv_values),
            iter_loaded_projects_fn=cast(Any, iter_loaded_projects),
            prompt_fn=cast(Any, prompt),
        )
        is True
    )

    assert calls == [
        (
            "discover-selector",
            (cfg,),
            {
                "selector_field": "module",
                "module_kind": "graphics",
                "has_analyzed_targets_fn": has_analyzed_targets,
                "iter_loaded_projects_fn": iter_loaded_projects,
                "collect_graphics_layout_entries_for_target_fn": collect_graphics_layout_entries_for_target,
            },
        ),
        (
            "pick-selector",
            ("module", "graphics"),
            {
                "cfg": cfg,
                "discover_graphics_rule_selector_options_fn": collect_graphics_layout_entries_for_target,
            },
        ),
        (
            "annotate",
            ([{"entry": 1}], project_bp, graph),
            {
                "classify_documentation_structure_fn": classify_documentation_structure,
                "discover_documentation_unit_candidates_fn": discover_documentation_unit_candidates,
            },
        ),
        (
            "graphics-menu",
            (cfg,),
            {
                "get_graphics_rules_path_fn": get_graphics_rules_path,
                "load_graphics_rules_fn": load_graphics_rules,
                "save_graphics_rules_fn": save_graphics_rules,
                "prompt_graphics_rule_definition_with_config_fn": prompt_graphics_rule_definition_with_config,
                "graphics_rule_label_fn": graphics_rule_label,
                "clear_screen_fn": clear_screen,
                "print_menu_fn": print_menu,
                "menu_option_factory": menu_option,
                "confirm_fn": confirm,
                "prompt_fn": prompt,
                "quit_app_fn": quit_app,
                "pause_fn": pause,
            },
        ),
        (
            "prompt-rule",
            (cfg,),
            {
                "prompt_fn": prompt,
                "pause_fn": pause,
                "pick_or_prompt_graphics_rule_selector_value_fn": pick_or_prompt_graphics_rule_selector_value,
                "interaction": "interaction",
            },
        ),
        (
            "collect-layout",
            ("Root", project_bp, graph),
            {
                "annotate_graphics_entries_with_structure_paths_fn": classify_documentation_structure,
            },
        ),
        (
            "validate-graphics",
            (cfg,),
            {
                "get_graphics_rules_path_fn": get_graphics_rules_path,
                "load_graphics_rules_fn": load_graphics_rules,
                "iter_loaded_projects_fn": iter_loaded_projects,
                "collect_graphics_layout_entries_for_target_fn": collect_graphics_layout_entries_for_target,
                "pause_fn": pause,
            },
        ),
        ("get-doc-selection", (), {}),
        (
            "preview-docs",
            (cfg,),
            {
                "iter_loaded_projects_fn": iter_loaded_projects,
                "pause_fn": pause,
            },
        ),
        (
            "scope-moduletype",
            (),
            {
                "split_csv_values_fn": split_csv_values,
                "pause_fn": pause,
            },
        ),
        (
            "scope-instance",
            (),
            {
                "split_csv_values_fn": split_csv_values,
                "pause_fn": pause,
            },
        ),
        ("scope-reset", (), {"pause_fn": pause}),
        (
            "generate-docs",
            (cfg,),
            {
                "iter_loaded_projects_fn": iter_loaded_projects,
                "prompt_fn": prompt,
                "pause_fn": pause,
            },
        ),
        (
            "documentation-menu",
            (cfg,),
            {
                "clear_screen_fn": clear_screen,
                "print_menu_fn": print_menu,
                "menu_option_factory": menu_option,
                "quit_app_fn": quit_app,
                "pause_fn": pause,
                "split_csv_values_fn": split_csv_values,
                "iter_loaded_projects_fn": iter_loaded_projects,
                "prompt_fn": prompt,
            },
        ),
    ]


def test_graphics_from_app_wrappers_delegate_live_dependencies(monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = cast(dict[str, Any], {"debug": False})
    build_menu_calls: list[str] = []
    interaction = SimpleNamespace(kind="interaction")
    selector_options = [{"label": "A"}]
    selector_value = "selector"
    annotated_entries = [{"path": "A"}]
    prompted_rule = {"name": "Rule"}
    layout_entries = [{"target": "Root"}]
    project_bp = cast(BasePicture, SimpleNamespace())
    graph = cast(ProjectGraph, SimpleNamespace())
    calls: list[tuple[str, tuple[object, ...], dict[str, object]]] = []
    graphics_menu_calls: list[tuple[object, dict[str, object]]] = []
    has_analyzed_targets = object()
    iter_loaded_projects = object()
    collect_graphics_layout_entries = object()
    discover_graphics_rule_selector_options = object()
    classify_documentation_structure = object()
    discover_documentation_unit_candidates = object()
    get_graphics_rules_path = object()
    load_graphics_rules = object()
    save_graphics_rules = object()
    prompt_graphics_rule_definition = object()
    graphics_rule_label = object()
    clear_screen = object()
    print_menu = object()
    menu_option = object()
    confirm = object()
    prompt = object()
    quit_app = object()
    pause = object()
    print_graphics_rules_summary = object()
    emit_output = object()
    pick_or_prompt_graphics_rule_selector_value = object()
    annotate_graphics_entries_with_structure_paths = object()

    def record(name: str, result: object):
        def _record(*args: object, **kwargs: object) -> object:
            calls.append((name, args, dict(kwargs)))
            return result

        return _record

    monkeypatch.setattr(
        _app_graphics_from_app.graphics_menus_module,
        "graphics_rules_menu",
        lambda local_cfg, **kwargs: graphics_menu_calls.append((local_cfg, dict(kwargs))),
    )

    app_module = SimpleNamespace(
        app_graphics=SimpleNamespace(
            discover_graphics_rule_selector_options=record("discover-selector", selector_options),
            pick_or_prompt_graphics_rule_selector_value=record("pick-selector", selector_value),
            annotate_graphics_entries_with_structure_paths=record("annotate", annotated_entries),
            print_graphics_rules_summary=print_graphics_rules_summary,
            emit_output=emit_output,
            prompt_graphics_rule_definition_with_config=record("prompt-rule", prompted_rule),
            collect_graphics_layout_entries_for_target=record("collect-layout", layout_entries),
            run_graphics_rules_validation=record("validate", None),
        ),
        _has_analyzed_targets=has_analyzed_targets,
        _iter_loaded_projects=iter_loaded_projects,
        _collect_graphics_layout_entries_for_target=collect_graphics_layout_entries,
        _discover_graphics_rule_selector_options=discover_graphics_rule_selector_options,
        classify_documentation_structure=classify_documentation_structure,
        discover_documentation_unit_candidates=discover_documentation_unit_candidates,
        get_graphics_rules_path=get_graphics_rules_path,
        load_graphics_rules=load_graphics_rules,
        save_graphics_rules=save_graphics_rules,
        _prompt_graphics_rule_definition_with_config=prompt_graphics_rule_definition,
        _graphics_rule_label=graphics_rule_label,
        clear_screen=clear_screen,
        _print_menu=print_menu,
        _menu_option=menu_option,
        confirm=confirm,
        prompt=prompt,
        quit_app=quit_app,
        pause=pause,
        build_menu_interaction=lambda: build_menu_calls.append("interaction") or interaction,
        _pick_or_prompt_graphics_rule_selector_value=pick_or_prompt_graphics_rule_selector_value,
        _annotate_graphics_entries_with_structure_paths=annotate_graphics_entries_with_structure_paths,
    )

    assert (
        _app_graphics_from_app.discover_graphics_rule_selector_options_from_app(
            cfg,
            selector_field="module",
            module_kind="graphics",
            app_module=app_module,
        )
        == selector_options
    )
    assert (
        _app_graphics_from_app.pick_or_prompt_graphics_rule_selector_value_from_app(
            "module",
            "graphics",
            cfg=cfg,
            app_module=app_module,
        )
        == selector_value
    )
    assert (
        _app_graphics_from_app.annotate_graphics_entries_with_structure_paths_from_app(
            [{"entry": 1}],
            project_bp,
            graph,
            app_module=app_module,
        )
        == annotated_entries
    )
    _app_graphics_from_app.graphics_rules_menu_from_app(cfg, app_module=app_module)
    assert (
        _app_graphics_from_app.prompt_graphics_rule_definition_with_config_from_app(
            cfg,
            app_module=app_module,
        )
        == prompted_rule
    )
    assert (
        _app_graphics_from_app.collect_graphics_layout_entries_for_target_from_app(
            "Root",
            project_bp,
            graph,
            app_module=app_module,
        )
        == layout_entries
    )
    _app_graphics_from_app.run_graphics_rules_validation_from_app(cfg, app_module=app_module)

    assert build_menu_calls == ["interaction"] * 2
    assert calls == [
        (
            "discover-selector",
            (cfg,),
            {
                "selector_field": "module",
                "module_kind": "graphics",
                "has_analyzed_targets_fn": has_analyzed_targets,
                "iter_loaded_projects_fn": iter_loaded_projects,
                "collect_graphics_layout_entries_for_target_fn": collect_graphics_layout_entries,
            },
        ),
        (
            "pick-selector",
            ("module", "graphics"),
            {
                "cfg": cfg,
                "discover_graphics_rule_selector_options_fn": discover_graphics_rule_selector_options,
            },
        ),
        (
            "annotate",
            ([{"entry": 1}], project_bp, graph),
            {
                "classify_documentation_structure_fn": classify_documentation_structure,
                "discover_documentation_unit_candidates_fn": discover_documentation_unit_candidates,
            },
        ),
        (
            "prompt-rule",
            (cfg,),
            {
                "prompt_fn": prompt,
                "pause_fn": pause,
                "pick_or_prompt_graphics_rule_selector_value_fn": pick_or_prompt_graphics_rule_selector_value,
                "interaction": interaction,
            },
        ),
        (
            "collect-layout",
            ("Root", project_bp, graph),
            {
                "annotate_graphics_entries_with_structure_paths_fn": annotate_graphics_entries_with_structure_paths,
            },
        ),
        (
            "validate",
            (cfg,),
            {
                "get_graphics_rules_path_fn": get_graphics_rules_path,
                "load_graphics_rules_fn": load_graphics_rules,
                "iter_loaded_projects_fn": iter_loaded_projects,
                "collect_graphics_layout_entries_for_target_fn": collect_graphics_layout_entries,
                "pause_fn": pause,
            },
        ),
    ]
    assert graphics_menu_calls == [
        (
            cfg,
            {
                "get_graphics_rules_path_fn": get_graphics_rules_path,
                "load_graphics_rules_fn": load_graphics_rules,
                "save_graphics_rules_fn": save_graphics_rules,
                "prompt_graphics_rule_definition_with_config_fn": prompt_graphics_rule_definition,
                "graphics_rule_label_fn": graphics_rule_label,
                "clear_screen_fn": clear_screen,
                "print_menu_fn": print_menu,
                "menu_option_factory": menu_option,
                "confirm_fn": confirm,
                "prompt_fn": prompt,
                "quit_app_fn": quit_app,
                "pause_fn": pause,
                "print_graphics_rules_summary_fn": print_graphics_rules_summary,
                "emit_output_fn": emit_output,
                "upsert_graphics_rule_fn": _app_graphics_from_app.graphics_rules_module.upsert_graphics_rule,
                "remove_graphics_rule_fn": _app_graphics_from_app.graphics_rules_module.remove_graphics_rule,
                "interaction": interaction,
            },
        )
    ]


def test_menus_from_app_wrappers_delegate_live_dependencies() -> None:
    cfg = cast(dict[str, Any], {"debug": False})
    build_menu_calls: list[str] = []
    interaction = SimpleNamespace(kind="interaction")
    iter_loaded_projects = object()
    target_is_library = object()
    analyze_variables = object()
    config_path = Path("config.toml")
    clear_screen = object()
    show_config = object()
    print_menu = object()
    menu_option = object()
    target_exists = object()
    save_config = object()
    apply_debug = object()
    graphics_rules_menu = object()
    quit_app = object()
    self_check = object()
    require_targets_for_menu_action = object()
    dump_menu = object()
    run_source_diff_report = object()
    refresh_analysis_caches = object()
    calls: list[tuple[str, tuple[object, ...], dict[str, object]]] = []

    def record(name: str, result: object):
        def _record(*args: object, **kwargs: object) -> object:
            calls.append((name, args, dict(kwargs)))
            return result

        return _record

    app_module = SimpleNamespace(
        app_menus=SimpleNamespace(
            dump_menu=record("dump", None),
            config_menu=record("config", True),
            tools_menu=record("tools", None),
        ),
        clear_screen=clear_screen,
        _print_menu=print_menu,
        _menu_option=menu_option,
        quit_app=quit_app,
        _iter_loaded_projects=iter_loaded_projects,
        _target_is_library=target_is_library,
        analyze_variables=analyze_variables,
        build_menu_interaction=lambda: build_menu_calls.append("interaction") or interaction,
        CONFIG_PATH=config_path,
        show_config=show_config,
        target_exists=target_exists,
        save_config=save_config,
        apply_debug=apply_debug,
        graphics_rules_menu=graphics_rules_menu,
        self_check=self_check,
        _require_targets_for_menu_action=require_targets_for_menu_action,
        dump_menu=dump_menu,
        run_source_diff_report=run_source_diff_report,
        refresh_analysis_caches=refresh_analysis_caches,
    )

    _app_menus_from_app.dump_menu_from_app(cfg, app_module=app_module)
    assert _app_menus_from_app.config_menu_from_app(cfg, app_module=app_module) is True
    _app_menus_from_app.tools_menu_from_app(cfg, app_module=app_module)

    assert build_menu_calls == ["interaction"] * 3
    assert calls == [
        (
            "dump",
            (cfg,),
            {
                "clear_screen_fn": clear_screen,
                "print_menu_fn": print_menu,
                "menu_option_factory": menu_option,
                "quit_app_fn": quit_app,
                "iter_loaded_projects_fn": iter_loaded_projects,
                "target_is_library_fn": target_is_library,
                "analyze_variables_fn": analyze_variables,
                "interaction": interaction,
            },
        ),
        (
            "config",
            (cfg,),
            {
                "config_path": config_path,
                "clear_screen_fn": clear_screen,
                "show_config_fn": show_config,
                "print_menu_fn": print_menu,
                "menu_option_factory": menu_option,
                "target_exists_fn": target_exists,
                "save_config_fn": save_config,
                "apply_debug_fn": apply_debug,
                "graphics_rules_menu_fn": graphics_rules_menu,
                "quit_app_fn": quit_app,
                "interaction": interaction,
            },
        ),
        (
            "tools",
            (cfg,),
            {
                "clear_screen_fn": clear_screen,
                "print_menu_fn": print_menu,
                "menu_option_factory": menu_option,
                "quit_app_fn": quit_app,
                "self_check_fn": self_check,
                "require_targets_for_menu_action_fn": require_targets_for_menu_action,
                "dump_menu_fn": dump_menu,
                "run_source_diff_report_fn": run_source_diff_report,
                "force_refresh_ast_fn": refresh_analysis_caches,
                "interaction": interaction,
            },
        ),
    ]


def test_remaining_from_app_wrappers_delegate_to_startup_core(monkeypatch: pytest.MonkeyPatch) -> None:  # noqa: PLR0915
    app_module = _build_startup_app_module()
    seen: list[tuple[str, tuple[object, ...], dict[str, object]]] = []
    project_bp = cast(BasePicture, SimpleNamespace())
    graph = cast(ProjectGraph, SimpleNamespace())

    def record(name: str, result: object):
        return lambda *args, **kwargs: seen.append((name, args, kwargs)) or result

    monkeypatch.setattr(_app_startup_from_app.startup_core, "run_icf_formatter", record("icf", None))
    monkeypatch.setattr(_app_startup_from_app.startup_core, "show_config", record("show-config", None))
    monkeypatch.setattr(_app_startup_from_app.startup_core, "print_menu", record("print-menu", None))
    monkeypatch.setattr(_app_startup_from_app.startup_core, "summarize_targets", record("summarize", "targets"))
    monkeypatch.setattr(_app_startup_from_app.startup_core, "show_help", record("show-help", None))
    monkeypatch.setattr(
        _app_startup_from_app.startup_core,
        "discover_graphics_rule_selector_options",
        record("discover-selector", [{"label": "A"}]),
    )
    monkeypatch.setattr(
        _app_startup_from_app.startup_core,
        "pick_or_prompt_graphics_rule_selector_value",
        record("pick-selector", "selector"),
    )
    monkeypatch.setattr(
        _app_startup_from_app.startup_core,
        "annotate_graphics_entries_with_structure_paths",
        record("annotate", [{"path": "A"}]),
    )
    monkeypatch.setattr(_app_startup_from_app.startup_core, "graphics_rules_menu", record("graphics-menu", None))
    monkeypatch.setattr(
        _app_startup_from_app.startup_core,
        "prompt_graphics_rule_definition_with_config",
        record("prompt-rule", {"rule": "value"}),
    )
    monkeypatch.setattr(
        _app_startup_from_app.startup_core,
        "collect_graphics_layout_entries_for_target",
        record("collect-layout", [{"target": "Root"}]),
    )
    monkeypatch.setattr(
        _app_startup_from_app.startup_core,
        "run_graphics_rules_validation",
        record("validate-graphics", None),
    )
    monkeypatch.setattr(
        _app_startup_from_app.startup_core,
        "get_documentation_unit_selection",
        record("get-doc-selection", {"mode": "all"}),
    )
    monkeypatch.setattr(
        _app_startup_from_app.startup_core,
        "preview_documentation_unit_candidates",
        record("preview-docs", None),
    )
    monkeypatch.setattr(
        _app_startup_from_app.startup_core,
        "configure_documentation_scope_by_moduletype",
        record("scope-moduletype", True),
    )
    monkeypatch.setattr(
        _app_startup_from_app.startup_core,
        "configure_documentation_scope_by_instance_path",
        record("scope-instance", False),
    )
    monkeypatch.setattr(
        _app_startup_from_app.startup_core,
        "reset_documentation_scope",
        record("scope-reset", True),
    )
    monkeypatch.setattr(
        _app_startup_from_app.startup_core,
        "run_generate_documentation",
        record("generate-docs", None),
    )
    monkeypatch.setattr(
        _app_startup_from_app.startup_core,
        "documentation_menu",
        record("docs-menu", True),
    )
    monkeypatch.setattr(_app_startup_from_app.startup_core, "dump_menu", record("dump-menu", None))
    monkeypatch.setattr(_app_startup_from_app.startup_core, "config_menu", record("config-menu", True))
    monkeypatch.setattr(_app_startup_from_app.startup_core, "tools_menu", record("tools-menu", None))

    _app_startup_from_app.run_icf_formatter_from_app({"debug": False}, app_module=app_module)
    _app_startup_from_app.show_config_from_app({"debug": False}, app_module=app_module)
    _app_startup_from_app.print_menu_from_app("Menu", [("1", "One")], intro="Intro", note="Note", app_module=app_module)
    assert _app_startup_from_app.summarize_targets_from_app({"debug": False}, app_module=app_module) == "targets"
    _app_startup_from_app.show_help_from_app({"debug": False}, app_module=app_module)
    assert _app_startup_from_app.discover_graphics_rule_selector_options_from_app(
        {"debug": False},
        selector_field="module",
        module_kind="graphics",
        app_module=app_module,
    ) == [{"label": "A"}]
    assert (
        _app_startup_from_app.pick_or_prompt_graphics_rule_selector_value_from_app(
            "module",
            "graphics",
            cfg={"debug": False},
            app_module=app_module,
        )
        == "selector"
    )
    assert _app_startup_from_app.annotate_graphics_entries_with_structure_paths_from_app(
        [{"entry": 1}],
        project_bp,
        graph,
        app_module=app_module,
    ) == [{"path": "A"}]
    _app_startup_from_app.graphics_rules_menu_from_app({"debug": False}, app_module=app_module)
    assert _app_startup_from_app.prompt_graphics_rule_definition_with_config_from_app(
        {"debug": False},
        app_module=app_module,
    ) == {"rule": "value"}
    assert _app_startup_from_app.collect_graphics_layout_entries_for_target_from_app(
        "Root",
        project_bp,
        graph,
        app_module=app_module,
    ) == [{"target": "Root"}]
    _app_startup_from_app.run_graphics_rules_validation_from_app({"debug": False}, app_module=app_module)
    assert _app_startup_from_app.get_documentation_unit_selection_from_app(app_module=app_module) == {"mode": "all"}
    _app_startup_from_app.preview_documentation_unit_candidates_from_app({"debug": False}, app_module=app_module)
    assert _app_startup_from_app.configure_documentation_scope_by_moduletype_from_app(app_module=app_module) is True
    assert _app_startup_from_app.configure_documentation_scope_by_instance_path_from_app(app_module=app_module) is False
    assert _app_startup_from_app.reset_documentation_scope_from_app(app_module=app_module) is True
    _app_startup_from_app.run_generate_documentation_from_app({"debug": False}, app_module=app_module)
    assert _app_startup_from_app.documentation_menu_from_app({"debug": False}, app_module=app_module) is True
    _app_startup_from_app.dump_menu_from_app({"debug": False}, app_module=app_module)
    assert _app_startup_from_app.config_menu_from_app({"debug": False}, app_module=app_module) is True
    _app_startup_from_app.tools_menu_from_app({"debug": False}, app_module=app_module)

    names = [name for name, _args, _kwargs in seen]
    assert names == [
        "icf",
        "show-config",
        "print-menu",
        "summarize",
        "show-help",
        "discover-selector",
        "pick-selector",
        "annotate",
        "graphics-menu",
        "prompt-rule",
        "collect-layout",
        "validate-graphics",
        "get-doc-selection",
        "preview-docs",
        "scope-moduletype",
        "scope-instance",
        "scope-reset",
        "generate-docs",
        "docs-menu",
        "dump-menu",
        "config-menu",
        "tools-menu",
    ]


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
    selection = cast(Any, app._get_documentation_unit_selection())
    assert selection.scope == "all"
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


def test_simulation_and_analysis_wrappers_delegate(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:  # noqa: PLR0915
    cfg = app.DEFAULT_CONFIG.copy()
    snapshot = object()
    project_bp = cast(BasePicture, SimpleNamespace())
    graph = cast(ProjectGraph, SimpleNamespace())
    analysis_calls: list[tuple[str, tuple[object, ...], dict[str, object]]] = []

    monkeypatch.setattr(app, "load_workspace_snapshot", lambda path, **kwargs: snapshot)
    import sattlint.simulation as simulation_module  # noqa: PLC0415

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
