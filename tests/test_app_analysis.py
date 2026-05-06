"""Tests for variable analysis workflows, advanced datatype analysis, and variable usage sub-menus in the app."""

import builtins
import os
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from typing import Any, ClassVar, cast

import pytest

from sattline_parser import parse_source_text as parser_core_parse_source_text
from sattline_parser.models.ast_model import FrameModule, ModuleTypeInstance, SingleModule
from sattlint import app, app_analysis
from sattlint.analyzers import variable_usage_reporting as variables_reporting_module
from sattlint.analyzers import variables as variables_module
from sattlint.reporting.variables_report import (
    ALL_VARIABLE_ANALYSIS_KINDS,
    DEFAULT_VARIABLE_ANALYSIS_KINDS,
    IssueKind,
    VariableIssue,
    VariablesReport,
)

VALID_SINGLE_FILE = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    A: integer := 0;
    B: integer := 1;
    C: integer := 2;
    D: integer := 3;
    X: integer := 0;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
        X = IF A > 0 THEN B ELSE C + D ENDIF;
ENDDEF (*BasePicture*);
"""

INVALID_SINGLE_FILE = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    TestVar: integer := 0
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
        TestVar = TestVar + 1;
ENDDEF (*BasePicture*);
"""


class DummyReport:
    basepicture_name: ClassVar[str] = "Dummy"
    issues: ClassVar[list[object]] = []
    visible_kinds: ClassVar[frozenset[IssueKind]] = frozenset(DEFAULT_VARIABLE_ANALYSIS_KINDS)
    include_empty_sections: ClassVar[bool] = True

    def summary(self):
        return "summary"


def make_shadowing_report(basepicture_name="Dummy"):
    return VariablesReport(
        basepicture_name=basepicture_name,
        issues=[],
        visible_kinds=frozenset({app.IssueKind.SHADOWING}),
        include_empty_sections=True,
    )


def make_variable_report(basepicture_name="Dummy"):
    return VariablesReport(
        basepicture_name=basepicture_name,
        issues=[],
        visible_kinds=frozenset(DEFAULT_VARIABLE_ANALYSIS_KINDS),
        include_empty_sections=True,
    )


def make_input(responses):
    it = iter(responses)

    def _input(_prompt=""):
        try:
            return next(it)
        except StopIteration as exc:
            raise AssertionError("No more input responses provided") from exc

    return _input


def _find_module_with_localvar(base_picture):
    def walk(mods, path):
        for mod in mods or []:
            if not hasattr(mod, "header"):
                continue
            mod_path = [*path, mod.header.name]

            if isinstance(mod, SingleModule):
                if mod.localvariables:
                    return mod_path, mod.localvariables[0].name
                found = walk(mod.submodules, mod_path)
                if found:
                    return found

            elif isinstance(mod, FrameModule):
                found = walk(mod.submodules, mod_path)
                if found:
                    return found

            elif isinstance(mod, ModuleTypeInstance):
                mt = next(
                    (
                        m
                        for m in (base_picture.moduletype_defs or [])
                        if m.name.casefold() == mod.moduletype_name.casefold()
                    ),
                    None,
                )
                if mt and mt.localvariables:
                    return mod_path, mt.localvariables[0].name

        return None

    return walk(getattr(base_picture, "submodules", None), [base_picture.header.name])


def _pick_any_variable_name(base_picture, graph):
    analyzer = variables_module.VariablesAnalyzer(
        base_picture,
        debug=False,
        fail_loudly=False,
        unavailable_libraries=getattr(graph, "unavailable_libraries", set()),
    )
    for var_list in analyzer._any_var_index.values():
        if var_list:
            for var in var_list:
                if getattr(var, "name", None):
                    return var.name
    return None


@pytest.fixture(scope="session")
def real_context():
    if os.getenv("SATTLINT_RUN_REAL_CONTEXT") != "1":
        return None
    cfg, _ = app.load_config(app.CONFIG_PATH)
    if not app.self_check(cfg):
        return None

    project_bp, graph = app.load_project(cfg)

    var_name = _pick_any_variable_name(project_bp, graph)
    module_info = _find_module_with_localvar(project_bp)

    if not var_name or not module_info:
        return None

    module_path, module_var = module_info
    module_path_str = ".".join(module_path[1:])
    if not module_path_str:
        return None

    return {
        "cfg": cfg,
        "var_name": var_name,
        "module_path": module_path_str,
        "module_var": module_var,
        "module_name": module_path[-1],
    }


