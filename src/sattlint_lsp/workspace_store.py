"""Workspace snapshot caching and background refresh helpers for the LSP."""

from __future__ import annotations

import threading
from concurrent.futures import Future, ThreadPoolExecutor, TimeoutError
from dataclasses import dataclass, field
from pathlib import Path
from time import monotonic
from typing import Any

from lsprotocol.types import Diagnostic

from sattlint.editor_api import (
    SemanticSnapshot,
    WorkspaceSourceDiscovery,
    discover_workspace_sources,
    load_workspace_snapshot,
)

_PROGRAM_SUFFIXES = {".s", ".x"}


def _path_key(path: Path) -> str:
    return path.as_posix().casefold()


def _cache_key(entry_file: Path) -> str:
    return _path_key(entry_file.resolve())


def _source_file_key(path: Path) -> tuple[str, str]:
    return (path.name.casefold(), path.parent.name.casefold())


def _build_source_path_index(
    paths: tuple[Path, ...],
) -> tuple[dict[str, tuple[Path, ...]], dict[tuple[str, str], Path]]:
    by_name: dict[str, list[Path]] = {}
    by_key: dict[tuple[str, str], Path] = {}
    for path in sorted((item.resolve() for item in paths), key=_path_key):
        by_name.setdefault(path.name.casefold(), []).append(path)
        by_key[_source_file_key(path)] = path
    return ({name: tuple(items) for name, items in by_name.items()}, by_key)


def _read_dependency_names(dependency_path: Path) -> tuple[str, ...]:
    try:
        text = dependency_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = dependency_path.read_text(encoding="cp1252")
    except OSError:
        return ()
    return tuple(line.strip().casefold() for line in text.splitlines() if line.strip())


def _workspace_entry_files(discovery: WorkspaceSourceDiscovery) -> tuple[Path, ...]:
    referenced_names: set[str] = set()
    for dependency_path in discovery.dependency_files:
        referenced_names.update(_read_dependency_names(dependency_path))

    candidates = [path.resolve() for path in discovery.program_files if path.stem.casefold() not in referenced_names]
    if candidates:
        return tuple(sorted(set(candidates), key=_path_key))
    return tuple(sorted((path.resolve() for path in discovery.program_files), key=_path_key))


@dataclass(frozen=True, slots=True)
class SnapshotBundle:
    snapshot: SemanticSnapshot
    source_paths_by_name: dict[str, tuple[Path, ...]]
    source_paths_by_key: dict[tuple[str, str], Path]
    entry_file: Path
    cache_key: str
    source_files: tuple[Path, ...]
    semantic_diagnostics_by_path: dict[Path, tuple[Diagnostic, ...]] = field(
        default_factory=dict, repr=False, compare=False
    )
    semantic_diagnostics_lock: threading.RLock = field(default_factory=threading.RLock, repr=False, compare=False)


@dataclass(slots=True)
class _EntrySnapshotState:
    entry_file: Path
    cache_key: str
    bundle: SnapshotBundle | None = None
    future: Future[SnapshotBundle] | None = None
    stale: bool = False
    generation: int = 0
    last_error: Exception | None = None
    last_access: float = 0.0


