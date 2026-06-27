# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportPrivateUsage=false, reportArgumentType=false, reportIndexIssue=false
# ruff: noqa: F403, F405
from ._app_analysis_test_support import *
from .helpers import AnalysisGraphStub, named_object


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

    monkeypatch.setattr(app_analysis, "ASTCache", FakeCache)
    monkeypatch.setattr(app_analysis, "get_cache_dir", lambda: Path("cache-dir"))
    monkeypatch.setattr(app_analysis.engine_module, "SattLineProjectLoader", FakeLoader)
    monkeypatch.setattr(app_analysis.engine_module, "merge_project_basepicture", lambda bp, graph: "merged")

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

    monkeypatch.setattr(app_analysis, "ASTCache", FakeCache)
    monkeypatch.setattr(app_analysis, "get_cache_dir", lambda: Path("cache-dir"))
    monkeypatch.setattr(app_analysis.engine_module, "SattLineProjectLoader", FakeLoader)

    with pytest.raises(RuntimeError, match="Target 'TargetA' was not parsed"):
        app_analysis.load_project(
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
        )


def test_load_project_raises_value_error_when_loader_config_missing(monkeypatch):
    monkeypatch.setattr(app_analysis, "ASTCache", lambda cache_dir: pytest.fail(f"unexpected cache init: {cache_dir}"))
    monkeypatch.setattr(app_analysis, "get_cache_dir", lambda: Path("cache-dir"))

    with pytest.raises(ValueError, match="Missing loader config keys: debug"):
        app_analysis.load_project(
            {
                "program_dir": "programs",
                "other_lib_dirs": [],
                "ABB_lib_dir": "abb",
                "mode": "draft",
                "scan_root_only": True,
                "analyzed_programs_and_libraries": ["TargetA"],
            },
            cache_key_for_target_fn=lambda _cfg, _target: "cache-key",
        )


def test_load_program_ast_force_dependency_resolution_returns_loaded_program(monkeypatch):
    seen_kwargs: dict[str, object] = {}

    class FakeLoader:
        def __init__(self, **kwargs):
            seen_kwargs.update(kwargs)
            self.kwargs = kwargs

        def resolve(self, program_name, strict=False):
            return SimpleNamespace(ast_by_name={program_name: "bp-main"})

    monkeypatch.setattr(app_analysis.engine_module, "SattLineProjectLoader", FakeLoader)

    result = app_analysis.load_program_ast(
        {
            "program_dir": "programs",
            "other_lib_dirs": [],
            "ABB_lib_dir": "abb",
            "mode": "draft",
            "scan_root_only": True,
            "debug": False,
        },
        "TargetA",
        force_dependency_resolution=True,
    )

    assert result == ("bp-main", SimpleNamespace(ast_by_name={"TargetA": "bp-main"}))
    assert seen_kwargs["scan_root_only"] is False


def test_force_refresh_ast_returns_none_without_targets():
    assert app_analysis.force_refresh_ast({}, get_analyzed_targets_fn=lambda _cfg: []) is None


