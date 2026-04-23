"""Parser-level tests for SattLine grammar coverage."""

from pathlib import Path

import pytest
from lark.exceptions import UnexpectedCharacters

from sattline_parser import api as parser_api
from sattline_parser import parse_source_text as parser_core_parse_source_text
from sattline_parser import strip_sl_comments
from sattlint import constants as const
from sattlint.engine import (
    StructuralValidationError,
    _load_source_text,
    create_sl_parser,
    parse_source_file,
    validate_single_file_syntax,
    validate_transformed_basepicture,
)
from sattlint.models.ast_model import (
    BasePicture,
    ModuleHeader,
    ModuleTypeInstance,
    Simple_DataType,
    Variable,
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


def test_validate_single_file_syntax_rejects_comment_outside_equation_or_sequence(tmp_path):
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    TransferRequest: boolean := False;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    (*
        Keep output publishing separate from guard evaluation.
        The regression steps update latched request variables, and this block
        republishes them every scan so the TransferPanel one-shot signals are
        continuously reasserted while a step needs them.
    *)
    EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
        TransferRequest = False;
ENDDEF (*BasePicture*);
"""
    source_file = tmp_path / "CommentOutsideEquationOrSequence.s"
    source_file.write_text(code, encoding="utf-8")

    result = validate_single_file_syntax(source_file)

    assert result.ok is False
    assert result.stage == "validation"
    assert result.line == 11
    assert result.column == 5
    assert result.message is not None
    assert "only allowed inside EQUATIONBLOCK or SEQUENCE/OPENSEQUENCE blocks" in result.message


def test_validate_single_file_syntax_allows_comment_inside_equation_block(tmp_path):
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
        (* This comment is allowed inside an equation block. *)
        Counter = Counter + 1;
ENDDEF (*BasePicture*);
"""
    source_file = tmp_path / "CommentInsideEquation.s"
    source_file.write_text(code, encoding="utf-8")

    result = validate_single_file_syntax(source_file)

    assert result.ok is True
    assert result.stage == "ok"


def test_validate_single_file_syntax_allows_comment_inside_sequence_block(tmp_path):
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    OPENSEQUENCE MainSequence (SeqControl) COORD 0.0, 0.2 OBJSIZE 2.0, 1.68
        (* This comment is allowed inside a sequence block. *)
        SEQINITSTEP InitSim
        SEQTRANSITION Start WAIT_FOR True
        SEQSTEP Running
    ENDOPENSEQUENCE
ENDDEF (*BasePicture*);
"""
    source_file = tmp_path / "CommentInsideSequence.s"
    source_file.write_text(code, encoding="utf-8")

    result = validate_single_file_syntax(source_file)

    assert result.ok is True
    assert result.stage == "ok"


def test_validate_single_file_syntax_allows_top_level_comment_outside_modulecode(tmp_path):
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
(*
    1998-11-20 08:11 FDH
    Library created
*)
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ENDDEF (*BasePicture*);
"""
    source_file = tmp_path / "TopLevelCommentAllowed.s"
    source_file.write_text(code, encoding="utf-8")

    result = validate_single_file_syntax(source_file)

    assert result.ok is True
    assert result.stage == "ok"


def test_validate_single_file_syntax_reports_location(tmp_path):
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    Counter: integer := 0
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
        Counter = Counter + 1;
ENDDEF (*BasePicture*);
"""
    source_file = tmp_path / "InvalidProgram.s"
    source_file.write_text(code, encoding="utf-8")

    result = validate_single_file_syntax(source_file)

    assert result.ok is False
    assert result.stage == "parse"
    assert result.line is not None
    assert result.message
    assert "Expected one of:" in result.message
    assert "^" in result.message


def test_validate_single_file_syntax_rejects_missing_transition(tmp_path):
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    OPENSEQUENCE MainSimulation (SeqControl) COORD 0.0, 0.2 OBJSIZE 2.0, 1.68
        SEQINITSTEP InitSim
        SEQTRANSITION StartSimulation WAIT_FOR Sim.Start
        SEQSTEP StopBatchIfActive
            ENTERCODE
                BatchControl.Sim.ActivateMES_Stop = True;
        SEQSTEP StartBatch
            ENTERCODE
                BatchControl.Sim.ActivateMES_Start = True;
    ENDOPENSEQUENCE
ENDDEF (*BasePicture*);
"""
    source_file = tmp_path / "MissingTransition.s"
    source_file.write_text(code, encoding="utf-8")

    result = validate_single_file_syntax(source_file)

    assert result.ok is False
    assert result.stage == "validation"
    assert result.message is not None
    assert "without an intervening transition" in result.message


def test_validate_single_file_syntax_warns_for_legacy_sequence_without_leading_initstep(tmp_path):
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    SEQUENCE DeleteListContent COORD 0.0, 0.0 OBJSIZE 1.0, 1.0
        SEQSTEP PutArray
        SEQTRANSITION WAIT_FOR True
        SEQSTEP ExtraScan
        ALTERNATIVESEQ
            SEQTRANSITION WAIT_FOR DeleteLineNumber <= ArrayLength
        ALTERNATIVEBRANCH
            SEQTRANSITION WAIT_FOR DeleteLineNumber > ArrayLength
            SEQINITSTEP standBy
            SEQTRANSITION WAIT_FOR DeleteListContent
        ENDALTERNATIVE
    ENDSEQUENCE
ENDDEF (*BasePicture*);
"""
    source_file = tmp_path / "LegacySequenceWarning.s"
    source_file.write_text(code, encoding="utf-8")

    result = validate_single_file_syntax(source_file)

    assert result.ok is True
    assert result.stage == "ok"
    assert any("must start with exactly one SEQINITSTEP" in warning for warning in result.warnings)
    assert any("outside the first position" in warning for warning in result.warnings)


def test_validate_transformed_basepicture_rejects_long_identifier():
    bp = BasePicture(
        header=ModuleHeader(name="BasePicture", invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0)),
        localvariables=[Variable(name="IdentifierLengthOver20", datatype=Simple_DataType.INTEGER)],
    )

    with pytest.raises(StructuralValidationError, match="exceeds 20 characters"):
        validate_transformed_basepicture(bp)


def test_validate_single_file_syntax_rejects_duplicate_variable_names(tmp_path):
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    PumpCmd: integer := 0;
    pumpcmd: integer := 1;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ENDDEF (*BasePicture*);
"""
    source_file = tmp_path / "DuplicateVars.s"
    source_file.write_text(code, encoding="utf-8")

    result = validate_single_file_syntax(source_file)

    assert result.ok is False
    assert result.stage == "validation"
    assert result.message is not None
    assert "duplicate variable names" in result.message


def test_validate_single_file_syntax_rejects_builtin_datatype_typo(tmp_path):
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    si: intege;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ENDDEF (*BasePicture*);
"""
    source_file = tmp_path / "DatatypeTypo.s"
    source_file.write_text(code, encoding="utf-8")

    result = validate_single_file_syntax(source_file)

    assert result.ok is False
    assert result.stage == "validation"
    assert result.line == 7
    assert result.message is not None
    assert "unknown datatype 'intege'" in result.message
    assert "did you mean 'integer'" in result.message


def test_validate_single_file_syntax_rejects_init_value_type_mismatch(tmp_path):
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    Counter: integer := "bad";
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ENDDEF (*BasePicture*);
"""
    source_file = tmp_path / "InitTypeMismatch.s"
    source_file.write_text(code, encoding="utf-8")

    result = validate_single_file_syntax(source_file)

    assert result.ok is False
    assert result.stage == "validation"
    assert result.line == 7
    assert result.message is not None
    assert "has init value 'bad'" in result.message
    assert "declared datatype is 'integer'" in result.message


def test_validate_single_file_syntax_accepts_duration_value_init_literals(tmp_path):
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    Dur5min: Duration OpSave := Duration_Value "0d0h5m0s0ms";
    DurMinus5min: Duration := Duration_Value "-0d0h5m0s0ms";
    Dur1Hour: Duration := "1h";
    Dur4Min: Duration := "4m";
    DurCombo: Duration := "7m6s123ms";
    DurFractionalSeconds: Duration := "5d5h3m6.5s";
    DurPlainSeconds: Duration := "12.345";
    DurZero: Duration := "0";
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ENDDEF (*BasePicture*);
"""
    source_file = tmp_path / "DurationInitOk.s"
    source_file.write_text(code, encoding="utf-8")

    result = validate_single_file_syntax(source_file)

    assert result.ok is True
    assert result.stage == "ok"


def test_validate_single_file_syntax_accepts_duration_shaped_string_init_for_string_datatype(tmp_path):
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    DurationText: String := "1h";
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ENDDEF (*BasePicture*);
"""
    source_file = tmp_path / "DurationStringValueOk.s"
    source_file.write_text(code, encoding="utf-8")

    result = validate_single_file_syntax(source_file)

    assert result.ok is True
    assert result.stage == "ok"


def test_validate_single_file_syntax_rejects_invalid_bare_duration_string(tmp_path):
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    DurBad: Duration := "bad";
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ENDDEF (*BasePicture*);
"""
    source_file = tmp_path / "DurationInitMissingKeyword.s"
    source_file.write_text(code, encoding="utf-8")

    result = validate_single_file_syntax(source_file)

    assert result.ok is False
    assert result.stage == "validation"
    assert result.line == 7
    assert result.message is not None
    assert "has init value 'bad'" in result.message
    assert "declared datatype is 'duration'" in result.message


def test_validate_single_file_syntax_rejects_invalid_duration_value_literal(tmp_path):
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    DurBad: Duration := Duration_Value "bad";
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ENDDEF (*BasePicture*);
"""
    source_file = tmp_path / "DurationInitInvalidKeywordLiteral.s"
    source_file.write_text(code, encoding="utf-8")

    result = validate_single_file_syntax(source_file)

    assert result.ok is False
    assert result.stage == "validation"
    assert result.line == 7
    assert result.message is not None
    assert "invalid duration literal 'bad'" in result.message


def test_validate_single_file_syntax_accepts_bare_time_init_literals(tmp_path):
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    StartTime: Time := "1984-01-01-00:00:00.000";
    StopTime: Time := "2099-01-01-00:00:00.000";
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ENDDEF (*BasePicture*);
"""
    source_file = tmp_path / "TimeInitOk.s"
    source_file.write_text(code, encoding="utf-8")

    result = validate_single_file_syntax(source_file)

    assert result.ok is True
    assert result.stage == "ok"


def test_validate_single_file_syntax_accepts_time_shaped_string_init_for_string_datatype(tmp_path):
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    TimeText: String := "1984-01-01-00:00:00.000";
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ENDDEF (*BasePicture*);
"""
    source_file = tmp_path / "TimeStringValueOk.s"
    source_file.write_text(code, encoding="utf-8")

    result = validate_single_file_syntax(source_file)

    assert result.ok is True
    assert result.stage == "ok"


def test_validate_single_file_syntax_rejects_invalid_bare_time_string(tmp_path):
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    BadTime: Time := "bad";
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ENDDEF (*BasePicture*);
"""
    source_file = tmp_path / "TimeInitInvalidBare.s"
    source_file.write_text(code, encoding="utf-8")

    result = validate_single_file_syntax(source_file)

    assert result.ok is False
    assert result.stage == "validation"
    assert result.line == 7
    assert result.message is not None
    assert "has init value 'bad'" in result.message
    assert "declared datatype is 'time'" in result.message


def test_validate_single_file_syntax_rejects_invalid_time_value_literal(tmp_path):
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    BadTime: Time := Time_Value "bad";
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ENDDEF (*BasePicture*);
"""
    source_file = tmp_path / "TimeInitInvalidKeywordLiteral.s"
    source_file.write_text(code, encoding="utf-8")

    result = validate_single_file_syntax(source_file)

    assert result.ok is False
    assert result.stage == "validation"
    assert result.line == 7
    assert result.message is not None
    assert "invalid time literal 'bad'" in result.message


def test_validate_single_file_syntax_rejects_const_write(tmp_path):
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    Limit: integer Const := 1;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
        Limit = 2;
ENDDEF (*BasePicture*);
"""
    source_file = tmp_path / "ConstWrite.s"
    source_file.write_text(code, encoding="utf-8")

    result = validate_single_file_syntax(source_file)

    assert result.ok is False
    assert result.stage == "validation"
    assert result.line == 12
    assert result.message is not None
    assert "writes to CONST variable 'Limit'" in result.message


def test_validate_single_file_syntax_rejects_duplicate_submodule_names(tmp_path):
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
SUBMODULES
    Child Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 2
    ModuleDef
    ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
    ENDDEF (*Child*);
    child Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 3
    ModuleDef
    ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
    ENDDEF (*child*);
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ENDDEF (*BasePicture*);
"""
    source_file = tmp_path / "DuplicateSubmodules.s"
    source_file.write_text(code, encoding="utf-8")

    result = validate_single_file_syntax(source_file)

    assert result.ok is False
    assert result.stage == "validation"
    assert result.message is not None
    assert "duplicate submodule names 'Child' and 'child'" in result.message


def test_validate_single_file_syntax_allows_moduletype_instance_reusing_inline_name(tmp_path):
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
TYPEDEFINITIONS
    ChildType = MODULEDEFINITION DateCode_ 2
    ModuleDef
    ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
    ENDDEF (*ChildType*);
SUBMODULES
    Child Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 3
    ModuleDef
    ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
    ENDDEF (*Child*);
    Child Invocation (0.0,0.0,0.0,1.0,1.0) : ChildType;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ENDDEF (*BasePicture*);
"""
    source_file = tmp_path / "RepeatedModuleTypeInvocationName.s"
    source_file.write_text(code, encoding="utf-8")

    result = validate_single_file_syntax(source_file)

    assert result.ok is True
    assert result.stage == "ok"


def test_validate_single_file_syntax_allows_distinct_moduletype_instances_with_same_type(tmp_path):
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
TYPEDEFINITIONS
    ChildType = MODULEDEFINITION DateCode_ 2
    ModuleDef
    ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
    ENDDEF (*ChildType*);
SUBMODULES
    ChildA Invocation (0.0,0.0,0.0,1.0,1.0) : ChildType;
    ChildB Invocation (0.0,0.0,0.0,1.0,1.0) : ChildType;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ENDDEF (*BasePicture*);
"""
    source_file = tmp_path / "DistinctModuleTypeInvocations.s"
    source_file.write_text(code, encoding="utf-8")

    result = validate_single_file_syntax(source_file)

    assert result.ok is True
    assert result.stage == "ok"


def test_validate_transformed_basepicture_workspace_mode_allows_external_style_datatypes():
    bp = BasePicture(
        header=ModuleHeader(name="BasePicture", invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0)),
        localvariables=[
            Variable(name="Wildcard", datatype="AnyType"),
            Variable(name="ExternalRef", datatype="DI_IOType"),
        ],
    )

    validate_transformed_basepicture(
        bp,
        allow_unresolved_external_datatypes=True,
    )


