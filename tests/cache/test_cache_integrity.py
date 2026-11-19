# pyright: reportPrivateUsage=false
"""Cache artifacts must stay trustworthy across a failed write and in storage."""

from __future__ import annotations

import stat
from pathlib import Path

import pytest

from sattlint import cache as cache_module
from sattlint.cache.classes import AnalysisReportCache, ASTCache, FoundationCache
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
    foundation_cache = FoundationCache(tmp_path / "caches")
    foundation_cache.save("key", {"foundation": True})

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
