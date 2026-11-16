"""Run history: persistence of completed analysis runs."""

from __future__ import annotations

from .io import (
    DEFAULT_RUN_HISTORY_LIMIT,
    delete_run,
    get_runs_dir,
    get_runs_dir_or_none,
    list_runs,
    load_run,
    prune_runs,
    runs_dir_location,
    save_run,
)
from .types import RUN_RECORD_SCHEMA_VERSION, RunAnalyzerRecord, RunModuleRecord, RunRecord, RunSummary, RunTargetRecord

__all__ = [
    "DEFAULT_RUN_HISTORY_LIMIT",
    "RUN_RECORD_SCHEMA_VERSION",
    "RunAnalyzerRecord",
    "RunModuleRecord",
    "RunRecord",
    "RunSummary",
    "RunTargetRecord",
    "delete_run",
    "get_runs_dir",
    "get_runs_dir_or_none",
    "list_runs",
    "load_run",
    "prune_runs",
    "runs_dir_location",
    "save_run",
]
