# pyright: reportMissingParameterType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportUnknownVariableType=false

"""Tests for app analysis project loading and AST cache behavior."""

import json
import pickle
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
from sattlint.cache import ANALYSIS_REPORT_CACHE_VERSION, AnalysisReportCache, compute_analysis_report_cache_key
from tests.helpers.app_projects import build_mini_project_context


def test_load_project_returns_cached_project_without_building_loader(monkeypatch):
    cached_graph = SimpleNamespace()
    cached_root = SimpleNamespace(header=SimpleNamespace(name="TargetA"))
    seen_cache_dirs: list[Path] = []
    validate_calls: list[tuple[str, bool]] = []
    merge_calls: list[tuple[object, object]] = []
    cached_payload = {"project": (cached_root, cached_graph)}

    class FakeCache:
        def __init__(self, cache_dir):
            self.cache_dir = cache_dir
            seen_cache_dirs.append(cache_dir)

        def load(self, key):
            assert key == "cache-key"
            return cached_payload

        def validate(self, key, *, fast=False):
            validate_calls.append((key, fast))
            return True

        def manifest_paths(self, key):
            assert key == "cache-key"
            return frozenset({Path("programs/TargetA.s")})

    monkeypatch.setattr(app_analysis, "ASTCache", FakeCache)
    monkeypatch.setattr(
        app_analysis.engine_module,
        "SattLineProjectLoader",
        lambda **_kwargs: pytest.fail("loader should not be created"),
    )
    monkeypatch.setattr(
        app_analysis.engine_module,
        "merge_project_basepicture",
        lambda root_bp, graph: merge_calls.append((root_bp, graph)) or ("bp-cached", graph),
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

    assert result == (("bp-cached", cached_graph), cached_graph)
    assert seen_cache_dirs == [Path("custom-cache-dir")]
    assert validate_calls == [("cache-key", False)]
    assert merge_calls == [(cached_root, cached_graph)]
    assert cached_graph.analysis_cache_key == "cache-key"
    assert cached_graph.analysis_manifest_files == frozenset({Path("programs/TargetA.s")})


def test_load_project_rebuilds_when_cached_project_is_invalid(monkeypatch):
    cached_project = ("bp-cached", SimpleNamespace())
    loader_calls: list[dict[str, object]] = []
    save_calls: list[tuple[str, dict[str, object]]] = []

    class FakeCache:
        def __init__(self, cache_dir):
            self.cache_dir = cache_dir

        def load(self, key):
            assert key == "cache-key"
            return {"project": cached_project}

        def validate(self, key, *, fast=False):
            assert key == "cache-key"
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
    assert saved_graph.analysis_cache_key == "cache-key"
    assert saved_graph.analysis_manifest_files == frozenset({Path("programs/TargetA.s")})
    assert len(loader_calls) == 1
    assert len(save_calls) == 1
    assert save_calls[0][0] == "cache-key"
    saved_project, cached_graph = cast(tuple[object, object], save_calls[0][1]["project"])
    assert getattr(saved_project, "header", None).name == "TargetA"
    assert getattr(cached_graph, "source_files", None) == {Path("programs/TargetA.s")}
    assert save_calls[0][1]["files"] == {Path("programs/TargetA.s")}


def test_analysis_report_cache_round_trips_report_payload(tmp_path):
    source_path = tmp_path / "TargetA.s"
    source_path.write_text("code", encoding="utf-8")
    report_cache = AnalysisReportCache(tmp_path)
    key = compute_analysis_report_cache_key("project-key", "variables:unused")
    report = {"issues": ["unused"]}

    assert report_cache.save(key, report=report, files=[source_path]) is True

    loaded = report_cache.load(key)

    assert loaded is not None
    assert report_cache.validate(loaded, fast=False) is True
    assert cast(dict[str, object], loaded)["report"] == report


def test_analysis_report_cache_invalidates_stale_manifest(tmp_path):
    source_path = tmp_path / "TargetA.s"
    source_path.write_text("code", encoding="utf-8")
    report_cache = AnalysisReportCache(tmp_path)
    key = compute_analysis_report_cache_key("project-key", "variables:unused")

    assert report_cache.save(key, report={"issues": []}, files=[source_path]) is True

    source_path.write_text("code changed", encoding="utf-8")
    loaded = report_cache.load(key)

    assert loaded is not None
    assert report_cache.validate(loaded, fast=False) is False


def test_analysis_report_cache_rejects_legacy_payload(tmp_path):
    source_path = tmp_path / "TargetA.s"
    source_path.write_text("code", encoding="utf-8")
    report_cache = AnalysisReportCache(tmp_path)
    key = compute_analysis_report_cache_key("project-key", "variables:unused")
    stat_result = source_path.stat()
    payload = {
        "version": ANALYSIS_REPORT_CACHE_VERSION + 1,
        "report": {"issues": []},
        "files": {str(source_path): (stat_result.st_mtime_ns, stat_result.st_size)},
    }

    with (report_cache.cache_dir / f"{key}.pickle").open("wb") as f:
        pickle.dump(payload, f, protocol=pickle.HIGHEST_PROTOCOL)

    loaded = report_cache.load(key)

    assert loaded is not None
    assert report_cache.validate(loaded, fast=False) is False


def test_analysis_report_cache_save_returns_false_for_unpicklable_report(tmp_path):
    source_path = tmp_path / "TargetA.s"
    source_path.write_text("code", encoding="utf-8")
    report_cache = AnalysisReportCache(tmp_path)
    key = compute_analysis_report_cache_key("project-key", "variables:unused")

    assert report_cache.save(key, report=lambda: None, files=[source_path]) is False

    loaded = report_cache.load(key)
    assert loaded is None or report_cache.validate(loaded, fast=False) is False


def test_load_project_ast_only_refresh_skips_project_merge_and_save(monkeypatch):
    loader_calls: list[dict[str, object]] = []

    class FakeCache:
        def __init__(self, cache_dir):
            self.cache_dir = cache_dir

        def load(self, key):
            assert key == "cache-key"
            return None

        def save(self, key, **kwargs):
            pytest.fail("project cache should not be saved during ast-only refresh")

    root_bp = SimpleNamespace(header=SimpleNamespace(name="TargetA"))
    graph = SimpleNamespace(
        ast_by_name={"TargetA": root_bp},
        missing=[],
        warnings=[],
        source_files={Path("programs/TargetA.s")},
    )

    class FakeLoader:
        def __init__(self, **kwargs):
            loader_calls.append(kwargs)

        def resolve(self, target_name, strict=False):
            assert target_name == "TargetA"
            assert strict is False
            return graph

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
        lambda *_args, **_kwargs: pytest.fail("merge should be skipped during ast-only refresh"),
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
        use_cache=False,
        use_file_ast_cache=False,
        refresh_mode="ast-only",
        cache_key_for_target_fn=lambda _cfg, _target: "cache-key",
        get_cache_dir_fn=lambda: Path("cache-dir"),
    )

    assert result == (root_bp, graph)
    assert loader_calls[0]["refresh_mode"] == "ast-only"
    assert loader_calls[0]["use_file_ast_cache"] is False


