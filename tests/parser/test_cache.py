# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportPrivateUsage=false, reportGeneralTypeIssues=false
"""Regression tests for AST cache serialization."""

import json
import os
import pickle
from pathlib import Path, PosixPath
from types import SimpleNamespace

import pytest

from sattline_parser.models.ast_model import FloatLiteral, IntLiteral, SourceSpan
from sattlint.cache import (
    ANALYSIS_REPORT_CACHE_VERSION,
    CACHE_VERSION,
    LOOKUP_CACHE_VERSION,
    AnalysisReportCache,
    ASTCache,
    CacheManager,
    CachePruneResult,
    FileASTCache,
    FileLookupCache,
    get_cache_manager,
    prune_cache_dir,
)


def test_int_literal_pickle_round_trip_preserves_span():
    value = IntLiteral(42, SourceSpan(12, 5))
    restored = pickle.loads(pickle.dumps(value, protocol=pickle.HIGHEST_PROTOCOL))

    assert isinstance(restored, IntLiteral)
    assert restored == 42
    assert restored.span == SourceSpan(12, 5)


def test_float_literal_pickle_round_trip_preserves_span():
    value = FloatLiteral(2.5, SourceSpan(20, 7))
    restored = pickle.loads(pickle.dumps(value, protocol=pickle.HIGHEST_PROTOCOL))

    assert isinstance(restored, FloatLiteral)
    assert restored == 2.5
    assert restored.span == SourceSpan(20, 7)


def test_legacy_literal_unpickle_without_span_defaults_to_origin():
    legacy_int = IntLiteral.__new__(IntLiteral, 7)
    legacy_float = FloatLiteral.__new__(FloatLiteral, 3.5)

    assert legacy_int.span is None
    assert legacy_float.span is None


def test_file_lookup_cache_can_batch_save_until_manual_flush(tmp_path: Path) -> None:
    save_calls: list[Path] = []

    class _LookupCache(FileLookupCache):
        def _save(self) -> None:
            save_calls.append(self.path)

    lookup_cache = _LookupCache(tmp_path, flush_interval=None)

    lookup_cache.set("code", "Root", "draft", tmp_path, ".s")
    lookup_cache.set("deps", "Root", "draft", tmp_path, ".l")

    assert save_calls == []

    lookup_cache.flush()

    assert save_calls == [lookup_cache.path]


def test_file_lookup_cache_flushes_periodically_by_mutation_count(tmp_path: Path) -> None:
    save_calls: list[Path] = []

    class _LookupCache(FileLookupCache):
        def _save(self) -> None:
            save_calls.append(self.path)

    lookup_cache = _LookupCache(tmp_path, flush_interval=2)

    lookup_cache.set("code", "Root", "draft", tmp_path, ".s")
    assert save_calls == []

    lookup_cache.set("deps", "Root", "draft", tmp_path, ".l")

    assert save_calls == [lookup_cache.path]
    assert lookup_cache._dirty is False


def test_file_lookup_cache_supports_write_through_mode(tmp_path: Path) -> None:
    save_calls: list[Path] = []

    class _LookupCache(FileLookupCache):
        def _save(self) -> None:
            save_calls.append(self.path)

    lookup_cache = _LookupCache(tmp_path, write_through=True)

    lookup_cache.set("code", "Root", "draft", tmp_path, ".s")
    lookup_cache.forget("code", "Root", "draft")

    assert save_calls == [lookup_cache.path, lookup_cache.path]


