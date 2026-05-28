# pyright: reportMissingParameterType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportUnknownVariableType=false

"""Tests for app analysis project loading and AST cache behavior."""

from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from sattline_parser.models.ast_model import (
    BasePicture,
    DataType,
    Equation,
    ModuleCode,
    ModuleHeader,
    Simple_DataType,
    Variable,
)
from sattlint import app_analysis
from sattlint import constants as const
from sattlint.analyzers.variables import IssueKind, analyze_variables
from tests.helpers.app_projects import build_mini_project_context


def test_load_project_returns_cached_project_without_building_loader(monkeypatch):
    cached_project = ("bp-cached", SimpleNamespace())
    seen_cache_dirs: list[Path] = []
    validate_calls: list[tuple[object, bool]] = []

    class FakeCache:
        def __init__(self, cache_dir):
            self.cache_dir = cache_dir
            seen_cache_dirs.append(cache_dir)

        def load(self, key):
            assert key == "cache-key"
            return {"project": cached_project}

        def validate(self, payload, *, fast=False):
            validate_calls.append((payload, fast))
            return True

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
    assert validate_calls == [({"project": cached_project}, False)]


def test_load_project_rebuilds_when_cached_project_is_invalid(monkeypatch):
    cached_project = ("bp-cached", SimpleNamespace())
    loader_calls: list[dict[str, object]] = []
    save_calls: list[tuple[str, dict[str, object]]] = []

    class FakeCache:
        def __init__(self, cache_dir):
            self.cache_dir = cache_dir

        def load(self, key):
            assert key == "cache-key"
            return {"project": cached_project, "files": {"programs/TargetA.s": (1, 1)}}

        def validate(self, payload, *, fast=False):
            assert payload["project"] == cached_project
            assert fast is False
            return False

        def save(self, key, **kwargs):
            save_calls.append((key, kwargs))

    class FakeLoader:
        def __init__(self, **kwargs):
            loader_calls.append(kwargs)

        def resolve(self, target_name, strict=False):
            assert target_name == "TargetA"
            assert strict is False
            return SimpleNamespace(
                ast_by_name={"TargetA": SimpleNamespace(header=SimpleNamespace(name="TargetA"))},
                missing=[],
                warnings=[],
                source_files={Path("programs/TargetA.s")},
            )

        def _find_deps_with_context(self, target_name, requester_dir):
            return None

        def _read_deps(self, deps_path):
            return []

        def _flush_lookup_cache(self):
            return None

    monkeypatch.setattr(app_analysis, "ASTCache", FakeCache)
    monkeypatch.setattr(app_analysis.engine_module, "SattLineProjectLoader", FakeLoader)
    monkeypatch.setattr(
        app_analysis.engine_module,
        "merge_project_basepicture",
        lambda root_bp, _graph: ("bp-fresh", root_bp.header.name),
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
        get_cache_dir_fn=lambda: Path("cache-dir"),
    )

    saved_bp, saved_graph = result
    assert saved_bp == ("bp-fresh", "TargetA")
    assert getattr(saved_graph, "source_files", None) == {Path("programs/TargetA.s")}
    assert len(loader_calls) == 1
    assert len(save_calls) == 1
    assert save_calls[0][0] == "cache-key"
    saved_project, cached_graph = cast(tuple[object, object], save_calls[0][1]["project"])
    assert saved_project == ("bp-fresh", "TargetA")
    assert getattr(cached_graph, "source_files", None) == {Path("programs/TargetA.s")}
    assert save_calls[0][1]["files"] == {Path("programs/TargetA.s")}


def test_load_project_raises_target_load_error_when_root_program_missing(monkeypatch):
    loader_kwargs: dict[str, object] = {}

    class FakeCache:
        def __init__(self, cache_dir):
            self.cache_dir = cache_dir

        def load(self, key):
            return None

        def save(self, key, **kwargs):
            pytest.fail("cache should not be saved when root program is missing")

    class FakeLoader:
        def __init__(self, **kwargs):
            loader_kwargs.update(kwargs)
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

        def _flush_lookup_cache(self):
            return None

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
    assert callable(loader_kwargs.get("status_update_fn"))


