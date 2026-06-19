# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportPrivateUsage=false
import json
import runpy
from types import SimpleNamespace

import pytest

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


def test_profiler_helper_selection_and_error_report_branches(tmp_path, monkeypatch):
    alpha = tmp_path / "Program" / "Alpha.s"
    beta = tmp_path / "Program" / "Beta.s"
    assert profiler._choose_target_entry_file(set(), target_name="Alpha") is None
    assert profiler._choose_target_entry_file({beta, alpha}, target_name="Missing") == alpha

    analyzer_specs = [
        SimpleNamespace(spec=SimpleNamespace(key="variables", name="Variables", enabled=True)),
        SimpleNamespace(spec=SimpleNamespace(key="signals", name="Signals", enabled=True)),
        SimpleNamespace(spec=SimpleNamespace(key="disabled", name="Disabled", enabled=False)),
    ]
    monkeypatch.setattr(
        profiler,
        "get_default_analyzer_catalog",
        lambda: SimpleNamespace(analyzers=analyzer_specs),
    )
    monkeypatch.setattr(profiler, "canonicalize_analyzer_key", lambda key: key.strip().casefold())
    assert [spec.key for spec in profiler._selected_analyzer_specs([" variables ", "", "SIGNALS"])] == [
        "variables",
        "signals",
    ]

    report = profiler._build_profile_report(
        workspace_root=tmp_path,
        program_files=[],
        dependency_file_count=0,
        entry_records=[],
        failures=[{"entry_file": "Broken.s", "duration_ms": 1.0, "error": "boom", "error_type": "ValueError"}],
        phase_timings=[{"phase": "load", "duration_ms": 1.0}],
        analyzer_keys=["variables"],
    )
    assert report["status"] == "error"


def test_profile_workspace_configured_target_failure_and_progress_paths(monkeypatch, tmp_path):
    config_path = tmp_path / "config.toml"
    config_path.write_text("[dummy]\n", encoding="utf-8")
    progress_messages: list[str] = []

    monkeypatch.setattr(
        profiler.config_module,
        "load_config",
        lambda _path: (
            {"program_dir": str(tmp_path / "Program"), "analyzed_targets": ["Configured"], "debug": False},
            False,
        ),
    )
    monkeypatch.setattr(
        profiler.app_module,
        "load_project",
        lambda *_args, **_kwargs: (SimpleNamespace(header=SimpleNamespace(name="Configured")), SimpleNamespace()),
    )
    monkeypatch.setattr(profiler, "source_paths_for_current_target", lambda *_args, **_kwargs: set())
    monkeypatch.setattr(profiler, "get_default_analyzer_catalog", lambda: SimpleNamespace(analyzers=[]))

    report = profiler.profile_workspace(
        tmp_path,
        config_path=config_path,
        timer=_clock([0.0, 0.02]),
        progress_callback=progress_messages.append,
    )

    assert progress_messages == ["Profiler: loading configured target Configured"]
    assert report["status"] == "error"
    assert report["configured_target"] == {
        "target": "Configured",
        "config_path": "<external>/config.toml",
    }
    assert report["snapshot_failures"] == [
        {
            "entry_file": "Configured",
            "duration_ms": 20.0,
            "error": "Could not resolve a source file for target 'Configured'",
            "error_type": "RuntimeError",
        }
    ]


