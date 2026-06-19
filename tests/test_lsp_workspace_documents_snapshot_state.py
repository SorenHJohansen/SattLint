# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportPrivateUsage=false
"""Snapshot state and finalization focused LSP workspace tests."""

from __future__ import annotations

from concurrent.futures import Future, TimeoutError
from functools import partial
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from sattlint.core.semantic import WorkspaceSourceDiscovery
from sattlint_lsp import workspace_store as lsp_workspace_store
from sattlint_lsp.server import SnapshotBundle


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_workspace_snapshot_store_index_and_configuration_edges(tmp_path, monkeypatch):
    workspace_root = tmp_path.resolve()
    main_a = (tmp_path / "Programs" / "Main.s").resolve()
    aux = (tmp_path / "Programs" / "Aux.s").resolve()
    main_b = (tmp_path / "OtherPrograms" / "Main.s").resolve()
    dependency = (tmp_path / "Libs" / "Support.l").resolve()

    for path in (main_a, aux, main_b, dependency):
        _write_text(path, '"x"\n"y"\n"z"\n')

    by_name, by_key = lsp_workspace_store._build_source_path_index((main_b, main_a, aux))
    assert by_name["main.s"] == tuple(sorted((main_a, main_b), key=lambda path: path.as_posix().casefold()))
    assert by_key[("main.s", "programs")] == main_a
    assert by_key[("main.s", "otherprograms")] == main_b

    candidate_discovery = WorkspaceSourceDiscovery(
        workspace_root=workspace_root,
        source_dirs=(main_a.parent, main_b.parent),
        program_files=(main_a, aux),
        dependency_files=(dependency,),
        program_files_by_stem={"main": (main_a,), "aux": (aux,)},
        dependency_files_by_stem={"support": (dependency,)},
        referenced_program_names=frozenset({"main"}),
    )
    assert lsp_workspace_store._workspace_entry_files(candidate_discovery) == (aux,)

    all_referenced_discovery = WorkspaceSourceDiscovery(
        workspace_root=workspace_root,
        source_dirs=(main_a.parent, main_b.parent),
        program_files=(main_a, main_b),
        dependency_files=(dependency,),
        program_files_by_stem={"main": (main_a, main_b)},
        dependency_files_by_stem={"support": (dependency,)},
        referenced_program_names=frozenset({"main"}),
    )
    assert lsp_workspace_store._workspace_entry_files(all_referenced_discovery) == tuple(
        sorted((main_a, main_b), key=lambda path: path.as_posix().casefold())
    )

    store = lsp_workspace_store.WorkspaceSnapshotStore()
    store._entry_files = (main_a,)
    assert store.list_entry_files() == (main_a,)
    assert store.resolve_entry_file(main_a) == main_a

    result = store.refresh_workspace()
    assert result == lsp_workspace_store.WorkspaceRefreshResult((), (), (main_a,))

    assert store.ensure_configured(None, SimpleNamespace()) is False

    monkeypatch.setattr(lsp_workspace_store, "discover_workspace_sources", lambda _root: candidate_discovery)
    settings = SimpleNamespace(entry_file="")
    assert store.ensure_configured(workspace_root, settings) is True
    assert store.ensure_configured(workspace_root, settings) is True

    stale_state = store._state_for_entry_locked(aux)
    stale_state.stale = True
    refreshed = store.refresh_workspace()
    assert refreshed.affected_entries == (aux,)

    missing_program = (tmp_path / "Programs" / "Missing.s").resolve()
    _write_text(missing_program, '"x"\n"y"\n"z"\n')
    assert store.invalidate_path(missing_program) == ()
    assert store.get_affected_entry_keys(missing_program) == (missing_program.as_posix().casefold(),)

    store._drop_entry_state_locked("missing")


