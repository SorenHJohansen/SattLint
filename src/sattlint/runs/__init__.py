"""Run history: persistence of completed analysis runs."""

from __future__ import annotations

from .io import (
    DEFAULT_RUN_HISTORY_LIMIT,
    get_runs_dir,
    list_runs,
    load_run,
    prune_runs,
    save_run,
)
from .types import RUN_RECORD_SCHEMA_VERSION, RunAnalyzerRecord, RunRecord, RunSummary, RunTargetRecord

__all__ = [
    "DEFAULT_RUN_HISTORY_LIMIT",
    "RUN_RECORD_SCHEMA_VERSION",
    "RunAnalyzerRecord",
    "RunRecord",
    "RunSummary",
    "RunTargetRecord",
    "get_runs_dir",
    "list_runs",
    "load_run",
    "prune_runs",
    "save_run",
]
