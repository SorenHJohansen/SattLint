from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lark import Lark
    from lark.exceptions import LarkError


@dataclass(frozen=True)
class CommentCodeHit:
    start_line: int
    end_line: int
    start_col: int
    end_col: int
    text: str
    indicators: tuple[str, ...]


# Regex patterns for fast filtering (syntax hints, not definitive)
_ASSIGN_RE = re.compile(r"\b[A-Za-z_][A-Za-z0-9_:.]*\s*(?::=|=(?!=))\s*")
_CALL_RE = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*\s*\([^()\n]*\S[^()\n]*\)")
_CONTROL_RE = re.compile(
    r"\b(IF|THEN|ELSIF|ELSE|ENDIF|FOR|WHILE|REPEAT|UNTIL|CASE|ENDCASE|"
    r"SEQUENCE|ENDSEQUENCE|EQUATIONBLOCK|MODULECODE|LOCALVARIABLES|TYPEDEFINITIONS)\b",
    re.IGNORECASE,
)
_COMPARE_RE = re.compile(r"\b[A-Za-z_][A-Za-z0-9_:.]*\s*(?:<=|>=|<>|<|>)\s*")

# Lazy-loaded grammar parsers for accurate code detection
_statement_parser: Lark | None = None
_expression_parser: Lark | None = None


def _get_grammar_text() -> str:
    """Load and format the SattLine grammar with constants."""
    from ..grammar import constants

    base_dir = Path(__file__).resolve().parent.parent
    grammar_path = base_dir / "grammar" / "sattline.lark"
    grammar_template = grammar_path.read_text(encoding="utf-8")

    # Substitute grammar constants
    substitutions = {
        name: getattr(constants, name)
        for name in dir(constants)
        if name.startswith("GRAMMAR_VALUE_") or name.startswith("GRAMMAR_REGEX_")
    }
    return grammar_template.format(**substitutions)


def _get_statement_parser() -> Lark:
    """Get or create a parser for SattLine statements."""
    global _statement_parser
    if _statement_parser is None:
        from lark import Lark

        grammar = _get_grammar_text()
        _statement_parser = Lark(grammar, start="statement", parser="lalr")
    return _statement_parser


def _get_expression_parser() -> Lark:
    """Get or create a parser for SattLine expressions."""
    global _expression_parser
    if _expression_parser is None:
        from lark import Lark

        grammar = _get_grammar_text()
        _expression_parser = Lark(grammar, start="expression", parser="lalr")
    return _expression_parser


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
    try:
        parser = _get_statement_parser()
        parser.parse(text)
        return True
    except Exception:
        pass

    # Try parsing as an expression
    try:
        parser = _get_expression_parser()
        parser.parse(text)
        return True
    except Exception:
        pass

    return False


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
    if has_strong:
        return True

    return False


def _extract_code_candidates(comment_text: str) -> list[str]:
    """
    Extract potential code snippets from comment text.

    Tries to find individual statements or expressions that might be code.
    Handles control structures (IF/THEN/ENDIF) that span multiple lines.
    """
    candidates = []
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
        for i, part in enumerate(parts[:-1]):
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


