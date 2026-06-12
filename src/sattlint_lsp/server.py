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
    overlay_definition_candidates as _overlay_definition_candidates,
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
from ._server_navigation import handle_definition as _handle_definition
from ._server_navigation import handle_hover as _handle_hover
from ._server_navigation import handle_references as _handle_references
from ._server_rename_completion import handle_completion as _handle_completion
from ._server_rename_completion import handle_rename as _handle_rename
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
    collect_completion_candidates,
    collect_local_completion_candidates,
    collect_local_definition_locations,
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


def _clear_workspace_diagnostics(ls: SattLineLanguageServer) -> None:
    with ls.workspace_scan_condition:
        affected_paths = {path.resolve() for path in ls.published_workspace_diagnostics}
        for diagnostics_by_path in ls.entry_diagnostics.values():
            affected_paths.update(path.resolve() for path in diagnostics_by_path)
        ls.entry_diagnostics.clear()
        ls.entry_scan_generation.clear()
        ls.workspace_scan_pending.clear()
    if affected_paths:
        _publish_workspace_diagnostics_for_paths(ls, affected_paths)


def _clear_workspace_entries(ls: SattLineLanguageServer, entry_files: tuple[Path, ...]) -> None:
    if not entry_files:
        return

    with ls.workspace_scan_condition:
        affected_paths: set[Path] = set()
        removed_keys = {entry_file.resolve().as_posix().casefold() for entry_file in entry_files}
        for entry_key in removed_keys:
            previous = ls.entry_diagnostics.pop(entry_key, {})
            affected_paths.update(path.resolve() for path in previous)
            ls.entry_scan_generation.pop(entry_key, None)
        ls.workspace_scan_pending = {
            path for path in ls.workspace_scan_pending if path.resolve().as_posix().casefold() not in removed_keys
        }

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
    with ls.workspace_scan_condition:
        ls.entry_diagnostics.clear()
        ls.published_workspace_diagnostics.clear()
        ls.entry_scan_generation.clear()
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
            invalidated_entries = _invalidate_cached_entries_for_path(ls, document_path)
            refresh_result = ls.snapshot_store.refresh_workspace()
            _clear_workspace_entries(ls, refresh_result.removed_entries)
            refreshed_entries = tuple(
                sorted(
                    {
                        *(entry.resolve() for entry in invalidated_entries),
                        *(entry.resolve() for entry in refresh_result.affected_entries),
                    },
                    key=lambda path: path.as_posix().casefold(),
                )
            )
            _schedule_workspace_scan(ls, refreshed_entries)
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
    return _handle_definition(ls, params)


@server.feature("textDocument/hover")
def on_hover(ls: SattLineLanguageServer, params: HoverParams) -> Hover | None:
    return _handle_hover(ls, params)


@server.feature("textDocument/references")
def on_references(ls: SattLineLanguageServer, params: ReferenceParams) -> list[Location] | None:
    return _handle_references(ls, params)


@server.feature("textDocument/rename")
def on_rename(ls: SattLineLanguageServer, params: RenameParams) -> WorkspaceEdit | None:
    return _handle_rename(
        ls,
        params,
        validated_rename_request=_validated_rename_request,
        validate_rename_target=_validate_rename_target,
        append_workspace_edit=_append_workspace_edit,
    )


@server.feature("textDocument/completion", CompletionOptions(trigger_characters=["."]))
def on_completion(ls: SattLineLanguageServer, params: TextDocumentPositionParams) -> CompletionList:
    return _handle_completion(
        ls,
        params,
        validated_text_document_position=_validated_text_document_position,
        document_path=_document_path,
        source_text_for_document=_source_text_for_document,
        get_or_build_local_snapshot=_get_or_build_local_snapshot,
        load_snapshot_bundle_compat=_load_snapshot_bundle_compat,
        collect_local_completion_candidates=collect_local_completion_candidates,
        merge_completion_items=_merge_completion_items,
        interactive_snapshot_wait_s=_INTERACTIVE_SNAPSHOT_WAIT_S,
    )


def cli() -> None:
    server.start_io()


if __name__ == "__main__":
    cli()
