"""SattLint language-server helper utilities - pure and stateless functions."""

from __future__ import annotations

import logging
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypeGuard, cast

from lsprotocol.types import (
    CompletionItem as LspCompletionItem,
)
from lsprotocol.types import (
    CompletionItemKind,
    Diagnostic,
    DiagnosticSeverity,
    Hover,
    Location,
    MarkupContent,
    MarkupKind,
    Position,
    Range,
    TextEdit,
)
from pygls import uris
from pygls.workspace import TextDocument

from sattline_parser.models.ast_model import Simple_DataType
from sattlint.core.semantic import (
    SemanticSnapshot,
    SymbolDefinition,
    SymbolReference,
    discover_workspace_sources,
    load_source_snapshot,
)
from sattlint.engine import CodeMode
from sattlint.semantic_analysis import build_variable_semantic_artifacts

from .local_parser import IncrementalDocumentParserAdapter
from .workspace_store import SnapshotBundle

_PROGRAM_SUFFIXES = {".s", ".x"}
_DIAGNOSTIC_SUFFIXES = {".s", ".x", ".g"}
_NAME_PATTERN = r"[0-9A-Za-z_'\u00C0-\u024F]+"
_REFERENCE_EXPR_RE = re.compile(rf"{_NAME_PATTERN}(?:\.{_NAME_PATTERN})*")
_BASE_COMPLETION_RE = re.compile(rf"(?P<base>{_NAME_PATTERN}(?:\.{_NAME_PATTERN})*)\.(?P<prefix>{_NAME_PATTERN})?$")
_IDENTIFIER_PREFIX_RE = re.compile(rf"(?P<prefix>{_NAME_PATTERN})$")
_VALID_IDENTIFIER_RE = re.compile(rf"^(?:'[^']+'|{_NAME_PATTERN})$")
_MODULE_START_RE = re.compile(
    rf"^\s*(?P<name>'[^']+'|{_NAME_PATTERN})\s+Invocation\b.*:\s+MODULEDEFINITION\b",
    re.IGNORECASE,
)
_TYPEDEF_START_RE = re.compile(
    rf"^\s*(?P<name>'[^']+'|{_NAME_PATTERN})\s*=\s*(?:PRIVATE_)?MODULEDEFINITION\b",
    re.IGNORECASE,
)
_ENDDEF_LABEL_RE = re.compile(r"^\s*ENDDEF\b(?:\s*\(\*(?P<label>.*?)\*\))?", re.IGNORECASE)
_INTERACTIVE_SNAPSHOT_WAIT_S = 0.05
_DIAGNOSTIC_SNAPSHOT_WAIT_S = 0.15
_MAX_IDENTIFIER_LENGTH = 20
_DEFAULT_MAX_COMPLETION_ITEMS = 100
_DEFAULT_LOCAL_PARSER = IncrementalDocumentParserAdapter()
_RECOVERABLE_LSP_EXCEPTIONS = (OSError, ValueError, RuntimeError, UnicodeError)
log = logging.getLogger(__name__)


def _is_program_path(path: Path) -> bool:
    return path.suffix.lower() in _PROGRAM_SUFFIXES


def _is_diagnostic_path(path: Path) -> bool:
    return path.suffix.lower() in _DIAGNOSTIC_SUFFIXES


def _cf(value: str) -> str:
    return value.casefold()


def _path_startswith(path: tuple[str, ...], prefix: tuple[str, ...]) -> bool:
    if len(prefix) > len(path):
        return False
    return tuple(_cf(part) for part in path[: len(prefix)]) == tuple(_cf(part) for part in prefix)


def _range_from_position(line: int, column: int, length: int) -> Range:
    start = Position(line=max(line - 1, 0), character=max(column - 1, 0))
    end = Position(line=max(line - 1, 0), character=max(column - 1 + max(length, 1), 0))
    return Range(start=start, end=end)


