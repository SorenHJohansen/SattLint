"""Developer tooling for analysis and validation workflows."""

import importlib
import typing

from .accuracy_metrics import (
    ACCURACY_METRICS_FILENAME,
    ACCURACY_SCHEMA_KIND,
    ACCURACY_SCHEMA_VERSION,
    VALIDATION_ANNOTATIONS_FILENAME,
    AccuracyMetrics,
    ValidationAnnotation,
    build_accuracy_metrics,
    load_annotations,
    write_accuracy_metrics,
)
from .artifact_registry import AUDIT_ARTIFACTS, PIPELINE_ARTIFACTS, ArtifactDefinition
from .baselines import (
    ANALYSIS_DIFF_SCHEMA_KIND,
    ANALYSIS_DIFF_SCHEMA_VERSION,
    build_analysis_diff_report,
    load_finding_collection,
)
from .corpus import (
    CORPUS_RESULTS_FILENAME,
    CORPUS_RESULTS_SCHEMA_KIND,
    CORPUS_RESULTS_SCHEMA_VERSION,
    CorpusCaseManifest,
    CorpusEvaluation,
    CorpusExpectation,
    CorpusRunResult,
    CorpusSuiteResult,
    execute_corpus_case,
    run_corpus_case,
    run_corpus_suite,
)
from .fault_injection import (
    FAULT_INJECTION_RESULTS_FILENAME,
    FAULT_INJECTION_SCHEMA_KIND,
    FAULT_INJECTION_SCHEMA_VERSION,
    FaultInjectionResults,
    FaultInjector,
    FaultRunRecord,
    FaultSpec,
    run_fault_injection_campaign,
    write_fault_injection_results,
)
from .fuzzer import (
    DEFAULT_TIMEOUT_SECONDS as FUZZER_DEFAULT_TIMEOUT_SECONDS,
)
from .fuzzer import (
    FUZZER_REPORT_FILENAME,
    FUZZER_REPORT_SCHEMA_KIND,
    FUZZER_REPORT_SCHEMA_VERSION,
    FuzzerReport,
    FuzzExecutionRecord,
    FuzzTarget,
    analyze_crashes,
    build_seed_corpus,
    parser_fuzz_target,
    run_fuzz_target,
    run_parser_fuzzer,
    write_fuzzer_report,
)
from .observability import collect_all_metrics, read_metrics, write_metrics
from .property_tests import (
    PROPERTY_TEST_RESULTS_FILENAME,
    PROPERTY_TEST_SCHEMA_KIND,
    PROPERTY_TEST_SCHEMA_VERSION,
    PropertyCheckRecord,
    PropertyTestResults,
    generate_seeded_property_inputs,
    run_property_tests,
    write_property_test_results,
)

if typing.TYPE_CHECKING:
    from .doc_gardener import DocFinding, run_scan
    from .review_tool import print_review, run_full_review

DocFinding: object
run_scan: object
print_review: object
run_full_review: object


def __getattr__(name: str):
    if name in {"DocFinding", "run_scan"}:
        return getattr(importlib.import_module("sattlint.devtools.doc_gardener"), name)
    if name in {"print_review", "run_full_review"}:
        return getattr(importlib.import_module("sattlint.devtools.review_tool"), name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
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
    "analyze_crashes",
    "build_accuracy_metrics",
    "build_analysis_diff_report",
    "build_seed_corpus",
    "collect_all_metrics",
    "execute_corpus_case",
    "generate_seeded_property_inputs",
    "load_annotations",
    "load_finding_collection",
    "parser_fuzz_target",
    "print_review",
    "read_metrics",
    "run_corpus_case",
    "run_corpus_suite",
    "run_fault_injection_campaign",
    "run_full_review",
    "run_fuzz_target",
    "run_parser_fuzzer",
    "run_property_tests",
    "run_scan",
    "write_accuracy_metrics",
    "write_fault_injection_results",
    "write_fuzzer_report",
    "write_metrics",
    "write_property_test_results",
]
