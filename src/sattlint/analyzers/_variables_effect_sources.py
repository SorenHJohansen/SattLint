"""Pure helpers for effect-flow source collection."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from sattlint.resolution.scope import ScopeContext

from ..grammar import constants as const
from .sattline_builtins import get_function_signature

EffectKey = tuple[str, ...]
ResolveEffectKey = Callable[[str, ScopeContext], EffectKey | None]


def collect_function_input_effect_keys(
    fn_name: str | None,
    args: list[Any],
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
        if args and isinstance(args[0], dict) and const.KEY_VAR_NAME in args[0]:
            key = resolve_effect_key(args[0][const.KEY_VAR_NAME], context)
            return {key} if key is not None else set()
        return set()

    if fn_key == "initvariable":
        if len(args) >= 2 and isinstance(args[1], dict) and const.KEY_VAR_NAME in args[1]:
            key = resolve_effect_key(args[1][const.KEY_VAR_NAME], context)
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
    obj: Any,
    context: ScopeContext,
    *,
    resolve_effect_key: ResolveEffectKey,
) -> set[EffectKey]:
    """Recursively collect effect keys from an expression tree."""
    sources: set[EffectKey] = set()

    if obj is None:
        return sources

    if isinstance(obj, dict):
        if const.KEY_VAR_NAME in obj:
            full_ref = obj[const.KEY_VAR_NAME]
            key = resolve_effect_key(full_ref, context)
            if key is not None:
                sources.add(key)
            return sources
        for value in obj.values():
            sources.update(
                collect_expression_effect_sources(
                    value,
                    context,
                    resolve_effect_key=resolve_effect_key,
                )
            )
        return sources

    if isinstance(obj, list):
        for item in obj:
            sources.update(
                collect_expression_effect_sources(
                    item,
                    context,
                    resolve_effect_key=resolve_effect_key,
                )
            )
        return sources

    if hasattr(obj, "data"):
        for child in getattr(obj, "children", []):
            sources.update(
                collect_expression_effect_sources(
                    child,
                    context,
                    resolve_effect_key=resolve_effect_key,
                )
            )
        return sources

    if isinstance(obj, tuple):
        if obj and obj[0] == const.KEY_FUNCTION_CALL:
            _, fn_name, fn_args = obj
            return collect_function_input_effect_keys(
                fn_name,
                fn_args or [],
                context,
                resolve_effect_key=resolve_effect_key,
            )
        items = obj[1:] if obj and isinstance(obj[0], str) else obj
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
