# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportArgumentType=false
import json
import os
from types import SimpleNamespace

from sattlint.analyzers.framework import Issue, SimpleReport
from sattlint.config import DEFAULT_CONFIG
from sattlint.reporting import target_report as analysis_reporting_module
from tests.helpers import AnalysisGraphStub, named_object
from tests.helpers.app_analysis_support import *


def test_select_report_source_path_propagates_callback_type_error() -> None:
    with pytest.raises(TypeError, match="bad graph"):
        analysis_reporting_module.select_report_source_path(
            SimpleNamespace(origin_file="Root.s"),
            SimpleNamespace(),
            source_paths_for_current_target_fn=lambda *_args: (_ for _ in ()).throw(TypeError("bad graph")),
            casefold_equal_fn=lambda left, right: left.casefold() == right.casefold(),
        )


def test_select_report_source_path_prefers_graph_root_origin_path() -> None:
    project_bp = named_object("Root")
    graph = AnalysisGraphStub(source_files={Path("fallback/Root.s")})
    graph.record_root_origin("Root", source_path=Path("preferred/Root.s"), library_name="Lib")

    selected = analysis_reporting_module.select_report_source_path(
        project_bp,
        graph,
        source_paths_for_current_target_fn=lambda *_args: {Path("fallback/Root.s"), Path("preferred/Root.s")},
        casefold_equal_fn=lambda left, right: left.casefold() == right.casefold(),
    )

    assert selected == Path("preferred/Root.s")


def test_source_version_label_uses_graph_root_origin_when_source_path_missing() -> None:
    project_bp = named_object("Root")
    graph = AnalysisGraphStub()
    graph.record_root_origin("Root", source_path=Path("preferred/Root.z"), library_name="Lib")

    label = analysis_reporting_module.source_version_label(
        project_bp,
        graph,
        None,
        draft_source_suffixes=frozenset({".s", ".l"}),
        official_source_suffixes=frozenset({".x", ".z"}),
    )

    assert label == "official"


def test_select_report_source_path_prefers_configured_mode_suffix_on_equal_mtime(tmp_path) -> None:
    draft = tmp_path / "Root.s"
    official = tmp_path / "Root.x"
    draft.touch()
    official.touch()

    draft_stat = draft.stat()
    os.utime(official, (draft_stat.st_atime, draft_stat.st_mtime))

    project_bp = named_object("Root")
    graph = AnalysisGraphStub()

    selected = analysis_reporting_module.select_report_source_path(
        project_bp,
        graph,
        source_paths_for_current_target_fn=lambda *_args: {draft, official},
        casefold_equal_fn=lambda left, right: left.casefold() == right.casefold(),
        preferred_suffixes=frozenset({".s", ".l"}),
    )

    assert selected == draft


def test_run_checks_reports_no_matching_checks_and_pauses(monkeypatch):
    lines: list[str] = []
    pauses: list[str] = []

    monkeypatch.setattr(output_module, "emit_output", lambda message: lines.append(message))

    checks_application.run_checks(
        DEFAULT_CONFIG.copy(),
        ["missing-check"],
        get_enabled_analyzers_fn=lambda: [SimpleNamespace(key="variables", name="Variables")],
        pause_fn=lambda: pauses.append("pause"),
    )

    assert any("No matching checks found" in line for line in lines)
    assert pauses == ["pause"]


def test_collect_run_checks_result_aborts_when_self_check_fails():
    run_calls: list[str] = []

    result = checks_application.collect_run_checks_result(
        DEFAULT_CONFIG.copy(),
        ["state-inference"],
        iter_loaded_projects_fn=cast(
            Any,
            lambda *_args, **_kwargs: iter(
                [
                    (
                        "TargetA",
                        named_object("TargetA"),
                        AnalysisGraphStub(unavailable_libraries=set()),
                    )
                ]
            ),
        ),
        get_enabled_analyzers_fn=lambda: [
            SimpleNamespace(
                key="state-inference",
                name="State inference",
                run=lambda _context: run_calls.append("run") or SimpleNamespace(issues=[], summary=lambda: "summary"),
            )
        ],
        target_is_library_fn=lambda *_args, **_kwargs: False,
        self_check_fn=lambda _cfg: False,
    )

    assert run_calls == []
    assert result.targets == ()
    assert result.selected_analyzers == ("state-inference",)
    assert any("Self-check failed. Analysis aborted" in line for line in result.output_lines)
    assert not any("Running checks" in line for line in result.output_lines)


