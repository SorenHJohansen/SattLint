"""One traversal of module code that keeps the block a statement came from.

Equation blocks, SFC step phases, and SFC transition guards carry different
execution semantics, so callers that reason about ordering or location need the
originating block, not just a flat statement list.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import cast

from sattlint.parser_api import (
    CodeItem,
    ModuleCode,
    SFCAlternative,
    SFCParallel,
    SFCStep,
    SFCSubsequence,
    SFCTransition,
    SFCTransitionSub,
    SLExpression,
)

from .ast_node_helpers import if_branches, if_else_block


class BlockKind(StrEnum):
    """The kind of module-code block a statement was collected from.

    An equation block re-evaluates every scan, so a read there is not an
    ordering hazard: the value carries over from the previous scan. Step
    phases and transition guards are judged in sequence order instead.
    """

    EQUATION = "equation"
    STEP = "step"
    TRANSITION = "transition"


@dataclass(frozen=True, slots=True)
class StatementSite:
    """One statement, the block it runs in, and a readable location."""

    node: CodeItem | SLExpression
    site: str
    block_kind: BlockKind


def iter_nested_statement_sites(modulecode: ModuleCode) -> Iterator[StatementSite]:
    """Yield every statement, descending into the bodies of ``IF`` blocks."""
    for event in iter_statement_sites(modulecode):
        yield from _nested_sites(event)


def _nested_sites(event: StatementSite) -> Iterator[StatementSite]:
    yield event
    for _condition, body in if_branches(event.node):
        for statement in cast(list[CodeItem], body):
            yield from _nested_sites(StatementSite(statement, event.site, event.block_kind))
    else_block = if_else_block(event.node)
    for statement in cast(list[CodeItem], else_block or ()):
        yield from _nested_sites(StatementSite(statement, event.site, event.block_kind))


def iter_statement_sites(modulecode: ModuleCode) -> Iterator[StatementSite]:
    for equation in modulecode.equationblocks or []:
        site = f"equation block {equation.name!r}"
        for statement in equation.code or []:
            yield StatementSite(statement, site, BlockKind.EQUATION)
    for sequence in modulecode.sequences or []:
        yield from _sequence_sites(sequence.code or [], sequence.name or "")


def _sequence_sites(nodes: Sequence[object], sequence_name: str) -> Iterator[StatementSite]:
    for node in nodes:
        if isinstance(node, SFCStep):
            for phase, statements in (
                ("ENTER", node.code.enter or []),
                ("ACTIVE", node.code.active or []),
                ("EXIT", node.code.exit or []),
            ):
                site = f"sequence {sequence_name!r} step {node.name!r} {phase}"
                for statement in statements:
                    yield StatementSite(statement, site, BlockKind.STEP)
            continue
        if isinstance(node, SFCTransition) and node.condition is not None:
            site = f"sequence {sequence_name!r} transition {node.name!r} condition"
            yield StatementSite(node.condition, site, BlockKind.TRANSITION)
            continue
        if isinstance(node, SFCAlternative | SFCParallel):
            for branch in node.branches or []:
                yield from _sequence_sites(list(branch or []), sequence_name)
            continue
        if isinstance(node, SFCSubsequence | SFCTransitionSub):
            yield from _sequence_sites(list(node.body or []), sequence_name)


__all__ = ["BlockKind", "StatementSite", "iter_nested_statement_sites", "iter_statement_sites"]
