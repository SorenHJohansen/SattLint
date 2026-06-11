from pathlib import Path
from types import SimpleNamespace

from sattlint.analyzers import comment_code as comment_code_module
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


def test_comment_code_analysis_copies_context_into_report_hits_and_issue_data(tmp_path: Path):
    source = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0,0,0,1,1) : MODULEDEFINITION DateCode_ 123
ModuleCode
EQUATIONBLOCK MainEq :
    (* OldEquation = Value + 1; *)
ENDEQUATIONBLOCK;
OPENSEQUENCE MainSequence (SeqControl) COORD 0.0, 0.2 OBJSIZE 2.0, 1.68
    SEQSTEP Running
        (* CallSomething(A); *)
ENDOPENSEQUENCE
ENDDEF (*BasePicture*);
"""
    path = tmp_path / "Program.s"
    path.write_text(source, encoding="utf-8")

    report = analyze_comment_code_files([path], basepicture_name="Program")

    assert len(report.hits) == 2
    assert report.hits[0].equation_name == "MainEq"
    assert report.hits[0].sequence_name is None
    assert report.hits[0].step_name is None
    assert report.hits[1].equation_name is None
    assert report.hits[1].sequence_name == "MainSequence"
    assert report.hits[1].step_name == "Running"
    issue0_data = report.issues[0].data
    issue1_data = report.issues[1].data

    assert issue0_data is not None
    assert issue0_data["path"] == str(path)
    assert issue0_data["start_line"] == 8
    assert issue0_data["end_line"] == 8
    assert issue0_data["start_col"] == 5
    assert issue0_data["end_col"] > issue0_data["start_col"]
    assert issue0_data["indicators"] == ("assignment",)
    assert issue0_data["equation_name"] == "MainEq"
    assert issue0_data["sequence_name"] is None
    assert issue0_data["step_name"] is None

    assert issue1_data is not None
    assert issue1_data["path"] == str(path)
    assert issue1_data["start_line"] == 12
    assert issue1_data["end_line"] == 12
    assert issue1_data["start_col"] == 9
    assert issue1_data["end_col"] > issue1_data["start_col"]
    assert issue1_data["indicators"] == ("call",)
    assert issue1_data["equation_name"] is None
    assert issue1_data["sequence_name"] == "MainSequence"
    assert issue1_data["step_name"] == "Running"


def test_comment_code_analysis_skips_missing_and_unsupported_paths(tmp_path: Path):
    txt_path = tmp_path / "Notes.txt"
    txt_path.write_text("(* Counter = Counter + 1; *)", encoding="utf-8")

    report = analyze_comment_code_files([tmp_path / "Missing.s", txt_path], basepicture_name="Program")

    assert report.files_scanned == 0
    assert report.hits == []
    assert report.issues == []


def test_comment_code_analysis_reports_read_errors(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "Broken.s"
    path.write_text("placeholder", encoding="utf-8")

    def _raise_read_error(_path: Path) -> str:
        raise OSError("boom")

    monkeypatch.setattr(comment_code_module, "_read_source_text", _raise_read_error)

    report = analyze_comment_code_files([path], basepicture_name="Program")

    assert report.files_scanned == 1
    assert report.hits == []
    assert len(report.issues) == 1
    assert report.issues[0].kind == "comment_code_read_error"
    assert report.issues[0].message == "Broken.s: boom"


def test_comment_code_read_source_text_preprocesses_compressed(monkeypatch, tmp_path: Path) -> None:
    path = tmp_path / "Compressed.s"
    path.write_text("compressed", encoding="utf-8")

    monkeypatch.setattr(comment_code_module, "is_compressed", lambda text: text == "compressed")
    monkeypatch.setattr(comment_code_module, "preprocess_sl_text", lambda text: ("expanded", {"meta": text}))

    assert comment_code_module._read_source_text(path) == "expanded"


def test_comment_code_comment_preview_handles_empty_and_truncates() -> None:
    assert comment_code_module._comment_preview("\n   \n") == ""

    preview = comment_code_module._comment_preview("\n  " + "A" * 140)

    assert preview == ("A" * 117) + "..."


def test_comment_code_format_line_range_handles_single_line_and_range() -> None:
    assert comment_code_module._format_line_range(4, 4) == "4"
    assert comment_code_module._format_line_range(4, 6) == "4-6"


def test_analyze_comment_code_handles_missing_graph() -> None:
    context = SimpleNamespace(
        base_picture=SimpleNamespace(header=SimpleNamespace(name="Program")),
        graph=None,
    )

    report = comment_code_module.analyze_comment_code(context)

    assert report.basepicture_name == "Program"
    assert report.files_scanned == 0
    assert report.hits == []


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
    assert hits[0].equation_name == "Main"
    assert hits[0].sequence_name is None
    assert hits[0].step_name is None


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
    assert hits[0].sequence_name == "MySeq"
    assert hits[0].step_name is None


def test_sequence_step_comments_track_step_name():
    text = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0,0,0,1,1) : MODULEDEFINITION DateCode_ 123
ModuleCode
OPENSEQUENCE MainSequence (SeqControl) COORD 0.0, 0.2 OBJSIZE 2.0, 1.68
    SEQINITSTEP InitStep
        (* Counter = Counter + 1; *)
    SEQTRANSITION Next WAIT_FOR Ready
    SEQSTEP Running
        (* CallSomething(A); *)
ENDOPENSEQUENCE
ENDDEF (*BasePicture*);
"""

    hits = find_comments_with_code(text)

    assert len(hits) == 2
    assert hits[0].sequence_name == "MainSequence"
    assert hits[0].step_name == "InitStep"
    assert hits[0].equation_name is None
    assert hits[1].sequence_name == "MainSequence"
    assert hits[1].step_name == "Running"