def test_cache_helpers_cover_lookup_env_and_validation_edges(tmp_path: Path, monkeypatch) -> None:  # noqa: PLR0915
    import sattlint.cache as cache_mod  # noqa: PLC0415

    assert cache_mod._as_mapping(["not", "a", "mapping"]) is None
    mapping = {"name": "value"}
    assert cache_mod._as_mapping(mapping) is mapping

    windows_base = tmp_path / "WindowsAppData"
    monkeypatch.setattr(cache_mod, "Path", PosixPath)
    monkeypatch.setattr(cache_mod.os, "name", "nt", raising=False)
    monkeypatch.setenv("APPDATA", str(windows_base))
    assert cache_mod.get_cache_dir() == windows_base / "sattlint" / "cache"

    xdg_config_base = tmp_path / "xdg-config"
    xdg_cache_base = tmp_path / "xdg-cache"
    monkeypatch.setattr(cache_mod.os, "name", "posix", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg_config_base))
    monkeypatch.setenv("XDG_CACHE_HOME", str(xdg_cache_base))
    assert cache_mod.get_cache_dir() == xdg_cache_base / "sattlint"

    legacy_cache_dir = xdg_config_base / "sattlint" / "cache"
    legacy_cache_dir.mkdir(parents=True, exist_ok=True)
    legacy_file = legacy_cache_dir / "file_lookup_cache.json"
    legacy_payload = '{"version": 1, "entries": {}}'
    legacy_file.write_text(legacy_payload, encoding="utf-8")
    migrated_cache_dir = cache_mod.get_cache_dir()
    assert migrated_cache_dir == xdg_cache_base / "sattlint"
    assert (migrated_cache_dir / "file_lookup_cache.json").read_text(encoding="utf-8") == legacy_payload
    assert not legacy_file.exists()

    lookup_dir = tmp_path / "lookup"
    lookup_dir.mkdir()
    lookup_path = lookup_dir / "file_lookup_cache.json"
    lookup_path.write_text("{bad json", encoding="utf-8")
    lookup_cache = FileLookupCache(lookup_dir)
    assert lookup_cache.get("code", "Root", "draft") is None

    lookup_path.write_text(json.dumps({"version": LOOKUP_CACHE_VERSION + 1, "entries": {}}), encoding="utf-8")
    lookup_cache = FileLookupCache(lookup_dir)
    assert lookup_cache.get("code", "Root", "draft") is None

    lookup_path.write_text(json.dumps({"version": LOOKUP_CACHE_VERSION, "entries": []}), encoding="utf-8")
    lookup_cache = FileLookupCache(lookup_dir)
    assert lookup_cache.get("code", "Root", "draft") is None

    lookup_cache._data["entries"] = {"code:draft:root": "bad-entry"}
    assert lookup_cache.get("code", "Root", "draft") is None
    lookup_cache._data["entries"] = {"code:draft:root": {"base_dir": 3, "ext": None}}
    assert lookup_cache.get("code", "Root", "draft") is None

    lookup_cache.set("code", "Root", "draft", tmp_path, ".s")
    assert lookup_cache.get("code", "Root", "draft") == {"base_dir": str(tmp_path), "ext": ".s"}
    lookup_cache.forget("code", "Root", "draft")
    assert lookup_cache.get("code", "Root", "draft") is None

    source_path = tmp_path / "Program" / "Main.s"
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_text('"a"\n"b"\n"c"\n', encoding="utf-8")
    file_ast_cache = FileASTCache(tmp_path)
    cache_file = file_ast_cache._path(source_path, "draft")

    assert file_ast_cache.load(source_path, "draft") is None
    cache_file.write_bytes(b"not-a-pickle")
    assert file_ast_cache.load(source_path, "draft") is None

    bad_payloads = [
        {"version": CACHE_VERSION, "meta": None, "ast": "value"},
        {
            "version": CACHE_VERSION,
            "meta": {"path": "wrong", "mode": "draft", "mtime_ns": 0, "size": 0},
            "ast": "value",
        },
        {
            "version": CACHE_VERSION,
            "meta": {"path": str(source_path), "mode": "official", "mtime_ns": 0, "size": 0},
            "ast": "value",
        },
    ]
    for payload in bad_payloads:
        with cache_file.open("wb") as handle:
            pickle.dump(payload, handle, protocol=pickle.HIGHEST_PROTOCOL)
        assert file_ast_cache.load(source_path, "draft") is None

    missing_source = tmp_path / "Program" / "Missing.s"
    with cache_file.open("wb") as handle:
        pickle.dump(
            {
                "version": CACHE_VERSION,
                "meta": {"path": str(missing_source), "mode": "draft", "mtime_ns": 0, "size": 0},
                "ast": "value",
            },
            handle,
            protocol=pickle.HIGHEST_PROTOCOL,
        )
    assert file_ast_cache.load(missing_source, "draft") is None

    file_ast_cache.save(source_path, "draft", {"ast": "value"})
    assert file_ast_cache.load(source_path, "draft") == {"ast": "value"}
    source_path.write_text('"a"\n"b"\n"changed"\n', encoding="utf-8")
    assert file_ast_cache.load(source_path, "draft") is None

    ast_cache = ASTCache(tmp_path / "project-cache")
    project_key = "project"
    assert ast_cache.load(project_key) is None
    ast_cache._path(project_key).write_bytes(b"bad-pickle")
    assert ast_cache.load(project_key) is None
    assert ast_cache.has_payload(project_key) is True
    assert ast_cache.has_manifest(project_key) is False

    manifest_path = tmp_path / "manifest.s"
    manifest_path.write_text('"x"\n"y"\n"z"\n', encoding="utf-8")
    manifest = {str(manifest_path): (manifest_path.stat().st_mtime_ns, manifest_path.stat().st_size)}
    ast_cache._manifest_path(project_key).write_text("[]", encoding="utf-8")
    assert ast_cache.has_manifest(project_key) is False
    ast_cache._manifest_path(project_key).write_text(json.dumps({"version": CACHE_VERSION}), encoding="utf-8")
    assert ast_cache.has_manifest(project_key) is False
    ast_cache._manifest_path(project_key).write_text(
        json.dumps({"version": CACHE_VERSION, "files": {str(manifest_path): ["bad", 2]}}),
        encoding="utf-8",
    )
    assert ast_cache.has_manifest(project_key) is False

    ast_cache.save(project_key, project=SimpleNamespace(name="project"), files=[manifest_path])
    payload = ast_cache.load(project_key)
    assert payload is not None
    assert payload == {"version": CACHE_VERSION, "project": SimpleNamespace(name="project")}
    assert ast_cache.has_payload(project_key) is True
    assert ast_cache.has_manifest(project_key) is True
    assert ast_cache.has_cache_artifact(project_key) is True
    assert ast_cache.load_manifest(project_key) == manifest
    assert ast_cache.manifest_paths(project_key) == frozenset({manifest_path})
    assert ast_cache.load_validated(project_key) == payload
    manifest_path.unlink()
    assert ast_cache.load_validated(project_key) is None
    ast_cache.clear(project_key)
    assert not ast_cache._path(project_key).exists()
    assert not ast_cache._manifest_path(project_key).exists()


