# pyright: reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportPrivateUsage=false, reportArgumentType=false, reportOptionalMemberAccess=false, reportUnusedImport=false
# ruff: noqa: F403, F405
from types import SimpleNamespace

from ._analyzers_variables_test_support import *


def test_iter_variables_for_datatype_field_analysis_includes_context_only_variables():
    root_var = Variable(name="RootTexts", datatype="StepTextType")
    context_var = Variable(name="StepText", datatype="StepTextType")
    bp = BasePicture(
        header=_hdr("BasePicture"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[root_var],
        submodules=[],
        modulecode=None,
        moduledef=None,
        origin_file="KaHAXDiluteLib.s",
        origin_lib="KaHAXDiluteLib",
    )
    fake_analyzer = SimpleNamespace(
        bp=bp,
        limit_to_module_path=None,
        analyzed_target_is_library=True,
        include_dependency_moduletype_usage=True,
        contexts_by_module_path={
            ("BasePicture", "Nested", "Display"): SimpleNamespace(
                env={"steptext": context_var},
                param_mappings={"steptext": (root_var, "", ["BasePicture"], ["BasePicture"])},
            )
        },
        is_from_root_origin=lambda origin_file, origin_lib=None: True,
    )

    collected = variable_issue_collection_module.iter_variables_for_datatype_field_analysis(fake_analyzer)

    assert any(variable is root_var for _path, variable, _role, _root_owned in collected)
    assert any(
        variable is context_var and path == ["BasePicture", "Nested", "Display"] and role == "moduleparameter"
        for path, variable, role, _root_owned in collected
    )


def test_unused_datatype_fields_include_context_only_variable_usage():
    root_var = Variable(name="RootTexts", datatype="StepTextType")
    context_var = Variable(name="StepText", datatype="StepTextType")
    record_type = DataType(
        name="StepTextType",
        description=None,
        datecode=None,
        var_list=[
            Variable(name="CleanCycle", datatype=Simple_DataType.STRING),
            Variable(name="WaitCleanCycle", datatype=Simple_DataType.STRING),
        ],
        origin_file="KaHAXDiluteLib.s",
        origin_lib="KaHAXDiluteLib",
    )
    bp = BasePicture(
        header=_hdr("BasePicture"),
        datatype_defs=[record_type],
        moduletype_defs=[],
        localvariables=[root_var],
        submodules=[],
        modulecode=None,
        moduledef=None,
        origin_file="KaHAXDiluteLib.s",
        origin_lib="KaHAXDiluteLib",
    )
    usage_by_id = {
        id(root_var): _UsageStub(field_reads={"WaitCleanCycle": [object()]}),
        id(context_var): _UsageStub(field_reads={"CleanCycle": [object()]}),
    }
    issues: list[VariableIssue] = []
    fake_analyzer = SimpleNamespace(
        bp=bp,
        limit_to_module_path=None,
        analyzed_target_is_library=False,
        include_dependency_moduletype_usage=False,
        contexts_by_module_path={
            ("BasePicture", "Nested", "Display"): SimpleNamespace(
                env={"steptext": context_var},
                param_mappings={"steptext": (root_var, "", ["BasePicture"], ["BasePicture"])},
            )
        },
        type_graph=SimpleNamespace(
            iter_leaf_field_paths=lambda _datatype: [("CleanCycle",), ("WaitCleanCycle",)],
            record=lambda _datatype: None,
        ),
        is_from_root_origin=lambda origin_file, origin_lib=None: True,
        get_usage=lambda variable: usage_by_id[id(variable)],
        append_issue=issues.append,
    )

    variable_issue_collection_module._add_unused_datatype_field_issues(fake_analyzer)

    assert not any(issue.kind is IssueKind.UNUSED_DATATYPE_FIELD for issue in issues)


def test_analyze_variables_library_target_counts_dependency_typedef_field_reads():
    from sattlint.analyzers.variables import analyze_variables  # noqa: PLC0415

    op_text_type = DataType(
        name="ApplOpTxtType",
        description=None,
        datecode=None,
        var_list=[
            Variable(name="LSH", datatype=Simple_DataType.STRING),
            Variable(name="DrainPipe", datatype=Simple_DataType.STRING),
        ],
        origin_file="KaHAApplSupportLib.s",
        origin_lib="KaHAApplSupportLib",
    )
    dependency_typedef = ModuleTypeDef(
        name="ConsumerType",
        moduleparameters=[],
        localvariables=[
            Variable(name="OPText", datatype="ApplOpTxtType"),
            Variable(name="Sink", datatype=Simple_DataType.STRING),
        ],
        submodules=[],
        moduledef=None,
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="ReadField",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (
                            const.KEY_ASSIGN,
                            _varref("Sink"),
                            _varref("OPText.LSH"),
                        )
                    ],
                )
            ]
        ),
        parametermappings=[],
        origin_file="KaHAApplLib.s",
        origin_lib="KaHAApplLib",
    )
    support_typedef = ModuleTypeDef(
        name="SupportType",
        moduleparameters=[],
        localvariables=[
            Variable(name="OPText", datatype="ApplOpTxtType"),
            Variable(name="Sink", datatype=Simple_DataType.STRING),
        ],
        submodules=[ModuleTypeInstance(header=_hdr("Consumer"), moduletype_name="ConsumerType", parametermappings=[])],
        moduledef=None,
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="ReadRootField",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (
                            const.KEY_ASSIGN,
                            _varref("Sink"),
                            _varref("OPText.DrainPipe"),
                        )
                    ],
                )
            ],
            sequences=[],
        ),
        parametermappings=[],
        origin_file="KaHAApplSupportLib.s",
        origin_lib="KaHAApplSupportLib",
    )
    bp = BasePicture(
        header=_hdr("BasePicture"),
        datatype_defs=[op_text_type],
        moduletype_defs=[support_typedef, dependency_typedef],
        localvariables=[],
        submodules=[],
        modulecode=None,
        moduledef=None,
        origin_file="KaHAApplSupportLib.s",
        origin_lib="KaHAApplSupportLib",
    )

    report = analyze_variables(bp, analyzed_target_is_library=True)

    unused_fields = {
        issue.field_path
        for issue in report.issues
        if issue.kind is IssueKind.UNUSED_DATATYPE_FIELD and issue.datatype_name == "ApplOpTxtType"
    }

    assert "LSH" not in unused_fields
    assert unused_fields == set()


