"""Internal semantic snapshot model types and default factories."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from sattline_parser.models.ast_model import BasePicture, ModuleTypeDef, SourceSpan

from ..call_signatures import CallSignatureOccurrence
from ..models._variable_issues import VariableIssue
from ..models.project_graph import ProjectGraph
from ..resolution import CanonicalPathKey, CanonicalSymbolTable, TypeGraph
from ..resolution.access_graph import AccessEvent
from ._semantic_helpers import identifier_contains_column
from .diagnostics import DroppedDiagnosticIssue, SemanticDiagnostic
from .workspace_discovery import WorkspaceSourceDiscovery


@dataclass(frozen=True, slots=True)
class SymbolDefinition:
    canonical_path: str
    kind: str
    datatype: str | None
    declaration_module_path: tuple[str, ...]
    display_module_path: tuple[str, ...]
    field_path: str | None = None
    source_file: str | None = None
    source_library: str | None = None
    declaration_span: SourceSpan | None = None


@dataclass(frozen=True, slots=True)
class SymbolReference:
    canonical_path: str
    source_file: str | None
    source_library: str | None
    line: int
    column: int
    length: int
    text: str


@dataclass(frozen=True, slots=True)
class _ReferenceOccurrence:
    line: int
    column: int
    text: str
    source_file: str | None
    source_library: str | None
    segment_texts: tuple[str, ...]
    definition_keys: tuple[tuple[str, ...], ...]

    def matches(self, line: int, column: int) -> bool:
        return self.line == line and identifier_contains_column(self.column, self.text, column)

    def definition_key_for_column(self, column: int) -> tuple[str, ...]:
        current_column = self.column
        for segment_text, definition_key in zip(self.segment_texts, self.definition_keys, strict=False):
            segment_end = current_column + len(segment_text) - 1
            if current_column <= column <= segment_end:
                return definition_key
            current_column = segment_end + 2
        return self.definition_keys[-1]

    def reference_for_definition_key(self, definition_key: tuple[str, ...]) -> SymbolReference | None:
        current_column = self.column
        for segment_text, candidate_key in zip(self.segment_texts, self.definition_keys, strict=False):
            if candidate_key == definition_key:
                return SymbolReference(
                    canonical_path=".".join(definition_key),
                    source_file=self.source_file,
                    source_library=self.source_library,
                    line=self.line,
                    column=current_column,
                    length=len(segment_text),
                    text=segment_text,
                )
            current_column += len(segment_text) + 1
        return None


ReferenceOccurrence = _ReferenceOccurrence

DefinitionKey = CanonicalPathKey
ReferencesByFile = dict[str, tuple[ReferenceOccurrence, ...]]
ReferencesByDefinitionKey = dict[DefinitionKey, tuple[SymbolReference, ...]]
AccessesByDefinitionKey = dict[DefinitionKey, tuple[AccessEvent, ...]]
EffectFlowEdges = dict[DefinitionKey, tuple[DefinitionKey, ...]]
EffectFlowDisplayNames = dict[DefinitionKey, str]
SemanticDiagnosticsByFile = dict[str, tuple[SemanticDiagnostic, ...]]


def _accesses_by_definition_key_factory() -> AccessesByDefinitionKey:
    return {}


def _effect_flow_display_names_factory() -> EffectFlowDisplayNames:
    return {}


def _effect_flow_edges_factory() -> EffectFlowEdges:
    return {}


def _moduletype_index_factory() -> dict[str, list[ModuleTypeDef]]:
    return {}


def _references_by_definition_key_factory() -> ReferencesByDefinitionKey:
    return {}


def _references_by_file_factory() -> ReferencesByFile:
    return {}


def _semantic_diagnostics_by_file_factory() -> SemanticDiagnosticsByFile:
    return {}


def _semantic_diagnostic_drops_factory() -> tuple[DroppedDiagnosticIssue, ...]:
    return ()


def _symbol_definition_map_factory() -> dict[DefinitionKey, SymbolDefinition]:
    return {}


@dataclass(frozen=True, slots=True)
class CompletionItem:
    label: str
    kind: str
    detail: str | None = None
    declaration_module_path: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SemanticAnalysisArtifacts:
    diagnostics: tuple[VariableIssue, ...] = ()
    accesses_by_definition_key: AccessesByDefinitionKey = field(default_factory=_accesses_by_definition_key_factory)
    effect_flow_edges: EffectFlowEdges = field(default_factory=_effect_flow_edges_factory)
    effect_flow_display_names: EffectFlowDisplayNames = field(default_factory=_effect_flow_display_names_factory)
    semantic_diagnostics_by_file: SemanticDiagnosticsByFile = field(
        default_factory=_semantic_diagnostics_by_file_factory
    )
    semantic_diagnostic_drops: tuple[DroppedDiagnosticIssue, ...] = field(
        default_factory=_semantic_diagnostic_drops_factory
    )


SemanticAnalysisProvider = Callable[
    [BasePicture, ProjectGraph, bool, bool, dict[DefinitionKey, SymbolDefinition]],
    SemanticAnalysisArtifacts,
]


@dataclass(frozen=True, slots=True)
class SemanticSnapshot:
    """Frozen query facade over semantic indexes.

    The container itself is immutable, but nested helper structures such as
    `symbol_table` and `type_graph` are build artifacts that callers should
    treat as read-only after construction.
    """

    workspace_root: Path
    entry_file: Path
    discovery: WorkspaceSourceDiscovery
    base_picture: BasePicture
    project_graph: ProjectGraph
    symbol_table: CanonicalSymbolTable
    type_graph: TypeGraph
    definitions: tuple[SymbolDefinition, ...]
    diagnostics: tuple[VariableIssue, ...] = ()
    call_signatures: tuple[CallSignatureOccurrence, ...] = ()
    _definitions_by_key: dict[DefinitionKey, SymbolDefinition] = field(
        default_factory=_symbol_definition_map_factory,
        repr=False,
        compare=False,
    )
    _moduletype_index: dict[str, list[ModuleTypeDef]] = field(
        default_factory=_moduletype_index_factory,
        repr=False,
        compare=False,
    )
    _references_by_file: ReferencesByFile = field(
        default_factory=_references_by_file_factory,
        repr=False,
        compare=False,
    )
    _references_by_definition_key: ReferencesByDefinitionKey = field(
        default_factory=_references_by_definition_key_factory,
        repr=False,
        compare=False,
    )
    _accesses_by_definition_key: AccessesByDefinitionKey = field(
        default_factory=_accesses_by_definition_key_factory,
        repr=False,
        compare=False,
    )
    _effect_flow_edges: EffectFlowEdges = field(
        default_factory=_effect_flow_edges_factory,
        repr=False,
        compare=False,
    )
    _effect_flow_display_names: EffectFlowDisplayNames = field(
        default_factory=_effect_flow_display_names_factory,
        repr=False,
        compare=False,
    )
    _semantic_diagnostics_by_file: SemanticDiagnosticsByFile = field(
        default_factory=_semantic_diagnostics_by_file_factory,
        repr=False,
        compare=False,
    )
    _semantic_diagnostic_drops: tuple[DroppedDiagnosticIssue, ...] = field(
        default_factory=_semantic_diagnostic_drops_factory,
        repr=False,
        compare=False,
    )
