from __future__ import annotations

from collections.abc import Callable


def scan_disallowed_comments[TViolation](
    text: str,
    *,
    advance_position: Callable[[str, str | None, int, int], tuple[int, int, int]],
    is_at_keyword: Callable[[str, int, str], bool],
    is_valid_enddef_label_comment: Callable[[str], bool],
    violation_factory: Callable[[int, int, str], TViolation],
) -> list[TViolation]:
    violations: list[TViolation] = []
    n = len(text)
    i = 0
    depth = 0
    in_string = False
    string_quote = ""
    line = 1
    col = 1
    in_module_code = False
    awaiting_first_block = False
    pending_enddef_label = False
    comment_start_line = 1
    comment_start_col = 1
    comment_text: list[str] = []
    comment_allowed_by_enddef = False

    while i < n:
        ch = text[i]
        next_ch = text[i + 1] if i + 1 < n else None

        if depth == 0:
            if not in_string:
                if pending_enddef_label and not ch.isspace() and not (ch == "(" and next_ch == "*"):
                    pending_enddef_label = False

                if is_at_keyword(text, i, "ModuleCode"):
                    in_module_code = True
                    awaiting_first_block = True
                    pending_enddef_label = False
                    i += len("ModuleCode")
                    col += len("ModuleCode")
                    continue

                if in_module_code and is_at_keyword(text, i, "EQUATIONBLOCK"):
                    awaiting_first_block = False
                    i += len("EQUATIONBLOCK")
                    col += len("EQUATIONBLOCK")
                    pending_enddef_label = False
                    continue

                if in_module_code and is_at_keyword(text, i, "OPENSEQUENCE"):
                    awaiting_first_block = False
                    i += len("OPENSEQUENCE")
                    col += len("OPENSEQUENCE")
                    pending_enddef_label = False
                    continue

                if in_module_code and is_at_keyword(text, i, "SEQUENCE"):
                    awaiting_first_block = False
                    i += len("SEQUENCE")
                    col += len("SEQUENCE")
                    pending_enddef_label = False
                    continue

                if is_at_keyword(text, i, "ENDDEF"):
                    if in_module_code:
                        awaiting_first_block = False
                        in_module_code = False
                    pending_enddef_label = True
                    i += len("ENDDEF")
                    col += len("ENDDEF")
                    continue

                if ch == '"' or ch == "'":
                    in_string = True
                    string_quote = ch
                    line, col, extra = advance_position(ch, next_ch, line, col)
                    i += 1 + extra
                    continue

                if ch == "(" and next_ch == "*":
                    comment_start_line = line
                    comment_start_col = col
                    comment_text = []
                    comment_allowed_by_enddef = pending_enddef_label
                    pending_enddef_label = False
                    if in_module_code and awaiting_first_block and not comment_allowed_by_enddef:
                        violations.append(violation_factory(comment_start_line, comment_start_col, ""))
                    depth = 1
                    i += 2
                    col += 2
                    continue
            else:
                if ch == "\n" or ch == "\r":
                    line, col, extra = advance_position(ch, next_ch, line, col)
                    i += 1 + extra
                    in_string = False
                    string_quote = ""
                    continue
                if ch == string_quote:
                    if next_ch == string_quote:
                        line, col, extra = advance_position(ch, next_ch, line, col)
                        i += 1 + extra
                        if next_ch is not None:
                            line, col, extra = advance_position(next_ch, None, line, col)
                            i += 1 + extra
                        continue
                    in_string = False
                    string_quote = ""
                elif ch == "\\":
                    line, col, extra = advance_position(ch, next_ch, line, col)
                    i += 1 + extra
                    if next_ch is not None:
                        line, col, extra = advance_position(next_ch, None, line, col)
                        i += 1 + extra
                    continue

            line, col, extra = advance_position(ch, next_ch, line, col)
            i += 1 + extra
        else:
            if ch == "(" and next_ch == "*":
                depth += 1
                comment_text.append("(*")
                i += 2
                col += 2
                continue

            if ch == "*" and next_ch == ")":
                depth -= 1
                i += 2
                col += 2
                if depth == 0:
                    if comment_allowed_by_enddef and not is_valid_enddef_label_comment("".join(comment_text)):
                        violations.append(
                            violation_factory(comment_start_line, comment_start_col, "".join(comment_text))
                        )
                    comment_text = []
                    comment_allowed_by_enddef = False
                else:
                    comment_text.append("*)")
                continue

            comment_text.append(ch)
            line, col, extra = advance_position(ch, next_ch, line, col)
            i += 1 + extra

    return violations


