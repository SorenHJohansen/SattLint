# pyright: reportUnknownLambdaType=false, reportUnknownArgumentType=false, reportPrivateUsage=false

"""Tests for app analysis project loading and AST cache behavior."""

import logging
from collections.abc import Callable, Mapping
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest
from sattline_parser.ast import Assignment, VarRef
from sattline_parser.models.ast_model import (
    BasePicture,
    DataType,
    Equation,
    ModuleCode,
    ModuleHeader,
    ScalarDatatype,
    Variable,
)
from sattline_parser.project import LoadValidation

import sattlint.cache as cache_mod
from sattlint.analyzers.datatype_fields import analyze_datatype_fields
from sattlint.analyzers.variables import IssueKind, analyze_variables
from sattlint.application import project as project_application
from sattlint.cache import (
    ANALYSIS_REPORT_CACHE_VERSION,
    AnalysisReportCache,
    ASTCache,
    compute_analysis_report_cache_key,
)
from sattlint.config.types import ConfigDict
from sattlint.core.syntax import CodeMode
from sattlint.models._variable_issues import VariableTargetIssue
from sattlint.models.project_graph import ProjectFailure, ProjectGraph
from sattlint.project import loading as analysis_loading_module
from sattlint.project.loader_config import LoadStageTimingSink
from sattlint.project.parser_adapter import ParserProjectBinding
from tests.helpers import AnalysisGraphStub, NamedObject, named_object
from tests.helpers.app_projects import build_mini_project_context


def test_load_project_returns_cached_project_without_building_loader(monkeypatch: pytest.MonkeyPatch):
    cached_graph = AnalysisGraphStub()
    cached_root = named_object("TargetA")
    seen_cache_dirs: list[Path] = []
    validated_load_calls: list[str] = []
    merge_calls: list[tuple[object, object]] = []
    cached_payload = {"project": (cached_root, cached_graph)}

    class FakeCache:
        def __init__(self, cache_dir: Path) -> None:
            self.cache_dir = cache_dir
            seen_cache_dirs.append(cache_dir)

        def load_validated(self, key: str) -> object | None:
            assert key == "cache-key"
            validated_load_calls.append(key)
            return cached_payload

        def manifest_paths(self, key: str) -> frozenset[Path]:
            assert key == "cache-key"
            return frozenset({Path("programs/TargetA.s")})

    monkeypatch.setattr(project_application, "ASTCache", FakeCache)
    monkeypatch.setattr(
        analysis_loading_module,
        "build_parser_binding",
        lambda *_args, **_kwargs: pytest.fail("loader should not be created"),
    )

    def fake_merge_project_basepicture(root_bp: BasePicture, graph: ProjectGraph) -> object:
        merge_calls.append((root_bp, graph))
        return ("bp-cached", graph)

    monkeypatch.setattr(
        analysis_loading_module,
        "merge_project_basepicture",
        fake_merge_project_basepicture,
    )

    result = project_application.load_project(
        cast(
            ConfigDict,
            {
                "program_dir": "programs",
                "other_lib_dirs": [],
                "ABB_lib_dir": "abb",
                "mode": "draft",
                "debug": False,
                "analyzed_programs_and_libraries": ["TargetA"],
            },
        ),
        cache_key_for_target_fn=lambda _cfg, _target: "cache-key",
        get_cache_dir_fn=lambda: Path("custom-cache-dir"),
    )

    assert result == (("bp-cached", cached_graph), cached_graph)
    assert seen_cache_dirs == [Path("custom-cache-dir")]
    assert validated_load_calls == ["cache-key"]
    assert merge_calls == [(cached_root, cached_graph)]
    assert cached_graph.analysis_cache_key == "cache-key"
    assert cached_graph.analysis_manifest_files == frozenset({Path("programs/TargetA.s")})


