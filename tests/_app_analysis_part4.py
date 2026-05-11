# ruff: noqa: F403, F405
from ._app_analysis_test_support import *


def test_load_project_saves_cache_after_successful_merge(monkeypatch):
    saved: dict[str, object] = {}

    class FakeCache:
        def __init__(self, cache_dir):
            self.cache_dir = cache_dir

        def load(self, key):
            assert key == "cache-key"
            return None

        def save(self, key, **kwargs):
            saved.update({"key": key, **kwargs})

    class FakeLoader:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def resolve(self, target_name, strict=False):
            return SimpleNamespace(
                ast_by_name={target_name: "root-bp"},
                missing=[],
                warnings=[],
                source_files={Path("programs/TargetA.s")},
            )

        def _find_deps_with_context(self, target_name, requester_dir):
            return None

    monkeypatch.setattr(app_analysis, "ASTCache", FakeCache)
    monkeypatch.setattr(app_analysis, "get_cache_dir", lambda: Path("cache-dir"))
    monkeypatch.setattr(app_analysis.engine_module, "SattLineProjectLoader", FakeLoader)
    monkeypatch.setattr(app_analysis.engine_module, "merge_project_basepicture", lambda bp, graph: "merged")

    result = app_analysis.load_project(
        {
            "program_dir": "programs",
            "other_lib_dirs": [],
            "ABB_lib_dir": "abb",
            "mode": "draft",
            "scan_root_only": True,
            "debug": False,
            "analyzed_programs_and_libraries": ["TargetA"],
        },
        cache_key_for_target_fn=lambda _cfg, _target: "cache-key",
    )

    assert result == (
        "merged",
        SimpleNamespace(
            ast_by_name={"TargetA": "root-bp"},
            missing=[],
            warnings=[],
            source_files={Path("programs/TargetA.s")},
        ),
    )
    assert saved["key"] == "cache-key"
    assert saved["project"] == result
    assert saved["files"] == {Path("programs/TargetA.s")}


def test_load_project_raises_default_error_when_target_missing(monkeypatch):
    class FakeCache:
        def __init__(self, cache_dir):
            self.cache_dir = cache_dir

        def load(self, key):
            return None

    class FakeLoader:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def resolve(self, target_name, strict=False):
            return SimpleNamespace(ast_by_name={}, missing=[], warnings=[], source_files=set())

        def _find_deps_with_context(self, target_name, requester_dir):
            return None

    monkeypatch.setattr(app_analysis, "ASTCache", FakeCache)
    monkeypatch.setattr(app_analysis, "get_cache_dir", lambda: Path("cache-dir"))
    monkeypatch.setattr(app_analysis.engine_module, "SattLineProjectLoader", FakeLoader)

    with pytest.raises(RuntimeError, match="Target 'TargetA' was not parsed"):
        app_analysis.load_project(
            {
                "program_dir": "programs",
                "other_lib_dirs": [],
                "ABB_lib_dir": "abb",
                "mode": "draft",
                "scan_root_only": True,
                "debug": False,
                "analyzed_programs_and_libraries": ["TargetA"],
            },
            cache_key_for_target_fn=lambda _cfg, _target: "cache-key",
        )


def test_load_program_ast_force_dependency_resolution_returns_loaded_program(monkeypatch):
    class FakeLoader:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def resolve(self, program_name, strict=False):
            return SimpleNamespace(ast_by_name={program_name: "bp-main"})

    monkeypatch.setattr(app_analysis.engine_module, "SattLineProjectLoader", FakeLoader)

    result = app_analysis.load_program_ast(
        {
            "program_dir": "programs",
            "other_lib_dirs": [],
            "ABB_lib_dir": "abb",
            "mode": "draft",
            "scan_root_only": True,
            "debug": False,
        },
        "TargetA",
        force_dependency_resolution=True,
    )

    assert result == ("bp-main", SimpleNamespace(ast_by_name={"TargetA": "bp-main"}))


