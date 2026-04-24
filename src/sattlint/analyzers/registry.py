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
from sattlint.analyzers.taint_paths import analyze_taint_paths

from .comment_code import analyze_comment_code
from .dataflow import analyze_dataflow
from .framework import AnalysisContext, AnalyzerSpec
from .mms import analyze_mms_interface_variables
from .rule_profiles import get_default_rule_profile_report
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


@dataclass(frozen=True)
class AnalyzerDeliveryMetadata:
    scope: str
    implementation_bucket: str
    output_artifacts: tuple[str, ...] = ()
    cli_exposed: bool = False
    lsp_exposed: bool = False
    acceptance_tests: tuple[str, ...] = ()
    depends_on_analyzers: tuple[str, ...] = ()
    depends_on_artifacts: tuple[str, ...] = ()
    supports_baselines: bool = True
    supports_incremental: bool = False
    min_fixture_set: tuple[str, ...] = ()
    exposed_via: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "scope": self.scope,
            "implementation_bucket": self.implementation_bucket,
            "output_artifacts": list(self.output_artifacts),
            "cli_exposed": self.cli_exposed,
            "lsp_exposed": self.lsp_exposed,
            "acceptance_tests": list(self.acceptance_tests),
            "depends_on_analyzers": list(self.depends_on_analyzers),
            "depends_on_artifacts": list(self.depends_on_artifacts),
            "supports_baselines": self.supports_baselines,
            "supports_incremental": self.supports_incremental,
            "min_fixture_set": list(self.min_fixture_set),
            "exposed_via": list(self.exposed_via),
        }


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


def _summary_output_for_analyzer(analyzer_key: str) -> str:
    return f"{analyzer_key}.summary"


