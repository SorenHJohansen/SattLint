"""SattLint language-server document state and diagnostic management."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from lsprotocol.types import PublishDiagnosticsParams
from pygls.workspace import TextDocument

from sattlint.core.semantic import SemanticSnapshot, SymbolDefinition

from ._server_helpers import (
    DIAGNOSTIC_SNAPSHOT_WAIT_S as _DIAGNOSTIC_SNAPSHOT_WAIT_S,
)
from ._server_helpers import (
    INTERACTIVE_SNAPSHOT_WAIT_S as _INTERACTIVE_SNAPSHOT_WAIT_S,
)
from ._server_helpers import (
    RECOVERABLE_LSP_EXCEPTIONS as _RECOVERABLE_LSP_EXCEPTIONS,
)
from ._server_helpers import (
    diagnostic_from_message as _diagnostic_from_message,
)
from ._server_helpers import (
    document_path as _document_path,
)
from ._server_helpers import (
    document_uri_for_path as _document_uri_for_path,
)
from ._server_helpers import (
    is_diagnostic_path as _is_diagnostic_path,
)
from ._server_helpers import (
    is_program_path as _is_program_path,
)
from ._server_helpers import (
    local_definition_candidates as _local_definition_candidates,
)
from ._server_helpers import (
    merge_unique_diagnostics as _merge_unique_diagnostics,
)
from ._server_helpers import (
    overlay_definition_candidates as _overlay_definition_candidates,
)
from ._server_helpers import (
    root_workspace_failure_message as _root_workspace_failure_message,
)
from ._server_helpers import (
    semantic_diagnostics_for_path as _semantic_diagnostics_for_path,
)
from ._server_scan_helpers import (
    document_state_for_path as _document_state_for_path,
)
from ._server_scan_helpers import (
    invalidate_cached_entries_for_path as _invalidate_cached_entries_for_path,
)
from ._server_scan_helpers import (
    publish_workspace_diagnostics_for_paths as _publish_workspace_diagnostics_for_paths,
)
from ._server_scan_helpers import (
    schedule_workspace_scan as _schedule_workspace_scan,
)
from .document_state import DocumentState
from .workspace_store import SnapshotBundle

_SCAN_HELPER_COMPAT_EXPORTS = (_document_state_for_path,)

if TYPE_CHECKING:
    from .server import SattLineLanguageServer

log = logging.getLogger(__name__)


def _ensure_snapshot_store_configured(ls: SattLineLanguageServer) -> bool:
    return ls.snapshot_store.ensure_configured(ls.workspace_root, ls.settings)


def _ensure_document_paths(ls: SattLineLanguageServer) -> dict[Path, str]:
    document_paths_obj = getattr(ls, "document_paths", None)
    if isinstance(document_paths_obj, dict):
        return cast(dict[Path, str], document_paths_obj)

    document_paths: dict[Path, str] = {}
    ls.document_paths = document_paths
    return document_paths


def _background_workspace_diagnostics_enabled(ls: SattLineLanguageServer) -> bool:
    return ls.settings.enable_variable_diagnostics and ls.settings.workspace_diagnostics_mode == "background"


_DOCUMENT_COMPAT_EXPORTS = (_background_workspace_diagnostics_enabled,)


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
    except Exception as exc:  # noqa: BLE001
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


ensure_document_paths = _ensure_document_paths
ensure_snapshot_store_configured = _ensure_snapshot_store_configured
get_or_build_local_snapshot = _get_or_build_local_snapshot
invalidate_cached_entries_for_path = _invalidate_cached_entries_for_path
load_snapshot_bundle = _load_snapshot_bundle
load_snapshot_bundle_compat = _load_snapshot_bundle_compat
publish_closed_document_diagnostics = _publish_closed_document_diagnostics
publish_diagnostics = _publish_diagnostics
publish_workspace_diagnostics_for_paths = _publish_workspace_diagnostics_for_paths
record_document_change = _record_document_change
record_document_open = _record_document_open
resolve_symbol_context = _resolve_symbol_context
schedule_workspace_scan = _schedule_workspace_scan
source_text_for_document = _source_text_for_document
