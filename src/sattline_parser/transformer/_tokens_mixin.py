"""Token coercion mixin for SLTransformer.

Handles grammar token-to-value conversion: STRING, NAME, numeric and boolean literals,
keywords, and terminal punctuation.
"""

# pyright: reportUnusedClass=false

from __future__ import annotations

from typing import Literal

from lark import Token

from sattline_parser.grammar import constants as const
from sattline_parser.models.ast_model import FloatLiteral, IntLiteral, SourceSpan

DEFAULT_INIT = object()


class _TokensMixin:
    """Mixin providing token and terminal coercion methods."""

    def _unwrap_token(self, tok: object) -> str | object:
        """Unwrap a Lark Token to string."""
        if isinstance(tok, Token):
            return str(tok)
        return tok

    # ---- Convert basic terminals to Python values ----

    def NAME(self, tok: Token) -> str:
        """Grammar NAME terminal -> string."""
        return str(tok)

    def STRING(self, tok: Token) -> str:
        """Grammar STRING terminal -> string (strip quotes, unescape)."""
        s = str(tok)
        # STRING includes quotes; "" inside is an escaped quote
        inner = s[1:-1] if len(s) >= 2 and s[0] == '"' and s[-1] == '"' else s
        return inner.replace('""', '"').rstrip("\n")

    def STRING_CRLF(self, tok: Token) -> str:
        """Grammar STRING_CRLF terminal -> string (treat like STRING but drop trailing newline)."""
        return self.STRING(tok)

    def SIGNED_INT(self, tok: Token) -> IntLiteral:
        """Grammar SIGNED_INT terminal -> IntLiteral with source span."""
        span = SourceSpan(line=getattr(tok, "line", 0), column=getattr(tok, "column", 0))
        return IntLiteral(int(str(tok)), span)

    def SIGNED_INT_NOTAIL(self, tok: Token) -> IntLiteral:
        """Grammar SIGNED_INT_NOTAIL terminal -> IntLiteral (no trailing coordinates)."""
        return self.SIGNED_INT(tok)

    def REAL(self, tok: Token) -> FloatLiteral:
        """Grammar REAL terminal -> FloatLiteral with source span."""
        span = SourceSpan(line=getattr(tok, "line", 0), column=getattr(tok, "column", 0))
        return FloatLiteral(float(str(tok)), span)

    def REAL_NOTAIL(self, tok: Token) -> FloatLiteral:
        """Grammar REAL_NOTAIL terminal -> FloatLiteral (no trailing coordinates)."""
        return self.REAL(tok)

    def BOOL(self, tok: Token) -> bool:
        """Grammar BOOL terminal -> bool."""
        s = str(tok)
        if s == const.GRAMMAR_VALUE_BOOL_TRUE:
            return True
        if s == const.GRAMMAR_VALUE_BOOL_FALSE:
            return False
        raise ValueError(f"BOOL expected {const.GRAMMAR_VALUE_BOOL_TRUE}/{const.GRAMMAR_VALUE_BOOL_FALSE}; got: {s}")

    def BOOL_NOTAIL(self, tok: Token) -> bool:
        """Grammar BOOL_NOTAIL terminal -> bool (no trailing coordinates)."""
        return self.BOOL(tok)

    def STRING_NOTAIL(self, tok: Token) -> str:
        """Grammar STRING_NOTAIL terminal -> string (no trailing coordinates)."""
        return self.STRING(tok)

    # Keywords we care about as flags

    def GLOBAL_KW(self, _tok: object) -> Literal[True]:  # "GLOBAL"
        """Grammar GLOBAL_KW keyword -> True."""
        return True

    def CONST_KW(self, _tok: object) -> Literal["Const"]:
        """Grammar CONST_KW keyword -> "Const"."""
        return "Const"

    def STATE_KW(self, _tok: object) -> Literal["State"]:
        """Grammar STATE_KW keyword -> "State"."""
        return "State"

    def OPSAVE_KW(self, _tok: object) -> Literal["OpSave"]:
        """Grammar OPSAVE_KW keyword -> "OpSave"."""
        return "OpSave"

    def SECURE_KW(self, _tok: object) -> Literal["Secure"]:
        """Grammar SECURE_KW keyword -> "Secure"."""
        return "Secure"

    # DEFAULT in init

    def DEFAULT(self, _tok: object) -> object:
        """Grammar DEFAULT terminal -> DEFAULT_INIT sentinel."""
        return DEFAULT_INIT

    # Punctuation tokens we don't need as data (returning None is fine; we'll filter Nones)

    def COLON(self, _tok: object) -> None:
        """Grammar COLON punctuation -> None (filtered out)."""
        return None

    def COMMA(self, _tok: object) -> None:
        """Grammar COMMA punctuation -> None (filtered out)."""
        return None

    def SEMI(self, _tok: object) -> None:
        """Grammar SEMI punctuation -> None (filtered out)."""
        return None

    # And the := and optional Duration_Value inside opt_var_init

    def ASSIGN_INIT_VALUE(self, _tok: object) -> None:
        """Grammar ASSIGN_INIT_VALUE (:=) punctuation -> None (filtered out)."""
        return None

    def DURATION_VALUE(self, _tok: object) -> object:
        """Grammar DURATION_VALUE terminal -> GRAMMAR_VALUE_DURATION_VALUE sentinel."""
        return const.GRAMMAR_VALUE_DURATION_VALUE

    def sl_datecode(self, items: list[object]) -> int:
        """Grammar sl_datecode rule -> int datecode."""
        for it in items:
            if isinstance(it, Token) and it.type == const.KEY_SL_DATECODE:
                try:
                    return int(it.value)
                except (TypeError, ValueError) as exc:
                    raise ValueError(f"Invalid {const.KEY_SL_DATECODE} value: {it.value!r}") from exc
            if isinstance(it, int):
                return it
        raise ValueError(f"sl_datecode expected int or {const.KEY_SL_DATECODE} Token; got: {items}")