def test_cache_helpers_cover_persistence_and_hash_edge_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:  # noqa: PLR0915
    import sattlint.cache as cache_mod  # noqa: PLC0415

    lookup_cache = FileLookupCache(tmp_path / "lookup-persist")
    lookup_cache.set("code", "Root", "draft", tmp_path, ".s")
    lookup_cache.flush()
    persisted = json.loads(lookup_cache.path.read_text(encoding="utf-8"))
    assert persisted["entries"]["code:draft:root"] == {"base_dir": str(tmp_path), "ext": ".s"}

    reloaded = FileLookupCache(lookup_cache.cache_dir)
    assert reloaded.get("code", "Root", "draft") == {"base_dir": str(tmp_path), "ext": ".s"}

    reloaded._data["entries"] = []
    reloaded.set("code", "Root", "draft", tmp_path, ".s")
    assert reloaded.get("code", "Root", "draft") is None
    reloaded.forget("code", "Root", "draft")
    reloaded._dirty = False
    reloaded.flush()
    assert json.loads(reloaded.path.read_text(encoding="utf-8"))["entries"] == persisted["entries"]

    valid_entries = {"code:draft:root": {"base_dir": str(tmp_path), "ext": ".s"}}
    reloaded._data["entries"] = valid_entries.copy()
    reloaded._dirty = False
    reloaded.set("code", "Root", "draft", tmp_path, ".s")
    assert reloaded._dirty is False
    reloaded.forget("code", "Root", "draft")
    assert reloaded._dirty is True

    source_path = tmp_path / "Program" / "Main.s"
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_text('"a"\n"b"\n"c"\n', encoding="utf-8")
    file_ast_cache = FileASTCache(tmp_path)
    cache_file = file_ast_cache._path(source_path, "draft")
    with cache_file.open("wb") as handle:
        pickle.dump({"version": CACHE_VERSION + 1, "meta": {}, "ast": "value"}, handle)
    assert file_ast_cache.load(source_path, "draft") is None

    file_ast_cache.save(source_path, "draft", "ast")
    source_path.unlink()
    assert file_ast_cache.load(source_path, "draft") is None

    source_path.write_text('"a"\n"b"\n"c"\n', encoding="utf-8")
    file_ast_cache.save(source_path, "draft", "ast")
    payload = pickle.loads(cache_file.read_bytes())
    payload["meta"]["size"] = payload["meta"]["size"] + 1
    cache_file.write_bytes(pickle.dumps(payload, protocol=pickle.HIGHEST_PROTOCOL))
    assert file_ast_cache.load(source_path, "draft") is None

    cfg = {
        "analysis_target": "main",
        "analyzed_programs_and_libraries": ["Main"],
        "mode": "draft",
        "scan_root_only": False,
        "program_dir": "Programs",
        "ABB_lib_dir": "ABB",
        "icf_dir": "ICF",
        "other_lib_dirs": ["Libs"],
    }
    first_key = cache_mod.compute_cache_key(cfg)
    second_key = cache_mod.compute_cache_key({**cfg, "mode": "official"})
    third_key = cache_mod.compute_cache_key({**cfg, "include_reverse_library_consumers": False})
    telemetry_key = cache_mod.compute_cache_key({**cfg, "telemetry": {"enabled": True}})
    analysis_key = cache_mod.compute_cache_key(
        {
            **cfg,
            "analysis": {"naming": {"variables": {"style": "snake", "allow": []}}},
        }
    )
    assert first_key != second_key
    assert first_key != third_key
    assert first_key == telemetry_key
    assert first_key == analysis_key

    monkeypatch.setattr(cache_mod, "PROJECT_CACHE_SCHEMA_VERSION", "different-project-schema")
    schema_key = cache_mod.compute_cache_key(cfg)
    assert first_key != schema_key

    ast_cache = ASTCache(tmp_path / "project-cache-extra")
    manifest_path = tmp_path / "manifest-extra.s"
    manifest_path.write_text('"x"\n"y"\n"z"\n', encoding="utf-8")
    manifest = (manifest_path.stat().st_mtime_ns, manifest_path.stat().st_size)
    ast_cache._manifest_path("project").write_text(
        json.dumps({str(manifest_path): [manifest[0], manifest[1] + 1]}),
        encoding="utf-8",
    )
    assert ast_cache.load_validated("project") is None
    ast_cache._path("project").write_bytes(
        pickle.dumps({"version": CACHE_VERSION + 1}, protocol=pickle.HIGHEST_PROTOCOL)
    )
    assert ast_cache.load_validated("project") is None


