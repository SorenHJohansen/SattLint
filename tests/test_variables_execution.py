# pyright: reportPrivateUsage=false
"""Focused coverage tests for _variables_execution helper branches."""

from __future__ import annotations

import logging
from collections.abc import Callable
from types import SimpleNamespace
from typing import Any, cast

import pytest

from sattline_parser.models.ast_model import BasePicture, ModuleTypeDef, Simple_DataType, SingleModule, Variable
from sattlint.analyzers import variables as variables_module
from sattlint.analyzers.variables import IssueKind
from sattlint.analyzers.variables import _variables_execution as variables_execution_module
from tests.helpers.variable_test_support import UsageStub as _UsageStub
from tests.helpers.variable_test_support import hdr as _hdr
from tests.helpers.variable_test_support import ns as _ns

variables_execution_impl: Any = variables_execution_module

_IssueTuple = tuple[IssueKind, tuple[str, ...], str, str, str | None]


def _noop(*_args: object, **_kwargs: object) -> None:
    return None


def _returns_false(*_args: object, **_kwargs: object) -> bool:
    return False


def _returns_true(*_args: object, **_kwargs: object) -> bool:
    return True


def _empty_effective_output_keys() -> set[tuple[str, ...]]:
    return set()


def _always_root_origin(_origin: object, _origin_lib: object | None = None) -> bool:
    return True


def _raise_should_not_run(*_args: object, **_kwargs: object) -> None:
    raise AssertionError("should not run")


def _append_issue(
    issues: list[_IssueTuple],
    kind: IssueKind,
    path: list[str],
    variable: Variable,
    role: str,
    field_path: str | None = None,
) -> None:
    issues.append((kind, tuple(path), variable.name, role, field_path))


def _append_phase_timing(
    phase_timings: list[dict[str, str | float]],
    phase: str,
    _started_at: float,
    ended_at: float | None = None,
    *,
    duration_ms: float,
) -> None:
    del ended_at
    phase_timings.append({"phase": phase, "duration_ms": duration_ms})


def _run_phase(helper: Any, phase: str, callback: Callable[[], object]) -> None:
    variables_execution_impl._run_timed_phase(helper, phase, callback)


def test_variables_execution_collect_basepicture_issues_covers_procedure_status_branch() -> None:
    procedure_var = Variable(name="ProcedureVar", datatype=Simple_DataType.INTEGER)
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[procedure_var],
        submodules=[],
        modulecode=None,
        moduledef=None,
    )
    issues: list[tuple[IssueKind, tuple[str, ...], str, str, str | None]] = []

    def _get_usage(variable: Variable) -> _UsageStub:
        return _UsageStub(read=True) if variable is procedure_var else _UsageStub()

    def _procedure_status_issue(
        variable: Variable,
        _usage: object,
    ) -> tuple[str, str | None] | None:
        if variable is procedure_var:
            return ("procedure-status", "Status")
        return None

    def _add_issue(
        kind: IssueKind,
        path: list[str],
        variable: Variable,
        role: str,
        field_path: str | None = None,
    ) -> None:
        _append_issue(issues, kind, path, variable, role, field_path)

    helper: Any = _ns(
        bp=bp,
        _get_usage=_get_usage,
        _procedure_status_issue=_procedure_status_issue,
        _add_issue=_add_issue,
        _has_output_effect=_returns_false,
        _has_procedure_status_binding=_returns_false,
        _is_const_candidate=_returns_true,
        _collect_issues_from_module=_noop,
    )

    variables_execution_impl._collect_basepicture_issues(helper, ["Root"])

    assert issues == [(IssueKind.PROCEDURE_STATUS, ("Root",), "ProcedureVar", "procedure-status", "Status")]


