"""Shared AST traversal helpers over the parser walk API."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Literal

from sattlint.parser_api import FuncCall, LitStringTail, ProcedureCall, VarRef, VarTail, walk

type CallKind = Literal["function", "procedure"]


@dataclass(frozen=True, slots=True)
class CallSite:
    """One function or procedure call, identified by kind and callee name."""

    kind: CallKind
    name: str


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
            yield CallSite(kind="function", name=current.name)
            continue
        if isinstance(current, ProcedureCall):
            yield CallSite(kind="procedure", name=current.name)


__all__ = ["CallKind", "CallSite", "iter_call_sites", "iter_variable_refs"]
