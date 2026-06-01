# ruff: noqa: F403, F405
from ._app_analysis_test_support import *


def test_run_advanced_datatype_analysis_covers_back_compare_and_debug_branches(monkeypatch):
    lines: list[str] = []
    pauses: list[str] = []

    monkeypatch.setattr(app_analysis, "emit_output", lambda message: lines.append(message))
    monkeypatch.setattr(builtins, "input", make_input(["b", "2", "Pump", "3", "FlowVar"]))
    monkeypatch.setattr(variables_reporting_module, "debug_variable_usage", lambda *_args, **_kwargs: "debug report")

    app_analysis.run_advanced_datatype_analysis(app.DEFAULT_CONFIG.copy(), pause_fn=lambda: pauses.append("pause-back"))
    app_analysis.run_advanced_datatype_analysis(
        app.DEFAULT_CONFIG.copy(), pause_fn=lambda: pauses.append("pause-compare")
    )
    app_analysis.run_advanced_datatype_analysis(
        app.DEFAULT_CONFIG.copy(),
        iter_loaded_projects_fn=cast(
            Any,
            lambda *_args, **_kwargs: iter([("TargetA", "bp-a", SimpleNamespace())]),
        ),
        pause_fn=lambda: pauses.append("pause-debug"),
    )

    assert any("Module comparison analysis not yet implemented" in line for line in lines)
    assert any("debug report" in line for line in lines)
    assert pauses == ["pause-back", "pause-compare", "pause-debug"]


def test_variable_usage_submenu_exposes_min_max_report(noop_screen, monkeypatch):
    captured: list[object] = []
    monkeypatch.setattr(app, "run_variable_analysis", lambda _cfg, kinds: captured.append(kinds))
    monkeypatch.setattr(builtins, "input", make_input(["9", "b"]))

    app.variable_usage_submenu(app.DEFAULT_CONFIG.copy())

    assert captured == [{app.IssueKind.MIN_MAX_MAPPING_MISMATCH}]


def test_variable_usage_submenu_exposes_ui_only_report(noop_screen, monkeypatch):
    captured: list[object] = []
    monkeypatch.setattr(app, "run_variable_analysis", lambda _cfg, kinds: captured.append(kinds))
    monkeypatch.setattr(builtins, "input", make_input(["15", "b"]))

    app.variable_usage_submenu(app.DEFAULT_CONFIG.copy())

    assert captured == [{app.IssueKind.UI_ONLY}]


def test_variable_usage_submenu_exposes_unknown_parameter_target_report(noop_screen, monkeypatch):
    captured: list[object] = []
    monkeypatch.setattr(app, "run_variable_analysis", lambda _cfg, kinds: captured.append(kinds))
    monkeypatch.setattr(builtins, "input", make_input(["6", "b"]))

    app.variable_usage_submenu(app.DEFAULT_CONFIG.copy())

    assert captured == [{app.IssueKind.UNKNOWN_PARAMETER_TARGET}]


def test_variable_usage_submenu_exposes_reset_contamination_report(noop_screen, monkeypatch):
    captured: list[object] = []
    monkeypatch.setattr(app, "run_variable_analysis", lambda _cfg, kinds: captured.append(kinds))
    monkeypatch.setattr(builtins, "input", make_input(["13", "b"]))

    app.variable_usage_submenu(app.DEFAULT_CONFIG.copy())

    assert captured == [{app.IssueKind.RESET_CONTAMINATION}]


def test_variable_usage_submenu_exposes_implicit_latch_report(noop_screen, monkeypatch):
    captured: list[object] = []
    monkeypatch.setattr(app, "run_variable_analysis", lambda _cfg, kinds: captured.append(kinds))
    monkeypatch.setattr(builtins, "input", make_input(["19", "b"]))

    app.variable_usage_submenu(app.DEFAULT_CONFIG.copy())

    assert captured == [{app.IssueKind.IMPLICIT_LATCH}]


def test_variable_usage_submenu_exposes_shadowing_report(noop_screen, monkeypatch):
    captured: list[object] = []
    monkeypatch.setattr(app, "run_variable_analysis", lambda _cfg, kinds: captured.append(kinds))
    monkeypatch.setattr(builtins, "input", make_input(["14", "b"]))

    app.variable_usage_submenu(app.DEFAULT_CONFIG.copy())

    assert captured == [{app.IssueKind.SHADOWING}]


