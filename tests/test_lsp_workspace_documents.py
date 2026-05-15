"""Workspace document and workspace-diagnostics focused LSP tests."""

from __future__ import annotations

import threading
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from lsprotocol.types import Position, Range

from sattlint_lsp.document_state import DocumentState
from sattlint_lsp.server import (
    LspSettings,
    SattLineLanguageServer,
    SnapshotBundle,
    _invalidate_cached_entries_for_path,
    _publish_closed_document_diagnostics,
    _publish_workspace_diagnostics_for_paths,
    _semantic_diagnostics_for_path,
    on_did_change,
    on_did_change_configuration,
    on_did_close,
    on_did_open,
    on_did_save,
    on_initialize,
)


def test_publish_workspace_diagnostics_for_paths_deduplicates_shared_library_diagnostics(tmp_path):
    shared = (tmp_path / "Libs" / "Shared.s").resolve()
    diagnostic = cast(
        Any,
        SimpleNamespace(
            range=Range(start=Position(line=0, character=0), end=Position(line=0, character=1)),
            message="Unused variable: localvariable",
            severity=1,
            source="sattlint",
        ),
    )
    ls = SattLineLanguageServer()
    ls.workspace_root = tmp_path
    ls.settings = LspSettings(enable_variable_diagnostics=True, workspace_diagnostics_mode="background")
    ls.entry_diagnostics = {
        "entry-a": {shared: (diagnostic,)},
        "entry-b": {shared: (diagnostic,)},
    }

    _publish_workspace_diagnostics_for_paths(ls, {shared})

    assert shared in ls.published_workspace_diagnostics
    assert len(ls.published_workspace_diagnostics[shared]) == 1
    assert ls.published_workspace_diagnostics[shared][0].message.startswith("Unused variable")


def test_publish_closed_document_diagnostics_restores_workspace_diagnostics(tmp_path):
    path = (tmp_path / "Libs" / "Shared.s").resolve()
    diagnostic = cast(
        Any,
        SimpleNamespace(
            range=Range(start=Position(line=0, character=0), end=Position(line=0, character=1)),
            message="Unused variable",
            severity=1,
            source="sattlint",
        ),
    )
    published = []

    ls = SattLineLanguageServer()
    ls.text_document_publish_diagnostics = lambda params: published.append(params)
    ls.entry_diagnostics = {"entry": {path: (diagnostic,)}}

    _publish_closed_document_diagnostics(ls, path)

    assert len(published) == 1
    assert published[0].uri.casefold() == path.as_uri().casefold()
    assert len(published[0].diagnostics) == 1
    assert published[0].diagnostics[0].message == "Unused variable"
    assert ls.published_workspace_diagnostics[path][0].message == "Unused variable"


def test_publish_closed_document_diagnostics_loads_snapshot_when_cache_is_empty(monkeypatch, tmp_path):
    path = (tmp_path / "Program" / "Main.s").resolve()
    diagnostic = cast(
        Any,
        SimpleNamespace(
            range=Range(start=Position(line=1, character=2), end=Position(line=1, character=5)),
            message="Variable is written but never read",
            severity=2,
            source="sattlint",
        ),
    )
    published = []
    fake_bundle = SnapshotBundle(
        snapshot=cast(Any, object()),
        source_paths_by_name={},
        source_paths_by_key={},
        entry_file=path,
        cache_key=path.as_posix().casefold(),
        source_files=(path,),
    )

    ls = SattLineLanguageServer()
    ls.text_document_publish_diagnostics = lambda params: published.append(params)

    monkeypatch.setattr(
        "sattlint_lsp._server_document._load_snapshot_bundle", lambda server, document_path: fake_bundle
    )
    monkeypatch.setattr(
        "sattlint_lsp._server_helpers.collect_semantic_diagnostics", lambda bundle, document_path: [diagnostic]
    )

    _publish_closed_document_diagnostics(ls, path)

    assert len(published) == 1
    assert published[0].uri.casefold() == path.as_uri().casefold()
    assert len(published[0].diagnostics) == 1
    assert published[0].diagnostics[0].message == "Variable is written but never read"
    assert ls.published_workspace_diagnostics[path][0].message == "Variable is written but never read"


