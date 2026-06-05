"""Internal semantic snapshot models and query helpers."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sattline_parser.models.ast_model import BasePicture, ModuleTypeDef, SourceSpan

from ..call_signatures import CallSignatureOccurrence
from ..models._variable_issues import VariableIssue
from ..models.project_graph import ProjectGraph
from ..resolution import CanonicalSymbolTable, TypeGraph
from ..resolution.access_graph import AccessEvent
from ..resolution.common import resolve_module_by_strict_path
from ._semantic_helpers import (
    cf,
    child_module_items,
    identifier_contains_column,
    path_startswith,
    source_file_key,
)
from .diagnostics import DroppedDiagnosticIssue, SemanticDiagnostic
from .safety_paths import (
    DEFAULT_SAFETY_SIGNAL_KEYWORDS,
    SafetyPathTrace,
    SymbolAccess,
    build_safety_path_traces,
    build_symbol_accesses,
)
from .taint_paths import TaintPathTrace, build_taint_path_traces
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

DefinitionKey = tuple[str, ...]
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

    def list_symbols(
        self, query: str = "", *, roots_only: bool = False, limit: int | None = None
    ) -> list[SymbolDefinition]:
        needle = query.strip().casefold()
        matches: list[SymbolDefinition] = []
        for definition in self.definitions:
            if roots_only and definition.field_path is not None:
                continue
            if needle and needle not in definition.canonical_path.casefold():
                continue
            matches.append(definition)
        if limit is not None:
            return matches[:limit]
        return matches

    def find_definitions(self, query: str, *, limit: int | None = None) -> list[SymbolDefinition]:
        raw = query.strip()
        if not raw:
            return []

        segments = tuple(segment for segment in raw.split(".") if segment)
        key = tuple(cf(segment) for segment in segments)

        direct = self._definitions_by_key.get(key)
        if direct is not None:
            return [direct]

        matches: list[tuple[int, int, SymbolDefinition]] = []
        for definition in self.definitions:
            definition_key = tuple(cf(segment) for segment in definition.canonical_path.split("."))
            if segments and definition_key[-len(key) :] == key:
                matches.append((len(key), len(definition_key), definition))
            elif len(key) == 1 and definition_key[-1] == key[0]:
                matches.append((1, len(definition_key), definition))

        matches.sort(key=lambda item: (-item[0], item[1], item[2].canonical_path.casefold()))
        results = [item[2] for item in matches]
        if limit is not None:
            return results[:limit]
        return results

    def find_definitions_at(
        self,
        source_file: Path | str,
        line: int,
        column: int,
    ) -> list[SymbolDefinition]:
        file_key = source_file_key(source_file)
        if file_key is None:
            return []

        matches: list[SymbolDefinition] = []
        seen: set[tuple[str, ...]] = set()
        for occurrence in self._references_by_file.get(file_key, ()):
            if not occurrence.matches(line, column):
                continue
            definition_key = occurrence.definition_key_for_column(column)
            definition = self._definitions_by_key.get(definition_key)
            root_definition_key = occurrence.definition_keys[0]
            if definition is None and definition_key != root_definition_key:
                definition = self._definitions_by_key.get(root_definition_key)
                definition_key = root_definition_key
            if definition is None or definition_key in seen:
                continue
            seen.add(definition_key)
            matches.append(definition)
        return matches

    def find_references_to(
        self,
        query: str | SymbolDefinition,
        *,
        limit: int | None = None,
    ) -> list[SymbolReference]:
        if isinstance(query, SymbolDefinition):
            definition_key = tuple(cf(segment) for segment in query.canonical_path.split("."))
        else:
            definitions = self.find_definitions(query, limit=1)
            if not definitions:
                return []
            definition_key = tuple(cf(segment) for segment in definitions[0].canonical_path.split("."))

        references = list(self._references_by_definition_key.get(definition_key, ()))
        if limit is not None:
            return references[:limit]
        return references

    def find_accesses_to(
        self,
        query: str | SymbolDefinition,
        *,
        limit: int | None = None,
    ) -> list[SymbolAccess]:
        if isinstance(query, SymbolDefinition):
            definition_key = tuple(cf(segment) for segment in query.canonical_path.split("."))
        else:
            definitions = self.find_definitions(query, limit=1)
            if not definitions:
                return []
            definition_key = tuple(cf(segment) for segment in definitions[0].canonical_path.split("."))

        accesses = list(build_symbol_accesses(self._accesses_by_definition_key.get(definition_key, ())))
        if limit is not None:
            return accesses[:limit]
        return accesses

    def iter_access_events_by_definition(
        self,
        *,
        roots_only: bool = False,
    ) -> Iterator[tuple[SymbolDefinition, tuple[AccessEvent, ...]]]:
        for definition in self.definitions:
            if roots_only and definition.field_path is not None:
                continue
            definition_key = tuple(cf(segment) for segment in definition.canonical_path.split("."))
            yield definition, self._accesses_by_definition_key.get(definition_key, ())

    def find_safety_paths(
        self,
        query: str = "",
        *,
        limit: int | None = None,
        keywords: tuple[str, ...] = DEFAULT_SAFETY_SIGNAL_KEYWORDS,
    ) -> list[SafetyPathTrace]:
        return build_safety_path_traces(
            self._accesses_by_definition_key,
            query=query,
            limit=limit,
            keywords=keywords,
        )

    def find_taint_paths(
        self,
        query: str = "",
        *,
        limit: int | None = None,
    ) -> list[TaintPathTrace]:
        return build_taint_path_traces(
            self._effect_flow_edges,
            self._accesses_by_definition_key,
            query=query,
            limit=limit,
            display_names_by_key=self._effect_flow_display_names,
        )

    def find_references_at(
        self,
        source_file: Path | str,
        line: int,
        column: int,
        *,
        limit: int | None = None,
    ) -> list[SymbolReference]:
        definitions = self.find_definitions_at(source_file, line, column)
        if not definitions:
            return []

        matches: list[SymbolReference] = []
        seen: set[tuple[str, str | None, str | None, int, int, int]] = set()
        for definition in definitions:
            for reference in self.find_references_to(definition):
                key = (
                    reference.canonical_path.casefold(),
                    reference.source_file.casefold() if reference.source_file is not None else None,
                    reference.source_library.casefold() if reference.source_library is not None else None,
                    reference.line,
                    reference.column,
                    reference.length,
                )
                if key in seen:
                    continue
                seen.add(key)
                matches.append(reference)
                if limit is not None and len(matches) >= limit:
                    return matches
        return matches

    def semantic_diagnostics_for_path(
        self,
        source_path: Path | str,
    ) -> tuple[SemanticDiagnostic, ...]:
        path = Path(str(source_path))
        file_key = path.name.casefold()
        candidates = self._semantic_diagnostics_by_file.get(file_key, ())
        if not candidates:
            return ()

        library_key = path.parent.name.casefold()
        exact_matches = tuple(
            candidate
            for candidate in candidates
            if candidate.source_library is not None and candidate.source_library.casefold() == library_key
        )
        if exact_matches:
            return exact_matches

        unscoped = tuple(candidate for candidate in candidates if candidate.source_library is None)
        if unscoped:
            return unscoped

        if len(candidates) == 1:
            return candidates
        return ()

    def semantic_diagnostic_drops(self) -> tuple[DroppedDiagnosticIssue, ...]:
        return self._semantic_diagnostic_drops

    def to_snapshot_dict(self) -> dict[str, Any]:
        """Serialize symbol resolution state for invariant verification."""
        return {
            "entry_file": str(self.entry_file),
            "workspace_root": str(self.workspace_root),
            "definitions": [
                {
                    "canonical_path": d.canonical_path,
                    "kind": d.kind,
                    "datatype": d.datatype,
                    "declaration_module_path": list(d.declaration_module_path),
                    "display_module_path": list(d.display_module_path),
                    "field_path": d.field_path,
                    "source_file": d.source_file,
                    "source_library": d.source_library,
                }
                for d in self.definitions
            ],
            "call_signatures": [
                {
                    "name": c.name,
                    "call_kind": c.call_kind,
                    "module_path": list(c.module_path),
                    "source_file": c.source_file,
                    "source_library": c.source_library,
                }
                for c in self.call_signatures
            ],
        }

    def find_call_signatures(
        self,
        query: str = "",
        *,
        source_path: Path | str | None = None,
        limit: int | None = None,
    ) -> list[CallSignatureOccurrence]:
        needle = query.strip().casefold()
        file_key = source_file_key(source_path) if source_path is not None else None
        library_key = None
        if source_path is not None:
            source = Path(str(source_path))
            library_key = source.parent.name.casefold()

        matches: list[CallSignatureOccurrence] = []
        for occurrence in self.call_signatures:
            if needle and occurrence.name.casefold() != needle:
                continue
            if file_key is not None and source_file_key(occurrence.source_file) != file_key:
                continue
            if (
                library_key is not None
                and occurrence.source_library is not None
                and occurrence.source_library.casefold() != library_key
            ):
                continue
            matches.append(occurrence)
        if limit is not None:
            return matches[:limit]
        return matches

    def complete(
        self,
        prefix: str = "",
        *,
        module_path: str | None = None,
        limit: int | None = None,
    ) -> list[CompletionItem]:
        prefix_cf = prefix.casefold()
        if module_path:
            try:
                resolved = resolve_module_by_strict_path(
                    self.base_picture,
                    module_path,
                    moduletype_index=self._moduletype_index,
                )
                visible_path = tuple(resolved.path)
                current_node: Any | None = resolved.node
            except ValueError:
                visible_path = tuple(segment for segment in module_path.split(".") if segment)
                if visible_path and cf(visible_path[0]) == cf(self.base_picture.header.name):
                    visible_path = visible_path[1:]
                current_node = None
        else:
            visible_path = (self.base_picture.header.name,)
            current_node = self.base_picture

        items_by_label: dict[str, CompletionItem] = {}

        for definition in self.definitions:
            if definition.field_path is not None:
                continue
            if not path_startswith(visible_path, definition.declaration_module_path):
                continue
            if prefix_cf and not definition.canonical_path.split(".")[-1].casefold().startswith(prefix_cf):
                continue

            label = definition.canonical_path.split(".")[-1]
            existing = items_by_label.get(label.casefold())
            current = CompletionItem(
                label=label,
                kind=definition.kind,
                detail=definition.datatype,
                declaration_module_path=definition.declaration_module_path,
            )
            if existing is None or len(current.declaration_module_path) > len(existing.declaration_module_path):
                items_by_label[label.casefold()] = current

        if current_node is not None:
            for child_name, child_kind in child_module_items(
                self.base_picture,
                current_node,
                self._moduletype_index,
                self.project_graph.unavailable_libraries,
            ):
                if prefix_cf and not child_name.casefold().startswith(prefix_cf):
                    continue
                items_by_label.setdefault(
                    child_name.casefold(),
                    CompletionItem(label=child_name, kind=child_kind, detail=None),
                )

        items = sorted(
            items_by_label.values(),
            key=lambda item: (item.label.casefold(), item.kind),
        )
        if limit is not None:
            return items[:limit]
        return items