def test_variable_usage_submenu_exposes_hidden_global_coupling_report(noop_screen, monkeypatch):
    captured: list[object] = []
    monkeypatch.setattr(app, "run_variable_analysis", lambda _cfg, kinds: captured.append(kinds))
    monkeypatch.setattr(builtins, "input", make_input(["21", "b"]))

    app.variable_usage_submenu(app.DEFAULT_CONFIG.copy())

    assert captured == [{app.IssueKind.HIDDEN_GLOBAL_COUPLING}]


def test_variable_usage_submenu_exposes_global_scope_minimization_report(noop_screen, monkeypatch):
    captured: list[object] = []
    monkeypatch.setattr(app, "run_variable_analysis", lambda _cfg, kinds: captured.append(kinds))
    monkeypatch.setattr(builtins, "input", make_input(["20", "b"]))

    app.variable_usage_submenu(app.DEFAULT_CONFIG.copy())

    assert captured == [{app.IssueKind.GLOBAL_SCOPE_MINIMIZATION}]


def test_variable_usage_submenu_exposes_high_fan_in_out_report(noop_screen, monkeypatch):
    captured: list[object] = []
    monkeypatch.setattr(app, "run_variable_analysis", lambda _cfg, kinds: captured.append(kinds))
    monkeypatch.setattr(builtins, "input", make_input(["22", "b"]))

    app.variable_usage_submenu(app.DEFAULT_CONFIG.copy())

    assert captured == [{app.IssueKind.HIGH_FAN_IN_OUT}]


def test_variable_usage_submenu_exposes_procedure_status_report(noop_screen, monkeypatch):
    captured: list[object] = []
    monkeypatch.setattr(app, "run_variable_analysis", lambda _cfg, kinds: captured.append(kinds))
    monkeypatch.setattr(builtins, "input", make_input(["16", "b"]))

    app.variable_usage_submenu(app.DEFAULT_CONFIG.copy())

    assert captured == [{app.IssueKind.PROCEDURE_STATUS}]


def test_variable_usage_submenu_exposes_write_without_effect_report(noop_screen, monkeypatch):
    captured: list[object] = []
    monkeypatch.setattr(app, "run_variable_analysis", lambda _cfg, kinds: captured.append(kinds))
    monkeypatch.setattr(builtins, "input", make_input(["17", "b"]))

    app.variable_usage_submenu(app.DEFAULT_CONFIG.copy())

    assert captured == [{app.IssueKind.WRITE_WITHOUT_EFFECT}]


def test_variable_usage_submenu_exposes_contract_mismatch_report(noop_screen, monkeypatch):
    captured: list[object] = []
    monkeypatch.setattr(app, "run_variable_analysis", lambda _cfg, kinds: captured.append(kinds))
    monkeypatch.setattr(builtins, "input", make_input(["18", "b"]))

    app.variable_usage_submenu(app.DEFAULT_CONFIG.copy())

    assert captured == [{app.IssueKind.CONTRACT_MISMATCH}]


def test_app_analysis_variable_usage_submenu_routes_investigation_tools_and_invalid_choice(monkeypatch):
    calls: list[str] = []
    pauses: list[str] = []

    monkeypatch.setattr(builtins, "input", make_input(["23", "24", "25", "invalid", "b"]))
    monkeypatch.setattr(app_analysis, "emit_output", lambda *_args, **_kwargs: None)

    app_analysis.variable_usage_submenu(
        app.DEFAULT_CONFIG.copy(),
        clear_screen_fn=lambda: calls.append("clear"),
        quit_app_fn=lambda: pytest.fail("quit should not be called"),
        run_variable_analysis_fn=lambda *_args, **_kwargs: pytest.fail("variable report should not be called"),
        run_datatype_usage_analysis_fn=lambda _cfg: calls.append("datatype"),
        run_debug_variable_usage_fn=lambda _cfg: calls.append("debug"),
        run_module_localvar_analysis_fn=lambda _cfg: calls.append("localvar"),
        pause_fn=lambda: pauses.append("pause"),
    )

    assert calls.count("datatype") == 1
    assert calls.count("debug") == 1
    assert calls.count("localvar") == 1
    assert pauses == ["pause"]


