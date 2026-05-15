"""Tail parser loader helper tests split from test_engine.py for structural budget control."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest

from sattlint import engine
from tests.parser.test_engine import _make_basepicture, _make_loader


def test_loader_read_and_library_helpers_cover_all_library_roots(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    other_lib = tmp_path.parent / "OtherLib"
    abb_lib = tmp_path.parent / "AbbLib"
    other_lib.mkdir()
    abb_lib.mkdir()
    loader = engine.SattLineProjectLoader(
        program_dir=tmp_path,
        other_lib_dirs=[other_lib],
        abb_lib_dir=abb_lib,
        mode=engine.CodeMode.DRAFT,
        scan_root_only=False,
        debug=False,
    )

    monkeypatch.setattr(engine, "read_text_with_fallback", lambda _path: " DepA \n\nDepB\n")
    external_path = tmp_path.parent / "ExternalLib" / "Program.s"

    assert loader._read_deps(tmp_path / "Program.l") == ["DepA", "DepB"]
    assert loader._read_text_simple(tmp_path / "Program.s") == " DepA \n\nDepB\n"
    assert loader._library_name_for_path(tmp_path / "Program.s") == tmp_path.name
    assert loader._library_name_for_path(other_lib / "Program.s") == "OtherLib"
    assert loader._library_name_for_path(abb_lib / "Program.s") == "AbbLib"
    assert loader._library_name_for_path(external_path) == "ExternalLib"
    assert loader._record_library_name("Program", other_lib / "Program.s") == "OtherLib"
    assert loader._lib_by_name["program"] == "OtherLib"


def test_loader_parse_and_cache_helpers_delegate_and_reuse_cached_ast(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    loader = _make_loader(monkeypatch, tmp_path, scan_root_only=False)
    basepicture = _make_basepicture()
    seen: dict[str, object] = {}

    monkeypatch.setattr(
        engine,
        "parser_core_parse_source_file",
        lambda code_path, *, parser, transformer, debug: (
            seen.update({"code_path": code_path, "parser": parser, "transformer": transformer, "debug": debug})
            or basepicture
        ),
    )

    parsed = loader._parse_one(tmp_path / "Program.s")

    class _AstCache:
        def __init__(self, cached):
            self.cached = cached
            self.save_calls: list[tuple[Path, str, object]] = []

        def load(self, code_path, mode):
            return self.cached

        def save(self, code_path, mode, bp):
            self.save_calls.append((code_path, mode, bp))

    cached_cache = _AstCache(basepicture)
    loader_any = cast(Any, loader)
    loader_any._ast_cache = cached_cache
    cached = loader._load_or_parse(tmp_path / "Program.s")

    parsed_cache = _AstCache(None)
    loader_any._ast_cache = parsed_cache
    monkeypatch.setattr(loader, "_parse_one", lambda _path: basepicture)
    uncached = loader._load_or_parse(tmp_path / "Program.s")

    assert parsed is basepicture
    assert seen == {
        "code_path": tmp_path / "Program.s",
        "parser": loader.parser,
        "transformer": loader.transformer,
        "debug": loader.dbg,
    }
    assert cached is basepicture
    assert cached_cache.save_calls == []
    assert uncached is basepicture
    assert parsed_cache.save_calls == [(tmp_path / "Program.s", "draft", basepicture)]
