"""SattLint-backed Language Server Protocol implementation for VS Code and other editors."""

from __future__ import annotations

import re
import threading
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from lsprotocol.types import (
    CompletionItem as LspCompletionItem,
)
from lsprotocol.types import (
    CompletionItemKind,
    CompletionList,
    CompletionOptions,
    DefinitionParams,
    Diagnostic,
    DiagnosticSeverity,
    DidChangeTextDocumentParams,
    DidCloseTextDocumentParams,
    DidOpenTextDocumentParams,
    DidSaveTextDocumentParams,
    Hover,
    HoverParams,
    InitializeParams,
    Location,
    MarkupContent,
    MarkupKind,
    Position,
    PublishDiagnosticsParams,
    Range,
    ReferenceParams,
    RenameParams,
    TextDocumentPositionParams,
    TextEdit,
    WorkspaceEdit,
)
from pygls import uris
from pygls.lsp.server import LanguageServer
from pygls.workspace import TextDocument

from sattline_parser.models.ast_model import Simple_DataType
from sattlint.editor_api import (
    SemanticSnapshot,
    SymbolDefinition,
    SymbolReference,
    discover_workspace_sources,
    load_source_snapshot,
)
from sattlint.engine import CodeMode

from .document_state import DocumentState
from .local_parser import IncrementalDocumentParserAdapter
from .workspace_store import SnapshotBundle, WorkspaceSnapshotStore

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
        if not isinstance(data, dict):
            return cls()
        raw_entry = str(data.get("entryFile", "")).strip()
        raw_mode = str(data.get("mode", CodeMode.DRAFT.value)).strip().lower() or CodeMode.DRAFT.value
        raw_limit = data.get("maxCompletionItems", _DEFAULT_MAX_COMPLETION_ITEMS)
        try:
            limit = max(1, int(raw_limit))
        except (TypeError, ValueError):
            limit = _DEFAULT_MAX_COMPLETION_ITEMS
        return cls(
            entry_file=raw_entry or None,
            mode=raw_mode,
            scan_root_only=bool(data.get("scanRootOnly", False)),
            enable_variable_diagnostics=bool(data.get("enableVariableDiagnostics", True)),
            workspace_diagnostics_mode=_normalize_workspace_diagnostics_mode(
                data.get("workspaceDiagnosticsMode", "off")
            ),
            max_completion_items=limit,
        )


class SattLineLanguageServer(LanguageServer):
    def __init__(self) -> None:
        super().__init__(name="sattline-lsp", version="0.1.0")
        self.settings = LspSettings()
        self.workspace_root: Path | None = None
        self.snapshot_store = WorkspaceSnapshotStore()
        self.document_states: dict[str, DocumentState] = {}
        self.document_paths: dict[Path, str] = {}
        self.entry_diagnostics: dict[str, dict[Path, tuple[Diagnostic, ...]]] = {}
        self.published_workspace_diagnostics: dict[Path, tuple[Diagnostic, ...]] = {}
        self.workspace_scan_condition = threading.Condition()
        self.workspace_scan_pending: set[Path] = set()
        self.workspace_scan_generation = 0
        self.entry_scan_generation: dict[str, int] = {}
        self.workspace_scan_thread: threading.Thread | None = None
        self.local_parser = _DEFAULT_LOCAL_PARSER


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


def _ensure_snapshot_store_configured(ls: SattLineLanguageServer) -> bool:
    return ls.snapshot_store.ensure_configured(ls.workspace_root, ls.settings)


def _document_state_for_path(ls: SattLineLanguageServer, document_path: Path) -> DocumentState | None:
    document_paths = getattr(ls, "document_paths", None)
    if document_paths is None:
        return None
    uri = document_paths.get(document_path.resolve())
    if uri is None:
        return None
    return ls.document_states.get(uri)


def _ensure_document_paths(ls: SattLineLanguageServer) -> dict[Path, str]:
    document_paths = getattr(ls, "document_paths", None)
    if document_paths is None:
        document_paths = {}
        ls.document_paths = document_paths
    return document_paths