def test_semantic_diagnostics_for_path_reuses_bundle_cache(monkeypatch, tmp_path):
    path = (tmp_path / "Program" / "Main.s").resolve()
    diagnostic = cast(
        Any,
        SimpleNamespace(
            range=Range(start=Position(line=0, character=0), end=Position(line=0, character=1)),
            message="Unused variable",
            severity=1,
            source="sattlint",
        ),
    )
    bundle = SnapshotBundle(
        snapshot=cast(Any, object()),
        source_paths_by_name={},
        source_paths_by_key={},
        entry_file=path,
        cache_key=path.as_posix().casefold(),
        source_files=(path,),
    )
    calls = 0

    def fake_collect(current_bundle, document_path):
        nonlocal calls
        calls += 1
        assert current_bundle is bundle
        assert document_path == path
        return [diagnostic]

    monkeypatch.setattr("sattlint_lsp._server_helpers.collect_semantic_diagnostics", fake_collect)

    first = _semantic_diagnostics_for_path(bundle, path)
    second = _semantic_diagnostics_for_path(bundle, path)

    assert len(first) == 1
    assert first is second
    assert first[0].message == "Unused variable"
    assert calls == 1


def test_on_did_close_clears_stale_diagnostics_when_no_workspace_diagnostics_exist(tmp_path):
    path = (tmp_path / "Program" / "Main.s").resolve()
    uri = path.as_uri()
    published = []

    ls = SattLineLanguageServer()
    ls.text_document_publish_diagnostics = lambda params: published.append(params)
    ls.document_states[uri] = DocumentState(
        uri=uri,
        path=path,
        version=2,
        text="Alpha = ;\n",
        is_dirty=True,
    )

    on_did_close(ls, cast(Any, SimpleNamespace(text_document=SimpleNamespace(uri=uri))))

    assert uri not in ls.document_states
    assert len(published) == 1
    assert published[0].uri.casefold() == uri.casefold()
    assert published[0].diagnostics == []


def test_invalidate_cached_entries_for_path_marks_affected_entries_stale(tmp_path):
    entry_a = (tmp_path / "Programs" / "PlantA.s").resolve()
    entry_b = (tmp_path / "Programs" / "PlantB.s").resolve()
    shared = (tmp_path / "Libs" / "Shared.s").resolve()
    other = (tmp_path / "Libs" / "Other.s").resolve()

    diagnostic = cast(
        Any,
        SimpleNamespace(
            range=Range(start=Position(line=0, character=0), end=Position(line=0, character=1)),
            message="Unused variable",
            severity=1,
            source="sattlint",
        ),
    )
    key_a = entry_a.as_posix().casefold()
    key_b = entry_b.as_posix().casefold()
    bundle_a = SnapshotBundle(
        snapshot=cast(Any, None),
        source_paths_by_name={},
        source_paths_by_key={},
        entry_file=entry_a,
        cache_key=key_a,
        source_files=(entry_a, shared),
    )
    bundle_b = SnapshotBundle(
        snapshot=cast(Any, None),
        source_paths_by_name={},
        source_paths_by_key={},
        entry_file=entry_b,
        cache_key=key_b,
        source_files=(entry_b, other),
    )

    ls = SattLineLanguageServer()
    ls.workspace_root = tmp_path
    ls.settings = LspSettings(enable_variable_diagnostics=True, workspace_diagnostics_mode="background")
    ls.snapshot_store.ensure_configured(tmp_path, ls.settings)
    with ls.snapshot_store._lock:
        state_a = ls.snapshot_store._state_for_entry_locked(entry_a)
        state_a.bundle = bundle_a
        state_b = ls.snapshot_store._state_for_entry_locked(entry_b)
        state_b.bundle = bundle_b
        ls.snapshot_store._source_file_to_entry_keys = {
            entry_a: {key_a},
            shared: {key_a},
            entry_b: {key_b},
            other: {key_b},
        }
    ls.entry_diagnostics = {
        key_a: {shared: (diagnostic,)},
        key_b: {other: (diagnostic,)},
    }
    ls.published_workspace_diagnostics = {shared: (diagnostic,), other: (diagnostic,)}

    affected_entries = _invalidate_cached_entries_for_path(ls, shared)

    assert affected_entries == (entry_a,)
    with ls.snapshot_store._lock:
        assert ls.snapshot_store._states[key_a].stale is True
        assert ls.snapshot_store._states[key_b].stale is False
        assert shared in ls.snapshot_store._source_file_to_entry_keys
    assert shared not in ls.published_workspace_diagnostics
    assert other in ls.published_workspace_diagnostics


