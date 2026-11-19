# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportPrivateUsage=false, reportArgumentType=false, reportIndexIssue=false

from sattlint.config import DEFAULT_CONFIG
from tests.helpers import AnalysisGraphStub, named_object
from tests.helpers.app_analysis_support import *


def test_load_project_saves_cache_after_successful_merge(monkeypatch):
    saved: dict[str, object] = {}
    root_bp = named_object("TargetA", origin_file="TargetA.s")
    graph = AnalysisGraphStub(
        ast_by_name={"TargetA": root_bp},
        missing=[],
        warnings=[],
        source_files={Path("programs/TargetA.s")},
    )

    class FakeCache:
        def __init__(self, cache_dir):
            self.cache_dir = cache_dir

        def load_validated(self, key):
            assert key == "cache-key"
            return None

        def manifest_paths(self, key):
            assert key == "cache-key"
            return frozenset()

        def save(self, key, **kwargs):
            saved.update({"key": key, **kwargs})

    def fake_build_parser_binding(
        cfg, *, status_update_fn=None, refresh_mode="full", stage_timing_sink=None, graphics_timing_sink=None
    ):
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
        {
            "program_dir": "programs",
            "other_lib_dirs": [],
            "ABB_lib_dir": "abb",
            "mode": "draft",
            "debug": False,
            "analyzed_programs_and_libraries": ["TargetA"],
        },
        cache_key_for_target_fn=lambda _cfg, _target: "cache-key",
    )

    assert result == (
        "merged",
        graph,
    )
    assert saved["key"] == "cache-key"
    assert saved["project"] == (root_bp, graph)
    assert saved["files"] == {Path("programs/TargetA.s")}


def test_load_project_runs_when_the_cache_directory_is_unusable(monkeypatch):
    root_bp = named_object("TargetA", origin_file="TargetA.s")
    graph = AnalysisGraphStub(
        ast_by_name={"TargetA": root_bp},
        missing=[],
        warnings=[],
        source_files={Path("programs/TargetA.s")},
    )

    def fake_build_parser_binding(
        cfg, *, status_update_fn=None, refresh_mode="full", stage_timing_sink=None, graphics_timing_sink=None
    ):
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
        {
            "program_dir": "programs",
            "other_lib_dirs": [],
            "ABB_lib_dir": "abb",
            "mode": "draft",
            "debug": False,
            "analyzed_programs_and_libraries": ["TargetA"],
        },
        cache_key_for_target_fn=lambda _cfg, _target: "cache-key",
        get_cache_dir_fn=lambda: None,
    )

    assert result == ("merged", graph)


