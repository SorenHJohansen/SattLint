from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from sattlint.parser_api import constants as const

# Keyword facts come from the parser's grammar constants, not a local list, so a
# grammar rename cannot silently desynchronize the comment scanner.
_KEYWORD_MODULEDEFINITION = const.GRAMMAR_VALUE_MODULEDEFINITION.casefold()
_KEYWORD_PRIVATE = const.GRAMMAR_VALUE_PRIVATE.casefold()
_KEYWORD_MODULECODE = const.GRAMMAR_VALUE_MODULECODE.casefold()
_KEYWORD_ENDDEF = const.GRAMMAR_VALUE_ENDDEF_KW.casefold()
_KEYWORD_INVOCATION = const.GRAMMAR_VALUE_INVOCATION.casefold()
_KEYWORD_SUBMODULES = const.GRAMMAR_VALUE_SUBMODULES.casefold()
_KEYWORD_TYPEDEFINITIONS = const.GRAMMAR_VALUE_TYPEDEFINITIONS.casefold()
_KEYWORD_MODULEPARAMETERS = const.GRAMMAR_VALUE_MODULEPARAMETERS.casefold()
_KEYWORD_LOCALVARIABLES = const.GRAMMAR_VALUE_LOCALVARIABLES.casefold()
_KEYWORD_EQUATIONBLOCK = const.GRAMMAR_VALUE_EQUATIONBLOCK.casefold()
_KEYWORD_SEQUENCE = const.GRAMMAR_VALUE_SEQUENCE.casefold()
_KEYWORD_OPENSEQUENCE = const.GRAMMAR_VALUE_OPENSEQUENCE.casefold()
_KEYWORD_ENDSEQUENCE = const.GRAMMAR_VALUE_ENDSEQUENCE.casefold()
_KEYWORD_ENDOPENSEQUENCE = const.GRAMMAR_VALUE_ENDOPENSEQUENCE.casefold()
_KEYWORD_SEQINITSTEP = const.GRAMMAR_VALUE_SEQINITSTEP.casefold()
_KEYWORD_SEQSTEP = const.GRAMMAR_VALUE_SEQSTEP.casefold()
_KEYWORD_SEQTRANSITION = const.GRAMMAR_VALUE_SEQTRANSITION.casefold()
_KEYWORD_SUBSEQTRANSITION = const.GRAMMAR_VALUE_SUBSEQTRANSITION.casefold()
_KEYWORD_ENDSUBSEQTRANSITION = const.GRAMMAR_VALUE_ENDSUBSEQTRANSITION.casefold()
_KEYWORD_SEQFORK = const.GRAMMAR_VALUE_SEQFORK.casefold()
_MODULE_PATH_BREAK_KEYWORDS = frozenset(
    {
        _KEYWORD_MODULEDEFINITION,
        _KEYWORD_MODULECODE,
        _KEYWORD_ENDDEF,
        _KEYWORD_PRIVATE,
        _KEYWORD_SUBMODULES,
        _KEYWORD_TYPEDEFINITIONS,
        _KEYWORD_MODULEPARAMETERS,
        _KEYWORD_LOCALVARIABLES,
    }
)


@dataclass
class _ModuleCodeContext:
    equation_name: str | None = None
    sequence_name: str | None = None
    step_name: str | None = None
    pending_name_kind: str | None = None


