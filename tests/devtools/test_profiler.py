import json
from types import SimpleNamespace

from sattlint.devtools import profiler


def _clock(values: list[float]):
    iterator = iter(values)
    return lambda: next(iterator)


def test_profile_workspace_collects_timings_and_bottlenecks(tmp_path, monkeypatch):
    entry_file = tmp_path / "Program" / "Main.s"
    discovery = SimpleNamespace(program_files=[entry_file], dependency_files=[tmp_path / "deps" / "Lib.l"])
    snapshot = SimpleNamespace(
        entry_file=entry_file,
        base_picture=SimpleNamespace(header=SimpleNamespace(name="Main")),
        project_graph=SimpleNamespace(),
        definitions=[object(), object(), object()],
    )
    analyzer_specs = [
        SimpleNamespace(
            spec=SimpleNamespace(
                key="fast",
                name="Fast",
                enabled=True,
                run=lambda _context: SimpleNamespace(issues=[object()]),
            )
        ),
        SimpleNamespace(
            spec=SimpleNamespace(
                key="slow",
                name="Slow",
                enabled=True,
                run=lambda _context: SimpleNamespace(issues=[object(), object()]),
            )
        ),
    ]

    monkeypatch.setattr(profiler, "discover_workspace_sources", lambda _root: discovery)
    monkeypatch.setattr(profiler, "load_workspace_snapshot", lambda *_args, **_kwargs: snapshot)
    monkeypatch.setattr(
        profiler,
        "get_default_analyzer_catalog",
        lambda: SimpleNamespace(analyzers=analyzer_specs),
    )

    report = profiler.profile_workspace(
        tmp_path,
        timer=_clock([0.0, 0.01, 0.01, 0.03, 0.03, 0.04, 0.04, 0.07]),
    )

    assert report["status"] == "ok"
    assert report["summary"] == {
        "program_file_count": 1,
        "profiled_entry_count": 1,
        "successful_entry_count": 1,
        "snapshot_failure_count": 0,
        "analyzer_count": 2,
        "total_duration_ms": 70.0,
    }
    assert report["phase_timings"] == [
        {"phase": "discovery", "duration_ms": 10.0},
        {"phase": "snapshot-loading", "duration_ms": 20.0},
        {"phase": "analyzer-run", "duration_ms": 40.0},
    ]
    assert report["entries"] == [
        {
            "entry_file": "Program/Main.s",
            "definition_count": 3,
            "analyzers": [
                {"key": "fast", "name": "Fast", "issue_count": 1, "duration_ms": 10.0},
                {"key": "slow", "name": "Slow", "issue_count": 2, "duration_ms": 30.0},
            ],
            "load_duration_ms": 20.0,
            "analysis_duration_ms": 40.0,
            "total_duration_ms": 60.0,
        }
    ]
    assert report["bottlenecks"]["slowest_entries"][0]["entry_file"] == "Program/Main.s"
    assert report["bottlenecks"]["slowest_analyzers"] == [
        {
            "key": "slow",
            "name": "Slow",
            "entry_count": 1,
            "issue_count": 2,
            "total_duration_ms": 30.0,
            "max_duration_ms": 30.0,
            "avg_duration_ms": 30.0,
        },
        {
            "key": "fast",
            "name": "Fast",
            "entry_count": 1,
            "issue_count": 1,
            "total_duration_ms": 10.0,
            "max_duration_ms": 10.0,
            "avg_duration_ms": 10.0,
        },
    ]
    assert report["snapshot_failures"] == []


