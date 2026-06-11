"""Workspace-scan scheduling and workspace-diagnostics helpers."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import TYPE_CHECKING

from lsprotocol.types import Diagnostic, PublishDiagnosticsParams

from ._server_helpers import (
    diagnostic_from_message as _diagnostic_from_message,
)
from ._server_helpers import (
    diagnostic_signature as _diagnostic_signature,
)
from ._server_helpers import (
    document_uri_for_path as _document_uri_for_path,
)
from ._server_helpers import (
    merge_unique_diagnostics as _merge_unique_diagnostics,
)
from ._server_helpers import (
    root_workspace_failure_message as _root_workspace_failure_message,
)
from ._server_symbol_helpers import semantic_diagnostics_for_path as _semantic_diagnostics_for_path
from .document_state import DocumentState

if TYPE_CHECKING:
    from .server import SattLineLanguageServer


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
    except Exception as exc:  # noqa: BLE001
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
    if not (ls.settings.enable_variable_diagnostics and ls.settings.workspace_diagnostics_mode == "background"):
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
            thread = threading.Thread(
                target=_workspace_scan_worker,
                args=(ls,),
                name="sattline-workspace-scan",
                daemon=True,
            )
            ls.workspace_scan_thread = thread
            thread.start()


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


collect_entry_workspace_diagnostics = _collect_entry_workspace_diagnostics
document_state_for_path = _document_state_for_path
invalidate_cached_entries_for_path = _invalidate_cached_entries_for_path
process_workspace_scan_entries = _process_workspace_scan_entries
publish_workspace_diagnostics_for_paths = _publish_workspace_diagnostics_for_paths
schedule_workspace_scan = _schedule_workspace_scan
store_entry_workspace_diagnostics = _store_entry_workspace_diagnostics
workspace_scan_worker = _workspace_scan_worker
