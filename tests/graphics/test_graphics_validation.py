from pathlib import Path
from typing import Any

import pytest
from lsprotocol.types import DiagnosticSeverity

from sattlint import app
from sattlint.engine import CodeMode, resolve_graphics_companion_path, validate_single_file_syntax
from sattlint.graphics_rules import (
    _collect_mismatches,
    _entry_rule_kind,
    _normalize_module_kind,
    _normalize_rule,
    _normalized_rule_name,
    _populated_path_selectors,
    _rule_matches_entry,
    _rule_selector_key,
    get_graphics_rules_path,
    load_graphics_rules,
    normalize_graphics_rules,
    remove_graphics_rule,
    save_graphics_rules,
    upsert_graphics_rule,
    validate_graphics_layout_entries,
)
from sattlint.graphics_validation import validate_graphics_text
from sattlint_lsp.server import collect_syntax_diagnostics

VALID_SINGLE_FILE = """"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ENDDEF (*BasePicture*);
"""


def _write_source_file(tmp_path: Path, name: str) -> Path:
    file_path = tmp_path / name
    file_path.write_text(VALID_SINGLE_FILE, encoding="utf-8")
    return file_path


def _write_graphics_file(tmp_path: Path, name: str, row: str) -> Path:
    content = f"""" Syntax version 2.23, date: 2026-04-22-00:00:00.000 N "

 5
 None  True   0.00000E+00 0.00000E+00
  3.00000E-01 2.00000E-01
 9
 2
 None 0  Lit 9 2 -1     0
 {row}
 None  True
 t
           0
"""
    file_path = tmp_path / name
    file_path.write_text(content, encoding="utf-8")
    return file_path


def test_validate_graphics_text_warns_for_unverified_scr_asset(tmp_path):
    file_path = _write_graphics_file(tmp_path, "Panel.g", "0 scr:missing_asset.wmf")

    result = validate_graphics_text(file_path.read_text(encoding="utf-8"), file_path)

    assert result.errors == ()
    assert len(result.warnings) == 1
    assert "could not be verified" in result.warnings[0].message


def test_validate_single_file_syntax_reports_graphics_error_for_empty_scr_alias(tmp_path):
    file_path = _write_graphics_file(tmp_path, "BrokenPanel.g", "0 scr:")

    result = validate_single_file_syntax(file_path)

    assert result.ok is False
    assert result.stage == "graphics"
    assert "must include a file name after 'scr:'" in str(result.message)