def test_load_project_rebuilds_when_cached_project_is_invalid(monkeypatch: pytest.MonkeyPatch):
    loader_calls: list[dict[str, object]] = []
    save_calls: list[tuple[str, dict[str, object]]] = []

    class FakeCache:
        def __init__(self, cache_dir: Path) -> None:
            self.cache_dir = cache_dir

        def load_validated(self, key: str) -> object | None:
            assert key == "cache-key"
            return None

        def save(self, key: str, **kwargs: object) -> None:
            save_calls.append((key, kwargs))

    graph = AnalysisGraphStub(
        ast_by_name={"TargetA": named_object("TargetA")},
        source_files={Path("programs/TargetA.s")},
    )

    def fake_build_parser_binding(
        cfg: Mapping[str, object],
        *,
        parser_cache_dir: Path | None = None,
        status_update_fn: Callable[[str], None] | None = None,
        stage_timing_sink: LoadStageTimingSink | None = None,
        graphics_timing_sink: LoadStageTimingSink | None = None,
    ) -> ParserProjectBinding:
        del cfg
        binding = ParserProjectBinding(
            program_dir=Path("programs"),
            other_lib_dirs=(),
            abb_lib_dir=None,
            mode=CodeMode.DRAFT,
            status_update_fn=status_update_fn,
            stage_timing_sink=stage_timing_sink,
            graphics_timing_sink=graphics_timing_sink,
        )
        loader_calls.append({"binding": binding})
        return binding

    monkeypatch.setattr(project_application, "ASTCache", FakeCache)
    monkeypatch.setattr(analysis_loading_module, "build_parser_binding", fake_build_parser_binding)
    monkeypatch.setattr(analysis_loading_module, "_load_parser_graph", lambda *_args, **_kwargs: graph)
    monkeypatch.setattr(analysis_loading_module, "find_dependency_path", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(analysis_loading_module, "read_dependency_names", lambda *_args, **_kwargs: [])

    def fake_merge_project_basepicture(root_bp: BasePicture, _graph: ProjectGraph) -> object:
        return ("bp-fresh", root_bp.header.name)

    monkeypatch.setattr(
        analysis_loading_module,
        "merge_project_basepicture",
        fake_merge_project_basepicture,
    )

    result = project_application.load_project(
        cast(
            ConfigDict,
            {
                "program_dir": "programs",
                "other_lib_dirs": [],
                "ABB_lib_dir": "abb",
                "mode": "draft",
                "debug": False,
                "analyzed_programs_and_libraries": ["TargetA"],
            },
        ),
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
    saved_project, cached_graph = cast(tuple[NamedObject, object], save_calls[0][1]["project"])
    assert saved_project.header.name == "TargetA"
    assert getattr(cached_graph, "source_files", None) == {Path("programs/TargetA.s")}
    assert save_calls[0][1]["files"] == {Path("programs/TargetA.s")}


def test_iter_loaded_projects_emits_debug_load_summary_when_debug_enabled(monkeypatch: pytest.MonkeyPatch):
    lines: list[str] = []
    project_bp = named_object("TargetA")
    graph = AnalysisGraphStub(
        source_files={Path("programs/TargetA.s"), Path("libs/Dep.l")},
        warnings=["warn"],
        missing=["MissingLib"],
        unavailable_libraries={"ControlLib"},
        load_stage_timings={
            "load_or_parse": 1.25,
            "validate": 0.5,
            "attach_graphics": 0.25,
            "index": 0.1,
        },
        graphics_load_timings={
            "picture-display-warnings": 0.1,
            "validate-graphics-file": 0.4,
        },
    )

    monkeypatch.setattr(project_application, "emit_output", lambda message: lines.append(message))

    loaded = list(
        project_application.iter_loaded_projects(
            cast(ConfigDict, {"debug": True}),
            use_cache=False,
            require_analyzed_targets_fn=lambda _cfg: ["TargetA"],
            load_project_fn=cast(
                Callable[..., tuple[BasePicture, ProjectGraph]], lambda _cfg, **_kwargs: (project_bp, graph)
            ),
        )
    )

    assert loaded == [("TargetA", project_bp, graph)]
    assert any(
        "DEBUG load summary for TargetA: source_files=2, warnings=1, missing=1, unavailable_libraries=1" in line
        for line in lines
    )
    assert any(
        "AST refresh stage totals:" in line and "load_or_parse=1.2500s" in line and "graphics=0.2500s" in line
        for line in lines
    )
    assert any("Graphics load phase totals:" in line and "validate-graphics-file=0.4000s" in line for line in lines)


def test_analysis_report_cache_round_trips_report_payload(tmp_path: Path):
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


def test_analysis_report_cache_invalidates_stale_manifest(tmp_path: Path):
    source_path = tmp_path / "TargetA.s"
    source_path.write_text("code", encoding="utf-8")
    report_cache = AnalysisReportCache(tmp_path)
    key = compute_analysis_report_cache_key("project-key", "variables:unused")

    assert report_cache.save(key, report={"issues": []}, files=[source_path]) is True

    source_path.write_text("code changed", encoding="utf-8")
    loaded = report_cache.load(key)

    assert loaded is not None
    assert report_cache.validate(loaded, fast=False) is False


def test_analysis_report_cache_rejects_legacy_payload(tmp_path: Path):
    source_path = tmp_path / "TargetA.s"
    source_path.write_text("code", encoding="utf-8")
    report_cache = AnalysisReportCache(tmp_path)
    key = compute_analysis_report_cache_key("project-key", "variables:unused")
    stat_result = source_path.stat()
    payload: dict[str, object] = {
        "version": ANALYSIS_REPORT_CACHE_VERSION + 1,
        "report": {"issues": []},
        "files": {str(source_path): (stat_result.st_mtime_ns, stat_result.st_size)},
    }

    cache_mod._save_pickle_payload(report_cache.cache_dir / f"{key}.pickle", payload)

    loaded = report_cache.load(key)

    assert loaded is not None
    assert report_cache.validate(loaded, fast=False) is False


def test_analysis_report_cache_save_returns_false_for_unpicklable_report(tmp_path: Path):
    source_path = tmp_path / "TargetA.s"
    source_path.write_text("code", encoding="utf-8")
    report_cache = AnalysisReportCache(tmp_path)
    key = compute_analysis_report_cache_key("project-key", "variables:unused")

    assert report_cache.save(key, report=lambda: None, files=[source_path]) is False

    loaded = report_cache.load(key)
    assert loaded is None or report_cache.validate(loaded, fast=False) is False


def test_load_project_ast_only_refresh_skips_project_merge_and_save(monkeypatch: pytest.MonkeyPatch):
    loader_calls: list[dict[str, object]] = []

    class FakeCache:
        def __init__(self, cache_dir: Path) -> None:
            self.cache_dir = cache_dir

        def load(self, key: str) -> object | None:
            assert key == "cache-key"
            return None

        def save(self, key: str, **kwargs: object) -> None:
            pytest.fail("project cache should not be saved during ast-only refresh")

    root_bp = named_object("TargetA")
    graph = AnalysisGraphStub(
        ast_by_name={"TargetA": root_bp},
        missing=[],
        warnings=[],
        source_files={Path("programs/TargetA.s")},
    )

    def fake_build_parser_binding(
        cfg: Mapping[str, object],
        *,
        parser_cache_dir: Path | None = None,
        status_update_fn: Callable[[str], None] | None = None,
        stage_timing_sink: LoadStageTimingSink | None = None,
        graphics_timing_sink: LoadStageTimingSink | None = None,
    ) -> ParserProjectBinding:
        del cfg
        return ParserProjectBinding(
            program_dir=Path("programs"),
            other_lib_dirs=(),
            abb_lib_dir=None,
            mode=CodeMode.DRAFT,
            status_update_fn=status_update_fn,
            stage_timing_sink=stage_timing_sink,
            graphics_timing_sink=graphics_timing_sink,
        )

    def fake_load_parser_graph(
        binding: ParserProjectBinding,
        target_name: str,
        *,
        strict: bool,
        lib_names: dict[str, str],
        validate: LoadValidation,
        index_program_view: bool,
    ) -> AnalysisGraphStub:
        loader_calls.append({"validate": validate.value, "index_program_view": index_program_view})
        return graph

    monkeypatch.setattr(project_application, "ASTCache", FakeCache)
    monkeypatch.setattr(analysis_loading_module, "build_parser_binding", fake_build_parser_binding)
    monkeypatch.setattr(analysis_loading_module, "_load_parser_graph", fake_load_parser_graph)
    monkeypatch.setattr(analysis_loading_module, "find_dependency_path", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(analysis_loading_module, "read_dependency_names", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        analysis_loading_module,
        "merge_project_basepicture",
        lambda *_args, **_kwargs: pytest.fail("merge should be skipped during ast-only refresh"),
    )

    result = project_application.load_project(
        cast(
            ConfigDict,
            {
                "program_dir": "programs",
                "other_lib_dirs": [],
                "ABB_lib_dir": "abb",
                "mode": "draft",
                "debug": False,
                "analyzed_programs_and_libraries": ["TargetA"],
            },
        ),
        use_cache=False,
        refresh_mode="ast-only",
        cache_key_for_target_fn=lambda _cfg, _target: "cache-key",
        get_cache_dir_fn=lambda: Path("cache-dir"),
    )

    assert result == (root_bp, graph)
    assert loader_calls == [{"validate": "none", "index_program_view": False}]


@pytest.mark.parametrize(
    ("mode", "code_suffix", "deps_suffix", "graphics_suffix"),
    [
        ("draft", ".s", ".l", ".g"),
        ("official", ".x", ".z", ".y"),
    ],
)
def test_load_project_saves_full_mode_file_family_in_cache_manifest(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    mode: str,
    code_suffix: str,
    deps_suffix: str,
    graphics_suffix: str,
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

    root_bp = named_object("TargetA", origin_file=code_path.name)

    class FakeCache:
        def __init__(self, cache_dir: Path) -> None:
            self.cache_dir = cache_dir

        def load_validated(self, key: str) -> object | None:
            assert key == "cache-key"
            return None

        def manifest_paths(self, key: str) -> frozenset[Path]:
            assert key == "cache-key"
            return frozenset()

        def save(self, key: str, **kwargs: object) -> None:
            save_calls.append((key, kwargs))

    def fake_find_dependency_path(binding: ParserProjectBinding, target_name: str, **_kwargs: object) -> Path | None:
        assert target_name == "TargetA"
        return deps_path

    def fake_read_dependency_names(deps_path_arg: Path) -> list[str]:
        assert deps_path_arg == deps_path
        return ["Dependency"]

    def fake_build_parser_binding(
        cfg: Mapping[str, object],
        *,
        parser_cache_dir: Path | None = None,
        status_update_fn: Callable[[str], None] | None = None,
        stage_timing_sink: LoadStageTimingSink | None = None,
        graphics_timing_sink: LoadStageTimingSink | None = None,
    ) -> ParserProjectBinding:
        del cfg
        return ParserProjectBinding(
            program_dir=Path("programs"),
            other_lib_dirs=(),
            abb_lib_dir=None,
            mode=CodeMode.DRAFT,
            status_update_fn=status_update_fn,
            stage_timing_sink=stage_timing_sink,
            graphics_timing_sink=graphics_timing_sink,
        )

    monkeypatch.setattr(project_application, "ASTCache", FakeCache)
    monkeypatch.setattr(analysis_loading_module, "build_parser_binding", fake_build_parser_binding)
    monkeypatch.setattr(
        analysis_loading_module,
        "_load_parser_graph",
        lambda *_args, **_kwargs: AnalysisGraphStub(ast_by_name={"TargetA": root_bp}, source_files={code_path}),
    )
    monkeypatch.setattr(analysis_loading_module, "find_dependency_path", fake_find_dependency_path)
    monkeypatch.setattr(analysis_loading_module, "read_dependency_names", fake_read_dependency_names)

    def fake_merge_project_basepicture(root_bp: BasePicture, _graph: ProjectGraph) -> object:
        return ("bp-fresh", root_bp.header.name)

    monkeypatch.setattr(
        analysis_loading_module,
        "merge_project_basepicture",
        fake_merge_project_basepicture,
    )

    saved_bp, saved_graph = project_application.load_project(
        cast(
            ConfigDict,
            {
                "program_dir": str(programs_dir),
                "other_lib_dirs": [],
                "ABB_lib_dir": str(abb_dir),
                "mode": mode,
                "debug": False,
                "analyzed_programs_and_libraries": ["TargetA"],
            },
        ),
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


def test_load_project_raises_target_load_error_when_root_program_missing(monkeypatch: pytest.MonkeyPatch):
    loader_kwargs: dict[str, object] = {}

    class FakeCache:
        def __init__(self, cache_dir: Path) -> None:
            self.cache_dir = cache_dir

        def load_validated(self, key: str) -> object | None:
            return None

        def manifest_paths(self, key: str) -> frozenset[Path]:
            return frozenset()

        def save(self, key: str, **kwargs: object) -> None:
            pytest.fail("cache should not be saved when root program is missing")

    def fake_build_parser_binding(
        cfg: Mapping[str, object],
        *,
        parser_cache_dir: Path | None = None,
        status_update_fn: Callable[[str], None] | None = None,
        stage_timing_sink: LoadStageTimingSink | None = None,
        graphics_timing_sink: LoadStageTimingSink | None = None,
    ) -> ParserProjectBinding:
        del cfg
        loader_kwargs.update({"status_update_fn": status_update_fn})
        return ParserProjectBinding(
            program_dir=Path("programs"),
            other_lib_dirs=(),
            abb_lib_dir=None,
            mode=CodeMode.DRAFT,
            status_update_fn=status_update_fn,
            stage_timing_sink=stage_timing_sink,
            graphics_timing_sink=graphics_timing_sink,
        )

    def fake_load_parser_graph(
        binding: ParserProjectBinding,
        target_name: str,
        *,
        strict: bool,
        lib_names: dict[str, str],
        validate: LoadValidation,
        index_program_view: bool,
    ) -> SimpleNamespace:
        return SimpleNamespace(
            ast_by_name={"Dependency": "bp-dependency"},
            missing=["dep parse error"],
            warnings=["dep warning"],
            failures={"dep": ProjectFailure("dep", "dep parse error", line=9, column=3)},
            source_files={Path("programs/Dependency.s")},
        )

    captured: dict[str, object] = {}

    monkeypatch.setattr(project_application, "ASTCache", FakeCache)
    monkeypatch.setattr(project_application, "get_cache_dir", lambda: Path("cache-dir"))
    monkeypatch.setattr(analysis_loading_module, "build_parser_binding", fake_build_parser_binding)
    monkeypatch.setattr(analysis_loading_module, "_load_parser_graph", fake_load_parser_graph)
    monkeypatch.setattr(
        analysis_loading_module, "find_dependency_path", lambda *_args, **_kwargs: Path("programs/TargetA.l")
    )
    monkeypatch.setattr(analysis_loading_module, "read_dependency_names", lambda *_args, **_kwargs: ["Dependency"])

    def fake_error_factory(target_name: str, **kwargs: object) -> Exception:
        captured.update({"target_name": target_name, **kwargs})
        return RuntimeError(f"missing {target_name}")

    with pytest.raises(RuntimeError, match="missing TargetA"):
        project_application.load_project(
            cast(
                ConfigDict,
                {
                    "program_dir": "programs",
                    "other_lib_dirs": ["libs"],
                    "ABB_lib_dir": "abb",
                    "mode": "draft",
                    "debug": True,
                    "analyzed_programs_and_libraries": ["TargetA"],
                },
            ),
            target_load_error_factory=fake_error_factory,
        )

    assert captured == {
        "target_name": "TargetA",
        "resolved": ["Dependency"],
        "missing": ["dep parse error"],
        "warnings": ["dep warning"],
        "direct_dependencies": ["Dependency"],
        "failures": {"dep": ProjectFailure("dep", "dep parse error", line=9, column=3)},
    }
    assert callable(loader_kwargs.get("status_update_fn"))


def test_load_program_ast_raises_when_program_was_not_parsed(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        analysis_loading_module,
        "_load_parser_graph",
        lambda _binding, _program_name, **_kwargs: SimpleNamespace(ast_by_name={"Other": "bp-other"}),
    )

    with pytest.raises(RuntimeError, match="Program 'TargetA' not parsed"):
        project_application.load_program_ast(
            cast(
                ConfigDict,
                {
                    "program_dir": "programs",
                    "other_lib_dirs": [],
                    "ABB_lib_dir": "abb",
                    "mode": "draft",
                    "debug": False,
                },
            ),
            "TargetA",
        )


def test_load_project_parses_portable_mini_project(tmp_path: Path):
    context = build_mini_project_context(tmp_path)

    project_bp, graph = project_application.load_project(
        cast(ConfigDict, context["cfg"]),
        use_cache=False,
        get_cache_dir_fn=lambda: tmp_path / "cache-dir",
    )

    assert project_bp.header.name == "BasePicture"
    assert context["target_name"] in graph.ast_by_name
    assert cast(Path, context["target_file"]).resolve() in graph.source_files


def test_load_project_library_target_includes_configured_reverse_consumers(monkeypatch: pytest.MonkeyPatch):
    save_calls: list[tuple[str, dict[str, object]]] = []
    visit_calls: list[tuple[str, Path, bool]] = []

    class FakeCache:
        def __init__(self, cache_dir: Path) -> None:
            self.cache_dir = cache_dir

        def load_validated(self, key: str) -> object | None:
            assert key == "cache-key"
            return None

        def manifest_paths(self, key: str) -> frozenset[Path]:
            assert key == "cache-key"
            return frozenset()

        def save(self, key: str, **kwargs: object) -> None:
            save_calls.append((key, kwargs))

    root_bp = named_object("LibraryTarget", origin_file="LibraryTarget.s")

    def fake_find_dependency_path(binding: ParserProjectBinding, target_name: str, **_kwargs: object) -> Path | None:
        mapping = {
            "LibraryTarget": None,
            "ConsumerTarget": Path("ProjectLib/ConsumerTarget.l"),
            "OtherTarget": Path("programs/OtherTarget.l"),
        }
        return mapping.get(target_name)

    def fake_read_dependency_names(deps_path: Path) -> list[str]:
        if deps_path == Path("ProjectLib/ConsumerTarget.l"):
            return ["LibraryTarget"]
        if deps_path == Path("programs/OtherTarget.l"):
            return ["Elsewhere"]
        return []

    def fake_build_parser_binding(
        cfg: Mapping[str, object],
        *,
        parser_cache_dir: Path | None = None,
        status_update_fn: Callable[[str], None] | None = None,
        stage_timing_sink: LoadStageTimingSink | None = None,
        graphics_timing_sink: LoadStageTimingSink | None = None,
    ) -> ParserProjectBinding:
        del cfg
        return ParserProjectBinding(
            program_dir=Path("programs"),
            other_lib_dirs=(),
            abb_lib_dir=None,
            mode=CodeMode.DRAFT,
            status_update_fn=status_update_fn,
            stage_timing_sink=stage_timing_sink,
            graphics_timing_sink=graphics_timing_sink,
        )

    def fake_visit_targets_into_graph(
        binding: ParserProjectBinding,
        graph: AnalysisGraphStub,
        targets: list[tuple[str, Path | None]],
        *,
        lib_names: dict[str, str],
    ) -> None:
        del binding, lib_names
        for target_name, requester_dir in targets:
            assert requester_dir is not None
            visit_calls.append((target_name, requester_dir, False))
            graph.ast_by_name[target_name] = named_object(target_name)
            graph.source_files.add(Path(f"ProjectLib/{target_name}.s"))

    monkeypatch.setattr(project_application, "ASTCache", FakeCache)
    monkeypatch.setattr(analysis_loading_module, "build_parser_binding", fake_build_parser_binding)
    monkeypatch.setattr(
        analysis_loading_module,
        "_load_parser_graph",
        lambda *_args, **_kwargs: AnalysisGraphStub(
            ast_by_name={"LibraryTarget": root_bp},
            source_files={Path("ProjectLib/LibraryTarget.s")},
        ),
    )
    monkeypatch.setattr(analysis_loading_module, "find_dependency_path", fake_find_dependency_path)
    monkeypatch.setattr(analysis_loading_module, "read_dependency_names", fake_read_dependency_names)
    monkeypatch.setattr(analysis_loading_module, "_visit_targets_into_graph", fake_visit_targets_into_graph)

    def fake_merge_project_basepicture(bp: BasePicture, graph: ProjectGraph) -> object:
        return (bp.header.name, tuple(sorted(graph.ast_by_name)))

    monkeypatch.setattr(
        analysis_loading_module,
        "merge_project_basepicture",
        fake_merge_project_basepicture,
    )

    project_bp, graph = project_application.load_project(
        cast(
            ConfigDict,
            {
                "program_dir": "programs",
                "other_lib_dirs": ["ProjectLib"],
                "ABB_lib_dir": "abb",
                "mode": "draft",
                "debug": False,
                "analyzed_programs_and_libraries": ["LibraryTarget", "ConsumerTarget", "OtherTarget"],
            },
        ),
        cache_key_for_target_fn=lambda _cfg, _target: "cache-key",
        get_cache_dir_fn=lambda: Path("cache-dir"),
    )

    assert project_bp == ("LibraryTarget", ("ConsumerTarget", "LibraryTarget"))
    assert sorted(graph.ast_by_name) == ["ConsumerTarget", "LibraryTarget"]
    assert visit_calls == [("ConsumerTarget", Path("ProjectLib"), False)]
    assert save_calls[0][0] == "cache-key"


def test_load_project_library_target_includes_workspace_reverse_consumers(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    save_calls: list[tuple[str, dict[str, object]]] = []
    visit_calls: list[tuple[str, Path, bool]] = []

    programs_dir = tmp_path / "programs"
    project_lib_dir = tmp_path / "ProjectLib"
    abb_dir = tmp_path / "abb"
    programs_dir.mkdir()
    project_lib_dir.mkdir()
    abb_dir.mkdir()
    (programs_dir / "ProgramConsumer.l").write_text("LibraryTarget\n", encoding="utf-8")
    (programs_dir / "DeepConsumer.l").write_text("ProgramConsumer\n", encoding="utf-8")
    (abb_dir / "AbbConsumer.l").write_text("LibraryTarget\n", encoding="utf-8")

    class FakeCache:
        def __init__(self, cache_dir: Path) -> None:
            self.cache_dir = cache_dir

        def load_validated(self, key: str) -> object | None:
            assert key == "cache-key"
            return None

        def manifest_paths(self, key: str) -> frozenset[Path]:
            assert key == "cache-key"
            return frozenset()

        def save(self, key: str, **kwargs: object) -> None:
            save_calls.append((key, kwargs))

    root_bp = named_object("LibraryTarget", origin_file="LibraryTarget.s")

    def fake_find_dependency_path(binding: ParserProjectBinding, target_name: str, **_kwargs: object) -> Path | None:
        if target_name == "LibraryTarget":
            return None
        return programs_dir / f"{target_name}.l"

    def fake_read_dependency_names(deps_path: Path) -> list[str]:
        return [line.strip() for line in deps_path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def fake_build_parser_binding(
        cfg: Mapping[str, object],
        *,
        parser_cache_dir: Path | None = None,
        status_update_fn: Callable[[str], None] | None = None,
        stage_timing_sink: LoadStageTimingSink | None = None,
        graphics_timing_sink: LoadStageTimingSink | None = None,
    ) -> ParserProjectBinding:
        del cfg
        return ParserProjectBinding(
            program_dir=Path("programs"),
            other_lib_dirs=(),
            abb_lib_dir=None,
            mode=CodeMode.DRAFT,
            status_update_fn=status_update_fn,
            stage_timing_sink=stage_timing_sink,
            graphics_timing_sink=graphics_timing_sink,
        )

    def fake_visit_targets_into_graph(
        binding: ParserProjectBinding,
        graph: AnalysisGraphStub,
        targets: list[tuple[str, Path | None]],
        *,
        lib_names: dict[str, str],
    ) -> None:
        del binding, lib_names
        for target_name, requester_dir in targets:
            assert requester_dir is not None
            visit_calls.append((target_name, requester_dir, False))
            graph.ast_by_name[target_name] = named_object(target_name)
            graph.source_files.add(requester_dir / f"{target_name}.s")

    monkeypatch.setattr(project_application, "ASTCache", FakeCache)
    monkeypatch.setattr(analysis_loading_module, "build_parser_binding", fake_build_parser_binding)
    monkeypatch.setattr(
        analysis_loading_module,
        "_load_parser_graph",
        lambda *_args, **_kwargs: AnalysisGraphStub(
            ast_by_name={"LibraryTarget": root_bp},
            source_files={project_lib_dir / "LibraryTarget.s"},
        ),
    )
    monkeypatch.setattr(analysis_loading_module, "find_dependency_path", fake_find_dependency_path)
    monkeypatch.setattr(analysis_loading_module, "read_dependency_names", fake_read_dependency_names)
    monkeypatch.setattr(analysis_loading_module, "_visit_targets_into_graph", fake_visit_targets_into_graph)

    def fake_merge_project_basepicture(bp: BasePicture, graph: ProjectGraph) -> object:
        return (bp.header.name, tuple(sorted(graph.ast_by_name)))

    monkeypatch.setattr(
        analysis_loading_module,
        "merge_project_basepicture",
        fake_merge_project_basepicture,
    )

    project_bp, graph = project_application.load_project(
        cast(
            ConfigDict,
            {
                "program_dir": str(programs_dir),
                "other_lib_dirs": [str(project_lib_dir)],
                "ABB_lib_dir": str(abb_dir),
                "mode": "draft",
                "debug": False,
                "analyzed_programs_and_libraries": ["LibraryTarget"],
            },
        ),
        cache_key_for_target_fn=lambda _cfg, _target: "cache-key",
        get_cache_dir_fn=lambda: tmp_path / "cache-dir",
    )

    # A consumer in the vendor root counts, and a consumer of that consumer
    # joins the closure one hop later: its imported module types can use the
    # target's types too.
    assert project_bp == (
        "LibraryTarget",
        ("AbbConsumer", "DeepConsumer", "LibraryTarget", "ProgramConsumer"),
    )
    assert sorted(graph.ast_by_name) == ["AbbConsumer", "DeepConsumer", "LibraryTarget", "ProgramConsumer"]
    assert visit_calls == [
        ("AbbConsumer", abb_dir, False),
        ("ProgramConsumer", programs_dir, False),
        ("DeepConsumer", programs_dir, False),
    ]
    assert save_calls[0][0] == "cache-key"


def test_load_project_library_target_workspace_program_usage_suppresses_unused_datatype_field(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    programs_dir = tmp_path / "programs"
    project_lib_dir = tmp_path / "ProjectLib"
    programs_dir.mkdir()
    project_lib_dir.mkdir()
    (programs_dir / "ProgramConsumer.l").write_text("LibraryTarget\n", encoding="utf-8")

    def _hdr(name: str) -> ModuleHeader:
        return ModuleHeader(name=name, invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0))

    def _varref(name: str) -> VarRef:
        return VarRef(name=name)

    library_datatype = DataType(
        name="ApplOpTxtType",
        description=None,
        datecode=None,
        var_list=[
            Variable(name="LSH", datatype=ScalarDatatype.STRING),
            Variable(name="DrainPipe", datatype=ScalarDatatype.STRING),
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
            Variable(name="Sink", datatype=ScalarDatatype.STRING),
        ],
        submodules=[],
        modulecode=ModuleCode(
            equationblocks=[
                Equation(
                    name="ReadField",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[Assignment(target=_varref("Sink"), value=_varref("OPText.LSH"))],
                )
            ],
            sequences=[],
        ),
        moduledef=None,
        origin_file="ProgramConsumer.s",
        origin_lib="Programs",
    )

    class FakeCache:
        def __init__(self, cache_dir: Path) -> None:
            self.cache_dir = cache_dir

        def load_validated(self, key: str) -> object | None:
            assert key == "cache-key"
            return None

        def manifest_paths(self, key: str) -> frozenset[Path]:
            assert key == "cache-key"
            return frozenset()

        def save(self, key: str, **kwargs: object) -> None:
            assert key == "cache-key"

    def fake_find_dependency_path(binding: ParserProjectBinding, target_name: str, **_kwargs: object) -> Path | None:
        if target_name == "LibraryTarget":
            return None
        return programs_dir / f"{target_name}.l"

    def fake_read_dependency_names(deps_path: Path) -> list[str]:
        return [line.strip() for line in deps_path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def fake_build_parser_binding(
        cfg: Mapping[str, object],
        *,
        parser_cache_dir: Path | None = None,
        status_update_fn: Callable[[str], None] | None = None,
        stage_timing_sink: LoadStageTimingSink | None = None,
        graphics_timing_sink: LoadStageTimingSink | None = None,
    ) -> ParserProjectBinding:
        del cfg
        return ParserProjectBinding(
            program_dir=Path("programs"),
            other_lib_dirs=(),
            abb_lib_dir=None,
            mode=CodeMode.DRAFT,
            status_update_fn=status_update_fn,
            stage_timing_sink=stage_timing_sink,
            graphics_timing_sink=graphics_timing_sink,
        )

    def fake_visit_targets_into_graph(
        binding: ParserProjectBinding,
        graph: AnalysisGraphStub,
        targets: list[tuple[str, Path | None]],
        *,
        lib_names: dict[str, str],
    ) -> None:
        del binding, lib_names
        for target_name, _requester_dir in targets:
            assert target_name == "ProgramConsumer"
            graph.ast_by_name[target_name] = program_bp
            graph.source_files.add(Path(f"{target_name}.s"))

    def _merge_project_basepicture(bp: BasePicture, graph: ProjectGraph) -> BasePicture:
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

    monkeypatch.setattr(project_application, "ASTCache", FakeCache)
    monkeypatch.setattr(analysis_loading_module, "build_parser_binding", fake_build_parser_binding)
    monkeypatch.setattr(
        analysis_loading_module,
        "_load_parser_graph",
        lambda *_args, **_kwargs: AnalysisGraphStub(
            ast_by_name={"LibraryTarget": root_bp},
            source_files={project_lib_dir / "LibraryTarget.s"},
        ),
    )
    monkeypatch.setattr(analysis_loading_module, "find_dependency_path", fake_find_dependency_path)
    monkeypatch.setattr(analysis_loading_module, "read_dependency_names", fake_read_dependency_names)
    monkeypatch.setattr(analysis_loading_module, "_visit_targets_into_graph", fake_visit_targets_into_graph)
    monkeypatch.setattr(analysis_loading_module, "merge_project_basepicture", _merge_project_basepicture)

    project_bp, _graph = project_application.load_project(
        cast(
            ConfigDict,
            {
                "program_dir": str(programs_dir),
                "other_lib_dirs": [str(project_lib_dir)],
                "ABB_lib_dir": str(tmp_path / "abb"),
                "mode": "draft",
                "debug": False,
                "analyzed_programs_and_libraries": ["LibraryTarget"],
            },
        ),
        cache_key_for_target_fn=lambda _cfg, _target: "cache-key",
        get_cache_dir_fn=lambda: tmp_path / "cache-dir",
    )

    report = analyze_datatype_fields(project_bp, analyzed_target_is_library=True)
    unused_fields = {
        issue.field_path
        for issue in report.issues
        if issue.kind is IssueKind.UNUSED_DATATYPE_FIELD and issue.datatype_name == "ApplOpTxtType"
    }

    assert unused_fields == {"DrainPipe"}


def test_ensure_ast_cache_handles_valid_fast_path_rebuilds_and_failures(monkeypatch: pytest.MonkeyPatch):
    lines: list[str] = []
    load_calls: list[str] = []

    class FakeCache:
        def __init__(self, cache_dir: Path) -> None:
            self.cache_dir = cache_dir

        def load_validated(self, key: str) -> object | None:
            mapping = {
                "key:Fresh": {"name": "Fresh"},
                "key:Stale": {"name": "Stale"},
                "key:Old": {"name": "Old"},
                "key:Broken": None,
            }
            return mapping[key]

        def has_payload(self, key: str) -> bool:
            return self.load_validated(key) is not None

        def has_manifest(self, key: str) -> bool:
            return key in {"key:Fresh", "key:Stale"}

        def has_cache_artifact(self, key: str) -> bool:
            return key == "key:Fresh"

    def fake_load_project(
        _cfg: ConfigDict,
        target_name: str | None = None,
        use_cache: bool = True,
        **_kwargs: object,
    ) -> tuple[BasePicture, ProjectGraph]:
        resolved_target = target_name or ""
        load_calls.append(resolved_target)
        if target_name == "Broken":
            raise RuntimeError("boom")
        return cast(tuple[BasePicture, ProjectGraph], (f"bp-{resolved_target}", SimpleNamespace()))

    monkeypatch.setattr(project_application, "emit_output", lambda message: lines.append(message))

    ok = project_application.ensure_ast_cache(
        cast(
            ConfigDict,
            {
                "analyzed_programs_and_libraries": ["Fresh", "Stale", "Old", "Broken"],
            },
        ),
        cache_key_for_target_fn=lambda _cfg, target_name: f"key:{target_name}",
        load_project_fn=fake_load_project,
        ast_cache_cls=cast(type[ASTCache], FakeCache),
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


def test_ensure_ast_cache_logs_debug_traceback_on_rebuild_failure(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
):
    lines: list[str] = []

    class FakeCache:
        def __init__(self, cache_dir: Path) -> None:
            self.cache_dir = cache_dir

        def has_payload(self, key: str) -> bool:
            return False

        def has_manifest(self, key: str) -> bool:
            return False

    def fail_load_project(
        _cfg: ConfigDict,
        target_name: str | None = None,
        use_cache: bool = True,
        **_kwargs: object,
    ) -> tuple[BasePicture, ProjectGraph]:
        raise RuntimeError("boom")

    monkeypatch.setattr(project_application, "emit_output", lambda message: lines.append(message))

    with caplog.at_level(logging.ERROR, logger="SattLint"):
        ok = project_application.ensure_ast_cache(
            cast(ConfigDict, {"debug": True}),
            get_analyzed_targets_fn=lambda _cfg: ["Broken"],
            cache_key_for_target_fn=lambda _cfg, target_name: f"key:{target_name}",
            load_project_fn=fail_load_project,
            ast_cache_cls=cast(type[ASTCache], FakeCache),
            get_cache_dir_fn=lambda: Path("cache-dir"),
        )

    assert ok is False
    assert any("Failed to build AST cache for Broken: boom" in line for line in lines)
    assert any("Failed to rebuild AST cache for 'Broken'" in message for message in caplog.messages)
    assert "Traceback (most recent call last)" in caplog.text


def test_ensure_ast_cache_uses_has_cache_artifact_for_warm_cache_checks(monkeypatch: pytest.MonkeyPatch):
    """ensure_ast_cache uses the cheap artifact check during warm-cache preflight."""
    artifact_check_calls: list[str] = []

    class FakeCache:
        def __init__(self, cache_dir: Path) -> None:
            self.cache_dir = cache_dir

        def has_payload(self, key: str) -> bool:
            return key == "key:Ok"

        def has_manifest(self, key: str) -> bool:
            return key == "key:Ok"

        def has_cache_artifact(self, key: str) -> bool:
            assert key == "key:Ok"
            artifact_check_calls.append(key)
            return True

    lines: list[str] = []
    monkeypatch.setattr(project_application, "emit_output", lambda message: lines.append(message))

    ok = project_application.ensure_ast_cache(
        cast(ConfigDict, {"analyzed_programs_and_libraries": ["Ok"]}),
        cache_key_for_target_fn=lambda _cfg, target_name: f"key:{target_name}",
        load_project_fn=cast(
            Callable[..., tuple[BasePicture, ProjectGraph]],
            lambda *args, **kwargs: pytest.fail("should not rebuild"),
        ),
        ast_cache_cls=cast(type[ASTCache], FakeCache),
        get_cache_dir_fn=lambda: Path("cache-dir"),
    )

    assert ok is True
    assert artifact_check_calls == ["key:Ok"]
    assert any("AST cache OK" in line for line in lines)


def test_ensure_ast_cache_rebuilds_when_has_cache_artifact_fails(monkeypatch: pytest.MonkeyPatch):
    """Warm-cache checks rebuild when the cheap artifact check fails."""
    artifact_check_calls: list[str] = []
    rebuild_calls: list[str] = []

    class FakeCache:
        def __init__(self, cache_dir: Path) -> None:
            self.cache_dir = cache_dir

        def has_payload(self, key: str) -> bool:
            return key == "key:Ok"

        def has_manifest(self, key: str) -> bool:
            return key == "key:Ok"

        def has_cache_artifact(self, key: str) -> bool:
            assert key == "key:Ok"
            artifact_check_calls.append(key)
            return False

    lines: list[str] = []
    monkeypatch.setattr(project_application, "emit_output", lambda message: lines.append(message))

    ok = project_application.ensure_ast_cache(
        cast(ConfigDict, {"analyzed_programs_and_libraries": ["Ok"]}),
        cache_key_for_target_fn=lambda _cfg, target_name: f"key:{target_name}",
        load_project_fn=cast(
            Callable[..., tuple[BasePicture, ProjectGraph]],
            lambda _cfg, target_name=None, **_kwargs: (
                rebuild_calls.append(cast(str, target_name)) or ("bp", SimpleNamespace())
            ),
        ),
        ast_cache_cls=cast(type[ASTCache], FakeCache),
        get_cache_dir_fn=lambda: Path("cache-dir"),
    )

    assert ok is True
    assert artifact_check_calls == ["key:Ok"]
    assert rebuild_calls == ["Ok"]
    assert any("AST cache stale; rebuilding" in line for line in lines)


LIBRARY_WITH_UNUSED_SOURCE = """
"Syntax version 2.23, date: 2026-04-23-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-04-23-12:00:00.000, name: MyLib"

BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1

LOCALVARIABLES
    UsedLocal: integer := 0;
    UnusedLocal: integer := 0;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
        UsedLocal = 1;
ENDDEF (*BasePicture*);
"""

DEP_SOURCE = """
"Syntax version 2.23, date: 2026-04-23-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-04-23-12:00:00.000, name: DepA"

BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1

LOCALVARIABLES
    DepLocal: integer := 0;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
        DepLocal = 1;
ENDDEF (*BasePicture*);
"""


def test_load_project_library_target_resolves_origin_and_finds_unused(tmp_path: Path):
    program_dir = tmp_path / "programs"
    lib_dir = tmp_path / "projectlib"
    abb_dir = tmp_path / "abb_lib"
    program_dir.mkdir(parents=True, exist_ok=True)
    lib_dir.mkdir(parents=True, exist_ok=True)
    abb_dir.mkdir(parents=True, exist_ok=True)

    target_name = "MyLib"
    target_file = lib_dir / f"{target_name}.s"
    dep_file = lib_dir / f"{target_name}.l"
    dep_src_file = lib_dir / "DepA.s"
    dep_dep_file = lib_dir / "DepA.l"

    target_file.write_text(LIBRARY_WITH_UNUSED_SOURCE, encoding="utf-8")
    dep_file.write_text("DepA\n", encoding="utf-8")
    dep_src_file.write_text(DEP_SOURCE, encoding="utf-8")
    dep_dep_file.write_text("", encoding="utf-8")

    cfg: dict[str, object] = {
        "program_dir": str(program_dir),
        "ABB_lib_dir": str(abb_dir),
        "other_lib_dirs": [str(lib_dir)],
        "analyzed_programs_and_libraries": [target_name],
        "mode": "draft",
        "use_cache": False,
        "debug": False,
    }

    project_bp, graph = project_application.load_project(
        cast(ConfigDict, cfg),
        use_cache=False,
        get_cache_dir_fn=lambda: tmp_path / "cache-dir",
    )

    assert getattr(project_bp, "origin_file", None) == f"{target_name}.s"
    assert getattr(project_bp, "origin_lib", None) == "projectlib"
    assert target_name in graph.ast_by_name
    assert "DepA" in graph.ast_by_name

    report = analyze_variables(
        project_bp,
        config=cfg,
        debug=False,
        unavailable_libraries=set(),
        analyzed_target_is_library=True,
        selected_issue_kinds={IssueKind.UNUSED},
    )

    unused_names = {issue.variable.name for issue in report.unused if isinstance(issue, VariableTargetIssue)}
    assert "UnusedLocal" in unused_names, f"Expected UnusedLocal in unused variables, got: {unused_names}"
    assert "UsedLocal" not in unused_names
    assert "DepLocal" not in unused_names


def test_load_program_asts_parses_the_batch_once_and_reuses_the_cache(monkeypatch: pytest.MonkeyPatch):
    program_a = named_object("ProgramA")
    program_b = named_object("ProgramB")
    graph = SimpleNamespace(
        ast_by_name={"ProgramA": program_a, "ProgramB": program_b},
        unavailable_libraries=set(),
        failures={},
        source_files={Path("ProgramA.x")},
    )
    parse_calls: list[tuple[str, object]] = []

    def _fake_load(_binding: object, target: str, **kwargs: object) -> object:
        parse_calls.append((target, kwargs.get("extra_roots")))
        return graph

    cache_state: dict[str, object] = {}
    save_calls: list[str] = []

    class FakeCache:
        def __init__(self, cache_dir: Path) -> None:
            self.cache_dir = cache_dir

        def load_validated(self, key: str) -> object | None:
            return cache_state.get(key)

        def manifest_paths(self, key: str) -> frozenset[Path]:
            del key
            return frozenset({Path("ProgramA.x")})

        def save(self, key: str, *, project: object, files: object) -> None:
            del files
            save_calls.append(key)
            cache_state[key] = {"project": project}

    monkeypatch.setattr(analysis_loading_module, "_load_parser_graph", _fake_load)
    monkeypatch.setattr(analysis_loading_module, "cache_manifest_files", lambda *_args, **_kwargs: {Path("ProgramA.x")})
    monkeypatch.setattr(cache_mod, "get_cache_dir_or_none", lambda: Path("cache-dir"))
    monkeypatch.setattr(cache_mod, "build_ast_cache", lambda cache_dir, _cls: FakeCache(cache_dir))

    cfg = cast(
        ConfigDict,
        {
            "program_dir": "programs",
            "other_lib_dirs": [],
            "ABB_lib_dir": "abb",
            "mode": "draft",
            "debug": False,
            "analyzed_programs_and_libraries": ["TargetA"],
            "icf_dir": "",
        },
    )

    asts, loaded_graph = analysis_loading_module.load_program_asts(cfg, ["ProgramA", "ProgramB"])

    expected_key = cache_mod.compute_cache_key(
        cfg,
        analysis_target="icf-program-batch::programa|programb",
    )
    assert asts == {"ProgramA": program_a, "ProgramB": program_b}
    assert loaded_graph is graph
    assert parse_calls == [("ProgramA", ("ProgramB",))]
    assert save_calls == [expected_key]

    cached_asts, cached_graph = analysis_loading_module.load_program_asts(cfg, ["ProgramB", "ProgramA"])

    assert len(parse_calls) == 1
    assert cached_asts == asts
    assert cached_graph is graph
