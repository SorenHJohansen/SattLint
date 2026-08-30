# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportUnknownArgumentType=false, reportMissingParameterType=false, reportAttributeAccessIssue=false
"""Focused tests for the cache class implementations."""

from __future__ import annotations

import json

import pytest

from sattlint import cache as cache_module
from sattlint._cache_classes import (
    AnalysisReportCache,
    ASTCache,
    FileASTCache,
    FileLookupCache,
)


def test_file_lookup_cache_roundtrip(tmp_path) -> None:
    cache = FileLookupCache(tmp_path)
    assert cache.get("picture", "Foo", "strict") is None
    cache.set("picture", "Foo", "strict", base_dir=tmp_path / "lib", ext=".pic")
    entry = cache.get("picture", "foo", "strict")
    assert entry is not None
    assert entry["ext"] == ".pic"
    assert cache.path.exists() is False
    cache.flush()
    assert cache.path.exists()
    reloaded = FileLookupCache(tmp_path)
    assert reloaded.get("picture", "FOO", "strict") == entry


def test_file_lookup_cache_dedupes_and_forgets(tmp_path) -> None:
    cache = FileLookupCache(tmp_path, flush_interval=2)
    cache.set("picture", "A", "mode", base_dir=tmp_path, ext=".pic")
    cache.set("picture", "A", "mode", base_dir=tmp_path, ext=".pic")
    cache.forget("picture", "A", "mode")
    assert cache.get("picture", "A", "mode") is None
    cache.forget("picture", "A", "mode")
    cache.set("picture", "B", "mode", base_dir=tmp_path, ext=".pic")
    cache.set("picture", "C", "mode", base_dir=tmp_path, ext=".pic")
    assert cache.path.exists()


def test_file_lookup_cache_write_through(tmp_path) -> None:
    cache = FileLookupCache(tmp_path, write_through=True)
    cache.set("picture", "A", "mode", base_dir=tmp_path, ext=".pic")
    assert cache.path.exists()


def test_file_lookup_cache_rejects_bad_flush_interval(tmp_path) -> None:
    with pytest.raises(ValueError):
        FileLookupCache(tmp_path, flush_interval=0)


def test_file_lookup_cache_prune_and_drain(tmp_path) -> None:
    assert FileLookupCache(tmp_path).prune_stale_entries() == 0
    cache = FileLookupCache(tmp_path, flush_interval=None)
    cache.set("picture", "A", "mode", base_dir=tmp_path, ext=".pic")
    cache.flush()
    assert cache.prune_stale_entries() == 0
    with cache.path.open("w", encoding="utf-8") as handle:
        handle.write("not json")
    assert cache.prune_stale_entries() == 1
    assert not cache.path.exists()


def test_file_lookup_cache_ignores_foreign_version(tmp_path) -> None:
    cache = FileLookupCache(tmp_path)
    cache.set("picture", "A", "mode", base_dir=tmp_path, ext=".pic")
    cache.flush()
    with cache.path.open("w", encoding="utf-8") as handle:
        json.dump({"version": "wrong", "entries": {}}, handle)
    reloaded = FileLookupCache(tmp_path)
    assert reloaded.get("picture", "a", "mode") is None


def test_file_ast_cache_roundtrip_and_invalidation(tmp_path) -> None:
    source = tmp_path / "mod.sl"
    source.write_text("x := 1;")
    cache = FileASTCache(tmp_path / "caches")
    cache.save(source, "full", {"ast": "payload"})
    assert cache.load(source, "full") == {"ast": "payload"}
    assert cache.load(source, "fast") is None
    assert cache.load(tmp_path / "missing.sl", "full") is None
    cache.save(source, "full", {"ast": "payload2"})
    assert cache.load(source, "full") == {"ast": "payload2"}
    assert cache.drain_startup_pruned_entries() >= 0


def test_file_ast_cache_prune_stale_entries(tmp_path) -> None:
    source = tmp_path / "mod.sl"
    source.write_text("x := 1;")
    cache = FileASTCache(tmp_path / "caches")
    cache.save(source, "full", {"ast": "payload"})
    assert cache.prune_stale_entries() == 0
    for path in cache.cache_dir.glob("*.pickle"):
        path.write_text("not a pickle")
    assert cache.prune_stale_entries() == 1


def test_ast_cache_save_load_and_validate(tmp_path) -> None:
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
    payload = cache.load("key")
    assert payload is not None and payload.get("project") == {"proj": True}
    validated = cache.load_validated("key")
    assert validated is not None and validated.get("version") == cache_module.CACHE_VERSION
    assert cache.load_manifest("nope") is None
    assert cache.has_manifest("nope") is False
    assert cache.manifest_paths("nope") == frozenset()
    assert cache.load_validated("nope") is None
    cache.clear("key")
    assert cache.has_cache_artifact("key") is False


def test_ast_cache_save_with_missing_file_writes_nothing(tmp_path) -> None:
    cache = ASTCache(tmp_path / "caches")
    cache.save("key", project={"proj": True}, files=[tmp_path / "missing.sl"])
    assert cache.has_cache_artifact("key") is False


def test_ast_cache_prune_orphan_artifacts(tmp_path) -> None:
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


def test_ast_cache_prune_stale_entries_validates_payloads(tmp_path) -> None:
    source = tmp_path / "mod.sl"
    source.write_text("x := 1;")
    cache = ASTCache(tmp_path / "caches")
    cache.save("key", project={"proj": True}, files=[source])
    assert cache.prune_stale_entries().ast_payload_entries == 0
    (tmp_path / "caches" / "bad.pickle").write_text("junk")
    result = cache.prune_stale_entries()
    assert result.ast_payload_entries == 1
    assert cache.has_cache_artifact("key") is True


def test_ast_cache_drain_startup_prune_result(tmp_path) -> None:
    cache = ASTCache(tmp_path / "caches")
    result = cache.drain_startup_prune_result()
    assert result.ast_payload_entries == 0
    assert result.ast_manifest_entries == 0


def test_analysis_report_cache_roundtrip(tmp_path) -> None:
    source = tmp_path / "mod.sl"
    source.write_text("x := 1;")
    cache = AnalysisReportCache(tmp_path / "caches")
    assert cache.save("key", report={"report": True}, files=[source]) is True
    payload = cache.load("key")
    assert payload is not None and payload.get("report") == {"report": True}
    assert cache.validate(payload) is True
    assert cache.validate(payload, fast=True) is True
    assert cache.validate({"version": "wrong"}) is False
    assert cache.validate({"version": cache_module.ANALYSIS_REPORT_CACHE_VERSION}) is False
    assert cache.load("missing") is None


def test_analysis_report_cache_save_failure_and_clear(tmp_path) -> None:
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


def test_analysis_report_cache_prune_and_drain(tmp_path) -> None:
    source = tmp_path / "mod.sl"
    source.write_text("x := 1;")
    cache = AnalysisReportCache(tmp_path / "caches")
    cache.save("key", report={"report": True}, files=[source])
    assert cache.prune_stale_entries() == 0
    for path in cache.cache_dir.glob("*.pickle"):
        path.write_text("junk")
    assert cache.prune_stale_entries() == 1
    assert cache.drain_startup_pruned_entries() >= 0