def test_load_program_ast_raises_when_program_was_not_parsed(monkeypatch):
    class FakeLoader:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def resolve(self, program_name, strict=False):
            return SimpleNamespace(ast_by_name={"Other": "bp-other"})

        def _flush_lookup_cache(self):
            return None

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


def test_load_project_parses_portable_mini_project(tmp_path):
    context = build_mini_project_context(tmp_path)

    project_bp, graph = app_analysis.load_project(
        cast(dict[str, object], context["cfg"]),
        use_cache=False,
        get_cache_dir_fn=lambda: tmp_path / "cache-dir",
    )

    assert project_bp.header.name == "BasePicture"
    assert context["target_name"] in graph.ast_by_name
    assert cast(Path, context["target_file"]).resolve() in graph.source_files


def test_load_project_library_target_includes_configured_reverse_consumers(monkeypatch):
    save_calls: list[tuple[str, dict[str, object]]] = []
    visit_calls: list[tuple[str, Path, bool]] = []

    class FakeCache:
        def __init__(self, cache_dir):
            self.cache_dir = cache_dir

        def load(self, key):
            assert key == "cache-key"
            return None

        def save(self, key, **kwargs):
            save_calls.append((key, kwargs))

    root_bp = SimpleNamespace(
        header=SimpleNamespace(name="LibraryTarget"),
        origin_file="LibraryTarget.s",
    )

    class FakeLoader:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def resolve(self, target_name, strict=False):
            assert target_name == "LibraryTarget"
            assert strict is False
            return SimpleNamespace(
                ast_by_name={target_name: root_bp},
                missing=[],
                warnings=[],
                source_files={Path("ProjectLib/LibraryTarget.s")},
            )

        def _find_deps_with_context(self, target_name, requester_dir):
            mapping = {
                "LibraryTarget": None,
                "ConsumerTarget": Path("ProjectLib/ConsumerTarget.l"),
                "OtherTarget": Path("programs/OtherTarget.l"),
            }
            return mapping.get(target_name)

        def _read_deps(self, deps_path):
            if deps_path == Path("ProjectLib/ConsumerTarget.l"):
                return ["LibraryTarget"]
            if deps_path == Path("programs/OtherTarget.l"):
                return ["Elsewhere"]
            return []

        def _visit(self, name, graph, strict, *, requester_dir, syntax_check=False):
            visit_calls.append((name, requester_dir, syntax_check))
            graph.ast_by_name[name] = SimpleNamespace(header=SimpleNamespace(name=name))
            graph.source_files.add(Path(f"ProjectLib/{name}.s"))

        def _flush_lookup_cache(self):
            return None

    monkeypatch.setattr(app_analysis, "ASTCache", FakeCache)
    monkeypatch.setattr(app_analysis.engine_module, "SattLineProjectLoader", FakeLoader)
    monkeypatch.setattr(
        app_analysis.engine_module,
        "merge_project_basepicture",
        lambda bp, graph: (bp.header.name, tuple(sorted(graph.ast_by_name))),
    )

    project_bp, graph = app_analysis.load_project(
        {
            "program_dir": "programs",
            "other_lib_dirs": ["ProjectLib"],
            "ABB_lib_dir": "abb",
            "mode": "draft",
            "scan_root_only": False,
            "debug": False,
            "analyzed_programs_and_libraries": ["LibraryTarget", "ConsumerTarget", "OtherTarget"],
        },
        cache_key_for_target_fn=lambda _cfg, _target: "cache-key",
        get_cache_dir_fn=lambda: Path("cache-dir"),
    )

    assert project_bp == ("LibraryTarget", ("ConsumerTarget", "LibraryTarget"))
    assert sorted(graph.ast_by_name) == ["ConsumerTarget", "LibraryTarget"]
    assert visit_calls == [("ConsumerTarget", Path("ProjectLib"), False)]
    assert save_calls[0][0] == "cache-key"


