from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from lark import Tree
from lsprotocol.types import DiagnosticSeverity

import sattlint.graphics_validation as graphics_validation
from sattline_parser.models.ast_model import BasePicture, GraphObject, ModuleDef, ModuleHeader, SourceSpan
from sattlint import app
from sattlint._validation_shared import ValidationNotice
from sattlint.core.ast_tools import iter_variable_refs
from sattlint.engine import CodeMode, resolve_graphics_companion_path, validate_single_file_syntax
from sattlint.graphics_validation import validate_graphics_text
from sattlint_lsp.server import collect_syntax_diagnostics

VALID_SINGLE_FILE = """"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ENDDEF (*BasePicture*);
"""
SAMPLE_FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "sample_sattline_files"


def _write_source_file(tmp_path: Path, name: str) -> Path:
    file_path = tmp_path / name
    file_path.write_text(VALID_SINGLE_FILE, encoding="utf-8")
    return file_path


def _write_graphics_file(tmp_path: Path, name: str, row: str) -> Path:
    content = f"""" Syntax version 2.23, date: 2026-04-22-00:00:00.000 N "

 5
 None  True   0.00000E+00 0.00000E+00
  3.00000E-01 2.00000E-01
 9
 2
 None 0  Lit 9 2 -1     0
 {row}
 None  True
 t
           0
"""
    file_path = tmp_path / name
    file_path.write_text(content, encoding="utf-8")
    return file_path


def test_validate_graphics_text_warns_for_unverified_scr_asset(tmp_path: Path):
    file_path = _write_graphics_file(tmp_path, "Panel.g", "0 scr:missing_asset.wmf")

    result = validate_graphics_text(file_path.read_text(encoding="utf-8"), file_path)

    assert result.errors == ()
    assert len(result.warnings) == 1
    assert result.warnings[0].message == ".emf and .wmf resolution is not implemented"


def test_validate_graphics_text_warns_for_unimplemented_env_var_wmf_asset(tmp_path: Path):
    file_path = _write_graphics_file(tmp_path, "Panel.g", "0 sg_pictures:missing_asset.wmf")

    result = validate_graphics_text(file_path.read_text(encoding="utf-8"), file_path)

    assert result.errors == ()
    assert len(result.warnings) == 1
    assert result.warnings[0].message == ".emf and .wmf resolution is not implemented"


def test_validate_single_file_syntax_reports_graphics_error_for_empty_scr_alias(tmp_path: Path):
    file_path = _write_graphics_file(tmp_path, "BrokenPanel.g", "0 scr:")

    result = validate_single_file_syntax(file_path)

    assert result.ok is False
    assert result.stage == "graphics"
    assert "must include a file name after 'scr:'" in str(result.message)


