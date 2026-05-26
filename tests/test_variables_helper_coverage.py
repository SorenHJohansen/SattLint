# pyright: reportPrivateUsage=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportUnknownMemberType=false

from __future__ import annotations

from collections import defaultdict
from types import SimpleNamespace
from typing import Any, cast

import pytest

from sattline_parser.models.ast_model import (
    Simple_DataType,
    Variable,
)
from sattlint.analyzers import _variables_access as variables_access_module
from sattlint.analyzers import _variables_execution as variables_execution_module
from sattlint.analyzers import _variables_status as variables_status_module
from sattlint.analyzers import variable_issue_collection as variable_issue_collection_module
from sattlint.analyzers import variables as variables_module
from sattlint.analyzers.variables import IssueKind, VariableIssue, VariablesAnalyzer
from sattlint.reporting.variables_report import VariablesReport
from tests.helpers.variable_test_support import UsageStub as _UsageStub
from tests.helpers.variable_test_support import ns as _ns


def test_variables_status_cover_pattern_and_binding_branches(monkeypatch: pytest.MonkeyPatch) -> None:
    assert variables_status_module._normalize_role_pattern_values("bad") == ()
    assert variables_status_module._normalize_role_pattern_values([" Cmd ", "cmd", 1, ""]) == ("cmd",)
    defaults = variables_status_module._configured_naming_role_patterns(None)
    assert defaults["status"].suffixes == ("status",)
    assert variables_status_module._configured_naming_role_patterns({"analysis": "bad"}) == defaults
    assert variables_status_module._configured_naming_role_patterns({"analysis": {}}) == defaults
    assert variables_status_module._configured_naming_role_patterns({"analysis": {"naming": {}}}) == defaults
    configured = variables_status_module._configured_naming_role_patterns(
        {"analysis": {"naming": {"role_patterns": {"command": {"prefixes": ["Start", "start"]}}}}}
    )
    assert "start" in configured["command"].prefixes

    variable = Variable(name="StatusVar", datatype=Simple_DataType.INTEGER)
    helper: Any = SimpleNamespace(
        procedure_status_bindings=defaultdict(list),
        ignorable_output_variable_ids=set(),
    )
    none_context: Any = _ns(resolve_variable=lambda *_: (None, None, [], None))
    variables_status_module._bind_procedure_status(
        helper,
        "StatusVar",
        call_name="Fn",
        parameter=_ns(name="Out", channel_kind=None),
        context=none_context,
    )
    variables_status_module._bind_ignorable_output(helper, "StatusVar", context=none_context)
    assert helper.procedure_status_bindings == {}
    assert helper.ignorable_output_variable_ids == set()

    good_context: Any = _ns(resolve_variable=lambda *_: (variable, "Field", ["Root"], None))
    variables_status_module._bind_procedure_status(
        helper,
        "StatusVar",
        call_name="Fn",
        parameter=_ns(name="Out", channel_kind=None),
        context=good_context,
    )
    variables_status_module._bind_procedure_status(
        helper,
        "StatusVar",
        call_name="Fn",
        parameter=_ns(name="Out", channel_kind=None),
        context=good_context,
    )
    variables_status_module._bind_ignorable_output(helper, "StatusVar", context=good_context)
    assert len(helper.procedure_status_bindings[id(variable)]) == 1
    assert id(variable) in helper.ignorable_output_variable_ids

    signature = _ns(
        parameters=[
            _ns(is_status_channel=True, name="StatusOut", channel_kind="status", direction="out"),
            _ns(is_status_channel=False, name="Ignored", channel_kind=None, direction="in"),
            _ns(is_status_channel=False, name="FoundRec", channel_kind=None, direction="out"),
        ]
    )
    status_calls: list[str] = []
    ignorable_calls: list[str] = []
    recorder: Any = SimpleNamespace(
        bind_procedure_status=lambda full_ref, **kwargs: status_calls.append(full_ref),
        bind_ignorable_output=lambda full_ref, **kwargs: ignorable_calls.append(full_ref),
    )
    monkeypatch.setattr(variables_status_module, "resolve_call_signature", lambda fn_name: None)
    variables_status_module._record_procedure_status_bindings(recorder, "Fn", [], good_context)
    variables_status_module._record_procedure_status_bindings(recorder, "Fn", [{"var_name": 5}], good_context)
    variables_status_module._record_ignorable_output_bindings(recorder, "SearchRecComponent", [], good_context)
    monkeypatch.setattr(variables_status_module, "resolve_call_signature", lambda fn_name: signature)
    variables_status_module._record_procedure_status_bindings(
        recorder,
        "Fn",
        [{"var_name": 5}],
        good_context,
    )
    variables_status_module._record_procedure_status_bindings(
        recorder,
        "Fn",
        [{}, {"var_name": 5}, {"var_name": "Ignored"}],
        good_context,
    )
    variables_status_module._record_procedure_status_bindings(
        recorder,
        "Fn",
        [{"var_name": "StatusVar"}],
        good_context,
    )
    variables_status_module._record_ignorable_output_bindings(
        recorder,
        "SearchRecComponent",
        [],
        good_context,
    )
    variables_status_module._record_ignorable_output_bindings(
        recorder,
        "SearchRecComponent",
        [{}, {}, {}],
        good_context,
    )
    variables_status_module._record_ignorable_output_bindings(
        recorder,
        "SearchRecComponent",
        [{}, {}, {"var_name": 7}],
        good_context,
    )
    variables_status_module._record_ignorable_output_bindings(
        recorder,
        "SearchRecComponent",
        [{"var_name": 7}, {"var_name": "Ignored"}, {"var_name": "StatusVar"}],
        good_context,
    )
    assert status_calls == ["StatusVar"]
    assert ignorable_calls == ["StatusVar"]