def test_workspace_snapshot_store_bundle_resolution_edges(tmp_path, monkeypatch):  # noqa: PLR0915
    entry = (tmp_path / "Programs" / "Main.s").resolve()
    dependency = (tmp_path / "Libs" / "Support.l").resolve()
    for path in (entry, dependency):
        _write_text(path, '"x"\n"y"\n"z"\n')

    bundle = SnapshotBundle(
        snapshot=cast(Any, object()),
        source_paths_by_name={},
        source_paths_by_key={},
        entry_file=entry,
        cache_key=entry.as_posix().casefold(),
        source_files=(entry,),
    )

    store = lsp_workspace_store.WorkspaceSnapshotStore()
    state = store._state_for_entry_locked(entry)
    state.bundle = bundle
    state.stale = False
    assert store.get_bundle_for_entry(entry) is bundle

    monkeypatch.setattr(store, "resolve_entry_file", lambda document_path: None)
    assert store.get_bundle_for_document(dependency) is None

    forwarded = []
    monkeypatch.setattr(store, "resolve_entry_file", lambda document_path: entry)
    monkeypatch.setattr(
        store,
        "get_bundle_for_entry",
        lambda entry_file, **kwargs: forwarded.append((entry_file, kwargs)) or bundle,
    )
    assert store.get_bundle_for_document(dependency, wait_budget=1.5, allow_stale=False, raise_on_error=True) is bundle
    assert forwarded == [
        (
            entry,
            {"wait_budget": 1.5, "allow_stale": False, "raise_on_error": True},
        )
    ]

    submit_store = lsp_workspace_store.WorkspaceSnapshotStore()

    class ReadyFuture:
        def result(self, timeout=None):
            return bundle

    ready_future = ReadyFuture()

    def _submit_ready(current_state):
        current_state.bundle = bundle
        current_state.future = ready_future
        return ready_future

    monkeypatch.setattr(submit_store, "_submit_refresh_locked", _submit_ready)
    assert submit_store.get_bundle_for_entry(entry) is bundle

    timeout_store = lsp_workspace_store.WorkspaceSnapshotStore()
    timeout_state = timeout_store._state_for_entry_locked(entry)
    finalized: list[tuple[str, object]] = []

    class TimeoutFuture:
        def result(self, timeout=None):
            raise TimeoutError()

    timeout_future = TimeoutFuture()

    monkeypatch.setattr(
        timeout_store,
        "_submit_refresh_locked",
        lambda current_state: setattr(current_state, "future", timeout_future) or timeout_future,
    )
    monkeypatch.setattr(
        timeout_store,
        "_finalize_future",
        lambda entry_key, future, **kwargs: finalized.append((entry_key, future)),
    )
    assert timeout_store.get_bundle_for_entry(entry, wait_budget=1.0) is None
    assert finalized == [(entry.as_posix().casefold(), timeout_future)]
    assert timeout_state.last_access > 0.0

    error_store = lsp_workspace_store.WorkspaceSnapshotStore()
    error_state = error_store._state_for_entry_locked(entry)

    class ErrorFuture:
        def result(self, timeout=None):
            raise RuntimeError("boom")

    error_future = ErrorFuture()
    monkeypatch.setattr(
        error_store,
        "_submit_refresh_locked",
        lambda current_state: setattr(current_state, "future", error_future) or error_future,
    )
    monkeypatch.setattr(error_store, "_finalize_future", lambda entry_key, future, **kwargs: None)
    with pytest.raises(RuntimeError, match="boom"):
        error_store.get_bundle_for_entry(entry, wait_budget=1.0, raise_on_error=True)
    assert error_state.last_access > 0.0

    missing_store = lsp_workspace_store.WorkspaceSnapshotStore()
    missing_store._state_for_entry_locked(entry)
    monkeypatch.setattr(
        missing_store,
        "_submit_refresh_locked",
        lambda current_state: setattr(current_state, "future", timeout_future) or timeout_future,
    )
    monkeypatch.setattr(
        missing_store,
        "_finalize_future",
        lambda entry_key, future, **kwargs: missing_store._states.pop(entry_key, None),
    )
    assert missing_store.get_bundle_for_entry(entry, wait_budget=1.0) is None

    final_bundle_store = lsp_workspace_store.WorkspaceSnapshotStore()
    final_bundle_state = final_bundle_store._state_for_entry_locked(entry)
    monkeypatch.setattr(
        final_bundle_store,
        "_submit_refresh_locked",
        lambda current_state: setattr(current_state, "future", timeout_future) or timeout_future,
    )
    monkeypatch.setattr(
        final_bundle_store,
        "_finalize_future",
        lambda entry_key, future, **kwargs: setattr(final_bundle_store._states[entry_key], "bundle", bundle),
    )
    assert final_bundle_store.get_bundle_for_entry(entry, wait_budget=1.0) is bundle
    assert final_bundle_state.bundle is bundle

    final_error_store = lsp_workspace_store.WorkspaceSnapshotStore()
    final_error_state = final_error_store._state_for_entry_locked(entry)
    monkeypatch.setattr(
        final_error_store,
        "_submit_refresh_locked",
        lambda current_state: setattr(current_state, "future", cast(Any, timeout_future)) or timeout_future,
    )
    monkeypatch.setattr(
        final_error_store,
        "_finalize_future",
        lambda entry_key, future, **kwargs: setattr(
            final_error_store._states[entry_key], "last_error", ValueError("final")
        ),
    )
    with pytest.raises(ValueError, match="final"):
        final_error_store.get_bundle_for_entry(entry, wait_budget=1.0, raise_on_error=True)
    assert final_error_state.last_error is not None

    captured_error_store = lsp_workspace_store.WorkspaceSnapshotStore()
    captured_state = captured_error_store._state_for_entry_locked(entry)
    captured_state.last_error = ValueError("captured")
    captured_state.future = cast(Any, timeout_future)
    monkeypatch.setattr(
        captured_error_store,
        "_finalize_future",
        lambda entry_key, future, **kwargs: setattr(captured_error_store._states[entry_key], "last_error", None),
    )
    with pytest.raises(ValueError, match="captured"):
        captured_error_store.get_bundle_for_entry(entry, wait_budget=1.0, raise_on_error=True)


