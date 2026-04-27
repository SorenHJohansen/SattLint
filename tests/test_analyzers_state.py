"""Tests for state-integrity analyzers: reset contamination, implicit latch, SFC step contract, write-without-effect, hidden global coupling, global scope minimization, high fan-in/out, and variables report summary."""

from sattlint import constants as const
from sattlint.analyzers.sfc import analyze_sfc
from sattlint.analyzers.variables import IssueKind, VariablesAnalyzer
from sattlint.models.ast_model import (
    BasePicture,
    Equation,
    ModuleCode,
    ModuleHeader,
    ModuleTypeDef,
    ParameterMapping,
    Sequence,
    SFCCodeBlocks,
    SFCStep,
    Simple_DataType,
    SingleModule,
    Variable,
)
from sattlint.reporting.variables_report import (
    ALL_VARIABLE_ANALYSIS_KINDS,
    VariableIssue,
    VariablesReport,
)


def _hdr(name: str) -> ModuleHeader:
    return ModuleHeader(name=name, invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0))


def _varref(s: str) -> dict:
    return {const.KEY_VAR_NAME: s}


def _state_ref(name: str, state: str) -> dict:
    return {const.KEY_VAR_NAME: name, "state": state}


def _issue_kinds(report) -> set[str]:
    return {issue.kind for issue in report.issues}


def _status_bridge_typedef() -> ModuleTypeDef:
    return ModuleTypeDef(
        name="StatusBridge",
        moduleparameters=[Variable(name="OperationStatus", datatype=Simple_DataType.INTEGER)],
        localvariables=[
            Variable(name="Source", datatype=Simple_DataType.INTEGER),
            Variable(name="Destination", datatype=Simple_DataType.INTEGER),
        ],
        moduledef=None,
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="BridgeEq",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (
                            const.KEY_FUNCTION_CALL,
                            "CopyVariable",
                            [_varref("Source"), _varref("Destination"), _varref("OperationStatus")],
                        )
                    ],
                )
            ]
        ),
    )


def test_reset_contamination_detected_for_missing_reset_write():
    seq = Sequence(
        name="OperationSequence",
        type="sequence",
        position=(0.0, 0.0),
        size=(1.0, 1.0),
        code=[],
    )

    eq = Equation(
        name="Main",
        position=(0.0, 0.0),
        size=(1.0, 1.0),
        code=[
            (
                const.GRAMMAR_VALUE_IF,
                [
                    (
                        (const.GRAMMAR_VALUE_NOT, _varref("OperationSequence.Reset")),
                        [
                            (
                                const.KEY_ASSIGN,
                                _varref("Counter"),
                                _varref("ResetValue"),
                            )
                        ],
                    ),
                    (
                        (const.GRAMMAR_VALUE_NOT, _varref("OprSeqResetOld")),
                        [
                            (
                                const.KEY_ASSIGN,
                                _varref("Other"),
                                _varref("ResetValue"),
                            )
                        ],
                    ),
                ],
                [],
            ),
            (
                const.KEY_ASSIGN,
                _varref("OprSeqResetOld"),
                _varref("OperationSequence.Reset"),
            ),
        ],
    )

    mod = SingleModule(
        header=_hdr("Unit"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[
            Variable(name="Counter", datatype=Simple_DataType.INTEGER),
            Variable(name="Other", datatype=Simple_DataType.INTEGER),
            Variable(name="ResetValue", datatype=Simple_DataType.INTEGER),
            Variable(name="OprSeqResetOld", datatype=Simple_DataType.BOOLEAN),
        ],
        submodules=[],
        modulecode=ModuleCode(sequences=[seq], equations=[eq]),
        parametermappings=[],
    )

    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[],
        submodules=[mod],
        modulecode=None,
        moduledef=None,
    )

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    issues = [i for i in analyzer.issues if i.kind is IssueKind.RESET_CONTAMINATION]
    assert any(i.variable and i.variable.name == "Counter" for i in issues)


