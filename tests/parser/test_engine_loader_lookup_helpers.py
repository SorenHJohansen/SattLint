"""Lookup and cache helper tests split from test_engine_loader_helpers.py."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, cast

import pytest

from sattlint import engine
from tests.parser.test_engine import _make_loader


def test_loader_resolve_logs_readable_debug_sections(monkeypatch, caplog, tmp_path) -> None:
    class _FakeLookupCache:
        def __init__(self, *_args, **_kwargs):
            pass

    class _FakeAstCache:
        def __init__(self, *_args, **_kwargs):
            pass

        def load(self, *_args, **_kwargs):
            return None

        def save(self, *_args, **_kwargs):
            return None

    monkeypatch.setattr(engine, "create_sl_parser", lambda: object())
    monkeypatch.setattr(engine, "SLTransformer", lambda: object())
    monkeypatch.setattr(engine, "FileLookupCache", _FakeLookupCache)
    monkeypatch.setattr(engine, "FileASTCache", _FakeAstCache)
    monkeypatch.setattr(engine, "get_cache_dir", lambda: tmp_path)

    loader = engine.SattLineProjectLoader(
        program_dir=tmp_path,
        other_lib_dirs=[],
        abb_lib_dir=tmp_path,
        mode=engine.CodeMode.DRAFT,
        scan_root_only=False,
        debug=True,
    )

    def fake_visit(root_name, graph, strict, requester_dir, syntax_check=False):
        assert root_name == "Root"
        assert strict is False
        assert requester_dir == tmp_path
        assert syntax_check is False
        graph.ast_by_name["iconlib"] = object()
        graph.ast_by_name["configlib"] = object()
        graph.missing.extend(
            [
                "supportlib parse/transform error: BasePicture moduletype 'GetRemoteFile' equation 'Delay' uses OLD on non-STATE variable 'ExecuteLocal'",
                "Missing code file for 'Simulation_PPLib' (draft)",
            ]
        )

    monkeypatch.setattr(loader, "_visit", fake_visit)

    caplog.clear()
    with caplog.at_level(logging.DEBUG, logger="SattLint"):
        loader.resolve("Root")

    messages = [record.getMessage() for record in caplog.records]

    assert "[DEBUG] Resolved ASTs (2):" in messages
    assert "[DEBUG]   - iconlib" in messages
    assert "[DEBUG]   - configlib" in messages
    assert "[DEBUG] Missing/failed (2):" in messages
    assert "[DEBUG]   - supportlib" in messages
    assert (
        "[DEBUG]     parse/transform error: BasePicture moduletype 'GetRemoteFile' equation 'Delay' uses OLD on non-STATE variable 'ExecuteLocal'"
        in messages
    )
    assert "[DEBUG]   - Missing code file for 'Simulation_PPLib' (draft)" in messages


def test_loader_can_bypass_file_ast_cache(monkeypatch, tmp_path) -> None:
    class _FakeLookupCache:
        def __init__(self, *_args, **_kwargs):
            pass

    class _FakeAstCache:
        def __init__(self, *_args, **_kwargs):
            self.load_calls = 0
            self.saved = []

        def load(self, *_args, **_kwargs):
            self.load_calls += 1
            return "cached"

        def save(self, *args, **_kwargs):
            self.saved.append(args)

    monkeypatch.setattr(engine, "create_sl_parser", lambda: object())
    monkeypatch.setattr(engine, "SLTransformer", lambda: object())
    monkeypatch.setattr(engine, "FileLookupCache", _FakeLookupCache)
    monkeypatch.setattr(engine, "FileASTCache", _FakeAstCache)
    monkeypatch.setattr(engine, "get_cache_dir", lambda: tmp_path)

    loader = engine.SattLineProjectLoader(
        program_dir=tmp_path,
        other_lib_dirs=[],
        abb_lib_dir=tmp_path,
        mode=engine.CodeMode.DRAFT,
        scan_root_only=False,
        debug=False,
        use_file_ast_cache=False,
    )

    parsed = object()
    monkeypatch.setattr(loader, "_parse_one", lambda *_args, **_kwargs: parsed)

    result = loader._load_or_parse(tmp_path / "Program.s")
    ast_cache = cast(_FakeAstCache, loader._ast_cache)

    assert result is parsed
    assert ast_cache.load_calls == 0
    assert len(ast_cache.saved) == 1


def test_loader_keeps_dependency_ast_when_validation_warns(monkeypatch, tmp_path) -> None:
    source_text = "\n".join(
        [
            '"SyntaxVersion"',
            '"OriginalFileDate"',
            '"ProgramDate"',
            "BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1",
            "ModuleDef",
            "ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )",
            "ENDDEF (*BasePicture*);",
        ]
    )
    root_file = tmp_path / "Root.s"
    root_file.write_text(source_text, encoding="utf-8")
    root_file.with_suffix(".l").write_text("Dep\n", encoding="utf-8")
    (tmp_path / "Dep.s").write_text(source_text, encoding="utf-8")

    loader = engine.SattLineProjectLoader(
        program_dir=tmp_path,
        other_lib_dirs=[],
        abb_lib_dir=tmp_path,
        mode=engine.CodeMode.DRAFT,
        scan_root_only=False,
        debug=False,
    )

    call_count = {"value": 0}
    original_validate = engine.validate_transformed_basepicture

    def fake_validate(*args, **kwargs):
        call_count["value"] += 1
        if call_count["value"] == 1:
            raise engine.StructuralValidationError("dependency issue")
        return original_validate(*args, **kwargs)

    monkeypatch.setattr(engine, "validate_transformed_basepicture", fake_validate)

    graph = loader.resolve("Root")

    assert "Dep" in graph.ast_by_name
    assert "Root" in graph.ast_by_name
    assert graph.missing == []
    assert any(warning == "Dep: validation warning: dependency issue" for warning in graph.warnings)


def test_loader_base_index_helpers_cover_missing_dirs_and_added_entries(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    loader = _make_loader(monkeypatch, tmp_path, scan_root_only=False)
    base = tmp_path / "Lib"
    base.mkdir()
    code_path = base / "Program.s"
    deps_path = base / "Program.l"
    ignored_path = base / "Program.txt"
    ignored_dir = base / "Nested"
    code_path.write_text("code", encoding="utf-8")
    deps_path.write_text("deps", encoding="utf-8")
    ignored_path.write_text("ignored", encoding="utf-8")
    ignored_dir.mkdir()

    missing_index = loader._get_base_index(tmp_path / "MissingLib")
    index = loader._get_base_index(base)
    added_path = base / "Program.z"
    loader._add_to_index(base, "Program", added_path)

    assert missing_index == {}
    assert index["program"][".s"] == code_path
    assert index["program"][".l"] == deps_path
    assert ".txt" not in index["program"]
    assert loader._find_in_index(base=base, name="PROGRAM", extensions=[".x", ".s"]) == code_path
    assert loader._find_in_index(base=base, name="Missing", extensions=[".s"]) is None
    assert index["program"][".z"] == added_path


def test_loader_base_and_vendor_helpers_cover_resolve_fallbacks(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    loader = _make_loader(monkeypatch, tmp_path, scan_root_only=False)
    ignored_base = tmp_path / "IgnoredLib"
    allowed_base = tmp_path / "AllowedLib"
    ignored_base.mkdir()
    allowed_base.mkdir()
    loader._ignored_dirs = {ignored_base}
    loader.other_lib_dirs = [allowed_base]
    vendor_code = ignored_base / "Vendor.s"
    vendor_deps = ignored_base / "Vendor.l"
    vendor_code.write_text("code", encoding="utf-8")
    vendor_deps.write_text("deps", encoding="utf-8")

    original_resolve = engine.Path.resolve

    def fake_resolve(path: Path, *args, **kwargs):
        if path in {ignored_base, allowed_base}:
            raise OSError("resolve failed")
        return original_resolve(path, *args, **kwargs)

    monkeypatch.setattr(engine.Path, "resolve", fake_resolve)

    assert loader._is_ignored_base(ignored_base) is True
    assert loader._is_allowed_base(allowed_base) is True
    assert loader._find_vendor_code("Vendor") == vendor_code
    assert loader._find_vendor_deps("Vendor") == vendor_deps


def test_loader_find_in_cached_base_handles_ignored_disallowed_and_existing_paths(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    loader = _make_loader(monkeypatch, tmp_path, scan_root_only=False)
    ignored_base = tmp_path / "IgnoredLib"
    ignored_base.mkdir()
    loader._ignored_dirs = {ignored_base}
    allowed_base = tmp_path
    success_path = allowed_base / "Program.x"
    success_path.write_text("code", encoding="utf-8")
    disallowed_base = tmp_path.parent / "OtherLib"
    forget_calls: list[tuple[str, str, str]] = []

    class _Cache:
        def __init__(self, payload: dict[str, str] | None):
            self.payload = payload

        def get(self, *_args, **_kwargs):
            return self.payload

        def forget(self, kind, name, mode):
            forget_calls.append((kind, name, mode))

    loader_any = cast(Any, loader)

    loader_any._lookup_cache = _Cache({"base_dir": str(ignored_base), "ext": ".x"})
    assert loader._find_in_cached_base(kind="code", name="Program", extensions=[".x"]) is None

    loader_any._lookup_cache = _Cache({"base_dir": str(disallowed_base), "ext": ".x"})
    assert loader._find_in_cached_base(kind="code", name="Program", extensions=[".x"]) is None

    loader_any._lookup_cache = _Cache({"base_dir": str(allowed_base), "ext": ".x"})
    assert loader._find_in_cached_base(kind="code", name="Program", extensions=[".s", ".x"]) == success_path
    assert forget_calls == [("code", "Program", "draft")]


def test_loader_code_and_deps_lookup_cover_contextual_indexed_disk_and_miss(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    class _Cache:
        def __init__(self):
            self.set_calls: list[tuple[str, str, str, Path, str]] = []

        def get(self, *_args, **_kwargs):
            return None

        def set(self, kind, name, mode, base, ext):
            self.set_calls.append((kind, name, mode, base, ext))

        def forget(self, *_args, **_kwargs):
            return None

    loader = _make_loader(monkeypatch, tmp_path, scan_root_only=False)
    loader_any = cast(Any, loader)
    loader_any._lookup_cache = _Cache()
    contextual_code = tmp_path / "Ctx.s"
    contextual_deps = tmp_path / "Ctx.l"
    indexed_code = tmp_path / "Indexed.s"
    disk_code = tmp_path / "Loose.s"
    indexed_deps = tmp_path / "Indexed.l"
    disk_deps = tmp_path / "Loose.l"
    for path in [contextual_code, contextual_deps, indexed_code, disk_code, indexed_deps, disk_deps]:
        path.write_text(path.stem, encoding="utf-8")

    loader.contextual_lookup = lambda name, _extensions, _requester, kind: (
        contextual_code
        if (name, kind) == ("Ctx", "code")
        else contextual_deps
        if (name, kind) == ("Ctx", "deps")
        else None
    )

    assert loader._find_code_with_context("Ctx", requester_dir=tmp_path) == contextual_code
    assert loader._find_deps_with_context("Ctx", requester_dir=tmp_path) == contextual_deps
    assert loader._find_code_with_context("Indexed", requester_dir=tmp_path) == indexed_code
    assert loader._find_deps_with_context("Indexed", requester_dir=tmp_path) == indexed_deps

    original_find_in_index = loader._find_in_index
    monkeypatch.setattr(
        loader,
        "_find_in_index",
        lambda *, name, **kwargs: None if name == "Loose" else original_find_in_index(name=name, **kwargs),
    )

    assert loader._find_code_with_context("Loose", requester_dir=tmp_path) == disk_code
    assert loader._find_deps_with_context("Loose", requester_dir=tmp_path) == disk_deps
    assert loader._find_code_with_context("Missing", requester_dir=tmp_path) is None
    assert loader._find_deps_with_context("Missing", requester_dir=tmp_path) is None
    assert ("code", "Indexed", "draft", tmp_path, ".s") in loader_any._lookup_cache.set_calls
    assert ("deps", "Loose", "draft", tmp_path, ".l") in loader_any._lookup_cache.set_calls


def test_loader_resolve_flushes_lookup_cache_once_per_run(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    class _Cache:
        def __init__(self):
            self.flush_calls = 0
            self.set_calls: list[tuple[str, str, str, Path, str]] = []

        def get(self, *_args, **_kwargs):
            return None

        def set(self, kind, name, mode, base, ext):
            self.set_calls.append((kind, name, mode, base, ext))

        def forget(self, *_args, **_kwargs):
            return None

        def flush(self):
            self.flush_calls += 1

    loader = _make_loader(monkeypatch, tmp_path, scan_root_only=False)
    loader_any = cast(Any, loader)
    loader_any._lookup_cache = _Cache()

    def _fake_visit(name, graph, strict, *, requester_dir, syntax_check=False):
        loader_any._lookup_cache.set("code", name, loader.mode.value, tmp_path, ".s")
        loader_any._lookup_cache.set("deps", name, loader.mode.value, tmp_path, ".l")

    monkeypatch.setattr(loader, "_visit", _fake_visit)

    graph = loader.resolve("Root")

    assert graph.ast_by_name == {}
    assert loader_any._lookup_cache.flush_calls == 1
    assert loader_any._lookup_cache.set_calls == [
        ("code", "Root", "draft", tmp_path, ".s"),
        ("deps", "Root", "draft", tmp_path, ".l"),
    ]
