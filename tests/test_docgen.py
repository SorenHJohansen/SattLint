
from typing import Any, cast

from docx import Document
from docx.document import Document as DocClass
from sattline_parser.grammar import constants as const

from sattlint import config as config_module
from sattlint.docgenerator.classification import (
    classify_documentation_structure,
    discover_documentation_unit_candidates,
)
from sattlint.docgenerator.docgen import generate_docx
from sattlint.models.ast_model import (
    BasePicture,
    Equation,
    ModuleCode,
    ModuleHeader,
    ParameterMapping,
    SFCCodeBlocks,
    SFCStep,
    SFCTransition,
    SingleModule,
    ModuleTypeDef,
    ModuleTypeInstance,
    Sequence,
    Variable,
)


def _hdr(name: str) -> ModuleHeader:
    return ModuleHeader(name=name, invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0))


def _literal_mapping(target: str, value: object) -> ParameterMapping:
    return ParameterMapping(
        target=target,
        source_type=const.KEY_VALUE,
        is_duration=False,
        is_source_global=False,
        source=None,
        source_literal=value,
    )


def _table_headers(document: DocClass) -> list[list[str]]:
    return [[cell.text.strip() for cell in table.rows[0].cells] for table in document.tables if table.rows]


def _table_text(document: DocClass) -> list[str]:
    return [cell.text.strip() for table in document.tables for row in table.rows for cell in row.cells if cell.text.strip()]


def _build_documentation_fixture() -> BasePicture:
    mes_state_control = ModuleTypeDef(name="MES_StateControl", origin_lib="NNEMESIFLib")
    equip_marker = ModuleTypeDef(name="EquipModCoordinate", origin_lib="nnestruct")
    recipe_param = ModuleTypeDef(name="RecParReal", origin_lib="NNELib")
    engineering_param = ModuleTypeDef(name="EngParReal", origin_lib="NNELib")
    user_param = ModuleTypeDef(name="UsrParReal", origin_lib="NNELib")

    operation_wrapper = ModuleTypeDef(
        name="OperationWrapper",
        origin_lib="ProjectLib",
        submodules=[
            ModuleTypeInstance(header=_hdr("MESInfo"), moduletype_name="MES_StateControl"),
            ModuleTypeInstance(header=_hdr("RecipeSP"), moduletype_name="RecParReal"),
            ModuleTypeInstance(header=_hdr("EngineeringLimit"), moduletype_name="EngParReal"),
            ModuleTypeInstance(header=_hdr("UserTarget"), moduletype_name="UsrParReal"),
        ],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Main",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=["Ready = True"],
                )
            ]
        ),
    )

    equipment_wrapper = ModuleTypeDef(
        name="TankEM",
        origin_lib="ProjectLib",
        submodules=[
            ModuleTypeInstance(header=_hdr("Coordinate"), moduletype_name="EquipModCoordinate"),
            ModuleTypeInstance(header=_hdr("SpeedLimit"), moduletype_name="EngParReal"),
        ],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Physical",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=["ValveOpen = True"],
                )
            ]
        ),
    )

    appl_tank = ModuleTypeDef(
        name="ApplTank",
        origin_lib="ProjectLib",
        submodules=[
            ModuleTypeInstance(header=_hdr("Prepare"), moduletype_name="OperationWrapper"),
            ModuleTypeInstance(header=_hdr("Tank"), moduletype_name="TankEM"),
        ],
    )

    dilute_unit = ModuleTypeDef(
        name="XDilute_221X251XY",
        origin_lib="ProjectLib",
        submodules=[
            ModuleTypeInstance(header=_hdr("DiluteTank"), moduletype_name="TankEM"),
        ],
    )

    return BasePicture(
        header=_hdr("BasePicture"),
        origin_lib="ProjectLib",
        moduletype_defs=[
            mes_state_control,
            equip_marker,
            recipe_param,
            engineering_param,
            user_param,
            operation_wrapper,
            equipment_wrapper,
            appl_tank,
            dilute_unit,
        ],
        submodules=[
            ModuleTypeInstance(header=_hdr("UnitA"), moduletype_name="ApplTank"),
            ModuleTypeInstance(header=_hdr("DilutionTrain"), moduletype_name="XDilute_221X251XY"),
            ModuleTypeInstance(header=_hdr("GlobalLimit"), moduletype_name="EngParReal"),
        ],
        library_dependencies={"projectlib": ["nnemesiflib", "nnestruct", "nnelib"]},
    )