def test_sequence_transition_comments_clear_step_name():
    text = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0,0,0,1,1) : MODULEDEFINITION DateCode_ 123
ModuleCode
OPENSEQUENCE MainSequence (SeqControl) COORD 0.0, 0.2 OBJSIZE 2.0, 1.68
    SEQSTEP Running
        Active:
            DoNewThing();
    SEQTRANSITION Next WAIT_FOR Ready
    (* OldTransitionLogic = True; *)
ENDOPENSEQUENCE
ENDDEF (*BasePicture*);
"""

    hits = find_comments_with_code(text)

    assert len(hits) == 1
    assert hits[0].sequence_name == "MainSequence"
    assert hits[0].step_name is None


def test_nested_module_code_restores_outer_sequence_context_after_inner_module():
    text = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0,0,0,1,1) : MODULEDEFINITION DateCode_ 123
SUBMODULES
    Sub1 Invocation (0,0,0,1,1) : MODULEDEFINITION DateCode_ 456
    ModuleCode
        OPENSEQUENCE OuterSequence (SeqControl) COORD 0.0, 0.2 OBJSIZE 2.0, 1.68
            SEQSTEP OuterStep
                (* OuterCode = True; *)
            SUBMODULES
                Sub2 Invocation (0,0,0,1,1) : MODULEDEFINITION DateCode_ 789
                ModuleCode
                    EQUATIONBLOCK InnerEquation :
                        (* InnerCode = True; *)
                    ENDEQUATIONBLOCK;
                ENDDEF (*Sub2*);
            (* OuterStillApplies = True; *)
        ENDOPENSEQUENCE
    ENDDEF (*Sub1*);
ENDDEF (*BasePicture*);
"""

    hits = find_comments_with_code(text)

    assert len(hits) == 3
    assert hits[0].sequence_name == "OuterSequence"
    assert hits[0].step_name == "OuterStep"
    assert hits[1].equation_name == "InnerEquation"
    assert hits[1].sequence_name is None
    assert hits[2].sequence_name == "OuterSequence"
    assert hits[2].step_name == "OuterStep"


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
    from sattlint.reporting.comment_code_report import CommentCodeReport  # noqa: PLC0415

    report = CommentCodeReport(basepicture_name="Main", hits=[], issues=[], files_scanned=3)
    assert report.name == "Main"
    result = report.summary()
    assert "Report: Commented-out code" in result
    assert "No code-like comments found" in result


def test_comment_code_report_summary_with_single_line_hit():
    from pathlib import Path  # noqa: PLC0415

    from sattlint.reporting.comment_code_report import CommentCodeHit, CommentCodeReport  # noqa: PLC0415

    hit = CommentCodeHit(
        file_path=Path("Main.s"),
        start_line=10,
        end_line=10,
        start_col=0,
        end_col=20,
        indicators=("IF", "THEN"),
        preview="IF x THEN",
        module_path=("BasePicture", "Pump"),
        sequence_name="MainSequence",
        step_name="Running",
    )
    report = CommentCodeReport(basepicture_name="Main", hits=[hit], issues=[], files_scanned=1)
    result = report.summary()
    assert "Findings:" in result
    assert "BasePicture.Pump (Main.s:10) [sequence=MainSequence | step=Running]" in result
    assert "IF, THEN" in result


def test_comment_code_report_summary_with_multi_line_hit():
    from pathlib import Path  # noqa: PLC0415

    from sattlint.reporting.comment_code_report import CommentCodeHit, CommentCodeReport  # noqa: PLC0415

    hit = CommentCodeHit(
        file_path=Path("Main.s"),
        start_line=5,
        end_line=8,
        start_col=0,
        end_col=0,
        indicators=(),
        preview="",
        module_path=("BasePicture", "TypeDef:WorkerType"),
        equation_name="MainEq",
    )
    report = CommentCodeReport(basepicture_name="Main", hits=[hit], issues=[], files_scanned=1)
    result = report.summary()
    assert "BasePicture.WorkerType (Main.s:5-8) [equation=MainEq]" in result
    assert "<empty>" in result
    assert "unknown" in result


def test_comment_code_report_summary_with_read_error():
    from sattlint.analyzers.framework import Issue  # noqa: PLC0415
    from sattlint.reporting.comment_code_report import CommentCodeReport  # noqa: PLC0415

    err_issue = Issue(kind="comment_code_read_error", message="Could not read Foo.s")
    report = CommentCodeReport(basepicture_name="Main", hits=[], issues=[err_issue], files_scanned=1)
    result = report.summary()
    assert "Read errors:" in result
    assert "Could not read Foo.s" in result


def test_comment_code_report_summary_without_module_path_uses_source_location_only():
    from pathlib import Path  # noqa: PLC0415

    from sattlint.reporting.comment_code_report import CommentCodeHit, CommentCodeReport  # noqa: PLC0415

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


def test_comment_code_report_summary_without_module_path_shows_sequence_context():
    from pathlib import Path  # noqa: PLC0415

    from sattlint.reporting.comment_code_report import CommentCodeHit, CommentCodeReport  # noqa: PLC0415

    hit = CommentCodeHit(
        file_path=Path("Main.s"),
        start_line=12,
        end_line=12,
        start_col=1,
        end_col=8,
        indicators=("assignment",),
        preview="Value := 1;",
        sequence_name="MainSequence",
        step_name="Running",
    )
    report = CommentCodeReport(basepicture_name="Main", hits=[hit], issues=[], files_scanned=1)

    result = report.summary()

    assert "Main.s:12 [sequence=MainSequence | step=Running] [assignment] Value := 1;" in result
