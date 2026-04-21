"""Shared AST traversal helpers."""

from __future__ import annotations

from ..grammar import constants as const


def iter_variable_refs(node: object, *, key_name: str = "var_name"):
    if isinstance(node, dict) and key_name in node:
        yield node
        return

    if isinstance(node, dict):
        for value in node.values():
            yield from iter_variable_refs(value, key_name=key_name)
        return

    if isinstance(node, tuple):
        for item in node:
            yield from iter_variable_refs(item, key_name=key_name)
        return

    if isinstance(node, list):
        for item in node:
            yield from iter_variable_refs(item, key_name=key_name)
        return

    children = getattr(node, "children", None)
    if children is not None:
        for child in children:
            yield from iter_variable_refs(child, key_name=key_name)
        return

    node_dict = getattr(node, "__dict__", None)
    if node_dict is not None:
        for value in node_dict.values():
            yield from iter_variable_refs(value, key_name=key_name)


def iter_call_sites(node: object):
    if isinstance(node, tuple) and len(node) == 3 and node[0] == const.KEY_FUNCTION_CALL:
        yield ("function", node[1], tuple(node[2] or ()))
        for argument in node[2] or ():
            yield from iter_call_sites(argument)
        return

    if isinstance(node, dict):
        if const.KEY_PROCEDURE_CALL in node and isinstance(node[const.KEY_PROCEDURE_CALL], dict):
            call = node[const.KEY_PROCEDURE_CALL]
            name = call.get(const.KEY_NAME)
            args = tuple(call.get(const.KEY_ARGS) or ())
            if isinstance(name, str):
                yield ("procedure", name, args)
            for argument in args:
                yield from iter_call_sites(argument)
            return

        if (
            const.KEY_NAME in node
            and const.KEY_ARGS in node
            and const.KEY_VAR_NAME not in node
            and isinstance(node.get(const.KEY_NAME), str)
            and isinstance(node.get(const.KEY_ARGS) or (), (list, tuple))
        ):
            args = tuple(node.get(const.KEY_ARGS) or ())
            yield ("procedure", node[const.KEY_NAME], args)
            for argument in args:
                yield from iter_call_sites(argument)
            for key, value in node.items():
                if key not in {const.KEY_NAME, const.KEY_ARGS}:
                    yield from iter_call_sites(value)
            return

        for value in node.values():
            yield from iter_call_sites(value)
        return

    if isinstance(node, list):
        for item in node:
            yield from iter_call_sites(item)
        return

    children = getattr(node, "children", None)
    if children is not None:
        for child in children:
            yield from iter_call_sites(child)
        return

    node_dict = getattr(node, "__dict__", None)
    if node_dict is not None:
        for value in node_dict.values():
            yield from iter_call_sites(value)