def scan_comments_with_code[THit](  # noqa: PLR0915
    text: str,
    *,
    advance_position: Callable[[str, str | None, int, int], tuple[int, int, int]],
    is_identifier_start: Callable[[str], bool],
    consume_identifier: Callable[[str, int], tuple[str, int]],
    comment_code_indicators: Callable[[str], tuple[str, ...]],
    hit_factory: Callable[
        [int, int, int, int, str, tuple[str, ...], tuple[str, ...], str | None, str | None, str | None],
        THit,
    ],
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
    module_code_contexts: list[_ModuleCodeContext] = []
    candidate_definition_name: str | None = None
    pending_definition_name: str | None = None
    pending_definition_mode: str | None = None

    while i < n:
        ch = text[i]
        next_ch = text[i + 1] if i + 1 < n else None

        if depth == 0:
            if not in_string:
                current_context = module_code_contexts[-1] if module_code_contexts else None
                typed_module_stack: list[str] = module_stack

                if is_identifier_start(ch):
                    token, token_end = consume_identifier(text, i)
                    token_cf = token.casefold()

                    if current_context is not None and current_context.pending_name_kind is not None:
                        if current_context.pending_name_kind == "equation":
                            current_context.equation_name = token
                            current_context.sequence_name = None
                            current_context.step_name = None
                        elif current_context.pending_name_kind == "sequence":
                            current_context.equation_name = None
                            current_context.sequence_name = token
                            current_context.step_name = None
                        else:
                            current_context.step_name = token
                        current_context.pending_name_kind = None
                        i = token_end
                        col += len(token)
                        continue

                    if pending_definition_mode == "header_postcolon":
                        if token_cf == _KEYWORD_MODULEDEFINITION and pending_definition_name is not None:
                            module_stack.append(pending_definition_name)
                        pending_definition_name = None
                        pending_definition_mode = None
                    elif pending_definition_mode == "typedef_after_equals":
                        if token_cf == _KEYWORD_PRIVATE:
                            i = token_end
                            col += len(token)
                            continue
                        if token_cf == _KEYWORD_MODULEDEFINITION and pending_definition_name is not None:
                            module_stack.append(f"TypeDef:{pending_definition_name}")
                        pending_definition_name = None
                        pending_definition_mode = None

                    if token_cf == _KEYWORD_MODULECODE:
                        if typed_module_stack:
                            module_code_paths.append(tuple(typed_module_stack))
                            module_code_contexts.append(_ModuleCodeContext())
                        candidate_definition_name = None
                        i = token_end
                        col += len(token)
                        continue

                    if token_cf == _KEYWORD_ENDDEF:
                        if module_code_paths and len(module_code_paths[-1]) == len(typed_module_stack):
                            module_code_paths.pop()
                            module_code_contexts.pop()
                        if typed_module_stack:
                            typed_module_stack.pop()
                        candidate_definition_name = None
                        pending_definition_name = None
                        pending_definition_mode = None
                        i = token_end
                        col += len(token)
                        continue

                    if token_cf == _KEYWORD_INVOCATION:
                        if candidate_definition_name is not None:
                            pending_definition_name = candidate_definition_name
                            pending_definition_mode = "header_precolon"
                        candidate_definition_name = None
                        i = token_end
                        col += len(token)
                        continue

                    if current_context is not None:
                        if token_cf == _KEYWORD_EQUATIONBLOCK:
                            current_context.equation_name = None
                            current_context.sequence_name = None
                            current_context.step_name = None
                            current_context.pending_name_kind = "equation"
                            candidate_definition_name = None
                            i = token_end
                            col += len(token)
                            continue

                        if token_cf in {_KEYWORD_SEQUENCE, _KEYWORD_OPENSEQUENCE}:
                            current_context.equation_name = None
                            current_context.sequence_name = None
                            current_context.step_name = None
                            current_context.pending_name_kind = "sequence"
                            candidate_definition_name = None
                            i = token_end
                            col += len(token)
                            continue

                        if token_cf in {_KEYWORD_ENDSEQUENCE, _KEYWORD_ENDOPENSEQUENCE}:
                            current_context.sequence_name = None
                            current_context.step_name = None
                            current_context.pending_name_kind = None
                            candidate_definition_name = None
                            i = token_end
                            col += len(token)
                            continue

                        if token_cf in {_KEYWORD_SEQINITSTEP, _KEYWORD_SEQSTEP}:
                            current_context.step_name = None
                            current_context.pending_name_kind = (
                                "step" if current_context.sequence_name is not None else None
                            )
                            candidate_definition_name = None
                            i = token_end
                            col += len(token)
                            continue

                        if token_cf in {
                            _KEYWORD_SEQTRANSITION,
                            _KEYWORD_SUBSEQTRANSITION,
                            _KEYWORD_ENDSUBSEQTRANSITION,
                            _KEYWORD_SEQFORK,
                        }:
                            current_context.step_name = None
                            if current_context.pending_name_kind == "step":
                                current_context.pending_name_kind = None
                            candidate_definition_name = None
                            i = token_end
                            col += len(token)
                            continue

                    candidate_definition_name = None if token_cf in _MODULE_PATH_BREAK_KEYWORDS else token

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

                if current_context is not None and current_context.pending_name_kind is not None and not ch.isspace():
                    current_context.pending_name_kind = None

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
                        current_context = module_code_contexts[-1]
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
                                    current_context.equation_name,
                                    current_context.sequence_name,
                                    current_context.step_name,
                                )
                            )
                    comment_text = []
                continue

            comment_text.append(ch)
            line, col, extra = advance_position(ch, next_ch, line, col)
            i += 1 + extra

    return hits