def test_load_project_skips_cache_when_a_dependency_is_unavailable(monkeypatch):
    root_bp = named_object("TargetA", origin_file="TargetA.s")
    graph = AnalysisGraphStub(
        ast_by_name={"TargetA": root_bp},
        missing=["Missing code file for 'MissingLib' (draft)"],
        unavailable_libraries={"missinglib"},
        source_files={Path("programs/TargetA.s")},
    )

    class FakeCache:
        def __init__(self, cache_dir):
            self.cache_dir = cache_dir

        def load_validated(self, key):
            assert key == "cache-key"
            return None

        def manifest_paths(self, key):
            return frozenset()

        def save(self, *args, **kwargs):
            pytest.fail("an unresolved graph must not be persisted")

    monkeypatch.setattr(project_application, "ASTCache", FakeCache)
    monkeypatch.setattr(project_application, "get_cache_dir", lambda: Path("cache-dir"))
    monkeypatch.setattr(analysis_loading_module, "build_parser_binding", lambda *_args, **_kwargs: SimpleNamespace())
    monkeypatch.setattr(analysis_loading_module, "_load_parser_graph", lambda *_args, **_kwargs: graph)
    monkeypatch.setattr(analysis_loading_module, "find_dependency_path", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(analysis_loading_module, "read_dependency_names", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(analysis_loading_module, "merge_project_basepicture", lambda bp, _graph: bp)

    result = project_application.load_project(
        {
            "program_dir": "programs",
            "other_lib_dirs": [],
            "ABB_lib_dir": "abb",
            "mode": "draft",
            "debug": False,
            "analyzed_programs_and_libraries": ["TargetA"],
        },
        cache_key_for_target_fn=lambda _cfg, _target: "cache-key",
    )

    assert result == (root_bp, graph)
    assert graph.analysis_cache_key is None


def test_load_project_raises_default_error_when_target_missing(monkeypatch):
    class FakeCache:
        def __init__(self, cache_dir):
            self.cache_dir = cache_dir

        def load_validated(self, key):
            assert key == "cache-key"
            return None

        def manifest_paths(self, key):
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
            {
                "program_dir": "programs",
                "other_lib_dirs": [],
                "ABB_lib_dir": "abb",
                "mode": "draft",
                "debug": False,
                "analyzed_programs_and_libraries": ["TargetA"],
            },
            cache_key_for_target_fn=lambda _cfg, _target: "cache-key",
        )


def test_load_project_raises_value_error_when_loader_config_missing(monkeypatch):
    monkeypatch.setattr(
        project_application, "ASTCache", lambda cache_dir: pytest.fail(f"unexpected cache init: {cache_dir}")
    )
    monkeypatch.setattr(project_application, "get_cache_dir", lambda: Path("cache-dir"))

    with pytest.raises(ValueError, match="Missing loader config keys: debug"):
        project_application.load_project(
            {
                "program_dir": "programs",
                "other_lib_dirs": [],
                "ABB_lib_dir": "abb",
                "mode": "draft",
                "analyzed_programs_and_libraries": ["TargetA"],
            },
            cache_key_for_target_fn=lambda _cfg, _target: "cache-key",
        )


def test_load_program_ast_returns_loaded_program(monkeypatch):
    monkeypatch.setattr(
        analysis_loading_module,
        "_load_parser_graph",
        lambda _binding, program_name, **_kwargs: SimpleNamespace(ast_by_name={program_name: "bp-main"}),
    )

    result = project_application.load_program_ast(
        {
            "program_dir": "programs",
            "other_lib_dirs": [],
            "ABB_lib_dir": "abb",
            "mode": "draft",
            "debug": False,
        },
        "TargetA",
    )

    assert result == ("bp-main", SimpleNamespace(ast_by_name={"TargetA": "bp-main"}))


def test_ensure_ast_cache_returns_true_without_targets():
    assert project_application.ensure_ast_cache({}, get_analyzed_targets_fn=lambda _cfg: []) is True


def test_load_project_uses_cached_ast_only_project_and_manifest_metadata(monkeypatch):
    root_bp = named_object("TargetA", origin_file="TargetA.s")
    graph = AnalysisGraphStub()

    class FakeCache:
        def __init__(self, cache_dir):
            self.cache_dir = cache_dir

        def load_validated(self, key):
            assert key == "cache-key"
            return {"project": (root_bp, graph)}

        def manifest_paths(self, key):
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
        {
            "program_dir": "programs",
            "other_lib_dirs": [],
            "ABB_lib_dir": "abb",
            "mode": "draft",
            "debug": False,
            "analyzed_programs_and_libraries": ["TargetA"],
        },
        cache_key_for_target_fn=lambda _cfg, _target: "cache-key",
        refresh_mode="ast-only",
    )

    assert result == (root_bp, graph)
    assert graph.analysis_cache_key == "cache-key"
    assert graph.analysis_manifest_files == frozenset({Path("programs/TargetA.z")})


