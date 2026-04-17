"""Tests for the interactive CLI application helpers."""

import builtins
from copy import deepcopy
import os
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from sattlint import app
from sattlint.analyzers import variables as variables_module
from sattlint.analyzers import variable_usage_reporting as variables_reporting_module
from sattlint.models.ast_model import FrameModule, ModuleTypeInstance, SingleModule
from sattlint.reporting.variables_report import (
    DEFAULT_VARIABLE_ANALYSIS_KINDS,
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
    basepicture_name = "Dummy"
    issues: list[object] = []
    visible_kinds = frozenset(DEFAULT_VARIABLE_ANALYSIS_KINDS)
    include_empty_sections = True

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
            mod_path = path + [mod.header.name]

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


def test_load_and_save_config(tmp_path, capsys):
    config_path = tmp_path / "config.toml"

    cfg, created = app.load_config(config_path)
    assert created is True
    assert cfg["mode"] == "official"
    assert config_path.exists()

    cfg["analyzed_programs_and_libraries"] = ["RootProgram"]
    app.save_config(config_path, cfg)
    out = capsys.readouterr().out
    assert "Config saved" in out

    loaded, created = app.load_config(config_path)
    assert created is False
    assert loaded["analyzed_programs_and_libraries"] == ["RootProgram"]


def test_save_config_rejects_none(tmp_path):
    config_path = tmp_path / "config.toml"
    cfg = cast(dict[str, object], app.DEFAULT_CONFIG.copy())
    cfg["analyzed_programs_and_libraries"] = None
    with pytest.raises(ValueError):
        app.save_config(config_path, cfg)


def test_clear_screen_uses_os_system_cls_on_windows(monkeypatch):
    calls: list[str] = []

    monkeypatch.setattr(app.os, "name", "nt")
    monkeypatch.setattr(app.os, "system", lambda command: calls.append(command) or 0)
    monkeypatch.setattr(app.sys, "stdout", SimpleNamespace(isatty=lambda: True))

    app.clear_screen()

    assert calls == ["cls"]


def test_self_check_handles_paths(tmp_path, monkeypatch, capsys):
    program_dir = tmp_path / "programs"
    abb_dir = tmp_path / "abb"
    program_dir.mkdir()
    abb_dir.mkdir()
    (program_dir / "Root.x").write_text("", encoding="utf-8")

    cfg = app.DEFAULT_CONFIG.copy()
    cfg.update(
        {
            "analyzed_programs_and_libraries": ["Root"],
            "program_dir": str(program_dir),
            "ABB_lib_dir": str(abb_dir),
            "other_lib_dirs": [str(tmp_path / "other")],
        }
    )

    ok = app.self_check(cfg)
    assert ok is True
    out = capsys.readouterr().out
    assert "Analyzed programs/libraries:" in out
    assert "✔ Root" in out


def test_self_check_allows_empty_analyzed_target_list(capsys):
    ok = app.self_check(app.DEFAULT_CONFIG.copy())

    out = capsys.readouterr().out
    assert ok is True
    assert "WARNING analyzed_programs_and_libraries is empty" in out


def test_documentation_config_defaults_are_merged(tmp_path):
    config_path = tmp_path / "config.toml"
    cfg, _created = app.load_config(config_path)
    cfg["documentation"] = {
        "classifications": {
            "ops": {
                "desc_label_equals": ["CustomLib:CustomOperation"]
            }
        }
    }

    app.save_config(config_path, cfg)
    loaded, _created = app.load_config(config_path)

    documentation_cfg = app.config_module.get_documentation_config(loaded)
    assert documentation_cfg["classifications"]["ops"]["desc_label_equals"] == [
        "CustomLib:CustomOperation"
    ]
    assert documentation_cfg["classifications"]["em"]["desc_label_equals"] == [
        "nnestruct:EquipModCoordinate"
    ]


def test_legacy_documentation_rule_keys_are_normalized():
    documentation_cfg = app.config_module.get_documentation_config(
        {
            "documentation": {
                "classifications": {
                    "ops": {
                        "descendant_moduletype_label_equals": [
                            "CustomLib:LegacyOperation"
                        ]
                    }
                }
            }
        }
    )

    assert documentation_cfg["classifications"]["ops"]["desc_label_equals"] == [
        "CustomLib:LegacyOperation"
    ]


def test_variable_analysis_menu_all_options(noop_screen, monkeypatch, real_context):
    if real_context:
        cfg = real_context["cfg"].copy()
        inputs = [
            "1",
            "1",
            "2",
            "3",
            "4",
            "5",
            "6",
            "7",
            "8",
            "9",
            "10",
            "11",
            "12",
            "13",
            "14",
            "15",
            "16",
            "b",
            "4",
            "1",
            "b",
            "f",
            "y",
            "b",
        ]
        monkeypatch.setattr(builtins, "input", make_input(inputs))
        app.analysis_menu(cfg)
        return

    calls = []

    def record(name):
        calls.append(name)

    monkeypatch.setattr(app, "run_variable_analysis", lambda *_: record("variable"))
    monkeypatch.setattr(
        app, "run_datatype_usage_analysis", lambda *_: record("datatype")
    )
    monkeypatch.setattr(app, "run_debug_variable_usage", lambda *_: record("debug"))
    monkeypatch.setattr(
        app, "run_module_localvar_analysis", lambda *_: record("module")
    )
    monkeypatch.setattr(app, "run_comment_code_analysis", lambda *_: record("comment"))
    monkeypatch.setattr(app, "force_refresh_ast", lambda *_: record("refresh"))

    inputs = [
        "1",
        "1",
        "2",
        "3",
        "4",
        "5",
        "6",
        "7",
        "8",
        "9",
        "10",
        "11",
        "12",
        "13",
        "14",
        "15",
        "16",
        "b",
        "4",
        "1",
        "b",
        "f",
        "y",
        "b",
    ]
    monkeypatch.setattr(builtins, "input", make_input(inputs))

    app.analysis_menu(app.DEFAULT_CONFIG.copy())

    assert calls.count("variable") == 13
    assert "datatype" in calls
    assert "debug" in calls
    assert "module" in calls
    assert "comment" in calls
    assert "refresh" in calls


def test_dump_menu_all_options(noop_screen, monkeypatch, real_context):
    if real_context:
        cfg = real_context["cfg"].copy()
        inputs = ["1", "y", "2", "y", "3", "y", "4", "y", "b"]
        monkeypatch.setattr(builtins, "input", make_input(inputs))
        app.dump_menu(cfg)
        return

    monkeypatch.setattr(
        app,
        "_iter_loaded_projects",
        lambda *_args, **_kwargs: iter([("TargetA", "project", SimpleNamespace())]),
    )

    dump_calls = []

    def record(name):
        dump_calls.append(name)

    monkeypatch.setattr(
        app.engine_module, "dump_parse_tree", lambda *_: record("parse")
    )
    monkeypatch.setattr(app.engine_module, "dump_ast", lambda *_: record("ast"))
    monkeypatch.setattr(
        app.engine_module, "dump_dependency_graph", lambda *_: record("deps")
    )
    monkeypatch.setattr(app, "analyze_variables", lambda *_, **__: DummyReport())

    inputs = ["1", "y", "2", "y", "3", "y", "4", "y", "b"]
    monkeypatch.setattr(builtins, "input", make_input(inputs))

    app.dump_menu(app.DEFAULT_CONFIG.copy())

    assert dump_calls == ["parse", "ast", "deps"]


def test_config_menu_all_options(noop_screen, monkeypatch, tmp_path):
    cfg = app.DEFAULT_CONFIG.copy()
    cfg["program_dir"] = str(tmp_path / "programs")
    cfg["ABB_lib_dir"] = str(tmp_path / "abb")

    monkeypatch.setattr(app, "target_exists", lambda *_: True)
    monkeypatch.setattr(app, "save_config", lambda *_: None)

    inputs = [
        "1",
        "NewTarget",
        "y",
        "3",
        "y",
        "4",
        "y",
        "5",
        "6",
        str(tmp_path / "prog"),
        "y",
        "7",
        str(tmp_path / "abb_new"),
        "y",
        "8",
        "y",
        str(tmp_path / "lib1"),
        "8",
        "n",
        "y",
        "1",
        "10",
        str(tmp_path / "icf"),
        "y",
        "11",
        "y",
        "9",
        "y",
        "b",
    ]
    monkeypatch.setattr(builtins, "input", make_input(inputs))

    dirty = app.config_menu(cfg)

    assert dirty is False
    assert cfg["analyzed_programs_and_libraries"] == ["NewTarget"]
    assert cfg["mode"] in ("official", "draft")


def test_documentation_menu_scope_by_moduletype(noop_screen, monkeypatch):
    cfg = deepcopy(app.DEFAULT_CONFIG)
    app._set_documentation_unit_selection(mode="all")
    inputs = ["4", "ApplTank, XDilute_221X251XY", "b"]
    monkeypatch.setattr(builtins, "input", make_input(inputs))

    dirty = app.documentation_menu(cfg)
    selection = app._get_documentation_unit_selection()

    assert dirty is True
    assert selection["mode"] == "moduletype_names"
    assert selection["moduletype_names"] == [
        "ApplTank",
        "XDilute_221X251XY",
    ]


def test_main_menu_all_options(noop_screen, monkeypatch, real_context):
    cfg = real_context["cfg"].copy() if real_context else app.DEFAULT_CONFIG.copy()

    monkeypatch.setattr(app, "load_config", lambda *_: (cfg, False))
    monkeypatch.setattr(app, "self_check", lambda *_: True)

    calls = []

    monkeypatch.setattr(app, "analysis_menu", lambda *_: calls.append("analysis"))
    monkeypatch.setattr(app, "dump_menu", lambda *_: calls.append("dump"))
    monkeypatch.setattr(app, "documentation_menu", lambda *_: True)
    monkeypatch.setattr(app, "config_menu", lambda *_: True)
    monkeypatch.setattr(app, "save_config", lambda *_: calls.append("save"))
    monkeypatch.setattr(app, "force_refresh_ast", lambda *_: None)

    inputs = ["1", "2", "3", "4", "5", "6", "y", "q", "y"]
    monkeypatch.setattr(builtins, "input", make_input(inputs))

    app.main()

    assert calls == ["analysis", "dump", "save"]


def test_syntax_check_command_ok(tmp_path, capsys):
    source_file = tmp_path / "ValidProgram.s"
    source_file.write_text(VALID_SINGLE_FILE, encoding="utf-8")

    exit_code = app.main(["syntax-check", str(source_file)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out.strip() == "OK"
    assert captured.err == ""


def test_cli_entry_point_forwards_sys_argv_without_loading_ast(
    tmp_path, capsys, monkeypatch
):
    source_file = tmp_path / "ValidProgram.s"
    source_file.write_text(VALID_SINGLE_FILE, encoding="utf-8")

    monkeypatch.setattr(app, "load_config", lambda *_: pytest.fail("load_config should not run"))
    monkeypatch.setattr(app, "ensure_ast_cache", lambda *_: pytest.fail("ensure_ast_cache should not run"))
    monkeypatch.setattr(app, "self_check", lambda *_: pytest.fail("self_check should not run"))
    monkeypatch.setattr(app.sys, "argv", ["sattlint", "syntax-check", str(source_file)])

    exit_code = app.cli()

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out.strip() == "OK"
    assert captured.err == ""


def test_main_starts_without_targets_and_skips_ast_cache(noop_screen, monkeypatch):
    cfg = deepcopy(app.DEFAULT_CONFIG)
    cfg["analyzed_programs_and_libraries"] = []
    calls = []

    monkeypatch.setattr(app, "load_config", lambda *_: (cfg, False))
    monkeypatch.setattr(app, "self_check", lambda *_: calls.append("self_check") or True)
    monkeypatch.setattr(
        app,
        "ensure_ast_cache",
        lambda *_: pytest.fail("ensure_ast_cache should not run without analyzed targets"),
    )
    monkeypatch.setattr(builtins, "input", make_input(["q"]))

    exit_code = app.main()

    assert exit_code == 0
    assert calls == ["self_check"]


def test_main_blocks_target_dependent_menu_actions_without_targets(
    noop_screen, monkeypatch, capsys
):
    cfg = deepcopy(app.DEFAULT_CONFIG)
    cfg["analyzed_programs_and_libraries"] = []

    monkeypatch.setattr(app, "load_config", lambda *_: (cfg, False))
    monkeypatch.setattr(app, "self_check", lambda *_: True)
    monkeypatch.setattr(
        app,
        "ensure_ast_cache",
        lambda *_: pytest.fail("ensure_ast_cache should not run without analyzed targets"),
    )
    monkeypatch.setattr(
        app,
        "analysis_menu",
        lambda *_: pytest.fail("analysis_menu should be blocked without analyzed targets"),
    )
    monkeypatch.setattr(
        app,
        "dump_menu",
        lambda *_: pytest.fail("dump_menu should be blocked without analyzed targets"),
    )
    monkeypatch.setattr(
        app,
        "documentation_menu",
        lambda *_: pytest.fail("documentation_menu should be blocked without analyzed targets"),
    )
    monkeypatch.setattr(
        app,
        "force_refresh_ast",
        lambda *_: pytest.fail("force_refresh_ast should be blocked without analyzed targets"),
    )
    monkeypatch.setattr(app, "pause", lambda: None)
    monkeypatch.setattr(builtins, "input", make_input(["1", "2", "3", "6", "q"]))

    exit_code = app.main()

    out = capsys.readouterr().out
    assert exit_code == 0
    assert out.count("No analyzed programs/libraries configured.") == 4


def test_syntax_check_command_reports_parse_error(tmp_path, capsys):
    source_file = tmp_path / "InvalidProgram.s"
    source_file.write_text(INVALID_SINGLE_FILE, encoding="utf-8")

    exit_code = app.main(["syntax-check", str(source_file)])

    captured = capsys.readouterr()
    assert exit_code != 0
    assert "ERROR [parse]" in captured.err
    assert str(source_file) in captured.err
    assert "Expected one of:" in captured.err
    assert "^" in captured.err


def test_syntax_check_command_rejects_missing_file(tmp_path, capsys):
    missing_file = tmp_path / "MissingProgram.s"

    exit_code = app.main(["syntax-check", str(missing_file)])

    captured = capsys.readouterr()
    assert exit_code != 0
    assert "File not found" in captured.err


def test_main_returns_error_for_unknown_cli_command(capsys):
    exit_code = app.main(["unknown-command"])

    captured = capsys.readouterr()
    assert exit_code != 0
    assert "usage:" in captured.err.lower()


def test_advanced_datatype_analysis_choices(noop_screen, monkeypatch, real_context):
    if real_context:
        cfg = real_context["cfg"].copy()

        monkeypatch.setattr(
            builtins,
            "input",
            make_input(["1", real_context["var_name"]]),
        )
        app.run_advanced_datatype_analysis(cfg)

        monkeypatch.setattr(
            builtins,
            "input",
            make_input(["2", real_context["module_name"]]),
        )
        app.run_advanced_datatype_analysis(cfg)

        monkeypatch.setattr(
            builtins,
            "input",
            make_input(["3", real_context["var_name"]]),
        )
        app.run_advanced_datatype_analysis(cfg)
        return

    monkeypatch.setattr(
        app,
        "_iter_loaded_projects",
        lambda *_args, **_kwargs: iter([("TargetA", "project", SimpleNamespace(unavailable_libraries=set()))]),
    )
    monkeypatch.setattr(
        variables_reporting_module, "analyze_datatype_usage", lambda *_, **__: "report"
    )
    monkeypatch.setattr(
        variables_reporting_module, "debug_variable_usage", lambda *_, **__: "report"
    )

    monkeypatch.setattr(builtins, "input", make_input(["1", "VarName"]))
    app.run_advanced_datatype_analysis(app.DEFAULT_CONFIG.copy())

    monkeypatch.setattr(builtins, "input", make_input(["2", "ModuleName"]))
    app.run_advanced_datatype_analysis(app.DEFAULT_CONFIG.copy())

    monkeypatch.setattr(builtins, "input", make_input(["3", "VarName"]))
    app.run_advanced_datatype_analysis(app.DEFAULT_CONFIG.copy())


def test_run_variable_analysis_runs_all_analyzed_targets(noop_screen, monkeypatch, capsys):
    monkeypatch.setattr(
        app,
        "_iter_loaded_projects",
        lambda *_args, **_kwargs: iter(
            [
                ("ProgramA", "bp-a", SimpleNamespace(unavailable_libraries=set())),
                ("LibB", "bp-b", SimpleNamespace(unavailable_libraries=set())),
            ]
        ),
    )
    monkeypatch.setattr(app, "analyze_variables", lambda *_, **__: make_variable_report())
    monkeypatch.setattr(app, "analyze_shadowing", lambda *_, **__: make_shadowing_report())

    app.run_variable_analysis(app.DEFAULT_CONFIG.copy(), None)

    out = capsys.readouterr().out
    assert "=== Target: ProgramA ===" in out
    assert "=== Target: LibB ===" in out
    assert out.count("Issues: 0") == 2


def test_run_variable_analysis_all_reports_lists_empty_categories(
    noop_screen, monkeypatch, capsys
):
    graph = SimpleNamespace(unavailable_libraries=set(), warnings=[])
    monkeypatch.setattr(
        app,
        "_iter_loaded_projects",
        lambda *_args, **_kwargs: iter([("ProgramA", "bp-a", graph)]),
    )
    monkeypatch.setattr(
        app,
        "analyze_variables",
        lambda *_, **__: VariablesReport(
            basepicture_name="ProgramA",
            issues=[],
            visible_kinds=frozenset(DEFAULT_VARIABLE_ANALYSIS_KINDS),
            include_empty_sections=True,
        ),
    )
    monkeypatch.setattr(
        app,
        "analyze_shadowing",
        lambda *_, **__: make_shadowing_report("ProgramA"),
    )

    app.run_variable_analysis(app.DEFAULT_CONFIG.copy(), None)

    out = capsys.readouterr().out
    assert "=== Target: ProgramA ===" in out
    assert "Issues: 0" in out
    assert "Min/Max mapping name mismatches" in out
    assert "Name collisions" in out
    assert "Reset contamination (missing reset writes)" in out
    assert out.count("      none") >= 3


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

    monkeypatch.setattr(app, "load_project", fake_load_project)

    projects = list(app._iter_loaded_projects(cfg))

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
    monkeypatch.setattr(app, "_iter_loaded_projects", lambda *_args, **_kwargs: iter(()))

    app.run_variable_analysis(app.DEFAULT_CONFIG.copy(), None)

    out = capsys.readouterr().out
    assert "No variable analysis output was produced because no target loaded successfully." in out


def test_run_variable_analysis_prints_validation_warnings(noop_screen, monkeypatch, capsys):
    graph = SimpleNamespace(
        unavailable_libraries=set(),
        warnings=["ProgramA: warning one", "dep_b: warning two"],
    )
    monkeypatch.setattr(
        app,
        "_iter_loaded_projects",
        lambda *_args, **_kwargs: iter([("ProgramA", "bp", graph)]),
    )
    monkeypatch.setattr(app, "analyze_variables", lambda *_, **__: make_variable_report())
    monkeypatch.setattr(app, "analyze_shadowing", lambda *_, **__: make_shadowing_report())

    app.run_variable_analysis(app.DEFAULT_CONFIG.copy(), None)

    out = capsys.readouterr().out
    assert "Validation warnings (1):" in out
    assert "  - ProgramA: warning one" in out
    assert "dep_b: warning two" not in out
    assert "Issues: 0" in out


def test_run_variable_analysis_hides_dependency_validation_warnings(
    noop_screen, monkeypatch, capsys
):
    graph = SimpleNamespace(
        unavailable_libraries=set(),
        warnings=["dep_a: warning one", "dep_b: warning two"],
    )
    monkeypatch.setattr(
        app,
        "_iter_loaded_projects",
        lambda *_args, **_kwargs: iter([("ProgramA", "bp", graph)]),
    )
    monkeypatch.setattr(app, "analyze_variables", lambda *_, **__: make_variable_report())
    monkeypatch.setattr(app, "analyze_shadowing", lambda *_, **__: make_shadowing_report())

    app.run_variable_analysis(app.DEFAULT_CONFIG.copy(), None)

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
        app,
        "_iter_loaded_projects",
        lambda *_args, **_kwargs: iter([("LibraryTarget", project_bp, graph)]),
    )

    captured: dict[str, object] = {}

    def _fake_analyze_variables(*_args, **kwargs):
        captured.update(kwargs)
        return make_variable_report()

    monkeypatch.setattr(app, "analyze_variables", _fake_analyze_variables)
    monkeypatch.setattr(app, "analyze_shadowing", lambda *_, **__: make_shadowing_report())

    cfg = app.DEFAULT_CONFIG.copy()
    cfg["program_dir"] = "programs"

    app.run_variable_analysis(cfg, None)

    assert captured["analyzed_target_is_library"] is True


def test_variable_usage_submenu_exposes_min_max_report(noop_screen, monkeypatch):
    captured: list[object] = []
    monkeypatch.setattr(app, "run_variable_analysis", lambda _cfg, kinds: captured.append(kinds))
    monkeypatch.setattr(builtins, "input", make_input(["9", "b"]))

    app.variable_usage_submenu(app.DEFAULT_CONFIG.copy())

    assert captured == [{app.IssueKind.MIN_MAX_MAPPING_MISMATCH}]


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


def test_variable_usage_submenu_exposes_shadowing_report(noop_screen, monkeypatch):
    captured: list[object] = []
    monkeypatch.setattr(app, "run_variable_analysis", lambda _cfg, kinds: captured.append(kinds))
    monkeypatch.setattr(builtins, "input", make_input(["13", "b"]))

    app.variable_usage_submenu(app.DEFAULT_CONFIG.copy())

    assert captured == [{app.IssueKind.SHADOWING}]
