# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportPrivateUsage=false, reportArgumentType=false
"""Lookup and cache helper tests split from test_engine_loader_helpers.py."""

from __future__ import annotations

import logging
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from sattline_parser.models.ast_model import (
    FrameModule,
    GraphObject,
    ModuleDef,
    ModuleHeader,
    ModuleTypeDef,
    ModuleTypeInstance,
    SingleModule,
)
from sattlint import _picture_display_path_runtime as picture_display_path_runtime
from sattlint import engine
from sattlint.graphics_validation import GraphicsCompositeRecord
from tests.parser.test_engine import _loader_config, _make_loader


def _header(name: str) -> ModuleHeader:
    return ModuleHeader(name=name, invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0))


def _composite_moduledef() -> ModuleDef:
    return ModuleDef(graph_objects=[GraphObject("CompositeObject")])


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

    loader = engine.SattLineProjectLoader(_loader_config(tmp_path, debug=True))

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

    loader = engine.SattLineProjectLoader(_loader_config(tmp_path, use_file_ast_cache=False))

    parsed = SimpleNamespace()
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

    loader = engine.SattLineProjectLoader(_loader_config(tmp_path))

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
    assert "root" in graph.failures
    assert any("dependency issue" in failure for failure in graph.missing)


def test_picture_display_runtime_lookup_helpers_cover_suffix_parent_and_name_queries() -> None:
    panel_a = picture_display_path_runtime.RuntimeModuleNode(
        name="Panel",
        path=("Top", "Root", "Area", "Panel"),
        current_library="RootLib",
        current_file="Root.s",
    )
    panel_b = picture_display_path_runtime.RuntimeModuleNode(
        name="Panel",
        path=("Top", "Other", "Area", "Panel"),
        current_library="OtherLib",
        current_file="Other.s",
    )
    root_area = picture_display_path_runtime.RuntimeModuleNode(
        name="Area",
        path=("Top", "Root", "Area"),
        current_library="RootLib",
        current_file="Root.s",
        children=(panel_a,),
    )
    other_area = picture_display_path_runtime.RuntimeModuleNode(
        name="Area",
        path=("Top", "Other", "Area"),
        current_library="OtherLib",
        current_file="Other.s",
        children=(panel_b,),
    )
    runtime_tree = picture_display_path_runtime._index_runtime_tree(
        picture_display_path_runtime.RuntimeModuleNode(
            name="Top",
            path=("Top",),
            current_library=None,
            current_file=None,
            children=(
                picture_display_path_runtime.RuntimeModuleNode(
                    name="Root",
                    path=("Top", "Root"),
                    current_library="RootLib",
                    current_file="Root.s",
                    children=(root_area,),
                ),
                picture_display_path_runtime.RuntimeModuleNode(
                    name="Other",
                    path=("Top", "Other"),
                    current_library="OtherLib",
                    current_file="Other.s",
                    children=(other_area,),
                ),
            ),
        )
    )

    assert picture_display_path_runtime.find_node(runtime_tree, ("top", "root", "area")) == root_area
    assert picture_display_path_runtime.find_parent_node(runtime_tree, panel_a.path) == root_area
    assert picture_display_path_runtime.find_suffix_nodes(runtime_tree, ("X", "Area", "Panel")) == (panel_b, panel_a)
    assert picture_display_path_runtime.find_best_suffix_node(runtime_tree, ("X", "Area", "Panel")) is None
    assert (
        picture_display_path_runtime.find_best_suffix_node(
            runtime_tree,
            ("X", "Area", "Panel"),
            exclude_path=panel_b.path,
        )
        == panel_a
    )
    assert picture_display_path_runtime.find_best_suffix_node(runtime_tree, ("X", "Root", "Area", "Panel")) == panel_a
    assert picture_display_path_runtime.find_suffix_nodes(runtime_tree, ("X", "Root", "Area", "Panel"))[0] == panel_a
    assert picture_display_path_runtime.consume_name(" Panel-Child") == ("Panel", "-Child")
    assert picture_display_path_runtime.consume_name("Panel") == ("Panel", "")
    assert picture_display_path_runtime.find_nearest_descendant(runtime_tree.root, "panel") == panel_a
    assert picture_display_path_runtime.find_nearest_descendant(runtime_tree.root, "missing") is None
    assert picture_display_path_runtime._common_suffix_length(("Root", "Area", "Panel"), ("X", "Area", "panel")) == 2