def test_variables_execution_collect_basepicture_issues_covers_write_without_effect_branch() -> None:
    effect_var = Variable(name="EffectVar", datatype=Simple_DataType.INTEGER)
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[effect_var],
        submodules=[],
        modulecode=None,
        moduledef=None,
    )
    issues: list[tuple[IssueKind, tuple[str, ...], str, str, str | None]] = []

    def _get_usage(variable: Variable) -> _UsageStub:
        return _UsageStub(read=True, written=True) if variable is effect_var else _UsageStub()

    def _add_issue(
        kind: IssueKind,
        path: list[str],
        variable: Variable,
        role: str,
        field_path: str | None = None,
    ) -> None:
        _append_issue(issues, kind, path, variable, role, field_path)

    helper: Any = _ns(
        bp=bp,
        _get_usage=_get_usage,
        _procedure_status_issue=_noop,
        _add_issue=_add_issue,
        _has_output_effect=_returns_false,
        _has_procedure_status_binding=_returns_false,
        _is_const_candidate=_returns_true,
        _collect_issues_from_module=_noop,
    )

    variables_execution_impl._collect_basepicture_issues(helper, ["Root"])

    assert issues == [(IssueKind.WRITE_WITHOUT_EFFECT, ("Root",), "EffectVar", "localvariable", None)]


def test_variables_execution_collect_typedef_issues_covers_moduleparameter_procedure_status_branch() -> None:
    procedure_param = Variable(name="ProcedureParam", datatype=Simple_DataType.INTEGER)
    moduletype = ModuleTypeDef(
        name="WorkerType",
        moduleparameters=[procedure_param],
        localvariables=[],
        submodules=[],
        moduledef=None,
        modulecode=None,
        parametermappings=[],
    )
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[moduletype],
        localvariables=[],
        submodules=[],
        modulecode=None,
        moduledef=None,
    )
    issues: list[tuple[IssueKind, tuple[str, ...], str, str, str | None]] = []

    def _get_usage(variable: Variable) -> _UsageStub:
        return _UsageStub(read=True) if variable is procedure_param else _UsageStub()

    def _procedure_status_issue(
        variable: Variable,
        _usage: object,
    ) -> tuple[str, str | None] | None:
        if variable is procedure_param:
            return ("procedure-status", "Status")
        return None

    def _add_issue(
        kind: IssueKind,
        path: list[str],
        variable: Variable,
        role: str,
        field_path: str | None = None,
    ) -> None:
        _append_issue(issues, kind, path, variable, role, field_path)

    helper: Any = _ns(
        bp=bp,
        _limit_to_module_path=None,
        _update_status=_noop,
        _analyze_typedef=_noop,
        _compute_effective_output_keys=_empty_effective_output_keys,
        _is_from_root_origin=_always_root_origin,
        _get_usage=_get_usage,
        _procedure_status_issue=_procedure_status_issue,
        _add_issue=_add_issue,
        _has_output_effect=_returns_false,
        _has_procedure_status_binding=_returns_false,
        _is_const_candidate=_returns_true,
        _collect_issues_from_module=_noop,
    )

    variables_execution_impl._collect_typedef_issues(helper)

    assert issues == [
        (
            IssueKind.PROCEDURE_STATUS,
            ("Root", "TypeDef:WorkerType"),
            "ProcedureParam",
            "procedure-status",
            "Status",
        )
    ]


def test_variables_execution_collect_typedef_issues_returns_early_for_scoped_runs() -> None:
    helper: Any = _ns(
        _limit_to_module_path=["Root", "Scoped"],
        bp=_ns(moduletype_defs=[object()]),
        _analyze_typedef=_raise_should_not_run,
    )

    assert variables_execution_impl._collect_typedef_issues(helper) is None


