"""Shared AST traversal helpers."""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping, Sequence
from typing import Literal, Protocol, cast

from ..grammar import constants as const
from ..types import VariableRef

_DEFAULT_VAR_NAME = "var_name"
type CallKind = Literal["function", "procedure"]
type CallSite = tuple[CallKind, str, tuple[object, ...]]


class _ChildrenNode(Protocol):
    @property
    def children(self) -> Sequence[object] | None: ...


def _iter_nested_values(node: object) -> Iterator[object]:
    if isinstance(node, Mapping):
        yield from cast(Mapping[str, object], node).values()
        return

    if isinstance(node, Sequence) and not isinstance(node, str | bytes | bytearray):
        yield from cast(Sequence[object], node)
        return

    children = getattr(cast(_ChildrenNode, node), "children", None)
    if isinstance(children, Sequence) and not isinstance(children, str | bytes | bytearray):
        yield from children
        return

    node_dict = getattr(node, "__dict__", None)
    if isinstance(node_dict, dict):
        yield from node_dict.values()


def iter_variable_refs(node: object, *, key_name: str = _DEFAULT_VAR_NAME) -> Iterator[VariableRef]:
    if isinstance(node, dict):
        mapping = cast(dict[str, object], node)
        if key_name in mapping:
            yield mapping
            return
        for value in mapping.values():
            yield from iter_variable_refs(value, key_name=key_name)
        return

    if isinstance(node, tuple):
        for item in cast(tuple[object, ...], node):
            yield from iter_variable_refs(item, key_name=key_name)
        return

    if isinstance(node, list):
        for item in cast(list[object], node):
            yield from iter_variable_refs(item, key_name=key_name)
        return

    for child in _iter_nested_values(node):
        yield from iter_variable_refs(child, key_name=key_name)


def iter_call_sites(node: object) -> Iterator[CallSite]:
    if isinstance(node, tuple):
        items = cast(tuple[object, ...], node)
        if len(items) == 3 and items[0] == const.KEY_FUNCTION_CALL and isinstance(items[1], str):
            raw_args = items[2]
            args = tuple(cast(Iterable[object], raw_args)) if isinstance(raw_args, list | tuple) else ()
            yield ("function", items[1], args)
            for argument in args:
                yield from iter_call_sites(argument)
            return
        for item in items:
            yield from iter_call_sites(item)
        return

    if isinstance(node, dict):
        mapping = cast(dict[str, object], node)
        if const.KEY_PROCEDURE_CALL in mapping:
            return

        name = mapping.get(const.KEY_NAME)
        raw_args = mapping.get(const.KEY_ARGS)
        if const.KEY_VAR_NAME not in mapping and isinstance(name, str) and isinstance(raw_args, list | tuple):
            args = tuple(cast(Iterable[object], raw_args))
            yield ("procedure", name, args)
            for argument in args:
                yield from iter_call_sites(argument)
            for key, value in mapping.items():
                if key not in {const.KEY_NAME, const.KEY_ARGS}:
                    yield from iter_call_sites(value)
            return

        for value in mapping.values():
            yield from iter_call_sites(value)
        return

    if isinstance(node, list):
        for item in cast(list[object], node):
            yield from iter_call_sites(item)
        return

    for child in _iter_nested_values(node):
        yield from iter_call_sites(child)
