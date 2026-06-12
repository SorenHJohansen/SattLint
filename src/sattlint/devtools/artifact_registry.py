"""Registry of machine-readable artifacts emitted by developer tooling."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

ANALYSIS_DIFF_FILENAME = "analysis_diff.json"
ANALYSIS_DIFF_SCHEMA_KIND = "sattlint.analysis_diff"
ANALYSIS_DIFF_SCHEMA_VERSION = 1

CORPUS_RESULTS_FILENAME = "corpus_results.json"
CORPUS_RESULTS_SCHEMA_KIND = "sattlint.corpus_results"
CORPUS_RESULTS_SCHEMA_VERSION = 1

AI_GC_REPORT_FILENAME = "ai_gc.json"
AI_GC_SCHEMA_KIND = "sattlint.ai_gc"
AI_GC_SCHEMA_VERSION = 1

CLI_CONSISTENCY_FILENAME = "cli_consistency.json"
CLI_CONSISTENCY_SCHEMA_KIND = "sattlint.cli_consistency"
CLI_CONSISTENCY_SCHEMA_VERSION = 1

AUDIT_RUN_HISTORY_FILENAME = "run_history.json"
AUDIT_RUN_HISTORY_SCHEMA_KIND = "sattlint.audit_run_history"
AUDIT_RUN_HISTORY_SCHEMA_VERSION = 1

ACCURACY_METRICS_FILENAME = "accuracy_metrics.json"
ACCURACY_SCHEMA_KIND = "sattlint.accuracy_metrics"
ACCURACY_SCHEMA_VERSION = 1

AI_TEMPLATE_SUMMARY_FILENAME = "ai_task_templates.json"
AI_TEMPLATE_SCHEMA_KIND = "sattlint.ai_templates"
AI_TEMPLATE_SCHEMA_VERSION = 1

ARTIFACT_READINESS_FILENAME = "artifact_readiness.json"
ARTIFACT_READINESS_SCHEMA_KIND = "sattlint.artifact_readiness"
ARTIFACT_READINESS_SCHEMA_VERSION = 1
READINESS_SCHEMA_KIND = ARTIFACT_READINESS_SCHEMA_KIND
READINESS_SCHEMA_VERSION = ARTIFACT_READINESS_SCHEMA_VERSION

AUDIT_FINDINGS_COMPARISON_FILENAME = "audit_findings_comparison.json"
AUDIT_FINDINGS_COMPARISON_SCHEMA_KIND = "sattlint.audit_findings_comparison"
AUDIT_FINDINGS_COMPARISON_SCHEMA_VERSION = 1
COMPARE_RESULTS_FILENAME = AUDIT_FINDINGS_COMPARISON_FILENAME
COMPARE_SCHEMA_KIND = AUDIT_FINDINGS_COMPARISON_SCHEMA_KIND
COMPARE_SCHEMA_VERSION = AUDIT_FINDINGS_COMPARISON_SCHEMA_VERSION

COVERAGE_RATCHET_FILENAME = "coverage_ratchet.json"
COVERAGE_RATCHET_SCHEMA_KIND = "sattlint.coverage_ratchet"
COVERAGE_RATCHET_SCHEMA_VERSION = 1

COVERAGE_SUMMARY_FILENAME = "coverage_summary.json"
COVERAGE_SUMMARY_SCHEMA_KIND = "sattlint.coverage_summary"
COVERAGE_SUMMARY_SCHEMA_VERSION = 1

CURRENT_DEBT_SNAPSHOT_FILENAME = "current_debt_snapshot.json"
CURRENT_DEBT_SNAPSHOT_SCHEMA_KIND = "sattlint.current_debt_snapshot"
CURRENT_DEBT_SNAPSHOT_SCHEMA_VERSION = 1

DIFFERENTIAL_FILENAME = "differential.json"
DIFFERENTIAL_SCHEMA_KIND = "sattlint.differential"
DIFFERENTIAL_SCHEMA_VERSION = 1

FAULT_INJECTION_RESULTS_FILENAME = "fault_injection_results.json"
FAULT_INJECTION_SCHEMA_KIND = "sattlint.fault_injection_results"
FAULT_INJECTION_SCHEMA_VERSION = 1

FUZZER_REPORT_FILENAME = "fuzzer_report.json"
FUZZER_REPORT_SCHEMA_KIND = "sattlint.fuzzer_report"
FUZZER_REPORT_SCHEMA_VERSION = 1

FUZZ_RESULTS_FILENAME = "fuzz_results.json"
FUZZ_RESULTS_SCHEMA_KIND = "sattlint.fuzz_results"
FUZZ_RESULTS_SCHEMA_VERSION = 1

INCREMENTAL_ANALYSIS_FILENAME = "incremental_analysis.json"
INCREMENTAL_ANALYSIS_SCHEMA_KIND = "sattlint.incremental_analysis"
INCREMENTAL_ANALYSIS_SCHEMA_VERSION = 1

LAYER_LINT_POLICY_FILENAME = "layer_lint_policy.json"
LAYER_LINT_POLICY_SCHEMA_KIND = "sattlint.layer_lint_policy"
LAYER_LINT_POLICY_SCHEMA_VERSION = 1
POLICY_KIND = LAYER_LINT_POLICY_SCHEMA_KIND
POLICY_SCHEMA_VERSION = LAYER_LINT_POLICY_SCHEMA_VERSION

MUTATION_RESULTS_FILENAME = "mutation_results.json"
MUTATION_SCHEMA_KIND = "sattlint.mutation_results"
MUTATION_SCHEMA_VERSION = 1

PERFORMANCE_BUDGET_FILENAME = "performance_budget.json"
PERFORMANCE_BUDGET_SCHEMA_KIND = "sattlint.performance_budget"
PERFORMANCE_BUDGET_SCHEMA_VERSION = 1

PRODUCTION_SUMMARY_FILENAME = "production_summary.json"
PRODUCTION_SCHEMA_KIND = "sattlint.production_summary"
PRODUCTION_SCHEMA_VERSION = 1

PROFILING_SUMMARY_FILENAME = "profiling_summary.json"
PROFILING_SUMMARY_SCHEMA_KIND = "sattlint.profiling_summary"
PROFILING_SUMMARY_SCHEMA_VERSION = 1

PROPERTY_TEST_RESULTS_FILENAME = "property_test_results.json"
PROPERTY_TEST_SCHEMA_KIND = "sattlint.property_test_results"
PROPERTY_TEST_SCHEMA_VERSION = 1

RELEASE_SMOKE_STATUS_FILENAME = "status.json"
RELEASE_SMOKE_STATUS_SCHEMA_KIND = "sattlint.release_smoke.status"
RELEASE_SMOKE_SUMMARY_FILENAME = "summary.json"
RELEASE_SMOKE_SUMMARY_SCHEMA_KIND = "sattlint.release_smoke.summary"
RELEASE_SMOKE_SCHEMA_VERSION = 1

RULE_METRICS_FILENAME = "rule_metrics.json"
RULE_METRICS_SCHEMA_KIND = "sattlint.rule_metrics"
RULE_METRICS_SCHEMA_VERSION = 1

SATTLINE_SEMANTIC_FILENAME = "sattline_semantic.json"
SATTLINE_SEMANTIC_SCHEMA_KIND = "sattlint.sattline_semantic"
SATTLINE_SEMANTIC_SCHEMA_VERSION = 1

SOURCE_DIGEST_MANIFEST_FILENAME = ".sources.json"
SOURCE_DIGEST_MANIFEST_KIND = "sattlint.generated_output_sources"
SOURCE_DIGEST_MANIFEST_SCHEMA_VERSION = 1
SOURCE_DIGEST_MANIFEST_SUFFIX = SOURCE_DIGEST_MANIFEST_FILENAME


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
    ArtifactDefinition(
        "progress", "progress.json", "progress", "sattlint.pipeline.progress", 1, profiles=("quick", "full")
    ),
    ArtifactDefinition(
        "status", "status.json", "status", "sattlint.pipeline.status", 1, profiles=("quick", "full"), blocking=True
    ),
    ArtifactDefinition(
        "summary", "summary.json", "summary", "sattlint.pipeline.summary", 1, profiles=("quick", "full"), blocking=True
    ),
    ArtifactDefinition(
        "findings", "findings.json", "findings", "sattlint.findings", 1, profiles=("quick", "full"), blocking=True
    ),
    ArtifactDefinition(
        "analysis_diff",
        ANALYSIS_DIFF_FILENAME,
        "analysis_diff",
        ANALYSIS_DIFF_SCHEMA_KIND,
        ANALYSIS_DIFF_SCHEMA_VERSION,
        profiles=("quick", "full"),
        optional=True,
        depends_on=("findings",),
    ),
    ArtifactDefinition(
        "recommendation_drift",
        "recommendation_drift.json",
        "recommendation_drift",
        "sattlint.pipeline.recommendation_drift",
        1,
        profiles=("full",),
        optional=True,
        depends_on=("status", "summary"),
    ),
    ArtifactDefinition(
        "corpus_results",
        CORPUS_RESULTS_FILENAME,
        "corpus_results",
        CORPUS_RESULTS_SCHEMA_KIND,
        CORPUS_RESULTS_SCHEMA_VERSION,
        profiles=("quick", "full"),
        optional=True,
        blocking=True,
    ),
    ArtifactDefinition(
        "artifact_registry",
        "artifact_registry.json",
        "artifact_registry",
        "sattlint.artifact_registry",
        1,
        profiles=("quick", "full"),
    ),
    ArtifactDefinition(
        "environment", "environment.json", "environment", "sattlint.environment", 1, profiles=("quick", "full")
    ),
    ArtifactDefinition(
        "ruff", "ruff.json", "ruff", "sattlint.tool_report", 1, profiles=("quick", "full"), blocking=True
    ),
    ArtifactDefinition(
        "pyright", "pyright.json", "pyright", "sattlint.tool_report", 1, profiles=("quick", "full"), blocking=True
    ),
    ArtifactDefinition(
        "pytest", "pytest.json", "pytest", "sattlint.tool_report", 1, profiles=("quick", "full"), blocking=True
    ),
    ArtifactDefinition(
        "vulture", "vulture.json", "vulture", "sattlint.tool_report", 1, profiles=("full",), optional=True
    ),
    ArtifactDefinition("bandit", "bandit.json", "bandit", "sattlint.tool_report", 1, profiles=("full",), optional=True),
    ArtifactDefinition(
        "architecture",
        "architecture.json",
        "architecture",
        "sattlint.architecture",
        1,
        profiles=("full",),
        optional=True,
    ),
    ArtifactDefinition(
        "analyzer_registry",
        "analyzer_registry.json",
        "analyzer_registry",
        "sattlint.analyzer_registry",
        1,
        profiles=("full",),
        optional=True,
    ),
    ArtifactDefinition(
        "dependency_graph",
        "dependency_graph.json",
        "dependency_graph",
        "sattlint.graph",
        1,
        profiles=("full",),
        optional=True,
    ),
    ArtifactDefinition(
        "call_graph", "call_graph.json", "call_graph", "sattlint.graph", 1, profiles=("full",), optional=True
    ),
    ArtifactDefinition(
        "graphics_layout",
        "graphics_layout.json",
        "graphics_layout",
        "sattlint.graphics_layout",
        1,
        profiles=("full",),
        optional=True,
    ),
    ArtifactDefinition(
        "impact_analysis",
        "impact_analysis.json",
        "impact_analysis",
        "sattlint.impact_analysis",
        1,
        profiles=("full",),
        optional=True,
    ),
    ArtifactDefinition("trace", "trace.json", "trace", "sattlint.trace", 1, profiles=("full",), optional=True),
    ArtifactDefinition(
        "incremental_analysis",
        INCREMENTAL_ANALYSIS_FILENAME,
        "incremental_analysis",
        INCREMENTAL_ANALYSIS_SCHEMA_KIND,
        INCREMENTAL_ANALYSIS_SCHEMA_VERSION,
        profiles=("quick", "full"),
        optional=True,
    ),
    ArtifactDefinition(
        "coverage_summary",
        COVERAGE_SUMMARY_FILENAME,
        "coverage_summary",
        COVERAGE_SUMMARY_SCHEMA_KIND,
        COVERAGE_SUMMARY_SCHEMA_VERSION,
        profiles=("full",),
        optional=True,
        depends_on=(),
    ),
    ArtifactDefinition(
        "current_debt_snapshot",
        CURRENT_DEBT_SNAPSHOT_FILENAME,
        "current_debt_snapshot",
        CURRENT_DEBT_SNAPSHOT_SCHEMA_KIND,
        CURRENT_DEBT_SNAPSHOT_SCHEMA_VERSION,
        profiles=("full",),
        optional=True,
    ),
    ArtifactDefinition(
        "sattline_semantic",
        SATTLINE_SEMANTIC_FILENAME,
        "sattline_semantic",
        SATTLINE_SEMANTIC_SCHEMA_KIND,
        SATTLINE_SEMANTIC_SCHEMA_VERSION,
        profiles=("full",),
        optional=True,
        depends_on=("findings",),
    ),
    ArtifactDefinition(
        "rule_metrics",
        RULE_METRICS_FILENAME,
        "rule_metrics",
        RULE_METRICS_SCHEMA_KIND,
        RULE_METRICS_SCHEMA_VERSION,
        profiles=("full",),
        optional=True,
        depends_on=("findings",),
    ),
    ArtifactDefinition(
        "mutation_results",
        MUTATION_RESULTS_FILENAME,
        "mutation_results",
        MUTATION_SCHEMA_KIND,
        MUTATION_SCHEMA_VERSION,
        profiles=("full",),
        optional=True,
        depends_on=("findings",),
    ),
    ArtifactDefinition(
        "accuracy_metrics",
        ACCURACY_METRICS_FILENAME,
        "accuracy_metrics",
        ACCURACY_SCHEMA_KIND,
        ACCURACY_SCHEMA_VERSION,
        profiles=("full",),
        optional=True,
        depends_on=("findings",),
    ),
    ArtifactDefinition(
        "differential",
        DIFFERENTIAL_FILENAME,
        "differential",
        DIFFERENTIAL_SCHEMA_KIND,
        DIFFERENTIAL_SCHEMA_VERSION,
        profiles=("full",),
        optional=True,
        depends_on=("findings",),
    ),
    ArtifactDefinition(
        "production_summary",
        PRODUCTION_SUMMARY_FILENAME,
        "production_summary",
        PRODUCTION_SCHEMA_KIND,
        PRODUCTION_SCHEMA_VERSION,
        profiles=("full",),
        optional=True,
        depends_on=("findings",),
    ),
    ArtifactDefinition(
        "ai_templates",
        AI_TEMPLATE_SUMMARY_FILENAME,
        "ai_templates",
        AI_TEMPLATE_SCHEMA_KIND,
        AI_TEMPLATE_SCHEMA_VERSION,
        profiles=("full",),
        optional=True,
    ),
    ArtifactDefinition(
        "symbolic_summary",
        "symbolic_summary.json",
        "symbolic_summary",
        "sattlint.symbolic_lite",
        1,
        profiles=("full",),
        optional=True,
        depends_on=("findings",),
    ),
    ArtifactDefinition(
        "profiling_summary",
        PROFILING_SUMMARY_FILENAME,
        "profiling_summary",
        PROFILING_SUMMARY_SCHEMA_KIND,
        PROFILING_SUMMARY_SCHEMA_VERSION,
        profiles=("full",),
        optional=True,
        depends_on=("trace",),
    ),
    ArtifactDefinition(
        "performance_budget",
        PERFORMANCE_BUDGET_FILENAME,
        "performance_budget",
        PERFORMANCE_BUDGET_SCHEMA_KIND,
        PERFORMANCE_BUDGET_SCHEMA_VERSION,
        profiles=("full",),
        optional=True,
        depends_on=("profiling_summary",),
    ),
)


AUDIT_ARTIFACTS: tuple[ArtifactDefinition, ...] = (
    ArtifactDefinition(
        "progress",
        "progress.json",
        "repo_audit_progress",
        "sattlint.repo_audit.progress",
        1,
        profiles=("quick", "full", "leaks"),
    ),
    ArtifactDefinition(
        "status",
        "status.json",
        "repo_audit",
        "sattlint.repo_audit.status",
        1,
        profiles=("quick", "full", "leaks"),
        blocking=True,
    ),
    ArtifactDefinition(
        "summary",
        "summary.json",
        "repo_audit",
        "sattlint.repo_audit.summary",
        1,
        profiles=("quick", "full", "leaks"),
        blocking=True,
    ),
    ArtifactDefinition(
        "findings",
        "findings.json",
        "repo_audit",
        "sattlint.findings",
        1,
        profiles=("quick", "full", "leaks"),
        blocking=True,
    ),
    ArtifactDefinition(
        "summary_markdown",
        "summary.md",
        "repo_audit",
        "markdown",
        1,
        profiles=("quick", "full", "leaks"),
        optional=True,
    ),
    ArtifactDefinition(
        "run_history",
        AUDIT_RUN_HISTORY_FILENAME,
        "repo_audit",
        AUDIT_RUN_HISTORY_SCHEMA_KIND,
        AUDIT_RUN_HISTORY_SCHEMA_VERSION,
        profiles=("quick", "full", "leaks"),
        optional=True,
    ),
    ArtifactDefinition(
        "cli_consistency",
        CLI_CONSISTENCY_FILENAME,
        "repo_audit",
        CLI_CONSISTENCY_SCHEMA_KIND,
        CLI_CONSISTENCY_SCHEMA_VERSION,
        profiles=("full",),
        optional=True,
    ),
    ArtifactDefinition(
        "ai_gc",
        AI_GC_REPORT_FILENAME,
        "repo_audit",
        AI_GC_SCHEMA_KIND,
        AI_GC_SCHEMA_VERSION,
        profiles=("quick", "full"),
        optional=True,
    ),
)


DEVTOOLS_ARTIFACTS: tuple[ArtifactDefinition, ...] = (
    ArtifactDefinition(
        "artifact_readiness",
        ARTIFACT_READINESS_FILENAME,
        "artifact_readiness",
        ARTIFACT_READINESS_SCHEMA_KIND,
        ARTIFACT_READINESS_SCHEMA_VERSION,
        optional=True,
    ),
    ArtifactDefinition(
        "audit_findings_comparison",
        AUDIT_FINDINGS_COMPARISON_FILENAME,
        "compare_audit_findings",
        AUDIT_FINDINGS_COMPARISON_SCHEMA_KIND,
        AUDIT_FINDINGS_COMPARISON_SCHEMA_VERSION,
        optional=True,
    ),
    ArtifactDefinition(
        "coverage_ratchet",
        COVERAGE_RATCHET_FILENAME,
        "coverage_reports",
        COVERAGE_RATCHET_SCHEMA_KIND,
        COVERAGE_RATCHET_SCHEMA_VERSION,
        optional=True,
    ),
    ArtifactDefinition(
        "fault_injection_results",
        FAULT_INJECTION_RESULTS_FILENAME,
        "fault_injection",
        FAULT_INJECTION_SCHEMA_KIND,
        FAULT_INJECTION_SCHEMA_VERSION,
        optional=True,
    ),
    ArtifactDefinition(
        "fuzz_results",
        FUZZ_RESULTS_FILENAME,
        "sandbox.fuzzer",
        FUZZ_RESULTS_SCHEMA_KIND,
        FUZZ_RESULTS_SCHEMA_VERSION,
        optional=True,
    ),
    ArtifactDefinition(
        "fuzzer_report",
        FUZZER_REPORT_FILENAME,
        "sandbox.fuzzer",
        FUZZER_REPORT_SCHEMA_KIND,
        FUZZER_REPORT_SCHEMA_VERSION,
        optional=True,
    ),
    ArtifactDefinition(
        "generated_output_sources",
        SOURCE_DIGEST_MANIFEST_FILENAME,
        "shared.pipeline_artifacts",
        SOURCE_DIGEST_MANIFEST_KIND,
        SOURCE_DIGEST_MANIFEST_SCHEMA_VERSION,
        optional=True,
    ),
    ArtifactDefinition(
        "layer_lint_policy",
        LAYER_LINT_POLICY_FILENAME,
        "layer_linter",
        LAYER_LINT_POLICY_SCHEMA_KIND,
        LAYER_LINT_POLICY_SCHEMA_VERSION,
        optional=True,
    ),
    ArtifactDefinition(
        "property_test_results",
        PROPERTY_TEST_RESULTS_FILENAME,
        "property_tests",
        PROPERTY_TEST_SCHEMA_KIND,
        PROPERTY_TEST_SCHEMA_VERSION,
        optional=True,
    ),
    ArtifactDefinition(
        "release_smoke_status",
        RELEASE_SMOKE_STATUS_FILENAME,
        "release_smoke",
        RELEASE_SMOKE_STATUS_SCHEMA_KIND,
        RELEASE_SMOKE_SCHEMA_VERSION,
        optional=True,
    ),
    ArtifactDefinition(
        "release_smoke_summary",
        RELEASE_SMOKE_SUMMARY_FILENAME,
        "release_smoke",
        RELEASE_SMOKE_SUMMARY_SCHEMA_KIND,
        RELEASE_SMOKE_SCHEMA_VERSION,
        optional=True,
    ),
)

REGISTERED_ARTIFACTS: tuple[ArtifactDefinition, ...] = PIPELINE_ARTIFACTS + AUDIT_ARTIFACTS + DEVTOOLS_ARTIFACTS


def _validate_registered_artifacts(artifacts: tuple[ArtifactDefinition, ...]) -> None:
    seen_producer_filename_and_kind: set[tuple[str, str, str]] = set()
    schema_versions: dict[str, int] = {}
    for artifact in artifacts:
        producer_filename_and_kind = (artifact.producer, artifact.filename, artifact.schema_kind)
        if producer_filename_and_kind in seen_producer_filename_and_kind:
            raise ValueError(
                "Duplicate artifact registry entry for "
                f"producer {artifact.producer!r}, filename {artifact.filename!r}, and schema {artifact.schema_kind!r}."
            )
        seen_producer_filename_and_kind.add(producer_filename_and_kind)
        existing_version = schema_versions.get(artifact.schema_kind)
        if existing_version is not None and existing_version != artifact.schema_version:
            raise ValueError(
                f"Schema kind {artifact.schema_kind!r} uses multiple versions: {existing_version} and {artifact.schema_version}."
            )
        schema_versions[artifact.schema_kind] = artifact.schema_version


_validate_registered_artifacts(REGISTERED_ARTIFACTS)


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
