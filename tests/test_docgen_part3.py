# ruff: noqa: F403, F405
from ._docgen_fixture_builders import *
from ._docgen_test_support import *


def test_classification_and_docgen_final_helper_edges():
    top_level = _documented_instance("BasePicture", ("BasePicture",), moduletype_name="TopType")
    scoped_root = _documented_instance(
        "ScopedUnit",
        ("BasePicture", "ScopedUnit"),
        moduletype_name="UnitType",
        moduleparameters=[Variable(name="SectionName", datatype="STRING")],
    )
    shared_sequence = Sequence(name="Shared", type="sequence", position=(0.0, 0.0), size=(1.0, 1.0), code=[])
    equipment = _documented_instance(
        "Pump",
        ("BasePicture", "ScopedUnit", "Pump"),
        moduletype_name="EquipModPump",
        modulecode=ModuleCode(
            sequences=[shared_sequence],
        ),
    )
    duplicate_equipment = _documented_instance(
        "Pump",
        ("BasePicture", "ScopedUnit", "Pump"),
        moduletype_name="EquipModPump",
        modulecode=ModuleCode(
            sequences=[shared_sequence],
        ),
    )
    wrapper_parent = _documented_instance(
        "OprFrame",
        ("BasePicture", "Operations", "OprFrame"),
        moduletype_name="OprFrame",
    )
    wrapper_marker = _documented_instance(
        "Prepare",
        ("BasePicture", "Operations", "OprFrame", "Prepare"),
        moduletype_name="OperationPhase",
    )
    rootless = _documented_instance("Root", (), moduletype_name="RootType")
    short_descendant = _documented_instance("Solo", ("Solo",), moduletype_name="Display")
    off_panel_descendant = _documented_instance(
        "Lamp",
        ("BasePicture", "ScopedUnit", "Pump", "Display", "Lamp"),
        moduletype_name="Display",
    )
    toggle_descendant = _documented_instance(
        "KaHCToggleLamp",
        ("BasePicture", "ScopedUnit", "Pump", "Panel", "KaHCToggleLamp"),
        moduletype_name="Display",
    )
    state_descendant = _documented_instance(
        "StateLamp",
        ("BasePicture", "ScopedUnit", "Pump", "Panel", "StateLamp"),
        moduletype_name="Display",
    )
    duplicate_state_descendant = _documented_instance(
        "StateLamp",
        ("BasePicture", "ScopedUnit", "Pump", "Panel", "StateLamp"),
        moduletype_name="Display",
    )
    event_entry = _documented_instance(
        "Event01",
        ("BasePicture", "ScopedUnit", "Pump", "Event01"),
        moduletype_name="EventModule",
        parametermappings=[_literal_mapping("Severity", "High"), _literal_mapping("Activation", "WhenTrue")],
    )
    calc_entry = _documented_instance(
        "Calc01",
        ("BasePicture", "ScopedUnit", "Pump", "Calc01"),
        moduletype_name="CalcModule",
    )
    pid_entry = _documented_instance(
        "PC101",
        ("BasePicture", "ScopedUnit", "Pump", "PC101"),
        moduletype_name="ControlModule",
    )
    blank_source_unit = DocumentUnit(
        root=_documented_instance(
            "RootUnit",
            ("BasePicture", "RootUnit"),
            moduletype_name="UnitType",
            parametermappings=[_literal_mapping("OutletPW", None)],
        ),
        unit_code="RootUnit",
        title="Root Unit",
        unit_class="UnitType",
        section_name="Root Unit",
        equipment_modules=[],
        operations=[],
        recipe_parameters=[],
        engineering_parameters=[],
        user_parameters=[],
    )
    blank_target_unit = DocumentUnit(
        root=_documented_instance(
            "BlankTargetUnit",
            ("BasePicture", "BlankTargetUnit"),
            moduletype_name="UnitType",
            parametermappings=[_literal_mapping("", "PipeA")],
        ),
        unit_code="BlankTargetUnit",
        title="Blank Target Unit",
        unit_class="UnitType",
        section_name="Blank Target Unit",
        equipment_modules=[],
        operations=[],
        recipe_parameters=[],
        engineering_parameters=[],
        user_parameters=[],
    )
    classification = DocumentationClassification(
        section_order=["em", "ops", "rp", "ep", "up"],
        categories={"em": [equipment], "ops": [], "rp": [], "ep": [], "up": []},
        uncategorized=[scoped_root],
        all_entries=[
            scoped_root,
            equipment,
            duplicate_equipment,
            short_descendant,
            off_panel_descendant,
            toggle_descendant,
            state_descendant,
            duplicate_state_descendant,
            event_entry,
            calc_entry,
            pid_entry,
        ],
    )

    assert top_level.short_path == "BasePicture"
    assert document_scope_summary(scoped_root, classification) == {"ops": 0, "em": 1, "rp": 0, "ep": 0, "up": 0}
    assert _equals_pattern("UnitType", ["", "UnitType"]) is True
    assert _matches_rule(scoped_root, {"name_contains": ["Unit"]}, [scoped_root]) is True
    assert (
        _marker_anchor(wrapper_marker, {wrapper_parent.path: wrapper_parent, wrapper_marker.path: wrapper_marker})
        is wrapper_parent
    )
    assert _matches_category_heuristic(scoped_root, "other") is False
    assert not _looks_like_equipment_module(
        _documented_instance("Coordinate", ("BasePicture", "Coordinate"), moduletype_name="PumpType")
    )
    assert not _looks_like_operation(_documented_instance("Step", ("Step",), moduletype_name="OperationPhase"))
    assert _looks_like_unit_root(scoped_root, classification, categorized_paths=set()) is True
    assert _looks_like_wrapper_name("Prefix:Panel") is True

    assert _configurable_parameter_rows(blank_source_unit) == []
    assert _simple_name_tag_rows([calc_entry], "description") == [["Detected CalcModule instance.", "Calc01"]]
    assert _event_table_rows([event_entry]) == [["Event01", "Detected EventModule instance.", "High", "WhenTrue"]]
    assert _calculation_rows([calc_entry]) == [["Calc01", "Detected CalcModule instance.", "ScopedUnit.Pump.Calc01"]]
    assert _communication_rows(blank_target_unit, direction="to") == []
    assert _state_rows(rootless, classification) == [
        ["StateLamp", "Detected Display instance.", "Display-only state definition"]
    ]
    assert _pid_controller_rows(scoped_root, classification) == [
        ["PC101", "ControlModule", "ScopedUnit.Pump.PC101", "Detected ControlModule instance."]
    ]
    assert _sequence_rows(scoped_root, classification) == [("Shared", _sequence_render_rows(shared_sequence))]


