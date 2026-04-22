"""Registry of machine-readable artifacts emitted by developer tooling."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ArtifactDefinition:
    artifact_id: str
    filename: str
    producer: str
    schema_kind: str
    schema_version: int
    profiles: tuple[str, ...] = ("full",)
    optional: bool = False
    blocking: bool = False
    depends_on: tuple[str, ...] = ()
    used_by: tuple[str, ...] = ()

    def is_available(self, *, profile: str, enabled: bool = True) -> bool:
        return enabled and profile in self.profiles

    def to_dict(self, *, enabled: bool = True) -> dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "filename": self.filename,
            "producer": self.producer,
            "schema_kind": self.schema_kind,
            "schema_version": self.schema_version,
            "profiles": list(self.profiles),
            "optional": self.optional,
            "blocking": self.blocking,
            "depends_on": list(self.depends_on),
            "used_by": list(self.used_by),
            "enabled": enabled,
        }


PIPELINE_ARTIFACTS: tuple[ArtifactDefinition, ...] = (
    ArtifactDefinition("progress", "progress.json", "progress", "sattlint.pipeline.progress", 1, profiles=("quick", "full")),
    ArtifactDefinition("status", "status.json", "status", "sattlint.pipeline.status", 1, profiles=("quick", "full"), blocking=True),
    ArtifactDefinition("summary", "summary.json", "summary", "sattlint.pipeline.summary", 1, profiles=("quick", "full"), blocking=True),
    ArtifactDefinition("findings", "findings.json", "findings", "sattlint.findings", 1, profiles=("quick", "full"), blocking=True),
    ArtifactDefinition("analysis_diff", "analysis_diff.json", "analysis_diff", "sattlint.analysis_diff", 1, profiles=("quick", "full"), optional=True, depends_on=("findings",)),
    ArtifactDefinition("corpus_results", "corpus_results.json", "corpus_results", "sattlint.corpus_results", 1, profiles=("quick", "full"), optional=True, blocking=True),
    ArtifactDefinition("artifact_registry", "artifact_registry.json", "artifact_registry", "sattlint.artifact_registry", 1, profiles=("quick", "full")),
    ArtifactDefinition("environment", "environment.json", "environment", "sattlint.environment", 1, profiles=("quick", "full")),
    ArtifactDefinition("ruff", "ruff.json", "ruff", "sattlint.tool_report", 1, profiles=("quick", "full"), blocking=True),
    ArtifactDefinition("pyright", "pyright.json", "pyright", "sattlint.tool_report", 1, profiles=("quick", "full"), blocking=True),
    ArtifactDefinition("pytest", "pytest.json", "pytest", "sattlint.tool_report", 1, profiles=("quick", "full"), blocking=True),
    ArtifactDefinition("vulture", "vulture.json", "vulture", "sattlint.tool_report", 1, profiles=("full",), optional=True),
    ArtifactDefinition("bandit", "bandit.json", "bandit", "sattlint.tool_report", 1, profiles=("full",), optional=True),
    ArtifactDefinition("architecture", "architecture.json", "architecture", "sattlint.architecture", 1, profiles=("full",), optional=True),
    ArtifactDefinition("analyzer_registry", "analyzer_registry.json", "analyzer_registry", "sattlint.analyzer_registry", 1, profiles=("full",), optional=True),
    ArtifactDefinition("dependency_graph", "dependency_graph.json", "dependency_graph", "sattlint.graph", 1, profiles=("full",), optional=True),
    ArtifactDefinition("call_graph", "call_graph.json", "call_graph", "sattlint.graph", 1, profiles=("full",), optional=True),
    ArtifactDefinition("impact_analysis", "impact_analysis.json", "impact_analysis", "sattlint.impact_analysis", 1, profiles=("full",), optional=True),
    ArtifactDefinition("trace", "trace.json", "trace", "sattlint.trace", 1, profiles=("full",), optional=True),
)


AUDIT_ARTIFACTS: tuple[ArtifactDefinition, ...] = (
    ArtifactDefinition("progress", "progress.json", "repo_audit_progress", "sattlint.repo_audit.progress", 1, profiles=("quick", "full", "leaks")),
    ArtifactDefinition("status", "status.json", "repo_audit", "sattlint.repo_audit.status", 1, profiles=("quick", "full", "leaks"), blocking=True),
    ArtifactDefinition("summary", "summary.json", "repo_audit", "sattlint.repo_audit.summary", 1, profiles=("quick", "full", "leaks"), blocking=True),
    ArtifactDefinition("findings", "findings.json", "repo_audit", "sattlint.findings", 1, profiles=("quick", "full", "leaks"), blocking=True),
    ArtifactDefinition("summary_markdown", "summary.md", "repo_audit", "markdown", 1, profiles=("quick", "full", "leaks"), optional=True),
)


def build_artifact_registry_report(
    artifacts: tuple[ArtifactDefinition, ...],
    *,
    generated_by: str,
    profile: str,
    enabled_artifact_ids: set[str] | None = None,
) -> dict[str, Any]:
    enabled_ids = enabled_artifact_ids or set()
    return {
        "generated_by": generated_by,
        "profile": profile,
        "artifacts": [
            artifact.to_dict(enabled=(artifact.artifact_id in enabled_ids))
            for artifact in artifacts
            if profile in artifact.profiles
        ],
    }


def artifact_reports_map(
    artifacts: tuple[ArtifactDefinition, ...],
    *,
    profile: str,
    enabled_artifact_ids: set[str],
) -> dict[str, str | None]:
    report_map: dict[str, str | None] = {}
    for artifact in artifacts:
        if profile not in artifact.profiles:
            report_map[artifact.artifact_id] = None
            continue
        report_map[artifact.artifact_id] = artifact.filename if artifact.artifact_id in enabled_artifact_ids else None
    return report_map
