"""Snapshot cache focused LSP workspace tests."""

from __future__ import annotations

from concurrent.futures import Future
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

from sattlint.core.semantic import WorkspaceSourceDiscovery
from sattlint_lsp import workspace_store as lsp_workspace_store
from sattlint_lsp.server import SnapshotBundle


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_workspace_snapshot_store_cache_prefetch_and_invalidation_edges(tmp_path, monkeypatch):
    store = lsp_workspace_store.WorkspaceSnapshotStore()
    workspace_root = tmp_path.resolve()
    entry = (tmp_path / "Programs" / "Main.s").resolve()
    sibling = (tmp_path / "Programs" / "Other.s").resolve()
    dependency = (tmp_path / "Libs" / "Support.l").resolve()

    for path in (entry, sibling, dependency):
        _write_text(path, '"x"\n"y"\n"z"\n')

    store._workspace_root = workspace_root
    store._settings = SimpleNamespace(entry_file="", max_cached_entry_snapshots=1)
    store._discovery = WorkspaceSourceDiscovery(
        workspace_root=workspace_root,
        source_dirs=(entry.parent,),
        program_files=(entry, sibling),
        dependency_files=(dependency,),
        program_files_by_stem={
            "main": (entry,),
            "other": (sibling,),
        },
        dependency_files_by_stem={"support": (dependency,)},
    )
    store._entry_files = (entry, sibling)

    state_entry = store._state_for_entry_locked(entry)
    state_sibling = store._state_for_entry_locked(sibling)
    bundle = SnapshotBundle(
        snapshot=cast(Any, object()),
        source_paths_by_name={},
        source_paths_by_key={},
        entry_file=entry,
        cache_key=state_entry.cache_key,
        source_files=(entry,),
    )
    state_entry.bundle = bundle
    state_entry.stale = False
    state_entry.last_access = 1.0
    state_entry.last_error = RuntimeError("old error")
    state_sibling.stale = True

    sibling_bundle = SnapshotBundle(
        snapshot=cast(Any, object()),
        source_paths_by_name={},
        source_paths_by_key={},
        entry_file=sibling,
        cache_key=state_sibling.cache_key,
        source_files=(sibling,),
    )

    refresh_future = Future()
    refresh_future.set_result(sibling_bundle)
    state_sibling.future = refresh_future
    store._source_file_to_entry_keys = {
        entry: {state_entry.cache_key},
    }
    store._finalize_future(state_sibling.cache_key, refresh_future)

    assert state_entry.bundle is None
    assert state_sibling.bundle is sibling_bundle
    assert entry not in store._source_file_to_entry_keys
    assert store._source_file_to_entry_keys[sibling] == {state_sibling.cache_key}

    submitted: list[Path] = []

    def _submit_refresh(state):
        submitted.append(state.entry_file)
        future = Future()
        future.set_result(bundle)
        state.future = future
        return future

    monkeypatch.setattr(store, "_submit_refresh_locked", _submit_refresh)

    assert store.prefetch_entries() == (entry,)
    assert submitted == [entry]
    assert state_entry.future is not None
    store._finalize_future(state_entry.cache_key, state_entry.future)
    assert store.get_cached_bundle(entry) is bundle
    state_entry.stale = True
    assert store.get_cached_bundle(entry, allow_stale=False) is None
    assert store.get_cached_bundle(entry, allow_stale=True) is bundle
    assert store.last_error_for_entry(entry) is state_entry.last_error
    assert store.last_error_for_entry(tmp_path / "missing.s") is None

    store._source_file_to_entry_keys[dependency] = {state_entry.cache_key, "missing"}
    affected = store.invalidate_path(dependency)
    assert affected == (entry,)
    assert state_entry.stale is True
    assert state_entry.generation == 1
    assert state_entry.last_error is None

    assert store.get_affected_entry_keys(entry) == (state_entry.cache_key,)


def test_workspace_snapshot_store_refresh_workspace_preserves_unchanged_bundles(tmp_path, monkeypatch):
    store = lsp_workspace_store.WorkspaceSnapshotStore()
    workspace_root = tmp_path.resolve()
    entry = (tmp_path / "Programs" / "Main.s").resolve()
    removed = (tmp_path / "Programs" / "Old.s").resolve()
    added = (tmp_path / "Programs" / "New.s").resolve()
    dependency = (tmp_path / "Libs" / "Support.l").resolve()

    for path in (entry, removed, added, dependency):
        _write_text(path, '"x"\n"y"\n"z"\n')

    store._workspace_root = workspace_root
    store._settings = SimpleNamespace(entry_file="", max_cached_entry_snapshots=2)
    store._discovery = WorkspaceSourceDiscovery(
        workspace_root=workspace_root,
        source_dirs=(entry.parent, dependency.parent),
        program_files=(entry, removed),
        dependency_files=(dependency,),
        program_files_by_stem={"main": (entry,), "old": (removed,)},
        dependency_files_by_stem={"support": (dependency,)},
    )
    store._entry_files = (entry, removed)

    entry_state = store._state_for_entry_locked(entry)
    removed_state = store._state_for_entry_locked(removed)
    preserved_bundle = SnapshotBundle(
        snapshot=cast(Any, object()),
        source_paths_by_name={},
        source_paths_by_key={},
        entry_file=entry,
        cache_key=entry_state.cache_key,
        source_files=(entry, dependency),
    )
    removed_bundle = SnapshotBundle(
        snapshot=cast(Any, object()),
        source_paths_by_name={},
        source_paths_by_key={},
        entry_file=removed,
        cache_key=removed_state.cache_key,
        source_files=(removed, dependency),
    )
    entry_state.bundle = preserved_bundle
    removed_state.bundle = removed_bundle
    store._source_file_to_entry_keys = {
        entry: {entry_state.cache_key},
        removed: {removed_state.cache_key},
        dependency: {entry_state.cache_key, removed_state.cache_key},
    }

    refreshed_discovery = WorkspaceSourceDiscovery(
        workspace_root=workspace_root,
        source_dirs=(entry.parent, dependency.parent),
        program_files=(entry, added),
        dependency_files=(dependency,),
        program_files_by_stem={"main": (entry,), "new": (added,)},
        dependency_files_by_stem={"support": (dependency,)},
    )
    monkeypatch.setattr(lsp_workspace_store, "discover_workspace_sources", lambda _root: refreshed_discovery)

    result = store.refresh_workspace()

    assert result.entry_files == (entry, added)
    assert result.affected_entries == (added,)
    assert result.removed_entries == (removed,)
    assert store.get_cached_bundle(entry) is preserved_bundle
    assert store.get_cached_bundle(removed) is None
    assert removed not in store._source_file_to_entry_keys
    assert store._source_file_to_entry_keys[dependency] == {entry_state.cache_key}
