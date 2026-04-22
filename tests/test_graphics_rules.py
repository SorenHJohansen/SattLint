
from sattlint.graphics_rules import (
    DEFAULT_GRAPHICS_RULES,
    load_graphics_rules,
    remove_graphics_rule,
    save_graphics_rules,
    upsert_graphics_rule,
    validate_graphics_layout_entries,
)


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
    assert [finding.module_path for finding in report.findings] == [
        "Program.Equipmentmoduler.Stop.L1"
    ]


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
    assert [finding.module_path for finding in report.findings] == [
        "Program.UnitA.L1.L2.Empty.L1.L2.EquipModPanel"
    ]
