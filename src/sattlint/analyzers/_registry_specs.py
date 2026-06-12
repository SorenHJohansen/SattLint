"""Shared analyzer registry context-kwarg builders.

This module lives outside the ``registry`` package so semantic-layer imports can
reuse the context provider seam without triggering registry package
initialization.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .framework import AnalysisContext

type ContextValueProvider = Callable[[Any, AnalysisContext], object]


_CONTEXT_VALUE_PROVIDERS: dict[str, ContextValueProvider] = {
    "analysis_context": lambda _registry_module, context: context,
    "analyzed_target_is_library": lambda _registry_module, context: context.target_is_library,
    "config": lambda _registry_module, context: context.config,
    "debug": lambda _registry_module, context: context.debug,
    "graph": lambda _registry_module, context: context.graph,
    "include_dependency_moduletype_usage": lambda _registry_module, context: getattr(
        context, "include_dependency_moduletype_usage", None
    ),
    "mutually_exclusive_steps": lambda registry_module, context: (
        registry_module.get_configured_mutually_exclusive_step_sets(context.config)
    ),
    "rules": lambda registry_module, context: registry_module.get_configured_naming_rules(context.config),
    "sfc_mutually_exclusive_steps": lambda registry_module, context: (
        registry_module.get_configured_mutually_exclusive_step_sets(context.config)
    ),
    "sfc_step_contracts": lambda registry_module, context: registry_module.get_configured_step_contracts(
        context.config
    ),
    "selected_issue_kinds": lambda _registry_module, context: getattr(context, "selected_issue_kinds", None),
    "shared_artifacts": lambda _registry_module, context: getattr(context, "shared_artifacts", None),
    "step_contracts": lambda registry_module, context: registry_module.get_configured_step_contracts(context.config),
    "unavailable_libraries": lambda _registry_module, context: context.unavailable_libraries,
}


def build_context_kwargs(
    spec: object,
    registry_module: Any,
    context: AnalysisContext,
    *,
    overrides: dict[str, object] | None = None,
) -> dict[str, object]:
    context_kwargs = getattr(spec, "context_kwargs", ())
    return {
        kwarg_name: overrides[kwarg_name]
        if overrides and kwarg_name in overrides
        else _CONTEXT_VALUE_PROVIDERS[kwarg_name](registry_module, context)
        for kwarg_name in context_kwargs
    }


__all__ = ["build_context_kwargs"]
