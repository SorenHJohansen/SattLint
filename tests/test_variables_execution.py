"""Focused coverage tests for _variables_execution helper branches."""

# pyright: reportPrivateUsage=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportUnknownMemberType=false

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from sattline_parser.models.ast_model import BasePicture, ModuleTypeDef, Simple_DataType, Variable
from sattlint.analyzers import _variables_execution as variables_execution_module
from sattlint.analyzers import variables as variables_module
from sattlint.analyzers.variables import IssueKind
from tests.helpers.variable_test_support import UsageStub as _UsageStub
from tests.helpers.variable_test_support import hdr as _hdr


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
    helper: Any = SimpleNamespace(
        bp=bp,
        _get_usage=lambda variable: _UsageStub(read=True) if variable is procedure_var else _UsageStub(),
        _procedure_status_issue=lambda variable, usage: (
            ("procedure-status", "Status") if variable is procedure_var else None
        ),
        _add_issue=lambda kind, path, variable, role, field_path=None: issues.append(
            (kind, tuple(path), variable.name, role, field_path)
        ),
        _has_output_effect=lambda *args, **kwargs: False,
        _has_procedure_status_binding=lambda *args, **kwargs: False,
        _is_const_candidate=lambda *args, **kwargs: True,
        _collect_issues_from_module=lambda *args, **kwargs: None,
    )

    variables_execution_module._collect_basepicture_issues(helper, ["Root"])

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
    helper: Any = SimpleNamespace(
        bp=bp,
        _get_usage=lambda variable: _UsageStub(read=True, written=True) if variable is effect_var else _UsageStub(),
        _procedure_status_issue=lambda variable, usage: None,
        _add_issue=lambda kind, path, variable, role, field_path=None: issues.append(
            (kind, tuple(path), variable.name, role, field_path)
        ),
        _has_output_effect=lambda *args, **kwargs: False,
        _has_procedure_status_binding=lambda *args, **kwargs: False,
        _is_const_candidate=lambda *args, **kwargs: True,
        _collect_issues_from_module=lambda *args, **kwargs: None,
    )

    variables_execution_module._collect_basepicture_issues(helper, ["Root"])

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
    helper: Any = SimpleNamespace(
        bp=bp,
        _limit_to_module_path=None,
        _update_status=lambda *args, **kwargs: None,
        _analyze_typedef=lambda *args, **kwargs: None,
        _compute_effective_output_keys=lambda: set(),
        _is_from_root_origin=lambda origin, origin_lib=None: True,
        _get_usage=lambda variable: _UsageStub(read=True) if variable is procedure_param else _UsageStub(),
        _procedure_status_issue=lambda variable, usage: (
            ("procedure-status", "Status") if variable is procedure_param else None
        ),
        _add_issue=lambda kind, path, variable, role, field_path=None: issues.append(
            (kind, tuple(path), variable.name, role, field_path)
        ),
        _has_output_effect=lambda *args, **kwargs: False,
        _has_procedure_status_binding=lambda *args, **kwargs: False,
        _is_const_candidate=lambda *args, **kwargs: True,
        _collect_issues_from_module=lambda *args, **kwargs: None,
    )

    variables_execution_module._collect_typedef_issues(helper)

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
    helper: Any = SimpleNamespace(
        _limit_to_module_path=["Root", "Scoped"],
        bp=SimpleNamespace(moduletype_defs=[object()]),
        _analyze_typedef=lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("should not run")),
    )

    assert variables_execution_module._collect_typedef_issues(helper) is None


def test_variables_execution_dependency_and_typedef_early_returns_cover_remaining_paths() -> None:
    dependency_helper: Any = SimpleNamespace(
        _limit_to_module_path=["Root", "Scoped"],
        analyzed_target_is_library=True,
        include_dependency_moduletype_usage=True,
        bp=SimpleNamespace(moduletype_defs=[object()]),
        _analyze_typedef=lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("should not run")),
    )

    assert variables_execution_module._analyze_library_dependency_typedef_usage(dependency_helper) is None

    no_issue_helper: Any = SimpleNamespace(
        _limit_to_module_path=None,
        _selected_issue_kinds=frozenset(),
        bp=SimpleNamespace(moduletype_defs=[object()]),
        _analyze_typedef=lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("should not run")),
    )

    assert variables_execution_module._collect_typedef_issues(no_issue_helper) is None

    moduletype = ModuleTypeDef(
        name="WorkerType",
        moduleparameters=[Variable(name="Param", datatype=Simple_DataType.INTEGER)],
        localvariables=[],
        submodules=[object()],
        moduledef=None,
        modulecode=None,
        parametermappings=[],
    )
    analyze_calls: list[str] = []
    collected_modules: list[object] = []
    name_collision_only_helper: Any = SimpleNamespace(
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
        _update_status=lambda *args, **kwargs: None,
        _analyze_typedef=lambda current, path: analyze_calls.append(path[-1]),
        _compute_effective_output_keys=lambda: set(),
        _is_from_root_origin=lambda origin, origin_lib=None: True,
        _collect_issues_from_module=lambda module, **kwargs: collected_modules.append(module),
    )

    assert variables_execution_module._collect_typedef_issues(name_collision_only_helper) is None
    assert analyze_calls == ["TypeDef:WorkerType"]
    assert collected_modules == []