def test_variables_execution_dependency_and_typedef_early_returns_cover_remaining_paths() -> None:
    dependency_helper: Any = _ns(
        _limit_to_module_path=["Root", "Scoped"],
        analyzed_target_is_library=True,
        include_dependency_moduletype_usage=True,
        bp=_ns(moduletype_defs=[object()]),
        _analyze_typedef=_raise_should_not_run,
    )

    assert variables_execution_impl._analyze_library_dependency_typedef_usage(dependency_helper) is None

    no_issue_helper: Any = _ns(
        _limit_to_module_path=None,
        _selected_issue_kinds=frozenset(),
        bp=_ns(moduletype_defs=[object()]),
        _analyze_typedef=_raise_should_not_run,
    )

    assert variables_execution_impl._collect_typedef_issues(no_issue_helper) is None

    moduletype = ModuleTypeDef(
        name="WorkerType",
        moduleparameters=[Variable(name="Param", datatype=Simple_DataType.INTEGER)],
        localvariables=[],
        submodules=[SingleModule.__new__(SingleModule)],
        moduledef=None,
        modulecode=None,
        parametermappings=[],
    )
    analyze_calls: list[str] = []
    collected_modules: list[object] = []

    def _analyze_typedef(_current: object, path: list[str]) -> None:
        analyze_calls.append(path[-1])

    def _collect_issues_from_module(module: object, **_kwargs: object) -> None:
        collected_modules.append(module)

    name_collision_only_helper: Any = _ns(
        _limit_to_module_path=None,
        _selected_issue_kinds=frozenset({IssueKind.NAME_COLLISION}),
        bp=BasePicture(
            header=_hdr("Root"),
            datatype_defs=[],
            moduletype_defs=[moduletype],
            localvariables=[],
            submodules=[],
            modulecode=None,
            moduledef=None,
        ),
        _update_status=_noop,
        _analyze_typedef=_analyze_typedef,
        _compute_effective_output_keys=_empty_effective_output_keys,
        _is_from_root_origin=_always_root_origin,
        _collect_issues_from_module=_collect_issues_from_module,
    )

    assert variables_execution_impl._collect_typedef_issues(name_collision_only_helper) is None
    assert analyze_calls == ["TypeDef:WorkerType"]
    assert collected_modules == []


def test_variables_execution_run_records_phase_timings() -> None:
    phase_timings: list[dict[str, str | float]] = []

    helper: Any = _ns(
        _issues=[],
        _param_mapping_issue_indexes={},
        context_builder=_ns(issues=[]),
        _limit_to_module_path=None,
        _phase_timings=phase_timings,
        _alias_links=[],
        _analysis_warnings=[],
        bp=_ns(header=_ns(name="Root"), localvariables=[], submodules=[], moduletype_defs=[]),
        debug=False,
        _trace=_noop,
        _update_status=_noop,
        _analyze_root_scope=_noop,
        _analyze_library_dependency_typedef_usage=_noop,
        _apply_alias_back_propagation=_noop,
        _propagate_procedure_status_bindings=_noop,
        _run_post_traversal_analyses=_noop,
        _collect_basepicture_issues=_noop,
        _collect_typedef_issues=_noop,
        _add_naming_role_mismatch_issues=_noop,
        _add_global_scope_minimization_issues=_noop,
        _add_hidden_global_coupling_issues=_noop,
        _add_high_fan_in_out_issues=_noop,
        _add_unused_datatype_field_issues=_noop,
    )

    def _record_phase_timing(phase: str, started_at: float, ended_at: float | None = None) -> None:
        _append_phase_timing(phase_timings, phase, started_at, ended_at, duration_ms=0.0)

    def _run_timed_phase(phase: str, callback: Callable[[], object]) -> None:
        _run_phase(helper, phase, callback)

    helper._record_phase_timing = _record_phase_timing
    helper._run_timed_phase = _run_timed_phase

    variables_execution_module.run(helper)

    assert [phase["phase"] for phase in helper._phase_timings] == [
        "root-traversal",
        "display-binding-scan",
        "dependency-typedef-usage",
        "alias-propagation",
        "post-traversal-checks",
        "base-picture-issue-scan",
        "typedef-scan",
        "final-issue-synthesis",
        "datatype-field-scan",
    ]


