from pathlib import Path

from docx import Document

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
    ModuleTypeDef,
    ModuleTypeInstance,
)


def _hdr(name: str) -> ModuleHeader:
    return ModuleHeader(name=name, invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0))


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
    assert "Equipment Module Tank" in paragraph_text
    assert "Operation Prepare" in paragraph_text


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
