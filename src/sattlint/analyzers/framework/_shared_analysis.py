"""Per-target shared analysis artifacts for one analyzer batch."""

from __future__ import annotations

from collections.abc import Iterator, MutableMapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from sattline_parser.models.ast_model import ModuleTypeDef, Variable

from ... import cache as cache_module
from ...resolution import TypeGraph
from ...resolution.access_graph import AccessGraph
from ...resolution.scope import ScopeContext

if TYPE_CHECKING:
    from ..variables._usage_tracker import UsageTracker


@dataclass(slots=True)
class AnalysisPerformanceCounters:
    shared_artifact_holders_created: int = 0
    semantic_analyzer_reruns: int = 0
    semantic_precomputed_reports_used: int = 0
    variable_foundation_builds: int = 0
    variable_root_traversals: int = 0
    local_env_builds: int = 0


@dataclass(frozen=True, slots=True)
class ReportsByKey(MutableMapping[str, Any]):
    """Typed ``derived_reports`` compartment: memoized per-analyzer ``Report``s.

    This is one of the three typed shared-artifact compartments (§2.1) alongside
    ``foundation`` and ``collected_views``. Each analyzer writes its result **once** here
    (``derived_reports.set(key, report)``) and dependent analyzers / the dispatcher read it,
    so a ``requires=("variables",)`` consumer reuses the memoized result instead of re-running
    the underlying computation.

    Keyed by analyzer key (case-sensitively, matching the registry); values are the analyzer's
    ``Report``. Loose dictionaries are deliberately *not* the cross-analyzer contract — this
    wrapper gives a discoverable, named type with ``get``/``set``/``contains`` accessors.
    """

    _store: dict[str, Any] = field(default_factory=lambda: {}, init=False)

    def __getitem__(self, key: str) -> Any:
        return self._store[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self._store[key] = value

    def __delitem__(self, key: str) -> None:
        del self._store[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._store)

    def __len__(self) -> int:
        return len(self._store)

    def set(self, key: str, report: Any) -> None:
        """Store an analyzer's memoized ``Report`` under ``key`` (idempotent by key)."""
        self._store[key] = report

    def get_report(self, key: str) -> Any | None:
        return self._store.get(key)


@dataclass(frozen=True, slots=True)
class VariableAnalysisArtifacts:
    type_graph: TypeGraph
    typedef_index: dict[str, tuple[ModuleTypeDef, ...]]
    dependency_library_display_names: dict[str, str]
    root_env: dict[str, Variable]
    any_var_index: dict[str, tuple[Variable, ...]]


@dataclass(frozen=True, slots=True)
class CollectedViews:
    """The one instance-aware collection pass, exposed for derived analyzers.

    Populated once by the canonical ``variables`` analyzer after ``run()`` so layered
    consumers (mms, sfc, and cheap derived issue-kind analyzers) read typed collected
    state instead of re-running the instance traversal or reaching into analyzer internals.
    """

    access_graph: AccessGraph | None = None
    usage_tracker: UsageTracker | None = None
    alias_links: tuple[tuple[Variable, Variable, str], ...] = ()
    effect_flow_edges: dict[tuple[str, ...], tuple[tuple[str, ...], ...]] | None = None
    effect_flow_display_names: dict[tuple[str, ...], str] | None = None
    contexts_by_module_path: dict[tuple[str, ...], ScopeContext] | None = None
    root_env: dict[str, Variable] | None = None
    typedef_index: dict[str, tuple[ModuleTypeDef, ...]] | None = None


@dataclass(slots=True)
class AnalysisSharedArtifacts:
    derived_reports: ReportsByKey = field(default_factory=ReportsByKey)
    variable_analysis: VariableAnalysisArtifacts | None = None
    collected_views: CollectedViews | None = None
    local_variable_envs: dict[int, dict[str, Variable]] = field(default_factory=lambda: {})
    counters: AnalysisPerformanceCounters = field(default_factory=AnalysisPerformanceCounters)
    # The canonical, fully-run VariablesAnalyzer for the current target (populated by the
    # `variables` analyzer). Consumers such as mms-interface and sfc read its collected state
    # (`usage_tracker`, `_alias_links`, `access_graph`, ...) instead of re-running the instance
    # traversal. Typed as Any to avoid a framework -> variables dependency cycle.
    variable_analyzer: Any = None
    # Phase E persistent-foundation cache support. `foundation_cache` is the disk store (created
    # lazily from the user cache dir), typed as Any to keep framework -> app coupling nil. The
    # project cache key + source-content manifest are seeded by the app orchestration layer; when
    # all three are present, `ensure_foundation()` restores the foundation from disk instead of
    # re-deriving it. Any source change alters the content-derived key and simply misses.
    foundation_cache: Any = None
    foundation_project_cache_key: str | None = None
    foundation_source_manifest: dict[str, tuple[int, int]] | None = None

    def ensure_foundation(self, build_fn: Any) -> VariableAnalysisArtifacts | None:
        """Lazily materialize the analysis foundation (type graph + indices + symbol skeleton).

        Mirrors `AnalysisContext.ensure_*`: only computes when an analyzer actually asks, then
        memoizes on this holder. When persistent-cache data is seeded, prefers a disk restore over
        a rebuild and persists newly-built foundations for the next cold run. The foundation must be
        treated as read-only shared state by consumers (never mutated).
        """
        if self.variable_analysis is not None:
            return self.variable_analysis

        if (
            self.foundation_cache is None
            and self.foundation_project_cache_key is not None
            and self.foundation_source_manifest is not None
        ):
            self.foundation_cache = cache_module.FoundationCache(cache_module.get_cache_dir())

        foundation_cache: Any = self.foundation_cache
        project_cache_key: str | None = self.foundation_project_cache_key
        source_manifest: dict[str, tuple[int, int]] | None = self.foundation_source_manifest
        cache_key: str | None = None
        if foundation_cache is not None and project_cache_key is not None and source_manifest is not None:
            cache_key = cache_module.compute_foundation_cache_key(project_cache_key, source_manifest)

        restored: VariableAnalysisArtifacts | None = None
        if foundation_cache is not None and cache_key is not None:
            payload = foundation_cache.load(cache_key)
            if isinstance(payload, VariableAnalysisArtifacts):
                restored = payload

        if restored is not None:
            self.variable_analysis = restored
            return restored

        built = build_fn()
        self.variable_analysis = built
        self.counters.variable_foundation_builds += 1
        if foundation_cache is not None and cache_key is not None:
            foundation_cache.save(cache_key, built)
        return built


__all__ = [
    "AnalysisPerformanceCounters",
    "AnalysisSharedArtifacts",
    "CollectedViews",
    "ReportsByKey",
    "VariableAnalysisArtifacts",
]
