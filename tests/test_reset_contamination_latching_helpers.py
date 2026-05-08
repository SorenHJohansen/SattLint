from __future__ import annotations

from types import SimpleNamespace

from sattline_parser.models.ast_model import (
    BasePicture,
    Equation,
    FrameModule,
    ModuleCode,
    ModuleHeader,
    Sequence,
    SFCAlternative,
    SFCCodeBlocks,
    SFCParallel,
    SFCStep,
    SFCSubsequence,
    SFCTransition,
    SFCTransitionSub,
    Simple_DataType,
    SingleModule,
    Variable,
)
from sattlint import constants as const
from sattlint.analyzers import reset_contamination as reset_contamination_module
from sattlint.reporting.variables_report import IssueKind, VariableIssue


def _hdr(name: str) -> ModuleHeader:
    return ModuleHeader(name=name, invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0))


def _varref(name: str) -> dict[str, str]:
    return {const.KEY_VAR_NAME: name}


def _eq(name: str, code: list[object]) -> Equation:
    return Equation(name=name, position=(0.0, 0.0), size=(1.0, 1.0), code=code)


def _seq(name: str, code: list[object]) -> Sequence:
    return Sequence(name=name, type="sequence", position=(0.0, 0.0), size=(1.0, 1.0), code=code)


def _bool_step(name: str, statements: list[object]) -> SFCStep:
    return SFCStep(kind="step", name=name, code=SFCCodeBlocks(active=statements))


def test_detection_walks_frame_submodules_for_reset_and_latching() -> None:
    child = SingleModule(
        header=_hdr("Child"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[
            Variable(name="Counter", datatype=Simple_DataType.INTEGER),
            Variable(name="Other", datatype=Simple_DataType.INTEGER),
            Variable(name="ResetValue", datatype=Simple_DataType.INTEGER),
            Variable(name="SeqResetOld", datatype=Simple_DataType.BOOLEAN),
            Variable(name="Start", datatype=Simple_DataType.BOOLEAN),
            Variable(name="Latch", datatype=Simple_DataType.BOOLEAN),
        ],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                _eq(
                    "ResetEq",
                    [
                        (
                            const.GRAMMAR_VALUE_IF,
                            [
                                (
                                    (const.GRAMMAR_VALUE_NOT, _varref("OpSeq.Reset")),
                                    [(const.KEY_ASSIGN, _varref("Counter"), _varref("ResetValue"))],
                                ),
                                (
                                    (const.GRAMMAR_VALUE_NOT, _varref("SeqResetOld")),
                                    [(const.KEY_ASSIGN, _varref("Other"), _varref("ResetValue"))],
                                ),
                            ],
                            [],
                        ),
                        (const.KEY_ASSIGN, _varref("SeqResetOld"), _varref("OpSeq.Reset")),
                    ],
                ),
                _eq(
                    "LatchEq",
                    [
                        (
                            const.GRAMMAR_VALUE_IF,
                            [(_varref("Start"), [(const.KEY_ASSIGN, _varref("Latch"), True)])],
                            [],
                        )
                    ],
                ),
            ],
            sequences=[_seq("OpSeq", [])],
        ),
        parametermappings=[],
    )
    picture = BasePicture(header=_hdr("Root"), submodules=[FrameModule(header=_hdr("Frame"), submodules=[child])])

    reset_issues: list[VariableIssue] = []
    latch_issues: list[VariableIssue] = []

    reset_contamination_module.detect_reset_contamination(
        picture,
        reset_issues,
        limit_to_module_path=["Root", "Frame", "Child"],
    )
    reset_contamination_module.detect_implicit_latching(
        picture,
        latch_issues,
        limit_to_module_path=["Root", "Frame", "Child"],
    )

    assert any(
        issue.module_path == ["Root", "Frame", "Child"]
        and issue.variable is not None
        and issue.variable.name == "Counter"
        for issue in reset_issues
    )
    assert [(issue.module_path, issue.variable.name) for issue in latch_issues if issue.variable is not None] == [
        (["Root", "Frame", "Child"], "Latch")
    ]


def test_reset_helpers_collect_nested_refs_and_skip_fully_reset_paths() -> None:
    env = {
        "counter": Variable(name="Counter", datatype=Simple_DataType.INTEGER),
        "resetvalue": Variable(name="ResetValue", datatype=Simple_DataType.INTEGER),
        "seqresetold": Variable(name="SeqResetOld", datatype=Simple_DataType.BOOLEAN),
    }
    modulecode = ModuleCode(
        equations=[
            _eq(
                "CoveredReset",
                [
                    (
                        const.GRAMMAR_VALUE_IF,
                        [
                            (
                                (const.GRAMMAR_VALUE_NOT, _varref("OpSeq.Reset")),
                                [(const.KEY_ASSIGN, _varref("Counter"), _varref("ResetValue"))],
                            ),
                            (
                                (const.GRAMMAR_VALUE_NOT, _varref("SeqResetOld")),
                                [(const.KEY_ASSIGN, _varref("Counter"), _varref("ResetValue"))],
                            ),
                        ],
                        [],
                    ),
                    (const.KEY_ASSIGN, _varref("SeqResetOld"), _varref("OpSeq.Reset")),
                ],
            )
        ],
        sequences=[
            _seq(
                "OpSeq",
                [
                    SFCTransition(name="Gate", condition=_varref("OpSeq.Reset")),
                    SFCAlternative(
                        branches=[
                            [
                                SFCSubsequence(
                                    name="Sub",
                                    body=[(const.KEY_ASSIGN, _varref("SeqResetOld"), _varref("OpSeq.Reset"))],
                                )
                            ]
                        ]
                    ),
                    SFCTransitionSub(
                        name="GateSub",
                        body=[(const.KEY_ASSIGN, _varref("Counter"), _varref("ResetValue"))],
                    ),
                ],
            )
        ],
    )

    issues: list[VariableIssue] = []
    reset_contamination_module._check_for_modulecode(modulecode, env, ["Root"], issues)

    assert issues == []
    assert "opseq.reset" in reset_contamination_module._collect_var_refs(modulecode)
    assert reset_contamination_module._collect_reset_old_vars(modulecode, "opseq.reset") == {"SeqResetOld"}