def test_profile_workspace_includes_analyzer_phase_timings(tmp_path, monkeypatch):
    entry_file = tmp_path / "Program" / "Main.s"
    discovery = SimpleNamespace(program_files=[entry_file], dependency_files=[])
    snapshot = SimpleNamespace(
        entry_file=entry_file,
        base_picture=SimpleNamespace(header=SimpleNamespace(name="Main")),
        project_graph=SimpleNamespace(),
        definitions=[],
    )
    analyzer_specs = [
        SimpleNamespace(
            spec=SimpleNamespace(
                key="variables",
                name="Variable issues",
                enabled=True,
                run=lambda _context: SimpleNamespace(
                    issues=[object()],
                    phase_timings=[
                        {"phase": "root-traversal", "duration_ms": 12.5},
                        {"phase": "typedef-scan", "duration_ms": 7.5},
                    ],
                ),
            )
        )
    ]

    monkeypatch.setattr(profiler, "discover_workspace_sources", lambda _root: discovery)
    monkeypatch.setattr(profiler, "load_workspace_snapshot", lambda *_args, **_kwargs: snapshot)
    monkeypatch.setattr(
        profiler,
        "get_default_analyzer_catalog",
        lambda: SimpleNamespace(analyzers=analyzer_specs),
    )

    report = profiler.profile_workspace(
        tmp_path,
        timer=_clock([0.0, 0.01, 0.01, 0.02, 0.02, 0.04]),
    )

    assert report["entries"][0]["analyzers"] == [
        {
            "key": "variables",
            "name": "Variable issues",
            "issue_count": 1,
            "duration_ms": 20.0,
            "phase_timings": [
                {"phase": "root-traversal", "duration_ms": 12.5},
                {"phase": "typedef-scan", "duration_ms": 7.5},
            ],
        }
    ]


def test_profile_workspace_reports_partial_failures(tmp_path, monkeypatch):
    ok_entry = tmp_path / "Program" / "Ok.s"
    bad_entry = tmp_path / "Program" / "Bad.s"
    discovery = SimpleNamespace(program_files=[ok_entry, bad_entry], dependency_files=[])
    snapshot = SimpleNamespace(
        entry_file=ok_entry,
        base_picture=SimpleNamespace(header=SimpleNamespace(name="Ok")),
        project_graph=SimpleNamespace(),
        definitions=[],
    )

    def _load(entry_file, **_kwargs):
        if entry_file == bad_entry:
            raise ValueError("boom")
        return snapshot

    monkeypatch.setattr(profiler, "discover_workspace_sources", lambda _root: discovery)
    monkeypatch.setattr(profiler, "load_workspace_snapshot", _load)
    monkeypatch.setattr(
        profiler,
        "get_default_analyzer_catalog",
        lambda: SimpleNamespace(
            analyzers=[
                SimpleNamespace(
                    spec=SimpleNamespace(
                        key="variables",
                        name="Variables",
                        enabled=True,
                        run=lambda _context: SimpleNamespace(issues=[]),
                    )
                )
            ]
        ),
    )

    report = profiler.profile_workspace(
        tmp_path,
        timer=_clock([0.0, 0.01, 0.01, 0.02, 0.02, 0.03, 0.03, 0.05, 0.05, 0.06]),
    )

    assert report["status"] == "partial"
    assert report["summary"]["snapshot_failure_count"] == 1
    assert report["snapshot_failures"] == [
        {
            "entry_file": "Program/Bad.s",
            "duration_ms": 20.0,
            "error": "boom",
            "error_type": "ValueError",
        }
    ]


def test_profile_workspace_supports_configured_target(monkeypatch, tmp_path):
    config_path = tmp_path / "config.toml"
    config_path.write_text("[dummy]\n", encoding="utf-8")
    entry_file = tmp_path / "Program" / "Target.s"
    entry_file.parent.mkdir(parents=True)
    entry_file.write_text("", encoding="utf-8")

    analyzer_specs = [
        SimpleNamespace(
            spec=SimpleNamespace(
                key="variables",
                name="Variables",
                enabled=True,
                run=lambda _context: SimpleNamespace(issues=[object(), object()]),
            )
        )
    ]
    project_bp = SimpleNamespace(
        header=SimpleNamespace(name="Target"),
        datatype_defs=[object(), object()],
        moduletype_defs=[object(), object()],
    )
    graph = SimpleNamespace(unavailable_libraries=set())

    monkeypatch.setattr(
        profiler.config_module,
        "load_config",
        lambda _path: (
            {"program_dir": str(tmp_path / "Program"), "analyzed_targets": ["Target"], "debug": False},
            False,
        ),
    )
    monkeypatch.setattr(
        profiler.app_module,
        "load_project",
        lambda *_args, **_kwargs: (project_bp, graph),
    )
    monkeypatch.setattr(
        profiler,
        "source_paths_for_current_target",
        lambda *_args, **_kwargs: {entry_file},
    )
    monkeypatch.setattr(
        profiler,
        "get_default_analyzer_catalog",
        lambda: SimpleNamespace(analyzers=analyzer_specs),
    )

    report = profiler.profile_workspace(
        tmp_path,
        config_path=config_path,
        target_name="Target",
        timer=_clock([0.0, 0.02, 0.02, 0.05]),
    )

    assert report["status"] == "ok"
    assert report["configured_target"] == {
        "target": "Target",
        "config_path": "<external>/config.toml",
    }
    assert report["summary"] == {
        "program_file_count": 1,
        "profiled_entry_count": 1,
        "successful_entry_count": 1,
        "snapshot_failure_count": 0,
        "analyzer_count": 1,
        "total_duration_ms": 50.0,
    }
    assert report["phase_timings"] == [
        {"phase": "configured-target-loading", "duration_ms": 20.0},
        {"phase": "analyzer-run", "duration_ms": 30.0},
    ]
    assert report["entries"] == [
        {
            "entry_file": "Target.s",
            "definition_count": 4,
            "analyzers": [{"key": "variables", "name": "Variables", "issue_count": 2, "duration_ms": 30.0}],
            "load_duration_ms": 20.0,
            "analysis_duration_ms": 30.0,
            "total_duration_ms": 50.0,
        }
    ]


