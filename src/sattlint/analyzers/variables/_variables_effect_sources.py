"""Pure helpers for effect-flow source collection."""

from __future__ import annotations

from collections.abc import Callable

from sattlint.parser_api import FuncCall, VarRef, get_function_signature, walk
from sattlint.resolution.scope import ScopeContext

EffectKey = tuple[str, ...]
ResolveEffectKey = Callable[[str, ScopeContext], EffectKey | None]


def _var_name_from_mapping(node: object) -> str | None:
    if isinstance(node, VarRef):
        return node.name or None
    return None


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

    if isinstance(obj, FuncCall):
        return collect_function_input_effect_keys(
            obj.name,
            list(obj.args),
            context,
            resolve_effect_key=resolve_effect_key,
        )

    for event in walk(obj):
        node = event.node
        if not isinstance(node, VarRef):
            continue
        full_ref = node.name
        if not full_ref:
            continue
        key = resolve_effect_key(full_ref, context)
        if key is not None:
            sources.add(key)

    return sources
