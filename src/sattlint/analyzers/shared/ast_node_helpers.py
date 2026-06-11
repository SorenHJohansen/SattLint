from __future__ import annotations

from typing import cast

from ...grammar import constants as const

NodeTuple = tuple[object, ...]
NodeList = list[object]
NodeSequence = NodeTuple | NodeList
NodeDict = dict[str, object]


def object_tuple(node: object) -> NodeTuple | None:
    if isinstance(node, tuple):
        return cast(NodeTuple, node)
    return None


def object_list(node: object) -> NodeList | None:
    if isinstance(node, list):
        return cast(NodeList, node)
    return None


def object_sequence(node: object) -> NodeSequence | None:
    tuple_items = object_tuple(node)
    if tuple_items is not None:
        return tuple_items
    return object_list(node)


def string_key_dict(node: object) -> NodeDict | None:
    if isinstance(node, dict):
        return cast(NodeDict, node)
    return None


def statement_children(node: object) -> NodeSequence | None:
    if getattr(node, "data", None) != const.KEY_STATEMENT:
        return None
    return object_sequence(getattr(node, "children", None))


def sequence_as_list(node: object) -> list[object]:
    items = object_sequence(node)
    if items is None:
        return []
    return list(items)


def iter_branch_pairs(node: object) -> list[tuple[object, object]]:
    branches = object_sequence(node)
    if branches is None:
        return []
    pairs: list[tuple[object, object]] = []
    for branch in branches:
        branch_items = object_sequence(branch)
        if branch_items is None or len(branch_items) < 2:
            continue
        pairs.append((branch_items[0], branch_items[1]))
    return pairs


def object_dict_values(node: object) -> list[object]:
    node_dict = getattr(node, "__dict__", None)
    if not isinstance(node_dict, dict):
        return []
    return list(cast(NodeDict, node_dict).values())
