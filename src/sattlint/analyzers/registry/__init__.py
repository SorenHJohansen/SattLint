"""Analyzer registry for CLI entrypoints."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import cast

from ...repo_paths import repo_root_from
from ..alarm_integrity import analyze_alarm_integrity
from ..comment_code import analyze_comment_code
from ..config_drift import analyze_config_drift
from ..cyclomatic_complexity import analyze_cyclomatic_complexity
from ..data_dependency import analyze_data_dependency
from ..dataflow import analyze_dataflow
from ..fault_handling import analyze_fault_handling
from ..framework import AnalyzerSpec
from ..initial_values import analyze_initial_values
from ..interface_contracts import analyze_interface_contracts
from ..loop_output_refactor import analyze_loop_output_refactor
from ..loop_stability import analyze_loop_stability
from ..mms import analyze_mms_interface_variables
from ..modules import analyze_version_drift
from ..naming import analyze_naming_consistency, get_configured_naming_rules
from ..numeric_constraints import analyze_numeric_constraints
from ..parameter_drift import analyze_parameter_drift
from ..picture_display_paths import analyze_picture_display_paths
from ..powerup import analyze_powerup
from ..resource_usage import analyze_resource_usage
from ..rule_profiles import get_default_rule_profile_report
from ..safety_paths import analyze_safety_paths
from ..same_cycle import analyze_same_cycle
from ..sattline_semantics import (
    SemanticRule,
    SemanticRuleGroup,
    analyze_sattline_semantics,
    get_sattline_semantic_rule_groups,
)
from ..scan_concurrency import analyze_scan_concurrency
from ..scan_loop_resource_usage import analyze_scan_loop_resource_usage
from ..sfc import analyze_sfc, get_configured_mutually_exclusive_step_sets, get_configured_step_contracts
from ..shadowing import analyze_shadowing
from ..signal_lifecycle import analyze_signal_lifecycle
from ..spec_compliance import analyze_spec_compliance
from ..state_inference import analyze_state_inference
from ..taint_paths import analyze_taint_paths
from ..timing import analyze_timing
from ..unsafe_defaults import analyze_unsafe_defaults
from ..variables import analyze_variables
from ._registry_delivery import AnalyzerDeliveryMetadata, build_delivery_metadata, summary_output_for_analyzer
from ._registry_specs import build_default_analyzers

SEMANTIC_LAYER_ANALYZER_KEY = "sattline-semantics"
DEFAULT_CLI_ANALYZER_KEYS: tuple[str, ...] = (
    "variables",
    "picture-display-paths",
    "mms-interface",
    "sfc",
    "comment-code",
    "shadowing",
    "spec-compliance",
    "loop-output-refactor",
    "powerup",
    "timing",
)
REPO_ROOT = repo_root_from(Path(__file__))
DEFAULT_CORPUS_MANIFEST_DIR = REPO_ROOT / "tests" / "fixtures" / "corpus" / "manifests"

LEGACY_ANALYZER_KEY_ALIASES: dict[str, str] = {
    "config_drift": "config-drift",
    "data_dependency": "data-dependency",
    "fault_handling": "fault-handling",
    "interface_contracts": "interface-contracts",
    "loop_stability": "loop-stability",
    "numeric_constraints": "numeric-constraints",
    "resource_usage": "resource-usage",
    "scan_concurrency": "scan-concurrency",
    "same_cycle": "same-cycle",
    "signal_lifecycle": "signal-lifecycle",
    "state_inference": "state-inference",
}

_RULE_ANALYZER_ALIASES: dict[str, tuple[str, ...]] = {
    "semantic.unknown-parameter-target": ("interface-contracts",),
    "semantic.required-parameter-connection": ("interface-contracts",),
    "semantic.cross-module-contract-mismatch": ("interface-contracts",),
    "semantic.string-mapping-mismatch": ("interface-contracts",),
    "semantic.missing-parameter-initial-value": ("powerup",),
    "semantic.unsafe-default-true": ("powerup",),
    "semantic.parallel-write-race": ("scan-concurrency", "same-cycle"),
    "semantic.scan-cycle-stale-read": ("timing",),
    "semantic.scan-cycle-implicit-new": ("timing",),
    "semantic.scan-cycle-temporal-misuse": ("timing",),
}

# Preserve the historical monkeypatch surface that tests and extracted helper modules use.
_REGISTRY_MONKEYPATCH_SURFACE = (
    analyze_alarm_integrity,
    analyze_comment_code,
    analyze_config_drift,
    analyze_cyclomatic_complexity,
    analyze_data_dependency,
    analyze_interface_contracts,
    analyze_dataflow,
    analyze_fault_handling,
    analyze_initial_values,
    analyze_loop_stability,
    analyze_loop_output_refactor,
    analyze_mms_interface_variables,
    analyze_naming_consistency,
    analyze_numeric_constraints,
    analyze_parameter_drift,
    analyze_picture_display_paths,
    analyze_powerup,
    analyze_resource_usage,
    analyze_safety_paths,
    analyze_same_cycle,
    analyze_scan_concurrency,
    analyze_sattline_semantics,
    analyze_scan_loop_resource_usage,
    analyze_sfc,
    analyze_shadowing,
    analyze_signal_lifecycle,
    analyze_spec_compliance,
    analyze_state_inference,
    analyze_taint_paths,
    analyze_timing,
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
        data: dict[str, object] = {
            "key": self.spec.key,
            "name": self.spec.name,
            "description": self.spec.description,
            "enabled": self.spec.enabled,
            "supports_live_diagnostics": self.spec.supports_live_diagnostics,
            "semantic_mapping_kind": self.spec.semantic_mapping_kind,
            "semantic_rule_source": self.spec.semantic_rule_source,
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
        semantic_sources = tuple(canonicalize_analyzer_key(group.source) for group in self.semantic_rule_groups)
        return {
            "generated_by": generated_by,
            "analyzers": [analyzer.to_dict() for analyzer in self.analyzers],
            "semantic_layer": {
                "analyzer_key": self.semantic_layer_analyzer_key,
                "sources": list(semantic_sources),
                "source_rule_counts": {
                    canonicalize_analyzer_key(group.source): len(group.rules) for group in self.semantic_rule_groups
                },
            },
            "rule_profiles": get_default_rule_profile_report(),
            "rules": [rule.to_dict() for rule in self.rules],
        }


def _is_batch_dispatch_analyzer(spec: AnalyzerSpec) -> bool:
    # The semantic layer aggregates semantic contributors and is only safe via
    # explicit direct-call surfaces such as corpus reporting.
    return spec.key != SEMANTIC_LAYER_ANALYZER_KEY


def canonicalize_analyzer_key(key: str) -> str:
    return LEGACY_ANALYZER_KEY_ALIASES.get(key.casefold(), key.casefold())


def canonicalize_analyzer_keys(keys: tuple[str, ...] | list[str] | set[str]) -> tuple[str, ...]:
    return tuple(canonicalize_analyzer_key(key) for key in keys if key.strip())


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
            (
                {catalog.semantic_layer_analyzer_key}
                | {canonicalize_analyzer_key(group.source) for group in catalog.semantic_rule_groups}
            )
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

        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        case_id = str(payload.get("case_id") or manifest_path.stem)
        expectation_payload = payload.get("expectation")
        expectation: dict[str, object] = (
            cast(dict[str, object], expectation_payload) if isinstance(expectation_payload, dict) else {}
        )
        expected_finding_ids = expectation.get("expected_finding_ids", [])
        if not isinstance(expected_finding_ids, list):
            continue
        for rule_id in cast(list[object], expected_finding_ids):
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
        source=canonicalize_analyzer_key(rule.source),
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


def _mapped_analyzers_for_rule(
    rule: SemanticRule,
    *,
    registered_keys: set[str],
) -> tuple[str, ...]:
    mapped_analyzers: list[str] = [SEMANTIC_LAYER_ANALYZER_KEY]
    canonical_rule_source = canonicalize_analyzer_key(rule.source)
    if canonical_rule_source in registered_keys and canonical_rule_source not in mapped_analyzers:
        mapped_analyzers.append(canonical_rule_source)

    for analyzer_key in _RULE_ANALYZER_ALIASES.get(rule.id, ()):
        if analyzer_key in registered_keys and analyzer_key not in mapped_analyzers:
            mapped_analyzers.append(analyzer_key)

    return tuple(mapped_analyzers)


def get_default_analyzer_catalog() -> AnalyzerCatalog:
    analyzer_specs = tuple(get_default_analyzers())
    semantic_rule_groups = get_sattline_semantic_rule_groups()
    registered_keys = {spec.key for spec in analyzer_specs}
    rule_ids_by_analyzer: dict[str, list[str]] = {spec.key: [] for spec in analyzer_specs}
    rule_ids_by_analyzer.setdefault(SEMANTIC_LAYER_ANALYZER_KEY, [])

    mapped_rules: list[tuple[SemanticRule, tuple[str, ...]]] = []
    for rule in sorted(_iter_semantic_rules(semantic_rule_groups), key=lambda item: item.id):
        mapped_analyzers = _mapped_analyzers_for_rule(rule, registered_keys=registered_keys)

        for analyzer_key in mapped_analyzers:
            rule_ids_by_analyzer.setdefault(analyzer_key, []).append(rule.id)
        mapped_rules.append((rule, mapped_analyzers))

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
    return [spec for spec in get_default_analyzer_catalog().enabled_specs() if _is_batch_dispatch_analyzer(spec)]


def get_selectable_analyzers() -> list[AnalyzerSpec]:
    return [spec for spec in get_default_analyzers() if _is_batch_dispatch_analyzer(spec)]


def get_default_cli_analyzers() -> list[AnalyzerSpec]:
    enabled_by_key = {spec.key.casefold(): spec for spec in get_enabled_analyzers()}
    return [
        enabled_by_key[key] for key in canonicalize_analyzer_keys(DEFAULT_CLI_ANALYZER_KEYS) if key in enabled_by_key
    ]


def get_default_analyzers() -> list[AnalyzerSpec]:
    return build_default_analyzers(semantic_layer_analyzer_key=SEMANTIC_LAYER_ANALYZER_KEY)
