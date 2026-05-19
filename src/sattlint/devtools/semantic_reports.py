"""Semantic analysis summary report builders for the pipeline.

ID2: build_sattline_semantic_report - per-rule/category/severity summary of semantic findings.
ID7: build_rule_metrics_report - per-rule trigger counts and coverage from findings payload.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from typing import TypedDict, cast

SATTLINE_SEMANTIC_SCHEMA_KIND = "sattlint.sattline_semantic"
SATTLINE_SEMANTIC_SCHEMA_VERSION = 1

RULE_METRICS_SCHEMA_KIND = "sattlint.rule_metrics"
RULE_METRICS_SCHEMA_VERSION = 1

ReportMapping = Mapping[str, object]


class _RuleMeta(TypedDict):
    severity: str
    category: str


class _SemanticRuleSummary(TypedDict):
    rule_id: str
    count: int
    severity: str
    category: str


class _RuleMetricsSummary(TypedDict):
    rule_id: str
    finding_count: int
    targets_affected: int


def _mapping_list(value: object) -> list[ReportMapping]:
    if not isinstance(value, list):
        return []
    items = cast(list[object], value)
    result: list[ReportMapping] = []
    for item in items:
        if isinstance(item, Mapping):
            result.append(cast(ReportMapping, item))
    return result


def _mapping(value: object) -> ReportMapping | None:
    if not isinstance(value, Mapping):
        return None
    return cast(ReportMapping, value)


def build_sattline_semantic_report(findings_report: ReportMapping) -> dict[str, object]:
    """Build a derived summary of semantic findings from the pipeline findings report.

    Extracts findings whose rule_id starts with 'semantic.' and produces:
    - total_count
    - per-rule breakdown (rule_id, count, severity, category)
    - by_category counts
    - by_severity counts
    - sources list
    """
    findings = _mapping_list(findings_report.get("findings"))
    semantic_findings = [f for f in findings if str(f.get("rule_id") or "").startswith("semantic.")]

    rule_counts: Counter[str] = Counter()
    rule_meta: dict[str, _RuleMeta] = {}
    category_counts: Counter[str] = Counter()
    severity_counts: Counter[str] = Counter()
    sources: set[str] = set()

    for finding in semantic_findings:
        rule_id = str(finding.get("rule_id") or "semantic.unknown")
        severity = str(finding.get("severity") or "warning")
        category = str(finding.get("category") or "unknown")
        source = str(finding.get("source") or "unknown")

        rule_counts[rule_id] += 1
        if rule_id not in rule_meta:
            rule_meta[rule_id] = {"severity": severity, "category": category}
        category_counts[category] += 1
        severity_counts[severity] += 1
        sources.add(source)

    rules: list[_SemanticRuleSummary] = sorted(
        [
            _SemanticRuleSummary(
                rule_id=rule_id,
                count=rule_counts[rule_id],
                severity=rule_meta[rule_id]["severity"],
                category=rule_meta[rule_id]["category"],
            )
            for rule_id in rule_counts
        ],
        key=lambda rule: (-int(rule["count"]), str(rule["rule_id"])),
    )

    return {
        "kind": SATTLINE_SEMANTIC_SCHEMA_KIND,
        "schema_version": SATTLINE_SEMANTIC_SCHEMA_VERSION,
        "total_count": len(semantic_findings),
        "rules": rules,
        "by_category": dict(sorted(category_counts.items())),
        "by_severity": dict(sorted(severity_counts.items())),
        "sources": sorted(sources),
    }


def build_rule_metrics_report(
    findings_report: ReportMapping,
    analyzer_registry: ReportMapping | None = None,
) -> dict[str, object]:
    """Build per-rule trigger counts and coverage from the pipeline findings payload.

    Counts how many times each semantic rule fired, how many distinct analyzed targets
    were affected, and (when an analyzer_registry is provided) reports which rules
    never triggered at all.
    """
    findings = _mapping_list(findings_report.get("findings"))
    semantic_findings = [f for f in findings if str(f.get("rule_id") or "").startswith("semantic.")]

    rule_fire_counts: Counter[str] = Counter()
    rule_target_sets: dict[str, set[str]] = {}

    for finding in semantic_findings:
        rule_id = str(finding.get("rule_id") or "semantic.unknown")
        # Use path as a proxy for "target" (may be None for cross-module findings).
        location = _mapping(finding.get("location"))
        path = str(location.get("path") or "<unknown>") if location is not None else "<unknown>"

        rule_fire_counts[rule_id] += 1
        rule_target_sets.setdefault(rule_id, set()).add(path)

    # All known semantic rule IDs from the registry (if provided).
    known_rule_ids: set[str] = set()
    if analyzer_registry:
        for rule_entry in _mapping_list(analyzer_registry.get("rules")):
            rule_id = str(rule_entry.get("rule_id") or rule_entry.get("id") or "")
            if rule_id.startswith("semantic."):
                known_rule_ids.add(rule_id)

    triggered_rule_ids = set(rule_fire_counts.keys())
    never_triggered = sorted(known_rule_ids - triggered_rule_ids)

    rules: list[_RuleMetricsSummary] = sorted(
        [
            _RuleMetricsSummary(
                rule_id=rule_id,
                finding_count=rule_fire_counts[rule_id],
                targets_affected=len(rule_target_sets.get(rule_id, set())),
            )
            for rule_id in triggered_rule_ids
        ],
        key=lambda rule: (-int(rule["finding_count"]), str(rule["rule_id"])),
    )

    return {
        "kind": RULE_METRICS_SCHEMA_KIND,
        "schema_version": RULE_METRICS_SCHEMA_VERSION,
        "rules": rules,
        "never_triggered": never_triggered,
        "summary": {
            "rules_triggered_count": len(triggered_rule_ids),
            "rules_never_triggered_count": len(never_triggered),
            "total_semantic_finding_count": sum(rule_fire_counts.values()),
        },
    }


__all__ = [
    "RULE_METRICS_SCHEMA_KIND",
    "RULE_METRICS_SCHEMA_VERSION",
    "SATTLINE_SEMANTIC_SCHEMA_KIND",
    "SATTLINE_SEMANTIC_SCHEMA_VERSION",
    "build_rule_metrics_report",
    "build_sattline_semantic_report",
]