def _background_workspace_diagnostics_enabled(ls: SattLineLanguageServer) -> bool:
    return ls.settings.enable_variable_diagnostics and ls.settings.workspace_diagnostics_mode == "background"


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
            local_snapshot = load_source_snapshot(document_path, source_text)
        except Exception:  # LSP handler — keep broad to prevent server crash
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
            local_snapshot = load_source_snapshot(document_path, source_text)
        except Exception:  # LSP handler — keep broad to prevent server crash
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


def _source_text_for_document(ls: SattLineLanguageServer, document: TextDocument) -> str:
    state = ls.document_states.get(document.uri)
    if state is not None:
        return state.text
    return document.source


def _record_document_open(
    ls: SattLineLanguageServer,
    document_path: Path,
    *,
    uri: str,
    version: int,
    text: str,
) -> DocumentState:
    document_paths = _ensure_document_paths(ls)
    state = ls.document_states.get(uri)
    if state is None:
        state = DocumentState(uri=uri, path=document_path, version=version, text=text)
        ls.document_states[uri] = state
    else:
        previous_path = state.path.resolve()
        document_paths.pop(previous_path, None)
        state.path = document_path
        state.replace_text(version=version, text=text, is_dirty=False)

    document_paths[document_path.resolve()] = uri
    return state


def _record_document_change(
    ls: SattLineLanguageServer,
    document_path: Path,
    *,
    uri: str,
    version: int,
    content_changes: list[Any],
    fallback_text: str,
) -> DocumentState:
    document_paths = _ensure_document_paths(ls)
    state = ls.document_states.get(uri)
    if state is None:
        state = DocumentState(uri=uri, path=document_path, version=version, text=fallback_text)
        ls.document_states[uri] = state
    else:
        previous_path = state.path.resolve()
        document_paths.pop(previous_path, None)
        state.path = document_path

    state.apply_changes(version=version, content_changes=content_changes, fallback_text=fallback_text)
    document_paths[document_path.resolve()] = uri
    return state


def _analyze_document_state(
    ls: SattLineLanguageServer,
    document: TextDocument,
    document_path: Path,
    *,
    include_comment_validation: bool,
    require_snapshot: bool,
) -> DocumentState:
    state = ls.document_states.get(document.uri)
    if state is None:
        state = _record_document_open(
            ls,
            document_path,
            uri=document.uri,
            version=getattr(document, "version", 0),
            text=document.source,
        )

    if state.has_analysis(
        include_comment_validation=include_comment_validation,
        require_snapshot=require_snapshot,
    ):
        return state

    prior_result = state.analysis_result if state.analysis_version == state.version else state.previous_analysis_result

    result = ls.local_parser.analyze(
        document_path,
        state.text,
        include_comment_validation=include_comment_validation,
        build_snapshot=require_snapshot,
        previous_result=prior_result,
        changed_line_ranges=state.changed_line_ranges,
    )
    state.remember_analysis(result, include_comment_validation=include_comment_validation)
    return state


def _get_or_build_local_snapshot(
    ls: SattLineLanguageServer,
    document: TextDocument,
    document_path: Path,
) -> SemanticSnapshot | None:
    state = _analyze_document_state(
        ls,
        document,
        document_path,
        include_comment_validation=False,
        require_snapshot=True,
    )
    return state.local_snapshot


def _load_snapshot_bundle(
    ls: SattLineLanguageServer,
    document_path: Path,
    *,
    wait_budget: float | None = _INTERACTIVE_SNAPSHOT_WAIT_S,
    allow_stale: bool = True,
    raise_on_error: bool = False,
) -> SnapshotBundle | None:
    if not _ensure_snapshot_store_configured(ls):
        return None
    return ls.snapshot_store.get_bundle_for_document(
        document_path,
        wait_budget=wait_budget,
        allow_stale=allow_stale,
        raise_on_error=raise_on_error,
    )


def _load_snapshot_bundle_compat(
    ls: SattLineLanguageServer,
    document_path: Path,
    *,
    wait_budget: float | None = _INTERACTIVE_SNAPSHOT_WAIT_S,
    allow_stale: bool = True,
    raise_on_error: bool = False,
) -> SnapshotBundle | None:
    try:
        return _load_snapshot_bundle(
            ls,
            document_path,
            wait_budget=wait_budget,
            allow_stale=allow_stale,
            raise_on_error=raise_on_error,
        )
    except TypeError as exc:
        if "unexpected keyword argument" not in str(exc):
            if raise_on_error:
                raise
            return None
    try:
        return _load_snapshot_bundle(ls, document_path)
    except Exception:  # LSP handler — keep broad to prevent server crash
        if raise_on_error:
            raise
        return None


