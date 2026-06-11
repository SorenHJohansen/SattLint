"""Cache helpers for parsed ASTs and file manifests."""

from __future__ import annotations

import hashlib
import json
import os
import pickle  # nosec B403 - trusted local cache files only
import shutil
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypedDict, cast

from ._config_defaults import PROJECT_CACHE_CONFIG_KEYS

CACHE_VERSION = 14  # Bump when cached AST semantics or warning content changes.
ANALYSIS_REPORT_CACHE_VERSION = 3
LOOKUP_CACHE_VERSION = 1
DEFAULT_LOOKUP_CACHE_FLUSH_INTERVAL = 25


class _FileLookupEntry(TypedDict):
    base_dir: str
    ext: str


class _FileLookupCacheData(TypedDict):
    version: int
    entries: dict[str, _FileLookupEntry]


@dataclass(frozen=True)
class CachePruneResult:
    file_lookup_entries: int = 0
    file_ast_entries: int = 0
    ast_payload_entries: int = 0
    ast_manifest_entries: int = 0
    analysis_report_entries: int = 0

    @property
    def removed_entries(self) -> int:
        return (
            self.file_lookup_entries
            + self.file_ast_entries
            + self.ast_payload_entries
            + self.ast_manifest_entries
            + self.analysis_report_entries
        )

    def combine(self, other: CachePruneResult) -> CachePruneResult:
        return CachePruneResult(
            file_lookup_entries=self.file_lookup_entries + other.file_lookup_entries,
            file_ast_entries=self.file_ast_entries + other.file_ast_entries,
            ast_payload_entries=self.ast_payload_entries + other.ast_payload_entries,
            ast_manifest_entries=self.ast_manifest_entries + other.ast_manifest_entries,
            analysis_report_entries=self.analysis_report_entries + other.analysis_report_entries,
        )


def _as_mapping(value: object) -> Mapping[str, object] | None:
    if not isinstance(value, Mapping):
        return None
    return cast(Mapping[str, object], value)


def _safe_stat(path: Path) -> os.stat_result | None:
    try:
        return path.stat()
    except OSError:
        return None


def _matches_stat_snapshot(path: Path, *, mtime_ns: object, size: object) -> bool:
    if not isinstance(mtime_ns, int) or not isinstance(size, int):
        return False
    stat_result = _safe_stat(path)
    if stat_result is None:
        return False
    return stat_result.st_mtime_ns == mtime_ns and stat_result.st_size == size


def _as_file_lookup_entry(value: object) -> _FileLookupEntry | None:
    entry = _as_mapping(value)
    if entry is None:
        return None
    base_dir = entry.get("base_dir")
    ext = entry.get("ext")
    if not isinstance(base_dir, str) or not isinstance(ext, str):
        return None
    return {"base_dir": base_dir, "ext": ext}


def _load_file_lookup_entries(value: object) -> dict[str, _FileLookupEntry] | None:
    if not isinstance(value, dict):
        return None

    entries: dict[str, _FileLookupEntry] = {}
    for raw_key, raw_entry in cast(dict[object, object], value).items():
        if not isinstance(raw_key, str):
            return None
        entry = _as_file_lookup_entry(raw_entry)
        if entry is None:
            return None
        entries[raw_key] = entry
    return entries


def _snapshot_manifest(files: Iterable[Path]) -> dict[str, tuple[int, int]] | None:
    manifest: dict[str, tuple[int, int]] = {}
    for path in files:
        stat_result = _safe_stat(path)
        if stat_result is None:
            return None
        manifest[str(path)] = (stat_result.st_mtime_ns, stat_result.st_size)
    return manifest


def _load_manifest_payload(path: Path) -> dict[str, tuple[int, int]] | None:
    try:
        with path.open("r", encoding="utf-8") as handle:
            loaded = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None

    if not isinstance(loaded, dict):
        return None

    manifest: dict[str, tuple[int, int]] = {}
    for raw_path, raw_meta in cast(dict[object, object], loaded).items():
        if not isinstance(raw_path, str):
            return None
        if not isinstance(raw_meta, list | tuple):
            return None
        meta_values = cast(list[object] | tuple[object, ...], raw_meta)
        if len(meta_values) != 2:
            return None
        mtime, size = meta_values
        if not isinstance(mtime, int) or not isinstance(size, int):
            return None
        manifest[raw_path] = (mtime, size)

    return manifest


