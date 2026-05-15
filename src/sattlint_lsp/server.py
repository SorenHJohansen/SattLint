"""SattLint-backed Language Server Protocol implementation for VS Code and other editors."""

from __future__ import annotations

import threading
from pathlib import Path

from lsprotocol.types import (
    CompletionList,
    CompletionOptions,
    DefinitionParams,
    Diagnostic,
    DidChangeConfigurationParams,
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
    ensure_document_paths as _ensure_document_paths,
)
from ._server_document import (
    ensure_snapshot_store_configured as _ensure_snapshot_store_configured,
)
from ._server_document import (
    get_or_build_local_snapshot as _get_or_build_local_snapshot,
)
from ._server_document import (
    invalidate_cached_entries_for_path as _invalidate_cached_entries_for_path,
)
from ._server_document import (
    load_snapshot_bundle as _load_snapshot_bundle,
)
from ._server_document import (
    load_snapshot_bundle_compat as _load_snapshot_bundle_compat,
)
from ._server_document import (
    publish_closed_document_diagnostics as _publish_closed_document_diagnostics,
)
from ._server_document import (
    publish_diagnostics as _publish_diagnostics,
)
from ._server_document import (
    publish_workspace_diagnostics_for_paths as _publish_workspace_diagnostics_for_paths,
)
from ._server_document import (
    record_document_change as _record_document_change,
)
from ._server_document import (
    record_document_open as _record_document_open,
)
from ._server_document import (
    resolve_symbol_context as _resolve_symbol_context,
)
from ._server_document import (
    schedule_workspace_scan as _schedule_workspace_scan,
)
from ._server_document import (
    source_text_for_document as _source_text_for_document,
)
from ._server_helpers import (
    DEFAULT_LOCAL_PARSER as _DEFAULT_LOCAL_PARSER,
)
from ._server_helpers import (
    INTERACTIVE_SNAPSHOT_WAIT_S as _INTERACTIVE_SNAPSHOT_WAIT_S,
)
from ._server_helpers import (
    LspSettings,
    build_source_path_index,
    collect_completion_candidates,
    collect_local_completion_candidates,
    collect_local_definition_locations,
    collect_semantic_diagnostics,
    collect_syntax_diagnostics,
    infer_module_path_from_source,
    resolve_definition_path,
    resolve_entry_file,
)
from ._server_helpers import (
    append_workspace_edit as _append_workspace_edit,
)
from ._server_helpers import (
    build_hover as _build_hover,
)
from ._server_helpers import (
    collect_reference_matches as _collect_reference_matches,
)
from ._server_helpers import (
    definition_locations_from_candidates as _definition_locations_from_candidates,
)
from ._server_helpers import (
    definition_uri as _definition_uri,
)
from ._server_helpers import (
    document_path as _document_path,
)
from ._server_helpers import (
    is_diagnostic_path as _is_diagnostic_path,
)
from ._server_helpers import (
    is_program_path as _is_program_path,
)
from ._server_helpers import (
    merge_completion_items as _merge_completion_items,
)
from ._server_helpers import (
    merge_locations as _merge_locations,
)
from ._server_helpers import (
    overlay_definition_candidates as _overlay_definition_candidates,
)
from ._server_helpers import (
    range_for_definition as _range_for_definition,
)
from ._server_helpers import (
    range_from_position as _range_from_position,
)
from ._server_helpers import (
    reference_locations_from_matches as _reference_locations_from_matches,
)
from ._server_helpers import (
    resolve_reference_path as _resolve_reference_path,
)
from ._server_helpers import (
    semantic_diagnostics_for_path as _semantic_diagnostics_for_path,
)
from ._server_helpers import (
    validate_rename_target as _validate_rename_target,
)
from ._server_helpers import (
    validated_change_request as _validated_change_request,
)
from ._server_helpers import (
    validated_open_request as _validated_open_request,
)
from ._server_helpers import (
    validated_rename_request as _validated_rename_request,
)
from ._server_helpers import (
    validated_text_document_position as _validated_text_document_position,
)
from ._server_helpers import (
    validated_text_document_uri as _validated_text_document_uri,
)
from ._server_workspace import (
    is_workspace_control_path as _is_workspace_control_path,
)
from ._server_workspace import (
    workspace_settings_signature as _workspace_settings_signature,
)
from .document_state import DocumentState
from .workspace_store import SnapshotBundle, WorkspaceSnapshotStore


class SattLineLanguageServer(LanguageServer):
    def __init__(self) -> None:
        super().__init__(name="sattline-lsp", version="0.1.0")  # pyright: ignore[reportUnknownMemberType]
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


server = SattLineLanguageServer()

# Keep selected helper re-exports visible to external tests and tooling.
_PUBLIC_SERVER_HELPERS = (
    SnapshotBundle,
    build_source_path_index,
    collect_semantic_diagnostics,
    collect_syntax_diagnostics,
    infer_module_path_from_source,
    resolve_definition_path,
    resolve_entry_file,
    _load_snapshot_bundle,
    _publish_workspace_diagnostics_for_paths,
    _overlay_definition_candidates,
    _semantic_diagnostics_for_path,
)


def _clear_workspace_scan_state(ls: SattLineLanguageServer) -> None:
    ls.entry_scan_generation.clear()
    with ls.workspace_scan_condition:
        ls.workspace_scan_pending.clear()


def _clear_workspace_diagnostics(ls: SattLineLanguageServer) -> None:
    affected_paths = {path.resolve() for path in ls.published_workspace_diagnostics}
    for diagnostics_by_path in ls.entry_diagnostics.values():
        affected_paths.update(path.resolve() for path in diagnostics_by_path)
    ls.entry_diagnostics.clear()
    _clear_workspace_scan_state(ls)
    if affected_paths:
        _publish_workspace_diagnostics_for_paths(ls, affected_paths)


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


@server.feature("workspace/didChangeConfiguration")
def on_did_change_configuration(ls: SattLineLanguageServer, params: DidChangeConfigurationParams) -> None:
    previous_settings = ls.settings
    next_settings = LspSettings.from_initialization_options(getattr(params, "settings", None))
    ls.settings = next_settings

    if _workspace_settings_signature(previous_settings) == _workspace_settings_signature(next_settings):
        return

    _clear_workspace_diagnostics(ls)
    if not _ensure_snapshot_store_configured(ls):
        return
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
    workspace_control_path = _is_workspace_control_path(getattr(ls, "workspace_root", None), document_path)
    if not _is_diagnostic_path(document_path):
        state = ls.document_states.pop(document.uri, None)
        if state is not None:
            ls.document_paths.pop(state.path.resolve(), None)
        ls.text_document_publish_diagnostics(PublishDiagnosticsParams(uri=document.uri, diagnostics=[]))
        if workspace_control_path:
            _clear_workspace_diagnostics(ls)
            ls.snapshot_store.refresh_workspace()
            _schedule_workspace_scan(ls)
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
