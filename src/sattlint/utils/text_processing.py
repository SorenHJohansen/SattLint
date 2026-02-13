from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class CommentCodeHit:
    start_line: int
    end_line: int
    start_col: int
    end_col: int
    text: str
    indicators: tuple[str, ...]


_ASSIGN_RE = re.compile(r"\b[A-Za-z_][A-Za-z0-9_:.]*\s*(?:=|:=)\s*")
_CALL_RE = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*\s*\(")
_CONTROL_RE = re.compile(
    r"\b(IF|THEN|ELSIF|ELSE|ENDIF|FOR|WHILE|REPEAT|UNTIL|CASE|ENDCASE|"
    r"SEQUENCE|ENDSEQUENCE|EQUATIONBLOCK|MODULECODE|LOCALVARIABLES|TYPEDEFINITIONS)\b",
    re.IGNORECASE,
)
_COMPARE_RE = re.compile(r"\b[A-Za-z_][A-Za-z0-9_:.]*\s*(?:<=|>=|<>|<|>)\s*")


def _comment_code_indicators(comment_text: str) -> tuple[str, ...]:
    indicators: list[str] = []
    if _ASSIGN_RE.search(comment_text):
        indicators.append("assignment")
    if _CALL_RE.search(comment_text):
        indicators.append("call")
    if _CONTROL_RE.search(comment_text):
        indicators.append("control")
    if _COMPARE_RE.search(comment_text):
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


def find_comments_with_code(text: str) -> list[CommentCodeHit]:
    """
    Find comment blocks that appear to contain code-like content.

    This operates on raw source text before comments are stripped.
    """
    hits: list[CommentCodeHit] = []
    n = len(text)
    i = 0
    depth = 0
    in_string = False
    string_quote = ""
    line = 1
    col = 1
    comment_start_line = 1
    comment_start_col = 1
    comment_text: list[str] = []

    while i < n:
        ch = text[i]
        next_ch = text[i + 1] if i + 1 < n else None

        if depth == 0:
            if not in_string:
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
                i += 2
                col += 2
                continue
            if ch == "*" and next_ch == ")":
                depth -= 1
                i += 2
                col += 2
                if depth == 0:
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