@pytest.fixture
def noop_screen(monkeypatch):
    monkeypatch.setattr(app, "clear_screen", lambda: None)
    monkeypatch.setattr(app, "pause", lambda: None)


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
    monkeypatch.setattr(app_analysis, "analyze_variables", lambda *_, **__: make_variable_report())
    monkeypatch.setattr(app_analysis, "analyze_shadowing", lambda *_, **__: make_shadowing_report())

    app_analysis.run_variable_analysis(app.DEFAULT_CONFIG.copy(), None)

    out = capsys.readouterr().out
    assert "=== Target: ProgramA ===" in out
    assert "=== Target: LibB ===" in out
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

    result = app_analysis.source_paths_for_current_target(project_bp, graph)

    assert result == {Path("programs/TargetA.s")}


def test_target_is_library_returns_false_without_matching_source_paths():
    cfg = {"program_dir": "programs"}
    project_bp = SimpleNamespace(header=SimpleNamespace(name="TargetA"), origin_file="Missing.s")
    graph = SimpleNamespace(source_files=set())

    assert app_analysis._target_is_library(cfg, project_bp, graph) is False


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


def test_run_module_duplicates_analysis_rejects_empty_name(monkeypatch):
    lines: list[str] = []
    pauses: list[str] = []

    monkeypatch.setattr(builtins, "input", lambda _prompt="": "   ")
    monkeypatch.setattr(app_analysis, "emit_output", lambda message: lines.append(message))

    app_analysis.run_module_duplicates_analysis(
        app.DEFAULT_CONFIG.copy(),
        iter_loaded_projects_fn=lambda *_args, **_kwargs: pytest.fail("should not load projects"),
        pause_fn=lambda: pauses.append("pause"),
    )

    assert any("No module name provided" in line for line in lines)
    assert pauses == ["pause"]


def test_run_module_duplicates_analysis_uses_selected_instances(monkeypatch):
    lines: list[str] = []
    pauses: list[str] = []
    matches = [
        (["Root", "Area", "PumpA"], SimpleNamespace(datecode=101)),
        (["Root", "Area", "PumpB"], SimpleNamespace(datecode=None)),
        (["Root", "Area", "PumpC"], SimpleNamespace(datecode=303)),
    ]
    captured: dict[str, object] = {}

    monkeypatch.setattr(builtins, "input", make_input(["Pump", "1, 3-2"]))
    monkeypatch.setattr(app_analysis, "emit_output", lambda message: lines.append(message))
    monkeypatch.setattr(app_analysis, "find_modules_by_name", lambda *_args, **_kwargs: matches)
    monkeypatch.setattr(
        app_analysis,
        "compare_modules",
        lambda selected: (
            captured.update({"selected": selected}) or SimpleNamespace(summary=lambda: "comparison summary")
        ),
    )
    monkeypatch.setattr(
        app_analysis,
        "analyze_module_duplicates",
        lambda *_args, **_kwargs: pytest.fail("should use explicit comparison path"),
    )

    app_analysis.run_module_duplicates_analysis(
        app.DEFAULT_CONFIG.copy(),
        iter_loaded_projects_fn=cast(Any, lambda *_args, **_kwargs: iter([("TargetA", "bp", SimpleNamespace())])),
        pause_fn=lambda: pauses.append("pause"),
    )

    assert captured["selected"] == matches
    assert any("Found 3 instance(s) for 'Pump':" in line for line in lines)
    assert any("comparison summary" in line for line in lines)
    assert pauses == ["pause"]


def test_run_module_duplicates_analysis_requires_two_selected_instances(monkeypatch):
    lines: list[str] = []
    pauses: list[str] = []
    matches = [
        (["Root", "PumpA"], SimpleNamespace(datecode=101)),
        (["Root", "PumpB"], SimpleNamespace(datecode=202)),
    ]

    monkeypatch.setattr(builtins, "input", make_input(["Pump", "1"]))
    monkeypatch.setattr(app_analysis, "emit_output", lambda message: lines.append(message))
    monkeypatch.setattr(app_analysis, "find_modules_by_name", lambda *_args, **_kwargs: matches)
    monkeypatch.setattr(
        app_analysis,
        "compare_modules",
        lambda *_args, **_kwargs: pytest.fail("should skip compare when fewer than two indices are selected"),
    )

    app_analysis.run_module_duplicates_analysis(
        app.DEFAULT_CONFIG.copy(),
        iter_loaded_projects_fn=cast(Any, lambda *_args, **_kwargs: iter([("TargetA", "bp", SimpleNamespace())])),
        pause_fn=lambda: pauses.append("pause"),
    )

    assert any("Need at least two instances to compare; skipping." in line for line in lines)
    assert pauses == ["pause"]