def _base_delivery_metadata_by_analyzer() -> dict[str, AnalyzerDeliveryMetadata]:
    shared_fixtures = ("tests/fixtures/sample_sattline_files",)
    return {
        SEMANTIC_LAYER_ANALYZER_KEY: AnalyzerDeliveryMetadata(
            scope="workspace",
            implementation_bucket="shared-semantic-core",
            lsp_exposed=True,
            acceptance_tests=(
                "tests/test_sattline_semantics.py",
                "tests/test_pipeline.py",
            ),
            min_fixture_set=shared_fixtures,
        ),
        "variables": AnalyzerDeliveryMetadata(
            scope="workspace",
            implementation_bucket="variables-reporting",
            cli_exposed=True,
            lsp_exposed=True,
            acceptance_tests=(
                "tests/test_analyzers.py",
                "tests/test_sattline_semantics.py",
                "tests/test_app.py",
            ),
            supports_incremental=True,
            min_fixture_set=shared_fixtures,
            exposed_via=(SEMANTIC_LAYER_ANALYZER_KEY,),
        ),
        "mms-interface": AnalyzerDeliveryMetadata(
            scope="workspace",
            implementation_bucket="interface-mapping",
            cli_exposed=True,
            acceptance_tests=(
                "tests/test_analyzers.py",
                "tests/test_app.py",
            ),
            min_fixture_set=shared_fixtures,
        ),
        "sfc": AnalyzerDeliveryMetadata(
            scope="single-file",
            implementation_bucket="shared-semantic-core",
            cli_exposed=True,
            lsp_exposed=True,
            acceptance_tests=(
                "tests/test_sfc.py",
                "tests/test_analyzers.py",
                "tests/test_sattline_semantics.py",
            ),
            depends_on_analyzers=(SEMANTIC_LAYER_ANALYZER_KEY,),
            min_fixture_set=shared_fixtures,
            exposed_via=(SEMANTIC_LAYER_ANALYZER_KEY,),
        ),
        "comment-code": AnalyzerDeliveryMetadata(
            scope="single-file",
            implementation_bucket="comment-scan",
            cli_exposed=True,
            acceptance_tests=(
                "tests/test_comment_code.py",
                "tests/test_app.py",
            ),
        ),
        "shadowing": AnalyzerDeliveryMetadata(
            scope="workspace",
            implementation_bucket="variables-reporting",
            cli_exposed=True,
            acceptance_tests=(
                "tests/test_analyzers.py",
                "tests/test_app.py",
                "tests/test_pipeline.py",
            ),
            min_fixture_set=shared_fixtures,
        ),
        "spec-compliance": AnalyzerDeliveryMetadata(
            scope="workspace",
            implementation_bucket="engineering-rules",
            cli_exposed=True,
            lsp_exposed=True,
            acceptance_tests=(
                "tests/test_spec_compliance.py",
                "tests/test_app.py",
            ),
            min_fixture_set=shared_fixtures,
        ),
        "loop-output-refactor": AnalyzerDeliveryMetadata(
            scope="single-file",
            implementation_bucket="engineering-rules",
            cli_exposed=True,
            acceptance_tests=(
                "tests/test_analyzers.py",
                "tests/test_app.py",
            ),
            min_fixture_set=shared_fixtures,
        ),
        "alarm-integrity": AnalyzerDeliveryMetadata(
            scope="cross-module",
            implementation_bucket="shared-semantic-core",
            lsp_exposed=True,
            acceptance_tests=(
                "tests/test_analyzers.py",
                "tests/test_sattline_semantics.py",
            ),
            depends_on_analyzers=(SEMANTIC_LAYER_ANALYZER_KEY,),
            min_fixture_set=shared_fixtures,
            exposed_via=(SEMANTIC_LAYER_ANALYZER_KEY,),
        ),
        "initial-values": AnalyzerDeliveryMetadata(
            scope="workspace",
            implementation_bucket="engineering-rules",
            lsp_exposed=True,
            acceptance_tests=("tests/test_analyzers.py",),
            min_fixture_set=shared_fixtures,
        ),
        "naming-consistency": AnalyzerDeliveryMetadata(
            scope="workspace",
            implementation_bucket="engineering-rules",
            acceptance_tests=("tests/test_analyzers.py",),
            min_fixture_set=shared_fixtures,
            exposed_via=("pipeline",),
        ),
        "cyclomatic-complexity": AnalyzerDeliveryMetadata(
            scope="single-file",
            implementation_bucket="engineering-rules",
            acceptance_tests=("tests/test_analyzers.py",),
            min_fixture_set=shared_fixtures,
            exposed_via=("pipeline",),
        ),
        "parameter-drift": AnalyzerDeliveryMetadata(
            scope="cross-module",
            implementation_bucket="engineering-rules",
            acceptance_tests=("tests/test_analyzers.py",),
            min_fixture_set=shared_fixtures,
            exposed_via=("pipeline",),
        ),
        "scan-loop-resource-usage": AnalyzerDeliveryMetadata(
            scope="single-file",
            implementation_bucket="engineering-rules",
            acceptance_tests=("tests/test_analyzers.py",),
            min_fixture_set=shared_fixtures,
            exposed_via=("pipeline",),
        ),
        "version-drift": AnalyzerDeliveryMetadata(
            scope="workspace",
            implementation_bucket="engineering-rules",
            acceptance_tests=(
                "tests/test_analyzers.py",
                "tests/test_docgen.py",
            ),
            min_fixture_set=shared_fixtures,
            exposed_via=("docgen",),
        ),
        "safety-paths": AnalyzerDeliveryMetadata(
            scope="cross-module",
            implementation_bucket="shared-semantic-core",
            lsp_exposed=True,
            acceptance_tests=(
                "tests/test_analyzers.py",
                "tests/test_sattline_semantics.py",
                "tests/test_editor_api.py",
            ),
            depends_on_analyzers=(SEMANTIC_LAYER_ANALYZER_KEY,),
            min_fixture_set=shared_fixtures,
            exposed_via=(SEMANTIC_LAYER_ANALYZER_KEY, "editor-api"),
        ),
        "taint-paths": AnalyzerDeliveryMetadata(
            scope="cross-module",
            implementation_bucket="graph-tracing",
            lsp_exposed=True,
            acceptance_tests=(
                "tests/test_analyzers.py",
                "tests/test_editor_api.py",
            ),
            min_fixture_set=shared_fixtures,
            exposed_via=(SEMANTIC_LAYER_ANALYZER_KEY, "editor-api"),
        ),
        "unsafe-defaults": AnalyzerDeliveryMetadata(
            scope="single-file",
            implementation_bucket="shared-semantic-core",
            lsp_exposed=True,
            acceptance_tests=(
                "tests/test_pipeline.py",
                "tests/test_sattline_semantics.py",
            ),
            depends_on_analyzers=(SEMANTIC_LAYER_ANALYZER_KEY,),
            min_fixture_set=shared_fixtures,
            exposed_via=(SEMANTIC_LAYER_ANALYZER_KEY,),
        ),
        "dataflow": AnalyzerDeliveryMetadata(
            scope="workspace",
            implementation_bucket="shared-semantic-core",
            lsp_exposed=True,
            acceptance_tests=(
                "tests/test_dataflow.py",
                "tests/test_analyzers.py",
                "tests/test_sattline_semantics.py",
            ),
            depends_on_analyzers=(SEMANTIC_LAYER_ANALYZER_KEY,),
            min_fixture_set=shared_fixtures,
            exposed_via=(SEMANTIC_LAYER_ANALYZER_KEY,),
        ),
    }


