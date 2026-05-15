"""Symbol resolution and semantic-diagnostics helpers for the LSP server."""

from __future__ import annotations

import logging
import re
from pathlib import Path

from lsprotocol.types import CompletionItem as LspCompletionItem
from lsprotocol.types import CompletionItemKind, Diagnostic, DiagnosticSeverity, Location
from pygls import uris

from sattline_parser.models.ast_model import Simple_DataType
from sattlint.core.semantic import SemanticSnapshot, SymbolDefinition, SymbolReference

from . import _server_helpers as _base_helpers
from ._server_helpers import (
    _DEFAULT_MAX_COMPLETION_ITEMS,
    _NAME_PATTERN,
    _RECOVERABLE_LSP_EXCEPTIONS,
    _cf,
    _path_startswith,
    _range_for_definition,
    _range_from_position,
    infer_module_path_from_source,
)
from .workspace_store import SnapshotBundle

_REFERENCE_EXPR_RE = re.compile(rf"{_NAME_PATTERN}(?:\.{_NAME_PATTERN})*")
_BASE_COMPLETION_RE = re.compile(rf"(?P<base>{_NAME_PATTERN}(?:\.{_NAME_PATTERN})*)\.(?P<prefix>{_NAME_PATTERN})?$")
_IDENTIFIER_PREFIX_RE = re.compile(rf"(?P<prefix>{_NAME_PATTERN})$")
log = logging.getLogger(__name__)


def _filter_visible_definitions(
    definitions: list[SymbolDefinition],
    module_path: str | None,
) -> list[SymbolDefinition]:
    if not module_path:
        return definitions
    current_path = tuple(segment for segment in module_path.split(".") if segment)
    visible = [
        definition for definition in definitions if _path_startswith(current_path, definition.declaration_module_path)
    ]
    if not visible:
        return definitions
    visible.sort(
        key=lambda definition: (-len(definition.declaration_module_path), definition.canonical_path.casefold())
    )
    return visible


def _reference_expr_at_position(source_text: str, *, line: int, column: int) -> str | None:
    lines = source_text.splitlines()
    if line < 0 or line >= len(lines):
        return None

    current_line = lines[line]
    for match in _REFERENCE_EXPR_RE.finditer(current_line):
        if match.start() <= column < match.end():
            return match.group(0)
    return None


def _semantic_completion_kind(kind: str) -> CompletionItemKind:
    if kind in {"local", "parameter"}:
        return CompletionItemKind.Variable
    if kind == "field":
        return CompletionItemKind.Field
    if kind in {"module", "frame", "moduletype-instance"}:
        return CompletionItemKind.Module
    return CompletionItemKind.Text


def collect_completion_candidates(
    snapshot: SemanticSnapshot,
    source_text: str,
    *,
    line: int,
    column: int,
    limit: int = _DEFAULT_MAX_COMPLETION_ITEMS,
) -> list[LspCompletionItem]:
    lines = source_text.splitlines()
    current_line = lines[line] if 0 <= line < len(lines) else ""
    line_prefix = current_line[:column]
    module_path = infer_module_path_from_source(source_text, line)

    dotted_match = _BASE_COMPLETION_RE.search(line_prefix)
    if dotted_match:
        base_expr = dotted_match.group("base")
        prefix = dotted_match.group("prefix") or ""
        items_by_label: dict[str, LspCompletionItem] = {}
        for definition in _filter_visible_definitions(snapshot.find_definitions(base_expr), module_path):
            datatype = definition.datatype
            if datatype is None:
                continue
            record = snapshot.type_graph.record(datatype)
            if record is None:
                continue
            for field in sorted(record.fields_by_key.values(), key=lambda item: item.name.casefold()):
                if prefix and not field.name.casefold().startswith(prefix.casefold()):
                    continue
                items_by_label.setdefault(
                    field.name.casefold(),
                    LspCompletionItem(
                        label=field.name,
                        kind=CompletionItemKind.Field,
                        detail=str(
                            field.datatype.value if isinstance(field.datatype, Simple_DataType) else field.datatype
                        ),
                    ),
                )
        return list(items_by_label.values())[:limit]

    prefix_match = _IDENTIFIER_PREFIX_RE.search(line_prefix)
    prefix = prefix_match.group("prefix") if prefix_match else ""
    semantic_items = snapshot.complete(prefix=prefix, module_path=module_path, limit=limit)
    return [
        LspCompletionItem(
            label=item.label,
            kind=_semantic_completion_kind(item.kind),
            detail=item.detail,
        )
        for item in semantic_items
    ]


