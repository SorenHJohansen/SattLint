"""Cache class implementations shared by sattlint.cache."""

from __future__ import annotations

import hashlib
import json
import os
import pickle
from collections.abc import Iterable
from pathlib import Path
from typing import cast

from . import cache as cache_module


class FileLookupCache:
    def __init__(
        self,
        cache_dir: Path,
        *,
        flush_interval: int | None = cache_module.DEFAULT_LOOKUP_CACHE_FLUSH_INTERVAL,
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
        self._data = {"version": cache_module.LOOKUP_CACHE_VERSION, "entries": {}}
        self._dirty = False
        self._startup_pruned_entries = self.prune_stale_entries()
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            with self.path.open("r", encoding="utf-8") as f:
                loaded = json.load(f)
            data = cache_module._as_mapping(loaded)
            if data is None or data.get("version") != cache_module.LOOKUP_CACHE_VERSION:
                return
            entries = cache_module._load_file_lookup_entries(data.get("entries"))
            if entries is not None:
                self._data = {"version": cache_module.LOOKUP_CACHE_VERSION, "entries": entries}
        except (OSError, json.JSONDecodeError):
            return

    def prune_stale_entries(self) -> int:
        if not self.path.exists():
            return 0
        try:
            with self.path.open("r", encoding="utf-8") as handle:
                loaded = json.load(handle)
        except (OSError, json.JSONDecodeError):
            return 1 if cache_module._remove_file(self.path) else 0

        data = cache_module._as_mapping(loaded)
        if data is None or data.get("version") != cache_module.LOOKUP_CACHE_VERSION:
            return 1 if cache_module._remove_file(self.path) else 0
        return 0

    def drain_startup_pruned_entries(self) -> int:
        removed = self._startup_pruned_entries
        self._startup_pruned_entries = 0
        return removed

    def _save(self) -> None:
        payload = {
            "version": cache_module.LOOKUP_CACHE_VERSION,
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
        entry = cache_module._as_file_lookup_entry(cast(dict[str, object], entries).get(key))
        if entry is None:
            return None
        return {"base_dir": entry["base_dir"], "ext": entry["ext"]}

    def set(self, kind: str, name: str, mode: str, base_dir: Path, ext: str) -> None:
        key = self._key(kind, name, mode)
        entries = cast(object, self._data.setdefault("entries", {}))
        if not isinstance(entries, dict):
            return
        entry_map = cast(dict[str, dict[str, str]], entries)
        payload = {
            "base_dir": cache_module._normalize_lookup_base_dir(base_dir),
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
        entry_map = cast(dict[str, dict[str, str]], entries)
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
        return cache_module._safe_stat(code_path)

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
        payload = cache_module._load_pickle_payload(p)
        if payload is None:
            return None

        payload_map = cache_module._as_mapping(payload)
        if payload_map is None or payload_map.get("version") != cache_module.CACHE_VERSION:
            return None
        meta = cache_module._as_mapping(payload_map.get("meta"))
        if meta is None:
            return None
        if meta.get("path") != str(code_path):
            return None
        if meta.get("mode") != mode:
            return None
        if not cache_module._matches_stat_snapshot(
            code_path,
            mtime_ns=meta.get("mtime_ns"),
            size=meta.get("size"),
        ):
            return None

        return payload_map.get("ast")

    def prune_stale_entries(self) -> int:
        removed = 0
        for path in self.cache_dir.glob("*.pickle"):
            payload = cache_module._load_pickle_payload(path)
            payload_map = cache_module._as_mapping(payload)
            if payload_map is not None and payload_map.get("version") == cache_module.CACHE_VERSION:
                continue
            if cache_module._remove_file(path):
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
            "version": cache_module.CACHE_VERSION,
            "meta": {
                "path": str(code_path),
                "mode": mode,
                "mtime_ns": st.st_mtime_ns,
                "size": st.st_size,
            },
            "ast": ast,
        }
        cache_module._save_pickle_payload(self._path(code_path, mode), payload)


class ASTCache:
    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._startup_prune_result = self.prune_startup_entries()

    def _path(self, key: str) -> Path:
        return self.cache_dir / f"{key}.pickle"

    def _manifest_path(self, key: str) -> Path:
        return self.cache_dir / f"{key}.manifest.json"

    def load(self, key: str) -> object | None:
        p = self._path(key)
        if not p.exists():
            return None
        payload = cache_module._load_pickle_payload(p)
        payload_map = cache_module._as_mapping(payload)
        if payload_map is None or payload_map.get("version") != cache_module.CACHE_VERSION:
            return None
        return payload

    def has_payload(self, key: str) -> bool:
        return self._path(key).exists()

    def load_manifest(self, key: str) -> dict[str, tuple[int, int]] | None:
        return cache_module._load_manifest_payload(self._manifest_path(key))

    def has_manifest(self, key: str) -> bool:
        return self.load_manifest(key) is not None

    def has_cache_artifact(self, key: str) -> bool:
        return self.has_payload(key) and self.has_manifest(key)

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
        manifest = cache_module._snapshot_manifest(files)
        if manifest is None:
            return

        payload: dict[str, object] = {
            "version": cache_module.CACHE_VERSION,
            "project": project,
        }

        with self._manifest_path(key).open("w", encoding="utf-8") as handle:
            json.dump(manifest, handle, ensure_ascii=True, indent=2, sort_keys=True)

        cache_module._save_pickle_payload(self._path(key), payload)

    def load_validated(self, key: str) -> object | None:
        manifest = self.load_manifest(key)
        if manifest is None:
            return None

        payload = self.load(key)
        if payload is None:
            return None

        if not cache_module._validate_manifest(manifest):
            return None

        return payload

    def prune_startup_entries(self) -> cache_module.CachePruneResult:
        removed_payloads = 0
        removed_manifests = 0
        payload_stems: set[str] = set()

        for payload_path in self.cache_dir.glob("*.pickle"):
            payload_stems.add(payload_path.stem)
            manifest_path = self._manifest_path(payload_path.stem)
            manifest_valid = manifest_path.exists() and cache_module._load_manifest_payload(manifest_path) is not None

            if manifest_valid:
                continue

            if cache_module._remove_file(payload_path):
                removed_payloads += 1
            if manifest_path.exists() and cache_module._remove_file(manifest_path):
                removed_manifests += 1

        for manifest_path in self.cache_dir.glob("*.manifest.json"):
            if manifest_path.name[: -len(".manifest.json")] in payload_stems:
                continue
            if cache_module._remove_file(manifest_path):
                removed_manifests += 1

        return cache_module.CachePruneResult(
            ast_payload_entries=removed_payloads,
            ast_manifest_entries=removed_manifests,
        )

    def prune_stale_entries(self) -> cache_module.CachePruneResult:
        removed_payloads = 0
        removed_manifests = 0
        payload_stems: set[str] = set()

        for payload_path in self.cache_dir.glob("*.pickle"):
            payload_stems.add(payload_path.stem)
            manifest_path = self._manifest_path(payload_path.stem)
            payload = cache_module._load_pickle_payload(payload_path)
            payload_map = cache_module._as_mapping(payload)
            manifest = cache_module._load_manifest_payload(manifest_path) if manifest_path.exists() else None
            payload_valid = payload_map is not None and payload_map.get("version") == cache_module.CACHE_VERSION
            manifest_valid = manifest is not None

            if payload_valid and manifest_valid:
                continue

            if cache_module._remove_file(payload_path):
                removed_payloads += 1
            if manifest_path.exists() and cache_module._remove_file(manifest_path):
                removed_manifests += 1

        for manifest_path in self.cache_dir.glob("*.manifest.json"):
            if manifest_path.name[: -len(".manifest.json")] in payload_stems:
                continue
            if cache_module._remove_file(manifest_path):
                removed_manifests += 1

        return cache_module.CachePruneResult(
            ast_payload_entries=removed_payloads,
            ast_manifest_entries=removed_manifests,
        )

    def drain_startup_prune_result(self) -> cache_module.CachePruneResult:
        result = self._startup_prune_result
        self._startup_prune_result = cache_module.CachePruneResult()
        return result

    def clear(self, key: str) -> None:
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
        payload = cache_module._load_pickle_payload(p)
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
        manifest = cache_module._snapshot_manifest(files)
        if manifest is None:
            return False

        payload: dict[str, object] = {
            "version": cache_module.ANALYSIS_REPORT_CACHE_VERSION,
            "report": report,
            "files": manifest,
        }

        try:
            cache_module._save_pickle_payload(self._path(key), payload)
        except (OSError, pickle.PicklingError, TypeError, AttributeError, ValueError):
            return False

        return True

    def validate(self, payload: object, *, fast: bool = False) -> bool:
        payload_map = cache_module._as_mapping(payload)
        if payload_map is None or payload_map.get("version") != cache_module.ANALYSIS_REPORT_CACHE_VERSION:
            return False

        if fast:
            return "report" in payload_map

        return cache_module._validate_manifest(payload_map.get("files"))

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
            payload = cache_module._load_pickle_payload(path)
            if self.validate(payload, fast=True):
                continue
            if cache_module._remove_file(path):
                removed += 1
        return removed

    def drain_startup_pruned_entries(self) -> int:
        removed = self._startup_pruned_entries
        self._startup_pruned_entries = 0
        return removed
