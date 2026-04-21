"""Tests for SFC analyzer checks."""

from sattlint import constants as const
from sattlint.analyzers.sfc import analyze_sfc
from sattlint.models.ast_model import (
    BasePicture,
    ModuleCode,
    ModuleHeader,
    Sequence,
    SFCCodeBlocks,
    SFCParallel,
    SFCStep,
    Simple_DataType,
    Variable,
)


def _hdr(name: str) -> ModuleHeader:
    return ModuleHeader(name=name, invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0))


def _varref(name: str) -> dict:
    return {const.KEY_VAR_NAME: name}


def _assign(name: str, value: object) -> tuple:
    return (const.KEY_ASSIGN, _varref(name), value)


def _step(name: str, active_stmts: list[object]) -> SFCStep:
    return SFCStep(kind="step", name=name, code=SFCCodeBlocks(active=active_stmts))


def _sequence(nodes: list[object]) -> Sequence:
    return Sequence(
        name="SeqMain",
        type="sequence",
        position=(0.0, 0.0),
        size=(1.0, 1.0),
        code=nodes,
    )


def test_parallel_branch_write_race_detected():
    seq = _sequence(
        [
            SFCParallel(
                branches=[
                    [_step("Left", [_assign("Output", 1)])],
                    [_step("Right", [_assign("Output", 2)])],
                ]
            )
        ]
    )

    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[Variable(name="Output", datatype=Simple_DataType.INTEGER)],
        modulecode=ModuleCode(sequences=[seq], equations=[]),
    )

    report = analyze_sfc(bp)

    assert any(i.kind == "sfc_parallel_write_race" for i in report.issues)


def test_parallel_branch_distinct_writes_not_reported():
    seq = _sequence(
        [
            SFCParallel(
                branches=[
                    [_step("Left", [_assign("OutputA", 1)])],
                    [_step("Right", [_assign("OutputB", 2)])],
                ]
            )
        ]
    )

    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[
            Variable(name="OutputA", datatype=Simple_DataType.INTEGER),
            Variable(name="OutputB", datatype=Simple_DataType.INTEGER),
        ],
        modulecode=ModuleCode(sequences=[seq], equations=[]),
    )

    report = analyze_sfc(bp)

    assert not report.issues


def test_illegal_state_combination_detected_for_parallel_steps():
    seq = _sequence(
        [
            SFCParallel(
                branches=[
                    [_step("Idle", [])],
                    [_step("Running", [])],
                ]
            )
        ]
    )

    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[],
        modulecode=ModuleCode(sequences=[seq], equations=[]),
    )

    report = analyze_sfc(
        bp,
        mutually_exclusive_steps=[("Idle", "Running")],
    )

    issues = [
        issue for issue in report.issues if issue.kind == "sfc_illegal_state_combination"
    ]
    assert len(issues) == 1
    assert issues[0].data is not None
    assert issues[0].data["conflicts"] == [["Idle", "Running"]]


def test_valid_parallel_state_combination_not_reported():
    seq = _sequence(
        [
            SFCParallel(
                branches=[
                    [_step("Idle", [])],
                    [_step("Holding", [])],
                ]
            )
        ]
    )

    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[],
        modulecode=ModuleCode(sequences=[seq], equations=[]),
    )

    report = analyze_sfc(
        bp,
        mutually_exclusive_steps=[("Idle", "Running")],
    )

    assert not any(
        issue.kind == "sfc_illegal_state_combination" for issue in report.issues
    )
