# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownArgumentType=false, reportPrivateUsage=false, reportMissingTypeArgument=false
from sattline_parser.models.ast_model import (
    BasePicture,
    Equation,
    FrameModule,
    ModuleCode,
    ModuleHeader,
    ModuleTypeDef,
    ModuleTypeInstance,
    Sequence,
    SFCAlternative,
    SFCBodyItem,
    SFCCodeBlocks,
    SFCParallel,
    SFCStep,
    SFCSubsequence,
    SFCTransition,
    SFCTransitionSub,
    SingleModule,
)
from sattline_parser.models.expressions import Assignment, VarRef

from sattlint.analyzers.registry import get_default_analyzers
from sattlint.analyzers.spec_compliance import SpecComplianceAnalyzer, analyze_spec_compliance


def _hdr(name: str) -> ModuleHeader:
    return ModuleHeader(name=name, invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0))


def _sequence(*nodes: SFCBodyItem) -> Sequence:
    return Sequence(
        name="SeqMain",
        type="sequence",
        position=(0.0, 0.0),
        size=(1.0, 1.0),
        code=list(nodes),
    )


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


def test_single_module_sequences_cover_nested_branch_nodes():
    bp = BasePicture(
        header=_hdr("Root"),
        submodules=[
            SingleModule(
                header=_hdr("Unit"),
                moduledef=None,
                moduleparameters=[],
                localvariables=[],
                submodules=[],
                modulecode=ModuleCode(
                    sequences=[
                        _sequence(
                            SFCAlternative(branches=[[SFCStep(kind="init", name="AltStart", code=SFCCodeBlocks())]]),
                            SFCParallel(branches=[[SFCTransition(name="ParallelGate", condition=True)]]),
                            SFCSubsequence(
                                name="NestedSeq",
                                body=[SFCStep(kind="step", name="NestedStep", code=SFCCodeBlocks())],
                            ),
                            SFCTransitionSub(
                                name="NestedGate",
                                body=[SFCTransition(name=None, condition=True)],
                            ),
                        )
                    ]
                ),
            )
        ],
    )

    report = analyze_spec_compliance(bp)

    kinds = {issue.kind for issue in report.issues}
    assert "spec.sequence_step_prefix" in kinds
    assert "spec.transition_prefix" in kinds
    assert "spec.transition_name_missing" in kinds


def test_spec_compliance_helper_origin_fallback():
    analyzer = SpecComplianceAnalyzer(BasePicture(header=_hdr("Root"), localvariables=[]))

    assert analyzer._is_from_root_origin(None) is True
    assert analyzer._is_from_root_origin("OtherLib.s") is False


def test_spec_compliance_analyzer_is_enabled_by_default():
    specs = {spec.key: spec for spec in get_default_analyzers()}

    assert "spec-compliance" in specs
    assert specs["spec-compliance"].enabled is True


def test_step_prefix_is_configurable():
    step = SFCStep(kind="init", name="START_Init", code=SFCCodeBlocks())
    bp = BasePicture(
        header=_hdr("Root"),
        submodules=[
            FrameModule(
                header=_hdr("Logic"),
                modulecode=ModuleCode(sequences=[_sequence(step)]),
            )
        ],
    )

    report = analyze_spec_compliance(bp, config={"analysis": {"spec_compliance": {"step_prefix": "START_"}}})

    assert not any(issue.kind == "spec.sequence_step_prefix" for issue in report.issues)


def test_transition_prefix_is_configurable():
    step = SFCStep(kind="init", name="ST_Start", code=SFCCodeBlocks())
    transition = SFCTransition(name="G_Next", condition=True)
    bp = BasePicture(
        header=_hdr("Root"),
        submodules=[
            FrameModule(
                header=_hdr("Logic"),
                modulecode=ModuleCode(sequences=[_sequence(step, transition)]),
            )
        ],
    )

    report = analyze_spec_compliance(bp, config={"analysis": {"spec_compliance": {"transition_prefix": "G_"}}})

    assert not any(issue.kind == "spec.transition_prefix" for issue in report.issues)


def test_sequence_name_prefix_check_is_opt_in():
    sequence = Sequence(
        name="MixSeq",
        type="sequence",
        position=(0.0, 0.0),
        size=(1.0, 1.0),
        code=[SFCStep(kind="init", name="ST_Start", code=SFCCodeBlocks())],
    )
    bp = BasePicture(
        header=_hdr("Root"),
        submodules=[FrameModule(header=_hdr("Logic"), modulecode=ModuleCode(sequences=[sequence]))],
    )

    default_report = analyze_spec_compliance(bp)
    assert not any(issue.kind == "spec.sequence_name_prefix" for issue in default_report.issues)

    configured_report = analyze_spec_compliance(
        bp, config={"analysis": {"spec_compliance": {"sequence_prefix": "SEQ_"}}}
    )
    issues = [issue for issue in configured_report.issues if issue.kind == "spec.sequence_name_prefix"]
    assert len(issues) == 1
    assert issues[0].data is not None
    assert issues[0].data["sequence"] == "MixSeq"


def test_equation_block_name_prefix_check_is_opt_in():
    bp = BasePicture(
        header=_hdr("Root"),
        submodules=[
            FrameModule(
                header=_hdr("Logic"),
                modulecode=ModuleCode(
                    equations=[
                        Equation(
                            name="MainEq",
                            position=(0.0, 0.0),
                            size=(1.0, 1.0),
                            code=[Assignment(target=VarRef(name="Out"), value=True)],
                        )
                    ]
                ),
            )
        ],
    )

    default_report = analyze_spec_compliance(bp)
    assert not any(issue.kind == "spec.equation_block_prefix" for issue in default_report.issues)

    configured_report = analyze_spec_compliance(
        bp, config={"analysis": {"spec_compliance": {"equation_prefix": "EQ_"}}}
    )
    issues = [issue for issue in configured_report.issues if issue.kind == "spec.equation_block_prefix"]
    assert len(issues) == 1
    assert issues[0].data is not None
    assert issues[0].data["equation"] == "MainEq"