def test_validate_transformed_basepicture_workspace_mode_allows_duplicate_submodule_names():
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
SUBMODULES
    Child Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 2
    ModuleDef
    ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
    ENDDEF (*Child*);
    child Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 3
    ModuleDef
    ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
    ENDDEF (*child*);
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ENDDEF (*BasePicture*);
"""
    bp = _parse_to_basepicture(code)

    validate_transformed_basepicture(
        bp,
        enforce_unique_submodule_names=False,
    )


def test_validate_transformed_basepicture_workspace_mode_allows_mappings_to_parameterless_module():
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
TYPEDEFINITIONS
    ChildType = MODULEDEFINITION DateCode_ 2
    ModuleDef
    ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
    ENDDEF (*ChildType*);
SUBMODULES
    Child Invocation (0.0,0.0,0.0,1.0,1.0) : ChildType (
        Wrong => Missing
    );
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ENDDEF (*BasePicture*);
"""
    bp = _parse_to_basepicture(code)

    validate_transformed_basepicture(
        bp,
        allow_parameterless_module_mappings=True,
    )


def test_validate_transformed_basepicture_workspace_mode_still_rejects_builtin_typos():
    bp = BasePicture(
        header=ModuleHeader(name="BasePicture", invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0)),
        localvariables=[Variable(name="Broken", datatype="intege")],
    )

    with pytest.raises(StructuralValidationError, match="did you mean 'integer'"):
        validate_transformed_basepicture(
            bp,
            allow_unresolved_external_datatypes=True,
        )


