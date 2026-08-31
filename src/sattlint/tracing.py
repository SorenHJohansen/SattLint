"""Internal tracing helpers used by the retained analyzer engine.

Only the symbols consumed by the retained analyzers are kept here; the trace
report and command surface has been removed.
"""

from __future__ import annotations

import time
from collections.abc import Sequence as SequenceABC
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sattline_parser.models.ast_model import (
    BasePicture,
    FrameModule,
    ModuleTypeInstance,
    SingleModule,
)

from .analyzers.sfc import collect_sfc_reachability_findings


def _empty_trace_events() -> list[dict[str, Any]]:
    return []


@dataclass(slots=True)
class AnalysisTraceRecorder:
    """Collects timestamped trace events for a single analysis run."""

    source_file: Path | None = None
    _start_time: float = field(default_factory=time.perf_counter)
    events: list[dict[str, Any]] = field(default_factory=_empty_trace_events)

    def event(self, phase: str, action: str, **data: Any) -> None:
        payload: dict[str, Any] = {
            "phase": phase,
            "action": action,
            "time_offset_ms": round((time.perf_counter() - self._start_time) * 1000, 3),
        }
        if data:
            payload["data"] = data
        self.events.append(payload)


def _module_node_label(node: object) -> str:
    if isinstance(node, SingleModule):
        return f"SingleModule:{node.header.name}"
    if isinstance(node, FrameModule):
        return f"FrameModule:{node.header.name}"
    if isinstance(node, ModuleTypeInstance):
        return f"ModuleTypeInstance:{node.header.name}"
    return type(node).__name__


def detect_transform_invariant_violations(base_picture: BasePicture) -> list[dict[str, Any]]:
    violations: list[dict[str, Any]] = []

    def walk_modules(modules: SequenceABC[object] | None, path: list[str]) -> None:
        seen_names: set[str] = set()
        for module in modules or []:
            if not isinstance(module, SingleModule | FrameModule | ModuleTypeInstance):
                violations.append(
                    {
                        "kind": "unexpected_submodule_type",
                        "module_path": path.copy(),
                        "node_label": _module_node_label(module),
                    }
                )
                continue

            header = getattr(module, "header", None)
            module_name = getattr(header, "name", None)
            if module_name:
                module_key = module_name.casefold()
                if module_key in seen_names:
                    violations.append(
                        {
                            "kind": "duplicate_sibling_name",
                            "module_path": path.copy(),
                            "module_name": module_name,
                        }
                    )
                seen_names.add(module_key)

            if isinstance(module, SingleModule | FrameModule):
                next_path = path + ([module_name] if module_name else [_module_node_label(module)])
                walk_modules(module.submodules, next_path)

    walk_modules(base_picture.submodules, [base_picture.header.name])
    return violations


def detect_unreachable_sequence_logic(base_picture: BasePicture) -> list[dict[str, Any]]:
    return [
        {
            "kind": "unreachable_sequence_node",
            "module_path": list(finding.module_path),
            "sequence_name": finding.sequence_name,
            "branch_path": list(finding.branch_path),
            "node_index": finding.node_index,
            "node_label": finding.node_label,
            "node_type": finding.node_type,
            "terminated_by": dict(finding.terminated_by),
        }
        for finding in collect_sfc_reachability_findings(base_picture)
    ]


__all__ = [
    "AnalysisTraceRecorder",
    "detect_transform_invariant_violations",
    "detect_unreachable_sequence_logic",
]
