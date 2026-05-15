from sattline_parser.models.ast_model import (
    BasePicture,
    Equation,
    ModuleCode,
    ModuleHeader,
    Sequence,
    SFCCodeBlocks,
    SFCStep,
    Simple_DataType,
    Variable,
)
from sattlint import constants as const
from sattlint.analyzers.loop_output_refactor import analyze_loop_output_refactor
from sattlint.analyzers.registry import get_default_analyzers


def _hdr(name: str) -> ModuleHeader:
    return ModuleHeader(name=name, invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0))


def _varref(name: str) -> dict:
    return {const.KEY_VAR_NAME: name}


def test_loop_output_refactor_detects_cycle_across_equations_and_active_step() -> None:
    eq_input = Equation(
        name="Input",
        position=(0.0, 0.0),
        size=(1.0, 1.0),
        code=[(const.KEY_ASSIGN, _varref("A"), _varref("B"))],
    )
    eq_feedback = Equation(
        name="Feedback",
        position=(1.0, 0.0),
        size=(1.0, 1.0),
        code=[(const.KEY_ASSIGN, _varref("B"), _varref("C"))],
    )
    seq = Sequence(
        name="MainSeq",
        type="sequence",
        position=(0.0, 1.0),
        size=(1.0, 1.0),
        code=[
            SFCStep(
                kind="step",
                name="Transfer",
                code=SFCCodeBlocks(active=[(const.KEY_ASSIGN, _varref("C"), _varref("A"))]),
            )
        ],
    )
    bp = BasePicture(
        header=_hdr("BasePicture"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[
            Variable(name="A", datatype=Simple_DataType.INTEGER),
            Variable(name="B", datatype=Simple_DataType.INTEGER),
            Variable(name="C", datatype=Simple_DataType.INTEGER),
        ],
        submodules=[],
        modulecode=ModuleCode(equations=[eq_input, eq_feedback], sequences=[seq]),
        moduledef=None,
    )

    report = analyze_loop_output_refactor(bp)

    issues = [issue for issue in report.issues if issue.kind == "sorting.loop_output_refactor"]
    assert len(issues) == 1
    issue = issues[0]
    assert issue.data is not None
    assert issue.data["dependency_variables"] == ["a", "b", "c"]
    assert issue.data["blocks"] == [
        "EquationBlock 'Input'",
        "EquationBlock 'Feedback'",
        "Sequence 'MainSeq' step 'Transfer' ACTIVE",
    ]
    assert "At least one dependency in this cycle is delayed by one scan" in issue.data["loop_text"]


def test_loop_output_refactor_ignores_acyclic_sorted_blocks() -> None:
    eq_source = Equation(
        name="Source",
        position=(0.0, 0.0),
        size=(1.0, 1.0),
        code=[(const.KEY_ASSIGN, _varref("A"), _varref("B"))],
    )
    eq_sink = Equation(
        name="Sink",
        position=(1.0, 0.0),
        size=(1.0, 1.0),
        code=[(const.KEY_ASSIGN, _varref("C"), _varref("A"))],
    )
    bp = BasePicture(
        header=_hdr("BasePicture"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[
            Variable(name="A", datatype=Simple_DataType.INTEGER),
            Variable(name="B", datatype=Simple_DataType.INTEGER),
            Variable(name="C", datatype=Simple_DataType.INTEGER),
        ],
        submodules=[],
        modulecode=ModuleCode(equations=[eq_source, eq_sink], sequences=[]),
        moduledef=None,
    )

    report = analyze_loop_output_refactor(bp)

    assert not any(issue.kind == "sorting.loop_output_refactor" for issue in report.issues)


def test_loop_output_refactor_analyzer_is_enabled_by_default() -> None:
    specs = {spec.key: spec for spec in get_default_analyzers()}

    assert "loop-output-refactor" in specs
    assert specs["loop-output-refactor"].enabled is True
