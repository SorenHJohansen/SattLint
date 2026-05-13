# ruff: noqa: F403, F405
from ._app_analysis_test_support import *


def test_advanced_datatype_analysis_choices(noop_screen, monkeypatch, real_context):
    if real_context:
        cfg = real_context["cfg"].copy()

        monkeypatch.setattr(
            builtins,
            "input",
            make_input(["1", real_context["var_name"]]),
        )
        app_analysis.run_advanced_datatype_analysis(cfg)

        monkeypatch.setattr(
            builtins,
            "input",
            make_input(["2", real_context["module_name"]]),
        )
        app_analysis.run_advanced_datatype_analysis(cfg)

        monkeypatch.setattr(
            builtins,
            "input",
            make_input(["3", real_context["var_name"]]),
        )
        app_analysis.run_advanced_datatype_analysis(cfg)
        return

    monkeypatch.setattr(
        app_analysis,
        "_iter_loaded_projects",
        lambda *_args, **_kwargs: iter([("TargetA", "project", SimpleNamespace(unavailable_libraries=set()))]),
    )
    monkeypatch.setattr(variables_reporting_module, "analyze_datatype_usage", lambda *_, **__: "report")
    monkeypatch.setattr(variables_reporting_module, "debug_variable_usage", lambda *_, **__: "report")

    monkeypatch.setattr(builtins, "input", make_input(["1", "VarName"]))
    app_analysis.run_advanced_datatype_analysis(app.DEFAULT_CONFIG.copy())

    monkeypatch.setattr(builtins, "input", make_input(["2", "ModuleName"]))
    app_analysis.run_advanced_datatype_analysis(app.DEFAULT_CONFIG.copy())

    monkeypatch.setattr(builtins, "input", make_input(["3", "VarName"]))
    app_analysis.run_advanced_datatype_analysis(app.DEFAULT_CONFIG.copy())


def test_run_variable_analysis_runs_all_analyzed_targets(noop_screen, monkeypatch, capsys):
    monkeypatch.setattr(
        app_analysis,
        "_iter_loaded_projects",
        lambda *_args, **_kwargs: iter(
            [
                ("ProgramA", "bp-a", SimpleNamespace(unavailable_libraries=set())),
                ("LibB", "bp-b", SimpleNamespace(unavailable_libraries=set())),
            ]
        ),
    )
    monkeypatch.setattr(app_analysis, "analyze_variables", lambda *_, **__: make_variable_report("BasePicture"))
    monkeypatch.setattr(app_analysis, "analyze_shadowing", lambda *_, **__: make_shadowing_report("BasePicture"))

    app_analysis.run_variable_analysis(app.DEFAULT_CONFIG.copy(), None)

    out = capsys.readouterr().out
    assert "=== Target: ProgramA ===" in out
    assert "=== Target: LibB ===" in out
    assert "Target: ProgramA" in out
    assert "Target: LibB" in out
    assert "Target: BasePicture" not in out
    assert out.count("Issues: 0") == 2


def test_run_variable_analysis_all_analyses_executes_real_analyzers(noop_screen, monkeypatch, capsys):
    project_bp = parser_core_parse_source_text(VALID_SINGLE_FILE)
    graph = SimpleNamespace(
        unavailable_libraries=set(),
        warnings=[],
        source_files=set(),
    )
    monkeypatch.setattr(
        app_analysis,
        "_iter_loaded_projects",
        lambda *_args, **_kwargs: iter([("SmokeTarget", project_bp, graph)]),
    )

    app_analysis.run_variable_analysis(app.DEFAULT_CONFIG.copy(), None)

    out = capsys.readouterr().out
    assert "=== Target: SmokeTarget ===" in out
    assert "Issues:" in out
    assert "No variable analysis output was produced" not in out


