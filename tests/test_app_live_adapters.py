# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportPrivateUsage=false, reportArgumentType=false, reportAttributeAccessIssue=false
from ._app_live_adapters_support import *


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

    monkeypatch.setattr(_app_startup_from_app.cli_entry, "run_cli", fake_run_cli)

    result = app.run_cli(["analyze", "--check", "variables"])

    assert result == 23
    assert seen["argv"] == ["analyze", "--check", "variables"]
    assert seen["config_path"] == app.CONFIG_PATH
    assert seen["build_cli_parser_fn"] is app.build_cli_parser
    assert seen["load_config_fn"] is app.load_config
    assert seen["apply_debug_fn"] is app.apply_debug
    assert seen["command_handlers"] == cli_command_handlers.build_app_command_handlers(app)


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
    collect_run_checks_result = object()
    iter_loaded_projects = object()
    get_selectable_analyzers = object()
    get_enabled_analyzers = object()
    target_is_library = object()
    simulate_target = object()
    get_documentation_unit_selection = object()

    app_module.validate_effective_config = validate_config
    app_module.app_analysis = SimpleNamespace(collect_run_checks_result=collect_run_checks_result)
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
        "validate_config_fn": validate_config,
        "output_format": "text",
        "exit_success": app_module.EXIT_SUCCESS,
        "exit_usage_error": app_module.EXIT_USAGE_ERROR,
    }

    analyze_args, analyze_kwargs = seen_by_name["analyze"]
    assert analyze_args == (cfg,)
    assert analyze_kwargs == {
        "selected_keys": selected_keys,
        "selected_issue_kinds": selected_issue_kinds,
        "use_cache": False,
        "output_format": "text",
        "run_analyze_command_fn": app_module.app_cli_commands.run_analyze_command,
        "collect_run_checks_result_fn": collect_run_checks_result,
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