def test_analyze_variables_library_target_counts_reverse_consumer_typedef_field_reads():
    from sattlint.analyzers.variables import analyze_variables  # noqa: PLC0415

    op_text_type = DataType(
        name="ApplOpTxtType",
        description=None,
        datecode=None,
        var_list=[
            Variable(name="LSH", datatype=Simple_DataType.STRING),
            Variable(name="DrainPipe", datatype=Simple_DataType.STRING),
        ],
        origin_file="KaHAApplSupportLib.s",
        origin_lib="KaHAApplSupportLib",
    )
    support_typedef = ModuleTypeDef(
        name="SupportType",
        moduleparameters=[],
        localvariables=[Variable(name="OPText", datatype="ApplOpTxtType")],
        submodules=[],
        moduledef=None,
        modulecode=ModuleCode(equations=[], sequences=[]),
        parametermappings=[],
        origin_file="KaHAApplSupportLib.s",
        origin_lib="KaHAApplSupportLib",
    )
    consumer_typedef = ModuleTypeDef(
        name="ConsumerType",
        moduleparameters=[],
        localvariables=[
            Variable(name="OPText", datatype="ApplOpTxtType"),
            Variable(name="Sink", datatype=Simple_DataType.STRING),
        ],
        submodules=[],
        moduledef=None,
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="ReadLSH",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (
                            const.KEY_ASSIGN,
                            _varref("Sink"),
                            _varref("OPText.LSH"),
                        )
                    ],
                )
            ],
            sequences=[],
        ),
        parametermappings=[],
        origin_file="KaHAApplLib.s",
        origin_lib="KaHAApplLib",
    )
    bp = BasePicture(
        header=_hdr("BasePicture"),
        datatype_defs=[op_text_type],
        moduletype_defs=[support_typedef, consumer_typedef],
        localvariables=[],
        submodules=[],
        modulecode=None,
        moduledef=None,
        origin_file="KaHAApplSupportLib.s",
        origin_lib="KaHAApplSupportLib",
    )

    report = analyze_variables(bp, analyzed_target_is_library=True)

    unused_fields = {
        issue.field_path
        for issue in report.issues
        if issue.kind is IssueKind.UNUSED_DATATYPE_FIELD and issue.datatype_name == "ApplOpTxtType"
    }

    assert "LSH" not in unused_fields
    assert unused_fields == {"DrainPipe"}
