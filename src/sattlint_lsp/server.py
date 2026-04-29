"""SattLint-backed Language Server Protocol implementation for VS Code and other editors."""

from __future__ import annotations

import threading
from pathlib import Path

from lsprotocol.types import (
    CompletionList,
    CompletionOptions,
    DefinitionParams,
    DidChangeTextDocumentParams,
    DidCloseTextDocumentParams,
    DidOpenTextDocumentParams,
    DidSaveTextDocumentParams,
    Hover,
    HoverParams,
    InitializeParams,
    Location,
    PublishDiagnosticsParams,
    ReferenceParams,
    RenameParams,
    TextDocumentPositionParams,
    TextEdit,
    WorkspaceEdit,
)
from pygls import uris
from pygls.lsp.server import LanguageServer

from ._server_document import (
    _ensure_document_paths,
    _ensure_snapshot_store_configured,
    _get_or_build_local_snapshot,  # noqa: F401
    _invalidate_cached_entries_for_path,  # noqa: F401
    _load_snapshot_bundle,  # noqa: F401
    _load_snapshot_bundle_compat,
    _publish_closed_document_diagnostics,  # noqa: F401
    _publish_diagnostics,  # noqa: F401
    _publish_workspace_diagnostics_for_paths,  # noqa: F401
    _record_document_change,
    _record_document_open,
    _resolve_symbol_context,
    _schedule_workspace_scan,
    _semantic_diagnostics_for_path,  # noqa: F401
    _source_text_for_document,
)
from ._server_helpers import (
    _DEFAULT_LOCAL_PARSER,
    _INTERACTIVE_SNAPSHOT_WAIT_S,
    LspSettings,
    _append_workspace_edit,
    _build_hover,
    _collect_reference_matches,
    _definition_locations_from_candidates,
    _definition_uri,
    _document_path,
    _is_diagnostic_path,
    _is_program_path,
    _merge_completion_items,
    _merge_locations,
    _overlay_definition_candidates,  # noqa: F401
    _range_for_definition,
    _range_from_position,
    _reference_locations_from_matches,
    _resolve_reference_path,
    _validate_rename_target,
    _validated_change_request,
    _validated_open_request,
    _validated_rename_request,
    _validated_text_document_position,
    _validated_text_document_uri,
    build_source_path_index,  # noqa: F401
    collect_completion_candidates,
    collect_local_completion_candidates,
    collect_local_definition_locations,
    collect_semantic_diagnostics,  # noqa: F401
    collect_syntax_diagnostics,  # noqa: F401
    infer_module_path_from_source,  # noqa: F401
    resolve_definition_path,  # noqa: F401
    resolve_entry_file,  # noqa: F401
)
from .document_state import DocumentState
from .workspace_store import SnapshotBundle, WorkspaceSnapshotStore  # noqa: F401


class SattLineLanguageServer(LanguageServer):
    def __init__(self) -> None:
        super().__init__(name="sattline-lsp", version="0.1.0")
        self.settings = LspSettings()
        self.workspace_root: Path | None = None
        self.snapshot_store = WorkspaceSnapshotStore()
        self.document_states: dict[str, DocumentState] = {}
        self.document_paths: dict[Path, str] = {}
        self.entry_diagnostics: dict[str, dict[Path, tuple]] = {}
        self.published_workspace_diagnostics: dict[Path, tuple] = {}
        self.workspace_scan_condition = threading.Condition()
        self.workspace_scan_pending: set[Path] = set()
        self.workspace_scan_generation = 0
        self.entry_scan_generation: dict[str, int] = {}
        self.workspace_scan_thread: threading.Thread | None = None
        self.local_parser = _DEFAULT_LOCAL_PARSER


server = SattLineLanguageServer()


@server.feature("initialize")
def on_initialize(ls: SattLineLanguageServer, params: InitializeParams) -> None:
    ls.settings = LspSettings.from_initialization_options(getattr(params, "initialization_options", None))
    root_uri = getattr(params, "root_uri", None)
    root_path = getattr(params, "root_path", None)
    if not isinstance(root_uri, str):
        root_uri = None
    if not isinstance(root_path, str):
        root_path = None

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
    request = _validated_open_request(params)
    if request is None:
        return

    document_uri, version, text = request
    document = ls.workspace.get_text_document(document_uri)
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
        version=version,
        text=text,
    )
    _publish_diagnostics(ls, document)


