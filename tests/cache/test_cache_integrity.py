# pyright: reportPrivateUsage=false
"""Cache artifacts must stay trustworthy across a failed write and in storage."""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path

import pytest

from sattlint import cache as cache_module
from sattlint.cache.classes import AnalysisReportCache, ASTCache
from sattlint.cache.manager import _CACHE_MANAGER_LIMIT, _CACHE_MANAGERS, get_cache_manager
from sattlint.runs import RunRecord, save_run


def _mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def _source(tmp_path: Path) -> Path:
    source = tmp_path / "mod.sl"
    source.write_text("x := 1;", encoding="utf-8")
    return source


def test_ast_cache_keeps_the_previous_manifest_when_the_payload_write_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = _source(tmp_path)
    cache = ASTCache(tmp_path / "caches")
    cache.save("key", project={"generation": 1}, files=[source])
    original_manifest = cache.load_manifest("key")
    assert original_manifest is not None

    def fail_payload_write(*_args: object, **_kwargs: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(cache_module, "_save_pickle_payload", fail_payload_write)
    source.write_text("changed contents", encoding="utf-8")

    with pytest.raises(OSError):
        cache.save("key", project={"generation": 2}, files=[source])

    # A fresh manifest over a stale payload would validate the old graph
    # against the new file state, so the manifest must not move at all.
    assert cache.load_manifest("key") == original_manifest


def test_cache_artifacts_are_owner_only(tmp_path: Path) -> None:
    source = _source(tmp_path)
    ast_cache = ASTCache(tmp_path / "caches")
    ast_cache.save("key", project={"generation": 1}, files=[source])
    report_cache = AnalysisReportCache(tmp_path / "caches")
    assert report_cache.save("key", report={"report": True}, files=[source]) is True

    artifacts = sorted(path for path in (tmp_path / "caches").rglob("*") if path.is_file())
    assert artifacts
    assert {_mode(path) for path in artifacts} == {0o600}
    assert _mode(cache_module._pickle_hmac_key_path()) == 0o600


def test_run_records_are_owner_only(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    record = RunRecord(
        run_id="", started_at="2026-01-01T00:00:00Z", finished_at="2026-01-01T00:00:01Z", project_tag="demo"
    )
    stored = save_run(record, runs_dir=runs_dir)

    artifacts = sorted(path for path in runs_dir.iterdir() if path.is_file())
    assert artifacts
    assert stored.run_id
    assert {_mode(path) for path in artifacts} == {0o600}


def test_signing_key_lives_outside_the_cache_tree(tmp_path: Path) -> None:
    source = _source(tmp_path)
    ASTCache(tmp_path / "caches").save("key", project={"generation": 1}, files=[source])

    cache_root = cache_module.cache_dir_location()
    key_path = cache_module._pickle_hmac_key_path()

    assert key_path.parent != cache_root
    assert cache_root not in key_path.parents
    assert key_path.exists()


def test_reading_a_cache_does_not_create_the_signing_key(tmp_path: Path) -> None:
    key_path = cache_module._pickle_hmac_key_path()
    assert not key_path.exists()

    cache = ASTCache(tmp_path / "caches")
    assert cache.load("missing") is None

    assert not key_path.exists()


def test_ast_cache_validates_the_manifest_before_unpickling(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = _source(tmp_path)
    cache = ASTCache(tmp_path / "caches")
    cache.save("key", project={"generation": 1}, files=[source])

    def fail_load(_key: str) -> object:
        raise AssertionError("a stale manifest must not pay the unpickle cost")

    cache.load = fail_load  # type: ignore[method-assign]
    source.write_text("a longer body", encoding="utf-8")

    assert cache.load_validated("key") is None


def test_ast_cache_does_not_store_an_entry_without_files(tmp_path: Path) -> None:
    cache = ASTCache(tmp_path / "caches")

    cache.save("key", project={"generation": 1}, files=[])

    assert cache.has_payload("key") is False
    assert cache.has_manifest("key") is False


def test_ast_cache_clear_tolerates_missing_artifacts(tmp_path: Path) -> None:
    cache = ASTCache(tmp_path / "caches")

    cache.clear("never-written")

    source = _source(tmp_path)
    cache.save("key", project={"generation": 1}, files=[source])
    cache.clear("key")
    cache.clear("key")

    assert cache.has_cache_artifact("key") is False


def test_cache_manager_memo_stays_bounded(tmp_path: Path) -> None:
    _CACHE_MANAGERS.clear()
    for index in range(_CACHE_MANAGER_LIMIT + 3):
        get_cache_manager(tmp_path / f"cache-{index}")

    assert len(_CACHE_MANAGERS) == _CACHE_MANAGER_LIMIT


def test_ast_cache_rejects_a_same_size_edit_that_preserves_the_modification_time(tmp_path: Path) -> None:
    """The digest decides, not the stat snapshot.

    A rewrite that keeps the byte count and restores the exact modification
    instant is invisible to ``(mtime_ns, size)``. The parser proves freshness by
    hashing the bytes, and the graph cache must hold the same line.
    """
    source = _source(tmp_path)
    original_stat = source.stat()
    cache = ASTCache(tmp_path / "caches")
    cache.save("key", project={"generation": 1}, files=[source])
    assert cache.load_validated("key") is not None

    source.write_text("y := 2;", encoding="utf-8")
    assert source.stat().st_size == original_stat.st_size
    os.utime(source, ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns))
    assert source.stat().st_mtime_ns == original_stat.st_mtime_ns

    assert cache.load_validated("key") is None


def test_the_report_cache_rejects_a_same_size_edit_that_preserves_the_modification_time(
    tmp_path: Path,
) -> None:
    source = _source(tmp_path)
    original_stat = source.stat()
    cache = AnalysisReportCache(tmp_path / "caches")
    assert cache.save("key", report={"report": "old"}, files=[source]) is True
    payload = cache.load("key")
    assert payload is not None and cache.validate(payload) is True

    source.write_text("y := 2;", encoding="utf-8")
    os.utime(source, ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns))

    assert cache.validate(payload) is False


def test_a_manifest_from_before_the_content_digest_is_not_trusted(tmp_path: Path) -> None:
    source = _source(tmp_path)
    stat_result = source.stat()
    cache = ASTCache(tmp_path / "caches")
    cache.save("key", project={"generation": 1}, files=[source])

    manifest_path = cache.cache_dir / "key.manifest.json"
    manifest_path.write_text(
        json.dumps({str(source): [stat_result.st_mtime_ns, stat_result.st_size]}),
        encoding="utf-8",
    )

    assert cache.load_manifest("key") is None
    assert cache.load_validated("key") is None
