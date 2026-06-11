"""Lightweight mutation engine for SattLine analyzer effectiveness testing."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from dataclasses import dataclass, field, replace
from pathlib import Path

from sattline_parser import parse_source_text as parser_core_parse_source_text
from sattline_parser.models.ast_model import (
    BasePicture,
)

from ..contracts import FindingCollection

MutationRecordValue = str | bool | None

MUTATION_RESULTS_FILENAME = "mutation_results.json"
MUTATION_SCHEMA_KIND = "sattlint.mutation_results"
MUTATION_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class MutationRecord:
    mutation_kind: str
    location: str
    original: str
    mutated: str
    killed: bool
    killing_analyzer: str | None = None
    killing_rule_id: str | None = None


def _empty_mutation_records() -> list[MutationRecord]:
    return []


@dataclass
class MutationResults:
    records: list[MutationRecord] = field(default_factory=_empty_mutation_records)

    def to_dict(self) -> dict[str, object]:
        records: list[dict[str, MutationRecordValue]] = [
            {
                "mutation_kind": record.mutation_kind,
                "location": record.location,
                "original": record.original,
                "mutated": record.mutated,
                "killed": record.killed,
                "killing_analyzer": record.killing_analyzer,
                "killing_rule_id": record.killing_rule_id,
            }
            for record in self.records
        ]
        return {
            "kind": MUTATION_SCHEMA_KIND,
            "schema_version": MUTATION_SCHEMA_VERSION,
            "summary": {
                "total_mutations": len(self.records),
                "killed": sum(1 for r in self.records if r.killed),
                "alive": sum(1 for r in self.records if not r.killed),
            },
            "records": records,
        }

    @property
    def killed_count(self) -> int:
        return sum(1 for r in self.records if r.killed)

    @property
    def alive_count(self) -> int:
        return sum(1 for r in self.records if not r.killed)


def _mutate_literal(source: str, literal_type: str = "bool") -> Iterable[str]:
    """Yield mutated source variants by flipping literals."""
    lines = source.splitlines(keepends=True)
    for i, line in enumerate(lines):
        stripped = line.strip()
        if literal_type == "bool":
            if stripped == "TRUE":
                mutated = source.replace("TRUE", "FALSE", 1)
                if mutated != source:
                    yield mutated
            elif stripped == "FALSE":
                mutated = source.replace("FALSE", "TRUE", 1)
                if mutated != source:
                    yield mutated
        elif literal_type == "numeric":

            def _flip_numeric(match: re.Match[str]) -> str:
                value: str = match.group(0)
                try:
                    return str(int(value) + 1)
                except ValueError:
                    try:
                        return str(float(value) + 1.0)
                    except ValueError:
                        return value

            new_line = re.sub(r"\b\d+(\.\d+)?\b", _flip_numeric, line)
            if new_line != line:
                mutated_lines = list(lines)
                mutated_lines[i] = new_line
                yield "".join(mutated_lines)


def run_mutation_analysis(
    source_file: Path,
    finding_collection: FindingCollection,
    *,
    mutation_kinds: tuple[str, ...] = ("bool-flip", "numeric-bump"),
) -> MutationResults:
    """Run mutation operators and check if existing findings detect the mutations."""
    source = source_file.read_text(encoding="utf-8", errors="ignore")
    results = MutationResults()

    for kind in mutation_kinds:
        mutated_sources = _mutate_literal(source, literal_type="bool" if "bool" in kind else "numeric")
        for mutated in mutated_sources:
            bp: BasePicture | None
            try:
                bp = parser_core_parse_source_text(mutated)
            except Exception:  # noqa: BLE001
                bp = None
            if bp is None:
                continue

            location = f"{source_file.as_posix()}"
            record = MutationRecord(
                mutation_kind=kind,
                location=location,
                original=source[:50],
                mutated=mutated[:50],
                killed=False,
            )

            for finding in finding_collection.findings:
                if finding.location.path and finding.location.path in location:
                    record = replace(
                        record, killed=True, killing_analyzer=finding.analyzer, killing_rule_id=finding.rule_id
                    )
                    break

            results.records.append(record)

    return results


__all__ = [
    "MUTATION_RESULTS_FILENAME",
    "MutationRecord",
    "MutationResults",
    "run_mutation_analysis",
    "write_mutation_results",
]


def write_mutation_results(output_dir: Path, results: MutationResults) -> None:
    """Write mutation_results.json to the pipeline output directory."""
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / MUTATION_RESULTS_FILENAME).write_text(
        json.dumps(results.to_dict(), indent=2, sort_keys=True),
        encoding="utf-8",
    )