def test_syntax_check_command_accepts_graphics_file_with_warning(tmp_path, capsys):
    file_path = _write_graphics_file(tmp_path, "Panel.g", "0 scr:missing_asset.wmf")

    exit_code = app.main(["syntax-check", str(file_path)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out.strip() == "OK"
    assert "PictureDisplay asset 'scr:missing_asset.wmf' could not be verified" in captured.err


def test_collect_syntax_diagnostics_returns_warning_for_graphics_asset(tmp_path):
    file_path = _write_graphics_file(tmp_path, "Panel.g", "0 scr:missing_asset.wmf")

    diagnostics = collect_syntax_diagnostics(
        file_path,
        file_path.read_text(encoding="utf-8"),
    )

    assert len(diagnostics) == 1
    assert diagnostics[0].severity == DiagnosticSeverity.Warning
    assert "could not be verified" in diagnostics[0].message


def test_resolve_graphics_companion_prefers_g_and_falls_back_to_y_in_draft_mode(tmp_path):
    source_file = _write_source_file(tmp_path, "Panel.s")
    fallback_file = _write_graphics_file(tmp_path, "Panel.y", "0 scr:missing_asset.wmf")

    assert resolve_graphics_companion_path(source_file, mode=CodeMode.DRAFT) == fallback_file

    preferred_file = _write_graphics_file(tmp_path, "Panel.g", "0 scr:missing_asset.wmf")

    assert resolve_graphics_companion_path(source_file, mode=CodeMode.DRAFT) == preferred_file


def test_validate_single_file_syntax_falls_back_to_y_when_g_is_missing(tmp_path):
    source_file = _write_source_file(tmp_path, "Panel.s")
    _write_graphics_file(tmp_path, "Panel.y", "0 scr:missing_asset.wmf")

    result = validate_single_file_syntax(source_file)

    assert result.ok is True
    assert result.warnings == (
        "PictureDisplay asset 'scr:missing_asset.wmf' could not be verified from this workspace",
    )


def test_validate_single_file_syntax_uses_y_when_mode_is_official(tmp_path):
    source_file = _write_source_file(tmp_path, "Panel.s")
    _write_graphics_file(tmp_path, "Panel.g", "0 scr:")
    _write_graphics_file(tmp_path, "Panel.y", "0 +L2+UnitControl+L1+L2+Panel")

    result = validate_single_file_syntax(source_file, mode=CodeMode.OFFICIAL)

    assert result.ok is True
    assert result.warnings == ()


def test_graphics_rules_normalization_helpers_cover_aliases_defaults_and_validation_errors():
    expected = {"moduledef": {"clipping_size": [1.0, 1.0]}}
    normalized = _normalize_rule(
        {
            "module_kind": "module",
            "unit_structure_path": "L1.L2.UnitControl",
            "expected": expected,
        }
    )
    moduletype_rule = _normalize_rule(
        {
            "module_kind": "moduletype-instance",
            "moduletype_name": "PumpType",
            "relative_module_path": "L1.L2.Pump",
            "expected": expected,
        }
    )
    named_rule = _normalize_rule(
        {
            "module_kind": "any",
            "module_name": "Panel",
            "expected": expected,
        }
    )

    assert _normalize_module_kind("module") == "single"
    assert _entry_rule_kind({"module_kind": "moduletype-instance"}) == "moduletype"
    assert _populated_path_selectors(normalized) == [("unit_structure_path", "L1.L2.UnitControl")]
    assert _rule_selector_key(normalized) == ("single", "", "", "l1.l2.unitcontrol", "", "unitcontrol")
    assert _normalized_rule_name(normalized) == "single:unit:L1.L2.UnitControl"
    assert _normalized_rule_name(moduletype_rule) == "moduletype:PumpType@path:L1.L2.Pump"
    assert _normalized_rule_name(named_rule) == "any:Panel"
    assert normalize_graphics_rules(None) == {"schema_version": 1, "rules": []}

    with pytest.raises(ValueError, match="Unsupported graphics rule module_kind"):
        _normalize_module_kind("unsupported")
    with pytest.raises(ValueError, match="Each graphics rule must be an object"):
        _normalize_rule(["bad"])
    with pytest.raises(ValueError, match="must use only one selector path field"):
        _normalize_rule(
            {
                "module_kind": "frame",
                "relative_module_path": "A.B",
                "unit_structure_path": "A.B",
                "expected": expected,
            }
        )
    with pytest.raises(ValueError, match="missing moduletype_name"):
        _normalize_rule({"module_kind": "moduletype", "expected": expected})
    with pytest.raises(ValueError, match="must declare a selector path or module_name"):
        _normalize_rule({"module_kind": "frame", "expected": expected})
    with pytest.raises(ValueError, match="must declare a non-empty expected object"):
        _normalize_rule({"module_kind": "any"})
    with pytest.raises(ValueError, match="Graphics rules JSON must be an object"):
        normalize_graphics_rules(["bad"])
    with pytest.raises(ValueError, match="must contain a 'rules' array"):
        normalize_graphics_rules({"rules": {}})


def test_graphics_rules_storage_helpers_cover_create_save_upsert_and_remove(tmp_path, monkeypatch):
    resolved_path = tmp_path / "resolved-rules.json"
    monkeypatch.setattr(
        "sattlint.graphics_rules.config_module.get_graphics_rules_path", lambda config_path=None: resolved_path
    )

    rules_path = tmp_path / "graphics_rules.json"
    _rules, created = load_graphics_rules(rules_path)
    assert created is True
    assert get_graphics_rules_path(tmp_path / "config.toml") == resolved_path
    assert rules_path.exists()

    save_graphics_rules(
        rules_path,
        {
            "schema_version": 1,
            "rules": [
                {
                    "module_kind": "frame",
                    "module_name": "Panel",
                    "expected": {"moduledef": {"clipping_size": [1.0, 1.0]}},
                }
            ],
        },
    )
    loaded, created_again = load_graphics_rules(rules_path)
    mutable_rules = {"schema_version": 1, "rules": []}
    rule = {
        "module_kind": "frame",
        "module_name": "Panel",
        "expected": {"moduledef": {"clipping_size": [1.0, 1.0]}},
    }

    assert created_again is False
    assert loaded["rules"][0]["module_name"] == "Panel"
    assert upsert_graphics_rule(mutable_rules, rule) is False
    assert upsert_graphics_rule(mutable_rules, {**rule, "description": "updated"}) is True
    assert remove_graphics_rule(mutable_rules, 0)["description"] == "updated"
    with pytest.raises(IndexError, match="Graphics rule index out of range"):
        remove_graphics_rule(mutable_rules, 0)


def test_graphics_rules_matching_validation_and_summary_cover_mismatches_and_unmatched_rules(tmp_path):
    frame_rule = _normalize_rule(
        {
            "module_kind": "frame",
            "unit_structure_path": "L1.L2.UnitControl",
            "expected": {
                "invocation": {"coords": [1, 2, 3, 4, 5]},
                "moduledef": {"clipping_size": [1.0, 1.0]},
            },
        }
    )
    moduletype_rule = _normalize_rule(
        {
            "module_kind": "moduletype",
            "moduletype_name": "PumpType",
            "equipment_module_structure_path": "L1.L2.Pump",
            "expected": {"moduledef": {"clipping_size": [1.0, 1.0]}},
        }
    )
    unmatched_rule = _normalize_rule(
        {
            "module_kind": "single",
            "relative_module_path": "L1.L2.Other",
            "expected": {"moduledef": {"clipping_size": [1.0, 1.0]}},
        }
    )
    named_rule = _normalize_rule(
        {
            "module_kind": "any",
            "module_name": "Panel",
            "expected": {"moduledef": {"clipping_size": [1.0, 1.0]}},
        }
    )
    selector_free_rule = _normalize_rule(
        {
            "module_kind": "any",
            "expected": {"moduledef": {"clipping_size": [1.0, 1.0]}},
        }
    )
    frame_entry = {
        "module_kind": "frame",
        "module_name": "UnitControl",
        "module_path": "BasePicture.UnitControl",
        "unit_structure_path": "L1.L2.UnitControl",
        "invocation": {"coords": [9, 2, 3, 4, 5]},
        "moduledef": None,
    }
    moduletype_entry = {
        "module_kind": "moduletype-instance",
        "module_name": "Pump",
        "module_path": "BasePicture.Pump",
        "equipment_module_structure_path": "L1.L2.Pump",
        "resolved_moduletype": {"name": "PumpType"},
        "invocation": {},
        "moduledef": {"clipping_size": [1.0, 1.0]},
    }
    mismatches: list[Any] = []

    _collect_mismatches(None, {"nested": 1}, field_path="moduledef", mismatches=mismatches)
    _collect_mismatches(1, 2, field_path="moduledef.size", mismatches=mismatches)

    assert _rule_matches_entry(frame_rule, frame_entry) is True
    assert _rule_matches_entry(frame_rule, {**frame_entry, "module_kind": "module"}) is False
    assert _rule_matches_entry(frame_rule, {**frame_entry, "module_kind": "basepicture"}) is False
    assert (
        _rule_matches_entry(unmatched_rule, {"module_kind": "module", "relative_module_path": "L1.L2.Different"})
        is False
    )
    assert _rule_matches_entry(frame_rule, {**frame_entry, "unit_structure_path": "L1.L2.Other"}) is False
    assert (
        _rule_matches_entry(moduletype_rule, {**moduletype_entry, "equipment_module_structure_path": "L1.L2.Other"})
        is False
    )
    assert _rule_matches_entry(moduletype_rule, moduletype_entry) is True
    assert _rule_matches_entry({**moduletype_rule, "moduletype_name": ""}, moduletype_entry) is False
    assert _rule_matches_entry(selector_free_rule, {"module_kind": "module", "module_name": "Anything"}) is True
    assert _rule_matches_entry(named_rule, {"module_kind": "module", "module_name": "Panel"}) is True
    assert _rule_matches_entry(named_rule, {"module_kind": "module", "module_name": "Other"}) is False
    assert [mismatch.field_path for mismatch in mismatches] == ["moduledef", "moduledef.size"]

    report = validate_graphics_layout_entries(
        [
            {"module_kind": "basepicture", "module_path": "BasePicture"},
            frame_entry,
            moduletype_entry,
        ],
        {"schema_version": 1, "rules": [frame_rule, moduletype_rule, unmatched_rule]},
        target_name="TargetA",
        rules_path=tmp_path / "graphics_rules.json",
    )
    summary = report.summary()

    assert report.configured_rule_count == 3
    assert report.matched_rule_count == 2
    assert report.checked_entry_count == 2
    assert len(report.findings) == 1
    assert report.findings[0].module_path == "BasePicture.UnitControl"
    assert report.unmatched_rule_names == ("single:path:L1.L2.Other",)
    assert "Configured rules : 3" in summary
    assert "Unmatched rules  : single:path:L1.L2.Other" in summary
    assert "moduledef: expected {'clipping_size': [1.0, 1.0]}, got None" in summary
