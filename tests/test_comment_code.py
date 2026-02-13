from pathlib import Path

from sattlint.analyzers.comment_code import analyze_comment_code_files
from sattlint.utils.text_processing import find_comments_with_code


def test_find_comments_with_code_detects_assignments_and_calls():
    text = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
(* Counter = Counter + 1; *)
(* CallSomething(A, B); *)
(* Just a comment with no code *)
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
(* IF Start THEN
    Running = True;
ENDIF; *)
(* Note: nothing special here. *)
"""
    path = tmp_path / "Program.s"
    path.write_text(source, encoding="utf-8")

    report = analyze_comment_code_files([path], basepicture_name="Program")

    assert report.files_scanned == 1
    assert len(report.hits) == 1
    assert report.hits[0].file_path.name == "Program.s"
    assert "control" in report.hits[0].indicators
