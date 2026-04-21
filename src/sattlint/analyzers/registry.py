"""Analyzer registry for CLI entrypoints."""
from __future__ import annotations

from dataclasses import dataclass

from sattlint.analyzers.alarm_integrity import analyze_alarm_integrity
from sattlint.analyzers.initial_values import analyze_initial_values
from sattlint.analyzers.modules import analyze_version_drift
from sattlint.analyzers.naming import analyze_naming_consistency, get_configured_naming_rules
from sattlint.analyzers.spec_compliance import analyze_spec_compliance
from sattlint.analyzers.safety_paths import analyze_safety_paths
from sattlint.analyzers.taint_paths import analyze_taint_paths

from .dataflow import analyze_dataflow
from .framework import AnalysisContext, AnalyzerSpec
from .sattline_semantics import (
    SemanticRule,
    SemanticRuleGroup,
    analyze_sattline_semantics,
    get_sattline_semantic_rule_groups,
)
from .sfc import (
    analyze_sfc,
    get_configured_mutually_exclusive_step_sets,
    get_configured_step_contracts,
)
from .unsafe_defaults import analyze_unsafe_defaults
from .variables import analyze_variables
from .shadowing import analyze_shadowing
from .comment_code import analyze_comment_code
from .mms import analyze_mms_interface_variables


SEMANTIC_LAYER_ANALYZER_KEY = "sattline-semantics"
DEFAULT_CLI_ANALYZER_KEYS: tuple[str, ...] = (
    "variables",
    "mms-interface",
    "sfc",
    "comment-code",
    "shadowing",
    "spec-compliance",
)


@dataclass(frozen=True)
class AnalyzerMetadata:
    spec: AnalyzerSpec
    rule_ids: tuple[str, ...] = ()

    @property
    def summary_output(self) -> str:
        return f"{self.spec.key}.summary"

    def to_dict(self) -> dict[str, object]:
        return {
            "key": self.spec.key,
            "name": self.spec.name,
            "description": self.spec.description,
            "enabled": self.spec.enabled,
            "supports_live_diagnostics": self.spec.supports_live_diagnostics,
            "summary_output": self.summary_output,
            "rule_ids": list(self.rule_ids),
        }


@dataclass(frozen=True)
class RuleMetadata:
    id: str
    source: str
    category: str
    severity: str
    applies_to: str
    description: str
    analyzers: tuple[str, ...]
    outputs: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "source": self.source,
            "category": self.category,
            "severity": self.severity,
            "applies_to": self.applies_to,
            "description": self.description,
            "analyzers": list(self.analyzers),
            "outputs": list(self.outputs),
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
                "source_rule_counts": {
                    group.source: len(group.rules)
                    for group in self.semantic_rule_groups
                },
            },
            "rules": [rule.to_dict() for rule in self.rules],
        }


def _summary_output_for_analyzer(analyzer_key: str) -> str:
    return f"{analyzer_key}.summary"


def _iter_semantic_rules(
    semantic_rule_groups: tuple[SemanticRuleGroup, ...],
) -> tuple[SemanticRule, ...]:
    return tuple(
        rule
        for group in semantic_rule_groups
        for rule in group.rules
    )


