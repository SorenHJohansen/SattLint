# ruff: noqa: F403, F405
import importlib.util
import sys
import typing as t

from ._docgen_fixture_builders import *
from ._docgen_test_support import *


def test_configgen_create_dashboard_sets_title_and_merge():
    generator = configgen.ExcelGenerator(extractor=_typed_extractor(object()))

    generator._create_dashboard(2, 2)

    assert "A1:H1" in [str(rng) for rng in generator.dashboard_ws.merged_cells.ranges]
    assert generator.dashboard_ws["A1"].value == "SattLine Configuration Dashboard"
    assert generator.dashboard_ws.row_dimensions[1].height == 30


def test_configgen_create_configuration_summary_sheet_no_configs_writes_message():
    class StubExtractor:
        def parse_all_configuration_files(self):
            return []

    generator = configgen.ExcelGenerator(extractor=_typed_extractor(StubExtractor()))

    generator._create_configuration_summary_sheet()

    ws = generator.wb["Configuration Summary"]
    assert ws["A3"].value == "No configuration files found or parsing failed"


def test_configgen_create_configuration_details_sheet_no_configs_writes_message():
    class StubExtractor:
        def parse_all_configuration_files(self):
            return []

    generator = configgen.ExcelGenerator(extractor=_typed_extractor(StubExtractor()))

    generator._create_configuration_details_sheet()

    ws = generator.wb["Configuration Details"]
    assert ws["A3"].value == "No configuration files found or parsing failed"


def test_configgen_create_configuration_summary_sheet_builds_rows_and_table():
    class StubExtractor:
        def parse_all_configuration_files(self):
            return [
                configgen.ConfigurationFileInfo(
                    config_name="kBConfig.z",
                    version="1.0",
                    date="2026-04-29",
                    main_program="ProgB",
                    programs=[{"name": "ProgB", "directory": "unitlib", "main_program": True}],
                    libraries=[{"name": "LibB", "directory": "projectlib"}],
                ),
                configgen.ConfigurationFileInfo(
                    config_name="kAConfig.z",
                    version="2.0",
                    date="2026-04-30",
                    main_program="ProgA",
                    programs=[{"name": "ProgA", "directory": "unitlib", "main_program": True}],
                    libraries=[{"name": "LibA", "directory": "projectlib"}],
                ),
            ]

    generator = configgen.ExcelGenerator(extractor=_typed_extractor(StubExtractor()))

    generator._create_configuration_summary_sheet()

    ws = generator.wb["Configuration Summary"]
    assert ws["A4"].value == "kAConfig.z"
    assert ws["A5"].value == "kBConfig.z"
    assert "ConfigurationSummary" in ws.tables


def test_configgen_create_configuration_details_sheet_builds_program_and_library_rows():
    class StubExtractor:
        def parse_all_configuration_files(self):
            return [
                configgen.ConfigurationFileInfo(
                    config_name="kMain.z",
                    version="3.1",
                    date="2026-04-29",
                    main_program="ProgMain",
                    programs=[{"name": "ProgMain", "directory": "unitlib", "main_program": True}],
                    libraries=[{"name": "CommonLib", "directory": "projectlib"}],
                )
            ]

    generator = configgen.ExcelGenerator(extractor=_typed_extractor(StubExtractor()))

    generator._create_configuration_details_sheet()

    ws = generator.wb["Configuration Details"]
    assert ws["A4"].value == "kMain.z"
    assert ws["B4"].value == "Program"
    assert ws["B5"].value == "Library"
    assert "ConfigurationDetails" in ws.tables


def test_configgen_build_station_configurations_adds_transitive_non_program_libraries():
    class StubExtractor:
        def parse_all_configuration_files(self):
            return [
                configgen.ConfigurationFileInfo(
                    config_name="KaGc_AllF",
                    version="1.0",
                    date="2026-04-29",
                    main_program="ProgA",
                    programs=[{"name": "ProgA", "directory": "unitlib", "main_program": True}],
                    libraries=[{"name": "DeclaredLib", "directory": "projectlib"}],
                )
            ]

    generator = configgen.ExcelGenerator(extractor=_typed_extractor(StubExtractor()))
    generator.workstation_mapper.workstation_map = {"KaGC_Allf": ["OP11"]}
    generator.workstation_mapper.physical_locations = {"OP11": "Control Room 3"}

    component_data = [
        configgen.ComponentInfo(
            name="proga",
            type="Program",
            ip_address="10.0.0.1",
            slc="SLC100",
            units="(1) UnitA",
            dependencies=["declaredlib", "TransitiveLib", "ProgB"],
        ),
        configgen.ComponentInfo(
            name="DeclaredLib",
            type="Project Library",
            ip_address="N/A",
            slc="No SLC",
            units="N/A",
            dependencies=[],
        ),
        configgen.ComponentInfo(
            name="transitivelib",
            type="SG Library",
            ip_address="N/A",
            slc="No SLC",
            units="N/A",
            dependencies=[],
        ),
        configgen.ComponentInfo(
            name="ProgB",
            type="Program",
            ip_address="10.0.0.2",
            slc="SLC101",
            units="(1) UnitB",
            dependencies=[],
        ),
    ]

    result = generator._build_station_configurations(component_data)

    assert result["OP11"]["config_file"] == "KaGC_Allf"
    assert result["OP11"]["type"] == "Operator Station"
    assert result["OP11"]["programs"] == ["ProgA"]
    assert result["OP11"]["libraries"] == ["DeclaredLib", "TransitiveLib"]