def test_reset_contamination_cleared_when_reset_writes_present():
    seq = Sequence(
        name="OperationSequence",
        type="sequence",
        position=(0.0, 0.0),
        size=(1.0, 1.0),
        code=[],
    )

    eq = Equation(
        name="Main",
        position=(0.0, 0.0),
        size=(1.0, 1.0),
        code=[
            (
                const.GRAMMAR_VALUE_IF,
                [
                    (
                        (const.GRAMMAR_VALUE_NOT, _varref("OperationSequence.Reset")),
                        [
                            (
                                const.KEY_ASSIGN,
                                _varref("Counter"),
                                _varref("ResetValue"),
                            )
                        ],
                    ),
                    (
                        (const.GRAMMAR_VALUE_NOT, _varref("OprSeqResetOld")),
                        [
                            (
                                const.KEY_ASSIGN,
                                _varref("Counter"),
                                _varref("ResetValue"),
                            )
                        ],
                    ),
                ],
                [],
            ),
            (
                const.KEY_ASSIGN,
                _varref("OprSeqResetOld"),
                _varref("OperationSequence.Reset"),
            ),
        ],
    )

    mod = SingleModule(
        header=_hdr("Unit"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[
            Variable(name="Counter", datatype=Simple_DataType.INTEGER),
            Variable(name="ResetValue", datatype=Simple_DataType.INTEGER),
            Variable(name="OprSeqResetOld", datatype=Simple_DataType.BOOLEAN),
        ],
        submodules=[],
        modulecode=ModuleCode(sequences=[seq], equations=[eq]),
        parametermappings=[],
    )

    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[],
        submodules=[mod],
        modulecode=None,
        moduledef=None,
    )

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    assert not any(i.kind is IssueKind.RESET_CONTAMINATION for i in analyzer.issues)


def test_implicit_latch_detected_when_if_branch_sets_true_without_else_clear():
    mod = SingleModule(
        header=_hdr("Unit"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[
            Variable(name="Start", datatype=Simple_DataType.BOOLEAN),
            Variable(name="AlarmLatched", datatype=Simple_DataType.BOOLEAN),
        ],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Main",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (
                            const.GRAMMAR_VALUE_IF,
                            [
                                (
                                    _varref("Start"),
                                    [
                                        (
                                            const.KEY_ASSIGN,
                                            _varref("AlarmLatched"),
                                            True,
                                        )
                                    ],
                                )
                            ],
                            [],
                        )
                    ],
                )
            ]
        ),
        parametermappings=[],
    )

    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[],
        submodules=[mod],
        modulecode=None,
        moduledef=None,
    )

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    issues = [i for i in analyzer.issues if i.kind is IssueKind.IMPLICIT_LATCH]
    assert len(issues) == 1
    assert issues[0].variable is not None
    assert issues[0].variable.name == "AlarmLatched"
    assert issues[0].site == "EQ:Main > IF"


def test_implicit_latch_not_reported_when_else_branch_clears_false():
    mod = SingleModule(
        header=_hdr("Unit"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[
            Variable(name="Start", datatype=Simple_DataType.BOOLEAN),
            Variable(name="AlarmLatched", datatype=Simple_DataType.BOOLEAN),
        ],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Main",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (
                            const.GRAMMAR_VALUE_IF,
                            [
                                (
                                    _varref("Start"),
                                    [
                                        (
                                            const.KEY_ASSIGN,
                                            _varref("AlarmLatched"),
                                            True,
                                        )
                                    ],
                                )
                            ],
                            [
                                (
                                    const.KEY_ASSIGN,
                                    _varref("AlarmLatched"),
                                    False,
                                )
                            ],
                        )
                    ],
                )
            ]
        ),
        parametermappings=[],
    )

    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[],
        submodules=[mod],
        modulecode=None,
        moduledef=None,
    )

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    assert not any(i.kind is IssueKind.IMPLICIT_LATCH for i in analyzer.issues)