def test_profile_workspace_configured_target_uses_cache_by_default(monkeypatch, tmp_path):
    config_path = tmp_path / "config.toml"
    config_path.write_text("[dummy]\n", encoding="utf-8")
    entry_file = tmp_path / "Program" / "Target.s"
    entry_file.parent.mkdir(parents=True)
    entry_file.write_text("", encoding="utf-8")

    project_bp = SimpleNamespace(header=SimpleNamespace(name="Target"))
    graph = SimpleNamespace(unavailable_libraries=set())
    load_project_calls: list[dict[str, object]] = []

    monkeypatch.setattr(
        profiler.config_module,
        "load_config",
        lambda _path: (
            {"program_dir": str(tmp_path / "Program"), "analyzed_targets": ["Target"], "debug": False},
            False,
        ),
    )

    def _load_project(*_args, **kwargs):
        load_project_calls.append(dict(kwargs))
        return project_bp, graph

    monkeypatch.setattr(profiler.app_module, "load_project", _load_project)
    monkeypatch.setattr(profiler, "source_paths_for_current_target", lambda *_args, **_kwargs: {entry_file})
    monkeypatch.setattr(
        profiler,
        "get_default_analyzer_catalog",
        lambda: SimpleNamespace(analyzers=[]),
    )

    profiler.profile_workspace(
        tmp_path,
        config_path=config_path,
        target_name="Target",
        timer=_clock([0.0, 0.02]),
    )

    assert load_project_calls == [{"target_name": "Target"}]


def test_profile_workspace_configured_target_skips_snapshot_build(monkeypatch, tmp_path):
    config_path = tmp_path / "config.toml"
    config_path.write_text("[dummy]\n", encoding="utf-8")
    entry_file = tmp_path / "Program" / "Target.s"
    entry_file.parent.mkdir(parents=True)
    entry_file.write_text("", encoding="utf-8")

    project_bp = SimpleNamespace(
        header=SimpleNamespace(name="Target"),
        datatype_defs=[object()],
        moduletype_defs=[object(), object()],
    )
    graph = SimpleNamespace(unavailable_libraries=set())

    monkeypatch.setattr(
        profiler.config_module,
        "load_config",
        lambda _path: (
            {"program_dir": str(tmp_path / "Program"), "analyzed_targets": ["Target"], "debug": False},
            False,
        ),
    )
    monkeypatch.setattr(profiler.app_module, "load_project", lambda *_args, **_kwargs: (project_bp, graph))
    monkeypatch.setattr(profiler, "source_paths_for_current_target", lambda *_args, **_kwargs: {entry_file})
    monkeypatch.setattr(
        profiler,
        "build_snapshot_from_loaded_project",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("snapshot build should be skipped")),
        raising=False,
    )
    monkeypatch.setattr(
        profiler,
        "get_default_analyzer_catalog",
        lambda: SimpleNamespace(analyzers=[]),
    )

    report = profiler.profile_workspace(
        tmp_path,
        config_path=config_path,
        target_name="Target",
        timer=_clock([0.0, 0.02]),
    )

    assert report["entries"] == [
        {
            "entry_file": "Target.s",
            "definition_count": 3,
            "analyzers": [],
            "load_duration_ms": 20.0,
            "analysis_duration_ms": 0.0,
            "total_duration_ms": 20.0,
        }
    ]


