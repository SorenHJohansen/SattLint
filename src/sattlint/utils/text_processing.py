from __future__ import annotations

import re
from dataclasses import dataclass
from functools import cache
from typing import TYPE_CHECKING, Any, cast

from lark.exceptions import UnexpectedInput

from sattline_parser.api import build_lark_parser

from ._comment_scanning import scan_comments_with_code, scan_disallowed_comments, strip_sl_comments_impl

if TYPE_CHECKING:
    from lark import Lark


@dataclass(frozen=True)
class CommentCodeHit:
    start_line: int
    end_line: int
    start_col: int
    end_col: int
    text: str
    indicators: tuple[str, ...]
    module_path: tuple[str, ...] = ()


@dataclass(frozen=True)
class CommentPlacementViolation:
    start_line: int
    start_col: int
    text: str


# Regex patterns for fast filtering (syntax hints, not definitive)
_ASSIGN_RE = re.compile(r"\b[A-Za-z_][A-Za-z0-9_:.]*\s*(?::=|=(?!=))\s*")
_CALL_RE = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*\s*\([^()\n]*\S[^()\n]*\)")
_CONTROL_RE = re.compile(
    r"\b(IF|THEN|ELSIF|ELSE|ENDIF|FOR|WHILE|REPEAT|UNTIL|CASE|ENDCASE|"
    r"SEQUENCE|ENDSEQUENCE|EQUATIONBLOCK|MODULECODE|LOCALVARIABLES|TYPEDEFINITIONS)\b",
    re.IGNORECASE,
)
_COMPARE_RE = re.compile(r"\b[A-Za-z_][A-Za-z0-9_:.]*\s*(?:<=|>=|<>|<|>)\s*")


@cache
def _get_statement_parser() -> Lark:
    return build_lark_parser(start="statement", propagate_positions=False)


@cache
def _get_expression_parser() -> Lark:
    return build_lark_parser(start="expression", propagate_positions=False)


def _is_valid_code_via_grammar(text: str) -> bool:
    """
    Check if text is valid SattLine code by trying to parse it.

    Returns True if the text parses as a statement or expression,
    AND contains actual code syntax (not just a single identifier).
    """
    text = text.strip()
    if not text:
        return False

    # Require evidence of actual code syntax, not just a single word
    # Single identifiers like "FUNCTIONS" or "Counter" are valid expressions
    # but don't indicate commented-out code
    has_code_syntax = (
        "=" in text  # Assignment or comparison
        or ";" in text  # Statement terminator
        or "(" in text  # Function call or grouping
        or ":=" in text  # Assignment operator
    )

    if not has_code_syntax:
        # Single word or simple phrase - likely documentation, not code
        return False

    # Try parsing as a statement first
    statement_is_valid = False
    try:
        parser = _get_statement_parser()
        cast(Any, parser).parse(text)
        statement_is_valid = True
    except UnexpectedInput:
        statement_is_valid = False

    if statement_is_valid:
        return True

    # Try parsing as an expression
    expression_is_valid = False
    try:
        parser = _get_expression_parser()
        cast(Any, parser).parse(text)
        expression_is_valid = True
    except UnexpectedInput:
        expression_is_valid = False

    return expression_is_valid


def _has_code_syntax_hints(comment_text: str) -> bool:
    """
    Fast regex check for code-like syntax patterns.
    Returns True if the comment contains hints of code syntax.
    """
    has_assignment = _ASSIGN_RE.search(comment_text) is not None
    has_call = _CALL_RE.search(comment_text) is not None
    has_control = _CONTROL_RE.search(comment_text) is not None
    has_comparison = _COMPARE_RE.search(comment_text) is not None
    has_semicolon = ";" in comment_text

    # Need at least one strong indicator
    has_strong = has_assignment or has_call or has_comparison

    if not has_strong and not has_control:
        return False

    # If we have semicolons and any indicator, it's likely code
    if has_semicolon and (has_strong or has_control):
        return True

    # Without semicolons, need stronger evidence
    return bool(has_strong)


def _extract_code_candidates(comment_text: str) -> list[str]:
    """
    Extract potential code snippets from comment text.

    Tries to find individual statements or expressions that might be code.
    Handles control structures (IF/THEN/ENDIF) that span multiple lines.
    """
    candidates: list[str] = []
    text = comment_text.strip()

    if not text:
        return candidates

    # Always try the full text first (for control structures, multi-line statements)
    candidates.append(text)

    # If control keywords are present, the whole thing might be a control structure
    # Don't split these - they're already added above
    control_keywords = [
        "IF",
        "THEN",
        "ENDIF",
        "FOR",
        "ENDFOR",
        "WHILE",
        "ENDWHILE",
        "REPEAT",
        "UNTIL",
        "CASE",
        "ENDCASE",
    ]
    has_control_structure = any(kw in text.upper() for kw in control_keywords)

    if has_control_structure:
        # For control structures, also try line-by-line extraction
        # in case there are multiple statements
        for line in text.splitlines():
            line = line.strip()
            if line and len(line) > 3:
                candidates.append(line)
    elif ";" in text:
        # Simple statements separated by semicolons
        # Split by semicolons but keep the semicolon with each part
        parts = text.split(";")
        for _i, part in enumerate(parts[:-1]):
            candidate = part.strip() + ";"
            if len(candidate) > 5:  # Minimum length for valid code
                candidates.append(candidate)
        # Last part (after final semicolon) might be incomplete
        last = parts[-1].strip()
        if last and len(last) > 5:
            candidates.append(last)

    return candidates