def test_variable_usage_submenu_handles_keyboard_interrupt_and_returns_to_menu(monkeypatch):
    lines: list[str] = []
    pauses: list[str] = []

    monkeypatch.setattr(builtins, "input", make_input(["1", "b"]))
    monkeypatch.setattr(
        app_analysis, "emit_output", lambda *args, **_kwargs: lines.append(" ".join(str(arg) for arg in args))
    )

    app_analysis.variable_usage_submenu(
        app.DEFAULT_CONFIG.copy(),
        clear_screen_fn=lambda: None,
        quit_app_fn=lambda: pytest.fail("quit should not be called"),
        run_variable_analysis_fn=lambda *_args, **_kwargs: (_ for _ in ()).throw(KeyboardInterrupt()),
        run_datatype_usage_analysis_fn=lambda _cfg: pytest.fail("datatype should not be called"),
        run_debug_variable_usage_fn=lambda _cfg: pytest.fail("debug should not be called"),
        run_module_localvar_analysis_fn=lambda _cfg: pytest.fail("localvar should not be called"),
        pause_fn=lambda: pauses.append("pause"),
    )

    assert any("Operation canceled. Returning to the menu." in line for line in lines)
    assert pauses == ["pause"]


def test_module_analysis_submenu_routes_choices_and_invalid_choice(monkeypatch):
    calls: list[str] = []
    pauses: list[str] = []

    monkeypatch.setattr(builtins, "input", make_input(["1", "2", "3", "4", "invalid", "b"]))

    app_analysis.module_analysis_submenu(
        app.DEFAULT_CONFIG.copy(),
        clear_screen_fn=lambda: calls.append("clear"),
        print_menu_fn=lambda *_args, **_kwargs: None,
        menu_option_factory=lambda key, label, detail: (key, label, detail),
        quit_app_fn=lambda: pytest.fail("quit should not be called"),
        run_module_duplicates_analysis_fn=lambda _cfg: calls.append("duplicates"),
        run_module_find_by_name_fn=lambda _cfg: calls.append("find"),
        run_module_tree_debug_fn=lambda _cfg: calls.append("tree"),
        run_graphics_rules_validation_fn=lambda _cfg: calls.append("graphics"),
        pause_fn=lambda: pauses.append("pause"),
    )

    assert calls.count("duplicates") == 1
    assert calls.count("find") == 1
    assert calls.count("tree") == 1
    assert calls.count("graphics") == 1
    assert pauses == ["pause"]


def test_interface_communication_submenu_routes_choices_and_invalid_choice(monkeypatch):
    calls: list[str] = []
    pauses: list[str] = []

    monkeypatch.setattr(builtins, "input", make_input(["1", "2", "3", "invalid", "b"]))

    app_analysis.interface_communication_submenu(
        app.DEFAULT_CONFIG.copy(),
        clear_screen_fn=lambda: calls.append("clear"),
        print_menu_fn=lambda *_args, **_kwargs: None,
        menu_option_factory=lambda key, label, detail: (key, label, detail),
        quit_app_fn=lambda: pytest.fail("quit should not be called"),
        run_mms_interface_analysis_fn=lambda _cfg: calls.append("mms"),
        run_icf_validation_fn=lambda _cfg: calls.append("icf-validate"),
        run_icf_formatter_fn=lambda _cfg: calls.append("icf-format"),
        pause_fn=lambda: pauses.append("pause"),
    )

    assert calls.count("mms") == 1
    assert calls.count("icf-validate") == 1
    assert calls.count("icf-format") == 1
    assert pauses == ["pause"]


def test_code_quality_submenu_routes_choice_and_invalid_choice(monkeypatch):
    calls: list[str] = []
    pauses: list[str] = []

    monkeypatch.setattr(builtins, "input", make_input(["1", "invalid", "b"]))

    app_analysis.code_quality_submenu(
        app.DEFAULT_CONFIG.copy(),
        clear_screen_fn=lambda: calls.append("clear"),
        print_menu_fn=lambda *_args, **_kwargs: None,
        menu_option_factory=lambda key, label, detail: (key, label, detail),
        quit_app_fn=lambda: pytest.fail("quit should not be called"),
        run_comment_code_analysis_fn=lambda _cfg: calls.append("comment-code"),
        pause_fn=lambda: pauses.append("pause"),
    )

    assert calls.count("comment-code") == 1
    assert pauses == ["pause"]


