# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportPrivateUsage=false, reportArgumentType=false
from sattlint.project import loading_support as loading_support_module

from ._app_analysis_test_support import *
from .helpers import AnalysisGraphStub


def test_app_analysis_wrappers_delegate_to_underlying_helpers(monkeypatch):
    monkeypatch.setattr(
        support_module,
        "target_validation_warnings",
        lambda target, warnings: [f"{target}:{len(warnings)}"],
    )
    monkeypatch.setattr(
        project_application, "_iter_loaded_projects", lambda *_args, **_kwargs: iter([("TargetA", "bp", "g")])
    )
    monkeypatch.setattr(project_application, "_source_paths_for_current_target", lambda *_args: {Path("TargetA.s")})
    monkeypatch.setattr(project_application, "_target_is_library", lambda *_args: True)
    monkeypatch.setattr(analysis_catalog_module, "get_default_cli_analyzers", lambda: ["variables"])

    assert project_application._target_validation_warnings("TargetA", ["a", "b"]) == ["TargetA:2"]
    assert list(project_application.iter_loaded_projects({})) == [("TargetA", "bp", "g")]
    assert project_application.source_paths_for_current_target(cast(Any, "bp"), cast(Any, "graph")) == {
        Path("TargetA.s")
    }
    assert project_application.target_is_library({}, cast(Any, "bp"), cast(Any, "graph")) is True
    assert checks_application._get_enabled_analyzers() == ["variables"]


def test_target_validation_warnings_suppresses_expected_unavailable_dependency_warning():
    assert project_application._target_validation_warnings(
        "KaHAMPCSøjleLib",
        [
            "KaHAMPCSøjleLib: dependency 'controllib' unavailable: expected proprietary dependency",
            "KaHAMPCSøjleLib: warning one",
            "dep_b: warning two",
        ],
    ) == ["KaHAMPCSøjleLib: warning one"]


def test_analysis_loading_helpers_cover_target_accessors_and_refresh_formatting(monkeypatch):
    monkeypatch.setattr(support_module, "get_analyzed_targets", lambda cfg: ["TargetA"])
    monkeypatch.setattr(support_module, "require_analyzed_targets", lambda cfg: ["TargetB"])

    assert project_application._get_analyzed_targets({}) == ["TargetA"]
    assert project_application._require_analyzed_targets({}) == ["TargetB"]
    assert loading_support_module._workspace_dependency_suffixes("draft") == (".l", ".z")
    assert loading_support_module._workspace_dependency_suffixes("official") == (".z",)
    assert analysis_loading_module._format_refresh_stage_timings(
        {"load_or_parse": 0.1, "validate": 0.2, "ast_cache_save": 0.3},
        refresh_mode="ast-only",
    ) == (
        "AST refresh stage totals: "
        "load_or_parse=0.1000s, validate=0.2000s, graphics=skipped, index=skipped, ast_cache_save=0.3000s"
    )


