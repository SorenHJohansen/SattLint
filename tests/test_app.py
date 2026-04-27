"""Tests for the interactive CLI application helpers."""

import builtins
import os
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from typing import Any, ClassVar, cast

import pytest

from sattline_parser import parse_source_text as parser_core_parse_source_text
from sattlint import app
from sattlint.analyzers import variable_usage_reporting as variables_reporting_module
from sattlint.analyzers import variables as variables_module
from sattlint.analyzers.framework import AnalyzerSpec, Issue, SimpleReport
from sattlint.analyzers.registry import get_actual_cli_analyzer_keys
from sattlint.models.ast_model import BasePicture, FrameModule, ModuleTypeInstance, SingleModule
from sattlint.models.project_graph import ProjectGraph
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


def test_clear_screen_uses_windows_console_helper(monkeypatch):
    calls: list[str] = []

    monkeypatch.setattr(app.os, "name", "nt")
    monkeypatch.setattr(app, "_clear_windows_console", lambda: calls.append("clear"))
    monkeypatch.setattr(
        app.sys,
        "stdout",
        SimpleNamespace(flush=lambda: None, write=lambda _text: None),
    )

    app.clear_screen()

    assert calls == ["clear"]


def test_run_icf_validation_forces_dependency_aware_ast_loading(tmp_path, monkeypatch, capsys, noop_screen):
    icf_dir = tmp_path / "icf"
    icf_dir.mkdir()
    icf_file = icf_dir / "Program.icf"
    icf_file.write_text("Tag=Program:Root.Value\n", encoding="utf-8")

    cfg = deepcopy(app.DEFAULT_CONFIG)
    cfg.update(
        {
            "icf_dir": str(icf_dir),
            "program_dir": str(tmp_path),
            "ABB_lib_dir": str(tmp_path),
            "other_lib_dirs": [],
            "scan_root_only": True,
            "debug": False,
        }
    )

    calls: list[tuple[str, bool]] = []

    def fake_load_program_ast(_cfg, program_name, *, force_dependency_resolution=False):
        calls.append((program_name, force_dependency_resolution))
        root_bp = SimpleNamespace(moduletype_defs=[])
        graph = SimpleNamespace(ast_by_name={program_name: SimpleNamespace(moduletype_defs=[])})
        return root_bp, graph

    class FakeReport:
        total_entries = 1
        valid_entries = 1
        skipped_entries = 0
        issues: ClassVar[list[object]] = []

        def summary(self):
            return "summary"

    monkeypatch.setattr(app, "load_program_ast", fake_load_program_ast)
    monkeypatch.setattr(app.engine_module, "merge_project_basepicture", lambda bp, _graph: bp)
    monkeypatch.setattr(app, "validate_icf_entries_against_program", lambda *args, **kwargs: FakeReport())

    app.run_icf_validation(cfg)

    assert calls == [("Program", True)]
    out = capsys.readouterr().out
    assert "summary" in out


def test_run_format_icf_command_formats_files_without_changing_nonblank_lines(tmp_path, capsys):
    icf_dir = tmp_path / "icf"
    icf_dir.mkdir()
    icf_file = icf_dir / "Program.icf"
    original = (
        "; header\n"
        "[Unit UnitA]\n"
        "[Journal JournalA]\n"
        "[Group JournalData_DCStoMES]\n"
        "OPR_ID=F::Program:UnitA.JournalA.T.OPR_ID\n"
        "[Operation OpStart]\n"
        "[Group StateChange_DCStoMES]\n"
        "STATE_NO=F::Program:UnitA.OpStart.STATE_NO\n"
    )
    icf_file.write_text(original, encoding="utf-8")

    cfg = deepcopy(app.DEFAULT_CONFIG)
    cfg["icf_dir"] = str(icf_dir)

    exit_code = app.run_format_icf_command(cfg)

    formatted = icf_file.read_text(encoding="utf-8")
    out = capsys.readouterr().out
    assert exit_code == app.EXIT_SUCCESS
    assert [line for line in formatted.splitlines() if line.strip()] == [
        line for line in original.splitlines() if line.strip()
    ]
    assert "[Journal JournalA]\n\n[Group JournalData_DCStoMES]" in formatted
    assert "[Operation OpStart]" in formatted
    assert "Changed: 1" in out


