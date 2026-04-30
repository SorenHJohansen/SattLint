"""Tests for validate_single_file_syntax, validate_transformed_basepicture, workspace-mode rules, compressed library sources, and builtin type checks."""

# ruff: noqa: E501

from pathlib import Path
from typing import Any, cast

import pytest

from sattline_parser import parse_source_text as parser_core_parse_source_text
from sattline_parser import strip_sl_comments
from sattline_parser.models.ast_model import (
    BasePicture,
    DataType,
    Equation,
    ModuleCode,
    ModuleHeader,
    ParameterMapping,
    Sequence,
    SFCBreak,
    SFCCodeBlocks,
    SFCFork,
    SFCStep,
    SFCTransition,
    SFCTransitionSub,
    Simple_DataType,
    Variable,
)
from sattline_parser.transformer.sl_transformer import SLTransformer
from sattlint import validation as validation_module
from sattlint.engine import (
    StructuralValidationError,
    _load_source_text,
    create_sl_parser,
    validate_single_file_syntax,
    validate_transformed_basepicture,
)
from sattlint.resolution.type_graph import TypeGraph


def _parse_to_basepicture(text: str):
    parser = create_sl_parser()
    tree = parser.parse(strip_sl_comments(text))
    return SLTransformer().transform(tree)


def _repo_path(*parts: str) -> Path:
    return Path(__file__).resolve().parents[1].joinpath(*parts)


def _var_ref(name: object, *, state: str | None = None) -> dict[str, object]:
    ref = {validation_module.const.KEY_VAR_NAME: name}
    if state is not None:
        ref["state"] = state
    return ref


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


def test_validate_single_file_syntax_rejects_long_program_name(tmp_path):
    code = """
"SyntaxVersion"
"OriginalFileDate"
"Program date: 2026-01-01-00:00:00.000, name: NameLongerThanTwenty1"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ENDDEF (*BasePicture*);
"""
    source_file = tmp_path / "LongProgramName.s"
    source_file.write_text(code, encoding="utf-8")

    result = validate_single_file_syntax(source_file)

    assert result.ok is False
    assert result.stage == "validation"
    assert result.message is not None
    assert "exceeds 20 characters" in result.message


def test_validate_single_file_syntax_rejects_program_name_reserved_keyword(tmp_path):
    code = """
"SyntaxVersion"
"OriginalFileDate"
"Program date: 2026-01-01-00:00:00.000, name: InteractObjects"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ENDDEF (*BasePicture*);
"""
    source_file = tmp_path / "ReservedProgramName.s"
    source_file.write_text(code, encoding="utf-8")

    result = validate_single_file_syntax(source_file)

    assert result.ok is False
    assert result.stage == "validation"
    assert result.message is not None
    assert "reserved SattLine keyword" in result.message
    assert "InteractObjects" in result.message


def test_validate_single_file_syntax_allows_colour_as_moduletype_local_variable_name(tmp_path):
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
TYPEDEFINITIONS
    LowPresColumnIcon = MODULEDEFINITION DateCode_ 2
    LOCALVARIABLES
        Colour: integer := 0;
    ModuleDef
    ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
    ENDDEF (*LowPresColumnIcon*);
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ENDDEF (*BasePicture*);
"""
    source_file = tmp_path / "ColourIdentifier.s"
    source_file.write_text(code, encoding="utf-8")

    result = validate_single_file_syntax(source_file)

    assert result.ok is True
    assert result.stage == "ok"


def test_validate_single_file_syntax_accepts_program_name_at_limit(tmp_path):
    # Exactly 20 characters: "NameLongerThanTwenty"
    code = """
"SyntaxVersion"
"OriginalFileDate"
"Program date: 2026-01-01-00:00:00.000, name: NameLongerThanTwenty"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ENDDEF (*BasePicture*);
"""
    source_file = tmp_path / "ExactTwentyName.s"
    source_file.write_text(code, encoding="utf-8")

    result = validate_single_file_syntax(source_file)

    assert result.ok is True
    assert result.stage == "ok"


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


def test_validate_single_file_syntax_accepts_const_without_init(tmp_path):
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    Limit: integer Const;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ENDDEF (*BasePicture*);
"""
    source_file = tmp_path / "ConstNoInit.s"
    source_file.write_text(code, encoding="utf-8")

    result = validate_single_file_syntax(source_file)

    assert result.ok is True
    assert result.stage == "ok"


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