def test_implicit_latch_detected_for_step_without_exit_clear():
    seq = Sequence(
        name="OperationSequence",
        type="sequence",
        position=(0.0, 0.0),
        size=(1.0, 1.0),
        code=[
            SFCStep(
                kind="step",
                name="Run",
                code=SFCCodeBlocks(
                    active=[
                        (
                            const.KEY_ASSIGN,
                            _varref("StepFlag"),
                            True,
                        )
                    ],
                    exit=[],
                ),
            )
        ],
    )

    mod = SingleModule(
        header=_hdr("Unit"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[Variable(name="StepFlag", datatype=Simple_DataType.BOOLEAN)],
        submodules=[],
        modulecode=ModuleCode(sequences=[seq], equations=[]),
        parametermappings=[],
    )

    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[],
        submodules=[mod],
        modulecode=None,
        moduledef=None,
    )

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    issues = [i for i in analyzer.issues if i.kind is IssueKind.IMPLICIT_LATCH]
    assert len(issues) == 1
    assert issues[0].variable is not None
    assert issues[0].variable.name == "StepFlag"
    assert issues[0].site == "SEQ:OperationSequence > STEP:Run"


def test_sfc_step_contract_detects_missing_enter_initialization():
    sequence = Sequence(
        name="OperationSequence",
        type="sequence",
        position=(0.0, 0.0),
        size=(1.0, 1.0),
        code=[
            SFCStep(
                kind="step",
                name="Run",
                code=SFCCodeBlocks(
                    enter=[],
                    active=[
                        (
                            const.KEY_ASSIGN,
                            _varref("Output"),
                            _varref("StepValue"),
                        )
                    ],
                    exit=[],
                ),
            )
        ],
    )

    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[
            Variable(name="StepValue", datatype=Simple_DataType.INTEGER),
            Variable(name="Output", datatype=Simple_DataType.INTEGER),
        ],
        modulecode=ModuleCode(sequences=[sequence], equations=[]),
    )

    report = analyze_sfc(
        bp,
        step_contracts={
            "Run": {"required_enter_writes": ["StepValue"]},
        },
    )

    issues = [issue for issue in report.issues if issue.kind == "sfc_missing_step_enter_contract"]
    assert len(issues) == 1
    assert issues[0].data is not None
    assert issues[0].data["missing_enter_writes"] == ["StepValue"]


def test_sfc_step_contract_detects_missing_exit_cleanup():
    sequence = Sequence(
        name="OperationSequence",
        type="sequence",
        position=(0.0, 0.0),
        size=(1.0, 1.0),
        code=[
            SFCStep(
                kind="step",
                name="Run",
                code=SFCCodeBlocks(
                    enter=[
                        (
                            const.KEY_ASSIGN,
                            _varref("StepValue"),
                            1,
                        )
                    ],
                    active=[],
                    exit=[],
                ),
            )
        ],
    )

    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[Variable(name="StepValue", datatype=Simple_DataType.INTEGER)],
        modulecode=ModuleCode(sequences=[sequence], equations=[]),
    )

    report = analyze_sfc(
        bp,
        step_contracts={
            "Run": {"required_exit_writes": ["StepValue"]},
        },
    )

    issues = [issue for issue in report.issues if issue.kind == "sfc_missing_step_exit_contract"]
    assert len(issues) == 1
    assert issues[0].data is not None
    assert issues[0].data["missing_exit_writes"] == ["StepValue"]


