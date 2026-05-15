"""Rename and completion LSP request handlers."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from lsprotocol.types import CompletionList, RenameParams, TextDocumentPositionParams, TextEdit, WorkspaceEdit
from pygls import uris

from ._server_document import resolve_symbol_context as _resolve_symbol_context
from ._server_helpers import collect_completion_candidates
from ._server_helpers import collect_reference_matches as _collect_reference_matches
from ._server_helpers import is_program_path as _is_program_path
from ._server_helpers import range_from_position as _range_from_position
from ._server_helpers import resolve_reference_path as _resolve_reference_path
from ._server_navigation import _declaration_locations

if TYPE_CHECKING:
    from .server import SattLineLanguageServer


def handle_rename(
    ls: SattLineLanguageServer,
    params: RenameParams,
    *,
    validated_rename_request: Callable[[Any], tuple[str, int, int, str] | None],
    validate_rename_target: Callable[[str], None],
    append_workspace_edit: Callable[[dict[str, list[TextEdit]], str, Any, str], None],
) -> WorkspaceEdit | None:
    request = validated_rename_request(params)
    if request is None:
        return None

    document_uri, line, character, new_name = request
    validate_rename_target(new_name)

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

    for location in _declaration_locations(candidates, bundle_path=document_path, bundle=bundle):
        append_workspace_edit(changes, location.uri, location.range, new_name)

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
        append_workspace_edit(
            changes,
            reference_uri,
            _range_from_position(reference.line, reference.column, reference.length),
            new_name,
        )

    if not changes:
        return None
    return WorkspaceEdit(changes=changes)


def handle_completion(
    ls: SattLineLanguageServer,
    params: TextDocumentPositionParams,
    *,
    validated_text_document_position: Callable[[Any], tuple[str, int, int] | None],
    document_path: Callable[[Any], Any],
    source_text_for_document: Callable[[SattLineLanguageServer, Any], str],
    get_or_build_local_snapshot: Callable[[SattLineLanguageServer, Any, Any], Any],
    load_snapshot_bundle_compat: Callable[..., Any],
    collect_local_completion_candidates: Callable[..., list[Any]],
    merge_completion_items: Callable[..., list[Any]],
    interactive_snapshot_wait_s: float,
) -> CompletionList:
    request = validated_text_document_position(params)
    if request is None:
        return CompletionList(is_incomplete=False, items=[])

    document_uri, line, character = request
    document = ls.workspace.get_text_document(document_uri)
    document_fs_path = document_path(document)
    if not _is_program_path(document_fs_path):
        return CompletionList(is_incomplete=False, items=[])

    source_text = source_text_for_document(ls, document)
    local_snapshot = get_or_build_local_snapshot(ls, document, document_fs_path)

    local_items = collect_local_completion_candidates(
        document_fs_path,
        source_text,
        line=line,
        column=character,
        limit=ls.settings.max_completion_items,
        snapshot=local_snapshot,
    )

    bundle = load_snapshot_bundle_compat(
        ls,
        document_fs_path,
        wait_budget=interactive_snapshot_wait_s,
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
    items = merge_completion_items(
        local_items,
        workspace_items,
        limit=ls.settings.max_completion_items,
    )
    return CompletionList(is_incomplete=False, items=items)
