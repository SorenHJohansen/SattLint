# pyright: reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportPrivateUsage=false, reportArgumentType=false, reportOptionalMemberAccess=false, reportUnusedImport=false

import pytest
from sattline_parser.ast import (
    AssignClause,
    Assignment,
    BoolOp,
    EnableClause,
    FrameModule,
    FuncCall,
    FuncCallStmt,
    IfStmt,
    MappingSource,
    ModuleArguments,
    ProcedureCall,
    Sequence,
    SFCAlternative,
    SFCCodeBlocks,
    SFCFork,
    SFCParallel,
    SFCStep,
    SFCSubsequence,
    SFCTransition,
    SFCTransitionSub,
    VarTail,
)

from tests.helpers.analyzers_variables_support import *


def test_interact_enable_expression_counts_mapped_parent_input_as_read() -> None:
    enable = Variable(name="Enable", datatype=Simple_DataType.BOOLEAN)
    child_type = ModuleTypeDef(
        name="CoreReal",
        moduleparameters=[enable],
        moduledefs=[
            ModuleDef(
                interact_objects=[
                    InteractObject(
                        type="TextBox_",
                        properties={
                            "body": [
                                EnableClause(
                                    enabled=True,
                                    tail=BoolOp(op="AND", operands=(_varref("Enable"), True)),
                                )
                            ]
                        },
                    )
                ]
            )
        ],
        origin_file="LibraryRoot.x",
        origin_lib="ProjectLib",
    )
    enable_privilege = Variable(name="EnablePrivilege", datatype=Simple_DataType.BOOLEAN)
    parent_type = ModuleTypeDef(
        name="EPDisp",
        moduleparameters=[enable_privilege],
        submodules=[
            ModuleTypeInstance(
                header=_hdr("ParameterDisplay"),
                moduletype_name="CoreReal",
                parametermappings=[
                    ParameterMapping(
                        target=_varref("Enable"),
                        source_type=MappingSource.VARIABLE,
                        is_duration=False,
                        is_source_global=False,
                        source=_varref("EnablePrivilege"),
                        source_literal=None,
                    )
                ],
            )
        ],
        origin_file="LibraryRoot.x",
        origin_lib="ProjectLib",
    )
    bp = BasePicture(
        header=_hdr("BasePicture"),
        moduletype_defs=[parent_type, child_type],
        origin_file="LibraryRoot.x",
        origin_lib="ProjectLib",
    )

    analyzer = VariablesAnalyzer(bp, analyzed_target_is_library=True)
    analyzer.run()

    assert not any(issue.kind is IssueKind.UNUSED and issue.variable is enable_privilege for issue in analyzer.issues)


@pytest.mark.parametrize("consumed", [False, True])
def test_written_local_consumed_by_dependency_has_external_effect(consumed: bool) -> None:
    local = Variable(name="Request", datatype=Simple_DataType.INTEGER)
    dependency = ModuleTypeDef(
        name="Consumer",
        origin_file="Dependency.s",
        moduleparameters=[Variable(name="Input", datatype=Simple_DataType.INTEGER)],
        localvariables=[Variable(name="Observed", datatype=Simple_DataType.INTEGER)],
        modulecodes=[
            ModuleCode(
                equationblocks=[
                    Equation(
                        name="Consume",
                        position=(0.0, 0.0),
                        size=(1.0, 1.0),
                        code=[
                            Assignment(
                                target=_varref("Observed"),
                                value=_varref("Input") if consumed else IntLiteral(0),
                            )
                        ],
                    )
                ]
            )
        ],
    )
    parent = ModuleTypeDef(
        name="Parent",
        origin_file="Root.s",
        localvariables=[local, Variable(name="Scratch", datatype=Simple_DataType.INTEGER)],
        modulecodes=[
            ModuleCode(
                equationblocks=[
                    Equation(
                        name="Generate",
                        position=(0.0, 0.0),
                        size=(1.0, 1.0),
                        code=[
                            Assignment(target=_varref("Request"), value=IntLiteral(2)),
                            Assignment(target=_varref("Scratch"), value=_varref("Request")),
                        ],
                    )
                ]
            )
        ],
        submodules=[
            ModuleTypeInstance(
                header=_hdr("ConsumerInstance"),
                moduletype_name="Consumer",
                parametermappings=[
                    ParameterMapping(
                        target=_varref("Input"),
                        source=_varref("Request"),
                        source_type=MappingSource.VARIABLE,
                        is_source_global=False,
                        is_duration=False,
                        source_literal=None,
                    )
                ],
            )
        ],
    )
    bp = BasePicture(header=_hdr("Root"), origin_file="Root.s", moduletype_defs=[parent, dependency])
    report = analyze_variables(
        bp, analyzed_target_is_library=True, selected_issue_kinds={IssueKind.WRITE_WITHOUT_EFFECT}
    )
    no_effect = any(issue.kind is IssueKind.WRITE_WITHOUT_EFFECT and issue.variable is local for issue in report.issues)
    assert no_effect is not consumed