def test_sfc_step_contract_detects_state_leakage_across_steps():
    sequence = Sequence(
        name="OperationSequence",
        type="sequence",
        position=(0.0, 0.0),
        size=(1.0, 1.0),
        code=[
            SFCStep(
                kind="step",
                name="Prime",
                code=SFCCodeBlocks(
                    active=[
                        (
                            const.KEY_ASSIGN,
                            _varref("StepValue"),
                            1,
                        )
                    ]
                ),
            ),
            SFCStep(
                kind="step",
                name="Run",
                code=SFCCodeBlocks(
                    enter=[],
                    active=[
                        (
                            const.KEY_ASSIGN,
                            _varref("Output"),
                            _varref("StepValue"),
                        )
                    ],
                    exit=[],
                ),
            ),
        ],
    )

    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[
            Variable(name="StepValue", datatype=Simple_DataType.INTEGER),
            Variable(name="Output", datatype=Simple_DataType.INTEGER),
        ],
        modulecode=ModuleCode(sequences=[sequence], equations=[]),
    )

    report = analyze_sfc(
        bp,
        step_contracts={
            "Run": {"required_enter_writes": ["StepValue"]},
        },
    )

    issues = [issue for issue in report.issues if issue.kind == "sfc_step_state_leakage"]
    assert len(issues) == 1
    assert issues[0].data is not None
    assert issues[0].data["leaked_state"] == ["StepValue"]


def test_write_without_effect_detected_for_internal_value_chain():
    child = SingleModule(
        header=_hdr("Worker"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[
            Variable(name="Stage1", datatype=Simple_DataType.INTEGER),
            Variable(name="Stage2", datatype=Simple_DataType.INTEGER),
        ],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Main",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (const.KEY_ASSIGN, _varref("Stage1"), 1),
                        (const.KEY_ASSIGN, _varref("Stage2"), _varref("Stage1")),
                    ],
                )
            ],
            sequences=[],
        ),
        parametermappings=[],
    )

    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[],
        submodules=[child],
        modulecode=None,
        moduledef=None,
    )

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    write_without_effect = [issue for issue in analyzer.issues if issue.kind is IssueKind.WRITE_WITHOUT_EFFECT]
    assert [issue.variable.name for issue in write_without_effect if issue.variable is not None] == ["Stage1"]
    assert any(
        issue.kind is IssueKind.NEVER_READ and issue.variable is not None and issue.variable.name == "Stage2"
        for issue in analyzer.issues
    )


def test_write_without_effect_is_suppressed_for_mapped_output_path():
    child = SingleModule(
        header=_hdr("Worker"),
        moduledef=None,
        moduleparameters=[Variable(name="Out", datatype=Simple_DataType.INTEGER)],
        localvariables=[Variable(name="Internal", datatype=Simple_DataType.INTEGER)],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Main",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (const.KEY_ASSIGN, _varref("Internal"), 1),
                        (const.KEY_ASSIGN, _varref("Out"), _varref("Internal")),
                    ],
                )
            ],
            sequences=[],
        ),
        parametermappings=[
            ParameterMapping(
                target=_varref("Out"),
                source_type=const.TREE_TAG_VARIABLE_NAME,
                is_duration=False,
                is_source_global=False,
                source=_varref("FinalOutput"),
                source_literal=None,
            )
        ],
    )

    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[Variable(name="FinalOutput", datatype=Simple_DataType.INTEGER)],
        submodules=[child],
        modulecode=None,
        moduledef=None,
    )

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    assert not any(
        issue.kind is IssueKind.WRITE_WITHOUT_EFFECT
        and issue.variable is not None
        and issue.variable.name in {"Internal", "Out"}
        for issue in analyzer.issues
    )


def test_hidden_global_coupling_is_reported_for_sibling_modules_using_root_global():
    shared_value = Variable(name="SharedValue", datatype=Simple_DataType.INTEGER)

    writer = SingleModule(
        header=_hdr("Writer"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="WriteShared",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[(const.KEY_ASSIGN, _varref("SharedValue"), 1)],
                )
            ],
            sequences=[],
        ),
        parametermappings=[],
    )
    reader = SingleModule(
        header=_hdr("Reader"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[Variable(name="Observed", datatype=Simple_DataType.INTEGER)],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="ReadShared",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[(const.KEY_ASSIGN, _varref("Observed"), _varref("SharedValue"))],
                )
            ],
            sequences=[],
        ),
        parametermappings=[],
    )

    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[shared_value],
        submodules=[writer, reader],
        modulecode=None,
        moduledef=None,
    )

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    hidden_issues = [
        issue
        for issue in analyzer.issues
        if issue.kind is IssueKind.HIDDEN_GLOBAL_COUPLING and issue.variable is shared_value
    ]
    assert len(hidden_issues) == 1
    assert "Writer (write)" in (hidden_issues[0].role or "")
    assert "Reader (read)" in (hidden_issues[0].role or "")