def _build_wrapper_documentation_fixture() -> BasePicture:
    mes_state_control = ModuleTypeDef(name="MES_StateControl")
    equip_marker = ModuleTypeDef(name="EquipModCoordinate")
    state_logic = ModuleTypeDef(name="StateLogic")
    analog_input = ModuleTypeDef(name="AnalogInput")
    recipe_param = ModuleTypeDef(name="RecParReal")
    engineering_param = ModuleTypeDef(name="EngParReal")

    operation_l2 = ModuleTypeDef(
        name="OperationL2",
        submodules=[
            ModuleTypeInstance(header=_hdr("MES_StateControl"), moduletype_name="MES_StateControl"),
        ],
    )
    operation_l1 = ModuleTypeDef(
        name="OperationL1",
        submodules=[
            ModuleTypeInstance(header=_hdr("L2"), moduletype_name="OperationL2"),
        ],
    )
    operation_wrapper = ModuleTypeDef(
        name="OperationWrapper",
        submodules=[
            ModuleTypeInstance(header=_hdr("L1"), moduletype_name="OperationL1"),
            ModuleTypeInstance(header=_hdr("RecipeSP"), moduletype_name="RecParReal"),
            ModuleTypeInstance(header=_hdr("EngineeringLimit"), moduletype_name="EngParReal"),
        ],
    )
    opr_frame = ModuleTypeDef(
        name="OprFrameWrapper",
        submodules=[
            ModuleTypeInstance(
                header=_hdr("Prepare"),
                moduletype_name="OperationWrapper",
                parametermappings=[_literal_mapping("Name", "Prepare")],
            ),
        ],
    )
    operations = ModuleTypeDef(
        name="OperationsWrapper",
        submodules=[
            ModuleTypeInstance(header=_hdr("OprFrame"), moduletype_name="OprFrameWrapper"),
        ],
    )
    unit_control = ModuleTypeDef(
        name="UnitControlWrapper",
        submodules=[
            ModuleTypeInstance(header=_hdr("Operations"), moduletype_name="OperationsWrapper"),
        ],
    )

    equip_panel = ModuleTypeDef(
        name="EquipPanel",
        submodules=[
            ModuleTypeInstance(header=_hdr("Coordinate"), moduletype_name="EquipModCoordinate"),
            ModuleTypeInstance(header=_hdr("Stop"), moduletype_name="StateLogic"),
        ],
    )
    equip_display = ModuleTypeDef(
        name="EquipDisplay",
        submodules=[
            ModuleTypeInstance(header=_hdr("Panel"), moduletype_name="EquipPanel"),
        ],
    )
    equip_l2 = ModuleTypeDef(
        name="EquipL2",
        submodules=[
            ModuleTypeInstance(header=_hdr("Display"), moduletype_name="EquipDisplay"),
        ],
    )
    equip_l1 = ModuleTypeDef(
        name="EquipL1",
        submodules=[
            ModuleTypeInstance(header=_hdr("L2"), moduletype_name="EquipL2"),
        ],
    )
    tank_em = ModuleTypeDef(
        name="TankEM",
        moduleparameters=[Variable(name="Name", datatype="STRING")],
        submodules=[
            ModuleTypeInstance(header=_hdr("L1"), moduletype_name="EquipL1"),
            ModuleTypeInstance(header=_hdr("SpeedLimit"), moduletype_name="EngParReal"),
        ],
    )

    unit_type = ModuleTypeDef(
        name="UnitType",
        moduleparameters=[
            Variable(name="Name", datatype="STRING"),
            Variable(name="HeaderName", datatype="STRING"),
            Variable(name="SectionName", datatype="STRING"),
            Variable(name="InletPW", datatype="STRING"),
        ],
        submodules=[
            ModuleTypeInstance(
                header=_hdr("EM_FILL"),
                moduletype_name="TankEM",
                parametermappings=[_literal_mapping("Name", "Fill")],
            ),
            ModuleTypeInstance(header=_hdr("TT100"), moduletype_name="AnalogInput"),
            ModuleTypeInstance(header=_hdr("UnitControl"), moduletype_name="UnitControlWrapper"),
        ],
    )

    return BasePicture(
        header=_hdr("BasePicture"),
        moduletype_defs=[
            mes_state_control,
            equip_marker,
            state_logic,
            analog_input,
            recipe_param,
            engineering_param,
            operation_l2,
            operation_l1,
            operation_wrapper,
            opr_frame,
            operations,
            unit_control,
            equip_panel,
            equip_display,
            equip_l2,
            equip_l1,
            tank_em,
            unit_type,
        ],
        submodules=[
            ModuleTypeInstance(
                header=_hdr("UnitA"),
                moduletype_name="UnitType",
                parametermappings=[
                    _literal_mapping("Name", "238A"),
                    _literal_mapping("HeaderName", "UF/DF Tank"),
                    _literal_mapping("SectionName", "UF/DF"),
                    _literal_mapping("InletPW", "PWTransfer"),
                ],
            ),
        ],
    )