def test_load_project_ast_only_collects_stage_timings(monkeypatch):
    root_bp = named_object("TargetA", origin_file="TargetA.s")
    graph = AnalysisGraphStub(ast_by_name={"TargetA": root_bp})

    class FakeCache:
        def __init__(self, cache_dir):
            self.cache_dir = cache_dir

        def load_validated(self, key):
            assert key == "cache-key"
            return None

        def manifest_paths(self, key):
            assert key == "cache-key"
            return frozenset()

        def save(self, *args, **kwargs):
            pytest.fail("ast-only refresh should return before saving cache")

    def fake_build_parser_binding(cfg, *, status_update_fn=None, stage_timing_sink=None, graphics_timing_sink=None):
        return SimpleNamespace(
            stage_timing_sink=stage_timing_sink,
            graphics_timing_sink=graphics_timing_sink,
        )

    def fake_load_parser_graph(binding, target_name, *, strict, lib_names, validate, index_program_view):
        assert strict is False
        assert validate.value == "none"
        assert index_program_view is False
        assert binding.stage_timing_sink is not None
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
        {
            "program_dir": "programs",
            "other_lib_dirs": [],
            "ABB_lib_dir": "abb",
            "mode": "draft",
            "debug": False,
            "analyzed_programs_and_libraries": ["TargetA"],
        },
        cache_key_for_target_fn=lambda _cfg, _target: "cache-key",
        refresh_mode="ast-only",
        collect_stage_timings=True,
    )

    assert result == (root_bp, graph)
    assert graph.load_stage_timings == {"load_or_parse": 0.1, "validate": 0.2}
    assert graph.load_stage_timings_by_program == {"TargetA": {"load_or_parse": 0.1, "validate": 0.2}}
    assert graph.graphics_load_timings == {"attach-graphics": 0.3}
    assert graph.graphics_load_timings_by_program == {"TargetA": {"attach-graphics": 0.3}}