def test_run_variable_analysis_all_reports_lists_empty_categories(noop_screen, monkeypatch, capsys):
    graph = SimpleNamespace(unavailable_libraries=set(), warnings=[])
    monkeypatch.setattr(
        app_analysis,
        "_iter_loaded_projects",
        lambda *_args, **_kwargs: iter([("ProgramA", "bp-a", graph)]),
    )
    monkeypatch.setattr(
        app_analysis,
        "analyze_variables",
        lambda *_, **__: VariablesReport(
            basepicture_name="ProgramA",
            issues=[],
            visible_kinds=frozenset(DEFAULT_VARIABLE_ANALYSIS_KINDS),
            include_empty_sections=True,
        ),
    )
    monkeypatch.setattr(
        app_analysis,
        "analyze_shadowing",
        lambda *_, **__: make_shadowing_report("ProgramA"),
    )

    app_analysis.run_variable_analysis(app.DEFAULT_CONFIG.copy(), None)

    out = capsys.readouterr().out
    assert "=== Target: ProgramA ===" in out
    assert "Issues: 0" in out
    assert "Sections:" in out
    assert "  - Unused variables: 0" in out
    assert "Min/Max mapping name mismatches" in out
    assert "Name collisions" in out
    assert "Reset contamination (missing reset writes)" in out
    assert "Implicit latching (missing matching False writes)" not in out
    assert "UI/display-only variables" not in out
    assert out.count("      none") >= 3


def test_run_variable_analysis_all_reports_hide_low_confidence_categories(noop_screen, monkeypatch, capsys):
    from sattline_parser.models.ast_model import Variable

    issue = VariableIssue(
        kind=app_analysis.IssueKind.UI_ONLY,
        module_path=["ProgramA"],
        variable=Variable(name="DisplayValue", datatype="integer"),
        role="localvariable",
    )
    graph = SimpleNamespace(unavailable_libraries=set(), warnings=[])
    monkeypatch.setattr(
        app_analysis,
        "_iter_loaded_projects",
        lambda *_args, **_kwargs: iter([("ProgramA", "bp-a", graph)]),
    )
    monkeypatch.setattr(
        app_analysis,
        "analyze_variables",
        lambda *_, **__: VariablesReport(
            basepicture_name="ProgramA",
            issues=[issue],
            visible_kinds=frozenset(ALL_VARIABLE_ANALYSIS_KINDS),
            include_empty_sections=True,
        ),
    )
    monkeypatch.setattr(
        app_analysis,
        "analyze_shadowing",
        lambda *_, **__: make_shadowing_report("ProgramA"),
    )

    app_analysis.run_variable_analysis(app.DEFAULT_CONFIG.copy(), None)

    out = capsys.readouterr().out
    assert "UI/display-only variables" not in out


def test_run_variable_analysis_can_render_low_confidence_category_on_request(noop_screen, monkeypatch, capsys):
    from sattline_parser.models.ast_model import Variable

    issue = VariableIssue(
        kind=app_analysis.IssueKind.UI_ONLY,
        module_path=["ProgramA"],
        variable=Variable(name="DisplayValue", datatype="integer"),
        role="localvariable",
    )
    graph = SimpleNamespace(unavailable_libraries=set(), warnings=[])
    monkeypatch.setattr(
        app_analysis,
        "_iter_loaded_projects",
        lambda *_args, **_kwargs: iter([("ProgramA", "bp-a", graph)]),
    )
    monkeypatch.setattr(
        app_analysis,
        "analyze_variables",
        lambda *_, **__: VariablesReport(
            basepicture_name="ProgramA",
            issues=[issue],
            visible_kinds=frozenset(ALL_VARIABLE_ANALYSIS_KINDS),
            include_empty_sections=True,
        ),
    )
    monkeypatch.setattr(
        app_analysis,
        "analyze_shadowing",
        lambda *_, **__: make_shadowing_report("ProgramA"),
    )

    app_analysis.run_variable_analysis(app.DEFAULT_CONFIG.copy(), {app_analysis.IssueKind.UI_ONLY})

    out = capsys.readouterr().out
    assert "UI/display-only variables" in out


def test_iter_loaded_projects_skips_failed_targets(noop_screen, monkeypatch, capsys):
    cfg = deepcopy(app.DEFAULT_CONFIG)
    cfg["analyzed_programs_and_libraries"] = ["Broken", "Working"]
    working_graph = SimpleNamespace(unavailable_libraries=set())

    def fake_load_project(_cfg, target_name=None, *, use_cache=True):
        if target_name == "Broken":
            raise app.TargetLoadError(
                "Broken",
                resolved=["dep_a", "dep_b"],
                missing=[
                    "Broken parse/transform error: root failed",
                    "dep_c parse/transform error: something bad happened",
                    "transitive_lib parse/transform error: nested failure",
                    "Missing code file for 'dep_d' (draft)",
                ],
                warnings=[
                    "dep_c: validation warning one",
                    "transitive_lib: validation warning two",
                ],
                direct_dependencies=["dep_c", "dep_d"],
            )
        return "bp-working", working_graph

    monkeypatch.setattr(app_analysis, "load_project", fake_load_project)

    projects = list(app_analysis._iter_loaded_projects(cfg))

    out = capsys.readouterr().out
    assert projects == [("Working", "bp-working", working_graph)]
    assert "=== Target: Broken ===" in out
    assert "Failed to load target:" in out
    assert "Target 'Broken' was not parsed." in out
    assert "Direct dependencies from the target file (2):" in out
    assert "Resolved targets (2):" in out
    assert "  - dep_a" in out
    assert "Root target validation errors (1):" in out
    assert "Failed direct dependencies (2):" in out
    assert "  - dep_c: something bad happened" in out
    assert "Direct dependency warnings (1):" in out
    assert "Transitive dependency failures (1):" in out
    assert "Transitive dependency warnings (1):" in out