def _resolve_bundle_source_path(
    bundle: SnapshotBundle, source_file: str | None, source_library: str | None
) -> Path | None:
    if not source_file:
        return None
    file_key = source_file.casefold()
    library_key = (source_library or "").casefold()
    direct = bundle.source_paths_by_key.get((file_key, library_key))
    if direct is not None:
        return direct
    candidates = bundle.source_paths_by_name.get(file_key, ())
    if len(candidates) == 1:
        return candidates[0]
    return None


def resolve_definition_path(bundle: SnapshotBundle, definition: SymbolDefinition) -> Path | None:
    return _resolve_bundle_source_path(bundle, definition.source_file, definition.source_library)


def _resolve_reference_path(bundle: SnapshotBundle, reference: SymbolReference) -> Path | None:
    return _resolve_bundle_source_path(bundle, reference.source_file, reference.source_library)


def _definition_key(definition: SymbolDefinition) -> tuple[str, ...]:
    return tuple(_cf(segment) for segment in definition.canonical_path.split("."))


def _merge_definitions(
    preferred: list[SymbolDefinition],
    fallback: list[SymbolDefinition],
) -> list[SymbolDefinition]:
    merged: list[SymbolDefinition] = []
    seen: set[tuple[str, ...]] = set()
    for definition in [*preferred, *fallback]:
        key = _definition_key(definition)
        if key in seen:
            continue
        seen.add(key)
        merged.append(definition)
    return merged


def _merge_completion_items(
    preferred: list[LspCompletionItem],
    fallback: list[LspCompletionItem],
    *,
    limit: int,
) -> list[LspCompletionItem]:
    def kind_value(item: LspCompletionItem) -> int:
        return int(item.kind) if item.kind is not None else 0

    items_by_label: dict[tuple[str, int], LspCompletionItem] = {}
    for item in [*preferred, *fallback]:
        key = (item.label.casefold(), kind_value(item))
        items_by_label.setdefault(key, item)
    merged = sorted(items_by_label.values(), key=lambda item: (item.label.casefold(), kind_value(item)))
    return merged[:limit]


def _reference_signature(reference: SymbolReference) -> tuple[str, str | None, str | None, int, int, int]:
    return (
        reference.canonical_path.casefold(),
        reference.source_file.casefold() if reference.source_file is not None else None,
        reference.source_library.casefold() if reference.source_library is not None else None,
        reference.line,
        reference.column,
        reference.length,
    )


def _merge_references(
    preferred: list[SymbolReference],
    fallback: list[SymbolReference],
) -> list[SymbolReference]:
    merged: list[SymbolReference] = []
    seen: set[tuple[str, str | None, str | None, int, int, int]] = set()
    for reference in [*preferred, *fallback]:
        signature = _reference_signature(reference)
        if signature in seen:
            continue
        seen.add(signature)
        merged.append(reference)
    return merged


def _definition_locations_from_candidates(
    candidates: list[SymbolDefinition],
    *,
    bundle: SnapshotBundle,
    local_snapshot: SemanticSnapshot | None,
    active_document_path: Path,
) -> list[Location]:
    locations: list[Location] = []
    active_name = active_document_path.name.casefold()
    active_uri = uris.from_fs_path(str(active_document_path.resolve())) or active_document_path.resolve().as_uri()

    for definition in candidates:
        target_range = _range_for_definition(definition)
        if target_range is None:
            continue

        target_uri: str | None = None
        if local_snapshot is not None and (definition.source_file or "").casefold() == active_name:
            target_uri = active_uri
        else:
            target_path = resolve_definition_path(bundle, definition)
            if target_path is not None:
                target_uri = uris.from_fs_path(str(target_path)) or target_path.as_uri()

        if target_uri is None:
            continue
        locations.append(Location(uri=target_uri, range=target_range))
    return locations


