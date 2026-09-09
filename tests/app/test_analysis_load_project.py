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

    class FakeLoader:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def resolve(self, target_name, strict=False):
            return graph

        def _find_deps_with_context(self, target_name, requester_dir):
            return None

        def find_dependency_path(self, target_name, requester_dir=None):
            return self._find_deps_with_context(target_name, requester_dir)

    monkeypatch.setattr(project_application, "ASTCache", FakeCache)
    monkeypatch.setattr(project_application, "get_cache_dir", lambda: Path("cache-dir"))
    monkeypatch.setattr(analysis_loading_module, "SattLineProjectLoader", FakeLoader)
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

    class FakeLoader:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def resolve(self, target_name, strict=False):
            return SimpleNamespace(ast_by_name={}, missing=[], warnings=[], source_files=set())

        def _find_deps_with_context(self, target_name, requester_dir):
            return None

        def find_dependency_path(self, target_name, requester_dir=None):
            return self._find_deps_with_context(target_name, requester_dir)

    monkeypatch.setattr(project_application, "ASTCache", FakeCache)
    monkeypatch.setattr(project_application, "get_cache_dir", lambda: Path("cache-dir"))
    monkeypatch.setattr(analysis_loading_module, "SattLineProjectLoader", FakeLoader)

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
    seen_kwargs: dict[str, object] = {}

    class FakeLoader:
        def __init__(self, **kwargs):
            seen_kwargs.update(kwargs)
            self.kwargs = kwargs

        def resolve(self, program_name, strict=False):
            return SimpleNamespace(ast_by_name={program_name: "bp-main"})

    monkeypatch.setattr(analysis_loading_module, "SattLineProjectLoader", FakeLoader)

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


def test_force_refresh_ast_returns_none_without_targets():
    assert project_application.force_refresh_ast({}, get_analyzed_targets_fn=lambda _cfg: []) is None


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


def test_load_project_ast_only_collects_stage_timings_and_flushes_lookup_cache(monkeypatch):
    flushed: list[str] = []
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

    class FakeLoader:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def resolve(self, target_name, strict=False):
            assert strict is False
            self.kwargs["stage_timing_sink"]("TargetA", "load_or_parse", 0.1)
            self.kwargs["stage_timing_sink"]("TargetA", "validate", 0.2)
            self.kwargs["graphics_timing_sink"]("TargetA", "attach-graphics", 0.3)
            return graph

        def _find_deps_with_context(self, target_name, requester_dir):
            return None

        def _read_deps(self, deps_path):
            return []

        def find_dependency_path(self, target_name, requester_dir=None):
            return self._find_deps_with_context(target_name, requester_dir)

        def read_dependency_names(self, deps_path):
            return self._read_deps(deps_path)

        def _flush_lookup_cache(self):
            flushed.append("flushed")

    monkeypatch.setattr(project_application, "ASTCache", FakeCache)
    monkeypatch.setattr(project_application, "get_cache_dir", lambda: Path("cache-dir"))
    monkeypatch.setattr(analysis_loading_module, "SattLineProjectLoader", FakeLoader)

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
    assert flushed == ["flushed"]


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

    class FakeLoader:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def resolve(self, target_name, strict=False):
            return SimpleNamespace(ast_by_name={}, missing=["missing-lib"], warnings=["warn-lib"], source_files=set())

        def _find_deps_with_context(self, target_name, requester_dir):
            return Path("programs/TargetA.z")

        def _read_deps(self, deps_path):
            return ["DepA"]

        def find_dependency_path(self, target_name, requester_dir=None):
            return self._find_deps_with_context(target_name, requester_dir)

        def read_dependency_names(self, deps_path):
            return self._read_deps(deps_path)

        def _flush_lookup_cache(self):
            return None

    def make_error(target_name, **kwargs):
        captured.update({"target_name": target_name, **kwargs})
        return CustomLoadError(f"custom:{target_name}")

    monkeypatch.setattr(project_application, "ASTCache", FakeCache)
    monkeypatch.setattr(project_application, "get_cache_dir", lambda: Path("cache-dir"))
    monkeypatch.setattr(analysis_loading_module, "SattLineProjectLoader", FakeLoader)

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
    }


