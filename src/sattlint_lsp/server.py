"""SattLint-backed Language Server Protocol implementation for VS Code and other editors."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any

from lsprotocol.types import (
    CompletionItem,
    CompletionItemKind,
    CompletionList,
    CompletionOptions,
    DidCloseTextDocumentParams,
    DefinitionParams,
    Diagnostic,
    DiagnosticSeverity,
    DidChangeTextDocumentParams,
    DidOpenTextDocumentParams,
    DidSaveTextDocumentParams,
    InitializeParams,
    Location,
    Position,
    PublishDiagnosticsParams,
    Range,
    TextDocumentPositionParams,
)
from pygls import uris
from pygls.lsp.server import LanguageServer
from pygls.workspace import TextDocument

from sattlint.editor_api import (
    SemanticSnapshot,
    SymbolDefinition,
    discover_workspace_sources,
    load_source_snapshot,
    load_workspace_snapshot,
)
from sattlint.engine import CodeMode
from sattlint.models.ast_model import Simple_DataType
from sattlint.reporting.variables_report import IssueKind

from .document_state import DocumentState
from .local_parser import IncrementalDocumentParserAdapter

_PROGRAM_SUFFIXES = {".s", ".x"}
_NAME_PATTERN = r"[0-9A-Za-z_'\u00C0-\u024F]+"
_REFERENCE_EXPR_RE = re.compile(rf"{_NAME_PATTERN}(?:\.{_NAME_PATTERN})*")
_BASE_COMPLETION_RE = re.compile(rf"(?P<base>{_NAME_PATTERN}(?:\.{_NAME_PATTERN})*)\.(?P<prefix>{_NAME_PATTERN})?$")
_IDENTIFIER_PREFIX_RE = re.compile(rf"(?P<prefix>{_NAME_PATTERN})$")
_MODULE_START_RE = re.compile(
    rf"^\s*(?P<name>'[^']+'|{_NAME_PATTERN})\s+Invocation\b.*:\s+MODULEDEFINITION\b",
    re.IGNORECASE,
)
_TYPEDEF_START_RE = re.compile(
    rf"^\s*(?P<name>'[^']+'|{_NAME_PATTERN})\s*=\s*(?:PRIVATE_)?MODULEDEFINITION\b",
    re.IGNORECASE,
)
_ENDDEF_RE = re.compile(r"^\s*ENDDEF\b", re.IGNORECASE)
_ENDDEF_LABEL_RE = re.compile(r"^\s*ENDDEF\b(?:\s*\(\*(?P<label>.*?)\*\))?", re.IGNORECASE)
_ISSUE_LABELS = {
    IssueKind.UNUSED: "Unused variable",
    IssueKind.READ_ONLY_NON_CONST: "Read-only variable should be CONST",
    IssueKind.NEVER_READ: "Variable is written but never read",
    IssueKind.STRING_MAPPING_MISMATCH: "String mapping datatype mismatch",
    IssueKind.DATATYPE_DUPLICATION: "Datatype duplication",
    IssueKind.NAME_COLLISION: "Name collision",
    IssueKind.MIN_MAX_MAPPING_MISMATCH: "Min/Max mapping name mismatch",
    IssueKind.MAGIC_NUMBER: "Magic number",
    IssueKind.SHADOWING: "Variable shadows outer scope",
    IssueKind.RESET_CONTAMINATION: "Variable is contaminated across reset",
}
_DEFAULT_LOCAL_PARSER = IncrementalDocumentParserAdapter()

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


def _diagnostic_from_message(message: str, line: int | None, column: int | None) -> Diagnostic:
    if line is None or column is None:
        range_ = Range(start=Position(line=0, character=0), end=Position(line=0, character=1))
    else:
        range_ = _range_from_position(line, column, 1)
    return Diagnostic(range=range_, message=message, severity=DiagnosticSeverity.Error, source="sattlint")


@dataclass(frozen=True, slots=True)
class LspSettings:
    entry_file: str | None = None
    mode: str = CodeMode.DRAFT.value
    scan_root_only: bool = False
    enable_variable_diagnostics: bool = True
    max_completion_items: int = 100

    @classmethod
    def from_initialization_options(cls, data: Any) -> "LspSettings":
        if not isinstance(data, dict):
            return cls()
        raw_entry = str(data.get("entryFile", "")).strip()
        raw_mode = str(data.get("mode", CodeMode.DRAFT.value)).strip().lower() or CodeMode.DRAFT.value
        raw_limit = data.get("maxCompletionItems", 100)
        try:
            limit = max(1, int(raw_limit))
        except (TypeError, ValueError):
            limit = 100
        return cls(
            entry_file=raw_entry or None,
            mode=raw_mode,
            scan_root_only=bool(data.get("scanRootOnly", False)),
            enable_variable_diagnostics=bool(data.get("enableVariableDiagnostics", True)),
            max_completion_items=limit,
        )


@dataclass(frozen=True, slots=True)
class SnapshotBundle:
    snapshot: SemanticSnapshot
    source_paths_by_name: dict[str, tuple[Path, ...]]
    source_paths_by_key: dict[tuple[str, str], Path]


class SattLineLanguageServer(LanguageServer):
    def __init__(self) -> None:
        super().__init__(name="sattline-lsp", version="0.1.0")
        self.settings = LspSettings()
        self.workspace_root: Path | None = None
        self.snapshot_cache: dict[str, SnapshotBundle] = {}
        self.document_states: dict[str, DocumentState] = {}
        self.local_parser = _DEFAULT_LOCAL_PARSER


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
        definition
        for definition in definitions
        if _path_startswith(current_path, definition.declaration_module_path)
    ]
    if not visible:
        return definitions
    visible.sort(key=lambda definition: (-len(definition.declaration_module_path), definition.canonical_path.casefold()))
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
    limit: int = 100,
) -> list[CompletionItem]:
    lines = source_text.splitlines()
    current_line = lines[line] if 0 <= line < len(lines) else ""
    line_prefix = current_line[:column]
    module_path = infer_module_path_from_source(source_text, line)

    dotted_match = _BASE_COMPLETION_RE.search(line_prefix)
    if dotted_match:
        base_expr = dotted_match.group("base")
        prefix = dotted_match.group("prefix") or ""
        items_by_label: dict[str, CompletionItem] = {}
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
                    CompletionItem(
                        label=field.name,
                        kind=CompletionItemKind.Field,
                        detail=str(field.datatype.value if isinstance(field.datatype, Simple_DataType) else field.datatype),
                    ),
                )
        return list(items_by_label.values())[:limit]

    prefix_match = _IDENTIFIER_PREFIX_RE.search(line_prefix)
    prefix = prefix_match.group("prefix") if prefix_match else ""
    semantic_items = snapshot.complete(prefix=prefix, module_path=module_path, limit=limit)
    return [
        CompletionItem(
            label=item.label,
            kind=_semantic_completion_kind(item.kind),
            detail=item.detail,
        )
        for item in semantic_items
    ]


def build_source_path_index(paths: set[Path]) -> tuple[dict[str, tuple[Path, ...]], dict[tuple[str, str], Path]]:
    by_name: dict[str, list[Path]] = {}
    by_key: dict[tuple[str, str], Path] = {}
    for path in sorted(paths):
        file_key = path.name.casefold()
        by_name.setdefault(file_key, []).append(path)
        by_key[(file_key, path.parent.name.casefold())] = path
    return ({name: tuple(items) for name, items in by_name.items()}, by_key)


def resolve_definition_path(bundle: SnapshotBundle, definition: SymbolDefinition) -> Path | None:
    if not definition.source_file:
        return None
    file_key = definition.source_file.casefold()
    library_key = (definition.source_library or "").casefold()
    direct = bundle.source_paths_by_key.get((file_key, library_key))
    if direct is not None:
        return direct
    candidates = bundle.source_paths_by_name.get(file_key, ())
    if len(candidates) == 1:
        return candidates[0]
    return None


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
    preferred: list[CompletionItem],
    fallback: list[CompletionItem],
    *,
    limit: int,
) -> list[CompletionItem]:
    def kind_value(item: CompletionItem) -> int:
        return int(item.kind) if item.kind is not None else 0

    items_by_label: dict[tuple[str, int], CompletionItem] = {}
    for item in [*preferred, *fallback]:
        key = (item.label.casefold(), kind_value(item))
        items_by_label.setdefault(key, item)
    merged = sorted(items_by_label.values(), key=lambda item: (item.label.casefold(), kind_value(item)))
    return merged[:limit]


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
        except Exception:
            return []

    definitions = local_snapshot.find_definitions_at(document_path, line + 1, column + 1)
    if not definitions:
        reference_expr = _reference_expr_at_position(source_text, line=line, column=column)
        if reference_expr:
            definitions = _filter_visible_definitions(
                local_snapshot.find_definitions(reference_expr),
                infer_module_path_from_source(source_text, line),
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
    limit: int = 100,
    snapshot: SemanticSnapshot | None = None,
) -> list[CompletionItem]:
    local_snapshot = snapshot
    if local_snapshot is None:
        try:
            local_snapshot = load_source_snapshot(document_path, source_text)
        except Exception:
            return []

    return collect_completion_candidates(
        local_snapshot,
        source_text,
        line=line,
        column=column,
        limit=limit,
    )


def collect_semantic_diagnostics(bundle: SnapshotBundle, document_path: Path) -> list[Diagnostic]:
    resolved_path = document_path.resolve()
    diagnostics: list[Diagnostic] = []

    for issue in bundle.snapshot.diagnostics:
        if issue.variable is None:
            continue

        query_segments = list(issue.module_path) + [issue.variable.name]
        if issue.field_path:
            query_segments.extend(segment for segment in issue.field_path.split(".") if segment)

        matches = bundle.snapshot.find_definitions(".".join(query_segments), limit=1)
        if not matches:
            continue

        definition = matches[0]
        target_path = resolve_definition_path(bundle, definition)
        if target_path is None or target_path.resolve() != resolved_path:
            continue

        range_ = _range_for_definition(definition)
        if range_ is None:
            continue

        label = _ISSUE_LABELS.get(issue.kind, "SattLint issue")
        message = label if issue.role is None else f"{label}: {issue.role}"
        diagnostics.append(
            Diagnostic(
                range=range_,
                message=message,
                severity=DiagnosticSeverity.Warning,
                source="sattlint",
            )
        )

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
    state = ls.document_states.get(uri)
    if state is None:
        state = DocumentState(uri=uri, path=document_path, version=version, text=text)
        ls.document_states[uri] = state
        return state

    state.path = document_path
    state.replace_text(version=version, text=text)
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
    state = ls.document_states.get(uri)
    if state is None:
        state = DocumentState(uri=uri, path=document_path, version=version, text=fallback_text)
        ls.document_states[uri] = state

    state.path = document_path
    state.apply_changes(version=version, content_changes=content_changes, fallback_text=fallback_text)
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


def _workspace_root_for_document(ls: SattLineLanguageServer, document_path: Path) -> Path:
    return (ls.workspace_root or document_path.parent).resolve()


def _cache_key(entry_file: Path) -> str:
    return entry_file.as_posix().casefold()


def _load_snapshot_bundle(ls: SattLineLanguageServer, document_path: Path) -> SnapshotBundle | None:
    workspace_root = _workspace_root_for_document(ls, document_path)
    entry_file = resolve_entry_file(
        document_path,
        workspace_root=workspace_root,
        configured_entry_file=ls.settings.entry_file,
    )
    if entry_file is None:
        return None

    key = _cache_key(entry_file)
    cached = ls.snapshot_cache.get(key)
    if cached is not None:
        return cached

    snapshot = load_workspace_snapshot(
        entry_file,
        workspace_root=workspace_root,
        mode=ls.settings.mode,
        scan_root_only=ls.settings.scan_root_only,
        collect_variable_diagnostics=ls.settings.enable_variable_diagnostics,
    )
    by_name, by_key = build_source_path_index(snapshot.project_graph.source_files)
    bundle = SnapshotBundle(snapshot=snapshot, source_paths_by_name=by_name, source_paths_by_key=by_key)
    ls.snapshot_cache[key] = bundle
    return bundle


def _publish_diagnostics(
    ls: SattLineLanguageServer,
    document: TextDocument,
    *,
    include_semantic: bool = True,
    include_comment_validation: bool = True,
) -> None:
    document_path = _document_path(document)
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

    if not include_semantic:
        ls.text_document_publish_diagnostics(PublishDiagnosticsParams(uri=document.uri, diagnostics=[]))
        return

    if not ls.settings.enable_variable_diagnostics:
        ls.text_document_publish_diagnostics(PublishDiagnosticsParams(uri=document.uri, diagnostics=[]))
        return

    try:
        bundle = _load_snapshot_bundle(ls, document_path)
    except Exception as exc:
        ls.text_document_publish_diagnostics(
            PublishDiagnosticsParams(uri=document.uri, diagnostics=[_diagnostic_from_message(str(exc), None, None)])
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
        PublishDiagnosticsParams(uri=document.uri, diagnostics=collect_semantic_diagnostics(bundle, document_path))
    )


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
    ls.snapshot_cache.clear()
    ls.document_states.clear()


@server.feature("textDocument/didOpen")
def on_did_open(ls: SattLineLanguageServer, params: DidOpenTextDocumentParams) -> None:
    document = ls.workspace.get_text_document(params.text_document.uri)
    _record_document_open(
        ls,
        _document_path(document),
        uri=document.uri,
        version=params.text_document.version,
        text=params.text_document.text,
    )
    _publish_diagnostics(ls, document)


@server.feature("textDocument/didChange")
def on_did_change(ls: SattLineLanguageServer, params: DidChangeTextDocumentParams) -> None:
    document = ls.workspace.get_text_document(params.text_document.uri)
    _record_document_change(
        ls,
        _document_path(document),
        uri=document.uri,
        version=params.text_document.version,
        content_changes=list(params.content_changes or []),
        fallback_text=document.source,
    )
    _publish_diagnostics(ls, document, include_semantic=False, include_comment_validation=False)


@server.feature("textDocument/didSave")
def on_did_save(ls: SattLineLanguageServer, params: DidSaveTextDocumentParams) -> None:
    document = ls.workspace.get_text_document(params.text_document.uri)
    _record_document_open(
        ls,
        _document_path(document),
        uri=document.uri,
        version=getattr(document, "version", 0),
        text=document.source,
    )
    ls.snapshot_cache.clear()
    _publish_diagnostics(ls, document)


@server.feature("textDocument/didClose")
def on_did_close(ls: SattLineLanguageServer, params: DidCloseTextDocumentParams) -> None:
    ls.document_states.pop(params.text_document.uri, None)


@server.feature("textDocument/definition")
def on_definition(ls: SattLineLanguageServer, params: DefinitionParams) -> list[Location] | None:
    document = ls.workspace.get_text_document(params.text_document.uri)
    document_path = _document_path(document)
    source_text = _source_text_for_document(ls, document)
    local_snapshot = _get_or_build_local_snapshot(ls, document, document_path)

    bundle = _load_snapshot_bundle(ls, document_path)
    if bundle is None:
        local_locations = collect_local_definition_locations(
            document_path,
            source_text,
            line=params.position.line,
            column=params.position.character,
            snapshot=local_snapshot,
        )
        return local_locations or None

    candidates = _overlay_definition_candidates(
        bundle,
        document_path=document_path,
        source_text=source_text,
        line=params.position.line,
        column=params.position.character,
        local_snapshot=local_snapshot,
    )
    locations = _definition_locations_from_candidates(
        candidates,
        bundle=bundle,
        local_snapshot=local_snapshot,
        active_document_path=document_path,
    )
    return locations or None


@server.feature("textDocument/completion", CompletionOptions(trigger_characters=["."]))
def on_completion(ls: SattLineLanguageServer, params: TextDocumentPositionParams) -> CompletionList:
    document = ls.workspace.get_text_document(params.text_document.uri)
    document_path = _document_path(document)
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

    bundle = _load_snapshot_bundle(ls, document_path)
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