def _publish_diagnostics(
    ls: SattLineLanguageServer,
    document: TextDocument,
    *,
    include_semantic: bool = True,
    include_comment_validation: bool = True,
) -> None:
    document_path = _document_path(document)
    if not _is_diagnostic_path(document_path):
        state = ls.document_states.pop(document.uri, None)
        state_path = getattr(state, "path", None)
        if state_path is not None:
            _ensure_document_paths(ls).pop(Path(state_path).resolve(), None)
        ls.text_document_publish_diagnostics(PublishDiagnosticsParams(uri=document.uri, diagnostics=[]))
        return

    state = _analyze_document_state(
        ls,
        document,
        document_path,
        include_comment_validation=include_comment_validation,
        require_snapshot=False,
    )
    syntax_diagnostics = list(state.syntax_diagnostics)
    if syntax_diagnostics:
        ls.text_document_publish_diagnostics(PublishDiagnosticsParams(uri=document.uri, diagnostics=syntax_diagnostics))
        return

    if not include_semantic or not _is_program_path(document_path) or not ls.settings.enable_variable_diagnostics:
        ls.text_document_publish_diagnostics(PublishDiagnosticsParams(uri=document.uri, diagnostics=[]))
        return

    try:
        bundle = _load_snapshot_bundle_compat(
            ls,
            document_path,
            wait_budget=_DIAGNOSTIC_SNAPSHOT_WAIT_S,
            allow_stale=True,
            raise_on_error=True,
        )
    except Exception as exc:
        ls.text_document_publish_diagnostics(
            PublishDiagnosticsParams(
                uri=document.uri,
                diagnostics=[
                    _diagnostic_from_message(
                        _root_workspace_failure_message(str(exc)),
                        getattr(exc, "line", None),
                        getattr(exc, "column", None),
                        getattr(exc, "length", None),
                    )
                ],
            )
        )
        return

    if bundle is None:
        ls.text_document_publish_diagnostics(
            PublishDiagnosticsParams(
                uri=document.uri,
                diagnostics=[
                    _diagnostic_from_message(
                        "Could not determine the root program for this file. Set sattlineLsp.entryFile in VS Code when editing libraries in multi-program workspaces.",
                        1,
                        1,
                    )
                ],
            )
        )
        return

    ls.text_document_publish_diagnostics(
        PublishDiagnosticsParams(
            uri=document.uri, diagnostics=list(_semantic_diagnostics_for_path(bundle, document_path))
        )
    )


def _store_entry_workspace_diagnostics(
    ls: SattLineLanguageServer,
    entry_key: str,
    diagnostics_by_path: dict[Path, tuple[Diagnostic, ...]],
    generation: int,
) -> None:
    if generation != ls.entry_scan_generation.get(entry_key):
        return
    previous = ls.entry_diagnostics.get(entry_key, {})
    ls.entry_diagnostics[entry_key] = diagnostics_by_path
    affected_paths = {path.resolve() for path in previous} | {path.resolve() for path in diagnostics_by_path}
    _publish_workspace_diagnostics_for_paths(ls, affected_paths)


def _collect_entry_workspace_diagnostics(
    ls: SattLineLanguageServer,
    entry_file: Path,
) -> tuple[str, dict[Path, tuple[Diagnostic, ...]]]:
    key = entry_file.resolve().as_posix().casefold()
    try:
        bundle = ls.snapshot_store.get_bundle_for_entry(
            entry_file,
            wait_budget=None,
            allow_stale=False,
            raise_on_error=True,
        )
    except Exception as exc:
        return (
            key,
            {
                entry_file.resolve(): (
                    _diagnostic_from_message(
                        _root_workspace_failure_message(str(exc)),
                        getattr(exc, "line", None),
                        getattr(exc, "column", None),
                        getattr(exc, "length", None),
                    ),
                )
            },
        )

    if bundle is None:
        return key, {}

    diagnostics_by_path: dict[Path, tuple[Diagnostic, ...]] = {}
    for source_path in bundle.source_files:
        diagnostics = _semantic_diagnostics_for_path(bundle, source_path)
        if diagnostics:
            diagnostics_by_path[source_path.resolve()] = diagnostics
    return key, diagnostics_by_path


