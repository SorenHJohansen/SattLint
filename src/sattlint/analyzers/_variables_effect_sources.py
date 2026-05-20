"""Pure helpers for effect-flow source collection."""

from __future__ import annotations

from collections.abc import Callable

from sattlint.resolution.scope import ScopeContext

from ..grammar import constants as const
from .ast_node_helpers import (
    object_list as _object_list,
)
from .ast_node_helpers import (
    object_sequence as _object_sequence,
)
from .ast_node_helpers import (
    object_tuple as _object_tuple,
)
from .ast_node_helpers import (
    sequence_as_list as _sequence_as_list,
)
from .ast_node_helpers import (
    string_key_dict as _string_key_dict,
)
from .sattline_builtins import get_function_signature

EffectKey = tuple[str, ...]
ResolveEffectKey = Callable[[str, ScopeContext], EffectKey | None]


def _var_name_from_mapping(node: object) -> str | None:
    mapping = _string_key_dict(node)
    if mapping is None:
        return None
    raw_name = mapping.get(const.KEY_VAR_NAME)
    return raw_name if isinstance(raw_name, str) and raw_name else None


def collect_function_input_effect_keys(
    fn_name: str | None,
    args: list[object],
    context: ScopeContext,
    *,
    resolve_effect_key: ResolveEffectKey,
) -> set[EffectKey]:
    """Collect source-side effect keys for a builtin or expression call."""
    if not fn_name:
        input_sources: set[EffectKey] = set()
        for arg in args:
            input_sources.update(
                collect_expression_effect_sources(
                    arg,
                    context,
                    resolve_effect_key=resolve_effect_key,
                )
            )
        return input_sources

    fn_key = fn_name.casefold()
    if fn_key in {"copyvariable", "copyvarnosort"}:
        full_ref = _var_name_from_mapping(args[0]) if args else None
        if full_ref is not None:
            key = resolve_effect_key(full_ref, context)
            return {key} if key is not None else set()
        return set()

    if fn_key == "initvariable":
        full_ref = _var_name_from_mapping(args[1]) if len(args) >= 2 else None
        if full_ref is not None:
            key = resolve_effect_key(full_ref, context)
            return {key} if key is not None else set()
        return set()

    sig = get_function_signature(fn_name)
    if sig is None:
        fallback_sources: set[EffectKey] = set()
        for arg in args:
            fallback_sources.update(
                collect_expression_effect_sources(
                    arg,
                    context,
                    resolve_effect_key=resolve_effect_key,
                )
            )
        return fallback_sources

    signature_sources: set[EffectKey] = set()
    for idx, arg in enumerate(args):
        direction = "in"
        if idx < len(sig.parameters):
            direction = sig.parameters[idx].direction
        if direction not in {"in", "in var", "inout"}:
            continue
        signature_sources.update(
            collect_expression_effect_sources(
                arg,
                context,
                resolve_effect_key=resolve_effect_key,
            )
        )
    return signature_sources


def collect_expression_effect_sources(
    obj: object,
    context: ScopeContext,
    *,
    resolve_effect_key: ResolveEffectKey,
) -> set[EffectKey]:
    """Recursively collect effect keys from an expression tree."""
    sources: set[EffectKey] = set()

    if obj is None:
        return sources

    node_dict = _string_key_dict(obj)
    if node_dict is not None:
        if const.KEY_VAR_NAME in node_dict:
            full_ref = node_dict[const.KEY_VAR_NAME]
            if isinstance(full_ref, str):
                key = resolve_effect_key(full_ref, context)
                if key is not None:
                    sources.add(key)
            return sources
        for value in node_dict.values():
            sources.update(
                collect_expression_effect_sources(
                    value,
                    context,
                    resolve_effect_key=resolve_effect_key,
                )
            )
        return sources

    list_node = _object_list(obj)
    if list_node is not None:
        for item in list_node:
            sources.update(
                collect_expression_effect_sources(
                    item,
                    context,
                    resolve_effect_key=resolve_effect_key,
                )
            )
        return sources

    children = _object_sequence(getattr(obj, "children", None))
    if children is not None:
        for child in children:
            sources.update(
                collect_expression_effect_sources(
                    child,
                    context,
                    resolve_effect_key=resolve_effect_key,
                )
            )
        return sources

    tuple_node = _object_tuple(obj)
    if tuple_node is not None:
        if tuple_node and tuple_node[0] == const.KEY_FUNCTION_CALL:
            fn_name = tuple_node[1] if len(tuple_node) > 1 and isinstance(tuple_node[1], str) else None
            fn_args = _sequence_as_list(tuple_node[2] if len(tuple_node) > 2 else None)
            return collect_function_input_effect_keys(
                fn_name,
                fn_args,
                context,
                resolve_effect_key=resolve_effect_key,
            )
        items = tuple_node[1:] if tuple_node and isinstance(tuple_node[0], str) else tuple_node
        for item in items:
            sources.update(
                collect_expression_effect_sources(
                    item,
                    context,
                    resolve_effect_key=resolve_effect_key,
                )
            )
        return sources

    return sources
