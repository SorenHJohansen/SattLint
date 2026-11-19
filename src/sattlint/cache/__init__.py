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
import uuid
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from .. import parser_api
from ..config.defaults import PROJECT_CACHE_CONFIG_KEYS
from .classes import AnalysisReportCache, ASTCache
from .manager import (
    CacheManager,
    build_analysis_report_cache,
    build_ast_cache,
    get_cache_manager,
    prune_cache_dir,
)

__all__ = [
    "ANALYSIS_REPORT_CACHE_VERSION",
    "CACHE_KEY_SCHEMA_VERSION",
    "CACHE_VERSION",
    "ASTCache",
    "AnalysisReportCache",
    "CacheManager",
    "CachePruneResult",
    "build_analysis_report_cache",
    "build_ast_cache",
    "cache_dir_location",
    "compute_analysis_report_cache_key",
    "get_cache_dir",
    "get_cache_dir_or_none",
    "get_cache_manager",
    "prune_cache_dir",
]

CACHE_VERSION = 17  # Bump when cached AST semantics or attached graphics companion record shapes change.
_legacy_migration_attempted = False
ANALYSIS_REPORT_CACHE_VERSION = 5
_PICKLE_CACHE_MAGIC = b"SATTLINT-PICKLE-V1\n"
_PICKLE_HMAC_KEY_NAME = ".sattlint-cache-key"
_PICKLE_HMAC_SIZE = 32


