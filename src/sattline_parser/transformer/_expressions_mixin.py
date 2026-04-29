"""Expression and statement mixin for SLTransformer.

Handles expression parsing, operator handling, statements, and value unwrapping.
"""

from __future__ import annotations

from typing import Any

from lark import Token, Tree

from sattline_parser.grammar import constants as const


class _ExpressionsMixin:
    """Mixin providing expression and statement transformation methods."""

    def value(self, items) -> Any:
        """Grammar value rule -> the base value (BOOL | REAL | STRING | SIGNED_INT)."""
        if not items:
            raise ValueError("value expected one item (BOOL|REAL|STRING|SIGNED_INT); got empty list")
        if len(items) != 1:
            raise ValueError(f"value expected exactly one item; got {len(items)}: {items!r}")
        v = items[0]
        if v is None:
            raise ValueError("value item is None")
        return v

    def connected_variable(self, items):
        """Grammar connected_variable rule -> variable or variable reference."""
        for it in items:
            if not isinstance(it, Token):
                return it
        raise ValueError(f"connected_variable expected a non-Token child; got: {items}")

    def invar_tail(self, items):
        """Grammar invar_tail rule -> tail specification or variable reference."""
        for it in items:
            if not isinstance(it, Token):
                return it
        raise ValueError(f"invar_tail expected a non-Token child; got: {items}")

    def or_expression(self, items):
        """Grammar or_expression -> (expr OR expr | expr)."""
        exprs = [it for it in items if not isinstance(it, Token)]
        if len(exprs) == 1:
            return exprs[0]
        return (const.GRAMMAR_VALUE_OR, exprs)

    def and_expression(self, items):
        """Grammar and_expression -> (expr AND expr | expr)."""
        exprs = [it for it in items if not isinstance(it, Token)]
        if len(exprs) == 1:
            return exprs[0]
        return (const.GRAMMAR_VALUE_AND, exprs)

    def not_expression(self, items):
        """Grammar not_expression -> (NOT expr | expr)."""
        # if "not" was present, should be (NOT, expr), else just expr
        if len(items) == 1:
            return items[0]
        if len(items) >= 2:
            # Has NOT
            expr = None
            for it in items:
                if not isinstance(it, Token):
                    expr = it
            if expr is not None:
                return (const.GRAMMAR_VALUE_NOT, expr)
        return items[-1]

    def compare(self, items):
        """Grammar compare -> (expr OP expr | expr)."""
        # Expected output: (KEY_COMPARE, [left, right1, right2, ...], [(op1, right1), (op2, right2), ...])
        values = []
        pairs = []  # (operator, right) pairs
        current_op = None
        for it in items:
            if isinstance(it, Token):
                current_op = it
            elif it is not None and not isinstance(it, Token):
                values.append(it)
                if current_op is not None:
                    pairs.append((current_op, it))
                    current_op = None
        if len(values) == 1:
            return values[0]
        return (const.KEY_COMPARE, values, pairs)

    def additive_expression(self, items):
        """Grammar additive_expression -> (expr + expr | expr - expr | expr)."""
        values = []
        pairs = []  # (operator, right) pairs
        current_op = None
        for it in items:
            if isinstance(it, Token):
                current_op = it
            elif it is not None and not isinstance(it, Token):
                values.append(it)
                if current_op is not None:
                    pairs.append((current_op, it))
                    current_op = None
        if len(values) == 1:
            return values[0]
        return (const.KEY_ADD, values, pairs)

    def multiplicative_expression(self, items):
        """Grammar multiplicative_expression -> (expr * expr | expr / expr | expr)."""
        values = []
        pairs = []  # (operator, right) pairs
        current_op = None
        for it in items:
            if isinstance(it, Token):
                current_op = it
            elif it is not None and not isinstance(it, Token):
                values.append(it)
                if current_op is not None:
                    pairs.append((current_op, it))
                    current_op = None
        if len(values) == 1:
            return values[0]
        return (const.KEY_MUL, values, pairs)

    def unary_expression(self, items):
        """Grammar unary_expression -> (- expr | + expr | expr)."""
        if len(items) == 1:
            return items[0]
        # has unary operator
        op = None
        expr = None
        for it in items:
            if isinstance(it, Token):
                op = it
            else:
                expr = it
        if op is None or expr is None:
            raise ValueError(f"unary_expression expected operator and expression; got: {items}")
        if op.type == const.KEY_MINUS:
            return (const.KEY_MINUS, expr)
        return (op.value, expr)

    def function_call(self, items):
        """Grammar function_call -> NAME LPAREN argument_list? RPAREN."""
        fn_name = None
        args = []
        for it in items:
            if isinstance(it, str) and not isinstance(it, list) and fn_name is None:
                fn_name = it
            elif not isinstance(it, Token):
                # this is argument_list result
                args = it
        return (const.KEY_FUNCTION_CALL, fn_name, args)

    def argument_list(self, items):
        """Grammar argument_list -> expression (COMMA expression)*."""
        return [it for it in items if not isinstance(it, Token)]

    def ternary_if(self, items):
        """Grammar ternary_if -> IF cond THEN expr (ELSIF cond THEN expr)* ELSE expr ENDIF."""
        branches = []
        else_expr = None
        i = 0
        # Expect IF
        while i < len(items):
            tok = items[i]
            if isinstance(tok, Token) and tok.type == const.GRAMMAR_VALUE_IF:
                cond = items[i + 1]
                # skip THEN at i+2
                then_expr = items[i + 3]
                branches.append((cond, then_expr))
                i += 4
            elif isinstance(tok, Token) and tok.type == const.GRAMMAR_VALUE_ELSIF:
                cond = items[i + 1]
                then_expr = items[i + 3]  # skip THEN
                branches.append((cond, then_expr))
                i += 4
            elif isinstance(tok, Token) and tok.type == const.GRAMMAR_VALUE_ELSE:
                else_expr = items[i + 1]
                i += 2
            else:
                i += 1
        return (const.KEY_TERNARY, branches, else_expr)

    def assignment_statement(self, items):
        """Grammar assignment_statement -> variable_name '=' expression."""
        if len(items) != 2:
            # Be defensive in case of stray tokens
            target = items[0]
            expr = items[-1]
        else:
            target, expr = items
        return (const.KEY_ASSIGN, target, expr)

    def if_statement(self, items):
        """Grammar if_statement -> IF expression THEN statement* (ELSIF...)* (ELSE...)? ENDIF."""
        branches = []
        else_block = None
        i = 0
        while i < len(items):
            tok = items[i]
            if (isinstance(tok, Token) and tok.type == const.GRAMMAR_VALUE_IF) or (
                isinstance(tok, Token) and tok.type == const.GRAMMAR_VALUE_ELSIF
            ):
                cond = items[i + 1]
                i += 2  # now at THEN
                # skip THEN
                i += 1
                stmts = []
                while i < len(items):
                    t = items[i]
                    if isinstance(t, Token) and t.type in (
                        const.GRAMMAR_VALUE_ELSIF,
                        const.GRAMMAR_VALUE_ELSE,
                        const.GRAMMAR_VALUE_ENDIF,
                    ):
                        break
                    stmts.append(t)
                    i += 1
                branches.append((cond, stmts))
            elif isinstance(tok, Token) and tok.type == const.GRAMMAR_VALUE_ELSE:
                i += 1
                else_block = []
                while i < len(items):
                    t = items[i]
                    if isinstance(t, Token) and t.type == const.GRAMMAR_VALUE_ENDIF:
                        break
                    else_block.append(t)
                    i += 1
                # ENDIF will be handled by loop increment
                i += 1
            else:
                i += 1
        return (const.GRAMMAR_VALUE_IF, branches, else_block)

    def statement(self, items) -> Tree:
        """Grammar statement -> assignment_statement | function_call | if_statement."""
        for it in items:
            if not isinstance(it, Token):
                return Tree(const.KEY_STATEMENT, [it])  # Keep the Tree wrapper
        types = ", ".join(type(x).__name__ for x in items)
        raise ValueError(
            f"statement expected a non-Token child "
            f"(assignment_statement | function_call | if_statement); got only tokens: {types}"
        )