def _build_sequence_doc_fixture() -> BasePicture:
    mes_state_control = ModuleTypeDef(name="MES_StateControl")
    recipe_param = ModuleTypeDef(name="RecParReal")
    engineering_param = ModuleTypeDef(name="EngParReal")

    operation_wrapper = ModuleTypeDef(
        name="OperationWrapper",
        submodules=[
            ModuleTypeInstance(header=_hdr("MESInfo"), moduletype_name="MES_StateControl"),
            ModuleTypeInstance(header=_hdr("RecipeSP"), moduletype_name="RecParReal"),
            ModuleTypeInstance(header=_hdr("EngineeringLimit"), moduletype_name="EngParReal"),
        ],
        modulecode=ModuleCode(
            sequences=[
                Sequence(
                    name="MainSequence",
                    type="sequence",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        SFCStep(
                            kind="init",
                            name="Init",
                            code=SFCCodeBlocks(
                                exit=[("assign", {"var_name": "p.GotoRunDone"}, True)]
                            ),
                        ),
                        SFCTransition(
                            name="Tr1",
                            condition=(
                                "OR",
                                [
                                    {"var_name": "p.GotoRun"},
                                    {"var_name": "p.Run"},
                                ],
                            ),
                        ),
                        SFCStep(
                            kind="step",
                            name="Tarering",
                            code=SFCCodeBlocks(
                                enter=[
                                    (
                                        "FunctionCall",
                                        "CopyString",
                                        [
                                            {"var_name": "StepText.Tarering"},
                                            {"var_name": "Step"},
                                            {"var_name": "si"},
                                        ],
                                    )
                                ],
                                exit=[("assign", {"var_name": "Dv.Tara_execute"}, True)],
                            ),
                        ),
                        SFCTransition(
                            name="Tr2",
                            condition=(
                                "AND",
                                [
                                    ("NOT", {"var_name": "Dv.Tara_execute"}),
                                    ("NOT", {"var_name": "ProfibusError"}),
                                ],
                            ),
                        ),
                    ],
                )
            ]
        ),
    )

    unit_type = ModuleTypeDef(
        name="UnitType",
        moduleparameters=[
            Variable(name="Name", datatype="STRING"),
            Variable(name="HeaderName", datatype="STRING"),
            Variable(name="SectionName", datatype="STRING"),
        ],
        submodules=[
            ModuleTypeInstance(
                header=_hdr("Prepare"),
                moduletype_name="OperationWrapper",
                parametermappings=[_literal_mapping("Name", "Prepare")],
            ),
        ],
    )

    return BasePicture(
        header=_hdr("BasePicture"),
        moduletype_defs=[
            mes_state_control,
            recipe_param,
            engineering_param,
            operation_wrapper,
            unit_type,
        ],
        submodules=[
            ModuleTypeInstance(
                header=_hdr("UnitA"),
                moduletype_name="UnitType",
                parametermappings=[
                    _literal_mapping("Name", "238A"),
                    _literal_mapping("HeaderName", "UF/DF Tank"),
                    _literal_mapping("SectionName", "UF/DF"),
                ],
            ),
        ],
    )