def test_validate_transformed_basepicture_workspace_mode_ignores_unknown_parameter_target():
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
TYPEDEFINITIONS
    ChildType = MODULEDEFINITION DateCode_ 2
    MODULEPARAMETERS
        Value: integer;
    ModuleDef
    ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
    ENDDEF (*ChildType*);
SUBMODULES
    Child Invocation (0.0,0.0,0.0,1.0,1.0) : ChildType (
        Wrong => 1
    );
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ENDDEF (*BasePicture*);
"""
    bp = _parse_to_basepicture(code)

    validate_transformed_basepicture(
        bp,
    )


def test_validate_transformed_basepicture_workspace_mode_warns_incompatible_parameter_mapping():
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
TYPEDEFINITIONS
    ChildType = MODULEDEFINITION DateCode_ 2
    MODULEPARAMETERS
        Value: integer;
    ModuleDef
    ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
    ENDDEF (*ChildType*);
LOCALVARIABLES
    Flag: boolean := False;
SUBMODULES
    Child Invocation (0.0,0.0,0.0,1.0,1.0) : ChildType (
        Value => Flag
    );
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ENDDEF (*BasePicture*);
"""
    bp = _parse_to_basepicture(code)
    warnings: list[str] = []

    validate_transformed_basepicture(
        bp,
        warn_incompatible_parameter_mappings=True,
        warning_sink=warnings.append,
    )

    assert len(warnings) == 1
    assert "maps 'Flag' with datatype 'boolean' to parameter target 'Value' with datatype 'integer'" in warnings[0]


