from sattlint.graphics_validation import _parse_picture_display_row


def test_parse_picture_display_row_accepts_nested_invalid_variable_paths() -> None:
    row = _parse_picture_display_row("2 1 Var Invalid 9 PathNotOK", record_index=1, line=10)

    assert row is not None
    assert row.index_token == "2"
    assert row.index_value == 2
    assert row.kind == "variable_invalid"
    assert row.raw_text == "PathNotOK"
    assert row.span.line == 10
    assert row.span.column == 19


def test_parse_picture_display_row_keeps_plain_invalid_variable_paths_excluded() -> None:
    assert _parse_picture_display_row("1 Var Invalid 7 PathAIT", record_index=1, line=3) is None