@dataclass(frozen=True)
class CachePruneResult:
    ast_payload_entries: int = 0
    ast_manifest_entries: int = 0
    analysis_report_entries: int = 0

    @property
    def removed_entries(self) -> int:
        return self.ast_payload_entries + self.ast_manifest_entries + self.analysis_report_entries

    def combine(self, other: CachePruneResult) -> CachePruneResult:
        return CachePruneResult(
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


def _snapshot_manifest(files: Iterable[Path]) -> dict[str, tuple[int, int]] | None:
    manifest: dict[str, tuple[int, int]] = {}
    for path in files:
        stat_result = _safe_stat(path)
        if stat_result is None:
            return None
        manifest[str(path)] = (stat_result.st_mtime_ns, stat_result.st_size)
    # Nothing to validate against means nothing can ever go stale, so an empty
    # file set is not a cache entry at all.
    return manifest or None


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

    # Reading never creates the key: a payload whose key is absent cannot be
    # verified, so the entry is a miss rather than a reason to write state.
    key = _read_pickle_hmac_key(_pickle_hmac_key_path())
    if key is None:
        return None

    expected_signature = hmac.new(key, pickled_payload, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected_signature):
        return None

    try:
        return pickle.loads(pickled_payload)
    except (pickle.UnpicklingError, TypeError, AttributeError, EOFError, ModuleNotFoundError, ValueError):
        return None


def _pickle_hmac_key_path() -> Path:
    """The key file, kept outside the cache tree it signs.

    A key stored beside the payloads it protects is readable and replaceable by
    anything that can reach the payloads, so it protects nothing. The file sits
    one level above the cache root: it survives a cache clear or a directory
    copy, and neither operation carries it along with the data.
    """
    return cache_dir_location().parent / _PICKLE_HMAC_KEY_NAME


def _load_or_create_pickle_hmac_key() -> bytes | None:
    key_path = _pickle_hmac_key_path()
    existing_key = _read_pickle_hmac_key(key_path)
    if existing_key is not None:
        return existing_key
    if key_path.exists() and not _remove_file(key_path):
        return None

    key_path.parent.mkdir(parents=True, exist_ok=True)
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
    key = _load_or_create_pickle_hmac_key()
    if key is None:
        raise OSError(f"Could not create the cache signing key for {path}")

    pickled_payload = pickle.dumps(payload, protocol=pickle.HIGHEST_PROTOCOL)
    signature = hmac.new(key, pickled_payload, hashlib.sha256).hexdigest().encode("ascii")
    temp_path = path.with_name(f"{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")

    try:
        fd = os.open(temp_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as handle:
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


def _save_manifest_payload(path: Path, manifest: Mapping[str, tuple[int, int]]) -> None:
    """Write a manifest atomically, owner-only, like the payload it describes."""
    temp_path = path.with_name(f"{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    try:
        fd = os.open(temp_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(manifest, handle, ensure_ascii=True, indent=2, sort_keys=True)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    except OSError:
        _remove_file(temp_path)
        raise


def _legacy_cache_dir() -> Path:
    xdg_config_home = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg_config_home) if xdg_config_home is not None else Path.home() / ".config"
    return base / "sattlint" / "cache"


def _discard_cache_entry(path: Path) -> None:
    """Remove one legacy cache entry that the destination already owns."""
    if path.is_dir():
        try:
            shutil.rmtree(path)
        except OSError:
            return
        return
    _remove_file(path)


def _merge_cache_directories(source: Path, destination: Path) -> None:
    """Move every entry of *source* into *destination*, resolving name collisions.

    Cache payloads are content-addressed, so a name that exists in both trees is
    the same logical entry: the destination copy wins and the source copy is
    discarded. Consuming the collision is what lets the caller finish the
    migration; leaving the source entry behind kept the legacy tree alive and
    every later run walked it again.
    """
    for child in source.iterdir():
        target = destination / child.name
        if not target.exists():
            shutil.move(str(child), str(target))
            continue
        if child.is_dir() and target.is_dir():
            _merge_cache_directories(child, target)
            try:
                child.rmdir()
            except OSError:
                continue
            continue
        _discard_cache_entry(child)


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


def cache_dir_location() -> Path:
    """The cache directory path without creating or migrating it."""
    if os.name == "nt":
        appdata = os.environ.get("APPDATA")
        base = Path(appdata) if appdata is not None else Path.home() / "AppData" / "Roaming"
        return base / "sattlint" / "cache"
    xdg_cache_home = os.environ.get("XDG_CACHE_HOME")
    base = Path(xdg_cache_home) if xdg_cache_home is not None else Path.home() / ".cache"
    return base / "sattlint"


def get_cache_dir() -> Path:
    global _legacy_migration_attempted

    cache_dir = cache_dir_location()
    if os.name != "nt" and not _legacy_migration_attempted:
        # The old layout is migrated once per process: a lookup should not walk
        # and move a legacy tree on every cache access.
        _legacy_migration_attempted = True
        _migrate_legacy_cache_dir(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def get_cache_dir_or_none() -> Path | None:
    """The cache directory, or ``None`` when it cannot be created.

    Every caller that persists something degrades to running without a cache
    instead of aborting the invocation, so the unusable-directory path has one
    spelling and one place to test.
    """
    try:
        return get_cache_dir()
    except OSError:
        return None


def _normalize_cache_dir(cache_dir: Path) -> Path:
    expanded = cache_dir.expanduser()
    try:
        return expanded.resolve()
    except OSError:
        return expanded


# One schema tag for every cache key. The parser version is read from the installed
# parser rather than embedded by hand, so a parser upgrade invalidates the key on its
# own; bump this tag only when the key's inputs or their encoding change.
CACHE_KEY_SCHEMA_VERSION = 1
_ANALYSIS_REPORT_ANALYZER_VERSIONS = {
    "comment-code": "2026-11-18-file-scoped-ast-paths",
    "cyclomatic-complexity": "2026-11-18-typedef-paths",
    "sfc": "2026-11-06-sequence-start",
    "variables": "2026-11-16-moduletype-traversal",
    "spec-compliance": "2026-11-16-typedef-path",
    "datatype-fields": "2026-11-18-root-scope",
    "moduletype-usage": "2026-11-18-private-visibility",
    "picture-display-paths": "2026-11-18-private-visibility",
}
# The analysis foundation (type graph + typedef/moduletype/datatype indices + symbol skeleton) is
# derived per run from the parsed ASTs and is not persisted: a restored foundation holds symbol
# objects from a different parse than the one the analyzers hold, so identity-based lookups
# silently miss. AST reuse is the supported cold-start saving.

_SINGLE_PATH_CONFIG_KEYS = frozenset({"program_dir", "ABB_lib_dir", "icf_dir"})
_PATH_LIST_CONFIG_KEYS = frozenset({"other_lib_dirs"})


def _canonical_cache_path(raw_value: object) -> str:
    """A path as the cache sees it: expanded, trimmed, and whatever the user meant."""
    text = str(raw_value).strip()
    if not text:
        return ""
    try:
        return str(Path(text).expanduser())
    except (OSError, RuntimeError):
        return text


def _canonical_cache_path_list(raw_value: object) -> list[str]:
    """Path list with duplicates dropped, keeping the first position.

    Order stays significant because the parser searches earlier roots first; a
    repeated root is the only ordering the parser itself folds away.
    """
    if not isinstance(raw_value, (list, tuple)):
        return [_canonical_cache_path(raw_value)]
    paths: list[str] = []
    seen: set[str] = set()
    for raw_path in cast(Sequence[object], raw_value):
        path = _canonical_cache_path(raw_path)
        if not path or path in seen:
            continue
        seen.add(path)
        paths.append(path)
    return paths


def _canonical_cache_value(raw_value: object) -> object:
    """A JSON-encodable value with a stable encoding for types ``repr`` orders badly."""
    if raw_value is None or isinstance(raw_value, (bool, int, float, str)):
        return raw_value
    if isinstance(raw_value, Path):
        return str(raw_value)
    if isinstance(raw_value, Mapping):
        return {
            str(key): _canonical_cache_value(value) for key, value in cast(Mapping[object, object], raw_value).items()
        }
    if isinstance(raw_value, (set, frozenset)):
        return sorted((_canonical_cache_value(item) for item in cast(Iterable[object], raw_value)), key=repr)
    if isinstance(raw_value, (list, tuple)):
        return [_canonical_cache_value(item) for item in cast(Sequence[object], raw_value)]
    return repr(raw_value)


def _cache_key_digest(payload: object) -> str:
    """Hash a key payload: JSON with sorted object keys and no incidental spacing."""
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=repr)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def compute_cache_key(cfg: Mapping[str, object], *, analysis_target: str | None = None) -> str:
    """
    Fast cache key based only on configuration.
    File changes are handled by manifest validation.
    """
    payload: dict[str, object] = {
        "schema": CACHE_KEY_SCHEMA_VERSION,
        "parser": parser_api.PARSER_VERSION,
        "target": str(analysis_target).strip() if analysis_target is not None else None,
    }
    for key in PROJECT_CACHE_CONFIG_KEYS:
        raw_value = cfg.get(key)
        if key in _SINGLE_PATH_CONFIG_KEYS:
            payload[key] = _canonical_cache_path(raw_value)
        elif key in _PATH_LIST_CONFIG_KEYS:
            payload[key] = _canonical_cache_path_list(raw_value)
        elif key == "mode":
            # The loader accepts the mode case-insensitively, so the key must too.
            payload[key] = str(raw_value or "").strip().casefold()
        else:
            payload[key] = _canonical_cache_value(raw_value)
    return _cache_key_digest(payload)


def compute_analysis_report_cache_key(
    project_cache_key: str,
    analyzer_key: str,
    *,
    analysis_settings: object = None,
) -> str:
    """Derive the per-analyzer report cache key.

    Analyzer knobs under ``analysis`` change findings without changing the
    parsed project, so they are part of the key. The settings are serialized in
    a stable form; non-JSON values fall back to ``repr`` so an unrepresentable
    value still invalidates the cache instead of silently sharing an entry.
    """
    payload: dict[str, object] = {
        "schema": CACHE_KEY_SCHEMA_VERSION,
        "parser": parser_api.PARSER_VERSION,
        "project": project_cache_key,
        "analyzer": analyzer_key,
        "analyzer_version": _ANALYSIS_REPORT_ANALYZER_VERSIONS.get(analyzer_key),
        "settings": _analysis_settings_fingerprint(analysis_settings),
    }
    return _cache_key_digest(payload)


def _analysis_settings_fingerprint(analysis_settings: object) -> str:
    if analysis_settings is None:
        return ""
    try:
        return json.dumps(analysis_settings, sort_keys=True, default=repr, separators=(",", ":"))
    except (TypeError, ValueError):
        return repr(analysis_settings)
