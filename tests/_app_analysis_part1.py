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


@pytest.mark.parametrize(
    ("kinds", "expect_reverse_consumers"),
    [
        ({app_analysis.IssueKind.UNUSED}, False),
        ({app_analysis.IssueKind.UNUSED_DATATYPE_FIELD}, True),
    ],
)
def test_run_variable_analysis_scopes_reverse_consumer_loading(
    noop_screen,
    capsys,
    kinds,
    expect_reverse_consumers,
):
    seen_flags: list[bool] = []

    def _fake_iter_loaded_projects(cfg, **_kwargs):
        seen_flags.append(bool(cfg["include_reverse_library_consumers"]))
        return iter(())

    app_analysis.run_variable_analysis(
        app.DEFAULT_CONFIG.copy(),
        kinds,
        iter_loaded_projects_fn=_fake_iter_loaded_projects,
    )

    assert seen_flags == [expect_reverse_consumers]
    assert "No variable analysis output was produced because no target loaded successfully." in capsys.readouterr().out


def test_run_variable_analysis_updates_live_status(monkeypatch):
    updates: list[str] = []

    class FakeLiveStatusLine:
        def __enter__(self):
            return updates.append

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(
        app_analysis,
        "_iter_loaded_projects",
        lambda *_args, **_kwargs: iter(
            [("TargetA", "bp-a", SimpleNamespace(unavailable_libraries=set(), warnings=[]))]
        ),
    )

    def _fake_analyze_variables(*_args, **kwargs):
        status_update_fn = kwargs.get("status_update_fn")
        if callable(status_update_fn):
            status_update_fn("Analyzing variable issues for TargetA: walking module path TargetA > StopOprLogic")
        return make_variable_report("BasePicture")

    monkeypatch.setattr(app_analysis, "analyze_variables", _fake_analyze_variables)
    monkeypatch.setattr(app_analysis.console_module, "live_status_line", lambda: FakeLiveStatusLine())

    app_analysis.run_variable_analysis(
        app.DEFAULT_CONFIG.copy(),
        {app_analysis.IssueKind.RECORD_COMPONENT_ORDER_DEPENDENCE},
    )

    assert updates == [
        "Analyzing variable issues for TargetA",
        "Analyzing variable issues for TargetA: walking module path TargetA > StopOprLogic",
    ]


def test_run_variable_analysis_real_analyzer_keeps_default_status_updates_coarse(monkeypatch):
    updates: list[str] = []

    class FakeLiveStatusLine:
        def __enter__(self):
            return updates.append

        def __exit__(self, exc_type, exc, tb):
            return False

    project_bp = parser_core_parse_source_text(VALID_SINGLE_FILE)
    graph = SimpleNamespace(unavailable_libraries=set(), warnings=[], source_files=set())

    monkeypatch.setattr(
        app_analysis,
        "_iter_loaded_projects",
        lambda *_args, **_kwargs: iter([("SmokeTarget", project_bp, graph)]),
    )
    monkeypatch.setattr(app_analysis.console_module, "live_status_line", lambda: FakeLiveStatusLine())

    app_analysis.run_variable_analysis(
        app.DEFAULT_CONFIG.copy(),
        {app_analysis.IssueKind.UNUSED},
    )

    assert updates[0] == "Analyzing variable issues for SmokeTarget"
    assert any("building root scope" in update for update in updates)
    assert any("finalizing findings" in update for update in updates)
    assert not any("walking module path" in update for update in updates)


def test_run_variable_analysis_includes_version_and_last_changed(noop_screen, monkeypatch, capsys, tmp_path):
    from datetime import datetime

    source_path = tmp_path / "ProgramA.s"
    source_path.write_text("BasePicture placeholder\n", encoding="utf-8")
    timestamp = datetime(2024, 5, 17, 12, 0, 0).timestamp()
    os.utime(source_path, (timestamp, timestamp))
    graph = SimpleNamespace(
        unavailable_libraries=set(),
        warnings=[],
        source_files={source_path},
    )
    project_bp = SimpleNamespace(
        header=SimpleNamespace(name="ProgramA"),
        origin_file="ProgramA.s",
    )
    monkeypatch.setattr(
        app_analysis,
        "_iter_loaded_projects",
        lambda *_args, **_kwargs: iter([("ProgramA", project_bp, graph)]),
    )
    monkeypatch.setattr(app_analysis, "analyze_variables", lambda *_, **__: make_variable_report("BasePicture"))
    monkeypatch.setattr(app_analysis, "analyze_shadowing", lambda *_, **__: make_shadowing_report("BasePicture"))

    app_analysis.run_variable_analysis(app.DEFAULT_CONFIG.copy(), None)

    out = capsys.readouterr().out
    assert "Version: draft" in out
    assert "Last changed: 2024-05-17" in out


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