def _validate_manifest(files: object) -> bool:
    if not isinstance(files, dict):
        return False
    for path_str, manifest in cast(dict[object, object], files).items():
        if not isinstance(path_str, str):
            return False
        if not isinstance(manifest, tuple):
            return False
        manifest_tuple = cast(tuple[object, ...], manifest)
        if len(manifest_tuple) != 2:
            return False
        mtime, size = manifest_tuple
        if not _matches_stat_snapshot(Path(path_str), mtime_ns=mtime, size=size):
            return False

    return True


def _load_pickle_payload(path: Path) -> object | None:
    try:
        with path.open("rb") as handle:
            return pickle.load(handle)  # nosec B301 - loading SattLint-owned local cache files only
    except (OSError, pickle.UnpicklingError, TypeError, AttributeError, EOFError):
        return None


def _remove_file(path: Path) -> bool:
    try:
        path.unlink()
    except OSError:
        return False
    return True


def _legacy_cache_dir() -> Path:
    base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "sattlint" / "cache"


def _merge_cache_directories(source: Path, destination: Path) -> None:
    for child in source.iterdir():
        target = destination / child.name
        if child.is_dir():
            if target.exists():
                if target.is_dir():
                    _merge_cache_directories(child, target)
            else:
                shutil.move(str(child), str(target))
                continue
            try:
                child.rmdir()
            except OSError:
                continue
            continue

        if target.exists():
            continue
        shutil.move(str(child), str(target))


def _migrate_legacy_cache_dir(cache_dir: Path) -> None:
    legacy_cache_dir = _legacy_cache_dir()
    if legacy_cache_dir == cache_dir or not legacy_cache_dir.exists():
        return

    cache_dir.parent.mkdir(parents=True, exist_ok=True)
    if not cache_dir.exists():
        try:
            legacy_cache_dir.rename(cache_dir)
            return
        except OSError:
            pass

    cache_dir.mkdir(parents=True, exist_ok=True)
    _merge_cache_directories(legacy_cache_dir, cache_dir)
    try:
        legacy_cache_dir.rmdir()
    except OSError:
        return


def get_cache_dir() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        cache_dir = base / "sattlint" / "cache"
    else:
        base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
        cache_dir = base / "sattlint"
        _migrate_legacy_cache_dir(cache_dir)

    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def _normalize_cache_dir(cache_dir: Path) -> Path:
    expanded = cache_dir.expanduser()
    try:
        return expanded.resolve()
    except OSError:
        return expanded


def _normalize_lookup_base_dir(base_dir: Path) -> str:
    return str(_normalize_cache_dir(base_dir))