def _build_version_drift_doc_fixture() -> BasePicture:
    variant_a = SingleModule(
        header=_hdr("Mixer"),
        datecode=100,
        moduledef=None,
        moduleparameters=[],
        localvariables=[Variable(name="Output", datatype="INTEGER")],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Logic",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[("assign", {"var_name": "Output"}, 1)],
                )
            ],
            sequences=[],
        ),
        parametermappings=[],
    )
    variant_b = SingleModule(
        header=_hdr("Mixer"),
        datecode=200,
        moduledef=None,
        moduleparameters=[],
        localvariables=[Variable(name="Output", datatype="INTEGER")],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Logic",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[("assign", {"var_name": "Output"}, 2)],
                )
            ],
            sequences=[],
        ),
        parametermappings=[],
    )
    cast(Any, variant_a).origin_file = "BasePicture.s"
    cast(Any, variant_b).origin_file = "BasePicture.s"
    return BasePicture(
        header=_hdr("BasePicture"),
        origin_file="BasePicture.s",
        submodules=[variant_a, variant_b],
    )


def test_classify_documentation_structure_detects_recursive_categories():
    base_picture = _build_documentation_fixture()

    classification = classify_documentation_structure(
        base_picture,
        config_module.get_documentation_config(),
    )

    operations = {entry.name for entry in classification.categories["ops"]}
    equipment_modules = {entry.name for entry in classification.categories["em"]}
    recipe_parameters = {entry.name for entry in classification.categories["rp"]}
    engineering_parameters = {entry.name for entry in classification.categories["ep"]}
    user_parameters = {entry.name for entry in classification.categories["up"]}

    assert operations == {"Prepare"}
    assert equipment_modules == {"Tank", "DiluteTank"}
    assert "RecipeSP" in recipe_parameters
    assert "EngineeringLimit" in engineering_parameters
    assert "GlobalLimit" in engineering_parameters
    assert "UserTarget" in user_parameters

    operation_entry = classification.categories["ops"][0]
    assert {entry.name for entry in classification.descendants(operation_entry, category="rp")} == {"RecipeSP"}


def test_generate_docx_renders_fs_style_sections(tmp_path):
    base_picture = _build_documentation_fixture()
    out_path = tmp_path / "functional-spec.docx"

    generate_docx(
        base_picture,
        out_path,
        documentation_config=config_module.get_documentation_config(),
    )

    assert out_path.exists()

    document = Document(out_path)
    paragraph_text = [paragraph.text.strip() for paragraph in document.paragraphs if paragraph.text.strip()]

    assert "Introduction" in paragraph_text
    assert "S88 Physical model" in paragraph_text
    assert "S88 Procedural model" in paragraph_text
    assert "Measurements and logging" in paragraph_text
    assert "Communication" in paragraph_text
    assert "Equipment Module Tank" in paragraph_text
    assert "Operation Prepare" in paragraph_text
    assert "Change Log" in paragraph_text


def test_classify_documentation_scope_by_moduletype_name():
    base_picture = _build_documentation_fixture()
    documentation_cfg = config_module.get_documentation_config()
    documentation_cfg["units"] = {
        "mode": "moduletype_names",
        "instance_paths": [],
        "moduletype_names": ["ApplTank"],
    }

    classification = classify_documentation_structure(base_picture, documentation_cfg)

    assert classification.scope is not None
    assert [entry.name for entry in classification.scope.roots or []] == ["UnitA"]
    assert {entry.name for entry in classification.categories["ops"]} == {"Prepare"}
    assert {entry.name for entry in classification.categories["em"]} == {"Tank"}


def test_discover_documentation_unit_candidates_returns_unit_roots():
    base_picture = _build_documentation_fixture()
    classification = classify_documentation_structure(
        base_picture,
        config_module.get_documentation_config(),
    )

    candidates = discover_documentation_unit_candidates(classification)

    assert {entry.name for entry in candidates} == {"UnitA", "DilutionTrain"}


def test_wrapper_heavy_classification_anchors_real_sections():
    base_picture = _build_wrapper_documentation_fixture()

    classification = classify_documentation_structure(
        base_picture,
        config_module.get_documentation_config(),
    )

    assert {entry.name for entry in classification.categories["em"]} == {"EM_FILL"}
    assert {entry.name for entry in classification.categories["ops"]} == {"Prepare"}

    candidates = discover_documentation_unit_candidates(classification)
    assert {entry.name for entry in candidates} == {"UnitA"}


