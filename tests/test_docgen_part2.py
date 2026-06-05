# ruff: noqa: F403, F405
from ._docgen_fixture_builders import *
from ._docgen_test_support import *


def test_generate_docx_renders_appendix_for_uncategorized_modules(tmp_path):
    base_picture = _build_documentation_fixture()
    out_path = tmp_path / "functional-spec-appendix.docx"

    generate_docx(
        base_picture,
        out_path,
        documentation_config=config_module.get_documentation_config(),
    )

    document = Document(out_path)
    paragraph_text = [paragraph.text.strip() for paragraph in document.paragraphs if paragraph.text.strip()]
    table_text = _table_text(document)

    assert "Appendix: Supporting modules" in paragraph_text
    assert "Other module instances" in paragraph_text
    assert "UnitA" in table_text
    assert "DilutionTrain" in table_text
    assert "GlobalLimit" not in table_text


def test_generate_docx_renders_empty_sequences_as_no_explicit_statements(tmp_path):
    base_picture = _build_empty_sequence_doc_fixture()
    out_path = tmp_path / "functional-spec-empty-sequence.docx"

    generate_docx(
        base_picture,
        out_path,
        documentation_config=config_module.get_documentation_config(),
    )

    document = Document(out_path)
    paragraph_text = [paragraph.text.strip() for paragraph in document.paragraphs if paragraph.text.strip()]

    assert "Sub sequence - EmptySequence" in paragraph_text
    assert "No explicit sequence statements detected." in paragraph_text


def test_classification_private_helpers_cover_scope_lookup_and_anchor_edges():
    unresolved_root = _documented_instance("Rootless", (), moduletype_name="LooseType")
    scoped_root = _documented_instance(
        "UnitAlpha",
        ("BasePicture", "AreaA", "UnitAlpha"),
        moduletype_name="UnitType",
        moduleparameters=[Variable(name="SectionName", datatype="STRING")],
    )
    wrapper = _documented_instance(
        "Operations",
        ("BasePicture", "AreaA", "UnitAlpha", "Operations"),
        moduletype_name="OperationsWrapper",
    )
    marker = _documented_instance(
        "Prepare",
        ("BasePicture", "AreaA", "UnitAlpha", "Operations", "OprFrame", "Prepare"),
        moduletype_name="OperationPhase",
    )
    entries = [scoped_root, wrapper, marker]
    entry_lookup = {entry.path: entry for entry in entries}

    assert unresolved_root.moduletype_name == "LooseType"
    assert unresolved_root.moduletype_label == "LooseType"
    assert unresolved_root.short_path == ""
    assert scoped_root.short_path == "AreaA.UnitAlpha"
    assert _matches_rule(scoped_root, {}, entries) is False
    assert _has_descendant_marker_match(scoped_root, entries, name_contains=["operation"], label_equals=[])
    assert _marker_anchor(marker, entry_lookup) is scoped_root

    roots, unmatched = _resolve_scope_paths([scoped_root], ["UnitAlpha", "Missing.Unit"])

    assert roots == [scoped_root]
    assert unmatched == ["Missing.Unit"]


def test_discover_documentation_unit_candidates_cover_fallback_paths():
    fallback_root = _documented_instance(
        "DeepUnit",
        ("BasePicture", "AreaA", "CellA", "DeepUnit"),
        moduletype_name="UnitType",
    )
    fallback_equipment = _documented_instance(
        "Pump",
        ("BasePicture", "AreaA", "CellA", "DeepUnit", "Pump"),
        moduletype_name="EquipModPump",
    )
    fallback_classification = DocumentationClassification(
        section_order=["em", "ops", "rp", "ep", "up"],
        categories={"em": [fallback_equipment], "ops": [], "rp": [], "ep": [], "up": []},
        uncategorized=[fallback_root],
        all_entries=[fallback_root, fallback_equipment],
    )

    top_level_root = _documented_instance(
        "LooseUnit",
        ("BasePicture", "LooseUnit"),
        moduletype_name="UnitType",
    )
    terminal_classification = DocumentationClassification(
        section_order=["em", "ops", "rp", "ep", "up"],
        categories={"em": [], "ops": [], "rp": [], "ep": [], "up": []},
        uncategorized=[top_level_root],
        all_entries=[top_level_root],
    )

    assert discover_documentation_unit_candidates(fallback_classification) == [fallback_root]
    assert discover_documentation_unit_candidates(terminal_classification) == [top_level_root]


