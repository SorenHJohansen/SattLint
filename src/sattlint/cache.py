"""Cache helpers for parsed ASTs and file manifests."""

from __future__ import annotations

import hashlib
import json
import os
import pickle  # nosec B403 - trusted local cache files only
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import cast

CACHE_VERSION = 14  # Bump when cached AST semantics or warning content changes.
ANALYSIS_REPORT_CACHE_VERSION = 1
LOOKUP_CACHE_VERSION = 1


def _as_mapping(value: object) -> Mapping[str, object] | None:
    if not isinstance(value, Mapping):
        return None
    return cast(Mapping[str, object], value)


def _safe_stat(path: Path) -> os.stat_result | None:
    try:
        return path.stat()
    except OSError:
        return None


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
        if not isinstance(mtime, int) or not isinstance(size, int):
            return False
        p = Path(path_str)
        if not p.exists():
            return False

        st = _safe_stat(p)
        if st is None:
            return False
        if st.st_mtime_ns != mtime or st.st_size != size:
            return False

    return True


def get_cache_dir() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))

    cache_dir = base / "sattlint" / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


class FileLookupCache:
    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.cache_dir / "file_lookup_cache.json"
        self._data: dict[str, object] = {"version": LOOKUP_CACHE_VERSION, "entries": {}}
        self._dirty = False
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
            entries = data.get("entries")
            if isinstance(entries, dict):
                self._data["entries"] = cast(dict[str, object], entries)
        except (OSError, json.JSONDecodeError):
            return

    def _save(self) -> None:
        payload = {
            "version": LOOKUP_CACHE_VERSION,
            "entries": self._data.get("entries", {}),
        }
        with self.path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=True, indent=2, sort_keys=True)

    def _key(self, kind: str, name: str, mode: str) -> str:
        return f"{kind}:{mode}:{name.casefold()}"

    def get(self, kind: str, name: str, mode: str) -> dict[str, str] | None:
        key = self._key(kind, name, mode)
        entries = self._data.get("entries")
        if not isinstance(entries, dict):
            return None
        entry = cast(dict[str, object], entries).get(key)
        if not isinstance(entry, dict):
            return None
        entry_map = cast(dict[str, object], entry)
        base_dir = entry_map.get("base_dir")
        ext = entry_map.get("ext")
        if not isinstance(base_dir, str) or not isinstance(ext, str):
            return None
        return {"base_dir": base_dir, "ext": ext}

    def set(self, kind: str, name: str, mode: str, base_dir: Path, ext: str) -> None:
        key = self._key(kind, name, mode)
        entries = self._data.setdefault("entries", {})
        if not isinstance(entries, dict):
            return
        entry_map = cast(dict[str, object], entries)
        payload = {
            "base_dir": str(base_dir),
            "ext": ext,
        }
        if entry_map.get(key) == payload:
            return
        entry_map[key] = payload
        self._dirty = True

    def forget(self, kind: str, name: str, mode: str) -> None:
        key = self._key(kind, name, mode)
        entries = self._data.get("entries")
        if not isinstance(entries, dict):
            return
        entry_map = cast(dict[str, object], entries)
        if key in entry_map:
            entry_map.pop(key, None)
            self._dirty = True

    def flush(self) -> None:
        if not self._dirty:
            return
        self._save()
        self._dirty = False


class FileASTCache:
    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir / "file_ast"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

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
        try:
            with p.open("rb") as f:
                payload = pickle.load(f)  # nosec B301 - loading SattLint-owned local cache files only
        except (OSError, pickle.UnpicklingError, TypeError, AttributeError, EOFError):
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

        st = self._stat(code_path)
        if st is None:
            return None
        if meta.get("mtime_ns") != st.st_mtime_ns or meta.get("size") != st.st_size:
            return None

        return payload_map.get("ast")

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
ANALYSIS_REPORT_CACHE_SCHEMA_VERSION = "2026-05-29-analysis-report-cache"


def compute_cache_key(cfg: Mapping[str, object]) -> str:
    """
    Fast cache key based only on configuration.
    File changes are handled by manifest validation.
    """
    h = hashlib.sha256()
    h.update(PROJECT_CACHE_SCHEMA_VERSION.encode())

    for k in (
        "analysis_target",
        "analyzed_programs_and_libraries",
        "include_reverse_library_consumers",
        "mode",
        "scan_root_only",
        "fast_cache_validation",
        "program_dir",
        "ABB_lib_dir",
        "icf_dir",
        "other_lib_dirs",
    ):
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

    def _path(self, key: str) -> Path:
        return self.cache_dir / f"{key}.pickle"

    def _manifest_path(self, key: str) -> Path:
        return self.cache_dir / f"{key}.manifest.json"

    def load(self, key: str) -> object | None:
        p = self._path(key)
        if not p.exists():
            return None
        try:
            with p.open("rb") as f:
                return pickle.load(f)  # nosec B301 - loading SattLint-owned local cache files only
        except (OSError, pickle.UnpicklingError, TypeError, AttributeError, EOFError):
            return None

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
        manifest = self.load_manifest(key)
        if manifest is None:
            return False

        if not self.has_payload(key):
            return False

        if fast:
            return True

        return _validate_manifest(manifest)

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

    def _path(self, key: str) -> Path:
        return self.cache_dir / f"{key}.pickle"

    def load(self, key: str) -> object | None:
        p = self._path(key)
        if not p.exists():
            return None
        try:
            with p.open("rb") as f:
                return pickle.load(f)  # nosec B301 - loading SattLint-owned local cache files only
        except (OSError, pickle.UnpicklingError, TypeError, AttributeError, EOFError):
            return None

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