def test_clear_screen_falls_back_to_ansi_when_windows_clear_fails(monkeypatch):
    writes: list[str] = []

    def _raise_os_error() -> None:
        raise OSError("clear failed")

    monkeypatch.setattr(app.os, "name", "nt")
    monkeypatch.setattr(app.os, "system", lambda _command: 1)
    monkeypatch.setattr(app, "_clear_windows_console", _raise_os_error)
    monkeypatch.setattr(
        app.sys,
        "stdout",
        SimpleNamespace(flush=lambda: None, write=lambda text: writes.append(text)),
    )

    app.clear_screen()

    assert writes == ["\033[2J\033[H"]


def test_clear_screen_falls_back_to_cls_before_ansi(monkeypatch):
    writes: list[str] = []
    calls: list[str] = []

    def _raise_os_error() -> None:
        raise OSError("clear failed")

    monkeypatch.setattr(app.os, "name", "nt")
    monkeypatch.setattr(app, "_clear_windows_console", _raise_os_error)
    monkeypatch.setattr(
        app.os,
        "system",
        lambda command: calls.append(command) or 0,
    )
    monkeypatch.setattr(
        app.sys,
        "stdout",
        SimpleNamespace(flush=lambda: None, write=lambda text: writes.append(text)),
    )

    app.clear_screen()

    assert calls == ["cls"]
    assert writes == []


@pytest.mark.skipif(os.name != "nt", reason="Windows-specific")
def test_configure_windows_console_api_sets_wide_char_signature():
    import ctypes

    class _FakeCall:
        argtypes = None
        restype = None

    class _FakeKernel32:
        GetStdHandle = _FakeCall()
        GetConsoleScreenBufferInfo = _FakeCall()
        FillConsoleOutputCharacterW = _FakeCall()
        FillConsoleOutputAttribute = _FakeCall()
        SetConsoleCursorPosition = _FakeCall()

    class _Coord(ctypes.Structure):  # type: ignore[misc]
        _fields_ = ()

    class _BufferInfo(ctypes.Structure):  # type: ignore[misc]
        _fields_ = ()

    kernel32 = _FakeKernel32()

    app._configure_windows_console_api(kernel32, _Coord, _BufferInfo)

    assert kernel32.FillConsoleOutputCharacterW.argtypes[1] is ctypes.wintypes.WCHAR  # type: ignore[union-attr]
    assert kernel32.FillConsoleOutputCharacterW.restype is ctypes.wintypes.BOOL  # type: ignore[union-attr]
    assert kernel32.SetConsoleCursorPosition.argtypes == [ctypes.wintypes.HANDLE, _Coord]  # type: ignore[union-attr]


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
    ok = app.self_check(deepcopy(app.DEFAULT_CONFIG))

    out = capsys.readouterr().out
    assert ok is True
    assert "WARNING analyzed_programs_and_libraries is empty" in out


def test_documentation_config_defaults_are_merged(tmp_path):
    config_path = tmp_path / "config.toml"
    cfg, _created = app.load_config(config_path)
    cfg["documentation"] = {"classifications": {"ops": {"desc_label_equals": ["CustomLib:CustomOperation"]}}}

    app.save_config(config_path, cfg)
    loaded, _created = app.load_config(config_path)

    documentation_cfg = app.config_module.get_documentation_config(loaded)
    assert documentation_cfg["classifications"]["ops"]["desc_label_equals"] == ["CustomLib:CustomOperation"]
    assert documentation_cfg["classifications"]["em"]["desc_label_equals"] == ["nnestruct:EquipModCoordinate"]


def test_legacy_documentation_rule_keys_are_normalized():
    documentation_cfg = app.config_module.get_documentation_config(
        {
            "documentation": {
                "classifications": {"ops": {"descendant_moduletype_label_equals": ["CustomLib:LegacyOperation"]}}
            }
        }
    )

    assert documentation_cfg["classifications"]["ops"]["desc_label_equals"] == ["CustomLib:LegacyOperation"]


