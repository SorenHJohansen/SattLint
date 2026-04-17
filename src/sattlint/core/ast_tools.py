"""Shared AST traversal helpers."""

from __future__ import annotations


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