def test_hidden_global_coupling_is_not_reported_for_explicit_parameter_mappings():
    writer = SingleModule(
        header=_hdr("Writer"),
        moduledef=None,
        moduleparameters=[Variable(name="Out", datatype=Simple_DataType.INTEGER)],
        localvariables=[],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Produce",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[(const.KEY_ASSIGN, _varref("Out"), 1)],
                )
            ],
            sequences=[],
        ),
        parametermappings=[
            ParameterMapping(
                target=_varref("Out"),
                source_type=const.TREE_TAG_VARIABLE_NAME,
                is_duration=False,
                is_source_global=False,
                source=_varref("SharedValue"),
                source_literal=None,
            )
        ],
    )
    reader = SingleModule(
        header=_hdr("Reader"),
        moduledef=None,
        moduleparameters=[Variable(name="In", datatype=Simple_DataType.INTEGER)],
        localvariables=[Variable(name="Observed", datatype=Simple_DataType.INTEGER)],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Consume",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[(const.KEY_ASSIGN, _varref("Observed"), _varref("In"))],
                )
            ],
            sequences=[],
        ),
        parametermappings=[
            ParameterMapping(
                target=_varref("In"),
                source_type=const.TREE_TAG_VARIABLE_NAME,
                is_duration=False,
                is_source_global=False,
                source=_varref("SharedValue"),
                source_literal=None,
            )
        ],
    )
    coordinator = SingleModule(
        header=_hdr("Coordinator"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[Variable(name="SharedValue", datatype=Simple_DataType.INTEGER)],
        submodules=[writer, reader],
        modulecode=None,
        parametermappings=[],
    )

    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[],
        submodules=[coordinator],
        modulecode=None,
        moduledef=None,
    )

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    assert not any(issue.kind is IssueKind.HIDDEN_GLOBAL_COUPLING for issue in analyzer.issues)


def test_global_scope_minimization_is_reported_for_root_global_confined_to_one_module_subtree():
    confined = Variable(name="ConfinedValue", datatype=Simple_DataType.INTEGER)

    worker = SingleModule(
        header=_hdr("Worker"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[Variable(name="Observed", datatype=Simple_DataType.INTEGER)],
        submodules=[
            SingleModule(
                header=_hdr("Nested"),
                moduledef=None,
                moduleparameters=[],
                localvariables=[],
                submodules=[],
                modulecode=ModuleCode(
                    equations=[
                        Equation(
                            name="WriteConfined",
                            position=(0.0, 0.0),
                            size=(1.0, 1.0),
                            code=[(const.KEY_ASSIGN, _varref("ConfinedValue"), 1)],
                        )
                    ],
                    sequences=[],
                ),
                parametermappings=[],
            )
        ],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="ReadConfined",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[(const.KEY_ASSIGN, _varref("Observed"), _varref("ConfinedValue"))],
                )
            ],
            sequences=[],
        ),
        parametermappings=[],
    )

    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[confined],
        submodules=[worker],
        modulecode=None,
        moduledef=None,
    )

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    issues = [
        issue
        for issue in analyzer.issues
        if issue.kind is IssueKind.GLOBAL_SCOPE_MINIMIZATION and issue.variable is confined
    ]

    assert len(issues) == 1
    assert "Worker" in (issues[0].role or "")
    assert "Nested" in (issues[0].role or "")