def test_run_variable_analysis_passes_selected_issue_kinds_to_analyzer(noop_screen, monkeypatch, capsys):
    graph = SimpleNamespace(unavailable_libraries=set(), warnings=[])
    seen_selected_kinds: list[set[IssueKind] | frozenset[IssueKind] | None] = []

    monkeypatch.setattr(
        app_analysis,
        "_iter_loaded_projects",
        lambda *_args, **_kwargs: iter([("ProgramA", "bp-a", graph)]),
    )

    def _fake_analyze_variables(*_args, **kwargs):
        seen_selected_kinds.append(kwargs.get("selected_issue_kinds"))
        return VariablesReport(
            basepicture_name="ProgramA",
            issues=[],
            visible_kinds=frozenset({IssueKind.UNUSED}),
            include_empty_sections=True,
        )

    monkeypatch.setattr(app_analysis, "analyze_variables", _fake_analyze_variables)
    monkeypatch.setattr(app_analysis, "analyze_shadowing", lambda *_, **__: make_shadowing_report("ProgramA"))

    app_analysis.run_variable_analysis(app.DEFAULT_CONFIG.copy(), {IssueKind.UNUSED})

    assert seen_selected_kinds == [{IssueKind.UNUSED}]
    assert "=== Target: ProgramA ===" in capsys.readouterr().out


def test_run_variable_analysis_uses_cached_report_for_selected_issue_kinds(noop_screen, monkeypatch, capsys):
    analyze_calls: list[set[IssueKind] | frozenset[IssueKind] | None] = []
    load_keys: list[str] = []

    class FakeReportCache:
        def __init__(self, cache_dir):
            assert cache_dir == Path("report-cache-dir")

        def load(self, key):
            load_keys.append(key)
            if key == "project-key:variables:unused":
                return {"report": make_variable_report("BasePicture")}
            return None

        def validate(self, payload, *, fast=False):
            del fast
            return payload is not None

        def save(self, key, *, report, files):
            pytest.fail(f"cache should not save on hit: {key}, {report}, {files}")

    graph = SimpleNamespace(
        unavailable_libraries=set(),
        warnings=[],
        analysis_cache_key="project-key",
        analysis_manifest_files=frozenset({Path("programs/ProgramA.s")}),
    )

    monkeypatch.setattr(
        app_analysis,
        "_iter_loaded_projects",
        lambda *_args, **_kwargs: iter([("ProgramA", "bp-a", graph)]),
    )
    monkeypatch.setattr(app_analysis, "AnalysisReportCache", FakeReportCache)
    monkeypatch.setattr(app_analysis, "get_cache_dir", lambda: Path("report-cache-dir"))
    monkeypatch.setattr(
        app_analysis,
        "compute_analysis_report_cache_key",
        lambda project_key, analyzer_key: f"{project_key}:{analyzer_key}",
    )

    def _fake_analyze_variables(*_args, **kwargs):
        analyze_calls.append(kwargs.get("selected_issue_kinds"))
        return make_variable_report("Live")

    monkeypatch.setattr(app_analysis, "analyze_variables", _fake_analyze_variables)

    app_analysis.run_variable_analysis(app.DEFAULT_CONFIG.copy(), {IssueKind.UNUSED})

    assert analyze_calls == []
    assert load_keys == ["project-key:variables:unused"]
    assert "=== Target: ProgramA ===" in capsys.readouterr().out


