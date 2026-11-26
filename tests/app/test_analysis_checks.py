# pyright: reportUnknownLambdaType=false, reportUnknownArgumentType=false
import json
import multiprocessing
import os
import time
from collections.abc import Callable, Iterable, Iterator
from pathlib import Path
from types import SimpleNamespace, TracebackType
from typing import Any, cast

import pytest
from sattline_parser.models.ast_model import (
    BasePicture,
    FrameModule,
    ModuleHeader,
    ModuleTypeDef,
    ModuleTypeInstance,
    SingleModule,
)

from sattlint import console as console_module
from sattlint.analyzers import catalog as analysis_catalog_module
from sattlint.analyzers.framework import AnalysisContext, Issue, SimpleReport
from sattlint.application import (
    checks as checks_application,
)
from sattlint.application import (
    checks_execution,
    checks_records,
)
from sattlint.application import (
    output as output_module,
)
from sattlint.application.project import LoadedProject
from sattlint.config import DEFAULT_CONFIG
from sattlint.config.types import ConfigDict
from sattlint.core import profiling as profiling_module
from sattlint.core.timings import PhaseTiming
from sattlint.models.project_graph import ProjectGraph
from sattlint.project import loading as project_loading_module
from sattlint.reporting import target_report as analysis_reporting_module
from sattlint.runs import load_run
from tests.helpers import AnalysisGraphStub, named_object


def test_snapshot_module_tree_includes_empty_modules_and_instance_children() -> None:
    def header(name: str) -> ModuleHeader:
        return ModuleHeader(name=name, invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0))

    template = ModuleTypeDef(
        name="InlineLager",
        submodules=[
            FrameModule(header=header("L1")),
            ModuleTypeInstance(header=header("UnitHeader1"), moduletype_name="UnitHeader"),
        ],
    )
    root = BasePicture(
        header=header("BasePicture"),
        origin_lib="HC",
        origin_file="KaHCBInlineLib.s",
        moduletype_defs=[template],
        submodules=[
            FrameModule(header=header("StartMaster"), submodules=[SingleModule(header=header("ChangeLog"))]),
            ModuleTypeInstance(header=header("InlineLager"), moduletype_name="InlineLager"),
        ],
    )

    graph = ProjectGraph()
    graph.moduletype_defs[("hc", "unitheader", "nnestruct.x")] = ModuleTypeDef(
        name="UnitHeader", origin_lib="HC", origin_file="nnestruct.x"
    )
    snapshot = checks_records.snapshot_module_tree(root, graph, "KaHCBInlineLib")

    assert snapshot.name == "KaHCBInlineLib:BasePicture"
    assert snapshot.kind == "SingleModule"
    assert [(child.name, child.kind, child.moduletype_name) for child in snapshot.children] == [
        ("StartMaster", "FrameModule", None),
        ("InlineLager", "", "InlineLager"),
    ]
    assert snapshot.children[0].children[0].name == "ChangeLog"
    assert [child.name for child in snapshot.children[1].children] == ["L1", "UnitHeader1"]
    assert snapshot.children[1].children[1].moduletype_name == "nnestruct:UnitHeader"


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


def test_select_report_source_path_prefers_configured_mode_suffix_on_equal_mtime(tmp_path: Path) -> None:
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


def test_run_checks_reports_no_matching_checks_and_pauses(monkeypatch: pytest.MonkeyPatch):
    lines: list[str] = []
    pauses: list[str] = []

    monkeypatch.setattr(output_module, "emit_output", lambda message: lines.append(message))

    checks_application.run_checks(
        cast(ConfigDict, DEFAULT_CONFIG.copy()),
        ["missing-check"],
        get_enabled_analyzers_fn=lambda: [SimpleNamespace(key="variables", name="Variables")],
        pause_fn=lambda: pauses.append("pause"),
    )

    assert any("No matching checks found" in line for line in lines)
    assert pauses == ["pause"]


