"""Tracing helpers for parser and analyzer execution over SattLine files."""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from collections.abc import Sequence as SequenceABC
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .analyzers.dataflow import analyze_dataflow
from .analyzers.sfc import collect_sfc_reachability_findings
from .analyzers.variables import analyze_variables
from .engine import parse_source_file, validate_single_file_syntax
from .models.ast_model import (
    BasePicture,
    FrameModule,
    ModuleTypeInstance,
    SingleModule,
)
from .path_sanitizer import sanitize_path_for_report

REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass(slots=True)
class AnalysisTraceRecorder:
    """Collects timestamped trace events for a single analysis run."""

    source_file: Path | None = None
    _start_time: float = field(default_factory=time.perf_counter)
    events: list[dict[str, Any]] = field(default_factory=list)

    def event(self, phase: str, action: str, **data: Any) -> None:
        payload = {
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


def collect_ast_summary(base_picture: BasePicture) -> dict[str, Any]:
    summary = {
        "datatype_definition_count": len(base_picture.datatype_defs or []),
        "moduletype_definition_count": len(base_picture.moduletype_defs or []),
        "root_localvariable_count": len(base_picture.localvariables or []),
        "submodule_count": 0,
        "single_module_count": 0,
        "frame_module_count": 0,
        "moduletype_instance_count": 0,
        "moduleparameter_count": 0,
        "module_localvariable_count": 0,
        "sequence_count": 0,
        "equation_count": 0,
    }

    def walk_modulecode(modulecode: object | None) -> None:
        if modulecode is None:
            return
        summary["sequence_count"] += len(getattr(modulecode, "sequences", []) or [])
        summary["equation_count"] += len(getattr(modulecode, "equations", []) or [])

    def walk_modules(modules: SequenceABC[object] | None) -> None:
        for module in modules or []:
            summary["submodule_count"] += 1
            if isinstance(module, SingleModule):
                summary["single_module_count"] += 1
                summary["moduleparameter_count"] += len(module.moduleparameters or [])
                summary["module_localvariable_count"] += len(module.localvariables or [])
                walk_modulecode(module.modulecode)
                walk_modules(module.submodules)
            elif isinstance(module, FrameModule):
                summary["frame_module_count"] += 1
                walk_modules(module.submodules)
            elif isinstance(module, ModuleTypeInstance):
                summary["moduletype_instance_count"] += 1

    walk_modulecode(base_picture.modulecode)
    walk_modules(base_picture.submodules)
    for moduletype in base_picture.moduletype_defs or []:
        summary["moduleparameter_count"] += len(moduletype.moduleparameters or [])
        summary["module_localvariable_count"] += len(moduletype.localvariables or [])
        walk_modulecode(moduletype.modulecode)

    return summary


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


def _build_timing_summary(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate trace events into per-phase event counts and span durations.

    For each phase, computes:
    - event_count: number of events in that phase
    - span_ms: elapsed time between first and last event in the phase
    """
    phase_events: dict[str, list[float]] = {}
    for event in events:
        phase = str(event.get("phase") or "unknown")
        offset = float(event.get("time_offset_ms") or 0.0)
        phase_events.setdefault(phase, []).append(offset)

    summary: dict[str, Any] = {}
    for phase, offsets in sorted(phase_events.items()):
        summary[phase] = {
            "event_count": len(offsets),
            "span_ms": round(max(offsets) - min(offsets), 3) if len(offsets) > 1 else 0.0,
        }
    return summary


def trace_basepicture_analysis(
    base_picture: BasePicture,
    *,
    source_file: Path | None = None,
    recorder: AnalysisTraceRecorder | None = None,
    debug: bool = False,
) -> dict[str, Any]:
    trace_recorder = recorder or AnalysisTraceRecorder(source_file=source_file)
    sanitized_source_file = sanitize_path_for_report(source_file, repo_root=REPO_ROOT)
    trace_recorder.event(
        "analysis",
        "basepicture-loaded",
        basepicture_name=base_picture.header.name,
        source_file=sanitized_source_file,
    )

    ast_summary = collect_ast_summary(base_picture)
    trace_recorder.event("analysis", "ast-summary", **ast_summary)

    report = analyze_variables(base_picture, debug=debug, trace_recorder=trace_recorder)
    dataflow_report = analyze_dataflow(base_picture)
    issue_counts = dict(sorted(Counter(issue.kind.value for issue in report.issues).items()))
    dataflow_issue_counts = dict(sorted(Counter(issue.kind for issue in dataflow_report.issues).items()))
    unreachable_logic = detect_unreachable_sequence_logic(base_picture)
    transform_violations = detect_transform_invariant_violations(base_picture)

    trace_recorder.event(
        "analysis",
        "completed",
        issue_count=len(report.issues),
        dataflow_issue_count=len(dataflow_report.issues),
        unreachable_logic_count=len(unreachable_logic),
        transform_violation_count=len(transform_violations),
    )

    return {
        "source_file": sanitized_source_file,
        "basepicture_name": base_picture.header.name,
        "ast_summary": ast_summary,
        "variable_analysis": {
            "issue_count": len(report.issues),
            "issue_counts": issue_counts,
        },
        "dataflow_analysis": {
            "issue_count": len(dataflow_report.issues),
            "issue_counts": dataflow_issue_counts,
            "findings": [
                {
                    "kind": issue.kind,
                    "message": issue.message,
                    "module_path": issue.module_path,
                    "data": issue.data,
                }
                for issue in dataflow_report.issues
            ],
        },
        "heuristics": {
            "unreachable_logic": unreachable_logic,
            "transform_invariant_violations": transform_violations,
        },
        "timing_summary": _build_timing_summary(trace_recorder.events),
        "events": trace_recorder.events,
    }


def trace_source_file_analysis(
    source_file: Path,
    *,
    output_path: Path | None = None,
    debug: bool = False,
) -> dict[str, Any]:
    resolved_source = source_file.resolve()
    recorder = AnalysisTraceRecorder(source_file=resolved_source)
    sanitized_source_file = sanitize_path_for_report(resolved_source, repo_root=REPO_ROOT)
    syntax_result = validate_single_file_syntax(resolved_source)
    recorder.event(
        "syntax",
        "validated",
        ok=syntax_result.ok,
        stage=syntax_result.stage,
        line=syntax_result.line,
        column=syntax_result.column,
        message=syntax_result.message,
    )

    payload: dict[str, Any] = {
        "source_file": sanitized_source_file,
        "syntax_validation": {
            "ok": syntax_result.ok,
            "stage": syntax_result.stage,
            "line": syntax_result.line,
            "column": syntax_result.column,
            "message": syntax_result.message,
        },
    }

    if syntax_result.ok:
        base_picture = parse_source_file(
            resolved_source,
            debug=(lambda message: recorder.event("parse", "debug", message=message)) if debug else None,
        )
        payload.update(
            trace_basepicture_analysis(
                base_picture,
                source_file=resolved_source,
                recorder=recorder,
                debug=debug,
            )
        )
    else:
        payload["events"] = recorder.events

    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    return payload


def cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Trace parser and analyzer execution for a SattLine file.")
    parser.add_argument("source_file", help="Path to the .s or .x source file to trace")
    parser.add_argument("--output", help="Write trace JSON to this path instead of stdout")
    parser.add_argument("--debug", action="store_true", help="Include parser debug events in the trace")
    args = parser.parse_args(argv)

    payload = trace_source_file_analysis(
        Path(args.source_file),
        output_path=Path(args.output) if args.output else None,
        debug=args.debug,
    )
    if args.output:
        print(f"Trace written to {Path(args.output).resolve()}")
    else:
        print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


__all__ = [
    "AnalysisTraceRecorder",
    "cli",
    "collect_ast_summary",
    "detect_transform_invariant_violations",
    "detect_unreachable_sequence_logic",
    "trace_basepicture_analysis",
    "trace_source_file_analysis",
]
