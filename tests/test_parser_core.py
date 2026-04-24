"""Tests for grammar coverage and parser-core behaviour (parse_source_text, source spans, flags, and identifier rules)."""

from pathlib import Path

import pytest
from lark.exceptions import UnexpectedCharacters

from sattline_parser import api as parser_api
from sattline_parser import parse_source_text as parser_core_parse_source_text
from sattline_parser import strip_sl_comments
from sattlint import constants as const
from sattlint.engine import (
    create_sl_parser,
    parse_source_file,
)
from sattlint.models.ast_model import (
    BasePicture,
    ModuleTypeInstance,
)
from sattlint.transformer.sl_transformer import SLTransformer


def _parse_to_basepicture(text: str):
    parser = create_sl_parser()
    tree = parser.parse(strip_sl_comments(text))
    return SLTransformer().transform(tree)


def _repo_path(*parts: str) -> Path:
    return Path(__file__).resolve().parents[1].joinpath(*parts)


def test_ternary_if_has_lowest_precedence():
    code = """
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
    bp = _parse_to_basepicture(code)
    stmt = bp.modulecode.equations[0].code[0]
    assert stmt[0] == const.KEY_ASSIGN

    expr = stmt[2]
    assert expr[0] == const.KEY_TERNARY

    else_expr = expr[2]
    assert else_expr[0] == const.KEY_ADD
    assert else_expr[1][const.KEY_VAR_NAME].casefold() == "c"
    assert else_expr[2][0][0] == "+"
    assert else_expr[2][0][1][const.KEY_VAR_NAME].casefold() == "d"


def test_quoted_identifier_length_is_limited_to_20_chars():
    long_name = "'QuotedIdentifierLength21'"  # 25 chars without quotes
    code = f"""
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    {long_name}: integer := 0;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
        {long_name} = 1;
ENDDEF (*BasePicture*);
"""
    parser = create_sl_parser()
    with pytest.raises(UnexpectedCharacters):
        parser.parse(strip_sl_comments(code))


def test_parse_source_file_accepts_valid_file(tmp_path):
    code = """
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
    source_file = tmp_path / "ValidProgram.s"
    source_file.write_text(code, encoding="utf-8")

    bp = parse_source_file(source_file)

    assert bp.name == "BasePicture"


def test_parser_core_preserves_invocation_argument_flags():
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0 IgnoreMaxModule) : MODULEDEFINITION DateCode_ 1
SUBMODULES
    Child Invocation (0.0,0.0,0.0,1.0,1.0 LayerModule) : ChildType;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ENDDEF (*BasePicture*);
"""

    bp = parser_core_parse_source_text(code)

    assert bp.header.invocation_arguments == ("IgnoreMaxModule",)
    assert len(bp.submodules) == 1
    child = bp.submodules[0]
    assert isinstance(child, ModuleTypeInstance)
    assert child.header.invocation_arguments == ("LayerModule",)


def test_parser_core_reuses_default_parser(monkeypatch):
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    A: integer := 0;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
        A = A + 1;
ENDDEF (*BasePicture*);
"""

    call_count = 0
    real_create_parser = parser_api.create_parser
    parser_api._default_parser.cache_clear()

    def counting_create_parser():
        nonlocal call_count
        call_count += 1
        return real_create_parser()

    monkeypatch.setattr(parser_api, "create_parser", counting_create_parser)

    parser_api.parse_source_text(code)
    parser_api.parse_source_text(code)

    assert call_count == 1
    parser_api._default_parser.cache_clear()


def test_create_parser_uses_regex_and_disk_cache(monkeypatch, tmp_path):
    captured: dict[str, object] = {}
    cache_dir = tmp_path / "lark-cache"

    class DummyLark:
        def __init__(self, grammar, **options):
            captured["grammar"] = grammar
            captured["options"] = options

    monkeypatch.setattr(parser_api, "Lark", DummyLark)
    monkeypatch.setattr(parser_api, "_PARSER_CACHE_DIR", cache_dir)
    parser = parser_api.create_parser()

    assert isinstance(parser, DummyLark)
    options = captured["options"]
    assert isinstance(options, dict)
    assert options["regex"] is True
    assert options["cache_grammar"] is True
    assert Path(options["cache"]).parent == cache_dir
    assert options["parser"] == "lalr"


def test_parser_core_strict_mode_compiles_cleanly():
    parser = parser_api.create_parser(strict=True)

    assert parser is not None


def test_parser_core_accepts_outline_colour_assignment_invar_tail():
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    WidthSource: integer := 0;
    FormatSource: integer := 0;
    ColourSource: integer := 0;
ModuleDef
    ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
    GraphObjects :
        TextObject ( 0.0 , 0.0 ) ( 1.0 , 1.0 )
            "Value" VarName Width_ = 5 : InVar_ "WidthSource"
            Format_String_ = "" : InVar_ "FormatSource"
            OutlineColour : Colour0 = 5 : InVar_ "ColourSource"