def test_variable_analysis_menu_all_options(noop_screen, monkeypatch, real_context):
    calls = []

    def record(name):
        calls.append(name)

    monkeypatch.setattr(app, "_run_checks", lambda *_: record("checks"))
    monkeypatch.setattr(app, "run_variable_analysis", lambda *_: record("variable"))
    monkeypatch.setattr(app, "run_datatype_usage_analysis", lambda *_: record("datatype"))
    monkeypatch.setattr(app, "run_debug_variable_usage", lambda *_: record("debug"))
    monkeypatch.setattr(app, "run_module_localvar_analysis", lambda *_: record("module"))
    monkeypatch.setattr(app, "run_module_duplicates_analysis", lambda *_: record("module-compare"))
    monkeypatch.setattr(app, "run_module_find_by_name", lambda *_: record("module-find"))
    monkeypatch.setattr(app, "run_module_tree_debug", lambda *_: record("module-tree"))
    monkeypatch.setattr(app, "run_mms_interface_analysis", lambda *_: record("mms"))
    monkeypatch.setattr(app, "run_icf_validation", lambda *_: record("icf"))
    monkeypatch.setattr(app, "run_comment_code_analysis", lambda *_: record("comment"))
    monkeypatch.setattr(
        app,
        "_get_enabled_analyzers",
        lambda: [
            SimpleNamespace(
                key="variables",
                name="Variable issues",
                description="Unused and never-read variables",
            )
        ],
    )

    inputs = [
        "1",
        "2",
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
        "17",
        "18",
        "19",
        "20",
        "21",
        "22",
        "23",
        "24",
        "b",
        "3",
        "1",
        "2",
        "3",
        "b",
        "4",
        "1",
        "2",
        "b",
        "5",
        "1",
        "b",
        "6",
        "1",
        "2",
        "b",
        "7",
        "1",
        "2",
        "3",
        "b",
        "b",
    ]
    monkeypatch.setattr(builtins, "input", make_input(inputs))

    app.analysis_menu(app.DEFAULT_CONFIG.copy())

    assert calls.count("variable") == 21
    assert calls.count("checks") == 3
    assert "datatype" in calls
    assert "debug" in calls
    assert "module" in calls
    assert "module-compare" in calls
    assert "module-find" in calls
    assert "module-tree" in calls
    assert "mms" in calls
    assert "icf" in calls
    assert "comment" in calls


def test_analyzer_catalog_menu_runs_selected_checks(noop_screen, monkeypatch):
    captured: list[object] = []
    monkeypatch.setattr(
        app,
        "_get_enabled_analyzers",
        lambda: [
            SimpleNamespace(
                key="variables",
                name="Variable issues",
                description="Unused and never-read variables",
            ),
            SimpleNamespace(
                key="spec-compliance",
                name="Engineering spec compliance",
                description="Engineering rule checks",
            ),
        ],
    )
    monkeypatch.setattr(app, "_run_checks", lambda _cfg, selected: captured.append(selected))
    monkeypatch.setattr(builtins, "input", make_input(["2", "1", "b"]))

    app.analyzer_catalog_menu(app.DEFAULT_CONFIG.copy())

    assert captured == [["variables"], None]


def test_get_enabled_analyzers_returns_default_cli_subset(monkeypatch):
    monkeypatch.setattr(
        app,
        "get_default_cli_analyzers",
        lambda: [SimpleNamespace(key="variables"), SimpleNamespace(key="sfc")],
    )

    analyzers = app._get_enabled_analyzers()

    assert [spec.key for spec in analyzers] == ["variables", "sfc"]


def test_run_checks_reaches_every_default_cli_analyzer(noop_screen, monkeypatch):
    invoked: list[str] = []
    analyzer_specs = [
        AnalyzerSpec(
            key=key,
            name=f"Analyzer {index}",
            description=f"Reachability probe for {key}",
            run=lambda context, analyzer_key=key: (
                invoked.append(analyzer_key),
                SimpleReport(name=analyzer_key),
            )[1],
        )
        for index, key in enumerate(get_actual_cli_analyzer_keys(), start=1)
    ]
    monkeypatch.setattr(app, "_get_enabled_analyzers", lambda: analyzer_specs)
    monkeypatch.setattr(
        app,
        "_iter_loaded_projects",
        lambda *_args, **_kwargs: iter([("ProgramA", "bp-a", SimpleNamespace(unavailable_libraries=set()))]),
    )

    app._run_checks(app.DEFAULT_CONFIG.copy(), None)

    assert invoked == list(get_actual_cli_analyzer_keys())


