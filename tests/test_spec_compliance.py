from sattlint import constants as const
from sattlint.analyzers.registry import get_default_analyzers
from sattlint.analyzers.spec_compliance import analyze_spec_compliance
from sattlint.models.ast_model import (
    BasePicture,
    FrameModule,
    ModuleCode,
    ModuleHeader,
    ModuleTypeDef,
    ModuleTypeInstance,
    ParameterMapping,
    Sequence,
    SFCCodeBlocks,
    SFCStep,
    SFCTransition,
    Simple_DataType,
    Variable,
)


def _hdr(name: str) -> ModuleHeader:
    return ModuleHeader(name=name, invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0))


def _varref(name: str) -> dict:
    return {const.KEY_VAR_NAME: name}


def _sequence(*nodes: object) -> Sequence:
    return Sequence(
        name="SeqMain",
        type="sequence",
        position=(0.0, 0.0),
        size=(1.0, 1.0),
        code=list(nodes),
    )


def test_basepicture_direct_code_is_reported():
    bp = BasePicture(
        header=_hdr("Root"),
        modulecode=ModuleCode(sequences=[_sequence()]),
    )

    report = analyze_spec_compliance(bp)

    assert any(issue.kind == "spec.basepicture_direct_code" for issue in report.issues)


def test_basepicture_code_inside_frame_module_is_allowed():
    frame = FrameModule(
        header=_hdr("CodeFrame"),
        modulecode=ModuleCode(sequences=[_sequence()]),
    )
    bp = BasePicture(
        header=_hdr("Root"),
        submodules=[frame],
    )

    report = analyze_spec_compliance(bp)

    assert not any(issue.kind == "spec.basepicture_direct_code" for issue in report.issues)


def test_sequence_step_prefix_is_reported():
    step = SFCStep(kind="init", name="Start", code=SFCCodeBlocks())
    transition = SFCTransition(name="TR_Next", condition=True)
    bp = BasePicture(
        header=_hdr("Root"),
        submodules=[
            FrameModule(
                header=_hdr("Logic"),
                modulecode=ModuleCode(sequences=[_sequence(step, transition)]),
            )
        ],
    )

    report = analyze_spec_compliance(bp)

    assert any(issue.kind == "spec.sequence_step_prefix" for issue in report.issues)


def test_transition_name_is_required():
    step = SFCStep(kind="init", name="ST_Start", code=SFCCodeBlocks())
    transition = SFCTransition(name=None, condition=True)
    bp = BasePicture(
        header=_hdr("Root"),
        submodules=[
            FrameModule(
                header=_hdr("Logic"),
                modulecode=ModuleCode(sequences=[_sequence(step, transition)]),
            )
        ],
    )

    report = analyze_spec_compliance(bp)

    assert any(issue.kind == "spec.transition_name_missing" for issue in report.issues)


def test_transition_prefix_is_reported():
    step = SFCStep(kind="init", name="ST_Start", code=SFCCodeBlocks())
    transition = SFCTransition(name="ToNext", condition=True)
    bp = BasePicture(
        header=_hdr("Root"),
        submodules=[
            FrameModule(
                header=_hdr("Logic"),
                modulecode=ModuleCode(sequences=[_sequence(step, transition)]),
            )
        ],
    )

    report = analyze_spec_compliance(bp)

    assert any(issue.kind == "spec.transition_prefix" for issue in report.issues)


def test_opmessage_use_signature_true_is_reported():
    opmessage = ModuleTypeDef(
        name="OPMessage",
        origin_lib="NNESystem",
        origin_file="Root.s",
        moduleparameters=[
            Variable(name="UseSignature", datatype=Simple_DataType.BOOLEAN, init_value=False)
        ],
    )
    instance = ModuleTypeInstance(
        header=_hdr("Prompt"),
        moduletype_name="OPMessage",
        parametermappings=[
            ParameterMapping(
                target=_varref("UseSignature"),
                source_type=const.KEY_VALUE,
                is_duration=False,
                is_source_global=False,
                source_literal=True,
            )
        ],
    )
    bp = BasePicture(
        header=_hdr("Root"),
        origin_file="Root.s",
        moduletype_defs=[opmessage],
        submodules=[instance],
    )

    report = analyze_spec_compliance(bp)

    assert any(issue.kind == "spec.opmessage_use_signature" for issue in report.issues)