def test_file_ast_cache_save_skips_missing_source(tmp_path: Path) -> None:
    source_path = tmp_path / "Program" / "Main.s"
    source_path.parent.mkdir(parents=True, exist_ok=True)
    file_ast_cache = FileASTCache(tmp_path)

    file_ast_cache.save(source_path, "draft", "ast")

    assert file_ast_cache._path(source_path, "draft").exists() is False


def test_file_ast_cache_load_tolerates_stat_race(tmp_path: Path, monkeypatch) -> None:
    source_path = tmp_path / "Program" / "Main.s"
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_text('"a"\n"b"\n"c"\n', encoding="utf-8")
    file_ast_cache = FileASTCache(tmp_path)
    file_ast_cache.save(source_path, "draft", "ast")

    path_type = type(source_path)
    original_exists = path_type.exists
    original_stat = path_type.stat

    def fake_exists(self: Path) -> bool:
        if self == source_path:
            return True
        return original_exists(self)

    def fake_stat(self: Path, *args: object, **kwargs: object) -> os.stat_result:
        if self == source_path:
            raise PermissionError("simulated stat race")
        return original_stat(self, *args, **kwargs)

    monkeypatch.setattr(path_type, "exists", fake_exists)
    monkeypatch.setattr(path_type, "stat", fake_stat)

    assert file_ast_cache.load(source_path, "draft") is None