def test_on_initialize_resets_server_state_and_prefers_root_uri(monkeypatch, tmp_path):
    ls = SattLineLanguageServer()
    ls.document_states["file:///old.s"] = DocumentState(
        uri="file:///old.s",
        path=tmp_path / "old.s",
        version=1,
        text="x",
    )
    ls.document_paths[(tmp_path / "old.s").resolve()] = "file:///old.s"
    ls.entry_diagnostics["entry"] = {}
    ls.published_workspace_diagnostics[(tmp_path / "old.s").resolve()] = ()
    ls.entry_scan_generation["entry"] = 1
    calls: list[str] = []

    monkeypatch.setattr(
        "sattlint_lsp.server._ensure_snapshot_store_configured", lambda current_ls: calls.append("configured") or True
    )
    monkeypatch.setattr(
        "sattlint_lsp.server._schedule_workspace_scan", lambda current_ls, entry_files=None: calls.append("scan")
    )

    params = SimpleNamespace(
        initialization_options={"workspaceDiagnosticsMode": "background"},
        root_uri=tmp_path.resolve().as_uri(),
        root_path=str(tmp_path / "ignored"),
    )

    on_initialize(ls, cast(Any, params))

    assert ls.workspace_root == tmp_path.resolve()
    assert ls.settings.workspace_diagnostics_mode == "background"
    assert ls.document_states == {}
    assert ls.document_paths == {}
    assert ls.entry_diagnostics == {}
    assert ls.published_workspace_diagnostics == {}
    assert ls.entry_scan_generation == {}
    assert calls == ["configured", "scan"]


def test_on_did_change_configuration_reconfigures_workspace_and_schedules_scan(monkeypatch, tmp_path):
    stale_path = (tmp_path / "Programs" / "Main.s").resolve()
    publish_calls: list[set[Path]] = []
    calls: list[str] = []

    ls = SimpleNamespace(
        settings=LspSettings(entry_file="Programs/Old.s", workspace_diagnostics_mode="background"),
        workspace_root=tmp_path,
        entry_diagnostics={"entry": {stale_path: ()}},
        published_workspace_diagnostics={stale_path: ()},
        entry_scan_generation={"entry": 1},
        workspace_scan_condition=threading.Condition(),
        workspace_scan_pending={stale_path},
    )

    monkeypatch.setattr(
        "sattlint_lsp.server._publish_workspace_diagnostics_for_paths",
        lambda current_ls, paths: publish_calls.append(set(paths)),
    )
    monkeypatch.setattr(
        "sattlint_lsp.server._ensure_snapshot_store_configured", lambda current_ls: calls.append("configured") or True
    )
    monkeypatch.setattr(
        "sattlint_lsp.server._schedule_workspace_scan", lambda current_ls, entry_files=None: calls.append("scan")
    )

    params = SimpleNamespace(
        settings={
            "entryFile": "Programs/New.s",
            "mode": "official",
            "workspaceDiagnosticsMode": "background",
        }
    )

    on_did_change_configuration(cast(Any, ls), cast(Any, params))

    assert ls.settings.entry_file == "Programs/New.s"
    assert ls.settings.mode == "official"
    assert ls.entry_diagnostics == {}
    assert ls.entry_scan_generation == {}
    assert ls.workspace_scan_pending == set()
    assert publish_calls == [{stale_path}]
    assert calls == ["configured", "scan"]


def test_on_did_change_configuration_reconfigures_when_cache_cap_changes(monkeypatch, tmp_path):
    calls: list[str] = []

    ls = SimpleNamespace(
        settings=LspSettings(max_cached_entry_snapshots=2),
        workspace_root=tmp_path,
        entry_diagnostics={},
        published_workspace_diagnostics={},
        entry_scan_generation={},
        workspace_scan_condition=threading.Condition(),
        workspace_scan_pending=set(),
    )

    monkeypatch.setattr(
        "sattlint_lsp.server._publish_workspace_diagnostics_for_paths",
        lambda current_ls, paths: None,
    )
    monkeypatch.setattr(
        "sattlint_lsp.server._ensure_snapshot_store_configured", lambda current_ls: calls.append("configured") or True
    )
    monkeypatch.setattr(
        "sattlint_lsp.server._schedule_workspace_scan", lambda current_ls, entry_files=None: calls.append("scan")
    )

    params = SimpleNamespace(settings={"maxCachedEntrySnapshots": 1})

    on_did_change_configuration(cast(Any, ls), cast(Any, params))

    assert ls.settings.max_cached_entry_snapshots == 1
    assert calls == ["configured", "scan"]


