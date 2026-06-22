"""Developer tooling for analysis and validation workflows."""

from __future__ import annotations

from importlib import import_module
from types import ModuleType
from typing import Any

_SUBMODULE_PREFIXES = (
    ".",
    ".ai.",
    ".audit.",
    ".sandbox.",
    ".shared.",
    ".structural.",
    ".pipeline.",
)

_EXPORT_PROVIDER_MODULES = (
    ".accuracy_metrics",
    ".artifact_registry",
    ".baselines",
    ".corpus",
    ".doc_gardener",
    ".fault_injection",
    ".observability",
    ".property_tests",
    ".review_tool",
    ".sandbox",
    ".sandbox.fuzzer",
    ".structural",
    ".audit",
)


def _is_missing_target(exc: ModuleNotFoundError, target_name: str) -> bool:
    return exc.name == target_name


def _load_submodule(name: str) -> ModuleType | None:
    for prefix in _SUBMODULE_PREFIXES:
        relative_name = f"{prefix}{name}" if prefix != "." else f".{name}"
        target_name = f"{__name__}{relative_name}"
        try:
            module = import_module(relative_name, __name__)
        except ModuleNotFoundError as exc:
            if _is_missing_target(exc, target_name):
                continue
            raise
        globals()[name] = module
        return module
    return None


def _load_reexport(name: str) -> Any:
    for provider_name in _EXPORT_PROVIDER_MODULES:
        provider = import_module(provider_name, __name__)
        if not hasattr(provider, name):
            continue
        value = getattr(provider, name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __getattr__(name: str) -> Any:
    module = _load_submodule(name)
    if module is not None:
        return module
    return _load_reexport(name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(_EXPORTED_NAMES))


_EXPORTED_NAMES = [
    "ACCURACY_METRICS_FILENAME",
    "ACCURACY_SCHEMA_KIND",
    "ACCURACY_SCHEMA_VERSION",
    "ANALYSIS_DIFF_SCHEMA_KIND",
    "ANALYSIS_DIFF_SCHEMA_VERSION",
    "AUDIT_ARTIFACTS",
    "CORPUS_RESULTS_FILENAME",
    "CORPUS_RESULTS_SCHEMA_KIND",
    "CORPUS_RESULTS_SCHEMA_VERSION",
    "FAULT_INJECTION_RESULTS_FILENAME",
    "FAULT_INJECTION_SCHEMA_KIND",
    "FAULT_INJECTION_SCHEMA_VERSION",
    "FUZZER_DEFAULT_TIMEOUT_SECONDS",
    "FUZZER_REPORT_FILENAME",
    "FUZZER_REPORT_SCHEMA_KIND",
    "FUZZER_REPORT_SCHEMA_VERSION",
    "PIPELINE_ARTIFACTS",
    "PROPERTY_TEST_RESULTS_FILENAME",
    "PROPERTY_TEST_SCHEMA_KIND",
    "PROPERTY_TEST_SCHEMA_VERSION",
    "VALIDATION_ANNOTATIONS_FILENAME",
    "AccuracyMetrics",
    "ArtifactDefinition",
    "CorpusCaseManifest",
    "CorpusEvaluation",
    "CorpusExpectation",
    "CorpusRunResult",
    "CorpusSuiteResult",
    "DocFinding",
    "FaultInjectionResults",
    "FaultInjector",
    "FaultRunRecord",
    "FaultSpec",
    "FuzzExecutionRecord",
    "FuzzTarget",
    "FuzzerReport",
    "PropertyCheckRecord",
    "PropertyTestResults",
    "ValidationAnnotation",
    "accuracy_metrics",
    "ai_chat_observability",
    "ai_gc",
    "ai_templates",
    "ai_work_map",
    "analyze_crashes",
    "artifact_readiness",
    "artifact_registry",
    "audit_core",
    "audit_core_discovery",
    "audit_orchestration",
    "baselines",
    "build_accuracy_metrics",
    "build_analysis_diff_report",
    "build_seed_corpus",
    "collect_all_metrics",
    "compare_audit_findings",
    "coordination_lock_state",
    "corpus",
    "coverage_reports",
    "derived_reports",
    "differential",
    "doc_gardener",
    "execute_corpus_case",
    "fault_injection",
    "finding_exports",
    "fuzzer",
    "generate_seeded_property_inputs",
    "impact_analyzer",
    "layer_linter",
    "leak_detection",
    "leak_detection_scan_paths",
    "ledger",
    "load_annotations",
    "load_finding_collection",
    "metrics_dashboard",
    "mutation_engine",
    "observability",
    "parser_fuzz_target",
    "parser_properties",
    "pipeline",
    "pipeline_artifacts",
    "pipeline_checks",
    "print_review",
    "production_summary",
    "profiler",
    "property_tests",
    "read_metrics",
    "refactoring",
    "release_smoke",
    "repo_audit",
    "repo_audit_cli",
    "repo_audit_cli_reporting",
    "repo_audit_compat",
    "repo_audit_entrypoints",
    "repo_audit_runs",
    "repo_audit_shared",
    "review_tool",
    "run_corpus_case",
    "run_corpus_suite",
    "run_fault_injection_campaign",
    "run_full_review",
    "run_fuzz_target",
    "run_parser_fuzzer",
    "run_property_tests",
    "run_scan",
    "source_diff_report",
    "structural_reports",
    "trace_reports",
    "write_accuracy_metrics",
    "write_fault_injection_results",
    "write_fuzzer_report",
    "write_metrics",
    "write_property_test_results",
]


__all__ = _EXPORTED_NAMES