def test_force_refresh_ast_returns_none_without_targets():
    assert app_analysis.force_refresh_ast({}, get_analyzed_targets_fn=lambda _cfg: []) is None


def test_ensure_ast_cache_returns_true_without_targets():
    assert app_analysis.ensure_ast_cache({}, get_analyzed_targets_fn=lambda _cfg: []) is True


def test_run_variable_analysis_shadowing_only_uses_shadowing_report_and_pauses(monkeypatch, capsys):
    monkeypatch.setattr(
        app_analysis,
        "_iter_loaded_projects",
        lambda *_args, **_kwargs: iter([("ProgramA", "bp", SimpleNamespace(unavailable_libraries=set(), warnings=[]))]),
    )
    monkeypatch.setattr(app_analysis, "analyze_variables", lambda *_, **__: make_variable_report())
    monkeypatch.setattr(app_analysis, "analyze_shadowing", lambda *_, **__: make_shadowing_report("ShadowOnly"))

    pauses: list[str] = []
    app_analysis.run_variable_analysis(
        app.DEFAULT_CONFIG.copy(),
        {IssueKind.SHADOWING},
        pause_fn=lambda: pauses.append("pause"),
    )

    out = capsys.readouterr().out
    assert "=== Target: ProgramA ===" in out
    assert pauses == ["pause"]


def test_run_datatype_usage_analysis_reports_success_error_and_pause(monkeypatch):
    lines: list[str] = []
    pauses: list[str] = []

    monkeypatch.setattr(app_analysis, "emit_output", lambda message: lines.append(message))
    monkeypatch.setattr(builtins, "input", make_input(["FlowVar"]))

    def fake_analyze(project_bp, var_name, debug=False, unavailable_libraries=None):
        if project_bp == "bp-b":
            raise RuntimeError("boom")
        return f"datatype:{project_bp}:{var_name}"

    monkeypatch.setattr(variables_reporting_module, "analyze_datatype_usage", fake_analyze)

    app_analysis.run_datatype_usage_analysis(
        app.DEFAULT_CONFIG.copy(),
        iter_loaded_projects_fn=cast(
            Any,
            lambda *_args, **_kwargs: iter(
                [
                    ("TargetA", "bp-a", SimpleNamespace(unavailable_libraries=set())),
                    ("TargetB", "bp-b", SimpleNamespace(unavailable_libraries=set())),
                ]
            ),
        ),
        pause_fn=lambda: pauses.append("pause"),
    )

    assert any("datatype:bp-a:FlowVar" in line for line in lines)
    assert any("Error during analysis for TargetB: boom" in line for line in lines)
    assert pauses == ["pause"]