@pytest.mark.parametrize("display_kind", ["text", "interact", "header"])
def test_display_read_is_an_observable_effect(display_kind: str) -> None:
    source = Variable(name="Source", datatype=Simple_DataType.BOOLEAN)
    shown = Variable(name="Shown", datatype=Simple_DataType.BOOLEAN)
    dead = Variable(name="Dead", datatype=Simple_DataType.BOOLEAN)
    parent = ModuleTypeDef(
        name="Display",
        origin_file="Root.s",
        localvariables=[source, shown, dead, Variable(name="Scratch", datatype=Simple_DataType.BOOLEAN)],
        modulecodes=[
            ModuleCode(
                equationblocks=[
                    Equation(
                        name="Calculate",
                        position=(0.0, 0.0),
                        size=(1.0, 1.0),
                        code=[
                            Assignment(target=_varref("Source"), value=True),
                            Assignment(target=_varref("Shown"), value=_varref("Source")),
                            Assignment(target=_varref("Dead"), value=True),
                            Assignment(target=_varref("Scratch"), value=_varref("Dead")),
                        ],
                    )
                ]
            )
        ],
    )
    if display_kind == "text":
        parent.moduledefs = [
            ModuleDef(graph_objects=[GraphObject("TextObject", properties={"text_vars": [_varref("Shown")]})])
        ]
    elif display_kind == "interact":
        parent.moduledefs = [
            ModuleDef(
                interact_objects=[
                    InteractObject("TextBox_", properties={"tails": [VarTail(direction="in", value="Shown")]})
                ]
            )
        ]
    else:
        header = _hdr("Visible")
        header.arguments = ModuleArguments(enable=EnableClause(enabled=True, tail=_varref("Shown")))
        parent.submodules = [FrameModule(header=header)]
    report = analyze_variables(
        BasePicture(header=_hdr("Root"), origin_file="Root.s", moduletype_defs=[parent]),
        analyzed_target_is_library=True,
        selected_issue_kinds={IssueKind.WRITE_WITHOUT_EFFECT},
    )
    flagged = [issue.variable for issue in report.issues if issue.kind is IssueKind.WRITE_WITHOUT_EFFECT]
    assert source not in flagged
    assert shown not in flagged
    assert dead in flagged


