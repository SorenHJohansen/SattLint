"""Cache helpers for parsed ASTs and file manifests."""
# pyright: reportUnusedFunction=false

from __future__ import annotations

import hashlib
import hmac
import json
import os
import pickle
import secrets
import shutil
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import TypedDict, cast

from ._cache_classes import AnalysisReportCache, ASTCache, FileASTCache, FileLookupCache
from ._cache_manager import (
    CacheManager,
    build_analysis_report_cache,
    build_ast_cache,
    get_cache_manager,
    prune_cache_dir,
)
from ._config_defaults import PROJECT_CACHE_CONFIG_KEYS

__all__ = [
    "ANALYSIS_REPORT_CACHE_VERSION",
    "CACHE_VERSION",
    "LOOKUP_CACHE_VERSION",
    "ASTCache",
    "AnalysisReportCache",
    "CacheManager",
    "CachePruneResult",
    "FileASTCache",
    "FileLookupCache",
    "build_analysis_report_cache",
    "build_ast_cache",
    "get_cache_dir",
    "get_cache_manager",
    "prune_cache_dir",
]

CACHE_VERSION = 15  # Bump when cached AST semantics or attached graphics companion record shapes change.
ANALYSIS_REPORT_CACHE_VERSION = 3
LOOKUP_CACHE_VERSION = 1
_PICKLE_CACHE_MAGIC = b"SATTLINT-PICKLE-V1\n"
_PICKLE_HMAC_KEY_NAME = ".pickle-hmac-key"
_PICKLE_HMAC_SIZE = 32


class _FileLookupEntry(TypedDict):
    base_dir: str
    ext: str


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
        payload_bytes = path.read_bytes()
    except OSError:
        return None

    signature, pickled_payload = _read_signed_pickle_envelope(payload_bytes)
    if signature is None:
        return None

    key = _load_or_create_pickle_hmac_key(path.parent)
    if key is None:
        return None

    expected_signature = hmac.new(key, pickled_payload, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected_signature):
        return None

    try:
        return pickle.loads(pickled_payload)
    except (pickle.UnpicklingError, TypeError, AttributeError, EOFError, ModuleNotFoundError, ValueError):
        return None


def _pickle_hmac_key_path(directory: Path) -> Path:
    return directory / _PICKLE_HMAC_KEY_NAME


def _load_or_create_pickle_hmac_key(directory: Path) -> bytes | None:
    key_path = _pickle_hmac_key_path(directory)
    existing_key = _read_pickle_hmac_key(key_path)
    if existing_key is not None:
        return existing_key
    if key_path.exists() and not _remove_file(key_path):
        return None

    directory.mkdir(parents=True, exist_ok=True)
    key = secrets.token_bytes(_PICKLE_HMAC_SIZE)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    try:
        fd = os.open(key_path, flags, 0o600)
    except FileExistsError:
        return _read_pickle_hmac_key(key_path)
    except OSError:
        return None

    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(key)
            handle.flush()
            os.fsync(handle.fileno())
    except OSError:
        _remove_file(key_path)
        return None

    return key


def _read_pickle_hmac_key(path: Path) -> bytes | None:
    try:
        key = path.read_bytes()
    except OSError:
        return None
    if len(key) != _PICKLE_HMAC_SIZE:
        return None
    return key


def _read_signed_pickle_envelope(payload_bytes: bytes) -> tuple[str | None, bytes]:
    if not payload_bytes.startswith(_PICKLE_CACHE_MAGIC):
        return None, b""

    remainder = payload_bytes[len(_PICKLE_CACHE_MAGIC) :]
    signature, separator, pickled_payload = remainder.partition(b"\n")
    if separator != b"\n" or len(signature) != hashlib.sha256().digest_size * 2:
        return None, b""

    try:
        return signature.decode("ascii"), pickled_payload
    except UnicodeDecodeError:
        return None, b""


def _save_pickle_payload(path: Path, payload: object) -> None:
    key = _load_or_create_pickle_hmac_key(path.parent)
    if key is None:
        raise OSError(f"Could not create pickle HMAC key for {path.parent}")

    pickled_payload = pickle.dumps(payload, protocol=pickle.HIGHEST_PROTOCOL)
    signature = hmac.new(key, pickled_payload, hashlib.sha256).hexdigest().encode("ascii")
    temp_path = path.with_name(f"{path.name}.tmp")

    try:
        with temp_path.open("wb") as handle:
            handle.write(_PICKLE_CACHE_MAGIC)
            handle.write(signature)
            handle.write(b"\n")
            handle.write(pickled_payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    except OSError:
        _remove_file(temp_path)
        raise


def _remove_file(path: Path) -> bool:
    try:
        path.unlink()
    except OSError:
        return False
    return True


def _legacy_cache_dir() -> Path:
    xdg_config_home = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg_config_home) if xdg_config_home is not None else Path.home() / ".config"
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
        appdata = os.environ.get("APPDATA")
        base = Path(appdata) if appdata is not None else Path.home() / "AppData" / "Roaming"
        cache_dir = base / "sattlint" / "cache"
    else:
        xdg_cache_home = os.environ.get("XDG_CACHE_HOME")
        base = Path(xdg_cache_home) if xdg_cache_home is not None else Path.home() / ".cache"
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


PROJECT_CACHE_SCHEMA_VERSION = "2026-06-11-project-graph-root-origin-schema"
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
