from __future__ import annotations

import logging
from pathlib import Path

import pytest

from sattlint.core import semantic as semantic_core


def _source_text() -> str:
    return """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    Counter: integer := 0;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ENDDEF (*BasePicture*);
""".strip()


def test_load_source_snapshot_routes_parser_debug_to_logger_not_stdout(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    capsys: pytest.CaptureFixture[str],
) -> None:
    entry_file = tmp_path / "Program" / "Main.s"

    with caplog.at_level(logging.DEBUG, logger="SattLint"):
        semantic_core.load_source_snapshot(
            entry_file,
            _source_text(),
            workspace_root=tmp_path,
            collect_variable_diagnostics=False,
            debug=True,
        )

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""
    assert "Semantic snapshot parser: Parse OK, transforming with SLTransformer" in caplog.messages
    assert "Semantic snapshot parser: Transform result type: BasePicture" in caplog.messages
