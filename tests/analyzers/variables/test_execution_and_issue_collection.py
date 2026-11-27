# pyright: reportPrivateUsage=false
from types import SimpleNamespace
from typing import (
    Any,
    cast,
)

import pytest
from sattline_parser.ast import MappingSource
from sattline_parser.models.ast_model import (
    Assignment,
    BasePicture,
    DataType,
    Equation,
    ModuleCode,
    ModuleHeader,
    ModuleTypeDef,
    ModuleTypeInstance,
    ParameterMapping,
    ScalarDatatype,
    SingleModule,
    Variable,
)
from sattline_parser.models.expressions import NotOp

from sattlint.analyzers.variables import (
    IssueKind,
    VariablesAnalyzer,
)
from sattlint.analyzers.variables import (
    _variable_issue_collection as variable_issue_collection_module,
)
from sattlint.analyzers.variables import (
    _variables_execution as variables_execution_module,
)
from sattlint.analyzers.variables._variables_contracts import TypedefUsageKey
from sattlint.reporting.variables_report import (
    FieldPathVariableIssue,
    UnusedDatatypeFieldIssue,
    UnusedDatatypeIssue,
    VariableIssue,
    VariableTargetIssue,
)
from sattlint.resolution.scope import ScopeContext
from tests.helpers.variable_test_support import (
    UsageStub as _UsageStub,
)
from tests.helpers.variable_test_support import (
    access_event as _access_event,
)
from tests.helpers.variable_test_support import (
    hdr as _hdr,
)
from tests.helpers.variable_test_support import (
    varref as _varref,
)


def _ignore_call(*args: object, **kwargs: object) -> None:
    """Accept and discard an analyzer callback."""


def _false_flag(*args: object, **kwargs: object) -> bool:
    return False


def _true_flag(*args: object, **kwargs: object) -> bool:
    return True


def _typedef_analysis_helper(
    *,
    usage_by_id: dict[int, _UsageStub],
    captured_display_paths: list[list[str]],
    checked_targets: list[tuple[Variable | None, tuple[str, ...], tuple[str, ...]]],
    collision_issues: list[VariableIssue],
) -> Any:
    """Analyzer stand-in for the typedef scope and collision paths."""

    def _record_collision(issue: VariableIssue) -> None:
        collision_issues.append(issue)

    def _usage_for(variable: Variable) -> _UsageStub:
        return usage_by_id[id(variable)]

    def _record_walk(moduledef: object, context: ScopeContext, path: list[str]) -> None:
        captured_display_paths.append(list(context.display_module_path))

    def _record_param_mapping(
        mapping: object,
        target_var: Variable | None,
        env: dict[str, Variable],
        context: ScopeContext,
        path: list[str],
    ) -> None:
        checked_targets.append((target_var, tuple(sorted(env)), tuple(path)))

    return SimpleNamespace(
        _analyzing_typedefs={TypedefUsageKey("", "childtype")},
        _contexts_by_module_path={},
        _append_issue=_record_collision,
        _get_usage=_usage_for,
        used_params_by_typedef={},
        param_reads_by_typedef={},
        param_ui_reads_by_typedef={},
        param_non_ui_reads_by_typedef={},
        param_writes_by_typedef={},
        _walk_moduledef=_record_walk,
        _walk_module_code=_ignore_call,
        _walk_submodules=_ignore_call,
        _walk_typedef_groupconn=_ignore_call,
        _check_param_mapping=_record_param_mapping,
    )


def _single_module_helper(usage_by_id: dict[int, _UsageStub]) -> Any:
    """Analyzer stand-in for the single-module context helpers."""

    def _usage_for(variable: Variable) -> _UsageStub:
        return usage_by_id[id(variable)]

    return SimpleNamespace(
        _walk_moduledef=_ignore_call,
        _walk_module_code=_ignore_call,
        _walk_submodules=_ignore_call,
        _get_usage=_usage_for,
        _analyzing_typedefs={TypedefUsageKey("", "childtype")},
    )


