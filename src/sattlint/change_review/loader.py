"""Load one project version (official or draft) into a semantic snapshot.

Both versions of the configured project are loaded through the existing
``SattLineProjectLoader`` and ``build_snapshot_from_loaded_project`` seam. Each
version is parsed exactly once; the resulting ``SemanticSnapshot`` and per-module
``CodeModel`` are reused by the semantic diff, impact analysis, and context
extraction. No analyzers run and no diagnostics are collected.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import cast

from ..config.types import ConfigDict
from ..core._semantic_snapshot import SemanticSnapshot
from ..core.semantic import build_snapshot_from_loaded_project
from ..core.syntax import CodeMode, code_ext, normalize_code_mode
from ..models.project_graph import ProjectGraph, merge_project_basepicture
from ..project import loading as project_loading
from ._code_model import CodeModel, build_code_model


@dataclass(frozen=True)
class VersionSnapshot:
    """One parsed project version with its semantic index and code model."""

    label: str
    snapshot: SemanticSnapshot
    code_model: CodeModel
    entry_file: Path
    workspace_root: Path
    source_files: dict[str, Path]
    total_source_size: int


def _resolve_entry_path(
    cfg: ConfigDict,
    graph: ProjectGraph,
    program_name: str,
    mode: CodeMode,
) -> Path:
    root_origin = graph.root_origin_for_name(program_name)
    if root_origin is not None and root_origin.source_path is not None:
        return root_origin.source_path
    program_dir = Path(str(cfg["program_dir"]))
    return program_dir / f"{program_name}{code_ext(mode)}"


def load_version_snapshot(
    cfg: ConfigDict,
    program_name: str,
    *,
    mode: str,
) -> VersionSnapshot:
    """Load and build the semantic snapshot for one project version."""
    normalized_mode = normalize_code_mode(mode)
    if normalized_mode is None:
        raise ValueError(f"Unsupported change-review mode: {mode!r}")

    version_cfg = cast(ConfigDict, {**cfg, "mode": normalized_mode.value})
    root_bp, graph = project_loading.load_program_ast(version_cfg, program_name)
    merged_bp = merge_project_basepicture(root_bp, graph)
    entry_path = _resolve_entry_path(version_cfg, graph, program_name, normalized_mode)
    workspace_root = Path(str(version_cfg["program_dir"]))

    snapshot = build_snapshot_from_loaded_project(
        merged_bp,
        graph,
        entry_file=entry_path,
        workspace_root=workspace_root,
        collect_variable_diagnostics=False,
    )
    code_model = build_code_model(snapshot)

    source_files: dict[str, Path] = {}
    total_size = 0
    for path in graph.source_files:
        source_files[path.name.casefold()] = path
        if path.exists():
            try:
                total_size += path.stat().st_size
            except OSError:
                continue

    return VersionSnapshot(
        label=normalized_mode.value,
        snapshot=snapshot,
        code_model=code_model,
        entry_file=entry_path,
        workspace_root=workspace_root,
        source_files=source_files,
        total_source_size=total_size,
    )
