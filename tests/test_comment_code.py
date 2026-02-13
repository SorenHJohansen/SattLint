from pathlib import Path

from sattlint.analyzers.comment_code import analyze_comment_code_files
from sattlint.utils.text_processing import find_comments_with_code


def test_find_comments_with_code_detects_assignments_and_calls():
    text = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0,0,0,1,1) : MODULEDEFINITION DateCode_ 123
ModuleCode
(* Counter = Counter + 1; *)
(* CallSomething(A, B); *)
(* Just a comment with no code *)
ENDDEF (*BasePicture*);
"""
    hits = find_comments_with_code(text)
    indicators = [hit.indicators for hit in hits]

    assert any("assignment" in ind for ind in indicators)
    assert any("call" in ind for ind in indicators)


def test_comment_code_analysis_reports_hits(tmp_path: Path):
    source = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0,0,0,1,1) : MODULEDEFINITION DateCode_ 123
ModuleCode
(* IF Start THEN
    Running = True;
ENDIF; *)
(* Note: nothing special here. *)
ENDDEF (*BasePicture*);
"""
    path = tmp_path / "Program.s"
    path.write_text(source, encoding="utf-8")

    report = analyze_comment_code_files([path], basepicture_name="Program")

    assert report.files_scanned == 1
    assert len(report.hits) == 1
    assert report.hits[0].file_path.name == "Program.s"
    assert "control" in report.hits[0].indicators


def test_comments_outside_modulecode_are_ignored():
    """Comments in header, LocalVariables, or type definitions should be ignored."""
    text = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
(* Counter = Counter + 1; *)
BasePicture Invocation (0,0,0,1,1) : MODULEDEFINITION DateCode_ 123
LOCALVARIABLES
    (* CallSomething(A, B); *)
    Var1: integer;
ModuleCode
    Var1 = 5;
ENDDEF (*BasePicture*);
"""
    hits = find_comments_with_code(text)

    # Comments outside ModuleCode should not be detected
    assert len(hits) == 0


def test_pseudocode_with_ellipsis_not_detected():
    """Comments with ellipsis (...) should not be detected as they're pseudocode."""
    text = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0,0,0,1,1) : MODULEDEFINITION DateCode_ 123
ModuleCode
(* IF NOT StateSequence.Reset THEN ... ENDIF *);
(* FOR i := 1 TO 10 DO ... END FOR *);
(* WHILE Condition DO ... END WHILE *);
ENDDEF (*BasePicture*);
"""
    hits = find_comments_with_code(text)

    # Ellipsis indicates pseudocode/documentation, not actual code
    assert len(hits) == 0


def test_control_structures_detected():
    """Various control structures should be detected when properly commented out."""
    text = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0,0,0,1,1) : MODULEDEFINITION DateCode_ 123
ModuleCode
(* IF Condition THEN
    DoSomething();
ENDIF; *)
(* FOR i := 1 TO 10 DO
    Process(i);
END FOR; *)
(* WHILE Running DO
    CheckStatus();
END WHILE; *)
ENDDEF (*BasePicture*);
"""
    hits = find_comments_with_code(text)

    # All three control structure comments should be detected
    assert len(hits) == 3
    indicators = [hit.indicators for hit in hits]
    assert all("control" in ind for ind in indicators)


def test_equation_block_comments():
    """Comments inside EQUATIONBLOCK should be detected."""
    text = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0,0,0,1,1) : MODULEDEFINITION DateCode_ 123
ModuleCode
EQUATIONBLOCK Main :
    (* OldCode = OldCode + 1; *)
    Var1 = 5;
ENDDEF (*Main*);
ENDDEF (*BasePicture*);
"""
    hits = find_comments_with_code(text)

    assert len(hits) == 1
    assert hits[0].indicators == ("assignment",)


def test_sequence_block_comments():
    """Comments inside SEQUENCE should be detected."""
    text = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0,0,0,1,1) : MODULEDEFINITION DateCode_ 123
ModuleCode
SEQUENCE MySeq (SeqControl, SeqTimer)
    (* IF OldCondition THEN
        DoOldThing();
    ENDIF; *)
    Step NewStep
        Active:
            DoNewThing();
ENDSEQUENCE;
ENDDEF (*BasePicture*);
"""
    hits = find_comments_with_code(text)

    assert len(hits) == 1


def test_nested_module_code_sections():
    """Nested modules with their own ModuleCode should all be checked."""
    text = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0,0,0,1,1) : MODULEDEFINITION DateCode_ 123
SUBMODULES
    Sub1 Invocation (0,0,0,1,1) : MODULEDEFINITION DateCode_ 456
    ModuleCode
        (* OuterModuleCode = True; *)
        SUBMODULES
            Sub2 Invocation (0,0,0,1,1) : MODULEDEFINITION DateCode_ 789
            ModuleCode
                (* InnerModuleCode = True; *)
            ENDDEF (*Sub2*);
    ENDDEF (*Sub1*);
ENDDEF (*BasePicture*);
"""
    hits = find_comments_with_code(text)

    # Both comments in nested ModuleCode sections should be detected
    assert len(hits) == 2


def test_invalid_code_not_detected():
    """Invalid SattLine syntax should not be flagged even if it looks like code."""
    text = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0,0,0,1,1) : MODULEDEFINITION DateCode_ 123
ModuleCode
(* This is not valid code @#$% *)
(* IF THEN ELSE ENDIF *)
(* = = = broken syntax = = = *)
ENDDEF (*BasePicture*);
"""
    hits = find_comments_with_code(text)

    # Invalid code should not be detected
    assert len(hits) == 0


def test_comparison_operators_detected():
    """Comments with comparison operators should be detected."""
    text = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0,0,0,1,1) : MODULEDEFINITION DateCode_ 123
ModuleCode
(* IF Value > 100 THEN
    Alert = True;
ENDIF; *)
(* IF Status <> 0 THEN
    Error = True;
ENDIF; *)
ENDDEF (*BasePicture*);
"""
    hits = find_comments_with_code(text)

    assert len(hits) == 2
    assert all("comparison" in hit.indicators for hit in hits)


def test_single_word_not_detected():
    """Single words that happen to be valid identifiers should not be detected."""
    text = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0,0,0,1,1) : MODULEDEFINITION DateCode_ 123
ModuleCode
(* FUNCTIONS *)
(* Counter *)
(* IF *)
(* SEQUENCE *)
ENDDEF (*BasePicture*);
"""
    hits = find_comments_with_code(text)

    # Single words without operators are not code
    assert len(hits) == 0


def test_empty_and_whitespace_comments_ignored():
    """Empty or whitespace-only comments should be ignored."""
    text = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0,0,0,1,1) : MODULEDEFINITION DateCode_ 123
ModuleCode
(* *)
(*    *)
(*

*)
ENDDEF (*BasePicture*);
"""
    hits = find_comments_with_code(text)

    assert len(hits) == 0
