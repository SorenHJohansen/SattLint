# pyright: reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportPrivateUsage=false, reportArgumentType=false, reportOptionalMemberAccess=false, reportUnusedImport=false

from dataclasses import replace

import pytest
from sattline_parser import parse_source_text as parser_core_parse_source_text
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
from sattline_parser.grammar import constants as const
from sattline_parser.models.ast_model import (
    BasePicture,
    DataType,
    Equation,
    GraphObject,
    InteractObject,
    IntLiteral,
    ModuleCode,
    ModuleDef,
    ModuleTypeDef,
    ModuleTypeInstance,
    ParameterMapping,
    ScalarDatatype,
    Variable,
)

from sattlint.analyzers.variables import (
    IssueKind,
    VariablesAnalyzer,
    analyze_variables,
)
from sattlint.analyzers.variables._variables_contracts import TypedefUsageKey
from sattlint.reporting.variables_report import DATATYPE_FIELD_ANALYSIS_KINDS
from tests.helpers.variable_test_support import (
    hdr as _hdr,
)
from tests.helpers.variable_test_support import (
    varref as _varref,
)


def test_interact_enable_expression_counts_mapped_parent_input_as_read() -> None:
    enable = Variable(name="Enable", datatype=ScalarDatatype.BOOLEAN)
    child_type = ModuleTypeDef(
        name="CoreReal",
        moduleparameters=[enable],
        moduledef=ModuleDef(
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
        ),
        origin_file="LibraryRoot.x",
        origin_lib="ProjectLib",
    )
    enable_privilege = Variable(name="EnablePrivilege", datatype=ScalarDatatype.BOOLEAN)
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
    local = Variable(name="Request", datatype=ScalarDatatype.INTEGER)
    dependency = ModuleTypeDef(
        name="Consumer",
        origin_file="Dependency.s",
        moduleparameters=[Variable(name="Input", datatype=ScalarDatatype.INTEGER)],
        localvariables=[Variable(name="Observed", datatype=ScalarDatatype.INTEGER)],
        modulecode=ModuleCode(
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
        ),
    )
    parent = ModuleTypeDef(
        name="Parent",
        origin_file="Root.s",
        localvariables=[local, Variable(name="Scratch", datatype=ScalarDatatype.INTEGER)],
        modulecode=ModuleCode(
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
        ),
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
    source = Variable(name="Source", datatype=ScalarDatatype.BOOLEAN)
    shown = Variable(name="Shown", datatype=ScalarDatatype.BOOLEAN)
    dead = Variable(name="Dead", datatype=ScalarDatatype.BOOLEAN)
    parent = ModuleTypeDef(
        name="Display",
        origin_file="Root.s",
        localvariables=[source, shown, dead, Variable(name="Scratch", datatype=ScalarDatatype.BOOLEAN)],
        modulecode=ModuleCode(
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
        ),
    )
    if display_kind == "text":
        parent.moduledef = ModuleDef(
            graph_objects=[GraphObject("TextObject", properties={"text_vars": [_varref("Shown")]})]
        )
    elif display_kind == "interact":
        parent.moduledef = ModuleDef(
            interact_objects=[
                InteractObject("TextBox_", properties={"tails": [VarTail(direction="in", value="Shown")]})
            ]
        )
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
    guard = Variable(name="Ready", datatype=ScalarDatatype.BOOLEAN)
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
        moduleparameters=[Variable(name="Output", datatype=ScalarDatatype.BOOLEAN)],
        localvariables=[guard, Variable(name="Scratch", datatype=ScalarDatatype.BOOLEAN)],
        modulecode=ModuleCode(
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
        ),
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
    ready = Variable(name="Ready", datatype=ScalarDatatype.BOOLEAN)
    leave = Variable(name="Leave", datatype=ScalarDatatype.BOOLEAN)
    phase = ModuleTypeDef(
        name="Phase",
        origin_file="Root.s",
        moduleparameters=[Variable(name="Output", datatype=ScalarDatatype.BOOLEAN)],
        localvariables=[ready, leave, Variable(name="Scratch", datatype=ScalarDatatype.BOOLEAN)],
        modulecode=ModuleCode(
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
        ),
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
    guard = Variable(name="Ready", datatype=ScalarDatatype.BOOLEAN)
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
        localvariables=[guard, Variable(name="Scratch", datatype=ScalarDatatype.BOOLEAN)],
        moduleparameters=[Variable(name="Output", datatype=ScalarDatatype.BOOLEAN)],
        modulecode=ModuleCode(
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
                                active=[Assignment(target=_varref("Output" if observable else "Scratch"), value=True)]
                            ),
                        ),
                    ],
                )
            ]
        ),
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
    flag = Variable(name="Request", datatype=ScalarDatatype.BOOLEAN)
    dead = Variable(name="Dead", datatype=ScalarDatatype.BOOLEAN)
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
        moduleparameters=[Variable(name="Output", datatype=ScalarDatatype.BOOLEAN)],
        localvariables=[
            flag,
            dead,
            Variable(name="Source", datatype=ScalarDatatype.BOOLEAN),
            Variable(name="Status", datatype=ScalarDatatype.INTEGER),
            Variable(name="Scratch", datatype=ScalarDatatype.BOOLEAN),
        ],
        modulecode=ModuleCode(
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
        ),
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
            Variable(name="Used", datatype=ScalarDatatype.INTEGER),
            Variable(name="Unused", datatype=ScalarDatatype.INTEGER),
        ],
        origin_file="LibraryRoot.x",
        origin_lib="ProjectLib",
    )

    exported = ModuleTypeDef(
        name="ExportedType",
        moduleparameters=[Variable(name="p", datatype="RecType")],
        localvariables=[Variable(name="sink", datatype=ScalarDatatype.INTEGER)],
        submodules=[],
        moduledef=None,
        modulecode=ModuleCode(
            equationblocks=[
                Equation(
                    name="Main",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[Assignment(target=_varref("sink"), value=_varref("p.Used"))],
                )
            ]
        ),
        origin_file="LibraryRoot.x",
        origin_lib="ProjectLib",
    )

    bp = BasePicture(
        header=_hdr("BasePicture"),
        datatype_defs=[record_type],
        moduletype_defs=[exported],
        localvariables=[],
        submodules=[],
        modulecode=None,
        moduledef=None,
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
    child_param = Variable(name="xSize", datatype=ScalarDatatype.REAL)
    child_type = ModuleTypeDef(
        name="ButtonType",
        moduleparameters=[child_param],
        localvariables=[],
        submodules=[],
        moduledef=ModuleDef(
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
        ),
        modulecode=None,
        origin_file="LibraryRoot.x",
        origin_lib="ProjectLib",
    )

    x_size = Variable(name="XSize", datatype=ScalarDatatype.REAL)
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
        moduledef=None,
        modulecode=None,
        origin_file="LibraryRoot.x",
        origin_lib="ProjectLib",
    )

    bp = BasePicture(
        header=_hdr("BasePicture"),
        datatype_defs=[],
        moduletype_defs=[parent_type, child_type],
        localvariables=[],
        submodules=[],
        modulecode=None,
        moduledef=None,
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
    child_param = Variable(name="xSize", datatype=ScalarDatatype.REAL)
    child_type = ModuleTypeDef(
        name="RecipePicklistSecond",
        moduleparameters=[child_param],
        localvariables=[],
        submodules=[],
        moduledef=ModuleDef(
            interact_objects=[
                InteractObject(
                    type=const.GRAMMAR_VALUE_COMBUTPROC,
                    properties={
                        "coords": [((0.0, 0.0), (1.0, 1.0))],
                        "procedure": ProcedureCall(name="ToggleWindow", args=(_varref("xSize"),)),
                    },
                )
            ]
        ),
        modulecode=None,
        origin_file="LibraryRoot.x",
        origin_lib="ProjectLib",
    )

    x_size = Variable(name="XSize", datatype=ScalarDatatype.REAL)
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
        moduledef=None,
        modulecode=None,
        origin_file="LibraryRoot.x",
        origin_lib="ProjectLib",
    )

    bp = BasePicture(
        header=_hdr("BasePicture"),
        datatype_defs=[],
        moduletype_defs=[parent_type, child_type],
        localvariables=[],
        submodules=[],
        modulecode=None,
        moduledef=None,
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


def test_typedef_usage_facts_are_keyed_by_library_not_only_type_name() -> None:
    reader_source = """
"Syntax version 2.23, date: 2026-06-19-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-06-19-12:00:00.000, name: ReaderLib"

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

TYPEDEFINITIONS
   SharedType = MODULEDEFINITION DateCode_ 1
   MODULEPARAMETERS
      Value: integer;
   LOCALVARIABLES
      Sink: integer := 0;
   ModuleDef
   ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
   ModuleCode
   EQUATIONBLOCK Eq COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      Sink = Value;
   ENDDEF (*SharedType*);

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )

ENDDEF (*BasePicture*);
"""
    writer_source = reader_source.replace("name: ReaderLib", "name: WriterLib").replace(
        "Sink = Value;", "Value = Sink;"
    )

    reader_type = parser_core_parse_source_text(reader_source).moduletype_defs[0]
    writer_type = parser_core_parse_source_text(writer_source).moduletype_defs[0]
    reader_type = replace(reader_type, origin_lib="ReaderLib", origin_file="ReaderLib.s")
    writer_type = replace(writer_type, origin_lib="WriterLib", origin_file="WriterLib.s")

    bp = BasePicture(
        header=_hdr("Root"),
        moduletype_defs=[reader_type, writer_type],
        localvariables=[],
        submodules=[],
        modulecode=None,
        moduledef=None,
    )
    analyzer = VariablesAnalyzer(bp, fail_loudly=False)
    analyzer._analyze_typedef(reader_type, ["Root", "TypeDef:SharedType"])
    analyzer._analyze_typedef(writer_type, ["Root", "TypeDef:SharedType"])

    reader_key = TypedefUsageKey("readerlib", "sharedtype")
    writer_key = TypedefUsageKey("writerlib", "sharedtype")
    assert analyzer.param_reads_by_typedef[reader_key] == {"value"}
    assert analyzer.param_writes_by_typedef[reader_key] == set()
    assert analyzer.param_writes_by_typedef[writer_key] == {"value"}
    assert analyzer.param_reads_by_typedef[writer_key] == set()


def test_usage_travels_through_a_multi_hop_parameter_mapping_chain() -> None:
    source = """
"Syntax version 2.23, date: 2026-06-19-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-06-19-12:00:00.000, name: Chain"
BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1
TYPEDEFINITIONS
   LeafType = MODULEDEFINITION DateCode_ 1
   MODULEPARAMETERS
      LeafParam: integer;
   LOCALVARIABLES
      Sink: integer := 0;
   ModuleDef
   ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
   ModuleCode
   EQUATIONBLOCK Eq COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      Sink = LeafParam;
   ENDDEF (*LeafType*);

   MiddleType = MODULEDEFINITION DateCode_ 2
   MODULEPARAMETERS
      Mapped: integer;
   SUBMODULES
      Leaf Invocation
         ( 0.0 , 0.0 , 0.0 , 0.4 , 0.4
          ) : LeafType (
         LeafParam => Mapped);
   ModuleDef
   ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
   ENDDEF (*MiddleType*);
LOCALVARIABLES
   RootValue: integer := 0;
SUBMODULES
   Middle Invocation
      ( 0.0 , 0.0 , 0.0 , 0.4 , 0.4
       ) : MiddleType (
      Mapped => RootValue);
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ENDDEF (*BasePicture*);
"""
    bp = parser_core_parse_source_text(source)
    analyzer = VariablesAnalyzer(bp, fail_loudly=False)
    analyzer.run()

    assert analyzer._get_usage(bp.localvariables[0]).read is True