ENDDEF (*BasePicture*);
"""

    bp = parser_core_parse_source_text(code)

    assert isinstance(bp, BasePicture)
    assert bp.moduledef is not None


def test_parser_core_accepts_clipping_bounds_and_interact_tail_sequences():
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
ModuleDef
    ClippingBounds = ( -1.0 , -3.12 : InVar_ "PanelResize" ClippingBounds = -2.33 -3.12 0.0 : InVar_ 0.0 100.0 : InVar_ 1.0 ) ( 1.0 , 0.22 )
    InteractObjects :
        TextBox_ ( 0.02 , 1.165 ) ( 0.48 , 1.245 )
            Real_Value
            "" : InVar_ LitString "+L2" 0
            Variable = 0.0 : OutVar_ "Plant.Real1"
            OpMin = 0.0 : InVar_ -1.0E+10
            OpMax = 100.0 : InVar_ 1.0E+10
            Event_Text_ = "" : InVar_ LitString "Real1"
            Event_Severity_ = 0 : InVar_ "Severity"
            LeftAligned Abs_ Decimal_
ENDDEF (*BasePicture*);
"""

    bp = parser_core_parse_source_text(code)

    assert isinstance(bp, BasePicture)
    assert bp.moduledef is not None
    assert bp.moduledef.interact_objects is not None
    assert len(bp.moduledef.interact_objects) == 1


def test_parser_core_accepts_interact_flag_plus_textobject_assignment():
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
ModuleDef
    ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
    InteractObjects :
        ComBut_ ( 0.0 , 0.0 ) ( 1.0 , 1.0 )
            Abs_ TextObject = "" : InVar_ LitString "Start Sim"
ENDDEF (*BasePicture*);
"""

    bp = parser_core_parse_source_text(code)

    assert isinstance(bp, BasePicture)
    assert bp.moduledef is not None
    assert bp.moduledef.interact_objects is not None
    assert len(bp.moduledef.interact_objects) == 1


def test_parser_core_accepts_combutproc_mixed_plain_and_tailed_args():
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
ModuleDef
    ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
    InteractObjects :
        ComButProc_ ( 0.0 , 0.0 ) ( 1.0 , 1.0 )
            ToggleWindow
            "" : InVar_ LitString "-+GainPanel" "" : InVar_ LitString "Calibration"
            False : InVar_ True 0.0 0.0 0.0 : InVar_ 0.23 0.0 False 0 0 False 0
            Variable = 0.0
ENDDEF (*BasePicture*);
"""

    bp = parser_core_parse_source_text(code)

    assert isinstance(bp, BasePicture)
    assert bp.moduledef is not None
    assert bp.moduledef.interact_objects is not None
    assert len(bp.moduledef.interact_objects) == 1


def test_parser_core_parse_source_text_accepts_valid_source():
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    A: integer := 0;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
        A = A + 1;
ENDDEF (*BasePicture*);
"""

    bp = parser_core_parse_source_text(code)

    assert isinstance(bp, BasePicture)
    assert bp.name == "BasePicture"


def test_parser_core_accepts_combining_mark_identifier():
    identifier = "Cafe\u0301"
    code = f"""
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    {identifier}: integer := 0;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
        {identifier} = {identifier} + 1;
ENDDEF (*BasePicture*);
"""

    bp = parser_core_parse_source_text(code)

    assert bp.localvariables[0].name == identifier


def test_parser_core_sets_sequence_control_and_timer_flags():
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    SEQUENCE MainSeq (SeqControl, SeqTimer) COORD 0.0, 0.0 OBJSIZE 1.0, 1.0
        SEQINITSTEP Start
        SEQTRANSITION Tr1 WAIT_FOR False
    ENDSEQUENCE
ENDDEF (*BasePicture*);
"""

    bp = parser_core_parse_source_text(code)

    assert bp.modulecode is not None
    assert bp.modulecode.sequences is not None
    seq = bp.modulecode.sequences[0]
    assert seq.seqcontrol is True
    assert seq.seqtimer is True


def test_parser_core_emits_declaration_and_reference_spans():
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    Counter: integer := 0;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
        Counter = Counter + 1;
ENDDEF (*BasePicture*);
""".strip()

    bp = parser_core_parse_source_text(code)
    declared = bp.localvariables[0]
    assert bp.modulecode is not None
    assert bp.modulecode.equations is not None
    assignment = bp.modulecode.equations[0].code[0]
    target = assignment[1]
    value_ref = assignment[2][1]

    assert declared.declaration_span is not None
    assert declared.declaration_span.line == 6
    assert declared.declaration_span.column == 5
    assert bp.header.declaration_span is not None
    assert bp.header.declaration_span.line == 4
    assert target["span"].line == 11
    assert target["span"].column == 9
    assert value_ref["span"].line == 11
    assert value_ref["span"].column == 19


def test_parser_core_preserves_invar_tails_in_invoke_coords_and_clipping_bounds():
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0 : InVar_ "PosX",0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    PosX: integer := 0;
    PanelResize: integer := 0;
ModuleDef
    ClippingBounds = ( -1.0 , -1.0 : InVar_ "PanelResize" ) ( 1.0 , 1.0 )
ENDDEF (*BasePicture*);
"""

    bp = parser_core_parse_source_text(code)

    assert bp.header.invoke_coord_tails == ["PosX"]
    assert bp.moduledef is not None
    assert bp.moduledef.properties[const.KEY_TAILS] == ["PanelResize"]

