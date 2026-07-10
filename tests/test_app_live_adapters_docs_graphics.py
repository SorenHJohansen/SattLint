# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportPrivateUsage=false, reportArgumentType=false, reportAttributeAccessIssue=false
from ._app_live_adapters_support import *


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
        ("preview", (cfg,), {"iter_loaded_projects_fn": loaded_projects, "pause_fn": pause}),
        ("scope-moduletype", (), {"split_csv_values_fn": split_csv_values, "interaction": interaction}),
        (
            "scope-instance-path",
            (),
            {"split_csv_values_fn": split_csv_values, "interaction": interaction},
        ),
        ("scope-reset", (), {"interaction": interaction}),
        ("generate", (cfg,), {"iter_loaded_projects_fn": loaded_projects, "interaction": interaction}),
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

    assert calls[0][0] == "discover-selector"


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
            cfg, selector_field="module", module_kind="graphics", app_module=app_module
        )
        == selector_options
    )
    assert (
        _app_graphics_from_app.pick_or_prompt_graphics_rule_selector_value_from_app(
            "module", "graphics", cfg=cfg, app_module=app_module
        )
        == selector_value
    )
    assert (
        _app_graphics_from_app.annotate_graphics_entries_with_structure_paths_from_app(
            [{"entry": 1}], project_bp, graph, app_module=app_module
        )
        == annotated_entries
    )
    _app_graphics_from_app.graphics_rules_menu_from_app(cfg, app_module=app_module)
    assert (
        _app_graphics_from_app.prompt_graphics_rule_definition_with_config_from_app(cfg, app_module=app_module)
        == prompted_rule
    )
    assert (
        _app_graphics_from_app.collect_graphics_layout_entries_for_target_from_app(
            "Root", project_bp, graph, app_module=app_module
        )
        == layout_entries
    )
    _app_graphics_from_app.run_graphics_rules_validation_from_app(cfg, app_module=app_module)

    assert build_menu_calls == ["interaction"] * 2
    assert graphics_menu_calls[0][0] is cfg


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
    assert docs_calls[0] == ("selection", None, app)


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
