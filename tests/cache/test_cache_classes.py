# pyright: reportPrivateUsage=false
"""Focused tests for the cache class implementations."""

from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest

from sattlint import cache as cache_module
from sattlint.cache.classes import AnalysisReportCache, ASTCache


def test_analyzer_version_bump_only_invalidates_that_analyzer(monkeypatch: pytest.MonkeyPatch) -> None:
    baseline = cache_module.compute_analysis_report_cache_key("project", "variables")
    unrelated = cache_module.compute_analysis_report_cache_key("project", "same-cycle")

    monkeypatch.setitem(cache_module._ANALYSIS_REPORT_ANALYZER_VERSIONS, "variables", "test-bump")

    assert cache_module.compute_analysis_report_cache_key("project", "variables") != baseline
    assert cache_module.compute_analysis_report_cache_key("project", "same-cycle") == unrelated


def test_ast_cache_save_load_and_validate(tmp_path: Path) -> None:
    source = tmp_path / "mod.sl"
    source.write_text("x := 1;")
    cache = ASTCache(tmp_path / "caches")
    assert cache.load("key") is None
    assert cache.has_cache_artifact("key") is False
    cache.save("key", project={"proj": True}, files=[source])
    assert cache.has_payload("key") is True
    assert cache.has_manifest("key") is True
    assert cache.has_cache_artifact("key") is True
    assert cache.manifest_paths("key") == {source}
    payload = cast("dict[str, object] | None", cache.load("key"))
    assert payload is not None and payload.get("project") == {"proj": True}
    validated = cast("dict[str, object] | None", cache.load_validated("key"))
    assert validated is not None and validated.get("version") == cache_module.CACHE_VERSION
    assert cache.load_manifest("nope") is None
    assert cache.has_manifest("nope") is False
    assert cache.manifest_paths("nope") == frozenset()
    assert cache.load_validated("nope") is None
    cache.clear("key")
    assert cache.has_cache_artifact("key") is False


def test_ast_cache_save_with_missing_file_writes_nothing(tmp_path: Path) -> None:
    cache = ASTCache(tmp_path / "caches")
    cache.save("key", project={"proj": True}, files=[tmp_path / "missing.sl"])
    assert cache.has_cache_artifact("key") is False


def test_ast_cache_prune_orphan_artifacts(tmp_path: Path) -> None:
    cache = ASTCache(tmp_path / "caches")
    (cache.cache_dir / "orphan.pickle").write_text("junk")
    (cache.cache_dir / "stray.manifest.json").write_text("{}")
    result = cache.prune_startup_entries()
    assert result.ast_payload_entries == 1
    assert result.ast_manifest_entries == 1
    assert not (cache.cache_dir / "stray.manifest.json").exists()
    empty = cache.prune_startup_entries()
    assert empty.ast_payload_entries == 0
    assert empty.ast_manifest_entries == 0


def test_ast_cache_prune_stale_entries_validates_payloads(tmp_path: Path) -> None:
    source = tmp_path / "mod.sl"
    source.write_text("x := 1;")
    cache = ASTCache(tmp_path / "caches")
    cache.save("key", project={"proj": True}, files=[source])
    assert cache.prune_stale_entries().ast_payload_entries == 0
    (tmp_path / "caches" / "bad.pickle").write_text("junk")
    result = cache.prune_stale_entries()
    assert result.ast_payload_entries == 1
    assert cache.has_cache_artifact("key") is True


def test_ast_cache_drain_startup_prune_result(tmp_path: Path) -> None:
    cache = ASTCache(tmp_path / "caches")
    result = cache.drain_startup_prune_result()
    assert result.ast_payload_entries == 0
    assert result.ast_manifest_entries == 0


def test_analysis_report_cache_roundtrip(tmp_path: Path) -> None:
    source = tmp_path / "mod.sl"
    source.write_text("x := 1;")
    cache = AnalysisReportCache(tmp_path / "caches")
    assert cache.save("key", report={"report": True}, files=[source]) is True
    payload = cast("dict[str, object] | None", cache.load("key"))
    assert payload is not None and payload.get("report") == {"report": True}
    assert cache.validate(payload) is True
    assert cache.validate(payload, fast=True) is True
    assert cache.validate({"version": "wrong"}) is False
    assert cache.validate({"version": cache_module.ANALYSIS_REPORT_CACHE_VERSION}) is False
    assert cache.load("missing") is None


def test_analysis_report_cache_save_failure_and_clear(tmp_path: Path) -> None:
    cache = AnalysisReportCache(tmp_path / "caches")
    assert cache.save("key", report={"report": True}, files=[tmp_path / "missing.sl"]) is False
    source = tmp_path / "mod.sl"
    source.write_text("x := 1;")
    cache.save("key", report={"report": True}, files=[source])
    cache.save("key2", report={"report": True}, files=[source])
    assert cache.clear_all() == 2
    cache.save("key3", report={"report": True}, files=[source])
    cache.clear("key3")
    assert cache.load("key3") is None


def test_analysis_report_cache_prune_and_drain(tmp_path: Path) -> None:
    source = tmp_path / "mod.sl"
    source.write_text("x := 1;")
    cache = AnalysisReportCache(tmp_path / "caches")
    cache.save("key", report={"report": True}, files=[source])
    assert cache.prune_stale_entries() == 0
    for path in cache.cache_dir.glob("*.pickle"):
        path.write_text("junk")
    assert cache.prune_stale_entries() == 1
    assert cache.drain_startup_pruned_entries() >= 0


def test_analysis_report_cache_key_tracks_analyzer_settings() -> None:
    baseline = cache_module.compute_analysis_report_cache_key(
        "proj-key",
        "cyclomatic-complexity",
        analysis_settings={"cyclomatic_module_threshold": 10},
    )

    assert baseline == cache_module.compute_analysis_report_cache_key(
        "proj-key",
        "cyclomatic-complexity",
        analysis_settings={"cyclomatic_module_threshold": 10},
    )
    assert baseline != cache_module.compute_analysis_report_cache_key(
        "proj-key",
        "cyclomatic-complexity",
        analysis_settings={"cyclomatic_module_threshold": 20},
    )


def test_report_cache_removes_entries_from_another_generation(tmp_path: Path) -> None:
    root = tmp_path / "caches" / "analysis_reports"
    stale = root / "v0-p0.0.1"
    stale.mkdir(parents=True)
    (stale / "entry.pickle").write_bytes(b"stale")

    cache = AnalysisReportCache(tmp_path / "caches")

    assert cache.cache_dir.is_dir()
    assert not stale.exists()
    assert cache.drain_startup_pruned_entries() == 1