def test_app_analysis_menus_quit_branch_calls_quit_app(monkeypatch):
    class QuitRequestedError(Exception):
        pass

    def quit_app():
        raise QuitRequestedError()

    menu_calls = [
        lambda: app_analysis.variable_usage_submenu(
            app.DEFAULT_CONFIG.copy(),
            clear_screen_fn=lambda: None,
            quit_app_fn=quit_app,
            run_variable_analysis_fn=lambda *_args, **_kwargs: None,
            run_datatype_usage_analysis_fn=lambda _cfg: None,
            run_debug_variable_usage_fn=lambda _cfg: None,
            run_module_localvar_analysis_fn=lambda _cfg: None,
            pause_fn=lambda: None,
        ),
        lambda: app_analysis.module_analysis_submenu(
            app.DEFAULT_CONFIG.copy(),
            clear_screen_fn=lambda: None,
            print_menu_fn=lambda *_args, **_kwargs: None,
            menu_option_factory=lambda key, label, detail: (key, label, detail),
            quit_app_fn=quit_app,
            run_module_duplicates_analysis_fn=lambda _cfg: None,
            run_module_find_by_name_fn=lambda _cfg: None,
            run_module_tree_debug_fn=lambda _cfg: None,
            run_graphics_rules_validation_fn=lambda _cfg: None,
            pause_fn=lambda: None,
        ),
        lambda: app_analysis.interface_communication_submenu(
            app.DEFAULT_CONFIG.copy(),
            clear_screen_fn=lambda: None,
            print_menu_fn=lambda *_args, **_kwargs: None,
            menu_option_factory=lambda key, label, detail: (key, label, detail),
            quit_app_fn=quit_app,
            run_mms_interface_analysis_fn=lambda _cfg: None,
            run_icf_validation_fn=lambda _cfg: None,
            run_icf_formatter_fn=lambda _cfg: None,
            pause_fn=lambda: None,
        ),
        lambda: app_analysis.code_quality_submenu(
            app.DEFAULT_CONFIG.copy(),
            clear_screen_fn=lambda: None,
            print_menu_fn=lambda *_args, **_kwargs: None,
            menu_option_factory=lambda key, label, detail: (key, label, detail),
            quit_app_fn=quit_app,
            run_comment_code_analysis_fn=lambda _cfg: None,
            pause_fn=lambda: None,
        ),
        lambda: app_analysis.analyzer_catalog_menu(
            app.DEFAULT_CONFIG.copy(),
            clear_screen_fn=lambda: None,
            print_menu_fn=lambda *_args, **_kwargs: None,
            menu_option_factory=lambda key, label, detail: (key, label, detail),
            quit_app_fn=quit_app,
            get_enabled_analyzers_fn=lambda: [SimpleNamespace(key="variables", name="Variables", description="desc")],
            run_checks_fn=lambda _cfg, _selected: None,
            pause_fn=lambda: None,
        ),
        lambda: app_analysis.advanced_analysis_menu(
            app.DEFAULT_CONFIG.copy(),
            clear_screen_fn=lambda: None,
            print_menu_fn=lambda *_args, **_kwargs: None,
            menu_option_factory=lambda key, label, detail: (key, label, detail),
            quit_app_fn=quit_app,
            run_datatype_usage_analysis_fn=lambda _cfg: None,
            run_debug_variable_usage_fn=lambda _cfg: None,
            run_module_localvar_analysis_fn=lambda _cfg: None,
            pause_fn=lambda: None,
        ),
        lambda: app_analysis.analysis_menu(
            app.DEFAULT_CONFIG.copy(),
            clear_screen_fn=lambda: None,
            print_menu_fn=lambda *_args, **_kwargs: None,
            menu_option_factory=lambda key, label, detail: (key, label, detail),
            quit_app_fn=quit_app,
            run_checks_fn=lambda _cfg, _selected: None,
            variable_usage_submenu_fn=lambda _cfg: None,
            module_analysis_submenu_fn=lambda _cfg: None,
            interface_communication_submenu_fn=lambda _cfg: None,
            code_quality_submenu_fn=lambda _cfg: None,
            analyzer_catalog_menu_fn=lambda _cfg: None,
            advanced_analysis_menu_fn=lambda _cfg: None,
            summarize_targets_fn=lambda _cfg: "TargetA",
            pause_fn=lambda: None,
        ),
    ]

    monkeypatch.setattr(builtins, "input", lambda _prompt="": "q")

    for run_menu in menu_calls:
        with pytest.raises(QuitRequestedError):
            run_menu()


def test_parse_index_selection_ignores_malformed_range_tokens():
    assert app_analysis.parse_index_selection("1-a, 2", 4) == [2]