def test_docgen_private_helpers_cover_mapping_and_support_row_filters():
    inlet_mapping = ParameterMapping(
        target={"var_name": "InletPW"},
        source_type=const.KEY_VALUE,
        is_duration=False,
        is_source_global=False,
        source={"var_name": "Feed.Line"},
        source_literal=None,
    )
    outlet_mapping = _literal_mapping("OutletPW", "Drain.Header")
    blank_mapping = _literal_mapping("Spare", None)

    equipment = _documented_instance(
        "Tank",
        ("BasePicture", "UnitA", "Tank"),
        moduletype_name="TankEM",
        localvariables=[Variable(name="Description", datatype="STRING", description="Tank description")],
        parametermappings=[inlet_mapping, outlet_mapping, blank_mapping],
    )
    state_panel = _documented_instance(
        "StateLamp",
        ("BasePicture", "UnitA", "Tank", "Panel", "StateLamp"),
        moduletype_name="StateDisplay",
    )
    toggle_panel = _documented_instance(
        "KaHCToggleStart",
        ("BasePicture", "UnitA", "Tank", "Panel", "KaHCToggleStart"),
        moduletype_name="ToggleWidget",
    )
    state_logic = _documented_instance(
        "StopLogic",
        ("BasePicture", "UnitA", "Tank", "Panel", "StateLamp", "StopLogic"),
        moduletype_name="StateLogic",
        modulecode=ModuleCode(
            equations=[Equation(name="Main", position=(0.0, 0.0), size=(1.0, 1.0), code=[True])],
            sequences=[
                Sequence(
                    name="StateSeq",
                    type="sequence",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[],
                )
            ],
        ),
    )
    message = _documented_instance(
        "OperatorMessage",
        ("BasePicture", "UnitA", "Tank", "OperatorMessage"),
        moduletype_name="OpMessageModule",
    )
    event = _documented_instance(
        "BatchJournal",
        ("BasePicture", "UnitA", "Tank", "BatchJournal"),
        moduletype_name="JournalModule",
    )
    special_log = _documented_instance(
        "AuditLog",
        ("BasePicture", "UnitA", "Tank", "AuditLog"),
        moduletype_name="LoggerModule",
    )
    classification = DocumentationClassification(
        section_order=["em", "ops", "rp", "ep", "up"],
        categories={"em": [], "ops": [], "rp": [], "ep": [], "up": []},
        uncategorized=[],
        all_entries=[equipment, state_panel, toggle_panel, state_logic, message, event, special_log],
    )
    unit = DocumentUnit(
        root=equipment,
        unit_code="UnitA",
        title="Unit A",
        unit_class="UnitType",
        section_name="Unit A",
        equipment_modules=[equipment],
        operations=[],
        recipe_parameters=[],
        engineering_parameters=[],
        user_parameters=[],
    )

    assert _mapping_target_name(inlet_mapping) == "InletPW"
    assert _mapping_source_text(inlet_mapping) == "Feed.Line"
    assert _mapping_source_text(outlet_mapping) == "Drain.Header"
    assert _mapping_source_text(blank_mapping) == ""
    assert _module_description(equipment) == "Tank description"
    assert _communication_rows(unit, direction="from") == [["Feed.Line", "Mapped via InletPW"]]
    assert _communication_rows(unit, direction="to") == [["Drain.Header", "Mapped via OutletPW"]]

    state_rows = _state_rows(equipment, classification)
    assert state_rows == [
        ["StateLamp", "Detected StateDisplay instance.", "1 state-logic modules, 1 sequences, 1 equation blocks"]
    ]
    assert _state_logic_summary(message, classification) == "Display-only state definition"
    assert [row[0] for row in _message_rows(equipment, classification)] == ["OperatorMessage"]
    assert [row[0] for row in _event_rows(equipment, classification)] == ["BatchJournal"]
    assert [row[0] for row in _special_logging_rows(equipment, classification)] == [
        "StopLogic",
        "BatchJournal",
        "AuditLog",
    ]