@pytest.mark.parametrize(
    ("mode", "code_suffix", "deps_suffix", "graphics_suffix"),
    [
        ("draft", ".s", ".l", ".g"),
        ("official", ".x", ".z", ".y"),
    ],
)
def test_load_project_saves_full_mode_file_family_in_cache_manifest(
    monkeypatch,
    tmp_path,
    mode,
    code_suffix,
    deps_suffix,
    graphics_suffix,
):
    save_calls: list[tuple[str, dict[str, object]]] = []

    programs_dir = tmp_path / "programs"
    abb_dir = tmp_path / "abb"
    programs_dir.mkdir()
    abb_dir.mkdir()

    code_path = programs_dir / f"TargetA{code_suffix}"
    deps_path = programs_dir / f"TargetA{deps_suffix}"
    graphics_path = programs_dir / f"TargetA{graphics_suffix}"
    code_path.write_text("code", encoding="utf-8")
    deps_path.write_text("Dependency\n", encoding="utf-8")
    graphics_path.write_text("graphics", encoding="utf-8")

    root_bp = SimpleNamespace(
        header=SimpleNamespace(name="TargetA"),
        origin_file=code_path.name,
    )

    class FakeCache:
        def __init__(self, cache_dir):
            self.cache_dir = cache_dir

        def load(self, key):
            assert key == "cache-key"
            return None

        def validate(self, key, *, fast=False):
            assert key == "cache-key"
            assert fast is False
            return False

        def manifest_paths(self, key):
            assert key == "cache-key"
            return frozenset()

        def save(self, key, **kwargs):
            save_calls.append((key, kwargs))

    class FakeLoader:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def resolve(self, target_name, strict=False):
            assert target_name == "TargetA"
            assert strict is False
            return SimpleNamespace(
                ast_by_name={target_name: root_bp},
                missing=[],
                warnings=[],
                source_files={code_path},
            )

        def _find_deps_with_context(self, target_name, requester_dir):
            assert target_name == "TargetA"
            assert requester_dir == programs_dir
            return deps_path

        def _read_deps(self, found_deps_path):
            assert found_deps_path == deps_path
            return ["Dependency"]

        def _flush_lookup_cache(self):
            return None

    monkeypatch.setattr(app_analysis, "ASTCache", FakeCache)
    monkeypatch.setattr(app_analysis.engine_module, "SattLineProjectLoader", FakeLoader)
    monkeypatch.setattr(
        app_analysis.engine_module,
        "merge_project_basepicture",
        lambda root_bp, _graph: ("bp-fresh", root_bp.header.name),
    )

    saved_bp, saved_graph = app_analysis.load_project(
        {
            "program_dir": str(programs_dir),
            "other_lib_dirs": [],
            "ABB_lib_dir": str(abb_dir),
            "mode": mode,
            "scan_root_only": False,
            "debug": False,
            "analyzed_programs_and_libraries": ["TargetA"],
        },
        cache_key_for_target_fn=lambda _cfg, _target: "cache-key",
        get_cache_dir_fn=lambda: tmp_path / "cache-dir",
    )

    assert saved_bp == ("bp-fresh", "TargetA")
    assert getattr(saved_graph, "source_files", None) == {code_path}
    assert save_calls == [
        (
            "cache-key",
            {
                "project": (root_bp, saved_graph),
                "files": {code_path, deps_path, graphics_path},
            },
        )
    ]