class FileLookupCache:
    def __init__(
        self,
        cache_dir: Path,
        *,
        flush_interval: int | None = DEFAULT_LOOKUP_CACHE_FLUSH_INTERVAL,
        write_through: bool = False,
    ):
        if flush_interval is not None and flush_interval <= 0:
            raise ValueError("flush_interval must be positive or None")
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.cache_dir / "file_lookup_cache.json"
        self._flush_interval = flush_interval
        self._write_through = write_through
        self._pending_mutations = 0
        self._data: _FileLookupCacheData = {"version": LOOKUP_CACHE_VERSION, "entries": {}}
        self._dirty = False
        self._startup_pruned_entries = self.prune_stale_entries()
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            with self.path.open("r", encoding="utf-8") as f:
                loaded = json.load(f)
            data = _as_mapping(loaded)
            if data is None or data.get("version") != LOOKUP_CACHE_VERSION:
                return
            entries = _load_file_lookup_entries(data.get("entries"))
            if entries is not None:
                self._data = {"version": LOOKUP_CACHE_VERSION, "entries": entries}
        except (OSError, json.JSONDecodeError):
            return

    def prune_stale_entries(self) -> int:
        if not self.path.exists():
            return 0
        try:
            with self.path.open("r", encoding="utf-8") as handle:
                loaded = json.load(handle)
        except (OSError, json.JSONDecodeError):
            return 1 if _remove_file(self.path) else 0

        data = _as_mapping(loaded)
        if data is None or data.get("version") != LOOKUP_CACHE_VERSION:
            return 1 if _remove_file(self.path) else 0
        return 0

    def drain_startup_pruned_entries(self) -> int:
        removed = self._startup_pruned_entries
        self._startup_pruned_entries = 0
        return removed

    def _save(self) -> None:
        payload = {
            "version": LOOKUP_CACHE_VERSION,
            "entries": self._data.get("entries", {}),
        }
        temp_path = self.path.with_name(f"{self.path.name}.tmp")
        with temp_path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=True, indent=2, sort_keys=True)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_path, self.path)

    def _record_mutation(self) -> None:
        self._dirty = True
        self._pending_mutations += 1
        should_flush = self._write_through or (
            self._flush_interval is not None and self._pending_mutations >= self._flush_interval
        )
        if should_flush:
            self.flush()

    def _key(self, kind: str, name: str, mode: str) -> str:
        return f"{kind}:{mode}:{name.casefold()}"

    def get(self, kind: str, name: str, mode: str) -> dict[str, str] | None:
        key = self._key(kind, name, mode)
        entries = cast(object, self._data.get("entries"))
        if not isinstance(entries, dict):
            return None
        entry = _as_file_lookup_entry(cast(dict[str, object], entries).get(key))
        if entry is None:
            return None
        return {"base_dir": entry["base_dir"], "ext": entry["ext"]}

    def set(self, kind: str, name: str, mode: str, base_dir: Path, ext: str) -> None:
        key = self._key(kind, name, mode)
        entries = cast(object, self._data.setdefault("entries", {}))
        if not isinstance(entries, dict):
            return
        entry_map = cast(dict[str, _FileLookupEntry], entries)
        payload: _FileLookupEntry = {
            "base_dir": _normalize_lookup_base_dir(base_dir),
            "ext": ext,
        }
        if entry_map.get(key) == payload:
            return
        entry_map[key] = payload
        self._record_mutation()

    def forget(self, kind: str, name: str, mode: str) -> None:
        key = self._key(kind, name, mode)
        entries = cast(object, self._data.get("entries"))
        if not isinstance(entries, dict):
            return
        entry_map = cast(dict[str, _FileLookupEntry], entries)
        if key in entry_map:
            entry_map.pop(key, None)
            self._record_mutation()

    def flush(self) -> None:
        if not self._dirty:
            return
        self._save()
        self._dirty = False
        self._pending_mutations = 0


class FileASTCache:
    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir / "file_ast"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._startup_pruned_entries = self.prune_stale_entries()

    def _stat(self, code_path: Path) -> os.stat_result | None:
        return _safe_stat(code_path)

    def _key(self, code_path: Path, mode: str) -> str:
        h = hashlib.sha256()
        h.update(str(code_path).encode("utf-8", errors="ignore"))
        h.update(mode.encode("utf-8", errors="ignore"))
        return h.hexdigest()

    def _path(self, code_path: Path, mode: str) -> Path:
        return self.cache_dir / f"{self._key(code_path, mode)}.pickle"

    def load(self, code_path: Path, mode: str) -> object | None:
        p = self._path(code_path, mode)
        if not p.exists():
            return None
        payload = _load_pickle_payload(p)
        if payload is None:
            return None

        payload_map = _as_mapping(payload)
        if payload_map is None or payload_map.get("version") != CACHE_VERSION:
            return None
        meta = _as_mapping(payload_map.get("meta"))
        if meta is None:
            return None
        if meta.get("path") != str(code_path):
            return None
        if meta.get("mode") != mode:
            return None
        if not _matches_stat_snapshot(
            code_path,
            mtime_ns=meta.get("mtime_ns"),
            size=meta.get("size"),
        ):
            return None

        return payload_map.get("ast")

    def prune_stale_entries(self) -> int:
        removed = 0
        for path in self.cache_dir.glob("*.pickle"):
            payload = _load_pickle_payload(path)
            payload_map = _as_mapping(payload)
            if payload_map is not None and payload_map.get("version") == CACHE_VERSION:
                continue
            if _remove_file(path):
                removed += 1
        return removed

    def drain_startup_pruned_entries(self) -> int:
        removed = self._startup_pruned_entries
        self._startup_pruned_entries = 0
        return removed

    def save(self, code_path: Path, mode: str, ast: object) -> None:
        st = self._stat(code_path)
        if st is None:
            return
        payload: dict[str, object] = {
            "version": CACHE_VERSION,
            "meta": {
                "path": str(code_path),
                "mode": mode,
                "mtime_ns": st.st_mtime_ns,
                "size": st.st_size,
            },
            "ast": ast,
        }
        with self._path(code_path, mode).open("wb") as f:
            pickle.dump(payload, f, protocol=pickle.HIGHEST_PROTOCOL)