def test_classification_private_helpers_cover_collection_resolution_and_wrapper_variants():
    loop_type = ModuleTypeDef(
        name="LoopType",
        origin_lib="ProjectLib",
        submodules=[ModuleTypeInstance(header=_hdr("Self"), moduletype_name="LoopType")],
    )
    frame = FrameModule(header=_hdr("FrameA"), submodules=[], modulecode=None)
    unknown_instance = ModuleTypeInstance(header=_hdr("Unknown"), moduletype_name="MissingType")
    loop_instance = ModuleTypeInstance(header=_hdr("Loop"), moduletype_name="LoopType")
    base_picture = BasePicture(
        header=_hdr("BasePicture"),
        origin_lib="ProjectLib",
        moduletype_defs=[loop_type],
        submodules=[frame, unknown_instance, loop_instance],
    )

    entries = _collect_documented_modules(base_picture)
    names = [entry.name for entry in entries]

    assert names == ["FrameA", "Unknown", "Loop", "Self"]
    assert (
        _resolve_instance_moduletype(
            base_picture, unknown_instance, current_library="ProjectLib", unavailable_libraries=None
        )
        is None
    )
    assert [entry.name for entry in _descendants_of(entries[2], entries)] == ["Self"]
    assert _normalize_requested_values("bad") == []
    assert _looks_like_wrapper_name("Prefix:Panel") is True
    assert _label_variants("Parent:Child") == {"parent:child", "child"}
    assert _looks_like_equipment_module(
        _documented_instance("EM_Pump", ("BasePicture", "EM_Pump"), moduletype_name="PumpType")
    )
    assert _looks_like_operation(
        _documented_instance("Prepare", ("BasePicture", "OprFrame", "Prepare"), moduletype_name="OperationPhase")
    )
    assert not _looks_like_operation(
        _documented_instance("MES_Stop", ("BasePicture", "OprFrame", "MES_Stop"), moduletype_name="OperationPhase")
    )


def test_docgen_private_helpers_cover_scalar_and_renderer_fallback_paths(tmp_path):
    plain_source_mapping = ParameterMapping(
        target="Target",
        source_type=const.KEY_VALUE,
        is_duration=False,
        is_source_global=False,
        source=cast(Any, "Upstream.Tag"),
        source_literal=None,
    )
    ignored_target = _literal_mapping("ProgramName", "IgnoreMe")
    empty_target = _literal_mapping("", "IgnoreMe")
    configurable_target = _literal_mapping("TargetTag", "Mapped.Value")
    equipment = _documented_instance(
        "Valve",
        ("BasePicture", "UnitA", "Valve"),
        moduletype_name="ValveType",
        moduleparameters=[Variable(name="Name", datatype="STRING"), Variable(name="Speed", datatype="REAL")],
        localvariables=[Variable(name="LocalText", datatype="STRING", description="Fallback description")],
        parametermappings=[plain_source_mapping, ignored_target, empty_target, configurable_target],
    )
    unit = DocumentUnit(
        root=equipment,
        unit_code="UnitA",
        title="Unit A",
        unit_class="UnitType",
        section_name="Unit A",
        equipment_modules=[equipment],
        operations=[],
        recipe_parameters=[],
        engineering_parameters=[],
        user_parameters=[],
    )
    document = Document()
    _ensure_styles(document)
    classification = DocumentationClassification(
        section_order=["em", "ops", "rp", "ep", "up"],
        categories={"em": [], "ops": [], "rp": [], "ep": [], "up": []},
        uncategorized=[],
        all_entries=[equipment],
    )

    assert _value_text(None) == ""
    assert _value_text(5) == "5"
    assert _format_coord(None) == "<none>"
    assert _format_coord((1.0, 2.5)) == "(1, 2.5)"
    assert _prettify_name("") == ""
    assert _prettify_name("ALLCAPS") == "ALLCAPS"
    assert _mapping_source_text(plain_source_mapping) == "Upstream.Tag"
    assert _first_non_empty("", "Value") == "Value"
    assert _entry_variable(equipment, "speed") is not None
    assert _entry_variable_text(equipment, "LocalText") == "Fallback description"
    assert _configurable_parameter_rows(unit) == [
        ["Target", "", "UnitA", "Upstream.Tag"],
        ["TargetTag", "", "UnitA", "Mapped.Value"],
    ]
    assert _variable_rows([Variable(name="Speed", datatype="REAL", description="Valve speed")]) == [
        ["Speed", "real", "", "Valve speed"]
    ]

    _render_equipment_module_section(document, equipment, classification)

    assert _module_description(equipment) == "Fallback description"
    assert ["Tag", "Datatype", "Init", "Description"] in _table_headers(document)

    base_picture = _build_documentation_fixture()
    cast(Any, base_picture.submodules[0]).parametermappings = [
        _literal_mapping("OutletPW", "Downstream.Header"),
    ]
    out_path = tmp_path / "functional-spec-outbound.docx"

    generate_docx(
        base_picture,
        out_path,
        documentation_config=config_module.get_documentation_config(),
    )

    rendered = Document(out_path)
    assert ["To", "Comment"] in _table_headers(rendered)
