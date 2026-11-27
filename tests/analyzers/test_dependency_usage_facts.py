"""Focused tests for shared dependency-usage fact collection."""

from __future__ import annotations

from sattlint.analyzers.shared._dependency_usage_facts import collect_statement_facts
from sattlint.analyzers.shared.statement_sites import BlockKind
from sattlint.parser_api import (
    Assignment,
    BasePicture,
    BinOp,
    Equation,
    FuncCall,
    ModuleCode,
    ModuleHeader,
    ScalarDatatype,
    Sequence,
    SFCCodeBlocks,
    SFCStep,
    SFCTransition,
    Variable,
    VarRef,
)


def test_output_argument_inside_expression_is_a_write_not_a_read() -> None:
    bp = BasePicture(
        header=ModuleHeader(name="Root", invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0)),
        localvariables=[
            Variable(name="Text", datatype=ScalarDatatype.STRING),
            Variable(name="Status", datatype=ScalarDatatype.INTEGER),
            Variable(name="Value", datatype=ScalarDatatype.INTEGER),
        ],
        modulecode=ModuleCode(
            equationblocks=[
                Equation(
                    name="Main",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        Assignment(
                            target=VarRef(name="Value"),
                            value=BinOp(
                                left=1,
                                op="+",
                                right=FuncCall(
                                    name="StringToInteger",
                                    args=(VarRef(name="Text"), VarRef(name="Status")),
                                ),
                            ),
                        )
                    ],
                )
            ],
            sequences=[],
        ),
    )

    facts = collect_statement_facts(bp)

    assignment = next(fact for fact in facts if any(write.key[-1] == "value" for write in fact.writes))
    read_names = {read.key[-1] for read in assignment.reads}
    write_names = {write.key[-1] for write in assignment.writes}

    assert "status" in write_names
    assert "status" not in read_names
    assert "text" in read_names


def _header(name: str) -> ModuleHeader:
    return ModuleHeader(name=name, invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0))


def test_equation_statement_facts_carry_the_equation_block_kind() -> None:
    bp = BasePicture(
        header=_header("Root"),
        localvariables=[
            Variable(name="Source", datatype=ScalarDatatype.INTEGER),
            Variable(name="Output", datatype=ScalarDatatype.INTEGER),
        ],
        modulecode=ModuleCode(
            equationblocks=[
                Equation(
                    name="Main",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        Assignment(target=VarRef(name="Output"), value=VarRef(name="Source")),
                        Assignment(target=VarRef(name="Source"), value=3),
                    ],
                )
            ],
            sequences=[],
        ),
    )

    facts = collect_statement_facts(bp)

    assert [fact.block_kind for fact in facts] == [BlockKind.EQUATION, BlockKind.EQUATION]
    assert [fact.site for fact in facts] == ["equation block 'Main'", "equation block 'Main'"]


def test_sequence_statement_facts_carry_step_and_transition_kinds() -> None:
    bp = BasePicture(
        header=_header("Root"),
        localvariables=[
            Variable(name="Source", datatype=ScalarDatatype.INTEGER),
            Variable(name="Output", datatype=ScalarDatatype.INTEGER),
            Variable(name="Gate", datatype=ScalarDatatype.BOOLEAN),
        ],
        modulecode=ModuleCode(
            equationblocks=[],
            sequences=[
                Sequence(
                    name="SeqMain",
                    type="sequence",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        SFCStep(
                            kind="step",
                            name="S1",
                            code=SFCCodeBlocks(
                                active=[Assignment(target=VarRef(name="Output"), value=VarRef(name="Source"))]
                            ),
                        ),
                        SFCTransition(name="Gate", condition=VarRef(name="Gate")),
                    ],
                )
            ],
        ),
    )

    facts = collect_statement_facts(bp)

    assert [fact.block_kind for fact in facts] == [BlockKind.STEP, BlockKind.TRANSITION]
    assert facts[0].site == "sequence 'SeqMain' step 'S1' ACTIVE"
    assert facts[1].site == "sequence 'SeqMain' transition 'Gate' condition"