def test_on_did_open_and_change_ignore_non_diagnostic_documents(monkeypatch, tmp_path):
    path = (tmp_path / "notes.txt").resolve()
    uri = path.as_uri()
    published = []

    ls = SimpleNamespace(
        workspace=SimpleNamespace(
            get_text_document=lambda requested_uri: SimpleNamespace(uri=requested_uri, source="text", version=2)
        ),
        text_document_publish_diagnostics=lambda params: published.append(params),
        document_states={uri: DocumentState(uri=uri, path=path, version=1, text="old")},
        document_paths={path: uri},
    )

    monkeypatch.setattr("sattlint_lsp.server._document_path", lambda document: path)

    open_params = SimpleNamespace(text_document=SimpleNamespace(uri=uri, version=2, text="text"))
    on_did_open(cast(Any, ls), cast(Any, open_params))

    assert uri not in ls.document_states
    assert path not in ls.document_paths
    assert published[-1].uri == uri
    assert published[-1].diagnostics == []

    ls.document_states[uri] = DocumentState(uri=uri, path=path, version=2, text="old")
    ls.document_paths[path] = uri
    change_params = SimpleNamespace(
        text_document=SimpleNamespace(uri=uri, version=3),
        content_changes=[SimpleNamespace(text="new")],
    )
    on_did_change(cast(Any, ls), cast(Any, change_params))

    assert uri not in ls.document_states
    assert path not in ls.document_paths
    assert published[-1].uri == uri
    assert published[-1].diagnostics == []


def test_on_did_save_ignores_non_diagnostic_documents(monkeypatch, tmp_path):
    path = (tmp_path / "notes.txt").resolve()
    uri = path.as_uri()
    published = []

    ls = SimpleNamespace(
        workspace=SimpleNamespace(
            get_text_document=lambda requested_uri: SimpleNamespace(uri=requested_uri, source="saved", version=4)
        ),
        text_document_publish_diagnostics=lambda params: published.append(params),
        document_states={uri: DocumentState(uri=uri, path=path, version=3, text="old")},
        document_paths={path: uri},
    )

    monkeypatch.setattr("sattlint_lsp.server._document_path", lambda document: path)

    save_params = SimpleNamespace(text_document=SimpleNamespace(uri=uri))
    on_did_save(cast(Any, ls), cast(Any, save_params))

    assert uri not in ls.document_states
    assert path not in ls.document_paths
    assert published[-1].uri == uri
    assert published[-1].diagnostics == []


@pytest.mark.parametrize("suffix", [".l", ".z"])
def test_on_did_save_rescans_workspace_dependency_lists(monkeypatch, tmp_path, suffix):
    path = (tmp_path / "Libs" / f"Support{suffix}").resolve()
    uri = path.as_uri()
    stale_path = (tmp_path / "Programs" / "Main.s").resolve()
    published = []
    publish_calls: list[set[Path]] = []
    calls: list[str] = []

    ls = SimpleNamespace(
        workspace=SimpleNamespace(
            get_text_document=lambda requested_uri: SimpleNamespace(uri=requested_uri, source="Support\n", version=4)
        ),
        text_document_publish_diagnostics=lambda params: published.append(params),
        document_states={uri: DocumentState(uri=uri, path=path, version=3, text="old")},
        document_paths={path: uri},
        workspace_root=tmp_path,
        entry_diagnostics={"entry": {stale_path: ()}},
        published_workspace_diagnostics={stale_path: ()},
        entry_scan_generation={"entry": 1},
        workspace_scan_condition=threading.Condition(),
        workspace_scan_pending={stale_path},
        snapshot_store=SimpleNamespace(refresh_workspace=lambda: calls.append("refresh")),
    )

    monkeypatch.setattr("sattlint_lsp.server._document_path", lambda document: path)
    monkeypatch.setattr(
        "sattlint_lsp.server._publish_workspace_diagnostics_for_paths",
        lambda current_ls, paths: publish_calls.append(set(paths)),
    )
    monkeypatch.setattr(
        "sattlint_lsp.server._schedule_workspace_scan", lambda current_ls, entry_files=None: calls.append("scan")
    )
    monkeypatch.setattr(
        "sattlint_lsp.server._record_document_open",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("dependency lists should not open diagnostics state")
        ),
    )
    monkeypatch.setattr(
        "sattlint_lsp.server._invalidate_cached_entries_for_path",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("dependency lists should refresh workspace inputs")
        ),
    )

    save_params = SimpleNamespace(text_document=SimpleNamespace(uri=uri))
    on_did_save(cast(Any, ls), cast(Any, save_params))

    assert uri not in ls.document_states
    assert path not in ls.document_paths
    assert published[-1].uri == uri
    assert published[-1].diagnostics == []
    assert ls.entry_diagnostics == {}
    assert ls.entry_scan_generation == {}
    assert ls.workspace_scan_pending == set()
    assert publish_calls == [{stale_path}]
    assert calls == ["refresh", "scan"]