def test_variables_execution_run_records_phase_timings() -> None:
    helper: Any = SimpleNamespace(
        _issues=[],
        _param_mapping_issue_indexes={},
        context_builder=SimpleNamespace(issues=[]),
        _limit_to_module_path=None,
        _phase_timings=[],
        _alias_links=[],
        _analysis_warnings=[],
        bp=SimpleNamespace(header=SimpleNamespace(name="Root"), localvariables=[], submodules=[], moduletype_defs=[]),
        debug=False,
        _trace=lambda *args, **kwargs: None,
        _update_status=lambda *args, **kwargs: None,
        _record_phase_timing=lambda phase, started_at, ended_at=None: helper._phase_timings.append(
            {"phase": phase, "duration_ms": 0.0}
        ),
        _run_timed_phase=lambda phase, callback: variables_execution_module._run_timed_phase(helper, phase, callback),
        _analyze_root_scope=lambda: None,
        _analyze_library_dependency_typedef_usage=lambda: None,
        _apply_alias_back_propagation=lambda: None,
        _propagate_procedure_status_bindings=lambda: None,
        _run_post_traversal_analyses=lambda: None,
        _collect_basepicture_issues=lambda _path: None,
        _collect_typedef_issues=lambda: None,
        _add_naming_role_mismatch_issues=lambda: None,
        _add_global_scope_minimization_issues=lambda: None,
        _add_hidden_global_coupling_issues=lambda: None,
        _add_high_fan_in_out_issues=lambda: None,
        _add_unused_datatype_field_issues=lambda: None,
    )

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
    helper: Any = SimpleNamespace(
        _issues=[],
        _param_mapping_issue_indexes={},
        context_builder=SimpleNamespace(issues=[]),
        _limit_to_module_path=None,
        _phase_timings=[],
        _alias_links=[],
        _analysis_warnings=[],
        _selected_issue_kinds=frozenset({IssueKind.UNUSED}),
        _analyzed_target_is_library=False,
        _include_dependency_moduletype_usage=False,
        bp=SimpleNamespace(header=SimpleNamespace(name="Root"), localvariables=[], submodules=[], moduletype_defs=[]),
        debug=False,
        _trace=lambda *args, **kwargs: None,
        _update_status=lambda *args, **kwargs: None,
        _record_phase_timing=lambda phase, started_at, ended_at=None: helper._phase_timings.append(
            {"phase": phase, "duration_ms": 0.0}
        ),
        _run_timed_phase=lambda phase, callback: variables_execution_module._run_timed_phase(helper, phase, callback),
        _analyze_root_scope=lambda: None,
        _analyze_library_dependency_typedef_usage=lambda: None,
        _apply_alias_back_propagation=lambda: None,
        _propagate_procedure_status_bindings=lambda: None,
        _run_post_traversal_analyses=lambda: None,
        _collect_basepicture_issues=lambda _path: None,
        _collect_typedef_issues=lambda: None,
        _add_naming_role_mismatch_issues=lambda: None,
        _add_global_scope_minimization_issues=lambda: None,
        _add_hidden_global_coupling_issues=lambda: None,
        _add_high_fan_in_out_issues=lambda: None,
        _add_unused_datatype_field_issues=lambda: None,
    )

    variables_execution_module.run(helper)

    assert [phase["phase"] for phase in helper._phase_timings] == [
        "root-traversal",
        "display-binding-scan",
        "alias-propagation",
        "base-picture-issue-scan",
        "typedef-scan",
    ]


def test_analyze_variables_includes_phase_timings_from_analyzer(monkeypatch) -> None:
    class _FakeAnalyzer:
        def __init__(self, *args: object, **kwargs: object) -> None:
            self.selected_issue_kinds = kwargs.get("selected_issue_kinds")
            self.phase_timings = [{"phase": "root-traversal", "duration_ms": 12.5}]

        def run(self) -> list[object]:
            return []

    monkeypatch.setattr(variables_module, "VariablesAnalyzer", _FakeAnalyzer)
    perf_counter_values = iter([1.0, 1.025])
    monkeypatch.setattr(variables_module.time, "perf_counter", lambda: next(perf_counter_values))

    report = variables_module.analyze_variables(
        SimpleNamespace(header=SimpleNamespace(name="Root")),
        selected_issue_kinds={IssueKind.UNUSED},
    )

    assert report.phase_timings == [
        {"phase": "analyzer-init", "duration_ms": 25.0},
        {"phase": "root-traversal", "duration_ms": 12.5},
    ]
    assert report.visible_kinds == frozenset({IssueKind.UNUSED})