def test_validate_single_file_syntax_accepts_relational_comparison_with_anytype(tmp_path):
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    Wildcard: AnyType;
    Flag: boolean := False;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
        Flag = Wildcard < 10;
ENDDEF (*BasePicture*);
"""
    source_file = tmp_path / "AnyTypeComparison.s"
    source_file.write_text(code, encoding="utf-8")

    result = validate_single_file_syntax(source_file)

    assert result.ok is True
    assert result.stage == "ok"


def test_validate_single_file_syntax_accepts_exitcode_arithmetic_with_anytype(tmp_path):
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    OprTemp: AnyType;
    Counter: integer := 0;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    SEQUENCE OperationSequence COORD 0.0, 0.0 OBJSIZE 1.0, 1.0
        SEQINITSTEP InitValues
            EXITCODE
                Counter = OprTemp + 1;
        SEQTRANSITION WAIT_FOR True
        SEQSTEP Done
    ENDSEQUENCE
ENDDEF (*BasePicture*);
"""
    source_file = tmp_path / "AnyTypeExitCodeArithmetic.s"
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


def test_validate_single_file_syntax_accepts_duplicate_sequence_labels_when_unused(tmp_path):
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    SEQUENCE MainSeq COORD 0.0, 0.0 OBJSIZE 1.0, 1.0
        SEQINITSTEP Init
        SEQTRANSITION Run WAIT_FOR True
        SEQSTEP run
        SEQTRANSITION TrDone WAIT_FOR True
    ENDSEQUENCE
ENDDEF (*BasePicture*);
"""
    source_file = tmp_path / "DuplicateSequenceLabelsUnused.s"
    source_file.write_text(code, encoding="utf-8")

    result = validate_single_file_syntax(source_file)

    assert result.ok is True
    assert result.stage == "ok"


def test_validate_single_file_syntax_rejects_ambiguous_seqfork_target(tmp_path):
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    SEQUENCE MainSeq COORD 0.0, 0.0 OBJSIZE 1.0, 1.0
        SEQINITSTEP Init
        SEQTRANSITION TrStart WAIT_FOR True
        SEQSTEP Run
        SEQTRANSITION Run WAIT_FOR True
            SEQFORK Run
    ENDSEQUENCE
ENDDEF (*BasePicture*);
"""
    source_file = tmp_path / "AmbiguousSeqForkTarget.s"
    source_file.write_text(code, encoding="utf-8")

    result = validate_single_file_syntax(source_file)

    assert result.ok is False
    assert result.stage == "validation"
    assert result.message is not None
    assert "ambiguous SEQFORK target 'Run'" in result.message


def test_validate_single_file_syntax_accepts_seqfork_after_step_without_seqbreak(tmp_path):
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    SEQUENCE Seq1 COORD 0.0, 0.0 OBJSIZE 1.0, 1.0
        SEQINITSTEP S1
        SEQFORK Tr2
        SEQTRANSITION Tr1 WAIT_FOR True
    ENDSEQUENCE

    SEQUENCE Seq2 COORD 0.0, 0.0 OBJSIZE 1.0, 1.0
        SEQINITSTEP S2
        SEQTRANSITION Tr2 WAIT_FOR True
            SEQFORK S1
    ENDSEQUENCE
ENDDEF (*BasePicture*);
"""
    source_file = tmp_path / "SeqForkAfterStep.s"
    source_file.write_text(code, encoding="utf-8")

    result = validate_single_file_syntax(source_file)

    assert result.ok is True
    assert result.stage == "ok"


def test_validate_single_file_syntax_rejects_parallel_branch_ending_in_transition(tmp_path):
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    SEQUENCE ParSeq COORD 0.0, 0.0 OBJSIZE 1.0, 1.0
        SEQINITSTEP Init
        SEQTRANSITION TrStart WAIT_FOR True
        PARALLELSEQ
            SEQSTEP BranchA
            SEQTRANSITION TrDoneA WAIT_FOR True
        PARALLELBRANCH
            SEQSTEP BranchB
            SEQTRANSITION TrDoneB WAIT_FOR True
            SEQSTEP BranchBDone
        ENDPARALLEL
        SEQSTEP Merge
    ENDSEQUENCE
ENDDEF (*BasePicture*);
"""
    source_file = tmp_path / "ParallelBranchEndsInTransition.s"
    source_file.write_text(code, encoding="utf-8")

    result = validate_single_file_syntax(source_file)

    assert result.ok is False
    assert result.stage == "validation"
    assert result.message is not None
    assert "parallel branch 1 ends with SEQTRANSITION" in result.message


