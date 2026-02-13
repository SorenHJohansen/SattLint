"""Cache helpers for parsed ASTs and file manifests."""
from __future__ import annotations
import hashlib
import pickle
from pathlib import Path
from typing import Iterable
import json
import os

CACHE_VERSION = 2  # Bump when the cache payload format changes.
LOOKUP_CACHE_VERSION = 1


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
        self._data = {"version": LOOKUP_CACHE_VERSION, "entries": {}}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            with self.path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("version") != LOOKUP_CACHE_VERSION:
                return
            entries = data.get("entries")
            if isinstance(entries, dict):
                self._data["entries"] = entries
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

    def get(self, kind: str, name: str, mode: str) -> dict | None:
        key = self._key(kind, name, mode)
        entry = self._data.get("entries", {}).get(key)
        return entry if isinstance(entry, dict) else None

    def set(self, kind: str, name: str, mode: str, base_dir: Path, ext: str) -> None:
        key = self._key(kind, name, mode)
        self._data.setdefault("entries", {})[key] = {
            "base_dir": str(base_dir),
            "ext": ext,
        }
        self._save()

    def forget(self, kind: str, name: str, mode: str) -> None:
        key = self._key(kind, name, mode)
        entries = self._data.get("entries", {})
        if key in entries:
            entries.pop(key, None)
            self._save()


class FileASTCache:
    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir / "file_ast"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _key(self, code_path: Path, mode: str) -> str:
        h = hashlib.sha256()
        h.update(str(code_path).encode("utf-8", errors="ignore"))
        h.update(mode.encode("utf-8", errors="ignore"))
        return h.hexdigest()

    def _path(self, code_path: Path, mode: str) -> Path:
        return self.cache_dir / f"{self._key(code_path, mode)}.pickle"

    def load(self, code_path: Path, mode: str):
        p = self._path(code_path, mode)
        if not p.exists():
            return None
        try:
            with p.open("rb") as f:
                payload = pickle.load(f)
        except (OSError, pickle.UnpicklingError):
            return None

        if payload.get("version") != CACHE_VERSION:
            return None
        meta = payload.get("meta", {})
        if meta.get("path") != str(code_path):
            return None
        if meta.get("mode") != mode:
            return None

        if not code_path.exists():
            return None

        st = code_path.stat()
        if meta.get("mtime_ns") != st.st_mtime_ns or meta.get("size") != st.st_size:
            return None

        return payload.get("ast")

    def save(self, code_path: Path, mode: str, ast) -> None:
        st = code_path.stat()
        payload = {
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


def compute_cache_key(cfg: dict) -> str:
    """
    Fast cache key based only on configuration.
    File changes are handled by manifest validation.
    """
    h = hashlib.sha256()

    for k in (
        "root",
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


class ASTCache:
    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        return self.cache_dir / f"{key}.pickle"

    def load(self, key: str):
        p = self._path(key)
        if not p.exists():
            return None
        with p.open("rb") as f:
            return pickle.load(f)

    def save(
        self,
        key: str,
        *,
        project,
        files: Iterable[Path],
    ) -> None:
        manifest = {str(p): (p.stat().st_mtime_ns, p.stat().st_size) for p in files}

        payload = {
            "version": CACHE_VERSION,
            "project": project,
            "files": manifest,
        }

        with self._path(key).open("wb") as f:
            pickle.dump(payload, f, protocol=pickle.HIGHEST_PROTOCOL)

    def validate(self, payload, *, fast: bool = False) -> bool:
        if payload.get("version") != CACHE_VERSION:
            return False

        if fast:
            return "project" in payload

        for path_str, (mtime, size) in payload.get("files", {}).items():
            p = Path(path_str)
            if not p.exists():
                return False

            st = p.stat()
            if st.st_mtime_ns != mtime or st.st_size != size:
                return False

        return True

    def clear(self, key: str) -> None:
        """Remove cache file for the given key."""
        p = self._path(key)
        if p.exists():
            p.unlink()