def test_run_module_duplicates_analysis_handles_missing_matches_default_compare_and_errors(monkeypatch):
    lines: list[str] = []
    pauses: list[str] = []
    matches = [(["Root", "Area", "PumpA"], SimpleNamespace(datecode=101))]

    monkeypatch.setattr(builtins, "input", make_input(["Missing, Pump, Boom", ""]))
    monkeypatch.setattr(app_analysis, "emit_output", lambda message: lines.append(message))

    def fake_find_modules(_project_bp, module_name, debug=False):
        if module_name == "Missing":
            return []
        if module_name == "Pump":
            return matches
        raise RuntimeError("boom")

    monkeypatch.setattr(app_analysis, "find_modules_by_name", fake_find_modules)
    monkeypatch.setattr(
        app_analysis,
        "analyze_module_duplicates",
        lambda *_args, **_kwargs: SimpleNamespace(summary=lambda: "default comparison summary"),
    )

    app_analysis.run_module_duplicates_analysis(
        app.DEFAULT_CONFIG.copy(),
        iter_loaded_projects_fn=cast(Any, lambda *_args, **_kwargs: iter([("TargetA", "bp", SimpleNamespace())])),
        pause_fn=lambda: pauses.append("pause"),
    )

    assert any("No modules found with name 'Missing'." in line for line in lines)
    assert any("default comparison summary" in line for line in lines)
    assert any("Error during analysis for 'Boom': boom" in line for line in lines)
    assert pauses == ["pause"]


def test_run_module_find_by_name_rejects_empty_name(monkeypatch):
    lines: list[str] = []
    pauses: list[str] = []

    monkeypatch.setattr(builtins, "input", lambda _prompt="": "   ")
    monkeypatch.setattr(app_analysis, "emit_output", lambda message: lines.append(message))

    app_analysis.run_module_find_by_name(
        app.DEFAULT_CONFIG.copy(),
        iter_loaded_projects_fn=lambda *_args, **_kwargs: pytest.fail("should not load projects"),
        pause_fn=lambda: pauses.append("pause"),
    )

    assert any("No module name provided" in line for line in lines)
    assert pauses == ["pause"]


def test_run_module_tree_debug_reports_errors_and_pauses(monkeypatch):
    lines: list[str] = []
    pauses: list[str] = []

    monkeypatch.setattr(app_analysis, "emit_output", lambda message: lines.append(message))
    monkeypatch.setattr(
        app_analysis, "debug_module_structure", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("boom"))
    )

    app_analysis.run_module_tree_debug(
        app.DEFAULT_CONFIG.copy(),
        prompt_fn=lambda _message, _default: "7",
        iter_loaded_projects_fn=cast(Any, lambda *_args, **_kwargs: iter([("TargetA", "bp", SimpleNamespace())])),
        pause_fn=lambda: pauses.append("pause"),
    )

    assert any("Error during debug: boom" in line for line in lines)
    assert pauses == ["pause"]


def test_run_module_localvar_analysis_reports_errors_and_pauses(monkeypatch):
    lines: list[str] = []
    pauses: list[str] = []

    monkeypatch.setattr(app_analysis, "emit_output", lambda message: lines.append(message))
    monkeypatch.setattr(builtins, "input", make_input(["UnitA", "Dv"]))

    reporting_module = pytest.importorskip("sattlint.analyzers.variable_usage_reporting")

    def fake_analyze_module_localvar_fields(project_bp, module_path, var_name, debug=False):
        if project_bp == "bp-b":
            raise RuntimeError("boom")
        return "field report"

    monkeypatch.setattr(reporting_module, "analyze_module_localvar_fields", fake_analyze_module_localvar_fields)

    app_analysis.run_module_localvar_analysis(
        app.DEFAULT_CONFIG.copy(),
        load_project_fn=cast(
            Any, lambda _cfg: (SimpleNamespace(header=SimpleNamespace(name="BasePicture")), SimpleNamespace())
        ),
        iter_loaded_projects_fn=cast(
            Any,
            lambda *_args, **_kwargs: iter(
                [
                    ("TargetA", "bp-a", SimpleNamespace()),
                    ("TargetB", "bp-b", SimpleNamespace()),
                ]
            ),
        ),
        pause_fn=lambda: pauses.append("pause"),
    )

    assert any("field report" in line for line in lines)
    assert any("Error during analysis for TargetB: boom" in line for line in lines)
    assert pauses == ["pause"]