def test_global_scope_minimization_is_not_reported_for_root_global_used_in_root_scope():
    confined = Variable(name="ConfinedValue", datatype=Simple_DataType.INTEGER)

    worker = SingleModule(
        header=_hdr("Worker"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="WriteConfined",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[(const.KEY_ASSIGN, _varref("ConfinedValue"), 1)],
                )
            ],
            sequences=[],
        ),
        parametermappings=[],
    )

    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[confined, Variable(name="Observed", datatype=Simple_DataType.INTEGER)],
        submodules=[worker],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="ReadAtRoot",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[(const.KEY_ASSIGN, _varref("Observed"), _varref("ConfinedValue"))],
                )
            ],
            sequences=[],
        ),
        moduledef=None,
    )

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    assert not any(
        issue.kind is IssueKind.GLOBAL_SCOPE_MINIMIZATION and issue.variable is confined for issue in analyzer.issues
    )


def test_global_scope_minimization_is_suppressed_for_library_targets():
    confined = Variable(name="ConfinedValue", datatype=Simple_DataType.INTEGER)

    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[confined],
        submodules=[
            SingleModule(
                header=_hdr("Worker"),
                moduledef=None,
                moduleparameters=[],
                localvariables=[Variable(name="Observed", datatype=Simple_DataType.INTEGER)],
                submodules=[],
                modulecode=ModuleCode(
                    equations=[
                        Equation(
                            name="UseConfined",
                            position=(0.0, 0.0),
                            size=(1.0, 1.0),
                            code=[
                                (const.KEY_ASSIGN, _varref("ConfinedValue"), 1),
                                (const.KEY_ASSIGN, _varref("Observed"), _varref("ConfinedValue")),
                            ],
                        )
                    ],
                    sequences=[],
                ),
                parametermappings=[],
            )
        ],
        modulecode=None,
        moduledef=None,
        origin_file="Root.s",
    )

    analyzer = VariablesAnalyzer(bp, analyzed_target_is_library=True)
    analyzer.run()

    assert not any(issue.kind is IssueKind.GLOBAL_SCOPE_MINIMIZATION for issue in analyzer.issues)
    assert not any(issue.kind is IssueKind.HIDDEN_GLOBAL_COUPLING for issue in analyzer.issues)


def test_high_fan_in_out_is_reported_for_root_global_shared_across_many_modules():
    shared = Variable(name="SharedValue", datatype=Simple_DataType.INTEGER)

    writer = SingleModule(
        header=_hdr("Writer"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="WriteShared",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[(const.KEY_ASSIGN, _varref("SharedValue"), 1)],
                )
            ],
            sequences=[],
        ),
        parametermappings=[],
    )
    reader_a = SingleModule(
        header=_hdr("ReaderA"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[Variable(name="Observed", datatype=Simple_DataType.INTEGER)],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="ReadSharedA",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[(const.KEY_ASSIGN, _varref("Observed"), _varref("SharedValue"))],
                )
            ],
            sequences=[],
        ),
        parametermappings=[],
    )
    reader_b = SingleModule(
        header=_hdr("ReaderB"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[Variable(name="Observed", datatype=Simple_DataType.INTEGER)],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="ReadSharedB",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[(const.KEY_ASSIGN, _varref("Observed"), _varref("SharedValue"))],
                )
            ],
            sequences=[],
        ),
        parametermappings=[],
    )
    reader_c = SingleModule(
        header=_hdr("ReaderC"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[Variable(name="Observed", datatype=Simple_DataType.INTEGER)],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="ReadSharedC",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[(const.KEY_ASSIGN, _varref("Observed"), _varref("SharedValue"))],
                )
            ],
            sequences=[],
        ),
        parametermappings=[],
    )

    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[shared],
        submodules=[writer, reader_a, reader_b, reader_c],
        modulecode=None,
        moduledef=None,
    )

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    issues = [
        issue for issue in analyzer.issues if issue.kind is IssueKind.HIGH_FAN_IN_OUT and issue.variable is shared
    ]

    assert len(issues) == 1
    assert "high fan-in with 3 readers" in (issues[0].role or "")
    assert "ReaderA" in (issues[0].role or "")
    assert "ReaderB" in (issues[0].role or "")
    assert "ReaderC" in (issues[0].role or "")