def test_picture_display_runtime_moduletype_helpers_cover_dedup_locality_and_resolution(monkeypatch) -> None:
    local_type = ModuleTypeDef(name="LocalType", origin_file="Root.s", origin_lib="root")
    dep_type = ModuleTypeDef(name="DepType", origin_file="Dep.s", origin_lib="DepLib")
    base_picture = engine.BasePicture(
        header=_header("Root"),
        name="Root",
        position=(0.0, 0.0, 0.0, 1.0, 1.0),
        moduledef=ModuleDef(),
        origin_file="Root.s",
        origin_lib="root",
        moduletype_defs=[local_type, dep_type],
    )
    graph = SimpleNamespace(
        moduletype_defs={("deplib", "deptype", "dep.s"): dep_type}, unavailable_libraries={"MissingLib"}
    )

    candidate_index = picture_display_path_runtime._candidate_moduletype_index(base_picture, graph)

    assert candidate_index["localtype"] == (local_type,)
    assert candidate_index["deptype"] == (dep_type,)
    assert picture_display_path_runtime._local_moduletype_defs(base_picture) == (local_type,)
    assert picture_display_path_runtime._is_local_moduletype_def(base_picture, local_type) is True
    assert picture_display_path_runtime._is_local_moduletype_def(base_picture, dep_type) is False

    same_file_base = engine.BasePicture(
        header=_header("Root"),
        name="Root",
        position=(0.0, 0.0, 0.0, 1.0, 1.0),
        moduledef=ModuleDef(),
        origin_file="Root.s",
        origin_lib="sharedlib",
    )
    assert (
        picture_display_path_runtime._is_local_moduletype_def(
            same_file_base,
            ModuleTypeDef(name="Sibling", origin_file="root.x", origin_lib="otherlib"),
        )
        is True
    )
    assert picture_display_path_runtime._same_origin_file_stem("Root.s", "ROOT.x") is True
    assert picture_display_path_runtime._same_origin_file_stem("Root.s", None) is False
    assert picture_display_path_runtime._file_stem_casefold("Root.s") == "root"

    original_path = picture_display_path_runtime.Path

    class _BrokenPath:
        def __init__(self, *_args, **_kwargs) -> None:
            raise ValueError("bad path")

    monkeypatch.setattr(picture_display_path_runtime, "Path", _BrokenPath)
    assert picture_display_path_runtime._file_stem_casefold("Root.s") == "root"
    monkeypatch.setattr(picture_display_path_runtime, "Path", original_path)

    child = ModuleTypeInstance(header=_header("Child"), moduletype_name="DepType")
    monkeypatch.setattr(
        picture_display_path_runtime, "select_moduletype_def_strict", lambda *_args, **_kwargs: dep_type
    )
    assert (
        picture_display_path_runtime._resolve_runtime_moduletype(
            base_picture,
            child,
            current_library="RootLib",
            current_file="Root.s",
            graph=graph,
            candidate_moduletype_index=candidate_index,
        )
        == dep_type
    )

    monkeypatch.setattr(
        picture_display_path_runtime,
        "select_moduletype_def_strict",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("bad resolve")),
    )
    assert (
        picture_display_path_runtime._resolve_runtime_moduletype(
            base_picture,
            child,
            current_library="RootLib",
            current_file="Root.s",
            graph=graph,
            candidate_moduletype_index=candidate_index,
        )
        is None
    )

    monkeypatch.setattr(
        picture_display_path_runtime,
        "select_moduletype_def_strict",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(TypeError("bad resolver wiring")),
    )
    with pytest.raises(TypeError, match="bad resolver wiring"):
        picture_display_path_runtime._resolve_runtime_moduletype(
            base_picture,
            child,
            current_library="RootLib",
            current_file="Root.s",
            graph=graph,
            candidate_moduletype_index=candidate_index,
        )