def test_validate_single_file_syntax_rejects_step_immediately_after_endparallel(tmp_path):
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    SEQUENCE ParSeq COORD 0.0, 0.0 OBJSIZE 1.0, 1.0
        SEQINITSTEP Init
        SEQTRANSITION TrStart WAIT_FOR True
        PARALLELSEQ
            SEQSTEP BranchA
            SEQTRANSITION TrDoneA WAIT_FOR True
            SEQSTEP BranchADone
        PARALLELBRANCH
            SEQSTEP BranchB
            SEQTRANSITION TrDoneB WAIT_FOR True
            SEQSTEP BranchBDone
        ENDPARALLEL
        SEQSTEP Merge
    ENDSEQUENCE
ENDDEF (*BasePicture*);
"""
    source_file = tmp_path / "StepAfterEndParallel.s"
    source_file.write_text(code, encoding="utf-8")

    result = validate_single_file_syntax(source_file)

    assert result.ok is False
    assert result.stage == "validation"
    assert result.message is not None
    assert "immediately after parallel block 'ENDPARALLEL'" in result.message


def test_validate_single_file_syntax_rejects_subseqtransition_starting_with_step(tmp_path):
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    SEQUENCE MainSeq COORD 0.0, 0.0 OBJSIZE 1.0, 1.0
        SEQINITSTEP Idle
        SEQTRANSITION TrStart WAIT_FOR True
        SEQSTEP Check
        SUBSEQTRANSITION TrCheckPhase
            SEQSTEP Checking
            SEQTRANSITION TrCheckOk WAIT_FOR True
        ENDSUBSEQTRANSITION
        SEQSTEP Active
    ENDSEQUENCE
ENDDEF (*BasePicture*);
"""
    source_file = tmp_path / "SubSeqTransitionStartsWithStep.s"
    source_file.write_text(code, encoding="utf-8")

    result = validate_single_file_syntax(source_file)

    assert result.ok is False
    assert result.stage == "validation"
    assert result.message is not None
    assert "must not start with SEQSTEP" in result.message


def test_validate_single_file_syntax_rejects_consecutive_transitions_in_sequence_path(tmp_path):
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    SEQUENCE MainSeq COORD 0.0, 0.0 OBJSIZE 1.0, 1.0
        SEQINITSTEP Start
        SEQTRANSITION TrStart WAIT_FOR True
        SEQTRANSITION TrNext WAIT_FOR True
        SEQSTEP Running
    ENDSEQUENCE
ENDDEF (*BasePicture*);
"""
    source_file = tmp_path / "ConsecutiveTransitions.s"
    source_file.write_text(code, encoding="utf-8")

    result = validate_single_file_syntax(source_file)

    assert result.ok is False
    assert result.stage == "validation"
    assert result.message is not None
    assert "only one transition may execute per cycle" in result.message


def test_validate_single_file_syntax_rejects_step_reset_without_seqcontrol(tmp_path):
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    Flag: boolean := False;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    SEQUENCE MainSeq COORD 0.0, 0.0 OBJSIZE 1.0, 1.0
        SEQINITSTEP Start
        SEQTRANSITION TrStart WAIT_FOR Start.Reset
        SEQSTEP Running
    ENDSEQUENCE
ENDDEF (*BasePicture*);
"""
    source_file = tmp_path / "StepResetWithoutSeqControl.s"
    source_file.write_text(code, encoding="utf-8")

    result = validate_single_file_syntax(source_file)

    assert result.ok is False
    assert result.stage == "validation"
    assert result.message is not None
    assert "only exposes .Reset when its sequence enables SeqControl" in result.message


def test_validate_single_file_syntax_accepts_step_reset_with_seqcontrol(tmp_path):
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    OPENSEQUENCE MainSeq (SeqControl) COORD 0.0, 0.0 OBJSIZE 1.0, 1.0
        SEQINITSTEP Start
        SEQTRANSITION TrStart WAIT_FOR Start.Reset
        SEQSTEP Running
    ENDOPENSEQUENCE