def test_validate_single_file_syntax_rejects_duplicate_parameter_mapping_targets(tmp_path):
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
TYPEDEFINITIONS
    ChildType = MODULEDEFINITION DateCode_ 2
    MODULEPARAMETERS
        Value: integer;
    ModuleDef
    ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
    ENDDEF (*ChildType*);
SUBMODULES
    Child Invocation (0.0,0.0,0.0,1.0,1.0) : ChildType (
        Value => 1,
        value => 2
    );
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ENDDEF (*BasePicture*);
"""
    source_file = tmp_path / "DuplicateParameterTargets.s"
    source_file.write_text(code, encoding="utf-8")

    result = validate_single_file_syntax(source_file)

    assert result.ok is False
    assert result.stage == "validation"
    assert result.message is not None
    assert "duplicate parameter mapping targets 'Value' and 'value'" in result.message


def test_validate_single_file_syntax_allows_unknown_parameter_mapping_target(tmp_path):
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
TYPEDEFINITIONS
    ChildType = MODULEDEFINITION DateCode_ 2
    MODULEPARAMETERS
        Value: integer;
    ModuleDef
    ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
    ENDDEF (*ChildType*);
SUBMODULES
    Child Invocation (0.0,0.0,0.0,1.0,1.0) : ChildType (
        Wrong => 1
    );
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ENDDEF (*BasePicture*);
"""
    source_file = tmp_path / "UnknownParameterTarget.s"
    source_file.write_text(code, encoding="utf-8")

    result = validate_single_file_syntax(source_file)

    assert result.ok is True
    assert result.stage == "ok"