def test_collect_run_checks_result_runs_analyzers_when_self_check_passes():
    run_calls: list[str] = []

    result = checks_application.collect_run_checks_result(
        DEFAULT_CONFIG.copy(),
        ["state-inference"],
        iter_loaded_projects_fn=cast(
            Any,
            lambda *_args, **_kwargs: iter(
                [
                    (
                        "TargetA",
                        named_object("TargetA"),
                        AnalysisGraphStub(unavailable_libraries=set()),
                    )
                ]
            ),
        ),
        get_enabled_analyzers_fn=lambda: [
            SimpleNamespace(
                key="state-inference",
                name="State inference",
                run=lambda _context: run_calls.append("run") or SimpleNamespace(issues=[], summary=lambda: "summary"),
            )
        ],
        target_is_library_fn=lambda *_args, **_kwargs: False,
        self_check_fn=lambda _cfg: True,
    )

    assert run_calls == ["run"]
    assert len(result.targets) == 1
    del result


def test_run_checks_runs_selected_non_default_cli_exposed_analyzer(monkeypatch):
    lines: list[str] = []

    monkeypatch.setattr(output_module, "emit_output", lambda message: lines.append(message))

    class MutableReport:
        def __init__(self) -> None:
            self.name = "BasePicture"

        def summary(self) -> str:
            return f"state inference summary for {self.name}"

    report = MutableReport()

    checks_application.run_checks(
        DEFAULT_CONFIG.copy(),
        ["state-inference"],
        iter_loaded_projects_fn=cast(
            Any,
            lambda *_args, **_kwargs: iter(
                [
                    (
                        "TargetA",
                        named_object("TargetA"),
                        AnalysisGraphStub(
                            unavailable_libraries=set(),
                            load_stage_timings={"load_or_parse": 0.5},
                            graphics_load_timings={"correlate-picture-display": 0.125},
                        ),
                    )
                ]
            ),
        ),
        get_enabled_analyzers_fn=lambda: [
            SimpleNamespace(
                key="state-inference",
                name="State inference",
                run=lambda _context: report,
            )
        ],
        target_is_library_fn=lambda *_args, **_kwargs: False,
        pause_fn=None,
    )

    assert any("State inference (state-inference)" in line for line in lines)
    assert any("state inference summary for TargetA" in line for line in lines)
    assert not any("state inference summary for BasePicture" in line for line in lines)


