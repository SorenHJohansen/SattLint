"""Shared helpers and type aliases for module transformer mixins."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from typing import Any, Literal, cast

from lark import Tree
from lark.visitors import v_args as _lark_v_args  # pyright: ignore[reportUnknownVariableType]

from sattline_parser.grammar import constants as const
from sattline_parser.models.ast_model import FrameModule, ModuleTypeInstance, SingleModule, SourceSpan

TransformerTree = Tree[Any]
TransformerItem = object
ModuleInvocation = SingleModule | FrameModule | ModuleTypeInstance
type VArgsDecorator = Callable[[object], object]
_V_ARGS_FACTORY = cast(Callable[..., VArgsDecorator], _lark_v_args)


def _v_args(*args: Any, **kwargs: Any) -> VArgsDecorator:
    return _V_ARGS_FACTORY(*args, **kwargs)


def _tree_children(tree: TransformerTree) -> list[TransformerItem]:
    return cast(list[TransformerItem], tree.children)


def _submodule_children(children: Iterable[TransformerItem]) -> list[ModuleInvocation]:
    submodules: list[ModuleInvocation] = []
    for child in children:
        if isinstance(child, list):
            nested = cast(list[TransformerItem], child)
            submodules.extend(
                [item for item in nested if isinstance(item, (SingleModule, FrameModule, ModuleTypeInstance))]
            )
        elif isinstance(child, (SingleModule, FrameModule, ModuleTypeInstance)):
            submodules.append(child)
    return submodules


def _float_tuple(raw: object, size: Literal[2, 5]) -> tuple[float, ...] | None:
    if not isinstance(raw, tuple):
        return None
    raw_values = cast(tuple[object, ...], raw)
    if len(raw_values) < size:
        return None
    values = raw_values[:size]
    if not all(isinstance(value, int | float) for value in values):
        return None
    return tuple(float(cast(int | float, value)) for value in values)


def _groupconn_value(info: dict[str, object] | None) -> dict[Any, Any] | None:
    if info is None:
        return None
    groupconn = info.get("groupconn")
    return cast(dict[Any, Any] | None, groupconn)


def _coord_pair(raw: object) -> tuple[float, float] | None:
    values = _float_tuple(raw, 2)
    if values is None:
        return None
    return cast(tuple[float, float], values)


def _meta_span(meta: Any) -> SourceSpan | None:
    """Extract source span from Lark meta."""
    line = getattr(meta, "line", None)
    column = getattr(meta, "column", None)
    if line is None or column is None:
        return None
    return SourceSpan(line=int(line), column=int(column))


def _flatten_items(items: Iterable[TransformerItem]) -> Iterator[TransformerItem]:
    """Yield flat stream of items from possibly nested lists and Trees."""
    for it in items:
        if isinstance(it, list):
            yield from _flatten_items(cast(list[TransformerItem], it))
        elif isinstance(it, Tree) and it.data in (
            const.TREE_TAG_BASE_MODULE_BODY,
            const.TREE_TAG_MODULE_BODY,
        ):
            tree = cast(TransformerTree, it)
            yield from _flatten_items(cast(list[TransformerItem], tree.children))
        else:
            yield it


__all__ = [
    "ModuleInvocation",
    "TransformerItem",
    "TransformerTree",
    "_coord_pair",
    "_flatten_items",
    "_float_tuple",
    "_groupconn_value",
    "_meta_span",
    "_submodule_children",
    "_tree_children",
    "_v_args",
]
