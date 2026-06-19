# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportPrivateUsage=false
"""Server and document lifecycle focused LSP workspace tests."""

from __future__ import annotations

import threading
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from lsprotocol.types import Position, Range

from sattlint_lsp import workspace_store as lsp_workspace_store
from sattlint_lsp.document_state import DocumentState
from sattlint_lsp.server import (
    LspSettings,
    SattLineLanguageServer,
    _clear_workspace_entries,
    _invalidate_cached_entries_for_path,
    on_did_change,
    on_did_change_configuration,
    on_did_close,
    on_did_open,
    on_did_save,
    on_initialize,
)


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


def test_on_did_close_restores_active_diagnostics_among_same_name_dependencies(tmp_path):
    active_path = (tmp_path / "Program" / "Main.s").resolve()
    support_path = (tmp_path / "Libs" / "Support" / "Main.s").resolve()
    backup_path = (tmp_path / "Libs" / "Backup" / "Main.s").resolve()
    uri = active_path.as_uri()
    published = []
    active_diagnostic = cast(
        Any,
        SimpleNamespace(
            range=Range(start=Position(line=1, character=0), end=Position(line=1, character=3)),
            message="Active document warning",
            severity=1,
            source="sattlint",
        ),
    )
    support_diagnostic = cast(
        Any,
        SimpleNamespace(
            range=Range(start=Position(line=2, character=0), end=Position(line=2, character=3)),
            message="Support library warning",
            severity=1,
            source="sattlint",
        ),
    )

    ls = SattLineLanguageServer()
    ls.text_document_publish_diagnostics = lambda params: published.append(params)
    ls.document_states[uri] = DocumentState(
        uri=uri,
        path=active_path,
        version=2,
        text="Renamed = Renamed;\n",
        is_dirty=True,
    )
    ls.entry_diagnostics = {
        "entry": {
            active_path: (active_diagnostic,),
            support_path: (support_diagnostic,),
            backup_path: (support_diagnostic,),
        }
    }

    on_did_close(ls, cast(Any, SimpleNamespace(text_document=SimpleNamespace(uri=uri))))

    assert published[-1].uri.casefold() == uri.casefold()
    assert [item.message for item in published[-1].diagnostics] == ["Active document warning"]
    assert ls.published_workspace_diagnostics[active_path][0].message == "Active document warning"
    assert support_path not in ls.published_workspace_diagnostics


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
    bundle_a = lsp_workspace_store.SnapshotBundle(
        snapshot=cast(Any, None),
        source_paths_by_name={},
        source_paths_by_key={},
        entry_file=entry_a,
        cache_key=key_a,
        source_files=(entry_a, shared),
    )
    bundle_b = lsp_workspace_store.SnapshotBundle(
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
    new_path = (tmp_path / "Programs" / "Other.s").resolve()
    unaffected_path = (tmp_path / "Programs" / "Keep.s").resolve()
    published = []
    publish_calls: list[set[Path]] = []
    invalidate_calls: list[Path] = []
    scan_calls: list[tuple[Path, ...] | None] = []

    ls = SimpleNamespace(
        workspace=SimpleNamespace(
            get_text_document=lambda requested_uri: SimpleNamespace(uri=requested_uri, source="Support\n", version=4)
        ),
        text_document_publish_diagnostics=lambda params: published.append(params),
        document_states={uri: DocumentState(uri=uri, path=path, version=3, text="old")},
        document_paths={path: uri},
        workspace_root=tmp_path,
        entry_diagnostics={"entry": {stale_path: ()}, "keep": {unaffected_path: ()}},
        published_workspace_diagnostics={stale_path: (), unaffected_path: ()},
        entry_scan_generation={"entry": 1, "keep": 2},
        workspace_scan_condition=threading.Condition(),
        workspace_scan_pending={stale_path},
        snapshot_store=SimpleNamespace(
            refresh_workspace=lambda: lsp_workspace_store.WorkspaceRefreshResult(
                entry_files=(stale_path, unaffected_path, new_path),
                affected_entries=(new_path,),
                removed_entries=(),
            )
        ),
    )

    monkeypatch.setattr("sattlint_lsp.server._document_path", lambda document: path)
    monkeypatch.setattr(
        "sattlint_lsp.server._publish_workspace_diagnostics_for_paths",
        lambda current_ls, paths: publish_calls.append(set(paths)),
    )
    monkeypatch.setattr(
        "sattlint_lsp.server._schedule_workspace_scan",
        lambda current_ls, entry_files=None: scan_calls.append(entry_files),
    )
    monkeypatch.setattr(
        "sattlint_lsp.server._record_document_open",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("dependency lists should not open diagnostics state")
        ),
    )
    monkeypatch.setattr(
        "sattlint_lsp.server._clear_workspace_diagnostics",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("dependency list saves should not clear unrelated workspace diagnostics")
        ),
    )
    monkeypatch.setattr(
        "sattlint_lsp.server._invalidate_cached_entries_for_path",
        lambda _ls, dependency_path: invalidate_calls.append(dependency_path) or (stale_path,),
    )

    save_params = SimpleNamespace(text_document=SimpleNamespace(uri=uri))
    on_did_save(cast(Any, ls), cast(Any, save_params))

    assert uri not in ls.document_states
    assert path not in ls.document_paths
    assert published[-1].uri == uri
    assert published[-1].diagnostics == []
    assert invalidate_calls == [path]
    assert ls.entry_diagnostics == {"entry": {stale_path: ()}, "keep": {unaffected_path: ()}}
    assert ls.entry_scan_generation == {"entry": 1, "keep": 2}
    assert ls.workspace_scan_pending == {stale_path}
    assert publish_calls == []
    assert scan_calls == [tuple(sorted((new_path, stale_path), key=lambda item: item.as_posix().casefold()))]


