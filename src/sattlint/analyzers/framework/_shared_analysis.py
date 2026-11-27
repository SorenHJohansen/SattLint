"""Per-target shared analysis artifacts for one analyzer batch."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from sattlint.parser_api import ModuleTypeDef, Variable

from ...resolution import TypeGraph
from ...resolution.access_graph import AccessGraph
from ...resolution.scope import ScopeContext

if TYPE_CHECKING:
    from ..variables._usage_tracker import UsageTracker


@dataclass(slots=True)
class AnalysisPerformanceCounters:
    shared_artifact_holders_created: int = 0
    variable_foundation_builds: int = 0
    variable_root_traversals: int = 0
    local_env_builds: int = 0


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
    consumers (sfc, and cheap derived issue-kind analyzers) read typed collected
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
    variable_analysis: VariableAnalysisArtifacts | None = None
    collected_views: CollectedViews | None = None
    local_variable_envs: dict[int, dict[str, Variable]] = field(default_factory=lambda: {})
    counters: AnalysisPerformanceCounters = field(default_factory=AnalysisPerformanceCounters)
    # The canonical, fully-run VariablesAnalyzer for the current target (populated by the
    # `variables` analyzer). Consumers such as sfc read its collected state
    # (`usage_tracker`, `_alias_links`, `access_graph`, ...) instead of re-running the instance
    # traversal. Typed as Any to avoid a framework -> variables dependency cycle.
    variable_analyzer: Any = None

    def ensure_foundation(self, build_fn: Callable[[], VariableAnalysisArtifacts]) -> VariableAnalysisArtifacts:
        """Lazily materialize the analysis foundation (type graph + indices + symbol skeleton).

        Mirrors `AnalysisContext.ensure_*`: only computes when an analyzer actually asks, then
        memoizes on this holder. The foundation is scoped to one run and one parse: it holds
        ``Variable`` and ``ModuleTypeDef`` instances, so it is never restored from or persisted to
        disk. A consumer must treat it as read-only shared state (never mutate it).
        """
        if self.variable_analysis is None:
            self.variable_analysis = build_fn()
            self.counters.variable_foundation_builds += 1
        return self.variable_analysis


__all__ = [
    "AnalysisPerformanceCounters",
    "AnalysisSharedArtifacts",
    "CollectedViews",
    "VariableAnalysisArtifacts",
]