def test_walk_tail_not_expression_marks_operand_variable_reads() -> None:
    parameter = Variable(name="EnableVar", datatype=ScalarDatatype.BOOLEAN)
    bp = BasePicture(
        header=_hdr("BasePicture"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[],
        submodules=[],
        modulecode=None,
        moduledef=None,
    )
    analyzer = VariablesAnalyzer(bp)
    context = ScopeContext(
        env={"enablevar": parameter},
        param_mappings={},
        module_path=["BasePicture", "Graph"],
        display_module_path=["BasePicture<BP>", "Graph<GO>"],
    )

    analyzer._walk_tail(NotOp(operand=_varref("EnableVar")), context, context.module_path, is_ui_read=True)

    assert analyzer._get_usage(parameter).read is True
    assert analyzer._get_usage(parameter).ui_read is True


def test_variables_execution_run_typedef_and_context_helpers_cover_remaining_paths(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    log_messages: list[tuple[object, ...]] = []

    def _record_log(*args: object) -> None:
        log_messages.append(args)

    monkeypatch.setattr(
        variables_execution_module,
        "log",
        SimpleNamespace(debug=_record_log),
    )

    runner: Any = SimpleNamespace(
        _issues=[],
        context_builder=SimpleNamespace(issues=None),
        graphics_attachments=SimpleNamespace(
            bindings=(),
            composite_occurrences=(),
            composite_records=(),
            picture_display_occurrences=(),
        ),
        _limit_to_module_path=None,
        bp=BasePicture(
            header=_hdr("Root"),
            datatype_defs=[],
            moduletype_defs=[],
            localvariables=[],
            submodules=[],
            modulecode=None,
            moduledef=None,
        ),
        debug=True,
        _analysis_warnings=[],
        _selected_issue_kinds=None,
        _alias_links=[],
        _trace=_ignore_call,
        _analyze_root_scope=_ignore_call,
        _apply_alias_back_propagation=_ignore_call,
        _propagate_procedure_status_bindings=_ignore_call,
        _run_post_traversal_analyses=_ignore_call,
        _collect_basepicture_issues=_ignore_call,
        _collect_typedef_issues=_ignore_call,
        _analyze_library_dependency_typedef_usage=_ignore_call,
        _add_global_scope_minimization_issues=_ignore_call,
        _add_hidden_global_coupling_issues=_ignore_call,
        _add_high_fan_in_out_issues=_ignore_call,
        _add_unused_datatype_field_issues=_ignore_call,
    )

    assert variables_execution_module.run(runner) == []
    assert runner.context_builder.issues == []
    assert any(
        args[0] == "Variables analysis start: %s locals=%d submodules=%d typedefs=%d selected=%s"
        for args in log_messages
    )
    assert any(args[0] == "Variables analysis complete. Issues=%d" for args in log_messages)

    assert variables_execution_module._is_external_typename(
        cast(Any, SimpleNamespace(typedef_index={"knowntype": object()})),
        "UnknownType",
    )
    assert not variables_execution_module._is_external_typename(
        cast(Any, SimpleNamespace(typedef_index={"knowntype": object()})),
        "KnownType",
    )

    colliding_param = Variable(name="Shared", datatype=ScalarDatatype.INTEGER)
    input_param = Variable(name="Input", datatype=ScalarDatatype.INTEGER)
    colliding_local = Variable(name="Shared", datatype=ScalarDatatype.INTEGER)
    usage_by_id = {
        id(colliding_param): _UsageStub(),
        id(input_param): _UsageStub(read=True),
        id(colliding_local): _UsageStub(),
    }
    moduletype = ModuleTypeDef(
        name="ChildType",
        moduleparameters=[colliding_param, input_param],
        localvariables=[colliding_local],
        submodules=[],
        moduledef=None,
        modulecode=None,
    )
    captured_display_paths: list[list[str]] = []
    checked_targets: list[tuple[Variable | None, tuple[str, ...], tuple[str, ...]]] = []
    collision_issues: list[VariableIssue] = []
    helper = _typedef_analysis_helper(
        usage_by_id=usage_by_id,
        captured_display_paths=captured_display_paths,
        checked_targets=checked_targets,
        collision_issues=collision_issues,
    )

    variables_execution_module._analyze_typedef(helper, moduletype, ["Root", "TypeDef:ChildType", "Nested"])
    assert collision_issues == []
    assert captured_display_paths == []

    helper._analyzing_typedefs = set()
    variables_execution_module._analyze_typedef(helper, moduletype, ["Root", "TypeDef:ChildType", "Nested"])
    assert collision_issues == []
    assert captured_display_paths[0] == ["Root<BP>", "TypeDef:ChildType<TD>"]
    assert helper.used_params_by_typedef[TypedefUsageKey("", "childtype")] == {"input"}
    assert helper.param_reads_by_typedef[TypedefUsageKey("", "childtype")] == {"input"}
    assert helper.param_ui_reads_by_typedef[TypedefUsageKey("", "childtype")] == set()
    assert helper.param_non_ui_reads_by_typedef[TypedefUsageKey("", "childtype")] == {"input"}
    assert helper.param_writes_by_typedef[TypedefUsageKey("", "childtype")] == set()
    # A module type definition has no mapping list in the grammar, so no
    # parameter mapping is checked on the typedef itself.
    assert checked_targets == []

    read_param = Variable(name="ReadParam", datatype=ScalarDatatype.INTEGER)
    write_param = Variable(name="WriteParam", datatype=ScalarDatatype.INTEGER)
    usage_by_id[id(read_param)] = _UsageStub(read=True)
    usage_by_id[id(write_param)] = _UsageStub(written=True)
    module = SingleModule(
        header=_hdr("Worker"),
        moduledef=None,
        moduleparameters=[read_param, write_param],
        localvariables=[],
        submodules=[],
        modulecode=None,
        parametermappings=[],
    )
    context = ScopeContext(
        env={},
        param_mappings={},
        module_path=["Root"],
        display_module_path=["Root"],
        current_library=None,
        parent_context=None,
    )
    simple_helper = _single_module_helper(usage_by_id)
    used_reads, used_ui_reads, used_non_ui_reads, used_writes = (
        variables_execution_module._analyze_single_module_with_context(
            simple_helper,
            module,
            context,
            ["Root", "Worker"],
        )
    )
    assert used_reads == {"readparam"}
    assert used_ui_reads == set()
    assert used_non_ui_reads == {"readparam"}
    assert used_writes == {"writeparam"}

    variables_execution_module._analyze_typedef_with_context(
        simple_helper,
        moduletype,
        context,
        ["Root", "TypeDef:ChildType"],
    )


def test_variables_execution_apply_alias_back_propagation_covers_prefixed_and_direct_marks():
    parent = Variable(name="Parent", datatype="Payload")
    child = Variable(name="Child", datatype="Payload")
    root_parent = Variable(name="RootParent", datatype=ScalarDatatype.INTEGER)
    root_child = Variable(name="RootChild", datatype=ScalarDatatype.INTEGER)

    parent_usage = _UsageStub()
    child_usage = _UsageStub(
        field_reads={"Leaf": [("reader", 1)], "": [("reader-empty", 3)]},
        field_writes={"": [("writer", 2)], "LeafWrite": [("writer-leaf", 4)]},
        usage_locations=[(("step", 1), "read"), (("step", 2), "write")],
    )
    root_parent_usage = _UsageStub()
    root_child_usage = _UsageStub(
        field_reads={"DirectLeaf": [("root-reader", 5)]},
        field_writes={"DirectWrite": [("root-writer", 6)]},
        usage_locations=[(("root", 1), "read"), (("root", 2), "write")],
    )
    usage_by_id = {
        id(parent): parent_usage,
        id(child): child_usage,
        id(root_parent): root_parent_usage,
        id(root_child): root_child_usage,
    }

    def _alias_usage(variable: Variable) -> _UsageStub:
        return usage_by_id[id(variable)]

    helper: Any = SimpleNamespace(
        _alias_links=[(parent, child, "Alias"), (root_parent, root_child, "")],
        _get_usage=_alias_usage,
    )

    variables_execution_module._apply_alias_back_propagation(helper)

    assert parent_usage.field_reads["Alias.Leaf"] == [("reader", 1)]
    assert parent_usage.field_reads["Alias"] == [("reader-empty", 3), ("step", 1)]
    assert parent_usage.field_writes["Alias"] == [("writer", 2), ("step", 2)]
    assert parent_usage.field_writes["Alias.LeafWrite"] == [("writer-leaf", 4)]
    assert root_parent_usage.field_reads["DirectLeaf"] == [("root-reader", 5)]
    assert root_parent_usage.field_writes["DirectWrite"] == [("root-writer", 6)]
    assert root_parent_usage.usage_locations == [(("root", 1), "read"), (("root", 2), "write")]


def test_program_target_dependency_mapping_marks_external_field_reads() -> None:
    drain_dv = Variable(name="DrainDV", datatype="Z251DrainDvType")
    dependency_typedef = ModuleTypeDef(
        name="Valve2PortPB",
        moduleparameters=[Variable(name="signal", datatype="Z251DrainDvType")],
        localvariables=[],
        submodules=[],
        moduledef=None,
        modulecode=ModuleCode(
            equationblocks=[
                Equation(
                    name="ReadSignal",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[_varref("signal.V991")],  # pyright: ignore[reportArgumentType]
                )
            ],
            sequences=[],
        ),
        origin_file="Valve2PortPB.s",
        origin_lib="SupportLib",
    )
    root_typedef = ModuleTypeDef(
        name="Unit251ZType",
        moduleparameters=[],
        localvariables=[drain_dv],
        submodules=[
            ModuleTypeInstance(
                header=ModuleHeader(name="Valve", invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0)),
                moduletype_name="Valve2PortPB",
                parametermappings=[
                    ParameterMapping(
                        target=_varref("signal"),
                        source_type=MappingSource.VARIABLE,
                        is_duration=False,
                        is_source_global=False,
                        source=_varref("DrainDV.V991"),
                        source_literal=None,
                    )
                ],
            )
        ],
        moduledef=None,
        modulecode=ModuleCode(
            equationblocks=[
                Equation(
                    name="WriteDrain",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[Assignment(target=_varref("DrainDV.V991"), value=1)],
                )
            ],
            sequences=[],
        ),
        origin_file="Root.s",
        origin_lib="ProjectLib",
    )
    bp = BasePicture(
        header=_hdr("BasePicture"),
        datatype_defs=[],
        moduletype_defs=[root_typedef, dependency_typedef],
        localvariables=[],
        submodules=[],
        modulecode=None,
        moduledef=None,
        origin_file="Root.s",
        origin_lib="ProjectLib",
    )

    analyzer = VariablesAnalyzer(bp, analyzed_target_is_library=False)
    issues = analyzer.run()
    usage = analyzer._get_usage(drain_dv)

    assert usage.read is True
    assert usage.written is True
    assert usage.field_reads["V991"] == [["BasePicture", "TypeDef:Unit251ZType"]]
    assert not any(issue.kind is IssueKind.NEVER_READ and issue.variable is drain_dv for issue in issues)


def test_variable_issue_collection_datatype_field_helper_covers_remaining_branches():
    external_datatype = DataType(name="ExternalPayload", description=None, datecode=None, var_list=[])
    cast(Any, external_datatype).origin_file = "external.s"
    empty_datatype = DataType(name="EmptyPayload", description=None, datecode=None, var_list=[])
    library_datatype = DataType(
        name="LibraryPayload",
        description=None,
        datecode=None,
        var_list=[Variable(name="FieldA", datatype=ScalarDatatype.INTEGER)],
    )
    no_access_datatype = DataType(
        name="PayloadNoAccess",
        description=None,
        datecode=None,
        var_list=[Variable(name="FieldA", datatype=ScalarDatatype.INTEGER)],
    )
    partial_datatype = DataType(
        name="PayloadPartial",
        description=None,
        datecode=None,
        var_list=[
            Variable(name="Used", datatype=ScalarDatatype.INTEGER),
            Variable(name="Unused", datatype=ScalarDatatype.INTEGER),
        ],
    )
    library_var = Variable(name="LibraryVar", datatype="LibraryPayload")
    no_access_var = Variable(name="NoAccessVar", datatype="PayloadNoAccess")
    partial_var = Variable(name="PartialVar", datatype="PayloadPartial")
    missing_var = Variable(name="MissingVar", datatype="MissingPayload")
    primitive_var = Variable(name="PrimitiveVar", datatype=ScalarDatatype.INTEGER)
    usage_by_id = {
        id(library_var): _UsageStub(),
        id(no_access_var): _UsageStub(),
        id(partial_var): _UsageStub(field_reads={"Used": [("reader", 1)]}),
        id(missing_var): _UsageStub(),
        id(primitive_var): _UsageStub(),
    }
    issues: list[VariableIssue] = []

    def _record_issue(issue: VariableIssue) -> None:
        issues.append(issue)

    def _issue_usage(variable: Variable) -> _UsageStub:
        return usage_by_id[id(variable)]

    def _not_external(origin: str, origin_lib: str | None = None) -> bool:
        return origin != "external.s"

    def _leaf_paths(name: str, library: str | None = None, policy: object = None) -> list[tuple[str, ...]]:
        return {
            "EmptyPayload": [],
            "LibraryPayload": [("FieldA",)],
            "PayloadNoAccess": [("FieldA",)],
            "PayloadPartial": [("Used",), ("Unused",)],
        }.get(name, [])

    def _missing_record(name: str, library: str | None = None) -> None:
        return None

    helper: Any = SimpleNamespace(
        bp=BasePicture(
            header=_hdr("Root"),
            datatype_defs=[external_datatype, empty_datatype, library_datatype, no_access_datatype, partial_datatype],
            moduletype_defs=[
                ModuleTypeDef(
                    name="Carrier",
                    moduleparameters=[library_var],
                    localvariables=[],
                    submodules=[],
                    modulecode=None,
                    moduledef=None,
                )
            ],
            localvariables=[primitive_var, missing_var, no_access_var, partial_var],
            submodules=[],
            modulecode=None,
            moduledef=None,
        ),
        analyzed_target_is_library=True,
        append_issue=_record_issue,
        get_usage=_issue_usage,
        is_from_root_origin=_not_external,
        limit_to_module_path=None,
        _selected_issue_kinds=None,
        _is_from_root_origin=_not_external,
        type_graph=SimpleNamespace(
            iter_leaf_field_paths=_leaf_paths,
            expand_leaf_paths=_leaf_paths,
            record=_missing_record,
        ),
        _warn_ambiguous_record=_ignore_call,
        _analyzed_target_is_library=True,
        _get_usage=_issue_usage,
        _append_issue=_record_issue,
        contexts_by_module_path={},
    )

    variable_issue_collection_module._add_unused_datatype_field_issues(helper)

    by_kind = {issue.kind: issue for issue in issues}
    assert set(by_kind) == {IssueKind.UNUSED_DATATYPE, IssueKind.UNUSED_DATATYPE_FIELD}
    record_issue = by_kind[IssueKind.UNUSED_DATATYPE]
    assert isinstance(record_issue, UnusedDatatypeIssue)
    assert record_issue.datatype_name == "PayloadNoAccess"
    field_issue = by_kind[IssueKind.UNUSED_DATATYPE_FIELD]
    assert isinstance(field_issue, UnusedDatatypeFieldIssue)
    assert field_issue.datatype_name == "PayloadPartial"
    assert field_issue.field_path == "Unused"


def test_field_usage_asymmetry_detects_sibling_miswire_and_treats_whole_record_read_directionally() -> None:
    payload = Variable(name="OutletConfig", datatype="Payload")
    usage = _UsageStub(
        field_reads={"OutletProd_Def.Std": [["Root", "Reader"]]},
        field_writes={"OutletProd_X_Def.Std": [["Root", "Writer"]]},
    )
    issues: list[VariableIssue] = []

    def _record_issue(issue: VariableIssue) -> None:
        issues.append(issue)

    def _asymmetry_usage(variable: Variable) -> _UsageStub:
        return usage

    def _root_origin(origin: str, origin_lib: str | None = None) -> bool:
        return True

    def _missing_field(record_type: object, field_name: str, library: str | None = None) -> None:
        return None

    def _missing_record(record_type: object, library: str | None = None) -> None:
        return None

    def _payload_leaf_paths(name: str, library: str | None = None, policy: object = None) -> list[tuple[str, ...]]:
        return (
            [
                ("OutletProd_Def", "Std"),
                ("OutletProd_X_Def", "Std"),
            ]
            if name == "Payload"
            else []
        )

    helper: Any = SimpleNamespace(
        bp=BasePicture(
            header=_hdr("Root"),
            datatype_defs=[],
            moduletype_defs=[],
            localvariables=[payload],
            submodules=[],
            modulecode=None,
            moduledef=None,
        ),
        _selected_issue_kinds=None,
        analyzed_target_is_library=False,
        include_dependency_moduletype_usage=False,
        append_issue=_record_issue,
        get_usage=_asymmetry_usage,
        is_from_root_origin=_root_origin,
        limit_to_module_path=None,
        type_graph=SimpleNamespace(
            field=_missing_field,
            record=_missing_record,
            iter_leaf_field_paths=_payload_leaf_paths,
            expand_leaf_paths=_payload_leaf_paths,
        ),
        _warn_ambiguous_record=_ignore_call,
        contexts_by_module_path={},
    )

    variable_issue_collection_module._add_field_usage_asymmetry_issues(helper)

    assert {
        (issue.kind, issue.variable.name, issue.field_path)
        for issue in issues
        if isinstance(issue, FieldPathVariableIssue)
    } == {
        (IssueKind.FIELD_READ_ONLY, "OutletConfig", "OutletProd_Def.Std"),
        (IssueKind.FIELD_NEVER_READ, "OutletConfig", "OutletProd_X_Def.Std"),
    }

    usage.usage_locations = [cast(tuple[object, str], (["Root", "WholeAccess"], "read"))]
    issues.clear()

    variable_issue_collection_module._add_field_usage_asymmetry_issues(helper)

    assert {
        (issue.kind, issue.variable.name, issue.field_path)
        for issue in issues
        if isinstance(issue, FieldPathVariableIssue)
    } == {
        (IssueKind.FIELD_READ_ONLY, "OutletConfig", "OutletProd_Def.Std"),
    }


@pytest.mark.parametrize("constant_level", ["none", "record", "parent", "leaf"])
def test_read_only_fields_exclude_constants_but_unused_fields_remain_reported(constant_level: str) -> None:
    inner = DataType(
        name="Inner",
        description=None,
        datecode=None,
        var_list=[
            Variable(name="Flag", datatype=ScalarDatatype.BOOLEAN, const=constant_level == "leaf"),
            Variable(name="Unused", datatype=ScalarDatatype.BOOLEAN, const=True),
        ],
    )
    outer = DataType(
        name="Outer",
        description=None,
        datecode=None,
        var_list=[Variable(name="Child", datatype="Inner", const=constant_level == "parent")],
    )
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[inner, outer],
        localvariables=[
            Variable(name="Record", datatype="Outer", const=constant_level == "record"),
            Variable(name="Sink", datatype=ScalarDatatype.BOOLEAN),
        ],
        modulecode=ModuleCode(
            equationblocks=[
                Equation(
                    name="Main",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[Assignment(target=_varref("Sink"), value=_varref("Record.Child.Flag"))],
                )
            ]
        ),
    )
    analyzer = VariablesAnalyzer(
        bp, selected_issue_kinds=frozenset({IssueKind.FIELD_READ_ONLY, IssueKind.UNUSED_DATATYPE_FIELD})
    )

    analyzer.run()

    read_only = [issue for issue in analyzer.issues if issue.kind is IssueKind.FIELD_READ_ONLY]
    assert [issue.field_path for issue in read_only] == (["Child.Flag"] if constant_level == "none" else [])
    assert any(
        issue.kind is IssueKind.UNUSED_DATATYPE_FIELD and issue.field_path == "Child.Unused"
        for issue in analyzer.issues
    )


