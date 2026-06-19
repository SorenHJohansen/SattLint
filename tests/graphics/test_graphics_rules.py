# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportPrivateUsage=false
from pathlib import Path
from typing import Any

import pytest

from sattlint.graphics_rules import (
    DEFAULT_GRAPHICS_RULES,
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


def test_graphics_rules_storage_helpers_cover_create_save_upsert_and_remove(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
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


def test_graphics_rules_matching_validation_and_summary_cover_mismatches_and_unmatched_rules(tmp_path: Path):
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

    _collect_mismatches(None, {"nested": 1}, field_path="moduledef", mismatches=mismatches)  # pyright: ignore[reportPrivateUsage]
    _collect_mismatches(1, 2, field_path="moduledef.size", mismatches=mismatches)  # pyright: ignore[reportPrivateUsage]

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


def test_load_graphics_rules_creates_default_json(tmp_path):
    rules_path = tmp_path / "graphics_rules.json"

    rules, created = load_graphics_rules(rules_path)

    assert created is True
    assert rules == DEFAULT_GRAPHICS_RULES
    assert rules_path.exists()


def test_upsert_and_remove_graphics_rule_roundtrip(tmp_path):
    rules_path = tmp_path / "graphics_rules.json"
    rules, _created = load_graphics_rules(rules_path)

    updated = upsert_graphics_rule(
        rules,
        {
            "module_name": "UnitControl",
            "module_kind": "single",
            "relative_module_path": "L1.UnitControl",
            "expected": {
                "invocation": {
                    "coords": [1.43, 1.35, 0.0, 0.56, 0.56],
                },
                "moduledef": {
                    "clipping_size": [1.0, 0.21429],
                },
            },
        },
    )
    save_graphics_rules(rules_path, rules)
    reloaded, _created = load_graphics_rules(rules_path)

    assert updated is False
    assert reloaded["rules"][0]["module_name"] == "UnitControl"
    assert reloaded["rules"][0]["expected"]["moduledef"]["clipping_size"] == [1.0, 0.21429]

    removed = remove_graphics_rule(reloaded, 0)

    assert removed["module_name"] == "UnitControl"
    assert reloaded["rules"] == []


def test_validate_graphics_layout_entries_reports_modules_not_to_spec(tmp_path):
    rules_path = tmp_path / "graphics_rules.json"
    rules = {
        "schema_version": 1,
        "rules": [
            {
                "module_name": "UnitControl",
                "module_kind": "single",
                "relative_module_path": "L1.UnitControl",
                "expected": {
                    "invocation": {
                        "coords": [1.43, 1.35, 0.0, 0.56, 0.56],
                    },
                    "moduledef": {
                        "clipping_size": [1.0, 0.21429],
                        "grid": 0.01,
                    },
                },
            }
        ],
    }
    entries = [
        {
            "module_path": "Program.L1.UnitControl",
            "relative_module_path": "L1.UnitControl",
            "module_name": "UnitControl",
            "module_kind": "module",
            "invocation": {
                "coords": [1.5, 1.35, 0.0, 0.56, 0.56],
            },
            "moduledef": {
                "clipping_size": [1.0, 0.25],
                "grid": 0.01,
            },
        }
    ]

    report = validate_graphics_layout_entries(
        entries,
        rules,
        target_name="Program",
        rules_path=rules_path,
    )

    assert report.configured_rule_count == 1
    assert report.matched_rule_count == 1
    assert len(report.findings) == 1
    assert report.findings[0].module_path == "Program.L1.UnitControl"
    assert [mismatch.field_path for mismatch in report.findings[0].mismatches] == [
        "invocation.coords",
        "moduledef.clipping_size",
    ]


def test_validate_graphics_layout_entries_uses_relative_path_for_duplicate_names(tmp_path):
    rules_path = tmp_path / "graphics_rules.json"
    rules = {
        "schema_version": 1,
        "rules": [
            {
                "module_kind": "frame",
                "relative_module_path": "Equipmentmoduler.Stop.L1",
                "expected": {
                    "moduledef": {
                        "clipping_size": [1.0, 0.14286],
                    },
                },
            }
        ],
    }
    entries = [
        {
            "module_path": "Program.Equipmentmoduler.Stop.L1",
            "relative_module_path": "Equipmentmoduler.Stop.L1",
            "module_name": "L1",
            "module_kind": "frame",
            "invocation": {},
            "moduledef": {"clipping_size": [1.1, 0.14286]},
        },
        {
            "module_path": "Program.Equipmentmoduler.Fill.L1",
            "relative_module_path": "Equipmentmoduler.Fill.L1",
            "module_name": "L1",
            "module_kind": "frame",
            "invocation": {},
            "moduledef": {"clipping_size": [1.0, 0.14286]},
        },
    ]

    report = validate_graphics_layout_entries(
        entries,
        rules,
        target_name="Program",
        rules_path=rules_path,
    )

    assert report.matched_rule_count == 1
    assert [finding.module_path for finding in report.findings] == ["Program.Equipmentmoduler.Stop.L1"]


def test_validate_graphics_layout_entries_matches_unit_structure_path(tmp_path):
    rules_path = tmp_path / "graphics_rules.json"
    rules = {
        "schema_version": 1,
        "rules": [
            {
                "module_kind": "frame",
                "unit_structure_path": "L1",
                "expected": {
                    "moduledef": {"clipping_size": [1.0, 1.0]},
                },
            }
        ],
    }
    entries = [
        {
            "module_path": "Program.UnitA.L1",
            "relative_module_path": "UnitA.L1",
            "unit_structure_path": "L1",
            "module_name": "L1",
            "module_kind": "frame",
            "invocation": {},
            "moduledef": {"clipping_size": [1.0, 0.95]},
        },
        {
            "module_path": "Program.UnitB.L1",
            "relative_module_path": "UnitB.L1",
            "unit_structure_path": "L1",
            "module_name": "L1",
            "module_kind": "frame",
            "invocation": {},
            "moduledef": {"clipping_size": [1.0, 1.0]},
        },
    ]

    report = validate_graphics_layout_entries(
        entries,
        rules,
        target_name="Program",
        rules_path=rules_path,
    )

    assert report.matched_rule_count == 1
    assert [finding.module_path for finding in report.findings] == ["Program.UnitA.L1"]


def test_validate_graphics_layout_entries_matches_equipment_structure_path(tmp_path):
    rules_path = tmp_path / "graphics_rules.json"
    rules = {
        "schema_version": 1,
        "rules": [
            {
                "module_kind": "moduletype",
                "moduletype_name": "EquipModPanelShort",
                "equipment_module_structure_path": "L1.L2.EquipModPanelShort",
                "expected": {
                    "moduledef": {"clipping_size": [0.13979, 0.14238]},
                },
            }
        ],
    }
    entries = [
        {
            "module_path": "Program.UnitA.L1.L2.Empty.L1.L2.EquipModPanel",
            "relative_module_path": "UnitA.L1.L2.Empty.L1.L2.EquipModPanel",
            "equipment_module_structure_path": "L1.L2.EquipModPanelShort",
            "module_name": "EquipModPanel",
            "module_kind": "moduletype-instance",
            "moduletype_name": "EquipModPanelShort",
            "invocation": {},
            "moduledef": {"clipping_size": [0.14, 0.14238]},
        },
        {
            "module_path": "Program.UnitA.L1.L2.Fill.L1.L2.EquipModPanel",
            "relative_module_path": "UnitA.L1.L2.Fill.L1.L2.EquipModPanel",
            "equipment_module_structure_path": "L1.L2.EquipModPanelShort",
            "module_name": "EquipModPanel",
            "module_kind": "moduletype-instance",
            "moduletype_name": "EquipModPanelShort",
            "invocation": {},
            "moduledef": {"clipping_size": [0.13979, 0.14238]},
        },
    ]

    report = validate_graphics_layout_entries(
        entries,
        rules,
        target_name="Program",
        rules_path=rules_path,
    )

    assert report.matched_rule_count == 1
    assert [finding.module_path for finding in report.findings] == ["Program.UnitA.L1.L2.Empty.L1.L2.EquipModPanel"]