def test_mes_batch_control_contract_is_reported():
    mes = ModuleTypeDef(
        name="MES_BatchControl",
        origin_lib="NNEMESIFLib",
        origin_file="Root.s",
        moduleparameters=[
            Variable(name="Max_TRY", datatype=Simple_DataType.INTEGER, init_value=5),
            Variable(name="Repeat_TRY", datatype=Simple_DataType.INTEGER),
        ],
    )
    instance = ModuleTypeInstance(
        header=_hdr("BatchCtrl"),
        moduletype_name="MES_BatchControl",
        parametermappings=[],
    )
    bp = BasePicture(
        header=_hdr("Root"),
        origin_file="Root.s",
        moduletype_defs=[mes],
        submodules=[instance],
    )

    report = analyze_spec_compliance(bp)

    kinds = {issue.kind for issue in report.issues}
    assert "spec.mes_batch_control_name" in kinds
    assert "spec.mes_batch_control_max_try" in kinds
    assert "spec.mes_batch_control_repeat_try" in kinds


def test_mes_batch_control_variable_init_mapping_is_accepted():
    mes = ModuleTypeDef(
        name="MES_BatchControl",
        origin_lib="NNEMESIFLib",
        origin_file="Root.s",
        moduleparameters=[
            Variable(name="Max_TRY", datatype=Simple_DataType.INTEGER),
            Variable(name="Repeat_TRY", datatype=Simple_DataType.INTEGER),
        ],
    )
    instance = ModuleTypeInstance(
        header=_hdr("MES_BatchControl"),
        moduletype_name="MES_BatchControl",
        parametermappings=[
            ParameterMapping(
                target=_varref("Max_TRY"),
                source_type=const.TREE_TAG_VARIABLE_NAME,
                is_duration=False,
                is_source_global=False,
                source=_varref("ConfiguredMaxTry"),
            ),
            ParameterMapping(
                target=_varref("Repeat_TRY"),
                source_type=const.TREE_TAG_VARIABLE_NAME,
                is_duration=False,
                is_source_global=False,
                source=_varref("ConfiguredRepeatTry"),
            ),
        ],
    )
    bp = BasePicture(
        header=_hdr("Root"),
        origin_file="Root.s",
        localvariables=[
            Variable(name="ConfiguredMaxTry", datatype=Simple_DataType.INTEGER, init_value=10),
            Variable(name="ConfiguredRepeatTry", datatype=Simple_DataType.INTEGER, init_value=20),
        ],
        moduletype_defs=[mes],
        submodules=[instance],
    )

    report = analyze_spec_compliance(bp)

    assert not any(issue.kind.startswith("spec.mes_batch_control_") for issue in report.issues)


def test_mes_batch_control_unresolved_mapping_is_reported():
    mes = ModuleTypeDef(
        name="MES_BatchControl",
        origin_lib="NNEMESIFLib",
        origin_file="Root.s",
        moduleparameters=[
            Variable(name="Max_TRY", datatype=Simple_DataType.INTEGER),
            Variable(name="Repeat_TRY", datatype=Simple_DataType.INTEGER),
        ],
    )
    instance = ModuleTypeInstance(
        header=_hdr("MES_BatchControl"),
        moduletype_name="MES_BatchControl",
        parametermappings=[
            ParameterMapping(
                target=_varref("Max_TRY"),
                source_type=const.TREE_TAG_VARIABLE_NAME,
                is_duration=False,
                is_source_global=False,
                source=_varref("RuntimeConfiguredMaxTry"),
            ),
            ParameterMapping(
                target=_varref("Repeat_TRY"),
                source_type=const.KEY_VALUE,
                is_duration=False,
                is_source_global=False,
                source_literal=20,
            ),
        ],
    )
    bp = BasePicture(
        header=_hdr("Root"),
        origin_file="Root.s",
        moduletype_defs=[mes],
        submodules=[instance],
    )

    report = analyze_spec_compliance(bp)

    issues = [issue for issue in report.issues if issue.kind == "spec.mes_batch_control_max_try"]
    assert len(issues) == 1
    assert "could not be resolved statically" in issues[0].message


def test_external_moduletype_sequence_rules_are_skipped_for_program_target():
    external = ModuleTypeDef(
        name="ExternalType",
        origin_lib="SomeLib",
        origin_file="OtherLib.s",
        modulecode=ModuleCode(
            sequences=[
                _sequence(
                    SFCStep(kind="init", name="Start", code=SFCCodeBlocks()),
                    SFCTransition(name="TR_Next", condition=True),
                )
            ]
        ),
    )
    bp = BasePicture(
        header=_hdr("Root"),
        origin_file="Root.s",
        moduletype_defs=[external],
        submodules=[
            ModuleTypeInstance(
                header=_hdr("External"),
                moduletype_name="ExternalType",
            )
        ],
    )

    report = analyze_spec_compliance(bp)

    assert not any(issue.kind == "spec.sequence_step_prefix" for issue in report.issues)


def test_spec_compliance_analyzer_is_enabled_by_default():
    specs = {spec.key: spec for spec in get_default_analyzers()}

    assert "spec-compliance" in specs
    assert specs["spec-compliance"].enabled is True