def find_comments_with_code(text: str) -> list[CommentCodeHit]:
    """
    Find comment blocks that appear to contain code-like content.

    This operates on raw source text before comments are stripped.
    Uses a hybrid approach: regex for fast filtering, grammar parsing for accuracy.
    Only checks comments that appear inside ModuleCode sections.
    """
    hits: list[CommentCodeHit] = []
    n = len(text)
    i = 0
    depth = 0  # Comment nesting depth
    in_string = False
    string_quote = ""
    line = 1
    col = 1
    comment_start_line = 1
    comment_start_col = 1
    comment_text: list[str] = []

    # Track ModuleCode section state
    in_module_code = False
    module_code_depth = 0  # Track nesting level when ModuleCode was seen

    while i < n:
        ch = text[i]
        next_ch = text[i + 1] if i + 1 < n else None

        if depth == 0:
            if not in_string:
                # Check for ModuleCode keyword (only when not in comments)
                if not in_module_code and _is_at_keyword(text, i, "ModuleCode"):
                    in_module_code = True
                    module_code_depth = 0
                    i += len("ModuleCode")
                    col += len("ModuleCode")
                    continue

                # Check for ENDDEF to exit ModuleCode section
                if in_module_code and _is_at_keyword(text, i, "ENDDEF"):
                    # Only exit if we're at the same nesting level as ModuleCode
                    if module_code_depth == 0:
                        in_module_code = False
                    i += len("ENDDEF")
                    col += len("ENDDEF")
                    continue

                if ch == '"' or ch == "'":
                    in_string = True
                    string_quote = ch
                    line, col, extra = _advance_position(ch, next_ch, line, col)
                    i += 1 + extra
                    continue
                if ch == "(" and next_ch == "*":
                    depth = 1
                    comment_start_line = line
                    comment_start_col = col
                    i += 2
                    col += 2
                    continue
            else:
                if ch == "\n" or ch == "\r":
                    line, col, extra = _advance_position(ch, next_ch, line, col)
                    i += 1 + extra
                    in_string = False
                    string_quote = ""
                    continue
                if ch == string_quote:
                    if next_ch == string_quote:
                        line, col, extra = _advance_position(ch, next_ch, line, col)
                        i += 1 + extra
                        line, col, extra = _advance_position(next_ch, None, line, col)
                        i += 1 + extra
                        continue
                    in_string = False
                    string_quote = ""
                elif ch == "\\":
                    line, col, extra = _advance_position(ch, next_ch, line, col)
                    i += 1 + extra
                    if next_ch is not None:
                        line, col, extra = _advance_position(next_ch, None, line, col)
                        i += 1 + extra
                    continue

            line, col, extra = _advance_position(ch, next_ch, line, col)
            i += 1 + extra
        else:
            if ch == "(" and next_ch == "*":
                depth += 1
                module_code_depth += 1  # Track nesting inside ModuleCode
                i += 2
                col += 2
                continue
            if ch == "*" and next_ch == ")":
                depth -= 1
                if depth > 0:
                    module_code_depth -= 1
                i += 2
                col += 2
                if depth == 0:
                    # Comment closed - only check for code if inside ModuleCode
                    if in_module_code:
                        indicators = _comment_code_indicators("".join(comment_text))
                        if indicators:
                            hits.append(
                                CommentCodeHit(
                                    start_line=comment_start_line,
                                    end_line=line,
                                    start_col=comment_start_col,
                                    end_col=col,
                                    text="".join(comment_text),
                                    indicators=indicators,
                                )
                            )
                    comment_text = []
                continue

            comment_text.append(ch)
            line, col, extra = _advance_position(ch, next_ch, line, col)
            i += 1 + extra

    return hits


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
    n = len(text)
    i = 0
    depth = 0
    in_string = False
    string_quote = ""  # either '"' or "'"
    out = []

    while i < n:
        ch = text[i]

        if depth == 0:
            if not in_string:
                # Enter string?
                if ch == '"' or ch == "'":
                    in_string = True
                    string_quote = ch
                    out.append(ch)
                    i += 1
                    continue
                # Enter comment?
                if ch == "(" and i + 1 < n and text[i + 1] == "*":
                    depth = 1
                    i += 2
                    continue
                # Normal code
                out.append(ch)
                i += 1
            else:
                # Inside string: copy literally, but end on newline
                if ch == "\n" or ch == "\r":
                    # Newline ends the (possibly unterminated) string
                    out.append(ch)
                    in_string = False
                    string_quote = ""
                    i += 1
                elif ch == string_quote:
                    # Support doubled quote within the same kind of string
                    if i + 1 < n and text[i + 1] == string_quote:
                        out.append(string_quote)
                        out.append(string_quote)
                        i += 2
                    else:
                        out.append(string_quote)
                        i += 1
                        in_string = False
                        string_quote = ""
                elif ch == "\\":
                    # Preserve backslash escape and following char (if any)
                    out.append("\\")
                    if i + 1 < n:
                        out.append(text[i + 1])
                        i += 2
                    else:
                        i += 1
                else:
                    out.append(ch)
                    i += 1
        else:
            # Inside comment: manage nesting and closing; preserve only CR/LF
            if ch == "(" and i + 1 < n and text[i + 1] == "*":
                depth += 1
                i += 2
            elif ch == "*" and i + 1 < n and text[i + 1] == ")":
                depth -= 1
                i += 2
                if depth == 0:
                    # Just closed the outermost comment: emit following whitespace/newlines,
                    # but remove one optional semicolon.
                    j = i
                    while j < n and text[j] in (" ", "\t", "\r", "\n"):
                        out.append(text[j])  # preserve whitespace/newlines
                        j += 1
                    if j < n and text[j] == ";":
                        j += 1  # skip a single semicolon
                    i = j
            else:
                if ch == "\n" or ch == "\r":
                    out.append(ch)
                i += 1

    return "".join(out)