def _process_workspace_scan_entries(
    ls: SattLineLanguageServer,
    entry_files: tuple[Path, ...],
) -> None:
    _ensure_snapshot_store_configured(ls)
    ls.snapshot_store.prefetch_entries(entry_files)
    for entry_file in entry_files:
        entry_key = entry_file.resolve().as_posix().casefold()
        generation = ls.entry_scan_generation.get(entry_key)
        if generation is None:
            continue
        key, diagnostics_by_path = _collect_entry_workspace_diagnostics(ls, entry_file)
        _store_entry_workspace_diagnostics(ls, key, diagnostics_by_path, generation)


def _workspace_scan_worker(ls: SattLineLanguageServer) -> None:
    while True:
        with ls.workspace_scan_condition:
            if not ls.workspace_scan_pending:
                ls.workspace_scan_thread = None
                return
            entry_files = tuple(
                sorted(
                    (path.resolve() for path in ls.workspace_scan_pending),
                    key=lambda path: path.as_posix().casefold(),
                )
            )
            ls.workspace_scan_pending.clear()
        _process_workspace_scan_entries(ls, entry_files)


def _schedule_workspace_scan(
    ls: SattLineLanguageServer,
    entry_files: tuple[Path, ...] | None = None,
) -> None:
    if not _background_workspace_diagnostics_enabled(ls):
        return
    if not _ensure_snapshot_store_configured(ls):
        return

    entries = entry_files or ls.snapshot_store.list_entry_files()
    if not entries:
        return

    ls.snapshot_store.prefetch_entries(entries)
    resolved_entries = tuple(sorted((path.resolve() for path in entries), key=lambda path: path.as_posix().casefold()))
    with ls.workspace_scan_condition:
        ls.workspace_scan_generation += 1
        generation = ls.workspace_scan_generation
        for entry in resolved_entries:
            ls.workspace_scan_pending.add(entry)
            ls.entry_scan_generation[entry.as_posix().casefold()] = generation
        if ls.workspace_scan_thread is None or not ls.workspace_scan_thread.is_alive():
            ls.workspace_scan_thread = threading.Thread(
                target=_workspace_scan_worker,
                args=(ls,),
                name="sattline-workspace-scan",
                daemon=True,
            )
            ls.workspace_scan_thread.start()


def _invalidate_cached_entries_for_path(
    ls: SattLineLanguageServer,
    document_path: Path,
) -> tuple[Path, ...]:
    if not _ensure_snapshot_store_configured(ls):
        return ()

    affected_entries = ls.snapshot_store.invalidate_path(document_path)
    affected_entry_keys = ls.snapshot_store.get_affected_entry_keys(document_path)
    affected_paths: set[Path] = set()
    for entry_key in affected_entry_keys:
        previous = ls.entry_diagnostics.pop(entry_key, {})
        affected_paths.update(path.resolve() for path in previous)
    if affected_paths:
        _publish_workspace_diagnostics_for_paths(ls, affected_paths)
    return affected_entries


def _publish_workspace_diagnostics_for_paths(
    ls: SattLineLanguageServer,
    paths: set[Path],
) -> None:
    for path in sorted((item.resolve() for item in paths), key=lambda candidate: candidate.as_posix().casefold()):
        state = _document_state_for_path(ls, path)
        if state is not None and state.is_dirty:
            continue

        merged = _merge_unique_diagnostics(
            *[
                diagnostics_by_path.get(path, ())
                for diagnostics_by_path in ls.entry_diagnostics.values()
                if path in diagnostics_by_path
            ]
        )
        previous = ls.published_workspace_diagnostics.get(path, ())
        if tuple(map(_diagnostic_signature, previous)) == tuple(map(_diagnostic_signature, merged)):
            continue
        if merged:
            ls.published_workspace_diagnostics[path] = merged
        else:
            ls.published_workspace_diagnostics.pop(path, None)

        ls.text_document_publish_diagnostics(
            PublishDiagnosticsParams(uri=_document_uri_for_path(path), diagnostics=list(merged))
        )