def test_run_module_find_by_name_lists_matches_and_reports_errors(monkeypatch):
    lines: list[str] = []
    pauses: list[str] = []

    def fake_find_modules(_project_bp, module_name, debug=False):
        if module_name == "Pump":
            return [(["Root", "PumpA"], SimpleNamespace(datecode=101))]
        if module_name == "Missing":
            return []
        raise RuntimeError("boom")

    monkeypatch.setattr(builtins, "input", lambda _prompt="": "Pump, Missing, Boom")
    monkeypatch.setattr(app_analysis, "emit_output", lambda message: lines.append(message))
    monkeypatch.setattr(app_analysis, "find_modules_by_name", fake_find_modules)

    app_analysis.run_module_find_by_name(
        app.DEFAULT_CONFIG.copy(),
        iter_loaded_projects_fn=cast(Any, lambda *_args, **_kwargs: iter([("TargetA", "bp", SimpleNamespace())])),
        pause_fn=lambda: pauses.append("pause"),
    )

    assert any("Found 1 module instance(s) for 'Pump':" in line for line in lines)
    assert any("No modules found with name 'Missing'." in line for line in lines)
    assert any("Error during search: boom" in line for line in lines)
    assert pauses == ["pause"]


def test_run_module_tree_debug_uses_default_depth_on_invalid_input(monkeypatch):
    lines: list[str] = []
    pauses: list[str] = []
    captured: dict[str, object] = {}

    monkeypatch.setattr(app_analysis, "emit_output", lambda message: lines.append(message))
    monkeypatch.setattr(
        app_analysis,
        "debug_module_structure",
        lambda project_bp, max_depth=0: captured.update({"project_bp": project_bp, "max_depth": max_depth}),
    )

    app_analysis.run_module_tree_debug(
        app.DEFAULT_CONFIG.copy(),
        prompt_fn=lambda _message, _default: "not-a-number",
        iter_loaded_projects_fn=cast(Any, lambda *_args, **_kwargs: iter([("TargetA", "bp", SimpleNamespace())])),
        pause_fn=lambda: pauses.append("pause"),
    )

    assert captured == {"project_bp": "bp", "max_depth": 10}
    assert any("Invalid depth; using default 10" in line for line in lines)
    assert pauses == ["pause"]


def test_run_checks_reports_no_matching_checks_and_pauses(monkeypatch):
    lines: list[str] = []
    pauses: list[str] = []

    monkeypatch.setattr(app_analysis, "emit_output", lambda message: lines.append(message))

    app_analysis.run_checks(
        app.DEFAULT_CONFIG.copy(),
        ["missing-check"],
        get_enabled_analyzers_fn=lambda: [SimpleNamespace(key="variables", name="Variables")],
        pause_fn=lambda: pauses.append("pause"),
    )

    assert any("No matching checks found" in line for line in lines)
    assert pauses == ["pause"]


def test_run_checks_runs_selected_non_default_cli_exposed_analyzer(monkeypatch):
    lines: list[str] = []

    monkeypatch.setattr(app_analysis, "emit_output", lambda message: lines.append(message))

    report = SimpleNamespace(summary=lambda: "state inference summary")

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
                run=lambda _context: report,
            )
        ],
        target_is_library_fn=lambda *_args, **_kwargs: False,
        pause_fn=None,
    )

    assert any("State inference (state_inference)" in line for line in lines)
    assert any("state inference summary" in line for line in lines)