def test_server_workspace_entry_and_initialization_edge_paths(monkeypatch, tmp_path):
    stale_path = (tmp_path / "Programs" / "Main.s").resolve()
    keep_path = (tmp_path / "Programs" / "Keep.s").resolve()
    publish_calls: list[set[Path]] = []

    ls = SimpleNamespace(
        entry_diagnostics={
            stale_path.as_posix().casefold(): {stale_path: ()},
            keep_path.as_posix().casefold(): {keep_path: ()},
        },
        entry_scan_generation={
            stale_path.as_posix().casefold(): 1,
            keep_path.as_posix().casefold(): 2,
        },
        workspace_scan_condition=threading.Condition(),
        workspace_scan_pending={stale_path, keep_path},
    )

    monkeypatch.setattr(
        "sattlint_lsp.server._publish_workspace_diagnostics_for_paths",
        lambda current_ls, paths: publish_calls.append(set(paths)),
    )

    _clear_workspace_entries(cast(Any, ls), ())
    _clear_workspace_entries(cast(Any, ls), (stale_path,))

    assert set(ls.entry_diagnostics) == {keep_path.as_posix().casefold()}
    assert ls.entry_scan_generation == {keep_path.as_posix().casefold(): 2}
    assert ls.workspace_scan_pending == {keep_path}
    assert publish_calls == [{stale_path}]

    calls: list[str] = []
    server_ls = SattLineLanguageServer()
    server_ls.document_states["file:///stale"] = cast(Any, object())
    server_ls.document_paths[stale_path] = "file:///stale"
    server_ls.entry_diagnostics = {"stale": {stale_path: ()}}
    server_ls.published_workspace_diagnostics = {stale_path: ()}
    server_ls.entry_scan_generation = {"stale": 1}
    with server_ls.workspace_scan_condition:
        server_ls.workspace_scan_pending.add(stale_path)
        server_ls.workspace_scan_thread = cast(Any, object())
        server_ls.workspace_scan_generation = 9

    monkeypatch.setattr(
        "sattlint_lsp.server._ensure_snapshot_store_configured",
        lambda current_ls: calls.append("configured") or True,
    )
    monkeypatch.setattr(
        "sattlint_lsp.server._schedule_workspace_scan",
        lambda current_ls, entry_files=None: calls.append("scan"),
    )

    on_initialize(
        server_ls,
        cast(
            Any,
            SimpleNamespace(initialization_options={}, root_uri=object(), root_path=str(tmp_path)),
        ),
    )
    assert server_ls.workspace_root == tmp_path.resolve()
    assert server_ls.document_states == {}
    assert server_ls.document_paths == {}
    assert server_ls.entry_diagnostics == {}
    assert server_ls.published_workspace_diagnostics == {}
    assert server_ls.entry_scan_generation == {}

    on_initialize(
        server_ls,
        cast(
            Any,
            SimpleNamespace(initialization_options={}, root_uri=None, root_path=object()),
        ),
    )

    assert server_ls.workspace_root is None
    assert calls == ["configured", "scan", "configured", "scan"]