def test_analyzer_catalog_menu_routes_suite_analyzers_and_invalid_choices(monkeypatch):
    calls: list[object] = []
    pauses: list[str] = []
    analyzers = [
        SimpleNamespace(key="variables", name="Variables", description="Variable checks"),
        SimpleNamespace(key="mms", name="MMS", description="MMS checks"),
    ]

    monkeypatch.setattr(builtins, "input", make_input(["1", "2", "3", "9", "invalid", "b"]))

    app_analysis.analyzer_catalog_menu(
        app.DEFAULT_CONFIG.copy(),
        clear_screen_fn=lambda: calls.append("clear"),
        print_menu_fn=lambda *_args, **_kwargs: None,
        menu_option_factory=lambda key, label, detail: (key, label, detail),
        quit_app_fn=lambda: pytest.fail("quit should not be called"),
        get_enabled_analyzers_fn=lambda: analyzers,
        run_checks_fn=lambda _cfg, selected: calls.append(tuple(selected) if selected is not None else None),
        pause_fn=lambda: pauses.append("pause"),
    )

    assert None in calls
    assert ("variables",) in calls
    assert ("mms",) in calls
    assert pauses == ["pause", "pause"]


def test_advanced_analysis_menu_routes_choices_and_invalid_choice(monkeypatch):
    calls: list[str] = []
    pauses: list[str] = []

    monkeypatch.setattr(builtins, "input", make_input(["1", "2", "3", "invalid", "b"]))

    app_analysis.advanced_analysis_menu(
        app.DEFAULT_CONFIG.copy(),
        clear_screen_fn=lambda: calls.append("clear"),
        print_menu_fn=lambda *_args, **_kwargs: None,
        menu_option_factory=lambda key, label, detail: (key, label, detail),
        quit_app_fn=lambda: pytest.fail("quit should not be called"),
        run_datatype_usage_analysis_fn=lambda _cfg: calls.append("datatype"),
        run_debug_variable_usage_fn=lambda _cfg: calls.append("debug"),
        run_module_localvar_analysis_fn=lambda _cfg: calls.append("localvar"),
        pause_fn=lambda: pauses.append("pause"),
    )

    assert calls.count("datatype") == 1
    assert calls.count("debug") == 1
    assert calls.count("localvar") == 1
    assert pauses == ["pause"]


def test_analysis_menu_routes_choices_and_invalid_choice(monkeypatch):
    calls: list[str] = []
    pauses: list[str] = []

    monkeypatch.setattr(builtins, "input", make_input(["1", "2", "3", "4", "5", "6", "7", "invalid", "b"]))

    app_analysis.analysis_menu(
        app.DEFAULT_CONFIG.copy(),
        clear_screen_fn=lambda: calls.append("clear"),
        print_menu_fn=lambda *_args, **_kwargs: None,
        menu_option_factory=lambda key, label, detail: (key, label, detail),
        quit_app_fn=lambda: pytest.fail("quit should not be called"),
        run_checks_fn=lambda _cfg, _selected: calls.append("checks"),
        variable_usage_submenu_fn=lambda _cfg: calls.append("variables"),
        module_analysis_submenu_fn=lambda _cfg: calls.append("modules"),
        interface_communication_submenu_fn=lambda _cfg: calls.append("interfaces"),
        code_quality_submenu_fn=lambda _cfg: calls.append("quality"),
        analyzer_catalog_menu_fn=lambda _cfg: calls.append("catalog"),
        advanced_analysis_menu_fn=lambda _cfg: calls.append("advanced"),
        summarize_targets_fn=lambda _cfg: "TargetA",
        pause_fn=lambda: pauses.append("pause"),
    )

    assert calls.count("checks") == 1
    assert calls.count("variables") == 1
    assert calls.count("modules") == 1
    assert calls.count("interfaces") == 1
    assert calls.count("quality") == 1
    assert calls.count("catalog") == 1
    assert calls.count("advanced") == 1
    assert pauses == ["pause"]


def test_analysis_menu_handles_keyboard_interrupt_from_submenu_and_returns_to_menu(monkeypatch):
    lines: list[str] = []
    pauses: list[str] = []

    monkeypatch.setattr(builtins, "input", make_input(["2", "b"]))
    monkeypatch.setattr(
        app_analysis, "emit_output", lambda *args, **_kwargs: lines.append(" ".join(str(arg) for arg in args))
    )

    app_analysis.analysis_menu(
        app.DEFAULT_CONFIG.copy(),
        clear_screen_fn=lambda: None,
        print_menu_fn=lambda *_args, **_kwargs: None,
        menu_option_factory=lambda key, label, detail: (key, label, detail),
        quit_app_fn=lambda: pytest.fail("quit should not be called"),
        run_checks_fn=lambda _cfg, _selected: pytest.fail("checks should not be called"),
        variable_usage_submenu_fn=lambda _cfg: (_ for _ in ()).throw(KeyboardInterrupt()),
        module_analysis_submenu_fn=lambda _cfg: pytest.fail("modules should not be called"),
        interface_communication_submenu_fn=lambda _cfg: pytest.fail("interfaces should not be called"),
        code_quality_submenu_fn=lambda _cfg: pytest.fail("quality should not be called"),
        analyzer_catalog_menu_fn=lambda _cfg: pytest.fail("catalog should not be called"),
        advanced_analysis_menu_fn=lambda _cfg: pytest.fail("advanced should not be called"),
        summarize_targets_fn=lambda _cfg: "TargetA",
        pause_fn=lambda: pauses.append("pause"),
    )

    assert any("Operation canceled. Returning to the menu." in line for line in lines)
    assert pauses == ["pause"]