def test_run_checks_applies_rule_profiles_to_simple_reports(noop_screen, monkeypatch, capsys):
    target = SimpleNamespace(header=SimpleNamespace(name="Program"))

    def _run_profiled_report(context):
        return SimpleReport(
            name="Profiled",
            issues=[
                Issue(kind="naming.inconsistent_style", message="Name drift"),
                Issue(kind="sorting.loop_output_refactor", message="Loop output refactor candidate"),
            ],
        )

    monkeypatch.setattr(
        app,
        "_get_enabled_analyzers",
        lambda: [
            AnalyzerSpec(
                key="profiled",
                name="Profiled",
                description="Synthetic analyzer for rule-profile coverage",
                run=_run_profiled_report,
            )
        ],
    )
    monkeypatch.setattr(
        app, "_iter_loaded_projects", lambda *_args, **_kwargs: iter([("Program", target, SimpleNamespace())])
    )

    strict_cfg = deepcopy(app.DEFAULT_CONFIG)
    strict_cfg["analysis"]["rule_profiles"]["active"] = "strict-pharma"
    app._run_checks(strict_cfg, None)
    strict_out = capsys.readouterr().out

    assert "semantic.naming-inconsistent-style" in strict_out
    assert "[error | style | semantic.naming-inconsistent-style]" in strict_out
    assert "Suggested fix:" in strict_out
    assert "semantic.loop-output-refactor" in strict_out

    legacy_cfg = deepcopy(app.DEFAULT_CONFIG)
    legacy_cfg["analysis"]["rule_profiles"]["active"] = "legacy-plant"
    app._run_checks(legacy_cfg, None)
    legacy_out = capsys.readouterr().out

    assert "semantic.naming-inconsistent-style" not in legacy_out
    assert "semantic.loop-output-refactor" not in legacy_out
    assert "No issues found." in legacy_out


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

    monkeypatch.setattr(app.engine_module, "dump_parse_tree", lambda *_: record("parse"))
    monkeypatch.setattr(app.engine_module, "dump_ast", lambda *_: record("ast"))
    monkeypatch.setattr(app.engine_module, "dump_dependency_graph", lambda *_: record("deps"))
    monkeypatch.setattr(app, "analyze_variables", lambda *_, **__: DummyReport())

    inputs = ["1", "y", "2", "y", "3", "y", "4", "y", "b"]
    monkeypatch.setattr(builtins, "input", make_input(inputs))

    app.dump_menu(app.DEFAULT_CONFIG.copy())

    assert dump_calls == ["parse", "ast", "deps"]


def test_config_menu_all_options(noop_screen, monkeypatch, tmp_path):
    cfg = deepcopy(app.DEFAULT_CONFIG)
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


def test_show_config_uses_sectioned_layout(capsys, monkeypatch, tmp_path):
    cfg = deepcopy(app.DEFAULT_CONFIG)
    cfg.update(
        {
            "analyzed_programs_and_libraries": ["KaHAApplSupportLib"],
            "mode": "draft",
            "scan_root_only": False,
            "fast_cache_validation": True,
            "debug": True,
            "program_dir": r"Projects\Program",
            "ABB_lib_dir": r"Projects\ABB",
            "icf_dir": r"Projects\ICF",
            "other_lib_dirs": [r"Projects\Lib1", r"Projects\Lib2"],
        }
    )

    monkeypatch.setattr(app, "get_graphics_rules_path", lambda: tmp_path / "graphics_rules.json")
    monkeypatch.setattr(
        app,
        "load_graphics_rules",
        lambda _path=None: (
            {
                "schema_version": 1,
                "rules": [
                    {
                        "module_kind": "frame",
                        "unit_structure_path": "L1.L2.UnitControl",
                        "description": "Unit shell",
                        "expected": {"moduledef": {"clipping_size": [1.0, 1.0]}},
                    },
                    {
                        "module_kind": "moduletype",
                        "moduletype_name": "EquipModPanelShort",
                        "equipment_module_structure_path": "L1.L2.EquipModPanelShort",
                        "expected": {"moduledef": {"clipping_size": [1.0, 1.0]}},
                    },
                ],
            },
            False,
        ),
    )
    (tmp_path / "graphics_rules.json").write_text("{}", encoding="utf-8")

    app.show_config(cfg)

    out = capsys.readouterr().out
    assert "Current Configuration" in out
    assert "Analyzed Programs" in out and "Libraries" in out
    assert "KaHAApplSupportLib" in out
    assert "General" in out
    assert "scan_root_only" in out
    assert "fast_cache_validation" in out
    assert "Directories" in out
    assert r"Projects\Program" in out
    assert "Other" in out and "Library" in out
    assert r"Projects\Lib2" in out
    assert "Graphics Rules" in out
    assert "graphics_rules_path" in out
    assert "Configured Graphics Rule Selectors" in out
    assert "unit_structure_path=L1.L2.UnitControl" in out
    assert "equipment_module_structure_path=L1.L2.EquipModPanelShort" in out
    assert "Documentation Classifications" in out
    assert "desc_label_equals  nnestruct:EquipModCoordinate" in out