def test_configgen_parse_configuration_file_extracts_programs_and_libraries(tmp_path):
    config_file = tmp_path / "Configuration" / "KaGC_Allf.k"
    _write_text(
        config_file,
        'Configuration ( Version "v1" Date "2026-04-29" Name "IgnoredByParser" )\n'
        'Program ( Name "MainProgram.z" Directory "UnitLib" MainProgram True )\n'
        'Program ( Name "SupportProgram" Directory "UnitLib" MainProgram False )\n'
        'Library ( Name "CommonLib.z" Directory "ProjectLib" )\n',
    )

    parser = configgen.ConfigurationFileParser()

    info = parser.parse_configuration_file(config_file)

    assert info is not None
    assert info.config_name == "KaGC_Allf"
    assert info.version == "v1"
    assert info.date == "2026-04-29"
    assert info.main_program == "MainProgram"
    assert info.programs == [
        {"name": "MainProgram", "directory": "UnitLib", "main_program": True},
        {"name": "SupportProgram", "directory": "UnitLib", "main_program": False},
    ]
    assert info.libraries == [{"name": "CommonLib", "directory": "ProjectLib"}]


def test_configgen_parse_configuration_file_returns_none_without_header(tmp_path):
    config_file = tmp_path / "Configuration" / "Broken.k"
    _write_text(config_file, 'Program ( Name "MainProgram.z" Directory "UnitLib" MainProgram True )\n')

    parser = configgen.ConfigurationFileParser()

    assert parser.parse_configuration_file(config_file) is None


def test_configgen_parse_configuration_file_returns_none_on_read_error(tmp_path, monkeypatch):
    config_file = tmp_path / "Configuration" / "Broken.k"
    _write_text(config_file, 'Configuration ( Version "v1" Date "2026-04-29" Name "Ignored" )\n')

    parser = configgen.ConfigurationFileParser()
    monkeypatch.setattr(configgen, "read_text_with_fallback", lambda _path: (_ for _ in ()).throw(OSError("boom")))

    assert parser.parse_configuration_file(config_file) is None