def _publish_closed_document_diagnostics(
    ls: SattLineLanguageServer,
    document_path: Path,
) -> None:
    resolved_path = document_path.resolve()
    merged = _merge_unique_diagnostics(
        *[
            diagnostics_by_path.get(resolved_path, ())
            for diagnostics_by_path in ls.entry_diagnostics.values()
            if resolved_path in diagnostics_by_path
        ]
    )

    if not merged and ls.settings.enable_variable_diagnostics:
        try:
            bundle = _load_snapshot_bundle_compat(
                ls,
                resolved_path,
                wait_budget=_INTERACTIVE_SNAPSHOT_WAIT_S,
                allow_stale=True,
                raise_on_error=False,
            )
        except Exception:  # LSP handler — keep broad to prevent server crash
            bundle = None
        if bundle is not None:
            merged = _semantic_diagnostics_for_path(bundle, resolved_path)

    if merged:
        ls.published_workspace_diagnostics[resolved_path] = merged
    else:
        ls.published_workspace_diagnostics.pop(resolved_path, None)

    ls.text_document_publish_diagnostics(
        PublishDiagnosticsParams(uri=_document_uri_for_path(resolved_path), diagnostics=list(merged))
    )


def _resolve_symbol_context(
    ls: SattLineLanguageServer,
    document: TextDocument,
    *,
    line: int,
    column: int,
) -> tuple[Path, str, SemanticSnapshot | None, SnapshotBundle | None, list[SymbolDefinition]]:
    document_path = _document_path(document)
    source_text = _source_text_for_document(ls, document)
    if not _is_program_path(document_path):
        return document_path, source_text, None, None, []

    local_snapshot = _get_or_build_local_snapshot(ls, document, document_path)
    bundle = _load_snapshot_bundle_compat(
        ls,
        document_path,
        wait_budget=_INTERACTIVE_SNAPSHOT_WAIT_S,
        allow_stale=True,
        raise_on_error=False,
    )

    if bundle is None:
        candidates = _local_definition_candidates(
            document_path,
            source_text,
            line=line,
            column=column,
            snapshot=local_snapshot,
        )
        return document_path, source_text, local_snapshot, None, candidates

    candidates = _overlay_definition_candidates(
        bundle,
        document_path=document_path,
        source_text=source_text,
        line=line,
        column=column,
        local_snapshot=local_snapshot,
    )
    return document_path, source_text, local_snapshot, bundle, candidates


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


server = SattLineLanguageServer()


@server.feature("initialize")
def on_initialize(ls: SattLineLanguageServer, params: InitializeParams) -> None:
    ls.settings = LspSettings.from_initialization_options(params.initialization_options)
    root_uri = getattr(params, "root_uri", None)
    root_path = getattr(params, "root_path", None)
    if root_uri:
        resolved_root = uris.to_fs_path(root_uri) or root_uri
        ls.workspace_root = Path(resolved_root).resolve()
    elif root_path:
        ls.workspace_root = Path(root_path).resolve()
    else:
        ls.workspace_root = None

    ls.document_states.clear()
    ls.document_paths.clear()
    ls.entry_diagnostics.clear()
    ls.published_workspace_diagnostics.clear()
    ls.entry_scan_generation.clear()
    with ls.workspace_scan_condition:
        ls.workspace_scan_pending.clear()
        ls.workspace_scan_generation = 0
        ls.workspace_scan_thread = None
    _ensure_snapshot_store_configured(ls)
    _schedule_workspace_scan(ls)


@server.feature("textDocument/didOpen")
def on_did_open(ls: SattLineLanguageServer, params: DidOpenTextDocumentParams) -> None:
    document = ls.workspace.get_text_document(params.text_document.uri)
    document_path = _document_path(document)
    if not _is_diagnostic_path(document_path):
        state = ls.document_states.pop(document.uri, None)
        if state is not None:
            _ensure_document_paths(ls).pop(state.path.resolve(), None)
        ls.text_document_publish_diagnostics(PublishDiagnosticsParams(uri=document.uri, diagnostics=[]))
        return

    _record_document_open(
        ls,
        document_path,
        uri=document.uri,
        version=params.text_document.version,
        text=params.text_document.text,
    )
    _publish_diagnostics(ls, document)