def test_profile_workspace_configured_target_emits_analysis_progress(monkeypatch, tmp_path):
    config_path = tmp_path / "config.toml"
    config_path.write_text("[dummy]\n", encoding="utf-8")
    entry_file = tmp_path / "Program" / "Configured.s"
    entry_file.parent.mkdir(parents=True)
    entry_file.write_text("", encoding="utf-8")
    progress_messages: list[str] = []

    monkeypatch.setattr(
        profiler.config_module,
        "load_config",
        lambda _path: (
            {"program_dir": str(tmp_path / "Program"), "analyzed_targets": ["Configured"], "debug": False},
            False,
        ),
    )
    monkeypatch.setattr(
        profiler.app_module,
        "load_project",
        lambda *_args, **_kwargs: (
            SimpleNamespace(header=SimpleNamespace(name="Configured"), datatype_defs=[], moduletype_defs=[]),
            SimpleNamespace(),
        ),
    )
    monkeypatch.setattr(profiler, "source_paths_for_current_target", lambda *_args, **_kwargs: {entry_file})
    monkeypatch.setattr(profiler, "get_default_analyzer_catalog", lambda: SimpleNamespace(analyzers=[]))

    profiler.profile_workspace(
        tmp_path,
        config_path=config_path,
        timer=_clock([0.0, 0.02]),
        progress_callback=progress_messages.append,
    )

    assert progress_messages == [
        "Profiler: loading configured target Configured",
        "Profiler: analyzing configured target Configured",
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


def test_profile_workspace_progress_and_max_file_branches(tmp_path, monkeypatch):
    first_entry = tmp_path / "Program" / "First.s"
    second_entry = tmp_path / "Program" / "Second.s"
    discovery = SimpleNamespace(program_files=[first_entry, second_entry], dependency_files=[])
    snapshot = SimpleNamespace(
        entry_file=first_entry,
        base_picture=SimpleNamespace(header=SimpleNamespace(name="First")),
        project_graph=SimpleNamespace(),
        definitions=[],
    )
    progress_messages: list[str] = []

    def _load(entry_file, **_kwargs):
        if entry_file == second_entry:
            raise ValueError("broken")
        return snapshot

    monkeypatch.setattr(profiler, "discover_workspace_sources", lambda _root: discovery)
    monkeypatch.setattr(profiler, "load_workspace_snapshot", _load)
    monkeypatch.setattr(profiler, "get_default_analyzer_catalog", lambda: SimpleNamespace(analyzers=[]))

    report = profiler.profile_workspace(
        tmp_path,
        timer=_clock([0.0, 0.01, 0.01, 0.02, 0.02, 0.03, 0.03, 0.05, 0.05, 0.06]),
        progress_callback=progress_messages.append,
    )

    assert report["status"] == "partial"
    assert progress_messages == [
        "Profiler: discovering workspace sources",
        "Profiler: loading 1/2 Program/First.s",
        "Profiler: analyzing 1/2 Program/First.s",
        "Profiler: loading 2/2 Program/Second.s",
        "Profiler: failed 2/2 Program/Second.s (ValueError)",
    ]

    limited_report = profiler.profile_workspace(
        tmp_path,
        max_files=0,
        timer=_clock([0.0, 0.01]),
    )
    assert limited_report["summary"]["program_file_count"] == 0
    assert limited_report["entries"] == []


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


def test_profiler_snapshot_and_text_output_helpers_cover_remaining_branches(tmp_path):
    analyzer_specs = [
        SimpleNamespace(
            key="variables",
            name="Variables",
            run=lambda _context: SimpleNamespace(
                issues=[object()],
                phase_timings=[
                    "skip",
                    {},
                    {"phase": "", "duration_ms": 1},
                    {"phase": "parse", "duration_ms": "bad"},
                    {"phase": "analyze", "duration_ms": None},
                ],
            ),
        )
    ]
    original_selected = profiler._selected_analyzer_specs
    try:
        profiler._selected_analyzer_specs = lambda analyzer_keys: analyzer_specs
        records, total_duration_ms = profiler._profile_snapshot_analyzers(
            SimpleNamespace(base_picture=SimpleNamespace(), project_graph=None),
            timer=_clock([0.0, 0.02]),
            analyzer_keys=None,
        )
    finally:
        profiler._selected_analyzer_specs = original_selected

    assert total_duration_ms == 20.0
    assert records == [
        {
            "key": "variables",
            "name": "Variables",
            "issue_count": 1,
            "duration_ms": 20.0,
            "phase_timings": [
                {"phase": "parse", "duration_ms": 0.0},
                {"phase": "analyze", "duration_ms": 0.0},
            ],
        }
    ]

    aggregated = profiler._aggregate_analyzer_bottlenecks(
        [
            {
                "analyzers": [
                    {"key": "", "name": "Skip", "issue_count": 9, "duration_ms": 99.0},
                    {"key": "variables", "name": "Variables", "issue_count": 1, "duration_ms": 20.0},
                ]
            }
        ]
    )
    assert aggregated == [
        {
            "key": "variables",
            "name": "Variables",
            "entry_count": 1,
            "issue_count": 1,
            "total_duration_ms": 20.0,
            "max_duration_ms": 20.0,
            "avg_duration_ms": 20.0,
        }
    ]

    empty_text = profiler._render_text_report(
        {
            "status": "ok",
            "workspace_root": ".",
            "summary": {"program_file_count": 0, "profiled_entry_count": 0, "total_duration_ms": 0.0},
            "phase_timings": [],
            "bottlenecks": {"slowest_entries": [], "slowest_analyzers": []},
        }
    )
    assert "Slowest entries:\n- none" in empty_text
    assert "Slowest analyzers:\n- none" in empty_text

    detailed_text = profiler._render_text_report(
        {
            "status": "partial",
            "workspace_root": ".",
            "summary": {"program_file_count": 1, "profiled_entry_count": 1, "total_duration_ms": 25.0},
            "configured_target": {"target": "Main", "config_path": "<external>/config.toml"},
            "phase_timings": [{"phase": "load", "duration_ms": 5.0}],
            "bottlenecks": {
                "slowest_entries": [
                    {
                        "entry_file": "Program/Main.s",
                        "total_duration_ms": 25.0,
                        "analyzers": [
                            {
                                "key": "summary-only",
                            },
                            {
                                "key": "variables",
                                "phase_timings": [{"phase": "scan", "duration_ms": 10.0}],
                            },
                        ],
                    }
                ],
                "slowest_analyzers": [{"key": "variables", "total_duration_ms": 20.0, "avg_duration_ms": 20.0}],
            },
        }
    )
    assert "Configured target: Main" in detailed_text
    assert "Config path: <external>/config.toml" in detailed_text
    assert "- Program/Main.s: 25.0 ms" in detailed_text
    assert "  - variables phases:" in detailed_text
    assert "    - scan: 10.0 ms" in detailed_text
    assert "- variables: total 20.0 ms, avg 20.0 ms" in detailed_text


def test_main_text_mode_and_module_entrypoint(tmp_path, monkeypatch, capsys):
    error_report = {
        "generated_by": "sattlint.devtools.profiler",
        "report_kind": "workspace-profile",
        "status": "error",
        "workspace_root": ".",
        "summary": {
            "program_file_count": 0,
            "profiled_entry_count": 0,
            "successful_entry_count": 0,
            "snapshot_failure_count": 1,
            "analyzer_count": 0,
            "total_duration_ms": 1.0,
        },
        "source_files": {"program_files": [], "dependency_file_count": 0},
        "phase_timings": [{"phase": "load", "duration_ms": 1.0}],
        "entries": [],
        "bottlenecks": {"slowest_entries": [], "slowest_analyzers": [], "slowest_phases": []},
        "snapshot_failures": [
            {"entry_file": "Broken.s", "duration_ms": 1.0, "error": "boom", "error_type": "ValueError"}
        ],
    }
    monkeypatch.setattr(profiler, "profile_workspace", lambda *_args, **_kwargs: error_report)

    exit_code = profiler.main(
        [
            "--workspace-root",
            str(tmp_path),
            "--format",
            "text",
            "--no-progress",
        ]
    )
    captured = capsys.readouterr()
    assert exit_code == 2
    assert "SattLint workspace profile" in captured.out

    monkeypatch.setattr(
        "sattlint.core.semantic.discover_workspace_sources",
        lambda _root: SimpleNamespace(program_files=[], dependency_files=[]),
    )
    monkeypatch.setattr(
        "sattlint.analyzers.registry.get_default_analyzer_catalog", lambda: SimpleNamespace(analyzers=[])
    )
    monkeypatch.setattr(
        "argparse.ArgumentParser.parse_args",
        lambda self, args: SimpleNamespace(
            workspace_root=str(tmp_path),
            config=None,
            target=None,
            max_files=None,
            analyzer=[],
            format="json",
            output_dir=None,
            no_progress=True,
        ),
    )

    with pytest.raises(SystemExit) as exc_info:
        runpy.run_module("sattlint.devtools.profiler", run_name="__main__")
    assert exc_info.value.code == 0