@pytest.mark.parametrize("alternative", [False, True])
@pytest.mark.parametrize("observable", [False, True])
def test_transition_guard_contributes_to_following_step_effect(alternative: bool, observable: bool) -> None:
    guard = Variable(name="Ready", datatype=Simple_DataType.BOOLEAN)
    following = [
        SFCTransition(name="Proceed", condition=_varref("Ready")),
        SFCStep(
            kind="step",
            name="Run",
            code=SFCCodeBlocks(
                active=[Assignment(target=_varref("Output" if observable else "Scratch"), value=True)],
            ),
        ),
    ]
    parent = ModuleTypeDef(
        name="Phase",
        origin_file="Root.s",
        moduleparameters=[Variable(name="Output", datatype=Simple_DataType.BOOLEAN)],
        localvariables=[guard, Variable(name="Scratch", datatype=Simple_DataType.BOOLEAN)],
        modulecodes=[
            ModuleCode(
                sequences=[
                    Sequence(
                        name="PhaseSequence",
                        type="sequence",
                        position=(0.0, 0.0),
                        size=(1.0, 1.0),
                        code=[
                            SFCStep(
                                kind="init",
                                name="Start",
                                code=SFCCodeBlocks(
                                    enter=[Assignment(target=_varref("Ready"), value=True)],
                                ),
                            ),
                            *([SFCAlternative(branches=[following, []])] if alternative else following),
                        ],
                    )
                ]
            )
        ],
    )
    report = analyze_variables(
        BasePicture(header=_hdr("Root"), origin_file="Root.s", moduletype_defs=[parent]),
        analyzed_target_is_library=True,
        selected_issue_kinds={IssueKind.WRITE_WITHOUT_EFFECT},
    )
    flagged = any(issue.kind is IssueKind.WRITE_WITHOUT_EFFECT and issue.variable is guard for issue in report.issues)
    assert flagged is not observable


@pytest.mark.parametrize("observable", [False, True])
@pytest.mark.parametrize("nested", [False, True])
def test_fallthrough_guard_reaches_joined_step_but_jump_guard_does_not(observable: bool, nested: bool) -> None:
    ready = Variable(name="Ready", datatype=Simple_DataType.BOOLEAN)
    leave = Variable(name="Leave", datatype=Simple_DataType.BOOLEAN)
    phase = ModuleTypeDef(
        name="Phase",
        origin_file="Root.s",
        moduleparameters=[Variable(name="Output", datatype=Simple_DataType.BOOLEAN)],
        localvariables=[ready, leave, Variable(name="Scratch", datatype=Simple_DataType.BOOLEAN)],
        modulecodes=[
            ModuleCode(
                sequences=[
                    Sequence(
                        name="PhaseSequence",
                        type="sequence",
                        position=(0.0, 0.0),
                        size=(1.0, 1.0),
                        code=[
                            SFCStep(
                                kind="init",
                                name="Start",
                                code=SFCCodeBlocks(
                                    enter=[
                                        Assignment(target=_varref("Ready"), value=True),
                                        Assignment(target=_varref("Leave"), value=True),
                                    ]
                                ),
                            ),
                            SFCAlternative(
                                branches=[
                                    [
                                        SFCSubsequence(
                                            name="Nested",
                                            body=[SFCTransition(name="ReadyToProceed", condition=_varref("Ready"))],
                                        )
                                    ]
                                    if nested
                                    else [SFCTransition(name="ReadyToProceed", condition=_varref("Ready"))],
                                    [
                                        SFCTransition(
                                            name="TryAgain",
                                            condition=_varref("Leave"),
                                            fork=SFCFork(targets=("Start",)),
                                        )
                                    ],
                                ]
                            ),
                            SFCStep(
                                kind="step",
                                name="Run",
                                code=SFCCodeBlocks(
                                    active=[
                                        Assignment(target=_varref("Output" if observable else "Scratch"), value=True),
                                    ]
                                ),
                            ),
                        ],
                    )
                ]
            )
        ],
    )
    report = analyze_variables(
        BasePicture(header=_hdr("Root"), origin_file="Root.s", moduletype_defs=[phase]),
        analyzed_target_is_library=True,
        selected_issue_kinds={IssueKind.WRITE_WITHOUT_EFFECT},
    )
    flagged = [issue.variable for issue in report.issues if issue.kind is IssueKind.WRITE_WITHOUT_EFFECT]
    assert (ready in flagged) is not observable
    assert leave in flagged