def test_configgen_extractor_get_component_info_reads_dependencies_ip_slc_and_units(tmp_path):
    root = tmp_path / "ProjectRoot"
    for relative in ["unitlib", "projectlib", "nnelib", "SL_Library", "Configuration"]:
        (root / relative).mkdir(parents=True)

    z_file = root / "unitlib" / "PBSLC123.z"
    _write_text(z_file, "CommonLib.z\nIOHelpers.z\n")
    _write_text(z_file.with_suffix(".q"), '( Name "10.0.0.7" )\n')
    _write_text(z_file.with_suffix(".x"), 'pMixer : pType;\npFilter "UF" : pType ;\n')

    extractor = configgen.SattLineConfigExtractor(root)

    component = extractor.get_component_info(z_file, "Program", True, {"PBSLC123": "10.0.0.7"})

    assert component.name == "PBSLC123"
    assert component.type == "Program"
    assert component.dependencies == ["CommonLib", "IOHelpers"]
    assert component.ip_address == "10.0.0.7"
    assert component.slc == "SLC123"
    assert component.units == "(2) Filter, Mixer"


def test_configgen_workstation_mapper_is_case_insensitive():
    mapper = configgen.WorkstationMapper()

    assert mapper.get_workstations("kagc_op_utilf.z") == ["LOP01", "OP06", "OP07"]
    assert mapper.get_workstations("missing-station") == []
    assert mapper.get_physical_location("OPC01") == "Server Room"
    assert mapper.get_physical_location("UNKNOWN") == "Unknown Location"


def test_configgen_extractor_raises_when_required_directories_are_missing(tmp_path):
    with pytest.raises(ValueError, match="Required directories not found"):
        configgen.SattLineConfigExtractor(tmp_path / "missing-root")


def test_configgen_parse_all_configuration_files_handles_missing_and_empty_directory(tmp_path):
    root = tmp_path / "ProjectRoot"
    for relative in ["unitlib", "projectlib", "nnelib", "SL_Library"]:
        (root / relative).mkdir(parents=True)

    extractor = configgen.SattLineConfigExtractor(root)

    assert extractor.parse_all_configuration_files() == []

    extractor.kfiles_dir.mkdir()

    assert extractor.parse_all_configuration_files() == []


def test_configgen_parse_all_configuration_files_returns_only_valid_configs(tmp_path):
    root = tmp_path / "ProjectRoot"
    for relative in ["unitlib", "projectlib", "nnelib", "SL_Library", "Configuration"]:
        (root / relative).mkdir(parents=True)

    _write_text(
        root / "Configuration" / "Valid.k",
        'Configuration ( Version "v2" Date "2026-04-30" Name "Valid" )\n'
        'Program ( Name "Main.z" Directory "UnitLib" MainProgram True )\n',
    )
    _write_text(
        root / "Configuration" / "Invalid.k", 'Program ( Name "Broken.z" Directory "UnitLib" MainProgram True )\n'
    )

    extractor = configgen.SattLineConfigExtractor(root)

    result = extractor.parse_all_configuration_files()

    assert [config.config_name for config in result] == ["Valid"]


def test_configgen_get_z_files_returns_sorted_files_and_empty_for_missing_directory(tmp_path):
    root = tmp_path / "ProjectRoot"
    for relative in ["unitlib", "projectlib", "nnelib", "SL_Library", "Configuration"]:
        (root / relative).mkdir(parents=True)

    extractor = configgen.SattLineConfigExtractor(root)
    assert extractor.get_z_files(root / "does-not-exist") == []

    _write_text(root / "projectlib" / "B.z", "")
    _write_text(root / "projectlib" / "A.z", "")

    assert [path.name for path in extractor.get_z_files(root / "projectlib")] == ["A.z", "B.z"]


def test_configgen_read_dependencies_returns_empty_list_when_cached_read_fails(tmp_path, monkeypatch):
    root = tmp_path / "ProjectRoot"
    for relative in ["unitlib", "projectlib", "nnelib", "SL_Library", "Configuration"]:
        (root / relative).mkdir(parents=True)

    extractor = configgen.SattLineConfigExtractor(root)
    z_file = root / "unitlib" / "Broken.z"
    _write_text(z_file, "LibA.z\n")

    def _boom(_path):
        raise OSError("read failed")

    monkeypatch.setattr(extractor, "_read_file_cached", _boom)

    assert extractor.read_dependencies(z_file) == []