def _range_for_definition(definition: SymbolDefinition) -> Range | None:
    if definition.declaration_span is None:
        return None
    label = definition.field_path.split(".")[-1] if definition.field_path else definition.canonical_path.split(".")[-1]
    return _range_from_position(definition.declaration_span.line, definition.declaration_span.column, len(label))


def _diagnostic_from_message(
    message: str,
    line: int | None,
    column: int | None,
    length: int | None = None,
) -> Diagnostic:
    if line is None or column is None:
        range_ = Range(start=Position(line=0, character=0), end=Position(line=0, character=1))
    else:
        range_ = _range_from_position(line, column, max(length or 8, 1))
    return Diagnostic(range=range_, message=message, severity=DiagnosticSeverity.Error, source="sattlint")


def _root_workspace_failure_message(message: str) -> str:
    lines: list[str] = []
    for raw_line in message.splitlines():
        line = raw_line.strip()
        if not line:
            if lines:
                break
            continue
        if line.startswith(("Resolved targets (", "Unavailable libraries (", "Other dependency issues (", "- ")):
            break
        lines.append(line)
    if lines:
        return "\n".join(lines)
    return message


def _normalize_workspace_diagnostics_mode(value: Any) -> str:
    normalized = str(value).strip().lower()
    if normalized in {"off", "background"}:
        return normalized
    return "background"


def _identifier_length(name: str) -> int:
    if len(name) >= 2 and name.startswith("'") and name.endswith("'"):
        return len(name[1:-1])
    return len(name)


def _validate_rename_target(new_name: str) -> None:
    if not _VALID_IDENTIFIER_RE.fullmatch(new_name):
        raise ValueError(f"{new_name!r} is not a valid SattLine identifier")
    if _identifier_length(new_name) > _MAX_IDENTIFIER_LENGTH:
        raise ValueError(f"{new_name!r} exceeds the {_MAX_IDENTIFIER_LENGTH} character identifier limit")


def _is_non_negative_int(value: object) -> TypeGuard[int]:
    return type(value) is int and value >= 0


def _validated_text_document_uri(params: Any) -> str | None:
    text_document = getattr(params, "text_document", None)
    uri = getattr(text_document, "uri", None)
    if not isinstance(uri, str) or not uri:
        return None
    return uri


def _validated_text_document_position(params: Any) -> tuple[str, int, int] | None:
    uri = _validated_text_document_uri(params)
    if uri is None:
        return None

    position = getattr(params, "position", None)
    line = getattr(position, "line", None)
    character = getattr(position, "character", None)
    if not _is_non_negative_int(line) or not _is_non_negative_int(character):
        return None
    return uri, line, character


def _validated_open_request(params: Any) -> tuple[str, int, str] | None:
    uri = _validated_text_document_uri(params)
    if uri is None:
        return None

    text_document = getattr(params, "text_document", None)
    version = getattr(text_document, "version", None)
    text = getattr(text_document, "text", None)
    if not _is_non_negative_int(version) or not isinstance(text, str):
        return None
    return uri, version, text


def _validated_change_request(params: Any) -> tuple[str, int, list[Any]] | None:
    uri = _validated_text_document_uri(params)
    if uri is None:
        return None

    text_document = getattr(params, "text_document", None)
    version = getattr(text_document, "version", None)
    content_changes = getattr(params, "content_changes", None)
    if not _is_non_negative_int(version):
        return None
    if content_changes is None:
        normalized_changes: list[Any] = []
    elif isinstance(content_changes, list):
        normalized_changes = cast(list[Any], content_changes)
    elif isinstance(content_changes, tuple):
        normalized_changes = list(cast(tuple[Any, ...], content_changes))
    else:
        return None
    return uri, version, normalized_changes


def _validated_rename_request(params: Any) -> tuple[str, int, int, str] | None:
    position_request = _validated_text_document_position(params)
    if position_request is None:
        return None

    new_name = getattr(params, "new_name", None)
    if not isinstance(new_name, str):
        return None

    uri, line, character = position_request
    return uri, line, character, new_name


