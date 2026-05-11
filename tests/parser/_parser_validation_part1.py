# ruff: noqa: F403, F405
from ._parser_validation_test_support import *


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