def test_analysis_loading_reverse_consumer_helpers_cover_scan_and_queueing(monkeypatch, tmp_path):
    program_dir = tmp_path / "programs"
    other_dir = tmp_path / "other"
    error_dir = tmp_path / "error"
    missing_dir = tmp_path / "missing"
    program_dir.mkdir()
    other_dir.mkdir()
    error_dir.mkdir()

    (program_dir / "consumer.l").write_text("", encoding="utf-8")
    (program_dir / "consumer.z").write_text("", encoding="utf-8")
    (program_dir / "selected.l").write_text("", encoding="utf-8")
    (program_dir / "notes.txt").write_text("", encoding="utf-8")
    (other_dir / "consumer.z").write_text("", encoding="utf-8")
    (other_dir / "remote.z").write_text("", encoding="utf-8")

    original_iterdir = Path.iterdir

    def fake_iterdir(path: Path):
        if path == error_dir:
            raise OSError("boom")
        return original_iterdir(path)

    monkeypatch.setattr(Path, "iterdir", fake_iterdir)

    cfg = {
        "program_dir": str(program_dir),
        "other_lib_dirs": [str(other_dir), str(error_dir), str(missing_dir)],
        "mode": "draft",
    }

    assert list(loading_support_module._iter_workspace_reverse_library_consumer_dependency_files(cfg)) == [
        ("consumer", program_dir / "consumer.l"),
        ("selected", program_dir / "selected.l"),
        ("remote", other_dir / "remote.z"),
    ]

    visits: list[tuple[str, Path]] = []
    deps_paths = {
        "CandidateA": program_dir / "CandidateA.z",
        "NoDeps": program_dir / "NoDeps.z",
        "NoPath": None,
        "DupLocal": program_dir / "CandidateA.z",
    }
    deps_map = {
        None: ["Selected"],
        program_dir / "CandidateA.z": ["Selected"],
        program_dir / "NoDeps.z": ["Other"],
        other_dir / "Remote.z": ["Selected"],
        other_dir / "Ignore.z": ["Other"],
    }

    class FakeLoader:
        def _visit(self, target_name, graph, syntax_only, requester_dir=None, syntax_check=False):
            self.visit_target(target_name, graph, syntax_only, requester_dir, syntax_check)

        def _find_deps_with_context(self, target_name, requester_dir=None):
            return deps_paths[target_name]

        def _read_deps(self, deps_path):
            return deps_map.get(deps_path, [])

        def visit_target(self, target_name, graph, syntax_only, requester_dir, syntax_check):
            del graph, syntax_only, syntax_check
            visits.append((target_name, requester_dir))

        def find_dependency_path(self, target_name, requester_dir=None):
            return self._find_deps_with_context(target_name, requester_dir=requester_dir)

        def read_dependency_names(self, deps_path):
            return self._read_deps(deps_path)

    loader = FakeLoader()
    engine_stub = SimpleNamespace(is_within_directory=lambda *_args: False)
    monkeypatch.setattr(analysis_loading_module, "target_is_library", lambda *args, **kwargs: False)
    analysis_loading_module._include_reverse_library_consumers(
        cfg,
        selected_target="Selected",
        root_bp=cast(Any, SimpleNamespace(header=SimpleNamespace(name="BasePicture"))),
        graph=cast(Any, "graph"),
        loader=loader,
        require_analyzed_targets_fn=lambda _cfg: ["Selected", "CandidateA", "NoDeps", "NoPath", "DupLocal"],
        engine_module=engine_stub,
        target_is_library_fn=lambda *_a, **_kw: False,
        source_paths_for_current_target_fn=lambda _bp, _graph: set(),
    )
    assert visits == []

    monkeypatch.setattr(analysis_loading_module, "target_is_library", lambda *args, **kwargs: True)
    monkeypatch.setattr(
        loading_support_module,
        "_iter_workspace_reverse_library_consumer_dependency_files",
        lambda _cfg: iter(
            [
                ("Selected", program_dir / "selected.l"),
                ("NoIterPath", None),
                ("Remote", other_dir / "Remote.z"),
                ("Ignore", other_dir / "Ignore.z"),
                ("CandidateA", program_dir / "CandidateA.z"),
            ]
        ),
    )

    analysis_loading_module._include_reverse_library_consumers(
        cfg,
        selected_target="Selected",
        root_bp=cast(Any, SimpleNamespace(header=SimpleNamespace(name="BasePicture"))),
        graph=cast(Any, "graph"),
        loader=loader,
        require_analyzed_targets_fn=lambda _cfg: ["Selected", "CandidateA", "NoDeps", "NoPath", "DupLocal"],
        engine_module=engine_stub,
        target_is_library_fn=lambda *_a, **_kw: True,
        source_paths_for_current_target_fn=lambda _bp, _graph: set(),
    )

    assert visits == [
        ("CandidateA", program_dir),
        ("DupLocal", program_dir),
        ("Remote", other_dir),
    ]


def test_analysis_loading_cache_manifest_files_adds_companions_and_dependency_manifests():
    cfg = {"program_dir": "programs", "mode": "draft"}
    target_a = SimpleNamespace(header=SimpleNamespace(name="TargetA"), origin_file=None)
    target_b = SimpleNamespace(header=SimpleNamespace(name="TargetB"), origin_file=None)
    graph = AnalysisGraphStub(
        source_files={Path("programs/TargetA.s")},
        ast_by_name={"TargetA": target_a, "TargetB": target_b},
    )
    graph.record_root_origin("TargetA", source_path=Path("programs/TargetA.s"), library_name="programs")
    graph.record_root_origin("TargetB", source_path=Path("libraries/TargetB.s"), library_name="libraries")

    manifest_files = analysis_loading_module.cache_manifest_files(
        cfg,
        graph,
        find_dependency_path_fn=lambda target_name, requester_dir: (
            None if requester_dir is None else requester_dir / f"{target_name}.z"
        ),
        resolve_graphics_companion_path_fn=lambda source_path, **_kwargs: source_path.with_suffix(".g"),
        casefold_equal_fn=lambda left, right: left.casefold() == right.casefold(),
        casefold_key_fn=lambda value: value.casefold(),
    )

    assert manifest_files == {
        Path("programs/TargetA.s"),
        Path("programs/TargetA.g"),
        Path("programs/TargetA.z"),
        Path("libraries/TargetB.z"),
    }
