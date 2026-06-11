from __future__ import annotations

import json
import logging
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any, cast

from sattline_parser.models.ast_model import BasePicture

from . import config as config_module
from . import console as console_module
from ._app_debug import log_debug_exception
from .cache import CachePruneResult
from .config import ConfigValidationResult
from .docgenerator import generate_docx
from .models.project_graph import ProjectGraph

emit_output = console_module.print_output  # type: ignore[assignment]
log = logging.getLogger("SattLint")

ConfigDict = dict[str, Any]
DocumentationSelection = dict[str, Any]
LoadedProject = tuple[str, BasePicture, ProjectGraph]


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
        emit_output(f"Failed to write {label} to {destination}: {exc}")
        return False
    emit_output(f"Wrote {destination}")
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


def run_validate_config_command(
    cfg: ConfigDict,
    *,
    config_path: Path,
    default_used: bool,
    validate_config_fn: Callable[[ConfigDict], ConfigValidationResult],
    exit_success: int,
    exit_usage_error: int,
) -> int:
    if default_used:
        emit_output(f"Warning: default config loaded from {config_path}")
    validation = validate_config_fn(cfg)
    for error in validation.errors:
        emit_output(error.message)
    return exit_success if validation.passed else exit_usage_error


def run_analyze_command(
    cfg: ConfigDict,
    *,
    selected_keys: list[str] | None,
    selected_issue_kinds: frozenset[str] | None = None,
    use_cache: bool,
    run_checks_fn: Callable[..., None],
    exit_success: int,
) -> int:
    run_checks_fn(cfg, selected_keys, use_cache, selected_issue_kinds=selected_issue_kinds)
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
        emit_output(str(exc))
        return exit_usage_error
    except Exception as exc:  # noqa: BLE001
        log_debug_exception(
            cfg, f"Simulation command failed for module {module_name!r} from {target_path!r}", logger=log
        )
        emit_output(f"Simulation failed: {exc}")
        return exit_usage_error

    if output_format == "json":
        payload = json.dumps(result.to_dict(), indent=2)
        if output_path:
            destination = Path(output_path)
            if not _write_output_file(destination, payload, label="simulation output", cfg=cfg):
                return exit_usage_error
        else:
            emit_output(payload)
        return exit_success

    summary = result.render_summary()
    if output_path:
        destination = Path(output_path)
        if not _write_output_file(destination, summary, label="simulation output", cfg=cfg):
            return exit_usage_error
    else:
        emit_output(summary)
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
        emit_output("No analyzed targets configured")
        return exit_usage_error

    if output_path and len(projects) > 1:
        emit_output("output_path requires exactly one configured target")
        return exit_usage_error

    base_output_dir: Path | None = None
    if output_dir:
        base_output_dir = Path(output_dir)
        base_output_dir.mkdir(parents=True, exist_ok=True)

    documentation_cfg = config_module.get_documentation_config(cfg)
    documentation_cfg["units"] = documentation_unit_selection_fn()

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
            emit_output(f"Documentation generation failed for {destination}: {exc}")
            return exit_usage_error
        emit_output(f"Generated {destination}")

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
        emit_output(f"Telemetry file not found: {telemetry_path}")
        return exit_usage_error
    except (OSError, ValueError) as exc:
        log_debug_exception(cfg, f"Telemetry summary failed for {telemetry_path}", logger=log)
        emit_output(f"Telemetry summary failed: {exc}")
        return exit_usage_error

    content = json.dumps(summary, indent=2) if output_format == "json" else render_text_summary_fn(summary)

    if output_path:
        if not _write_output_file(Path(output_path), content, label="telemetry summary", cfg=cfg):
            return exit_usage_error
    else:
        emit_output(content)
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
        emit_output(f"Cache prune failed for {target_dir}: {exc}")
        return exit_usage_error

    if result.removed_entries == 0:
        emit_output(f"Cache directory already clean: {target_dir}")
        return exit_success

    entry_label = "entry" if result.removed_entries == 1 else "entries"
    emit_output(
        f"Removed {result.removed_entries} stale cache {entry_label} from {target_dir} ({_format_cache_prune_result(result)})."
    )
    return exit_success
