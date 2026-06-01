"""Per-target shared analysis artifacts for one analyzer batch."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sattline_parser.models.ast_model import ModuleTypeDef, Variable

from ..resolution import TypeGraph


@dataclass(slots=True)
class AnalysisPerformanceCounters:
    shared_artifact_holders_created: int = 0
    semantic_analyzer_reruns: int = 0
    semantic_precomputed_reports_used: int = 0
    variable_foundation_builds: int = 0
    local_env_builds: int = 0


@dataclass(frozen=True, slots=True)
class VariableAnalysisArtifacts:
    type_graph: TypeGraph
    typedef_index: dict[str, tuple[ModuleTypeDef, ...]]
    dependency_library_display_names: dict[str, str]
    root_env: dict[str, Variable]
    any_var_index: dict[str, tuple[Variable, ...]]


@dataclass(slots=True)
class AnalysisSharedArtifacts:
    reports_by_analyzer_key: dict[str, Any] = field(default_factory=lambda: {})
    variable_analysis: VariableAnalysisArtifacts | None = None
    local_variable_envs: dict[int, dict[str, Variable]] = field(default_factory=lambda: {})
    counters: AnalysisPerformanceCounters = field(default_factory=AnalysisPerformanceCounters)


__all__ = [
    "AnalysisPerformanceCounters",
    "AnalysisSharedArtifacts",
    "VariableAnalysisArtifacts",
]