def test_run_checks_success_path_pauses(monkeypatch):
    lines: list[str] = []
    pauses: list[str] = []

    monkeypatch.setattr(app_analysis, "emit_output", lambda message: lines.append(message))

    app_analysis.run_checks(
        app.DEFAULT_CONFIG.copy(),
        ["state_inference"],
        iter_loaded_projects_fn=cast(
            Any,
            lambda *_args, **_kwargs: iter(
                [
                    (
                        "TargetA",
                        SimpleNamespace(header=SimpleNamespace(name="TargetA")),
                        SimpleNamespace(unavailable_libraries=set()),
                    )
                ]
            ),
        ),
        get_enabled_analyzers_fn=lambda: [
            SimpleNamespace(
                key="state_inference",
                name="State inference",
                run=lambda _context: SimpleNamespace(summary=lambda: "state inference summary"),
            )
        ],
        target_is_library_fn=lambda *_args, **_kwargs: False,
        pause_fn=lambda: pauses.append("pause"),
    )

    assert any("state inference summary" in line for line in lines)
    assert pauses == ["pause"]


def test_run_icf_validation_builds_moduletype_index(monkeypatch, tmp_path):
    lines: list[str] = []
    pauses: list[str] = []
    captured: dict[str, object] = {}
    icf_dir = tmp_path / "icf"
    icf_dir.mkdir()
    valid_file = icf_dir / "Valid.icf"
    valid_file.write_text("dummy", encoding="utf-8")

    monkeypatch.setattr(app_analysis, "emit_output", lambda message: lines.append(message))
    monkeypatch.setattr(app_analysis, "parse_icf_file", lambda _path: [SimpleNamespace()])
    monkeypatch.setattr(app_analysis.engine_module, "merge_project_basepicture", lambda bp, _graph: bp)

    graph = SimpleNamespace(
        ast_by_name={
            "Valid": SimpleNamespace(
                moduletype_defs=[SimpleNamespace(name="PumpType"), SimpleNamespace(name="ValveType")]
            )
        }
    )

    def fake_validate(program_bp, entries, expected_program, debug=False, moduletype_index=None):
        captured["moduletype_index"] = moduletype_index
        return SimpleNamespace(
            total_entries=1,
            valid_entries=1,
            issues=[],
            skipped_entries=0,
            summary=lambda: "icf report",
        )

    app_analysis.run_icf_validation(
        app.DEFAULT_CONFIG.copy(),
        configured_icf_files_fn=lambda _cfg: (icf_dir, [valid_file]),
        load_program_ast_fn=cast(Any, lambda _cfg, _program_name: ("bp-valid", graph)),
        validate_icf_entries_against_program_fn=fake_validate,
        pause_fn=lambda: pauses.append("pause"),
    )

    moduletype_index = cast(dict[str, list[object]], captured["moduletype_index"])
    assert list(moduletype_index) == ["pumptype", "valvetype"]
    assert any("icf report" in line for line in lines)
    assert pauses == ["pause"]


def test_run_debug_variable_usage_reports_errors_and_pauses(monkeypatch):
    lines: list[str] = []
    pauses: list[str] = []

    monkeypatch.setattr(app_analysis, "emit_output", lambda message: lines.append(message))
    monkeypatch.setattr(builtins, "input", make_input(["FlowVar"]))
    monkeypatch.setattr(
        app_analysis,
        "debug_variable_usage",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    app_analysis.run_debug_variable_usage(
        app.DEFAULT_CONFIG.copy(),
        iter_loaded_projects_fn=cast(Any, lambda *_args, **_kwargs: iter([("TargetA", "bp-a", SimpleNamespace())])),
        pause_fn=lambda: pauses.append("pause"),
    )

    assert any("Error during debug for TargetA: boom" in line for line in lines)
    assert pauses == ["pause"]
