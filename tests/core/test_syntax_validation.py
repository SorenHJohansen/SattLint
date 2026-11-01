from pathlib import Path

from sattline_parser import parse_source_text

from sattlint.core.syntax import validate_single_file_syntax
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