def test_run_variable_analysis_reports_when_no_targets_load(noop_screen, monkeypatch, capsys):
    monkeypatch.setattr(app_analysis, "_iter_loaded_projects", lambda *_args, **_kwargs: iter(()))

    app_analysis.run_variable_analysis(app.DEFAULT_CONFIG.copy(), None)

    out = capsys.readouterr().out
    assert "No variable analysis output was produced because no target loaded successfully." in out


def test_run_variable_analysis_prints_validation_warnings(noop_screen, monkeypatch, capsys):
    graph = SimpleNamespace(
        unavailable_libraries=set(),
        warnings=["ProgramA: warning one", "dep_b: warning two"],
    )
    monkeypatch.setattr(
        app_analysis,
        "_iter_loaded_projects",
        lambda *_args, **_kwargs: iter([("ProgramA", "bp", graph)]),
    )
    monkeypatch.setattr(app_analysis, "analyze_variables", lambda *_, **__: make_variable_report())
    monkeypatch.setattr(app_analysis, "analyze_shadowing", lambda *_, **__: make_shadowing_report())

    app_analysis.run_variable_analysis(app.DEFAULT_CONFIG.copy(), None)

    out = capsys.readouterr().out
    assert "Validation warnings (1):" in out
    assert "  - ProgramA: warning one" in out
    assert "dep_b: warning two" not in out
    assert "Issues: 0" in out


def test_run_variable_analysis_hides_dependency_validation_warnings(noop_screen, monkeypatch, capsys):
    graph = SimpleNamespace(
        unavailable_libraries=set(),
        warnings=["dep_a: warning one", "dep_b: warning two"],
    )
    monkeypatch.setattr(
        app_analysis,
        "_iter_loaded_projects",
        lambda *_args, **_kwargs: iter([("ProgramA", "bp", graph)]),
    )
    monkeypatch.setattr(app_analysis, "analyze_variables", lambda *_, **__: make_variable_report())
    monkeypatch.setattr(app_analysis, "analyze_shadowing", lambda *_, **__: make_shadowing_report())

    app_analysis.run_variable_analysis(app.DEFAULT_CONFIG.copy(), None)

    out = capsys.readouterr().out
    assert "Validation warnings (" not in out
    assert "dep_a: warning one" not in out
    assert "Issues: 0" in out


def test_run_variable_analysis_hides_expected_unavailable_dependency_warnings(noop_screen, monkeypatch, capsys):
    graph = SimpleNamespace(
        unavailable_libraries={"controllib"},
        warnings=["KaHAMPCSøjleLib: dependency 'controllib' unavailable: expected proprietary dependency"],
    )
    monkeypatch.setattr(
        app_analysis,
        "_iter_loaded_projects",
        lambda *_args, **_kwargs: iter([("KaHAMPCSøjleLib", "bp", graph)]),
    )
    monkeypatch.setattr(app_analysis, "analyze_variables", lambda *_, **__: make_variable_report())
    monkeypatch.setattr(app_analysis, "analyze_shadowing", lambda *_, **__: make_shadowing_report())

    app_analysis.run_variable_analysis(app.DEFAULT_CONFIG.copy(), None)

    out = capsys.readouterr().out
    assert "Validation warnings (" not in out
    assert "expected proprietary dependency" not in out
    assert "Issues: 0" in out


