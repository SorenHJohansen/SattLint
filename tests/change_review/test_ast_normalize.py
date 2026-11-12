"""Tests for the span-normalized change-review fingerprint.

Change Review currently fingerprints code statements. Header and
module-definition nodes are not statement nodes, so their bound-tail semantics
are pinned here at the fingerprint layer that the diff consumes.
"""

from __future__ import annotations

from sattline_parser.ast import (
    Assignment,
    ClippingClause,
    CodeComment,
    EnableClause,
    ModuleArguments,
    ModuleDef,
    ModuleHeader,
    ModuleTypeDef,
    SourceSpan,
    VarRef,
    VarTail,
)

from sattlint.change_review._ast_normalize import normalize_ast_value

SPAN_A = SourceSpan(start=0, end=1, line=1, column=1)
SPAN_B = SourceSpan(start=40, end=41, line=9, column=5)


def test_span_only_change_normalizes_equal() -> None:
    official = Assignment(target=VarRef(name="Flow", span=SPAN_A), value=1, span=SPAN_A)
    draft = Assignment(target=VarRef(name="Flow", span=SPAN_B), value=1, span=SPAN_B)

    assert normalize_ast_value(official) == normalize_ast_value(draft)


def test_layout_metadata_ignores_invoke_coordinate() -> None:
    official = ModuleHeader(name="Child", invoke_coord=(0.0, 0.0, 0.0, 0.5, 0.5))
    draft = ModuleHeader(name="Child", invoke_coord=(0.1, 0.1, 0.0, 0.9, 0.9))

    assert normalize_ast_value(official) == normalize_ast_value(draft)


def test_bound_coordinate_tail_change_normalizes_differently() -> None:
    official = ModuleHeader(
        name="Child",
        invoke_coord=(0.0, 0.0, 0.0, 0.5, 0.5),
        invoke_coord_tails=[VarTail(direction="in", value="PosVar")],
    )
    draft = ModuleHeader(
        name="Child",
        invoke_coord=(0.0, 0.0, 0.0, 0.5, 0.5),
        invoke_coord_tails=[VarTail(direction="in", value="OtherPosVar")],
    )

    assert normalize_ast_value(official) != normalize_ast_value(draft)


def test_enable_tail_change_normalizes_differently() -> None:
    official = ModuleHeader(
        name="Child",
        invoke_coord=(0.0, 0.0, 0.0, 0.5, 0.5),
        arguments=ModuleArguments(enable=EnableClause(enabled=True, tail=VarTail(direction="in", value="Flag"))),
    )
    draft = ModuleHeader(
        name="Child",
        invoke_coord=(0.0, 0.0, 0.0, 0.5, 0.5),
        arguments=ModuleArguments(enable=EnableClause(enabled=True, tail=VarTail(direction="in", value="OtherFlag"))),
    )

    assert normalize_ast_value(official) != normalize_ast_value(draft)


def test_clipping_bounds_are_layout_but_tails_are_semantic() -> None:
    official = ModuleDef(
        clipping=ClippingClause(
            bounds=((-1.0, -1.0), (1.0, 1.0)),
            tails=(VarTail(direction="in", value="ClipVar"),),
        )
    )
    moved = ModuleDef(
        clipping=ClippingClause(
            bounds=((-2.0, -2.0), (2.0, 2.0)),
            tails=(VarTail(direction="in", value="ClipVar"),),
        )
    )
    retargeted = ModuleDef(
        clipping=ClippingClause(
            bounds=((-1.0, -1.0), (1.0, 1.0)),
            tails=(VarTail(direction="in", value="OtherClipVar"),),
        )
    )

    assert normalize_ast_value(official) == normalize_ast_value(moved)
    assert normalize_ast_value(official) != normalize_ast_value(retargeted)


def test_comment_list_change_is_ignored() -> None:
    official = ModuleTypeDef(name="Valve", trailing_comments=[CodeComment(text="old note")])
    draft = ModuleTypeDef(name="Valve", trailing_comments=[CodeComment(text="new note")])

    assert normalize_ast_value(official) == normalize_ast_value(draft)


def test_unmarked_visual_configuration_is_semantic() -> None:
    # The parser does not mark grid/zoom metadata as layout, so Change Review
    # keeps them semantic by default. This guards that deliberate choice.
    official = ModuleDef(grid=0.2, zoomable=False)
    draft = ModuleDef(grid=0.5, zoomable=True)

    assert normalize_ast_value(official) != normalize_ast_value(draft)