PROJECT_CACHE_SCHEMA_VERSION = "2026-05-28-library-reverse-consumer-scan"
ANALYSIS_REPORT_CACHE_SCHEMA_VERSION = "2026-06-04-string-literal-mismatch-threshold"


def compute_cache_key(cfg: Mapping[str, object]) -> str:
    """
    Fast cache key based only on configuration.
    File changes are handled by manifest validation.
    """
    h = hashlib.sha256()
    h.update(PROJECT_CACHE_SCHEMA_VERSION.encode())
    h.update(repr(cfg.get("analysis_target")).encode())

    for k in PROJECT_CACHE_CONFIG_KEYS:
        h.update(repr(cfg.get(k)).encode())

    return h.hexdigest()


def compute_analysis_report_cache_key(project_cache_key: str, analyzer_key: str) -> str:
    h = hashlib.sha256()
    h.update(ANALYSIS_REPORT_CACHE_SCHEMA_VERSION.encode())
    h.update(project_cache_key.encode("utf-8", errors="ignore"))
    h.update(analyzer_key.encode("utf-8", errors="ignore"))
    return h.hexdigest()


class ASTCache:
    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._startup_prune_result = self.prune_stale_entries()

    def _path(self, key: str) -> Path:
        return self.cache_dir / f"{key}.pickle"

    def _manifest_path(self, key: str) -> Path:
        return self.cache_dir / f"{key}.manifest.json"

    def load(self, key: str) -> object | None:
        p = self._path(key)
        if not p.exists():
            return None
        payload = _load_pickle_payload(p)
        payload_map = _as_mapping(payload)
        if payload_map is None or payload_map.get("version") != CACHE_VERSION:
            return None
        return payload

    def has_payload(self, key: str) -> bool:
        return self._path(key).exists()

    def load_manifest(self, key: str) -> dict[str, tuple[int, int]] | None:
        return _load_manifest_payload(self._manifest_path(key))

    def has_manifest(self, key: str) -> bool:
        return self.load_manifest(key) is not None

    def manifest_paths(self, key: str) -> frozenset[Path]:
        manifest = self.load_manifest(key)
        if manifest is None:
            return frozenset()
        return frozenset(Path(path_str) for path_str in manifest)

    def save(
        self,
        key: str,
        *,
        project: object,
        files: Iterable[Path],
    ) -> None:
        manifest = _snapshot_manifest(files)
        if manifest is None:
            return

        payload: dict[str, object] = {
            "version": CACHE_VERSION,
            "project": project,
        }

        with self._manifest_path(key).open("w", encoding="utf-8") as handle:
            json.dump(manifest, handle, ensure_ascii=True, indent=2, sort_keys=True)

        with self._path(key).open("wb") as f:
            pickle.dump(payload, f, protocol=pickle.HIGHEST_PROTOCOL)

    def validate(self, key: str, *, fast: bool = False) -> bool:
        if self.load(key) is None:
            return False

        manifest = self.load_manifest(key)
        if manifest is None:
            return False

        if fast:
            return True

        return _validate_manifest(manifest)

    def prune_stale_entries(self) -> CachePruneResult:
        removed_payloads = 0
        removed_manifests = 0
        payload_stems: set[str] = set()

        for payload_path in self.cache_dir.glob("*.pickle"):
            payload_stems.add(payload_path.stem)
            manifest_path = self._manifest_path(payload_path.stem)
            payload = _load_pickle_payload(payload_path)
            payload_map = _as_mapping(payload)
            manifest = _load_manifest_payload(manifest_path) if manifest_path.exists() else None
            payload_valid = payload_map is not None and payload_map.get("version") == CACHE_VERSION
            manifest_valid = manifest is not None

            if payload_valid and manifest_valid:
                continue

            if _remove_file(payload_path):
                removed_payloads += 1
            if manifest_path.exists() and _remove_file(manifest_path):
                removed_manifests += 1

        for manifest_path in self.cache_dir.glob("*.manifest.json"):
            if manifest_path.name[: -len(".manifest.json")] in payload_stems:
                continue
            if _remove_file(manifest_path):
                removed_manifests += 1

        return CachePruneResult(
            ast_payload_entries=removed_payloads,
            ast_manifest_entries=removed_manifests,
        )

    def drain_startup_prune_result(self) -> CachePruneResult:
        result = self._startup_prune_result
        self._startup_prune_result = CachePruneResult()
        return result

    def clear(self, key: str) -> None:
        """Remove cache file for the given key."""
        p = self._path(key)
        if p.exists():
            p.unlink()
        manifest_path = self._manifest_path(key)
        if manifest_path.exists():
            manifest_path.unlink()


