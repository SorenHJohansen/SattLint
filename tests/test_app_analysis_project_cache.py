"""Tests for app analysis project loading and AST cache behavior."""

from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from sattlint import app_analysis


def test_load_project_returns_cached_project_without_building_loader(monkeypatch):
    cached_project = ("bp-cached", SimpleNamespace())
    seen_cache_dirs: list[Path] = []

    class FakeCache:
        def __init__(self, cache_dir):
            self.cache_dir = cache_dir
            seen_cache_dirs.append(cache_dir)

        def load(self, key):
            assert key == "cache-key"
            return {"project": cached_project}

    monkeypatch.setattr(app_analysis, "ASTCache", FakeCache)
    monkeypatch.setattr(
        app_analysis.engine_module,
        "SattLineProjectLoader",
        lambda **_kwargs: pytest.fail("loader should not be created"),
    )

    result = app_analysis.load_project(
        {
            "program_dir": "programs",
            "other_lib_dirs": [],
            "ABB_lib_dir": "abb",
            "mode": "draft",
            "scan_root_only": True,
            "debug": False,
            "analyzed_programs_and_libraries": ["TargetA"],
        },
        cache_key_for_target_fn=lambda _cfg, _target: "cache-key",
        get_cache_dir_fn=lambda: Path("custom-cache-dir"),
    )

    assert result == cached_project
    assert seen_cache_dirs == [Path("custom-cache-dir")]


def test_load_project_raises_target_load_error_when_root_program_missing(monkeypatch):
    class FakeCache:
        def __init__(self, cache_dir):
            self.cache_dir = cache_dir

        def load(self, key):
            return None

        def save(self, key, **kwargs):
            pytest.fail("cache should not be saved when root program is missing")

    class FakeLoader:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def resolve(self, target_name, strict=False):
            return SimpleNamespace(
                ast_by_name={"Dependency": "bp-dependency"},
                missing=["dep parse error"],
                warnings=["dep warning"],
                source_files={Path("programs/Dependency.s")},
            )

        def _find_deps_with_context(self, target_name, requester_dir):
            return Path("programs/TargetA.l")

        def _read_deps(self, deps_path):
            return ["Dependency"]

    captured: dict[str, object] = {}

    monkeypatch.setattr(app_analysis, "ASTCache", FakeCache)
    monkeypatch.setattr(app_analysis, "get_cache_dir", lambda: Path("cache-dir"))
    monkeypatch.setattr(app_analysis.engine_module, "SattLineProjectLoader", FakeLoader)

    def fake_error_factory(target_name, **kwargs):
        captured.update({"target_name": target_name, **kwargs})
        return RuntimeError(f"missing {target_name}")

    with pytest.raises(RuntimeError, match="missing TargetA"):
        app_analysis.load_project(
            {
                "program_dir": "programs",
                "other_lib_dirs": ["libs"],
                "ABB_lib_dir": "abb",
                "mode": "draft",
                "scan_root_only": False,
                "debug": True,
                "analyzed_programs_and_libraries": ["TargetA"],
            },
            target_load_error_factory=fake_error_factory,
        )

    assert captured == {
        "target_name": "TargetA",
        "resolved": ["Dependency"],
        "missing": ["dep parse error"],
        "warnings": ["dep warning"],
        "direct_dependencies": ["Dependency"],
    }


def test_load_program_ast_raises_when_program_was_not_parsed(monkeypatch):
    class FakeLoader:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def resolve(self, program_name, strict=False):
            return SimpleNamespace(ast_by_name={"Other": "bp-other"})

    monkeypatch.setattr(app_analysis.engine_module, "SattLineProjectLoader", FakeLoader)

    with pytest.raises(RuntimeError, match="Program 'TargetA' not parsed"):
        app_analysis.load_program_ast(
            {
                "program_dir": "programs",
                "other_lib_dirs": [],
                "ABB_lib_dir": "abb",
                "mode": "draft",
                "scan_root_only": True,
                "debug": False,
            },
            "TargetA",
        )


def test_force_refresh_ast_clears_cache_entries_and_reloads_all_targets():
    cache_clears: list[str] = []
    load_calls: list[tuple[str, bool, bool]] = []

    class FakeCache:
        def __init__(self, cache_dir):
            self.cache_dir = cache_dir

        def clear(self, key):
            cache_clears.append(key)

    result = app_analysis.force_refresh_ast(
        {"analyzed_programs_and_libraries": ["TargetA", "TargetB"]},
        cache_key_for_target_fn=lambda _cfg, target_name: f"key:{target_name}",
        load_project_fn=cast(
            Any,
            lambda _cfg, target_name=None, use_cache=True, use_file_ast_cache=True: (
                load_calls.append(((target_name or ""), use_cache, use_file_ast_cache))
                or (f"bp-{target_name or ''}", SimpleNamespace())
            ),
        ),
        ast_cache_cls=cast(Any, FakeCache),
        get_cache_dir_fn=lambda: Path("cache-dir"),
    )

    assert cache_clears == ["key:TargetA", "key:TargetB"]
    assert load_calls == [("TargetA", False, False), ("TargetB", False, False)]
    assert result == ("bp-TargetB", SimpleNamespace())


def test_ensure_ast_cache_handles_valid_fast_path_rebuilds_and_failures(monkeypatch):
    lines: list[str] = []
    load_calls: list[str] = []

    class FakeCache:
        def __init__(self, cache_dir):
            self.cache_dir = cache_dir

        def load(self, key):
            mapping = {
                "key:Fresh": {"name": "Fresh", "files": ["a"]},
                "key:Stale": {"name": "Stale", "files": ["a"]},
                "key:Old": {"name": "Old"},
                "key:Broken": None,
            }
            return mapping[key]

        def validate(self, cached, fast=False):
            return cached == {"name": "Fresh", "files": ["a"]} and fast is False

    def fake_load_project(_cfg, target_name=None, use_cache=True, use_file_ast_cache=True):
        resolved_target = target_name or ""
        load_calls.append(resolved_target)
        if target_name == "Broken":
            raise RuntimeError("boom")
        return (f"bp-{resolved_target}", SimpleNamespace())

    monkeypatch.setattr(app_analysis, "emit_output", lambda message: lines.append(message))

    ok = app_analysis.ensure_ast_cache(
        {
            "analyzed_programs_and_libraries": ["Fresh", "Stale", "Old", "Broken"],
            "fast_cache_validation": True,
        },
        cache_key_for_target_fn=lambda _cfg, target_name: f"key:{target_name}",
        load_project_fn=cast(Any, fake_load_project),
        ast_cache_cls=cast(Any, FakeCache),
        get_cache_dir_fn=lambda: Path("cache-dir"),
    )

    assert ok is False
    assert load_calls == ["Stale", "Old", "Broken"]
    assert any("Checking AST cache for Fresh..." in line for line in lines)
    assert any("AST cache OK" in line for line in lines)
    assert any("AST cache stale; rebuilding" in line for line in lines)
    assert any("AST cache missing file manifest; rebuilding" in line for line in lines)
    assert any("AST cache missing; building" in line for line in lines)
    assert any("AST cache updated" in line for line in lines)
    assert any("Failed to build AST cache for Broken: boom" in line for line in lines)