def test_latching_helpers_cover_boolean_paths_and_sequence_recursion() -> None:
    env = {
        "flag": Variable(name="Flag", datatype=Simple_DataType.BOOLEAN),
        "otherflag": Variable(name="OtherFlag", datatype=Simple_DataType.BOOLEAN),
    }
    states = reset_contamination_module._collect_boolean_stmt_paths(
        SimpleNamespace(
            data=const.KEY_STATEMENT,
            children=[
                (
                    const.GRAMMAR_VALUE_IF,
                    [
                        (True, [(const.KEY_ASSIGN, _varref("Flag"), True)]),
                        (False, [(const.KEY_FUNCTION_CALL, "SetBooleanValue", [_varref("OtherFlag"), True])]),
                    ],
                    [(const.KEY_FUNCTION_CALL, "SetBooleanValue", [_varref("Flag"), False])],
                ),
                [SimpleNamespace(children=[(const.KEY_ASSIGN, _varref("OtherFlag"), False)])],
                SimpleNamespace(children=[(const.KEY_FUNCTION_CALL, "SetBooleanValue", [_varref("Flag"), False])]),
            ],
        ),
        env,
        [reset_contamination_module._BooleanPathState()],
    )
    seq_states = reset_contamination_module._collect_boolean_seq_block_paths(
        [
            SFCStep(
                kind="step",
                name="StepA",
                code=SFCCodeBlocks(
                    enter=[(const.KEY_ASSIGN, _varref("Flag"), True)],
                    active=[(const.KEY_FUNCTION_CALL, "SetBooleanValue", [_varref("OtherFlag"), True])],
                    exit=[(const.KEY_FUNCTION_CALL, "SetBooleanValue", [_varref("Flag"), False])],
                ),
            ),
            SFCTransition(name="Gate", condition=True),
            SFCAlternative(
                branches=[
                    [_bool_step("AltA", [(const.KEY_ASSIGN, _varref("Flag"), True)])],
                    [_bool_step("AltB", [(const.KEY_ASSIGN, _varref("OtherFlag"), True)])],
                ]
            ),
            SFCParallel(
                branches=[
                    [_bool_step("ParA", [(const.KEY_ASSIGN, _varref("Flag"), True)])],
                    [_bool_step("ParB", [(const.KEY_FUNCTION_CALL, "SetBooleanValue", [_varref("OtherFlag"), False])])],
                ]
            ),
            SFCSubsequence(name="Sub", body=[(const.KEY_ASSIGN, _varref("Flag"), True)]),
            SFCTransitionSub(name="SubGate", body=[(const.KEY_ASSIGN, _varref("OtherFlag"), False)]),
        ],
        env,
        [reset_contamination_module._BooleanPathState()],
    )
    merged_states = reset_contamination_module._merge_boolean_parallel_branch_results(
        [
            [reset_contamination_module._BooleanPathState(true_writes={("flag", ""): (env["flag"], "")})],
            [reset_contamination_module._BooleanPathState(false_writes={("otherflag", ""): (env["otherflag"], "")})],
        ]
    )
    assert reset_contamination_module._merge_boolean_parallel_branch_results([]) == []

    issues: list[VariableIssue] = []
    reset_contamination_module._scan_stmt_for_latching(
        (
            const.GRAMMAR_VALUE_IF,
            [(True, [(const.KEY_ASSIGN, _varref("Flag"), True)])],
            [(const.KEY_FUNCTION_CALL, "SetBooleanValue", [_varref("Flag"), False])],
        ),
        env,
        ["Root"],
        issues,
        set(),
        site="EQ:Guard",
        sequence_name="SeqA",
    )
    reset_contamination_module._scan_seq_nodes_for_latching(
        [
            _bool_step("LatchStep", [(const.KEY_ASSIGN, _varref("Flag"), True)]),
            SFCAlternative(
                branches=[
                    [_bool_step("Left", [(const.KEY_ASSIGN, _varref("Flag"), True)])],
                    [_bool_step("Right", [(const.KEY_ASSIGN, _varref("OtherFlag"), True)])],
                ]
            ),
            SFCParallel(branches=[[_bool_step("Parallel", [(const.KEY_ASSIGN, _varref("Flag"), True)])]]),
            SFCSubsequence(name="Nested", body=[_bool_step("NestedStep", [(const.KEY_ASSIGN, _varref("Flag"), True)])]),
            SFCTransitionSub(
                name="NestedGate",
                body=[_bool_step("NestedGateStep", [(const.KEY_ASSIGN, _varref("OtherFlag"), True)])],
            ),
        ],
        env,
        ["Root"],
        issues,
        set(),
        site="SEQ:Main",
        sequence_name="Main",
    )

    assert any(state.true_writes for state in states)
    assert any(state.false_writes for state in states)
    assert seq_states
    assert merged_states[0].true_writes == {("flag", ""): (env["flag"], "")}
    assert merged_states[0].false_writes == {("otherflag", ""): (env["otherflag"], "")}
    assert any(issue.kind is IssueKind.IMPLICIT_LATCH for issue in issues)
    assert any(issue.sequence_name == "Main" for issue in issues)