ENDDEF (*BasePicture*);
"""
    source_file = tmp_path / "StepResetWithSeqControl.s"
    source_file.write_text(code, encoding="utf-8")

    result = validate_single_file_syntax(source_file)

    assert result.ok is True
    assert result.stage == "ok"


def test_validate_single_file_syntax_rejects_sequence_reset_without_seqcontrol(tmp_path):
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    OPENSEQUENCE MainSeq COORD 0.0, 0.0 OBJSIZE 1.0, 1.0
        SEQINITSTEP Start
        SEQTRANSITION TrStart WAIT_FOR MainSeq.Reset
        SEQSTEP Running
    ENDOPENSEQUENCE
ENDDEF (*BasePicture*);
"""
    source_file = tmp_path / "SequenceResetWithoutSeqControl.s"
    source_file.write_text(code, encoding="utf-8")

    result = validate_single_file_syntax(source_file)

    assert result.ok is False
    assert result.stage == "validation"
    assert result.message is not None
    assert "sequence 'MainSeq' only exposes .Reset when it enables SeqControl" in result.message


def test_validate_single_file_syntax_accepts_sequence_reset_and_hold_with_seqcontrol(tmp_path):
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    si: integer := 0;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    OPENSEQUENCE MainSeq (SeqControl) COORD 0.0, 0.0 OBJSIZE 1.0, 1.0
        SEQINITSTEP Start
        SEQTRANSITION TrStart WAIT_FOR False
        SEQSTEP Running
    ENDOPENSEQUENCE
    EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
        IF NOT MainSeq.Reset AND NOT MainSeq.Hold THEN
            si = 1;
        ENDIF;
ENDDEF (*BasePicture*);
"""
    source_file = tmp_path / "SequenceResetHoldWithSeqControl.s"
    source_file.write_text(code, encoding="utf-8")

    result = validate_single_file_syntax(source_file)

    assert result.ok is True
    assert result.stage == "ok"


def test_validate_single_file_syntax_rejects_step_timer_without_seqtimer(tmp_path):
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    SEQUENCE MainSeq COORD 0.0, 0.0 OBJSIZE 1.0, 1.0
        SEQINITSTEP Start
        SEQTRANSITION TrStart WAIT_FOR Start.T >= 1
        SEQSTEP Running
    ENDSEQUENCE
ENDDEF (*BasePicture*);
"""
    source_file = tmp_path / "StepTimerWithoutSeqTimer.s"
    source_file.write_text(code, encoding="utf-8")

    result = validate_single_file_syntax(source_file)

    assert result.ok is False
    assert result.stage == "validation"
    assert result.message is not None
    assert "only exposes .T when its sequence enables SeqTimer" in result.message


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


def test_validate_single_file_syntax_rejects_assignment_to_old_state_access(tmp_path):
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    Counter: boolean State := False;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
        Counter:Old = True;
