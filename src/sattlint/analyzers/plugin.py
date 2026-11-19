"""Public ``register_analyzer`` developer API (Phase G).

New analyzers are written as a plain ``run(context: AnalysisContext) -> Report``
function and declared with :func:`register_analyzer`. The framework owns
shared-artifact memoization and telemetry, so adding an analyzer no longer
requires touching ``context_kwargs``/provider plumbing.

Every registered analyzer is wired with ``direct_context=True``: its runnable always
receives the full :class:`~.framework.AnalysisContext`, so there is no way for a spec to
(accidentally) omit access to ``shared_artifacts``.
"""

from __future__ import annotations

from collections.abc import Callable

from ._registry_spec_templates import default_spec_templates
from .framework import Analyzer, AnalyzerSpec

_plugin_analyzers: dict[str, AnalyzerSpec] = {}
_plugin_generation = 0
_BUILTIN_ANALYZER_KEYS = frozenset(template.key.casefold() for template in default_spec_templates())
#: Retired spellings that resolve to a current key. Registration must honour
#: them too, or a plugin named with a retired spelling slips past the
#: reserved-key guard and later replaces the built-in entry.
LEGACY_ANALYZER_KEY_ALIASES: dict[str, str] = {
    "same_cycle": "same-cycle",
}


def get_plugin_registry_generation() -> int:
    """Return a counter that changes on every plugin registration change.

    The analyzer catalogue is expensive to build, so it is cached. Keying the
    cache by this counter keeps the catalogue in step with the plugin registry
    regardless of whether a plugin registers before or after the first build.
    """
    return _plugin_generation


def _bump_plugin_registry_generation() -> None:
    global _plugin_generation
    _plugin_generation += 1


def register_analyzer(
    *,
    key: str,
    contributes: str | None = None,
    name: str | None = None,
    description: str = "",
    enabled: bool = True,
) -> Callable[[Analyzer], Analyzer]:
    """Register a ``run(context) -> Report`` function as a new analyzer.

    Args:
        key: Unique analyzer key (matched case-insensitively).
        contributes: Optional human/discoverability label for the shared artifact this analyzer
            writes (e.g. ``"my-analyzer-artifacts"``).
        name: Display name (defaults to ``key``).
        description: One-line description for registry/tooling output.
        enabled: Whether the analyzer is active by default.

    Returns:
        The decorator that registers the given runnable and returns it unchanged.
    """
    canonical_key = LEGACY_ANALYZER_KEY_ALIASES.get(key.casefold(), key.casefold())
    if canonical_key in _BUILTIN_ANALYZER_KEYS:
        raise ValueError(f"Analyzer key {key!r} is reserved by a built-in analyzer.")

    def decorator(run: Analyzer) -> Analyzer:
        existing = _plugin_analyzers.get(canonical_key)
        if existing is not None:
            raise ValueError(f"Analyzer key {key!r} is already registered by {existing.name!r}.")
        spec = AnalyzerSpec(
            key=key,
            name=name or key,
            description=description,
            run=run,
            enabled=enabled,
            direct_context=True,
            contributes=contributes,
        )
        _plugin_analyzers[canonical_key] = spec
        _bump_plugin_registry_generation()
        return run

    return decorator


def get_registered_plugin_analyzers() -> tuple[AnalyzerSpec, ...]:
    """Return the plugin analyzers registered via :func:`register_analyzer`.

    Registration is expected at import/startup time, before the analyzer catalog is first
    built; the registry merges these into the default analyzer set. Entries are
    sorted by canonical key so the analyzer order never depends on import order.
    """
    return tuple(_plugin_analyzers[key] for key in sorted(_plugin_analyzers))


def clear_registered_plugin_analyzers() -> None:
    """Reset the plugin registry (used by tests)."""
    _plugin_analyzers.clear()
    _bump_plugin_registry_generation()


__all__ = [
    "clear_registered_plugin_analyzers",
    "get_plugin_registry_generation",
    "get_registered_plugin_analyzers",
    "register_analyzer",
]
