from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

from . import app_docs as app_docs_module
from . import config as config_module
from . import console as console_module
from .docgenerator import generate_docx
from sattline_parser.models.ast_model import BasePicture
from .models.project_graph import ProjectGraph

emit_output = console_module.print_output  # type: ignore[assignment]


def run_validate_config_command(
    cfg: dict,
    *,
    config_path: Path,
    default_used: bool,
    self_check_fn: Callable[[dict], bool],
    exit_success: int,
    exit_usage_error: int,
) -> int:
    if default_used:
        emit_output(f"Warning: default config loaded from {config_path}")
    is_valid = self_check_fn(cfg)
    return exit_success if is_valid else exit_usage_error


def run_analyze_command(
    cfg: dict,
    *,
    selected_keys: list[str] | None,
    use_cache: bool,
    run_checks_fn: Callable[[dict, list[str] | None, bool], None],
    exit_success: int,
) -> int:
    run_checks_fn(cfg, selected_keys, use_cache)
    return exit_success


def run_docgen_command(
    cfg: dict,
    *,
    use_cache: bool,
    output_dir: str | None,
    output_path: str | None,
    iter_loaded_projects_fn: Callable[[dict, bool], Iterator[tuple[str, BasePicture, ProjectGraph]]],
    documentation_unit_selection_fn: Callable[[], dict[str, Any]],
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
            unavailable_libraries=getattr(graph, "unavailable_libraries", set()),
        )
        emit_output(f"Generated {destination}")

    return exit_success