def test_validate_single_file_syntax_rejects_parameter_mapping_type_mismatch(tmp_path):
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
TYPEDEFINITIONS
    ChildType = MODULEDEFINITION DateCode_ 2
    MODULEPARAMETERS
        Value: integer;
    ModuleDef
    ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
    ENDDEF (*ChildType*);
SUBMODULES
    Child Invocation (0.0,0.0,0.0,1.0,1.0) : ChildType (
        Value => "bad"
    );
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ENDDEF (*BasePicture*);
"""
    source_file = tmp_path / "ParameterTargetTypeMismatch.s"
    source_file.write_text(code, encoding="utf-8")

    result = validate_single_file_syntax(source_file)

    assert result.ok is False
    assert result.stage == "validation"
    assert result.message is not None
    assert "with datatype 'string'" in result.message
    assert "with datatype 'integer'" in result.message


def test_validate_single_file_syntax_allows_setstringpos_on_const_string(tmp_path):
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    Delimiter: string Const := ";";
    Status: integer := 0;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
        SetStringPos(Delimiter, 1, Status);
ENDDEF (*BasePicture*);
"""
    source_file = tmp_path / "ConstSetStringPos.s"
    source_file.write_text(code, encoding="utf-8")

    result = validate_single_file_syntax(source_file)

    assert result.ok is True
    assert result.stage == "ok"