class AnalysisReportCache:
    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir / "analysis_reports"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._startup_pruned_entries = self.prune_stale_entries()

    def _path(self, key: str) -> Path:
        return self.cache_dir / f"{key}.pickle"

    def load(self, key: str) -> object | None:
        p = self._path(key)
        if not p.exists():
            return None
        payload = _load_pickle_payload(p)
        if payload is None:
            return None
        return payload

    def save(
        self,
        key: str,
        *,
        report: object,
        files: Iterable[Path],
    ) -> bool:
        manifest = _snapshot_manifest(files)
        if manifest is None:
            return False

        payload: dict[str, object] = {
            "version": ANALYSIS_REPORT_CACHE_VERSION,
            "report": report,
            "files": manifest,
        }

        try:
            with self._path(key).open("wb") as f:
                pickle.dump(payload, f, protocol=pickle.HIGHEST_PROTOCOL)
        except (OSError, pickle.PicklingError, TypeError, AttributeError, ValueError):
            return False

        return True

    def validate(self, payload: object, *, fast: bool = False) -> bool:
        payload_map = _as_mapping(payload)
        if payload_map is None or payload_map.get("version") != ANALYSIS_REPORT_CACHE_VERSION:
            return False

        if fast:
            return "report" in payload_map

        return _validate_manifest(payload_map.get("files"))

    def clear(self, key: str) -> None:
        p = self._path(key)
        if p.exists():
            p.unlink()

    def clear_all(self) -> int:
        removed = 0
        for path in self.cache_dir.glob("*.pickle"):
            try:
                path.unlink()
            except OSError:
                continue
            removed += 1
        return removed

    def prune_stale_entries(self) -> int:
        removed = 0
        for path in self.cache_dir.glob("*.pickle"):
            payload = _load_pickle_payload(path)
            if self.validate(payload, fast=True):
                continue
            if _remove_file(path):
                removed += 1
        return removed

    def drain_startup_pruned_entries(self) -> int:
        removed = self._startup_pruned_entries
        self._startup_pruned_entries = 0
        return removed


class CacheManager:
    def __init__(
        self,
        cache_dir: Path | None = None,
        *,
        file_lookup_cache_cls: type[FileLookupCache] = FileLookupCache,
        file_ast_cache_cls: type[FileASTCache] = FileASTCache,
        ast_cache_cls: type[ASTCache] = ASTCache,
        analysis_report_cache_cls: type[AnalysisReportCache] = AnalysisReportCache,
    ) -> None:
        resolved_cache_dir = get_cache_dir() if cache_dir is None else cache_dir
        self.cache_dir = resolved_cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._file_lookup_cache_cls = file_lookup_cache_cls
        self._file_ast_cache_cls = file_ast_cache_cls
        self._ast_cache_cls = ast_cache_cls
        self._analysis_report_cache_cls = analysis_report_cache_cls
        self._file_lookup_cache: FileLookupCache | None = None
        self._file_ast_cache: FileASTCache | None = None
        self._ast_cache: ASTCache | None = None
        self._analysis_report_cache: AnalysisReportCache | None = None

    @property
    def file_lookup_cache(self) -> FileLookupCache:
        if self._file_lookup_cache is None:
            self._file_lookup_cache = self._file_lookup_cache_cls(self.cache_dir)
        return self._file_lookup_cache

    @property
    def file_ast_cache(self) -> FileASTCache:
        if self._file_ast_cache is None:
            self._file_ast_cache = self._file_ast_cache_cls(self.cache_dir)
        return self._file_ast_cache

    @property
    def ast_cache(self) -> ASTCache:
        if self._ast_cache is None:
            self._ast_cache = self._ast_cache_cls(self.cache_dir)
        return self._ast_cache

    @property
    def analysis_report_cache(self) -> AnalysisReportCache:
        if self._analysis_report_cache is None:
            self._analysis_report_cache = self._analysis_report_cache_cls(self.cache_dir)
        return self._analysis_report_cache

    def prune_stale_entries(self) -> CachePruneResult:
        result = CachePruneResult()
        file_lookup_cache = self.file_lookup_cache
        file_ast_cache = self.file_ast_cache
        ast_cache = self.ast_cache
        analysis_report_cache = self.analysis_report_cache
        result = result.combine(
            CachePruneResult(
                file_lookup_entries=file_lookup_cache.drain_startup_pruned_entries()
                + file_lookup_cache.prune_stale_entries()
            )
        )
        result = result.combine(
            CachePruneResult(
                file_ast_entries=file_ast_cache.drain_startup_pruned_entries() + file_ast_cache.prune_stale_entries()
            )
        )
        result = result.combine(ast_cache.drain_startup_prune_result().combine(ast_cache.prune_stale_entries()))
        result = result.combine(
            CachePruneResult(
                analysis_report_entries=analysis_report_cache.drain_startup_pruned_entries()
                + analysis_report_cache.prune_stale_entries()
            )
        )
        return result