def test_variable_issue_collection_direct_global_helpers_cover_remaining_branches():
    shared = Variable(name="Shared", datatype=ScalarDatatype.INTEGER)
    issues: list[VariableIssue] = []

    def _record_issue(issue: VariableIssue) -> None:
        issues.append(issue)

    helper: Any = SimpleNamespace(
        bp=BasePicture(
            header=_hdr("Root"),
            datatype_defs=[],
            moduletype_defs=[],
            localvariables=[shared],
            submodules=[],
            modulecode=None,
            moduledef=None,
        ),
        analyzed_target_is_library=False,
        append_issue=_record_issue,
        trace=_ignore_call,
        _analyzed_target_is_library=False,
        _trace=_ignore_call,
        _append_issue=_record_issue,
    )
    helper.access_graph = SimpleNamespace(
        events=[
            _access_event(("root",), ["Root", "Short"], variable_issue_collection_module.AccessKind.READ),
            _access_event(("root", "other"), ["Root", "Other"], variable_issue_collection_module.AccessKind.READ),
            _access_event(("root", "shared"), ["Root", "Writer"], variable_issue_collection_module.AccessKind.WRITE),
            _access_event(("root", "shared"), ["Root", "Reader"], variable_issue_collection_module.AccessKind.READ),
        ]
    )

    variable_issue_collection_module._add_hidden_global_coupling_issues(helper)

    assert len(issues) == 1
    assert "Writer (write)" in (issues[0].role or "")
    assert "Reader (read)" in (issues[0].role or "")

    issues.clear()
    helper.access_graph = SimpleNamespace(
        events=[
            _access_event(
                ("root", "shared", "field"), ["Root", "Writer"], variable_issue_collection_module.AccessKind.WRITE
            ),
            _access_event(
                ("root", "shared", "otherfield"),
                ["Root", "Reader"],
                variable_issue_collection_module.AccessKind.READ,
            ),
        ]
    )
    variable_issue_collection_module._add_hidden_global_coupling_issues(helper)

    assert len(issues) == 1
    assert "Writer (write)" in (issues[0].role or "")
    assert "Reader (read)" in (issues[0].role or "")

    issues.clear()
    helper.access_graph = SimpleNamespace(
        events=[
            _access_event(("root", "shared"), ["Root", "ReaderA"], variable_issue_collection_module.AccessKind.READ),
            _access_event(("root", "shared"), ["Root", "ReaderB"], variable_issue_collection_module.AccessKind.READ),
        ]
    )
    variable_issue_collection_module._add_hidden_global_coupling_issues(helper)
    assert issues == []

    helper.access_graph = SimpleNamespace(
        events=[
            _access_event(("root",), ["Root", "Short"], variable_issue_collection_module.AccessKind.READ),
            _access_event(("root", "other"), ["Root", "Other"], variable_issue_collection_module.AccessKind.READ),
            _access_event(("root", "shared"), ["Root", "ReaderA"], variable_issue_collection_module.AccessKind.READ),
            _access_event(("root", "shared"), ["Root", "ReaderB"], variable_issue_collection_module.AccessKind.READ),
            _access_event(("root", "shared"), ["Root", "ReaderC"], variable_issue_collection_module.AccessKind.READ),
            _access_event(("root", "shared"), ["Root", "WriterA"], variable_issue_collection_module.AccessKind.WRITE),
            _access_event(("root", "shared"), ["Root", "WriterB"], variable_issue_collection_module.AccessKind.WRITE),
            _access_event(("root", "shared"), ["Root", "WriterC"], variable_issue_collection_module.AccessKind.WRITE),
        ]
    )
    variable_issue_collection_module._add_high_fan_in_out_issues(helper)

    assert len(issues) == 1
    assert "high fan-in with 3 readers" in (issues[0].role or "")
    assert "high fan-out with 3 writers" in (issues[0].role or "")

    issues.clear()
    helper.access_graph = SimpleNamespace(
        events=[
            _access_event(("root",), ["Root", "Short"], variable_issue_collection_module.AccessKind.READ),
            _access_event(("root", "shared"), ["Root", "Worker"], variable_issue_collection_module.AccessKind.READ),
            _access_event(
                ("root", "shared"), ["Root", "Worker", "Nested"], variable_issue_collection_module.AccessKind.WRITE
            ),
        ]
    )
    variable_issue_collection_module._add_global_scope_minimization_issues(helper)

    assert len(issues) == 1
    assert "module subtree Worker" in (issues[0].role or "")
    assert "Worker.Nested" in (issues[0].role or "")