def test_ast_cache_save_skips_missing_manifest_file(tmp_path: Path) -> None:
    ast_cache = ASTCache(tmp_path / "project-cache-race")
    manifest_path = tmp_path / "missing-manifest.s"

    ast_cache.save("project", project=SimpleNamespace(name="project"), files=[manifest_path])

    assert ast_cache._path("project").exists() is False


def test_ast_cache_load_validated_tolerates_stat_race(tmp_path: Path, monkeypatch) -> None:
    ast_cache = ASTCache(tmp_path / "project-cache-race")
    manifest_path = tmp_path / "manifest-race.s"
    manifest_path.write_text('"x"\n"y"\n"z"\n', encoding="utf-8")
    manifest = (manifest_path.stat().st_mtime_ns, manifest_path.stat().st_size)
    ast_cache._path("project").write_bytes(pickle.dumps({"version": CACHE_VERSION}, protocol=pickle.HIGHEST_PROTOCOL))

    path_type = type(manifest_path)
    original_exists = path_type.exists
    original_stat = path_type.stat

    def fake_exists(self: Path) -> bool:
        if self == manifest_path:
            return True
        return original_exists(self)

    def fake_stat(self: Path, *args: object, **kwargs: object):
        if self == manifest_path:
            raise PermissionError("simulated stat race")
        return original_stat(self, *args, **kwargs)

    monkeypatch.setattr(path_type, "exists", fake_exists)
    monkeypatch.setattr(path_type, "stat", fake_stat)

    ast_cache._manifest_path("project").write_text(json.dumps({str(manifest_path): list(manifest)}), encoding="utf-8")

    assert ast_cache.load_validated("project") is None


def test_ast_cache_load_and_validated_load_require_matching_payload_version(tmp_path: Path) -> None:
    ast_cache = ASTCache(tmp_path / "project-cache-version")
    manifest_path = tmp_path / "manifest-version.s"
    manifest_path.write_text('"x"\n"y"\n"z"\n', encoding="utf-8")
    manifest = (manifest_path.stat().st_mtime_ns, manifest_path.stat().st_size)

    ast_cache._path("project").write_bytes(
        pickle.dumps({"version": CACHE_VERSION + 1, "project": "stale"}, protocol=pickle.HIGHEST_PROTOCOL)
    )
    ast_cache._manifest_path("project").write_text(json.dumps({str(manifest_path): list(manifest)}), encoding="utf-8")

    assert ast_cache.load("project") is None
    assert ast_cache.load_validated("project") is None


def test_ast_cache_startup_prune_skips_payload_deserialization(tmp_path: Path, monkeypatch) -> None:
    import sattlint.cache as cache_mod  # noqa: PLC0415

    cache_dir = tmp_path / "project-cache-startup"
    cache_dir.mkdir()
    manifest_path = tmp_path / "manifest-startup.s"
    manifest_path.write_text('"x"\n"y"\n"z"\n', encoding="utf-8")
    manifest = (manifest_path.stat().st_mtime_ns, manifest_path.stat().st_size)

    (cache_dir / "project.pickle").write_bytes(
        pickle.dumps({"version": CACHE_VERSION, "project": {"name": "project"}}, protocol=pickle.HIGHEST_PROTOCOL)
    )
    (cache_dir / "project.manifest.json").write_text(
        json.dumps({str(manifest_path): list(manifest)}),
        encoding="utf-8",
    )

    def fail_load_pickle(_path: Path) -> object:
        raise AssertionError("startup pruning must not deserialize AST payloads")

    monkeypatch.setattr(cache_mod, "_load_pickle_payload", fail_load_pickle)

    ast_cache = cache_mod.ASTCache(cache_dir)

    assert ast_cache.has_payload("project") is True
    assert ast_cache.has_manifest("project") is True
    assert ast_cache.drain_startup_prune_result() == CachePruneResult()


