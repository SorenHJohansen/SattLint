from pathlib import Path

from sattlint.analyzers.comment_code import analyze_comment_code_files
from sattlint.utils import text_processing
from sattlint.utils.text_processing import find_comments_with_code, find_disallowed_comments


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
    assert report.hits[0].module_path == ("BasePicture",)
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
    assert hits[0].module_path == ("BasePicture", "Sub1")
    assert hits[1].module_path == ("BasePicture", "Sub1", "Sub2")


def test_find_comments_with_code_tracks_typedef_module_paths():
    text = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0,0,0,1,1) : MODULEDEFINITION DateCode_ 123
TYPEDEFINITIONS
    WorkerType = MODULEDEFINITION DateCode_ 456
    ModuleCode
        (* Result = InputValue + 1; *)
    ENDDEF (*WorkerType*);
ENDDEF (*BasePicture*);
"""

    hits = find_comments_with_code(text)

    assert len(hits) == 1
    assert hits[0].module_path == ("BasePicture", "TypeDef:WorkerType")


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


def test_find_disallowed_comments_allows_comments_before_modulecode():
    """Comments before ModuleCode should be allowed."""
    text = """(* This is OK *)
BasePicture Invocation (0,0,0,1,1) : MODULEDEFINITION DateCode_ 123
ModuleCode
EQUATIONBLOCK
x = 1;
ENDEQUATIONBLOCK;
ENDDEF (*BasePicture*);
"""
    violations = find_disallowed_comments(text)

    assert len(violations) == 0


def test_find_disallowed_comments_flags_freestanding_before_equationblock():
    """Freestanding comments inside ModuleCode before EQUATIONBLOCK should be flagged."""
    text = """BasePicture Invocation (0,0,0,1,1) : MODULEDEFINITION DateCode_ 123
ModuleCode
(* Freestanding comment *)
EQUATIONBLOCK
x = 1;
ENDEQUATIONBLOCK;
ENDDEF (*BasePicture*);
"""
    violations = find_disallowed_comments(text)

    assert len(violations) == 1
    assert violations[0].start_line == 3


def test_find_disallowed_comments_flags_freestanding_before_sequence():
    """Freestanding comments inside ModuleCode before SEQUENCE should be flagged."""
    text = """BasePicture Invocation (0,0,0,1,1) : MODULEDEFINITION DateCode_ 123
ModuleCode
(* Disallowed comment *)
SEQUENCE
S1 : Statement1;
ENDSEQUENCE;
ENDDEF (*BasePicture*);
"""
    violations = find_disallowed_comments(text)

    assert len(violations) == 1
    assert violations[0].start_line == 3


def test_find_disallowed_comments_allows_enddef_label():
    """ENDDEF label comments should not be flagged."""
    text = """BasePicture Invocation (0,0,0,1,1) : MODULEDEFINITION DateCode_ 123
ModuleCode
EQUATIONBLOCK
x = 1;
ENDEQUATIONBLOCK;
ENDDEF (*BasePicture*);
"""
    violations = find_disallowed_comments(text)

    # The ENDDEF label comment is allowed, so no violations
    assert len(violations) == 0


def test_find_disallowed_comments_allows_comments_after_equationblock():
    """Comments inside EQUATIONBLOCK should be allowed."""
    text = """BasePicture Invocation (0,0,0,1,1) : MODULEDEFINITION DateCode_ 123
ModuleCode
EQUATIONBLOCK
(* This comment inside block is OK *)
x = 1;
ENDEQUATIONBLOCK;
ENDDEF (*BasePicture*);
"""
    violations = find_disallowed_comments(text)

    assert len(violations) == 0


def test_find_disallowed_comments_allows_comments_in_opensequence():
    """Comments inside OPENSEQUENCE block should be allowed."""
    text = """BasePicture Invocation (0,0,0,1,1) : MODULEDEFINITION DateCode_ 123
ModuleCode
OPENSEQUENCE
(* Comment in sequence *)
S1 : Statement1;
ENDSEQUENCE;
ENDDEF (*BasePicture*);
"""
    violations = find_disallowed_comments(text)

    assert len(violations) == 0


def test_find_disallowed_comments_ignores_comments_outside_modulecode():
    """Comments outside ModuleCode should be ignored entirely."""
    text = """(* Before module *)
BasePicture Invocation (0,0,0,1,1) : MODULEDEFINITION DateCode_ 123
(* After module *)
ENDDEF (*BasePicture*);
"""
    violations = find_disallowed_comments(text)

    assert len(violations) == 0


def test_find_disallowed_comments_flags_multiline_enddef_label_comment():
    text = """BasePicture Invocation (0,0,0,1,1) : MODULEDEFINITION DateCode_ 123
ModuleCode
EQUATIONBLOCK
x = 1;
ENDEQUATIONBLOCK;
ENDDEF (*Base
Picture*);
"""

    violations = find_disallowed_comments(text)

    assert len(violations) == 1
    assert violations[0].start_line == 6


def test_find_disallowed_comments_resets_enddef_label_when_non_comment_token_appears():
    text = """BasePicture Invocation (0,0,0,1,1) : MODULEDEFINITION DateCode_ 123
ModuleCode
EQUATIONBLOCK
x = 1;
ENDEQUATIONBLOCK;
ENDDEF; (* not an ENDDEF label comment *)
"""

    violations = find_disallowed_comments(text)

    assert violations == []


def test_find_disallowed_comments_handles_strings_and_nested_comments_before_first_block():
    text = """BasePicture Invocation (0,0,0,1,1) : MODULEDEFINITION DateCode_ 123