def test_load_project_library_target_includes_workspace_reverse_consumers(monkeypatch, tmp_path):
    save_calls: list[tuple[str, dict[str, object]]] = []
    visit_calls: list[tuple[str, Path, bool]] = []

    programs_dir = tmp_path / "programs"
    project_lib_dir = tmp_path / "ProjectLib"
    programs_dir.mkdir()
    project_lib_dir.mkdir()
    (programs_dir / "ProgramConsumer.l").write_text("LibraryTarget\n", encoding="utf-8")

    class FakeCache:
        def __init__(self, cache_dir):
            self.cache_dir = cache_dir

        def load(self, key):
            assert key == "cache-key"
            return None

        def save(self, key, **kwargs):
            save_calls.append((key, kwargs))

    root_bp = SimpleNamespace(
        header=SimpleNamespace(name="LibraryTarget"),
        origin_file="LibraryTarget.s",
    )

    class FakeLoader:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def resolve(self, target_name, strict=False):
            assert target_name == "LibraryTarget"
            assert strict is False
            return SimpleNamespace(
                ast_by_name={target_name: root_bp},
                missing=[],
                warnings=[],
                source_files={project_lib_dir / "LibraryTarget.s"},
            )

        def _find_deps_with_context(self, target_name, requester_dir):
            if target_name == "LibraryTarget":
                return None
            return requester_dir / f"{target_name}.l"

        def _read_deps(self, deps_path):
            return [line.strip() for line in deps_path.read_text(encoding="utf-8").splitlines() if line.strip()]

        def _visit(self, name, graph, strict, *, requester_dir, syntax_check=False):
            visit_calls.append((name, requester_dir, syntax_check))
            graph.ast_by_name[name] = SimpleNamespace(header=SimpleNamespace(name=name))
            graph.source_files.add(requester_dir / f"{name}.s")

        def _flush_lookup_cache(self):
            return None

    monkeypatch.setattr(app_analysis, "ASTCache", FakeCache)
    monkeypatch.setattr(app_analysis.engine_module, "SattLineProjectLoader", FakeLoader)
    monkeypatch.setattr(
        app_analysis.engine_module,
        "merge_project_basepicture",
        lambda bp, graph: (bp.header.name, tuple(sorted(graph.ast_by_name))),
    )

    project_bp, graph = app_analysis.load_project(
        {
            "program_dir": str(programs_dir),
            "other_lib_dirs": [str(project_lib_dir)],
            "ABB_lib_dir": str(tmp_path / "abb"),
            "mode": "draft",
            "scan_root_only": False,
            "debug": False,
            "analyzed_programs_and_libraries": ["LibraryTarget"],
        },
        cache_key_for_target_fn=lambda _cfg, _target: "cache-key",
        get_cache_dir_fn=lambda: tmp_path / "cache-dir",
    )

    assert project_bp == ("LibraryTarget", ("LibraryTarget", "ProgramConsumer"))
    assert sorted(graph.ast_by_name) == ["LibraryTarget", "ProgramConsumer"]
    assert visit_calls == [("ProgramConsumer", programs_dir, False)]
    assert save_calls[0][0] == "cache-key"


