# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownLambdaType=false, reportUnknownArgumentType=false, reportPrivateUsage=false

"""Tests for app config, screen helpers, interactive menus, and CLI entry points."""

import builtins
import ctypes
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from typing import Any, ClassVar, cast

import pytest

from sattline_parser.models.ast_model import BasePicture
from sattlint import _app_graphics_menus as app_graphics_menus_module
from sattlint import app, app_base, app_docs, app_graphics, app_menus
from sattlint.analyzers.framework import AnalyzerSpec, Issue, SimpleReport
from sattlint.analyzers.registry import get_actual_cli_analyzer_keys
from sattlint.models.project_graph import ProjectGraph

from ._app_menus_support import (
    DummyReport,
    make_input,
)
from .helpers import NoOpWriter, RecordingWriter
from .helpers.app_projects import build_mini_project_context


@pytest.fixture
def noop_screen(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SATTLINT_UI", "classic")
    monkeypatch.setattr(app, "clear_screen", lambda: None)
    monkeypatch.setattr(app, "pause", lambda: None)


def test_load_and_save_config(tmp_path, capsys):
    config_path = tmp_path / "config.toml"
    program_dir = tmp_path / "programs"
    program_dir.mkdir()
    (program_dir / "RootProgram.x").write_text("official", encoding="utf-8")

    cfg, created = app_base.load_config(config_path)
    assert created is True
    assert cfg["mode"] == "official"
    assert config_path.exists()

    cfg["program_dir"] = str(program_dir)
    cfg["analyzed_programs_and_libraries"] = ["RootProgram"]
    app_base.save_config(config_path, cfg)
    out = capsys.readouterr().out
    assert "Config saved" in out

    loaded, created = app_base.load_config(config_path)
    assert created is False
    assert loaded["analyzed_programs_and_libraries"] == ["RootProgram"]


def test_save_config_rejects_none(tmp_path):
    config_path = tmp_path / "config.toml"
    cfg = cast(dict[str, object], app_base.DEFAULT_CONFIG.copy())
    cfg["analyzed_programs_and_libraries"] = None
    with pytest.raises(ValueError):
        app_base.save_config(config_path, cfg)


def test_clear_screen_uses_windows_console_helper(monkeypatch):
    calls: list[str] = []
    writer = NoOpWriter()

    monkeypatch.setattr(app_base.os, "name", "nt")
    monkeypatch.setattr(app_base, "_clear_windows_console", lambda: calls.append("clear"))
    monkeypatch.setattr(app_base.sys, "stdout", writer)

    app_base.clear_screen()

    assert calls == ["clear"]


def test_clear_screen_falls_back_to_ansi_when_windows_clear_fails(monkeypatch):
    writer = RecordingWriter()

    def _raise_os_error() -> None:
        raise OSError("clear failed")

    monkeypatch.setattr(app_base.os, "name", "nt")
    monkeypatch.setattr(app_base.os, "system", lambda _command: 1)
    monkeypatch.setattr(app_base, "_clear_windows_console", _raise_os_error)
    monkeypatch.setattr(app_base.sys, "stdout", writer)

    app_base.clear_screen()

    assert writer.writes == ["\033[2J\033[H"]


def test_clear_screen_falls_back_to_cls_before_ansi(monkeypatch):
    calls: list[str] = []
    writer = RecordingWriter()

    def _raise_os_error() -> None:
        raise OSError("clear failed")

    monkeypatch.setattr(app_base.os, "name", "nt")
    monkeypatch.setattr(app_base, "_clear_windows_console", _raise_os_error)
    monkeypatch.setattr(
        app_base.os,
        "system",
        lambda command: calls.append(command) or 0,
    )
    monkeypatch.setattr(app_base.sys, "stdout", writer)

    app_base.clear_screen()

    assert calls == ["cls"]
    assert writer.writes == []


def test_configure_windows_console_api_sets_wide_char_signature():
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
        _fields_: ClassVar[Any] = []

    class _BufferInfo(ctypes.Structure):  # type: ignore[misc]
        _fields_: ClassVar[Any] = []

    kernel32 = _FakeKernel32()

    app_base._configure_windows_console_api(kernel32, _Coord, _BufferInfo)

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


def test_run_checks_forwards_selected_issue_kinds(noop_screen, monkeypatch):
    seen: dict[str, object] = {}

    monkeypatch.setattr(
        app.app_analysis,
        "run_checks",
        lambda cfg, selected_keys, selected_issue_kinds=None, **kwargs: seen.update(
            {
                "cfg": cfg,
                "selected_keys": selected_keys,
                "selected_issue_kinds": selected_issue_kinds,
                "get_enabled_analyzers_fn": kwargs.get("get_enabled_analyzers_fn"),
            }
        ),
    )

    app._run_checks(
        app.DEFAULT_CONFIG.copy(),
        ["sfc"],
        selected_issue_kinds=frozenset({"sfc_parallel_write_race"}),
    )

    assert seen["selected_keys"] == ["sfc"]
    assert seen["selected_issue_kinds"] == frozenset({"sfc_parallel_write_race"})
    assert seen["get_enabled_analyzers_fn"] is app._get_selectable_analyzers


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
    strict_cfg["analysis"]["rule_profiles"]["active"] = "custom-escalate"
    strict_cfg["analysis"]["rule_profiles"]["profiles"]["custom-escalate"] = {
        "description": "Escalate style drift",
        "disabled_rules": [],
        "severity_overrides": {
            "semantic.naming-inconsistent-style": "error",
        },
        "confidence_overrides": {},
    }
    app._run_checks(strict_cfg, None)
    strict_out = capsys.readouterr().out

    assert "semantic.naming-inconsistent-style" in strict_out
    assert "[error | style | semantic.naming-inconsistent-style]" in strict_out
    assert "Suggested fix:" in strict_out
    assert "semantic.loop-output-refactor" in strict_out

    legacy_cfg = deepcopy(app.DEFAULT_CONFIG)
    legacy_cfg["analysis"]["rule_profiles"]["active"] = "custom-suppress"
    legacy_cfg["analysis"]["rule_profiles"]["profiles"]["custom-suppress"] = {
        "description": "Suppress style drift",
        "disabled_rules": [
            "semantic.naming-inconsistent-style",
            "semantic.loop-output-refactor",
        ],
        "severity_overrides": {},
        "confidence_overrides": {},
    }
    app._run_checks(legacy_cfg, None)
    legacy_out = capsys.readouterr().out

    assert "semantic.naming-inconsistent-style" not in legacy_out
    assert "semantic.loop-output-refactor" not in legacy_out
    assert "No issues found." in legacy_out


def test_run_checks_skips_picture_display_paths_for_library_targets(noop_screen, monkeypatch):
    invoked: list[str] = []
    target = SimpleNamespace(header=SimpleNamespace(name="LibraryTarget"))

    def _run_report(context, *, analyzer_key: str) -> SimpleReport:
        invoked.append(analyzer_key)
        return SimpleReport(name=analyzer_key)

    monkeypatch.setattr(
        app,
        "_get_enabled_analyzers",
        lambda: [
            AnalyzerSpec(
                key="picture-display-paths",
                name="PictureDisplay paths",
                description="Synthetic picture display analyzer",
                run=lambda context: _run_report(context, analyzer_key="picture-display-paths"),
            ),
            AnalyzerSpec(
                key="variables",
                name="Variable issues",
                description="Synthetic variables analyzer",
                run=lambda context: _run_report(context, analyzer_key="variables"),
            ),
        ],
    )
    monkeypatch.setattr(
        app,
        "_iter_loaded_projects",
        lambda *_args, **_kwargs: iter([("LibraryTarget", target, SimpleNamespace())]),
    )
    monkeypatch.setattr(app, "_target_is_library", lambda *_args, **_kwargs: True)

    app._run_checks(app.DEFAULT_CONFIG.copy(), None)

    assert invoked == ["variables"]


def test_dump_menu_all_options(noop_screen, monkeypatch, tmp_path):
    cfg = cast(dict[str, object], build_mini_project_context(tmp_path)["cfg"])
    monkeypatch.setattr(app, "get_cache_dir", lambda: tmp_path / "cache-dir")

    dump_calls = []

    def record(name):
        dump_calls.append(name)

    monkeypatch.setattr(app.engine_module, "dump_parse_tree", lambda *_: record("parse"))
    monkeypatch.setattr(app.engine_module, "dump_ast", lambda *_: record("ast"))
    monkeypatch.setattr(app.engine_module, "dump_dependency_graph", lambda *_: record("deps"))
    monkeypatch.setattr(app, "analyze_variables", lambda *_, **__: DummyReport())

    inputs = ["1", "y", "2", "y", "3", "y", "4", "y", "b"]
    monkeypatch.setattr(builtins, "input", make_input(inputs))

    app.dump_menu(cfg)

    assert dump_calls == ["parse", "ast", "deps"]


def test_dump_menu_updates_live_status(noop_screen, monkeypatch, tmp_path):
    cfg = cast(dict[str, object], build_mini_project_context(tmp_path)["cfg"])
    monkeypatch.setattr(app, "get_cache_dir", lambda: tmp_path / "cache-dir")
    updates: list[str] = []

    class FakeLiveStatusLine:
        def __enter__(self):
            return updates.append

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(app.engine_module, "dump_parse_tree", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(app.app_menus_module.console_module, "live_status_line", lambda: FakeLiveStatusLine())
    monkeypatch.setattr(builtins, "input", make_input(["1", "y", "b"]))

    app.dump_menu(cfg)

    assert "Dump parse tree: TargetA" in updates


def test_dump_menu_variable_report_passes_library_target_flag(noop_screen, monkeypatch, tmp_path):
    cfg = cast(dict[str, object], build_mini_project_context(tmp_path)["cfg"])
    monkeypatch.setattr(app, "get_cache_dir", lambda: tmp_path / "cache-dir")
    captured_kwargs: dict[str, object] = {}

    def analyze_variables_stub(*_args, **kwargs):
        captured_kwargs.update(kwargs)
        return DummyReport()

    monkeypatch.setattr(app, "analyze_variables", analyze_variables_stub)
    monkeypatch.setattr(app, "_target_is_library", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(builtins, "input", make_input(["4", "y", "b"]))

    app.dump_menu(cfg)

    assert captured_kwargs["analyzed_target_is_library"] is True


def test_dump_menu_can_use_injected_choice_handler(noop_screen, monkeypatch, tmp_path):
    cfg = cast(dict[str, object], build_mini_project_context(tmp_path)["cfg"])
    monkeypatch.setattr(app, "get_cache_dir", lambda: tmp_path / "cache-dir")
    seen: dict[str, object] = {}

    monkeypatch.setattr(
        app,
        "choose_menu_option",
        lambda title, options, *, intro=None, note=None: (
            seen.update({"title": title, "intro": intro, "note": note, "option_count": len(options)}) or "b"
        ),
    )

    app.dump_menu(cfg)

    assert seen["title"] == "Diagnostics & dumps"
    assert seen["option_count"] == 6


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
        "12",
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
    assert cfg["telemetry"]["enabled"] is True
    assert "path" not in cfg["telemetry"]


def test_config_menu_can_update_telemetry_without_touching_other_settings(noop_screen, monkeypatch, tmp_path):
    cfg = deepcopy(app.DEFAULT_CONFIG)
    monkeypatch.setattr(
        builtins,
        "input",
        make_input(
            [
                "12",
                "y",
                "b",
            ]
        ),
    )

    dirty = app.config_menu(cfg)

    assert dirty is True
    assert cfg["telemetry"] == {"enabled": True}
    assert cfg["mode"] == app.DEFAULT_CONFIG["mode"]


def test_config_menu_can_use_injected_choice_handler(noop_screen, monkeypatch):
    cfg = deepcopy(app.DEFAULT_CONFIG)
    choices = iter(["12", "b"])
    seen: dict[str, object] = {}

    monkeypatch.setattr(app, "confirm", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(
        app,
        "choose_menu_option",
        lambda title, options, *, intro=None, note=None: (
            seen.update({"title": title, "intro": intro, "note": note, "option_count": len(options)}) or next(choices)
        ),
    )

    dirty = app.config_menu(cfg)

    assert dirty is True
    assert cfg["telemetry"] == {"enabled": True}
    assert seen["title"] == "Setup"
    assert seen["option_count"] == 15


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
        app.app_graphics.graphics_reports_module, "telemetry_output_path", lambda: tmp_path / "telemetry.jsonl"
    )
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
    assert "Telemetry" in out
    assert "enabled" in out
    assert "path" in out
    assert str(tmp_path / "telemetry.jsonl") in out
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


def test_graphics_rules_menu_reports_explicit_save_failure(noop_screen, monkeypatch, tmp_path, capsys):
    rules_path = tmp_path / "graphics_rules.json"
    rules = {"schema_version": 1, "rules": []}

    monkeypatch.setattr(app, "get_graphics_rules_path", lambda: rules_path)
    monkeypatch.setattr(app, "load_graphics_rules", lambda _path=None: (rules, False))
    monkeypatch.setattr(
        app,
        "save_graphics_rules",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(PermissionError("read-only filesystem")),
    )
    monkeypatch.setattr(builtins, "input", make_input(["3", "", "b"]))

    app.graphics_rules_menu()

    out = capsys.readouterr().out
    assert f"Failed to save graphics rules to {rules_path}" in out
    assert "read-only filesystem" in out


def test_graphics_rules_menu_stays_open_when_save_before_back_fails(noop_screen, monkeypatch, tmp_path, capsys):
    rules_path = tmp_path / "graphics_rules.json"
    rules = {"schema_version": 1, "rules": []}
    save_attempts: list[str] = []
    confirm_answers = iter([True, False])

    monkeypatch.setattr(app, "get_graphics_rules_path", lambda: rules_path)
    monkeypatch.setattr(app, "load_graphics_rules", lambda _path=None: (rules, False))
    monkeypatch.setattr(
        app,
        "save_graphics_rules",
        lambda *_args, **_kwargs: (save_attempts.append("save"), (_ for _ in ()).throw(PermissionError("locked")))[1],
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
    monkeypatch.setattr(app, "confirm", lambda *_args, **_kwargs: next(confirm_answers))
    monkeypatch.setattr(builtins, "input", make_input(["1", "", "b", "b"]))

    app.graphics_rules_menu()

    out = capsys.readouterr().out
    assert save_attempts == ["save"]
    assert f"Failed to save graphics rules to {rules_path}" in out
    assert "locked" in out


def test_prompt_optional_float_list_raises_skipped_on_blank(monkeypatch):
    monkeypatch.setattr(builtins, "input", make_input([""]))

    with pytest.raises(app_graphics.OptionalPromptSkipped):
        app_graphics.prompt_optional_float_list("Invocation coords", 5, pause_fn=lambda: None)


def test_prompt_optional_float_list_raises_validation_error_on_non_numeric(monkeypatch):
    pauses: list[str] = []
    monkeypatch.setattr(builtins, "input", make_input(["x,1,2,3,4"]))

    with pytest.raises(app_graphics.OptionalPromptValidationError):
        app_graphics.prompt_optional_float_list("Invocation coords", 5, pause_fn=lambda: pauses.append("pause"))

    assert pauses == ["pause"]


def test_prompt_optional_bool_raises_validation_error_on_invalid_value(monkeypatch):
    monkeypatch.setattr(builtins, "input", make_input(["maybe"]))

    with pytest.raises(app_graphics.OptionalPromptValidationError):
        app_graphics.prompt_optional_bool("Invocation zoomable")


def test_pick_or_prompt_graphics_rule_selector_value_raises_on_blank_manual_input(monkeypatch):
    monkeypatch.setattr(builtins, "input", make_input([""]))

    with pytest.raises(app_graphics.RequiredPromptValidationError):
        app_graphics.pick_or_prompt_graphics_rule_selector_value(
            "unit_structure_path",
            "single",
            cfg=app.DEFAULT_CONFIG.copy(),
            discover_graphics_rule_selector_options_fn=lambda *_args, **_kwargs: [],
        )


def test_prompt_graphics_rule_definition_returns_none_on_missing_required_selector(monkeypatch):
    pauses: list[str] = []
    monkeypatch.setattr(builtins, "input", make_input(["1"]))

    rule = app_graphics.prompt_graphics_rule_definition_with_config(
        app.DEFAULT_CONFIG.copy(),
        prompt_fn=lambda *_args, **_kwargs: "",
        pause_fn=lambda: pauses.append("pause"),
        pick_or_prompt_graphics_rule_selector_value_fn=(
            lambda *_args, **_kwargs: (_ for _ in ()).throw(
                app_graphics.RequiredPromptValidationError("Selector path is required")
            )
        ),
    )

    assert rule is None
    assert pauses == ["pause"]


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


def test_discover_graphics_rule_selector_options_propagates_type_errors() -> None:
    cfg = deepcopy(app.DEFAULT_CONFIG)
    cfg["analyzed_programs_and_libraries"] = ["TargetA"]

    with pytest.raises(TypeError, match="bad entries"):
        app_graphics_menus_module.discover_graphics_rule_selector_options(
            cfg,
            selector_field="unit_structure_path",
            module_kind="single",
            has_analyzed_targets_fn=lambda _cfg: True,
            iter_loaded_projects_fn=lambda _cfg: iter([("TargetA", SimpleNamespace(), SimpleNamespace())]),
            collect_graphics_layout_entries_for_target_fn=lambda *_args: (_ for _ in ()).throw(
                TypeError("bad entries")
            ),
        )


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


def test_run_graphics_rules_validation_updates_live_status(noop_screen, monkeypatch):
    cfg = deepcopy(app.DEFAULT_CONFIG)
    cfg["analyzed_programs_and_libraries"] = ["TargetA"]
    graph = SimpleNamespace(unavailable_libraries=set())
    updates: list[str] = []

    class FakeLiveStatusLine:
        def __enter__(self):
            return updates.append

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(
        app,
        "load_graphics_rules",
        lambda _path=None: ({"schema_version": 1, "rules": [{"module_name": "L1"}]}, False),
    )
    monkeypatch.setattr(
        app,
        "_iter_loaded_projects",
        lambda *_args, **_kwargs: iter([("TargetA", SimpleNamespace(), graph)]),
    )
    monkeypatch.setattr(
        app,
        "_collect_graphics_layout_entries_for_target",
        lambda *_args, **_kwargs: [],
    )
    monkeypatch.setattr(app.app_graphics_module.console_module, "live_status_line", lambda: FakeLiveStatusLine())

    app.run_graphics_rules_validation(cfg)

    assert updates == [
        "Graphics rules: collecting layout entries for TargetA",
        "Graphics rules: validating TargetA",
    ]


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


def test_documentation_menu_scope_by_moduletype(monkeypatch):
    cfg = deepcopy(app.DEFAULT_CONFIG)
    app_docs.set_documentation_unit_selection(mode="all")
    inputs = ["4", "ApplTank, XDilute_221X251XY", "b"]
    monkeypatch.setattr(builtins, "input", make_input(inputs))

    dirty = app_docs.documentation_menu(
        cfg,
        clear_screen_fn=lambda: None,
        print_menu_fn=app._print_menu,
        menu_option_factory=lambda key, label, description: app.MenuOption(key, label, description),
        quit_app_fn=app.quit_app,
        pause_fn=lambda: None,
        split_csv_values_fn=app._split_csv_values,
        iter_loaded_projects_fn=app._iter_loaded_projects,
        prompt_fn=app.prompt,
    )
    selection = app_docs.get_documentation_unit_selection()

    assert dirty is True
    assert selection["mode"] == "moduletype_names"
    assert selection["moduletype_names"] == [
        "ApplTank",
        "XDilute_221X251XY",
    ]


def test_main_menu_all_options(noop_screen, monkeypatch):
    cfg = app.DEFAULT_CONFIG.copy()
    cfg["analyzed_programs_and_libraries"] = ["TargetA"]

    monkeypatch.delenv("SATTLINT_UI", raising=False)
    monkeypatch.setattr(app, "load_config", lambda *_: (cfg, False))
    monkeypatch.setattr(app, "self_check", lambda *_: pytest.fail("textual startup should skip terminal self-check"))

    calls = []

    monkeypatch.setattr(
        app, "analysis_menu", lambda *_: pytest.fail("legacy analysis menu should not run during textual startup")
    )
    monkeypatch.setattr(
        app,
        "documentation_menu",
        lambda *_: pytest.fail("legacy documentation menu should not run during textual startup"),
    )
    monkeypatch.setattr(
        app, "config_menu", lambda *_: pytest.fail("legacy config menu should not run during textual startup")
    )
    monkeypatch.setattr(
        app, "tools_menu", lambda *_: pytest.fail("legacy tools menu should not run during textual startup")
    )
    monkeypatch.setattr(
        app, "show_help", lambda *_: pytest.fail("legacy help menu should not run during textual startup")
    )
    monkeypatch.setattr(
        app, "save_config", lambda *_: pytest.fail("startup should not save config before the textual shell runs")
    )
    monkeypatch.setattr(app, "run_interactive_session", lambda *_args, **_kwargs: calls.append("session"))

    exit_code = app.main()

    assert exit_code == 0
    assert calls == ["session"]


def test_main_menu_stays_open_on_save_before_quit_error(noop_screen, monkeypatch, tmp_path, capsys):
    cfg = app.DEFAULT_CONFIG.copy()
    cfg["analyzed_programs_and_libraries"] = ["TargetA"]
    save_calls: list[str] = []
    session_calls: list[str] = []

    monkeypatch.delenv("SATTLINT_UI", raising=False)
    monkeypatch.setattr(app, "CONFIG_PATH", tmp_path / "config.toml")
    monkeypatch.setattr(app, "load_config", lambda *_: (cfg, False))
    monkeypatch.setattr(app, "self_check", lambda *_: pytest.fail("textual startup should skip terminal self-check"))
    monkeypatch.setattr(app, "analysis_menu", lambda *_: None)
    monkeypatch.setattr(app, "documentation_menu", lambda *_: False)
    monkeypatch.setattr(app, "config_menu", lambda *_: True)
    monkeypatch.setattr(app, "tools_menu", lambda *_: None)
    monkeypatch.setattr(app, "show_help", lambda *_: None)

    def fail_save(*_args, **_kwargs):
        save_calls.append("save")
        raise PermissionError("read-only filesystem")

    monkeypatch.setattr(app, "save_config", fail_save)
    monkeypatch.setattr(app, "run_interactive_session", lambda *_args, **_kwargs: session_calls.append("session"))

    exit_code = app.main()

    out = capsys.readouterr().out
    assert exit_code == 0
    assert session_calls == ["session"]
    assert save_calls == []
    assert out == ""


def test_main_menu_can_use_injected_choice_handler(noop_screen, monkeypatch):
    cfg = app.DEFAULT_CONFIG.copy()
    cfg["analyzed_programs_and_libraries"] = ["TargetA"]
    calls: list[str] = []

    monkeypatch.delenv("SATTLINT_UI", raising=False)
    monkeypatch.setattr(app, "load_config", lambda *_: (cfg, False))
    monkeypatch.setattr(app, "self_check", lambda *_: pytest.fail("textual startup should skip terminal self-check"))
    monkeypatch.setattr(
        app, "analysis_menu", lambda *_: pytest.fail("legacy analysis menu should not run during textual startup")
    )
    monkeypatch.setattr(
        app,
        "documentation_menu",
        lambda *_: pytest.fail("legacy documentation menu should not run during textual startup"),
    )
    monkeypatch.setattr(
        app, "config_menu", lambda *_: pytest.fail("legacy config menu should not run during textual startup")
    )
    monkeypatch.setattr(
        app, "tools_menu", lambda *_: pytest.fail("legacy tools menu should not run during textual startup")
    )
    monkeypatch.setattr(
        app, "show_help", lambda *_: pytest.fail("legacy help menu should not run during textual startup")
    )
    monkeypatch.setattr(
        app,
        "choose_menu_option",
        lambda *_args, **_kwargs: pytest.fail("legacy menu choice handler should not run during textual startup"),
    )
    monkeypatch.setattr(app, "run_interactive_session", lambda *_args, **_kwargs: calls.append("session"))

    exit_code = app.main()

    assert exit_code == 0
    assert calls == ["session"]


def test_tools_menu_all_options(noop_screen, monkeypatch):
    cfg = deepcopy(app.DEFAULT_CONFIG)
    cfg["analyzed_programs_and_libraries"] = ["TargetA"]
    calls: list[str] = []

    monkeypatch.setattr(app, "self_check", lambda *_: calls.append("self-check") or True)
    monkeypatch.setattr(app, "dump_menu", lambda *_: calls.append("dump"))
    monkeypatch.setattr(app, "run_source_diff_report", lambda *_: calls.append("source-diff"))
    monkeypatch.setattr(app, "refresh_analysis_caches", lambda *_: calls.append("refresh"))
    monkeypatch.setattr(builtins, "input", make_input(["1", "2", "3", "4", "y", "b"]))

    app.tools_menu(cfg)

    assert calls == ["self-check", "dump", "source-diff", "refresh"]


def test_tools_menu_can_use_injected_choice_handler(noop_screen, monkeypatch):
    cfg = deepcopy(app.DEFAULT_CONFIG)
    cfg["analyzed_programs_and_libraries"] = ["TargetA"]
    calls: list[str] = []
    seen: dict[str, object] = {}
    choices = iter(["1", "b"])

    monkeypatch.setattr(app, "self_check", lambda *_: calls.append("self-check") or True)
    monkeypatch.setattr(app, "pause", lambda: calls.append("pause"))
    monkeypatch.setattr(
        app,
        "choose_menu_option",
        lambda title, options, *, intro=None, note=None: (
            seen.update({"title": title, "intro": intro, "note": note, "option_count": len(options)}) or next(choices)
        ),
    )

    app.tools_menu(cfg)

    assert calls == ["self-check", "pause"]
    assert seen["title"] == "Tools"
    assert seen["option_count"] == 6


def test_tools_menu_does_not_append_duplicate_refresh_message(noop_screen, monkeypatch):
    cfg = deepcopy(app.DEFAULT_CONFIG)
    cfg["analyzed_programs_and_libraries"] = ["TargetA"]
    outputs: list[str] = []

    monkeypatch.setattr(app_menus, "emit_output", lambda message: outputs.append(message))
    monkeypatch.setattr(app, "refresh_analysis_caches", lambda *_: outputs.append("OK AST cache refreshed"))
    monkeypatch.setattr(builtins, "input", make_input(["4", "y", "b"]))

    app.tools_menu(cfg)

    assert outputs.count("OK AST cache refreshed") == 1