def test_high_fan_in_out_is_not_reported_below_threshold():
    shared = Variable(name="SharedValue", datatype=Simple_DataType.INTEGER)

    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[shared],
        submodules=[
            SingleModule(
                header=_hdr("Writer"),
                moduledef=None,
                moduleparameters=[],
                localvariables=[],
                submodules=[],
                modulecode=ModuleCode(
                    equations=[
                        Equation(
                            name="WriteShared",
                            position=(0.0, 0.0),
                            size=(1.0, 1.0),
                            code=[(const.KEY_ASSIGN, _varref("SharedValue"), 1)],
                        )
                    ],
                    sequences=[],
                ),
                parametermappings=[],
            ),
            SingleModule(
                header=_hdr("ReaderA"),
                moduledef=None,
                moduleparameters=[],
                localvariables=[Variable(name="Observed", datatype=Simple_DataType.INTEGER)],
                submodules=[],
                modulecode=ModuleCode(
                    equations=[
                        Equation(
                            name="ReadSharedA",
                            position=(0.0, 0.0),
                            size=(1.0, 1.0),
                            code=[(const.KEY_ASSIGN, _varref("Observed"), _varref("SharedValue"))],
                        )
                    ],
                    sequences=[],
                ),
                parametermappings=[],
            ),
            SingleModule(
                header=_hdr("ReaderB"),
                moduledef=None,
                moduleparameters=[],
                localvariables=[Variable(name="Observed", datatype=Simple_DataType.INTEGER)],
                submodules=[],
                modulecode=ModuleCode(
                    equations=[
                        Equation(
                            name="ReadSharedB",
                            position=(0.0, 0.0),
                            size=(1.0, 1.0),
                            code=[(const.KEY_ASSIGN, _varref("Observed"), _varref("SharedValue"))],
                        )
                    ],
                    sequences=[],
                ),
                parametermappings=[],
            ),
        ],
        modulecode=None,
        moduledef=None,
    )

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    assert not any(issue.kind is IssueKind.HIGH_FAN_IN_OUT and issue.variable is shared for issue in analyzer.issues)


def test_variables_report_summary_includes_name_collisions():
    variable = Variable(name="Value", datatype=Simple_DataType.INTEGER)
    issue = VariableIssue(
        kind=IssueKind.NAME_COLLISION,
        module_path=["BasePicture", "TypeDef:Unit"],
        variable=variable,
        role="name collision with parameter 'Value'",
    )

    summary = VariablesReport(basepicture_name="BasePicture", issues=[issue]).summary()

    assert "Sections:" in summary
    assert "  - Name collisions: 1" in summary
    assert "Name collisions" in summary
    assert ("BasePicture.TypeDef:Unit :: Value (integer) | " "name collision with parameter 'Value'") in summary


def test_variables_report_summary_includes_write_without_effect_section():
    variable = Variable(name="Stage1", datatype=Simple_DataType.INTEGER)
    issue = VariableIssue(
        kind=IssueKind.WRITE_WITHOUT_EFFECT,
        module_path=["BasePicture", "Worker"],
        variable=variable,
        role="localvariable",
    )

    summary = VariablesReport(basepicture_name="BasePicture", issues=[issue]).summary()

    assert "Write-without-effect variables" in summary
    assert "  - Write-without-effect variables: 1" in summary
    assert "Stage1" in summary


def test_variables_report_summary_includes_hidden_global_coupling_section():
    variable = Variable(name="SharedValue", datatype=Simple_DataType.INTEGER)
    issue = VariableIssue(
        kind=IssueKind.HIDDEN_GLOBAL_COUPLING,
        module_path=["BasePicture"],
        variable=variable,
        role="hidden global coupling across modules: Writer (write), Reader (read)",
    )

    summary = VariablesReport(basepicture_name="BasePicture", issues=[issue]).summary()

    assert "Hidden global coupling" in summary
    assert "SharedValue" in summary


