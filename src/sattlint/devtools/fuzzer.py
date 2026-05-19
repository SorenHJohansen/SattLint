"""Parser fuzz helpers and reusable fuzz targets."""

from __future__ import annotations

import concurrent.futures
import json
import time
from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sattline_parser.api import parse_source_text
from sattline_parser.fuzz_harness import (
    FuzzResult,
    TimeoutError,
    assert_no_crashes,
    assert_no_timeouts,
    collect_corpus_inputs,
    generate_random_text,
    is_expected_parse_error,
    run_corpus_regression,
    run_random_fuzz,
)

DEFAULT_TIMEOUT_SECONDS = 2.0
FUZZER_REPORT_FILENAME = "fuzzer_report.json"
FUZZER_REPORT_SCHEMA_KIND = "sattlint.fuzzer_report"
FUZZER_REPORT_SCHEMA_VERSION = 1

FUZZ_RESULTS_FILENAME = "fuzz_results.json"
FUZZ_RESULTS_SCHEMA_KIND = "sattlint.fuzz_results"
FUZZ_RESULTS_SCHEMA_VERSION = 1


def _fuzz_result_list() -> list[FuzzResult]:
    return []


def _fuzz_execution_record_list() -> list[FuzzExecutionRecord]:
    return []


def analyze_fuzz_crashes(results: list[FuzzResult]) -> list[dict[str, Any]]:
    """Return unexpected crash records from a fuzz run."""
    crashes: list[dict[str, Any]] = []
    for result in results:
        error = result.error
        if error is None or isinstance(error, TimeoutError) or is_expected_parse_error(error):
            continue
        crashes.append(result.to_dict())
    return crashes


@dataclass
class FuzzCampaignResults:
    """Machine-readable summary of a corpus plus random fuzz campaign."""

    results: list[FuzzResult] = field(default_factory=_fuzz_result_list)

    @property
    def crash_reports(self) -> list[dict[str, Any]]:
        return analyze_fuzz_crashes(self.results)

    def to_dict(self) -> dict[str, Any]:
        success_count = sum(1 for result in self.results if result.success)
        timeout_count = sum(1 for result in self.results if isinstance(result.error, TimeoutError))
        expected_parse_error_count = sum(
            1
            for result in self.results
            if result.error is not None
            and not isinstance(result.error, TimeoutError)
            and is_expected_parse_error(result.error)
        )
        return {
            "kind": FUZZ_RESULTS_SCHEMA_KIND,
            "schema_version": FUZZ_RESULTS_SCHEMA_VERSION,
            "summary": {
                "total_runs": len(self.results),
                "success_count": success_count,
                "timeout_count": timeout_count,
                "expected_parse_error_count": expected_parse_error_count,
                "unexpected_crash_count": len(self.crash_reports),
            },
            "crashes": self.crash_reports,
            "results": [result.to_dict() for result in self.results],
        }


def run_fuzz_campaign(
    *,
    corpus_max_files: int | None = 10,
    random_rounds: int = 10,
    text_length: int = 100,
    timeout: float = 5.0,
    seed: int = 42,
    assert_stable: bool = False,
) -> FuzzCampaignResults:
    """Run a combined corpus and random fuzz campaign."""
    results = run_corpus_regression(timeout=timeout, max_files=corpus_max_files)
    if random_rounds > 0:
        results.extend(
            run_random_fuzz(
                rounds=random_rounds,
                text_length=text_length,
                timeout=timeout,
                seed=seed,
            )
        )

    if assert_stable:
        assert_no_crashes(results)
        assert_no_timeouts(results)

    return FuzzCampaignResults(results=results)


