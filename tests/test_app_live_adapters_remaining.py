# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportPrivateUsage=false, reportArgumentType=false
from ._app_live_adapters_support import *


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
    assert calls[0][0] == "dump"


def test_remaining_from_app_wrappers_delegate_to_startup_core(monkeypatch: pytest.MonkeyPatch) -> None:
    app_module = _build_startup_app_module()
    seen: list[tuple[str, tuple[object, ...], dict[str, object]]] = []
    project_bp = cast(BasePicture, SimpleNamespace())
    graph = cast(ProjectGraph, SimpleNamespace())

    def record(name: str, result: object):
        return lambda *args, **kwargs: seen.append((name, args, kwargs)) or result

    monkeypatch.setattr(_app_startup_from_app.interactive_core, "run_icf_formatter", record("icf", None))
    monkeypatch.setattr(_app_startup_from_app.interactive_core, "show_config", record("show-config", None))
    monkeypatch.setattr(_app_startup_from_app.interactive_core, "print_menu", record("print-menu", None))
    monkeypatch.setattr(_app_startup_from_app.interactive_core, "summarize_targets", record("summarize", "targets"))
    monkeypatch.setattr(_app_startup_from_app.interactive_core, "show_help", record("show-help", None))
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
        _app_startup_from_app.startup_core, "run_graphics_rules_validation", record("validate-graphics", None)
    )
    monkeypatch.setattr(
        _app_startup_from_app.startup_core,
        "get_documentation_unit_selection",
        record("get-doc-selection", {"mode": "all"}),
    )
    monkeypatch.setattr(
        _app_startup_from_app.startup_core, "preview_documentation_unit_candidates", record("preview-docs", None)
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
    monkeypatch.setattr(_app_startup_from_app.startup_core, "reset_documentation_scope", record("scope-reset", True))
    monkeypatch.setattr(_app_startup_from_app.startup_core, "run_generate_documentation", record("generate-docs", None))
    monkeypatch.setattr(_app_startup_from_app.startup_core, "documentation_menu", record("docs-menu", True))
    monkeypatch.setattr(_app_startup_from_app.interactive_core, "dump_menu", record("dump-menu", None))
    monkeypatch.setattr(_app_startup_from_app.interactive_core, "config_menu", record("config-menu", True))
    monkeypatch.setattr(_app_startup_from_app.interactive_core, "tools_menu", record("tools-menu", None))

    _app_startup_from_app.run_icf_formatter_from_app({"debug": False}, app_module=app_module)
    _app_startup_from_app.show_config_from_app({"debug": False}, app_module=app_module)
    _app_startup_from_app.print_menu_from_app("Menu", [("1", "One")], intro="Intro", note="Note", app_module=app_module)
    assert _app_startup_from_app.summarize_targets_from_app({"debug": False}, app_module=app_module) == "targets"
    _app_startup_from_app.show_help_from_app({"debug": False}, app_module=app_module)
    assert _app_startup_from_app.discover_graphics_rule_selector_options_from_app(
        {"debug": False}, selector_field="module", module_kind="graphics", app_module=app_module
    ) == [{"label": "A"}]
    assert (
        _app_startup_from_app.pick_or_prompt_graphics_rule_selector_value_from_app(
            "module", "graphics", cfg={"debug": False}, app_module=app_module
        )
        == "selector"
    )
    assert _app_startup_from_app.annotate_graphics_entries_with_structure_paths_from_app(
        [{"entry": 1}], project_bp, graph, app_module=app_module
    ) == [{"path": "A"}]
    _app_startup_from_app.graphics_rules_menu_from_app({"debug": False}, app_module=app_module)
    assert _app_startup_from_app.prompt_graphics_rule_definition_with_config_from_app(
        {"debug": False}, app_module=app_module
    ) == {"rule": "value"}
    assert _app_startup_from_app.collect_graphics_layout_entries_for_target_from_app(
        "Root", project_bp, graph, app_module=app_module
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

    assert seen[0][0] == "icf"


def test_simulation_and_analysis_wrappers_delegate(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
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
    assert analysis_by_name["load-program-ast"][0] == (cfg, "Worker")


def test_running_app_as_main_raises_system_exit_from_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_app_startup_from_app, "main_from_app", lambda argv, *, app_module: 17)
    monkeypatch.setattr(sys, "argv", ["sattlint", "--help"])

    with pytest.raises(SystemExit) as exc_info:
        runpy.run_module("sattlint.app", run_name="__main__")

    assert exc_info.value.code == 17
