"""Tests for the interactive CLI application helpers."""

import builtins
import os
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from sattlint import app
from sattlint.analyzers import variables as variables_module
from sattlint.analyzers import variable_usage_reporting as variables_reporting_module
from sattlint.models.ast_model import FrameModule, ModuleTypeInstance, SingleModule


class DummyReport:
    def summary(self):
        return "summary"


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

    cfg["root"] = "RootProgram"
    app.save_config(config_path, cfg)
    out = capsys.readouterr().out
    assert "Config saved" in out

    loaded, created = app.load_config(config_path)
    assert created is False
    assert loaded["root"] == "RootProgram"


def test_save_config_rejects_none(tmp_path):
    config_path = tmp_path / "config.toml"
    cfg = cast(dict[str, object], app.DEFAULT_CONFIG.copy())
    cfg["root"] = None
    with pytest.raises(ValueError):
        app.save_config(config_path, cfg)


def test_self_check_handles_paths(tmp_path, monkeypatch, capsys):
    program_dir = tmp_path / "programs"
    abb_dir = tmp_path / "abb"
    program_dir.mkdir()
    abb_dir.mkdir()
    (program_dir / "Root.x").write_text("", encoding="utf-8")

    cfg = app.DEFAULT_CONFIG.copy()
    cfg.update(
        {
            "root": "Root",
            "program_dir": str(program_dir),
            "ABB_lib_dir": str(abb_dir),
            "other_lib_dirs": [str(tmp_path / "other")],
        }
    )

    ok = app.self_check(cfg)
    assert ok is True
    out = capsys.readouterr().out
    assert "Root program/library found" in out


def test_variable_analysis_menu_all_options(noop_screen, monkeypatch, real_context):
    if real_context:
        cfg = real_context["cfg"].copy()
        inputs = [
            "1",
            "2",
            "3",
            "4",
            "5",
            "6",
            "7",
            "8",
            real_context["var_name"],
            "9",
            real_context["var_name"],
            "10",
            real_context["module_path"],
            real_context["module_var"],
            "16",
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
    monkeypatch.setattr(app, "run_datatype_usage_analysis", lambda *_: record("datatype"))
    monkeypatch.setattr(app, "run_debug_variable_usage", lambda *_: record("debug"))
    monkeypatch.setattr(app, "run_module_localvar_analysis", lambda *_: record("module"))
    monkeypatch.setattr(app, "run_comment_code_analysis", lambda *_: record("comment"))
    monkeypatch.setattr(app, "force_refresh_ast", lambda *_: record("refresh"))

    inputs = [
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
        "16",
        "f",
        "y",
        "b",
    ]
    monkeypatch.setattr(builtins, "input", make_input(inputs))

    app.analysis_menu(app.DEFAULT_CONFIG.copy())

    assert calls.count("variable") == 7
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

    monkeypatch.setattr(app, "load_project", lambda *_: ("project", SimpleNamespace()))

    dump_calls = []

    def record(name):
        dump_calls.append(name)

    monkeypatch.setattr(app.engine_module, "dump_parse_tree", lambda *_: record("parse"))
    monkeypatch.setattr(app.engine_module, "dump_ast", lambda *_: record("ast"))
    monkeypatch.setattr(app.engine_module, "dump_dependency_graph", lambda *_: record("deps"))
    monkeypatch.setattr(app, "analyze_variables", lambda *_ , **__: DummyReport())

    inputs = ["1", "y", "2", "y", "3", "y", "4", "y", "b"]
    monkeypatch.setattr(builtins, "input", make_input(inputs))

    app.dump_menu(app.DEFAULT_CONFIG.copy())

    assert dump_calls == ["parse", "ast", "deps"]


def test_config_menu_all_options(noop_screen, monkeypatch, tmp_path):
    cfg = app.DEFAULT_CONFIG.copy()
    cfg["program_dir"] = str(tmp_path / "programs")
    cfg["ABB_lib_dir"] = str(tmp_path / "abb")

    monkeypatch.setattr(app, "root_exists", lambda *_: True)
    monkeypatch.setattr(app, "save_config", lambda *_: None)

    inputs = [
        "1",
        "NewRoot",
        "y",
        "2",
        "y",
        "3",
        "y",
        "4",
        "y",
        "5",
        str(tmp_path / "prog"),
        "y",
        "6",
        str(tmp_path / "abb_new"),
        "y",
        "7",
        "y",
        str(tmp_path / "lib1"),
        "7",
        "n",
        "y",
        "1",
        "8",
        "y",
        "b",
    ]
    monkeypatch.setattr(builtins, "input", make_input(inputs))

    dirty = app.config_menu(cfg)

    assert dirty is False
    assert cfg["root"] == "NewRoot"
    assert cfg["mode"] in ("official", "draft")


def test_main_menu_all_options(noop_screen, monkeypatch, real_context):
    cfg = (real_context["cfg"].copy() if real_context else app.DEFAULT_CONFIG.copy())

    monkeypatch.setattr(app, "load_config", lambda *_: (cfg, False))
    monkeypatch.setattr(app, "self_check", lambda *_: True)

    calls = []

    monkeypatch.setattr(app, "analysis_menu", lambda *_: calls.append("analysis"))
    monkeypatch.setattr(app, "dump_menu", lambda *_: calls.append("dump"))
    monkeypatch.setattr(app, "config_menu", lambda *_: True)
    monkeypatch.setattr(app, "save_config", lambda *_: calls.append("save"))
    monkeypatch.setattr(app, "force_refresh_ast", lambda *_: None)

    inputs = ["1", "2", "3", "4", "5", "y", "q", "y"]
    monkeypatch.setattr(builtins, "input", make_input(inputs))

    app.main()

    assert calls == ["analysis", "dump", "save"]


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

    monkeypatch.setattr(app, "load_project", lambda *_: ("project", "graph"))
    monkeypatch.setattr(variables_reporting_module, "analyze_datatype_usage", lambda *_ , **__: "report")
    monkeypatch.setattr(variables_reporting_module, "debug_variable_usage", lambda *_ , **__: "report")

    monkeypatch.setattr(builtins, "input", make_input(["1", "VarName"]))
    app.run_advanced_datatype_analysis(app.DEFAULT_CONFIG.copy())

    monkeypatch.setattr(builtins, "input", make_input(["2", "ModuleName"]))
    app.run_advanced_datatype_analysis(app.DEFAULT_CONFIG.copy())

    monkeypatch.setattr(builtins, "input", make_input(["3", "VarName"]))
    app.run_advanced_datatype_analysis(app.DEFAULT_CONFIG.copy())