def test_load_project_raises_target_load_error_when_root_program_missing(monkeypatch):
    loader_kwargs: dict[str, object] = {}

    class FakeCache:
        def __init__(self, cache_dir):
            self.cache_dir = cache_dir

        def load(self, key):
            return None

        def validate(self, key, *, fast=False):
            assert fast is False
            return False

        def manifest_paths(self, key):
            return frozenset()

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

        def validate(self, key, *, fast=False):
            assert key == "cache-key"
            assert fast is False
            return False

        def manifest_paths(self, key):
            assert key == "cache-key"
            return frozenset()

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

        def validate(self, key, *, fast=False):
            assert key == "cache-key"
            assert fast is False
            return False

        def manifest_paths(self, key):
            assert key == "cache-key"
            return frozenset()

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

        def validate(self, key, *, fast=False):
            assert key == "cache-key"
            assert fast is False
            return False

        def manifest_paths(self, key):
            assert key == "cache-key"
            return frozenset()

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
    load_calls: list[tuple[str, bool, bool, str, bool]] = []
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
                lambda _cfg, target_name=None, use_cache=True, use_file_ast_cache=True, refresh_mode="full", collect_stage_timings=False: (
                    load_calls.append(
                        ((target_name or ""), use_cache, use_file_ast_cache, refresh_mode, collect_stage_timings)
                    )
                    or (f"bp-{target_name or ''}", SimpleNamespace())
                ),
            ),
            ast_cache_cls=cast(Any, FakeCache),
            get_cache_dir_fn=lambda: Path("cache-dir"),
        )
    finally:
        app_analysis.emit_output = original_emit_output

    assert cache_clears == ["key:TargetA", "key:TargetB"]
    assert load_calls == [
        ("TargetA", False, False, "ast-only", False),
        ("TargetB", False, False, "ast-only", False),
    ]
    assert any("Refreshing AST caches for 2 target(s)..." in line for line in lines)
    assert any("Refreshing AST cache for TargetA... (1/2)" in line for line in lines)
    assert any("Refreshing AST cache for TargetB... (2/2)" in line for line in lines)
    assert sum(1 for line in lines if line == "OK AST cache refreshed") == 2
    assert result == ("bp-TargetB", SimpleNamespace())


def test_force_refresh_ast_emits_stage_timing_summary_in_debug_mode(monkeypatch):
    lines: list[str] = []
    load_calls: list[tuple[str, str, bool]] = []

    class FakeCache:
        def __init__(self, cache_dir):
            self.cache_dir = cache_dir

        def clear(self, _key):
            return None

    monkeypatch.setattr(app_analysis, "emit_output", lambda message: lines.append(str(message)))

    graph = SimpleNamespace(
        load_stage_timings={"load_or_parse": 1.25, "validate": 0.75, "ast_cache_save": 0.25},
        graphics_load_timings={"validate-graphics-file": 0.4, "picture-display-warnings": 0.1},
    )

    result = app_analysis.force_refresh_ast(
        {
            "analyzed_programs_and_libraries": ["TargetA"],
            "debug": True,
        },
        cache_key_for_target_fn=lambda _cfg, target_name: f"key:{target_name}",
        load_project_fn=cast(
            Any,
            lambda _cfg, target_name=None, use_cache=True, use_file_ast_cache=True, refresh_mode="full", collect_stage_timings=False: (
                load_calls.append((target_name or "", refresh_mode, collect_stage_timings)) or ("bp", graph)
            ),
        ),
        ast_cache_cls=cast(Any, FakeCache),
        get_cache_dir_fn=lambda: Path("cache-dir"),
    )

    assert load_calls == [("TargetA", "ast-only", True)]
    assert any("AST refresh stage totals:" in line for line in lines)
    assert any("graphics=skipped" in line for line in lines)
    assert any("index=skipped" in line for line in lines)
    assert result == ("bp", graph)


