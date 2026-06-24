# pyright: reportUnusedClass=false

"""SFC (Sequence Function Chart) mixin for SLTransformer.

Handles sequence elements, transitions, steps, equations, and related SFC constructs.
"""

from __future__ import annotations

from typing import Any, cast

from lark import Token, Tree

from sattline_parser.grammar import constants as const
from sattline_parser.models.ast_model import (
    Equation,
    ModuleCode,
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

from ._module_shared import TransformerItem, TransformerTree, coord_pair, tree_children

CodeBlockPayload = dict[str, list[object]]
SfcBody = list[object]


class SFCMixin:
    """Mixin providing SFC (sequence function chart) transformation methods."""

    def entercode(self, items: list[TransformerItem]) -> CodeBlockPayload:
        """Grammar entercode -> normalized enter block payload."""
        statements = [item for item in items if not isinstance(item, Token)]
        return {"enter": statements}

    def activecode(self, items: list[TransformerItem]) -> CodeBlockPayload:
        """Grammar activecode -> normalized active block payload."""
        statements = [item for item in items if not isinstance(item, Token)]
        return {"active": statements}

    def exitcode(self, items: list[TransformerItem]) -> CodeBlockPayload:
        """Grammar exitcode -> normalized exit block payload."""
        statements = [item for item in items if not isinstance(item, Token)]
        return {"exit": statements}

    def code_blocks(self, items: list[TransformerItem]) -> SFCCodeBlocks:
        """Grammar code_blocks -> SFCCodeBlocks with enter/active/exit blocks."""
        blocks: CodeBlockPayload = {"enter": [], "active": [], "exit": []}
        for item in items:
            if not isinstance(item, dict):
                continue
            payload = cast(CodeBlockPayload, item)
            for key in ("enter", "active", "exit"):
                statements = payload.get(key)
                if statements:
                    blocks[key].extend(statements)
        return SFCCodeBlocks(
            enter=blocks["enter"],
            active=blocks["active"],
            exit=blocks["exit"],
        )

    def modulecode(self, items: list[TransformerItem]) -> ModuleCode:
        """Grammar modulecode -> ModuleCode with sequences and equations."""
        module_code = ModuleCode()
        sequences: list[Sequence] = []
        equations: list[Equation] = []

        for item in items:
            if isinstance(item, Sequence):
                sequences.append(item)
            elif isinstance(item, Equation):
                equations.append(item)
            elif isinstance(item, list):
                for nested_item in cast(list[TransformerItem], item):
                    if isinstance(nested_item, Sequence):
                        sequences.append(nested_item)
                    elif isinstance(nested_item, Equation):
                        equations.append(nested_item)

        if sequences:
            module_code.sequences = sequences
        if equations:
            module_code.equations = equations

        return module_code

    def seqinitstep(self, items: list[TransformerItem]) -> SFCStep:
        """Grammar seqinitstep -> SEQINITSTEP NAME code_blocks."""
        if len(items) != 3 or not isinstance(items[1], str) or not isinstance(items[2], SFCCodeBlocks):
            raise ValueError(f"seqinitstep expected (SEQINITSTEP, NAME, code_blocks); got: {items!r}")
        return SFCStep(kind="init", name=items[1], code=items[2])

    def seqstep(self, items: list[TransformerItem]) -> SFCStep:
        """Grammar seqstep -> SEQSTEP NAME code_blocks."""
        if len(items) != 3 or not isinstance(items[1], str) or not isinstance(items[2], SFCCodeBlocks):
            raise ValueError(f"seqstep expected (SEQSTEP, NAME, code_blocks); got: {items!r}")
        return SFCStep(kind="step", name=items[1], code=items[2])

    def seqtransition(self, items: list[TransformerItem]) -> SFCTransition:
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

    def seqtransitionsub(self, items: list[TransformerItem]) -> SFCTransitionSub:
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
        tree = cast(TransformerTree, items[2])
        return SFCTransitionSub(name=items[1], body=tree_children(tree))

    def seqsub(self, items: list[TransformerItem]) -> SFCSubsequence:
        """Grammar seqsub -> SUBSEQUENCE NAME sequence_body ENDSUBSEQUENCE."""
        if (
            len(items) != 4
            or not isinstance(items[1], str)
            or not (isinstance(items[2], Tree) and items[2].data == const.KEY_SEQUENCE_BODY)
        ):
            raise ValueError(f"seqsub expected (SUBSEQUENCE, NAME, sequence_body, ENDSUBSEQUENCE); got: {items!r}")
        tree = cast(TransformerTree, items[2])
        return SFCSubsequence(name=items[1], body=tree_children(tree))

    def seqalternative(self, items: list[TransformerItem]) -> SFCAlternative:
        """Grammar seqalternative -> ALTERNATIVESEQ sequence_body (ALTERNATIVEBRANCH sequence_body)+ ENDALTERNATIVE."""
        branches: list[SfcBody] = []
        for item in items:
            if isinstance(item, Tree) and item.data == const.KEY_SEQUENCE_BODY:
                tree = cast(TransformerTree, item)
                branches.append(tree_children(tree))
        return SFCAlternative(branches=branches)

    def seqparallel(self, items: list[TransformerItem]) -> SFCParallel:
        """Grammar seqparallel -> PARALLELSEQ sequence_body (PARALLELBRANCH sequence_body)+ ENDPARALLEL."""
        branches: list[SfcBody] = []
        for item in items:
            if isinstance(item, Tree) and item.data == const.KEY_SEQUENCE_BODY:
                tree = cast(TransformerTree, item)
                branches.append(tree_children(tree))
        return SFCParallel(branches=branches)

    def seqfork(self, items: list[TransformerItem]) -> SFCFork:
        """Grammar seqfork -> SEQFORK NAME ("," NAME)*."""
        targets: list[str] = []
        for item in items:
            if isinstance(item, Token):
                if item.type == "NAME":
                    targets.append(str(item))
                continue
            if type(item) is str:
                targets.append(item)
        targets_tuple = tuple(targets)
        if not targets_tuple:
            raise ValueError(f"seqfork expected at least one NAME target; got: {items!r}")
        return SFCFork(targets=targets_tuple)

    def seqbreak(self, _items: list[TransformerItem]) -> SFCBreak:
        """Grammar seqbreak -> SEQBREAK."""
        return SFCBreak()

    def seq_element(self, items: list[TransformerItem]) -> TransformerItem | None:
        """Grammar seq_element -> passthrough SFC node."""
        for item in items:
            return item
        return None

    def sequence_body(self, items: list[TransformerItem]) -> TransformerTree:
        """Grammar sequence_body -> Tree of SFC sequence elements."""
        return Tree(const.KEY_SEQUENCE_BODY, cast(list[Any], items))

    def sequence(self, items: list[TransformerItem]) -> Sequence:
        """Grammar sequence -> Sequence with name, position, size, seqcontrol/seqtimer flags, code."""
        name: str | None = None
        position: tuple[float, float] | None = None
        size: tuple[float, float] | None = None
        seqcontrol = False
        seqtimer = False
        code: list[object] = []
        seqtype = const.GRAMMAR_VALUE_SEQUENCE

        for item in items:
            if isinstance(item, Token):
                if item.type == const.GRAMMAR_VALUE_SEQUENCE:
                    seqtype = const.GRAMMAR_VALUE_SEQUENCE
                elif item.type == const.GRAMMAR_VALUE_OPENSEQUENCE:
                    seqtype = const.GRAMMAR_VALUE_OPENSEQUENCE
                continue

            if isinstance(item, str) and name is None:
                name = item
                continue

            coord = coord_pair(item)
            if coord is not None:
                if position is None:
                    position = coord
                elif size is None:
                    size = coord
                continue

            if isinstance(item, Tree) and item.data == const.KEY_SEQ_CONTROL_OPS:
                tree = cast(TransformerTree, item)
                for child in tree_children(tree):
                    if not isinstance(child, Token):
                        continue
                    if child.value == const.GRAMMAR_VALUE_SEQCONTROL:
                        seqcontrol = True
                    elif child.value == const.GRAMMAR_VALUE_SEQTIMER:
                        seqtimer = True
                continue

            if isinstance(item, Tree) and item.data == const.KEY_SEQUENCE_BODY:
                tree = cast(TransformerTree, item)
                code.extend(tree_children(tree))

        if name is None:
            raise ValueError("Name can't be None")
        if position is None:
            raise ValueError("Position can't be None")
        if size is None:
            raise ValueError("Size can't be None")

        return Sequence(
            name=name,
            type=seqtype,
            position=position,
            size=size,
            seqcontrol=seqcontrol,
            seqtimer=seqtimer,
            code=code,
        )

    def equationblock(self, items: list[TransformerItem]) -> Equation:
        """Grammar equationblock -> Equation with name, position, size, code."""
        name: str | None = None
        position: tuple[float, float] | None = None
        size: tuple[float, float] | None = None
        code: list[object] = []

        for item in items:
            if isinstance(item, Token):
                continue

            if isinstance(item, str) and name is None:
                name = item
                continue

            coord = coord_pair(item)
            if coord is not None:
                if position is None:
                    position = coord
                elif size is None:
                    size = coord
                continue

            if isinstance(item, Tree) and item.data == const.KEY_STATEMENT:
                tree = cast(TransformerTree, item)
                code.extend(tree_children(tree))

        if name is None:
            raise ValueError("Name can't be None")
        if position is None:
            raise ValueError("Position can't be None")
        if size is None:
            raise ValueError("Size can't be None")

        return Equation(name=name, position=position, size=size, code=code)


__all__ = ["SFCMixin"]