def test_cache_prune_dir_removes_stale_persistent_cache_artifacts(tmp_path: Path) -> None:
    cache_dir = tmp_path / "cache-root"
    cache_dir.mkdir()
    (cache_dir / "file_lookup_cache.json").write_text(
        json.dumps({"version": LOOKUP_CACHE_VERSION + 1, "entries": {}}),
        encoding="utf-8",
    )

    file_ast_dir = cache_dir / "file_ast"
    file_ast_dir.mkdir()
    (file_ast_dir / "stale.pickle").write_bytes(
        pickle.dumps({"version": CACHE_VERSION + 1}, protocol=pickle.HIGHEST_PROTOCOL)
    )

    (cache_dir / "project.pickle").write_bytes(
        pickle.dumps({"version": CACHE_VERSION + 1}, protocol=pickle.HIGHEST_PROTOCOL)
    )
    (cache_dir / "project.manifest.json").write_text("{}", encoding="utf-8")
    (cache_dir / "orphan.manifest.json").write_text("{}", encoding="utf-8")

    report_dir = cache_dir / "analysis_reports"
    report_dir.mkdir()
    (report_dir / "stale-report.pickle").write_bytes(
        pickle.dumps({"version": ANALYSIS_REPORT_CACHE_VERSION + 1}, protocol=pickle.HIGHEST_PROTOCOL)
    )

    result = prune_cache_dir(cache_dir)

    assert result == CachePruneResult(
        file_lookup_entries=1,
        file_ast_entries=1,
        ast_payload_entries=1,
        ast_manifest_entries=2,
        analysis_report_entries=1,
    )
    assert result.removed_entries == 6
    assert (cache_dir / "file_lookup_cache.json").exists() is False
    assert list(file_ast_dir.glob("*.pickle")) == []
    assert list(cache_dir.glob("*.pickle")) == []
    assert list(cache_dir.glob("*.manifest.json")) == []
    assert list(report_dir.glob("*.pickle")) == []


