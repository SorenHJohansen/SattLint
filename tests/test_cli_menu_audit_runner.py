from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_cli_menu_audit_module():
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "run_cli_menu_audit.py"
    spec = importlib.util.spec_from_file_location("run_cli_menu_audit", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


cli_menu_audit = _load_cli_menu_audit_module()


def _base_context() -> object:
    return cli_menu_audit.AuditContext(
        config_path=Path("config.toml"),
        graphics_rules_path=Path("graphics_rules.json"),
        cfg={
            "analyzed_programs_and_libraries": ["TargetA"],
            "program_dir": "Programs",
            "ABB_lib_dir": "ABB",
            "other_lib_dirs": ["OtherLib"],
            "icf_dir": "ICF",
        },
        default_config_created=False,
        analyzed_targets=["TargetA"],
        extra_target_name="TargetB",
        enabled_analyzer_keys=["variables", "shadowing", "spec-compliance"],
        variable_analysis_keys=["1", "2", "22"],
        targets_loaded=True,
        target_context=cli_menu_audit.TargetContext(
            target_name="TargetA",
            variable_name="FlowVar",
            module_name="UnitA",
            module_path="UnitA.L1.L2.UnitControl",
            module_local_var="Dv",
            documentation_instance_path="UnitA",
            documentation_moduletype_name="ApplTank",
            graphics_relative_module_path="Area.UnitControl",
            graphics_selector_has_options=True,
        ),
    )


def test_graphics_add_inputs_use_selector_index_when_options_exist():
    context = _base_context()

    inputs = cli_menu_audit._graphics_add_inputs(context)

    assert inputs is not None
    assert inputs[:5] == ["1", "1", "1", "CLI audit rule", "1,2,3,4,5"]
    assert inputs[-1] == "b"


def test_build_scenarios_includes_dynamic_variable_and_catalog_entries(tmp_path):
    context = _base_context()

    scenarios = cli_menu_audit.build_scenarios(context, output_dir=tmp_path)
    names = {scenario.name for scenario in scenarios}

    assert "variables.1" in names
    assert "variables.2" in names
    assert "variables.22" in names
    assert "catalog.variables" in names
    assert "catalog.shadowing" in names
    assert "catalog.spec-compliance" in names


def test_build_scenarios_keeps_matrix_when_target_details_are_missing(tmp_path):
    base = _base_context()
    context = cli_menu_audit.AuditContext(
        config_path=base.config_path,
        graphics_rules_path=base.graphics_rules_path,
        cfg=base.cfg,
        default_config_created=base.default_config_created,
        analyzed_targets=base.analyzed_targets,
        extra_target_name=base.extra_target_name,
        enabled_analyzer_keys=base.enabled_analyzer_keys,
        variable_analysis_keys=base.variable_analysis_keys,
        targets_loaded=True,
        target_context=None,
    )

    scenarios = {scenario.name: scenario for scenario in cli_menu_audit.build_scenarios(context, output_dir=tmp_path)}

    assert "variables.1" in scenarios
    assert "catalog.variables" in scenarios
    assert (
        scenarios["variables.datatype-usage"].blocked_reason
        == "No live variable name was discovered from the loaded target."
    )


def test_build_scenarios_blocks_target_dependent_paths_without_loaded_targets(tmp_path):
    context = cli_menu_audit.AuditContext(
        config_path=Path("config.toml"),
        graphics_rules_path=Path("graphics_rules.json"),
        cfg={"analyzed_programs_and_libraries": []},
        default_config_created=False,
        analyzed_targets=[],
        extra_target_name=None,
        enabled_analyzer_keys=["variables"],
        variable_analysis_keys=["1"],
        targets_loaded=False,
        target_context=None,
    )

    scenarios = cli_menu_audit.build_scenarios(context, output_dir=tmp_path)
    blocked = {scenario.name: scenario.blocked_reason for scenario in scenarios if scenario.blocked_reason}

    assert blocked["startup.analyze-route"]
    assert blocked["documentation.generate"]
    assert blocked["analysis.full-suite"]
