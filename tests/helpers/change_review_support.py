"""Shared fixtures and helpers for Change Review tests."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import cast

from sattlint.change_review import VersionSnapshot, load_version_snapshot
from sattlint.config import DEFAULT_CONFIG
from sattlint.config.types import ConfigDict

OFFICIAL_PROGRAM = """\
"Syntax version 2.23, date: 2026-04-20-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-04-20-12:00:00.000, name: Demo"

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

LOCALVARIABLES
   ValveOpen: boolean := False;
   Flow: integer := 0;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
   EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      Flow = 0;
      ValveOpen = Flow > 0;

ENDDEF (*BasePicture*);
"""

DRAFT_PROGRAM = """\
"Syntax version 2.23, date: 2026-04-20-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-04-20-12:00:00.000, name: Demo"

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

LOCALVARIABLES
   ValveOpen: boolean := False;
   Flow: integer := 0;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
   EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      Flow = 0;
      ValveOpen = Flow > 5;

ENDDEF (*BasePicture*);
"""

FUNCTION_BLOCK_OFFICIAL = """\
"Syntax version 2.23, date: 2026-06-19-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-06-19-12:00:00.000, name: Demo"

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

TYPEDEFINITIONS
   PumpType = MODULEDEFINITION DateCode_ 1
   MODULEPARAMETERS
      Speed: real;
   LOCALVARIABLES
      Running: boolean  := False;
   ModuleDef
   ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
   ModuleCode
   EQUATIONBLOCK Eq COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      Running = Speed > 0.0;
   ENDDEF (*PumpType*);

LOCALVARIABLES
   SpeedRef: real  := 50.0;
   StartCmd: boolean := False;
   Status: integer := 0;

SUBMODULES
   Pump Invocation
      ( 0.0 , 0.0 , 0.0 , 0.5 , 0.5
       ) : PumpType (
      Speed => SpeedRef);

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )

ENDDEF (*BasePicture*);
"""

FUNCTION_BLOCK_DRAFT = FUNCTION_BLOCK_OFFICIAL.replace("Running = Speed > 0.0;", "Running = Speed > 5.0;")

CONNECTION_PROGRAM = """\
"Syntax version 2.23, date: 2026-06-19-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-06-19-12:00:00.000, name: Demo"

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

TYPEDEFINITIONS
   ValveType = MODULEDEFINITION DateCode_ 1
   MODULEPARAMETERS
      Open: boolean;
   LOCALVARIABLES
      Opening: boolean := False;
   ModuleDef
   ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
   ModuleCode
   EQUATIONBLOCK Ctrl COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      Opening = Open;
   ENDDEF (*ValveType*);

LOCALVARIABLES
   StartCmd: boolean := False;
   AltCmd: boolean := False;

SUBMODULES
   FillValve Invocation
      ( 0.0 , 0.0 , 0.0 , 0.5 , 0.5
       ) : ValveType (
      Open => StartCmd);

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ENDDEF (*BasePicture*);
"""

CONNECTION_PROGRAM_ALT_SOURCE = CONNECTION_PROGRAM.replace("Open => StartCmd", "Open => AltCmd")

IF_PROGRAM = OFFICIAL_PROGRAM.replace(
    "      Flow = 0;\n      ValveOpen = Flow > 0;",
    "      IF Flow > 0 THEN\n         ValveOpen = True;\n      ENDIF;",
)

IF_PROGRAM_DRAFT = IF_PROGRAM.replace("ValveOpen = True;", "ValveOpen = False;")

ALIGN_PROGRAM = """\
"Syntax version 2.23, date: 2026-06-19-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-06-19-12:00:00.000, name: Demo"

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

LOCALVARIABLES
   A: integer := 0;
   B: integer := 0;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
   EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      A = 1;
      B = 2;
      A = A + 1;