def test_picture_display_runtime_collectors_build_tree_and_correlate_placeholders() -> None:
    local_nested = SingleModule(header=_header("LocalNested"), moduledef=_composite_moduledef())
    local_type = ModuleTypeDef(
        name="LocalType",
        origin_file="Root.s",
        origin_lib="root",
        moduledef=_composite_moduledef(),
        submodules=[local_nested],
    )
    dep_child = SingleModule(header=_header("DepChild"), moduledef=_composite_moduledef())
    dep_type = ModuleTypeDef(
        name="DepType",
        origin_file="Dep.s",
        origin_lib="DepLib",
        moduledef=_composite_moduledef(),
        submodules=[
            dep_child,
            ModuleTypeInstance(header=_header("Recursive"), moduletype_name="DepType"),
        ],
    )
    external_instance = ModuleTypeInstance(header=_header("DepInst"), moduletype_name="DepType")
    unresolved_instance = ModuleTypeInstance(header=_header("MissingInst"), moduletype_name="MissingType")
    frame = FrameModule(
        header=_header("Frame"),
        moduledef=_composite_moduledef(),
        submodules=[external_instance, unresolved_instance],
    )
    local_instance = ModuleTypeInstance(header=_header("LocalInst"), moduletype_name="LocalType")
    base_picture = engine.BasePicture(
        header=_header("Root"),
        name="Root",
        position=(0.0, 0.0, 0.0, 1.0, 1.0),
        moduledef=_composite_moduledef(),
        origin_file="Root.s",
        origin_lib="root",
        moduletype_defs=[local_type],
        submodules=[local_instance, frame],
    )
    graph = engine.ProjectGraph()
    graph.moduletype_defs = {("deplib", "deptype", "dep.s"): dep_type}

    placeholders = picture_display_path_runtime.collect_concrete_composite_placeholders(base_picture, graph=graph)
    correlated = picture_display_path_runtime.correlate_composite_records(
        base_picture,
        tuple(
            GraphicsCompositeRecord(
                record_index=index, record_start_line=index, record_end_line=index + 1, family_code="5"
            )
            for index in range(1, len(placeholders) + 2)
        ),
        graph=graph,
    )
    runtime_tree = picture_display_path_runtime.build_runtime_tree(base_picture, graph=graph)

    assert [placeholder.module_path for placeholder in placeholders] == [
        ("Root", "Frame", "DepInst", "DepChild"),
        ("Root", "Frame", "DepInst"),
        ("Root", "Frame"),
        ("Root", "LocalType", "LocalNested"),
        ("Root", "LocalType"),
        ("Root",),
    ]
    assert placeholders[3].resolution_module_path == ("Root", "LocalInst", "LocalNested")
    assert placeholders[3].resolution_parent_step_adjustment == -1
    assert placeholders[4].resolution_module_path == ("Root", "LocalInst")
    assert correlated[-1].declaring_module_path == ("Root",)
    assert [occurrence.record_index for occurrence in correlated] == list(range(1, len(placeholders) + 1))

    dep_inst_node = picture_display_path_runtime.find_node(runtime_tree, ("Root", "Frame", "DepInst"))
    missing_node = picture_display_path_runtime.find_node(runtime_tree, ("Root", "Frame", "MissingInst"))

    assert dep_inst_node is not None
    assert dep_inst_node.resolved_moduletype_name == "DepType"
    assert [child.name for child in dep_inst_node.children] == ["DepChild", "Recursive"]
    assert missing_node is not None
    assert missing_node.resolved_moduletype_name is None


