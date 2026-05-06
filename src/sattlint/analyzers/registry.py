"""Analyzer registry for CLI entrypoints."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from sattlint.analyzers.alarm_integrity import analyze_alarm_integrity
from sattlint.analyzers.cyclomatic_complexity import analyze_cyclomatic_complexity
from sattlint.analyzers.initial_values import analyze_initial_values
from sattlint.analyzers.loop_output_refactor import analyze_loop_output_refactor
from sattlint.analyzers.modules import analyze_version_drift
from sattlint.analyzers.naming import analyze_naming_consistency, get_configured_naming_rules
from sattlint.analyzers.parameter_drift import analyze_parameter_drift
from sattlint.analyzers.safety_paths import analyze_safety_paths
from sattlint.analyzers.scan_loop_resource_usage import analyze_scan_loop_resource_usage
from sattlint.analyzers.spec_compliance import analyze_spec_compliance
from sattlint.analyzers.state_inference import analyze_state_inference
from sattlint.analyzers.taint_paths import analyze_taint_paths

from ._registry_delivery import AnalyzerDeliveryMetadata, build_delivery_metadata, summary_output_for_analyzer
from ._registry_specs import build_default_analyzers
from .comment_code import analyze_comment_code
from .dataflow import analyze_dataflow
from .framework import AnalyzerSpec
from .mms import analyze_mms_interface_variables
from .rule_profiles import get_default_rule_profile_report
from .sattline_semantics import (
    SemanticRule,
    SemanticRuleGroup,
    analyze_sattline_semantics,
    get_sattline_semantic_rule_groups,
)
from .sfc import analyze_sfc, get_configured_mutually_exclusive_step_sets, get_configured_step_contracts
from .shadowing import analyze_shadowing
from .unsafe_defaults import analyze_unsafe_defaults
from .variables import analyze_variables

SEMANTIC_LAYER_ANALYZER_KEY = "sattline-semantics"
DEFAULT_CLI_ANALYZER_KEYS: tuple[str, ...] = (
    "variables",
    "mms-interface",
    "sfc",
    "comment-code",
    "shadowing",
    "spec-compliance",
    "loop-output-refactor",
)
REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CORPUS_MANIFEST_DIR = REPO_ROOT / "tests" / "fixtures" / "corpus" / "manifests"

# Preserve the historical monkeypatch surface that tests and extracted helper modules use.
_REGISTRY_MONKEYPATCH_SURFACE = (
    analyze_alarm_integrity,
    analyze_comment_code,
    analyze_cyclomatic_complexity,
    analyze_dataflow,
    analyze_initial_values,
    analyze_loop_output_refactor,
    analyze_mms_interface_variables,
    analyze_naming_consistency,
    analyze_parameter_drift,
    analyze_safety_paths,
    analyze_sattline_semantics,
    analyze_scan_loop_resource_usage,
    analyze_sfc,
    analyze_shadowing,
    analyze_spec_compliance,
    analyze_state_inference,
    analyze_taint_paths,
    analyze_unsafe_defaults,
    analyze_variables,
    analyze_version_drift,
    get_configured_mutually_exclusive_step_sets,
    get_configured_naming_rules,
    get_configured_step_contracts,
)


@dataclass(frozen=True)
class AnalyzerMetadata:
    spec: AnalyzerSpec
    rule_ids: tuple[str, ...] = ()
    delivery: AnalyzerDeliveryMetadata = field(
        default_factory=lambda: AnalyzerDeliveryMetadata(
            scope="workspace",
            implementation_bucket="analyzers",
        )
    )

    @property
    def summary_output(self) -> str:
        return f"{self.spec.key}.summary"

    def to_dict(self) -> dict[str, object]:
        data = {
            "key": self.spec.key,
            "name": self.spec.name,
            "description": self.spec.description,
            "enabled": self.spec.enabled,
            "supports_live_diagnostics": self.spec.supports_live_diagnostics,
            "summary_output": self.summary_output,
            "rule_ids": list(self.rule_ids),
        }
        data.update(self.delivery.to_dict())
        return data


@dataclass(frozen=True)
class RuleMetadata:
    id: str
    source: str
    category: str
    severity: str
    confidence: str
    applies_to: str
    description: str
    explanation: str | None
    suggestion: str | None
    analyzers: tuple[str, ...]
    outputs: tuple[str, ...]
    acceptance_tests: tuple[str, ...] | None = None
    corpus_cases: tuple[str, ...] = ()
    mutation_applicability: str | None = None
    suppression_modes: tuple[str, ...] | None = None
    incremental_safe: bool | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "source": self.source,
            "category": self.category,
            "severity": self.severity,
            "confidence": self.confidence,
            "applies_to": self.applies_to,
            "description": self.description,
            "explanation": self.explanation,
            "suggestion": self.suggestion,
            "analyzers": list(self.analyzers),
            "outputs": list(self.outputs),
            "acceptance_tests": list(self.acceptance_tests or ()),
            "corpus_cases": list(self.corpus_cases),
            "mutation_applicability": self.mutation_applicability or "unspecified",
            "suppression_modes": list(self.suppression_modes or ()),
            "incremental_safe": self.incremental_safe,
        }


@dataclass(frozen=True)
class AnalyzerCatalog:
    analyzers: tuple[AnalyzerMetadata, ...]
    semantic_rule_groups: tuple[SemanticRuleGroup, ...]
    rules: tuple[RuleMetadata, ...]
    semantic_layer_analyzer_key: str = SEMANTIC_LAYER_ANALYZER_KEY

    def enabled_specs(self) -> tuple[AnalyzerSpec, ...]:
        return tuple(analyzer.spec for analyzer in self.analyzers if analyzer.spec.enabled)

    def to_report(self, *, generated_by: str) -> dict[str, object]:
        return {
            "generated_by": generated_by,
            "analyzers": [analyzer.to_dict() for analyzer in self.analyzers],
            "semantic_layer": {
                "analyzer_key": self.semantic_layer_analyzer_key,
                "sources": [group.source for group in self.semantic_rule_groups],
                "source_rule_counts": {group.source: len(group.rules) for group in self.semantic_rule_groups},
            },
            "rule_profiles": get_default_rule_profile_report(),
            "rules": [rule.to_dict() for rule in self.rules],
        }


def get_declared_cli_analyzer_keys() -> tuple[str, ...]:
    return tuple(
        sorted(
            analyzer.spec.key for analyzer in get_default_analyzer_catalog().analyzers if analyzer.delivery.cli_exposed
        )
    )


def get_actual_cli_analyzer_keys() -> tuple[str, ...]:
    return tuple(spec.key for spec in get_default_cli_analyzers())


def get_declared_lsp_analyzer_keys() -> tuple[str, ...]:
    return tuple(
        sorted(
            analyzer.spec.key for analyzer in get_default_analyzer_catalog().analyzers if analyzer.delivery.lsp_exposed
        )
    )


def get_actual_lsp_analyzer_keys() -> tuple[str, ...]:
    catalog = get_default_analyzer_catalog()
    registry_keys = {analyzer.spec.key for analyzer in catalog.analyzers}
    return tuple(
        sorted(
            ({catalog.semantic_layer_analyzer_key} | {group.source for group in catalog.semantic_rule_groups})
            & registry_keys
        )
    )


def _iter_semantic_rules(
    semantic_rule_groups: tuple[SemanticRuleGroup, ...],
) -> tuple[SemanticRule, ...]:
    return tuple(rule for group in semantic_rule_groups for rule in group.rules)


@lru_cache(maxsize=1)
def _rule_corpus_cases_by_rule_id() -> dict[str, tuple[str, ...]]:
    if not DEFAULT_CORPUS_MANIFEST_DIR.exists():
        return {}

    linked_cases: dict[str, set[str]] = {}
    for manifest_path in sorted(DEFAULT_CORPUS_MANIFEST_DIR.rglob("*.json")):
        if not manifest_path.is_file():
            continue

        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        case_id = str(payload.get("case_id") or manifest_path.stem)
        expectation = payload.get("expectation") or {}
        for rule_id in expectation.get("expected_finding_ids", []):
            linked_cases.setdefault(str(rule_id), set()).add(case_id)

    return {rule_id: tuple(sorted(case_ids)) for rule_id, case_ids in linked_cases.items()}


def _build_rule_metadata(
    rule: SemanticRule,
    *,
    mapped_analyzers: tuple[str, ...],
    analyzer_metadata_by_key: dict[str, AnalyzerMetadata],
) -> RuleMetadata:
    corpus_cases = tuple(sorted(set(rule.corpus_cases) | set(_rule_corpus_cases_by_rule_id().get(rule.id, ()))))
    return RuleMetadata(
        id=rule.id,
        source=rule.source,
        category=rule.category,
        severity=rule.severity,
        confidence=rule.confidence,
        applies_to=rule.applies_to,
        description=rule.description,
        explanation=rule.explanation or rule.description,
        suggestion=rule.suggestion,
        analyzers=mapped_analyzers,
        outputs=tuple(
            analyzer_metadata_by_key[analyzer_key].summary_output
            if analyzer_key in analyzer_metadata_by_key
            else summary_output_for_analyzer(analyzer_key)
            for analyzer_key in mapped_analyzers
        ),
        acceptance_tests=(None if rule.acceptance_tests is None else tuple(sorted(rule.acceptance_tests))),
        corpus_cases=corpus_cases,
        mutation_applicability=rule.mutation_applicability,
        suppression_modes=(None if rule.suppression_modes is None else tuple(sorted(rule.suppression_modes))),
        incremental_safe=rule.incremental_safe,
    )


def _build_delivery_metadata(spec: AnalyzerSpec, rule_ids: tuple[str, ...]) -> AnalyzerDeliveryMetadata:
    return build_delivery_metadata(
        spec,
        rule_ids,
        semantic_layer_analyzer_key=SEMANTIC_LAYER_ANALYZER_KEY,
    )


def get_default_analyzer_catalog() -> AnalyzerCatalog:
    analyzer_specs = tuple(get_default_analyzers())
    semantic_rule_groups = get_sattline_semantic_rule_groups()
    registered_keys = {spec.key for spec in analyzer_specs}
    rule_ids_by_analyzer: dict[str, list[str]] = {spec.key: [] for spec in analyzer_specs}
    rule_ids_by_analyzer.setdefault(SEMANTIC_LAYER_ANALYZER_KEY, [])

    mapped_rules: list[tuple[SemanticRule, tuple[str, ...]]] = []
    for rule in sorted(_iter_semantic_rules(semantic_rule_groups), key=lambda item: item.id):
        mapped_analyzers = [SEMANTIC_LAYER_ANALYZER_KEY]
        if rule.source in registered_keys and rule.source not in mapped_analyzers:
            mapped_analyzers.append(rule.source)

        for analyzer_key in mapped_analyzers:
            rule_ids_by_analyzer.setdefault(analyzer_key, []).append(rule.id)
        mapped_rules.append((rule, tuple(mapped_analyzers)))

    analyzers = tuple(
        AnalyzerMetadata(
            spec=spec,
            rule_ids=tuple(sorted(rule_ids_by_analyzer.get(spec.key, []))),
            delivery=_build_delivery_metadata(spec, tuple(sorted(rule_ids_by_analyzer.get(spec.key, [])))),
        )
        for spec in analyzer_specs
    )
    analyzer_metadata_by_key = {analyzer.spec.key: analyzer for analyzer in analyzers}
    rules = tuple(
        _build_rule_metadata(
            rule,
            mapped_analyzers=mapped_analyzers,
            analyzer_metadata_by_key=analyzer_metadata_by_key,
        )
        for rule, mapped_analyzers in mapped_rules
    )

    return AnalyzerCatalog(
        analyzers=analyzers,
        semantic_rule_groups=semantic_rule_groups,
        rules=rules,
    )


def get_enabled_analyzers() -> list[AnalyzerSpec]:
    return list(get_default_analyzer_catalog().enabled_specs())


def get_default_cli_analyzers() -> list[AnalyzerSpec]:
    enabled_by_key = {spec.key.casefold(): spec for spec in get_enabled_analyzers()}
    return [enabled_by_key[key] for key in DEFAULT_CLI_ANALYZER_KEYS if key in enabled_by_key]


def get_default_analyzers() -> list[AnalyzerSpec]:
    return build_default_analyzers(semantic_layer_analyzer_key=SEMANTIC_LAYER_ANALYZER_KEY)
