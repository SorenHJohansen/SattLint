from __future__ import annotations
import hashlib
import pickle
from pathlib import Path
from typing import Iterable

CACHE_VERSION = 2  # bump because format changed


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
        "program_dir",
        "ABB_lib_dir",
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

    def validate(self, payload) -> bool:
        if payload.get("version") != CACHE_VERSION:
            return False

        for path_str, (mtime, size) in payload["files"].items():
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
