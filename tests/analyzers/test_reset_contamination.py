from sattline_parser.models.ast_model import (
    BasePicture,
    Equation,
    FrameModule,
    ModuleCode,
    ModuleHeader,
    ModuleTypeDef,
    Sequence,
    Simple_DataType,
    SingleModule,
    Variable,
)
from sattlint import constants as const
from sattlint.analyzers import reset_contamination as reset_contamination_module
from sattlint.reporting.variables_report import VariableIssue


def _hdr(name: str) -> ModuleHeader:
    return ModuleHeader(name=name, invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0))


def _varref(name: str) -> dict[str, str]:
    return {const.KEY_VAR_NAME: name}


def _eq(name: str, code: list[object]) -> Equation:
    return Equation(name=name, position=(0.0, 0.0), size=(1.0, 1.0), code=code)


def _seq(name: str, code: list[object]) -> Sequence:
    return Sequence(name=name, type="sequence", position=(0.0, 0.0), size=(1.0, 1.0), code=code)


def _reset_equation(run_target: str, reset_target: str) -> Equation:
    return Equation(
        name="Main",
        position=(0.0, 0.0),
        size=(1.0, 1.0),
        code=[
            (
                const.GRAMMAR_VALUE_IF,
                [
                    (
                        (const.GRAMMAR_VALUE_NOT, _varref("OpSeq.Reset")),
                        [(const.KEY_ASSIGN, _varref(run_target), _varref("ResetValue"))],
                    ),
                    (
                        (const.GRAMMAR_VALUE_NOT, _varref("SeqResetOld")),
                        [(const.KEY_ASSIGN, _varref(reset_target), _varref("ResetValue"))],
                    ),
                ],
                [],
            ),
            (const.KEY_ASSIGN, _varref("SeqResetOld"), _varref("OpSeq.Reset")),
        ],
    )


def _reset_modulecode(run_target: str = "Counter", reset_target: str = "Other") -> ModuleCode:
    return ModuleCode(
        sequences=[_seq("OpSeq", [])],
        equations=[_reset_equation(run_target, reset_target)],
    )


def _typedef_with_latch(name: str) -> ModuleTypeDef:
    return ModuleTypeDef(
        name=name,
        moduleparameters=[],
        localvariables=[
            Variable(name="Start", datatype=Simple_DataType.BOOLEAN),
            Variable(name="AlarmLatched", datatype=Simple_DataType.BOOLEAN),
        ],
        moduledef=None,
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="LatchEq",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (
                            const.GRAMMAR_VALUE_IF,
                            [(_varref("Start"), [(const.KEY_ASSIGN, _varref("AlarmLatched"), True)])],
                            [],
                        )
                    ],
                )
            ]
        ),
    )


def test_state_integrity_top_level_detection_covers_typedef_origin_limit_and_root() -> None:
    typedef_reset = ModuleTypeDef(
        name="ResetType",
        moduleparameters=[],
        localvariables=[
            Variable(name="Counter", datatype=Simple_DataType.INTEGER),
            Variable(name="Other", datatype=Simple_DataType.INTEGER),
            Variable(name="ResetValue", datatype=Simple_DataType.INTEGER),
            Variable(name="SeqResetOld", datatype=Simple_DataType.BOOLEAN),
        ],
        moduledef=None,
        modulecode=_reset_modulecode(),
    )
    typedef_reset.origin_file = "root.s"

    typedef_skipped = ModuleTypeDef(
        name="SkippedType",
        moduleparameters=[],
        localvariables=[
            Variable(name="Counter", datatype=Simple_DataType.INTEGER),
            Variable(name="Other", datatype=Simple_DataType.INTEGER),
            Variable(name="ResetValue", datatype=Simple_DataType.INTEGER),
            Variable(name="SeqResetOld", datatype=Simple_DataType.BOOLEAN),
        ],
        moduledef=None,
        modulecode=_reset_modulecode(),
    )
    typedef_skipped.origin_file = "other.s"

    typedef_latch = _typedef_with_latch("LatchType")
    typedef_latch.origin_file = "root.s"

    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[typedef_reset, typedef_skipped, typedef_latch],
        localvariables=[
            Variable(name="Start", datatype=Simple_DataType.BOOLEAN),
            Variable(name="RootLatched", datatype=Simple_DataType.BOOLEAN),
        ],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="RootEq",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (
                            const.GRAMMAR_VALUE_IF,
                            [(_varref("Start"), [(const.KEY_ASSIGN, _varref("RootLatched"), True)])],
                            [],
                        )
                    ],
                )
            ]
        ),
        moduledef=None,
    )
    bp.origin_file = "root.s"

    reset_issues: list[VariableIssue] = []
    reset_contamination_module.detect_reset_contamination(bp, reset_issues)

    assert [(issue.module_path, issue.variable.name) for issue in reset_issues if issue.variable is not None] == [
        (["Root", "TypeDef:ResetType"], "Counter")
    ]

    latch_issues: list[VariableIssue] = []
    reset_contamination_module.detect_implicit_latching(bp, latch_issues)
    assert sorted((issue.module_path, issue.variable.name) for issue in latch_issues if issue.variable is not None) == [
        (["Root"], "RootLatched"),
        (["Root", "TypeDef:LatchType"], "AlarmLatched"),
    ]


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