def get_default_analyzer_catalog() -> AnalyzerCatalog:
    analyzer_specs = tuple(get_default_analyzers())
    semantic_rule_groups = get_sattline_semantic_rule_groups()
    registered_keys = {spec.key for spec in analyzer_specs}
    rule_ids_by_analyzer: dict[str, list[str]] = {spec.key: [] for spec in analyzer_specs}
    rule_ids_by_analyzer.setdefault(SEMANTIC_LAYER_ANALYZER_KEY, [])

    rules: list[RuleMetadata] = []
    for rule in sorted(_iter_semantic_rules(semantic_rule_groups), key=lambda item: item.id):
        mapped_analyzers = [SEMANTIC_LAYER_ANALYZER_KEY]
        if rule.source in registered_keys and rule.source not in mapped_analyzers:
            mapped_analyzers.append(rule.source)

        mapped_outputs = tuple(_summary_output_for_analyzer(key) for key in mapped_analyzers)
        for analyzer_key in mapped_analyzers:
            rule_ids_by_analyzer.setdefault(analyzer_key, []).append(rule.id)

        rules.append(
            RuleMetadata(
                id=rule.id,
                source=rule.source,
                category=rule.category,
                severity=rule.severity,
                applies_to=rule.applies_to,
                description=rule.description,
                analyzers=tuple(mapped_analyzers),
                outputs=mapped_outputs,
            )
        )

    analyzers = tuple(
        AnalyzerMetadata(
            spec=spec,
            rule_ids=tuple(sorted(rule_ids_by_analyzer.get(spec.key, []))),
        )
        for spec in analyzer_specs
    )

    return AnalyzerCatalog(
        analyzers=analyzers,
        semantic_rule_groups=semantic_rule_groups,
        rules=tuple(rules),
    )


def get_enabled_analyzers() -> list[AnalyzerSpec]:
    return list(get_default_analyzer_catalog().enabled_specs())


def get_default_cli_analyzers() -> list[AnalyzerSpec]:
    enabled_by_key = {
        spec.key.casefold(): spec
        for spec in get_enabled_analyzers()
    }
    return [
        enabled_by_key[key]
        for key in DEFAULT_CLI_ANALYZER_KEYS
        if key in enabled_by_key
    ]