def test_cache_manifest_and_analysis_report_edge_branches(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import sattlint.cache as cache_mod  # noqa: PLC0415

    manifest_file = tmp_path / "manifest-edge.s"
    manifest_file.write_text('"x"\n"y"\n"z"\n', encoding="utf-8")
    manifest = (manifest_file.stat().st_mtime_ns, manifest_file.stat().st_size)

    bad_manifest_payloads = [
        {str(manifest_file): "bad"},
        {str(manifest_file): [manifest[0]]},
        {str(manifest_file): ["bad", manifest[1]]},
    ]
    for index, payload in enumerate(bad_manifest_payloads):
        manifest_path = tmp_path / f"bad-manifest-{index}.json"
        manifest_path.write_text(json.dumps(payload), encoding="utf-8")
        assert cache_mod._load_manifest_payload(manifest_path) is None

    manifest_path = tmp_path / "bad-manifest-non-string-key.json"
    manifest_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(cache_mod.json, "load", lambda _handle: {1: [manifest[0], manifest[1]]})
    assert cache_mod._load_manifest_payload(manifest_path) is None

    assert cache_mod._validate_manifest([]) is False
    assert cache_mod._validate_manifest({1: manifest}) is False
    assert cache_mod._validate_manifest({str(manifest_file): [manifest[0], manifest[1]]}) is False
    assert cache_mod._validate_manifest({str(manifest_file): (manifest[0],)}) is False
    assert cache_mod._validate_manifest({str(manifest_file): ("bad", manifest[1])}) is False

    ast_cache = ASTCache(tmp_path / "project-cache-manifest-edges")
    assert ast_cache.manifest_paths("missing") == frozenset()
    assert ast_cache.has_cache_artifact("missing") is False
    assert ast_cache.load_validated("missing") is None

    report_cache = AnalysisReportCache(tmp_path)
    key = "report-key"
    assert report_cache.load(key) is None
    assert report_cache.save(key, report={"issues": []}, files=[tmp_path / "missing-source.s"]) is False

    report_cache._path(key).write_bytes(b"not-a-pickle")
    assert report_cache.load(key) is None

    source_path = tmp_path / "report-source.s"
    source_path.write_text("code", encoding="utf-8")
    assert report_cache.save(key, report={"issues": []}, files=[source_path]) is True
    loaded = report_cache.load(key)
    assert loaded is not None
    assert report_cache.validate({"version": ANALYSIS_REPORT_CACHE_VERSION, "files": {}}, fast=True) is False
    assert (
        report_cache.validate({"version": ANALYSIS_REPORT_CACHE_VERSION, "report": {}, "files": {}}, fast=True) is True
    )
    report_cache.clear(key)
    assert report_cache._path(key).exists() is False


def test_file_lookup_cache_normalizes_equivalent_base_dirs(tmp_path: Path) -> None:
    actual_base = tmp_path / "lookup-real"
    actual_base.mkdir()
    alias_base = tmp_path / "lookup-alias"
    alias_base.symlink_to(actual_base, target_is_directory=True)

    lookup_cache = FileLookupCache(tmp_path / "lookup-normalized")
    lookup_cache.set("code", "Root", "draft", alias_base, ".s")
    lookup_cache.flush()

    persisted = json.loads(lookup_cache.path.read_text(encoding="utf-8"))
    assert persisted["entries"]["code:draft:root"] == {"base_dir": str(actual_base.resolve()), "ext": ".s"}

    lookup_cache._dirty = False
    lookup_cache.set("code", "Root", "draft", actual_base, ".s")
    assert lookup_cache._dirty is False


def test_file_ast_cache_load_rejects_non_integer_stat_metadata(tmp_path: Path) -> None:
    source_path = tmp_path / "Program" / "Main.s"
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_text('"a"\n"b"\n"c"\n', encoding="utf-8")

    file_ast_cache = FileASTCache(tmp_path)
    cache_file = file_ast_cache._path(source_path, "draft")
    with cache_file.open("wb") as handle:
        pickle.dump(
            {
                "version": CACHE_VERSION,
                "meta": {
                    "path": str(source_path),
                    "mode": "draft",
                    "mtime_ns": "bad",
                    "size": source_path.stat().st_size,
                },
                "ast": "value",
            },
            handle,
            protocol=pickle.HIGHEST_PROTOCOL,
        )

    assert file_ast_cache.load(source_path, "draft") is None


def test_analysis_report_cache_clear_all_removes_cached_entries(tmp_path):
    source_path = tmp_path / "report-source.s"
    source_path.write_text("code", encoding="utf-8")
    report_cache = AnalysisReportCache(tmp_path)

    assert report_cache.save("report-a", report={"issues": []}, files=[source_path]) is True
    assert report_cache.save("report-b", report={"issues": []}, files=[source_path]) is True

    assert report_cache.clear_all() == 2
    assert list(report_cache.cache_dir.glob("*.pickle")) == []
    assert report_cache.clear_all() == 0


def test_cache_manager_reuses_singleton_instances_for_same_directory(tmp_path: Path) -> None:
    manager = get_cache_manager(tmp_path)
    same_manager = get_cache_manager(tmp_path)

    assert isinstance(manager, CacheManager)
    assert same_manager is manager
    assert manager.file_lookup_cache is same_manager.file_lookup_cache
    assert manager.file_ast_cache is same_manager.file_ast_cache
    assert manager.ast_cache is same_manager.ast_cache
    assert manager.analysis_report_cache is same_manager.analysis_report_cache