def test_main_passes_config_and_target_to_profile_workspace(tmp_path, monkeypatch, capsys):
    expected_report = {
        "generated_by": "sattlint.devtools.profiler",
        "report_kind": "workspace-profile",
        "status": "ok",
        "workspace_root": ".",
        "summary": {
            "program_file_count": 1,
            "profiled_entry_count": 1,
            "successful_entry_count": 1,
            "snapshot_failure_count": 0,
            "analyzer_count": 1,
            "total_duration_ms": 5.0,
        },
        "source_files": {"program_files": ["Program/Main.s"], "dependency_file_count": 0},
        "phase_timings": [{"phase": "configured-target-loading", "duration_ms": 5.0}],
        "entries": [],
        "bottlenecks": {"slowest_entries": [], "slowest_analyzers": [], "slowest_phases": []},
        "snapshot_failures": [],
        "configured_target": {"target": "Main", "config_path": "<external>/config.toml"},
    }

    def _profile_workspace(*_args, **kwargs):
        assert kwargs["config_path"] == (tmp_path / "config.toml").resolve()
        assert kwargs["target_name"] == "Main"
        return expected_report

    monkeypatch.setattr(profiler, "profile_workspace", _profile_workspace)

    exit_code = profiler.main(
        [
            "--config",
            str(tmp_path / "config.toml"),
            "--target",
            "Main",
            "--no-progress",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert json.loads(captured.out) == expected_report


def test_main_writes_report_and_progress(tmp_path, monkeypatch, capsys):
    expected_report = {
        "generated_by": "sattlint.devtools.profiler",
        "report_kind": "workspace-profile",
        "status": "ok",
        "workspace_root": ".",
        "summary": {
            "program_file_count": 1,
            "profiled_entry_count": 1,
            "successful_entry_count": 1,
            "snapshot_failure_count": 0,
            "analyzer_count": 1,
            "total_duration_ms": 5.0,
        },
        "source_files": {"program_files": ["Program/Main.s"], "dependency_file_count": 0},
        "phase_timings": [{"phase": "discovery", "duration_ms": 5.0}],
        "entries": [],
        "bottlenecks": {"slowest_entries": [], "slowest_analyzers": [], "slowest_phases": []},
        "snapshot_failures": [],
    }

    def _profile_workspace(*_args, **kwargs):
        progress_callback = kwargs.get("progress_callback")
        assert progress_callback is not None
        progress_callback("Profiler: discovering workspace sources")
        return expected_report

    monkeypatch.setattr(profiler, "profile_workspace", _profile_workspace)

    output_dir = tmp_path / "artifacts"
    exit_code = profiler.main(
        [
            "--workspace-root",
            str(tmp_path),
            "--output-dir",
            str(output_dir),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Profiler: discovering workspace sources" in captured.err
    assert json.loads(captured.out) == expected_report
    assert json.loads((output_dir / profiler.DEFAULT_OUTPUT_FILENAME).read_text(encoding="utf-8")) == expected_report


def test_main_returns_failure_when_output_report_write_fails(tmp_path, monkeypatch, capsys):
    expected_report = {
        "generated_by": "sattlint.devtools.profiler",
        "report_kind": "workspace-profile",
        "status": "ok",
        "workspace_root": ".",
        "summary": {
            "program_file_count": 1,
            "profiled_entry_count": 1,
            "successful_entry_count": 1,
            "snapshot_failure_count": 0,
            "analyzer_count": 1,
            "total_duration_ms": 5.0,
        },
        "source_files": {"program_files": ["Program/Main.s"], "dependency_file_count": 0},
        "phase_timings": [{"phase": "discovery", "duration_ms": 5.0}],
        "entries": [],
        "bottlenecks": {"slowest_entries": [], "slowest_analyzers": [], "slowest_phases": []},
        "snapshot_failures": [],
    }
    monkeypatch.setattr(profiler, "profile_workspace", lambda *_args, **_kwargs: expected_report)
    monkeypatch.setattr(
        profiler,
        "_write_profiler_report",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(PermissionError("locked")),
    )

    exit_code = profiler.main(
        [
            "--workspace-root",
            str(tmp_path),
            "--no-progress",
            "--output-dir",
            str(tmp_path / "artifacts"),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert json.loads(captured.out) == expected_report
    assert "profiler output error: locked" in captured.err
