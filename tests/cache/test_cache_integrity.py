# pyright: reportPrivateUsage=false
"""Cache artifacts must stay trustworthy across a failed write and in storage."""

from __future__ import annotations

import json
import os
import stat
import subprocess
import time
from pathlib import Path

import pytest

from sattlint import cache as cache_module
from sattlint.cache.classes import AnalysisReportCache, ASTCache
from sattlint.cache.manager import _CACHE_MANAGER_LIMIT, _CACHE_MANAGERS, get_cache_manager
from sattlint.runs import RunRecord, save_run


class _CraftedCall:
    """A pickle that asks the unpickler to call *function* with *arguments*."""

    def __init__(self, function: object, arguments: tuple[object, ...]) -> None:
        self._function = function
        self._arguments = arguments

    def __reduce__(self) -> tuple[object, tuple[object, ...]]:
        return (self._function, self._arguments)


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


def test_a_plain_manifest_with_the_current_shape_is_not_trusted(tmp_path: Path) -> None:
    """Writing the manifest directory is not enough to control the next read.

    The body below is exactly what a legitimate manifest holds. Without the
    HMAC that matches it, it must be a miss, not a load.
    """
    source = _source(tmp_path)
    stat_result = source.stat()
    cache = ASTCache(tmp_path / "caches")
    cache.save("key", project={"generation": 1}, files=[source])

    manifest_path = cache.cache_dir / "key.manifest.json"
    manifest_path.write_text(
        json.dumps({str(source): [stat_result.st_mtime_ns, stat_result.st_size, "0" * 64]}),
        encoding="utf-8",
    )

    assert cache.load_manifest("key") is None
    assert cache.load_validated("key") is None


def _split_signed_manifest(path: Path) -> tuple[bytes, bytes, bytes]:
    raw_bytes = path.read_bytes()
    magic = cache_module._MANIFEST_CACHE_MAGIC
    assert raw_bytes.startswith(magic)
    signature, _separator, body = raw_bytes[len(magic) :].partition(b"\n")
    return magic, signature, body


def test_a_manifest_with_a_tampered_signature_is_rejected(tmp_path: Path) -> None:
    source = _source(tmp_path)
    cache = ASTCache(tmp_path / "caches")
    cache.save("key", project={"generation": 1}, files=[source])
    manifest_path = cache.cache_dir / "key.manifest.json"
    magic, signature, body = _split_signed_manifest(manifest_path)

    manifest_path.write_bytes(magic + b"0" * len(signature) + b"\n" + body)
    assert cache.load_manifest("key") is None

    manifest_path.write_bytes(magic + b"short\n" + body)
    assert cache.load_manifest("key") is None


def test_a_manifest_with_a_tampered_body_is_rejected(tmp_path: Path) -> None:
    source = _source(tmp_path)
    cache = ASTCache(tmp_path / "caches")
    cache.save("key", project={"generation": 1}, files=[source])
    manifest_path = cache.cache_dir / "key.manifest.json"
    magic, signature, body = _split_signed_manifest(manifest_path)
    rewritten = json.loads(body)
    rewritten[str(source)] = [0, 0, "f" * 64]

    manifest_path.write_bytes(magic + signature + b"\n" + json.dumps(rewritten).encode("utf-8"))

    assert cache.load_manifest("key") is None
    assert cache.load_validated("key") is None


def test_a_signed_manifest_still_loads_and_validates(tmp_path: Path) -> None:
    source = _source(tmp_path)
    cache = ASTCache(tmp_path / "caches")
    cache.save("key", project={"generation": 1}, files=[source])

    manifest = cache.load_manifest("key")

    assert manifest is not None
    assert set(manifest) == {str(source)}
    assert cache.has_manifest("key") is True
    assert cache.load_validated("key") is not None