@server.feature("textDocument/didChange")
def on_did_change(ls: SattLineLanguageServer, params: DidChangeTextDocumentParams) -> None:
    document = ls.workspace.get_text_document(params.text_document.uri)
    document_path = _document_path(document)
    if not _is_diagnostic_path(document_path):
        state = ls.document_states.pop(document.uri, None)
        if state is not None:
            _ensure_document_paths(ls).pop(state.path.resolve(), None)
        ls.text_document_publish_diagnostics(PublishDiagnosticsParams(uri=document.uri, diagnostics=[]))
        return

    _record_document_change(
        ls,
        document_path,
        uri=document.uri,
        version=params.text_document.version,
        content_changes=list(params.content_changes or []),
        fallback_text=document.source,
    )
    _publish_diagnostics(ls, document, include_semantic=False, include_comment_validation=False)


@server.feature("textDocument/didSave")
def on_did_save(ls: SattLineLanguageServer, params: DidSaveTextDocumentParams) -> None:
    document = ls.workspace.get_text_document(params.text_document.uri)
    document_path = _document_path(document)
    if not _is_diagnostic_path(document_path):
        state = ls.document_states.pop(document.uri, None)
        if state is not None:
            ls.document_paths.pop(state.path.resolve(), None)
        ls.text_document_publish_diagnostics(PublishDiagnosticsParams(uri=document.uri, diagnostics=[]))
        return

    _record_document_open(
        ls,
        document_path,
        uri=document.uri,
        version=getattr(document, "version", 0),
        text=document.source,
    )
    affected_entries = _invalidate_cached_entries_for_path(ls, document_path)
    _publish_diagnostics(ls, document)
    _schedule_workspace_scan(ls, affected_entries)


@server.feature("textDocument/didClose")
def on_did_close(ls: SattLineLanguageServer, params: DidCloseTextDocumentParams) -> None:
    state = ls.document_states.pop(params.text_document.uri, None)
    document_path = (
        state.path if state is not None else Path(uris.to_fs_path(params.text_document.uri) or params.text_document.uri)
    )
    _ensure_document_paths(ls).pop(document_path.resolve(), None)
    if not _is_diagnostic_path(document_path):
        ls.text_document_publish_diagnostics(PublishDiagnosticsParams(uri=params.text_document.uri, diagnostics=[]))
        return

    if not _is_program_path(document_path):
        ls.text_document_publish_diagnostics(PublishDiagnosticsParams(uri=params.text_document.uri, diagnostics=[]))
        return

    _publish_closed_document_diagnostics(ls, document_path)


@server.feature("textDocument/definition")
def on_definition(ls: SattLineLanguageServer, params: DefinitionParams) -> list[Location] | None:
    document = ls.workspace.get_text_document(params.text_document.uri)
    document_path, source_text, local_snapshot, bundle, candidates = _resolve_symbol_context(
        ls,
        document,
        line=params.position.line,
        column=params.position.character,
    )
    if not _is_program_path(document_path):
        return None

    if bundle is None:
        local_locations = collect_local_definition_locations(
            document_path,
            source_text,
            line=params.position.line,
            column=params.position.character,
            snapshot=local_snapshot,
        )
        return local_locations or None

    locations = _definition_locations_from_candidates(
        candidates,
        bundle=bundle,
        local_snapshot=local_snapshot,
        active_document_path=document_path,
    )
    return locations or None


@server.feature("textDocument/hover")
def on_hover(ls: SattLineLanguageServer, params: HoverParams) -> Hover | None:
    document = ls.workspace.get_text_document(params.text_document.uri)
    document_path, _source_text, _local_snapshot, _bundle, candidates = _resolve_symbol_context(
        ls,
        document,
        line=params.position.line,
        column=params.position.character,
    )
    if not _is_program_path(document_path) or not candidates:
        return None
    return _build_hover(candidates[0])


