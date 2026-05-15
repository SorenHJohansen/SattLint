from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any, cast

from sattline_parser.models.ast_model import BasePicture

from . import config as config_module
from . import console as console_module
from .config import ConfigValidationResult
from .docgenerator import generate_docx
from .models.project_graph import ProjectGraph

emit_output = console_module.print_output  # type: ignore[assignment]

ConfigDict = dict[str, Any]
DocumentationSelection = dict[str, Any]
LoadedProject = tuple[str, BasePicture, ProjectGraph]


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
    use_cache: bool,
    run_checks_fn: Callable[[ConfigDict, list[str] | None, bool], None],
    exit_success: int,
) -> int:
    run_checks_fn(cfg, selected_keys, use_cache)
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
        result = simulate_fn(
            cfg,
            target_path=target_path,
            module_name=module_name,
            mode=mode,
            max_scans=max_scans,
            use_cache=use_cache,
        )
    except (FileNotFoundError, ValueError) as exc:
        emit_output(str(exc))
        return exit_usage_error
    except Exception as exc:
        emit_output(f"Simulation failed: {exc}")
        return exit_usage_error

    if output_format == "json":
        payload = json.dumps(result.to_dict(), indent=2)
        if output_path:
            destination = Path(output_path)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(payload + "\n", encoding="utf-8")
            emit_output(f"Wrote {destination}")
        else:
            emit_output(payload)
        return exit_success

    summary = result.render_summary()
    if output_path:
        destination = Path(output_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(summary + "\n", encoding="utf-8")
        emit_output(f"Wrote {destination}")
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

        generate_docx(
            project_bp,
            str(destination),
            documentation_config=documentation_cfg,
            unavailable_libraries=cast(set[str], getattr(graph, "unavailable_libraries", cast(set[str], set()))),
        )
        emit_output(f"Generated {destination}")

    return exit_success