def test_validate_single_file_syntax_accepts_parameter_mapping_to_anytype(tmp_path):
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
TYPEDEFINITIONS
    ChildType = MODULEDEFINITION DateCode_ 2
    MODULEPARAMETERS
        Value: AnyType;
    ModuleDef
    ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
    ENDDEF (*ChildType*);
SUBMODULES
    Child Invocation (0.0,0.0,0.0,1.0,1.0) : ChildType (
        Value => 1
    );
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ENDDEF (*BasePicture*);
"""
    source_file = tmp_path / "AnyTypeParameterTarget.s"
    source_file.write_text(code, encoding="utf-8")

    result = validate_single_file_syntax(source_file)

    assert result.ok is True
    assert result.stage == "ok"


def test_validate_single_file_syntax_rejects_unknown_seqfork_target(tmp_path):
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    OPENSEQUENCE MainSimulation (SeqControl) COORD 0.0, 0.2 OBJSIZE 2.0, 1.68
        SEQINITSTEP InitSim
        SEQTRANSITION StartSimulation WAIT_FOR True
        SEQSTEP Running
        ALTERNATIVESEQ
            SEQTRANSITION Jump WAIT_FOR True
            SEQFORK MissingTarget
            SEQBREAK
        ALTERNATIVEBRANCH
            SEQTRANSITION Stay WAIT_FOR False
        ENDALTERNATIVE
    ENDOPENSEQUENCE
ENDDEF (*BasePicture*);
"""
    source_file = tmp_path / "UnknownForkTarget.s"
    source_file.write_text(code, encoding="utf-8")

    result = validate_single_file_syntax(source_file)

    assert result.ok is False
    assert result.stage == "validation"
    assert result.message is not None
    assert "SEQFORK target 'MissingTarget'" in result.message


def test_validate_single_file_syntax_rejects_old_on_non_state_variable(tmp_path):
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
        IF Counter:Old THEN
            Counter = 1;
        ENDIF;
ENDDEF (*BasePicture*);
"""
    source_file = tmp_path / "OldOnNonState.s"
    source_file.write_text(code, encoding="utf-8")

    result = validate_single_file_syntax(source_file)

    assert result.ok is False
    assert result.stage == "validation"
    assert result.message is not None
    assert "uses OLD on non-STATE variable 'Counter'" in result.message


def test_validate_single_file_syntax_accepts_old_on_state_record_field(tmp_path):
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
TYPEDEFINITIONS
    CmdType = RECORD DateCode_ 1
        WaterPipeFull: boolean State;
        Other: boolean;
    ENDDEF (*CmdType*);
LOCALVARIABLES
    CMD: CmdType;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
        IF CMD.WaterPipeFull:Old THEN
            CMD.Other = True;
        ENDIF;
ENDDEF (*BasePicture*);
"""
    source_file = tmp_path / "OldOnStateRecordField.s"
    source_file.write_text(code, encoding="utf-8")

    result = validate_single_file_syntax(source_file)

    assert result.ok is True
    assert result.stage == "ok"


def test_validate_single_file_syntax_rejects_old_on_non_state_record_field(tmp_path):
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
TYPEDEFINITIONS
    CmdType = RECORD DateCode_ 1
        WaterPipeFull: boolean State;
        Other: boolean;
    ENDDEF (*CmdType*);
LOCALVARIABLES
    CMD: CmdType;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
        IF CMD.Other:Old THEN
            CMD.Other = True;
        ENDIF;