def test_load_program_ast_raises_when_program_missing(monkeypatch):
    class FakeLoader:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def resolve(self, program_name, strict=False):
            return SimpleNamespace(ast_by_name={"Other": "bp-other"})

    monkeypatch.setattr(analysis_loading_module, "SattLineProjectLoader", FakeLoader)

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


def test_force_refresh_ast_emits_stage_timings_and_profiling(monkeypatch):
    lines: list[str] = []
    clears: list[str] = []
    emitted: list[dict[str, object]] = []
    results = {
        "TargetA": (
            named_object("TargetA"),
            AnalysisGraphStub(
                load_stage_timings={"load_or_parse": 0.1}, graphics_load_timings={"attach-graphics": 0.2}
            ),
        ),
        "TargetB": (named_object("TargetB"), SimpleNamespace()),
    }

    class FakeCache:
        def __init__(self, cache_dir):
            self.cache_dir = cache_dir

        def clear(self, key):
            clears.append(key)

    class FakeTelemetry:
        enabled = True

        def emit(self, **payload):
            emitted.append(payload)

    monkeypatch.setattr(project_application, "emit_output", lambda message: lines.append(str(message)))
    monkeypatch.setattr(profiling_module, "create_profiler", lambda: FakeTelemetry())

    result = project_application.force_refresh_ast(
        {"debug": False},
        get_analyzed_targets_fn=lambda _cfg: ["TargetA", "TargetB"],
        cache_key_for_target_fn=lambda _cfg, target_name: f"key:{target_name}",
        load_project_fn=lambda _cfg, *, target_name, **kwargs: results[target_name],
        ast_cache_cls=FakeCache,
        get_cache_dir_fn=lambda: Path("cache-dir"),
    )

    assert result == results["TargetB"]
    assert clears == ["key:TargetA", "key:TargetB"]
    assert any("Refreshing AST caches for 2 target(s)..." in line for line in lines)
    assert any(
        "AST refresh stage totals: load_or_parse=0.1000s, graphics=skipped, index=skipped" in line for line in lines
    )
    assert emitted[0]["target_name"] == "TargetA"
    assert emitted[0]["payload"]["refresh_mode"] == "ast-only"
    assert emitted[0]["payload"]["stage_timings_s"] == {"load_or_parse": 0.1}
    assert emitted[0]["payload"]["stage_timings_ms"] == {"load_or_parse": 100.0}
    assert emitted[0]["payload"]["stage_bottleneck"] == {
        "kind": "stage",
        "name": "load_or_parse",
        "duration_ms": 100.0,
    }
    assert emitted[0]["payload"]["graphics_timings_ms"] == {"attach-graphics": 200.0}
    assert emitted[0]["payload"]["graphics_bottleneck"] == {
        "kind": "graphics-phase",
        "name": "attach-graphics",
        "duration_ms": 200.0,
    }
    assert emitted[0]["payload"]["bottleneck_kind"] == "graphics-phase"
    assert emitted[0]["payload"]["bottleneck"] == {
        "kind": "graphics-phase",
        "name": "attach-graphics",
        "duration_ms": 200.0,
    }
    assert emitted[1]["target_name"] == "TargetB"
    assert emitted[1]["payload"] == {"refresh_mode": "ast-only"}


def test_iter_loaded_projects_passes_collect_stage_timings_to_load_project(monkeypatch):
    seen: list[tuple[str | None, bool, bool]] = []

    def fake_load_project(_cfg, target_name=None, *, use_cache=True, collect_stage_timings=False, **_kwargs):
        seen.append((target_name, use_cache, collect_stage_timings))
        return named_object(target_name or "Unknown"), SimpleNamespace()

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