def test_variables_status_propagation_and_variables_helpers(monkeypatch: pytest.MonkeyPatch) -> None:
    source = Variable(name="Source", datatype=Simple_DataType.INTEGER)
    target = Variable(name="Target", datatype=Simple_DataType.INTEGER)
    binding = variables_status_module.ProcedureStatusBinding(
        call_name="Fn",
        parameter_name="Out",
        channel_kind="status",
        field_path="Leaf",
    )
    root_binding = variables_status_module.ProcedureStatusBinding(
        call_name="Fn",
        parameter_name="Out",
        channel_kind="status",
        field_path=None,
    )
    helper: Any = SimpleNamespace(
        alias_links=[(source, target, "Mapped")],
        procedure_status_bindings=defaultdict(list, {id(target): [binding, root_binding], id(source): []}),
    )
    variables_status_module._propagate_procedure_status_bindings(helper)
    variables_status_module._propagate_procedure_status_bindings(helper)
    assert helper.procedure_status_bindings[id(source)] == [
        variables_status_module.ProcedureStatusBinding(
            call_name="Fn",
            parameter_name="Out",
            channel_kind="status",
            field_path="Mapped.Leaf",
        ),
        variables_status_module.ProcedureStatusBinding(
            call_name="Fn",
            parameter_name="Out",
            channel_kind="status",
            field_path="Mapped",
        ),
    ]

    assert (
        variables_status_module._has_procedure_status_binding(
            _ns(procedure_status_bindings={id(source): [binding]}),
            source,
        )
        is True
    )
    assert (
        variables_status_module._has_ignorable_output_binding(
            _ns(ignorable_output_variable_ids={id(source)}),
            source,
        )
        is True
    )
    status_issue = variables_status_module._procedure_status_issue(
        _ns(procedure_status_bindings={id(source): [binding]}),
        source,
        cast(Any, _UsageStub(written=True, ui_read=True)),
    )
    assert status_issue is not None
    status_role, field_path = status_issue
    assert status_role.startswith("procedure status output")
    assert field_path == "Leaf"

    report = VariablesReport(
        basepicture_name="Root",
        issues=[VariableIssue(kind=IssueKind.UNUSED, module_path=["Root"], variable=source, role="unused")],
        visible_kinds=frozenset({IssueKind.UNUSED}),
        include_empty_sections=True,
    )
    assert variables_module.filter_variable_report(report, set()) is report
    filtered = variables_module.filter_variable_report(report, {IssueKind.UI_ONLY})
    assert filtered.issues == []
    assert filtered.visible_kinds == frozenset({IssueKind.UI_ONLY})

    warning_log: list[str] = []
    traces: list[tuple[str, dict[str, str]]] = []
    analyzer = VariablesAnalyzer.__new__(VariablesAnalyzer)
    analyzer._analysis_warnings = []
    analyzer.debug = True
    analyzer._trace = lambda action, **kwargs: traces.append((action, kwargs))
    monkeypatch.setattr(variables_module.log, "warning", warning_log.append)
    analyzer._warn("demo warning")
    assert analyzer.analysis_warnings == ["demo warning"]
    assert warning_log == ["demo warning"]
    assert traces == [("warning", {"message": "demo warning"})]