@pytest.mark.parametrize("container", ["parallel", "subsequence", "transition-sub"])
@pytest.mark.parametrize("observable", [False, True])
def test_nested_sequence_guard_reaches_following_output(container: str, observable: bool) -> None:
    guard = Variable(name="Ready", datatype=Simple_DataType.BOOLEAN)
    body = [SFCTransition(name="ReadyToProceed", condition=_varref("Ready"))]
    if container == "parallel":
        node = SFCParallel(branches=[body, []])
    elif container == "subsequence":
        node = SFCSubsequence(name="Nested", body=body)
    else:
        node = SFCTransitionSub(name="Nested", body=body)
    phase = ModuleTypeDef(
        name="Phase",
        origin_file="Root.s",
        localvariables=[guard, Variable(name="Scratch", datatype=Simple_DataType.BOOLEAN)],
        moduleparameters=[Variable(name="Output", datatype=Simple_DataType.BOOLEAN)],
        modulecodes=[
            ModuleCode(
                sequences=[
                    Sequence(
                        name="PhaseSequence",
                        type="sequence",
                        position=(0.0, 0.0),
                        size=(1.0, 1.0),
                        code=[
                            SFCStep(
                                kind="init",
                                name="Start",
                                code=SFCCodeBlocks(enter=[Assignment(target=_varref("Ready"), value=True)]),
                            ),
                            node,
                            SFCStep(
                                kind="step",
                                name="Run",
                                code=SFCCodeBlocks(
                                    active=[
                                        Assignment(target=_varref("Output" if observable else "Scratch"), value=True)
                                    ]
                                ),
                            ),
                        ],
                    )
                ]
            )
        ],
    )
    report = analyze_variables(
        BasePicture(header=_hdr("Root"), origin_file="Root.s", moduletype_defs=[phase]),
        analyzed_target_is_library=True,
        selected_issue_kinds={IssueKind.WRITE_WITHOUT_EFFECT},
    )
    flagged = any(issue.kind is IssueKind.WRITE_WITHOUT_EFFECT and issue.variable is guard for issue in report.issues)
    assert flagged is not observable


@pytest.mark.parametrize("procedure", [False, True])
@pytest.mark.parametrize("branch_location", ["first", "else", "nested"])
def test_condition_controlling_output_has_observable_effect(procedure: bool, branch_location: str) -> None:
    flag = Variable(name="Request", datatype=Simple_DataType.BOOLEAN)
    dead = Variable(name="Dead", datatype=Simple_DataType.BOOLEAN)
    if procedure:
        body = FuncCallStmt(
            call=FuncCall(name="CopyVariable", args=(_varref("Source"), _varref("Output"), _varref("Status")))
        )
    else:
        body = Assignment(target=_varref("Output"), value=True)
    condition = BoolOp(op="AND", operands=(_varref("Request"), True))
    branch = IfStmt(branches=((condition, (body,)),), else_block=None)
    if branch_location == "else":
        branch = IfStmt(branches=((condition, ()),), else_block=(body,))
    elif branch_location == "nested":
        branch = IfStmt(branches=((True, (branch,)),), else_block=None)
    parent = ModuleTypeDef(
        name="Parent",
        origin_file="Root.s",
        moduleparameters=[Variable(name="Output", datatype=Simple_DataType.BOOLEAN)],
        localvariables=[
            flag,
            dead,
            Variable(name="Source", datatype=Simple_DataType.BOOLEAN),
            Variable(name="Status", datatype=Simple_DataType.INTEGER),
            Variable(name="Scratch", datatype=Simple_DataType.BOOLEAN),
        ],
        modulecodes=[
            ModuleCode(
                equationblocks=[
                    Equation(
                        name="Control",
                        position=(0.0, 0.0),
                        size=(1.0, 1.0),
                        code=[
                            Assignment(target=_varref("Request"), value=True),
                            branch,
                            Assignment(target=_varref("Dead"), value=True),
                            Assignment(target=_varref("Scratch"), value=_varref("Dead")),
                        ],
                    )
                ]
            )
        ],
    )
    report = analyze_variables(
        BasePicture(header=_hdr("Root"), origin_file="Root.s", moduletype_defs=[parent]),
        analyzed_target_is_library=True,
        selected_issue_kinds={IssueKind.WRITE_WITHOUT_EFFECT},
    )
    no_effect = [issue.variable for issue in report.issues if issue.kind is IssueKind.WRITE_WITHOUT_EFFECT]
    assert flag not in no_effect
    assert dead in no_effect