def test_run_icf_validation_covers_missing_dir_invalid_dir_and_empty_file_list(monkeypatch, tmp_path):
    lines: list[str] = []
    pauses: list[str] = []

    monkeypatch.setattr(app_analysis, "emit_output", lambda message: lines.append(message))

    app_analysis.run_icf_validation(
        app.DEFAULT_CONFIG.copy(),
        configured_icf_files_fn=lambda _cfg: (None, []),
        load_program_ast_fn=lambda *_args, **_kwargs: pytest.fail("should not load program"),
        pause_fn=lambda: pauses.append("pause-none"),
    )

    missing_dir = tmp_path / "missing-icf"
    app_analysis.run_icf_validation(
        app.DEFAULT_CONFIG.copy(),
        configured_icf_files_fn=lambda _cfg: (missing_dir, [missing_dir / "ProgramA.icf"]),
        load_program_ast_fn=lambda *_args, **_kwargs: pytest.fail("should not load program"),
        pause_fn=lambda: pauses.append("pause-missing"),
    )

    valid_dir = tmp_path / "icf"
    valid_dir.mkdir()
    app_analysis.run_icf_validation(
        app.DEFAULT_CONFIG.copy(),
        configured_icf_files_fn=lambda _cfg: (valid_dir, []),
        load_program_ast_fn=lambda *_args, **_kwargs: pytest.fail("should not load program"),
        pause_fn=lambda: pauses.append("pause-empty"),
    )

    assert any("icf_dir is not set in the config" in line for line in lines)
    assert any(f"icf_dir does not exist or is not a directory: {missing_dir}" in line for line in lines)
    assert any(f"No .icf files found in {valid_dir}" in line for line in lines)
    assert pauses == ["pause-none", "pause-missing", "pause-empty"]


def test_run_module_localvar_analysis_rejects_empty_module_path_and_variable(monkeypatch):
    lines: list[str] = []
    pauses: list[str] = []

    monkeypatch.setattr(app_analysis, "emit_output", lambda message: lines.append(message))
    monkeypatch.setattr(builtins, "input", make_input(["", "UnitA", ""]))

    def load_project_fn(_cfg):
        return (SimpleNamespace(header=SimpleNamespace(name="BasePicture")), SimpleNamespace())

    app_analysis.run_module_localvar_analysis(
        app.DEFAULT_CONFIG.copy(),
        load_project_fn=cast(Any, load_project_fn),
        pause_fn=lambda: pauses.append("pause-module"),
    )
    app_analysis.run_module_localvar_analysis(
        app.DEFAULT_CONFIG.copy(),
        load_project_fn=cast(Any, load_project_fn),
        pause_fn=lambda: pauses.append("pause-var"),
    )

    assert any("No module path provided" in line for line in lines)
    assert any("No variable name provided" in line for line in lines)
    assert pauses == ["pause-module", "pause-var"]