def test_picture_display_runtime_guard_branches_cover_invalid_template_shapes_and_originless_cases() -> None:
    invalid_child = SingleModule(
        header=_header("InvalidChild"),
        moduledef=SimpleNamespace(graph_objects=[SimpleNamespace(type=None), SimpleNamespace(type="NotComposite")]),
        submodules=[object()],
    )
    local_type = ModuleTypeDef(
        name="LocalType",
        moduledef=SimpleNamespace(graph_objects=[SimpleNamespace(type=None), SimpleNamespace(type="NotComposite")]),
        submodules=[object(), invalid_child],
    )
    base_picture = engine.BasePicture(
        header=_header("Root"),
        name="Root",
        position=(0.0, 0.0, 0.0, 1.0, 1.0),
        moduledef=SimpleNamespace(graph_objects=()),
        moduletype_defs=[local_type, local_type],
        submodules=[ModuleTypeInstance(header=_header("LocalInst"), moduletype_name="LocalType")],
    )

    placeholders = picture_display_path_runtime.collect_concrete_composite_placeholders(base_picture, graph=None)
    candidates = picture_display_path_runtime._candidate_moduletype_defs(base_picture, graph=None)

    nested_local_type = ModuleTypeDef(
        name="NestedLocalType",
        moduledef=SimpleNamespace(graph_objects=()),
        submodules=[
            SingleModule(
                header=_header("NestedParent"),
                moduledef=SimpleNamespace(graph_objects=[]),
                submodules=[SingleModule(header=_header("NestedLeaf"), moduledef=SimpleNamespace(graph_objects=[]))],
            )
        ],
    )
    nested_picture = engine.BasePicture(
        header=_header("NestedRoot"),
        name="NestedRoot",
        position=(0.0, 0.0, 0.0, 1.0, 1.0),
        moduledef=ModuleDef(),
        moduletype_defs=[nested_local_type],
        submodules=[ModuleTypeInstance(header=_header("NestedInst"), moduletype_name="NestedLocalType")],
    )

    assert placeholders == ()
    assert candidates == (local_type,)
    assert picture_display_path_runtime._is_local_moduletype_def(base_picture, local_type) is True
    assert picture_display_path_runtime._same_origin_file_stem(None, "Root.s") is True
    assert picture_display_path_runtime._file_stem_casefold(None) is None
    assert picture_display_path_runtime.collect_concrete_composite_placeholders(nested_picture, graph=None) == ()


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


def test_loader_lookup_prefers_requester_branch_without_contextual_callback(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    program_dir = tmp_path / "libs" / "BranchA" / "Program"
    same_branch_lib = tmp_path / "libs" / "BranchA" / "Shared"
    other_branch_lib = tmp_path / "libs" / "BranchB" / "Shared"
    abb_lib = tmp_path / "AbbLib"
    for path in (program_dir, same_branch_lib, other_branch_lib, abb_lib):
        path.mkdir(parents=True, exist_ok=True)

    local_code = same_branch_lib / "Support.s"
    local_deps = same_branch_lib / "Support.l"
    remote_code = other_branch_lib / "Support.s"
    remote_deps = other_branch_lib / "Support.l"
    for path, text in (
        (local_code, "local"),
        (local_deps, "local deps"),
        (remote_code, "remote"),
        (remote_deps, "remote deps"),
    ):
        path.write_text(text, encoding="utf-8")

    loader = _make_loader(monkeypatch, program_dir, scan_root_only=False)
    loader.other_lib_dirs = [other_branch_lib, same_branch_lib]
    loader.abb_lib_dir = abb_lib
    loader.contextual_lookup = None

    assert loader._find_code_with_context("Support", requester_dir=program_dir) == local_code
    assert loader._find_deps_with_context("Support", requester_dir=program_dir) == local_deps


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