def test_module_analysis_submenu_runs_graphics_rules_check(noop_screen, monkeypatch):
    calls: list[str] = []

    monkeypatch.setattr(
        app,
        "run_module_duplicates_analysis",
        lambda *_: calls.append("compare"),
    )
    monkeypatch.setattr(
        app,
        "run_module_find_by_name",
        lambda *_: calls.append("find"),
    )
    monkeypatch.setattr(
        app,
        "run_module_tree_debug",
        lambda *_: calls.append("tree"),
    )
    monkeypatch.setattr(
        app,
        "run_graphics_rules_validation",
        lambda *_: calls.append("graphics"),
    )
    monkeypatch.setattr(builtins, "input", make_input(["1", "2", "3", "4", "b"]))

    app.module_analysis_submenu(app.DEFAULT_CONFIG.copy())

    assert calls == ["compare", "find", "tree", "graphics"]


def test_graphics_rules_menu_adds_and_saves_rule(noop_screen, monkeypatch, tmp_path):
    rules_path = tmp_path / "graphics_rules.json"
    rules = {"schema_version": 1, "rules": []}
    saved_rules: list[dict[str, Any]] = []

    monkeypatch.setattr(app, "get_graphics_rules_path", lambda: rules_path)
    monkeypatch.setattr(app, "load_graphics_rules", lambda _path=None: (rules, False))
    monkeypatch.setattr(
        app,
        "save_graphics_rules",
        lambda _path, payload: saved_rules.append(deepcopy(payload)),
    )
    monkeypatch.setattr(
        app,
        "_prompt_graphics_rule_definition_with_config",
        lambda _cfg=None: {
            "module_name": "L1",
            "module_kind": "frame",
            "relative_module_path": "Equipmentmoduler.Stop.L1",
            "moduletype_name": "",
            "description": "House rule",
            "expected": {
                "invocation": {"coords": [1.43, 1.35, 0.0, 0.56, 0.56]},
                "moduledef": {"clipping_size": [1.0, 0.21429]},
            },
        },
    )
    monkeypatch.setattr(builtins, "input", make_input(["1", "", "3", "", "b"]))

    app.graphics_rules_menu()

    assert len(saved_rules) == 1
    assert saved_rules[0]["rules"][0]["relative_module_path"] == "Equipmentmoduler.Stop.L1"


def test_pick_or_prompt_graphics_rule_selector_value_picks_discovered_option(monkeypatch):
    monkeypatch.setattr(
        app,
        "_discover_graphics_rule_selector_options",
        lambda *_args, **_kwargs: [
            {
                "selector_value": "L1.L2.UnitControl",
                "count": 2,
                "target_count": 1,
                "sample_module_path": "TargetA.UnitA.L1.L2.UnitControl",
            }
        ],
    )
    monkeypatch.setattr(builtins, "input", make_input(["1"]))

    selected = app._pick_or_prompt_graphics_rule_selector_value(
        "unit_structure_path",
        "single",
        cfg=app.DEFAULT_CONFIG.copy(),
    )

    assert selected == "L1.L2.UnitControl"


def test_discover_graphics_rule_selector_options_deduplicates_selectors(monkeypatch):
    cfg = deepcopy(app.DEFAULT_CONFIG)
    cfg["analyzed_programs_and_libraries"] = ["TargetA"]
    graph = SimpleNamespace(unavailable_libraries=set())
    monkeypatch.setattr(
        app,
        "_iter_loaded_projects",
        lambda *_args, **_kwargs: iter([("TargetA", SimpleNamespace(), graph)]),
    )
    monkeypatch.setattr(
        app,
        "_collect_graphics_layout_entries_for_target",
        lambda *_args, **_kwargs: [
            {
                "module_path": "TargetA.UnitA.L1.L2.UnitControl",
                "unit_root_path": "TargetA.UnitA",
                "unit_structure_path": "L1.L2.UnitControl",
                "module_kind": "module",
            },
            {
                "module_path": "TargetA.UnitB.L1.L2.UnitControl",
                "unit_root_path": "TargetA.UnitB",
                "unit_structure_path": "L1.L2.UnitControl",
                "module_kind": "module",
            },
        ],
    )

    options = app._discover_graphics_rule_selector_options(
        cfg,
        selector_field="unit_structure_path",
        module_kind="single",
    )

    assert options == [
        {
            "selector_value": "L1.L2.UnitControl",
            "count": 2,
            "target_count": 1,
            "sample_module_path": "TargetA.UnitA.L1.L2.UnitControl",
        }
    ]


