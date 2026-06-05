from __future__ import annotations

from collections import defaultdict
from types import SimpleNamespace
from typing import Any, cast

import pytest

from sattline_parser.models.ast_model import (
    Simple_DataType,
    Variable,
)
from sattlint.analyzers import _variable_issue_collection as variable_issue_collection_module
from sattlint.analyzers import _variables_access as variables_access_module
from sattlint.analyzers import _variables_execution as variables_execution_module
from sattlint.analyzers import _variables_status as variables_status_module
from sattlint.analyzers import variable_utils as variable_utils_module
from sattlint.analyzers import variables as variables_module
from sattlint.analyzers._variables_analyzer_facade import VariablesAnalyzerFacadeMixin
from sattlint.analyzers._variables_facade_properties import VariablesAnalyzerFacadePropertiesMixin
from sattlint.analyzers.variables import IssueKind, VariableIssue, VariablesAnalyzer
from sattlint.reporting.variables_report import VariablesReport
from tests.helpers.variable_test_support import UsageStub as _UsageStub
from tests.helpers.variable_test_support import ns as _ns

variable_issue_collection_impl: Any = variable_issue_collection_module
variables_access_impl: Any = variables_access_module
variables_execution_impl: Any = variables_execution_module
variables_status_impl: Any = variables_status_module
VariablesAnalyzerType: Any = VariablesAnalyzer


def _returns_false(*_args: object, **_kwargs: object) -> bool:
    return False


def _returns_true(*_args: object, **_kwargs: object) -> bool:
    return True