def _mapped_root_variable_read_module(name: str) -> SingleModule:
    return SingleModule(
        header=_hdr(name),
        moduledef=None,
        moduleparameters=[Variable(name="Signal", datatype=ScalarDatatype.INTEGER)],
        localvariables=[Variable(name="Copy", datatype=ScalarDatatype.INTEGER)],
        submodules=[],
        modulecode=ModuleCode(
            equationblocks=[
                Equation(
                    name="Main",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[Assignment(target=_varref("Copy"), value=_varref("Signal"))],
                )
            ]
        ),
        parametermappings=[
            ParameterMapping(
                target=_varref("Signal"),
                source_type=MappingSource.VARIABLE,
                is_duration=False,
                is_source_global=False,
                source=_varref("Shared"),
                source_literal=None,
            )
        ],
    )


def test_variables_analyzer_records_root_variable_access_summary_phase_timing():
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[Variable(name="Shared", datatype=ScalarDatatype.INTEGER)],
        submodules=[_mapped_root_variable_read_module("Reader"), _mapped_root_variable_read_module("Writer")],
        modulecode=None,
        moduledef=None,
    )

    analyzer = VariablesAnalyzer(
        bp,
        selected_issue_kinds=frozenset({IssueKind.HIDDEN_GLOBAL_COUPLING}),
    )
    analyzer.run()

    phases = [entry.phase for entry in analyzer.phase_timings]
    assert "root-variable-access-summary-build" in phases
    assert "final-issue-synthesis" in phases


