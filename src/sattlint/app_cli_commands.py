from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from sattline_parser.models.ast_model import BasePicture

from . import console as console_module
from .cache import CachePruneResult
from .cli_output import render_json_output
from .config_types import ConfigDict
from .models.project_graph import ProjectGraph

log = logging.getLogger("SattLint")
emit_output: Callable[..., None] = console_module.print_output  # type: ignore[assignment]

LoadedProject = tuple[str, BasePicture, ProjectGraph]


@dataclass(frozen=True, slots=True)
class AnalyzeCommandResult:
    output_lines: tuple[str, ...]
    cancelled: bool = False
    selected_keys: tuple[str, ...] | None = None
    selected_issue_kinds: tuple[str, ...] | None = None
    selected_analyzers: tuple[str, ...] = ()
    targets: tuple[object, ...] = ()


def _serialize_analyze_analyzer_result(result: object) -> dict[str, Any]:
    selected_issue_kinds = getattr(result, "selected_issue_kinds", None)
    return {
        "key": getattr(result, "key", None),
        "name": getattr(result, "name", None),
        "status": getattr(result, "status", None),
        "summary": getattr(result, "summary", None),
        "report_kind": getattr(result, "report_kind", None),
        "issue_count": getattr(result, "issue_count", None),
        "duration_ms": getattr(result, "duration_ms", None),
        "phase_timings_ms": list(getattr(result, "phase_timings_ms", ())),
        "selected_issue_kinds": None
        if selected_issue_kinds is None
        else list(cast(tuple[str, ...], selected_issue_kinds)),
        "skip_reason": getattr(result, "skip_reason", None),
    }


def _serialize_analyze_target_result(result: object) -> dict[str, Any]:
    return {
        "target_name": getattr(result, "target_name", None),
        "is_library": getattr(result, "is_library", None),
        "analyzers": [
            _serialize_analyze_analyzer_result(analyzer)
            for analyzer in cast(tuple[object, ...], getattr(result, "analyzers", ()))
        ],
        "stage_timings_ms": getattr(result, "stage_timings_ms", None),
        "graphics_timings_ms": getattr(result, "graphics_timings_ms", None),
        "analyzer_bottleneck": getattr(result, "analyzer_bottleneck", None),
        "analyzer_phase_bottleneck": getattr(result, "analyzer_phase_bottleneck", None),
        "shared_artifact_profile": getattr(result, "shared_artifact_profile", None),
    }


def _analyze_command_json_payload(result: AnalyzeCommandResult) -> dict[str, Any]:
    return {
        "cancelled": result.cancelled,
        "selected_checks": None if result.selected_keys is None else list(result.selected_keys),
        "selected_issue_kinds": None if result.selected_issue_kinds is None else list(result.selected_issue_kinds),
        "selected_analyzers": list(result.selected_analyzers),
        "targets": [_serialize_analyze_target_result(target) for target in result.targets],
    }


def render_analyze_command_result(
    result: AnalyzeCommandResult,
    *,
    emit_output_fn: Callable[[str], None] = emit_output,
) -> None:
    for line in result.output_lines:
        emit_output_fn(line)


def _format_cache_prune_result(result: CachePruneResult) -> str:
    details = (
        ("lookup", result.file_lookup_entries),
        ("file-ast", result.file_ast_entries),
        ("ast-payload", result.ast_payload_entries),
        ("ast-manifest", result.ast_manifest_entries),
        ("analysis-report", result.analysis_report_entries),
    )
    parts = [f"{label}={count}" for label, count in details if count]
    return ", ".join(parts) if parts else "no stale entries"


def _cache_prune_json_payload(target_dir: Path, result: CachePruneResult) -> dict[str, Any]:
    return {
        "status": "ok",
        "cache_dir": str(target_dir),
        "removed_entries": result.removed_entries,
        "details": {
            "lookup": result.file_lookup_entries,
            "file_ast": result.file_ast_entries,
            "ast_payload": result.ast_payload_entries,
            "ast_manifest": result.ast_manifest_entries,
            "analysis_report": result.analysis_report_entries,
        },
    }


def run_analyze_command(
    cfg: ConfigDict,
    *,
    selected_keys: list[str] | None,
    selected_issue_kinds: frozenset[str] | None,
    use_cache: bool,
    output_format: str = "text",
    collect_analyze_result_fn: Callable[..., Any],
    emit_output_fn: Callable[[str], None] = emit_output,
    exit_success: int,
) -> int:
    del use_cache
    collected = collect_analyze_result_fn(
        cfg,
        selected_keys=selected_keys,
        selected_issue_kinds=selected_issue_kinds,
    )
    result = AnalyzeCommandResult(
        output_lines=tuple(getattr(collected, "output_lines", ())),
        cancelled=bool(getattr(collected, "cancelled", False)),
        selected_keys=None if selected_keys is None else tuple(selected_keys),
        selected_issue_kinds=None if selected_issue_kinds is None else tuple(sorted(selected_issue_kinds)),
        selected_analyzers=tuple(getattr(collected, "selected_analyzers", ())),
        targets=tuple(getattr(collected, "targets", ())),
    )
    if output_format == "json":
        emit_output_fn(render_json_output(_analyze_command_json_payload(result)))
        return exit_success
    render_analyze_command_result(result, emit_output_fn=emit_output_fn)
    if result.cancelled:
        emit_output_fn("\nOperation canceled. Returning to the menu.")
    return exit_success


def run_cache_prune_command(
    *,
    cache_dir: str | None,
    output_format: str = "text",
    prune_cache_dir_fn: Callable[[Path | None], CachePruneResult],
    get_cache_dir_fn: Callable[[], Path],
    exit_success: int,
    exit_usage_error: int,
) -> int:
    target_dir = Path(cache_dir).expanduser() if cache_dir else get_cache_dir_fn()
    try:
        result = prune_cache_dir_fn(target_dir)
    except OSError as exc:
        if output_format == "json":
            console_module.print_output(
                render_json_output(
                    {
                        "status": "error",
                        "message": f"Cache prune failed for {target_dir}: {exc}",
                        "cache_dir": str(target_dir),
                    }
                )
            )
        else:
            console_module.print_output(f"Cache prune failed for {target_dir}: {exc}")
        return exit_usage_error

    if output_format == "json":
        console_module.print_output(render_json_output(_cache_prune_json_payload(target_dir, result)))
        return exit_success

    if result.removed_entries == 0:
        console_module.print_output(f"Cache directory already clean: {target_dir}")
        return exit_success

    entry_label = "entry" if result.removed_entries == 1 else "entries"
    console_module.print_output(
        f"Removed {result.removed_entries} stale cache {entry_label} from {target_dir} ({_format_cache_prune_result(result)})."
    )
    return exit_success
