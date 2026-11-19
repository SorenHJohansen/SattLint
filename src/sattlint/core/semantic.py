"""Shared semantic snapshot and project/source loading layer.

Owns the canonical in-memory ``SemanticSnapshot`` (symbol index, access
graph) and the project/source loading helpers that build it from a parsed
project. This is shared *infrastructure*: it is consumed by
``change_review`` and the public ``sattlint`` package surface, and it does
not implement analyzer rules.
"""

from __future__ import annotations

import logging
from pathlib import Path

from sattlint.parser_api import BasePicture
from sattlint.parser_api import parse_source_text as parser_core_parse_source_text

from ..models.project_graph import ProjectGraph
from ._semantic_index import SemanticIndexBuilder
from ._semantic_snapshot import SemanticSnapshot, SymbolDefinition, SymbolReference
from .call_signatures import CallSignatureOccurrence

log = logging.getLogger("SattLint")


def _emit_parser_debug(message: str) -> None:
    log.debug("Semantic snapshot parser: %s", message)


def _build_semantic_snapshot(
    base_picture: BasePicture,
    *,
    entry_path: Path,
    workspace_root: Path,
    project_graph: ProjectGraph,
    include_dependency_modules: bool = True,
    build_reference_index: bool = True,
) -> SemanticSnapshot:
    root_origin = project_graph.root_origin_for_basepicture(base_picture)
    root_origin_file = root_origin.origin_file if root_origin is not None else base_picture.origin_file
    root_origin_library = (
        root_origin.library_name
        if root_origin is not None and root_origin.library_name is not None
        else base_picture.origin_lib
    )
    builder = SemanticIndexBuilder(
        base_picture,
        root_origin_file=root_origin_file,
        root_origin_library=root_origin_library,
        unavailable_libraries=project_graph.unavailable_libraries,
        include_dependency_modules=include_dependency_modules,
        graphics_attachments=project_graph.graphics_attachments_for(base_picture),
        build_reference_index=build_reference_index,
    )
    builder_result = builder.build()
    symbol_table = builder_result.symbol_table
    type_graph = builder_result.type_graph
    definitions = builder_result.definitions
    definitions_by_key = builder_result.definitions_by_key
    moduletype_index = builder_result.moduletype_index
    references_by_file = builder_result.references_by_file
    references_by_definition_key = builder_result.references_by_definition_key
    call_signatures = builder_result.call_signatures

    return SemanticSnapshot(
        workspace_root=workspace_root,
        entry_file=entry_path,
        base_picture=base_picture,
        project_graph=project_graph,
        symbol_table=symbol_table,
        type_graph=type_graph,
        definitions=definitions,
        call_signatures=call_signatures,
        _definitions_by_key=definitions_by_key,
        _moduletype_index=moduletype_index,
        _references_by_file=references_by_file,
        _references_by_definition_key=references_by_definition_key,
    )


def load_source_snapshot(
    source_file: Path,
    source_text: str,
    *,
    workspace_root: Path | None = None,
    debug: bool = False,
) -> SemanticSnapshot:
    base_picture = parser_core_parse_source_text(
        source_text,
        debug=(_emit_parser_debug if debug else None),
        source_path=Path(source_file),
    )
    return build_source_snapshot_from_basepicture(
        base_picture,
        source_file,
        workspace_root=workspace_root,
    )


def build_source_snapshot_from_basepicture(
    base_picture: BasePicture,
    source_file: Path,
    *,
    workspace_root: Path | None = None,
) -> SemanticSnapshot:
    entry_path = Path(source_file).resolve()
    root = Path(workspace_root).resolve() if workspace_root else entry_path.parent

    project_graph = ProjectGraph()
    project_graph.index_from_basepic(
        base_picture,
        source_path=entry_path,
        library_name=entry_path.parent.name,
    )

    return _build_semantic_snapshot(
        base_picture,
        entry_path=entry_path,
        workspace_root=root,
        project_graph=project_graph,
    )


def build_snapshot_from_loaded_project(
    base_picture: BasePicture,
    project_graph: ProjectGraph,
    *,
    entry_file: Path,
    workspace_root: Path,
    include_dependency_modules: bool = True,
    build_reference_index: bool = True,
) -> SemanticSnapshot:
    resolved_entry_path = Path(entry_file).resolve()
    resolved_workspace_root = Path(workspace_root).resolve()
    return _build_semantic_snapshot(
        base_picture,
        entry_path=resolved_entry_path,
        workspace_root=resolved_workspace_root,
        project_graph=project_graph,
        include_dependency_modules=include_dependency_modules,
        build_reference_index=build_reference_index,
    )


__all__ = [
    "CallSignatureOccurrence",
    "SemanticSnapshot",
    "SymbolDefinition",
    "SymbolReference",
    "build_source_snapshot_from_basepicture",
    "load_source_snapshot",
]