@server.feature("textDocument/didChange")
def on_did_change(ls: SattLineLanguageServer, params: DidChangeTextDocumentParams) -> None:
    request = _validated_change_request(params)
    if request is None:
        return

    document_uri, version, content_changes = request
    document = ls.workspace.get_text_document(document_uri)
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
        version=version,
        content_changes=content_changes,
        fallback_text=document.source,
    )
    _publish_diagnostics(ls, document, include_semantic=False, include_comment_validation=False)


@server.feature("textDocument/didSave")
def on_did_save(ls: SattLineLanguageServer, params: DidSaveTextDocumentParams) -> None:
    document_uri = _validated_text_document_uri(params)
    if document_uri is None:
        return

    document = ls.workspace.get_text_document(document_uri)
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
    document_uri = _validated_text_document_uri(params)
    if document_uri is None:
        return

    state = ls.document_states.pop(document_uri, None)
    document_path = state.path if state is not None else Path(uris.to_fs_path(document_uri) or document_uri)
    _ensure_document_paths(ls).pop(document_path.resolve(), None)
    if not _is_diagnostic_path(document_path):
        ls.text_document_publish_diagnostics(PublishDiagnosticsParams(uri=document_uri, diagnostics=[]))
        return

    if not _is_program_path(document_path):
        ls.text_document_publish_diagnostics(PublishDiagnosticsParams(uri=document_uri, diagnostics=[]))
        return

    _publish_closed_document_diagnostics(ls, document_path)


@server.feature("textDocument/definition")
def on_definition(ls: SattLineLanguageServer, params: DefinitionParams) -> list[Location] | None:
    request = _validated_text_document_position(params)
    if request is None:
        return None

    document_uri, line, character = request
    document = ls.workspace.get_text_document(document_uri)
    document_path, source_text, local_snapshot, bundle, candidates = _resolve_symbol_context(
        ls,
        document,
        line=line,
        column=character,
    )
    if not _is_program_path(document_path):
        return None

    if bundle is None:
        local_locations = collect_local_definition_locations(
            document_path,
            source_text,
            line=line,
            column=character,
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
    request = _validated_text_document_position(params)
    if request is None:
        return None

    document_uri, line, character = request
    document = ls.workspace.get_text_document(document_uri)
    document_path, _source_text, _local_snapshot, _bundle, candidates = _resolve_symbol_context(
        ls,
        document,
        line=line,
        column=character,
    )
    if not _is_program_path(document_path) or not candidates:
        return None
    return _build_hover(candidates[0])


@server.feature("textDocument/references")
def on_references(ls: SattLineLanguageServer, params: ReferenceParams) -> list[Location] | None:
    request = _validated_text_document_position(params)
    if request is None:
        return None

    document_uri, line, character = request
    document = ls.workspace.get_text_document(document_uri)
    document_path, _source_text, local_snapshot, bundle, candidates = _resolve_symbol_context(
        ls,
        document,
        line=line,
        column=character,
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
    request = _validated_rename_request(params)
    if request is None:
        return None

    document_uri, line, character, new_name = request
    _validate_rename_target(new_name)

    document = ls.workspace.get_text_document(document_uri)
    document_path, _source_text, local_snapshot, bundle, candidates = _resolve_symbol_context(
        ls,
        document,
        line=line,
        column=character,
    )
    if not _is_program_path(document_path) or not candidates:
        return None

    references = _collect_reference_matches(bundle, local_snapshot, candidates)
    changes: dict[str, list[TextEdit]] = {}

    for definition in candidates:
        target_range = _range_for_definition(definition)
        target_uri = _definition_uri(definition, bundle=bundle, active_document_path=document_path)
        if target_range is not None and target_uri is not None:
            _append_workspace_edit(changes, target_uri, target_range, new_name)

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
            new_name,
        )

    if not changes:
        return None
    return WorkspaceEdit(changes=changes)


@server.feature("textDocument/completion", CompletionOptions(trigger_characters=["."]))
def on_completion(ls: SattLineLanguageServer, params: TextDocumentPositionParams) -> CompletionList:
    request = _validated_text_document_position(params)
    if request is None:
        return CompletionList(is_incomplete=False, items=[])

    document_uri, line, character = request
    document = ls.workspace.get_text_document(document_uri)
    document_path = _document_path(document)
    if not _is_program_path(document_path):
        return CompletionList(is_incomplete=False, items=[])

    source_text = _source_text_for_document(ls, document)
    local_snapshot = _get_or_build_local_snapshot(ls, document, document_path)

    local_items = collect_local_completion_candidates(
        document_path,
        source_text,
        line=line,
        column=character,
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
        line=line,
        column=character,
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