@pytest.mark.skipif(os.name != "posix", reason="creating a symlink needs POSIX semantics")
def test_a_symlinked_signing_key_is_not_trusted(tmp_path: Path) -> None:
    key_path = cache_module._pickle_hmac_key_path()
    target = tmp_path / "elsewhere.key"
    target.write_bytes(b"k" * cache_module._PICKLE_HMAC_SIZE)
    target.chmod(0o600)
    key_path.symlink_to(target)

    assert cache_module._read_pickle_hmac_key(key_path) is None

    replacement = cache_module._load_or_create_pickle_hmac_key()

    assert replacement is not None
    assert replacement != target.read_bytes()
    # The link itself is replaced; its target keeps its bytes.
    assert key_path.is_symlink() is False
    assert stat.S_IMODE(key_path.stat().st_mode) == 0o600
    assert target.read_bytes() == b"k" * cache_module._PICKLE_HMAC_SIZE


@pytest.mark.skipif(os.name != "posix", reason="POSIX permission bits do not exist here")
@pytest.mark.parametrize("mode", [0o644, 0o666])
def test_a_key_with_group_or_other_permissions_is_not_trusted(tmp_path: Path, mode: int) -> None:
    key_path = cache_module._pickle_hmac_key_path()
    key_path.write_bytes(b"k" * cache_module._PICKLE_HMAC_SIZE)
    key_path.chmod(mode)

    assert cache_module._read_pickle_hmac_key(key_path) is None

    replacement = cache_module._load_or_create_pickle_hmac_key()

    assert replacement is not None
    assert stat.S_IMODE(key_path.stat().st_mode) == 0o600


@pytest.mark.skipif(os.name != "posix", reason="POSIX file ownership does not exist here")
def test_a_key_owned_by_another_user_is_not_trusted(tmp_path: Path) -> None:
    key_path = cache_module._pickle_hmac_key_path()
    key_path.write_bytes(b"k" * cache_module._PICKLE_HMAC_SIZE)
    key_path.chmod(0o600)
    other_uid = 1 if os.getuid() == 0 else 0
    try:
        os.chown(key_path, other_uid, -1)
    except OSError:
        pytest.skip("changing the key owner needs a privilege this platform does not grant")

    assert cache_module._read_pickle_hmac_key(key_path) is None


@pytest.mark.skipif(os.name != "posix", reason="POSIX permission bits do not exist here")
def test_an_untrusted_key_turns_an_existing_entry_into_a_miss(tmp_path: Path) -> None:
    source = _source(tmp_path)
    cache = ASTCache(tmp_path / "caches")
    cache.save("key", project={"generation": 1}, files=[source])
    assert cache.load_validated("key") is not None

    cache_module._pickle_hmac_key_path().chmod(0o644)

    assert cache.load("key") is None
    assert cache.load_validated("key") is None


def test_a_crafted_pickle_cannot_reach_a_process_launch(tmp_path: Path) -> None:
    marker = tmp_path / "executed"
    crafted = [
        (os.system, (f"touch {marker}",)),  # pyright: ignore[reportDeprecated]  # blocked by the unpickler, never called
        (subprocess.Popen, (["touch", str(marker)],)),
        (eval, ('open("executed", "w")',)),
    ]
    payload_path = tmp_path / "crafted.pickle"

    for function, arguments in crafted:
        cache_module._save_pickle_payload(payload_path, _CraftedCall(function, arguments))

        assert cache_module._load_pickle_payload(payload_path) is None
        assert not marker.exists()


def test_a_save_over_the_budget_prunes_the_oldest_entry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = _source(tmp_path)
    cache = ASTCache(tmp_path / "caches")
    # Learn the new entry's size first, so the budget fits exactly one entry.
    cache.save("probe", project={"generation": 1}, files=[source])
    new_size = (cache.cache_dir / "probe.pickle").stat().st_size
    cache.clear("probe")

    monkeypatch.setattr(cache_module, "CACHE_PAYLOAD_BUDGET_BYTES", new_size + 100)
    monkeypatch.setattr(cache_module, "CACHE_EVICTION_MIN_AGE_SECONDS", 24 * 60 * 60)
    old_payload = cache.cache_dir / "old.pickle"
    old_payload.write_bytes(b"x" * 120)
    old_manifest = cache.cache_dir / "old.manifest.json"
    old_manifest.write_bytes(b"unsigned")
    aged_at = time.time() - 2 * 24 * 60 * 60
    os.utime(old_payload, (aged_at, aged_at))

    cache.save("key", project={"generation": 1}, files=[source])

    assert cache.has_cache_artifact("key") is True
    assert not old_payload.exists()
    assert not old_manifest.exists()
