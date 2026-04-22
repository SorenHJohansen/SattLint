from pathlib import Path

from lsprotocol.types import DiagnosticSeverity

from sattlint import app
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


def test_validate_graphics_text_warns_for_unverified_scr_asset(tmp_path):
    file_path = _write_graphics_file(tmp_path, "Panel.g", "0 scr:missing_asset.wmf")

    result = validate_graphics_text(file_path.read_text(encoding="utf-8"), file_path)

    assert result.errors == ()
    assert len(result.warnings) == 1
    assert "could not be verified" in result.warnings[0].message


def test_validate_single_file_syntax_reports_graphics_error_for_empty_scr_alias(tmp_path):
    file_path = _write_graphics_file(tmp_path, "BrokenPanel.g", "0 scr:")

    result = validate_single_file_syntax(file_path)

    assert result.ok is False
    assert result.stage == "graphics"
    assert "must include a file name after 'scr:'" in str(result.message)


def test_syntax_check_command_accepts_graphics_file_with_warning(tmp_path, capsys):
    file_path = _write_graphics_file(tmp_path, "Panel.g", "0 scr:missing_asset.wmf")

    exit_code = app.main(["syntax-check", str(file_path)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out.strip() == "OK"
    assert "PictureDisplay asset 'scr:missing_asset.wmf' could not be verified" in captured.err


def test_collect_syntax_diagnostics_returns_warning_for_graphics_asset(tmp_path):
    file_path = _write_graphics_file(tmp_path, "Panel.g", "0 scr:missing_asset.wmf")

    diagnostics = collect_syntax_diagnostics(
        file_path,
        file_path.read_text(encoding="utf-8"),
    )

    assert len(diagnostics) == 1
    assert diagnostics[0].severity == DiagnosticSeverity.Warning
    assert "could not be verified" in diagnostics[0].message


def test_resolve_graphics_companion_prefers_g_and_falls_back_to_y_in_draft_mode(tmp_path):
    source_file = _write_source_file(tmp_path, "Panel.s")
    fallback_file = _write_graphics_file(tmp_path, "Panel.y", "0 scr:missing_asset.wmf")

    assert resolve_graphics_companion_path(source_file, mode=CodeMode.DRAFT) == fallback_file

    preferred_file = _write_graphics_file(tmp_path, "Panel.g", "0 scr:missing_asset.wmf")

    assert resolve_graphics_companion_path(source_file, mode=CodeMode.DRAFT) == preferred_file


def test_validate_single_file_syntax_falls_back_to_y_when_g_is_missing(tmp_path):
    source_file = _write_source_file(tmp_path, "Panel.s")
    _write_graphics_file(tmp_path, "Panel.y", "0 scr:missing_asset.wmf")

    result = validate_single_file_syntax(source_file)

    assert result.ok is True
    assert result.warnings == (
        "PictureDisplay asset 'scr:missing_asset.wmf' could not be verified from this workspace",
    )


def test_validate_single_file_syntax_uses_y_when_mode_is_official(tmp_path):
    source_file = _write_source_file(tmp_path, "Panel.s")
    _write_graphics_file(tmp_path, "Panel.g", "0 scr:")
    _write_graphics_file(tmp_path, "Panel.y", "0 +L2+UnitControl+L1+L2+Panel")

    result = validate_single_file_syntax(source_file, mode=CodeMode.OFFICIAL)

    assert result.ok is True
    assert result.warnings == ()
