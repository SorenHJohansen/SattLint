"""Tracing report builders for the analysis pipeline."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sattlint.tracing import trace_source_file_analysis


def collect_trace_report(
    trace_target: Path,
    *,
    debug: bool = False,
) -> dict[str, Any]:
    return trace_source_file_analysis(trace_target, debug=debug)


__all__ = ["collect_trace_report"]