ENDDEF (*BasePicture*);
"""
    source_file = tmp_path / "OldOnNonStateRecordField.s"
    source_file.write_text(code, encoding="utf-8")

    result = validate_single_file_syntax(source_file)

    assert result.ok is False
    assert result.stage == "validation"
    assert result.message is not None
    assert "uses OLD on non-STATE variable 'CMD.Other'" in result.message


def test_load_source_text_preserves_state_markers_in_compressed_libraries():
    if not _repo_path("Libs").exists():
        pytest.skip("Compressed library files not available")

    cases = [
        ("SupportLib.x", "GetRemoteFile", "ExecuteLocal"),
        ("NSupportLib.x", "zRestoreStringList", "ExecuteState"),
        ("EventLib.x", "EventLogger2", "CurrentEventFinished"),
        ("MmsVarLib.x", "MMSWriteVar", "Rdy"),
        ("ReportLib.x", "ReportGeneralTable", "Ready"),
    ]

    for file_name, moduletype_name, variable_name in cases:
        source_path = _repo_path("Libs", "HA", "ABBLib", file_name)
        src = _load_source_text(source_path)
        basepicture = parser_core_parse_source_text(src)
        moduletype = next(
            (
                item
                for item in (basepicture.moduletype_defs or [])
                if item.name.casefold() == moduletype_name.casefold()
            ),
            None,
        )

        assert moduletype is not None, f"missing moduletype {moduletype_name} in {file_name}"

        variable = next(
            (
                item
                for item in [*(moduletype.moduleparameters or []), *(moduletype.localvariables or [])]
                if item.name.casefold() == variable_name.casefold()
            ),
            None,
        )

        assert variable is not None, f"missing variable {variable_name} in {file_name}"
        assert variable.state is True, f"expected {file_name}:{moduletype_name}.{variable_name} to decode as State"


def test_load_source_text_preserves_duration_value_in_compressed_libraries():
    if not _repo_path("Libs").exists():
        pytest.skip("Compressed library files not available")

    journal_path = _repo_path("Libs", "HA", "ABBLib", "JournalLib.x")
    journal_src = _load_source_text(journal_path)
    assert 'Duration_Value "1h"' in journal_src
    assert 'Time_Value "1984-01-01-00:00:00.000"' in journal_src

    journal_basepicture = parser_core_parse_source_text(journal_src)
    curve_type = next(
        (item for item in (journal_basepicture.datatype_defs or []) if item.name.casefold() == "Curve4Par".casefold()),
        None,
    )
    assert curve_type is not None

    field = next(
        (item for item in (curve_type.var_list or []) if item.name.casefold() == "TimeRange".casefold()),
        None,
    )
    assert field is not None
    assert field.init_value == "1h"
    assert field.init_is_duration is True

    jou_read_tag_type = next(
        (
            item
            for item in (journal_basepicture.datatype_defs or [])
            if item.name.casefold() == "JouReadTagType".casefold()
        ),
        None,
    )
    assert jou_read_tag_type is not None

    start_time = next(
        (item for item in (jou_read_tag_type.var_list or []) if item.name.casefold() == "StartTime".casefold()),
        None,
    )
    assert start_time is not None
    assert isinstance(start_time.init_value, dict)
    assert start_time.init_value.get("Time_Value") == "1984-01-01-00:00:00.000"

    event_path = _repo_path("Libs", "HA", "ABBLib", "EventLib.x")
    event_src = _load_source_text(event_path)
    assert 'Duration_Value "590ms"' in event_src


def test_validate_single_file_syntax_accepts_reported_compressed_library_files():
    if not _repo_path("Libs").exists():
        pytest.skip("Compressed library files not available")

    for file_name in [
        "SupportLib.x",
        "NSupportLib.x",
        "JournalLib.x",
        "EventLib.x",
        "MmsVarLib.x",
        "ReportLib.x",
        "SLIoUnitLib.x",
    ]:
        result = validate_single_file_syntax(_repo_path("Libs", "HA", "ABBLib", file_name))
        assert result.ok is True, f"{file_name}: {result.stage} {result.message}"


def test_validate_single_file_syntax_rejects_string_literal_in_call_argument(tmp_path):
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
TYPEDEFINITIONS
    DummyType = RECORD DateCode_ 1
        StepText: string;
    ENDDEF (*DummyType*);
LOCALVARIABLES
    Dummy: boolean := False;
    Self: DummyType;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
        Dummy = EqualStrings(Self.StepText, "Log", True);
ENDDEF (*BasePicture*);
"""
    source_file = tmp_path / "StringLiteralInCall.s"
    source_file.write_text(code, encoding="utf-8")

    result = validate_single_file_syntax(source_file)

    assert result.ok is False
    assert result.stage == "validation"
    assert result.message is not None
    assert "call 'EqualStrings' argument 2 uses string literal 'Log'" in result.message


def test_validate_single_file_syntax_allows_string_literal_parameter_connection(tmp_path):
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
TYPEDEFINITIONS
    MessageModule = MODULEDEFINITION DateCode_ 1
    MODULEPARAMETERS
        StepName: string;
    ModuleDef
    ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
    ENDDEF (*MessageModule*);