ENDDEF (*BasePicture*);
"""

ALIGN_PROGRAM_REORDERED = ALIGN_PROGRAM.replace(
    "      A = 1;\n      B = 2;\n      A = A + 1;",
    "      B = 9;\n      A = 8;\n      A = A + 2;",
)

ALIGN_PROGRAM_WITH_INSERTION = ALIGN_PROGRAM.replace(
    "      A = 1;\n      B = 2;",
    "      B = 0;\n      A = 1;\n      B = 2;",
)

INSTANCE_DEPENDENCY_PROGRAM = """\
"Syntax version 2.23, date: 2026-06-19-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-06-19-12:00:00.000, name: Demo"

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

TYPEDEFINITIONS
   CalcType = MODULEDEFINITION DateCode_ 1
   LOCALVARIABLES
      Factor: real := 1.0;
      Result: real := 0.0;
   ModuleDef
   ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
   ModuleCode
   EQUATIONBLOCK Calc COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      Result = 0.0;
   ENDDEF (*CalcType*);

LOCALVARIABLES
   Sink: real := 0.0;

SUBMODULES
   A Invocation
      ( 0.0 , 0.0 , 0.0 , 0.5 , 0.5
       ) : CalcType;
   B Invocation
      ( 0.5 , 0.0 , 0.0 , 0.5 , 0.5
       ) : CalcType;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ENDDEF (*BasePicture*);
"""

INSTANCE_DEPENDENCY_PROGRAM_DRAFT = INSTANCE_DEPENDENCY_PROGRAM.replace(
    "      Result = 0.0;",
    "      Result = Factor;",
)

RECORD_FIELD_PROGRAM = """\
"Syntax version 2.23, date: 2026-06-19-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-06-19-12:00:00.000, name: Demo"

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

TYPEDEFINITIONS
   RecType = RECORD DateCode_ 1
      Flag "state flag": boolean OpSave := True;
   ENDDEF
TYPEDEFINITIONS
   HolderType = MODULEDEFINITION DateCode_ 2
   LOCALVARIABLES
      Rec: RecType;
   ModuleDef
   ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
   ModuleCode
   EQUATIONBLOCK Eq COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      Rec.Flag = True;
   ENDDEF (*HolderType*);

SUBMODULES
   Holder Invocation
      ( 0.0 , 0.0 , 0.0 , 0.5 , 0.5
       ) : HolderType;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ENDDEF (*BasePicture*);
"""

RECORD_FIELD_PROGRAM_DRAFT = RECORD_FIELD_PROGRAM.replace(
    'Flag "state flag": boolean OpSave := True;',
    'Flag "state flag": boolean;',
)

FRAME_PROGRAM = """\
"Syntax version 2.23, date: 2026-06-19-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-06-19-12:00:00.000, name: Demo"

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

LOCALVARIABLES
   Flow: integer := 0;

SUBMODULES
   Frame1 Invocation
      ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
       ) : MODULEDEFINITION DateCode_ 2 ( Frame_Module )
      LOCALVARIABLES
         Local: integer := 0;
      ModuleDef
      ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
      ModuleCode
         EQUATIONBLOCK FCalc COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
            Local = Flow + 1;
      ENDDEF (*Frame1*);

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ENDDEF (*BasePicture*);
"""

FRAME_PROGRAM_DRAFT = FRAME_PROGRAM.replace("Local = Flow + 1;", "Local = Flow + 2;")

SEQUENCE_OFFICIAL = """\
"Syntax version 2.23, date: 2026-06-19-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-06-19-12:00:00.000, name: Demo"

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

LOCALVARIABLES
   StartCmd: boolean := False;
   Status: integer := 0;
   DrainCmd: boolean := False;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
   SEQUENCE MainSeq (SeqControl, SeqTimer) COORD 0.0, 0.0 OBJSIZE 1.0, 1.0
      SEQINITSTEP Idle
         ENTERCODE
            Status = 0;
      SEQTRANSITION TrGo WAIT_FOR StartCmd
      SEQSTEP Fill
         ENTERCODE
            Status = 1;
   ENDSEQUENCE