def _build_delivery_metadata(
    spec: AnalyzerSpec,
    rule_ids: tuple[str, ...],
) -> AnalyzerDeliveryMetadata:
    base = _base_delivery_metadata_by_analyzer().get(spec.key)
    if base is None:
        return AnalyzerDeliveryMetadata(
            scope="workspace",
            implementation_bucket="analyzers",
            output_artifacts=(_summary_output_for_analyzer(spec.key),),
        )

    output_artifacts = [_summary_output_for_analyzer(spec.key)]
    semantic_summary = _summary_output_for_analyzer(SEMANTIC_LAYER_ANALYZER_KEY)
    if spec.key != SEMANTIC_LAYER_ANALYZER_KEY and rule_ids and semantic_summary not in output_artifacts:
        output_artifacts.append(semantic_summary)

    return AnalyzerDeliveryMetadata(
        scope=base.scope,
        implementation_bucket=base.implementation_bucket,
        output_artifacts=tuple(output_artifacts),
        cli_exposed=base.cli_exposed,
        lsp_exposed=base.lsp_exposed,
        acceptance_tests=base.acceptance_tests,
        depends_on_analyzers=base.depends_on_analyzers,
        depends_on_artifacts=base.depends_on_artifacts,
        supports_baselines=base.supports_baselines,
        supports_incremental=base.supports_incremental,
        min_fixture_set=base.min_fixture_set,
        exposed_via=base.exposed_via,
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
            else _summary_output_for_analyzer(analyzer_key)
            for analyzer_key in mapped_analyzers
        ),
        acceptance_tests=(None if rule.acceptance_tests is None else tuple(sorted(rule.acceptance_tests))),
        corpus_cases=corpus_cases,
        mutation_applicability=rule.mutation_applicability,
        suppression_modes=(None if rule.suppression_modes is None else tuple(sorted(rule.suppression_modes))),
        incremental_safe=rule.incremental_safe,
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
            delivery=_build_delivery_metadata(
                spec,
                tuple(sorted(rule_ids_by_analyzer.get(spec.key, []))),
            ),
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
    def _run_variables(context: AnalysisContext):
        return analyze_variables(
            context.base_picture,
            debug=context.debug,
            unavailable_libraries=context.unavailable_libraries,
            analyzed_target_is_library=context.target_is_library,
            config=context.config,
        )

    def _run_sattline_semantics(context: AnalysisContext):
        return analyze_sattline_semantics(
            context.base_picture,
            debug=context.debug,
            unavailable_libraries=context.unavailable_libraries,
            analyzed_target_is_library=context.target_is_library,
            sfc_mutually_exclusive_steps=get_configured_mutually_exclusive_step_sets(context.config),
            sfc_step_contracts=get_configured_step_contracts(context.config),
            config=context.config,
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
            mutually_exclusive_steps=get_configured_mutually_exclusive_step_sets(context.config),
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

    def _run_loop_output_refactor(context: AnalysisContext):
        return analyze_loop_output_refactor(context.base_picture)

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

    def _run_cyclomatic_complexity(context: AnalysisContext):
        return analyze_cyclomatic_complexity(context.base_picture)

    def _run_parameter_drift(context: AnalysisContext):
        return analyze_parameter_drift(
            context.base_picture,
            unavailable_libraries=context.unavailable_libraries,
        )

    def _run_scan_loop_resource_usage(context: AnalysisContext):
        return analyze_scan_loop_resource_usage(context.base_picture)

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
            key="loop-output-refactor",
            name="Loop output refactor",
            description="Detect dependency loops across sorted equation blocks and active step code",
            run=_run_loop_output_refactor,
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
            key="cyclomatic-complexity",
            name="Cyclomatic complexity",
            description="Detect modules and SFC steps whose control-flow complexity exceeds default thresholds",
            run=_run_cyclomatic_complexity,
            enabled=True,
        ),
        AnalyzerSpec(
            key="parameter-drift",
            name="Parameter drift",
            description="Detect moduletype instances whose resolved literal parameter values drift across the analyzed target",
            run=_run_parameter_drift,
            enabled=True,
        ),
        AnalyzerSpec(
            key="scan-loop-resource-usage",
            name="Scan-loop resource usage",
            description="Detect non precision-scan-safe builtin calls inside equation blocks and SFC active code",
            run=_run_scan_loop_resource_usage,
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