ModuleCode
Message = "A ""quoted"" path \\tmp";
Broken = "unterminated
(* Outer (* inner *) still outer *)
EQUATIONBLOCK
x = 1;
ENDEQUATIONBLOCK;
ENDDEF (*BasePicture*);
"""

    violations = find_disallowed_comments(text)

    assert len(violations) == 1
    assert violations[0].start_line == 5


def test_find_comments_with_code_handles_nested_comments_inside_modulecode(monkeypatch):
    text = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0,0,0,1,1) : MODULEDEFINITION DateCode_ 123
ModuleCode
(* Outer note (* nested note *) Counter = Counter + 1; *)
ENDDEF (*BasePicture*);
"""
    seen_comment_text: list[str] = []

    def _fake_indicators(comment_text: str) -> tuple[str, ...]:
        seen_comment_text.append(comment_text)
        return ("assignment",)

    monkeypatch.setattr(text_processing, "_comment_code_indicators", _fake_indicators)

    hits = find_comments_with_code(text)

    assert len(hits) == 1
    assert seen_comment_text == [" Outer note  nested note  Counter = Counter + 1; "]
    assert "assignment" in hits[0].indicators


def test_find_comments_with_code_ignores_comment_markers_inside_strings():
    text = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0,0,0,1,1) : MODULEDEFINITION DateCode_ 123
ModuleCode
EQUATIONBLOCK Main :
    Message = "(* not a comment *) and ""quoted"" text";
    PathValue = ".\\Temp\\(* keep *)";
ENDDEF (*BasePicture*);
"""

    hits = find_comments_with_code(text)

    assert hits == []


def test_find_comments_with_code_tracks_private_typedef_module_paths():
    text = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0,0,0,1,1) : MODULEDEFINITION DateCode_ 123
TYPEDEFINITIONS
    WorkerType = Private_ MODULEDEFINITION DateCode_ 456
    ModuleCode
        (* Result = InputValue + 1; *)
    ENDDEF (*WorkerType*);
ENDDEF (*BasePicture*);
"""

    hits = find_comments_with_code(text)

    assert len(hits) == 1
    assert hits[0].module_path == ("BasePicture", "TypeDef:WorkerType")


def test_find_comments_with_code_treats_newline_as_end_of_unterminated_string():
    text = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0,0,0,1,1) : MODULEDEFINITION DateCode_ 123
ModuleCode
Message = "unterminated
(* Counter = Counter + 1; *)
ENDDEF (*BasePicture*);
"""

    hits = find_comments_with_code(text)

    assert len(hits) == 1
    assert hits[0].start_line == 8


# --- comment_code_report.py CommentCodeReport.summary() ---
def test_comment_code_report_summary_no_hits_returns_ok():
    from sattlint.reporting.comment_code_report import CommentCodeReport

    report = CommentCodeReport(basepicture_name="Main", hits=[], issues=[], files_scanned=3)
    assert report.name == "Main"
    result = report.summary()
    assert "Report: Commented-out code" in result
    assert "No code-like comments found" in result


def test_comment_code_report_summary_with_single_line_hit():
    from pathlib import Path

    from sattlint.reporting.comment_code_report import CommentCodeHit, CommentCodeReport

    hit = CommentCodeHit(
        file_path=Path("Main.s"),
        start_line=10,
        end_line=10,
        start_col=0,
        end_col=20,
        indicators=("IF", "THEN"),
        preview="IF x THEN",
        module_path=("BasePicture", "Pump"),
    )
    report = CommentCodeReport(basepicture_name="Main", hits=[hit], issues=[], files_scanned=1)
    result = report.summary()
    assert "Findings:" in result
    assert "BasePicture.Pump (Main.s:10)" in result
    assert "IF, THEN" in result


def test_comment_code_report_summary_with_multi_line_hit():
    from pathlib import Path

    from sattlint.reporting.comment_code_report import CommentCodeHit, CommentCodeReport

    hit = CommentCodeHit(
        file_path=Path("Main.s"),
        start_line=5,
        end_line=8,
        start_col=0,
        end_col=0,
        indicators=(),
        preview="",
        module_path=("BasePicture", "TypeDef:WorkerType"),
    )
    report = CommentCodeReport(basepicture_name="Main", hits=[hit], issues=[], files_scanned=1)
    result = report.summary()
    assert "BasePicture.WorkerType (Main.s:5-8)" in result
    assert "<empty>" in result
    assert "unknown" in result


def test_comment_code_report_summary_with_read_error():
    from sattlint.analyzers.framework import Issue
    from sattlint.reporting.comment_code_report import CommentCodeReport

    err_issue = Issue(kind="comment_code_read_error", message="Could not read Foo.s")
    report = CommentCodeReport(basepicture_name="Main", hits=[], issues=[err_issue], files_scanned=1)
    result = report.summary()
    assert "Read errors:" in result
    assert "Could not read Foo.s" in result


def test_comment_code_report_summary_without_module_path_uses_source_location_only():
    from pathlib import Path

    from sattlint.reporting.comment_code_report import CommentCodeHit, CommentCodeReport

    hit = CommentCodeHit(
        file_path=Path("Main.s"),
        start_line=12,
        end_line=12,
        start_col=1,
        end_col=8,
        indicators=("assignment",),
        preview="Value := 1;",
    )
    report = CommentCodeReport(basepicture_name="Main", hits=[hit], issues=[], files_scanned=1)

    result = report.summary()

    assert "Main.s:12 [assignment] Value := 1;" in result
