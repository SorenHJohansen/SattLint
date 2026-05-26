"""Canonical shared semantic query and loading helpers."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from sattline_parser import parse_source_text as parser_core_parse_source_text
from sattline_parser.models.ast_model import BasePicture

from ..call_signatures import CallSignatureOccurrence
from ..engine import CodeMode, SattLineProjectLoader, merge_project_basepicture
from ..models.project_graph import ProjectGraph
from . import _semantic_helpers as _semantic_helpers
from . import workspace_discovery as _workspace_discovery
from ._semantic_index import SemanticIndexBuilder
from ._semantic_snapshot import (
    CompletionItem,
    SemanticAnalysisArtifacts,
    SemanticAnalysisProvider,
    SemanticSnapshot,
    SymbolDefinition,
    SymbolReference,
)
from .diagnostics import SemanticDiagnostic
from .safety_paths import DEFAULT_SAFETY_SIGNAL_KEYWORDS, SafetyPathTrace, SymbolAccess
from .taint_paths import TaintPathTrace
from .workspace_discovery import WorkspaceSourceDiscovery, discover_workspace_sources, single_entry_discovery

_cf = _semantic_helpers.cf
_format_datatype = _semantic_helpers.format_datatype
_format_name_list = _semantic_helpers.format_name_list
_format_workspace_snapshot_failure = _semantic_helpers.format_workspace_snapshot_failure
_identifier_contains_column = _semantic_helpers.identifier_contains_column
_normalize_mode = _semantic_helpers.normalize_mode
_path_startswith = _semantic_helpers.path_startswith
_source_file_key = _semantic_helpers.source_file_key
_first_branch_under = _workspace_discovery.first_branch_under
_resolved_path = _workspace_discovery.resolved_path


class WorkspaceSnapshotError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        line: int | None = None,
        column: int | None = None,
        length: int | None = None,
    ):
        super().__init__(message)
        self.line = line
        self.column = column
        self.length = length


def _build_lsp_workspace_lookup(
    discovery: WorkspaceSourceDiscovery,
) -> Callable[[str, list[str], Path | None, str], Path | None]:
    def lookup(name: str, extensions: list[str], requester_dir: Path | None, kind: str) -> Path | None:
        candidate = discovery.locate_source_file(
            name,
            extensions=extensions,
            requester_dir=requester_dir,
        )
        return candidate

    return lookup


def _build_semantic_snapshot(
    base_picture: BasePicture,
    *,
    entry_path: Path,
    workspace_root: Path,
    discovery: WorkspaceSourceDiscovery,
    project_graph: ProjectGraph,
    collect_variable_diagnostics: bool,
    debug: bool,
    analysis_provider: SemanticAnalysisProvider | None = None,
) -> SemanticSnapshot:
    builder = SemanticIndexBuilder(
        base_picture,
        unavailable_libraries=project_graph.unavailable_libraries,
    )
    builder_result = builder.build()
    symbol_table = builder_result[0]
    type_graph = builder_result[1]
    definitions = builder_result[2]
    definitions_by_key = builder_result[3]
    moduletype_index = builder_result[4]
    references_by_file = builder_result[5]
    references_by_definition_key = builder_result[6]
    call_signatures = builder_result[7]

    analysis = SemanticAnalysisArtifacts()
    if analysis_provider is not None:
        analysis = analysis_provider(
            base_picture,
            project_graph,
            collect_variable_diagnostics,
            debug,
            definitions_by_key,
        )

    return SemanticSnapshot(
        workspace_root=workspace_root,
        entry_file=entry_path,
        discovery=discovery,
        base_picture=base_picture,
        project_graph=project_graph,
        symbol_table=symbol_table,
        type_graph=type_graph,
        definitions=definitions,
        diagnostics=analysis.diagnostics,
        call_signatures=call_signatures,
        _definitions_by_key=definitions_by_key,
        _moduletype_index=moduletype_index,
        _references_by_file=references_by_file,
        _references_by_definition_key=references_by_definition_key,
        _accesses_by_definition_key=analysis.accesses_by_definition_key,
        _effect_flow_edges=analysis.effect_flow_edges,
        _effect_flow_display_names=analysis.effect_flow_display_names,
        _semantic_diagnostics_by_file=analysis.semantic_diagnostics_by_file,
        _semantic_diagnostic_drops=analysis.semantic_diagnostic_drops,
    )


def load_source_snapshot(
    source_file: Path,
    source_text: str,
    *,
    workspace_root: Path | None = None,
    collect_variable_diagnostics: bool = False,
    debug: bool = False,
    _analysis_provider: SemanticAnalysisProvider | None = None,
) -> SemanticSnapshot:
    base_picture = parser_core_parse_source_text(source_text, debug=(print if debug else None))
    return build_source_snapshot_from_basepicture(
        base_picture,
        source_file,
        workspace_root=workspace_root,
        collect_variable_diagnostics=collect_variable_diagnostics,
        debug=debug,
        _analysis_provider=_analysis_provider,
    )


def build_source_snapshot_from_basepicture(
    base_picture: BasePicture,
    source_file: Path,
    *,
    workspace_root: Path | None = None,
    collect_variable_diagnostics: bool = False,
    debug: bool = False,
    _analysis_provider: SemanticAnalysisProvider | None = None,
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
        collect_variable_diagnostics=collect_variable_diagnostics,
        debug=debug,
        analysis_provider=_analysis_provider,
    )


def load_workspace_snapshot(
    entry_file: Path,
    *,
    workspace_root: Path | None = None,
    discovery: WorkspaceSourceDiscovery | None = None,
    mode: CodeMode | str = CodeMode.DRAFT,
    other_lib_dirs: list[Path] | None = None,
    abb_lib_dir: Path | None = None,
    scan_root_only: bool = False,
    debug: bool = False,
    collect_variable_diagnostics: bool = True,
    _analysis_provider: SemanticAnalysisProvider | None = None,
) -> SemanticSnapshot:
    entry_path = Path(entry_file).resolve()
    if not entry_path.exists():
        raise FileNotFoundError(f"Entry file does not exist: {entry_path}")

    root = Path(workspace_root).resolve() if workspace_root else entry_path.parent
    resolved_discovery = discovery or discover_workspace_sources(root)
    normalized_mode = _normalize_mode(mode)
    selected_other_lib_dirs = (
        list(other_lib_dirs) if other_lib_dirs is not None else list(resolved_discovery.other_lib_dirs_for(entry_path))
    )
    selected_abb_lib_dir = abb_lib_dir or resolved_discovery.abb_lib_dir or (root / "__missing_abb_lib__")

    loader = SattLineProjectLoader(
        program_dir=entry_path.parent,
        other_lib_dirs=selected_other_lib_dirs,
        abb_lib_dir=selected_abb_lib_dir,
        mode=normalized_mode,
        scan_root_only=scan_root_only,
        debug=debug,
        contextual_lookup=_build_lsp_workspace_lookup(resolved_discovery),
    )

    graph = loader.resolve(entry_path.stem, strict=False)
    root_bp = graph.ast_by_name.get(entry_path.stem)
    if root_bp is None:
        target_prefix = f"{entry_path.stem} parse/transform error:"
        target_failure = next(
            (message for message in graph.missing if message.casefold().startswith(target_prefix.casefold())),
            None,
        )
        if target_failure is not None:
            detail = target_failure[len(target_prefix) :].strip()
            failure = graph.failures.get(entry_path.stem.casefold())
            raise WorkspaceSnapshotError(
                _format_workspace_snapshot_failure(entry_path.stem, graph, detail=detail),
                line=failure.line if failure is not None else None,
                column=failure.column if failure is not None else None,
                length=failure.length if failure is not None else None,
            )
        raise WorkspaceSnapshotError(_format_workspace_snapshot_failure(entry_path.stem, graph))

    project_bp = merge_project_basepicture(root_bp, graph)

    return _build_semantic_snapshot(
        project_bp,
        entry_path=entry_path,
        workspace_root=root,
        discovery=resolved_discovery,
        project_graph=graph,
        collect_variable_diagnostics=collect_variable_diagnostics,
        debug=debug,
        analysis_provider=_analysis_provider,
    )


__all__ = [
    "DEFAULT_SAFETY_SIGNAL_KEYWORDS",
    "CallSignatureOccurrence",
    "CompletionItem",
    "SafetyPathTrace",
    "SemanticAnalysisArtifacts",
    "SemanticAnalysisProvider",
    "SemanticDiagnostic",
    "SemanticSnapshot",
    "SymbolAccess",
    "SymbolDefinition",
    "SymbolReference",
    "TaintPathTrace",
    "WorkspaceSnapshotError",
    "WorkspaceSourceDiscovery",
    "build_source_snapshot_from_basepicture",
    "discover_workspace_sources",
    "load_source_snapshot",
    "load_workspace_snapshot",
]
