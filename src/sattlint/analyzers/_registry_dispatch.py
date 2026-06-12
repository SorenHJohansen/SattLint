"""Shared analyzer registry dispatch helpers.

These helpers live outside the ``registry`` package so semantic-layer imports
can execute without triggering registry package initialization.
"""

from __future__ import annotations

from collections.abc import Callable, Collection, Mapping
from typing import Any, cast

from ._registry_specs import build_context_kwargs
from .framework import AnalysisContext, Report

type BuildContextKwargsFn = Callable[..., dict[str, object]]


def _registry_module() -> Any:
    from . import registry as registry_module  # noqa: PLC0415 - avoid registry package init cycles

    return registry_module


def _canonical_key(key: str) -> str:
    return key.casefold()


def _with_required_analyzers(
    analyzers: tuple[Any, ...], *, available_analyzers: tuple[Any, ...] | None = None
) -> tuple[Any, ...]:
    keyed_specs = {
        _canonical_key(cast(str, getattr(spec, "key", ""))): spec
        for spec in (available_analyzers or analyzers)
        if getattr(spec, "key", "")
    }
    ordered_specs: list[Any] = []
    seen_keys: set[str] = set()

    def _append_with_requirements(spec: Any) -> None:
        spec_key = _canonical_key(cast(str, getattr(spec, "key", "")))
        if spec_key in seen_keys:
            return
        for required_key in cast(tuple[str, ...], getattr(spec, "requires", ())):
            required_spec = keyed_specs.get(_canonical_key(required_key))
            if required_spec is not None:
                _append_with_requirements(required_spec)
        seen_keys.add(spec_key)
        ordered_specs.append(spec)

    for spec in analyzers:
        _append_with_requirements(spec)

    return tuple(ordered_specs)


def _requirement_satisfied(required_key: str, shared_artifacts: Any | None) -> bool:
    if shared_artifacts is None:
        return False
    if _canonical_key(required_key) == "variables":
        return getattr(shared_artifacts, "variable_analysis", None) is not None
    reports_by_key = getattr(shared_artifacts, "reports_by_analyzer_key", None)
    if not isinstance(reports_by_key, Mapping):
        return False
    return required_key in reports_by_key


def _validate_required_analyzers(spec: Any, context: AnalysisContext) -> None:
    missing = [
        required_key
        for required_key in cast(tuple[str, ...], getattr(spec, "requires", ()))
        if _canonical_key(required_key) != _canonical_key(cast(str, getattr(spec, "key", "")))
        and not _requirement_satisfied(required_key, getattr(context, "shared_artifacts", None))
    ]
    if missing:
        required = ", ".join(sorted(missing))
        raise RuntimeError(f"Analyzer '{spec.key}' requires analyzer results from: {required}")


def _order_analyzers_for_batch(analyzers: tuple[Any, ...], *, semantic_layer_analyzer_key: str) -> tuple[Any, ...]:
    semantic_analyzers = tuple(spec for spec in analyzers if getattr(spec, "key", None) == semantic_layer_analyzer_key)
    if not semantic_analyzers:
        return analyzers
    return (
        tuple(spec for spec in analyzers if getattr(spec, "key", None) != semantic_layer_analyzer_key)
        + semantic_analyzers
    )


def get_cli_dispatch_analyzers(
    *,
    selected_keys: Collection[str] | None,
    get_enabled_analyzers_fn: Callable[[], list[Any]],
) -> tuple[Any, ...]:
    registry_module = _registry_module()

    analyzers = tuple(spec for spec in get_enabled_analyzers_fn() if registry_module._is_batch_dispatch_analyzer(spec))
    available_analyzers = analyzers
    if selected_keys:
        selected = {registry_module.canonicalize_analyzer_key(key) for key in selected_keys}
        analyzers = tuple(spec for spec in analyzers if getattr(spec, "key", "").casefold() in selected)
    analyzers = _with_required_analyzers(analyzers, available_analyzers=available_analyzers)
    return _order_analyzers_for_batch(
        analyzers,
        semantic_layer_analyzer_key=registry_module.SEMANTIC_LAYER_ANALYZER_KEY,
    )


def get_semantic_contributor_specs() -> tuple[Any, ...]:
    registry_module = _registry_module()

    return tuple(
        analyzer.spec
        for analyzer in registry_module.get_default_analyzer_catalog().analyzers
        if analyzer.spec.enabled
        and analyzer.spec.semantic_mapping_kind is not None
        and analyzer.spec.key != registry_module.SEMANTIC_LAYER_ANALYZER_KEY
    )


def get_registry_analyzer_spec(key: str) -> Any:
    registry_module = _registry_module()

    canonical_key = registry_module.canonicalize_analyzer_key(key)
    for analyzer in registry_module.get_default_analyzer_catalog().analyzers:
        if analyzer.spec.key.casefold() == canonical_key:
            return analyzer.spec
    raise KeyError(key)


def get_lsp_projection_analyzers() -> tuple[Any, ...]:
    registry_module = _registry_module()

    excluded_keys = {registry_module.SEMANTIC_LAYER_ANALYZER_KEY.casefold(), "variables"}
    return tuple(
        analyzer
        for analyzer in registry_module.get_default_analyzer_catalog().analyzers
        if analyzer.delivery.lsp_exposed and analyzer.spec.key.casefold() not in excluded_keys
    )


def run_registry_analyzer(
    spec: Any,
    context: AnalysisContext,
    *,
    overrides: Mapping[str, object] | None = None,
    use_shared_artifacts: bool = False,
    build_context_kwargs_fn: BuildContextKwargsFn = build_context_kwargs,
) -> Report:
    _validate_required_analyzers(spec, context)
    shared_artifacts = context.shared_artifacts
    if use_shared_artifacts and shared_artifacts is not None:
        cached_report = shared_artifacts.reports_by_analyzer_key.get(spec.key)
        if cached_report is not None:
            shared_artifacts.counters.semantic_precomputed_reports_used += 1
            return cast(Report, cached_report)

    analyzer_attr = cast(str, getattr(spec, "analyzer_attr", ""))
    if analyzer_attr:
        registry_module = _registry_module()

        analyzer_fn = getattr(registry_module, analyzer_attr)
        if getattr(spec, "direct_context", False):
            report = analyzer_fn(context)
        else:
            report = analyzer_fn(
                context.base_picture,
                **build_context_kwargs_fn(
                    spec,
                    registry_module,
                    context,
                    overrides=None if overrides is None else dict(overrides),
                ),
            )
    else:
        report = spec.run(context)

    if use_shared_artifacts and shared_artifacts is not None:
        shared_artifacts.counters.semantic_analyzer_reruns += 1
    return cast(Report, report)


__all__ = [
    "get_cli_dispatch_analyzers",
    "get_lsp_projection_analyzers",
    "get_registry_analyzer_spec",
    "get_semantic_contributor_specs",
    "run_registry_analyzer",
]
