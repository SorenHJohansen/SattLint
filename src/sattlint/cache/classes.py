# pyright: reportPrivateUsage=false
"""Cache class implementations shared by sattlint.cache."""

from __future__ import annotations

import pickle
import time
from collections.abc import Iterable
from contextlib import suppress
from pathlib import Path

from .. import cache as cache_module
from ..parser_api import PARSER_VERSION


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

        # The payload is the data; the manifest is what makes it trusted. Write
        # the payload first, so a failed write leaves the previous manifest
        # paired with the previous payload instead of blessing a stale one.
        cache_module._save_pickle_payload(self._path(key), payload)
        cache_module._save_manifest_payload(self._manifest_path(key), manifest)

    def load_validated(self, key: str) -> object | None:
        manifest = self.load_manifest(key)
        if manifest is None:
            return None

        # Validate the file snapshot before unpickling: a stale entry must not
        # pay the deserialization cost only to be thrown away.
        if not cache_module._validate_manifest(manifest):
            return None

        return self.load(key)

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

    def prune_over_budget_entries(self, *, now: float | None = None) -> cache_module.CachePruneResult:
        """Drop the least recently used entries once the family exceeds its budget."""
        payload_paths = sorted(self.cache_dir.glob("*.pickle"))
        over_budget = cache_module.payloads_over_budget(
            payload_paths,
            time.time() if now is None else now,
        )
        removed_payloads = 0
        removed_manifests = 0
        for payload_path in over_budget:
            if not cache_module._remove_file(payload_path):
                continue
            removed_payloads += 1
            manifest_path = self._manifest_path(payload_path.stem)
            if manifest_path.exists() and cache_module._remove_file(manifest_path):
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
        # A concurrent pruner may remove either file first; clearing is
        # best-effort and must not raise into the caller's action.
        cache_module._remove_file(self._path(key))
        cache_module._remove_file(self._manifest_path(key))


class AnalysisReportCache:
    def __init__(self, cache_dir: Path):
        self._root_dir = cache_dir / "analysis_reports"
        self.cache_dir = self._root_dir / f"v{cache_module.ANALYSIS_REPORT_CACHE_VERSION}-p{PARSER_VERSION}"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        # An entry is only valid for the schema version and parser release
        # that wrote it, and the key path carries both. Entries from another
        # generation are never read again, so they are removed here rather
        # than validated one by one on every construction.
        self._startup_pruned_entries = self._prune_other_generations()

    def _prune_other_generations(self) -> int:
        removed = 0
        for path in self._root_dir.iterdir():
            if not path.is_dir():
                # Only a versioned directory is ever read, so a payload written
                # directly under the root by an older layout is unreachable.
                if path.is_file() and cache_module._remove_file(path):
                    removed += 1
                continue
            if path == self.cache_dir:
                continue
            for entry in path.iterdir():
                if entry.is_file() and cache_module._remove_file(entry):
                    removed += 1
            with suppress(OSError):
                path.rmdir()
        return removed

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
        cache_module._remove_file(self._path(key))

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
