from __future__ import annotations

from collections import defaultdict
from types import SimpleNamespace
from typing import Any, cast

import pytest

from sattline_parser.models.ast_model import Simple_DataType, Variable
from sattlint.analyzers import _variables_access as variables_access_module
from sattlint.analyzers import _variables_contracts as variables_contracts_module
from sattlint.analyzers import _variables_execution as variables_execution_module
from sattlint.analyzers import _variables_status as variables_status_module
from sattlint.analyzers import variable_issue_collection as variable_issue_collection_module
from sattlint.analyzers import variables as variables_module
from sattlint.analyzers.variables import IssueKind, VariableIssue, VariablesAnalyzer
from sattlint.reporting.variables_report import VariablesReport
from sattlint.resolution import AccessKind, CanonicalPath


def _ns(**kwargs: Any) -> Any:
    return SimpleNamespace(**kwargs)


class _UsageStub:
    def __init__(
        self,
        *,
        read: bool = False,
        written: bool = False,
        is_unused: bool = False,
        is_display_only: bool = False,
        is_read_only: bool = False,
        non_ui_read: bool = False,
        ui_read: bool = False,
        field_reads: dict[str, object] | None = None,
        field_writes: dict[str, object] | None = None,
    ) -> None:
        self.read = read
        self.written = written
        self.is_unused = is_unused
        self.is_display_only = is_display_only
        self.is_read_only = is_read_only
        self.non_ui_read = non_ui_read
        self.ui_read = ui_read
        self.field_reads = field_reads or {}
        self.field_writes = field_writes or {}


def test_variables_access_wrapper_helpers_delegate_and_parse_fields() -> None:
    tracker_calls: list[tuple[str, object]] = []
    usage_tracker = _ns(
        record_access=lambda **kwargs: tracker_calls.append(("record", kwargs)),
        mark_ref_access=lambda **kwargs: tracker_calls.append(("mark", kwargs)),
    )
    effect_tracker = _ns(
        effect_key_for_variable=lambda variable, decl_path: ("effect", variable.name, *decl_path),
        resolve_effect_key=lambda full_ref, context: ("resolved", full_ref),
        mapping_source_effect_key=lambda pm, **kwargs: ("mapping",),
        resolve_local_effect_key=lambda full_ref, context: ("local", full_ref),
        resolve_mapped_effect_source_key=lambda full_ref, context: ("mapped", full_ref),
        record_effect_flow=lambda source_key, target_key: tracker_calls.append(("flow", (source_key, target_key))),
        collect_function_input_effect_keys=lambda fn_name, args, context: {(fn_name or "", len(args))},
        collect_expression_effect_sources=lambda obj, context: {("expr",)},
        record_assignment_effect_flow=lambda target_ref, expr, context: tracker_calls.append(("assign", target_ref)),
        record_function_call_effect_flow=lambda fn_name, args, context: tracker_calls.append(("call", fn_name)),
    )
    helper: Any = SimpleNamespace(
        usage_tracker=usage_tracker,
        effect_flow_tracker=effect_tracker,
        root_env={},
        any_var_index={"fallback": [Variable(name="Fallback", datatype=Simple_DataType.INTEGER)]},
    )
    variable = Variable(name="Demo", datatype=Simple_DataType.INTEGER)
    context: Any = _ns(
        env={"local": variable},
        param_mappings={"local": object()},
        module_path=["Root"],
        resolve_variable=lambda full_ref: (
            (None, None, [], None) if full_ref == "local.field" else (variable, "field", ["Decl"], None)
        ),
    )

    assert variables_access_module._canonical_path(helper, ["Root"], variable, "field..leaf") == CanonicalPath(
        ("Root", "Demo", "field", "leaf")
    )
    variables_access_module._record_access(
        helper,
        AccessKind.READ,
        CanonicalPath(("Root", "Demo")),
        context,
        "Demo",
    )
    variables_access_module._mark_ref_access(helper, "local.field", context, ["Root"], AccessKind.READ)
    variables_access_module._mark_ref_access(helper, "resolved.field", context, ["Root"], AccessKind.WRITE)
    assert variables_access_module._effect_key_for_variable(helper, variable, ["Root"]) == ("effect", "Demo", "Root")
    assert variables_access_module._resolve_effect_key(helper, "x", context) == ("resolved", "x")
    assert variables_access_module._mapping_source_effect_key(
        helper, _ns(target="x"), parent_env={}, parent_context=None
    ) == ("mapping",)
    assert variables_access_module._resolve_local_effect_key(helper, "x", context) == ("local", "x")
    assert variables_access_module._resolve_mapped_effect_source_key(helper, "x", context) == ("mapped", "x")
    variables_access_module._record_effect_flow(helper, ("a",), ("b",))
    assert variables_access_module._collect_function_input_effect_keys(helper, "Fn", [1], context) == {("Fn", 1)}
    assert variables_access_module._collect_expression_effect_sources(helper, object(), context) == {("expr",)}
    variables_access_module._record_assignment_effect_flow(helper, "dest", object(), context)
    variables_access_module._record_function_call_effect_flow(helper, "Fn", [], context)

    assert len([call for call in tracker_calls if call[0] == "mark"]) == 2
    assert variables_access_module._lookup_global_variable(helper, None) is None
    helper.root_env["direct"] = variable
    assert variables_access_module._lookup_global_variable(helper, "direct") is variable
    assert variables_access_module._lookup_global_variable(helper, "fallback") is not None
    assert variables_access_module._extract_field_path(helper, {}) == (None, None)
    assert variables_access_module._extract_field_path(helper, {"var_name": 1}) == (None, None)
    assert variables_access_module._extract_field_path(helper, {"var_name": "Demo"}) == ("demo", None)
    assert variables_access_module._extract_field_path(helper, {"var_name": "Demo.Field"}) == ("demo", "Field")