def test_variables_analyzer_reuse_resets_access_state_for_limited_rerun():
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[Variable(name="Shared", datatype=ScalarDatatype.INTEGER)],
        submodules=[_mapped_root_variable_read_module("ReaderA"), _mapped_root_variable_read_module("ReaderB")],
        modulecode=None,
        moduledef=None,
    )

    analyzer = VariablesAnalyzer(
        bp,
        selected_issue_kinds=frozenset({IssueKind.HIDDEN_GLOBAL_COUPLING}),
    )
    analyzer.run()

    first_paths = {event.use_module_path for event in analyzer.access_graph.events}
    assert first_paths == {("Root", "ReaderA"), ("Root", "ReaderB")}

    analyzer.run(limit_to_module_path=["Root", "ReaderA"])

    second_paths = {event.use_module_path for event in analyzer.access_graph.events}
    assert second_paths == {("Root", "ReaderA")}


def test_variable_issue_collection_collect_module_issue_helper_covers_remaining_branches():
    procedure_param = Variable(name="ProcedureParam", datatype=ScalarDatatype.INTEGER)
    ui_param = Variable(name="UiParam", datatype=ScalarDatatype.INTEGER)
    effect_param = Variable(name="EffectParam", datatype=ScalarDatatype.INTEGER)
    procedure_local = Variable(name="ProcedureLocal", datatype=ScalarDatatype.INTEGER)
    ui_local = Variable(name="UiLocal", datatype=ScalarDatatype.INTEGER)
    read_only_local = Variable(name="ReadOnlyLocal", datatype=ScalarDatatype.INTEGER)
    usage_by_id = {
        id(procedure_param): _UsageStub(read=True),
        id(ui_param): _UsageStub(is_display_only=True),
        id(effect_param): _UsageStub(read=True, written=True),
        id(procedure_local): _UsageStub(read=True),
        id(ui_local): _UsageStub(is_display_only=True),
        id(read_only_local): _UsageStub(read=True, is_read_only=True),
    }
    issues: list[tuple[IssueKind, tuple[str, ...], str, str, str | None]] = []
    module = SingleModule(
        header=_hdr("Worker"),
        moduledef=None,
        moduleparameters=[procedure_param, ui_param, effect_param],
        localvariables=[procedure_local, ui_local, read_only_local],
        submodules=[],
        modulecode=None,
        parametermappings=[],
    )

    def _record_module_issue(issue: VariableIssue) -> None:
        issues.append(
            (
                issue.kind,
                tuple(issue.module_path),
                issue.variable.name if isinstance(issue, VariableTargetIssue) else "",
                issue.role or "",
                issue.field_path if isinstance(issue, FieldPathVariableIssue) else None,
            )
        )

    def _module_usage(variable: Variable) -> _UsageStub:
        return usage_by_id[id(variable)]

    def _status_issue(variable: Variable, usage: _UsageStub) -> tuple[str, str] | None:
        if variable is procedure_param or variable is procedure_local:
            return ("procedure-status", "Status")
        return None

    helper: Any = SimpleNamespace(
        append_issue=_record_module_issue,
        _selected_issue_kinds=None,
        get_usage=_module_usage,
        has_output_effect=_false_flag,
        has_procedure_status_binding=_false_flag,
        is_const_candidate=_true_flag,
        procedure_status_issue=_status_issue,
        _get_usage=_module_usage,
        _procedure_status_issue=_status_issue,
        _has_output_effect=_false_flag,
        _has_procedure_status_binding=_false_flag,
        _is_const_candidate=_true_flag,
    )

    variable_issue_collection_module._collect_issues_from_module(helper, module, ["Root"])

    assert (
        IssueKind.PROCEDURE_STATUS,
        ("Root", "Worker"),
        "ProcedureParam",
        "procedure-status",
        "Status",
    ) in issues
    assert (
        IssueKind.WRITE_WITHOUT_EFFECT,
        ("Root", "Worker"),
        "EffectParam",
        "moduleparameter",
        None,
    ) not in issues
    assert (
        IssueKind.PROCEDURE_STATUS,
        ("Root", "Worker"),
        "ProcedureLocal",
        "procedure-status",
        "Status",
    ) in issues
    assert (IssueKind.READ_ONLY_NON_CONST, ("Root", "Worker"), "UiLocal", "localvariable", None) in issues
    assert (
        IssueKind.READ_ONLY_NON_CONST,
        ("Root", "Worker"),
        "ReadOnlyLocal",
        "localvariable",
        None,
    ) in issues


