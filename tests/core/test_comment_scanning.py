# pyright: reportPrivateUsage=false
"""Comment scanning hands one typed record to its hit factory."""

from __future__ import annotations

from sattlint.utils._comment_scanning import CommentScanHit, scan_comments_with_code
from sattlint.utils.text_processing import (
    _advance_position,
    _comment_code_indicators,
    _consume_identifier,
    _is_identifier_start,
)


def test_hit_factory_receives_one_record() -> None:
    records: list[CommentScanHit] = []

    def _factory(record: CommentScanHit) -> CommentScanHit:
        records.append(record)
        return record

    text = """
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    X = 1;
    (* X = 2; *)
ENDDEF (*BasePicture*);
""".strip()

    hits = scan_comments_with_code(
        text,
        advance_position=_advance_position,
        is_identifier_start=_is_identifier_start,
        consume_identifier=_consume_identifier,
        comment_code_indicators=_comment_code_indicators,
        hit_factory=_factory,
    )

    assert hits == records
    assert records[0].text.strip() == "X = 2;"