def test_run_variable_analysis_marks_library_targets(noop_screen, monkeypatch):
    graph = SimpleNamespace(
        unavailable_libraries=set(),
        warnings=[],
        source_files={
            Path("ProjectLib/LibraryTarget.x"),
        },
    )
    project_bp = SimpleNamespace(
        header=SimpleNamespace(name="LibraryTarget"),
        origin_file="LibraryTarget.x",
    )
    monkeypatch.setattr(
        app_analysis,
        "_iter_loaded_projects",
        lambda *_args, **_kwargs: iter([("LibraryTarget", project_bp, graph)]),
    )

    captured: dict[str, object] = {}

    def _fake_analyze_variables(*_args, **kwargs):
        captured.update(kwargs)
        return make_variable_report()

    monkeypatch.setattr(app_analysis, "analyze_variables", _fake_analyze_variables)
    monkeypatch.setattr(app_analysis, "analyze_shadowing", lambda *_, **__: make_shadowing_report())

    cfg = app.DEFAULT_CONFIG.copy()
    cfg["program_dir"] = "programs"

    app_analysis.run_variable_analysis(cfg, None)

    assert captured["analyzed_target_is_library"] is True


def test_print_validation_warnings_truncates(monkeypatch):
    lines: list[str] = []
    monkeypatch.setattr(app_analysis, "emit_output", lambda message: lines.append(message))

    app_analysis._print_validation_warnings(["warn1", "warn2", "warn3"], limit=2)

    assert lines == [
        "Validation warnings (3):",
        "  - warn1",
        "  - warn2",
        "  - ... (+1 more)",
    ]


def test_cache_key_for_target_adds_analysis_target(monkeypatch):
    captured: dict[str, object] = {}
    monkeypatch.setattr(
        app_analysis,
        "compute_cache_key",
        lambda cfg: captured.update({"cfg": cfg.copy()}) or "cache-key",
    )

    cfg = {"mode": "official"}
    result = app_analysis._cache_key_for_target(cfg, "TargetA")

    assert result == "cache-key"
    assert cfg == {"mode": "official"}
    assert captured["cfg"] == {"mode": "official", "analysis_target": "TargetA"}


def test_source_paths_for_current_target_falls_back_to_header_name():
    project_bp = SimpleNamespace(header=SimpleNamespace(name="TargetA"), origin_file=None)
    graph = SimpleNamespace(source_files={Path("libs/Other.s"), Path("programs/TargetA.s")})

    result = app_analysis.source_paths_for_current_target(cast(Any, project_bp), cast(Any, graph))

    assert result == {Path("programs/TargetA.s")}


def test_target_is_library_returns_false_without_matching_source_paths():
    cfg = {"program_dir": "programs"}
    project_bp = SimpleNamespace(header=SimpleNamespace(name="TargetA"), origin_file="Missing.s")
    graph = SimpleNamespace(source_files=set())

    assert app_analysis._target_is_library(cfg, cast(Any, project_bp), cast(Any, graph)) is False


def test_run_datatype_usage_analysis_rejects_empty_input(monkeypatch):
    monkeypatch.setattr(builtins, "input", lambda _prompt="": "   ")
    pauses: list[str] = []
    lines: list[str] = []
    monkeypatch.setattr(app_analysis, "emit_output", lambda message: lines.append(message))
    monkeypatch.setattr(
        app_analysis, "_iter_loaded_projects", lambda *_args, **_kwargs: pytest.fail("should not load projects")
    )

    app_analysis.run_datatype_usage_analysis(app.DEFAULT_CONFIG.copy(), pause_fn=lambda: pauses.append("pause"))

    assert "No variable name provided" in "\n".join(lines)
    assert pauses == ["pause"]


def test_run_datatype_usage_analysis_reports_errors_and_pauses(monkeypatch):
    monkeypatch.setattr(builtins, "input", lambda _prompt="": "FlowVar")
    pauses: list[str] = []
    lines: list[str] = []
    monkeypatch.setattr(app_analysis, "emit_output", lambda message: lines.append(message))
    monkeypatch.setattr(
        app_analysis,
        "_iter_loaded_projects",
        lambda *_args, **_kwargs: iter([("TargetA", "bp-a", SimpleNamespace(unavailable_libraries={"ControlLib"}))]),
    )
    monkeypatch.setattr(
        variables_reporting_module,
        "analyze_datatype_usage",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    app_analysis.run_datatype_usage_analysis(app.DEFAULT_CONFIG.copy(), pause_fn=lambda: pauses.append("pause"))

    assert any("Error during analysis for TargetA: boom" in line for line in lines)
    assert pauses == ["pause"]


def test_parse_index_selection_supports_ranges_and_filters_invalid_tokens():
    assert app_analysis.parse_index_selection("1, 3-5, 8-6, bad, 11", 8) == [1, 3, 4, 5, 6, 7, 8]