ENDDEF (*BasePicture*);
"""
    source_file = tmp_path / "AssignOldStateAccess.s"
    source_file.write_text(code, encoding="utf-8")

    result = validate_single_file_syntax(source_file)

    assert result.ok is False
    assert result.stage == "validation"
    assert result.message is not None
    assert "must not use OLD state access" in result.message


def test_validation_internal_reserved_keywords_skip_non_string_grammar_values(monkeypatch):
    monkeypatch.setattr(validation_module.const, "GRAMMAR_VALUE_FAKE_NUMBER", 123, raising=False)

    reserved = validation_module._build_reserved_identifier_keywords()

    assert "123" not in reserved


def test_validation_internal_declared_variable_returns_for_untyped_literal(monkeypatch):
    variable = Variable(name="Value", datatype=Simple_DataType.INTEGER, init_value=object())

    monkeypatch.setattr(validation_module, "_infer_literal_datatype", lambda *args, **kwargs: None)

    validation_module._validate_declared_variable(
        variable,
        "test",
        type_graph=TypeGraph.from_datatypes([]),
        known_datatypes=(),
    )


def test_validation_internal_declared_variable_returns_for_workspace_external_datatype():
    variable = Variable(name="Value", datatype="ExternalType", init_value=1)

    validation_module._validate_declared_variable(
        variable,
        "test",
        type_graph=TypeGraph.from_datatypes([]),
        known_datatypes=(),
        allow_unresolved_external_datatypes=True,
    )


def test_validation_internal_collect_sequence_labels_keeps_first_casefolded_label():
    nodes = [
        SFCStep(kind="init", name="Start", code=SFCCodeBlocks()),
        SFCTransition(name="Run", condition=True),
        SFCStep(kind="step", name="run", code=SFCCodeBlocks()),
    ]

    labels: dict[str, str] = {}

    validation_module._collect_sequence_labels(nodes, labels, "test sequence")

    assert labels == {"start": "Start", "run": "Run"}


def test_validation_internal_validate_sequence_nodes_warns_for_multiple_init_steps():
    warnings: list[str] = []
    nodes = [
        SFCStep(kind="init", name="Start", code=SFCCodeBlocks()),
        SFCTransition(name="TrStart", condition=True),
        SFCStep(kind="init", name="Restart", code=SFCCodeBlocks()),
    ]

    validation_module._validate_sequence_nodes(
        nodes,
        "test sequence",
        labels={},
        label_counts={},
        env={},
        type_graph=TypeGraph.from_datatypes([]),
        require_init_step=True,
        warning_sink=warnings.append,
    )

    assert any("outside the first position" in warning for warning in warnings)
    assert any("must contain exactly one SEQINITSTEP" in warning for warning in warnings)


def test_validation_internal_iter_sequence_node_refs_collects_step_and_transition_refs():
    refs = validation_module._iter_sequence_node_refs(
        [
            SFCStep(
                kind="step",
                name="Running",
                code=SFCCodeBlocks(
                    enter=[_var_ref("Start.Hold")],
                    active=[(_var_ref("Start.Reset"),)],
                    exit=[],
                ),
            ),
            SFCTransition(name="TrDone", condition=_var_ref("Running.T")),
        ]
    )

    assert refs == [_var_ref("Start.Hold"), _var_ref("Start.Reset"), _var_ref("Running.T")]


def test_validation_internal_step_auto_variable_refs_cover_skip_and_hold_paths():
    validation_module._validate_step_auto_variable_refs(None, {}, "test module")

    modulecode = ModuleCode(
        sequences=cast(
            Any,
            [
                object(),
                Sequence(
                    name="MainSeq",
                    type="sequence",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[SFCStep(kind="init", name="Start", code=SFCCodeBlocks())],
                ),
            ],
        ),
        equations=[
            Equation(
                name="Main",
                position=(0.0, 0.0),
                size=(1.0, 1.0),
                code=[
                    _var_ref(123),
                    _var_ref("Local.Reset"),
                    _var_ref("MainSeq.Hold"),
                ],
            )
        ],
    )

    with pytest.raises(StructuralValidationError, match=r"sequence 'MainSeq' only exposes \.Hold"):
        validation_module._validate_step_auto_variable_refs(
            modulecode,
            {"local": Variable(name="Local", datatype=Simple_DataType.BOOLEAN)},
            "test module",
        )


@pytest.mark.parametrize(
    ("ref_name", "expected_message"),
    [
        ("Missing.Reset", "no sequence step named 'Missing' exists in this module"),
        ("Start.Hold", "step 'Start' only exposes .Hold when its sequence enables SeqControl"),
    ],
)
def test_validation_internal_step_auto_variable_refs_reports_missing_and_step_hold(ref_name, expected_message):
    modulecode = ModuleCode(
        sequences=[
            Sequence(
                name="MainSeq",
                type="sequence",
                position=(0.0, 0.0),
                size=(1.0, 1.0),
                code=[SFCStep(kind="init", name="Start", code=SFCCodeBlocks())],
            )
        ],
        equations=[
            Equation(
                name="Main",
                position=(0.0, 0.0),
                size=(1.0, 1.0),
                code=[_var_ref(ref_name)],
            )
        ],
    )

    with pytest.raises(StructuralValidationError, match=expected_message):
        validation_module._validate_step_auto_variable_refs(modulecode, {}, "test module")


def test_validation_internal_parallel_branch_trailer_recognizes_all_branch_markers():
    assert validation_module._parallel_branch_trailer(SFCTransitionSub(name="Tr", body=[])) == "SUBSEQTRANSITION"
    assert validation_module._parallel_branch_trailer(SFCFork(target="Target")) == "SEQFORK"
    assert validation_module._parallel_branch_trailer(SFCBreak()) == "SEQBREAK"


def test_validation_internal_variable_refs_skip_unknown_roots_and_simple_field_access():
    validation_module._validate_variable_refs(
        [
            _var_ref("Missing", state="Old"),
            _var_ref("Counter.Child", state="Old"),
        ],
        {"counter": Variable(name="Counter", datatype=Simple_DataType.INTEGER, state=False)},
        TypeGraph.from_datatypes([]),
        "test module",
    )


def test_validation_internal_parameter_mappings_cover_skip_and_target_branches():
    policy = validation_module._ModuleValidationPolicy()

    validation_module._validate_parameter_mappings(
        cast(
            Any,
            [
                object(),
                ParameterMapping(
                    target=_var_ref("Value"),
                    source_type="value",
                    is_duration=False,
                    is_source_global=False,
                    source_literal=1,
                ),
            ],
        ),
        "test module",
        type_graph=TypeGraph.from_datatypes([]),
        expected_parameters={"value": Variable(name="Value", datatype=Simple_DataType.INTEGER)},
        policy=policy,
    )

    with pytest.raises(StructuralValidationError, match="uses field access on non-record parameter 'Value'"):
        validation_module._validate_parameter_mappings(
            [
                ParameterMapping(
                    target=_var_ref("Value.Child"),
                    source_type="value",
                    is_duration=False,
                    is_source_global=False,
                    source_literal=1,
                )
            ],
            "test module",
            type_graph=TypeGraph.from_datatypes([]),
            expected_parameters={"value": Variable(name="Value", datatype=Simple_DataType.INTEGER)},
            policy=policy,
        )

    record_graph = TypeGraph.from_datatypes(
        [
            DataType(
                name="RecordParam",
                description=None,
                datecode=1,
                var_list=[Variable(name="Present", datatype=Simple_DataType.INTEGER)],
            )
        ]
    )
    with pytest.raises(StructuralValidationError, match=r"parameter mapping target 'Config\.Missing' does not exist"):
        validation_module._validate_parameter_mappings(
            [
                ParameterMapping(
                    target=_var_ref("Config.Missing"),
                    source_type="value",
                    is_duration=False,
                    is_source_global=False,
                    source_literal=1,
                )
            ],
            "test module",
            type_graph=record_graph,
            expected_parameters={"config": Variable(name="Config", datatype="RecordParam")},
            policy=policy,
        )

    validation_module._validate_parameter_mappings(
        [
            ParameterMapping(
                target=_var_ref("External.Child"),
                source_type="value",
                is_duration=False,
                is_source_global=False,
                source_literal=1,
            )
        ],
        "test module",
        type_graph=TypeGraph.from_datatypes([]),
        expected_parameters={"external": Variable(name="External", datatype="UnresolvedExternalType")},
        policy=policy,
    )


def test_validation_internal_parameter_mappings_fallback_to_target_variable_datatype(monkeypatch):
    monkeypatch.setattr(validation_module, "_resolve_variable_field_datatype", lambda *args, **kwargs: None)

    validation_module._validate_parameter_mappings(
        [
            ParameterMapping(
                target=_var_ref("Value"),
                source_type="value",
                is_duration=False,
                is_source_global=False,
                source_literal=1,
            )
        ],
        "test module",
        type_graph=TypeGraph.from_datatypes([]),
        expected_parameters={"value": Variable(name="Value", datatype=Simple_DataType.INTEGER)},
        policy=validation_module._ModuleValidationPolicy(),
    )


@pytest.mark.parametrize(
    ("target_name", "datatype", "source_literal", "is_duration", "expected_message"),
    [
        (
            "Delay",
            Simple_DataType.DURATION,
            "bad",
            True,
            "maps invalid duration literal 'bad' to parameter target 'Delay'",
        ),
        (
            "Stamp",
            Simple_DataType.TIME,
            {validation_module.const.GRAMMAR_VALUE_TIME_VALUE: "bad"},
            False,
            "maps invalid time literal 'bad' to parameter target 'Stamp'",
        ),
    ],
)
def test_validation_internal_parameter_mappings_reject_invalid_literal_shapes(
    target_name,
    datatype,
    source_literal,
    is_duration,
    expected_message,
):
    with pytest.raises(StructuralValidationError, match=expected_message):
        validation_module._validate_parameter_mappings(
            [
                ParameterMapping(
                    target=_var_ref(target_name),
                    source_type="value",
                    is_duration=is_duration,
                    is_source_global=False,
                    source_literal=source_literal,
                )
            ],
            "test module",
            type_graph=TypeGraph.from_datatypes([]),
            expected_parameters={target_name.casefold(): Variable(name=target_name, datatype=datatype)},
            policy=validation_module._ModuleValidationPolicy(),
        )


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


def test_validate_single_file_syntax_rejects_string_assignment(tmp_path):
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    StrA: string := "Hello";
    StrB: string := "World";
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
        StrA = StrB;
ENDDEF (*BasePicture*);
"""
    source_file = tmp_path / "StringAssignment.s"
    source_file.write_text(code, encoding="utf-8")

    result = validate_single_file_syntax(source_file)

    assert result.ok is False
    assert result.stage == "validation"
    assert result.message is not None
    assert "assignment to string variable 'StrA' is not allowed" in result.message
    assert "CopyString" in result.message


