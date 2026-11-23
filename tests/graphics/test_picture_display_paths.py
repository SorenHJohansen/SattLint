"""PictureDisplay path diagnostics honor the project's string capacities.

A dynamic path row is resolved through exact string inference, so the
configured capacity of the string datatype decides whether a copy into the
path variable overflows - and therefore whether the row has a candidate at
all.
"""

from __future__ import annotations

from sattline_parser.models.ast_model import (
    BasePicture,
    Equation,
    GraphObject,
    ModuleCode,
    ModuleDef,
    ModuleHeader,
    ScalarDatatype,
    SourceSpan,
    Variable,
)
from sattline_parser.models.expressions import FuncCall, FuncCallStmt, VarRef

from sattlint.config.string_capacities import STANDARD_STRING_CAPACITIES, StringCapacities
from sattlint.graphics.picture_display_paths import (
    correlate_picture_display_records,
    diagnose_picture_display_paths,
)
from sattlint.graphics.validation import PictureDisplayPathRow, PictureDisplayRecord

PATH_TEXT = "MissingPanel1234567890123"
"""A 25-character path: longer than a 20-character string, shorter than 40."""


def _string_capacities(*, string_capacity: int) -> StringCapacities:
    return StringCapacities(
        identstring=STANDARD_STRING_CAPACITIES.identstring,
        tagstring=STANDARD_STRING_CAPACITIES.tagstring,
        string=string_capacity,
        linestring=STANDARD_STRING_CAPACITIES.linestring,
        maxstring=STANDARD_STRING_CAPACITIES.maxstring,
    )


def _base_picture() -> BasePicture:
    return BasePicture(
        header=ModuleHeader(name="Root", invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0)),
        name="Root",
        localvariables=[Variable(name="PathVar", datatype=ScalarDatatype.STRING)],
        moduledef=ModuleDef(graph_objects=[GraphObject("CompositeObject")]),
        modulecode=ModuleCode(
            equationblocks=[
                Equation(
                    name="Main",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        FuncCallStmt(
                            call=FuncCall(
                                name="CopyString",
                                args=(PATH_TEXT, VarRef(name="PathVar")),
                            )
                        )
                    ],  # pyright: ignore[reportArgumentType]
                )
            ]
        ),
    )


def _variable_occurrences(base_picture: BasePicture):
    record = PictureDisplayRecord(
        record_index=1,
        record_start_line=1,
        record_end_line=2,
        path_rows=(
            PictureDisplayPathRow(
                1,
                "0",
                0,
                "variable",
                "PathVar",
                SourceSpan(start=0, end=0, line=1, column=1),
            ),
        ),
    )
    occurrences = correlate_picture_display_records(base_picture, (record,))
    assert occurrences
    return occurrences


def test_default_capacity_infers_the_path_and_reports_it_unresolved() -> None:
    base_picture = _base_picture()

    diagnostics = diagnose_picture_display_paths(
        base_picture,
        _variable_occurrences(base_picture),
        capacities=STANDARD_STRING_CAPACITIES,
    )

    assert len(diagnostics) == 1
    assert diagnostics[0].resolution.path_text == PATH_TEXT
    assert diagnostics[0].resolution.failure_reason == "missing_named_child"


def test_a_tighter_string_capacity_overflows_the_copy_and_drops_the_candidate() -> None:
    base_picture = _base_picture()

    diagnostics = diagnose_picture_display_paths(
        base_picture,
        _variable_occurrences(base_picture),
        capacities=_string_capacities(string_capacity=20),
    )

    assert diagnostics == ()


def test_a_literal_path_row_is_independent_of_the_configured_capacity() -> None:
    base_picture = _base_picture()
    record = PictureDisplayRecord(
        record_index=1,
        record_start_line=1,
        record_end_line=2,
        path_rows=(
            PictureDisplayPathRow(
                1,
                "0",
                0,
                "literal",
                PATH_TEXT,
                SourceSpan(start=0, end=0, line=1, column=1),
            ),
        ),
    )
    occurrences = correlate_picture_display_records(base_picture, (record,))
    assert occurrences

    diagnostics = diagnose_picture_display_paths(
        base_picture,
        occurrences,
        capacities=_string_capacities(string_capacity=20),
    )

    assert len(diagnostics) == 1
    assert diagnostics[0].resolution.path_text == PATH_TEXT
