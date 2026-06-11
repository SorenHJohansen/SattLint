"""Deterministic fault injection scaffolding for robustness tests."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

FAULT_INJECTION_RESULTS_FILENAME = "fault_injection_results.json"
FAULT_INJECTION_SCHEMA_KIND = "sattlint.fault_injection_results"
FAULT_INJECTION_SCHEMA_VERSION = 1

_EXCEPTION_TYPES: dict[str, type[Exception]] = {
    "io": OSError,
    "runtime": RuntimeError,
    "syntax": SyntaxError,
    "value": ValueError,
}


def _checkpoint_count_map() -> dict[str, int]:
    return {}


def _triggered_fault_id_list() -> list[str]:
    return []


def _fault_run_record_list() -> list[FaultRunRecord]:
    return []


@dataclass(frozen=True)
class FaultSpec:
    """A deterministic fault to inject at a named checkpoint."""

    checkpoint: str
    fault_id: str
    exception_type: str = "runtime"
    message: str = "Injected fault"
    trigger_count: int = 1

    def build_exception(self) -> Exception:
        exception_cls = _EXCEPTION_TYPES.get(self.exception_type.casefold(), RuntimeError)
        return exception_cls(self.message)

    def to_dict(self) -> dict[str, Any]:
        return {
            "checkpoint": self.checkpoint,
            "fault_id": self.fault_id,
            "exception_type": self.exception_type,
            "message": self.message,
            "trigger_count": self.trigger_count,
        }


@dataclass
class FaultInjector:
    """Inject configured faults when checkpoints are reached."""

    specs: tuple[FaultSpec, ...] = ()
    checkpoint_counts: dict[str, int] = field(default_factory=_checkpoint_count_map)
    triggered_fault_ids: list[str] = field(default_factory=_triggered_fault_id_list)

    def checkpoint(self, checkpoint: str) -> None:
        current_count = self.checkpoint_counts.get(checkpoint, 0) + 1
        self.checkpoint_counts[checkpoint] = current_count
        for spec in self.specs:
            if spec.checkpoint != checkpoint:
                continue
            if spec.trigger_count != current_count:
                continue
            self.triggered_fault_ids.append(spec.fault_id)
            raise spec.build_exception()


@dataclass(frozen=True)
class FaultRunRecord:
    """The outcome of one baseline or injected test case run."""

    case_id: str
    status: str
    fault_id: str | None = None
    checkpoint: str | None = None
    exception_type: str | None = None
    message: str | None = None
    checkpoint_counts: Mapping[str, int] = field(default_factory=_checkpoint_count_map)

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "status": self.status,
            "fault_id": self.fault_id,
            "checkpoint": self.checkpoint,
            "exception_type": self.exception_type,
            "message": self.message,
            "checkpoint_counts": dict(self.checkpoint_counts),
        }


@dataclass
class FaultInjectionResults:
    """Collection of fault injection outcomes with a machine-readable summary."""

    records: list[FaultRunRecord] = field(default_factory=_fault_run_record_list)

    def to_dict(self) -> dict[str, Any]:
        status_counts: dict[str, int] = {}
        for record in self.records:
            status_counts[record.status] = status_counts.get(record.status, 0) + 1
        return {
            "kind": FAULT_INJECTION_SCHEMA_KIND,
            "schema_version": FAULT_INJECTION_SCHEMA_VERSION,
            "summary": {
                "total_runs": len(self.records),
                "status_counts": status_counts,
            },
            "records": [record.to_dict() for record in self.records],
        }


def run_fault_injection_campaign(
    case_id: str,
    case_fn: Callable[[FaultInjector], Any],
    *,
    fault_specs: tuple[FaultSpec, ...] = (),
    include_baseline: bool = True,
) -> FaultInjectionResults:
    """Run one test case with a baseline and isolated injected faults."""

    results = FaultInjectionResults()

    if include_baseline:
        baseline_injector = FaultInjector()
        try:
            case_fn(baseline_injector)
        except Exception as exc:  # pragma: no cover - exercised through the same branch below  # noqa: BLE001
            results.records.append(
                FaultRunRecord(
                    case_id=case_id,
                    status="baseline-error",
                    exception_type=type(exc).__name__,
                    message=str(exc),
                    checkpoint_counts=dict(baseline_injector.checkpoint_counts),
                )
            )
        else:
            results.records.append(
                FaultRunRecord(
                    case_id=case_id,
                    status="baseline-pass",
                    checkpoint_counts=dict(baseline_injector.checkpoint_counts),
                )
            )

    for spec in fault_specs:
        injector = FaultInjector(specs=(spec,))
        try:
            case_fn(injector)
        except Exception as exc:  # noqa: BLE001
            status = "fault-injected" if spec.fault_id in injector.triggered_fault_ids else "unexpected-error"
            checkpoint = spec.checkpoint if spec.fault_id in injector.triggered_fault_ids else None
            results.records.append(
                FaultRunRecord(
                    case_id=case_id,
                    status=status,
                    fault_id=spec.fault_id,
                    checkpoint=checkpoint,
                    exception_type=type(exc).__name__,
                    message=str(exc),
                    checkpoint_counts=dict(injector.checkpoint_counts),
                )
            )
        else:
            status = "missed-fault" if spec.fault_id not in injector.triggered_fault_ids else "fault-injected"
            results.records.append(
                FaultRunRecord(
                    case_id=case_id,
                    status=status,
                    fault_id=spec.fault_id,
                    checkpoint=spec.checkpoint,
                    checkpoint_counts=dict(injector.checkpoint_counts),
                )
            )

    return results


def write_fault_injection_results(output_dir: Path, results: FaultInjectionResults) -> Path:
    """Write a machine-readable fault injection report."""

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / FAULT_INJECTION_RESULTS_FILENAME
    output_path.write_text(json.dumps(results.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
    return output_path


__all__ = [
    "FAULT_INJECTION_RESULTS_FILENAME",
    "FAULT_INJECTION_SCHEMA_KIND",
    "FAULT_INJECTION_SCHEMA_VERSION",
    "FaultInjectionResults",
    "FaultInjector",
    "FaultRunRecord",
    "FaultSpec",
    "run_fault_injection_campaign",
    "write_fault_injection_results",
]
