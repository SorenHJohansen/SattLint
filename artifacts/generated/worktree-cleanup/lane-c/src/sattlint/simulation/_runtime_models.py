from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from ..analyzers.dataflow import ScalarValue

type JsonScalar = None | bool | int | float | str
type JsonValue = JsonScalar | Sequence[JsonValue] | Mapping[str, JsonValue]


@dataclass(frozen=True)
class ScanSnapshot:
    scan: int
    active_steps: list[str]
    state: dict[str, ScalarValue]
    transition_fires: list[str]

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "scan": self.scan,
            "active_steps": self.active_steps,
            "state": self.state,
            "transition_fires": self.transition_fires,
        }


@dataclass(frozen=True)
class SimulationResult:
    target: str
    mode: str
    steady_state_reached: bool
    cycle_detected: bool
    scan_budget_exhausted: bool
    outcome: str
    total_scans: int
    cycle_start_scan: int | None
    cycle_length: int | None
    snapshots: list[ScanSnapshot]

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "target": self.target,
            "mode": self.mode,
            "steady_state_reached": self.steady_state_reached,
            "cycle_detected": self.cycle_detected,
            "scan_budget_exhausted": self.scan_budget_exhausted,
            "outcome": self.outcome,
            "total_scans": self.total_scans,
            "cycle_start_scan": self.cycle_start_scan,
            "cycle_length": self.cycle_length,
            "snapshots": [snapshot.to_dict() for snapshot in self.snapshots],
        }

    def render_summary(self) -> str:
        if self.steady_state_reached:
            return f"steady state reached after {self.total_scans} scans"
        if self.cycle_detected:
            return (
                f"cycle detected after {self.total_scans} scans "
                f"(start={self.cycle_start_scan}, length={self.cycle_length})"
            )
        return f"scan budget exhausted after {self.total_scans} scans"
