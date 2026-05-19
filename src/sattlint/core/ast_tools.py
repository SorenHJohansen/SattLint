"""Shared AST traversal helpers."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from typing import Literal, TypeAlias, cast

from ..grammar import constants as const

_DEFAULT_VAR_NAME = "var_name"
VariableRef: TypeAlias = dict[str, object]
CallKind: TypeAlias = Literal["function", "procedure"]
CallSite: TypeAlias = tuple[CallKind, str, tuple[object, ...]]


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

    children = getattr(node, "children", None)
    if isinstance(children, list):
        for child in cast(list[object], children):
            yield from iter_variable_refs(child, key_name=key_name)
        return
    if isinstance(children, tuple):
        for child in cast(tuple[object, ...], children):
            yield from iter_variable_refs(child, key_name=key_name)
        return

    node_dict = getattr(node, "__dict__", None)
    if isinstance(node_dict, dict):
        for value in cast(dict[str, object], node_dict).values():
            yield from iter_variable_refs(value, key_name=key_name)


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
        raw_call = mapping.get(const.KEY_PROCEDURE_CALL)
        if isinstance(raw_call, dict):
            call = cast(dict[str, object], raw_call)
            name = call.get(const.KEY_NAME)
            raw_args = call.get(const.KEY_ARGS)
            args = tuple(cast(Iterable[object], raw_args)) if isinstance(raw_args, list | tuple) else ()
            if isinstance(name, str):
                yield ("procedure", name, args)
            for argument in args:
                yield from iter_call_sites(argument)
            return

        name = mapping.get(const.KEY_NAME)
        raw_args = mapping.get(const.KEY_ARGS)
        if (
            const.KEY_VAR_NAME not in mapping
            and isinstance(name, str)
            and isinstance(raw_args, list | tuple)
        ):
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

    children = getattr(node, "children", None)
    if isinstance(children, list):
        for child in cast(list[object], children):
            yield from iter_call_sites(child)
        return
    if isinstance(children, tuple):
        for child in cast(tuple[object, ...], children):
            yield from iter_call_sites(child)
        return

    node_dict = getattr(node, "__dict__", None)
    if isinstance(node_dict, dict):
        for value in cast(dict[str, object], node_dict).values():
            yield from iter_call_sites(value)