def test_validate_single_file_syntax_rejects_real_assignment_to_integer(tmp_path):
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    OperatorSetpoint: real := 50.0;
    Output: integer := 0;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
        Output = OperatorSetpoint;
ENDDEF (*BasePicture*);
"""
    source_file = tmp_path / "RealToIntegerAssignment.s"
    source_file.write_text(code, encoding="utf-8")

    result = validate_single_file_syntax(source_file)

    assert result.ok is False
    assert result.stage == "validation"
    assert result.message is not None
    assert (
        "assigns 'OperatorSetpoint' with datatype 'real' to target 'Output' with datatype 'integer'" in result.message
    )


def test_validate_single_file_syntax_rejects_arithmetic_with_boolean_operand(tmp_path):
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    Count: integer := 0;
    Flag: boolean := False;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
        Count = Count + Flag;
ENDDEF (*BasePicture*);
"""
    source_file = tmp_path / "ArithmeticBooleanOperand.s"
    source_file.write_text(code, encoding="utf-8")

    result = validate_single_file_syntax(source_file)

    assert result.ok is False
    assert result.stage == "validation"
    assert result.message is not None
    assert "arithmetic operator '+' expects numeric operands" in result.message


def test_validate_single_file_syntax_rejects_logical_with_integer_operand(tmp_path):
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    Count: integer := 0;
    Flag: boolean := False;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
        Flag = Count AND True;
