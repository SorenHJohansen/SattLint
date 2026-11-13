# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownArgumentType=false
"""Focused tests for shared dependency-usage fact collection."""

from __future__ import annotations

from sattlint.analyzers.shared._dependency_usage_facts import collect_statement_facts
from sattlint.parser_api import (
    Assignment,
    BasePicture,
    BinOp,
    Equation,
    FuncCall,
    ModuleCode,
    ModuleHeader,
    Simple_DataType,
    Variable,
    VarRef,
)


def test_output_argument_inside_expression_is_a_write_not_a_read() -> None:
    bp = BasePicture(
        header=ModuleHeader(name="Root", invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0)),
        localvariables=[
            Variable(name="Text", datatype=Simple_DataType.STRING),
            Variable(name="Status", datatype=Simple_DataType.INTEGER),
            Variable(name="Value", datatype=Simple_DataType.INTEGER),
        ],
        modulecodes=[
            ModuleCode(
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
            )
        ],
    )

    facts = collect_statement_facts(bp)

    assignment = next(fact for fact in facts if any(write.key[-1] == "value" for write in fact.writes))
    read_names = {read.key[-1] for read in assignment.reads}
    write_names = {write.key[-1] for write in assignment.writes}

    assert "status" in write_names
    assert "status" not in read_names
    assert "text" in read_names