def test_configgen_create_station_configuration_sheet_writes_defaults_for_missing_config_data():
    class StubExtractor:
        def parse_all_configuration_files(self):
            return []

    generator = configgen.ExcelGenerator(extractor=_typed_extractor(StubExtractor()))
    generator.workstation_mapper.workstation_map = {"KaGC_Missing": ["OP99"]}
    generator.workstation_mapper.physical_locations = {"OP99": "Lab"}

    generator._create_station_configuration_sheet([])

    ws = generator.wb["Station Configuration"]
    assert ws["A4"].value == "OP99"
    assert ws["B4"].value == "Operator Station"
    assert ws["C4"].value == "Lab"
    assert ws["D4"].value == "KaGC_Missing"
    assert ws["E4"].value == "No SLC"
    assert ws["F4"].value == "No programs"
    assert ws["G4"].value == "No libraries"
    assert ws["H4"].value == "No units assigned"
    assert ws["I4"].value == "N/A"
    assert "StationConfiguration" in ws.tables


def test_get_example_fixtures_for_analyzer_returns_examples():
    from sattlint.docgenerator.analyzer_ref import get_example_fixtures_for_analyzer

    variables_examples = get_example_fixtures_for_analyzer("variables")
    assert len(variables_examples) >= 1
    assert any("CommonQualityIssues" in ex["fixture"] for ex in variables_examples)

    sfc_examples = get_example_fixtures_for_analyzer("sfc")
    assert len(sfc_examples) >= 2
    assert any("ParallelWriteRace" in ex["fixture"] for ex in sfc_examples)

    unknown_examples = get_example_fixtures_for_analyzer("nonexistent")
    assert unknown_examples == []


def test_get_example_fixtures_for_analyzer_returns_expected_rule_ids():
    from sattlint.docgenerator.analyzer_ref import get_example_fixtures_for_analyzer

    shadowing_examples = get_example_fixtures_for_analyzer("shadowing")
    assert len(shadowing_examples) >= 1
    example = shadowing_examples[0]
    assert "semantic.shadowing" in example["expected_rule_ids"]

    config_drift_examples = get_example_fixtures_for_analyzer("config-drift")
    assert len(config_drift_examples) == 1
    assert config_drift_examples[0]["expected_rule_ids"] == ["semantic.instance-configuration-drift"]


def test_build_analyzer_reference_entry():
    from sattlint.analyzers.framework import AnalyzerSpec
    from sattlint.docgenerator.analyzer_ref import build_analyzer_reference_entry

    def _dummy_run(context):
        from sattlint.analyzers.framework import SimpleReport

        return SimpleReport(name="test")

    spec = AnalyzerSpec(
        key="variables",
        name="Variable issues",
        description="Unused/read-only/never-read variables",
        run=_dummy_run,
        enabled=True,
        supports_live_diagnostics=True,
    )

    entry = build_analyzer_reference_entry(spec)

    assert entry["key"] == "variables"
    assert entry["name"] == "Variable issues"
    assert entry["enabled"] is True
    assert "delivery" in entry
    assert "rules" in entry
    assert "examples" in entry
    assert entry["example_count"] >= 1


def test_build_full_analyzer_reference():
    from sattlint.docgenerator.analyzer_ref import build_full_analyzer_reference

    reference = build_full_analyzer_reference()

    assert "generated_by" in reference
    assert "schema_version" in reference
    assert "analyzers" in reference
    assert "total_analyzers" in reference
    assert "total_rules" in reference
    assert reference["total_analyzers"] > 0
    assert reference["total_rules"] > 0


def test_build_full_analyzer_reference_includes_wave2_analyzers_with_rules_and_examples():
    from sattlint.docgenerator.analyzer_ref import build_full_analyzer_reference

    reference = build_full_analyzer_reference()
    analyzers = {entry["key"]: entry for entry in reference["analyzers"]}

    for key in (
        "signal-lifecycle",
        "loop-stability",
        "fault-handling",
        "numeric-constraints",
        "config-drift",
    ):
        assert key in analyzers
        assert analyzers[key]["rules"]
        assert analyzers[key]["examples"]


