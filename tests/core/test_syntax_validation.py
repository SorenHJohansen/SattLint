from pathlib import Path

from sattline_parser import parse_source_text

from sattlint.core.syntax import validate_single_file_syntax
from sattlint.graphics.validation import GraphicsValidationResult
from sattlint.validation.policy import validate_basepicture_strict
from sattlint.validation.shared import StructuralValidationError

_VALID_SOURCE = """\"SyntaxVersion\"
\"OriginalFileDate\"
\"ProgramDate\"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    A: integer := 0;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
        A = Missing;
ENDDEF (*BasePicture*);
"""


def _write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="cp1252")
    return path


def test_syntax_check_reports_the_first_validation_error_with_its_position(tmp_path: Path) -> None:
    code_path = _write(tmp_path / "Program.s", _VALID_SOURCE)

    result = validate_single_file_syntax(code_path)

    assert result.ok is False
    assert result.stage == "validation"
    assert result.message == "Reference to undefined variable 'Missing'"
    assert (result.line, result.column) == (11, 13)


def test_strict_validation_error_carries_the_diagnostic_length() -> None:
    basepic = parse_source_text(_VALID_SOURCE)

    try:
        validate_basepicture_strict(basepic)
    except StructuralValidationError as exc:
        assert (exc.line, exc.column, exc.length) == (11, 13, len("Missing"))
    else:
        raise AssertionError("expected a structural validation error")


def test_syntax_check_reports_graphics_structural_errors(tmp_path: Path) -> None:
    code_path = _write(tmp_path / "Program.s", _VALID_SOURCE.replace("A = Missing;", "A = A + 1;"))
    _write(tmp_path / "Program.g", "5\nalpha\n")

    result = validate_single_file_syntax(code_path)

    assert result.ok is False
    assert result.stage == "graphics"
    assert result.message == "Unterminated graphics record; expected trailing '0' line"
    assert (result.line, result.column) == (1, 1)


def test_syntax_check_accepts_a_valid_code_and_graphics_pair(tmp_path: Path) -> None:
    _write(tmp_path / "Program.s", _VALID_SOURCE.replace("A = Missing;", "A = A + 1;"))
    _write(tmp_path / "Program.g", '"Syntax version 2.23"\nNone True\n')

    result = validate_single_file_syntax(tmp_path / "Program.s")

    assert result.ok is True
    assert result.stage == "ok"


def test_a_paired_body_that_cannot_be_parsed_reports_the_skipped_path_checks(tmp_path: Path) -> None:
    graphics_path = _write(tmp_path / "Program.g", '"Syntax version 2.23"\nNone True\n')
    paired_body = _write(tmp_path / "Program.s", "not a SattLine body")

    result = validate_single_file_syntax(
        graphics_path,
        validate_graphics_file_fn=lambda _path: GraphicsValidationResult(),
        graphics_source_context_path_fn=lambda _path: paired_body,
        load_picture_display_source_context_fn=lambda _path: None,
    )

    assert result.ok is True
    assert any("PictureDisplay path checks were skipped" in warning for warning in result.warnings)
    assert any("Program.s" in warning for warning in result.warnings)


def test_comment_before_a_code_block_is_rejected_by_the_parser(tmp_path: Path) -> None:
    source = _VALID_SOURCE.replace(
        "    EQUATIONBLOCK Main",
        "    (* freestanding comment *)\n    EQUATIONBLOCK Main",
    )
    code_path = _write(tmp_path / "Program.s", source)

    result = validate_single_file_syntax(code_path)

    assert result.ok is False
    assert result.stage == "parse"


_SFC_SOURCE = """\"Syntax version 2.23, date: 2026-10-26-12:00:00.000 N\"
\"Original file date: ---\"
\"Program date: 2026-10-26-12:00:00.000, name: SfcNames\"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    Flag: boolean := False;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
{body}ENDDEF (*BasePicture*);
"""


def _sfc_sequence(body: str) -> str:
    return "   SEQUENCE Demo COORD 0.0, 0.0 OBJSIZE 1.0, 1.0\n" + body + "   ENDSEQUENCE\n"


def test_sequence_wrapper_may_reuse_a_name_from_its_own_body(tmp_path: Path) -> None:
    body = _sfc_sequence(
        "      SEQSTEP S1\n"
        "      SUBSEQTRANSITION Pak_Udpak\n"
        "         SEQTRANSITION Pak_Udpak WAIT_FOR Flag\n"
        "      ENDSUBSEQTRANSITION\n"
        "      SEQSTEP S2\n"
        "      SEQTRANSITION T2 WAIT_FOR Flag\n"
    )
    code_path = _write(tmp_path / "SfcNames.s", _SFC_SOURCE.format(body=body))

    result = validate_single_file_syntax(code_path)

    assert result.ok is True
    assert result.stage == "ok"


def test_sibling_steps_and_transitions_must_still_have_unique_names(tmp_path: Path) -> None:
    body = _sfc_sequence(
        "      SEQSTEP S1\n"
        "      SEQTRANSITION T1 WAIT_FOR Flag\n"
        "      SEQSTEP S2\n"
        "      SEQTRANSITION T1 WAIT_FOR Flag\n"
    )
    code_path = _write(tmp_path / "SfcNames.s", _SFC_SOURCE.format(body=body))

    result = validate_single_file_syntax(code_path)

    assert result.ok is False
    assert result.stage == "validation"
    assert "T1" in (result.message or "")
