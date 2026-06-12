from __future__ import annotations

import json
import logging
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from sattline_parser.models.ast_model import BasePicture

from . import config as config_module
from . import console as console_module
from ._app_debug import log_debug_exception
from .cache import CachePruneResult
from .cli_output import render_json_output
from .config_types import ConfigDict
from .docgenerator import generate_docx
from .models.project_graph import ProjectGraph

log = logging.getLogger("SattLint")
emit_output: Callable[..., None] = console_module.print_output  # type: ignore[assignment]

DocumentationSelection = dict[str, Any]
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


def _run_with_live_status(status_text: str, run_fn: Callable[[], Any]) -> Any:
    with console_module.live_status_line() as status_update_fn:
        status_update_fn(status_text)
        return run_fn()


def _write_output_file(destination: Path, content: str, *, label: str, cfg: ConfigDict | None = None) -> bool:
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content + "\n", encoding="utf-8")
    except OSError as exc:
        if cfg is not None:
            log_debug_exception(cfg, f"Failed to write {label} to {destination}", logger=log)
        console_module.print_output(f"Failed to write {label} to {destination}: {exc}")
        return False
    console_module.print_output(f"Wrote {destination}")
    return True


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


def run_simulate_command(
    cfg: ConfigDict,
    *,
    target_path: str,
    module_name: str,
    mode: str,
    max_scans: int,
    output_format: str,
    output_path: str | None,
    use_cache: bool,
    simulate_fn: Callable[..., Any],
    exit_success: int,
    exit_usage_error: int,
) -> int:
    try:
        result = _run_with_live_status(
            f"Simulating {module_name} from {target_path}",
            lambda: simulate_fn(
                cfg,
                target_path=target_path,
                module_name=module_name,
                mode=mode,
                max_scans=max_scans,
                use_cache=use_cache,
            ),
        )
    except (FileNotFoundError, ValueError) as exc:
        console_module.print_output(str(exc))
        return exit_usage_error
    except Exception as exc:  # noqa: BLE001
        log_debug_exception(
            cfg, f"Simulation command failed for module {module_name!r} from {target_path!r}", logger=log
        )
        console_module.print_output(f"Simulation failed: {exc}")
        return exit_usage_error

    if output_format == "json":
        payload = json.dumps(result.to_dict(), indent=2)
        if output_path:
            destination = Path(output_path)
            if not _write_output_file(destination, payload, label="simulation output", cfg=cfg):
                return exit_usage_error
        else:
            console_module.print_output(payload)
        return exit_success

    summary = result.render_summary()
    if output_path:
        destination = Path(output_path)
        if not _write_output_file(destination, summary, label="simulation output", cfg=cfg):
            return exit_usage_error
    else:
        console_module.print_output(summary)
    return exit_success


def run_docgen_command(
    cfg: ConfigDict,
    *,
    use_cache: bool,
    output_dir: str | None,
    output_path: str | None,
    iter_loaded_projects_fn: Callable[[ConfigDict, bool], Iterator[LoadedProject]],
    documentation_unit_selection_fn: Callable[[], DocumentationSelection],
    exit_success: int,
    exit_usage_error: int,
) -> int:
    projects = list(iter_loaded_projects_fn(cfg, use_cache))
    if not projects:
        console_module.print_output("No analyzed targets configured")
        return exit_usage_error

    if output_path and len(projects) > 1:
        console_module.print_output("output_path requires exactly one configured target")
        return exit_usage_error

    base_output_dir: Path | None = None
    if output_dir:
        base_output_dir = Path(output_dir)
        base_output_dir.mkdir(parents=True, exist_ok=True)

    documentation_cfg = {
        "classifications": config_module.get_documentation_config(cfg)["classifications"],
        "units": documentation_unit_selection_fn(),
    }

    for target_name, project_bp, graph in projects:
        if output_path:
            destination = Path(output_path)
        elif base_output_dir is not None:
            destination = base_output_dir / f"{target_name}_FS.docx"
        else:
            destination = Path(f"{target_name}_FS.docx")

        destination.parent.mkdir(parents=True, exist_ok=True)

        try:
            _run_with_live_status(
                f"Generating documentation for {target_name}",
                lambda project_bp=project_bp, destination=destination, graph=graph: generate_docx(
                    project_bp,
                    str(destination),
                    documentation_config=documentation_cfg,
                    unavailable_libraries=cast(
                        set[str],
                        getattr(graph, "unavailable_libraries", cast(set[str], set())),
                    ),
                ),
            )
        except OSError as exc:
            log_debug_exception(
                cfg, f"Documentation generation failed for target {target_name!r} to {destination}", logger=log
            )
            console_module.print_output(f"Documentation generation failed for {destination}: {exc}")
            return exit_usage_error
        console_module.print_output(f"Generated {destination}")

    return exit_success


def run_telemetry_summary_command(
    cfg: ConfigDict,
    *,
    config_path: Path,
    output_format: str,
    output_path: str | None,
    telemetry_output_path_fn: Callable[[Path], Path],
    summarize_telemetry_fn: Callable[[Path], dict[str, Any]],
    render_text_summary_fn: Callable[[dict[str, Any]], str],
    exit_success: int,
    exit_usage_error: int,
) -> int:
    telemetry_path = telemetry_output_path_fn(config_path)
    try:
        summary = summarize_telemetry_fn(telemetry_path)
    except FileNotFoundError:
        console_module.print_output(f"Telemetry file not found: {telemetry_path}")
        return exit_usage_error
    except (OSError, ValueError) as exc:
        log_debug_exception(cfg, f"Telemetry summary failed for {telemetry_path}", logger=log)
        console_module.print_output(f"Telemetry summary failed: {exc}")
        return exit_usage_error

    content = json.dumps(summary, indent=2) if output_format == "json" else render_text_summary_fn(summary)

    if output_path:
        if not _write_output_file(Path(output_path), content, label="telemetry summary", cfg=cfg):
            return exit_usage_error
    else:
        console_module.print_output(content)
    return exit_success


def run_cache_prune_command(
    *,
    cache_dir: str | None,
    prune_cache_dir_fn: Callable[[Path | None], CachePruneResult],
    get_cache_dir_fn: Callable[[], Path],
    exit_success: int,
    exit_usage_error: int,
) -> int:
    target_dir = Path(cache_dir).expanduser() if cache_dir else get_cache_dir_fn()
    try:
        result = prune_cache_dir_fn(target_dir)
    except OSError as exc:
        console_module.print_output(f"Cache prune failed for {target_dir}: {exc}")
        return exit_usage_error

    if result.removed_entries == 0:
        console_module.print_output(f"Cache directory already clean: {target_dir}")
        return exit_success

    entry_label = "entry" if result.removed_entries == 1 else "entries"
    console_module.print_output(
        f"Removed {result.removed_entries} stale cache {entry_label} from {target_dir} ({_format_cache_prune_result(result)})."
    )
    return exit_success