def test_load_project_library_target_workspace_program_usage_suppresses_unused_datatype_field(monkeypatch, tmp_path):
    programs_dir = tmp_path / "programs"
    project_lib_dir = tmp_path / "ProjectLib"
    programs_dir.mkdir()
    project_lib_dir.mkdir()
    (programs_dir / "ProgramConsumer.l").write_text("LibraryTarget\n", encoding="utf-8")

    def _hdr(name: str) -> ModuleHeader:
        return ModuleHeader(name=name, invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0))

    def _varref(name: str) -> dict[str, str]:
        return {const.KEY_VAR_NAME: name}

    library_datatype = DataType(
        name="ApplOpTxtType",
        description=None,
        datecode=None,
        var_list=[
            Variable(name="LSH", datatype=Simple_DataType.STRING),
            Variable(name="DrainPipe", datatype=Simple_DataType.STRING),
        ],
        origin_file="LibraryTarget.s",
        origin_lib="LibraryTarget",
    )
    root_bp = BasePicture(
        header=_hdr("LibraryTarget"),
        datatype_defs=[library_datatype],
        moduletype_defs=[],
        localvariables=[],
        submodules=[],
        modulecode=None,
        moduledef=None,
        origin_file="LibraryTarget.s",
        origin_lib="LibraryTarget",
    )
    program_bp = BasePicture(
        header=_hdr("ProgramConsumer"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[
            Variable(name="OPText", datatype="ApplOpTxtType"),
            Variable(name="Sink", datatype=Simple_DataType.STRING),
        ],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="ReadField",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[(const.KEY_ASSIGN, _varref("Sink"), _varref("OPText.LSH"))],
                )
            ],
            sequences=[],
        ),
        moduledef=None,
        origin_file="ProgramConsumer.s",
        origin_lib="Programs",
    )

    class FakeCache:
        def __init__(self, cache_dir):
            self.cache_dir = cache_dir

        def load(self, key):
            assert key == "cache-key"
            return None

        def save(self, key, **kwargs):
            assert key == "cache-key"

    class FakeLoader:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def resolve(self, target_name, strict=False):
            assert target_name == "LibraryTarget"
            assert strict is False
            return SimpleNamespace(
                ast_by_name={target_name: root_bp},
                missing=[],
                warnings=[],
                source_files={project_lib_dir / "LibraryTarget.s"},
            )

        def _find_deps_with_context(self, target_name, requester_dir):
            if target_name == "LibraryTarget":
                return None
            return requester_dir / f"{target_name}.l"

        def _read_deps(self, deps_path):
            return [line.strip() for line in deps_path.read_text(encoding="utf-8").splitlines() if line.strip()]

        def _visit(self, name, graph, strict, *, requester_dir, syntax_check=False):
            assert name == "ProgramConsumer"
            graph.ast_by_name[name] = program_bp
            graph.source_files.add(requester_dir / f"{name}.s")

        def _flush_lookup_cache(self):
            return None

    def _merge_project_basepicture(bp, graph):
        consumer_bp = graph.ast_by_name.get("ProgramConsumer")
        return BasePicture(
            header=bp.header,
            datatype_defs=bp.datatype_defs,
            moduletype_defs=bp.moduletype_defs,
            localvariables=[] if consumer_bp is None else consumer_bp.localvariables,
            submodules=[],
            modulecode=None if consumer_bp is None else consumer_bp.modulecode,
            moduledef=None,
            origin_file=bp.origin_file,
            origin_lib=bp.origin_lib,
        )

    monkeypatch.setattr(app_analysis, "ASTCache", FakeCache)
    monkeypatch.setattr(app_analysis.engine_module, "SattLineProjectLoader", FakeLoader)
    monkeypatch.setattr(app_analysis.engine_module, "merge_project_basepicture", _merge_project_basepicture)

    project_bp, _graph = app_analysis.load_project(
        {
            "program_dir": str(programs_dir),
            "other_lib_dirs": [str(project_lib_dir)],
            "ABB_lib_dir": str(tmp_path / "abb"),
            "mode": "draft",
            "scan_root_only": False,
            "debug": False,
            "analyzed_programs_and_libraries": ["LibraryTarget"],
        },
        cache_key_for_target_fn=lambda _cfg, _target: "cache-key",
        get_cache_dir_fn=lambda: tmp_path / "cache-dir",
    )

    report = analyze_variables(project_bp, analyzed_target_is_library=True)
    unused_fields = {
        issue.field_path
        for issue in report.issues
        if issue.kind is IssueKind.UNUSED_DATATYPE_FIELD and issue.datatype_name == "ApplOpTxtType"
    }

    assert unused_fields == {"DrainPipe"}