def test_render_analyzer_reference_markdown():
    from sattlint.docgenerator.analyzer_ref import render_analyzer_reference_markdown

    markdown = render_analyzer_reference_markdown()

    assert "# SattLint Analyzer Reference" in markdown
    assert "Generated by:" in markdown
    assert "Total analyzers:" in markdown
    assert "Total rules:" in markdown


def test_render_analyzer_reference_markdown_contains_analyzer_info():
    from sattlint.docgenerator.analyzer_ref import render_analyzer_reference_markdown

    markdown = render_analyzer_reference_markdown()

    assert "## Variable issues" in markdown or "## SFC checks" in markdown
    assert "**Description:**" in markdown
    assert "**Enabled:**" in markdown


def test_save_analyzer_reference_json(tmp_path):
    from sattlint.docgenerator.analyzer_ref import save_analyzer_reference_json

    output_path = tmp_path / "analyzer_ref.json"
    save_analyzer_reference_json(output_path)

    assert output_path.exists()
    import json

    data = json.loads(output_path.read_text())
    assert "analyzers" in data
    assert len(data["analyzers"]) > 0


def test_save_analyzer_reference_markdown(tmp_path):
    from sattlint.docgenerator.analyzer_ref import save_analyzer_reference_markdown

    output_path = tmp_path / "analyzer_ref.md"
    save_analyzer_reference_markdown(output_path)

    assert output_path.exists()
    content = output_path.read_text()
    assert "# SattLint Analyzer Reference" in content
    assert "Generated by:" in content


def test_resolve_fixture_path_returns_fixture_root_path():
    from sattlint.docgenerator import analyzer_ref

    resolved = analyzer_ref.resolve_fixture_path("corpus/semantic/ConfigDrift.s")

    assert resolved == analyzer_ref.FIXTURES_DIR / "corpus" / "semantic" / "ConfigDrift.s"


def test_build_analyzer_reference_entry_returns_error_for_unknown_catalog():
    from types import SimpleNamespace

    from sattlint.analyzers.framework import AnalyzerSpec
    from sattlint.docgenerator.analyzer_ref import build_analyzer_reference_entry

    def _dummy_run(context):
        from sattlint.analyzers.framework import SimpleReport

        return SimpleReport(name="test")

    spec = AnalyzerSpec(
        key="missing-analyzer",
        name="Missing analyzer",
        description="Not registered",
        run=_dummy_run,
        enabled=True,
        supports_live_diagnostics=False,
    )

    entry = build_analyzer_reference_entry(
        spec,
        catalog=SimpleNamespace(analyzers=[], rules=[]),
    )

    assert entry == {"key": "missing-analyzer", "error": "Analyzer not found in catalog"}


def test_build_full_analyzer_reference_uses_supplied_catalog_and_explicit_markdown_reference(tmp_path):
    from sattlint.docgenerator.analyzer_ref import (
        build_full_analyzer_reference,
        render_analyzer_reference_markdown,
        save_analyzer_reference_markdown,
    )

    class _EmptyCatalog:
        analyzers: t.ClassVar[list[object]] = []
        rules: t.ClassVar[list[object]] = []

        def enabled_specs(self):
            return []

    reference = build_full_analyzer_reference(catalog=_EmptyCatalog())
    explicit_reference = {
        "generated_by": "custom-analyzer-ref",
        "schema_version": 7,
        "total_analyzers": 1,
        "total_rules": 0,
        "analyzers": [
            {
                "name": "Custom Analyzer",
                "key": "custom",
                "description": "Synthetic reference entry",
                "enabled": False,
                "supports_live_diagnostics": False,
                "delivery": {},
                "rules": [],
                "examples": [],
            }
        ],
    }

    markdown = render_analyzer_reference_markdown(explicit_reference)
    output_path = tmp_path / "explicit-analyzer-ref.md"
    save_analyzer_reference_markdown(output_path, explicit_reference)

    assert reference["analyzers"] == []
    assert reference["total_analyzers"] == 0
    assert "### Delivery Metadata" not in markdown
    assert "Generated by: custom-analyzer-ref" in output_path.read_text(encoding="utf-8")


def test_analyzer_ref_module_executes_type_checking_branch(monkeypatch):
    from sattlint.docgenerator import analyzer_ref

    module_name = "sattlint.docgenerator._analyzer_ref_typecheck_probe"
    spec = importlib.util.spec_from_file_location(module_name, analyzer_ref.__file__)

    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    monkeypatch.setattr(t, "TYPE_CHECKING", True)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(module_name, None)

    assert module.FIXTURES_DIR == analyzer_ref.FIXTURES_DIR
