"""Declarative analyzer spec templates for the registry builder."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AnalyzerSpecTemplate:
    key: str
    name: str
    description: str
    analyzer_attr: str
    requires: tuple[str, ...] = ()
    context_kwargs: tuple[str, ...] = ()
    enabled: bool = True
    supports_live_diagnostics: bool = False
    direct_context: bool = False
    semantic_mapping_kind: str | None = None
    semantic_rule_source: str | None = None
    composed_analyzer_keys: tuple[str, ...] = ()
    composed_issue_kind_names: tuple[str, ...] = ()


def default_spec_templates(semantic_layer_analyzer_key: str) -> tuple[AnalyzerSpecTemplate, ...]:
    return (
        AnalyzerSpecTemplate(
            key=semantic_layer_analyzer_key,
            name="SattLine semantics",
            description="Aggregated domain-aware semantic checks for SattLine programs and libraries",
            analyzer_attr="analyze_sattline_semantics",
            context_kwargs=(
                "analysis_context",
                "debug",
                "unavailable_libraries",
                "analyzed_target_is_library",
                "sfc_mutually_exclusive_steps",
                "sfc_step_contracts",
                "config",
            ),
        ),
        AnalyzerSpecTemplate(
            key="variables",
            name="Variable issues",
            description="Unused/read-only/never-read variables and type mismatches",
            analyzer_attr="analyze_variables",
            context_kwargs=(
                "analysis_context",
                "debug",
                "unavailable_libraries",
                "analyzed_target_is_library",
                "include_dependency_moduletype_usage",
                "selected_issue_kinds",
                "config",
            ),
            supports_live_diagnostics=True,
            semantic_mapping_kind="variable",
            semantic_rule_source="variables",
        ),
        AnalyzerSpecTemplate(
            key="picture-display-paths",
            name="PictureDisplay paths",
            description="Resolve constant PictureDisplay module paths against the loaded module tree",
            analyzer_attr="analyze_picture_display_paths",
            context_kwargs=("graph", "analyzed_target_is_library"),
        ),
        AnalyzerSpecTemplate(
            key="mms-interface",
            name="MMS interface mappings",
            description="MMSWriteVar/MMSReadVar inventory with OPC and MES validation checks",
            analyzer_attr="analyze_mms_interface_variables",
            context_kwargs=("debug", "config"),
            semantic_rule_source="mms-interface",
        ),
        AnalyzerSpecTemplate(
            key="sfc",
            name="SFC checks",
            description="Parallel-branch write race and structural dead-path detection",
            analyzer_attr="analyze_sfc",
            requires=("variables",),
            context_kwargs=("analysis_context", "mutually_exclusive_steps", "step_contracts"),
            semantic_mapping_kind="framework",
            semantic_rule_source="sfc",
        ),
        AnalyzerSpecTemplate(
            key="comment-code",
            name="Commented-out code",
            description="Code-like content inside comments",
            analyzer_attr="analyze_comment_code",
            direct_context=True,
            semantic_rule_source="comment-code",
        ),
        AnalyzerSpecTemplate(
            key="shadowing",
            name="Variable shadowing",
            description="Local variables hiding outer or global names",
            analyzer_attr="analyze_shadowing",
            context_kwargs=("debug", "unavailable_libraries"),
            semantic_mapping_kind="variable",
            semantic_rule_source="variables",
        ),
        AnalyzerSpecTemplate(
            key="spec-compliance",
            name="Engineering spec compliance",
            description="AST-visible checks from the application engineering spec",
            analyzer_attr="analyze_spec_compliance",
            context_kwargs=("debug", "unavailable_libraries"),
            semantic_mapping_kind="spec",
            semantic_rule_source="spec-compliance",
        ),
        AnalyzerSpecTemplate(
            key="loop-output-refactor",
            name="Loop output refactor",
            description="Detect dependency loops across sorted equation blocks and active step code",
            analyzer_attr="analyze_loop_output_refactor",
            semantic_rule_source="loop-output-refactor",
        ),
        AnalyzerSpecTemplate(
            key="alarm-integrity",
            name="Alarm integrity",
            description="Cross-module duplicate tag, duplicate condition, priority, and latch-style alarm checks",
            analyzer_attr="analyze_alarm_integrity",
            context_kwargs=("debug", "unavailable_libraries"),
            semantic_mapping_kind="framework",
            semantic_rule_source="alarm-integrity",
        ),
        AnalyzerSpecTemplate(
            key="initial-values",
            name="Initial value validation",
            description="Detect recipe and engineering parameter modules that do not resolve a required startup value",
            analyzer_attr="analyze_initial_values",
            context_kwargs=("debug", "unavailable_libraries"),
            semantic_mapping_kind="framework",
            semantic_rule_source="initial-values",
        ),
        AnalyzerSpecTemplate(
            key="interface-contracts",
            name="Interface contracts",
            description="Detect missing required parameter mappings, unknown targets, and cross-module contract mismatches",
            analyzer_attr="analyze_interface_contracts",
            context_kwargs=("debug", "unavailable_libraries", "analyzed_target_is_library"),
        ),
        AnalyzerSpecTemplate(
            key="powerup",
            name="Power-up",
            description="Detect startup-value gaps and unsafe startup defaults that affect power-up behavior",
            analyzer_attr="analyze_powerup",
            context_kwargs=("debug", "unavailable_libraries"),
            composed_analyzer_keys=("initial-values", "unsafe-defaults"),
        ),
        AnalyzerSpecTemplate(
            key="naming-consistency",
            name="Naming consistency",
            description="Detect inconsistent naming styles for variables, modules, and instances across the analyzed target",
            analyzer_attr="analyze_naming_consistency",
            context_kwargs=("rules",),
        ),
        AnalyzerSpecTemplate(
            key="cyclomatic-complexity",
            name="Cyclomatic complexity",
            description="Detect modules and SFC steps whose control-flow complexity exceeds default thresholds",
            analyzer_attr="analyze_cyclomatic_complexity",
        ),
        AnalyzerSpecTemplate(
            key="parameter-drift",
            name="Parameter drift",
            description="Detect moduletype instances whose resolved literal parameter values drift across the analyzed target",
            analyzer_attr="analyze_parameter_drift",
            context_kwargs=("unavailable_libraries",),
        ),
        AnalyzerSpecTemplate(
            key="signal-lifecycle",
            name="Signal lifecycle",
            description="Track reads before writes and signals that are written but never consumed",
            analyzer_attr="analyze_signal_lifecycle",
            semantic_mapping_kind="framework",
            semantic_rule_source="signal-lifecycle",
        ),
        AnalyzerSpecTemplate(
            key="loop-stability",
            name="Loop stability",
            description="Detect contradictory literal setpoint writes that can destabilize scan-loop behavior",
            analyzer_attr="analyze_loop_stability",
            semantic_mapping_kind="framework",
            semantic_rule_source="loop-stability",
        ),
        AnalyzerSpecTemplate(
            key="fault-handling",
            name="Fault handling",
            description="Detect raised alarm or fault paths that are never cleared or never consumed",
            analyzer_attr="analyze_fault_handling",
            semantic_mapping_kind="framework",
            semantic_rule_source="fault-handling",
        ),
        AnalyzerSpecTemplate(
            key="numeric-constraints",
            name="Numeric constraints",
            description="Validate literal assignments against visible Min/Max style bounds",
            analyzer_attr="analyze_numeric_constraints",
            semantic_mapping_kind="framework",
            semantic_rule_source="numeric-constraints",
        ),
        AnalyzerSpecTemplate(
            key="data-dependency",
            name="Data dependency",
            description="Report deterministic dependency chains and initialization-order hazards",
            analyzer_attr="analyze_data_dependency",
            context_kwargs=("unavailable_libraries", "analyzed_target_is_library"),
            semantic_rule_source="data-dependency",
        ),
        AnalyzerSpecTemplate(
            key="config-drift",
            name="Config drift",
            description="Detect moduletype instances whose visible configuration signatures drift across the analyzed target",
            analyzer_attr="analyze_config_drift",
            context_kwargs=("unavailable_libraries",),
            semantic_mapping_kind="framework",
            semantic_rule_source="config-drift",
        ),
        AnalyzerSpecTemplate(
            key="scan-loop-resource-usage",
            name="Scan-loop resource usage",
            description="Detect non precision-scan-safe builtin calls inside equation blocks and SFC active code",
            analyzer_attr="analyze_scan_loop_resource_usage",
        ),
        AnalyzerSpecTemplate(
            key="resource-usage",
            name="Resource usage",
            description="Detect unreleased or prematurely released resource handles and scan-loop resource hazards",
            analyzer_attr="analyze_resource_usage",
            context_kwargs=("unavailable_libraries", "analyzed_target_is_library"),
            semantic_rule_source="resource-usage",
        ),
        AnalyzerSpecTemplate(
            key="scan-concurrency",
            name="Scan concurrency",
            description="Detect parallel scan or sequence branches that write the same variable without arbitration",
            analyzer_attr="analyze_scan_concurrency",
            context_kwargs=("config",),
            composed_analyzer_keys=("same-cycle",),
            composed_issue_kind_names=("sfc_parallel_write_race",),
        ),
        AnalyzerSpecTemplate(
            key="scan-shared-access",
            name="Scan shared access",
            description="Detect non-STATE variables that are read and written across multiple continuous scan sites",
            analyzer_attr="analyze_scan_shared_access",
            context_kwargs=("config",),
            composed_analyzer_keys=("same-cycle",),
            composed_issue_kind_names=("same_cycle_non_state_multi_site_hazard",),
        ),
        AnalyzerSpecTemplate(
            key="same-cycle",
            name="Same-cycle hazards",
            description="Detect same-scan shared-variable hazards across modules and parallel SFC branches",
            analyzer_attr="analyze_same_cycle",
            context_kwargs=("analysis_context", "debug", "unavailable_libraries", "analyzed_target_is_library"),
            supports_live_diagnostics=True,
            semantic_mapping_kind="framework",
            semantic_rule_source="same-cycle",
        ),
        AnalyzerSpecTemplate(
            key="timing",
            name="Timing",
            description="Detect scan-cycle temporal hazards and non precision-scan-safe resource usage",
            analyzer_attr="analyze_timing",
            context_kwargs=("unavailable_libraries", "analyzed_target_is_library"),
            composed_analyzer_keys=("dataflow", "scan-loop-resource-usage"),
            composed_issue_kind_names=(
                "dataflow.scan_cycle_stale_read",
                "dataflow.scan_cycle_implicit_new",
                "dataflow.scan_cycle_temporal_misuse",
                "scan_cycle.resource_usage",
            ),
        ),
        AnalyzerSpecTemplate(
            key="version-drift",
            name="Version drift",
            description="Detect repeated module names that have drifted structurally beyond datecode-only changes",
            analyzer_attr="analyze_version_drift",
            context_kwargs=("debug",),
            semantic_rule_source="version-drift",
        ),
        AnalyzerSpecTemplate(
            key="safety-paths",
            name="Safety paths",
            description="Cross-module tracing for shutdown and emergency signal propagation",
            analyzer_attr="analyze_safety_paths",
            context_kwargs=("debug", "unavailable_libraries", "analyzed_target_is_library"),
            semantic_mapping_kind="framework",
            semantic_rule_source="safety-paths",
        ),
        AnalyzerSpecTemplate(
            key="taint-paths",
            name="Taint paths",
            description="Cross-module taint tracing from external inputs to safety-critical sinks",
            analyzer_attr="analyze_taint_paths",
            context_kwargs=("debug", "unavailable_libraries", "analyzed_target_is_library"),
            semantic_mapping_kind="framework",
            semantic_rule_source="taint-paths",
        ),
        AnalyzerSpecTemplate(
            key="unsafe-defaults",
            name="Unsafe defaults",
            description="Explicit boolean defaults that can enable logic or bypass safeguards at startup",
            analyzer_attr="analyze_unsafe_defaults",
            semantic_mapping_kind="framework",
            semantic_rule_source="unsafe-defaults",
        ),
        AnalyzerSpecTemplate(
            key="dataflow",
            name="Lightweight dataflow",
            description="Constant-condition and unreachable-path detection across branches",
            analyzer_attr="analyze_dataflow",
            context_kwargs=("unavailable_libraries", "analyzed_target_is_library", "shared_artifacts"),
            semantic_mapping_kind="framework",
            semantic_rule_source="dataflow",
        ),
        AnalyzerSpecTemplate(
            key="state-inference",
            name="State inference",
            description="Infer stable boolean and numeric state and report contradictory control flow",
            analyzer_attr="analyze_state_inference",
            context_kwargs=("unavailable_libraries", "analyzed_target_is_library"),
        ),
    )


__all__ = ["AnalyzerSpecTemplate", "default_spec_templates"]