def test_force_refresh_ast_clears_cache_entries_and_reloads_all_targets():
    cache_clears: list[str] = []
    load_calls: list[tuple[str, bool, bool]] = []
    lines: list[str] = []

    class FakeCache:
        def __init__(self, cache_dir):
            self.cache_dir = cache_dir

        def clear(self, key):
            cache_clears.append(key)

    original_emit_output = app_analysis.emit_output
    app_analysis.emit_output = lambda message: lines.append(message)

    try:
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
    finally:
        app_analysis.emit_output = original_emit_output

    assert cache_clears == ["key:TargetA", "key:TargetB"]
    assert load_calls == [("TargetA", False, False), ("TargetB", False, False)]
    assert any("Refreshing AST caches for 2 target(s)..." in line for line in lines)
    assert any("Refreshing AST cache for TargetA... (1/2)" in line for line in lines)
    assert any("Refreshing AST cache for TargetB... (2/2)" in line for line in lines)
    assert sum(1 for line in lines if line == "OK AST cache refreshed") == 2
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
            # fast_cache_validation=True → validate is always called with fast=True.
            # "Fresh" is the only cache entry that passes validation.
            return fast is True and cached.get("name") == "Fresh"

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
    assert any("Refreshing AST caches for 4 target(s)..." in line for line in lines)
    assert any("Checking AST cache for Fresh... (1/4)" in line for line in lines)
    assert any("Checking AST cache for Stale... (2/4)" in line for line in lines)
    assert any("Checking AST cache for Old... (3/4)" in line for line in lines)
    assert any("Checking AST cache for Broken... (4/4)" in line for line in lines)
    assert any("Checking AST cache for Fresh..." in line for line in lines)
    assert any("AST cache OK" in line for line in lines)
    assert any("AST cache stale; rebuilding" in line for line in lines)
    assert any("AST cache missing file manifest; rebuilding" in line for line in lines)
    assert any("AST cache missing; building" in line for line in lines)
    assert any("AST cache updated" in line for line in lines)
    assert any("Failed to build AST cache for Broken: boom" in line for line in lines)


def test_ensure_ast_cache_slow_path_passes_fast_false_to_validate(monkeypatch):
    """When fast_cache_validation is False, validate() must receive fast=False (full stat sweep)."""
    validate_fast_args: list[bool] = []

    class FakeCache:
        def __init__(self, cache_dir):
            self.cache_dir = cache_dir

        def load(self, key):
            if key == "key:Ok":
                return {"name": "Ok", "files": ["x"]}
            return None

        def validate(self, cached, fast=False):
            validate_fast_args.append(fast)
            return True

    lines: list[str] = []
    monkeypatch.setattr(app_analysis, "emit_output", lambda message: lines.append(message))

    ok = app_analysis.ensure_ast_cache(
        {
            "analyzed_programs_and_libraries": ["Ok"],
            "fast_cache_validation": False,
        },
        cache_key_for_target_fn=lambda _cfg, target_name: f"key:{target_name}",
        load_project_fn=cast(Any, lambda *a, **kw: pytest.fail("should not rebuild")),
        ast_cache_cls=cast(Any, FakeCache),
        get_cache_dir_fn=lambda: Path("cache-dir"),
    )

    assert ok is True
    assert validate_fast_args == [False], (
        "validate() must be called with fast=False when fast_cache_validation is False"
    )
    assert any("AST cache OK" in line for line in lines)


def test_ensure_ast_cache_fast_path_passes_fast_true_to_validate_when_manifest_present(monkeypatch):
    """When fast_cache_validation is True and manifest is present, validate() must receive fast=True."""
    validate_fast_args: list[bool] = []

    class FakeCache:
        def __init__(self, cache_dir):
            self.cache_dir = cache_dir

        def load(self, key):
            if key == "key:Ok":
                return {"name": "Ok", "files": ["x"]}
            return None

        def validate(self, cached, fast=False):
            validate_fast_args.append(fast)
            return True

    lines: list[str] = []
    monkeypatch.setattr(app_analysis, "emit_output", lambda message: lines.append(message))

    ok = app_analysis.ensure_ast_cache(
        {
            "analyzed_programs_and_libraries": ["Ok"],
            "fast_cache_validation": True,
        },
        cache_key_for_target_fn=lambda _cfg, target_name: f"key:{target_name}",
        load_project_fn=cast(Any, lambda *a, **kw: pytest.fail("should not rebuild")),
        ast_cache_cls=cast(Any, FakeCache),
        get_cache_dir_fn=lambda: Path("cache-dir"),
    )

    assert ok is True
    assert validate_fast_args == [True], (
        "validate() must be called with fast=True when fast_cache_validation=True and manifest is present"
    )
