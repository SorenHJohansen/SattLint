"""SattLint language-server document state and diagnostic management."""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Any

from lsprotocol.types import (
    Diagnostic,
    PublishDiagnosticsParams,
)
from pygls.workspace import TextDocument

from sattlint.core.semantic import SemanticSnapshot, SymbolDefinition

from ._server_helpers import (
    _DIAGNOSTIC_SNAPSHOT_WAIT_S,
    _INTERACTIVE_SNAPSHOT_WAIT_S,
    _RECOVERABLE_LSP_EXCEPTIONS,
    _diagnostic_from_message,
    _diagnostic_signature,
    _document_path,
    _document_uri_for_path,
    _is_diagnostic_path,
    _is_program_path,
    _local_definition_candidates,
    _merge_unique_diagnostics,
    _overlay_definition_candidates,
    _root_workspace_failure_message,
    _semantic_diagnostics_for_path,
)
from .document_state import DocumentState
from .workspace_store import SnapshotBundle

if TYPE_CHECKING:
    from .server import SattLineLanguageServer

log = logging.getLogger(__name__)


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
    except _RECOVERABLE_LSP_EXCEPTIONS as exc:
        log.warning(
            "LSP snapshot compatibility fallback failed; path=%s error=%s",
            document_path,
            exc,
        )
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
                        "Could not determine the root program for this file. Set "
                        "sattlineLsp.entryFile in VS Code when editing libraries in "
                        "multi-program workspaces.",
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
            if ls.workspace_scan_thread is not None:
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
        except _RECOVERABLE_LSP_EXCEPTIONS as exc:
            log.warning(
                "LSP closed-document snapshot load failed; fallback=entry-diagnostics path=%s error=%s",
                resolved_path,
                exc,
            )
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
