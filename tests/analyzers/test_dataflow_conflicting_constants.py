# pyright: reportUnknownVariableType=false, reportUnknownParameterType=false, reportUnknownArgumentType=false, reportMissingTypeArgument=false
from __future__ import annotations

from typing import Any

from sattline_parser.models.ast_model import (
    BasePicture,
    CodeItem,
    DataType,
    Equation,
    IntLiteral,
    ModuleCode,
    ModuleHeader,
    Simple_DataType,
    Variable,
)
from sattline_parser.models.expressions import Assignment, IfStmt, VarRef

from sattlint.analyzers.dataflow import analyze_dataflow


def _hdr(name: str) -> ModuleHeader:
    return ModuleHeader(name=name, invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0))


def _varref(name: str) -> VarRef:
    return VarRef(name=name)


def _report(code: list[CodeItem], variables: tuple[str, ...] = ("X", "Y", "Cond")):
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[Variable(name=name, datatype=Simple_DataType.INTEGER) for name in variables],
        modulecode=ModuleCode(
            sequences=[],
            equations=[Equation(name="Main", position=(0.0, 0.0), size=(1.0, 1.0), code=code)],
        ),
        moduledef=None,
    )
    return analyze_dataflow(bp)


def _record_report(code: list[CodeItem]):
    record_type = DataType(
        name="RecordType",
        description=None,
        datecode=None,
        var_list=[
            Variable(name="First", datatype=Simple_DataType.BOOLEAN),
            Variable(name="Second", datatype=Simple_DataType.BOOLEAN),
        ],
    )
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[record_type],
        localvariables=[
            Variable(name="Rec", datatype="RecordType"),
            Variable(name="Snapshot", datatype="RecordType"),
            Variable(name="Sink", datatype=Simple_DataType.BOOLEAN),
        ],
        modulecode=ModuleCode(
            sequences=[],
            equations=[Equation(name="Main", position=(0.0, 0.0), size=(1.0, 1.0), code=code)],
        ),
        moduledef=None,
    )
    return analyze_dataflow(bp)


def _conflicting_kinds(report: Any) -> set[str]:
    return {issue.kind for issue in report.issues if hasattr(issue, "kind")}


def test_conflicting_constants_fires_when_constant_read_in_between() -> None:
    report = _report(
        [
            Assignment(target=_varref("X"), value=IntLiteral(1)),
            Assignment(target=_varref("Y"), value=_varref("X")),
            Assignment(target=_varref("X"), value=IntLiteral(2)),
        ]
    )

    issues = [issue for issue in report.issues if issue.kind == "dataflow.conflicting_constants"]
    assert len(issues) == 1
    assert issues[0].data is not None
    assert issues[0].data["symbol"] == "X"
    assert issues[0].data["previous_value"] == 1
    assert issues[0].data["value"] == 2


def test_conflicting_constants_ignores_reads_of_sibling_record_fields() -> None:
    report = _record_report(
        [
            Assignment(target=_varref("Rec.First"), value=True),
            Assignment(target=_varref("Sink"), value=_varref("Rec.Second")),
            Assignment(target=_varref("Rec.First"), value=False),
        ]
    )

    assert "dataflow.conflicting_constants" not in _conflicting_kinds(report)


def test_conflicting_constants_tracks_whole_record_reads_of_fields() -> None:
    report = _record_report(
        [
            Assignment(target=_varref("Rec.First"), value=True),
            Assignment(target=_varref("Snapshot"), value=_varref("Rec")),
            Assignment(target=_varref("Rec.First"), value=False),
        ]
    )

    assert "dataflow.conflicting_constants" in _conflicting_kinds(report)


def test_dead_overwrite_survives_sibling_record_field_reads() -> None:
    report = _record_report(
        [
            Assignment(target=_varref("Rec.First"), value=True),
            Assignment(target=_varref("Sink"), value=_varref("Rec.Second")),
            Assignment(target=_varref("Rec.First"), value=False),
        ]
    )

    issues = [issue for issue in report.issues if issue.kind == "dataflow.dead_overwrite"]
    assert len(issues) == 1
    assert issues[0].data is not None
    assert issues[0].data["symbol"] == "Rec.First"


def test_dead_overwrite_is_consumed_by_whole_record_reads() -> None:
    report = _record_report(
        [
            Assignment(target=_varref("Rec.First"), value=True),
            Assignment(target=_varref("Snapshot"), value=_varref("Rec")),
            Assignment(target=_varref("Rec.First"), value=False),
        ]
    )

    assert "dataflow.dead_overwrite" not in _conflicting_kinds(report)


def test_conflicting_constants_does_not_fire_without_read_in_between() -> None:
    report = _report(
        [
            Assignment(target=_varref("X"), value=IntLiteral(1)),
            Assignment(target=_varref("X"), value=IntLiteral(2)),
        ]
    )

    assert "dataflow.conflicting_constants" not in _conflicting_kinds(report)
    assert "dataflow.dead_overwrite" in _conflicting_kinds(report)


def test_conflicting_constants_is_path_sensitive_for_branch_exclusive_writes() -> None:
    report = _report(
        [
            IfStmt(
                branches=((_varref("Cond"), (Assignment(target=_varref("X"), value=IntLiteral(1)),)),),
                else_block=(Assignment(target=_varref("X"), value=IntLiteral(2)),),
            )
        ]
    )

    assert "dataflow.conflicting_constants" not in _conflicting_kinds(report)


def test_conflicting_constants_does_not_fire_across_branch_then_reassignment() -> None:
    report = _report(
        [
            IfStmt(
                branches=((_varref("Cond"), (Assignment(target=_varref("X"), value=IntLiteral(1)),)),),
                else_block=(),
            ),
            Assignment(target=_varref("X"), value=IntLiteral(2)),
        ]
    )

    assert "dataflow.conflicting_constants" not in _conflicting_kinds(report)


def test_conflicting_constants_fires_after_read_in_branch_merge() -> None:
    report = _report(
        [
            Assignment(target=_varref("X"), value=IntLiteral(1)),
            Assignment(target=_varref("Y"), value=_varref("X")),
            IfStmt(
                branches=((_varref("Cond"), (Assignment(target=_varref("X"), value=IntLiteral(3)),)),),
                else_block=(),
            ),
            Assignment(target=_varref("X"), value=IntLiteral(4)),
        ]
    )

    assert "dataflow.conflicting_constants" in _conflicting_kinds(report)