def test_variables_execution_run_skips_irrelevant_phases_for_unused_only() -> None:
    phase_timings: list[dict[str, str | float]] = []

    helper: Any = _ns(
        _issues=[],
        _param_mapping_issue_indexes={},
        context_builder=_ns(issues=[]),
        _limit_to_module_path=None,
        _phase_timings=phase_timings,
        _alias_links=[],
        _analysis_warnings=[],
        _selected_issue_kinds=frozenset({IssueKind.UNUSED}),
        _analyzed_target_is_library=False,
        _include_dependency_moduletype_usage=False,
        bp=_ns(header=_ns(name="Root"), localvariables=[], submodules=[], moduletype_defs=[]),
        debug=False,
        _trace=_noop,
        _update_status=_noop,
        _analyze_root_scope=_noop,
        _analyze_library_dependency_typedef_usage=_noop,
        _apply_alias_back_propagation=_noop,
        _propagate_procedure_status_bindings=_noop,
        _run_post_traversal_analyses=_noop,
        _collect_basepicture_issues=_noop,
        _collect_typedef_issues=_noop,
        _add_naming_role_mismatch_issues=_noop,
        _add_global_scope_minimization_issues=_noop,
        _add_hidden_global_coupling_issues=_noop,
        _add_high_fan_in_out_issues=_noop,
        _add_unused_datatype_field_issues=_noop,
    )

    def _record_phase_timing(phase: str, started_at: float, ended_at: float | None = None) -> None:
        _append_phase_timing(phase_timings, phase, started_at, ended_at, duration_ms=0.0)

    def _run_timed_phase(phase: str, callback: Callable[[], object]) -> None:
        _run_phase(helper, phase, callback)

    helper._record_phase_timing = _record_phase_timing
    helper._run_timed_phase = _run_timed_phase

    variables_execution_module.run(helper)

    assert [phase["phase"] for phase in helper._phase_timings] == [
        "root-traversal",
        "display-binding-scan",
        "alias-propagation",
        "base-picture-issue-scan",
        "typedef-scan",
    ]


