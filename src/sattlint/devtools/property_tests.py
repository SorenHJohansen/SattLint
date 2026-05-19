"""Deterministic property-style parser robustness checks."""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sattline_parser.fuzz_harness import (
    collect_corpus_inputs,
    fuzz_parse_text,
    generate_random_text,
    is_expected_parse_error,
)

PROPERTY_TEST_RESULTS_FILENAME = "property_test_results.json"
PROPERTY_TEST_SCHEMA_KIND = "sattlint.property_test_results"
PROPERTY_TEST_SCHEMA_VERSION = 1


def _property_check_record_list() -> list[PropertyCheckRecord]:
    return []


@dataclass(frozen=True)
class PropertyCheckRecord:
    property_id: str
    input_desc: str
    passed: bool
    message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "property_id": self.property_id,
            "input_desc": self.input_desc,
            "passed": self.passed,
            "message": self.message,
        }


@dataclass
class PropertyTestResults:
    records: list[PropertyCheckRecord] = field(default_factory=_property_check_record_list)

    def to_dict(self) -> dict[str, Any]:
        status_counts = Counter("passed" if record.passed else "failed" for record in self.records)
        property_counts = Counter(record.property_id for record in self.records)
        return {
            "kind": PROPERTY_TEST_SCHEMA_KIND,
            "schema_version": PROPERTY_TEST_SCHEMA_VERSION,
            "summary": {
                "total_checks": len(self.records),
                "passed": status_counts.get("passed", 0),
                "failed": status_counts.get("failed", 0),
                "properties": dict(sorted(property_counts.items())),
            },
            "records": [record.to_dict() for record in self.records],
        }


def generate_seeded_property_inputs(
    seeds: Iterable[int],
    *,
    text_length: int = 120,
) -> list[tuple[int, str]]:
    return [(seed, generate_random_text(length=text_length, seed=seed)) for seed in seeds]


def run_property_tests(
    *,
    seeds: Iterable[int] = (11, 23, 37),
    text_length: int = 120,
    timeout: float = 2.0,
    max_corpus_files: int = 5,
) -> PropertyTestResults:
    results = PropertyTestResults()

    for seed in seeds:
        left = generate_random_text(length=text_length, seed=seed)
        right = generate_random_text(length=text_length, seed=seed)
        results.records.append(
            PropertyCheckRecord(
                property_id="seeded-generation-is-deterministic",
                input_desc=f"seed:{seed}",
                passed=left == right,
                message=None if left == right else "Seeded random text generation drifted for the same seed.",
            )
        )

    valid_inputs = collect_corpus_inputs(
        include_valid=True,
        include_invalid=False,
        include_edge_cases=False,
        max_files=max_corpus_files,
    )
    for file_path, content in valid_inputs:
        parse_result = fuzz_parse_text(content, input_desc=file_path, timeout=timeout)
        results.records.append(
            PropertyCheckRecord(
                property_id="valid-corpus-parses",
                input_desc=file_path,
                passed=parse_result.success,
                message=None if parse_result.success else f"Valid corpus case failed: {parse_result.error}",
            )
        )

    for seed, source in generate_seeded_property_inputs(seeds, text_length=text_length):
        parse_result = fuzz_parse_text(source, input_desc=f"seed:{seed}", timeout=timeout)
        passed = parse_result.error is None or is_expected_parse_error(parse_result.error)
        results.records.append(
            PropertyCheckRecord(
                property_id="random-inputs-fail-gracefully",
                input_desc=f"seed:{seed}",
                passed=passed,
                message=None if passed else f"Unexpected parser crash: {parse_result.error}",
            )
        )

    return results


def write_property_test_results(output_dir: Path, results: PropertyTestResults) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / PROPERTY_TEST_RESULTS_FILENAME
    output_path.write_text(json.dumps(results.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
    return output_path


__all__ = [
    "PROPERTY_TEST_RESULTS_FILENAME",
    "PROPERTY_TEST_SCHEMA_KIND",
    "PROPERTY_TEST_SCHEMA_VERSION",
    "PropertyCheckRecord",
    "PropertyTestResults",
    "generate_seeded_property_inputs",
    "run_property_tests",
    "write_property_test_results",
]