def test_library_typedef_moduleparameter_unused_fields_are_suppressed():
    record_type = DataType(
        name="RecType",
        description=None,
        datecode=None,
        var_list=[
            Variable(name="Used", datatype=Simple_DataType.INTEGER),
            Variable(name="Unused", datatype=Simple_DataType.INTEGER),
        ],
        origin_file="LibraryRoot.x",
        origin_lib="ProjectLib",
    )

    exported = ModuleTypeDef(
        name="ExportedType",
        moduleparameters=[Variable(name="p", datatype="RecType")],
        localvariables=[Variable(name="sink", datatype=Simple_DataType.INTEGER)],
        submodules=[],
        moduledefs=[],
        modulecodes=[
            ModuleCode(
                equationblocks=[
                    Equation(
                        name="Main",
                        position=(0.0, 0.0),
                        size=(1.0, 1.0),
                        code=[Assignment(target=_varref("sink"), value=_varref("p.Used"))],
                    )
                ]
            )
        ],
        parametermappings=[],
        origin_file="LibraryRoot.x",
        origin_lib="ProjectLib",
    )

    bp = BasePicture(
        header=_hdr("BasePicture"),
        datatype_defs=[record_type],
        moduletype_defs=[exported],
        localvariables=[],
        submodules=[],
        modulecodes=[],
        moduledefs=[],
        origin_file="LibraryRoot.x",
        origin_lib="ProjectLib",
    )

    program_analyzer = VariablesAnalyzer(
        bp,
        analyzed_target_is_library=False,
        selected_issue_kinds=frozenset(DATATYPE_FIELD_ANALYSIS_KINDS),
    )
    program_analyzer.run()
    assert any(
        issue.kind is IssueKind.UNUSED_DATATYPE_FIELD
        and issue.datatype_name == "RecType"
        and issue.field_path == "Unused"
        for issue in program_analyzer.issues
    )

    library_analyzer = VariablesAnalyzer(
        bp,
        analyzed_target_is_library=True,
        selected_issue_kinds=frozenset(DATATYPE_FIELD_ANALYSIS_KINDS),
    )
    library_analyzer.run()
    assert not any(
        issue.kind is IssueKind.UNUSED_DATATYPE_FIELD
        and issue.datatype_name == "RecType"
        and issue.field_path == "Unused"
        for issue in library_analyzer.issues
    )


