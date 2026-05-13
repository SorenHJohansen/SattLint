"""Analyzer spec factory extracted from the analyzer registry."""

from __future__ import annotations

from .framework import AnalysisContext, AnalyzerSpec


def build_default_analyzers(*, semantic_layer_analyzer_key: str) -> list[AnalyzerSpec]:
    from . import registry as registry_module

    def _run_variables(context: AnalysisContext):
        return registry_module.analyze_variables(
            context.base_picture,
            debug=context.debug,
            unavailable_libraries=context.unavailable_libraries,
            analyzed_target_is_library=context.target_is_library,
            config=context.config,
        )

    def _run_sattline_semantics(context: AnalysisContext):
        return registry_module.analyze_sattline_semantics(
            context.base_picture,
            debug=context.debug,
            unavailable_libraries=context.unavailable_libraries,
            analyzed_target_is_library=context.target_is_library,
            sfc_mutually_exclusive_steps=registry_module.get_configured_mutually_exclusive_step_sets(context.config),
            sfc_step_contracts=registry_module.get_configured_step_contracts(context.config),
            config=context.config,
        )

    def _run_mms_interface(context: AnalysisContext):
        return registry_module.analyze_mms_interface_variables(
            context.base_picture,
            debug=context.debug,
            config=context.config,
        )

    def _run_sfc_checks(context: AnalysisContext):
        return registry_module.analyze_sfc(
            context.base_picture,
            mutually_exclusive_steps=registry_module.get_configured_mutually_exclusive_step_sets(context.config),
            step_contracts=registry_module.get_configured_step_contracts(context.config),
        )

    def _run_shadowing(context: AnalysisContext):
        return registry_module.analyze_shadowing(
            context.base_picture,
            debug=context.debug,
            unavailable_libraries=context.unavailable_libraries,
        )

    def _run_spec_compliance(context: AnalysisContext):
        return registry_module.analyze_spec_compliance(
            context.base_picture,
            debug=context.debug,
            unavailable_libraries=context.unavailable_libraries,
        )

    def _run_loop_output_refactor(context: AnalysisContext):
        return registry_module.analyze_loop_output_refactor(context.base_picture)

    def _run_alarm_integrity(context: AnalysisContext):
        return registry_module.analyze_alarm_integrity(
            context.base_picture,
            debug=context.debug,
            unavailable_libraries=context.unavailable_libraries,
        )

    def _run_initial_values(context: AnalysisContext):
        return registry_module.analyze_initial_values(
            context.base_picture,
            debug=context.debug,
            unavailable_libraries=context.unavailable_libraries,
        )

    def _run_interface_contracts(context: AnalysisContext):
        return registry_module.analyze_interface_contracts(
            context.base_picture,
            debug=context.debug,
            unavailable_libraries=context.unavailable_libraries,
            analyzed_target_is_library=context.target_is_library,
        )

    def _run_powerup(context: AnalysisContext):
        return registry_module.analyze_powerup(
            context.base_picture,
            debug=context.debug,
            unavailable_libraries=context.unavailable_libraries,
        )

    def _run_naming_consistency(context: AnalysisContext):
        return registry_module.analyze_naming_consistency(
            context.base_picture,
            rules=registry_module.get_configured_naming_rules(context.config),
        )

    def _run_cyclomatic_complexity(context: AnalysisContext):
        return registry_module.analyze_cyclomatic_complexity(context.base_picture)

    def _run_parameter_drift(context: AnalysisContext):
        return registry_module.analyze_parameter_drift(
            context.base_picture,
            unavailable_libraries=context.unavailable_libraries,
        )

    def _run_signal_lifecycle(context: AnalysisContext):
        return registry_module.analyze_signal_lifecycle(context.base_picture)

    def _run_loop_stability(context: AnalysisContext):
        return registry_module.analyze_loop_stability(context.base_picture)

    def _run_fault_handling(context: AnalysisContext):
        return registry_module.analyze_fault_handling(context.base_picture)

    def _run_numeric_constraints(context: AnalysisContext):
        return registry_module.analyze_numeric_constraints(context.base_picture)

    def _run_data_dependency(context: AnalysisContext):
        return registry_module.analyze_data_dependency(
            context.base_picture,
            unavailable_libraries=context.unavailable_libraries,
            analyzed_target_is_library=context.target_is_library,
        )

    def _run_config_drift(context: AnalysisContext):
        return registry_module.analyze_config_drift(
            context.base_picture,
            unavailable_libraries=context.unavailable_libraries,
        )

    def _run_scan_loop_resource_usage(context: AnalysisContext):
        return registry_module.analyze_scan_loop_resource_usage(context.base_picture)

    def _run_resource_usage(context: AnalysisContext):
        return registry_module.analyze_resource_usage(
            context.base_picture,
            unavailable_libraries=context.unavailable_libraries,
            analyzed_target_is_library=context.target_is_library,
        )

    def _run_scan_concurrency(context: AnalysisContext):
        return registry_module.analyze_scan_concurrency(
            context.base_picture,
            config=context.config,
        )

    def _run_timing(context: AnalysisContext):
        return registry_module.analyze_timing(
            context.base_picture,
            unavailable_libraries=context.unavailable_libraries,
            analyzed_target_is_library=context.target_is_library,
        )

    def _run_version_drift(context: AnalysisContext):
        return registry_module.analyze_version_drift(
            context.base_picture,
            debug=context.debug,
        )

    def _run_safety_paths(context: AnalysisContext):
        return registry_module.analyze_safety_paths(
            context.base_picture,
            debug=context.debug,
            unavailable_libraries=context.unavailable_libraries,
            analyzed_target_is_library=context.target_is_library,
        )

    def _run_taint_paths(context: AnalysisContext):
        return registry_module.analyze_taint_paths(
            context.base_picture,
            debug=context.debug,
            unavailable_libraries=context.unavailable_libraries,
            analyzed_target_is_library=context.target_is_library,
        )

    def _run_unsafe_defaults(context: AnalysisContext):
        return registry_module.analyze_unsafe_defaults(context.base_picture)

    def _run_dataflow(context: AnalysisContext):
        return registry_module.analyze_dataflow(
            context.base_picture,
            unavailable_libraries=context.unavailable_libraries,
            analyzed_target_is_library=context.target_is_library,
        )

    def _run_state_inference(context: AnalysisContext):
        return registry_module.analyze_state_inference(
            context.base_picture,
            unavailable_libraries=context.unavailable_libraries,
            analyzed_target_is_library=context.target_is_library,
        )

    def _run_comment_code(context: AnalysisContext):
        return registry_module.analyze_comment_code(context)

    return [
        AnalyzerSpec(
            key=semantic_layer_analyzer_key,
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
            key="interface_contracts",
            name="Interface contracts",
            description="Detect missing required parameter mappings, unknown targets, and cross-module contract mismatches",
            run=_run_interface_contracts,
            enabled=True,
        ),
        AnalyzerSpec(
            key="powerup",
            name="Power-up",
            description="Detect startup-value gaps and unsafe startup defaults that affect power-up behavior",
            run=_run_powerup,
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
            key="signal_lifecycle",
            name="Signal lifecycle",
            description="Track reads before writes and signals that are written but never consumed",
            run=_run_signal_lifecycle,
            enabled=True,
        ),
        AnalyzerSpec(
            key="loop_stability",
            name="Loop stability",
            description="Detect contradictory literal setpoint writes that can destabilize scan-loop behavior",
            run=_run_loop_stability,
            enabled=True,
        ),
        AnalyzerSpec(
            key="fault_handling",
            name="Fault handling",
            description="Detect raised alarm or fault paths that are never cleared or never consumed",
            run=_run_fault_handling,
            enabled=True,
        ),
        AnalyzerSpec(
            key="numeric_constraints",
            name="Numeric constraints",
            description="Validate literal assignments against visible Min/Max style bounds",
            run=_run_numeric_constraints,
            enabled=True,
        ),
        AnalyzerSpec(
            key="data_dependency",
            name="Data dependency",
            description="Report deterministic dependency chains and initialization-order hazards",
            run=_run_data_dependency,
            enabled=True,
        ),
        AnalyzerSpec(
            key="config_drift",
            name="Config drift",
            description="Detect moduletype instances whose visible configuration signatures drift across the analyzed target",
            run=_run_config_drift,
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
            key="resource_usage",
            name="Resource usage",
            description="Detect unreleased or prematurely released resource handles and scan-loop resource hazards",
            run=_run_resource_usage,
            enabled=True,
        ),
        AnalyzerSpec(
            key="scan_concurrency",
            name="Scan concurrency",
            description="Detect parallel scan or sequence branches that write the same variable without arbitration",
            run=_run_scan_concurrency,
            enabled=True,
        ),
        AnalyzerSpec(
            key="timing",
            name="Timing",
            description="Detect scan-cycle temporal hazards and non precision-scan-safe resource usage",
            run=_run_timing,
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
        AnalyzerSpec(
            key="state_inference",
            name="State inference",
            description="Infer stable boolean and numeric state and report contradictory control flow",
            run=_run_state_inference,
            enabled=True,
        ),
    ]


__all__ = ["AnalyzerSpec", "build_default_analyzers"]
