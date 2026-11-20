import pytest
from lark.exceptions import UnexpectedInput

from sattlint.utils import text_processing

# pyright: reportPrivateUsage=false


def _always_valid(_text: str) -> bool:
    return True


def _never_valid(_text: str) -> bool:
    return False


def test_text_processing_advance_position_handles_crlf_and_lf() -> None:
    assert text_processing._advance_position("\r", "\n", 1, 1) == (2, 1, 1)
    assert text_processing._advance_position("\r", None, 1, 1) == (2, 1, 0)
    assert text_processing._advance_position("\n", None, 1, 5) == (2, 1, 0)
    assert text_processing._advance_position("A", None, 3, 4) == (3, 5, 0)


def test_text_processing_is_valid_code_via_grammar_handles_blank_and_expression_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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


def test_text_processing_comment_code_indicators_returns_empty_when_no_valid_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(text_processing, "_is_valid_code_via_grammar", _never_valid)

    indicators = text_processing._comment_code_indicators("Counter := Counter + 1;")

    assert indicators == ()


def test_text_processing_comment_code_indicators_ignores_template_ellipsis(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(text_processing, "_is_valid_code_via_grammar", _always_valid)

    assert text_processing._comment_code_indicators("IF NOT StateSequence.Reset THEN ... ENDIF;") == ()
    assert text_processing._comment_code_indicators("IF NOT StateSequence.Reset THEN \u2026 ENDIF;") == ()


def test_text_processing_comment_code_indicators_keeps_code_with_stray_ellipsis(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(text_processing, "_is_valid_code_via_grammar", _always_valid)

    indicators = text_processing._comment_code_indicators("Counter := OldValue ... ;")

    assert "assignment" in indicators


def test_text_processing_comment_code_indicators_returns_assignment_and_call_when_valid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(text_processing, "_is_valid_code_via_grammar", _always_valid)

    indicators = text_processing._comment_code_indicators("Counter := CallSomething(A);")

    assert "assignment" in indicators
    assert "call" in indicators