def test_analyze_variables_includes_phase_timings_from_analyzer(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FakeAnalyzer:
        def __init__(self, *args: object, **kwargs: object) -> None:
            self.selected_issue_kinds = kwargs.get("selected_issue_kinds")
            self.phase_timings = [{"phase": "root-traversal", "duration_ms": 12.5}]
            self.access_graph = SimpleNamespace(by_path_key={})
            self.effect_flow_edges = {}
            self.effect_flow_display_names = {}

        def run(self) -> list[object]:
            return []

    monkeypatch.setattr(variables_module, "VariablesAnalyzer", _FakeAnalyzer)
    perf_counter_values = iter([1.0, 1.025])
    monkeypatch.setattr(variables_module.time, "perf_counter", lambda: next(perf_counter_values))
    base_picture = cast(BasePicture, SimpleNamespace(header=SimpleNamespace(name="Root")))

    report = variables_module.analyze_variables(
        base_picture,
        selected_issue_kinds={IssueKind.UNUSED},
    )

    assert report.phase_timings == [
        {"phase": "analyzer-init", "duration_ms": 25.0},
        {"phase": "root-traversal", "duration_ms": 12.5},
    ]
    assert report.selected_issue_kinds == frozenset({IssueKind.UNUSED})
    assert report.visible_kinds == frozenset({IssueKind.UNUSED})


def test_analyze_variables_includes_access_and_effect_artifacts_from_analyzer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    usage_event = object()

    class _FakeAnalyzer:
        def __init__(self, *args: object, **kwargs: object) -> None:
            self.phase_timings = []
            self.access_graph = SimpleNamespace(by_path_key={("root", "out"): [usage_event]})
            self.effect_flow_edges = {("root", "out"): (("root", "sink"),)}
            self.effect_flow_display_names = {("root", "out"): "Root.Out"}

        def run(self) -> list[object]:
            return []

    monkeypatch.setattr(variables_module, "VariablesAnalyzer", _FakeAnalyzer)
    perf_counter_values = iter([1.0, 1.0])
    monkeypatch.setattr(variables_module.time, "perf_counter", lambda: next(perf_counter_values))
    base_picture = cast(BasePicture, SimpleNamespace(header=SimpleNamespace(name="Root")))

    report = variables_module.analyze_variables(base_picture)

    assert report.accesses_by_definition_key == {("root", "out"): (usage_event,)}
    assert report.effect_flow_edges == {("root", "out"): (("root", "sink"),)}
    assert report.effect_flow_display_names == {("root", "out"): "Root.Out"}


def test_variables_execution_run_debug_logs_phase_counts_and_aggregated_unresolved_lookups(
    caplog: pytest.LogCaptureFixture,
) -> None:
    phase_timings: list[dict[str, str | float]] = []

    helper: Any = _ns(
        _issues=[],
        _param_mapping_issue_indexes={},
        context_builder=_ns(issues=[]),
        _limit_to_module_path=None,
        _phase_timings=phase_timings,
        _alias_links=[],
        _analysis_warnings=[],
        _selected_issue_kinds=frozenset({IssueKind.UNUSED}),
        _analyzed_target_is_library=False,
        _include_dependency_moduletype_usage=False,
        bp=_ns(header=_ns(name="Root"), localvariables=[], submodules=[], moduletype_defs=[]),
        debug=True,
        _trace=_noop,
        _update_status=_noop,
        _analyze_library_dependency_typedef_usage=_noop,
        _apply_alias_back_propagation=_noop,
        _propagate_procedure_status_bindings=_noop,
        _run_post_traversal_analyses=_noop,
        _collect_typedef_issues=_noop,
        _add_naming_role_mismatch_issues=_noop,
        _add_global_scope_minimization_issues=_noop,
        _add_hidden_global_coupling_issues=_noop,
        _add_high_fan_in_out_issues=_noop,
        _add_unused_datatype_field_issues=_noop,
    )

    def _record_phase_timing(phase: str, started_at: float, ended_at: float | None = None) -> None:
        _append_phase_timing(phase_timings, phase, started_at, ended_at, duration_ms=1.0)

    def _run_timed_phase(phase: str, callback: Callable[[], object]) -> None:
        _run_phase(helper, phase, callback)

    helper._record_phase_timing = _record_phase_timing
    helper._run_timed_phase = _run_timed_phase

    def _analyze_root_scope() -> None:
        helper._unresolved_variable_lookup_counts.update({"ToggleWindow": 12, "Bool_Value": 4})
        helper._unresolved_variable_lookup_examples.update(
            {
                "ToggleWindow": (80, "BasePicture -> TypeDef:Example"),
                "Bool_Value": (14, "BasePicture -> TypeDef:Example -> Info"),
            }
        )
        helper._unresolved_variable_lookup_total = 16

    def _collect_basepicture_issues(_path: list[str]) -> None:
        helper._issues.extend([_ns(kind=IssueKind.UNUSED), _ns(kind=IssueKind.UNUSED)])

    helper._analyze_root_scope = _analyze_root_scope
    helper._collect_basepicture_issues = _collect_basepicture_issues

    with caplog.at_level(logging.DEBUG, logger="SattLint"):
        variables_execution_module.run(helper)

    assert "Variables analysis start: Root locals=0 submodules=0 typedefs=0 selected=unused" in caplog.messages
    assert "Variables selected issue kinds: unused" in caplog.messages
    assert "Variables issue counts: unused=2" in caplog.messages
    assert any(message.startswith("Variables phase timings (ms): root-traversal=1.000") for message in caplog.messages)
    assert "Variables unresolved lookups: suppressed 16 ignored UI token hit(s)" in caplog.messages
    assert not any(message.startswith("  unresolved ") for message in caplog.messages)
    assert not any("Variable not found in scope:" in message for message in caplog.messages)