def test_variables_report_summary_includes_high_fan_in_out_section():
    variable = Variable(name="SharedValue", datatype=Simple_DataType.INTEGER)
    issue = VariableIssue(
        kind=IssueKind.HIGH_FAN_IN_OUT,
        module_path=["BasePicture"],
        variable=variable,
        role="high fan-in with 3 readers: ReaderA, ReaderB, ReaderC",
    )

    summary = VariablesReport(basepicture_name="BasePicture", issues=[issue]).summary()

    assert "High fan-in or fan-out variables" in summary
    assert "SharedValue" in summary


def test_variables_report_summary_includes_global_scope_minimization_section():
    variable = Variable(name="ConfinedValue", datatype=Simple_DataType.INTEGER)
    issue = VariableIssue(
        kind=IssueKind.GLOBAL_SCOPE_MINIMIZATION,
        module_path=["BasePicture"],
        variable=variable,
        role="global scope can be reduced to module subtree Worker: Worker, Worker.Nested",
    )

    summary = VariablesReport(basepicture_name="BasePicture", issues=[issue]).summary()

    assert "Global scope minimization candidates" in summary
    assert "ConfinedValue" in summary


def test_variables_report_summary_includes_ui_only_section():
    variable = Variable(name="DisplayValue", datatype=Simple_DataType.INTEGER)
    issue = VariableIssue(
        kind=IssueKind.UI_ONLY,
        module_path=["BasePicture", "Panel"],
        variable=variable,
        role="localvariable",
    )

    summary = VariablesReport(basepicture_name="BasePicture", issues=[issue]).summary()

    assert "UI/display-only variables" in summary
    assert "DisplayValue" in summary


def test_variables_report_summary_includes_unknown_parameter_targets():
    issue = VariableIssue(
        kind=IssueKind.UNKNOWN_PARAMETER_TARGET,
        module_path=["BasePicture", "Child"],
        variable=None,
        role="unknown parameter mapping target 'MissingValue'",
    )

    summary = VariablesReport(basepicture_name="BasePicture", issues=[issue]).summary()

    assert "Unknown parameter mapping targets" in summary
    assert "BasePicture.Child :: unknown parameter mapping target 'MissingValue'" in summary


def test_variables_report_summary_lists_all_requested_categories_when_empty():
    report = VariablesReport(
        basepicture_name="BasePicture",
        issues=[],
        visible_kinds=frozenset(ALL_VARIABLE_ANALYSIS_KINDS),
        include_empty_sections=True,
    )

    summary = report.summary()

    assert "Issues: 0" in summary
    assert "Sections:" in summary
    assert "  - Unused variables: 0" in summary
    assert "Unused variables" in summary
    assert "Unused fields in datatypes" in summary
    assert "Read-only but not Const variables" in summary
    assert "UI/display-only variables" in summary
    assert "Procedure status handling" in summary
    assert "Written but never read variables" in summary
    assert "Global scope minimization candidates" in summary
    assert "Hidden global coupling" in summary
    assert "Unknown parameter mapping targets" in summary
    assert "String mapping type mismatches" in summary
    assert "Duplicated complex datatypes (should be RECORD)" in summary
    assert "Min/Max mapping name mismatches" in summary
    assert "Magic numbers in code" in summary
    assert "Name collisions" in summary
    assert "Reset contamination (missing reset writes)" in summary
    assert "Implicit latching (missing matching False writes)" in summary
    assert summary.count("      none") == len(ALL_VARIABLE_ANALYSIS_KINDS)


def test_variables_report_summary_keeps_filtered_empty_output_scoped():
    report = VariablesReport(
        basepicture_name="BasePicture",
        issues=[],
        visible_kinds=frozenset({IssueKind.RESET_CONTAMINATION}),
        include_empty_sections=True,
    )

    summary = report.summary()

    assert "Issues: 0" in summary
    assert "Sections:" in summary
    assert "  - Reset contamination (missing reset writes): 0" in summary
    assert "Reset contamination (missing reset writes)" in summary
    assert "      none" in summary
    assert "Unused variables" not in summary