@server.feature("textDocument/references")
def on_references(ls: SattLineLanguageServer, params: ReferenceParams) -> list[Location] | None:
    document = ls.workspace.get_text_document(params.text_document.uri)
    document_path, _source_text, local_snapshot, bundle, candidates = _resolve_symbol_context(
        ls,
        document,
        line=params.position.line,
        column=params.position.character,
    )
    if not _is_program_path(document_path) or not candidates:
        return None

    references = _collect_reference_matches(bundle, local_snapshot, candidates)
    locations = _reference_locations_from_matches(
        references,
        bundle=bundle,
        active_document_path=document_path,
    )
    ref_context = getattr(params, "context", None)
    if getattr(ref_context, "include_declaration", False) or getattr(ref_context, "includeDeclaration", False):
        declaration_locations: list[Location] = []
        for definition in candidates:
            target_range = _range_for_definition(definition)
            target_uri = _definition_uri(definition, bundle=bundle, active_document_path=document_path)
            if target_range is None or target_uri is None:
                continue
            declaration_locations.append(Location(uri=target_uri, range=target_range))
        locations = _merge_locations(declaration_locations, locations)
    return locations or None


@server.feature("textDocument/rename")
def on_rename(ls: SattLineLanguageServer, params: RenameParams) -> WorkspaceEdit | None:
    _validate_rename_target(params.new_name)

    document = ls.workspace.get_text_document(params.text_document.uri)
    document_path, _source_text, local_snapshot, bundle, candidates = _resolve_symbol_context(
        ls,
        document,
        line=params.position.line,
        column=params.position.character,
    )
    if not _is_program_path(document_path) or not candidates:
        return None

    references = _collect_reference_matches(bundle, local_snapshot, candidates)
    changes: dict[str, list[TextEdit]] = {}

    for definition in candidates:
        target_range = _range_for_definition(definition)
        target_uri = _definition_uri(definition, bundle=bundle, active_document_path=document_path)
        if target_range is not None and target_uri is not None:
            _append_workspace_edit(changes, target_uri, target_range, params.new_name)

    for reference in references:
        reference_uri: str | None = None
        if (reference.source_file or "").casefold() == document_path.name.casefold():
            reference_uri = uris.from_fs_path(str(document_path.resolve())) or document_path.resolve().as_uri()
        elif bundle is not None:
            target_path = _resolve_reference_path(bundle, reference)
            if target_path is not None:
                reference_uri = uris.from_fs_path(str(target_path)) or target_path.as_uri()
        if reference_uri is None:
            continue
        _append_workspace_edit(
            changes,
            reference_uri,
            _range_from_position(reference.line, reference.column, reference.length),
            params.new_name,
        )

    if not changes:
        return None
    return WorkspaceEdit(changes=changes)


@server.feature("textDocument/completion", CompletionOptions(trigger_characters=["."]))
def on_completion(ls: SattLineLanguageServer, params: TextDocumentPositionParams) -> CompletionList:
    document = ls.workspace.get_text_document(params.text_document.uri)
    document_path = _document_path(document)
    if not _is_program_path(document_path):
        return CompletionList(is_incomplete=False, items=[])

    source_text = _source_text_for_document(ls, document)
    local_snapshot = _get_or_build_local_snapshot(ls, document, document_path)

    local_items = collect_local_completion_candidates(
        document_path,
        source_text,
        line=params.position.line,
        column=params.position.character,
        limit=ls.settings.max_completion_items,
        snapshot=local_snapshot,
    )

    bundle = _load_snapshot_bundle_compat(
        ls,
        document_path,
        wait_budget=_INTERACTIVE_SNAPSHOT_WAIT_S,
        allow_stale=True,
        raise_on_error=False,
    )
    if bundle is None:
        return CompletionList(is_incomplete=False, items=local_items)

    workspace_items = collect_completion_candidates(
        bundle.snapshot,
        source_text,
        line=params.position.line,
        column=params.position.character,
        limit=ls.settings.max_completion_items,
    )
    items = _merge_completion_items(
        local_items,
        workspace_items,
        limit=ls.settings.max_completion_items,
    )
    return CompletionList(is_incomplete=False, items=items)


def cli() -> None:
    server.start_io()


if __name__ == "__main__":
    cli()