def test_app_analysis_wrappers_delegate_to_underlying_helpers(monkeypatch):
    monkeypatch.setattr(
        app_analysis.app_support_module,
        "target_validation_warnings",
        lambda target, warnings: [f"{target}:{len(warnings)}"],
    )
    monkeypatch.setattr(app_analysis, "_iter_loaded_projects", lambda *_args, **_kwargs: iter([("TargetA", "bp", "g")]))
    monkeypatch.setattr(app_analysis, "_source_paths_for_current_target", lambda *_args: {Path("TargetA.s")})
    monkeypatch.setattr(app_analysis, "_target_is_library", lambda *_args: True)
    monkeypatch.setattr(app_analysis, "get_default_cli_analyzers", lambda: ["variables"])

    assert app_analysis._target_validation_warnings("TargetA", ["a", "b"]) == ["TargetA:2"]
    assert list(app_analysis.iter_loaded_projects({})) == [("TargetA", "bp", "g")]
    assert app_analysis.source_paths_for_current_target(cast(Any, "bp"), cast(Any, "graph")) == {Path("TargetA.s")}
    assert app_analysis.target_is_library({}, cast(Any, "bp"), cast(Any, "graph")) is True
    assert app_analysis._get_enabled_analyzers() == ["variables"]


def test_target_validation_warnings_suppresses_expected_unavailable_dependency_warning():
    assert app_analysis._target_validation_warnings(
        "KaHAMPCSøjleLib",
        [
            "KaHAMPCSøjleLib: dependency 'controllib' unavailable: expected proprietary dependency",
            "KaHAMPCSøjleLib: warning one",
            "dep_b: warning two",
        ],
    ) == ["KaHAMPCSøjleLib: warning one"]


def test_analysis_loading_helpers_cover_target_accessors_and_refresh_formatting(monkeypatch):
    monkeypatch.setattr(app_analysis.app_support_module, "get_analyzed_targets", lambda cfg: ["TargetA"])
    monkeypatch.setattr(app_analysis.app_support_module, "require_analyzed_targets", lambda cfg: ["TargetB"])

    assert app_analysis._get_analyzed_targets({}) == ["TargetA"]
    assert app_analysis._require_analyzed_targets({}) == ["TargetB"]
    assert app_analysis.analysis_loading_module._workspace_dependency_suffixes("draft") == (".l", ".z")
    assert app_analysis.analysis_loading_module._workspace_dependency_suffixes("official") == (".z",)
    assert app_analysis.analysis_loading_module._format_refresh_stage_timings(
        {"load_or_parse": 0.1, "validate": 0.2, "ast_cache_save": 0.3},
        refresh_mode="ast-only",
    ) == (
        "AST refresh stage totals: "
        "load_or_parse=0.1000s, validate=0.2000s, graphics=skipped, index=skipped, ast_cache_save=0.3000s"
    )