def test_library_typedef_local_used_via_child_interact_coordinate_tail_is_not_unused():
    child_param = Variable(name="xSize", datatype=Simple_DataType.REAL)
    child_type = ModuleTypeDef(
        name="ButtonType",
        moduleparameters=[child_param],
        localvariables=[],
        submodules=[],
        moduledefs=[
            ModuleDef(
                interact_objects=[
                    InteractObject(
                        type=const.GRAMMAR_VALUE_COMBUT,
                        properties={
                            "coords": [((0.0, 0.0), (1.0, 1.0))],
                            "tails": [VarTail(direction="in", value="xSize")],
                            "body": [AssignClause(name="ButtonType", value=0, tail=None)],
                        },
                    )
                ]
            )
        ],
        modulecodes=[],
        parametermappings=[],
        origin_file="LibraryRoot.x",
        origin_lib="ProjectLib",
    )

    x_size = Variable(name="XSize", datatype=Simple_DataType.REAL)
    parent_type = ModuleTypeDef(
        name="EluMasterLinie",
        moduleparameters=[],
        localvariables=[x_size],
        submodules=[
            ModuleTypeInstance(
                header=_hdr("Button"),
                moduletype_name="ButtonType",
                parametermappings=[
                    ParameterMapping(
                        target=_varref("xSize"),
                        source_type=MappingSource.VARIABLE,
                        is_duration=False,
                        is_source_global=False,
                        source=_varref("XSize"),
                        source_literal=None,
                    )
                ],
            )
        ],
        moduledefs=[],
        modulecodes=[],
        parametermappings=[],
        origin_file="LibraryRoot.x",
        origin_lib="ProjectLib",
    )

    bp = BasePicture(
        header=_hdr("BasePicture"),
        datatype_defs=[],
        moduletype_defs=[parent_type, child_type],
        localvariables=[],
        submodules=[],
        modulecodes=[],
        moduledefs=[],
        origin_file="LibraryRoot.x",
        origin_lib="ProjectLib",
    )

    analyzer = VariablesAnalyzer(bp, analyzed_target_is_library=True)
    analyzer.run()

    assert not any(
        issue.kind is IssueKind.UNUSED
        and issue.variable is x_size
        and issue.module_path == ["BasePicture", "TypeDef:EluMasterLinie"]
        for issue in analyzer.issues
    )


def test_library_typedef_local_used_via_child_combutproc_togglewindow_arg_is_not_unused():
    child_param = Variable(name="xSize", datatype=Simple_DataType.REAL)
    child_type = ModuleTypeDef(
        name="RecipePicklistSecond",
        moduleparameters=[child_param],
        localvariables=[],
        submodules=[],
        moduledefs=[
            ModuleDef(
                interact_objects=[
                    InteractObject(
                        type=const.GRAMMAR_VALUE_COMBUTPROC,
                        properties={
                            "coords": [((0.0, 0.0), (1.0, 1.0))],
                            "procedure": ProcedureCall(name="ToggleWindow", args=(_varref("xSize"),)),
                        },
                    )
                ]
            )
        ],
        modulecodes=[],
        parametermappings=[],
        origin_file="LibraryRoot.x",
        origin_lib="ProjectLib",
    )

    x_size = Variable(name="XSize", datatype=Simple_DataType.REAL)
    parent_type = ModuleTypeDef(
        name="EluMasterLinie",
        moduleparameters=[],
        localvariables=[x_size],
        submodules=[
            ModuleTypeInstance(
                header=_hdr("Picklist"),
                moduletype_name="RecipePicklistSecond",
                parametermappings=[
                    ParameterMapping(
                        target=_varref("xSize"),
                        source_type=MappingSource.VARIABLE,
                        is_duration=False,
                        is_source_global=False,
                        source=_varref("XSize"),
                        source_literal=None,
                    )
                ],
            )
        ],
        moduledefs=[],
        modulecodes=[],
        parametermappings=[],
        origin_file="LibraryRoot.x",
        origin_lib="ProjectLib",
    )

    bp = BasePicture(
        header=_hdr("BasePicture"),
        datatype_defs=[],
        moduletype_defs=[parent_type, child_type],
        localvariables=[],
        submodules=[],
        modulecodes=[],
        moduledefs=[],
        origin_file="LibraryRoot.x",
        origin_lib="ProjectLib",
    )

    analyzer = VariablesAnalyzer(bp, analyzed_target_is_library=True)
    analyzer.run()

    assert not any(
        issue.kind is IssueKind.UNUSED
        and issue.variable is x_size
        and issue.module_path == ["BasePicture", "TypeDef:EluMasterLinie"]
        for issue in analyzer.issues
    )