def test_collect_run_checks_result_aborts_when_self_check_fails():
    run_calls: list[str] = []

    result = checks_application.collect_run_checks_result(
        cast(ConfigDict, DEFAULT_CONFIG.copy()),
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


def test_collect_run_checks_result_streams_each_line_while_the_run_is_in_progress():
    streamed: list[str] = []
    streamed_before_yield: list[str] = []

    def _projects(
        *_args: object, emit_output_fn: Callable[..., None] | None = None, **_kwargs: object
    ) -> Iterator[tuple[str, object, object]]:
        assert callable(emit_output_fn)
        emit_output_fn("Loading TargetA")
        streamed_before_yield.extend(streamed)
        yield ("TargetA", named_object("TargetA"), AnalysisGraphStub(unavailable_libraries=set()))

    result = checks_application.collect_run_checks_result(
        cast(ConfigDict, DEFAULT_CONFIG.copy()),
        ["state-inference"],
        iter_loaded_projects_fn=cast(Callable[..., Iterator[LoadedProject]], _projects),
        get_enabled_analyzers_fn=lambda: [
            SimpleNamespace(
                key="state-inference",
                name="State inference",
                run=lambda _context: SimpleNamespace(issues=[], summary=lambda: "summary"),
            )
        ],
        target_is_library_fn=lambda *_args, **_kwargs: False,
        self_check_fn=lambda _cfg: True,
        emit_output=streamed.append,
    )

    assert any("--- Running checks ---" in line for line in streamed_before_yield)
    assert streamed == list(result.output_lines)


def test_collect_run_checks_result_runs_analyzers_when_self_check_passes():
    run_calls: list[str] = []

    result = checks_application.collect_run_checks_result(
        cast(ConfigDict, DEFAULT_CONFIG.copy()),
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


def test_run_checks_runs_selected_non_default_cli_exposed_analyzer(monkeypatch: pytest.MonkeyPatch):
    lines: list[str] = []

    monkeypatch.setattr(output_module, "emit_output", lambda message: lines.append(message))

    class MutableReport:
        def __init__(self) -> None:
            self.basepicture_name = "BasePicture"

        def summary(self) -> str:
            return f"state inference summary for {self.basepicture_name}"

    report = MutableReport()

    checks_application.run_checks(
        cast(ConfigDict, DEFAULT_CONFIG.copy()),
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


def test_run_checks_updates_live_status_for_active_analyzer(monkeypatch: pytest.MonkeyPatch):
    updates: list[str] = []

    class FakeLiveStatusLine:
        def __enter__(self) -> Callable[[str], None]:
            return updates.append

        def __exit__(
            self,
            exc_type: type[BaseException] | None,
            exc: BaseException | None,
            tb: TracebackType | None,
        ) -> bool:
            return False

    monkeypatch.setattr(output_module, "emit_output", lambda _message: None)
    monkeypatch.setattr(console_module, "live_status_line", lambda: FakeLiveStatusLine())

    checks_application.run_checks(
        cast(ConfigDict, DEFAULT_CONFIG.copy()),
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
        cast(ConfigDict, DEFAULT_CONFIG.copy()),
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
    assert analyzer.phase_timings_ms == (PhaseTiming(phase="plan", duration_ms=1.25),)


def test_collect_run_checks_result_runs_icf_once_as_whole_run_target(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: dict[str, int] = {"n": 0}

    def _fake_icf(context: AnalysisContext) -> SimpleReport:
        calls["n"] += 1
        return SimpleReport(
            name="ICF configuration",
            issues=[Issue(kind="icf.unresolved_path", message="Program.icf:1: unresolved path")],
        )

    result = checks_application.collect_run_checks_result(
        cast(ConfigDict, DEFAULT_CONFIG.copy()),
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


def test_collect_run_checks_result_binds_the_program_loader_for_per_run_analyzers() -> None:
    captured: list[AnalysisContext] = []

    def _capture(context: AnalysisContext) -> SimpleReport:
        captured.append(context)
        return SimpleReport(name="Program loader probe")

    result = checks_application.collect_run_checks_result(
        cast(ConfigDict, DEFAULT_CONFIG.copy()),
        ["program-loader-probe"],
        use_cache=False,
        get_enabled_analyzers_fn=lambda: [
            SimpleNamespace(
                key="program-loader-probe",
                name="Program loader probe",
                scope="per-run",
                run=_capture,
            )
        ],
        target_is_library_fn=lambda *_args, **_kwargs: False,
        self_check_fn=lambda _cfg: True,
    )

    assert result.cancelled is False
    assert len(captured) == 1
    assert captured[0].program_ast_loader is project_loading_module.load_program_ast
    assert captured[0].program_ast_batch_loader is project_loading_module.load_program_asts


def test_run_checks_selection_is_exact_and_drops_unregistered_keys(monkeypatch: pytest.MonkeyPatch):
    lines: list[str] = []
    run_order: list[str] = []
    shared_ids: list[int] = []

    def _report(name: str):
        return SimpleNamespace(summary=lambda: name, issues=[])

    def _variables_run(context: AnalysisContext):
        run_order.append("variables")
        shared_ids.append(id(context.shared_artifacts))
        assert context.shared_artifacts is not None
        return _report("variables summary")

    monkeypatch.setattr(output_module, "emit_output", lambda message: lines.append(message))

    checks_application.run_checks(
        cast(ConfigDict, DEFAULT_CONFIG.copy()),
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


def test_run_checks_writes_target_profiling_summary(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    profile_path = tmp_path / "profile.jsonl"
    monkeypatch.setattr(output_module, "emit_output", lambda _message: None)
    monkeypatch.setenv("SATTLINT_PROFILE", "1")
    monkeypatch.setattr(profiling_module, "profiling_log_path", lambda: tmp_path / "profile.jsonl")

    checks_application.run_checks(
        cast(ConfigDict, DEFAULT_CONFIG.copy()),
        ["state-inference", "variables"],
        iter_loaded_projects_fn=cast(
            Any,
            lambda *_args, **_kwargs: iter(
                [
                    (
                        "TargetA",
                        SimpleNamespace(header=SimpleNamespace(name="TargetA")),
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


def test_run_checks_uses_cached_report_when_available(monkeypatch: pytest.MonkeyPatch):
    lines: list[str] = []
    run_calls: list[str] = []
    load_keys: list[str] = []
    validate_calls: list[tuple[object, bool]] = []
    save_calls: list[tuple[str, object, frozenset[Path]]] = []

    class MutableReport:
        def __init__(self, name: str) -> None:
            self.basepicture_name = name
            self.issues: list[object] = []

        def summary(self) -> str:
            return f"state inference summary for {self.basepicture_name}"

    cached_report = MutableReport("BasePicture")

    class FakeReportCache:
        def __init__(self, cache_dir: Path):
            assert cache_dir == Path("report-cache-dir")

        def load(self, key: str) -> dict[str, object]:
            load_keys.append(key)
            return {"report": cached_report}

        def validate(self, payload: object, *, fast: bool = False) -> bool:
            validate_calls.append((payload, fast))
            return True

        def save(self, key: str, *, report: object, files: Iterable[Path]) -> bool:
            save_calls.append((key, report, frozenset(files)))
            return True

    monkeypatch.setattr(output_module, "emit_output", lambda message: lines.append(message))
    monkeypatch.setattr(checks_application, "AnalysisReportCache", FakeReportCache)
    monkeypatch.setattr(checks_application, "get_cache_dir_or_none", lambda: Path("report-cache-dir"))
    monkeypatch.setattr(
        checks_application,
        "compute_analysis_report_cache_key",
        lambda project_key, analyzer_key, **_kwargs: f"{project_key}:{analyzer_key}",
    )

    checks_application.run_checks(
        cast(ConfigDict, DEFAULT_CONFIG.copy()),
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


def test_run_checks_rebuilds_report_cache_when_cached_payload_is_stale(monkeypatch: pytest.MonkeyPatch):
    lines: list[str] = []
    run_calls: list[str] = []
    load_keys: list[str] = []
    save_calls: list[tuple[str, object, frozenset[Path]]] = []

    class MutableReport:
        def __init__(self, name: str) -> None:
            self.basepicture_name = name
            self.issues: list[object] = []

        def summary(self) -> str:
            return f"state inference summary for {self.basepicture_name}"

    class FakeReportCache:
        def __init__(self, cache_dir: Path):
            assert cache_dir == Path("report-cache-dir")

        def load(self, key: str) -> dict[str, object]:
            load_keys.append(key)
            return {"report": MutableReport("Stale")}

        def validate(self, payload: object, *, fast: bool = False) -> bool:
            del payload, fast
            return False

        def save(self, key: str, *, report: object, files: Iterable[Path]) -> bool:
            save_calls.append((key, report, frozenset(files)))
            return True

    monkeypatch.setattr(output_module, "emit_output", lambda message: lines.append(message))
    monkeypatch.setattr(checks_application, "AnalysisReportCache", FakeReportCache)
    monkeypatch.setattr(checks_application, "get_cache_dir_or_none", lambda: Path("report-cache-dir"))
    monkeypatch.setattr(
        checks_application,
        "compute_analysis_report_cache_key",
        lambda project_key, analyzer_key, **_kwargs: f"{project_key}:{analyzer_key}",
    )

    checks_application.run_checks(
        cast(ConfigDict, DEFAULT_CONFIG.copy()),
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


def test_run_checks_passes_analysis_settings_to_the_report_cache_key(monkeypatch: pytest.MonkeyPatch):
    captured: list[object] = []

    class FakeReportCache:
        def __init__(self, _cache_dir: Path):
            return None

        def load(self, _key: str) -> None:
            return None

        def validate(self, _payload: object, *, fast: bool = False) -> bool:
            del fast
            return False

        def save(self, _key: str, *, report: object, files: Iterable[Path]) -> bool:
            del report, files
            return True

    def key_fn(project_key: str, analyzer_key: str, **kwargs: object):
        captured.append(kwargs.get("analysis_settings"))
        return f"{project_key}:{analyzer_key}"

    monkeypatch.setattr(checks_application, "AnalysisReportCache", FakeReportCache)
    monkeypatch.setattr(checks_application, "get_cache_dir_or_none", lambda: Path("report-cache-dir"))
    monkeypatch.setattr(checks_application, "compute_analysis_report_cache_key", key_fn)

    checks_application.collect_run_checks_result(
        cast(ConfigDict, DEFAULT_CONFIG.copy() | {"analysis": {"fan_in_out_threshold": 7}}),
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
                run=lambda _context: SimpleNamespace(issues=[], summary=lambda: "summary"),
            )
        ],
        target_is_library_fn=lambda *_args, **_kwargs: False,
        self_check_fn=lambda _cfg: True,
    )

    assert captured == [{"fan_in_out_threshold": 7}]


def test_module_tree_is_built_only_for_a_run_that_gets_persisted(monkeypatch: pytest.MonkeyPatch) -> None:
    built: list[str] = []

    def fake_snapshot(_bp: object, _graph: object, _target: str) -> SimpleNamespace:
        built.append(_target)
        return SimpleNamespace(name=_target)

    monkeypatch.setattr(checks_execution, "snapshot_module_tree", fake_snapshot)
    monkeypatch.setattr(checks_records, "get_runs_dir_or_none", lambda: None)

    def run(persist: bool) -> None:
        checks_application.collect_run_checks_result(
            cast(ConfigDict, DEFAULT_CONFIG.copy()),
            ["state-inference"],
            iter_loaded_projects_fn=cast(
                Any,
                lambda *_args, **_kwargs: iter(
                    [
                        (
                            "TargetA",
                            BasePicture(
                                header=ModuleHeader(name="BasePicture", invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0))
                            ),
                            AnalysisGraphStub(),
                        )
                    ]
                ),
            ),
            get_enabled_analyzers_fn=lambda: [
                SimpleNamespace(
                    key="state-inference",
                    name="State inference",
                    run=lambda _context: SimpleNamespace(issues=[], summary=lambda: "summary"),
                )
            ],
            target_is_library_fn=lambda *_args, **_kwargs: False,
            self_check_fn=lambda _cfg: True,
            persist_run=persist,
        )

    run(False)
    assert built == []

    run(True)
    assert built == ["TargetA"]


def test_collect_run_checks_result_records_loader_failures_as_text():
    def iterator(
        _cfg: ConfigDict,
        *,
        failure_sink: Callable[[str, str], None] | None = None,
        emit_output_fn: Callable[..., None] | None = None,
        **_kwargs: object,
    ):
        assert failure_sink is not None
        assert emit_output_fn is not None
        failure_sink("Broken", "root failed")
        emit_output_fn(RuntimeError("boom"))
        return iter(())

    result = checks_application.collect_run_checks_result(
        cast(ConfigDict, DEFAULT_CONFIG.copy() | {"analyzed_programs_and_libraries": ["Broken"]}),
        ["state-inference"],
        iter_loaded_projects_fn=cast(Callable[..., Iterator[LoadedProject]], iterator),
        get_enabled_analyzers_fn=lambda: [
            SimpleNamespace(
                key="state-inference",
                name="State inference",
                run=lambda _context: SimpleNamespace(issues=[], summary=lambda: "summary"),
            )
        ],
        target_is_library_fn=lambda *_args, **_kwargs: False,
        self_check_fn=lambda _cfg: True,
    )

    assert [(failure.target_name, failure.message) for failure in result.failures] == [("Broken", "root failed")]
    assert "\n".join(result.output_lines).endswith("boom")


def test_collect_run_checks_result_forwards_refresh_ast_to_project_loading(monkeypatch: pytest.MonkeyPatch):
    seen: list[bool] = []

    def iterator(_cfg: ConfigDict, *, refresh_ast: bool = False, **_kwargs: object):
        seen.append(refresh_ast)
        return iter(())

    checks_application.collect_run_checks_result(
        cast(ConfigDict, DEFAULT_CONFIG.copy()),
        ["state-inference"],
        refresh_ast=True,
        iter_loaded_projects_fn=cast(Callable[..., Iterator[LoadedProject]], iterator),
        get_enabled_analyzers_fn=lambda: [
            SimpleNamespace(
                key="state-inference",
                name="State inference",
                run=lambda _context: SimpleNamespace(issues=[], summary=lambda: "summary"),
            )
        ],
        target_is_library_fn=lambda *_args, **_kwargs: False,
        self_check_fn=lambda _cfg: True,
    )

    assert seen == [True]


def test_disabling_the_report_cache_leaves_the_parsed_graph_cached(monkeypatch: pytest.MonkeyPatch):
    """``--no-cache`` discards analyzer reports, not the parsed project graph."""
    seen: list[bool] = []

    def iterator(_cfg: ConfigDict, *, refresh_ast: bool = False, **_kwargs: object):
        seen.append(refresh_ast)
        return iter(())

    checks_application.collect_run_checks_result(
        cast(ConfigDict, DEFAULT_CONFIG.copy()),
        ["state-inference"],
        use_cache=False,
        iter_loaded_projects_fn=cast(Callable[..., Iterator[LoadedProject]], iterator),
        get_enabled_analyzers_fn=lambda: [
            SimpleNamespace(
                key="state-inference",
                name="State inference",
                run=lambda _context: SimpleNamespace(issues=[], summary=lambda: "summary"),
            )
        ],
        target_is_library_fn=lambda *_args, **_kwargs: False,
        self_check_fn=lambda _cfg: True,
    )

    assert seen == [False]


def test_collect_run_checks_result_does_not_prune_when_save_fails(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    spec = analysis_catalog_module.get_selectable_analyzers()[0]

    def fail_save(*_args: object, **_kwargs: object):
        raise OSError("disk full")

    monkeypatch.setattr(checks_records, "get_runs_dir_or_none", lambda: tmp_path / "runs")
    monkeypatch.setattr(checks_records, "save_run", fail_save)
    monkeypatch.setattr(checks_records, "prune_runs", lambda *_args, **_kwargs: pytest.fail("must not prune"))

    result = checks_application.collect_run_checks_result(
        cast(ConfigDict, DEFAULT_CONFIG.copy() | {"analyzed_programs_and_libraries": ["Demo"]}),
        [spec.key],
        use_cache=False,
        persist_run=True,
        iter_loaded_projects_fn=cast(Callable[..., Iterator[LoadedProject]], lambda *_args, **_kwargs: iter(())),
        get_enabled_analyzers_fn=lambda: [spec],
        target_is_library_fn=lambda *_args, **_kwargs: False,
        self_check_fn=lambda _cfg: True,
    )

    assert result.run_id is None


def test_collect_run_checks_result_exposes_failed_per_run_analyzer() -> None:
    result = checks_application.collect_run_checks_result(
        cast(ConfigDict, DEFAULT_CONFIG.copy()),
        ["icf"],
        iter_loaded_projects_fn=cast(Callable[..., Iterator[LoadedProject]], lambda *_args, **_kwargs: iter(())),
        get_enabled_analyzers_fn=lambda: [
            SimpleNamespace(
                key="icf",
                name="ICF configuration",
                scope="per-run",
                run=lambda _context: (_ for _ in ()).throw(RuntimeError("boom")),
            )
        ],
        target_is_library_fn=lambda *_args, **_kwargs: False,
        self_check_fn=lambda _cfg: True,
    )

    assert result.targets[0].is_pseudo is True
    assert [(failure.analyzer_name, failure.target_name) for failure in result.analyzer_failures] == [
        ("ICF configuration", "ICF configuration")
    ]


def test_collect_run_checks_result_keeps_running_when_report_cache_is_unusable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    blocked_cache = tmp_path / "blocked-cache"
    blocked_cache.write_text("not a directory", encoding="utf-8")
    monkeypatch.setattr(checks_application, "get_cache_dir_or_none", lambda: blocked_cache)

    result = checks_application.collect_run_checks_result(
        cast(ConfigDict, DEFAULT_CONFIG.copy()),
        ["state-inference"],
        use_cache=True,
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
                run=lambda _context: SimpleNamespace(issues=[], summary=lambda: "summary"),
            )
        ],
        target_is_library_fn=lambda *_args, **_kwargs: False,
        self_check_fn=lambda _cfg: True,
    )

    assert len(result.targets) == 1
    assert result.targets[0].analyzers[0].status == "completed"


def test_run_checks_bypasses_report_cache_when_use_cache_disabled(monkeypatch: pytest.MonkeyPatch):
    run_calls: list[str] = []

    class ForbiddenReportCache:
        def __init__(self, _cache_dir: Path) -> None:
            pytest.fail("report cache should be bypassed when use_cache is false")

    monkeypatch.setattr(checks_application, "AnalysisReportCache", ForbiddenReportCache)

    checks_application.run_checks(
        cast(ConfigDict, DEFAULT_CONFIG.copy()),
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


def test_run_checks_bypasses_report_cache_when_debug_enabled(monkeypatch: pytest.MonkeyPatch):
    run_calls: list[str] = []

    class ForbiddenReportCache:
        def __init__(self, _cache_dir: Path) -> None:
            pytest.fail("report cache should be bypassed when debug is true")

    monkeypatch.setattr(checks_application, "AnalysisReportCache", ForbiddenReportCache)

    checks_application.run_checks(
        cast(ConfigDict, DEFAULT_CONFIG.copy() | {"debug": True}),
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


def test_run_checks_handles_keyboard_interrupt_and_pauses(monkeypatch: pytest.MonkeyPatch):
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


def test_run_checks_accepts_legacy_underscore_analyzer_key(monkeypatch: pytest.MonkeyPatch):
    lines: list[str] = []

    monkeypatch.setattr(output_module, "emit_output", lambda message: lines.append(message))

    checks_application.run_checks(
        cast(ConfigDict, DEFAULT_CONFIG.copy()),
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


def test_run_checks_result_returns_structured_result_and_persists_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    emitted: list[str] = []
    monkeypatch.setattr(output_module, "emit_output", lambda message: emitted.append(str(message)))
    monkeypatch.setattr(checks_records, "get_runs_dir_or_none", lambda: tmp_path)

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
        cast(ConfigDict, DEFAULT_CONFIG.copy()),
        ["state-inference"],
        iter_loaded_projects_fn=cast(
            Any,
            lambda *_args, **_kwargs: iter(
                [("TargetA", SimpleNamespace(header=SimpleNamespace(name="TargetA")), AnalysisGraphStub())]
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


def test_collect_run_checks_result_returns_the_partial_target_when_an_analyzer_is_cancelled() -> None:
    result = checks_application.collect_run_checks_result(
        cast(ConfigDict, DEFAULT_CONFIG.copy()),
        ["first", "second"],
        use_cache=False,
        jobs=1,
        iter_loaded_projects_fn=cast(
            Any,
            lambda *_args, **_kwargs: iter(
                [("TargetA", SimpleNamespace(header=SimpleNamespace(name="TargetA")), AnalysisGraphStub())]
            ),
        ),
        get_enabled_analyzers_fn=lambda: [
            SimpleNamespace(
                key="first",
                name="First",
                run=lambda _context: SimpleNamespace(issues=[], summary=lambda: "first summary"),
            ),
            SimpleNamespace(
                key="second",
                name="Second",
                run=lambda _context: (_ for _ in ()).throw(KeyboardInterrupt()),
            ),
        ],
        target_is_library_fn=lambda *_args, **_kwargs: False,
        self_check_fn=lambda _cfg: True,
    )

    assert result.cancelled is True
    assert len(result.targets) == 1
    assert [(analyzer.key, analyzer.status) for analyzer in result.targets[0].analyzers] == [
        ("first", "completed"),
        ("second", "cancelled"),
    ]
    assert result.targets[0].analyzers[1].duration_ms is not None
    assert any("first summary" in line for line in result.output_lines)


def test_collect_run_checks_result_keeps_completed_per_run_results_when_cancelled() -> None:
    result = checks_application.collect_run_checks_result(
        cast(ConfigDict, DEFAULT_CONFIG.copy()),
        ["first-run", "second-run"],
        use_cache=False,
        get_enabled_analyzers_fn=lambda: [
            SimpleNamespace(
                key="first-run",
                name="First run",
                scope="per-run",
                run=lambda _context: SimpleNamespace(issues=[], summary=lambda: "first run summary"),
            ),
            SimpleNamespace(
                key="second-run",
                name="Second run",
                scope="per-run",
                run=lambda _context: (_ for _ in ()).throw(KeyboardInterrupt()),
            ),
        ],
        target_is_library_fn=lambda *_args, **_kwargs: False,
        self_check_fn=lambda _cfg: True,
    )

    assert result.cancelled is True
    assert [target.target_name for target in result.targets] == ["First run"]
    assert [(analyzer.key, analyzer.status) for analyzer in result.targets[0].analyzers] == [("first-run", "completed")]
    assert any("first run summary" in line for line in result.output_lines)


def test_per_target_analyzer_raise_is_reported_as_analyzer_failure() -> None:
    def _explode(_context: AnalysisContext):
        raise RuntimeError("boom")

    result = checks_application.collect_run_checks_result(
        cast(ConfigDict, DEFAULT_CONFIG.copy()),
        ["state-inference"],
        use_cache=False,
        iter_loaded_projects_fn=cast(
            Any,
            lambda *_args, **_kwargs: iter(
                [("TargetA", SimpleNamespace(header=SimpleNamespace(name="TargetA")), AnalysisGraphStub())]
            ),
        ),
        get_enabled_analyzers_fn=lambda: [SimpleNamespace(key="state-inference", name="State inference", run=_explode)],
        target_is_library_fn=lambda *_args, **_kwargs: False,
        self_check_fn=lambda _cfg: True,
    )

    assert result.targets[0].analyzers[0].status == "failed"
    summary = result.targets[0].analyzers[0].summary or ""
    assert summary == "State inference failed: RuntimeError"
    assert "boom" not in summary
    assert [(failure.analyzer_name, failure.target_name) for failure in result.analyzer_failures] == [
        ("State inference", "TargetA")
    ]


def test_failed_analyzer_still_saves_the_run(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(checks_records, "get_runs_dir_or_none", lambda: tmp_path / "runs")
    monkeypatch.setattr(checks_records, "prune_runs", lambda *_args, **_kwargs: None)

    def _explode(_context: AnalysisContext):
        raise RuntimeError("boom")

    loaded = SimpleNamespace(header=SimpleNamespace(name="TargetA"))
    result = checks_application.collect_run_checks_result(
        cast(ConfigDict, DEFAULT_CONFIG.copy() | {"analyzed_programs_and_libraries": ["TargetA"]}),
        ["state-inference"],
        use_cache=False,
        persist_run=True,
        iter_loaded_projects_fn=cast(
            Callable[..., Iterator[LoadedProject]],
            lambda *_args, **_kwargs: iter([("TargetA", loaded, AnalysisGraphStub())]),
        ),
        get_enabled_analyzers_fn=lambda: [SimpleNamespace(key="state-inference", name="State inference", run=_explode)],
        target_is_library_fn=lambda *_args, **_kwargs: False,
        self_check_fn=lambda _cfg: True,
    )

    assert result.run_id is not None
    stored = load_run(result.run_id, runs_dir=tmp_path / "runs")
    assert stored is not None
    analyzer = stored.targets[0].analyzers[0]
    assert analyzer.status == "failed"
    assert analyzer.summary == "State inference failed: RuntimeError"
    assert "boom" not in (analyzer.summary or "")
    assert [(failure.analyzer_name, failure.target_name) for failure in result.analyzer_failures] == [
        ("State inference", "TargetA")
    ]


def test_pseudo_target_is_not_persisted_in_the_run_record() -> None:
    result = checks_application.collect_run_checks_result(
        cast(ConfigDict, DEFAULT_CONFIG.copy()),
        ["state-inference"],
        use_cache=False,
        iter_loaded_projects_fn=cast(Callable[..., Iterator[LoadedProject]], lambda *_args, **_kwargs: iter(())),
        get_enabled_analyzers_fn=lambda: [
            SimpleNamespace(
                key="state-inference",
                name="State inference",
                scope="per-run",
                run=lambda _context: SimpleNamespace(summary=lambda: "ok", issues=[]),
            )
        ],
        target_is_library_fn=lambda *_args, **_kwargs: False,
        self_check_fn=lambda _cfg: True,
    )

    record = checks_application.build_run_record(result, cast(ConfigDict, DEFAULT_CONFIG.copy()))

    assert [(target.target_name, target.is_library) for target in record.targets] == []


def test_analyzer_issue_count_matches_the_findings_it_stores():
    result = checks_application.collect_run_checks_result(
        cast(ConfigDict, DEFAULT_CONFIG.copy()),
        ["state-inference"],
        iter_loaded_projects_fn=cast(
            Any,
            lambda *_args, **_kwargs: iter(
                [("TargetA", named_object("TargetA"), AnalysisGraphStub(unavailable_libraries=set()))]
            ),
        ),
        get_enabled_analyzers_fn=lambda: [
            SimpleNamespace(
                key="state-inference",
                name="State inference",
                run=lambda _context: SimpleNamespace(summary=lambda: "summary"),
            )
        ],
        target_is_library_fn=lambda *_args, **_kwargs: False,
        self_check_fn=lambda _cfg: True,
    )

    analyzer = result.targets[0].analyzers[0]
    assert analyzer.findings == ()
    assert analyzer.issue_count == 0


def test_debug_run_keeps_the_full_analyzer_failure_text() -> None:
    def _explode(_context: AnalysisContext):
        raise RuntimeError("boom")

    result = checks_application.collect_run_checks_result(
        cast(ConfigDict, DEFAULT_CONFIG.copy() | {"debug": True}),
        ["state-inference"],
        use_cache=False,
        iter_loaded_projects_fn=cast(
            Any,
            lambda *_args, **_kwargs: iter(
                [("TargetA", SimpleNamespace(header=SimpleNamespace(name="TargetA")), AnalysisGraphStub())]
            ),
        ),
        get_enabled_analyzers_fn=lambda: [SimpleNamespace(key="state-inference", name="State inference", run=_explode)],
        target_is_library_fn=lambda *_args, **_kwargs: False,
        self_check_fn=lambda _cfg: True,
    )

    assert result.targets[0].analyzers[0].summary == "State inference failed: boom"


def test_run_record_keeps_the_target_load_duration() -> None:
    result = checks_application.collect_run_checks_result(
        cast(ConfigDict, DEFAULT_CONFIG.copy()),
        ["state-inference"],
        iter_loaded_projects_fn=cast(
            Any,
            lambda *_args, **_kwargs: iter(
                [("TargetA", named_object("TargetA"), AnalysisGraphStub(unavailable_libraries=set()))]
            ),
        ),
        get_enabled_analyzers_fn=lambda: [
            SimpleNamespace(
                key="state-inference",
                name="State inference",
                run=lambda _context: SimpleNamespace(summary=lambda: "summary"),
            )
        ],
        target_is_library_fn=lambda *_args, **_kwargs: False,
        self_check_fn=lambda _cfg: True,
    )

    record = checks_application.build_run_record(result, cast(ConfigDict, DEFAULT_CONFIG.copy()))

    load_duration_ms = record.targets[0].load_duration_ms
    assert load_duration_ms is not None
    assert load_duration_ms >= 0.0


def _order_probe_analyzers(delays: dict[str, float]) -> Callable[[], list[SimpleNamespace]]:
    def make(key: str) -> SimpleNamespace:
        def run(_context: object) -> SimpleNamespace:
            time.sleep(delays[key])
            return SimpleNamespace(issues=[], summary=lambda: f"{key} summary")

        return SimpleNamespace(key=key, name=key.title(), run=run)

    return lambda: [make(key) for key in delays]


def _run_order_probe(delays: dict[str, float], *, jobs: int | None) -> Any:
    return checks_application.collect_run_checks_result(
        cast(ConfigDict, DEFAULT_CONFIG.copy()),
        list(delays),
        use_cache=False,
        jobs=jobs,
        iter_loaded_projects_fn=cast(
            Any,
            lambda *_args, **_kwargs: iter(
                [("TargetA", SimpleNamespace(header=SimpleNamespace(name="TargetA")), AnalysisGraphStub())]
            ),
        ),
        get_enabled_analyzers_fn=_order_probe_analyzers(delays),
        target_is_library_fn=lambda *_args, **_kwargs: False,
        self_check_fn=lambda _cfg: True,
    )


def _analysis_lines(lines: Iterable[str]) -> list[str]:
    return [line for line in lines if "Running" not in line or "worker processes" not in line]


@pytest.mark.skipif(
    "fork" not in multiprocessing.get_all_start_methods(),
    reason="the worker pool needs the fork start method",
)
def test_parallel_run_keeps_the_sequential_output_order() -> None:
    delays = {"slow": 0.2, "medium": 0.1, "fast": 0.0}

    sequential = _run_order_probe(delays, jobs=1)
    parallel = _run_order_probe(delays, jobs=3)

    assert _analysis_lines(parallel.output_lines) == _analysis_lines(sequential.output_lines)
    assert [analyzer.key for analyzer in parallel.targets[0].analyzers] == ["slow", "medium", "fast"]
    assert [analyzer.key for analyzer in sequential.targets[0].analyzers] == ["slow", "medium", "fast"]


@pytest.mark.skipif(
    "fork" not in multiprocessing.get_all_start_methods(),
    reason="the worker pool needs the fork start method",
)
def test_parallel_run_announces_the_worker_count() -> None:
    result = _run_order_probe({"first": 0.0, "second": 0.0}, jobs=2)

    assert any("Running 2 analyzers across 2 worker processes" in line for line in result.output_lines)


def test_parallel_pool_is_skipped_when_the_platform_cannot_fork(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(checks_execution.analyzer_workers, "pooling_supported", lambda: False)

    result = _run_order_probe({"first": 0.0, "second": 0.0}, jobs=2)

    assert not any("worker processes" in line for line in result.output_lines)
    assert [analyzer.key for analyzer in result.targets[0].analyzers] == ["first", "second"]


def test_parallel_run_records_the_effective_worker_count_in_the_profile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(output_module, "emit_output", lambda _message: None)
    monkeypatch.setenv("SATTLINT_PROFILE", "1")
    monkeypatch.setattr(profiling_module, "profiling_log_path", lambda: tmp_path / "profile.jsonl")

    checks_application.run_checks(
        cast(ConfigDict, DEFAULT_CONFIG.copy()),
        ["first", "second"],
        jobs=2,
        iter_loaded_projects_fn=cast(
            Any,
            lambda *_args, **_kwargs: iter(
                [("TargetA", named_object("TargetA"), AnalysisGraphStub(unavailable_libraries=set()))]
            ),
        ),
        get_enabled_analyzers_fn=_order_probe_analyzers({"first": 0.0, "second": 0.0}),
        target_is_library_fn=lambda *_args, **_kwargs: False,
        pause_fn=None,
    )

    events = [json.loads(line) for line in (tmp_path / "profile.jsonl").read_text(encoding="utf-8").splitlines()]

    assert events[0]["payload"]["jobs"] == 2


def test_sequential_run_records_a_single_worker_in_the_profile(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(output_module, "emit_output", lambda _message: None)
    monkeypatch.setenv("SATTLINT_PROFILE", "1")
    monkeypatch.setattr(profiling_module, "profiling_log_path", lambda: tmp_path / "profile.jsonl")

    checks_application.run_checks(
        cast(ConfigDict, DEFAULT_CONFIG.copy()),
        ["first", "second"],
        jobs=1,
        iter_loaded_projects_fn=cast(
            Any,
            lambda *_args, **_kwargs: iter(
                [("TargetA", named_object("TargetA"), AnalysisGraphStub(unavailable_libraries=set()))]
            ),
        ),
        get_enabled_analyzers_fn=_order_probe_analyzers({"first": 0.0, "second": 0.0}),
        target_is_library_fn=lambda *_args, **_kwargs: False,
        pause_fn=None,
    )

    events = [json.loads(line) for line in (tmp_path / "profile.jsonl").read_text(encoding="utf-8").splitlines()]

    assert events[0]["payload"]["jobs"] == 1


@pytest.mark.skipif(
    "fork" not in multiprocessing.get_all_start_methods(),
    reason="the worker pool needs the fork start method",
)
def test_parallel_run_overlaps_analyzer_execution(tmp_path: Path) -> None:
    trace_path = tmp_path / "trace.jsonl"

    def analyzer(key: str) -> Callable[[], SimpleNamespace]:
        def make() -> SimpleNamespace:
            def run(_context: object) -> SimpleNamespace:
                started_at = time.time()
                time.sleep(0.3)
                trace_path.open("a", encoding="utf-8").write(
                    json.dumps({"key": key, "start": started_at, "end": time.time()}) + "\n"
                )
                return SimpleNamespace(issues=[], summary=lambda: f"{key} summary")

            return SimpleNamespace(key=key, name=key.title(), run=run)

        return make

    checks_application.collect_run_checks_result(
        cast(ConfigDict, DEFAULT_CONFIG.copy()),
        ["first", "second", "third"],
        use_cache=False,
        jobs=3,
        iter_loaded_projects_fn=cast(
            Any,
            lambda *_args, **_kwargs: iter(
                [("TargetA", SimpleNamespace(header=SimpleNamespace(name="TargetA")), AnalysisGraphStub())]
            ),
        ),
        get_enabled_analyzers_fn=lambda: [analyzer(key)() for key in ("first", "second", "third")],
        target_is_library_fn=lambda *_args, **_kwargs: False,
        self_check_fn=lambda _cfg: True,
    )

    spans = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines()]
    assert len(spans) == 3

    latest_start = max(span["start"] for span in spans)
    earliest_end = min(span["end"] for span in spans)
    assert latest_start < earliest_end, f"analyzer spans did not overlap: {spans}"
