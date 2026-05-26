from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from sattlint import app

MINI_PROJECT_SOURCE = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    A: integer := 0;
    B: integer := 1;
    C: integer := 2;
    D: integer := 3;
    X: integer := 0;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
        X = IF A > 0 THEN B ELSE C + D ENDIF;
ENDDEF (*BasePicture*);
"""


def build_mini_project_context(
    tmp_path: Path,
    *,
    target_name: str = "TargetA",
    source_text: str = MINI_PROJECT_SOURCE,
) -> dict[str, Any]:
    program_dir = tmp_path / "programs"
    abb_dir = tmp_path / "abb"
    icf_dir = tmp_path / "icf"
    program_dir.mkdir(parents=True, exist_ok=True)
    abb_dir.mkdir(parents=True, exist_ok=True)
    icf_dir.mkdir(parents=True, exist_ok=True)

    target_file = program_dir / f"{target_name}.s"
    target_file.write_text(source_text, encoding="utf-8")

    cfg = deepcopy(app.DEFAULT_CONFIG)
    cfg.update(
        {
            "program_dir": str(program_dir),
            "ABB_lib_dir": str(abb_dir),
            "icf_dir": str(icf_dir),
            "other_lib_dirs": [],
            "analyzed_programs_and_libraries": [target_name],
            "mode": "draft",
            "scan_root_only": True,
            "debug": False,
        }
    )

    return {
        "cfg": cfg,
        "target_name": target_name,
        "target_file": target_file,
        "program_dir": program_dir,
        "abb_dir": abb_dir,
        "icf_dir": icf_dir,
    }