def test_variable_issue_collection_nested_scope_and_magic_helpers_cover_remaining_branches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    nested_param = Variable(name="NestedParam", datatype="OuterPayload")
    nested_local = Variable(name="NestedLocal", datatype=ScalarDatatype.INTEGER)
    child_local = Variable(name="ChildLocal", datatype=ScalarDatatype.INTEGER)
    whole_access_var = Variable(name="WholeAccess", datatype="WholePayload")
    primitive_var = Variable(name="Primitive", datatype=ScalarDatatype.INTEGER)
    missing_field_var = Variable(name="MissingField", datatype="MissingFieldPayload")
    detached_var = Variable(name="Detached", datatype="DetachedPayload")

    nested_state = {
        ("", "innerpayload"): variable_issue_collection_module._DatatypeDefinitionState(
            datatype_name="InnerPayload",
            module_path=("Root", "DataType:InnerPayload"),
            index=variable_issue_collection_module.LeafPathIndex.empty(),
            accessed_prefixes=set(),
        )
    }
    type_records = {
        "OuterPayload": SimpleNamespace(
            fields_by_key={"inner": SimpleNamespace(datatype="InnerPayload")}, library=None
        ),
        "MissingFieldPayload": SimpleNamespace(fields_by_key={}, library=None),
        "DetachedPayload": SimpleNamespace(
            fields_by_key={"inner": SimpleNamespace(datatype="DetachedInner")}, library=None
        ),
        "WholePayload": SimpleNamespace(
            fields_by_key={"inner": SimpleNamespace(datatype="InnerPayload")}, library=None
        ),
    }
    issues: list[VariableIssue] = []

    def _record_issue(issue: VariableIssue) -> None:
        issues.append(issue)

    def _root_origin(*args: object, **kwargs: object) -> bool:
        return True

    def _record_lookup(name: str, library: str | None = None) -> object | None:
        return type_records.get(name)

    def _whole_leaf_paths(name: str, library: str | None = None, policy: object = None) -> list[tuple[str, ...]]:
        return {"WholePayload": [("Inner", "Leaf")]}.get(name, [])

    def _helper_usage(variable: Variable) -> _UsageStub:
        return {
            id(whole_access_var): _UsageStub(usage_locations=[("Root", "read")]),
        }.get(id(variable), _UsageStub())

    helper: Any = SimpleNamespace(
        bp=BasePicture(
            header=_hdr("Root"),
            datatype_defs=[
                DataType(
                    name="WholePayload",
                    description=None,
                    datecode=None,
                    var_list=[Variable(name="Inner", datatype="InnerPayload")],
                )
            ],
            moduletype_defs=[],
            localvariables=[],
            submodules=[
                SingleModule(
                    header=_hdr("Parent"),
                    moduledef=None,
                    moduleparameters=[nested_param],
                    localvariables=[nested_local],
                    submodules=[
                        SingleModule(
                            header=_hdr("Child"),
                            moduledef=None,
                            moduleparameters=[],
                            localvariables=[child_local],
                            submodules=[],
                            modulecode=None,
                            parametermappings=[],
                        )
                    ],
                    modulecode=None,
                    parametermappings=[],
                )
            ],
            modulecode=None,
            moduledef=None,
        ),
        analyzed_target_is_library=False,
        include_dependency_moduletype_usage=False,
        limit_to_module_path=None,
        _selected_issue_kinds=None,
        contexts_by_module_path={},
        is_from_root_origin=_root_origin,
        type_graph=SimpleNamespace(
            record=_record_lookup,
            iter_leaf_field_paths=_whole_leaf_paths,
            expand_leaf_paths=_whole_leaf_paths,
        ),
        _warn_ambiguous_record=_ignore_call,
        get_usage=_helper_usage,
        append_issue=_record_issue,
        trace=_ignore_call,
        site_str=lambda: "Root > Worker",
    )

    collected = variable_issue_collection_module.iter_variables_for_datatype_field_analysis(helper)
    collected_names = [entry.variable.name for entry in collected]
    assert collected_names == ["NestedParam", "NestedLocal", "ChildLocal"]

    variable_issue_collection_module._record_nested_datatype_access(helper, nested_state, nested_param, "")
    variable_issue_collection_module._record_nested_datatype_access(helper, nested_state, primitive_var, "Inner")
    variable_issue_collection_module._record_nested_datatype_access(helper, nested_state, missing_field_var, "Inner")
    variable_issue_collection_module._record_nested_datatype_access(helper, nested_state, detached_var, "Inner")
    variable_issue_collection_module._record_nested_datatype_access(helper, nested_state, nested_param, "Inner")
    assert nested_state[("", "innerpayload")].accessed_prefixes == set()
    assert nested_state[("", "innerpayload")].has_whole_access is True

    helper.bp.localvariables = [whole_access_var]
    helper.bp.submodules = []
    variable_issue_collection_module._add_unused_datatype_field_issues(helper)
    assert issues == []

    summary_without_modules = variable_issue_collection_module._RootVariableAccessSummary()
    divergent_summary = variable_issue_collection_module._RootVariableAccessSummary(
        access_module_keys={("left", "branch"), ("right", "branch")},
        display_paths={
            ("left", "branch"): ("Left", "Branch"),
            ("right", "branch"): ("Right", "Branch"),
        },
    )
    shared = Variable(name="Shared", datatype=ScalarDatatype.INTEGER)
    helper.bp.localvariables = [shared]

    def _summaries(_self: object) -> dict[str, object]:
        return {"shared": summary_without_modules}

    monkeypatch.setattr(
        variable_issue_collection_module,
        "_build_root_variable_access_summaries",
        _summaries,
    )
    variable_issue_collection_module._add_global_scope_minimization_issues(helper)
    assert issues == []

    def _divergent_summaries(_self: object) -> dict[str, object]:
        return {"shared": divergent_summary}

    monkeypatch.setattr(
        variable_issue_collection_module,
        "_build_root_variable_access_summaries",
        _divergent_summaries,
    )
    variable_issue_collection_module._add_global_scope_minimization_issues(helper)
    assert issues == []

    variable_issue_collection_module._add_magic_number_issue(helper, ["Root", "Worker"], 0, None)
    variable_issue_collection_module._add_magic_number_issue(helper, ["Root", "Worker"], 7, None)

    assert len(issues) == 1
    assert issues[0].kind is IssueKind.MAGIC_NUMBER
    assert issues[0].literal_value == 7
    assert issues[0].site == "Root > Worker"
