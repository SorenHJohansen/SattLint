# pyright: reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownLambdaType=false, reportPrivateUsage=false
from lark.exceptions import UnexpectedInput

from sattlint.utils import text_processing


def test_text_processing_is_at_keyword_honors_boundaries() -> None:
    assert text_processing._is_at_keyword("ModuleCode", 0, "ModuleCode") is True
    assert text_processing._is_at_keyword("ModuleCodes", 0, "ModuleCode") is False
    assert text_processing._is_at_keyword("XModuleCode", 1, "ModuleCode") is False


def test_text_processing_advance_position_handles_crlf_and_lf() -> None:
    assert text_processing._advance_position("\r", "\n", 1, 1) == (2, 1, 1)
    assert text_processing._advance_position("\r", None, 1, 1) == (2, 1, 0)
    assert text_processing._advance_position("\n", None, 1, 5) == (2, 1, 0)
    assert text_processing._advance_position("A", None, 3, 4) == (3, 5, 0)


def test_text_processing_is_valid_code_via_grammar_handles_blank_and_expression_fallback(monkeypatch) -> None:
    class _FakeUnexpectedInput(UnexpectedInput):
        def __init__(self) -> None:
            pass

    class _FailParser:
        def parse(self, _text: str) -> None:
            raise _FakeUnexpectedInput()

    class _PassParser:
        def parse(self, _text: str) -> None:
            return None

    monkeypatch.setattr(text_processing, "_get_statement_parser", lambda: _FailParser())
    monkeypatch.setattr(text_processing, "_get_expression_parser", lambda: _PassParser())

    assert text_processing._is_valid_code_via_grammar("   ") is False
    assert text_processing._is_valid_code_via_grammar("(Counter)") is True


def test_text_processing_extract_code_candidates_splits_semicolon_sequences() -> None:
    candidates = text_processing._extract_code_candidates("Counter := Counter + 1; CallSomething(A);")

    assert "Counter := Counter + 1; CallSomething(A);" in candidates
    assert "Counter := Counter + 1;" in candidates
    assert "CallSomething(A);" in candidates


def test_text_processing_extract_code_candidates_handles_empty_and_trailing_fragment() -> None:
    assert text_processing._extract_code_candidates("   ") == []

    candidates = text_processing._extract_code_candidates("Counter := Counter + 1; trailing branch")

    assert "trailing branch" in candidates


def test_text_processing_comment_code_indicators_returns_empty_when_no_valid_code(monkeypatch) -> None:
    monkeypatch.setattr(text_processing, "_is_valid_code_via_grammar", lambda _text: False)

    indicators = text_processing._comment_code_indicators("Counter := Counter + 1;")

    assert indicators == ()


def test_text_processing_comment_code_indicators_returns_assignment_and_call_when_valid(monkeypatch) -> None:
    monkeypatch.setattr(text_processing, "_is_valid_code_via_grammar", lambda _text: True)

    indicators = text_processing._comment_code_indicators("Counter := CallSomething(A);")

    assert "assignment" in indicators
    assert "call" in indicators


def test_strip_sl_comments_removes_nested_comments_and_optional_semicolon() -> None:
    stripped = text_processing.strip_sl_comments("Value = 1; (* outer\n(* inner *)\ncomment *)\n   ;\nNext = 2;\n")

    assert stripped == "Value = 1; \n\n\n   \nNext = 2;\n"


def test_strip_sl_comments_preserves_strings_with_comment_tokens_and_backslashes() -> None:
    stripped = text_processing.strip_sl_comments(
        'Message = "(* keep *) and ""quoted"" text";\nPathValue = ".\\\\Temp\\\\(* keep *)";\n(* remove me *) ;\n'
    )

    assert '"(* keep *) and ""quoted"" text"' in stripped
    assert '".\\\\Temp\\\\(* keep *)"' in stripped
    assert "remove me" not in stripped
    assert stripped.endswith(" \n")


def test_strip_sl_comments_ends_unterminated_string_at_newline_before_comment() -> None:
    stripped = text_processing.strip_sl_comments('Message = "unterminated\n(* remove me *)\nNext = 2;\n')

    assert stripped == 'Message = "unterminated\n\nNext = 2;\n'


def test_strip_sl_comments_preserves_terminal_backslash_inside_string() -> None:
    assert text_processing.strip_sl_comments('"abc\\') == '"abc\\'
