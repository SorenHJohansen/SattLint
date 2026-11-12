"""Shared AST traversal helpers over the parser walk API."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Literal

from sattlint.parser_api import FuncCall, LitStringTail, ProcedureCall, VarRef, VarTail, walk

type CallKind = Literal["function", "procedure"]
type CallSite = tuple[CallKind, str, tuple[object, ...]]


def iter_variable_refs(node: object) -> Iterator[VarRef]:
    """Yield every variable reference and bound tail name under ``node``."""
    for event in walk(node):
        current = event.node
        if isinstance(current, VarRef):
            yield current
            continue
        if isinstance(current, VarTail) and not isinstance(current.value, LitStringTail):
            bound_name = current.bound_name
            if bound_name is not None:
                yield VarRef(name=bound_name, span=current.span)


def iter_call_sites(node: object) -> Iterator[CallSite]:
    """Yield every function and procedure call under ``node``."""
    for event in walk(node):
        current = event.node
        if isinstance(current, FuncCall):
            yield ("function", current.name, tuple(current.args))
            continue
        if isinstance(current, ProcedureCall):
            yield ("procedure", current.name, tuple(current.args))
