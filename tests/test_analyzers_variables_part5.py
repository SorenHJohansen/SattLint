# ruff: noqa: F403, F405
from ._analyzers_variables_test_support import *


def test_walk_tail_children_fallback_marks_parent_scope_variable_reads() -> None:
    parent_parameter = Variable(name="p", datatype=Simple_DataType.IDENTSTRING)
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
    parent_context = ScopeContext(
        env={"p": parent_parameter},
        param_mappings={},
        module_path=["BasePicture", "Parent"],
        display_module_path=["BasePicture<BP>", "Parent<SM>"],
    )
    child_context = ScopeContext(
        env={},
        param_mappings={},
        module_path=["BasePicture", "Parent", "Child"],
        display_module_path=["BasePicture<BP>", "Parent<SM>", "Child<SM>"],
        parent_context=parent_context,
    )

    analyzer._walk_tail(SimpleNamespace(children=[_varref("p.name")]), child_context, child_context.module_path)

    assert analyzer._get_usage(parent_parameter).read is True


def test_variables_execution_run_typedef_and_context_helpers_cover_remaining_paths(monkeypatch):
    log_messages: list[tuple[object, ...]] = []
    monkeypatch.setattr(
        variables_execution_module,
        "log",
        SimpleNamespace(debug=lambda *args: log_messages.append(args)),
    )

    runner: Any = SimpleNamespace(
        _issues=[],
        context_builder=SimpleNamespace(issues=None),
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
        _alias_links=[],
        _trace=lambda *args, **kwargs: None,
        _analyze_root_scope=lambda: None,
        _apply_alias_back_propagation=lambda: None,
        _propagate_procedure_status_bindings=lambda: None,
        _run_post_traversal_analyses=lambda: None,
        _collect_basepicture_issues=lambda bp_path: None,
        _collect_typedef_issues=lambda: None,
        _analyze_library_dependency_typedef_usage=lambda: None,
        _add_naming_role_mismatch_issues=lambda: None,
        _add_global_scope_minimization_issues=lambda: None,
        _add_hidden_global_coupling_issues=lambda: None,
        _add_high_fan_in_out_issues=lambda: None,
        _add_unused_datatype_field_issues=lambda: None,
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

    colliding_param = Variable(name="Shared", datatype=Simple_DataType.INTEGER)
    input_param = Variable(name="Input", datatype=Simple_DataType.INTEGER)
    colliding_local = Variable(name="Shared", datatype=Simple_DataType.INTEGER)
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
        parametermappings=[
            ParameterMapping(
                target=_varref("Input"),
                source_type=const.KEY_VALUE,
                is_duration=False,
                is_source_global=False,
                source=None,
                source_literal=1,
            )
        ],
    )
    captured_display_paths: list[list[str]] = []
    checked_targets: list[tuple[Variable | None, tuple[str, ...], tuple[str, ...]]] = []
    collision_issues: list[VariableIssue] = []
    helper: Any = SimpleNamespace(
        _analyzing_typedefs={"childtype"},
        _contexts_by_module_path={},
        _append_issue=lambda issue: collision_issues.append(issue),
        _get_usage=lambda variable: usage_by_id[id(variable)],
        used_params_by_typedef={},
        param_reads_by_typedef={},
        param_ui_reads_by_typedef={},
        param_non_ui_reads_by_typedef={},
        param_writes_by_typedef={},
        _walk_moduledef=lambda moduledef, context, path: captured_display_paths.append(
            list(context.display_module_path)
        ),
        _walk_module_code=lambda *args, **kwargs: None,
        _walk_submodules=lambda *args, **kwargs: None,
        _walk_typedef_groupconn=lambda *args, **kwargs: None,
        _check_param_mapping=lambda mapping, target_var, env, context, path: checked_targets.append(
            (target_var, tuple(sorted(env)), tuple(path))
        ),
    )

    variables_execution_module._analyze_typedef(helper, moduletype, ["Root", "TypeDef:ChildType", "Nested"])
    assert collision_issues == []
    assert captured_display_paths == []

    helper._analyzing_typedefs = set()
    variables_execution_module._analyze_typedef(helper, moduletype, ["Root", "TypeDef:ChildType", "Nested"])
    assert collision_issues[0].kind is IssueKind.NAME_COLLISION
    assert collision_issues[0].source_variable is colliding_param
    assert captured_display_paths[0] == ["Root<BP>", "TypeDef:ChildType<TD>"]
    assert helper.used_params_by_typedef["ChildType"] == {"input"}
    assert helper.param_reads_by_typedef["childtype"] == {"input"}
    assert helper.param_ui_reads_by_typedef["childtype"] == set()
    assert helper.param_non_ui_reads_by_typedef["childtype"] == {"input"}
    assert helper.param_writes_by_typedef["childtype"] == set()
    assert checked_targets[0][0] is input_param

    read_param = Variable(name="ReadParam", datatype=Simple_DataType.INTEGER)
    write_param = Variable(name="WriteParam", datatype=Simple_DataType.INTEGER)
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
    simple_helper: Any = SimpleNamespace(
        _walk_moduledef=lambda *args, **kwargs: None,
        _walk_module_code=lambda *args, **kwargs: None,
        _walk_submodules=lambda *args, **kwargs: None,
        _get_usage=lambda variable: usage_by_id[id(variable)],
        _analyzing_typedefs={"childtype"},
    )
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
    root_parent = Variable(name="RootParent", datatype=Simple_DataType.INTEGER)
    root_child = Variable(name="RootChild", datatype=Simple_DataType.INTEGER)

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
    helper: Any = SimpleNamespace(
        _alias_links=[(parent, child, "Alias"), (root_parent, root_child, "")],
        _get_usage=lambda variable: usage_by_id[id(variable)],
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
            equations=[
                Equation(
                    name="ReadSignal",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[_varref("signal.V991")],
                )
            ],
            sequences=[],
        ),
        parametermappings=[],
        origin_file="Valve2PortPB.s",
        origin_lib="SupportLib",
    )
    root_typedef = ModuleTypeDef(
        name="KaHA251ZType",
        moduleparameters=[],
        localvariables=[drain_dv],
        submodules=[
            ModuleTypeInstance(
                header=ModuleHeader(name="Valve", invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0)),
                moduletype_name="Valve2PortPB",
                parametermappings=[
                    ParameterMapping(
                        target=_varref("signal"),
                        source_type=const.TREE_TAG_VARIABLE_NAME,
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
            equations=[
                Equation(
                    name="WriteDrain",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[(const.KEY_ASSIGN, _varref("DrainDV.V991"), 1)],
                )
            ],
            sequences=[],
        ),
        parametermappings=[],
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
    assert usage.field_reads["V991"] == [["BasePicture", "TypeDef:KaHA251ZType"]]
    assert not any(issue.kind is IssueKind.NEVER_READ and issue.variable is drain_dv for issue in issues)


def test_variable_issue_collection_datatype_field_helper_covers_remaining_branches():
    external_datatype = DataType(name="ExternalPayload", description=None, datecode=None, var_list=[])
    cast(Any, external_datatype).origin_file = "external.s"
    empty_datatype = DataType(name="EmptyPayload", description=None, datecode=None, var_list=[])
    library_datatype = DataType(
        name="LibraryPayload",
        description=None,
        datecode=None,
        var_list=[Variable(name="FieldA", datatype=Simple_DataType.INTEGER)],
    )
    no_access_datatype = DataType(
        name="PayloadNoAccess",
        description=None,
        datecode=None,
        var_list=[Variable(name="FieldA", datatype=Simple_DataType.INTEGER)],
    )
    partial_datatype = DataType(
        name="PayloadPartial",
        description=None,
        datecode=None,
        var_list=[
            Variable(name="Used", datatype=Simple_DataType.INTEGER),
            Variable(name="Unused", datatype=Simple_DataType.INTEGER),
        ],
    )
    library_var = Variable(name="LibraryVar", datatype="LibraryPayload")
    no_access_var = Variable(name="NoAccessVar", datatype="PayloadNoAccess")
    partial_var = Variable(name="PartialVar", datatype="PayloadPartial")
    missing_var = Variable(name="MissingVar", datatype="MissingPayload")
    primitive_var = Variable(name="PrimitiveVar", datatype=Simple_DataType.INTEGER)
    usage_by_id = {
        id(library_var): _UsageStub(),
        id(no_access_var): _UsageStub(),
        id(partial_var): _UsageStub(field_reads={"Used": [("reader", 1)]}),
        id(missing_var): _UsageStub(),
        id(primitive_var): _UsageStub(),
    }
    issues: list[VariableIssue] = []
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
        append_issue=lambda issue: issues.append(issue),
        get_usage=lambda variable: usage_by_id[id(variable)],
        is_from_root_origin=lambda origin, origin_lib=None: origin != "external.s",
        limit_to_module_path=None,
        _is_from_root_origin=lambda origin, origin_lib=None: origin != "external.s",
        type_graph=SimpleNamespace(
            iter_leaf_field_paths=lambda name: {
                "EmptyPayload": [],
                "LibraryPayload": [("FieldA",)],
                "PayloadNoAccess": [("FieldA",)],
                "PayloadPartial": [("Used",), ("Unused",)],
            }.get(name, []),
            record=lambda name: None,
        ),
        _analyzed_target_is_library=True,
        _get_usage=lambda variable: usage_by_id[id(variable)],
        _append_issue=lambda issue: issues.append(issue),
        contexts_by_module_path={},
    )

    variable_issue_collection_module._add_unused_datatype_field_issues(helper)

    assert len(issues) == 1
    issue = issues[0]
    assert issue.kind is IssueKind.UNUSED_DATATYPE_FIELD
    assert issue.datatype_name == "PayloadPartial"
    assert issue.field_path == "Unused"


def test_variable_issue_collection_direct_global_helpers_cover_remaining_branches():
    shared = Variable(name="Shared", datatype=Simple_DataType.INTEGER)
    issues: list[VariableIssue] = []
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
        append_issue=lambda issue: issues.append(issue),
        trace=lambda *args, **kwargs: None,
        _analyzed_target_is_library=False,
        _trace=lambda *args, **kwargs: None,
        _append_issue=lambda issue: issues.append(issue),
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
        moduleparameters=[Variable(name="Signal", datatype=Simple_DataType.INTEGER)],
        localvariables=[Variable(name="Copy", datatype=Simple_DataType.INTEGER)],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Main",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[(const.KEY_ASSIGN, _varref("Copy"), _varref("Signal"))],
                )
            ]
        ),
        parametermappings=[
            ParameterMapping(
                target=_varref("Signal"),
                source_type=const.TREE_TAG_VARIABLE_NAME,
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
        localvariables=[Variable(name="Shared", datatype=Simple_DataType.INTEGER)],
        submodules=[_mapped_root_variable_read_module("Reader"), _mapped_root_variable_read_module("Writer")],
        modulecode=None,
        moduledef=None,
    )

    analyzer = VariablesAnalyzer(
        bp,
        selected_issue_kinds=frozenset({IssueKind.HIDDEN_GLOBAL_COUPLING}),
    )
    analyzer.run()

    phases = [entry["phase"] for entry in analyzer.phase_timings]
    assert "root-variable-access-summary-build" in phases
    assert "final-issue-synthesis" in phases


def test_variables_analyzer_reuse_resets_access_state_for_limited_rerun():
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[Variable(name="Shared", datatype=Simple_DataType.INTEGER)],
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
    procedure_param = Variable(name="ProcedureParam", datatype=Simple_DataType.INTEGER)
    ui_param = Variable(name="UiParam", datatype=Simple_DataType.INTEGER)
    effect_param = Variable(name="EffectParam", datatype=Simple_DataType.INTEGER)
    procedure_local = Variable(name="ProcedureLocal", datatype=Simple_DataType.INTEGER)
    ui_local = Variable(name="UiLocal", datatype=Simple_DataType.INTEGER)
    read_only_local = Variable(name="ReadOnlyLocal", datatype=Simple_DataType.INTEGER)
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
    helper: Any = SimpleNamespace(
        append_issue=lambda issue: issues.append(
            (issue.kind, tuple(issue.module_path), issue.variable.name, issue.role, issue.field_path)
        ),
        get_usage=lambda variable: usage_by_id[id(variable)],
        has_output_effect=lambda *args, **kwargs: False,
        has_procedure_status_binding=lambda *args, **kwargs: False,
        is_const_candidate=lambda *args, **kwargs: True,
        procedure_status_issue=lambda variable, usage: (
            ("procedure-status", "Status") if variable is procedure_param or variable is procedure_local else None
        ),
        _get_usage=lambda variable: usage_by_id[id(variable)],
        _procedure_status_issue=lambda variable, usage: (
            ("procedure-status", "Status") if variable is procedure_param or variable is procedure_local else None
        ),
        _add_issue=lambda kind, path, variable, role, field_path=None: issues.append(
            (kind, tuple(path), variable.name, role, field_path)
        ),
        _has_output_effect=lambda *args, **kwargs: False,
        _has_procedure_status_binding=lambda *args, **kwargs: False,
        _is_const_candidate=lambda *args, **kwargs: True,
    )

    variable_issue_collection_module._collect_issues_from_module(helper, module, ["Root"])

    assert (
        IssueKind.PROCEDURE_STATUS,
        ("Root", "Worker"),
        "ProcedureParam",
        "procedure-status",
        "Status",
    ) in issues
    assert (IssueKind.UI_ONLY, ("Root", "Worker"), "UiParam", "moduleparameter", None) in issues
    assert (
        IssueKind.WRITE_WITHOUT_EFFECT,
        ("Root", "Worker"),
        "EffectParam",
        "moduleparameter",
        None,
    ) in issues
    assert (
        IssueKind.PROCEDURE_STATUS,
        ("Root", "Worker"),
        "ProcedureLocal",
        "procedure-status",
        "Status",
    ) in issues
    assert (IssueKind.UI_ONLY, ("Root", "Worker"), "UiLocal", "localvariable", None) in issues
    assert (
        IssueKind.READ_ONLY_NON_CONST,
        ("Root", "Worker"),
        "ReadOnlyLocal",
        "localvariable",
        None,
    ) in issues


def test_variable_issue_collection_nested_scope_and_magic_helpers_cover_remaining_branches(monkeypatch):
    nested_param = Variable(name="NestedParam", datatype="OuterPayload")
    nested_local = Variable(name="NestedLocal", datatype=Simple_DataType.INTEGER)
    child_local = Variable(name="ChildLocal", datatype=Simple_DataType.INTEGER)
    whole_access_var = Variable(name="WholeAccess", datatype="WholePayload")
    primitive_var = Variable(name="Primitive", datatype=Simple_DataType.INTEGER)
    missing_field_var = Variable(name="MissingField", datatype="MissingFieldPayload")
    detached_var = Variable(name="Detached", datatype="DetachedPayload")

    nested_state = {
        "innerpayload": {
            "accessed_prefixes": set(),
            "has_whole_access": False,
        }
    }
    type_records = {
        "OuterPayload": SimpleNamespace(fields_by_key={"inner": SimpleNamespace(datatype="InnerPayload")}),
        "MissingFieldPayload": SimpleNamespace(fields_by_key={}),
        "DetachedPayload": SimpleNamespace(fields_by_key={"inner": SimpleNamespace(datatype="DetachedInner")}),
        "WholePayload": SimpleNamespace(fields_by_key={"inner": SimpleNamespace(datatype="InnerPayload")}),
    }
    issues: list[VariableIssue] = []
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
        contexts_by_module_path={},
        is_from_root_origin=lambda *args, **kwargs: True,
        type_graph=SimpleNamespace(
            record=lambda name: type_records.get(name),
            iter_leaf_field_paths=lambda name: {"WholePayload": [("Inner", "Leaf")]}.get(name, []),
        ),
        get_usage=lambda variable: {
            id(whole_access_var): _UsageStub(usage_locations=[("Root", "read")]),
        }.get(id(variable), _UsageStub()),
        append_issue=lambda issue: issues.append(issue),
        trace=lambda *args, **kwargs: None,
        site_str=lambda: "Root > Worker",
    )

    collected = variable_issue_collection_module._iter_variables_for_datatype_field_analysis(helper)
    collected_names = [variable.name for _, variable, _, _ in collected]
    assert collected_names == ["NestedParam", "NestedLocal", "ChildLocal"]

    variable_issue_collection_module._record_nested_datatype_access(helper, nested_state, nested_param, "")
    variable_issue_collection_module._record_nested_datatype_access(helper, nested_state, primitive_var, "Inner")
    variable_issue_collection_module._record_nested_datatype_access(helper, nested_state, missing_field_var, "Inner")
    variable_issue_collection_module._record_nested_datatype_access(helper, nested_state, detached_var, "Inner")
    variable_issue_collection_module._record_nested_datatype_access(helper, nested_state, nested_param, "Inner")
    assert nested_state["innerpayload"]["accessed_prefixes"] == set()
    assert nested_state["innerpayload"]["has_whole_access"] is True

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
    shared = Variable(name="Shared", datatype=Simple_DataType.INTEGER)
    helper.bp.localvariables = [shared]

    monkeypatch.setattr(
        variable_issue_collection_module,
        "_build_root_variable_access_summaries",
        lambda _self: {"shared": summary_without_modules},
    )
    variable_issue_collection_module._add_global_scope_minimization_issues(helper)
    assert issues == []

    monkeypatch.setattr(
        variable_issue_collection_module,
        "_build_root_variable_access_summaries",
        lambda _self: {"shared": divergent_summary},
    )
    variable_issue_collection_module._add_global_scope_minimization_issues(helper)
    assert issues == []

    variable_issue_collection_module._add_magic_number_issue(helper, ["Root", "Worker"], 0, None)
    variable_issue_collection_module._add_magic_number_issue(helper, ["Root", "Worker"], 7, None)

    assert len(issues) == 1
    assert issues[0].kind is IssueKind.MAGIC_NUMBER
    assert issues[0].literal_value == 7
    assert issues[0].site == "Root > Worker"