def test_run_checks_updates_live_status_for_active_analyzer(monkeypatch):
    updates: list[str] = []

    class FakeLiveStatusLine:
        def __enter__(self):
            return updates.append

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(output_module, "emit_output", lambda _message: None)
    monkeypatch.setattr(console_module, "live_status_line", lambda: FakeLiveStatusLine())

    checks_application.run_checks(
        DEFAULT_CONFIG.copy(),
        ["state-inference"],
        iter_loaded_projects_fn=cast(
            Any,
            lambda *_args, **_kwargs: iter(
                [
                    (
                        "TargetA",
                        named_object("TargetA"),
                        AnalysisGraphStub(
                            unavailable_libraries=set(),
                            load_stage_timings={"load_or_parse": 0.5},
                            graphics_load_timings={"correlate-picture-display": 0.125},
                        ),
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
        pause_fn=None,
    )

    assert updates == ["Analyzing TargetA: State inference (state-inference)"]


def test_collect_run_checks_result_captures_target_and_analyzer_metadata():
    result = checks_application.collect_run_checks_result(
        DEFAULT_CONFIG.copy(),
        ["state-inference"],
        iter_loaded_projects_fn=cast(
            Any,
            lambda *_args, **_kwargs: iter(
                [
                    (
                        "TargetA",
                        named_object("TargetA"),
                        AnalysisGraphStub(
                            unavailable_libraries=set(),
                            load_stage_timings={},
                            graphics_load_timings={},
                        ),
                    )
                ]
            ),
        ),
        get_enabled_analyzers_fn=lambda: [
            SimpleNamespace(
                key="state-inference",
                name="State inference",
                run=lambda _context: SimpleNamespace(
                    summary=lambda: "state inference summary",
                    issues=[Issue(kind="unused", message="unused state")],
                    phase_timings=[{"phase": "plan", "duration_ms": 1.25}],
                ),
            )
        ],
        target_is_library_fn=lambda *_args, **_kwargs: False,
    )

    assert result.cancelled is False
    assert result.selected_analyzers == ("state-inference",)
    assert result.output_lines[0] == "\n--- Running checks ---"
    assert len(result.targets) == 1

    target = result.targets[0]
    assert target.target_name == "TargetA"
    assert target.is_library is False
    assert len(target.analyzers) == 1

    analyzer = target.analyzers[0]
    assert analyzer.key == "state-inference"
    assert analyzer.name == "State inference"
    assert analyzer.status == "completed"
    assert analyzer.summary == "state inference summary"
    assert analyzer.report_kind == "SimpleNamespace"
    assert analyzer.issue_count == 1
    assert analyzer.phase_timings_ms == ({"phase": "plan", "duration_ms": 1.25},)


def test_collect_run_checks_result_runs_icf_once_as_whole_run_target(monkeypatch) -> None:
    calls: dict[str, int] = {"n": 0}

    def _fake_icf(context) -> SimpleReport:
        calls["n"] += 1
        return SimpleReport(
            name="ICF configuration",
            issues=[Issue(kind="icf.unresolved_path", message="Program.icf:1: unresolved path")],
        )

    result = checks_application.collect_run_checks_result(
        DEFAULT_CONFIG.copy(),
        ["icf"],
        iter_loaded_projects_fn=cast(
            Any,
            lambda *_args, **_kwargs: iter(
                [
                    (
                        "TargetA",
                        named_object("TargetA"),
                        AnalysisGraphStub(unavailable_libraries=set()),
                    )
                ]
            ),
        ),
        get_enabled_analyzers_fn=lambda: [
            SimpleNamespace(
                key="icf",
                name="ICF configuration",
                scope="per-run",
                run=_fake_icf,
            )
        ],
        target_is_library_fn=lambda *_args, **_kwargs: False,
    )

    assert calls["n"] == 1
    assert result.selected_analyzers == ("icf",)

    icf_targets = [target for target in result.targets if target.target_name == "ICF configuration"]
    assert len(icf_targets) == 1

    analyzer = icf_targets[0].analyzers[0]
    assert analyzer.key == "icf"
    assert analyzer.status == "completed"
    assert analyzer.issue_count == 1
    assert analyzer.report_kind == "SimpleReport"


def test_run_checks_selection_is_exact_and_drops_unregistered_keys(monkeypatch):
    lines: list[str] = []
    run_order: list[str] = []
    shared_ids: list[int] = []

    def _report(name: str):
        return SimpleNamespace(summary=lambda: name, issues=[])

    def _variables_run(context):
        run_order.append("variables")
        shared_ids.append(id(context.shared_artifacts))
        assert context.shared_artifacts is not None
        return _report("variables summary")

    monkeypatch.setattr(output_module, "emit_output", lambda message: lines.append(message))

    checks_application.run_checks(
        DEFAULT_CONFIG.copy(),
        ["variables", "sattline-semantics"],
        iter_loaded_projects_fn=cast(
            Any,
            lambda *_args, **_kwargs: iter(
                [
                    (
                        "TargetA",
                        named_object("TargetA"),
                        AnalysisGraphStub(
                            unavailable_libraries=set(),
                            load_stage_timings={"load_or_parse": 0.5},
                            graphics_load_timings={"correlate-picture-display": 0.125},
                        ),
                    )
                ]
            ),
        ),
        get_enabled_analyzers_fn=lambda: [
            SimpleNamespace(key="variables", name="Variable issues", run=_variables_run),
        ],
        target_is_library_fn=lambda *_args, **_kwargs: False,
        pause_fn=None,
    )

    assert run_order == ["variables"]
    assert len(set(shared_ids)) == 1
    assert any("variables summary" in line for line in lines)


def test_run_checks_writes_target_profiling_summary(tmp_path, monkeypatch):
    profile_path = tmp_path / "profile.jsonl"
    monkeypatch.setattr(output_module, "emit_output", lambda _message: None)
    monkeypatch.setenv("SATTLINT_PROFILE", "1")
    monkeypatch.setattr(profiling_module, "profiling_log_path", lambda: tmp_path / "profile.jsonl")

    checks_application.run_checks(
        DEFAULT_CONFIG.copy(),
        ["state-inference", "variables"],
        iter_loaded_projects_fn=cast(
            Any,
            lambda *_args, **_kwargs: iter(
                [
                    (
                        "TargetA",
                        SimpleNamespace(header=SimpleNamespace(name="TargetA")),
                        SimpleNamespace(
                            unavailable_libraries=set(),
                            load_stage_timings={"load_or_parse": 0.5},
                            graphics_load_timings={"correlate-picture-display": 0.125},
                        ),
                    )
                ]
            ),
        ),
        get_enabled_analyzers_fn=lambda: [
            SimpleNamespace(
                key="state-inference",
                name="State inference",
                run=lambda _context: SimpleNamespace(
                    summary=lambda: "state inference summary",
                    phase_timings=[
                        {"phase": "collect", "duration_ms": 1.25},
                        {"phase": "report", "duration_ms": 2.5},
                    ],
                ),
            ),
            SimpleNamespace(
                key="variables",
                name="Variable issues",
                run=lambda _context: SimpleNamespace(summary=lambda: "variables summary"),
            ),
        ],
        target_is_library_fn=lambda *_args, **_kwargs: False,
        pause_fn=None,
    )

    events = [json.loads(line) for line in profile_path.read_text(encoding="utf-8").splitlines()]

    assert len(events) == 1
    assert events[0]["kind"] == "sattlint.app.profile"
    assert events[0]["operation"] == "checks"
    assert events[0]["target_name"] == "TargetA"
    assert events[0]["success"] is True
    assert events[0]["payload"]["selected_analyzers"] == ["state-inference", "variables"]
    assert set(events[0]["payload"]["analyzer_timings_ms"]) == {"variables", "state-inference"}
    assert events[0]["payload"]["analyzer_phase_timings_ms"] == {
        "state-inference": [
            {"phase": "collect", "duration_ms": 1.25},
            {"phase": "report", "duration_ms": 2.5},
        ]
    }
    assert events[0]["payload"]["analyzer_phase_bottleneck"] == {
        "kind": "analyzer-phase",
        "name": "report",
        "duration_ms": 2.5,
        "analyzer_key": "state-inference",
    }
    assert events[0]["payload"]["bottleneck_kind"] == "analyzer-phase"
    assert events[0]["payload"]["stage_timings_ms"] == {"load_or_parse": 500.0}
    assert events[0]["payload"]["graphics_timings_ms"] == {"correlate-picture-display": 125.0}


def test_run_checks_uses_cached_report_when_available(monkeypatch):
    lines: list[str] = []
    run_calls: list[str] = []
    load_keys: list[str] = []
    validate_calls: list[tuple[object, bool]] = []
    save_calls: list[tuple[str, object, frozenset[Path]]] = []

    class MutableReport:
        def __init__(self, name: str) -> None:
            self.name = name
            self.issues: list[object] = []

        def summary(self) -> str:
            return f"state inference summary for {self.name}"

    cached_report = MutableReport("BasePicture")

    class FakeReportCache:
        def __init__(self, cache_dir):
            assert cache_dir == Path("report-cache-dir")

        def load(self, key):
            load_keys.append(key)
            return {"report": cached_report}

        def validate(self, payload, *, fast=False):
            validate_calls.append((payload, fast))
            return True

        def save(self, key, *, report, files):
            save_calls.append((key, report, frozenset(files)))
            return True

    monkeypatch.setattr(output_module, "emit_output", lambda message: lines.append(message))
    monkeypatch.setattr(checks_application, "AnalysisReportCache", FakeReportCache)
    monkeypatch.setattr(checks_application, "get_cache_dir", lambda: Path("report-cache-dir"))
    monkeypatch.setattr(
        checks_application,
        "compute_analysis_report_cache_key",
        lambda project_key, analyzer_key: f"{project_key}:{analyzer_key}",
    )

    checks_application.run_checks(
        DEFAULT_CONFIG.copy(),
        ["state-inference"],
        iter_loaded_projects_fn=cast(
            Any,
            lambda *_args, **_kwargs: iter(
                [
                    (
                        "TargetA",
                        named_object("TargetA"),
                        AnalysisGraphStub(
                            unavailable_libraries=set(),
                            analysis_cache_key="project-key",
                            analysis_manifest_files=frozenset({Path("programs/TargetA.s")}),
                        ),
                    )
                ]
            ),
        ),
        get_enabled_analyzers_fn=lambda: [
            SimpleNamespace(
                key="state-inference",
                name="State inference",
                run=lambda _context: run_calls.append("run") or MutableReport("Live"),
            )
        ],
        target_is_library_fn=lambda *_args, **_kwargs: False,
        pause_fn=None,
    )

    assert run_calls == []
    assert load_keys == ["project-key:state-inference"]
    assert validate_calls == [({"report": cached_report}, False)]
    assert save_calls == []
    assert any("state inference summary for TargetA" in line for line in lines)


def test_run_checks_rebuilds_report_cache_when_cached_payload_is_stale(monkeypatch):
    lines: list[str] = []
    run_calls: list[str] = []
    load_keys: list[str] = []
    save_calls: list[tuple[str, object, frozenset[Path]]] = []

    class MutableReport:
        def __init__(self, name: str) -> None:
            self.name = name
            self.issues: list[object] = []

        def summary(self) -> str:
            return f"state inference summary for {self.name}"

    class FakeReportCache:
        def __init__(self, cache_dir):
            assert cache_dir == Path("report-cache-dir")

        def load(self, key):
            load_keys.append(key)
            return {"report": MutableReport("Stale")}

        def validate(self, payload, *, fast=False):
            del payload, fast
            return False

        def save(self, key, *, report, files):
            save_calls.append((key, report, frozenset(files)))
            return True

    monkeypatch.setattr(output_module, "emit_output", lambda message: lines.append(message))
    monkeypatch.setattr(checks_application, "AnalysisReportCache", FakeReportCache)
    monkeypatch.setattr(checks_application, "get_cache_dir", lambda: Path("report-cache-dir"))
    monkeypatch.setattr(
        checks_application,
        "compute_analysis_report_cache_key",
        lambda project_key, analyzer_key: f"{project_key}:{analyzer_key}",
    )

    checks_application.run_checks(
        DEFAULT_CONFIG.copy(),
        ["state-inference"],
        iter_loaded_projects_fn=cast(
            Any,
            lambda *_args, **_kwargs: iter(
                [
                    (
                        "TargetA",
                        named_object("TargetA"),
                        AnalysisGraphStub(
                            unavailable_libraries=set(),
                            analysis_cache_key="project-key",
                            analysis_manifest_files=frozenset({Path("programs/TargetA.s")}),
                        ),
                    )
                ]
            ),
        ),
        get_enabled_analyzers_fn=lambda: [
            SimpleNamespace(
                key="state-inference",
                name="State inference",
                run=lambda _context: run_calls.append("run") or MutableReport("Live"),
            )
        ],
        target_is_library_fn=lambda *_args, **_kwargs: False,
        pause_fn=None,
    )

    assert run_calls == ["run"]
    assert load_keys == ["project-key:state-inference"]
    assert save_calls == [
        (
            "project-key:state-inference",
            save_calls[0][1],
            frozenset({Path("programs/TargetA.s")}),
        )
    ]
    assert any("state inference summary for TargetA" in line for line in lines)


def test_run_checks_bypasses_report_cache_when_use_cache_disabled(monkeypatch):
    run_calls: list[str] = []

    class ForbiddenReportCache:
        def __init__(self, _cache_dir):
            pytest.fail("report cache should be bypassed when use_cache is false")

    monkeypatch.setattr(checks_application, "AnalysisReportCache", ForbiddenReportCache)

    checks_application.run_checks(
        DEFAULT_CONFIG.copy(),
        ["state-inference"],
        use_cache=False,
        iter_loaded_projects_fn=cast(
            Any,
            lambda *_args, **_kwargs: iter(
                [
                    (
                        "TargetA",
                        named_object("TargetA"),
                        AnalysisGraphStub(
                            unavailable_libraries=set(),
                            analysis_cache_key="project-key",
                            analysis_manifest_files=frozenset({Path("programs/TargetA.s")}),
                        ),
                    )
                ]
            ),
        ),
        get_enabled_analyzers_fn=lambda: [
            SimpleNamespace(
                key="state-inference",
                name="State inference",
                run=lambda _context: run_calls.append("run") or SimpleNamespace(issues=[], summary=lambda: "summary"),
            )
        ],
        target_is_library_fn=lambda *_args, **_kwargs: False,
        pause_fn=None,
    )

    assert run_calls == ["run"]


def test_run_checks_bypasses_report_cache_when_debug_enabled(monkeypatch):
    run_calls: list[str] = []

    class ForbiddenReportCache:
        def __init__(self, _cache_dir):
            pytest.fail("report cache should be bypassed when debug is true")

    monkeypatch.setattr(checks_application, "AnalysisReportCache", ForbiddenReportCache)

    checks_application.run_checks(
        DEFAULT_CONFIG.copy() | {"debug": True},
        ["state-inference"],
        iter_loaded_projects_fn=cast(
            Any,
            lambda *_args, **_kwargs: iter(
                [
                    (
                        "TargetA",
                        named_object("TargetA"),
                        AnalysisGraphStub(
                            unavailable_libraries=set(),
                            analysis_cache_key="project-key",
                            analysis_manifest_files=frozenset({Path("programs/TargetA.s")}),
                        ),
                    )
                ]
            ),
        ),
        get_enabled_analyzers_fn=lambda: [
            SimpleNamespace(
                key="state-inference",
                name="State inference",
                run=lambda _context: run_calls.append("run") or SimpleNamespace(issues=[], summary=lambda: "summary"),
            )
        ],
        target_is_library_fn=lambda *_args, **_kwargs: False,
        pause_fn=None,
    )

    assert run_calls == ["run"]


def test_run_checks_handles_keyboard_interrupt_and_pauses(monkeypatch):
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
                        named_object("TargetA"),
                        AnalysisGraphStub(),
                    )
                ]
            ),
        ),
        get_enabled_analyzers_fn=lambda: [
            SimpleNamespace(
                key="state-inference",
                name="State inference",
                run=lambda _context: (_ for _ in ()).throw(KeyboardInterrupt()),
            )
        ],
        target_is_library_fn=lambda *_args, **_kwargs: False,
        pause_fn=lambda: pauses.append("pause"),
    )

    assert any("Operation canceled. Returning to the menu." in line for line in lines)
    assert pauses == ["pause"]