class WorkspaceSnapshotStore:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="sattline-snapshot")
        self._workspace_root: Path | None = None
        self._settings: Any = None
        self._discovery: WorkspaceSourceDiscovery | None = None
        self._entry_files: tuple[Path, ...] = ()
        self._states: dict[str, _EntrySnapshotState] = {}
        self._source_file_to_entry_keys: dict[Path, set[str]] = {}
        self._config_version = 0

    def ensure_configured(self, workspace_root: Path | None, settings: Any) -> bool:
        normalized_root = workspace_root.resolve() if workspace_root is not None else None
        with self._lock:
            if normalized_root is None:
                self._workspace_root = None
                self._settings = None
                self._discovery = None
                self._entry_files = ()
                self._states.clear()
                self._source_file_to_entry_keys.clear()
                self._config_version += 1
                return False

            if self._workspace_root == normalized_root and self._settings == settings and self._discovery is not None:
                return True

            self._workspace_root = normalized_root
            self._settings = settings
            self._discovery = discover_workspace_sources(normalized_root)
            self._entry_files = _workspace_entry_files(self._discovery)
            self._states.clear()
            self._source_file_to_entry_keys.clear()
            self._config_version += 1
            return True

    def list_entry_files(self) -> tuple[Path, ...]:
        with self._lock:
            return self._entry_files

    def resolve_entry_file(self, document_path: Path) -> Path | None:
        resolved_document = document_path.resolve()
        with self._lock:
            discovery = self._discovery
            entry_files = self._entry_files
            settings = self._settings
            workspace_root = self._workspace_root

        if resolved_document.suffix.lower() in _PROGRAM_SUFFIXES:
            return resolved_document
        if workspace_root is None or discovery is None:
            return None

        configured_entry = str(getattr(settings, "entry_file", "") or "").strip()
        if configured_entry:
            configured_path = Path(configured_entry)
            candidate = configured_path if configured_path.is_absolute() else (workspace_root / configured_path)
            if candidate.exists() and candidate.suffix.lower() in _PROGRAM_SUFFIXES:
                return candidate.resolve()

        if len(entry_files) == 1:
            return entry_files[0]
        return None

    def prefetch_entries(self, entry_files: tuple[Path, ...] | None = None) -> tuple[Path, ...]:
        with self._lock:
            targets = entry_files or self._entry_files
            scheduled: list[Path] = []
            for entry_file in targets:
                state = self._state_for_entry_locked(entry_file.resolve())
                if state.future is None and (state.bundle is None or state.stale):
                    self._submit_refresh_locked(state)
                    scheduled.append(state.entry_file)
            return tuple(scheduled)

    def invalidate_path(self, document_path: Path) -> tuple[Path, ...]:
        resolved_path = document_path.resolve()
        with self._lock:
            entry_keys = set(self._source_file_to_entry_keys.get(resolved_path, set()))
            if resolved_path.suffix.lower() in _PROGRAM_SUFFIXES and not entry_keys:
                entry_keys.add(_cache_key(resolved_path))

            affected_entries: list[Path] = []
            for entry_key in sorted(entry_keys):
                state = self._states.get(entry_key)
                if state is None:
                    continue
                state.generation += 1
                state.stale = True
                state.last_error = None
                affected_entries.append(state.entry_file)
            return tuple(sorted(set(affected_entries), key=_path_key))

    def get_affected_entry_keys(self, document_path: Path) -> tuple[str, ...]:
        resolved_path = document_path.resolve()
        with self._lock:
            entry_keys = set(self._source_file_to_entry_keys.get(resolved_path, set()))
            if resolved_path.suffix.lower() in _PROGRAM_SUFFIXES and not entry_keys:
                entry_keys.add(_cache_key(resolved_path))
            return tuple(sorted(entry_keys))

    def get_bundle_for_document(
        self,
        document_path: Path,
        *,
        wait_budget: float | None = 0.0,
        allow_stale: bool = True,
        raise_on_error: bool = False,
    ) -> SnapshotBundle | None:
        entry_file = self.resolve_entry_file(document_path)
        if entry_file is None:
            return None
        return self.get_bundle_for_entry(
            entry_file,
            wait_budget=wait_budget,
            allow_stale=allow_stale,
            raise_on_error=raise_on_error,
        )

    def get_bundle_for_entry(
        self,
        entry_file: Path,
        *,
        wait_budget: float | None = 0.0,
        allow_stale: bool = True,
        raise_on_error: bool = False,
    ) -> SnapshotBundle | None:
        resolved_entry = entry_file.resolve()
        future: Future[SnapshotBundle] | None = None
        state_key = _cache_key(resolved_entry)
        with self._lock:
            state = self._state_for_entry_locked(resolved_entry)
            state.last_access = monotonic()
            bundle = self._bundle_from_state(state, allow_stale=allow_stale)
            if bundle is not None and not state.stale:
                return bundle
            if state.future is None and (state.bundle is None or state.stale):
                future = self._submit_refresh_locked(state)
            else:
                future = state.future
            bundle = self._bundle_from_state(state, allow_stale=allow_stale)
            if bundle is not None:
                return bundle
            last_error = state.last_error

        if future is not None and wait_budget != 0:
            timeout = None if wait_budget is None else max(wait_budget, 0.0)
            try:
                future.result(timeout=timeout)
            except TimeoutError:
                pass
            except Exception as exc:
                if raise_on_error:
                    raise exc
            finally:
                self._finalize_future(state_key, future)

        with self._lock:
            final_state = self._states.get(state_key)
            if final_state is None:
                return None
            bundle = self._bundle_from_state(final_state, allow_stale=allow_stale)
            if bundle is not None:
                return bundle
            if raise_on_error and final_state.last_error is not None:
                raise final_state.last_error
            if raise_on_error and last_error is not None:
                raise last_error
            return None

    def get_cached_bundle(self, entry_file: Path, *, allow_stale: bool = True) -> SnapshotBundle | None:
        with self._lock:
            state = self._states.get(_cache_key(entry_file.resolve()))
            if state is None:
                return None
            return self._bundle_from_state(state, allow_stale=allow_stale)

    def last_error_for_entry(self, entry_file: Path) -> Exception | None:
        with self._lock:
            state = self._states.get(_cache_key(entry_file.resolve()))
            if state is None:
                return None
            return state.last_error

    def _bundle_from_state(self, state: _EntrySnapshotState, *, allow_stale: bool) -> SnapshotBundle | None:
        if state.bundle is None:
            return None
        if state.stale and not allow_stale:
            return None
        return state.bundle

    def _state_for_entry_locked(self, entry_file: Path) -> _EntrySnapshotState:
        cache_key = _cache_key(entry_file)
        state = self._states.get(cache_key)
        if state is None:
            state = _EntrySnapshotState(entry_file=entry_file, cache_key=cache_key)
            self._states[cache_key] = state
        return state

    def _submit_refresh_locked(self, state: _EntrySnapshotState) -> Future[SnapshotBundle]:
        if self._workspace_root is None or self._settings is None or self._discovery is None:
            raise RuntimeError("workspace snapshot store is not initialized")
        config_version = self._config_version
        generation = state.generation
        workspace_root = self._workspace_root
        settings = self._settings
        discovery = self._discovery
        future = self._executor.submit(
            self._build_bundle,
            state.entry_file,
            workspace_root,
            settings,
            discovery,
        )
        state.future = future

        def _complete_snapshot(completed: Future[SnapshotBundle]) -> None:
            self._finalize_future(
                state.cache_key,
                completed,
                expected_config_version=config_version,
                expected_generation=generation,
            )

        future.add_done_callback(_complete_snapshot)
        return future

    def _build_bundle(
        self,
        entry_file: Path,
        workspace_root: Path,
        settings: Any,
        discovery: WorkspaceSourceDiscovery,
    ) -> SnapshotBundle:
        snapshot = load_workspace_snapshot(
            entry_file,
            workspace_root=workspace_root,
            mode=getattr(settings, "mode", "draft"),
            scan_root_only=bool(getattr(settings, "scan_root_only", False)),
            collect_variable_diagnostics=bool(getattr(settings, "enable_variable_diagnostics", True)),
            discovery=discovery,
        )
        source_files = tuple(
            sorted(
                (path.resolve() for path in snapshot.project_graph.source_files),
                key=_path_key,
            )
        )
        source_paths_by_name, source_paths_by_key = _build_source_path_index(source_files)
        return SnapshotBundle(
            snapshot=snapshot,
            source_paths_by_name=source_paths_by_name,
            source_paths_by_key=source_paths_by_key,
            entry_file=entry_file.resolve(),
            cache_key=_cache_key(entry_file),
            source_files=source_files,
        )

    def _finalize_future(
        self,
        entry_key: str,
        future: Future[SnapshotBundle],
        *,
        expected_config_version: int | None = None,
        expected_generation: int | None = None,
    ) -> None:
        try:
            bundle = future.result()
            error: Exception | None = None
        except Exception as exc:
            bundle = None
            error = exc

        with self._lock:
            if expected_config_version is not None and expected_config_version != self._config_version:
                return

            state = self._states.get(entry_key)
            if state is None:
                return
            if expected_generation is not None and expected_generation != state.generation:
                if state.future is future:
                    state.future = None
                return
            if state.future is not future:
                return

            state.future = None
            if error is not None:
                state.last_error = error
                return

            if bundle is None:
                state.last_error = RuntimeError("snapshot refresh completed without a bundle")
                return
            previous_bundle = state.bundle
            state.bundle = bundle
            state.stale = False
            state.last_error = None

            if previous_bundle is not None:
                for source_file in previous_bundle.source_files:
                    resolved_source = source_file.resolve()
                    keys = self._source_file_to_entry_keys.get(resolved_source)
                    if keys is None:
                        continue
                    keys.discard(entry_key)
                    if not keys:
                        self._source_file_to_entry_keys.pop(resolved_source, None)

            for source_file in bundle.source_files:
                self._source_file_to_entry_keys.setdefault(source_file.resolve(), set()).add(entry_key)