def _reference_locations_from_matches(
    references: list[SymbolReference],
    *,
    bundle: SnapshotBundle | None,
    active_document_path: Path,
) -> list[Location]:
    locations: list[Location] = []
    active_uri = uris.from_fs_path(str(active_document_path.resolve())) or active_document_path.resolve().as_uri()
    active_name = active_document_path.name.casefold()

    for reference in references:
        target_uri: str | None = None
        if (reference.source_file or "").casefold() == active_name:
            target_uri = active_uri
        elif bundle is not None:
            target_path = _resolve_reference_path(bundle, reference)
            if target_path is not None:
                target_uri = uris.from_fs_path(str(target_path)) or target_path.as_uri()

        if target_uri is None:
            continue
        locations.append(
            Location(
                uri=target_uri,
                range=_range_from_position(reference.line, reference.column, reference.length),
            )
        )
    return locations


def _merge_locations(preferred: list[Location], fallback: list[Location]) -> list[Location]:
    merged: list[Location] = []
    seen: set[tuple[str, int, int, int, int]] = set()
    for location in [*preferred, *fallback]:
        key = (
            location.uri.casefold(),
            location.range.start.line,
            location.range.start.character,
            location.range.end.line,
            location.range.end.character,
        )
        if key in seen:
            continue
        seen.add(key)
        merged.append(location)
    return merged


def _overlay_definition_candidates(
    bundle: SnapshotBundle,
    *,
    document_path: Path,
    source_text: str,
    line: int,
    column: int,
    local_snapshot: SemanticSnapshot | None,
) -> list[SymbolDefinition]:
    module_path = infer_module_path_from_source(source_text, line)
    reference_expr = _reference_expr_at_position(source_text, line=line, column=column)
    if reference_expr:
        local_matches = []
        if local_snapshot is not None:
            local_matches = _filter_visible_definitions(local_snapshot.find_definitions(reference_expr), module_path)
        workspace_matches = _filter_visible_definitions(bundle.snapshot.find_definitions(reference_expr), module_path)
        merged = _merge_definitions(local_matches, workspace_matches)
        if merged:
            return merged

    workspace_at_cursor = bundle.snapshot.find_definitions_at(document_path, line + 1, column + 1)
    if local_snapshot is None:
        return workspace_at_cursor

    local_at_cursor = local_snapshot.find_definitions_at(document_path, line + 1, column + 1)
    return _merge_definitions(local_at_cursor, workspace_at_cursor)


def _local_definition_candidates(
    document_path: Path,
    source_text: str,
    *,
    line: int,
    column: int,
    snapshot: SemanticSnapshot | None,
) -> list[SymbolDefinition]:
    if snapshot is None:
        return []

    definitions = snapshot.find_definitions_at(document_path, line + 1, column + 1)
    if definitions:
        return definitions

    reference_expr = _reference_expr_at_position(source_text, line=line, column=column)
    if not reference_expr:
        return []
    return _filter_visible_definitions(
        snapshot.find_definitions(reference_expr),
        infer_module_path_from_source(source_text, line),
    )


def collect_local_definition_locations(
    document_path: Path,
    source_text: str,
    *,
    line: int,
    column: int,
    snapshot: SemanticSnapshot | None = None,
) -> list[Location]:
    local_snapshot = snapshot
    if local_snapshot is None:
        try:
            local_snapshot = _base_helpers.load_source_snapshot(
                document_path,
                source_text,
                _analysis_provider=_base_helpers.build_variable_semantic_artifacts,
            )
        except _RECOVERABLE_LSP_EXCEPTIONS as exc:
            log.warning(
                "LSP local-definition snapshot failed; fallback=empty path=%s error=%s",
                document_path,
                exc,
            )
            return []

    definitions = _local_definition_candidates(
        document_path,
        source_text,
        line=line,
        column=column,
        snapshot=local_snapshot,
    )
    if not definitions:
        return []

    document_uri = uris.from_fs_path(str(document_path.resolve())) or document_path.resolve().as_uri()
    locations: list[Location] = []
    for definition in definitions:
        target_range = _range_for_definition(definition)
        if target_range is None:
            continue
        locations.append(Location(uri=document_uri, range=target_range))
    return locations