def write_fuzz_results(output_dir: Path, results: FuzzCampaignResults) -> Path:
    """Write a machine-readable fuzz campaign report."""
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / FUZZ_RESULTS_FILENAME
    output_path.write_text(json.dumps(results.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
    return output_path


@dataclass(frozen=True)
class FuzzTarget:
    target_id: str
    runner: Callable[[str], Any]


@dataclass(frozen=True)
class FuzzExecutionRecord:
    target_id: str
    input_desc: str
    status: str
    duration_ms: float
    error_type: str | None = None
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_id": self.target_id,
            "input_desc": self.input_desc,
            "status": self.status,
            "duration_ms": self.duration_ms,
            "error_type": self.error_type,
            "error_message": self.error_message,
        }


@dataclass
class FuzzerReport:
    records: list[FuzzExecutionRecord] = field(default_factory=_fuzz_execution_record_list)

    def to_dict(self) -> dict[str, Any]:
        status_counts = Counter(record.status for record in self.records)
        return {
            "kind": FUZZER_REPORT_SCHEMA_KIND,
            "schema_version": FUZZER_REPORT_SCHEMA_VERSION,
            "summary": {
                "total_runs": len(self.records),
                "status_counts": dict(sorted(status_counts.items())),
                "unexpected_crash_count": status_counts.get("unexpected-crash", 0),
            },
            "records": [record.to_dict() for record in self.records],
        }


def parser_fuzz_target(source: str) -> Any:
    return parse_source_text(source)


def build_seed_corpus(
    *,
    max_files: int = 10,
    include_invalid: bool = True,
    include_edge_cases: bool = True,
) -> list[tuple[str, str]]:
    return collect_corpus_inputs(
        include_valid=True,
        include_invalid=include_invalid,
        include_edge_cases=include_edge_cases,
        max_files=max_files,
    )


def _run_with_timeout(runner: Callable[[str], Any], source: str, timeout: float) -> tuple[Exception | None, float]:
    start = time.perf_counter()
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(runner, source)
            try:
                future.result(timeout=timeout)
                return None, (time.perf_counter() - start) * 1000
            except concurrent.futures.TimeoutError:
                duration_ms = (time.perf_counter() - start) * 1000
                return TimeoutError(f"Fuzz target timed out after {timeout}s"), duration_ms
    except Exception as exc:
        return exc, (time.perf_counter() - start) * 1000


def _record_for_error(
    target_id: str,
    input_desc: str,
    error: Exception | None,
    duration_ms: float,
) -> FuzzExecutionRecord:
    if error is None:
        return FuzzExecutionRecord(
            target_id=target_id,
            input_desc=input_desc,
            status="success",
            duration_ms=duration_ms,
        )
    if isinstance(error, TimeoutError):
        status = "timeout"
    elif is_expected_parse_error(error):
        status = "expected-parse-error"
    else:
        status = "unexpected-crash"
    return FuzzExecutionRecord(
        target_id=target_id,
        input_desc=input_desc,
        status=status,
        duration_ms=duration_ms,
        error_type=type(error).__name__,
        error_message=str(error),
    )


def run_fuzz_target(
    target: FuzzTarget,
    *,
    corpus_inputs: Iterable[tuple[str, str]] | None = None,
    random_rounds: int = 10,
    text_length: int = 120,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    seed: int = 101,
) -> FuzzerReport:
    report = FuzzerReport()
    resolved_corpus = list(build_seed_corpus() if corpus_inputs is None else corpus_inputs)

    for input_desc, source in resolved_corpus:
        error, duration_ms = _run_with_timeout(target.runner, source, timeout)
        report.records.append(_record_for_error(target.target_id, f"corpus:{input_desc}", error, duration_ms))

    for index in range(random_rounds):
        source = generate_random_text(length=text_length, seed=seed + index)
        error, duration_ms = _run_with_timeout(target.runner, source, timeout)
        report.records.append(
            _record_for_error(target.target_id, f"random:{index}(seed={seed + index})", error, duration_ms)
        )

    return report


def analyze_crashes(report: FuzzerReport) -> list[FuzzExecutionRecord]:
    return [record for record in report.records if record.status == "unexpected-crash"]


def run_parser_fuzzer(
    *,
    corpus_max_files: int = 10,
    random_rounds: int = 10,
    text_length: int = 120,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    seed: int = 101,
) -> FuzzerReport:
    return run_fuzz_target(
        FuzzTarget(target_id="parser", runner=parser_fuzz_target),
        corpus_inputs=build_seed_corpus(max_files=corpus_max_files),
        random_rounds=random_rounds,
        text_length=text_length,
        timeout=timeout,
        seed=seed,
    )


def write_fuzzer_report(output_dir: Path, report: FuzzerReport) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / FUZZER_REPORT_FILENAME
    output_path.write_text(json.dumps(report.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
    return output_path


__all__ = [
    "DEFAULT_TIMEOUT_SECONDS",
    "FUZZER_REPORT_FILENAME",
    "FUZZER_REPORT_SCHEMA_KIND",
    "FUZZER_REPORT_SCHEMA_VERSION",
    "FUZZ_RESULTS_FILENAME",
    "FUZZ_RESULTS_SCHEMA_KIND",
    "FUZZ_RESULTS_SCHEMA_VERSION",
    "FuzzCampaignResults",
    "FuzzExecutionRecord",
    "FuzzTarget",
    "FuzzerReport",
    "analyze_crashes",
    "analyze_fuzz_crashes",
    "build_seed_corpus",
    "parser_fuzz_target",
    "run_fuzz_campaign",
    "run_fuzz_target",
    "run_parser_fuzzer",
    "write_fuzz_results",
    "write_fuzzer_report",
]
