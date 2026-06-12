"""Analyzer spec factory extracted from the analyzer registry."""

from __future__ import annotations

import sys
from typing import Any, cast

from .._registry_specs import build_context_kwargs
from ..framework import AnalysisContext, Analyzer, AnalyzerSpec, Report
from ._registry_spec_templates import AnalyzerSpecTemplate, default_spec_templates


def _registry_module() -> Any:
    package_name = __package__
    if package_name is None:
        raise RuntimeError("Registry specs module package is unavailable.")
    return sys.modules[package_name]


def _build_runner(template: AnalyzerSpecTemplate, registry_module: Any) -> Analyzer:
    def _run(context: AnalysisContext) -> Report:
        analyzer = getattr(registry_module, template.analyzer_attr)
        if template.direct_context:
            return cast(Report, analyzer(context))

        kwargs = build_context_kwargs(template, registry_module, context)
        return cast(Report, analyzer(context.base_picture, **kwargs))

    return cast(Analyzer, _run)


def build_default_analyzers(*, semantic_layer_analyzer_key: str) -> list[AnalyzerSpec]:
    registry_module = _registry_module()

    return [
        AnalyzerSpec(
            key=template.key,
            name=template.name,
            description=template.description,
            run=_build_runner(template, registry_module),
            requires=template.requires,
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
