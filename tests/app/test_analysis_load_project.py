# pyright: reportUnknownLambdaType=false, reportUnknownArgumentType=false
from collections.abc import Callable, Mapping
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from sattline_parser.models.ast_model import BasePicture
from sattline_parser.project import LoadValidation

from sattlint.application import (
    checks as checks_application,
)
from sattlint.application import (
    output as output_module,
)
from sattlint.application import (
    project as project_application,
)
from sattlint.cache import ASTCache
from sattlint.config import DEFAULT_CONFIG
from sattlint.config.types import ConfigDict
from sattlint.core.progress import AnalysisProgressEvent, ProgressPhase
from sattlint.models.project_graph import ProjectGraph
from sattlint.project import loading as analysis_loading_module
from sattlint.project.loader_config import LoadStageTimingSink
from sattlint.project.parser_adapter import ParserProjectBinding
from tests.helpers import AnalysisGraphStub, named_object


def test_load_project_saves_cache_after_successful_merge(monkeypatch: pytest.MonkeyPatch):
    saved: dict[str, object] = {}
    root_bp = named_object("TargetA", origin_file="TargetA.s")
    graph = AnalysisGraphStub(
        ast_by_name={"TargetA": root_bp},
        missing=[],
        warnings=[],
        source_files={Path("programs/TargetA.s")},
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
            saved.update({"key": key, **kwargs})

    def fake_build_parser_binding(
        cfg: Mapping[str, object],
        *,
        parser_cache_dir: Path | None = None,
        status_update_fn: Callable[[str], None] | None = None,
        refresh_mode: str = "full",
        stage_timing_sink: LoadStageTimingSink | None = None,
        graphics_timing_sink: LoadStageTimingSink | None = None,
    ) -> SimpleNamespace:
        return SimpleNamespace(
            status_update_fn=status_update_fn,
            refresh_mode=refresh_mode,
            stage_timing_sink=stage_timing_sink,
            graphics_timing_sink=graphics_timing_sink,
        )

    monkeypatch.setattr(project_application, "ASTCache", FakeCache)
    monkeypatch.setattr(project_application, "get_cache_dir", lambda: Path("cache-dir"))
    monkeypatch.setattr(analysis_loading_module, "build_parser_binding", fake_build_parser_binding)
    monkeypatch.setattr(analysis_loading_module, "_load_parser_graph", lambda *_args, **_kwargs: graph)
    monkeypatch.setattr(analysis_loading_module, "find_dependency_path", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(analysis_loading_module, "read_dependency_names", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(analysis_loading_module, "merge_project_basepicture", lambda bp, graph: "merged")

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
    )

    assert result == (
        "merged",
        graph,
    )
    assert saved["key"] == "cache-key"
    assert saved["project"] == (root_bp, graph)
    assert saved["files"] == {Path("programs/TargetA.s"), Path("programs"), Path("abb")}


def test_load_project_runs_when_the_cache_directory_is_unusable(monkeypatch: pytest.MonkeyPatch):
    root_bp = named_object("TargetA", origin_file="TargetA.s")
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
        refresh_mode: str = "full",
        stage_timing_sink: LoadStageTimingSink | None = None,
        graphics_timing_sink: LoadStageTimingSink | None = None,
    ) -> SimpleNamespace:
        return SimpleNamespace(
            status_update_fn=status_update_fn,
            refresh_mode=refresh_mode,
            stage_timing_sink=stage_timing_sink,
            graphics_timing_sink=graphics_timing_sink,
        )

    monkeypatch.setattr(analysis_loading_module, "build_parser_binding", fake_build_parser_binding)
    monkeypatch.setattr(analysis_loading_module, "_load_parser_graph", lambda *_args, **_kwargs: graph)
    monkeypatch.setattr(analysis_loading_module, "find_dependency_path", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(analysis_loading_module, "read_dependency_names", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(analysis_loading_module, "merge_project_basepicture", lambda bp, graph: "merged")

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
        get_cache_dir_fn=lambda: None,
    )

    assert result == ("merged", graph)


def test_load_project_skips_cache_when_a_dependency_is_unavailable(monkeypatch: pytest.MonkeyPatch):
    root_bp = named_object("TargetA", origin_file="TargetA.s")
    graph = AnalysisGraphStub(
        ast_by_name={"TargetA": root_bp},
        missing=["Missing code file for 'MissingLib' (draft)"],
        unavailable_libraries={"MISSINGLIB"},
        source_files={Path("programs/TargetA.s")},
    )

    class FakeCache:
        def __init__(self, cache_dir: Path) -> None:
            self.cache_dir = cache_dir

        def load_validated(self, key: str) -> object | None:
            assert key == "cache-key"
            return None

        def manifest_paths(self, key: str) -> frozenset[Path]:
            return frozenset()

        def save(self, *args: object, **kwargs: object) -> None:
            pytest.fail("an unresolved graph must not be persisted")

    monkeypatch.setattr(project_application, "ASTCache", FakeCache)
    monkeypatch.setattr(project_application, "get_cache_dir", lambda: Path("cache-dir"))
    monkeypatch.setattr(analysis_loading_module, "build_parser_binding", lambda *_args, **_kwargs: SimpleNamespace())
    monkeypatch.setattr(analysis_loading_module, "_load_parser_graph", lambda *_args, **_kwargs: graph)
    monkeypatch.setattr(analysis_loading_module, "find_dependency_path", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(analysis_loading_module, "read_dependency_names", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(analysis_loading_module, "merge_project_basepicture", lambda bp, _graph: bp)

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
    )

    assert result == (root_bp, graph)
    assert graph.analysis_cache_key is None


def test_load_project_raises_default_error_when_target_missing(monkeypatch: pytest.MonkeyPatch):
    class FakeCache:
        def __init__(self, cache_dir: Path) -> None:
            self.cache_dir = cache_dir

        def load_validated(self, key: str) -> object | None:
            assert key == "cache-key"
            return None

        def manifest_paths(self, key: str) -> frozenset[Path]:
            assert key == "cache-key"
            return frozenset()

    monkeypatch.setattr(project_application, "ASTCache", FakeCache)
    monkeypatch.setattr(project_application, "get_cache_dir", lambda: Path("cache-dir"))
    monkeypatch.setattr(
        analysis_loading_module, "build_parser_binding", lambda *_args, **_kwargs: SimpleNamespace(debug_fn=None)
    )
    monkeypatch.setattr(
        analysis_loading_module,
        "_load_parser_graph",
        lambda *_args, **_kwargs: SimpleNamespace(
            ast_by_name={}, missing=[], warnings=[], failures={}, source_files=set()
        ),
    )
    monkeypatch.setattr(analysis_loading_module, "find_dependency_path", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(analysis_loading_module, "read_dependency_names", lambda *_args, **_kwargs: [])

    with pytest.raises(RuntimeError, match="Target 'TargetA' was not parsed"):
        project_application.load_project(
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
        )


def test_load_project_raises_value_error_when_loader_config_missing(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        project_application, "ASTCache", lambda cache_dir: pytest.fail(f"unexpected cache init: {cache_dir}")
    )
    monkeypatch.setattr(project_application, "get_cache_dir", lambda: Path("cache-dir"))

    with pytest.raises(ValueError, match="Missing loader config keys: debug"):
        project_application.load_project(
            cast(
                ConfigDict,
                {
                    "program_dir": "programs",
                    "other_lib_dirs": [],
                    "ABB_lib_dir": "abb",
                    "mode": "draft",
                    "analyzed_programs_and_libraries": ["TargetA"],
                },
            ),
            cache_key_for_target_fn=lambda _cfg, _target: "cache-key",
        )


def test_load_program_ast_returns_loaded_program(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        analysis_loading_module,
        "_load_parser_graph",
        lambda _binding, program_name, **_kwargs: SimpleNamespace(ast_by_name={program_name: "bp-main"}),
    )

    result = project_application.load_program_ast(
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

    assert result == ("bp-main", SimpleNamespace(ast_by_name={"TargetA": "bp-main"}))


def test_ensure_ast_cache_returns_true_without_targets():
    assert project_application.ensure_ast_cache(cast(ConfigDict, {}), get_analyzed_targets_fn=lambda _cfg: []) is True


def test_load_project_uses_cached_ast_only_project_and_manifest_metadata(monkeypatch: pytest.MonkeyPatch):
    root_bp = named_object("TargetA", origin_file="TargetA.s")
    graph = AnalysisGraphStub()

    class FakeCache:
        def __init__(self, cache_dir: Path) -> None:
            self.cache_dir = cache_dir

        def load_validated(self, key: str) -> object | None:
            assert key == "cache-key"
            return {"project": (root_bp, graph)}

        def manifest_paths(self, key: str) -> frozenset[Path]:
            assert key == "cache-key"
            return frozenset({Path("programs/TargetA.z")})

    monkeypatch.setattr(project_application, "ASTCache", FakeCache)
    monkeypatch.setattr(project_application, "get_cache_dir", lambda: Path("cache-dir"))
    monkeypatch.setattr(
        analysis_loading_module,
        "merge_project_basepicture",
        lambda *_args, **_kwargs: pytest.fail("ast-only cache hit should not merge project view"),
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
        refresh_mode="ast-only",
    )

    assert result == (root_bp, graph)
    assert graph.analysis_cache_key == "cache-key"
    assert graph.analysis_manifest_files == frozenset({Path("programs/TargetA.z")})


def test_load_project_ast_only_collects_stage_timings(monkeypatch: pytest.MonkeyPatch):
    root_bp = named_object("TargetA", origin_file="TargetA.s")
    graph = AnalysisGraphStub(ast_by_name={"TargetA": root_bp})

    class FakeCache:
        def __init__(self, cache_dir: Path) -> None:
            self.cache_dir = cache_dir

        def load_validated(self, key: str) -> object | None:
            assert key == "cache-key"
            return None

        def manifest_paths(self, key: str) -> frozenset[Path]:
            assert key == "cache-key"
            return frozenset()

        def save(self, *args: object, **kwargs: object) -> None:
            pytest.fail("ast-only refresh should return before saving cache")

    def fake_build_parser_binding(
        cfg: Mapping[str, object],
        *,
        parser_cache_dir: Path | None = None,
        status_update_fn: Callable[[str], None] | None = None,
        stage_timing_sink: LoadStageTimingSink | None = None,
        graphics_timing_sink: LoadStageTimingSink | None = None,
    ) -> SimpleNamespace:
        return SimpleNamespace(
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
        assert strict is False
        assert validate.value == "none"
        assert index_program_view is False
        assert binding.stage_timing_sink is not None
        assert binding.graphics_timing_sink is not None
        binding.stage_timing_sink("TargetA", "load_or_parse", 0.1)
        binding.stage_timing_sink("TargetA", "validate", 0.2)
        binding.graphics_timing_sink("TargetA", "attach-graphics", 0.3)
        return graph

    monkeypatch.setattr(project_application, "ASTCache", FakeCache)
    monkeypatch.setattr(project_application, "get_cache_dir", lambda: Path("cache-dir"))
    monkeypatch.setattr(analysis_loading_module, "build_parser_binding", fake_build_parser_binding)
    monkeypatch.setattr(analysis_loading_module, "_load_parser_graph", fake_load_parser_graph)
    monkeypatch.setattr(analysis_loading_module, "find_dependency_path", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(analysis_loading_module, "read_dependency_names", lambda *_args, **_kwargs: [])

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
        refresh_mode="ast-only",
        collect_stage_timings=True,
    )

    assert result == (root_bp, graph)
    assert graph.load_stage_timings == {"load_or_parse": 0.1, "validate": 0.2}
    assert graph.load_stage_timings_by_program == {"TargetA": {"load_or_parse": 0.1, "validate": 0.2}}
    assert graph.graphics_load_timings == {"attach-graphics": 0.3}
    assert graph.graphics_load_timings_by_program == {"TargetA": {"attach-graphics": 0.3}}


def test_load_project_uses_custom_target_load_error_factory(monkeypatch: pytest.MonkeyPatch):
    captured: dict[str, object] = {}

    class CustomLoadError(RuntimeError):
        pass

    class FakeCache:
        def __init__(self, cache_dir: Path) -> None:
            self.cache_dir = cache_dir

        def load_validated(self, key: str) -> object | None:
            assert key == "cache-key"
            return None

        def manifest_paths(self, key: str) -> frozenset[Path]:
            assert key == "cache-key"
            return frozenset()

    def fake_build_parser_binding(
        cfg: Mapping[str, object],
        *,
        parser_cache_dir: Path | None = None,
        status_update_fn: Callable[[str], None] | None = None,
        refresh_mode: str = "full",
        stage_timing_sink: LoadStageTimingSink | None = None,
        graphics_timing_sink: LoadStageTimingSink | None = None,
    ) -> SimpleNamespace:
        return SimpleNamespace(
            status_update_fn=status_update_fn,
            refresh_mode=refresh_mode,
            stage_timing_sink=stage_timing_sink,
            graphics_timing_sink=graphics_timing_sink,
        )

    monkeypatch.setattr(project_application, "ASTCache", FakeCache)
    monkeypatch.setattr(project_application, "get_cache_dir", lambda: Path("cache-dir"))
    monkeypatch.setattr(analysis_loading_module, "build_parser_binding", fake_build_parser_binding)
    monkeypatch.setattr(
        analysis_loading_module,
        "_load_parser_graph",
        lambda *_args, **_kwargs: SimpleNamespace(
            ast_by_name={}, missing=["missing-lib"], warnings=["warn-lib"], failures={}, source_files=set()
        ),
    )
    monkeypatch.setattr(
        analysis_loading_module, "find_dependency_path", lambda *_args, **_kwargs: Path("programs/TargetA.z")
    )
    monkeypatch.setattr(analysis_loading_module, "read_dependency_names", lambda *_args, **_kwargs: ["DepA"])

    def make_error(target_name: str, **kwargs: object) -> Exception:
        captured.update({"target_name": target_name, **kwargs})
        return CustomLoadError(f"custom:{target_name}")

    with pytest.raises(CustomLoadError, match="custom:TargetA"):
        project_application.load_project(
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
            target_load_error_factory=make_error,
        )

    assert captured == {
        "target_name": "TargetA",
        "resolved": [],
        "missing": ["missing-lib"],
        "warnings": ["warn-lib"],
        "direct_dependencies": ["DepA"],
        "failures": {},
    }


def test_load_program_ast_raises_when_program_missing(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        analysis_loading_module,
        "_load_parser_graph",
        lambda *_args, **_kwargs: SimpleNamespace(ast_by_name={"Other": "bp-other"}),
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


def test_iter_loaded_projects_passes_collect_stage_timings_to_load_project(monkeypatch: pytest.MonkeyPatch):
    seen: list[tuple[str | None, bool, bool]] = []

    def fake_load_project(
        _cfg: ConfigDict,
        target_name: str | None = None,
        *,
        refresh_ast: bool = False,
        collect_stage_timings: bool = False,
        **_kwargs: object,
    ) -> tuple[BasePicture, ProjectGraph]:
        seen.append((target_name, refresh_ast, collect_stage_timings))
        return cast(tuple[BasePicture, ProjectGraph], (named_object(target_name or "Unknown"), AnalysisGraphStub()))

    monkeypatch.setattr(project_application, "emit_output", lambda *_args, **_kwargs: None)

    results = list(
        project_application.iter_loaded_projects(
            cast(ConfigDict, {"analyzed_programs_and_libraries": ["TargetA"], "debug": True}),
            refresh_ast=True,
            require_analyzed_targets_fn=lambda _cfg: ["TargetA"],
            load_project_fn=fake_load_project,
        )
    )

    assert [target_name for target_name, _bp, _graph in results] == ["TargetA"]
    assert seen == [("TargetA", True, True)]


def test_iter_loaded_projects_reports_loading_progress_for_every_target(monkeypatch: pytest.MonkeyPatch):
    events: list[AnalysisProgressEvent] = []

    def fake_load_project(
        _cfg: ConfigDict,
        target_name: str | None = None,
        **_kwargs: object,
    ) -> tuple[BasePicture, ProjectGraph]:
        if target_name == "Broken":
            raise RuntimeError("boom")
        return cast(
            tuple[BasePicture, ProjectGraph],
            (named_object(target_name or "Unknown"), AnalysisGraphStub(unavailable_libraries=set())),
        )

    monkeypatch.setattr(project_application, "emit_output", lambda *_args, **_kwargs: None)

    results = list(
        project_application.iter_loaded_projects(
            cast(ConfigDict, {"analyzed_programs_and_libraries": ["TargetA", "Broken", "TargetB"]}),
            require_analyzed_targets_fn=lambda _cfg: ["TargetA", "Broken", "TargetB"],
            load_project_fn=fake_load_project,
            progress_fn=events.append,
        )
    )

    assert [target_name for target_name, _bp, _graph in results] == ["TargetA", "TargetB"]
    assert [(event.phase, event.target_index, event.target_total, event.target_name) for event in events] == [
        (ProgressPhase.LOADING, 1, 3, "TargetA"),
        (ProgressPhase.LOADING, 2, 3, "Broken"),
        (ProgressPhase.TARGET_COMPLETE, 2, 3, "Broken"),
        (ProgressPhase.LOADING, 3, 3, "TargetB"),
    ]


def test_ensure_ast_cache_covers_cache_hit_stale_missing_and_failure(monkeypatch: pytest.MonkeyPatch):
    lines: list[str] = []
    load_calls: list[tuple[str, bool]] = []

    cache_state = {
        "TargetA": (True, True, True),
        "TargetB": (True, True, False),
        "TargetC": (True, False, False),
        "TargetD": (False, False, False),
        "TargetE": (False, False, False),
    }

    class FakeCache:
        def __init__(self, cache_dir: Path) -> None:
            self.cache_dir = cache_dir

        def has_payload(self, key: str) -> bool:
            return cache_state[key][0]

        def has_manifest(self, key: str) -> bool:
            return cache_state[key][1]

        def has_cache_artifact(self, key: str) -> bool:
            return cache_state[key][2]

    def fake_load_project(
        _cfg: ConfigDict, *, target_name: str, refresh_ast: bool, **_kwargs: object
    ) -> tuple[BasePicture, ProjectGraph]:
        load_calls.append((target_name, refresh_ast))
        if target_name == "TargetE":
            raise RuntimeError("boom")
        return cast(tuple[BasePicture, ProjectGraph], (SimpleNamespace(), SimpleNamespace()))

    monkeypatch.setattr(project_application, "emit_output", lambda message: lines.append(str(message)))

    ok = project_application.ensure_ast_cache(
        cast(ConfigDict, {}),
        get_analyzed_targets_fn=lambda _cfg: ["TargetA", "TargetB", "TargetC", "TargetD", "TargetE"],
        cache_key_for_target_fn=lambda _cfg, target_name: target_name,
        load_project_fn=fake_load_project,
        ast_cache_cls=cast(type[ASTCache], FakeCache),
        get_cache_dir_fn=lambda: Path("cache-dir"),
    )

    assert ok is False
    assert load_calls == [
        ("TargetB", True),
        ("TargetC", True),
        ("TargetD", True),
        ("TargetE", True),
    ]
    assert any("AST cache OK" in line for line in lines)
    assert any("AST cache stale; rebuilding" in line for line in lines)
    assert any("AST cache missing file manifest; rebuilding" in line for line in lines)
    assert any("AST cache missing; building" in line for line in lines)
    assert any("AST cache updated" in line for line in lines)
    assert any("Failed to build AST cache for TargetE: boom" in line for line in lines)


def test_run_checks_success_path_pauses(monkeypatch: pytest.MonkeyPatch):
    lines: list[str] = []
    pauses: list[str] = []

    monkeypatch.setattr(output_module, "emit_output", lambda message: lines.append(message))

    checks_application.run_checks(
        cast(ConfigDict, DEFAULT_CONFIG.copy()),
        ["state-inference"],
        iter_loaded_projects_fn=cast(
            Any,
            lambda *_args, **_kwargs: iter(
                [
                    (
                        "TargetA",
                        SimpleNamespace(header=SimpleNamespace(name="TargetA")),
                        AnalysisGraphStub(unavailable_libraries=set()),
                    )
                ]
            ),
        ),
        get_enabled_analyzers_fn=lambda: [
            SimpleNamespace(
                key="state-inference",
                name="State inference",
                run=lambda _context: SimpleNamespace(summary=lambda: "state inference summary"),
            )
        ],
        target_is_library_fn=lambda *_args, **_kwargs: False,
        pause_fn=lambda: pauses.append("pause"),
    )

    assert any("state inference summary" in line for line in lines)
    assert pauses == ["pause"]


def test_load_project_does_not_build_a_parser_cache_when_the_directory_is_unavailable(monkeypatch: pytest.MonkeyPatch):
    root_bp = named_object("TargetA", origin_file="TargetA.s")
    graph = AnalysisGraphStub(
        ast_by_name={"TargetA": root_bp},
        missing=[],
        warnings=[],
        source_files={Path("programs/TargetA.s")},
    )

    def _unexpected(*_args: object, **_kwargs: object):
        raise AssertionError("the AST cache must not be built without a cache directory")

    monkeypatch.setattr(analysis_loading_module, "build_parser_binding", lambda *_args, **_kwargs: SimpleNamespace())
    monkeypatch.setattr(analysis_loading_module, "_load_parser_graph", lambda *_args, **_kwargs: graph)
    monkeypatch.setattr(analysis_loading_module, "find_dependency_path", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(analysis_loading_module, "read_dependency_names", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(analysis_loading_module, "merge_project_basepicture", lambda bp, _graph: bp)
    monkeypatch.setattr(analysis_loading_module.cache_module, "build_ast_cache", _unexpected)

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
        get_cache_dir_fn=lambda: None,
    )

    assert result == (root_bp, graph)


def test_load_project_ignores_a_cache_write_failure(monkeypatch: pytest.MonkeyPatch):
    root_bp = named_object("TargetA", origin_file="TargetA.s")
    graph = AnalysisGraphStub(
        ast_by_name={"TargetA": root_bp},
        missing=[],
        warnings=[],
        source_files={Path("programs/TargetA.s")},
    )

    class FailingCache:
        def __init__(self, cache_dir: Path) -> None:
            self.cache_dir = cache_dir

        def load_validated(self, key: str) -> object | None:
            return None

        def manifest_paths(self, key: str) -> frozenset[Path]:
            return frozenset()

        def save(self, key: str, **kwargs: object) -> None:
            raise OSError("disk full")

    def fake_build_parser_binding(
        cfg: Mapping[str, object],
        *,
        parser_cache_dir: Path | None = None,
        status_update_fn: Callable[[str], None] | None = None,
        stage_timing_sink: LoadStageTimingSink | None = None,
        graphics_timing_sink: LoadStageTimingSink | None = None,
    ) -> SimpleNamespace:
        return SimpleNamespace()

    monkeypatch.setattr(project_application, "ASTCache", FailingCache)
    monkeypatch.setattr(project_application, "get_cache_dir", lambda: Path("cache-dir"))
    monkeypatch.setattr(analysis_loading_module, "build_parser_binding", fake_build_parser_binding)
    monkeypatch.setattr(analysis_loading_module, "_load_parser_graph", lambda *_args, **_kwargs: graph)
    monkeypatch.setattr(analysis_loading_module, "find_dependency_path", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(analysis_loading_module, "read_dependency_names", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(analysis_loading_module, "merge_project_basepicture", lambda bp, _graph: bp)

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
    )

    assert result == (root_bp, graph)


def test_load_project_drops_stale_stage_timings_on_a_cache_hit(monkeypatch: pytest.MonkeyPatch):
    root_bp = named_object("TargetA", origin_file="TargetA.s")
    graph = AnalysisGraphStub(
        ast_by_name={"TargetA": root_bp},
        load_stage_timings={"load_or_parse": 0.1},
        load_stage_timings_by_program={"TargetA": {"load_or_parse": 0.1}},
        graphics_load_timings={"attach_graphics": 0.2},
    )

    class CachedCache:
        def __init__(self, cache_dir: Path) -> None:
            self.cache_dir = cache_dir

        def load_validated(self, key: str) -> object | None:
            return {"project": (root_bp, graph)}

        def manifest_paths(self, key: str) -> frozenset[Path]:
            return frozenset()

    monkeypatch.setattr(project_application, "ASTCache", CachedCache)
    monkeypatch.setattr(project_application, "get_cache_dir", lambda: Path("cache-dir"))
    monkeypatch.setattr(analysis_loading_module, "merge_project_basepicture", lambda bp, _graph: bp)

    project_application.load_project(
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
    )

    assert graph.load_stage_timings == {}
    assert graph.load_stage_timings_by_program == {}
    assert graph.graphics_load_timings == {}


def test_a_refresh_rebuilds_the_graph_but_keeps_the_verified_parser_cache(
    monkeypatch: pytest.MonkeyPatch,
):
    root_bp = named_object("TargetA", origin_file="TargetA.s")
    graph = AnalysisGraphStub(
        ast_by_name={"TargetA": root_bp},
        missing=[],
        warnings=[],
        source_files={Path("programs/TargetA.s")},
    )
    parser_cache_dirs: list[Path | None] = []
    graph_cache_loads: list[str] = []

    class FakeCache:
        def __init__(self, cache_dir: Path) -> None:
            self.cache_dir = cache_dir

        def load_validated(self, key: str) -> None:
            graph_cache_loads.append(key)
            return None

        def manifest_paths(self, _key: str) -> frozenset[Path]:
            return frozenset()

        def save(self, *_args: object, **_kwargs: object) -> None:
            return None

    def fake_build_parser_binding(
        _cfg: Mapping[str, object],
        *,
        parser_cache_dir: Path | None = None,
        **_kwargs: object,
    ) -> SimpleNamespace:
        parser_cache_dirs.append(parser_cache_dir)
        return SimpleNamespace()

    monkeypatch.setattr(project_application, "ASTCache", FakeCache)
    monkeypatch.setattr(analysis_loading_module, "build_parser_binding", fake_build_parser_binding)
    monkeypatch.setattr(analysis_loading_module, "_load_parser_graph", lambda *_args, **_kwargs: graph)
    monkeypatch.setattr(analysis_loading_module, "find_dependency_path", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(analysis_loading_module, "read_dependency_names", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(analysis_loading_module, "merge_project_basepicture", lambda bp, graph: "merged")
    cfg = cast(
        ConfigDict,
        {
            "program_dir": "programs",
            "other_lib_dirs": [],
            "ABB_lib_dir": "abb",
            "mode": "draft",
            "debug": False,
            "analyzed_programs_and_libraries": ["TargetA"],
        },
    )

    project_application.load_project(
        cfg,
        cache_key_for_target_fn=lambda _cfg, _target: "key",
        get_cache_dir_fn=lambda: Path("cache-dir"),
        refresh_ast=False,
    )
    project_application.load_project(
        cfg,
        cache_key_for_target_fn=lambda _cfg, _target: "key",
        get_cache_dir_fn=lambda: Path("cache-dir"),
        refresh_ast=True,
    )

    # A refresh rebuilds SattLint's own graph entry, so only the first load reads it.
    assert graph_cache_loads == ["key"]
    # The parser's per-file caches are verified against the source bytes, so a
    # refresh keeps them: re-parsing would be waste, not safety.
    assert parser_cache_dirs == [Path("cache-dir"), Path("cache-dir")]
