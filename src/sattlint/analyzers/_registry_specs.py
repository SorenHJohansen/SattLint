"""Analyzer spec factory extracted from the analyzer registry."""

from __future__ import annotations

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
    "step_contracts": lambda registry_module, context: registry_module.get_configured_step_contracts(context.config),
    "unavailable_libraries": lambda _registry_module, context: context.unavailable_libraries,
}


def build_context_kwargs(
    spec: AnalyzerSpecTemplate | AnalyzerSpec,
    registry_module: Any,
    context: AnalysisContext,
    *,
    overrides: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        kwarg_name: overrides[kwarg_name]
        if overrides and kwarg_name in overrides
        else _CONTEXT_VALUE_PROVIDERS[kwarg_name](registry_module, context)
        for kwarg_name in spec.context_kwargs
    }


def _build_runner(template: AnalyzerSpecTemplate, registry_module: Any) -> Analyzer:
    def _run(context: AnalysisContext) -> Report:
        analyzer = getattr(registry_module, template.analyzer_attr)
        if template.direct_context:
            return cast(Report, analyzer(context))

        kwargs = build_context_kwargs(template, registry_module, context)
        return cast(Report, analyzer(context.base_picture, **kwargs))

    return cast(Analyzer, _run)


def build_default_analyzers(*, semantic_layer_analyzer_key: str) -> list[AnalyzerSpec]:
    from . import registry as registry_module

    return [
        AnalyzerSpec(
            key=template.key,
            name=template.name,
            description=template.description,
            run=_build_runner(template, registry_module),
            enabled=template.enabled,
            supports_live_diagnostics=template.supports_live_diagnostics,
            analyzer_attr=template.analyzer_attr,
            context_kwargs=template.context_kwargs,
            direct_context=template.direct_context,
            semantic_mapping_kind=template.semantic_mapping_kind,
            semantic_rule_source=template.semantic_rule_source,
        )
        for template in default_spec_templates(semantic_layer_analyzer_key)
    ]


__all__ = ["AnalyzerSpec", "build_context_kwargs", "build_default_analyzers"]