def test_configgen_read_dependencies_refreshes_when_file_changes(tmp_path):
    root = tmp_path / "ProjectRoot"
    for relative in ["unitlib", "projectlib", "nnelib", "SL_Library", "Configuration"]:
        (root / relative).mkdir(parents=True)

    extractor = configgen.SattLineConfigExtractor(root)
    z_file = root / "unitlib" / "Dynamic.z"
    _write_text(z_file, "LibA.z\n")

    assert extractor.read_dependencies(z_file) == ["LibA"]

    _write_text(z_file, "LibB.z\n")

    assert extractor.read_dependencies(z_file) == ["LibB"]


def test_configgen_read_dependencies_can_bypass_cached_reads(tmp_path, monkeypatch):
    root = tmp_path / "ProjectRoot"
    for relative in ["unitlib", "projectlib", "nnelib", "SL_Library", "Configuration"]:
        (root / relative).mkdir(parents=True)

    extractor = configgen.SattLineConfigExtractor(root, use_cached_dependency_reads=False)
    z_file = root / "unitlib" / "Bypass.z"
    _write_text(z_file, "LibA.z\n")

    def _cached_read_should_not_run(_path):
        raise AssertionError("cached dependency read should be bypassed")

    monkeypatch.setattr(extractor, "_read_file_cached", _cached_read_should_not_run)

    assert extractor.read_dependencies(z_file) == ["LibA"]


def test_configgen_ip_and_slc_helpers_cover_default_and_error_paths(tmp_path, monkeypatch):
    root = tmp_path / "ProjectRoot"
    for relative in ["unitlib", "projectlib", "nnelib", "SL_Library", "Configuration"]:
        (root / relative).mkdir(parents=True)

    z_file = root / "unitlib" / "WdSlc045.z"
    _write_text(z_file, "")
    extractor = configgen.SattLineConfigExtractor(root)

    assert extractor.get_ip_address(z_file) == "No Q-File"

    q_file = z_file.with_suffix(".q")
    _write_text(q_file, "No matching name token\n")
    assert extractor.get_ip_address(z_file) == "No SLC assigned"

    monkeypatch.setattr(configgen, "read_text_with_fallback", lambda _path: (_ for _ in ()).throw(OSError("q broken")))
    assert extractor.get_ip_address(z_file) == "Error reading Q-File"

    assert extractor.get_slc_name("No Q-File", {"PBSLC123": "10.0.0.7"}) == "No SLC"
    assert extractor.get_slc_name("10.0.0.8", {"WdSlc045": "10.0.0.8"}) == "SLC045"
    assert extractor.get_slc_name("10.0.0.9", {"OtherProgram": "10.0.0.9"}) == "No SLC"


def test_configgen_get_units_in_program_covers_missing_empty_and_error_paths(tmp_path, monkeypatch):
    root = tmp_path / "ProjectRoot"
    for relative in ["unitlib", "projectlib", "nnelib", "SL_Library", "Configuration"]:
        (root / relative).mkdir(parents=True)

    z_file = root / "unitlib" / "ProgramA.z"
    _write_text(z_file, "")
    extractor = configgen.SattLineConfigExtractor(root)

    assert extractor.get_units_in_program(z_file) == "No X-File"

    x_file = z_file.with_suffix(".x")
    _write_text(x_file, "No pType declarations here\n")
    assert extractor.get_units_in_program(z_file) == "No units assigned"

    monkeypatch.setattr(configgen, "read_text_with_fallback", lambda _path: (_ for _ in ()).throw(OSError("x broken")))
    assert extractor.get_units_in_program(z_file) == "Error reading X-File"


def test_configgen_get_component_info_sets_na_fields_for_non_program_components(tmp_path):
    root = tmp_path / "ProjectRoot"
    for relative in ["unitlib", "projectlib", "nnelib", "SL_Library", "Configuration"]:
        (root / relative).mkdir(parents=True)

    z_file = root / "projectlib" / "CommonLib.z"
    _write_text(z_file, "DepA.z\n")
    extractor = configgen.SattLineConfigExtractor(root)

    component = extractor.get_component_info(z_file, "Project Library", False, {})

    assert component.name == "CommonLib"
    assert component.ip_address == "N/A"
    assert component.slc == "N/A"
    assert component.units == "N/A"
    assert component.dependencies == ["DepA"]
