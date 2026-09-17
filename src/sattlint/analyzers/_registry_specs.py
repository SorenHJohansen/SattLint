"""Shared analyzer registry helpers owned by the analyzer package."""

from __future__ import annotations

import sys
from collections.abc import Callable
from typing import Any, cast

from ._registry_spec_templates import AnalyzerSpecTemplate, default_spec_templates
from .framework import AnalysisContext, Analyzer, AnalyzerSpec, Report

type ContextValueProvider = Callable[[Any, AnalysisContext], object]


_CONTEXT_VALUE_PROVIDERS: dict[str, ContextValueProvider] = {
    "analysis_context": lambda _registry_module, context: context,
    "analyzed_target_is_library": lambda _registry_module, context: context.target_is_library,
    "config": lambda _registry_module, context: context.config,
    "debug": lambda _registry_module, context: context.debug,
    "graph": lambda _registry_module, context: context.graph,
    "include_dependency_moduletype_usage": lambda _registry_module, context: (
        context.include_dependency_moduletype_usage
    ),
    "shared_artifacts": lambda _registry_module, context: getattr(context, "shared_artifacts", None),
    "unavailable_libraries": lambda _registry_module, context: context.unavailable_libraries,
}


def build_context_kwargs(
    spec: AnalyzerSpecTemplate,
    registry_module: Any,
    context: AnalysisContext,
) -> dict[str, object]:
    return {
        kwarg_name: _CONTEXT_VALUE_PROVIDERS[kwarg_name](registry_module, context) for kwarg_name in spec.context_kwargs
    }


def _resolve_registry_module(registry_module: Any | None = None) -> Any:
    if registry_module is not None:
        return registry_module

    package_name = __package__
    if package_name is None:
        raise RuntimeError("Analyzer registry helpers package is unavailable.")

    sibling_registry_name = f"{package_name}.registry"
    resolved_registry_module = sys.modules.get(sibling_registry_name)
    if resolved_registry_module is None:
        raise RuntimeError("Analyzer registry package is unavailable.")
    return resolved_registry_module


def _build_runner(template: AnalyzerSpecTemplate, registry_module: Any) -> Analyzer:
    analyzer = getattr(registry_module, template.analyzer_attr)

    def _run(context: AnalysisContext) -> Report:
        if template.direct_context:
            return cast(Report, analyzer(context))

        kwargs = build_context_kwargs(template, registry_module, context)
        return cast(Report, analyzer(context.base_picture, **kwargs))

    return cast(Analyzer, _run)


def build_default_analyzers(
    registry_module: Any | None = None,
) -> list[AnalyzerSpec]:
    resolved_registry_module = _resolve_registry_module(registry_module)

    return [
        AnalyzerSpec(
            key=template.key,
            name=template.name,
            description=template.description,
            run=_build_runner(template, resolved_registry_module),
            category=template.category,
            enabled=template.enabled,
            scope=template.scope,
            context_kwargs=template.context_kwargs,
            direct_context=template.direct_context,
        )
        for template in default_spec_templates()
    ]


__all__ = [
    "AnalyzerSpec",
    "AnalyzerSpecTemplate",
    "build_context_kwargs",
    "build_default_analyzers",
    "default_spec_templates",
]