def _comment_code_indicators(comment_text: str) -> tuple[str, ...]:
    """
    Determine if comment contains code using hybrid approach:
    1. Fast regex filtering to skip obvious non-code
    2. Grammar parsing for accurate detection
    """
    # Step 1: Fast regex filter
    if not _has_code_syntax_hints(comment_text):
        return ()

    # Step 2: Try to extract and validate code candidates via grammar
    indicators: list[str] = []

    # Check what syntax hints we have
    has_assignment = _ASSIGN_RE.search(comment_text) is not None
    has_call = _CALL_RE.search(comment_text) is not None
    has_control = _CONTROL_RE.search(comment_text) is not None
    has_comparison = _COMPARE_RE.search(comment_text) is not None

    # Extract potential code snippets
    candidates = _extract_code_candidates(comment_text)

    # Try to validate each candidate with the grammar
    valid_code_found = False
    for candidate in candidates:
        if _is_valid_code_via_grammar(candidate):
            valid_code_found = True
            break

    if not valid_code_found:
        # No valid code found via grammar parsing
        # This filters out documentation that describes code
        return ()

    # Valid code confirmed - record what patterns matched
    if has_assignment:
        indicators.append("assignment")
    if has_call:
        indicators.append("call")
    if has_control:
        indicators.append("control")
    if has_comparison:
        indicators.append("comparison")

    return tuple(indicators)


def _advance_position(
    ch: str,
    next_ch: str | None,
    line: int,
    col: int,
) -> tuple[int, int, int]:
    if ch == "\r":
        line += 1
        col = 1
        if next_ch == "\n":
            return line, col, 1
        return line, col, 0
    if ch == "\n":
        line += 1
        col = 1
        return line, col, 0
    return line, col + 1, 0


def _is_at_keyword(text: str, pos: int, keyword: str) -> bool:
    """Check if text at position starts with keyword (case-insensitive, word boundary)."""
    if pos + len(keyword) > len(text):
        return False
    if pos > 0:
        before_char = text[pos - 1]
        if before_char.isalnum() or before_char == "_":
            return False
    substr = text[pos : pos + len(keyword)]
    if substr.casefold() != keyword.casefold():
        return False
    # Check word boundary after
    after_pos = pos + len(keyword)
    if after_pos < len(text):
        after_char = text[after_pos]
        if after_char.isalnum() or after_char == "_":
            return False
    return True


def _is_identifier_start(ch: str) -> bool:
    return ch.isalpha() or ch == "_"


def _is_identifier_char(ch: str) -> bool:
    return ch.isalnum() or ch == "_"


def _consume_identifier(text: str, pos: int) -> tuple[str, int]:
    end = pos + 1
    while end < len(text) and _is_identifier_char(text[end]):
        end += 1
    return text[pos:end], end


def _is_valid_enddef_label_comment(comment_text: str) -> bool:
    stripped = comment_text.strip()
    return bool(stripped) and "\n" not in stripped and "\r" not in stripped


def find_disallowed_comments(text: str) -> list[CommentPlacementViolation]:
    """Find comments that appear outside equation and sequence blocks.

    Inside ModuleCode, freestanding comments before the first EQUATIONBLOCK or
    SEQUENCE/OPENSEQUENCE block are rejected. Conventional ENDDEF label
    comments such as ``ENDDEF (*BasePicture*);`` remain allowed.

    Comments outside ModuleCode are ignored.
    """
    return scan_disallowed_comments(
        text,
        advance_position=_advance_position,
        is_at_keyword=_is_at_keyword,
        is_valid_enddef_label_comment=_is_valid_enddef_label_comment,
        violation_factory=CommentPlacementViolation,
    )


def find_comments_with_code(text: str) -> list[CommentCodeHit]:
    """
    Find comment blocks that appear to contain code-like content.

    This operates on raw source text before comments are stripped.
    Uses a hybrid approach: regex for fast filtering, grammar parsing for accuracy.
    Only checks comments that appear inside ModuleCode sections.
    """
    return scan_comments_with_code(
        text,
        advance_position=_advance_position,
        is_identifier_start=_is_identifier_start,
        consume_identifier=_consume_identifier,
        comment_code_indicators=_comment_code_indicators,
        hit_factory=CommentCodeHit,
    )


def strip_sl_comments(text: str) -> str:
    """
    Remove nested comments of the form (* ... *) from the input text.
    Preserves original line numbers by emitting newline characters
    encountered inside comments and in the whitespace after a comment.
    Also removes a single semicolon that immediately follows a comment
    (allowing intervening whitespace/newlines), while preserving those
    whitespace/newlines.

    Additionally:
    - Does NOT treat (* or *) as comment delimiters when they appear inside
      single- or double-quoted strings.
    - Inside strings, supports doubled quotes ("" and '') and backslash escapes.
    - A newline ends a string if it hasn't been closed yet. Both LF and CR will
      terminate the string; CRLF is preserved as-is.

    Assumptions:
    - Comments can be nested and may contain newlines.
    - Every comment is closed before EOF.
    """
    return strip_sl_comments_impl(text)