def test_generate_docx_renders_wrapper_heavy_fs_sections(tmp_path):
    base_picture = _build_wrapper_documentation_fixture()
    out_path = tmp_path / "functional-spec-wrapper.docx"

    generate_docx(
        base_picture,
        out_path,
        documentation_config=config_module.get_documentation_config(),
    )

    document = Document(out_path)
    paragraph_text = [paragraph.text.strip() for paragraph in document.paragraphs if paragraph.text.strip()]

    assert "Process Cell - UF/DF" in paragraph_text
    assert "Unit Class definition: UF/DF Tank" in paragraph_text
    assert "Measurements and logging" in paragraph_text
    assert "Communication" in paragraph_text
    assert "Equipment Module Fill" in paragraph_text
    assert "Operation Prepare" in paragraph_text
    assert "Change Log" in paragraph_text


def test_generate_docx_respects_single_unit_scope(tmp_path):
    base_picture = _build_documentation_fixture()
    out_path = tmp_path / "functional-spec-scoped.docx"
    documentation_cfg = config_module.get_documentation_config()
    documentation_cfg["units"] = {
        "mode": "moduletype_names",
        "instance_paths": [],
        "moduletype_names": ["ApplTank"],
    }

    generate_docx(
        base_picture,
        out_path,
        documentation_config=documentation_cfg,
    )

    document = Document(out_path)
    paragraph_text = [paragraph.text.strip() for paragraph in document.paragraphs if paragraph.text.strip()]

    assert "Operation Prepare" in paragraph_text
    assert "Equipment Module Tank" in paragraph_text
    assert "DilutionTrain" not in paragraph_text
    assert "Equipment Module DiluteTank" not in paragraph_text


def test_generate_docx_uses_template_shaped_front_matter_and_tables(tmp_path):
    base_picture = _build_wrapper_documentation_fixture()
    out_path = tmp_path / "functional-spec-template-shaped.docx"

    generate_docx(
        base_picture,
        out_path,
        documentation_config=config_module.get_documentation_config(),
    )

    document = Document(out_path)
    headers = _table_headers(document)

    assert ["NNE Author", "NNE Author", "NNE Author"] in headers
    assert ["", "Document", "NN Doc. no."] in headers
    assert ["Unit", "Unit Class", "Danish Description", "Unit Definition"] in headers
    assert ["Measurement", "Tag", "Min", "Max", "Eng. Unit", "Log interval\n(Max)", "Dead-band\nrelative", "Log interval \n(Min)"] in headers
    assert ["From", "Comment"] in headers


def test_generate_docx_renders_upgrade_insights_for_version_drift(tmp_path):
    base_picture = _build_version_drift_doc_fixture()
    out_path = tmp_path / "functional-spec-upgrades.docx"

    generate_docx(
        base_picture,
        out_path,
        documentation_config=config_module.get_documentation_config(),
    )

    document = Document(out_path)
    paragraph_text = [paragraph.text.strip() for paragraph in document.paragraphs if paragraph.text.strip()]

    assert "Upgrade insights" in paragraph_text
    assert "Module Mixer" in paragraph_text
    assert any("Equation 'Logic' changed" in paragraph for paragraph in paragraph_text)


def test_generate_docx_renders_sfc_sequences_as_tables(tmp_path):
    base_picture = _build_sequence_doc_fixture()
    out_path = tmp_path / "functional-spec-sfc.docx"

    generate_docx(
        base_picture,
        out_path,
        documentation_config=config_module.get_documentation_config(),
    )

    document = Document(out_path)
    headers = _table_headers(document)
    table_text = _table_text(document)

    assert ["Type", "Name", "Condition / Detail", "Enter", "Active", "Exit"] in headers
    assert "Sub sequence - MainSequence" in [paragraph.text.strip() for paragraph in document.paragraphs if paragraph.text.strip()]
    assert "Init step" in table_text
    assert "Init" in table_text
    assert "p.GotoRunDone = True" in table_text
    assert "Transition" in table_text
    assert "Tr1" in table_text
    assert "p.GotoRun OR \np.Run" in table_text
    assert "Step" in table_text
    assert "Tarering" in table_text
    assert "CopyString(StepText.Tarering, Step, si)" in table_text
    assert "NOT(Dv.Tara_execute) AND \nNOT(ProfibusError)" in table_text
    assert not any("SFCStep(" in text for text in table_text)
    assert not any("SFCTransition(" in text for text in table_text)