def test_ensure_ast_cache_returns_true_without_targets():
    assert app_analysis.ensure_ast_cache({}, get_analyzed_targets_fn=lambda _cfg: []) is True


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

    monkeypatch.setattr(app_analysis, "ASTCache", FakeCache)
    monkeypatch.setattr(app_analysis, "get_cache_dir", lambda: Path("cache-dir"))
    monkeypatch.setattr(
        app_analysis.engine_module,
        "merge_project_basepicture",
        lambda *_args, **_kwargs: pytest.fail("ast-only cache hit should not merge project view"),
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

    monkeypatch.setattr(app_analysis, "ASTCache", FakeCache)
    monkeypatch.setattr(app_analysis, "get_cache_dir", lambda: Path("cache-dir"))
    monkeypatch.setattr(app_analysis.engine_module, "SattLineProjectLoader", FakeLoader)

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

    monkeypatch.setattr(app_analysis, "ASTCache", FakeCache)
    monkeypatch.setattr(app_analysis, "get_cache_dir", lambda: Path("cache-dir"))
    monkeypatch.setattr(app_analysis.engine_module, "SattLineProjectLoader", FakeLoader)

    with pytest.raises(CustomLoadError, match="custom:TargetA"):
        app_analysis.load_project(
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
            force_dependency_resolution=False,
        )


def test_force_refresh_ast_emits_stage_timings_and_telemetry(monkeypatch):
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

    monkeypatch.setattr(app_analysis, "emit_output", lambda message: lines.append(str(message)))
    monkeypatch.setattr(app_analysis.telemetry_module, "create_app_telemetry", lambda cfg: FakeTelemetry())

    result = app_analysis.force_refresh_ast(
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

    monkeypatch.setattr(app_analysis, "emit_output", lambda *_args, **_kwargs: None)

    results = list(
        app_analysis.iter_loaded_projects(
            {"analyzed_programs_and_libraries": ["TargetA"], "debug": True},
            use_cache=False,
            require_analyzed_targets_fn=lambda _cfg: ["TargetA"],
            load_project_fn=fake_load_project,
        )
    )

    assert [target_name for target_name, _bp, _graph in results] == ["TargetA"]
    assert seen == [("TargetA", False, True)]


def test_force_refresh_ast_emits_basic_telemetry_when_stage_timings_disabled(monkeypatch):
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
    monkeypatch.setattr(app_analysis, "emit_output", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(app_analysis.telemetry_module, "create_app_telemetry", lambda cfg: FakeTelemetry())

    app_analysis.force_refresh_ast(
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

    monkeypatch.setattr(app_analysis, "emit_output", lambda message: lines.append(str(message)))

    ok = app_analysis.ensure_ast_cache(
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
        app_analysis,
        "_iter_loaded_projects",
        lambda *_args, **_kwargs: iter([("ProgramA", "bp", AnalysisGraphStub())]),
    )
    monkeypatch.setattr(
        app_analysis,
        "analyze_variables",
        lambda *_, **__: analyze_variables_calls.append("called") or make_variable_report(),
    )
    monkeypatch.setattr(app_analysis, "analyze_shadowing", lambda *_, **__: make_shadowing_report("ShadowOnly"))

    pauses: list[str] = []
    app_analysis_commands.run_variable_analysis(
        app.DEFAULT_CONFIG.copy(),
        {IssueKind.SHADOWING},
        pause_fn=lambda: pauses.append("pause"),
    )

    out = capsys.readouterr().out
    assert analyze_variables_calls == []
    assert "=== Target: ProgramA ===" in out
    assert pauses == ["pause"]


def test_run_datatype_usage_analysis_reports_success_error_and_pause(monkeypatch):
    lines: list[str] = []
    pauses: list[str] = []

    monkeypatch.setattr(app_analysis, "emit_output", lambda message: lines.append(message))
    monkeypatch.setattr(builtins, "input", make_input(["FlowVar"]))

    def fake_analyze(project_bp, var_name, debug=False, unavailable_libraries=None):
        if project_bp == "bp-b":
            raise RuntimeError("boom")
        return f"datatype:{project_bp}:{var_name}"

    monkeypatch.setattr(variables_reporting_module, "report_datatype_usage", fake_analyze)

    app_analysis_commands.run_datatype_usage_analysis(
        app.DEFAULT_CONFIG.copy(),
        iter_loaded_projects_fn=cast(
            Any,
            lambda *_args, **_kwargs: iter(
                [
                    ("TargetA", "bp-a", AnalysisGraphStub()),
                    ("TargetB", "bp-b", AnalysisGraphStub()),
                ]
            ),
        ),
        pause_fn=lambda: pauses.append("pause"),
    )

    assert any("datatype:bp-a:FlowVar" in line for line in lines)
    assert any("Error during analysis for TargetB: boom" in line for line in lines)
    assert pauses == ["pause"]


def test_parse_index_selection_ignores_malformed_range_tokens():
    assert app_analysis.parse_index_selection("1-a, 2", 4) == [2]


def test_run_module_duplicates_analysis_handles_missing_matches_default_compare_and_errors(monkeypatch):
    lines: list[str] = []
    pauses: list[str] = []
    matches = [(["Root", "Area", "PumpA"], SimpleNamespace(datecode=101))]

    monkeypatch.setattr(builtins, "input", make_input(["Missing, Pump, Boom", ""]))
    monkeypatch.setattr(app_analysis, "emit_output", lambda message: lines.append(message))

    def fake_find_modules(_project_bp, module_name, debug=False):
        if module_name == "Missing":
            return []
        if module_name == "Pump":
            return matches
        raise RuntimeError("boom")

    monkeypatch.setattr(app_analysis, "find_modules_by_name", fake_find_modules)
    monkeypatch.setattr(
        app_analysis,
        "analyze_module_duplicates",
        lambda *_args, **_kwargs: SimpleNamespace(summary=lambda: "default comparison summary"),
    )

    app_analysis_commands.run_module_duplicates_analysis(
        app.DEFAULT_CONFIG.copy(),
        iter_loaded_projects_fn=cast(Any, lambda *_args, **_kwargs: iter([("TargetA", "bp", AnalysisGraphStub())])),
        pause_fn=lambda: pauses.append("pause"),
    )

    assert any("No modules found with name 'Missing'." in line for line in lines)
    assert any("default comparison summary" in line for line in lines)
    assert any("Error during analysis for 'Boom': boom" in line for line in lines)
    assert pauses == ["pause"]


def test_run_module_find_by_name_rejects_empty_name(monkeypatch):
    lines: list[str] = []
    pauses: list[str] = []

    monkeypatch.setattr(builtins, "input", lambda _prompt="": "   ")
    monkeypatch.setattr(app_analysis, "emit_output", lambda message: lines.append(message))

    app_analysis_commands.run_module_find_by_name(
        app.DEFAULT_CONFIG.copy(),
        iter_loaded_projects_fn=lambda *_args, **_kwargs: pytest.fail("should not load projects"),
        pause_fn=lambda: pauses.append("pause"),
    )

    assert any("No module name provided" in line for line in lines)
    assert pauses == ["pause"]


def test_run_module_tree_debug_reports_errors_and_pauses(monkeypatch):
    lines: list[str] = []
    pauses: list[str] = []

    monkeypatch.setattr(app_analysis, "emit_output", lambda message: lines.append(message))
    monkeypatch.setattr(
        app_analysis, "debug_module_structure", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("boom"))
    )

    app_analysis_commands.run_module_tree_debug(
        app.DEFAULT_CONFIG.copy(),
        prompt_fn=lambda _message, _default: "7",
        iter_loaded_projects_fn=cast(Any, lambda *_args, **_kwargs: iter([("TargetA", "bp", AnalysisGraphStub())])),
        pause_fn=lambda: pauses.append("pause"),
    )

    assert any("Error during debug: boom" in line for line in lines)
    assert pauses == ["pause"]


def test_run_module_localvar_analysis_reports_errors_and_pauses(monkeypatch):
    lines: list[str] = []
    pauses: list[str] = []

    monkeypatch.setattr(app_analysis, "emit_output", lambda message: lines.append(message))
    monkeypatch.setattr(builtins, "input", make_input(["UnitA", "Dv"]))

    reporting_module = pytest.importorskip("sattlint.analyzers.variable_usage_reporting")

    def fake_analyze_module_localvar_fields(project_bp, module_path, var_name, debug=False):
        if project_bp == "bp-b":
            raise RuntimeError("boom")
        return "field report"

    monkeypatch.setattr(reporting_module, "report_module_localvar_fields", fake_analyze_module_localvar_fields)

    app_analysis_commands.run_module_localvar_analysis(
        app.DEFAULT_CONFIG.copy(),
        load_project_fn=cast(Any, lambda _cfg: (named_object("BasePicture"), AnalysisGraphStub())),
        iter_loaded_projects_fn=cast(
            Any,
            lambda *_args, **_kwargs: iter(
                [
                    ("TargetA", "bp-a", AnalysisGraphStub()),
                    ("TargetB", "bp-b", AnalysisGraphStub()),
                ]
            ),
        ),
        pause_fn=lambda: pauses.append("pause"),
    )

    assert any("field report" in line for line in lines)
    assert any("Error during analysis for TargetB: boom" in line for line in lines)
    assert pauses == ["pause"]


def test_run_checks_success_path_pauses(monkeypatch):
    lines: list[str] = []
    pauses: list[str] = []

    monkeypatch.setattr(app_analysis, "emit_output", lambda message: lines.append(message))

    app_analysis_checks.run_checks(
        app.DEFAULT_CONFIG.copy(),
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

    monkeypatch.setattr(app_analysis, "emit_output", lambda message: lines.append(message))
    monkeypatch.setattr(app_analysis, "parse_icf_file", lambda _path: [SimpleNamespace()])
    monkeypatch.setattr(app_analysis.engine_module, "merge_project_basepicture", lambda bp, _graph: bp)

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

    app_analysis_commands.run_icf_validation(
        app.DEFAULT_CONFIG.copy(),
        configured_icf_files_fn=lambda _cfg: (icf_dir, [valid_file]),
        load_program_ast_fn=cast(Any, lambda _cfg, _program_name: ("bp-valid", graph)),
        validate_icf_entries_against_program_fn=fake_validate,
        pause_fn=lambda: pauses.append("pause"),
    )

    moduletype_index = cast(dict[str, list[object]], captured["moduletype_index"])
    assert list(moduletype_index) == ["pumptype", "valvetype"]
    assert any("icf report" in line for line in lines)
    assert pauses == ["pause"]


def test_run_debug_variable_usage_reports_errors_and_pauses(monkeypatch):
    lines: list[str] = []
    pauses: list[str] = []

    monkeypatch.setattr(app_analysis, "emit_output", lambda message: lines.append(message))
    monkeypatch.setattr(builtins, "input", make_input(["FlowVar"]))
    monkeypatch.setattr(
        app_analysis,
        "debug_variable_usage",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    app_analysis_commands.run_debug_variable_usage(
        app.DEFAULT_CONFIG.copy(),
        iter_loaded_projects_fn=cast(Any, lambda *_args, **_kwargs: iter([("TargetA", "bp-a", SimpleNamespace())])),
        pause_fn=lambda: pauses.append("pause"),
    )

    assert any("Error during debug for TargetA: boom" in line for line in lines)
    assert pauses == ["pause"]