def test_variables_access_strict_datatype_and_leaf_helpers_cover_warning_and_error_paths() -> None:
    warnings: list[str] = []
    record_with_known_field = _ns(
        name="RecordType",
        fields_by_key={"known": _ns(name="Known", datatype=Simple_DataType.INTEGER)},
    )
    helper: Any = SimpleNamespace(
        fail_loudly=False,
        unavailable_libraries={"Lib"},
        opaque_builtin_types={"opaque"},
        type_graph=_ns(record=lambda name: None if name == "Unknown" else record_with_known_field),
        site_stack=["site"],
        warn=warnings.append,
    )

    assert (
        variables_access_module._strict_datatype_at_field_prefix(
            helper,
            Simple_DataType.INTEGER,
            "field",
            fn_name="Fn",
            syntactic_ref="Ref",
            resolved_var_name="Demo",
            use_path=["Root"],
        )
        == Simple_DataType.INTEGER
    )
    assert any("cannot access field" in warning for warning in warnings)

    helper.fail_loudly = True
    with pytest.raises(ValueError):
        variables_access_module._strict_datatype_at_field_prefix(
            helper,
            Simple_DataType.INTEGER,
            "field",
            fn_name="Fn",
            syntactic_ref="Ref",
            resolved_var_name="Demo",
            use_path=["Root"],
        )
    helper.fail_loudly = False

    assert (
        variables_access_module._strict_datatype_at_field_prefix(
            helper,
            "opaque",
            "field",
            fn_name="Fn",
            syntactic_ref="Ref",
            resolved_var_name="Demo",
            use_path=["Root"],
        )
        == "opaque"
    )

    assert (
        variables_access_module._strict_datatype_at_field_prefix(
            helper,
            "Unknown",
            "field",
            fn_name="Fn",
            syntactic_ref="Ref",
            resolved_var_name="Demo",
            use_path=["Root"],
        )
        == "Unknown"
    )

    helper.fail_loudly = True
    helper.unavailable_libraries = set()
    with pytest.raises(ValueError):
        variables_access_module._strict_datatype_at_field_prefix(
            helper,
            "Unknown",
            "field",
            fn_name="Fn",
            syntactic_ref="Ref",
            resolved_var_name="Demo",
            use_path=["Root"],
        )
    helper.fail_loudly = False
    helper.unavailable_libraries = {"Lib"}

    warnings.clear()
    assert (
        variables_access_module._strict_datatype_at_field_prefix(
            helper,
            "RecordType",
            "know",
            fn_name="Fn",
            syntactic_ref="Ref",
            resolved_var_name="Demo",
            use_path=["Root"],
        )
        == "RecordType"
    )
    assert any("Close matches" in warning for warning in warnings)

    helper.fail_loudly = True
    helper.unavailable_libraries = set()
    with pytest.raises(ValueError):
        variables_access_module._iter_leaf_field_paths_strict(
            helper,
            "Unknown",
            fn_name="Fn",
            syntactic_ref="Ref",
            resolved_var_name="Demo",
        )

    helper.fail_loudly = False
    helper.unavailable_libraries = {"Lib"}
    warnings.clear()
    assert variables_access_module._iter_leaf_field_paths_strict(
        helper,
        "Unknown",
        fn_name="Fn",
        syntactic_ref="Ref",
        resolved_var_name="Demo",
    ) == [()]
    assert warnings

    helper.unavailable_libraries = set()
    warnings.clear()
    assert variables_access_module._iter_leaf_field_paths_strict(
        helper,
        "Unknown",
        fn_name="Fn",
        syntactic_ref="Ref",
        resolved_var_name="Demo",
    ) == [()]
    assert warnings

    helper.type_graph = _ns(record=lambda name: None if name in {"Unknown", "opaque"} else record_with_known_field)
    helper.opaque_builtin_types = {"opaque"}
    assert variables_access_module._iter_leaf_field_paths_strict(
        helper,
        "opaque",
        fn_name="Fn",
        syntactic_ref="Ref",
        resolved_var_name="Demo",
    ) == [()]
    assert variables_access_module._iter_leaf_field_paths_strict(
        helper,
        "AnyType",
        fn_name="Fn",
        syntactic_ref="Ref",
        resolved_var_name="Demo",
    ) == [()]

    helper.type_graph = _ns(
        record=lambda name: (
            _ns(fields_by_key={"leaf": _ns(name="Leaf", datatype="AnyType")}) if name == "RecordType" else None
        )
    )
    assert variables_access_module._iter_leaf_field_paths_strict(
        helper,
        "RecordType",
        fn_name="Fn",
        syntactic_ref="Ref",
        resolved_var_name="Demo",
    ) == [("Leaf",)]

    cyclic_record = _ns(fields_by_key={"self": _ns(name="Self", datatype="Loop")})
    helper.type_graph = _ns(record=lambda name: cyclic_record if name == "Loop" else None)
    helper.fail_loudly = True
    helper.unavailable_libraries = set()
    with pytest.raises(ValueError):
        variables_access_module._iter_leaf_field_paths_strict(
            helper,
            "Loop",
            fn_name="Fn",
            syntactic_ref="Ref",
            resolved_var_name="Demo",
        )


