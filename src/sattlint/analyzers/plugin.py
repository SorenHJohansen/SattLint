"""Public ``register_analyzer`` developer API (Phase G).

New analyzers are written as a plain ``run(context: AnalysisContext) -> Report``
function and declared with :func:`register_analyzer`. The framework owns dependency
ordering (``requires`` -> topological), shared-artifact memoization, and telemetry, so
adding an analyzer no longer requires touching ``context_kwargs``/provider plumbing.

Every registered analyzer is wired with ``direct_context=True``: its runnable always
receives the full :class:`~.framework.AnalysisContext`, so there is no way for a spec to
(accidentally) omit access to ``shared_artifacts`` — the exact bug class that previously
cost ``mms-interface`` ~114s. A ``requires=("variables",)`` declaration means "consume the
canonical variables collection", *not* "run variables again"; the dispatcher reuses the
already-collected foundation / collected views.
"""

from __future__ import annotations

from collections.abc import Callable

from .framework import Analyzer, AnalyzerSpec

_plugin_analyzers: dict[str, AnalyzerSpec] = {}


def register_analyzer(
    *,
    key: str,
    requires: tuple[str, ...] = (),
    contributes: str | None = None,
    name: str | None = None,
    description: str = "",
    enabled: bool = True,
) -> Callable[[Analyzer], Analyzer]:
    """Register a ``run(context) -> Report`` function as a new analyzer.

    Args:
        key: Unique analyzer key (matched case-insensitively).
        requires: Analyzer keys that must run and be collected first (``"variables"`` is the
            canonical collection pass; other keys map to their memoized result).
        contributes: Optional human/discoverability label for the shared artifact this analyzer
            writes (e.g. ``"derived_reports.my-analyzer"``).
        name: Display name (defaults to ``key``).
        description: One-line description for registry/tooling output.
        enabled: Whether the analyzer is active by default.

    Returns:
        The decorator that registers the given runnable and returns it unchanged.
    """
    canonical_key = key.casefold()

    def decorator(run: Analyzer) -> Analyzer:
        spec = AnalyzerSpec(
            key=key,
            name=name or key,
            description=description,
            run=run,
            requires=tuple(requires),
            enabled=enabled,
            direct_context=True,
            contributes=contributes,
        )
        _plugin_analyzers[canonical_key] = spec
        return run

    return decorator


def get_registered_plugin_analyzers() -> tuple[AnalyzerSpec, ...]:
    """Return the plugin analyzers registered via :func:`register_analyzer`.

    Registration is expected at import/startup time, before the analyzer catalog is first
    built; the registry merges these into the default analyzer set.
    """
    return tuple(_plugin_analyzers.values())


def clear_registered_plugin_analyzers() -> None:
    """Reset the plugin registry (used by tests)."""
    _plugin_analyzers.clear()


__all__ = ["get_registered_plugin_analyzers", "register_analyzer"]