def test_load_project_uses_custom_target_load_error_factory(monkeypatch):
    captured: dict[str, object] = {}

    class CustomLoadError(RuntimeError):
        pass

    class FakeCache:
        def __init__(self, cache_dir):
            self.cache_dir = cache_dir

        def load_validated(self, key):
            assert key == "cache-key"
            return None

        def manifest_paths(self, key):
            assert key == "cache-key"
            return frozenset()

    def fake_build_parser_binding(
        cfg, *, status_update_fn=None, refresh_mode="full", stage_timing_sink=None, graphics_timing_sink=None
    ):
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

    def make_error(target_name, **kwargs):
        captured.update({"target_name": target_name, **kwargs})
        return CustomLoadError(f"custom:{target_name}")

    with pytest.raises(CustomLoadError, match="custom:TargetA"):
        project_application.load_project(
            {
                "program_dir": "programs",
                "other_lib_dirs": [],
                "ABB_lib_dir": "abb",
                "mode": "draft",
                "debug": False,
                "analyzed_programs_and_libraries": ["TargetA"],
            },
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


def test_load_program_ast_raises_when_program_missing(monkeypatch):
    monkeypatch.setattr(
        analysis_loading_module,
        "_load_parser_graph",
        lambda *_args, **_kwargs: SimpleNamespace(ast_by_name={"Other": "bp-other"}),
    )

    with pytest.raises(RuntimeError, match="Program 'TargetA' not parsed"):
        project_application.load_program_ast(
            {
                "program_dir": "programs",
                "other_lib_dirs": [],
                "ABB_lib_dir": "abb",
                "mode": "draft",
                "debug": False,
            },
            "TargetA",
        )


def test_iter_loaded_projects_passes_collect_stage_timings_to_load_project(monkeypatch):
    seen: list[tuple[str | None, bool, bool]] = []

    def fake_load_project(_cfg, target_name=None, *, use_cache=True, collect_stage_timings=False, **_kwargs):
        seen.append((target_name, use_cache, collect_stage_timings))
        return named_object(target_name or "Unknown"), AnalysisGraphStub()

    monkeypatch.setattr(project_application, "emit_output", lambda *_args, **_kwargs: None)

    results = list(
        project_application.iter_loaded_projects(
            {"analyzed_programs_and_libraries": ["TargetA"], "debug": True},
            use_cache=False,
            require_analyzed_targets_fn=lambda _cfg: ["TargetA"],
            load_project_fn=fake_load_project,
        )
    )

    assert [target_name for target_name, _bp, _graph in results] == ["TargetA"]
    assert seen == [("TargetA", False, True)]


def test_ensure_ast_cache_covers_cache_hit_stale_missing_and_failure(monkeypatch):
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
        def __init__(self, cache_dir):
            self.cache_dir = cache_dir

        def has_payload(self, key):
            return cache_state[key][0]

        def has_manifest(self, key):
            return cache_state[key][1]

        def has_cache_artifact(self, key):
            return cache_state[key][2]

    def fake_load_project(_cfg, *, target_name, use_cache, **kwargs):
        load_calls.append((target_name, use_cache))
        if target_name == "TargetE":
            raise RuntimeError("boom")
        return SimpleNamespace(), SimpleNamespace()

    monkeypatch.setattr(project_application, "emit_output", lambda message: lines.append(str(message)))

    ok = project_application.ensure_ast_cache(
        {},
        get_analyzed_targets_fn=lambda _cfg: ["TargetA", "TargetB", "TargetC", "TargetD", "TargetE"],
        cache_key_for_target_fn=lambda _cfg, target_name: target_name,
        load_project_fn=fake_load_project,
        ast_cache_cls=FakeCache,
        get_cache_dir_fn=lambda: Path("cache-dir"),
    )

    assert ok is False
    assert load_calls == [
        ("TargetB", False),
        ("TargetC", False),
        ("TargetD", False),
        ("TargetE", False),
    ]
    assert any("AST cache OK" in line for line in lines)
    assert any("AST cache stale; rebuilding" in line for line in lines)
    assert any("AST cache missing file manifest; rebuilding" in line for line in lines)
    assert any("AST cache missing; building" in line for line in lines)
    assert any("AST cache updated" in line for line in lines)
    assert any("Failed to build AST cache for TargetE: boom" in line for line in lines)


def test_run_checks_success_path_pauses(monkeypatch):
    lines: list[str] = []
    pauses: list[str] = []

    monkeypatch.setattr(output_module, "emit_output", lambda message: lines.append(message))

    checks_application.run_checks(
        DEFAULT_CONFIG.copy(),
        ["state-inference"],
        iter_loaded_projects_fn=cast(
            Any,
            lambda *_args, **_kwargs: iter(
                [
                    (
                        "TargetA",
                        SimpleNamespace(header=SimpleNamespace(name="TargetA")),
                        SimpleNamespace(unavailable_libraries=set()),
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


def test_load_project_does_not_build_a_parser_cache_when_the_directory_is_unavailable(monkeypatch):
    root_bp = named_object("TargetA", origin_file="TargetA.s")
    graph = AnalysisGraphStub(
        ast_by_name={"TargetA": root_bp},
        missing=[],
        warnings=[],
        source_files={Path("programs/TargetA.s")},
    )

    def _unexpected(*_args, **_kwargs):
        raise AssertionError("the AST cache must not be built without a cache directory")

    monkeypatch.setattr(analysis_loading_module, "build_parser_binding", lambda *_args, **_kwargs: SimpleNamespace())
    monkeypatch.setattr(analysis_loading_module, "_load_parser_graph", lambda *_args, **_kwargs: graph)
    monkeypatch.setattr(analysis_loading_module, "find_dependency_path", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(analysis_loading_module, "read_dependency_names", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(analysis_loading_module, "merge_project_basepicture", lambda bp, _graph: bp)
    monkeypatch.setattr(analysis_loading_module.cache_module, "build_ast_cache", _unexpected)

    result = project_application.load_project(
        {
            "program_dir": "programs",
            "other_lib_dirs": [],
            "ABB_lib_dir": "abb",
            "mode": "draft",
            "debug": False,
            "analyzed_programs_and_libraries": ["TargetA"],
        },
        cache_key_for_target_fn=lambda _cfg, _target: "cache-key",
        get_cache_dir_fn=lambda: None,
    )

    assert result == (root_bp, graph)