def test_variables_access_record_wide_access_and_origin_helpers() -> None:
    variable = Variable(name="Demo", datatype="RecordType")
    unresolved_context: Any = _ns(resolve_variable=lambda *_: (None, None, [], None))
    helper: Any = SimpleNamespace(site_stack=["site"])
    with pytest.raises(ValueError):
        variables_access_module._mark_record_wide_builtin_access(
            helper,
            "Demo",
            kind=AccessKind.READ,
            fn_name="Fn",
            context=unresolved_context,
            path=["Root"],
        )

    refs: list[tuple[str, bool]] = []
    context: Any = _ns(resolve_variable=lambda *_: (variable, None, ["Root"], None))
    original_strict = variables_access_module._strict_datatype_at_field_prefix
    original_iter = variables_access_module._iter_leaf_field_paths_strict
    original_mark = variables_access_module._mark_ref_access
    try:
        variables_access_module._strict_datatype_at_field_prefix = lambda *args, **kwargs: "RecordType"
        variables_access_module._iter_leaf_field_paths_strict = lambda *args, **kwargs: [(), ("Leaf",)]
        variables_access_module._mark_ref_access = lambda self, syntactic_ref, context, path, kind, is_ui_read=False: (
            refs.append((syntactic_ref, is_ui_read))
        )
        variables_access_module._mark_record_wide_builtin_access(
            helper,
            "Demo",
            kind=AccessKind.WRITE,
            fn_name="Fn",
            context=context,
            path=["Root"],
            is_ui_read=True,
        )
    finally:
        variables_access_module._strict_datatype_at_field_prefix = original_strict
        variables_access_module._iter_leaf_field_paths_strict = original_iter
        variables_access_module._mark_ref_access = original_mark

    assert refs == [("Demo", True), ("Demo.Leaf", True)]

    library_helper: Any = _ns(
        analyzed_target_is_library=True,
        bp=_ns(origin_lib="RootLib", origin_file="RootLib.s"),
    )
    assert variables_access_module._is_from_root_origin(library_helper, "Other.s", "rootlib") is True

    class BrokenPath:
        def __init__(self, value: str) -> None:
            self.value = value

        def rsplit(self, sep: str, maxsplit: int) -> list[str]:
            return self.value.rsplit(sep, maxsplit)

    fallback_helper: Any = _ns(
        analyzed_target_is_library=False,
        bp=_ns(origin_file=BrokenPath("Root.s")),
    )
    assert variables_access_module._is_from_root_origin(fallback_helper, cast(Any, BrokenPath("Root.x"))) is True
    assert (
        variables_access_module._is_from_root_origin(_ns(analyzed_target_is_library=False, bp=_ns()), "Root.x") is False
    )

    broken_library_helper: Any = _ns(
        analyzed_target_is_library=True,
        bp=_ns(origin_lib="Root", origin_file=BrokenPath("Root.s")),
    )
    assert variables_access_module._is_from_root_origin(broken_library_helper, "Other.s", "root") is True