def test_variable_issue_collection_and_variables_cover_remaining_branches(monkeypatch: pytest.MonkeyPatch) -> None:
    proc_var = Variable(name="Proc", datatype=Simple_DataType.INTEGER)
    ui_var = Variable(name="Display", datatype=Simple_DataType.INTEGER)
    effect_var = Variable(name="Effect", datatype=Simple_DataType.INTEGER)
    issues: list[tuple[IssueKind, str, str | None]] = []
    helper: Any = SimpleNamespace(
        bp=SimpleNamespace(),
        unavailable_libraries=set(),
        analyzed_target_is_library=False,
        limit_to_module_path=["Root"],
        is_from_root_origin=lambda *_: True,
        get_usage=lambda variable: {
            id(proc_var): _UsageStub(read=True, written=True),
            id(ui_var): _UsageStub(is_display_only=True),
            id(effect_var): _UsageStub(read=True, written=True),
        }[id(variable)],
        procedure_status_issue=lambda variable, usage: ("status-role", "Field") if variable is proc_var else None,
        has_output_effect=lambda *args, **kwargs: False,
        has_procedure_status_binding=lambda *args, **kwargs: False,
        append_issue=lambda issue: issues.append((issue.kind, issue.role, issue.field_path)),
    )
    monkeypatch.setattr(
        variable_issue_collection_module,
        "resolve_moduletype_def_strict",
        lambda *args, **kwargs: _ns(
            moduleparameters=[proc_var, ui_var, effect_var],
            localvariables=[],
            submodules=[],
            origin_file="Root.s",
            origin_lib=None,
        ),
    )
    mod: Any = _ns(header=_ns(name="Worker"), moduletype_name="WorkerType")
    variable_issue_collection_module._collect_issues_from_module(helper, mod, ["Root"])
    assert issues == [
        (IssueKind.PROCEDURE_STATUS, "status-role", "Field"),
        (IssueKind.UI_ONLY, "moduleparameter", None),
        (IssueKind.WRITE_WITHOUT_EFFECT, "moduleparameter", None),
    ]

    report = VariablesReport(
        basepicture_name="Root",
        issues=[
            VariableIssue(kind=IssueKind.UNUSED, module_path=["Root"], variable=proc_var, role="unused"),
        ],
        visible_kinds=frozenset({IssueKind.UNUSED}),
        include_empty_sections=True,
    )
    assert variables_execution_module._mapping_target_name(_ns(target="Demo.Field")) == "demo"
    assert variables_execution_module._mapping_target_name(_ns(target={"var_name": "Demo.Field"})) == "demo"
    assert variables_execution_module._mapping_target_name(_ns(target={})) is None
    assert variables_access_module._site_str(_ns(site_stack=[])) == ""
    assert variables_access_module._site_str(_ns(site_stack=["A", "B"])) == "A > B"
    assert report.basepicture_name == "Root"
