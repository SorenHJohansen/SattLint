# ruff: noqa: F403, F405
from ._parser_validation_test_support import *


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


def test_validate_single_file_syntax_accepts_multiple_seqfork_targets(tmp_path):
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
        SEQSTEP PathA
        SEQTRANSITION TrNext WAIT_FOR True
        SEQSTEP PathB
        SEQTRANSITION TrFork WAIT_FOR True
            SEQFORK PathA, pathb
    ENDSEQUENCE
ENDDEF (*BasePicture*);
"""
    source_file = tmp_path / "ValidMultiForkTarget.s"
    source_file.write_text(code, encoding="utf-8")

    result = validate_single_file_syntax(source_file)

    assert result.ok is True
    assert result.stage == "ok"


def test_validate_single_file_syntax_rejects_unknown_multi_seqfork_target(tmp_path):
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
        SEQSTEP PathA
        SEQTRANSITION TrNext WAIT_FOR True
        SEQSTEP PathB
        SEQTRANSITION TrFork WAIT_FOR True
            SEQFORK PathA, MissingTarget
    ENDSEQUENCE
ENDDEF (*BasePicture*);
"""
    source_file = tmp_path / "UnknownMultiForkTarget.s"
    source_file.write_text(code, encoding="utf-8")

    result = validate_single_file_syntax(source_file)

    assert result.ok is False
    assert result.stage == "validation"
    assert result.message is not None
    assert "SEQFORK target 'MissingTarget'" in result.message


def test_validate_single_file_syntax_rejects_ambiguous_multi_seqfork_target(tmp_path):
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
        SEQSTEP PathA
        SEQTRANSITION Run WAIT_FOR True
        SEQSTEP Run
        SEQTRANSITION TrFork WAIT_FOR True
            SEQFORK PathA, Run
    ENDSEQUENCE
ENDDEF (*BasePicture*);
"""
    source_file = tmp_path / "AmbiguousMultiForkTarget.s"
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