def test_run_checks_accepts_legacy_underscore_analyzer_key(monkeypatch):
    lines: list[str] = []

    monkeypatch.setattr(output_module, "emit_output", lambda message: lines.append(message))

    checks_application.run_checks(
        DEFAULT_CONFIG.copy(),
        ["same_cycle"],
        iter_loaded_projects_fn=cast(
            Any,
            lambda *_args, **_kwargs: iter(
                [
                    (
                        "TargetA",
                        named_object("TargetA"),
                        AnalysisGraphStub(),
                    )
                ]
            ),
        ),
        get_enabled_analyzers_fn=lambda: [
            SimpleNamespace(
                key="same-cycle",
                name="Same-cycle hazards",
                run=lambda _context: SimpleNamespace(summary=lambda: "same-cycle summary"),
            )
        ],
        target_is_library_fn=lambda *_args, **_kwargs: False,
        pause_fn=None,
    )

    assert any("Same-cycle hazards (same-cycle)" in line for line in lines)


def test_run_checks_result_returns_structured_result_and_persists_run(tmp_path, monkeypatch) -> None:
    emitted: list[str] = []
    monkeypatch.setattr(output_module, "emit_output", lambda message: emitted.append(str(message)))
    monkeypatch.setattr(checks_application, "get_runs_dir", lambda: tmp_path)

    report = SimpleNamespace(
        summary=lambda: "state inference summary",
        issues=[
            Issue(
                kind="unused",
                message="declared but never read",
                module_path=["TargetA"],
            )
        ],
    )

    result = checks_application.run_checks_result(
        DEFAULT_CONFIG.copy(),
        ["state-inference"],
        iter_loaded_projects_fn=cast(
            Any,
            lambda *_args, **_kwargs: iter(
                [("TargetA", SimpleNamespace(header=SimpleNamespace(name="TargetA")), SimpleNamespace())]
            ),
        ),
        get_enabled_analyzers_fn=lambda: [
            SimpleNamespace(key="state-inference", name="State inference", run=lambda _context: report)
        ],
        target_is_library_fn=lambda *_args, **_kwargs: False,
    )

    assert result.selected_analyzers == ("state-inference",)
    assert result.targets[0].analyzers[0].status == "completed"
    assert result.targets[0].analyzers[0].findings[0].kind == "unused"
    assert result.targets[0].analyzers[0].findings[0].module_path == ("TargetA",)
    assert any("state inference summary" in line for line in emitted)
    assert len(list(tmp_path.glob("*.json"))) == 1