_CACHE_MANAGERS: dict[Path, CacheManager] = {}


def _uses_default_cache_types(
    *,
    file_lookup_cache_cls: type[FileLookupCache],
    file_ast_cache_cls: type[FileASTCache],
    ast_cache_cls: type[ASTCache],
    analysis_report_cache_cls: type[AnalysisReportCache],
) -> bool:
    return (
        file_lookup_cache_cls is FileLookupCache
        and file_ast_cache_cls is FileASTCache
        and ast_cache_cls is ASTCache
        and analysis_report_cache_cls is AnalysisReportCache
    )


def get_cache_manager(
    cache_dir: Path | None = None,
    *,
    file_lookup_cache_cls: type[FileLookupCache] = FileLookupCache,
    file_ast_cache_cls: type[FileASTCache] = FileASTCache,
    ast_cache_cls: type[ASTCache] = ASTCache,
    analysis_report_cache_cls: type[AnalysisReportCache] = AnalysisReportCache,
) -> CacheManager:
    raw_cache_dir = get_cache_dir() if cache_dir is None else cache_dir
    resolved_cache_dir = _normalize_cache_dir(raw_cache_dir)
    if not _uses_default_cache_types(
        file_lookup_cache_cls=file_lookup_cache_cls,
        file_ast_cache_cls=file_ast_cache_cls,
        ast_cache_cls=ast_cache_cls,
        analysis_report_cache_cls=analysis_report_cache_cls,
    ):
        return CacheManager(
            raw_cache_dir,
            file_lookup_cache_cls=file_lookup_cache_cls,
            file_ast_cache_cls=file_ast_cache_cls,
            ast_cache_cls=ast_cache_cls,
            analysis_report_cache_cls=analysis_report_cache_cls,
        )

    manager = _CACHE_MANAGERS.get(resolved_cache_dir)
    if manager is None:
        manager = CacheManager(resolved_cache_dir)
        _CACHE_MANAGERS[resolved_cache_dir] = manager
    return manager


def build_file_lookup_cache(cache_dir: Path, file_lookup_cache_cls: type[Any] = FileLookupCache) -> Any:
    return get_cache_manager(
        cache_dir,
        file_lookup_cache_cls=cast(type[FileLookupCache], file_lookup_cache_cls),
    ).file_lookup_cache


def build_file_ast_cache(cache_dir: Path, file_ast_cache_cls: type[Any] = FileASTCache) -> Any:
    return get_cache_manager(
        cache_dir,
        file_ast_cache_cls=cast(type[FileASTCache], file_ast_cache_cls),
    ).file_ast_cache


def build_ast_cache(cache_dir: Path, ast_cache_cls: type[Any] = ASTCache) -> Any:
    return get_cache_manager(
        cache_dir,
        ast_cache_cls=cast(type[ASTCache], ast_cache_cls),
    ).ast_cache


def build_analysis_report_cache(cache_dir: Path, analysis_report_cache_cls: type[Any] = AnalysisReportCache) -> Any:
    return get_cache_manager(
        cache_dir,
        analysis_report_cache_cls=cast(type[AnalysisReportCache], analysis_report_cache_cls),
    ).analysis_report_cache


def prune_cache_dir(cache_dir: Path | None = None) -> CachePruneResult:
    return get_cache_manager(cache_dir).prune_stale_entries()