def collect_local_completion_candidates(
    document_path: Path,
    source_text: str,
    *,
    line: int,
    column: int,
    limit: int = _DEFAULT_MAX_COMPLETION_ITEMS,
    snapshot: SemanticSnapshot | None = None,
) -> list[LspCompletionItem]:
    local_snapshot = snapshot
    if local_snapshot is None:
        try:
            local_snapshot = _base_helpers.load_source_snapshot(
                document_path,
                source_text,
                _analysis_provider=_base_helpers.build_variable_semantic_artifacts,
            )
        except _RECOVERABLE_LSP_EXCEPTIONS as exc:
            log.warning(
                "LSP completion snapshot failed; fallback=empty path=%s error=%s",
                document_path,
                exc,
            )
            return []

    return collect_completion_candidates(
        local_snapshot,
        source_text,
        line=line,
        column=column,
        limit=limit,
    )


def collect_semantic_diagnostics(bundle: SnapshotBundle, document_path: Path) -> list[Diagnostic]:
    return [
        Diagnostic(
            range=_range_from_position(item.line, item.column, item.length),
            message=item.message,
            severity=DiagnosticSeverity.Warning,
            source="sattlint",
            code=item.analyzer_key,
        )
        for item in bundle.snapshot.semantic_diagnostics_for_path(document_path.resolve())
    ]


def _semantic_diagnostics_for_path(bundle: SnapshotBundle, document_path: Path) -> tuple[Diagnostic, ...]:
    resolved_path = document_path.resolve()
    with bundle.semantic_diagnostics_lock:
        cached = bundle.semantic_diagnostics_by_path.get(resolved_path)
    if cached is not None:
        return cached

    diagnostics = tuple(collect_semantic_diagnostics(bundle, resolved_path))
    with bundle.semantic_diagnostics_lock:
        cached = bundle.semantic_diagnostics_by_path.get(resolved_path)
        if cached is not None:
            return cached
        bundle.semantic_diagnostics_by_path[resolved_path] = diagnostics
    return diagnostics


def _collect_reference_matches(
    bundle: SnapshotBundle | None,
    local_snapshot: SemanticSnapshot | None,
    candidates: list[SymbolDefinition],
) -> list[SymbolReference]:
    local_references: list[SymbolReference] = []
    workspace_references: list[SymbolReference] = []
    for definition in candidates:
        if local_snapshot is not None:
            local_references.extend(local_snapshot.find_references_to(definition))
        if bundle is not None:
            workspace_references.extend(bundle.snapshot.find_references_to(definition))
    return _merge_references(local_references, workspace_references)


def _definition_uri(
    definition: SymbolDefinition,
    *,
    bundle: SnapshotBundle | None,
    active_document_path: Path,
) -> str | None:
    active_name = active_document_path.name.casefold()
    if (definition.source_file or "").casefold() == active_name:
        return uris.from_fs_path(str(active_document_path.resolve())) or active_document_path.resolve().as_uri()
    if bundle is None:
        return None
    target_path = resolve_definition_path(bundle, definition)
    if target_path is None:
        return None
    return uris.from_fs_path(str(target_path)) or target_path.as_uri()


collect_reference_matches = _collect_reference_matches
definition_locations_from_candidates = _definition_locations_from_candidates
definition_uri = _definition_uri
filter_visible_definitions = _filter_visible_definitions
local_definition_candidates = _local_definition_candidates
merge_completion_items = _merge_completion_items
merge_definitions = _merge_definitions
merge_locations = _merge_locations
merge_references = _merge_references
overlay_definition_candidates = _overlay_definition_candidates
reference_expr_at_position = _reference_expr_at_position
reference_locations_from_matches = _reference_locations_from_matches
resolve_reference_path = _resolve_reference_path
semantic_completion_kind = _semantic_completion_kind
semantic_diagnostics_for_path = _semantic_diagnostics_for_path