def test_run_module_localvar_analysis_reports_success_and_errors(monkeypatch):
    lines: list[str] = []
    pauses: list[str] = []

    monkeypatch.setattr(app_analysis, "emit_output", lambda message: lines.append(message))
    monkeypatch.setattr(builtins, "input", make_input(["UnitA", "Dv"]))

    reporting_module = pytest.importorskip("sattlint.analyzers.variable_usage_reporting")
    monkeypatch.setattr(reporting_module, "analyze_module_localvar_fields", lambda *_args, **_kwargs: "field report")

    app_analysis.run_module_localvar_analysis(
        app.DEFAULT_CONFIG.copy(),
        load_project_fn=cast(
            Any,
            lambda _cfg: (SimpleNamespace(header=SimpleNamespace(name="BasePicture")), SimpleNamespace()),
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

    assert any("=== Target: TargetA ===" in line for line in lines)
    assert any("field report" in line for line in lines)
    assert pauses == ["pause"]


def test_menu_wrappers_delegate_to_underlying_callbacks():
    calls: list[tuple[str, object]] = []

    app_analysis.run_analysis_menu(app.DEFAULT_CONFIG.copy(), analysis_menu_fn=lambda cfg: calls.append(("run", cfg)))
    app_analysis.variable_analysis_menu(
        app.DEFAULT_CONFIG.copy(), analysis_menu_fn=lambda cfg: calls.append(("var", cfg))
    )
    app_analysis.run_checks_menu(
        app.DEFAULT_CONFIG.copy(),
        run_checks_fn=lambda cfg, selected: calls.append(("checks", selected if selected is not None else cfg)),
    )

    assert calls[0][0] == "run"
    assert calls[1][0] == "var"
    assert calls[2] == ("checks", app.DEFAULT_CONFIG.copy())


def test_run_mms_interface_analysis_reports_summary_and_errors(monkeypatch):
    lines: list[str] = []
    pauses: list[str] = []

    monkeypatch.setattr(app_analysis, "emit_output", lambda message: lines.append(message))

    def fake_mms(project_bp, debug=False, config=None):
        if project_bp == "bp-b":
            raise RuntimeError("boom")
        return SimpleNamespace(summary=lambda: "mms summary")

    monkeypatch.setattr(app_analysis, "analyze_mms_interface_variables", fake_mms)

    app_analysis.run_mms_interface_analysis(
        app.DEFAULT_CONFIG.copy(),
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

    assert any("mms summary" in line for line in lines)
    assert any("Error during analysis for TargetB: boom" in line for line in lines)
    assert pauses == ["pause"]


def test_run_icf_validation_reports_entryless_files_load_failures_and_summary(monkeypatch, tmp_path):
    lines: list[str] = []
    pauses: list[str] = []
    icf_dir = tmp_path / "icf"
    icf_dir.mkdir()
    empty_file = icf_dir / "Empty.icf"
    broken_file = icf_dir / "Broken.icf"
    valid_file = icf_dir / "Valid.icf"
    for path in (empty_file, broken_file, valid_file):
        path.write_text("dummy", encoding="utf-8")

    monkeypatch.setattr(app_analysis, "emit_output", lambda message: lines.append(message))
    monkeypatch.setattr(
        app_analysis,
        "parse_icf_file",
        lambda path: [] if path.name == "Empty.icf" else [SimpleNamespace()],
    )
    monkeypatch.setattr(app_analysis.engine_module, "merge_project_basepicture", lambda bp, _graph: bp)

    def fake_load_program(_cfg, program_name):
        if program_name == "Broken":
            raise RuntimeError("load failed")
        return "bp-valid", SimpleNamespace(ast_by_name={})

    def fake_validate(program_bp, entries, expected_program, debug=False, moduletype_index=None):
        assert program_bp == "bp-valid"
        assert expected_program == "Valid"
        return SimpleNamespace(
            total_entries=3,
            valid_entries=2,
            issues=[object()],
            skipped_entries=1,
            summary=lambda: "icf report",
        )

    app_analysis.run_icf_validation(
        app.DEFAULT_CONFIG.copy(),
        configured_icf_files_fn=lambda _cfg: (icf_dir, [empty_file, broken_file, valid_file]),
        load_program_ast_fn=cast(Any, fake_load_program),
        validate_icf_entries_against_program_fn=fake_validate,
        pause_fn=lambda: pauses.append("pause"),
    )

    assert any("Empty.icf: no entries found" in line for line in lines)
    assert any("Broken.icf: failed to load program 'Broken': load failed" in line for line in lines)
    assert any("icf report" in line for line in lines)
    assert any("Files processed: 3" in line for line in lines)
    assert any("Files failed: 1" in line for line in lines)
    assert any("Entries: 3" in line for line in lines)
    assert any("Valid: 2" in line for line in lines)
    assert any("Invalid: 1" in line for line in lines)
    assert any("Skipped: 1" in line for line in lines)
    assert pauses == ["pause"]


def test_run_debug_variable_usage_and_comment_code_analysis_cover_empty_success_and_error(monkeypatch):
    lines: list[str] = []
    pauses: list[str] = []

    monkeypatch.setattr(app_analysis, "emit_output", lambda message: lines.append(message))
    monkeypatch.setattr(builtins, "input", make_input(["", "FlowVar"]))
    monkeypatch.setattr(
        app_analysis, "debug_variable_usage", lambda bp, var_name, debug=False: f"debug:{bp}:{var_name}"
    )
    monkeypatch.setattr(
        app_analysis,
        "analyze_comment_code_files",
        lambda paths, root_name: SimpleNamespace(
            summary=lambda: f"comment:{root_name}:{sorted(str(path) for path in paths)}"
        ),
    )

    app_analysis.run_debug_variable_usage(app.DEFAULT_CONFIG.copy(), pause_fn=lambda: pauses.append("pause-empty"))
    app_analysis.run_debug_variable_usage(
        app.DEFAULT_CONFIG.copy(),
        iter_loaded_projects_fn=cast(
            Any,
            lambda *_args, **_kwargs: iter(
                [
                    ("TargetA", "bp-a", SimpleNamespace()),
                    ("TargetB", "bp-b", SimpleNamespace()),
                ]
            ),
        ),
        pause_fn=lambda: pauses.append("pause-debug"),
    )
    app_analysis.run_comment_code_analysis(
        app.DEFAULT_CONFIG.copy(),
        iter_loaded_projects_fn=cast(
            Any,
            lambda *_args, **_kwargs: iter(
                [("TargetA", SimpleNamespace(header=SimpleNamespace(name="Root")), "graph")]
            ),
        ),
        source_paths_for_current_target_fn=lambda _project_bp, _graph: {Path("A.s"), Path("B.s")},
        pause_fn=lambda: pauses.append("pause-comment"),
    )

    assert any("No variable name provided" in line for line in lines)
    assert any("debug:bp-a:FlowVar" in line for line in lines)
    assert any("debug:bp-b:FlowVar" in line for line in lines)
    assert any("comment:Root:['A.s', 'B.s']" in line for line in lines)
    assert pauses == ["pause-empty", "pause-debug", "pause-comment"]


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
    monkeypatch.setattr(builtins, "input", make_input(["14", "b"]))

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
    monkeypatch.setattr(builtins, "input", make_input(["12", "b"]))

    app.variable_usage_submenu(app.DEFAULT_CONFIG.copy())

    assert captured == [{app.IssueKind.RESET_CONTAMINATION}]


def test_variable_usage_submenu_exposes_implicit_latch_report(noop_screen, monkeypatch):
    captured: list[object] = []
    monkeypatch.setattr(app, "run_variable_analysis", lambda _cfg, kinds: captured.append(kinds))
    monkeypatch.setattr(builtins, "input", make_input(["18", "b"]))

    app.variable_usage_submenu(app.DEFAULT_CONFIG.copy())

    assert captured == [{app.IssueKind.IMPLICIT_LATCH}]


def test_variable_usage_submenu_exposes_shadowing_report(noop_screen, monkeypatch):
    captured: list[object] = []
    monkeypatch.setattr(app, "run_variable_analysis", lambda _cfg, kinds: captured.append(kinds))
    monkeypatch.setattr(builtins, "input", make_input(["13", "b"]))

    app.variable_usage_submenu(app.DEFAULT_CONFIG.copy())

    assert captured == [{app.IssueKind.SHADOWING}]


def test_variable_usage_submenu_exposes_hidden_global_coupling_report(noop_screen, monkeypatch):
    captured: list[object] = []
    monkeypatch.setattr(app, "run_variable_analysis", lambda _cfg, kinds: captured.append(kinds))
    monkeypatch.setattr(builtins, "input", make_input(["20", "b"]))

    app.variable_usage_submenu(app.DEFAULT_CONFIG.copy())

    assert captured == [{app.IssueKind.HIDDEN_GLOBAL_COUPLING}]


def test_variable_usage_submenu_exposes_global_scope_minimization_report(noop_screen, monkeypatch):
    captured: list[object] = []
    monkeypatch.setattr(app, "run_variable_analysis", lambda _cfg, kinds: captured.append(kinds))
    monkeypatch.setattr(builtins, "input", make_input(["19", "b"]))

    app.variable_usage_submenu(app.DEFAULT_CONFIG.copy())

    assert captured == [{app.IssueKind.GLOBAL_SCOPE_MINIMIZATION}]


def test_variable_usage_submenu_exposes_high_fan_in_out_report(noop_screen, monkeypatch):
    captured: list[object] = []
    monkeypatch.setattr(app, "run_variable_analysis", lambda _cfg, kinds: captured.append(kinds))
    monkeypatch.setattr(builtins, "input", make_input(["21", "b"]))

    app.variable_usage_submenu(app.DEFAULT_CONFIG.copy())

    assert captured == [{app.IssueKind.HIGH_FAN_IN_OUT}]


def test_variable_usage_submenu_exposes_procedure_status_report(noop_screen, monkeypatch):
    captured: list[object] = []
    monkeypatch.setattr(app, "run_variable_analysis", lambda _cfg, kinds: captured.append(kinds))
    monkeypatch.setattr(builtins, "input", make_input(["15", "b"]))

    app.variable_usage_submenu(app.DEFAULT_CONFIG.copy())

    assert captured == [{app.IssueKind.PROCEDURE_STATUS}]


def test_variable_usage_submenu_exposes_write_without_effect_report(noop_screen, monkeypatch):
    captured: list[object] = []
    monkeypatch.setattr(app, "run_variable_analysis", lambda _cfg, kinds: captured.append(kinds))
    monkeypatch.setattr(builtins, "input", make_input(["16", "b"]))

    app.variable_usage_submenu(app.DEFAULT_CONFIG.copy())

    assert captured == [{app.IssueKind.WRITE_WITHOUT_EFFECT}]


def test_variable_usage_submenu_exposes_contract_mismatch_report(noop_screen, monkeypatch):
    captured: list[object] = []
    monkeypatch.setattr(app, "run_variable_analysis", lambda _cfg, kinds: captured.append(kinds))
    monkeypatch.setattr(builtins, "input", make_input(["17", "b"]))

    app.variable_usage_submenu(app.DEFAULT_CONFIG.copy())

    assert captured == [{app.IssueKind.CONTRACT_MISMATCH}]
