"""Focused app config, self-check, and ICF command tests."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path, PosixPath
from types import SimpleNamespace
from typing import ClassVar

import pytest

from sattlint import app
from sattlint import config as config_module
from sattlint import graphics_rules as graphics_rules_module


@pytest.fixture
def noop_screen(monkeypatch):
    monkeypatch.setattr(app, "clear_screen", lambda: None)
    monkeypatch.setattr(app, "pause", lambda: None)


def test_validate_config_reports_key_mode_analysis_and_documentation_errors():
    result = config_module.validate_config(
        {
            "invalid_key": True,
            "mode": "bad_mode",
            "analysis": "bad",
            "telemetry": "bad",
            "documentation": "bad",
        }
    )

    assert result.passed is False
    assert {error.key_path for error in result.errors} == {
        "invalid_key",
        "mode",
        "analysis",
        "telemetry",
        "documentation",
    }


def test_validate_config_reports_unknown_telemetry_keys_and_invalid_shapes():
    result = config_module.validate_config(
        {
            "telemetry": {
                "extra": True,
                "enabled": "yes",
                "path": "legacy.jsonl",
            }
        }
    )

    assert result.passed is False
    assert {error.key_path for error in result.errors} == {
        "telemetry.extra",
        "telemetry.enabled",
        "telemetry.path",
    }


def test_validate_config_reports_unknown_analysis_naming_targets_and_style():
    result = config_module.validate_config(
        {
            "analysis": {
                "unknown_analyzer": {},
                "naming": {
                    "unknown_target": {"style": "snake"},
                    "variables": {"style": "bad_style"},
                },
            }
        }
    )

    assert result.passed is False
    assert {error.key_path for error in result.errors} == {
        "analysis.unknown_analyzer",
        "analysis.naming.unknown_target",
        "analysis.naming.variables.style",
    }


def test_validate_config_passes_valid_config_and_serializes_result():
    valid = config_module.validate_config(
        {
            "mode": "draft",
            "telemetry": {"enabled": True},
            "analysis": {"naming": {"variables": {"style": "snake"}}},
        }
    )
    invalid = config_module.validate_config({"bad_key": True})

    assert valid.passed is True
    assert valid.errors == ()
    assert invalid.to_dict() == {
        "passed": False,
        "errors": [
            {
                "key_path": "bad_key",
                "message": invalid.errors[0].message,
            }
        ],
    }


def test_load_config_warns_on_invalid_keys_and_normalizes_legacy_documentation_keys(tmp_path, capsys):
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        "\n".join(
            [
                "bad_key = true",
                "ignore_ABB_lib = true",
                "[documentation.classifications.equipment_modules]",
                'moduletype_name_contains = ["Tank"]',
                'descendant_moduletype_label_equals = ["nnestruct:EquipModCoordinate"]',
            ]
        ),
        encoding="utf-8",
    )

    loaded, created = config_module.load_config(config_path)

    out = capsys.readouterr().out
    assert created is False
    assert "Config warning [bad_key]" in out
    assert "ignore_ABB_lib" not in loaded
    assert loaded["documentation"]["classifications"]["em"]["name_contains"] == ["Tank"]
    assert loaded["documentation"]["classifications"]["em"]["desc_label_equals"] == ["nnestruct:EquipModCoordinate"]
    assert "equipment_modules" not in loaded["documentation"]["classifications"]


def test_load_config_backfills_missing_telemetry_section_without_overwriting_existing_keys(tmp_path):
    config_path = tmp_path / "config.toml"
    config_path.write_text('mode = "draft"\nprogram_dir = "programs"', encoding="utf-8")

    loaded, created = config_module.load_config(config_path)

    persisted_text = config_path.read_text(encoding="utf-8")
    assert created is False
    assert loaded["mode"] == "draft"
    assert loaded["program_dir"] == "programs"
    assert loaded["telemetry"] == {"enabled": False}
    assert 'mode = "draft"' in persisted_text
    assert 'program_dir = "programs"' in persisted_text
    assert "[telemetry]" in persisted_text
    assert "enabled = false" in persisted_text
    assert 'path = ""' not in persisted_text


def test_load_config_strips_legacy_telemetry_path_from_existing_file(tmp_path):
    config_path = tmp_path / "config.toml"
    config_path.write_text('[telemetry]\nenabled = true\npath = "legacy.jsonl"\n', encoding="utf-8")

    loaded, created = config_module.load_config(config_path)

    persisted_text = config_path.read_text(encoding="utf-8")
    assert created is False
    assert loaded["telemetry"] == {"enabled": True}
    assert "enabled = true" in persisted_text
    assert 'path = "legacy.jsonl"' not in persisted_text


def test_config_io_helper_guards_cover_empty_legacy_text_windows_path_and_non_table_save(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_io_module = config_module._config_io_module

    class _NonTableConfig:
        def get(self, _key: str, _default: object | None = None) -> object | None:
            return None

    assert config_io_module._strip_legacy_telemetry_path("") == ""

    monkeypatch.setattr(config_io_module.os, "name", "nt", raising=False)
    monkeypatch.setattr(config_io_module, "Path", PosixPath)
    monkeypatch.setenv("APPDATA", str(tmp_path / "AppData"))
    assert config_module.get_config_path() == tmp_path / "AppData" / "sattlint" / "config.toml"

    monkeypatch.setattr(config_io_module, "deepcopy", lambda _value: _NonTableConfig())
    with pytest.raises(ValueError, match="Config serialization must produce a table/object"):
        config_module.save_config(tmp_path / "bad-config.toml", {"mode": "draft"})


def test_config_io_helper_branches_cover_missing_load_passthrough_and_save_guards(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config_io_module = config_module._config_io_module
    config_path = tmp_path / "config.toml"

    loaded, created = config_module.load_config(config_path)

    out = capsys.readouterr().out
    assert created is True
    assert loaded["telemetry"] == {"enabled": False}
    assert config_path.exists()
    assert "No config found, creating default" in out

    unchanged_cfg = {"telemetry": {"enabled": True}}
    config_path.write_text("[telemetry]\nenabled = true\n", encoding="utf-8")
    assert config_io_module._normalize_telemetry_section(config_path, unchanged_cfg) == unchanged_cfg

    save_path = tmp_path / "saved-config.toml"
    config_module.save_config(save_path, {"mode": "draft", "telemetry": {"enabled": True, "path": "old.jsonl"}})
    assert 'path = "old.jsonl"' not in save_path.read_text(encoding="utf-8")

    with pytest.raises(ValueError, match="Cannot serialize None"):
        config_module.save_config(tmp_path / "invalid-config.toml", {"mode": None})


def test_target_exists_honors_mode_and_available_directories(tmp_path):
    program_dir = tmp_path / "programs"
    abb_dir = tmp_path / "abb"
    other_lib = tmp_path / "lib"
    for directory in (program_dir, abb_dir, other_lib):
        directory.mkdir()

    (program_dir / "DraftOnly.s").write_text("draft", encoding="utf-8")
    (abb_dir / "OfficialOnly.x").write_text("official", encoding="utf-8")
    (other_lib / "Shared.x").write_text("shared", encoding="utf-8")

    draft_cfg = {
        "program_dir": str(program_dir),
        "ABB_lib_dir": str(abb_dir),
        "other_lib_dirs": [str(other_lib)],
        "mode": "draft",
    }
    official_cfg = {**draft_cfg, "mode": "official"}

    assert config_module.target_exists("DraftOnly", draft_cfg) is True
    assert config_module.target_exists("DraftOnly", official_cfg) is False
    assert config_module.target_exists("OfficialOnly", official_cfg) is True
    assert config_module.target_exists("Shared", official_cfg) is True


def test_validate_effective_config_reports_unresolved_targets_after_defaults_merge(tmp_path):
    for directory_name in ("programs", "abb", "lib"):
        (tmp_path / directory_name).mkdir()

    cfg = deepcopy(app.DEFAULT_CONFIG)
    cfg.update(
        {
            "program_dir": str(tmp_path / "programs"),
            "ABB_lib_dir": str(tmp_path / "abb"),
            "other_lib_dirs": [str(tmp_path / "lib")],
            "analyzed_programs_and_libraries": ["MissingTarget"],
        }
    )

    result = config_module.validate_effective_config(cfg)

    assert result.passed is False
    assert result.errors == (
        config_module.ConfigValidationError(
            key_path="analyzed_programs_and_libraries[0]",
            message="MissingTarget (not found)",
        ),
    )


def test_config_helpers_normalize_legacy_conflicts_and_serialize_paths(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "AppData"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg-config"))

    normalized = config_module._normalize_documentation_rule_keys(
        {
            "documentation": {
                "classifications": {
                    "operations": {"moduletype_label_equals": ["LegacyCategoryRule"]},
                    "ops": {
                        "moduletype_label_equals": ["LegacyRule"],
                        "label_equals": ["ModernRule"],
                    },
                }
            }
        }
    )
    config_path = config_module.get_config_path()
    save_path = tmp_path / "saved-config.toml"
    save_cfg = {
        "program_dir": tmp_path / "programs",
        "ABB_lib_dir": tmp_path / "abb",
        "other_lib_dirs": (tmp_path / "lib-a", tmp_path / "lib-b"),
        "documentation": {"classifications": {"ops": {"label_equals": ["ModernRule"]}}},
    }

    config_module.save_config(save_path, save_cfg)

    saved_text = save_path.read_text(encoding="utf-8")
    assert "operations" not in normalized["documentation"]["classifications"]
    assert normalized["documentation"]["classifications"]["ops"]["label_equals"] == ["ModernRule"]
    expected_config_path = (
        tmp_path / "AppData" / "sattlint" / "config.toml"
        if config_module.os.name == "nt"
        else tmp_path / "xdg-config" / "sattlint" / "config.toml"
    )
    assert config_path == expected_config_path
    assert config_path.parent.is_dir()
    assert 'program_dir = "' in saved_text
    assert "programs" in saved_text
    assert "lib-a" in saved_text
    assert (
        config_module.target_exists(
            "MissingTarget",
            {
                "program_dir": str(tmp_path / "missing-programs"),
                "ABB_lib_dir": str(tmp_path / "missing-abb"),
                "other_lib_dirs": [str(tmp_path / "missing-lib")],
                "mode": "official",
            },
        )
        is False
    )


def test_config_helper_branches_cover_defaults_and_deduplication() -> None:
    helper_module = config_module._config_validation_module

    assert helper_module._object_list(("A", "B")) == ["A", "B"]
    assert helper_module._object_list("not-a-sequence") == []

    assert helper_module._normalize_documentation_rule_keys({"analysis": {}}) == {"analysis": {}}
    assert helper_module._normalize_documentation_rule_keys({"documentation": {}}) == {"documentation": {}}

    normalized = helper_module._normalize_documentation_rule_keys(
        {
            "documentation": {
                "classifications": {
                    "ops": ["not-a-dict"],
                }
            }
        }
    )
    assert normalized["documentation"]["classifications"]["ops"] == ["not-a-dict"]

    default_docs = helper_module.get_documentation_config()
    assert default_docs == app.DEFAULT_CONFIG["documentation"]

    duplicate_error = helper_module.ConfigValidationError(key_path="analysis", message="duplicate")
    merged = helper_module._merge_validation_results(
        helper_module.ConfigValidationResult(passed=False, errors=(duplicate_error,)),
        helper_module.ConfigValidationResult(passed=False, errors=(duplicate_error,)),
    )

    assert merged == helper_module.ConfigValidationResult(passed=False, errors=(duplicate_error,))


def test_self_check_reports_top_level_section_shapes_and_valid_graphics_rules(tmp_path, monkeypatch, capsys):
    readable_dir = tmp_path / "readable"
    readable_dir.mkdir()
    graphics_rules_path = tmp_path / "graphics-rules.json"
    graphics_rules_path.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(config_module, "get_graphics_rules_path", lambda: graphics_rules_path)
    monkeypatch.setattr(
        graphics_rules_module, "load_graphics_rules", lambda *_args, **_kwargs: ({"rules": [1, 2]}, False)
    )
    monkeypatch.setattr(config_module.os, "access", lambda path, mode: Path(path) != readable_dir)

    cfg = deepcopy(app.DEFAULT_CONFIG)
    cfg.update(
        {
            "program_dir": str(readable_dir),
            "ABB_lib_dir": "",
            "icf_dir": "",
            "other_lib_dirs": [str(readable_dir)],
            "documentation": "bad",
            "analysis": "bad",
        }
    )

    ok = config_module.self_check(cfg)

    out = capsys.readouterr().out
    assert ok is False
    assert "program_dir not readable" in out
    assert "other_lib_dirs: " in out
    assert "documentation must be a table/object" in out
    assert "analysis must be a table/object" in out
    assert "graphics_rules_path:" in out
    assert "2 rules" in out


def test_self_check_reports_nested_documentation_and_analysis_shape_errors(tmp_path, monkeypatch, capsys):
    graphics_rules_path = tmp_path / "graphics-rules.json"
    monkeypatch.setattr(config_module, "get_graphics_rules_path", lambda: graphics_rules_path)

    cfg = deepcopy(app.DEFAULT_CONFIG)
    cfg.update(
        {
            "documentation": {"classifications": {"ops": "bad"}},
            "analysis": {"sfc": "bad", "naming": "bad"},
        }
    )

    bad_ok = config_module.self_check(cfg)
    bad_out = capsys.readouterr().out

    cfg["documentation"] = {"classifications": {}}
    cfg["analysis"] = {
        "sfc": {"mutually_exclusive_steps": "bad", "step_contracts": []},
        "naming": {
            "variables": {"label_equals": ["Unused"]},
            "modules": {},
            "instances": {},
        },
    }

    empty_ok = config_module.self_check(cfg)
    empty_out = capsys.readouterr().out

    assert bad_ok is False
    assert "documentation.classifications.ops must be a table/object" in bad_out
    assert "analysis.sfc must be a table/object" in bad_out
    assert "analysis.naming must be a table/object" in bad_out
    assert "graphics_rules_path not created yet" in bad_out
    assert empty_ok is False
    assert "documentation.classifications must be a non-empty table/object" in empty_out
    assert "analysis.sfc.mutually_exclusive_steps must be a list" in empty_out
    assert "analysis.sfc.step_contracts must be a table/object" in empty_out


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


def test_self_check_reports_invalid_nested_config_and_graphics_rule_errors(tmp_path, monkeypatch, capsys):
    graphics_rules_path = tmp_path / "graphics-rules.json"
    graphics_rules_path.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(config_module, "get_graphics_rules_path", lambda: graphics_rules_path)
    monkeypatch.setattr(
        graphics_rules_module,
        "load_graphics_rules",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("broken rules")),
    )
    monkeypatch.setattr(config_module, "target_exists", lambda *_args, **_kwargs: False)

    cfg = deepcopy(app.DEFAULT_CONFIG)
    cfg.pop("mode")
    cfg.update(
        {
            "analyzed_programs_and_libraries": ["MissingTarget"],
            "program_dir": str(tmp_path / "missing-programs"),
            "ABB_lib_dir": "",
            "icf_dir": str(tmp_path / "missing-icf"),
            "other_lib_dirs": [str(tmp_path / "missing-other")],
            "documentation": {
                "classifications": {
                    "unknown": {},
                    "ops": {
                        "desc_label_equals": "not-a-list",
                        "label_equals": [1],
                    },
                }
            },
            "analysis": {
                "sfc": {
                    "mutually_exclusive_steps": "bad",
                    "step_contracts": {
                        "": {},
                        "StepA": {
                            "required_enter_writes": "bad",
                            "required_exit_writes": [1],
                        },
                        "StepB": "bad",
                    },
                },
                "naming": {
                    "variables": {"style": "bad", "allow": "bad"},
                    "modules": "bad",
                    "instances": {"allow": [1]},
                },
            },
        }
    )

    ok = config_module.self_check(cfg)

    out = capsys.readouterr().out
    assert ok is False
    assert "Missing config key: mode" in out
    assert "program_dir does not exist" in out
    assert "ABB_lib_dir not set" in out
    assert "icf_dir does not exist" in out
    assert "other_lib_dirs entry missing" in out
    assert "MissingTarget (not found)" in out
    assert "documentation.classifications.unknown is not a supported category" in out
    assert "documentation.classifications.ops.desc_label_equals must be a list of strings" in out
    assert "documentation.classifications.ops.label_equals must be a list of strings" in out
    assert "analysis.sfc.mutually_exclusive_steps must be a list" in out
    assert "analysis.sfc.step_contracts keys must be non-empty strings" in out
    assert "analysis.sfc.step_contracts.StepA.required_enter_writes must be a list of strings" in out
    assert "analysis.sfc.step_contracts.StepA.required_exit_writes must be a list of strings" in out
    assert "analysis.sfc.step_contracts.StepB must be a table/object" in out
    assert "analysis.naming.variables.style must be one of" in out
    assert "analysis.naming.variables.allow must be a list of strings" in out
    assert "analysis.naming.modules must be a table/object" in out
    assert "analysis.naming.instances.allow must be a list of strings" in out
    assert "graphics_rules_path invalid" in out


def test_main_pauses_when_initial_ast_check_fails(monkeypatch):
    cfg = deepcopy(app.DEFAULT_CONFIG)
    cfg["analyzed_programs_and_libraries"] = ["Broken"]
    calls: list[str] = []

    monkeypatch.setattr(app, "load_config", lambda *_: (cfg, False))
    monkeypatch.setattr(app, "apply_debug", lambda *_: None)
    monkeypatch.setattr(app, "self_check", lambda *_: True)
    monkeypatch.setattr(app, "ensure_ast_cache", lambda *_: False)
    monkeypatch.setattr(app, "pause", lambda: calls.append("pause"))
    monkeypatch.setattr(
        app.app_menus_module,
        "run_main_loop",
        lambda *_args, **_kwargs: calls.append("menu"),
    )

    exit_code = app.main()

    assert exit_code == 0
    assert calls == ["pause", "menu"]