def test_force_refresh_ast_collects_stage_timings_and_writes_telemetry_when_enabled(tmp_path, monkeypatch):
    lines: list[str] = []
    load_calls: list[tuple[str, str, bool]] = []

    class FakeCache:
        def __init__(self, cache_dir):
            self.cache_dir = cache_dir

        def clear(self, _key):
            return None

    telemetry_path = tmp_path / "telemetry.jsonl"
    monkeypatch.setattr(app_analysis, "emit_output", lambda message: lines.append(str(message)))
    monkeypatch.setattr(app_analysis.telemetry_module, "get_config_path", lambda: tmp_path / "config.toml")

    graph = SimpleNamespace(
        load_stage_timings={"load_or_parse": 1.25, "validate": 0.75, "ast_cache_save": 0.25},
        graphics_load_timings={"validate-graphics-file": 0.4, "picture-display-warnings": 0.1},
    )

    result = app_analysis.force_refresh_ast(
        {
            "analyzed_programs_and_libraries": ["TargetA"],
            "debug": False,
            "telemetry": {"enabled": True},
        },
        cache_key_for_target_fn=lambda _cfg, target_name: f"key:{target_name}",
        load_project_fn=cast(
            Any,
            lambda _cfg, target_name=None, use_cache=True, use_file_ast_cache=True, refresh_mode="full", collect_stage_timings=False: (
                load_calls.append((target_name or "", refresh_mode, collect_stage_timings)) or ("bp", graph)
            ),
        ),
        ast_cache_cls=cast(Any, FakeCache),
        get_cache_dir_fn=lambda: Path("cache-dir"),
    )

    events = [json.loads(line) for line in telemetry_path.read_text(encoding="utf-8").splitlines()]

    assert load_calls == [("TargetA", "ast-only", True)]
    assert any("AST refresh stage totals:" in line for line in lines)
    assert len(events) == 1
    assert events[0]["kind"] == "sattlint.app.telemetry"
    assert events[0]["operation"] == "ast-refresh"
    assert events[0]["target_name"] == "TargetA"
    assert events[0]["success"] is True
    assert events[0]["payload"]["stage_timings_s"] == {
        "ast_cache_save": 0.25,
        "load_or_parse": 1.25,
        "validate": 0.75,
    }
    assert events[0]["payload"]["stage_timings_ms"] == {
        "ast_cache_save": 250.0,
        "load_or_parse": 1250.0,
        "validate": 750.0,
    }
    assert events[0]["payload"]["stage_bottleneck"] == {
        "kind": "stage",
        "name": "load_or_parse",
        "duration_ms": 1250.0,
    }
    assert events[0]["payload"]["graphics_timings_ms"] == {
        "picture-display-warnings": 100.0,
        "validate-graphics-file": 400.0,
    }
    assert events[0]["payload"]["graphics_bottleneck"] == {
        "kind": "graphics-phase",
        "name": "validate-graphics-file",
        "duration_ms": 400.0,
    }
    assert events[0]["payload"]["bottleneck_kind"] == "stage"
    assert result == ("bp", graph)


def test_ensure_ast_cache_handles_valid_fast_path_rebuilds_and_failures(monkeypatch):
    lines: list[str] = []
    load_calls: list[str] = []

    class FakeCache:
        def __init__(self, cache_dir):
            self.cache_dir = cache_dir

        def load(self, key):
            mapping = {
                "key:Fresh": {"name": "Fresh"},
                "key:Stale": {"name": "Stale"},
                "key:Old": {"name": "Old"},
                "key:Broken": None,
            }
            return mapping[key]

        def has_payload(self, key):
            return self.load(key) is not None

        def has_manifest(self, key):
            return key in {"key:Fresh", "key:Stale"}

        def validate(self, key, fast=False):
            # fast_cache_validation=True → validate is always called with fast=True.
            # "Fresh" is the only cache entry that passes validation.
            return fast is True and key == "key:Fresh"

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

        def has_payload(self, key):
            return key == "key:Ok"

        def has_manifest(self, key):
            return key == "key:Ok"

        def validate(self, key, fast=False):
            assert key == "key:Ok"
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

        def has_payload(self, key):
            return key == "key:Ok"

        def has_manifest(self, key):
            return key == "key:Ok"

        def validate(self, key, fast=False):
            assert key == "key:Ok"
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