@dataclass(frozen=True, slots=True)
class LspSettings:
    entry_file: str | None = None
    mode: str = CodeMode.DRAFT.value
    scan_root_only: bool = False
    enable_variable_diagnostics: bool = True
    workspace_diagnostics_mode: str = "off"
    max_completion_items: int = _DEFAULT_MAX_COMPLETION_ITEMS

    @classmethod
    def from_initialization_options(cls, data: Any) -> LspSettings:
        if not isinstance(data, Mapping):
            return cls()
        settings_data = cast(Mapping[str, object], data)
        raw_entry = str(settings_data.get("entryFile", "")).strip()
        raw_mode = str(settings_data.get("mode", CodeMode.DRAFT.value)).strip().lower() or CodeMode.DRAFT.value
        raw_limit = settings_data.get("maxCompletionItems", _DEFAULT_MAX_COMPLETION_ITEMS)
        try:
            limit = max(1, int(cast(Any, raw_limit)))
        except (TypeError, ValueError):
            limit = _DEFAULT_MAX_COMPLETION_ITEMS
        return cls(
            entry_file=raw_entry or None,
            mode=raw_mode,
            scan_root_only=bool(settings_data.get("scanRootOnly", False)),
            enable_variable_diagnostics=bool(settings_data.get("enableVariableDiagnostics", True)),
            workspace_diagnostics_mode=_normalize_workspace_diagnostics_mode(
                settings_data.get("workspaceDiagnosticsMode", "off")
            ),
            max_completion_items=limit,
        )


def _diagnostic_signature(diagnostic: Diagnostic) -> tuple[int, int, int, int, int, str, str, int]:
    severity = int(diagnostic.severity) if diagnostic.severity is not None else 0
    return (
        diagnostic.range.start.line,
        diagnostic.range.start.character,
        diagnostic.range.end.line,
        diagnostic.range.end.character,
        severity,
        diagnostic.source or "",
        diagnostic.message,
        0,
    )


def _merge_unique_diagnostics(*collections: Sequence[Diagnostic]) -> tuple[Diagnostic, ...]:
    unique: dict[tuple[int, int, int, int, int, str, str, int], Diagnostic] = {}
    for collection in collections:
        for diagnostic in collection:
            unique.setdefault(_diagnostic_signature(diagnostic), diagnostic)
    return tuple(unique[key] for key in sorted(unique))


def _document_uri_for_path(path: Path) -> str:
    resolved = path.resolve()
    return uris.from_fs_path(str(resolved)) or resolved.as_uri()


def resolve_entry_file(
    document_path: Path,
    *,
    workspace_root: Path,
    configured_entry_file: str | None = None,
) -> Path | None:
    suffix = document_path.suffix.lower()
    if suffix in _PROGRAM_SUFFIXES:
        return document_path.resolve()

    if configured_entry_file:
        configured = Path(configured_entry_file)
        candidate = configured if configured.is_absolute() else (workspace_root / configured)
        if candidate.exists() and candidate.suffix.lower() in _PROGRAM_SUFFIXES:
            return candidate.resolve()

    discovery = discover_workspace_sources(workspace_root)
    if len(discovery.program_files) == 1:
        return discovery.program_files[0].resolve()
    return None


def collect_syntax_diagnostics(
    document_path: Path,
    text: str,
    *,
    include_comment_validation: bool = True,
) -> list[Diagnostic]:
    return list(
        _DEFAULT_LOCAL_PARSER.analyze(
            document_path,
            text,
            include_comment_validation=include_comment_validation,
            build_snapshot=False,
        ).syntax_diagnostics
    )


def infer_module_path_from_source(source_text: str, line_number: int) -> str | None:
    stack: list[str] = []
    lines = source_text.splitlines()
    for line in lines[: line_number + 1]:
        module_match = _MODULE_START_RE.match(line)
        if module_match:
            stack.append(module_match.group("name"))
            continue

        typedef_match = _TYPEDEF_START_RE.match(line)
        if typedef_match:
            stack.append(typedef_match.group("name"))
            continue

        enddef_match = _ENDDEF_LABEL_RE.match(line)
        if not enddef_match:
            continue

        label = (enddef_match.group("label") or "").strip()
        if label and stack and _cf(stack[-1]) == _cf(label):
            stack.pop()

    return ".".join(stack) if stack else None


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