def _assert_snapshot_finalize_error_paths(entry: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    class TimeoutFuture:
        def result(self, timeout=None):
            raise TimeoutError()

    timeout_future = TimeoutFuture()

    final_error_store = lsp_workspace_store.WorkspaceSnapshotStore()
    final_error_state = final_error_store._state_for_entry_locked(entry)
    monkeypatch.setattr(
        final_error_store,
        "_submit_refresh_locked",
        lambda current_state: setattr(current_state, "future", timeout_future) or timeout_future,
    )
    monkeypatch.setattr(
        final_error_store,
        "_finalize_future",
        lambda entry_key, future, **kwargs: setattr(
            final_error_store._states[entry_key], "last_error", ValueError("final")
        ),
    )
    with pytest.raises(ValueError, match="final"):
        final_error_store.get_bundle_for_entry(entry, wait_budget=1.0, raise_on_error=True)
    assert final_error_state.last_error is not None

    captured_error_store = lsp_workspace_store.WorkspaceSnapshotStore()
    captured_state = captured_error_store._state_for_entry_locked(entry)
    captured_state.last_error = ValueError("captured")
    captured_state.future = cast(Any, timeout_future)
    monkeypatch.setattr(
        captured_error_store,
        "_finalize_future",
        lambda entry_key, future, **kwargs: setattr(captured_error_store._states[entry_key], "last_error", None),
    )
    with pytest.raises(ValueError, match="captured"):
        captured_error_store.get_bundle_for_entry(entry, wait_budget=1.0, raise_on_error=True)


def test_workspace_snapshot_store_cache_submit_build_and_finalize_edges(tmp_path, monkeypatch):  # noqa: PLR0915
    workspace_root = tmp_path.resolve()
    entry = (tmp_path / "Programs" / "Main.s").resolve()
    old_source = (tmp_path / "Programs" / "Old.s").resolve()
    dependency = (tmp_path / "Libs" / "Support.l").resolve()
    for path in (entry, old_source, dependency):
        _write_text(path, '"x"\n"y"\n"z"\n')

    discovery = WorkspaceSourceDiscovery(
        workspace_root=workspace_root,
        source_dirs=(entry.parent, dependency.parent),
        program_files=(entry,),
        dependency_files=(dependency,),
        program_files_by_stem={"main": (entry,)},
        dependency_files_by_stem={"support": (dependency,)},
    )

    bundle = SnapshotBundle(
        snapshot=cast(Any, object()),
        source_paths_by_name={},
        source_paths_by_key={},
        entry_file=entry,
        cache_key=entry.as_posix().casefold(),
        source_files=(entry,),
    )
    old_bundle = SnapshotBundle(
        snapshot=cast(Any, object()),
        source_paths_by_name={},
        source_paths_by_key={},
        entry_file=entry,
        cache_key=entry.as_posix().casefold(),
        source_files=(old_source,),
    )

    store = lsp_workspace_store.WorkspaceSnapshotStore()
    state = store._state_for_entry_locked(entry)
    assert store._bundle_from_state(state, allow_stale=True) is None

    store._settings = SimpleNamespace(max_cached_entry_snapshots="bad")
    assert store._max_cached_entry_snapshots_locked() == 2

    store._remove_bundle_sources_locked(state.cache_key, bundle)

    store._evict_bundle_locked(state)
    state.bundle = bundle
    state.stale = True
    store._source_file_to_entry_keys = {entry: {state.cache_key}}
    store._evict_bundle_locked(state)
    assert state.bundle is None
    assert state.stale is False
    assert entry not in store._source_file_to_entry_keys

    state.bundle = bundle
    state.last_access = 1.0
    store._states = {state.cache_key: state}
    store._settings = SimpleNamespace(max_cached_entry_snapshots=5)
    store._enforce_bundle_cap_locked()
    assert state.bundle is bundle

    uninitialized_store = lsp_workspace_store.WorkspaceSnapshotStore()
    with pytest.raises(RuntimeError, match="not initialized"):
        uninitialized_store._submit_refresh_locked(uninitialized_store._state_for_entry_locked(entry))

    submit_store = lsp_workspace_store.WorkspaceSnapshotStore()
    submit_store._workspace_root = workspace_root
    submit_store._settings = SimpleNamespace(mode="official", scan_root_only=True, enable_variable_diagnostics=False)
    submit_store._discovery = discovery
    submit_store._config_version = 3
    submit_state = submit_store._state_for_entry_locked(entry)
    submit_state.generation = 4
    submit_calls: list[tuple[str, int | None, int | None]] = []

    class ImmediateExecutor:
        def submit(self, fn, *args):
            future = Future()
            future.set_result(bundle)
            return future

    monkeypatch.setattr(submit_store, "_executor", ImmediateExecutor())
    monkeypatch.setattr(
        submit_store,
        "_finalize_future",
        lambda entry_key, future, **kwargs: submit_calls.append(
            (entry_key, kwargs.get("expected_config_version"), kwargs.get("expected_generation"))
        ),
    )
    returned_future = submit_store._submit_refresh_locked(submit_state)
    assert submit_state.future is returned_future
    assert submit_calls == [(submit_state.cache_key, 3, 4)]

    build_store = lsp_workspace_store.WorkspaceSnapshotStore()
    snapshot = SimpleNamespace(project_graph=SimpleNamespace(source_files=(dependency, entry)))
    load_calls: list[tuple[Path, Path, str, bool, bool, object]] = []
    monkeypatch.setattr(
        lsp_workspace_store,
        "load_workspace_snapshot",
        lambda entry_file, *, workspace_root, mode, scan_root_only, collect_variable_diagnostics, discovery, _analysis_provider: (
            load_calls.append(
                (entry_file, workspace_root, mode, scan_root_only, collect_variable_diagnostics, _analysis_provider)
            )
            or snapshot
        ),
    )
    built_bundle = build_store._build_bundle(
        entry,
        workspace_root,
        SimpleNamespace(mode="official", scan_root_only=True, enable_variable_diagnostics=False),
        discovery,
    )
    assert built_bundle.entry_file == entry
    assert built_bundle.source_files == tuple(sorted((dependency, entry), key=lambda path: path.as_posix().casefold()))
    assert built_bundle.source_paths_by_key[("main.s", "programs")] == entry
    assert len(load_calls) == 1
    assert load_calls[0][:5] == (entry, workspace_root, "official", True, False)
    analysis_provider = load_calls[0][5]
    assert isinstance(analysis_provider, partial)
    assert analysis_provider.func is lsp_workspace_store.build_variable_semantic_artifacts
    assert analysis_provider.keywords == {
        "config": {
            "enable_variable_diagnostics": False,
            "entry_file": str(entry),
            "mode": "official",
            "scan_root_only": True,
            "workspace_root": str(workspace_root),
        },
        "target_is_library": False,
    }

    config_store = lsp_workspace_store.WorkspaceSnapshotStore()
    config_state = config_store._state_for_entry_locked(entry)
    config_future = Future()
    config_future.set_result(bundle)
    config_state.future = config_future
    config_store._config_version = 2
    config_store._finalize_future(config_state.cache_key, config_future, expected_config_version=1)
    assert config_state.future is config_future

    missing_state_store = lsp_workspace_store.WorkspaceSnapshotStore()
    missing_future = Future()
    missing_future.set_result(bundle)
    missing_state_store._finalize_future(entry.as_posix().casefold(), missing_future)

    _assert_snapshot_finalize_error_paths(entry, monkeypatch)
    none_store = lsp_workspace_store.WorkspaceSnapshotStore()
    none_state = none_store._state_for_entry_locked(entry)
    none_future = Future()
    none_future.set_result(cast(Any, None))
    none_state.future = none_future
    none_store._finalize_future(none_state.cache_key, none_future)
    assert isinstance(none_state.last_error, RuntimeError)

    previous_store = lsp_workspace_store.WorkspaceSnapshotStore()
    previous_state = previous_store._state_for_entry_locked(entry)
    previous_state.bundle = old_bundle
    previous_future = Future()
    previous_future.set_result(bundle)
    previous_state.future = previous_future
    previous_store._source_file_to_entry_keys = {old_source: {previous_state.cache_key}}
    previous_store._finalize_future(previous_state.cache_key, previous_future)
    assert previous_state.bundle is bundle
    assert old_source not in previous_store._source_file_to_entry_keys