def scan_comments_with_code[THit](
    text: str,
    *,
    advance_position: Callable[[str, str | None, int, int], tuple[int, int, int]],
    is_identifier_start: Callable[[str], bool],
    consume_identifier: Callable[[str, int], tuple[str, int]],
    comment_code_indicators: Callable[[str], tuple[str, ...]],
    hit_factory: Callable[[int, int, int, int, str, tuple[str, ...], tuple[str, ...]], THit],
) -> list[THit]:
    hits: list[THit] = []
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
    module_stack: list[str] = []
    module_code_paths: list[tuple[str, ...]] = []
    candidate_definition_name: str | None = None
    pending_definition_name: str | None = None
    pending_definition_mode: str | None = None

    while i < n:
        ch = text[i]
        next_ch = text[i + 1] if i + 1 < n else None

        if depth == 0:
            if not in_string:
                if is_identifier_start(ch):
                    token, token_end = consume_identifier(text, i)
                    token_cf = token.casefold()

                    if pending_definition_mode == "header_postcolon":
                        if token_cf == "moduledefinition" and pending_definition_name is not None:
                            module_stack.append(pending_definition_name)
                        pending_definition_name = None
                        pending_definition_mode = None
                    elif pending_definition_mode == "typedef_after_equals":
                        if token_cf == "private_":
                            i = token_end
                            col += len(token)
                            continue
                        if token_cf == "moduledefinition" and pending_definition_name is not None:
                            module_stack.append(f"TypeDef:{pending_definition_name}")
                        pending_definition_name = None
                        pending_definition_mode = None

                    if token_cf == "modulecode":
                        if module_stack:
                            module_code_paths.append(tuple(module_stack))
                        candidate_definition_name = None
                        i = token_end
                        col += len(token)
                        continue

                    if token_cf == "enddef":
                        if module_code_paths and len(module_code_paths[-1]) == len(module_stack):
                            module_code_paths.pop()
                        if module_stack:
                            module_stack.pop()
                        candidate_definition_name = None
                        pending_definition_name = None
                        pending_definition_mode = None
                        i = token_end
                        col += len(token)
                        continue

                    if token_cf == "invocation":
                        if candidate_definition_name is not None:
                            pending_definition_name = candidate_definition_name
                            pending_definition_mode = "header_precolon"
                        candidate_definition_name = None
                        i = token_end
                        col += len(token)
                        continue

                    if token_cf == "basepicture":
                        candidate_definition_name = token
                        i = token_end
                        col += len(token)
                        continue

                    if token_cf in {
                        "moduledefinition",
                        "modulecode",
                        "enddef",
                        "private_",
                        "submodules",
                        "typedefinitions",
                        "moduleparameters",
                        "localvariables",
                    }:
                        candidate_definition_name = None
                    else:
                        candidate_definition_name = token

                    i = token_end
                    col += len(token)
                    continue

                if pending_definition_mode == "header_precolon" and ch == ":":
                    pending_definition_mode = "header_postcolon"
                    i += 1
                    col += 1
                    continue

                if not module_code_paths and candidate_definition_name is not None and ch == "=":
                    pending_definition_name = candidate_definition_name
                    pending_definition_mode = "typedef_after_equals"
                    candidate_definition_name = None
                    i += 1
                    col += 1
                    continue

                if candidate_definition_name is not None and not ch.isspace():
                    candidate_definition_name = None

                if ch == '"' or ch == "'":
                    in_string = True
                    string_quote = ch
                    line, col, extra = advance_position(ch, next_ch, line, col)
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
                    line, col, extra = advance_position(ch, next_ch, line, col)
                    i += 1 + extra
                    in_string = False
                    string_quote = ""
                    continue
                if ch == string_quote:
                    if next_ch == string_quote:
                        line, col, extra = advance_position(ch, next_ch, line, col)
                        i += 1 + extra
                        if next_ch is not None:
                            line, col, extra = advance_position(next_ch, None, line, col)
                            i += 1 + extra
                        continue
                    in_string = False
                    string_quote = ""
                elif ch == "\\":
                    line, col, extra = advance_position(ch, next_ch, line, col)
                    i += 1 + extra
                    if next_ch is not None:
                        line, col, extra = advance_position(next_ch, None, line, col)
                        i += 1 + extra
                    continue

            line, col, extra = advance_position(ch, next_ch, line, col)
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
                    if module_code_paths:
                        indicators = comment_code_indicators("".join(comment_text))
                        if indicators:
                            hits.append(
                                hit_factory(
                                    comment_start_line,
                                    line,
                                    comment_start_col,
                                    col,
                                    "".join(comment_text),
                                    indicators,
                                    module_code_paths[-1],
                                )
                            )
                    comment_text = []
                continue

            comment_text.append(ch)
            line, col, extra = advance_position(ch, next_ch, line, col)
            i += 1 + extra

    return hits


def strip_sl_comments_impl(text: str) -> str:
    n = len(text)
    i = 0
    depth = 0
    in_string = False
    string_quote = ""
    out: list[str] = []

    while i < n:
        ch = text[i]

        if depth == 0:
            if not in_string:
                if ch == '"' or ch == "'":
                    in_string = True
                    string_quote = ch
                    out.append(ch)
                    i += 1
                    continue
                if ch == "(" and i + 1 < n and text[i + 1] == "*":
                    depth = 1
                    i += 2
                    continue
                out.append(ch)
                i += 1
            else:
                if ch == "\n" or ch == "\r":
                    out.append(ch)
                    in_string = False
                    string_quote = ""
                    i += 1
                elif ch == string_quote:
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
            if ch == "(" and i + 1 < n and text[i + 1] == "*":
                depth += 1
                i += 2
            elif ch == "*" and i + 1 < n and text[i + 1] == ")":
                depth -= 1
                i += 2
                if depth == 0:
                    j = i
                    while j < n and text[j] in (" ", "\t", "\r", "\n"):
                        out.append(text[j])
                        j += 1
                    if j < n and text[j] == ";":
                        j += 1
                    i = j
            else:
                if ch == "\n" or ch == "\r":
                    out.append(ch)
                i += 1

    return "".join(out)