SUBMODULES
    Msg Invocation (0.0,0.0,0.0,1.0,1.0) : MessageModule (
        StepName => "Log"
    );
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ENDDEF (*BasePicture*);
"""
    source_file = tmp_path / "StringLiteralParameterConnection.s"
    source_file.write_text(code, encoding="utf-8")

    result = validate_single_file_syntax(source_file)

    assert result.ok is True
    assert result.stage == "ok"


def test_validate_single_file_syntax_rejects_builtin_function_datatype_mismatch(tmp_path):
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    Name1: string;
    Flag: boolean := False;
    Match: boolean := False;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
        Match = EqualStrings(Name1, Flag, True);
ENDDEF (*BasePicture*);
"""
    source_file = tmp_path / "BuiltinFunctionDatatypeMismatch.s"
    source_file.write_text(code, encoding="utf-8")

    result = validate_single_file_syntax(source_file)

    assert result.ok is False
    assert result.stage == "validation"
    assert result.message is not None
    assert "call 'EqualStrings' argument 2 has datatype 'boolean'" in result.message
    assert "expects 'string'" in result.message


def test_validate_single_file_syntax_rejects_builtin_procedure_datatype_mismatch(tmp_path):
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    SourceDuration: duration;
    DestinationTime: time;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
        CopyTime(SourceDuration, DestinationTime);
ENDDEF (*BasePicture*);
"""
    source_file = tmp_path / "BuiltinProcedureDatatypeMismatch.s"
    source_file.write_text(code, encoding="utf-8")

    result = validate_single_file_syntax(source_file)

    assert result.ok is False
    assert result.stage == "validation"
    assert result.message is not None
    assert "call 'CopyTime' argument 1 has datatype 'duration'" in result.message
    assert "expects 'time'" in result.message


def test_validate_single_file_syntax_allows_builtin_string_family_match(tmp_path):
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    Name1: identstring;
    Name2: string;
    Match: boolean := False;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
        Match = EqualStrings(Name1, Name2, True);
ENDDEF (*BasePicture*);
"""
    source_file = tmp_path / "BuiltinStringFamilyMatch.s"
    source_file.write_text(code, encoding="utf-8")

    result = validate_single_file_syntax(source_file)

    assert result.ok is True
    assert result.stage == "ok"


def test_validate_single_file_syntax_rejects_builtin_arity_mismatch(tmp_path):
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    Name1: string;
    Name2: string;
    Match: boolean := False;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
        Match = EqualStrings(Name1, Name2);
ENDDEF (*BasePicture*);
"""
    source_file = tmp_path / "BuiltinArityMismatch.s"
    source_file.write_text(code, encoding="utf-8")

    result = validate_single_file_syntax(source_file)

    assert result.ok is False
    assert result.stage == "validation"
    assert result.message is not None
    assert "call 'EqualStrings' has 2 arguments but builtin expects 3" in result.message


def test_validate_single_file_syntax_rejects_builtin_in_var_expression(tmp_path):
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    SourceTime: time;
    DestinationTime: time;
    UseSource: boolean := False;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
        CopyTime(IF UseSource THEN SourceTime ELSE SourceTime ENDIF, DestinationTime);
ENDDEF (*BasePicture*);
"""
    source_file = tmp_path / "BuiltinInVarExpression.s"
    source_file.write_text(code, encoding="utf-8")

    result = validate_single_file_syntax(source_file)

    assert result.ok is False
    assert result.stage == "validation"
    assert result.message is not None
    assert "call 'CopyTime' argument 1 must be a variable reference" in result.message
    assert "is 'in var'" in result.message


def test_validate_single_file_syntax_rejects_builtin_out_expression(tmp_path):
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    SourceTime: time;
    DestinationTime: time;
    UseDestination: boolean := False;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
        CopyTime(SourceTime, IF UseDestination THEN DestinationTime ELSE DestinationTime ENDIF);
ENDDEF (*BasePicture*);
"""
    source_file = tmp_path / "BuiltinOutExpression.s"
    source_file.write_text(code, encoding="utf-8")

    result = validate_single_file_syntax(source_file)

    assert result.ok is False
    assert result.stage == "validation"
    assert result.message is not None
    assert "call 'CopyTime' argument 2 must be a variable reference" in result.message
    assert "is 'out'" in result.message