def test_run_variable_analysis_cache_keys_selected_issue_kinds_separately(noop_screen, monkeypatch):
    save_keys: list[str] = []

    class FakeReportCache:
        def __init__(self, cache_dir):
            assert cache_dir == Path("report-cache-dir")

        def load(self, key):
            return None

        def validate(self, payload, *, fast=False):
            del payload, fast
            return False

        def save(self, key, *, report, files):
            del report, files
            save_keys.append(key)
            return True

    graph = SimpleNamespace(
        unavailable_libraries=set(),
        warnings=[],
        analysis_cache_key="project-key",
        analysis_manifest_files=frozenset({Path("programs/ProgramA.s")}),
    )

    monkeypatch.setattr(
        app_analysis,
        "_iter_loaded_projects",
        lambda *_args, **_kwargs: iter([("ProgramA", "bp-a", graph)]),
    )
    monkeypatch.setattr(app_analysis, "AnalysisReportCache", FakeReportCache)
    monkeypatch.setattr(app_analysis, "get_cache_dir", lambda: Path("report-cache-dir"))
    monkeypatch.setattr(
        app_analysis,
        "compute_analysis_report_cache_key",
        lambda project_key, analyzer_key: f"{project_key}:{analyzer_key}",
    )
    monkeypatch.setattr(app_analysis, "analyze_variables", lambda *_, **__: make_variable_report("ProgramA"))
    monkeypatch.setattr(app_analysis, "analyze_shadowing", lambda *_, **__: make_shadowing_report("ProgramA"))

    app_analysis.run_variable_analysis(app.DEFAULT_CONFIG.copy(), {IssueKind.UNUSED})
    app_analysis.run_variable_analysis(app.DEFAULT_CONFIG.copy(), None)

    default_kinds_key = ",".join(sorted(kind.name.casefold() for kind in DEFAULT_VARIABLE_ANALYSIS_KINDS))
    assert save_keys == [
        "project-key:variables:unused",
        f"project-key:variables:{default_kinds_key}",
        "project-key:variables:shadowing",
    ]


def test_run_variable_analysis_bypasses_report_cache_when_use_cache_disabled(noop_screen, monkeypatch):
    analyze_calls: list[str] = []

    class ForbiddenReportCache:
        def __init__(self, _cache_dir):
            pytest.fail("report cache should be bypassed when use_cache is false")

    graph = SimpleNamespace(
        unavailable_libraries=set(),
        warnings=[],
        analysis_cache_key="project-key",
        analysis_manifest_files=frozenset({Path("programs/ProgramA.s")}),
    )

    monkeypatch.setattr(
        app_analysis,
        "_iter_loaded_projects",
        lambda *_args, **_kwargs: iter([("ProgramA", "bp-a", graph)]),
    )
    monkeypatch.setattr(app_analysis, "AnalysisReportCache", ForbiddenReportCache)
    monkeypatch.setattr(
        app_analysis,
        "analyze_variables",
        lambda *_, **__: analyze_calls.append("run") or make_variable_report("ProgramA"),
    )

    app_analysis.run_variable_analysis(app.DEFAULT_CONFIG.copy() | {"use_cache": False}, {IssueKind.UNUSED})

    assert analyze_calls == ["run"]


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
    assert "  - warning one" in out
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

    app_analysis._print_validation_warnings(["TargetA: warn1", "TargetA: warn2", "TargetA: warn3"], limit=2)

    assert lines == [
        "Validation warnings (3):",
        "  - warn1",
        "  - warn2",
        "  - ... (+1 more)",
    ]


def test_print_validation_warnings_formats_picture_display_entries(monkeypatch):
    lines: list[str] = []
    monkeypatch.setattr(app_analysis, "emit_output", lambda message: lines.append(message))

    app_analysis._print_validation_warnings(
        [
            "TargetA: PictureDisplay in module 'Root.L1' path '+MissingPanel' could not be resolved: "
            "module 'MissingPanel' was not found under 'Root.L1'"
        ]
    )

    assert lines == [
        "Validation warnings (1):",
        "  - [Root.L1] '+MissingPanel'",
        "    module 'MissingPanel' was not found under 'Root.L1'",
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


def test_run_datatype_usage_analysis_updates_live_status(monkeypatch):
    updates: list[str] = []

    class FakeLiveStatusLine:
        def __enter__(self):
            return updates.append

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(builtins, "input", lambda _prompt="": "FlowVar")
    monkeypatch.setattr(
        app_analysis,
        "_iter_loaded_projects",
        lambda *_args, **_kwargs: iter(
            [("TargetA", "bp-a", SimpleNamespace(unavailable_libraries=set(), warnings=[]))]
        ),
    )
    monkeypatch.setattr(variables_reporting_module, "analyze_datatype_usage", lambda *_args, **_kwargs: "report")
    monkeypatch.setattr(app_analysis.console_module, "live_status_line", lambda: FakeLiveStatusLine())
    monkeypatch.setattr(app_analysis, "emit_output", lambda *_args, **_kwargs: None)

    app_analysis.run_datatype_usage_analysis(app.DEFAULT_CONFIG.copy(), pause_fn=None)

    assert updates == ["Analyzing datatype usage for TargetA: FlowVar"]


def test_parse_index_selection_supports_ranges_and_filters_invalid_tokens():
    assert app_analysis.parse_index_selection("1, 3-5, 8-6, bad, 11", 8) == [1, 3, 4, 5, 6, 7, 8]
