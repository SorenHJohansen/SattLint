"""Tail parser loader helper tests split from test_engine.py for structural budget control."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from lark import Lark

from sattlint import engine
from tests.parser.test_engine import _make_basepicture, _make_loader


def test_engine_wrapper_helpers_cover_file_parsing_and_ok_validation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    basepicture = _make_basepicture()
    parser = cast(Lark, object())
    transformer = cast(engine.SLTransformer, object())
    debug_messages: list[str] = []
    seen: dict[str, object] = {}

    monkeypatch.setattr(
        engine,
        "parser_core_parse_source_file",
        lambda code_path, *, parser, transformer, debug: (
            seen.update(
                {
                    "code_path": code_path,
                    "parser": parser,
                    "transformer": transformer,
                    "debug": debug,
                }
            )
            or basepicture
        ),
    )
    monkeypatch.setattr(engine, "validate_transformed_basepicture", lambda bp: seen.setdefault("validated", bp))

    parsed = engine.parse_source_file(
        tmp_path / "Program.s",
        parser=parser,
        transformer=transformer,
        debug=debug_messages.append,
    )

    assert parsed is basepicture
    assert seen == {
        "code_path": tmp_path / "Program.s",
        "parser": parser,
        "transformer": transformer,
        "debug": debug_messages.append,
        "validated": basepicture,
    }
    assert engine.is_within_directory(tmp_path / "nested" / "Program.s", tmp_path) is True
    assert engine.is_within_directory(tmp_path.parent / "Elsewhere.s", tmp_path) is False
    engine._raise_syntax_validation_failure(
        engine.SyntaxValidationResult(file_path=tmp_path / "Program.s", ok=True, stage="ok")
    )


def test_validate_single_file_syntax_for_graphics_file_loads_source_context(monkeypatch: pytest.MonkeyPatch) -> None:
    basepicture = _make_basepicture()
    warnings = (engine.ValidationNotice(message="picture warning", line=4, column=2, length=6),)
    occurrence = object()

    monkeypatch.setattr(
        engine,
        "validate_graphics_file",
        lambda _path: SimpleNamespace(
            messages=(),
            warnings=(),
            errors=[],
            picture_display_records=(object(),),
        ),
    )
    monkeypatch.setattr(engine, "_graphics_source_context_path", lambda _path: Path("Program.s"))
    monkeypatch.setattr(engine, "_load_picture_display_source_context", lambda _path: basepicture)
    monkeypatch.setattr(engine, "correlate_picture_display_records", lambda _bp, _records: (occurrence,))
    monkeypatch.setattr(engine, "_picture_display_path_warnings", lambda _bp, _occurrences: warnings)

    result = engine.validate_single_file_syntax(Path("Program.g"))

    assert result == engine.SyntaxValidationResult(
        file_path=Path("Program.g"),
        ok=True,
        stage="ok",
        warnings=("picture warning",),
        warning_notices=warnings,
    )


def test_loader_status_and_lookup_wrappers_cover_blank_duplicate_and_forget(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    loader = _make_loader(monkeypatch, tmp_path, scan_root_only=False)
    status_messages: list[str] = []
    loader_any = cast(Any, loader)
    loader_any._status_update_fn = status_messages.append

    class _Cache:
        def __init__(self):
            self.forget_calls: list[tuple[str, str, str]] = []

        def get(self, *_args, **_kwargs):
            return {"base_dir": str(tmp_path), "ext": ".x"}

        def forget(self, kind, name, mode):
            self.forget_calls.append((kind, name, mode))

    cache = _Cache()
    loader_any._lookup_cache = cache

    loader._update_status(" Loading Root ")
    loader._update_status("   ")
    loader._update_status("Loading Root")
    loader._update_status("Loading Dep")

    assert loader._find_in_cached_base(kind="code", name="Program", extensions=[".x"]) is None
    monkeypatch.setattr(loader, "_find_code_with_context", lambda _name, requester_dir=None: tmp_path / "Cached.s")
    monkeypatch.setattr(loader, "_find_deps_with_context", lambda _name, requester_dir=None: tmp_path / "Cached.l")

    assert loader._find_code("Program") == tmp_path / "Cached.s"
    assert loader._find_deps("Program") == tmp_path / "Cached.l"
    assert status_messages == ["Loading Root", "Loading Dep"]
    assert cache.forget_calls == [("code", "Program", "draft")]


def test_record_missing_library_covers_unavailable_and_strict_missing_cases() -> None:
    graph = engine.ProjectGraph()

    engine._record_missing_library(
        graph,
        name="ControlLib",
        mode="draft",
        strict=False,
        requester="ControlLib",
    )

    assert graph.warnings == ["ControlLib: unavailable library: expected proprietary dependency"]
    assert graph.unavailable_libraries == {"controllib"}

    with pytest.raises(FileNotFoundError, match=r"Missing code file for 'MissingLib' \(draft\)"):
        engine._record_missing_library(
            graph,
            name="MissingLib",
            mode="draft",
            strict=True,
        )


def test_loader_lookup_returns_cached_code_and_deps_paths(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    class _Cache:
        def get(self, kind, *_args, **_kwargs):
            return {"base_dir": str(tmp_path), "ext": ".s" if kind == "code" else ".l"}

        def set(self, *_args, **_kwargs):
            return None

        def forget(self, *_args, **_kwargs):
            return None

    loader = _make_loader(monkeypatch, tmp_path, scan_root_only=False)
    cast(Any, loader)._lookup_cache = _Cache()
    code_path = tmp_path / "Program.s"
    deps_path = tmp_path / "Program.l"
    code_path.write_text("code", encoding="utf-8")
    deps_path.write_text("deps", encoding="utf-8")

    assert loader._find_code_with_context("Program", requester_dir=tmp_path) == code_path
    assert loader._find_deps_with_context("Program", requester_dir=tmp_path) == deps_path


def test_loader_library_name_for_path_falls_back_when_base_resolve_raises(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    other_lib = tmp_path.parent / "OtherLib"
    abb_lib = tmp_path.parent / "AbbLib"
    other_lib.mkdir(exist_ok=True)
    abb_lib.mkdir(exist_ok=True)
    loader = engine.SattLineProjectLoader(
        program_dir=tmp_path,
        other_lib_dirs=[other_lib],
        abb_lib_dir=abb_lib,
        mode=engine.CodeMode.DRAFT,
        scan_root_only=False,
        debug=False,
    )

    original_resolve = engine.Path.resolve

    def fake_resolve(path: Path, *args, **kwargs):
        if path in {tmp_path, other_lib, abb_lib}:
            raise OSError("resolve failed")
        return original_resolve(path, *args, **kwargs)

    monkeypatch.setattr(engine.Path, "resolve", fake_resolve)

    assert loader._library_name_for_path(tmp_path / "Program.s") == tmp_path.name
    assert loader._library_name_for_path(other_lib / "Program.s") == other_lib.name
    assert loader._library_name_for_path(abb_lib / "Program.s") == abb_lib.name


def test_root_only_loader_success_records_warnings_and_indexes_definitions(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    loader = _make_loader(monkeypatch, tmp_path)
    code_path = tmp_path / "Root.s"
    basepicture = _make_basepicture(origin_file=code_path.name, origin_lib=tmp_path.name)
    save_calls: list[tuple[Path, str, object]] = []

    class _AstCache:
        def load(self, *_args, **_kwargs):
            return None

        def save(self, code_path, mode, bp):
            save_calls.append((code_path, mode, bp))

    cast(Any, loader)._ast_cache = _AstCache()
    monkeypatch.setattr(loader, "_find_code", lambda _name: code_path)
    monkeypatch.setattr(loader, "_load_or_parse", lambda _path: basepicture)
    monkeypatch.setattr(
        engine,
        "validate_transformed_basepicture",
        lambda _bp, warning_sink, **_kwargs: warning_sink("warning-a"),
    )
    monkeypatch.setattr(engine, "_graphics_companion_needs_refresh", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(engine, "_attach_graphics_companion", lambda *_args, **_kwargs: True)

    graph = loader.resolve("Root")

    assert graph.ast_by_name["Root"] is basepicture
    assert graph.warnings == ["Root: warning-a"]
    assert graph.warning_notices == [("Root", engine.ValidationNotice(message="warning-a"))]
    assert save_calls == [(code_path, "draft", basepicture)]


def test_root_only_loader_strict_none_basepicture_reraises(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    loader = _make_loader(monkeypatch, tmp_path)
    code_path = tmp_path / "Root.s"

    monkeypatch.setattr(loader, "_find_code", lambda _name: code_path)
    monkeypatch.setattr(loader, "_load_or_parse", lambda _path: None)

    with pytest.raises(RuntimeError, match="transformed to no BasePicture"):
        loader.resolve("Root", strict=True)


def test_root_only_loader_full_mode_records_stage_timings(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    timings: list[tuple[str, str, float]] = []
    loader = _make_loader(monkeypatch, tmp_path)
    cast(Any, loader)._stage_timing_sink = lambda owner, stage, duration: timings.append((owner, stage, duration))
    code_path = tmp_path / "Root.s"
    basepicture = _make_basepicture(origin_file=code_path.name, origin_lib=tmp_path.name)

    class _AstCache:
        def load(self, *_args, **_kwargs):
            return None

        def save(self, *_args, **_kwargs):
            return None

    cast(Any, loader)._ast_cache = _AstCache()
    monkeypatch.setattr(loader, "_find_code", lambda _name: code_path)
    monkeypatch.setattr(loader, "_parse_one", lambda _path: basepicture)
    monkeypatch.setattr(engine, "validate_transformed_basepicture", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(engine, "_graphics_companion_needs_refresh", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(engine, "_attach_graphics_companion", lambda *_args, **_kwargs: False)

    graph = loader.resolve("Root")

    assert graph.ast_by_name["Root"] is basepicture
    assert {stage for _owner, stage, _duration in timings} == {
        "load_or_parse",
        "validate",
        "attach_graphics",
        "index",
        "ast_cache_save",
    }


def test_root_only_loader_ast_only_refresh_skips_enrichment_but_records_core_stage_timings(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    timings: list[tuple[str, str, float]] = []
    loader = _make_loader(monkeypatch, tmp_path)
    loader.refresh_mode = "ast-only"
    cast(Any, loader)._stage_timing_sink = lambda owner, stage, duration: timings.append((owner, stage, duration))
    code_path = tmp_path / "Root.s"
    basepicture = _make_basepicture(origin_file=code_path.name, origin_lib=tmp_path.name)

    class _AstCache:
        def load(self, *_args, **_kwargs):
            return None

        def save(self, *_args, **_kwargs):
            return None

    cast(Any, loader)._ast_cache = _AstCache()
    monkeypatch.setattr(loader, "_find_code", lambda _name: code_path)
    monkeypatch.setattr(loader, "_parse_one", lambda _path: basepicture)
    monkeypatch.setattr(engine, "validate_transformed_basepicture", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        engine,
        "_graphics_companion_needs_refresh",
        lambda *_args, **_kwargs: pytest.fail("graphics companion checks should be skipped during ast-only refresh"),
    )
    monkeypatch.setattr(
        engine,
        "_attach_graphics_companion",
        lambda *_args, **_kwargs: pytest.fail(
            "graphics companion attachment should be skipped during ast-only refresh"
        ),
    )

    graph = loader.resolve("Root")

    assert graph.ast_by_name["Root"] is basepicture
    assert {stage for _owner, stage, _duration in timings} == {
        "load_or_parse",
        "validate",
        "ast_cache_save",
    }


def test_loader_lookup_skips_ignored_base_before_finding_other_matches(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    class _Cache:
        def get(self, *_args, **_kwargs):
            return None

        def set(self, *_args, **_kwargs):
            return None

        def forget(self, *_args, **_kwargs):
            return None

    loader = _make_loader(monkeypatch, tmp_path, scan_root_only=False)
    other_lib = tmp_path.parent / "OtherLib"
    other_lib.mkdir(exist_ok=True)
    (other_lib / "Program.s").write_text("code", encoding="utf-8")
    (other_lib / "Program.l").write_text("deps", encoding="utf-8")
    loader.other_lib_dirs = [other_lib]
    loader._ignored_dirs = {tmp_path}
    cast(Any, loader)._lookup_cache = _Cache()

    assert loader._find_code_with_context("Program", requester_dir=tmp_path) == other_lib / "Program.s"
    assert loader._find_deps_with_context("Program", requester_dir=tmp_path) == other_lib / "Program.l"


def test_loader_visit_short_circuits_and_reraises_strict_none_basepicture(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    loader = _make_loader(monkeypatch, tmp_path, scan_root_only=False)
    graph = engine.ProjectGraph()
    loader._visited.add("root")
    loader._visit("Root", graph, strict=False, requester_dir=tmp_path)
    assert loader._visit_stack == []

    loader._visited.clear()
    code_path = tmp_path / "Root.s"
    monkeypatch.setattr(loader, "_find_deps_with_context", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(loader, "_find_code_with_context", lambda *_args, **_kwargs: code_path)
    monkeypatch.setattr(loader, "_load_or_parse", lambda _path: None)

    with pytest.raises(RuntimeError, match="transform produced no BasePicture"):
        loader._visit("Root", engine.ProjectGraph(), strict=True, requester_dir=tmp_path)


def test_loader_read_and_library_helpers_cover_all_library_roots(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    other_lib = tmp_path.parent / "OtherLib"
    abb_lib = tmp_path.parent / "AbbLib"
    other_lib.mkdir(exist_ok=True)
    abb_lib.mkdir(exist_ok=True)
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


def test_root_only_loader_records_missing_root_library(monkeypatch, tmp_path) -> None:
    loader = _make_loader(monkeypatch, tmp_path)
    monkeypatch.setattr(loader, "_find_code", lambda _name: None)

    graph = loader.resolve("MissingRoot")

    assert graph.missing == ["Missing code file for 'MissingRoot' (mode=draft)"]
    assert graph.unavailable_libraries == {"missingroot"}


def test_root_only_loader_records_none_basepicture_without_raising(monkeypatch, tmp_path) -> None:
    loader = _make_loader(monkeypatch, tmp_path)
    code_path = tmp_path / "Root.s"

    monkeypatch.setattr(loader, "_find_code", lambda _name: code_path)
    monkeypatch.setattr(loader, "_load_or_parse", lambda _path: None)

    graph = loader.resolve("Root")

    assert graph.missing == ["Root transformed to no BasePicture (parse/transform issue?)"]
    assert graph.ast_by_name == {}


def test_root_only_loader_records_validation_warning_before_failure(monkeypatch, tmp_path) -> None:
    loader = _make_loader(monkeypatch, tmp_path)
    code_path = tmp_path / "Root.s"

    monkeypatch.setattr(loader, "_find_code", lambda _name: code_path)
    monkeypatch.setattr(loader, "_load_or_parse", lambda _path: object())
    monkeypatch.setattr(loader, "_library_name_for_path", lambda _path: "RootLib")
    monkeypatch.setattr(
        engine,
        "validate_transformed_basepicture",
        lambda _bp, warning_sink, **_kwargs: (
            warning_sink("warning-a") or (_ for _ in ()).throw(engine.StructuralValidationError("bad root"))
        ),
    )

    graph = loader.resolve("Root")

    assert graph.warnings == ["Root: warning-a"]
    assert graph.warning_notices == [("Root", engine.ValidationNotice(message="warning-a"))]
    assert graph.missing == ["Root parse/transform error: bad root"]
    assert graph.failures["root"].line is None