def test_run_graphics_rules_validation_reports_not_to_spec(noop_screen, monkeypatch, capsys):
    cfg = deepcopy(app.DEFAULT_CONFIG)
    cfg["analyzed_programs_and_libraries"] = ["TargetA"]
    graph = SimpleNamespace(unavailable_libraries=set())

    monkeypatch.setattr(
        app,
        "load_graphics_rules",
        lambda _path=None: (
            {
                "schema_version": 1,
                "rules": [
                    {
                        "module_name": "L1",
                        "module_kind": "frame",
                        "relative_module_path": "Equipmentmoduler.Stop.L1",
                        "expected": {
                            "invocation": {"coords": [1.43, 1.35, 0.0, 0.56, 0.56]},
                        },
                    }
                ],
            },
            False,
        ),
    )
    monkeypatch.setattr(
        app,
        "_iter_loaded_projects",
        lambda *_args, **_kwargs: iter([("TargetA", SimpleNamespace(), graph)]),
    )
    monkeypatch.setattr(
        app,
        "_collect_graphics_layout_entries_for_target",
        lambda *_args, **_kwargs: [
            {
                "module_path": "TargetA.Equipmentmoduler.Stop.L1",
                "relative_module_path": "Equipmentmoduler.Stop.L1",
                "module_name": "L1",
                "module_kind": "frame",
                "invocation": {"coords": [1.5, 1.35, 0.0, 0.56, 0.56]},
                "moduledef": {},
            }
        ],
    )

    app.run_graphics_rules_validation(cfg)

    out = capsys.readouterr().out
    assert "=== Target: TargetA ===" in out
    assert "Not to spec      : 1" in out
    assert "TargetA.Equipmentmoduler.Stop.L1" in out


def test_print_graphics_rules_summary_shows_table(capsys):
    app._print_graphics_rules_summary(
        Path("graphics_rules.json"),
        {
            "schema_version": 1,
            "rules": [
                {
                    "module_kind": "frame",
                    "module_name": "L1",
                    "relative_module_path": "Equipmentmoduler.Stop.L1",
                    "moduletype_name": "",
                    "description": "Stop state layout",
                    "expected": {
                        "moduledef": {"clipping_size": [1.0, 0.14286]},
                    },
                }
            ],
        },
        dirty=False,
    )

    out = capsys.readouterr().out
    assert "Selector" in out
    assert "Fields" in out
    assert "Description" in out
    assert "Equipmentmoduler.Stop.L1" in out


