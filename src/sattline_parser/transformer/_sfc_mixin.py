"""SFC (Sequence Function Chart) mixin for SLTransformer.

Handles sequence elements, transitions, steps, equations, and related SFC constructs.
"""

from __future__ import annotations

from typing import Any, cast

from lark import Token, Tree

from sattline_parser.grammar import constants as const
from sattline_parser.models.ast_model import (
    Equation,
    Sequence,
    SFCAlternative,
    SFCBreak,
    SFCCodeBlocks,
    SFCFork,
    SFCParallel,
    SFCStep,
    SFCSubsequence,
    SFCTransition,
    SFCTransitionSub,
)


class _SFCMixin:
    """Mixin providing SFC (sequence function chart) transformation methods."""

    def code_blocks(self, items) -> SFCCodeBlocks:
        """Grammar code_blocks -> SFCCodeBlocks with enter/active/exit blocks."""
        blocks: dict[str, list[Any]] = {"enter": [], "active": [], "exit": []}
        for it in items:
            if isinstance(it, dict):
                for k in ("enter", "active", "exit"):
                    if it.get(k):
                        blocks[k].extend(it[k])
        return SFCCodeBlocks(
            enter=blocks["enter"],
            active=blocks["active"],
            exit=blocks["exit"],
        )

    def modulecode(self, items):
        """Grammar modulecode -> ModuleCode with sequences and equations."""
        from sattline_parser.models.ast_model import ModuleCode

        mc = ModuleCode()
        sequences: list[Sequence] = []
        equations: list[Equation] = []

        for it in items:
            if isinstance(it, Sequence):
                sequences.append(it)
            elif isinstance(it, Equation):
                equations.append(it)
            elif isinstance(it, list):
                for item in it:
                    if isinstance(item, Sequence):
                        sequences.append(item)
                    elif isinstance(item, Equation):
                        equations.append(item)

        if sequences:
            mc.sequences = sequences
        if equations:
            mc.equations = equations

        return mc

    def seqinitstep(self, items) -> SFCStep:
        """Grammar seqinitstep -> SEQINITSTEP NAME code_blocks."""
        if len(items) != 3 or not isinstance(items[1], str) or not isinstance(items[2], SFCCodeBlocks):
            raise ValueError(f"seqinitstep expected (SEQINITSTEP, NAME, code_blocks); got: {items!r}")
        return SFCStep(kind="init", name=items[1], code=items[2])

    def seqstep(self, items) -> SFCStep:
        """Grammar seqstep -> SEQSTEP NAME code_blocks."""
        if len(items) != 3 or not isinstance(items[1], str) or not isinstance(items[2], SFCCodeBlocks):
            raise ValueError(f"seqstep expected (SEQSTEP, NAME, code_blocks); got: {items!r}")
        return SFCStep(kind="step", name=items[1], code=items[2])

    def seqtransition(self, items) -> SFCTransition:
        """Grammar seqtransition -> SEQTRANSITION NAME? WAIT_FOR expression."""
        if len(items) == 4 and isinstance(items[1], str) and isinstance(items[2], Token):
            if items[2].type != "WAIT_FOR":
                raise ValueError(f"seqtransition expected WAIT_FOR; got token {items[2]!r}")
            return SFCTransition(name=items[1], condition=items[3])

        if len(items) == 3 and isinstance(items[1], Token):
            if items[1].type != "WAIT_FOR":
                raise ValueError(f"seqtransition expected WAIT_FOR; got token {items[1]!r}")
            return SFCTransition(name=None, condition=items[2])

        raise ValueError(f"seqtransition expected (SEQTRANSITION, NAME?, WAIT_FOR, expr); got: {items!r}")

    def seqtransitionsub(self, items) -> SFCTransitionSub:
        """Grammar seqtransitionsub -> SUBSEQTRANSITION NAME sequence_body ENDSUBSEQTRANSITION."""
        if (
            len(items) != 4
            or not isinstance(items[1], str)
            or not (isinstance(items[2], Tree) and items[2].data == const.KEY_SEQUENCE_BODY)
        ):
            raise ValueError(
                "seqtransitionsub expected "
                "(SUBSEQTRANSITION, NAME, sequence_body, ENDSUBSEQTRANSITION); "
                f"got: {items!r}"
            )
        tree = cast(Tree, items[2])
        return SFCTransitionSub(name=items[1], body=tree.children)

    def seqsub(self, items) -> SFCSubsequence:
        """Grammar seqsub -> SUBSEQUENCE NAME sequence_body ENDSUBSEQUENCE."""
        if (
            len(items) != 4
            or not isinstance(items[1], str)
            or not (isinstance(items[2], Tree) and items[2].data == const.KEY_SEQUENCE_BODY)
        ):
            raise ValueError(f"seqsub expected (SUBSEQUENCE, NAME, sequence_body, ENDSUBSEQUENCE); got: {items!r}")
        tree = cast(Tree, items[2])
        return SFCSubsequence(name=items[1], body=tree.children)

    def seqalternative(self, items) -> SFCAlternative:
        """Grammar seqalternative -> ALTERNATIVESEQ sequence_body (ALTERNATIVEBRANCH sequence_body)+ ENDALTERNATIVE."""
        branches = []
        for it in items:
            if isinstance(it, Tree) and it.data == const.KEY_SEQUENCE_BODY:
                tree = cast(Tree, it)
                branches.append(tree.children)
        return SFCAlternative(branches=branches)

    def seqparallel(self, items) -> SFCParallel:
        """Grammar seqparallel -> PARALLELSEQ sequence_body (PARALLELBRANCH sequence_body)+ ENDPARALLEL."""
        branches = []
        for it in items:
            if isinstance(it, Tree) and it.data == const.KEY_SEQUENCE_BODY:
                tree = cast(Tree, it)
                branches.append(tree.children)
        return SFCParallel(branches=branches)

    def seqfork(self, items) -> SFCFork:
        """Grammar seqfork -> SEQFORK NAME."""
        if len(items) != 2 or not isinstance(items[1], str):
            raise ValueError(f"seqfork expected (SEQFORK, NAME); got: {items!r}")
        return SFCFork(target=items[1])

    def seqbreak(self, _items) -> SFCBreak:
        """Grammar seqbreak -> SEQBREAK."""
        return SFCBreak()

    def seq_element(self, items) -> Any:
        """Grammar seq_element -> passthrough SFC node."""
        for it in items:
            return it

    def sequence_body(self, items):
        """Grammar sequence_body -> Tree of SFC sequence elements."""
        return Tree(const.KEY_SEQUENCE_BODY, items)

    def sequence(self, items) -> Sequence:
        """Grammar sequence -> Sequence with name, position, size, seqcontrol/seqtimer flags, code."""
        name: str | None = None
        position: tuple[float, float] | None = None
        size: tuple[float, float] | None = None
        seqcontrol = False
        seqtimer = False
        code = []
        seqtype = const.GRAMMAR_VALUE_SEQUENCE  # default

        for item in items:
            if isinstance(item, Token):
                if item.type == const.GRAMMAR_VALUE_SEQUENCE:
                    seqtype = const.GRAMMAR_VALUE_SEQUENCE
                elif item.type == const.GRAMMAR_VALUE_OPENSEQUENCE:
                    seqtype = const.GRAMMAR_VALUE_OPENSEQUENCE
            elif isinstance(item, str) and name is None:
                name = item
            elif isinstance(item, tuple) and len(item) == 2 and all(isinstance(x, int | float) for x in item):
                # First 2-tuple is position, second 2-tuple (if present) is size
                if position is None:
                    position = (float(item[0]), float(item[1]))
                elif size is None:
                    size = (float(item[0]), float(item[1]))
            elif isinstance(item, Tree) and item.data == const.KEY_SEQ_CONTROL_OPS:
                tree = cast(Tree, item)
                for child in tree.children:
                    if isinstance(child, Token):
                        if child.value == const.GRAMMAR_VALUE_SEQCONTROL:
                            seqcontrol = True
                        elif child.value == const.GRAMMAR_VALUE_SEQTIMER:
                            seqtimer = True
            elif isinstance(item, Tree) and item.data == const.KEY_SEQUENCE_BODY:
                # children are already typed SFC nodes
                tree = cast(Tree, item)
                code.extend(tree.children)

        if name is None:
            raise ValueError("Name can't be None")

        if position is None:
            raise ValueError("Position can't be None")

        if size is None:
            raise ValueError("Size can't be None")

        return Sequence(
            name=name or "",
            type=seqtype,
            position=position,
            size=size,
            seqcontrol=seqcontrol,
            seqtimer=seqtimer,
            code=code,
        )

    def equationblock(self, items) -> Equation:
        """Grammar equationblock -> Equation with name, position, size, code."""
        name: str | None = None
        position: tuple[float, float] | None = None
        size: tuple[float, float] | None = None
        code = []
        for item in items:
            if isinstance(item, str) and not isinstance(item, Token) and name is None:
                name = item
            elif (
                isinstance(item, tuple)
                and len(item) == 2
                and all(isinstance(x, int | float) for x in item)
                and position is None
            ):
                position = (float(item[0]), float(item[1]))  # from codeblock_coord
            elif (
                isinstance(item, tuple)
                and len(item) == 2
                and all(isinstance(x, int | float) for x in item)
                and size is None
            ):
                size = (float(item[0]), float(item[1]))
            elif isinstance(item, Tree) and item.data == const.KEY_STATEMENT:
                tree = cast(Tree, item)
                code.extend(tree.children)

        if name is None:
            raise ValueError("Name can't be None")

        if position is None:
            raise ValueError("Position can't be None")

        if size is None:
            raise ValueError("Size can't be None")

        return Equation(name=name, position=position, size=size, code=code)