def test_variables_status_cover_pattern_and_binding_branches(monkeypatch: pytest.MonkeyPatch) -> None:
    assert variables_status_impl._normalize_role_pattern_values("bad") == ()
    assert variables_status_impl._normalize_role_pattern_values([" Cmd ", "cmd", 1, ""]) == ("cmd",)
    defaults = variables_status_impl._configured_naming_role_patterns(None)
    assert defaults["status"].suffixes == ("status",)
    assert variables_status_impl._configured_naming_role_patterns({"analysis": "bad"}) == defaults
    assert variables_status_impl._configured_naming_role_patterns({"analysis": {}}) == defaults
    assert variables_status_impl._configured_naming_role_patterns({"analysis": {"naming": {}}}) == defaults
    configured = variables_status_impl._configured_naming_role_patterns(
        {"analysis": {"naming": {"role_patterns": {"command": {"prefixes": ["Start", "start"]}}}}}
    )
    assert "start" in configured["command"].prefixes

    variable = Variable(name="StatusVar", datatype=Simple_DataType.INTEGER)
    helper: Any = SimpleNamespace(
        procedure_status_bindings=defaultdict(list),
        ignorable_output_variable_ids=set(),
    )

    def _resolve_missing_variable(*_args: object) -> tuple[None, None, list[str], None]:
        return (None, None, [], None)

    none_context: Any = _ns(resolve_variable=_resolve_missing_variable)
    variables_status_impl._bind_procedure_status(
        helper,
        "StatusVar",
        call_name="Fn",
        parameter=_ns(name="Out", channel_kind=None),
        context=none_context,
    )
    variables_status_impl._bind_ignorable_output(helper, "StatusVar", context=none_context)
    assert helper.procedure_status_bindings == {}
    assert helper.ignorable_output_variable_ids == set()

    def _resolve_bound_variable(*_args: object) -> tuple[Variable, str, list[str], None]:
        return (variable, "Field", ["Root"], None)

    good_context: Any = _ns(resolve_variable=_resolve_bound_variable)
    variables_status_impl._bind_procedure_status(
        helper,
        "StatusVar",
        call_name="Fn",
        parameter=_ns(name="Out", channel_kind=None),
        context=good_context,
    )
    variables_status_impl._bind_procedure_status(
        helper,
        "StatusVar",
        call_name="Fn",
        parameter=_ns(name="Out", channel_kind=None),
        context=good_context,
    )
    variables_status_impl._bind_ignorable_output(helper, "StatusVar", context=good_context)
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

    def _bind_status(full_ref: str, **_kwargs: object) -> None:
        status_calls.append(full_ref)

    def _bind_ignorable(full_ref: str, **_kwargs: object) -> None:
        ignorable_calls.append(full_ref)

    recorder: Any = SimpleNamespace(
        bind_procedure_status=_bind_status,
        bind_ignorable_output=_bind_ignorable,
    )

    def _resolve_missing_signature(_fn_name: str) -> None:
        return None

    def _resolve_signature(_fn_name: str) -> Any:
        return signature

    monkeypatch.setattr(variables_status_module, "resolve_call_signature", _resolve_missing_signature)
    variables_status_impl._record_procedure_status_bindings(recorder, "Fn", [], good_context)
    variables_status_impl._record_procedure_status_bindings(recorder, "Fn", [{"var_name": 5}], good_context)
    variables_status_impl._record_ignorable_output_bindings(recorder, "SearchRecComponent", [], good_context)
    monkeypatch.setattr(variables_status_module, "resolve_call_signature", _resolve_signature)
    variables_status_impl._record_procedure_status_bindings(
        recorder,
        "Fn",
        [{"var_name": 5}],
        good_context,
    )
    variables_status_impl._record_procedure_status_bindings(
        recorder,
        "Fn",
        [{}, {"var_name": 5}, {"var_name": "Ignored"}],
        good_context,
    )
    variables_status_impl._record_procedure_status_bindings(
        recorder,
        "Fn",
        [{"var_name": "StatusVar"}],
        good_context,
    )
    variables_status_impl._record_ignorable_output_bindings(
        recorder,
        "SearchRecComponent",
        [],
        good_context,
    )
    variables_status_impl._record_ignorable_output_bindings(
        recorder,
        "SearchRecComponent",
        [{}, {}, {}],
        good_context,
    )
    variables_status_impl._record_ignorable_output_bindings(
        recorder,
        "SearchRecComponent",
        [{}, {}, {"var_name": 7}],
        good_context,
    )
    variables_status_impl._record_ignorable_output_bindings(
        recorder,
        "SearchRecComponent",
        [{"var_name": 7}, {"var_name": "Ignored"}, {"var_name": "StatusVar"}],
        good_context,
    )
    variables_status_impl._record_ignorable_output_bindings(
        recorder,
        "Fn",
        [{"var_name": "StatusVar"}],
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
    variables_status_impl._propagate_procedure_status_bindings(helper)
    variables_status_impl._propagate_procedure_status_bindings(helper)
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
    no_binding_helper: Any = SimpleNamespace(
        alias_links=[(source, target, "Mapped")],
        procedure_status_bindings=defaultdict(list),
    )
    variables_status_impl._propagate_procedure_status_bindings(no_binding_helper)
    assert no_binding_helper.procedure_status_bindings == defaultdict(list)

    assert (
        variables_status_impl._has_procedure_status_binding(
            _ns(procedure_status_bindings={id(source): [binding]}),
            source,
        )
        is True
    )
    assert (
        variables_status_impl._has_ignorable_output_binding(
            _ns(ignorable_output_variable_ids={id(source)}),
            source,
        )
        is True
    )
    status_issue = variables_status_impl._procedure_status_issue(
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
    analyzer: Any = VariablesAnalyzer.__new__(VariablesAnalyzer)
    analyzer._analysis_warnings = []
    analyzer.debug = True

    def _trace(action: str, **kwargs: str) -> None:
        traces.append((action, kwargs))

    analyzer._trace = _trace
    monkeypatch.setattr(variables_module.log, "warning", warning_log.append)
    analyzer._warn("demo warning")
    assert analyzer.analysis_warnings == ["demo warning"]
    assert warning_log == ["demo warning"]
    assert traces == [("warning", {"message": "demo warning"})]


def test_variables_status_naming_role_and_issue_helpers_cover_remaining_branches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    command_var = Variable(name="StartCmd", datatype=Simple_DataType.INTEGER)
    status_var = Variable(name="PumpStatus", datatype=Simple_DataType.INTEGER)
    alarm_var = Variable(name="TripAlarm", datatype=Simple_DataType.INTEGER)
    bound_var = Variable(name="BoundStatus", datatype=Simple_DataType.INTEGER)
    binding = variables_status_module.ProcedureStatusBinding(
        call_name="RunProc",
        parameter_name="StatusOut",
        channel_kind="status",
        field_path="Leaf",
    )
    helper: Any = SimpleNamespace(
        naming_role_patterns={},
    )

    def _matches_naming_role(name_key: str, role_name: str) -> bool:
        return (name_key, role_name) in {
            (command_var.name.casefold(), "command"),
            (status_var.name.casefold(), "status"),
            (alarm_var.name.casefold(), "alarm"),
        }

    def _has_bound_status(variable: Variable) -> bool:
        return variable is bound_var

    helper.matches_naming_role = _matches_naming_role
    helper.has_output_effect = _returns_false
    helper.has_procedure_status_binding = _has_bound_status
    helper.procedure_status_bindings = {id(bound_var): [binding]}

    assert variables_status_impl._procedure_status_issue(
        helper,
        bound_var,
        cast(Any, _UsageStub(written=True, ui_read=False, non_ui_read=False)),
    ) == (
        "procedure status output from 'RunProc' parameter 'StatusOut' is ignored after the procedure writes it.",
        "Leaf",
    )
    assert (
        variables_status_impl._procedure_status_issue(
            helper,
            bound_var,
            cast(Any, _UsageStub(written=False)),
        )
        is None
    )
    assert (
        variables_status_impl._procedure_status_issue(
            helper,
            bound_var,
            cast(Any, _UsageStub(written=True, non_ui_read=True)),
        )
        is None
    )
    assert (
        variables_status_impl._naming_role_mismatch_reason(
            helper,
            command_var,
            cast(Any, _UsageStub(read=True, written=True)),
            ["Root"],
        )
        == "Cmd-suffixed variable behaves like internal state instead of a one-way command signal."
    )
    assert (
        variables_status_impl._naming_role_mismatch_reason(
            helper,
            status_var,
            cast(Any, _UsageStub(written=True)),
            ["Root"],
        )
        == "Status-suffixed variable is written directly in logic instead of being treated as observed status."
    )
    assert (
        variables_status_impl._naming_role_mismatch_reason(
            helper,
            alarm_var,
            cast(Any, _UsageStub(non_ui_read=True)),
            ["Root"],
        )
        == "Alarm-suffixed variable is consumed in non-UI logic and behaves like a control input."
    )
    command_ok_helper: Any = SimpleNamespace(
        **{
            **helper.__dict__,
            "has_output_effect": _returns_true,
        }
    )
    assert (
        variables_status_impl._naming_role_mismatch_reason(
            command_ok_helper,
            command_var,
            cast(Any, _UsageStub(read=True, written=True)),
            ["Root"],
        )
        is None
    )
    bound_helper: Any = SimpleNamespace(
        **helper.__dict__,
    )

    def _has_status_binding(variable: Variable) -> bool:
        return variable is status_var

    bound_helper.has_procedure_status_binding = _has_status_binding
    assert (
        variables_status_impl._naming_role_mismatch_reason(
            bound_helper,
            status_var,
            cast(Any, _UsageStub(written=True)),
            ["Root"],
        )
        is None
    )
    assert (
        variables_status_impl._naming_role_mismatch_reason(
            helper,
            alarm_var,
            cast(Any, _UsageStub(non_ui_read=False)),
            ["Root"],
        )
        is None
    )
    assert (
        variables_status_impl._naming_role_mismatch_reason(
            helper,
            Variable(name="PlainVar", datatype=Simple_DataType.INTEGER),
            cast(Any, _UsageStub()),
            ["Root"],
        )
        is None
    )
    assert (
        variables_status_impl._matches_naming_role(
            cast(Any, SimpleNamespace(naming_role_patterns={})),
            "plain_name",
            "status",
        )
        is False
    )

    added_issues: list[tuple[IssueKind, list[str], Variable, str]] = []

    def _get_usage(_variable: Variable) -> _UsageStub:
        return _UsageStub(read=True, written=True)

    def _naming_role_mismatch_reason(
        variable: Variable,
        _usage: _UsageStub,
        _decl_path: list[str],
    ) -> str | None:
        if variable is alarm_var:
            return None
        return "mismatch"

    def _add_issue(kind: IssueKind, decl_path: list[str], variable: Variable, role: str = "") -> None:
        added_issues.append((kind, decl_path, variable, role))

    analyzer: Any = SimpleNamespace(
        get_usage=_get_usage,
        naming_role_mismatch_reason=_naming_role_mismatch_reason,
        add_issue=_add_issue,
    )

    def _iter_variables_for_datatype_field_analysis(
        _self: object,
    ) -> list[tuple[list[str], Variable, None, bool]]:
        return [(["Root"], command_var, None, True), (["Root"], alarm_var, None, True)]

    monkeypatch.setattr(
        variables_status_module,
        "_iter_variables_for_datatype_field_analysis",
        _iter_variables_for_datatype_field_analysis,
    )
    variables_status_impl._add_naming_role_mismatch_issues(analyzer)
    assert added_issues == [(IssueKind.NAMING_ROLE_MISMATCH, ["Root"], command_var, "mismatch")]


def test_variables_analyzer_warn_trace_and_status_helpers_cover_remaining_branches() -> None:
    forwarded_warnings: list[str] = []
    trace_events: list[tuple[str, str, dict[str, object]]] = []
    status_updates: list[str] = []

    analyzer: Any = VariablesAnalyzer.__new__(VariablesAnalyzer)
    analyzer._analysis_warnings = []
    analyzer.debug = False

    def _record_trace_event(category: str, action: str, **data: object) -> None:
        trace_events.append((category, action, data))

    analyzer._trace_recorder = SimpleNamespace(event=_record_trace_event)
    analyzer._status_update_fn = status_updates.append
    analyzer._last_status_message = None
    analyzer.bp = _ns(header=_ns(name="Root"))

    analyzer._warn = forwarded_warnings.append
    analyzer.warn("wrapped warning")
    assert forwarded_warnings == ["wrapped warning"]

    VariablesAnalyzer.trace(analyzer, "custom-action", detail="value")
    assert trace_events == [("variables", "custom-action", {"detail": "value"})]

    analyzer._last_status_message = None
    VariablesAnalyzerType._update_status(analyzer, "building root scope")
    VariablesAnalyzerType._update_status(analyzer, "building root scope")
    assert status_updates == ["Analyzing variable issues for Root: building root scope"]
    assert analyzer._last_status_message == status_updates[0]

    analyzer._status_update_fn = None
    VariablesAnalyzerType._update_status(analyzer, "ignored")


def test_variables_facade_forwarders_and_properties_cover_remaining_branches() -> None:
    variable = Variable(name="FacadeVar", datatype=Simple_DataType.INTEGER)
    other_variable = Variable(name="GlobalVar", datatype=Simple_DataType.INTEGER)
    issue = VariableIssue(kind=IssueKind.UNUSED, module_path=["Root"], variable=variable, role="unused")
    mapping = SimpleNamespace(name="Map")
    parent_context = SimpleNamespace(name="parent")
    context = SimpleNamespace(name="ctx")
    forwarded_calls: list[tuple[str, tuple[object, ...], dict[str, object]]] = []

    class FacadeProbe(VariablesAnalyzerFacadeMixin):
        _OPAQUE_BUILTIN_TYPES = cast(set[str], frozenset({"OPAQUE"}))

    def _get_usage(arg: Variable) -> tuple[str, Variable]:
        return ("usage", arg)

    def _append_issue(arg: VariableIssue) -> None:
        forwarded_calls.append(("append_issue", (arg,), {}))

    def _append_param_mapping_issue(arg1: object, arg2: object) -> None:
        forwarded_calls.append(("append_param_mapping_issue", (arg1, arg2), {}))

    def _add_issue(*args: object, **kwargs: object) -> None:
        forwarded_calls.append(("add_issue", args, dict(kwargs)))

    def _is_from_root_origin(origin_file: str | None, origin_lib: str | None = None) -> bool:
        return (origin_file, origin_lib) == ("root.mod", "LIB")

    def _has_output_effect(arg: Variable, path: list[str]) -> bool:
        return (arg, path) == (variable, ["Root", "Out"])

    def _has_ignorable_output_binding(arg: Variable) -> bool:
        return arg is variable

    def _analyze_library_dependency_typedef_usage() -> None:
        forwarded_calls.append(("analyze_library_dependency_typedef_usage", (), {}))

    def _check_param_mapping(*args: object, **kwargs: object) -> None:
        forwarded_calls.append(("check_param_mapping", args, dict(kwargs)))

    def _lookup_global_variable(name: str | None) -> Variable | None:
        return other_variable if name == "GlobalVar" else None

    def _walk_moduledef(*args: object) -> None:
        forwarded_calls.append(("walk_moduledef", args, {}))

    def _walk_module_code(*args: object) -> None:
        forwarded_calls.append(("walk_module_code", args, {}))

    facade: Any = FacadeProbe.__new__(FacadeProbe)
    facade.usage_tracker = SimpleNamespace(get_usage=_get_usage, access_graph="graph")
    facade._append_issue = _append_issue
    facade._append_param_mapping_issue = _append_param_mapping_issue
    facade._add_issue = _add_issue
    facade._is_from_root_origin = _is_from_root_origin
    facade._has_output_effect = _has_output_effect
    facade._has_ignorable_output_binding = _has_ignorable_output_binding
    facade._analyze_library_dependency_typedef_usage = _analyze_library_dependency_typedef_usage
    facade._check_param_mapping = _check_param_mapping
    facade._lookup_global_variable = _lookup_global_variable
    facade._walk_moduledef = _walk_moduledef
    facade._walk_module_code = _walk_module_code

    assert facade.get_usage(variable) == ("usage", variable)
    facade.append_issue(issue)
    facade.append_param_mapping_issue(mapping, issue)
    facade.add_issue(IssueKind.UNUSED, ["Root"], variable, role="unused", field_path="Leaf")
    assert facade.is_from_root_origin("root.mod", "LIB") is True
    assert facade.has_output_effect(variable, ["Root", "Out"]) is True
    assert facade.has_ignorable_output_binding(variable) is True
    facade.analyze_library_dependency_typedef_usage()
    facade.check_param_mapping(mapping, variable, {"FacadeVar": variable}, None, ["Root"], owner_contract_id=17)
    assert facade.lookup_global_variable("GlobalVar") is other_variable
    facade.walk_moduledef("moduledef", context, ["Root"])
    facade.walk_module_code("modulecode", context, ["Root"])

    with pytest.raises(AttributeError, match="missing_attr"):
        _ = facade.missing_attr

    class PropertiesProbe(VariablesAnalyzerFacadePropertiesMixin):
        _OPAQUE_BUILTIN_TYPES = cast(set[str], frozenset({"OPAQUE", "OPAQUE2"}))

    properties_probe: Any = PropertiesProbe.__new__(PropertiesProbe)
    properties_probe.usage_tracker = SimpleNamespace(access_graph="graph")
    properties_probe._effect_flow_edges = {("src",): {("z",), ("a",)}}
    properties_probe._contexts_by_module_path = {("Root",): parent_context}
    properties_probe._effect_flow_display_names = {("Root",): "Root.Display"}
    properties_probe._analysis_warnings = ["warning"]
    properties_probe._issues = [issue]

    assert properties_probe.access_graph == "graph"
    assert properties_probe.opaque_builtin_types == {"OPAQUE", "OPAQUE2"}
    assert properties_probe.effect_flow_edges == {("src",): (("a",), ("z",))}
    assert properties_probe.contexts_by_module_path is properties_probe._contexts_by_module_path
    assert properties_probe.effect_flow_display_names == {("Root",): "Root.Display"}
    assert properties_probe.effect_flow_display_names is not properties_probe._effect_flow_display_names
    assert properties_probe.analysis_warnings == ["warning"]
    assert properties_probe.issues == [issue]

    assert forwarded_calls == [
        ("append_issue", (issue,), {}),
        ("append_param_mapping_issue", (mapping, issue), {}),
        (
            "add_issue",
            (IssueKind.UNUSED, ["Root"], variable),
            {"role": "unused", "field_path": "Leaf"},
        ),
        ("analyze_library_dependency_typedef_usage", (), {}),
        (
            "check_param_mapping",
            (mapping, variable, {"FacadeVar": variable}, None, ["Root"]),
            {"owner_contract_id": 17},
        ),
        ("walk_moduledef", ("moduledef", context, ["Root"]), {}),
        ("walk_module_code", ("modulecode", context, ["Root"]), {}),
    ]


def test_variable_utils_cover_mapping_and_origin_fallback_branches(monkeypatch: pytest.MonkeyPatch) -> None:
    analyzer: Any = SimpleNamespace()
    assert (
        variable_utils_module.is_const_candidate(
            analyzer,
            Variable(name="Counter", datatype=Simple_DataType.INTEGER),
        )
        is True
    )
    assert (
        variable_utils_module.is_const_candidate(
            analyzer,
            Variable(name="Timer", datatype=Simple_DataType.TIME),
        )
        is False
    )

    assert variable_utils_module.external_mapping_usage("MMSReadWrite", "inputVariable") == (True, False)
    assert variable_utils_module.external_mapping_usage("MMSReadWrite", "outputVariable") == (False, True)
    assert variable_utils_module.external_mapping_usage("MMSReadDevice", "localVariable") == (False, True)
    assert variable_utils_module.external_mapping_usage("MMSWriteDevice", "writeData") == (True, False)
    assert variable_utils_module.external_mapping_usage("Other", "writeData") is None

    assert variable_utils_module.same_origin_file_stem(None, "root.s") is True
    assert variable_utils_module.same_origin_file_stem("root.s", None) is False
    assert variable_utils_module.same_origin_file_stem("Dir/Root.S", "root.g") is True

    original_path = variable_utils_module.Path

    class RaisingPath:
        def __init__(self, path: str) -> None:
            raise ValueError(path)

    monkeypatch.setattr(variable_utils_module, "Path", RaisingPath)
    try:
        assert variable_utils_module.same_origin_file_stem("Root.s", "root.g") is True
        assert (
            variable_utils_module.matches_root_origin(
                "child.s",
                "Root.s",
                analyzed_target_is_library=True,
                origin_lib="LIB_A",
                root_origin_lib="root",
            )
            is False
        )
        assert (
            variable_utils_module.matches_root_origin(
                "child.s",
                "Root.s",
                analyzed_target_is_library=True,
                origin_lib="root",
                root_origin_lib="root",
            )
            is True
        )
    finally:
        monkeypatch.setattr(variable_utils_module, "Path", original_path)

    assert variable_utils_module.matches_root_origin(None, "Root.s") is True
    assert (
        variable_utils_module.matches_root_origin(
            None,
            "Root.s",
            analyzed_target_is_library=False,
            origin_lib="ProjectLib",
            root_origin_lib="ProjectLib",
        )
        is True
    )
    assert (
        variable_utils_module.matches_root_origin(
            None,
            "Root.s",
            analyzed_target_is_library=False,
            origin_lib="SupportLib",
            root_origin_lib="ProjectLib",
        )
        is False
    )
    assert variable_utils_module.matches_root_origin("Root.s", "root.g") is True


def test_variable_issue_collection_and_variables_cover_remaining_branches(monkeypatch: pytest.MonkeyPatch) -> None:
    proc_var = Variable(name="Proc", datatype=Simple_DataType.INTEGER)
    ui_var = Variable(name="Display", datatype=Simple_DataType.INTEGER)
    effect_var = Variable(name="Effect", datatype=Simple_DataType.INTEGER)
    issues: list[tuple[IssueKind, str | None, str | None]] = []

    def _is_from_root_origin(*_args: object) -> bool:
        return True

    def _get_usage(variable: Variable) -> _UsageStub:
        return {
            id(proc_var): _UsageStub(read=True, written=True),
            id(ui_var): _UsageStub(is_display_only=True),
            id(effect_var): _UsageStub(read=True, written=True),
        }[id(variable)]

    def _procedure_status_issue(
        variable: Variable,
        _usage: _UsageStub,
    ) -> tuple[str, str | None] | None:
        if variable is proc_var:
            return ("status-role", "Field")
        return None

    def _append_issue(issue: VariableIssue) -> None:
        issues.append((issue.kind, issue.role, issue.field_path))

    helper: Any = SimpleNamespace(
        bp=SimpleNamespace(),
        unavailable_libraries=set(),
        analyzed_target_is_library=False,
        limit_to_module_path=["Root"],
        is_from_root_origin=_is_from_root_origin,
        get_usage=_get_usage,
        procedure_status_issue=_procedure_status_issue,
        has_output_effect=_returns_false,
        has_procedure_status_binding=_returns_false,
        append_issue=_append_issue,
    )

    def _resolve_moduletype_def_strict(*_args: object, **_kwargs: object) -> Any:
        return _ns(
            moduleparameters=[proc_var, ui_var, effect_var],
            localvariables=[],
            submodules=[],
            origin_file="Root.s",
            origin_lib=None,
        )

    monkeypatch.setattr(
        variable_issue_collection_module,
        "resolve_moduletype_def_strict",
        _resolve_moduletype_def_strict,
    )
    mod: Any = _ns(header=_ns(name="Worker"), moduletype_name="WorkerType")
    variable_issue_collection_impl._collect_issues_from_module(helper, mod, ["Root"])
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
    assert variables_execution_impl._mapping_target_name(_ns(target="Demo.Field")) == "demo"
    assert variables_execution_impl._mapping_target_name(_ns(target={"var_name": "Demo.Field"})) == "demo"
    assert variables_execution_impl._mapping_target_name(_ns(target={})) is None
    assert variables_access_impl._site_str(_ns(site_stack=[])) == ""
    assert variables_access_impl._site_str(_ns(site_stack=["A", "B"])) == "A > B"
    assert report.basepicture_name == "Root"