def test_analysis_loading_reverse_consumer_helpers_cover_scan_and_queueing(monkeypatch, tmp_path):
    program_dir = tmp_path / "programs"
    other_dir = tmp_path / "other"
    error_dir = tmp_path / "error"
    missing_dir = tmp_path / "missing"
    program_dir.mkdir()
    other_dir.mkdir()
    error_dir.mkdir()

    (program_dir / "consumer.l").write_text("", encoding="utf-8")
    (program_dir / "consumer.z").write_text("", encoding="utf-8")
    (program_dir / "selected.l").write_text("", encoding="utf-8")
    (program_dir / "notes.txt").write_text("", encoding="utf-8")
    (other_dir / "consumer.z").write_text("", encoding="utf-8")
    (other_dir / "remote.z").write_text("", encoding="utf-8")

    original_iterdir = Path.iterdir

    def fake_iterdir(path: Path):
        if path == error_dir:
            raise OSError("boom")
        return original_iterdir(path)

    monkeypatch.setattr(Path, "iterdir", fake_iterdir)

    cfg = {
        "program_dir": str(program_dir),
        "other_lib_dirs": [str(other_dir), str(error_dir), str(missing_dir)],
        "mode": "draft",
    }

    assert list(
        app_analysis.analysis_loading_module._iter_workspace_reverse_library_consumer_dependency_files(cfg)
    ) == [
        ("consumer", program_dir / "consumer.l"),
        ("selected", program_dir / "selected.l"),
        ("remote", other_dir / "remote.z"),
    ]

    visits: list[tuple[str, Path]] = []
    deps_paths = {
        "CandidateA": program_dir / "CandidateA.z",
        "NoDeps": program_dir / "NoDeps.z",
        "NoPath": None,
        "DupLocal": program_dir / "CandidateA.z",
    }
    deps_map = {
        None: ["Selected"],
        program_dir / "CandidateA.z": ["Selected"],
        program_dir / "NoDeps.z": ["Other"],
        other_dir / "Remote.z": ["Selected"],
        other_dir / "Ignore.z": ["Other"],
    }

    class FakeLoader:
        def _find_deps_with_context(self, target_name, requester_dir=None):
            return deps_paths[target_name]

        def _read_deps(self, deps_path):
            return deps_map.get(deps_path, [])

        def _visit(self, target_name, graph, syntax_only, requester_dir, syntax_check):
            del graph, syntax_only, syntax_check
            visits.append((target_name, requester_dir))

    loader = FakeLoader()
    monkeypatch.setattr(app_analysis.analysis_loading_module, "target_is_library", lambda *args, **kwargs: False)
    app_analysis.analysis_loading_module._include_reverse_library_consumers(
        cfg,
        selected_target="Selected",
        root_bp=cast(Any, "bp"),
        graph=cast(Any, "graph"),
        loader=loader,
        require_analyzed_targets_fn=lambda _cfg: ["Selected", "CandidateA", "NoDeps", "NoPath", "DupLocal"],
        engine_module=SimpleNamespace(is_within_directory=lambda *_args: False),
    )
    assert visits == []

    monkeypatch.setattr(app_analysis.analysis_loading_module, "target_is_library", lambda *args, **kwargs: True)
    monkeypatch.setattr(
        app_analysis.analysis_loading_module,
        "_iter_workspace_reverse_library_consumer_dependency_files",
        lambda _cfg: iter(
            [
                ("Selected", program_dir / "selected.l"),
                ("NoIterPath", None),
                ("Remote", other_dir / "Remote.z"),
                ("Ignore", other_dir / "Ignore.z"),
                ("CandidateA", program_dir / "CandidateA.z"),
            ]
        ),
    )

    app_analysis.analysis_loading_module._include_reverse_library_consumers(
        cfg,
        selected_target="Selected",
        root_bp=cast(Any, "bp"),
        graph=cast(Any, "graph"),
        loader=loader,
        require_analyzed_targets_fn=lambda _cfg: ["Selected", "CandidateA", "NoDeps", "NoPath", "DupLocal"],
        engine_module=SimpleNamespace(is_within_directory=lambda *_args: False),
    )

    assert visits == [
        ("CandidateA", program_dir),
        ("DupLocal", program_dir),
        ("Remote", other_dir),
    ]


def test_analysis_loading_cache_manifest_files_adds_companions_and_dependency_manifests():
    cfg = {"program_dir": "programs", "mode": "draft"}
    target_a = SimpleNamespace(header=SimpleNamespace(name="TargetA"), origin_file="TargetA.s")
    target_b = SimpleNamespace(header=SimpleNamespace(name="TargetB"), origin_file="TargetB.s")
    graph = SimpleNamespace(
        source_files={Path("programs/TargetA.s")},
        ast_by_name={"TargetA": target_a, "TargetB": target_b},
    )

    manifest_files = app_analysis.analysis_loading_module.cache_manifest_files(
        cfg,
        graph,
        find_dependency_path_fn=lambda target_name, requester_dir: (
            None if requester_dir is None else requester_dir / f"{target_name}.z"
        ),
        resolve_graphics_companion_path_fn=lambda source_path, **_kwargs: source_path.with_suffix(".g"),
        casefold_equal_fn=lambda left, right: left.casefold() == right.casefold(),
        casefold_key_fn=lambda value: value.casefold(),
    )

    assert manifest_files == {
        Path("programs/TargetA.s"),
        Path("programs/TargetA.g"),
        Path("programs/TargetA.z"),
        Path("programs/TargetB.z"),
    }