ENDDEF (*BasePicture*);
"""
    source_file = tmp_path / "LogicalIntegerOperand.s"
    source_file.write_text(code, encoding="utf-8")

    result = validate_single_file_syntax(source_file)

    assert result.ok is False
    assert result.stage == "validation"
    assert result.message is not None
    assert "logical operator 'AND' expects boolean operands" in result.message


def test_validate_single_file_syntax_rejects_comparison_with_boolean_operand(tmp_path):
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    Left: boolean := False;
    Right: boolean := True;
    Flag: boolean := False;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
        Flag = Left < Right;
ENDDEF (*BasePicture*);
"""
    source_file = tmp_path / "ComparisonBooleanOperand.s"
    source_file.write_text(code, encoding="utf-8")

    result = validate_single_file_syntax(source_file)

    assert result.ok is False
    assert result.stage == "validation"
    assert result.message is not None
    assert "comparison expects numeric operands" in result.message


def test_validate_single_file_syntax_rejects_division_by_zero_literal(tmp_path):
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    Count: integer := 0;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
        Count = Count / 0;
ENDDEF (*BasePicture*);
"""
    source_file = tmp_path / "DivisionByZeroLiteral.s"
    source_file.write_text(code, encoding="utf-8")

    result = validate_single_file_syntax(source_file)

    assert result.ok is False
    assert result.stage == "validation"
    assert result.message is not None
    assert "division by zero is not allowed" in result.message


def test_validate_single_file_syntax_rejects_if_expression_with_incompatible_branches(tmp_path):
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    Count: integer := 0;
    Flag: boolean := False;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
        Count = IF Flag THEN Count ELSE Flag ENDIF;
ENDDEF (*BasePicture*);
"""
    source_file = tmp_path / "IfBranchTypeMismatch.s"
    source_file.write_text(code, encoding="utf-8")

    result = validate_single_file_syntax(source_file)

    assert result.ok is False
    assert result.stage == "validation"
    assert result.message is not None
    assert "IF-expression branches must have compatible datatypes" in result.message


def test_validate_single_file_syntax_allows_copystring_for_string_copy(tmp_path):
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    StrA: string := "Hello";
    StrB: string := "World";
    Status: integer := 0;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
        CopyString(StrB, StrA, Status);
ENDDEF (*BasePicture*);
"""
    source_file = tmp_path / "CopyStringAllowed.s"
    source_file.write_text(code, encoding="utf-8")

    result = validate_single_file_syntax(source_file)

    assert result.ok is True
    assert result.stage == "ok"