def test_syntax_check_command_accepts_graphics_file_with_warning(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
):
    file_path = _write_graphics_file(tmp_path, "Panel.g", "0 scr:missing_asset.wmf")

    exit_code = app.main(["syntax-check", str(file_path)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out.strip() == "OK"
    assert ".emf and .wmf resolution is not implemented" in captured.err


def test_collect_syntax_diagnostics_returns_warning_for_graphics_asset(tmp_path: Path):
    file_path = _write_graphics_file(tmp_path, "Panel.g", "0 scr:missing_asset.wmf")

    diagnostics = collect_syntax_diagnostics(
        file_path,
        file_path.read_text(encoding="utf-8"),
    )

    assert len(diagnostics) == 1
    assert diagnostics[0].severity == DiagnosticSeverity.Warning
    assert diagnostics[0].message == ".emf and .wmf resolution is not implemented"


def test_validate_graphics_text_collects_var_expr_and_lit_bindings(tmp_path: Path):
    file_path = _write_graphics_file(tmp_path, "Panel.g", "Expr  True  13 not PrintList")
    literal_file_path = _write_graphics_file(tmp_path, "LiteralPanel.g", "Lit  True  4 True")

    result = validate_graphics_text(file_path.read_text(encoding="utf-8"), file_path)
    literal_result = validate_graphics_text(literal_file_path.read_text(encoding="utf-8"), literal_file_path)

    expr_bindings = [binding for binding in result.bindings if binding.kind == "expr"]
    literal_bindings = [binding for binding in literal_result.bindings if binding.kind == "lit"]

    assert literal_bindings
    assert any(binding.raw_text == "True" and binding.value is True for binding in literal_bindings)
    assert [binding.raw_text for binding in expr_bindings] == ["not PrintList"]

    refs = list(iter_variable_refs(expr_bindings[0].value))
    assert len(refs) == 1
    assert refs[0]["var_name"] == "PrintList"
    assert refs[0]["span"].line == 9


def test_validate_graphics_text_collects_var_binding_with_source_span(tmp_path: Path):
    file_path = _write_graphics_file(tmp_path, "Panel.g", "Var 0 10 ErrorIndex")

    result = validate_graphics_text(file_path.read_text(encoding="utf-8"), file_path)

    var_bindings = [binding for binding in result.bindings if binding.kind == "var"]

    assert [binding.raw_text for binding in var_bindings] == ["ErrorIndex"]
    assert var_bindings[0].value == {
        "var_name": "ErrorIndex",
        "span": var_bindings[0].span,
    }
    assert var_bindings[0].span is not None
    assert var_bindings[0].span.line == 9


def test_validate_graphics_text_decodes_picturedisplay_path_rows(tmp_path: Path) -> None:
    file_path = _write_graphics_file(tmp_path, "Panel.g", "0 0 +L2+UnitControl")

    result = validate_graphics_text(file_path.read_text(encoding="utf-8"), file_path)

    assert len(result.picture_display_records) == 1
    record = result.picture_display_records[0]
    assert record.record_index == 1
    assert record.subtype == "2"
    assert [row.kind for row in record.path_rows] == ["literal"]
    assert record.path_rows[0].index_token == "0"
    assert record.path_rows[0].index_value == 0
    assert record.path_rows[0].raw_text == "+L2+UnitControl"
    assert record.path_rows[0].span.line == 9


def test_validate_graphics_text_decodes_picturedisplay_variable_path_rows(tmp_path: Path) -> None:
    file_path = _write_graphics_file(tmp_path, "Panel.g", "1 Var 0 19 Paths.OperationPath")

    result = validate_graphics_text(file_path.read_text(encoding="utf-8"), file_path)

    assert len(result.picture_display_records) == 1
    record = result.picture_display_records[0]
    assert [row.kind for row in record.path_rows] == ["variable"]
    assert record.path_rows[0].index_token == "1"
    assert record.path_rows[0].index_value == 1
    assert record.path_rows[0].raw_text == "Paths.OperationPath"
    assert record.path_rows[0].span.line == 9


def test_validate_graphics_text_handles_internal_zero_lines_before_record_terminator(tmp_path: Path) -> None:
    file_path = tmp_path / "Panel.g"
    file_path.write_text(
        "\n".join(
            [
                '" Syntax version 2.23, date: 2026-04-22-00:00:00.000 N "',
                "",
                " 5",
                " None  True  -1.00000E-02 2.50000E-01",
                "  6.90000E-01 1.20000E+00",
                " 0",
                " 2",
                " Var 0 10 ColumnType  Lit 0 2 -1     2",
                "1 0 +InletMPC+++Inlet_Z2 ",
                "2 0 +InletMPC+++Inlet_Z3_5 ",
                " 0 +InletMPC+++Inlet_Z2 ",
                " None  True  ",
                "t",
                "           0",
                "",
                " 5",
                " None  True   4.70000E-01 1.16000E+00",
                "  1.41000E+00 1.39000E+00",
                " 0",
                " 2",
                " None 0  Lit 0 2 -1     0",
                " 0 +UnitControl+++Operations++OprFrame+Produktion+++Displays+++FacePlateModule+++FacePlate ",
                " None  True  ",
                "t",
                "           0",
                "",
            ]
        ),
        encoding="utf-8",
    )

    result = validate_graphics_text(file_path.read_text(encoding="utf-8"), file_path)

    assert [record.record_index for record in result.picture_display_records] == [1, 2]
    assert [row.raw_text for row in result.picture_display_records[0].path_rows] == [
        "+InletMPC+++Inlet_Z2",
        "+InletMPC+++Inlet_Z3_5",
        "+InletMPC+++Inlet_Z2",
    ]
    assert [row.raw_text for row in result.picture_display_records[1].path_rows] == [
        "+UnitControl+++Operations++OprFrame+Produktion+++Displays+++FacePlateModule+++FacePlate",
    ]


def test_validate_graphics_text_collects_inline_bindings_from_fixture() -> None:
    file_path = SAMPLE_FIXTURE_DIR / "TestGFileParse.g"

    result = validate_graphics_text(file_path.read_text(encoding="utf-8"), file_path)

    variable_names = {binding.raw_text.casefold() for binding in result.bindings if binding.kind == "var"}

    assert {
        "enablevar",
        "indexvar",
        "linecolorvar",
        "index1pathvar",
        "index2parthvar",
        "defaultpathvar",
        "resetvar",
        "minvar",
        "maxvar",
        "unitvar",
        "barvariable",
        "maxlimitvar",
        "minlimitvar",
        "areacolorvar",
        "textcolorvar",
    } <= variable_names


def test_validate_graphics_text_tracks_all_composite_record_ranges(tmp_path: Path) -> None:
    file_path = tmp_path / "Panel.g"
    file_path.write_text(
        "\n".join(
            [
                '" Syntax version 2.23, date: 2026-04-22-00:00:00.000 N "',
                "",
                " 1",
                " Var  True  10 NestedOnly",
                "  2.00000E-01 8.00000E-01",
                " 0",
                " 0",
                "",
                " 5",
                " None  True   0.00000E+00 0.00000E+00",
                "  3.00000E-01 2.00000E-01",
                " 9",
                " 2",
                " None 0  Lit 9 2 -1     0",
                " 0 +L2+UnitControl",
                " None  True",
                " t",
                "           0",
            ]
        ),
        encoding="utf-8",
    )

    result = validate_graphics_text(file_path.read_text(encoding="utf-8"), file_path)

    assert [record.record_index for record in result.composite_records] == [1, 2]
    assert result.composite_records[0].record_start_line == 3
    assert result.composite_records[0].record_end_line == 7
    assert result.composite_records[1].record_start_line == 9
    assert result.composite_records[1].record_end_line == 18


def test_graphics_validation_helper_branches_cover_tree_span_and_literal_paths(tmp_path: Path) -> None:
    unwrap_expression_root = graphics_validation._unwrap_expression_root
    offset_source_spans = graphics_validation._offset_source_spans
    coerce_graphics_literal = graphics_validation._coerce_graphics_literal
    extract_literal_path = graphics_validation._extract_literal_path
    parse_picture_display_row = graphics_validation._parse_picture_display_row
    validate_literal_path = graphics_validation._validate_literal_path

    assert unwrap_expression_root(Tree("expression", ["leaf"])) == "leaf"
    passthrough_tree = Tree("term", ["leaf"])
    assert unwrap_expression_root(passthrough_tree) is passthrough_tree

    list_node = [{"span": SourceSpan(line=1, column=2)}]
    offset_source_spans(list_node, line_offset=5, column_offset=7)
    assert list_node[0]["span"] == SourceSpan(line=5, column=8)

    child_list_node = SimpleNamespace(children=[{"span": SourceSpan(line=2, column=3)}])
    offset_source_spans(child_list_node, line_offset=10, column_offset=4)
    assert child_list_node.children[0]["span"] == SourceSpan(line=11, column=3)

    child_tuple_node = SimpleNamespace(children=({"span": SourceSpan(line=1, column=1)},))
    offset_source_spans(child_tuple_node, line_offset=8, column_offset=6)
    assert child_tuple_node.children[0]["span"] == SourceSpan(line=8, column=6)

    assert coerce_graphics_literal("false") is False
    assert coerce_graphics_literal("1.25") == 1.25
    assert extract_literal_path("0") is None
    assert extract_literal_path("0 Var 0 3 Foo") is None

    assert parse_picture_display_row("", record_index=1, line=3) is None
    assert parse_picture_display_row("0", record_index=1, line=3) is None
    assert parse_picture_display_row("0    ", record_index=1, line=3) is None
    assert parse_picture_display_row("1 Lit 0 4 True", record_index=1, line=3) is None
    assert parse_picture_display_row("1 None ignored", record_index=1, line=3) is None

    empty_path_message = validate_literal_path(tmp_path / "Panel.g", "   ", line=4, column=5)
    assert empty_path_message is not None
    assert empty_path_message.message == "PictureDisplay contains an empty literal path"

    asset_dir = tmp_path / "scr"
    asset_dir.mkdir()
    (asset_dir / "present.wmf").write_text("", encoding="utf-8")
    present_asset_message = validate_literal_path(tmp_path / "nested" / "Panel.g", "scr:present.wmf", line=4, column=5)
    assert present_asset_message is not None
    assert present_asset_message.message == ".emf and .wmf resolution is not implemented"

    class _BlankPayload(str):
        def split(self, _sep: object = None, _maxsplit: int = -1) -> list[str]:
            return ["1", "   "]

    class _RowText(str):
        def strip(self) -> _BlankPayload:
            return _BlankPayload(self)

    assert parse_picture_display_row(cast(Any, _RowText("forced-empty-payload")), record_index=1, line=3) is None


def test_graphics_validation_helper_branches_cover_binding_failures_and_warnings() -> None:
    binding_line_re = graphics_validation._BINDING_LINE_RE
    parse_graphics_binding_match = graphics_validation._parse_graphics_binding_match

    negative_length_row = "Expr 0 -1 ignored"
    negative_length_match = binding_line_re.search(negative_length_row)
    assert negative_length_match is not None
    assert parse_graphics_binding_match(
        negative_length_row,
        line=6,
        match=negative_length_match,
    ) == (None, ())

    empty_payload_row = "Lit 0 3    "
    empty_payload_match = binding_line_re.search(empty_payload_row)
    assert empty_payload_match is not None
    assert parse_graphics_binding_match(
        empty_payload_row,
        line=7,
        match=empty_payload_match,
    ) == (None, ())

    bad_expr_row = "Expr 0 4 ????"
    bad_expr_match = binding_line_re.search(bad_expr_row)
    assert bad_expr_match is not None
    binding, messages = parse_graphics_binding_match(bad_expr_row, line=8, match=bad_expr_match)

    assert binding is not None
    assert binding.kind == "expr"
    assert binding.value == "????"
    assert len(messages) == 1
    assert messages[0].severity == "warning"
    assert "Could not parse graphics expression" in messages[0].message


def test_validate_graphics_text_covers_unterminated_wrong_subtype_and_keep_shape_errors(tmp_path: Path) -> None:
    file_path = _write_graphics_file(tmp_path, "Panel.g", "0 +L2+UnitControl")
    text = file_path.read_text(encoding="utf-8")

    unterminated_result = validate_graphics_text(text.rsplit("0", 1)[0], file_path)
    assert unterminated_result.picture_display_records == ()
    assert unterminated_result.errors[0].message == "Unterminated graphics record; expected trailing '0' line"

    wrong_subtype_result = validate_graphics_text(text.replace("\n 2\n", "\n 7\n", 1), file_path)
    assert wrong_subtype_result.messages == ()
    assert wrong_subtype_result.picture_display_records == ()

    missing_keep_shape_result = validate_graphics_text(text.replace("\n t\n", "\n maybe\n", 1), file_path)
    assert missing_keep_shape_result.picture_display_records == ()
    assert missing_keep_shape_result.errors[0].message == (
        "PictureDisplay record is missing the trailing KeepPictureShape flag"
    )


def test_resolve_graphics_companion_prefers_g_and_falls_back_to_y_in_draft_mode(tmp_path: Path):
    source_file = _write_source_file(tmp_path, "Panel.s")
    fallback_file = _write_graphics_file(tmp_path, "Panel.y", "0 scr:missing_asset.wmf")

    assert resolve_graphics_companion_path(source_file, mode=CodeMode.DRAFT) == fallback_file

    preferred_file = _write_graphics_file(tmp_path, "Panel.g", "0 scr:missing_asset.wmf")

    assert resolve_graphics_companion_path(source_file, mode=CodeMode.DRAFT) == preferred_file


def test_validate_single_file_syntax_falls_back_to_y_when_g_is_missing(tmp_path: Path):
    source_file = _write_source_file(tmp_path, "Panel.s")
    _write_graphics_file(tmp_path, "Panel.y", "0 scr:missing_asset.wmf")

    result = validate_single_file_syntax(source_file)

    assert result.ok is True
    assert result.warnings == (".emf and .wmf resolution is not implemented",)


def test_validate_single_file_syntax_uses_y_when_mode_is_official(tmp_path: Path):
    source_file = _write_source_file(tmp_path, "Panel.s")
    _write_graphics_file(tmp_path, "Panel.g", "0 scr:")
    _write_graphics_file(tmp_path, "Panel.y", "0 +L2+UnitControl+L1+L2+Panel")

    result = validate_single_file_syntax(source_file, mode=CodeMode.OFFICIAL)

    assert result.ok is True
    assert result.warnings == ()


def test_validate_single_file_syntax_warns_for_unresolved_picturedisplay_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source_file = _write_source_file(tmp_path, "Panel.s")
    _write_graphics_file(tmp_path, "Panel.g", "0 +MissingPanel")
    base_picture = BasePicture(
        header=ModuleHeader(name="Panel", invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0)),
        name="Panel",
        moduledef=ModuleDef(graph_objects=[GraphObject("CompositeObject")]),
    )

    monkeypatch.setattr("sattlint.engine._load_source_text", lambda _path: VALID_SINGLE_FILE)
    monkeypatch.setattr("sattlint.engine.find_disallowed_comments", lambda _src: [])
    monkeypatch.setattr("sattlint.engine.parser_core_parse_source_text", lambda *args, **kwargs: base_picture)
    monkeypatch.setattr("sattlint.engine.validate_transformed_basepicture", lambda *args, **kwargs: None)

    result = validate_single_file_syntax(source_file)

    assert result.ok is True
    assert any("could not be resolved" in warning for warning in result.warnings)


def test_validate_single_file_syntax_uses_sibling_source_context_for_graphics_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    graphics_file = _write_graphics_file(tmp_path, "Panel.g", "0 +MissingPanel")
    (tmp_path / "Panel.s").write_text(VALID_SINGLE_FILE, encoding="utf-8")
    base_picture = BasePicture(
        header=ModuleHeader(name="Panel", invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0)),
        name="Panel",
        moduledef=ModuleDef(graph_objects=[GraphObject("CompositeObject")]),
    )

    monkeypatch.setattr("sattlint.engine._load_source_text", lambda _path: VALID_SINGLE_FILE)
    monkeypatch.setattr("sattlint.engine.parser_core_parse_source_text", lambda *args, **kwargs: base_picture)
    monkeypatch.setattr("sattlint.engine.validate_transformed_basepicture", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        "sattlint.engine.validate_graphics_file",
        lambda _path: SimpleNamespace(errors=[], warnings=[], picture_display_records=[object()]),
    )
    monkeypatch.setattr(
        "sattlint.engine.correlate_picture_display_records",
        lambda current_bp, records: (object(),),
    )
    monkeypatch.setattr(
        "sattlint.engine._picture_display_path_warnings",
        lambda current_bp, occurrences: (ValidationNotice(message="could not be resolved"),),
    )

    result = validate_single_file_syntax(graphics_file)

    assert result.ok is True
    assert any("could not be resolved" in warning for warning in result.warnings)