def build_source_path_index(
    paths: set[Path] | tuple[Path, ...],
) -> tuple[dict[str, tuple[Path, ...]], dict[tuple[str, str], Path]]:
    by_name: dict[str, list[Path]] = {}
    by_key: dict[tuple[str, str], Path] = {}
    for path in sorted((item.resolve() for item in paths), key=lambda item: item.as_posix().casefold()):
        file_key = path.name.casefold()
        by_name.setdefault(file_key, []).append(path)
        by_key[(file_key, path.parent.name.casefold())] = path
    return ({name: tuple(items) for name, items in by_name.items()}, by_key)


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
            local_snapshot = load_source_snapshot(
                document_path,
                source_text,
                _analysis_provider=build_variable_semantic_artifacts,
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
            local_snapshot = load_source_snapshot(
                document_path,
                source_text,
                _analysis_provider=build_variable_semantic_artifacts,
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


def _document_path(document: TextDocument) -> Path:
    uri = document.uri or ""
    return Path(uris.to_fs_path(uri) or uri).resolve()


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


def _append_workspace_edit(
    changes: dict[str, list[TextEdit]],
    uri: str,
    range_: Range,
    new_text: str,
) -> None:
    changes.setdefault(uri, []).append(TextEdit(range=range_, new_text=new_text))


def _build_hover(definition: SymbolDefinition) -> Hover | None:
    lines = [f"**{definition.canonical_path.split('.')[-1]}**"]
    if definition.datatype:
        lines.append(f"Type: {definition.datatype}")
    lines.append(f"Kind: {definition.kind}")
    lines.append(f"Path: {definition.canonical_path}")
    if definition.display_module_path:
        lines.append(f"Scope: {' -> '.join(definition.display_module_path)}")
    return Hover(contents=MarkupContent(kind=MarkupKind.Markdown, value="\n\n".join(lines)))


DEFAULT_LOCAL_PARSER = _DEFAULT_LOCAL_PARSER
INTERACTIVE_SNAPSHOT_WAIT_S = _INTERACTIVE_SNAPSHOT_WAIT_S
DIAGNOSTIC_SNAPSHOT_WAIT_S = _DIAGNOSTIC_SNAPSHOT_WAIT_S
RECOVERABLE_LSP_EXCEPTIONS = _RECOVERABLE_LSP_EXCEPTIONS
append_workspace_edit = _append_workspace_edit
build_hover = _build_hover
collect_reference_matches = _collect_reference_matches
definition_locations_from_candidates = _definition_locations_from_candidates
definition_uri = _definition_uri
diagnostic_from_message = _diagnostic_from_message
diagnostic_signature = _diagnostic_signature
document_path = _document_path
document_uri_for_path = _document_uri_for_path
is_diagnostic_path = _is_diagnostic_path
is_program_path = _is_program_path
local_definition_candidates = _local_definition_candidates
merge_completion_items = _merge_completion_items
merge_locations = _merge_locations
merge_unique_diagnostics = _merge_unique_diagnostics
overlay_definition_candidates = _overlay_definition_candidates
range_for_definition = _range_for_definition
range_from_position = _range_from_position
reference_locations_from_matches = _reference_locations_from_matches
resolve_reference_path = _resolve_reference_path
root_workspace_failure_message = _root_workspace_failure_message
semantic_diagnostics_for_path = _semantic_diagnostics_for_path
validate_rename_target = _validate_rename_target
validated_change_request = _validated_change_request
validated_open_request = _validated_open_request
validated_rename_request = _validated_rename_request
validated_text_document_position = _validated_text_document_position
validated_text_document_uri = _validated_text_document_uri