def get_default_analyzers() -> list[AnalyzerSpec]:
    def _run_variables(context: AnalysisContext):
        return analyze_variables(
            context.base_picture,
            debug=context.debug,
            unavailable_libraries=context.unavailable_libraries,
            analyzed_target_is_library=context.target_is_library,
        )

    def _run_sattline_semantics(context: AnalysisContext):
        return analyze_sattline_semantics(
            context.base_picture,
            debug=context.debug,
            unavailable_libraries=context.unavailable_libraries,
            analyzed_target_is_library=context.target_is_library,
            sfc_mutually_exclusive_steps=get_configured_mutually_exclusive_step_sets(
                context.config
            ),
            sfc_step_contracts=get_configured_step_contracts(context.config),
        )

    def _run_mms_interface(context: AnalysisContext):
        return analyze_mms_interface_variables(
            context.base_picture,
            debug=context.debug,
            config=context.config,
        )

    def _run_sfc_checks(context: AnalysisContext):
        return analyze_sfc(
            context.base_picture,
            mutually_exclusive_steps=get_configured_mutually_exclusive_step_sets(
                context.config
            ),
            step_contracts=get_configured_step_contracts(context.config),
        )

    def _run_shadowing(context: AnalysisContext):
        return analyze_shadowing(
            context.base_picture,
            debug=context.debug,
            unavailable_libraries=context.unavailable_libraries,
        )

    def _run_spec_compliance(context: AnalysisContext):
        return analyze_spec_compliance(
            context.base_picture,
            debug=context.debug,
            unavailable_libraries=context.unavailable_libraries,
        )

    def _run_alarm_integrity(context: AnalysisContext):
        return analyze_alarm_integrity(
            context.base_picture,
            debug=context.debug,
            unavailable_libraries=context.unavailable_libraries,
        )

    def _run_initial_values(context: AnalysisContext):
        return analyze_initial_values(
            context.base_picture,
            debug=context.debug,
            unavailable_libraries=context.unavailable_libraries,
        )

    def _run_naming_consistency(context: AnalysisContext):
        return analyze_naming_consistency(
            context.base_picture,
            rules=get_configured_naming_rules(context.config),
        )

    def _run_version_drift(context: AnalysisContext):
        return analyze_version_drift(
            context.base_picture,
            debug=context.debug,
        )

    def _run_safety_paths(context: AnalysisContext):
        return analyze_safety_paths(
            context.base_picture,
            debug=context.debug,
            unavailable_libraries=context.unavailable_libraries,
            analyzed_target_is_library=context.target_is_library,
        )

    def _run_taint_paths(context: AnalysisContext):
        return analyze_taint_paths(
            context.base_picture,
            debug=context.debug,
            unavailable_libraries=context.unavailable_libraries,
            analyzed_target_is_library=context.target_is_library,
        )

    def _run_unsafe_defaults(context: AnalysisContext):
        return analyze_unsafe_defaults(context.base_picture)

    def _run_dataflow(context: AnalysisContext):
        return analyze_dataflow(
            context.base_picture,
            unavailable_libraries=context.unavailable_libraries,
        )

    def _run_comment_code(context: AnalysisContext):
        return analyze_comment_code(context)

    return [
        AnalyzerSpec(
            key=SEMANTIC_LAYER_ANALYZER_KEY,
            name="SattLine semantics",
            description="Aggregated domain-aware semantic checks for SattLine programs and libraries",
            run=_run_sattline_semantics,
            enabled=True,
        ),
        AnalyzerSpec(
            key="variables",
            name="Variable issues",
            description="Unused/read-only/never-read variables and type mismatches",
            run=_run_variables,
            supports_live_diagnostics=True,
        ),
        AnalyzerSpec(
            key="mms-interface",
            name="MMS interface mappings",
            description="MMSWriteVar/MMSReadVar inventory with OPC and MES validation checks",
            run=_run_mms_interface,
        ),
        AnalyzerSpec(
            key="sfc",
            name="SFC checks",
            description="Parallel-branch write race and structural dead-path detection",
            run=_run_sfc_checks,
            enabled=True,
        ),
        AnalyzerSpec(
            key="comment-code",
            name="Commented-out code",
            description="Code-like content inside comments",
            run=_run_comment_code,
            enabled=True,
        ),
        AnalyzerSpec(
            key="shadowing",
            name="Variable shadowing",
            description="Local variables hiding outer or global names",
            run=_run_shadowing,
            enabled=True,
        ),
        AnalyzerSpec(
            key="spec-compliance",
            name="Engineering spec compliance",
            description="AST-visible checks from the application engineering spec",
            run=_run_spec_compliance,
            enabled=True,
        ),
        AnalyzerSpec(
            key="alarm-integrity",
            name="Alarm integrity",
            description="Cross-module duplicate tag, duplicate condition, priority, and latch-style alarm checks",
            run=_run_alarm_integrity,
            enabled=True,
        ),
        AnalyzerSpec(
            key="initial-values",
            name="Initial value validation",
            description="Detect recipe and engineering parameter modules that do not resolve a required startup value",
            run=_run_initial_values,
            enabled=True,
        ),
        AnalyzerSpec(
            key="naming-consistency",
            name="Naming consistency",
            description="Detect inconsistent naming styles for variables, modules, and instances across the analyzed target",
            run=_run_naming_consistency,
            enabled=True,
        ),
        AnalyzerSpec(
            key="version-drift",
            name="Version drift",
            description="Detect repeated module names that have drifted structurally beyond datecode-only changes",
            run=_run_version_drift,
            enabled=True,
        ),
        AnalyzerSpec(
            key="safety-paths",
            name="Safety paths",
            description="Cross-module tracing for shutdown and emergency signal propagation",
            run=_run_safety_paths,
            enabled=True,
        ),
        AnalyzerSpec(
            key="taint-paths",
            name="Taint paths",
            description="Cross-module taint tracing from external inputs to safety-critical sinks",
            run=_run_taint_paths,
            enabled=True,
        ),
        AnalyzerSpec(
            key="unsafe-defaults",
            name="Unsafe defaults",
            description="Explicit boolean defaults that can enable logic or bypass safeguards at startup",
            run=_run_unsafe_defaults,
            enabled=True,
        ),
        AnalyzerSpec(
            key="dataflow",
            name="Lightweight dataflow",
            description="Constant-condition and unreachable-path detection across branches",
            run=_run_dataflow,
            enabled=True,
        ),
    ]