def test_force_refresh_ast_emits_basic_profiling_when_stage_timings_disabled(monkeypatch):
    emitted: list[dict[str, object]] = []

    class FakeCache:
        def __init__(self, cache_dir):
            self.cache_dir = cache_dir

        def clear(self, key):
            return None

    class FakeTelemetry:
        enabled = False

        def emit(self, **payload):
            emitted.append(payload)

    calls: list[bool] = []
    monkeypatch.setattr(project_application, "emit_output", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(profiling_module, "create_profiler", lambda: FakeTelemetry())

    project_application.force_refresh_ast(
        {"debug": False},
        get_analyzed_targets_fn=lambda _cfg: ["TargetA"],
        cache_key_for_target_fn=lambda _cfg, target_name: target_name,
        load_project_fn=lambda _cfg, *, target_name, collect_stage_timings, **kwargs: (
            calls.append(collect_stage_timings) or (named_object(target_name), SimpleNamespace())
        ),
        ast_cache_cls=FakeCache,
        get_cache_dir_fn=lambda: Path("cache-dir"),
    )

    assert calls == [False]
    assert emitted == [
        {
            "operation": "ast-refresh",
            "target_name": "TargetA",
            "duration_ms": emitted[0]["duration_ms"],
            "success": True,
            "payload": {"refresh_mode": "ast-only"},
        }
    ]


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


def test_run_variable_analysis_shadowing_only_uses_shadowing_report_and_pauses(monkeypatch, capsys):
    analyze_variables_calls: list[str] = []

    monkeypatch.setattr(
        project_application,
        "_iter_loaded_projects",
        lambda *_args, **_kwargs: iter([("ProgramA", "bp", AnalysisGraphStub())]),
    )
    monkeypatch.setattr(
        commands_application,
        "analyze_variables",
        lambda *_, **__: analyze_variables_calls.append("called") or make_variable_report(),
    )
    monkeypatch.setattr(commands_application, "analyze_shadowing", lambda *_, **__: make_shadowing_report("ShadowOnly"))

    pauses: list[str] = []
    commands_application.run_variable_analysis(
        DEFAULT_CONFIG.copy(),
        {IssueKind.SHADOWING},
        pause_fn=lambda: pauses.append("pause"),
    )

    out = capsys.readouterr().out
    assert analyze_variables_calls == []
    assert "=== Target: ProgramA ===" in out
    assert pauses == ["pause"]


def test_parse_index_selection_ignores_malformed_range_tokens():
    assert commands_application.parse_index_selection("1-a, 2", 4) == [2]


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


def test_run_icf_validation_builds_moduletype_index(monkeypatch, tmp_path):
    lines: list[str] = []
    pauses: list[str] = []
    captured: dict[str, object] = {}
    icf_dir = tmp_path / "icf"
    icf_dir.mkdir()
    valid_file = icf_dir / "Valid.icf"
    valid_file.write_text("dummy", encoding="utf-8")

    monkeypatch.setattr(output_module, "emit_output", lambda message: lines.append(message))
    monkeypatch.setattr(commands_application, "parse_icf_file", lambda _path: [SimpleNamespace()])
    monkeypatch.setattr(commands_application, "merge_project_basepicture", lambda bp, _graph: bp)

    graph = SimpleNamespace(
        ast_by_name={
            "Valid": SimpleNamespace(
                moduletype_defs=[SimpleNamespace(name="PumpType"), SimpleNamespace(name="ValveType")]
            )
        }
    )

    def fake_validate(program_bp, entries, expected_program, debug=False, moduletype_index=None):
        captured["moduletype_index"] = moduletype_index
        return SimpleNamespace(
            total_entries=1,
            valid_entries=1,
            issues=[],
            skipped_entries=0,
            summary=lambda: "icf report",
        )

    commands_application.run_icf_validation(
        DEFAULT_CONFIG.copy(),
        configured_icf_files_fn=lambda _cfg: (icf_dir, [valid_file]),
        load_program_ast_fn=cast(Any, lambda _cfg, _program_name: ("bp-valid", graph)),
        validate_icf_entries_against_program_fn=fake_validate,
        pause_fn=lambda: pauses.append("pause"),
    )

    moduletype_index = cast(dict[str, list[object]], captured["moduletype_index"])
    assert list(moduletype_index) == ["pumptype", "valvetype"]
    assert any("icf report" in line for line in lines)
    assert pauses == ["pause"]
