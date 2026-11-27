# pyright: reportPrivateUsage=false
"""The cache keeps its working set and drops what it can never read again."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest

from sattlint import cache as cache_module
from sattlint.cache.classes import AnalysisReportCache, ASTCache


def _write_payload(cache_dir: Path, stem: str, size: int = 16) -> tuple[Path, Path]:
    payload = cache_dir / f"{stem}.pickle"
    payload.write_bytes(b"x" * size)
    manifest = cache_dir / f"{stem}.manifest.json"
    manifest.write_text(json.dumps({}), encoding="utf-8")
    return payload, manifest


def _age(path: Path, *, days: float) -> None:
    timestamp = time.time() - days * 24 * 60 * 60
    os.utime(path, (timestamp, timestamp))


def test_entries_used_recently_survive_the_budget(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(cache_module, "CACHE_PAYLOAD_BUDGET_BYTES", 100)
    cache = ASTCache(tmp_path)
    recent, recent_manifest = _write_payload(tmp_path, "recent", 80)
    aged, _aged_manifest = _write_payload(tmp_path, "aged", 80)
    _age(aged, days=2)

    removed = cache.prune_over_budget_entries()

    assert removed.ast_payload_entries == 0
    assert recent.exists()
    assert recent_manifest.exists()


def test_older_entries_are_dropped_until_the_family_fits(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(cache_module, "CACHE_PAYLOAD_BUDGET_BYTES", 100)
    monkeypatch.setattr(cache_module, "CACHE_EVICTION_MIN_AGE_SECONDS", 24 * 60 * 60)
    cache = ASTCache(tmp_path)
    old, old_manifest = _write_payload(tmp_path, "old", 80)
    kept, _kept_manifest = _write_payload(tmp_path, "kept", 80)
    _age(old, days=30)
    _age(old_manifest, days=30)
    _age(kept, days=15)

    removed = cache.prune_over_budget_entries()

    assert removed.ast_payload_entries == 1
    assert removed.ast_manifest_entries == 1
    assert not old.exists()
    assert not old_manifest.exists()
    assert kept.exists()


def test_a_cache_within_budget_is_untouched(tmp_path: Path) -> None:
    cache = ASTCache(tmp_path)
    first, _first_manifest = _write_payload(tmp_path, "first", 8)
    second, _second_manifest = _write_payload(tmp_path, "second", 8)

    removed = cache.prune_over_budget_entries()

    assert removed.removed_entries == 0
    assert first.exists()
    assert second.exists()


def test_a_payload_written_before_the_versioned_layout_is_removed(tmp_path: Path) -> None:
    root = tmp_path / "analysis_reports"
    root.mkdir()
    stray = root / "stray.pickle"
    stray.write_bytes(b"x")

    cache = AnalysisReportCache(tmp_path)

    assert not stray.exists()
    assert cache.cache_dir.is_dir()


def test_the_current_generation_is_kept(tmp_path: Path) -> None:
    cache = AnalysisReportCache(tmp_path)
    kept = cache.cache_dir / "kept.pickle"
    kept.write_bytes(b"x")

    AnalysisReportCache(tmp_path)

    assert kept.exists()
