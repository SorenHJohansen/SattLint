"""Architecture and analyzer registry report helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from sattlint.devtools.json_helpers import nonempty_string_entries as _string_entries


def _missing_report_paths(repo_root: Path, paths: tuple[str, ...] | list[str]) -> list[str]:
    missing: list[str] = []
    for raw_path in paths:
        candidate = Path(raw_path)
        resolved = candidate if candidate.is_absolute() else repo_root / candidate
        if not resolved.is_file():
            missing.append(raw_path)
    return missing


def _append_missing_acceptance_test_path_findings(
    findings: list[dict[str, Any]],
    *,
    repo_root: Path,
    analyzers: tuple[Any, ...],
    rules: tuple[Any, ...],
) -> None:
    analyzer_path_gaps: list[dict[str, Any]] = []
    for analyzer in analyzers:
        if not analyzer.spec.enabled or not analyzer.delivery.acceptance_tests:
            continue
        missing_paths = _missing_report_paths(repo_root, analyzer.delivery.acceptance_tests)
        if missing_paths:
            analyzer_path_gaps.append(
                {
                    "analyzer": analyzer.spec.key,
                    "missing_paths": missing_paths,
                }
            )

    if analyzer_path_gaps:
        findings.append(
            {
                "id": "analyzer-acceptance-test-path-gap",
                "severity": "medium",
                "message": "Some enabled analyzers declare acceptance-test files that do not exist in the repository.",
                "missing_analyzers": sorted(entry["analyzer"] for entry in analyzer_path_gaps),
                "missing_acceptance_test_paths": analyzer_path_gaps,
            }
        )

    rule_path_gaps: list[dict[str, Any]] = []
    for rule in rules:
        if not rule.acceptance_tests:
            continue
        missing_paths = _missing_report_paths(repo_root, rule.acceptance_tests)
        if missing_paths:
            rule_path_gaps.append(
                {
                    "rule_id": rule.id,
                    "missing_paths": missing_paths,
                }
            )

    if rule_path_gaps:
        findings.append(
            {
                "id": "rule-acceptance-test-path-gap",
                "severity": "medium",
                "message": "Some semantic rules declare acceptance-test files that do not exist in the repository.",
                "missing_rule_ids": sorted(entry["rule_id"] for entry in rule_path_gaps),
                "missing_acceptance_test_paths": rule_path_gaps,
            }
        )


def _finding_entries(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    findings: list[dict[str, Any]] = []
    for entry in cast(list[object], value):
        if isinstance(entry, dict):
            findings.append(cast(dict[str, Any], entry))
    return findings


def _append_structural_budget_findings(findings: list[dict[str, Any]], structural_budgets: dict[str, Any]) -> None:
    if structural_budgets["source_files_over_budget"]:
        findings.append(
            {
                "id": "structural-source-file-budget",
                "severity": "medium",
                "message": "Some source modules exceed the structural line budget and should be split before they grow further.",
                "count": len(structural_budgets["source_files_over_budget"]),
                "over_budget_files": structural_budgets["source_files_over_budget"][:10],
            }
        )

    if structural_budgets["test_files_over_budget"]:
        findings.append(
            {
                "id": "structural-test-file-budget",
                "severity": "medium",
                "message": "Some test modules exceed the structural line budget and should be split by owning surface.",
                "count": len(structural_budgets["test_files_over_budget"]),
                "over_budget_files": structural_budgets["test_files_over_budget"][:10],
            }
        )

    if structural_budgets["functions_over_budget"]:
        findings.append(
            {
                "id": "structural-function-budget",
                "severity": "medium",
                "message": "Some Python functions exceed the structural function budget and should be decomposed.",
                "count": len(structural_budgets["functions_over_budget"]),
                "over_budget_functions": structural_budgets["functions_over_budget"][:10],
            }
        )

    if structural_budgets["classes_over_budget"]:
        findings.append(
            {
                "id": "structural-class-budget",
                "severity": "medium",
                "message": "Some classes exceed the structural method-count budget and should be split by responsibility.",
                "count": len(structural_budgets["classes_over_budget"]),
                "over_budget_classes": structural_budgets["classes_over_budget"][:10],
            }
        )

    if structural_budgets["repeated_private_names"]:
        findings.append(
            {
                "id": "structural-private-helper-duplication",
                "severity": "medium",
                "message": "Some private helper names repeat across many files, which often signals duplicated local implementations.",
                "count": len(structural_budgets["repeated_private_names"]),
                "repeated_private_names": structural_budgets["repeated_private_names"][:10],
            }
        )

    if structural_budgets["facade_private_entrypoints"]:
        findings.append(
            {
                "id": "structural-facade-private-boundary",
                "severity": "medium",
                "message": "Some facade modules call private cross-module entrypoints instead of stable owner APIs.",
                "count": len(structural_budgets["facade_private_entrypoints"]),
                "private_entrypoints": structural_budgets["facade_private_entrypoints"][:10],
            }
        )


def collect_phase2_rule_metadata_gate(
    architecture_report: dict[str, Any],
) -> dict[str, Any]:
    from sattlint.devtools import structural_reports as structural_reports_module  # noqa: PLC0415

    findings = _finding_entries(architecture_report.get("findings"))
    blocking_findings = [
        finding
        for finding in findings
        if finding.get("id") in structural_reports_module.PHASE2_ENFORCED_RULE_METADATA_FINDING_IDS
    ]
    advisory_findings = [
        finding
        for finding in findings
        if finding.get("id") in structural_reports_module.PHASE2_ADVISORY_RULE_METADATA_FINDING_IDS
    ]
    blocking_rule_ids = sorted(
        {rule_id for finding in blocking_findings for rule_id in _string_entries(finding.get("missing_rule_ids"))}
    )
    advisory_rule_ids = sorted(
        {rule_id for finding in advisory_findings for rule_id in _string_entries(finding.get("missing_rule_ids"))}
    )
    return {
        "status": "fail" if blocking_rule_ids else "pass",
        "enforced_fields": ["acceptance_tests", "mutation_applicability"],
        "advisory_fields": ["corpus_cases"],
        "blocking_finding_ids": [finding["id"] for finding in blocking_findings],
        "advisory_finding_ids": [finding["id"] for finding in advisory_findings],
        "blocking_rule_ids": blocking_rule_ids,
        "advisory_rule_ids": advisory_rule_ids,
    }


def collect_architecture_report(
    repo_root: Path,
    *,
    ratchet_path: Path | None = None,
) -> dict[str, Any]:
    from sattlint.devtools import structural_reports as structural_reports_module  # noqa: PLC0415

    structural_budgets = structural_reports_module.collect_structural_budget_report(
        repo_root, ratchet_path=ratchet_path
    )
    cli_filter_kinds = sorted(
        {
            issue_kind.value
            for _label, kinds in structural_reports_module.VARIABLE_ANALYSES.values()
            if kinds is not None
            for issue_kind in kinds
        }
    )
    summary_supported = {
        structural_reports_module.IssueKind.UNUSED.value: isinstance(
            getattr(structural_reports_module.VariablesReport, "unused", None),
            property,
        ),
        structural_reports_module.IssueKind.UNUSED_DATATYPE_FIELD.value: isinstance(
            getattr(structural_reports_module.VariablesReport, "unused_datatype_fields", None),
            property,
        ),
        structural_reports_module.IssueKind.READ_ONLY_NON_CONST.value: isinstance(
            getattr(structural_reports_module.VariablesReport, "read_only_non_const", None),
            property,
        ),
        structural_reports_module.IssueKind.UI_ONLY.value: isinstance(
            getattr(structural_reports_module.VariablesReport, "ui_only", None),
            property,
        ),
        structural_reports_module.IssueKind.NEVER_READ.value: isinstance(
            getattr(structural_reports_module.VariablesReport, "never_read", None),
            property,
        ),
        structural_reports_module.IssueKind.GLOBAL_SCOPE_MINIMIZATION.value: isinstance(
            getattr(structural_reports_module.VariablesReport, "global_scope_minimization", None),
            property,
        ),
        structural_reports_module.IssueKind.HIGH_FAN_IN_OUT.value: isinstance(
            getattr(structural_reports_module.VariablesReport, "high_fan_in_out", None),
            property,
        ),
        structural_reports_module.IssueKind.STRING_MAPPING_MISMATCH.value: isinstance(
            getattr(structural_reports_module.VariablesReport, "string_mapping_mismatch", None),
            property,
        ),
        structural_reports_module.IssueKind.HIDDEN_GLOBAL_COUPLING.value: isinstance(
            getattr(structural_reports_module.VariablesReport, "hidden_global_coupling", None),
            property,
        ),
        structural_reports_module.IssueKind.DATATYPE_DUPLICATION.value: isinstance(
            getattr(structural_reports_module.VariablesReport, "datatype_duplication", None),
            property,
        ),
        structural_reports_module.IssueKind.MIN_MAX_MAPPING_MISMATCH.value: isinstance(
            getattr(structural_reports_module.VariablesReport, "min_max_mapping_mismatch", None),
            property,
        ),
        structural_reports_module.IssueKind.MAGIC_NUMBER.value: isinstance(
            getattr(structural_reports_module.VariablesReport, "magic_numbers", None),
            property,
        ),
        structural_reports_module.IssueKind.NAME_COLLISION.value: isinstance(
            getattr(structural_reports_module.VariablesReport, "name_collisions", None),
            property,
        ),
        structural_reports_module.IssueKind.SHADOWING.value: isinstance(
            getattr(structural_reports_module.VariablesReport, "shadowing", None),
            property,
        ),
        structural_reports_module.IssueKind.RESET_CONTAMINATION.value: isinstance(
            getattr(structural_reports_module.VariablesReport, "reset_contamination", None),
            property,
        ),
        structural_reports_module.IssueKind.IMPLICIT_LATCH.value: isinstance(
            getattr(structural_reports_module.VariablesReport, "implicit_latches", None),
            property,
        ),
    }

    catalog = structural_reports_module.get_default_analyzer_catalog()
    analyzers = catalog.analyzers
    registry_keys = [analyzer.spec.key for analyzer in analyzers]
    live_diagnostic_analyzers = [analyzer.spec.key for analyzer in analyzers if analyzer.spec.supports_live_diagnostics]
    declared_cli_analyzers = list(structural_reports_module.get_declared_cli_analyzer_keys())
    actual_cli_analyzers = sorted(structural_reports_module.get_actual_cli_analyzer_keys())
    semantic_layer_sources = list(structural_reports_module.get_actual_lsp_analyzer_keys())
    declared_lsp_analyzers = list(structural_reports_module.get_declared_lsp_analyzer_keys())
    analyzers_missing_exposure = sorted(
        analyzer.spec.key
        for analyzer in analyzers
        if not (analyzer.delivery.cli_exposed or analyzer.delivery.lsp_exposed or analyzer.delivery.exposed_via)
    )
    analyzers_missing_acceptance_tests = sorted(
        analyzer.spec.key for analyzer in analyzers if analyzer.spec.enabled and not analyzer.delivery.acceptance_tests
    )
    rules_missing_acceptance_tests = sorted(rule.id for rule in catalog.rules if not rule.acceptance_tests)
    rules_missing_corpus_links = sorted(
        rule.id for rule in catalog.rules if rule.mutation_applicability != "not_applicable" and not rule.corpus_cases
    )
    rules_missing_mutation_applicability = sorted(
        rule.id for rule in catalog.rules if rule.mutation_applicability in (None, "unspecified")
    )
    rules_missing_suppression_modes = sorted(rule.id for rule in catalog.rules if rule.suppression_modes is None)
    rules_missing_incremental_safety_markers = sorted(
        rule.id for rule in catalog.rules if rule.incremental_safe is None
    )
    promised_output_artifacts = sorted(
        {output for analyzer in analyzers for output in analyzer.delivery.output_artifacts}
    )
    delivered_output_artifacts = sorted(
        {analyzer.summary_output for analyzer in analyzers}
        | {output for rule in catalog.rules for output in rule.outputs}
    )
    missing_output_artifacts = sorted(
        output for output in promised_output_artifacts if output not in delivered_output_artifacts
    )

    findings: list[dict[str, Any]] = []
    missing_cli_filters = sorted(
        kind for kind, supported in summary_supported.items() if supported and kind not in cli_filter_kinds
    )
    if missing_cli_filters:
        findings.append(
            {
                "id": "cli-variable-filter-gap",
                "severity": "medium",
                "message": "Some variable issue kinds are rendered in reports but not exposed as CLI quick filters.",
                "missing_issue_kinds": missing_cli_filters,
            }
        )

    if declared_cli_analyzers != actual_cli_analyzers:
        findings.append(
            {
                "id": "cli-analyzer-metadata-drift",
                "severity": "medium",
                "message": "Analyzer metadata and the default CLI analyzer subset disagree about which checks are directly exposed.",
                "declared_cli_analyzers": declared_cli_analyzers,
                "actual_cli_analyzers": actual_cli_analyzers,
            }
        )

    if declared_lsp_analyzers != semantic_layer_sources:
        findings.append(
            {
                "id": "lsp-analyzer-metadata-drift",
                "severity": "medium",
                "message": "Analyzer metadata and the semantic-layer/LSP rule sources disagree about which checks surface in editor diagnostics.",
                "declared_lsp_analyzers": declared_lsp_analyzers,
                "actual_lsp_analyzers": semantic_layer_sources,
            }
        )

    if analyzers_missing_exposure:
        findings.append(
            {
                "id": "analyzer-exposure-gap",
                "severity": "medium",
                "message": "Some enabled analyzers are registered and tested but still have no declared delivery surface.",
                "missing_analyzers": analyzers_missing_exposure,
            }
        )

    if analyzers_missing_acceptance_tests:
        findings.append(
            {
                "id": "analyzer-acceptance-test-gap",
                "severity": "medium",
                "message": "Some enabled analyzers do not declare acceptance-test coverage.",
                "missing_analyzers": analyzers_missing_acceptance_tests,
            }
        )

    if rules_missing_acceptance_tests:
        findings.append(
            {
                "id": "rule-acceptance-test-gap",
                "severity": "medium",
                "message": "Some semantic rules do not declare acceptance-test coverage.",
                "missing_rule_ids": rules_missing_acceptance_tests,
            }
        )

    if rules_missing_corpus_links:
        findings.append(
            {
                "id": "rule-corpus-link-gap",
                "severity": "medium",
                "message": "Some semantic rules are not linked to any checked-in corpus manifest cases.",
                "missing_rule_ids": rules_missing_corpus_links,
            }
        )

    if rules_missing_mutation_applicability:
        findings.append(
            {
                "id": "rule-mutation-metadata-gap",
                "severity": "medium",
                "message": "Some semantic rules do not declare mutation applicability metadata.",
                "missing_rule_ids": rules_missing_mutation_applicability,
            }
        )

    if rules_missing_suppression_modes:
        findings.append(
            {
                "id": "rule-suppression-metadata-gap",
                "severity": "medium",
                "message": "Some semantic rules do not declare suppression metadata.",
                "missing_rule_ids": rules_missing_suppression_modes,
            }
        )

    if rules_missing_incremental_safety_markers:
        findings.append(
            {
                "id": "rule-incremental-safety-gap",
                "severity": "medium",
                "message": "Some semantic rules do not declare whether incremental analysis is safe.",
                "missing_rule_ids": rules_missing_incremental_safety_markers,
            }
        )

    if missing_output_artifacts:
        findings.append(
            {
                "id": "analyzer-output-artifact-gap",
                "severity": "medium",
                "message": "Some analyzer metadata promises output artifacts that are not represented in the analyzer catalog outputs.",
                "missing_outputs": missing_output_artifacts,
            }
        )

    _append_missing_acceptance_test_path_findings(
        findings,
        repo_root=repo_root,
        analyzers=analyzers,
        rules=catalog.rules,
    )

    _append_structural_budget_findings(findings, structural_budgets)
    phase2_rule_metadata_gate = structural_reports_module.collect_phase2_rule_metadata_gate({"findings": findings})

    return {
        "registered_analyzers": registry_keys,
        "live_diagnostic_analyzers": live_diagnostic_analyzers,
        "declared_cli_analyzers": declared_cli_analyzers,
        "actual_cli_analyzers": actual_cli_analyzers,
        "declared_lsp_analyzers": declared_lsp_analyzers,
        "actual_lsp_analyzers": semantic_layer_sources,
        "analyzers_missing_exposure": analyzers_missing_exposure,
        "analyzers_missing_acceptance_tests": analyzers_missing_acceptance_tests,
        "rules_missing_acceptance_tests": rules_missing_acceptance_tests,
        "rules_missing_corpus_links": rules_missing_corpus_links,
        "rules_missing_mutation_applicability": rules_missing_mutation_applicability,
        "rules_missing_suppression_modes": rules_missing_suppression_modes,
        "rules_missing_incremental_safety_markers": rules_missing_incremental_safety_markers,
        "promised_output_artifacts": promised_output_artifacts,
        "delivered_output_artifacts": delivered_output_artifacts,
        "cli_variable_filter_issue_kinds": cli_filter_kinds,
        "variables_report_summary_support": summary_supported,
        "structural_budgets": structural_budgets,
        "phase2_rule_metadata_gate": phase2_rule_metadata_gate,
        "findings": findings,
    }


def collect_analyzer_registry_report() -> dict[str, Any]:
    from sattlint.devtools import structural_reports as structural_reports_module  # noqa: PLC0415

    catalog = structural_reports_module.get_default_analyzer_catalog()
    return catalog.to_report(generated_by="sattlint.devtools.pipeline")


__all__ = [
    "_append_structural_budget_findings",
    "collect_analyzer_registry_report",
    "collect_architecture_report",
    "collect_phase2_rule_metadata_gate",
]