def test_variables_contracts_cover_guard_branches(monkeypatch: pytest.MonkeyPatch) -> None:
    non_any = Variable(name="Scalar", datatype=Simple_DataType.INTEGER)
    any_param = Variable(name="AnyParam", datatype="AnyType")
    extractor: Any = _ns(get_usage=lambda variable: _UsageStub())
    assert variables_contracts_module._build_anytype_parameter_contract(_ns(), extractor, non_any) is None
    assert variables_contracts_module._build_anytype_parameter_contract(_ns(), extractor, any_param) is None

    helper: Any = SimpleNamespace(iter_anytype_typedefs=lambda: [])
    assert variables_contracts_module._build_anytype_field_contracts(helper) == {}

    display_only = Variable(name="DisplayOnly", datatype=Simple_DataType.INTEGER)
    required = Variable(name="Required", datatype=Simple_DataType.INTEGER)
    moduletype: Any = _ns(moduleparameters=[display_only, required], name="Worker")
    usage_by_id = {
        id(display_only): _UsageStub(read=True, is_display_only=True),
        id(required): _UsageStub(read=True),
    }
    monkeypatch.setattr(
        variables_contracts_module,
        "_make_nested_contract_extractor",
        lambda self: SimpleNamespace(
            analyze_typedef=lambda *args, **kwargs: None,
            get_usage=lambda variable: usage_by_id[id(variable)],
        ),
    )
    owner: Any = _ns(bp=_ns(header=_ns(name="Root")), required_parameter_names_by_owner={})
    assert variables_contracts_module._get_required_parameter_names_for_typedef(owner, moduletype) == {
        "required": "Required"
    }

    issues: list[str] = []
    parameter = Variable(name="Required", datatype=Simple_DataType.INTEGER)
    self_single: Any = SimpleNamespace(
        get_usage=lambda variable: _UsageStub(read=True, is_display_only=variable is not parameter),
        append_issue=lambda issue: issues.append(issue.role),
        check_param_mapping=lambda *args, **kwargs: issues.append("checked"),
    )
    mod: Any = _ns(
        moduleparameters=[Variable(name="Display", datatype=Simple_DataType.INTEGER), parameter], parametermappings=[]
    )
    variables_contracts_module._check_param_mappings_for_single(self_single, mod, {}, {}, ["Root"])
    assert issues == ["required parameter connection missing for 'Required'"]

    inst: Any = _ns(moduletype_name="Missing", parametermappings=[])
    self_inst: Any = SimpleNamespace(
        bp=_ns(),
        unavailable_libraries=set(),
        get_required_parameter_names_for_typedef=lambda mt: {"missing": "Missing"},
        append_issue=lambda issue: (_ for _ in ()).throw(AssertionError("unexpected issue")),
        check_param_mapping=lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        variables_contracts_module,
        "resolve_moduletype_def_strict",
        lambda *args, **kwargs: (_ for _ in ()).throw(ValueError("missing")),
    )
    variables_contracts_module._check_param_mappings_for_type_instance(self_inst, inst, {}, ["Root"])
    monkeypatch.setattr(
        variables_contracts_module,
        "resolve_moduletype_def_strict",
        lambda *args, **kwargs: SimpleNamespace(moduleparameters=[]),
    )
    variables_contracts_module._check_param_mappings_for_type_instance(self_inst, inst, {}, ["Root"])


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