ENDDEF (*BasePicture*);
"""

SEQUENCE_DRAFT_ADDED_STEP = SEQUENCE_OFFICIAL.replace(
    "            Status = 1;\n   ENDSEQUENCE",
    "            Status = 1;\n      SEQTRANSITION TrDrain WAIT_FOR True\n      SEQSTEP Drain\n         ENTERCODE\n            DrainCmd = True;\n   ENDSEQUENCE",
)

SEQUENCE_DRAFT_CHANGED_TRANSITION = SEQUENCE_OFFICIAL.replace(
    "SEQTRANSITION TrGo WAIT_FOR StartCmd",
    "SEQTRANSITION TrGo WAIT_FOR NOT StartCmd",
)

SEQUENCE_WITH_LITERAL_TRANSITION = SEQUENCE_OFFICIAL.replace(
    "            Status = 1;\n   ENDSEQUENCE",
    "            Status = 1;\n      SEQTRANSITION TrFalse WAIT_FOR False\n   ENDSEQUENCE",
)

SEQUENCE_WITH_CHANGED_LITERAL_TRANSITION = SEQUENCE_WITH_LITERAL_TRANSITION.replace(
    "SEQTRANSITION TrFalse WAIT_FOR False",
    "SEQTRANSITION TrFalse WAIT_FOR True",
)

FORMATTED_PROGRAM = """\
"Syntax version 2.23, date: 2026-04-20-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-04-20-12:00:00.000, name: Demo"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    ValveOpen: boolean := False;
    Flow: integer := 0;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
        Flow = 0;
        ValveOpen = Flow > 0;
ENDDEF (*BasePicture*);
"""


def write_project(
    program_dir: Path,
    *,
    name: str,
    official_text: str,
    draft_text: str,
) -> None:
    program_dir.mkdir(parents=True, exist_ok=True)
    (program_dir / f"{name}.x").write_text(official_text, encoding="utf-8")
    (program_dir / f"{name}.s").write_text(draft_text, encoding="utf-8")


def build_cfg(
    tmp_path: Path,
    *,
    program_dir: Path | None = None,
    target_name: str = "Demo",
    review_output_dir: str = "",
) -> ConfigDict:
    selected_program_dir = program_dir
    if selected_program_dir is None:
        selected_program_dir = tmp_path / "programs"
        write_project(
            selected_program_dir,
            name=target_name,
            official_text=OFFICIAL_PROGRAM,
            draft_text=DRAFT_PROGRAM,
        )
    for sub in ("abb", "icf"):
        (tmp_path / sub).mkdir(parents=True, exist_ok=True)
    cfg = deepcopy(DEFAULT_CONFIG)
    cfg.update(
        {
            "program_dir": str(selected_program_dir),
            "ABB_lib_dir": str(tmp_path / "abb"),
            "icf_dir": str(tmp_path / "icf"),
            "other_lib_dirs": [],
            "analyzed_programs_and_libraries": [target_name],
            "mode": "draft",
            "debug": False,
        }
    )
    if review_output_dir:
        cast(dict[str, object], cfg["review"])["output_dir"] = review_output_dir
    return cast(ConfigDict, cfg)


def load_pair(
    tmp_path: Path,
    official_text: str,
    draft_text: str,
    *,
    name: str = "Demo",
) -> tuple[VersionSnapshot, VersionSnapshot, ConfigDict]:
    program_dir = tmp_path / "programs"
    write_project(program_dir, name=name, official_text=official_text, draft_text=draft_text)
    cfg = build_cfg(tmp_path, program_dir=program_dir, target_name=name)
    official = load_version_snapshot(cfg, name, mode="official")
    draft = load_version_snapshot(cfg, name, mode="draft")
    return official, draft, cfg