def test_annotate_graphics_entries_with_structure_paths_adds_unit_and_equipment_paths(monkeypatch):
    documented_unit = SimpleNamespace(path=("TargetA", "KaHA221A"), name="KaHA221A")
    monkeypatch.setattr(app, "classify_documentation_structure", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(
        app,
        "discover_documentation_unit_candidates",
        lambda _classification: [documented_unit],
    )

    entries = [
        {
            "module_path": "TargetA.KaHA221A.L1",
            "module_name": "L1",
            "module_kind": "frame",
        },
        {
            "module_path": "TargetA.KaHA221A.L1.L2.UnitControl",
            "module_name": "UnitControl",
            "module_kind": "module",
        },
        {
            "module_path": "TargetA.KaHA221A.L1.L2.Empty.L1.L2.EquipModPanel",
            "module_name": "EquipModPanel",
            "module_kind": "moduletype-instance",
            "moduletype_name": "EquipModPanelShort",
        },
    ]

    annotated = app._annotate_graphics_entries_with_structure_paths(
        entries,
        cast(BasePicture, SimpleNamespace()),
        cast(ProjectGraph, SimpleNamespace(unavailable_libraries=set())),
    )

    assert annotated[0]["unit_structure_path"] == "L1"
    assert annotated[1]["unit_structure_path"] == "L1.L2.UnitControl"
    assert annotated[2]["unit_structure_path"] == "L1.L2.Empty.L1.L2.EquipModPanelShort"
    assert annotated[2]["equipment_module_structure_path"] == "L1.L2.EquipModPanelShort"


def test_annotate_graphics_entries_with_structure_paths_ignores_wrapper_candidate_without_unitcontrol(
    monkeypatch,
):
    wrapper_candidate = SimpleNamespace(path=("BasePicture", "L1"), name="L1")
    monkeypatch.setattr(app, "classify_documentation_structure", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(
        app,
        "discover_documentation_unit_candidates",
        lambda _classification: [wrapper_candidate],
    )

    entries = [
        {
            "module_path": "BasePicture.L1.Changelog",
            "module_name": "Changelog",
            "module_kind": "module",
        },
        {
            "module_path": "BasePicture.L1.LoadPanel_Frame",
            "module_name": "LoadPanel_Frame",
            "module_kind": "frame",
        },
    ]

    annotated = app._annotate_graphics_entries_with_structure_paths(
        entries,
        cast(BasePicture, SimpleNamespace()),
        cast(ProjectGraph, SimpleNamespace(unavailable_libraries=set())),
    )

    assert all("unit_root_path" not in entry for entry in annotated)
    assert all("unit_structure_path" not in entry for entry in annotated)


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
    cfg["analyzed_programs_and_libraries"] = ["TargetA"]

    monkeypatch.setattr(app, "load_config", lambda *_: (cfg, False))
    monkeypatch.setattr(app, "self_check", lambda *_: True)

    calls = []

    monkeypatch.setattr(app, "analysis_menu", lambda *_: calls.append("analysis"))
    monkeypatch.setattr(app, "documentation_menu", lambda *_: calls.append("documentation") or True)
    monkeypatch.setattr(app, "config_menu", lambda *_: calls.append("setup") or True)
    monkeypatch.setattr(app, "tools_menu", lambda *_: calls.append("tools"))
    monkeypatch.setattr(app, "show_help", lambda *_: calls.append("help"))
    monkeypatch.setattr(app, "save_config", lambda *_: calls.append("save"))

    inputs = ["1", "2", "3", "4", "5", "q", "y"]
    monkeypatch.setattr(builtins, "input", make_input(inputs))

    app.main()

    assert calls == ["analysis", "documentation", "setup", "tools", "help", "save"]


def test_tools_menu_all_options(noop_screen, monkeypatch):
    cfg = deepcopy(app.DEFAULT_CONFIG)
    cfg["analyzed_programs_and_libraries"] = ["TargetA"]
    calls: list[str] = []

    monkeypatch.setattr(app, "self_check", lambda *_: calls.append("self-check") or True)
    monkeypatch.setattr(app, "dump_menu", lambda *_: calls.append("dump"))
    monkeypatch.setattr(app, "force_refresh_ast", lambda *_: calls.append("refresh"))
    monkeypatch.setattr(builtins, "input", make_input(["1", "2", "3", "y", "b"]))

    app.tools_menu(cfg)

    assert calls == ["self-check", "dump", "refresh"]


def test_force_refresh_ast_bypasses_file_ast_cache(monkeypatch):
    cfg = deepcopy(app.DEFAULT_CONFIG)
    cfg["analyzed_programs_and_libraries"] = ["TargetA", "TargetB"]
    cleared: list[str] = []
    load_calls: list[tuple[str | None, bool, bool]] = []

    class _FakeCache:
        def __init__(self, *_args, **_kwargs):
            pass

        def clear(self, key: str) -> None:
            cleared.append(key)

    def fake_load_project(
        _cfg,
        target_name=None,
        *,
        use_cache=True,
        use_file_ast_cache=True,
    ):
        load_calls.append((target_name, use_cache, use_file_ast_cache))
        return ("bp", "graph")

    monkeypatch.setattr(app, "ASTCache", _FakeCache)
    monkeypatch.setattr(app, "get_cache_dir", lambda: Path("/tmp/cache"))
    monkeypatch.setattr(app, "load_project", fake_load_project)

    result = app.force_refresh_ast(cfg)

    assert len(cleared) == 2
    assert load_calls == [
        ("TargetA", False, False),
        ("TargetB", False, False),
    ]
    assert result == ("bp", "graph")


def test_show_help_mentions_setup_and_syntax_check(noop_screen, capsys):
    cfg = deepcopy(app.DEFAULT_CONFIG)

    app.show_help(cfg)

    out = capsys.readouterr().out
    assert "Open Setup" in out
    assert "syntax-check" in out
    assert "format-icf" in out
    assert "Tools" in out


def test_syntax_check_command_ok(tmp_path, capsys):
    source_file = tmp_path / "ValidProgram.s"
    source_file.write_text(VALID_SINGLE_FILE, encoding="utf-8")

    exit_code = app.main(["syntax-check", str(source_file)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out.strip() == "OK"
    assert captured.err == ""


def test_cli_entry_point_forwards_sys_argv_without_loading_ast(tmp_path, capsys, monkeypatch):
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


def test_main_blocks_target_dependent_menu_actions_without_targets(noop_screen, monkeypatch, capsys):
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
    monkeypatch.setattr(builtins, "input", make_input(["1", "2", "4", "2", "3", "q", "b", "q"]))

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
    assert "InvalidProgram.s" in captured.err
    assert "Expected one of:" in captured.err
    assert "^" in captured.err


def test_syntax_check_command_prints_warning_for_legacy_sequence_initstep(tmp_path, capsys):
    source_file = tmp_path / "LegacySequenceWarning.s"
    source_file.write_text(
        """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
	SEQUENCE DeleteListContent COORD 0.0, 0.0 OBJSIZE 1.0, 1.0
		SEQSTEP PutArray
		SEQTRANSITION WAIT_FOR True
		SEQSTEP ExtraScan
		ALTERNATIVESEQ
			SEQTRANSITION WAIT_FOR DeleteLineNumber <= ArrayLength
		ALTERNATIVEBRANCH
			SEQTRANSITION WAIT_FOR DeleteLineNumber > ArrayLength
			SEQINITSTEP standBy
			SEQTRANSITION WAIT_FOR DeleteListContent
		ENDALTERNATIVE
	ENDSEQUENCE
ENDDEF (*BasePicture*);
""",
        encoding="utf-8",
    )

    exit_code = app.main(["syntax-check", str(source_file)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out.strip() == "OK"
    assert "WARNING [validation]" in captured.err
    assert "must start with exactly one SEQINITSTEP" in captured.err


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
    monkeypatch.setattr(variables_reporting_module, "analyze_datatype_usage", lambda *_, **__: "report")
    monkeypatch.setattr(variables_reporting_module, "debug_variable_usage", lambda *_, **__: "report")

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


def test_run_variable_analysis_all_analyses_executes_real_analyzers(noop_screen, monkeypatch, capsys):
    project_bp = parser_core_parse_source_text(VALID_SINGLE_FILE)
    graph = SimpleNamespace(
        unavailable_libraries=set(),
        warnings=[],
        source_files=set(),
    )
    monkeypatch.setattr(
        app,
        "_iter_loaded_projects",
        lambda *_args, **_kwargs: iter([("SmokeTarget", project_bp, graph)]),
    )

    app.run_variable_analysis(app.DEFAULT_CONFIG.copy(), None)

    out = capsys.readouterr().out
    assert "=== Target: SmokeTarget ===" in out
    assert "Issues:" in out
    assert "No variable analysis output was produced" not in out


def test_run_variable_analysis_all_reports_lists_empty_categories(noop_screen, monkeypatch, capsys):
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
    assert "Sections:" in out
    assert "  - Unused variables: 0" in out
    assert "Min/Max mapping name mismatches" in out
    assert "Name collisions" in out
    assert "Reset contamination (missing reset writes)" in out
    assert "Implicit latching (missing matching False writes)" not in out
    assert "UI/display-only variables" not in out
    assert out.count("      none") >= 3


def test_run_variable_analysis_all_reports_hide_low_confidence_categories(noop_screen, monkeypatch, capsys):
    from sattlint.models.ast_model import Variable

    issue = VariableIssue(
        kind=app.IssueKind.UI_ONLY,
        module_path=["ProgramA"],
        variable=Variable(name="DisplayValue", datatype="integer"),
        role="localvariable",
    )
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
            issues=[issue],
            visible_kinds=frozenset(ALL_VARIABLE_ANALYSIS_KINDS),
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
    assert "UI/display-only variables" not in out


def test_run_variable_analysis_can_render_low_confidence_category_on_request(noop_screen, monkeypatch, capsys):
    from sattlint.models.ast_model import Variable

    issue = VariableIssue(
        kind=app.IssueKind.UI_ONLY,
        module_path=["ProgramA"],
        variable=Variable(name="DisplayValue", datatype="integer"),
        role="localvariable",
    )
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
            issues=[issue],
            visible_kinds=frozenset(ALL_VARIABLE_ANALYSIS_KINDS),
            include_empty_sections=True,
        ),
    )
    monkeypatch.setattr(
        app,
        "analyze_shadowing",
        lambda *_, **__: make_shadowing_report("ProgramA"),
    )

    app.run_variable_analysis(app.DEFAULT_CONFIG.copy(), {app.IssueKind.UI_ONLY})

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


def test_run_variable_analysis_hides_dependency_validation_warnings(noop_screen, monkeypatch, capsys):
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
