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

from sattline_parser import parse_source_text as parser_core_parse_source_text
from sattline_parser.models.ast_model import BasePicture

from ..models.project_graph import ProjectGraph
from ._semantic_index import SemanticIndexBuilder
from ._semantic_snapshot import SemanticSnapshot, SymbolDefinition, SymbolReference
from .call_signatures import CallSignatureOccurrence
from .workspace_discovery import WorkspaceSourceDiscovery, single_entry_discovery

log = logging.getLogger("SattLint")


def _string_attr(value: object, attr_name: str) -> str | None:
    raw = getattr(value, attr_name, None)
    if isinstance(raw, str):
        normalized = raw.strip()
        return normalized or None
    return None


def _emit_parser_debug(message: str) -> None:
    log.debug("Semantic snapshot parser: %s", message)


def _build_semantic_snapshot(
    base_picture: BasePicture,
    *,
    entry_path: Path,
    workspace_root: Path,
    discovery: WorkspaceSourceDiscovery,
    project_graph: ProjectGraph,
    debug: bool,
) -> SemanticSnapshot:
    root_origin_for_basepicture = getattr(project_graph, "root_origin_for_basepicture", None)
    root_origin = root_origin_for_basepicture(base_picture) if callable(root_origin_for_basepicture) else None
    root_origin_file = (
        _string_attr(root_origin, "origin_file")
        if root_origin is not None
        else getattr(base_picture, "origin_file", None)
    )
    root_origin_library = (
        _string_attr(root_origin, "library_name")
        if root_origin is not None
        else getattr(base_picture, "origin_lib", None)
    )
    try:
        builder = SemanticIndexBuilder(
            base_picture,
            root_origin_file=root_origin_file,
            root_origin_library=root_origin_library,
            unavailable_libraries=project_graph.unavailable_libraries,
        )
    except TypeError as exc:
        if "unexpected keyword argument" not in str(exc):
            raise
        builder = SemanticIndexBuilder(
            base_picture,
            unavailable_libraries=project_graph.unavailable_libraries,
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
        discovery=discovery,
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
    base_picture = parser_core_parse_source_text(source_text, debug=(_emit_parser_debug if debug else None))
    return build_source_snapshot_from_basepicture(
        base_picture,
        source_file,
        workspace_root=workspace_root,
        debug=debug,
    )


def build_source_snapshot_from_basepicture(
    base_picture: BasePicture,
    source_file: Path,
    *,
    workspace_root: Path | None = None,
    debug: bool = False,
) -> SemanticSnapshot:
    entry_path = Path(source_file).resolve()
    root = Path(workspace_root).resolve() if workspace_root else entry_path.parent
    discovery = single_entry_discovery(entry_path, root)

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
        discovery=discovery,
        project_graph=project_graph,
        debug=debug,
    )


def build_snapshot_from_loaded_project(
    base_picture: BasePicture,
    project_graph: ProjectGraph,
    *,
    entry_file: Path,
    workspace_root: Path,
    debug: bool = False,
) -> SemanticSnapshot:
    resolved_entry_path = Path(entry_file).resolve()
    resolved_workspace_root = Path(workspace_root).resolve()
    discovery = single_entry_discovery(resolved_entry_path, resolved_workspace_root)
    return _build_semantic_snapshot(
        base_picture,
        entry_path=resolved_entry_path,
        workspace_root=resolved_workspace_root,
        discovery=discovery,
        project_graph=project_graph,
        debug=debug,
    )


__all__ = [
    "CallSignatureOccurrence",
    "SemanticSnapshot",
    "SymbolDefinition",
    "SymbolReference",
    "WorkspaceSourceDiscovery",
    "build_source_snapshot_from_basepicture",
    "load_source_snapshot",
]
