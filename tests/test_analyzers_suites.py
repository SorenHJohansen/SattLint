"""Tests for full-suite analyzers: SFC parallel write race, dataflow, variables analyzer suites, version drift, initial values, naming consistency, alarm integrity, safety paths, and taint paths."""

from typing import Any, cast

from sattlint import constants as const
from sattlint.analyzers.alarm_integrity import analyze_alarm_integrity
from sattlint.analyzers.dataflow import analyze_dataflow
from sattlint.analyzers.initial_values import analyze_initial_values
from sattlint.analyzers.modules import analyze_version_drift
from sattlint.analyzers.naming import analyze_naming_consistency, get_configured_naming_rules
from sattlint.analyzers.registry import get_default_analyzers
from sattlint.analyzers.safety_paths import analyze_safety_paths
from sattlint.analyzers.sfc import analyze_sfc
from sattlint.analyzers.taint_paths import analyze_taint_paths
from sattlint.analyzers.variables import IssueKind, VariablesAnalyzer
from sattlint.models.ast_model import (
    BasePicture,
    DataType,
    Equation,
    FrameModule,
    GraphObject,
    IntLiteral,
    ModuleCode,
    ModuleDef,
    ModuleHeader,
    ModuleTypeDef,
    ModuleTypeInstance,
    ParameterMapping,
    Sequence,
    SFCCodeBlocks,
    SFCParallel,
    SFCStep,
    SFCTransition,
    Simple_DataType,
    SingleModule,
    Variable,
)


def _hdr(name: str) -> ModuleHeader:
    return ModuleHeader(name=name, invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0))


def _varref(s: str) -> dict:
    return {const.KEY_VAR_NAME: s}


def _state_ref(name: str, state: str) -> dict:
    return {const.KEY_VAR_NAME: name, "state": state}


def _issue_kinds(report) -> set[str]:
    return {issue.kind for issue in report.issues}


def _status_bridge_typedef() -> ModuleTypeDef:
    return ModuleTypeDef(
        name="StatusBridge",
        moduleparameters=[Variable(name="OperationStatus", datatype=Simple_DataType.INTEGER)],
        localvariables=[
            Variable(name="Source", datatype=Simple_DataType.INTEGER),
            Variable(name="Destination", datatype=Simple_DataType.INTEGER),
        ],
        moduledef=None,
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="BridgeEq",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (
                            const.KEY_FUNCTION_CALL,
                            "CopyVariable",
                            [_varref("Source"), _varref("Destination"), _varref("OperationStatus")],
                        )
                    ],
                )
            ]
        ),
    )


def test_sfc_parallel_write_race_detected_for_same_variable():
    sequence = Sequence(
        name="SeqMain",
        type="sequence",
        position=(0.0, 0.0),
        size=(1.0, 1.0),
        code=[
            SFCParallel(
                branches=[
                    [
                        SFCStep(
                            kind="step",
                            name="Left",
                            code=SFCCodeBlocks(active=[(const.KEY_ASSIGN, _varref("Output"), 1)]),
                        )
                    ],
                    [
                        SFCStep(
                            kind="step",
                            name="Right",
                            code=SFCCodeBlocks(active=[(const.KEY_ASSIGN, _varref("Output"), 2)]),
                        )
                    ],
                ]
            )
        ],
    )
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[Variable(name="Output", datatype=Simple_DataType.INTEGER)],
        modulecode=ModuleCode(sequences=[sequence], equations=[]),
    )

    report = analyze_sfc(bp)

    issues = [issue for issue in report.issues if issue.kind == "sfc_parallel_write_race"]
    assert len(issues) == 1
    assert issues[0].data is not None
    assert issues[0].data["conflicts"] == ["Root.Output"]


def test_dataflow_flags_implicit_same_scan_state_read_in_sequence_step():
    sequence = Sequence(
        name="SeqMain",
        type="sequence",
        position=(0.0, 0.0),
        size=(1.0, 1.0),
        code=[
            SFCStep(
                kind="step",
                name="Drive",
                code=SFCCodeBlocks(
                    active=[
                        (const.KEY_ASSIGN, _state_ref("Flag", "new"), True),
                        (const.KEY_ASSIGN, _varref("Output"), _varref("Flag")),
                    ]
                ),
            )
        ],
    )
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[
            Variable(name="Flag", datatype=Simple_DataType.BOOLEAN, state=True),
            Variable(name="Output", datatype=Simple_DataType.BOOLEAN),
        ],
        modulecode=ModuleCode(sequences=[sequence], equations=[]),
    )

    report = analyze_dataflow(bp)

    assert any(
        issue.kind == "dataflow.scan_cycle_implicit_new"
        and issue.data is not None
        and issue.data.get("symbol") == "Flag"
        for issue in report.issues
    )


def test_dataflow_flags_old_as_out_parameter_temporal_misuse():
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[Variable(name="Flag", datatype=Simple_DataType.BOOLEAN, state=True)],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Main",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (
                            const.KEY_FUNCTION_CALL,
                            "MaxLim",
                            [1.0, 2.0, 0.1, _state_ref("Flag", "old")],
                        )
                    ],
                )
            ]
        ),
    )

    report = analyze_dataflow(bp)

    assert any(
        issue.kind == "dataflow.scan_cycle_temporal_misuse"
        and issue.data is not None
        and issue.data.get("symbol") == "Flag:Old"
        and issue.data.get("operation") == "out parameter"
        for issue in report.issues
    )


def test_variables_analyzer_flags_ignored_procedure_status_output():
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[
            Variable(name="Source", datatype=Simple_DataType.INTEGER),
            Variable(name="Destination", datatype=Simple_DataType.INTEGER),
            Variable(name="Status", datatype=Simple_DataType.INTEGER),
        ],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Main",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (
                            const.KEY_FUNCTION_CALL,
                            "CopyVariable",
                            [_varref("Source"), _varref("Destination"), _varref("Status")],
                        )
                    ],
                )
            ]
        ),
    )

    issues = VariablesAnalyzer(bp).run()

    status_issues = [issue for issue in issues if issue.kind is IssueKind.PROCEDURE_STATUS]
    assert len(status_issues) == 1
    assert status_issues[0].variable is not None
    assert status_issues[0].variable.name == "Status"
    assert "ignored" in (status_issues[0].role or "")
    assert not any(
        issue.kind in {IssueKind.NEVER_READ, IssueKind.WRITE_WITHOUT_EFFECT}
        and issue.variable is not None
        and issue.variable.name == "Status"
        for issue in issues
    )


def test_variables_analyzer_flags_dependency_mapped_status_that_only_reaches_ui():
    bridge = ModuleTypeInstance(
        header=_hdr("Bridge"),
        moduletype_name="StatusBridge",
        parametermappings=[
            ParameterMapping(
                target=_varref("OperationStatus"),
                source_type=const.TREE_TAG_VARIABLE_NAME,
                is_duration=False,
                is_source_global=False,
                source=_varref("StatusSink"),
            )
        ],
    )
    bp = BasePicture(
        header=_hdr("Root"),
        moduletype_defs=[_status_bridge_typedef()],
        localvariables=[Variable(name="StatusSink", datatype=Simple_DataType.INTEGER)],
        submodules=[bridge],
        moduledef=ModuleDef(graph_objects=[GraphObject(type="TextObject", properties={"text_vars": ["StatusSink"]})]),
    )

    issues = VariablesAnalyzer(bp).run()

    status_issues = [
        issue
        for issue in issues
        if issue.kind is IssueKind.PROCEDURE_STATUS
        and issue.variable is not None
        and issue.variable.name == "StatusSink"
    ]
    assert len(status_issues) == 1
    assert "UI" in (status_issues[0].role or "")


def test_variables_analyzer_flags_naming_to_behavior_mismatches():
    unit = SingleModule(
        header=_hdr("Unit"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[
            Variable(name="StartCmd", datatype=Simple_DataType.BOOLEAN),
            Variable(name="CmdLatch", datatype=Simple_DataType.BOOLEAN),
        ],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="LocalLogic",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (const.KEY_ASSIGN, _varref("StartCmd"), True),
                        (const.KEY_ASSIGN, _varref("CmdLatch"), _varref("StartCmd")),
                    ],
                )
            ]
        ),
        parametermappings=[],
    )
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[
            Variable(name="ValveStatus", datatype=Simple_DataType.INTEGER),
            Variable(name="HighAlarm", datatype=Simple_DataType.BOOLEAN),
            Variable(name="Shutdown", datatype=Simple_DataType.BOOLEAN),
        ],
        submodules=[unit],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Main",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (const.KEY_ASSIGN, _varref("ValveStatus"), IntLiteral(1)),
                        (const.KEY_ASSIGN, _varref("Shutdown"), _varref("HighAlarm")),
                    ],
                )
            ]
        ),
        moduledef=None,
    )

    issues = VariablesAnalyzer(bp).run()

    naming_issues = [issue for issue in issues if issue.kind is IssueKind.NAMING_ROLE_MISMATCH]
    assert {
        (issue.variable.name, tuple(issue.module_path)) for issue in naming_issues if issue.variable is not None
    } == {
        ("StartCmd", ("Root", "Unit")),
        ("ValveStatus", ("Root",)),
        ("HighAlarm", ("Root",)),
    }
    roles_by_name = {issue.variable.name: (issue.role or "") for issue in naming_issues if issue.variable is not None}
    assert "internal state" in roles_by_name["StartCmd"]
    assert "written directly" in roles_by_name["ValveStatus"]
    assert "control input" in roles_by_name["HighAlarm"]


def test_variables_analyzer_ignores_safe_naming_role_counterexamples():
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[
            Variable(name="StartCmd", datatype=Simple_DataType.BOOLEAN),
            Variable(name="Output", datatype=Simple_DataType.BOOLEAN),
            Variable(name="Status", datatype=Simple_DataType.INTEGER),
            Variable(name="Source", datatype=Simple_DataType.INTEGER),
            Variable(name="Destination", datatype=Simple_DataType.INTEGER),
            Variable(name="HighAlarm", datatype=Simple_DataType.BOOLEAN),
        ],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Main",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (const.KEY_ASSIGN, _varref("Output"), _varref("StartCmd")),
                        (
                            const.KEY_FUNCTION_CALL,
                            "CopyVariable",
                            [_varref("Source"), _varref("Destination"), _varref("Status")],
                        ),
                    ],
                )
            ]
        ),
        moduledef=ModuleDef(graph_objects=[GraphObject(type="TextObject", properties={"text_vars": ["HighAlarm"]})]),
    )

    issues = VariablesAnalyzer(bp).run()

    assert not any(issue.kind is IssueKind.NAMING_ROLE_MISMATCH for issue in issues)


def test_variables_analyzer_supports_configured_naming_role_prefixes():
    unit = SingleModule(
        header=_hdr("Unit"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[
            Variable(name="CmdStart", datatype=Simple_DataType.BOOLEAN),
            Variable(name="StatusValve", datatype=Simple_DataType.INTEGER),
            Variable(name="Hold", datatype=Simple_DataType.BOOLEAN),
        ],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Main",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (const.KEY_ASSIGN, _varref("CmdStart"), True),
                        (const.KEY_ASSIGN, _varref("Hold"), _varref("CmdStart")),
                        (const.KEY_ASSIGN, _varref("StatusValve"), IntLiteral(1)),
                    ],
                )
            ]
        ),
        parametermappings=[],
    )
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[],
        submodules=[unit],
        modulecode=None,
        moduledef=None,
    )

    default_issues = VariablesAnalyzer(bp).run()
    configured_issues = VariablesAnalyzer(
        bp,
        config={
            "analysis": {
                "naming": {
                    "role_patterns": {
                        "command": {"prefixes": ["cmd"]},
                        "status": {"prefixes": ["status"]},
                    }
                }
            }
        },
    ).run()

    assert not any(issue.kind is IssueKind.NAMING_ROLE_MISMATCH for issue in default_issues)
    configured_names = {
        issue.variable.name
        for issue in configured_issues
        if issue.kind is IssueKind.NAMING_ROLE_MISMATCH and issue.variable is not None
    }
    assert configured_names == {"CmdStart", "StatusValve"}


def test_variables_analyzer_treats_dependency_mapped_status_as_handled_when_read_in_logic():
    bridge = ModuleTypeInstance(
        header=_hdr("Bridge"),
        moduletype_name="StatusBridge",
        parametermappings=[
            ParameterMapping(
                target=_varref("OperationStatus"),
                source_type=const.TREE_TAG_VARIABLE_NAME,
                is_duration=False,
                is_source_global=False,
                source=_varref("StatusSink"),
            )
        ],
    )
    bp = BasePicture(
        header=_hdr("Root"),
        moduletype_defs=[_status_bridge_typedef()],
        localvariables=[
            Variable(name="StatusSink", datatype=Simple_DataType.INTEGER),
            Variable(name="Handled", datatype=Simple_DataType.BOOLEAN),
        ],
        submodules=[bridge],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Main",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[(const.KEY_ASSIGN, _varref("Handled"), _varref("StatusSink"))],
                )
            ]
        ),
    )

    issues = VariablesAnalyzer(bp).run()

    assert not any(
        issue.variable is not None
        and issue.variable.name == "StatusSink"
        and issue.kind in {IssueKind.PROCEDURE_STATUS, IssueKind.WRITE_WITHOUT_EFFECT, IssueKind.NEVER_READ}
        for issue in issues
    )


def test_dataflow_flags_contradictory_branch_condition_in_analyzer_suite():
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[
            Variable(name="Flag", datatype=Simple_DataType.BOOLEAN),
            Variable(name="Output", datatype=Simple_DataType.BOOLEAN),
        ],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Main",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (
                            const.GRAMMAR_VALUE_IF,
                            [
                                (
                                    (
                                        const.GRAMMAR_VALUE_AND,
                                        [
                                            _varref("Flag"),
                                            (const.GRAMMAR_VALUE_NOT, _varref("Flag")),
                                        ],
                                    ),
                                    [
                                        (
                                            const.KEY_ASSIGN,
                                            _varref("Output"),
                                            True,
                                        )
                                    ],
                                )
                            ],
                            [
                                (
                                    const.KEY_ASSIGN,
                                    _varref("Output"),
                                    False,
                                )
                            ],
                        )
                    ],
                )
            ]
        ),
    )

    report = analyze_dataflow(bp)

    assert "dataflow.condition_always_false" in _issue_kinds(report)
    assert "dataflow.unreachable_branch" in _issue_kinds(report)


def test_dataflow_flags_impossible_inferred_compare_condition_in_analyzer_suite():
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[
            Variable(name="Counter", datatype=Simple_DataType.INTEGER),
            Variable(name="Output", datatype=Simple_DataType.BOOLEAN),
        ],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Main",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (
                            const.GRAMMAR_VALUE_IF,
                            [
                                (
                                    (
                                        const.GRAMMAR_VALUE_AND,
                                        [
                                            (
                                                const.KEY_COMPARE,
                                                _varref("Counter"),
                                                [("==", 1)],
                                            ),
                                            (
                                                const.KEY_COMPARE,
                                                _varref("Counter"),
                                                [("==", 2)],
                                            ),
                                        ],
                                    ),
                                    [
                                        (
                                            const.KEY_ASSIGN,
                                            _varref("Output"),
                                            True,
                                        )
                                    ],
                                )
                            ],
                            [],
                        )
                    ],
                )
            ]
        ),
    )

    report = analyze_dataflow(bp)

    impossible_conditions = [
        issue
        for issue in report.issues
        if issue.kind == "dataflow.condition_always_false"
        and issue.data is not None
        and "Counter == 1" in str(issue.data.get("condition"))
        and "Counter == 2" in str(issue.data.get("condition"))
    ]

    assert impossible_conditions
    assert "dataflow.unreachable_branch" in _issue_kinds(report)


def test_sfc_parallel_write_race_detected_for_record_field_overlap():
    sequence = Sequence(
        name="SeqMain",
        type="sequence",
        position=(0.0, 0.0),
        size=(1.0, 1.0),
        code=[
            SFCParallel(
                branches=[
                    [
                        SFCStep(
                            kind="step",
                            name="Left",
                            code=SFCCodeBlocks(active=[(const.KEY_ASSIGN, _varref("Rec"), 1)]),
                        )
                    ],
                    [
                        SFCStep(
                            kind="step",
                            name="Right",
                            code=SFCCodeBlocks(active=[(const.KEY_ASSIGN, _varref("Rec.Field"), 2)]),
                        )
                    ],
                ]
            )
        ],
    )
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[
            DataType(
                name="RecType",
                description=None,
                datecode=None,
                var_list=[Variable(name="Field", datatype=Simple_DataType.INTEGER)],
            )
        ],
        localvariables=[Variable(name="Rec", datatype="RecType")],
        modulecode=ModuleCode(sequences=[sequence], equations=[]),
        moduledef=None,
    )

    report = analyze_sfc(bp)

    issues = [issue for issue in report.issues if issue.kind == "sfc_parallel_write_race"]
    assert len(issues) == 1
    assert issues[0].data is not None
    assert issues[0].data["conflicts"] == ["Root.Rec"]


def test_sfc_transition_logic_detects_always_true_guard():
    sequence = Sequence(
        name="SeqMain",
        type="sequence",
        position=(0.0, 0.0),
        size=(1.0, 1.0),
        code=[
            SFCTransition(
                name="AlwaysOpen",
                condition=(
                    const.GRAMMAR_VALUE_OR,
                    [_varref("Permit"), (const.GRAMMAR_VALUE_NOT, _varref("Permit"))],
                ),
            )
        ],
    )
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[Variable(name="Permit", datatype=Simple_DataType.BOOLEAN)],
        modulecode=ModuleCode(sequences=[sequence], equations=[]),
    )

    report = analyze_sfc(bp)

    issues = [issue for issue in report.issues if issue.kind == "sfc_transition_always_true"]
    assert len(issues) == 1
    assert issues[0].data is not None
    assert issues[0].data["transition_name"] == "AlwaysOpen"


def test_sfc_transition_logic_detects_always_false_guard():
    sequence = Sequence(
        name="SeqMain",
        type="sequence",
        position=(0.0, 0.0),
        size=(1.0, 1.0),
        code=[
            SFCTransition(
                name="NeverOpen",
                condition=(
                    const.GRAMMAR_VALUE_AND,
                    [_varref("Permit"), (const.GRAMMAR_VALUE_NOT, _varref("Permit"))],
                ),
            )
        ],
    )
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[Variable(name="Permit", datatype=Simple_DataType.BOOLEAN)],
        modulecode=ModuleCode(sequences=[sequence], equations=[]),
    )

    report = analyze_sfc(bp)

    issues = [issue for issue in report.issues if issue.kind == "sfc_transition_always_false"]
    assert len(issues) == 1
    assert issues[0].data is not None
    assert issues[0].data["transition_name"] == "NeverOpen"


def test_sfc_transition_logic_detects_duplicate_guards_after_normalization():
    sequence = Sequence(
        name="SeqMain",
        type="sequence",
        position=(0.0, 0.0),
        size=(1.0, 1.0),
        code=[
            SFCTransition(
                name="OpenPrimary",
                condition=(const.GRAMMAR_VALUE_AND, [_varref("Permit"), _varref("Ready")]),
            ),
            SFCTransition(
                name="OpenBackup",
                condition=(const.GRAMMAR_VALUE_AND, [_varref("Ready"), _varref("Permit")]),
            ),
        ],
    )
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[
            Variable(name="Permit", datatype=Simple_DataType.BOOLEAN),
            Variable(name="Ready", datatype=Simple_DataType.BOOLEAN),
        ],
        modulecode=ModuleCode(sequences=[sequence], equations=[]),
    )

    report = analyze_sfc(bp)

    issues = [issue for issue in report.issues if issue.kind == "sfc_duplicate_transition_guard"]
    assert len(issues) == 1
    assert issues[0].data is not None
    assert issues[0].data["transition_names"] == ["OpenPrimary", "OpenBackup"]


def test_version_drift_detects_small_code_delta_between_same_named_modules():
    variant_a = SingleModule(
        header=_hdr("Mixer"),
        datecode=100,
        moduledef=None,
        moduleparameters=[],
        localvariables=[Variable(name="Output", datatype=Simple_DataType.INTEGER)],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Logic",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[(const.KEY_ASSIGN, _varref("Output"), 1)],
                )
            ],
            sequences=[],
        ),
        parametermappings=[],
    )
    variant_b = SingleModule(
        header=_hdr("Mixer"),
        datecode=200,
        moduledef=None,
        moduleparameters=[],
        localvariables=[Variable(name="Output", datatype=Simple_DataType.INTEGER)],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Logic",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[(const.KEY_ASSIGN, _varref("Output"), 2)],
                )
            ],
            sequences=[],
        ),
        parametermappings=[],
    )
    cast(Any, variant_a).origin_file = "Root.s"
    cast(Any, variant_b).origin_file = "Root.s"
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[],
        submodules=[variant_a, variant_b],
        modulecode=None,
        moduledef=None,
        origin_file="Root.s",
    )

    report = analyze_version_drift(bp)

    issues = [issue for issue in report.issues if issue.kind == "module.version_drift"]
    assert len(issues) == 1
    assert issues[0].data is not None
    assert issues[0].data["module_name"] == "Mixer"
    assert issues[0].data["unique_variants"] == 2
    assert "code" in issues[0].data["material_differences"]
    assert "modified_equations" in issues[0].data["material_differences"]["code"]
    assert "Logic" in issues[0].data["material_differences"]["code"]["modified_equations"]
    assert issues[0].data["material_differences"]["code"]["modified_equations"]["Logic"]
    assert any("Equation 'Logic' changed" in note for note in issues[0].data["upgrade_notes"])


def test_version_drift_records_modified_variable_shape_diffs():
    variant_a = SingleModule(
        header=_hdr("Mixer"),
        datecode=100,
        moduledef=None,
        moduleparameters=[],
        localvariables=[Variable(name="Output", datatype=Simple_DataType.INTEGER)],
        submodules=[],
        modulecode=None,
        parametermappings=[],
    )
    variant_b = SingleModule(
        header=_hdr("Mixer"),
        datecode=200,
        moduledef=None,
        moduleparameters=[],
        localvariables=[Variable(name="Output", datatype=Simple_DataType.REAL)],
        submodules=[],
        modulecode=None,
        parametermappings=[],
    )
    cast(Any, variant_a).origin_file = "Root.s"
    cast(Any, variant_b).origin_file = "Root.s"
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[],
        submodules=[variant_a, variant_b],
        modulecode=None,
        moduledef=None,
        origin_file="Root.s",
    )

    report = analyze_version_drift(bp)

    issues = [issue for issue in report.issues if issue.kind == "module.version_drift"]
    assert len(issues) == 1
    assert issues[0].data is not None
    assert "localvariables" in issues[0].data["material_differences"]
    assert "Output" in issues[0].data["material_differences"]["localvariables"]["modified"]
    assert any(
        detail["path"] == "datatype"
        for detail in issues[0].data["material_differences"]["localvariables"]["modified"]["Output"]
    )
    assert any("Local variable 'Output' changed" in note for note in issues[0].data["upgrade_notes"])


def test_version_drift_ignores_datecode_only_differences():
    variant_a = SingleModule(
        header=_hdr("Mixer"),
        datecode=100,
        moduledef=None,
        moduleparameters=[],
        localvariables=[Variable(name="Output", datatype=Simple_DataType.INTEGER)],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Logic",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[(const.KEY_ASSIGN, _varref("Output"), 1)],
                )
            ],
            sequences=[],
        ),
        parametermappings=[],
    )
    variant_b = SingleModule(
        header=_hdr("Mixer"),
        datecode=200,
        moduledef=None,
        moduleparameters=[],
        localvariables=[Variable(name="Output", datatype=Simple_DataType.INTEGER)],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Logic",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[(const.KEY_ASSIGN, _varref("Output"), 1)],
                )
            ],
            sequences=[],
        ),
        parametermappings=[],
    )
    cast(Any, variant_a).origin_file = "Root.s"
    cast(Any, variant_b).origin_file = "Root.s"
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[],
        submodules=[variant_a, variant_b],
        modulecode=None,
        moduledef=None,
        origin_file="Root.s",
    )

    report = analyze_version_drift(bp)

    assert report.issues == []


def test_version_drift_analyzer_is_enabled_by_default():
    specs = {spec.key: spec for spec in get_default_analyzers()}

    assert "version-drift" in specs
    assert specs["version-drift"].enabled is True


def test_initial_value_validation_flags_recipe_parameter_without_value_default():
    recipe_parameter = ModuleTypeDef(
        name="RecParReal",
        moduleparameters=[
            Variable(name="Value", datatype=Simple_DataType.REAL),
            Variable(name="MinValue", datatype=Simple_DataType.REAL, init_value=0.0),
            Variable(name="MaxValue", datatype=Simple_DataType.REAL, init_value=100.0),
        ],
        localvariables=[],
        submodules=[],
        moduledef=None,
        modulecode=None,
        parametermappings=[],
        origin_file="Root.s",
    )
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[recipe_parameter],
        localvariables=[],
        submodules=[
            ModuleTypeInstance(
                header=_hdr("RecipeSP"),
                moduletype_name="RecParReal",
                parametermappings=[],
            )
        ],
        modulecode=None,
        moduledef=None,
        origin_file="Root.s",
    )

    report = analyze_initial_values(bp)

    issues = [issue for issue in report.issues if issue.kind == "initial-values.missing_required_default"]
    assert len(issues) == 1
    assert issues[0].module_path == ["Root", "RecipeSP"]
    assert issues[0].data == {
        "parameter_category": "recipe",
        "instance": "RecipeSP",
        "moduletype": "RecParReal",
        "moduletype_label": "RecParReal",
        "required_parameters": ["Value"],
        "parameter_statuses": {"Value": "not_configured"},
    }


def test_initial_value_validation_accepts_engineering_parameter_mapped_from_initialized_variable():
    engineering_parameter = ModuleTypeDef(
        name="EngParReal",
        moduleparameters=[
            Variable(name="Value", datatype=Simple_DataType.REAL),
            Variable(name="MinValue", datatype=Simple_DataType.REAL, init_value=0.0),
            Variable(name="MaxValue", datatype=Simple_DataType.REAL, init_value=100.0),
        ],
        localvariables=[],
        submodules=[],
        moduledef=None,
        modulecode=None,
        parametermappings=[],
        origin_file="Root.s",
    )
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[engineering_parameter],
        localvariables=[Variable(name="ConfiguredLimit", datatype=Simple_DataType.REAL, init_value=42.5)],
        submodules=[
            ModuleTypeInstance(
                header=_hdr("EngineeringLimit"),
                moduletype_name="EngParReal",
                parametermappings=[
                    ParameterMapping(
                        target=_varref("Value"),
                        source_type=const.TREE_TAG_VARIABLE_NAME,
                        is_duration=False,
                        is_source_global=False,
                        source=_varref("ConfiguredLimit"),
                        source_literal=None,
                    ),
                    ParameterMapping(
                        target=_varref("MinValue"),
                        source_type=const.KEY_VALUE,
                        is_duration=False,
                        is_source_global=False,
                        source_literal=0.0,
                    ),
                    ParameterMapping(
                        target=_varref("MaxValue"),
                        source_type=const.KEY_VALUE,
                        is_duration=False,
                        is_source_global=False,
                        source_literal=100.0,
                    ),
                ],
            )
        ],
        modulecode=None,
        moduledef=None,
        origin_file="Root.s",
    )

    report = analyze_initial_values(bp)

    assert report.issues == []


def test_initial_value_validation_analyzer_is_enabled_by_default():
    specs = {spec.key: spec for spec in get_default_analyzers()}

    assert "initial-values" in specs
    assert specs["initial-values"].enabled is True


def test_naming_consistency_flags_inconsistent_variable_names():
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[Variable(name="FlowRate", datatype=Simple_DataType.INTEGER)],
        submodules=[
            SingleModule(
                header=_hdr("MixerUnit"),
                moduledef=None,
                moduleparameters=[],
                localvariables=[Variable(name="PumpSpeed", datatype=Simple_DataType.INTEGER)],
                submodules=[],
                modulecode=None,
                parametermappings=[],
            ),
            SingleModule(
                header=_hdr("HoldingUnit"),
                moduledef=None,
                moduleparameters=[],
                localvariables=[Variable(name="tank_level", datatype=Simple_DataType.INTEGER)],
                submodules=[],
                modulecode=None,
                parametermappings=[],
            ),
        ],
        modulecode=None,
        moduledef=None,
    )

    report = analyze_naming_consistency(bp)

    issues = [
        issue
        for issue in report.issues
        if issue.kind == "naming.inconsistent_style"
        and issue.data is not None
        and issue.data.get("symbol_kind") == "variable"
    ]
    assert len(issues) == 1
    assert issues[0].module_path == ["Root", "HoldingUnit"]
    assert issues[0].data == {
        "symbol_kind": "variable",
        "name": "tank_level",
        "actual_style": "snake",
        "expected_style": "pascal",
    }


def test_naming_consistency_flags_inconsistent_module_names():
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[],
        submodules=[
            SingleModule(
                header=_hdr("MixerUnit"),
                moduledef=None,
                moduleparameters=[],
                localvariables=[],
                submodules=[],
                modulecode=None,
                parametermappings=[],
            ),
            FrameModule(
                header=_hdr("HoldingFrame"),
                submodules=[],
                moduledef=None,
                modulecode=None,
            ),
            SingleModule(
                header=_hdr("cooling_stage"),
                moduledef=None,
                moduleparameters=[],
                localvariables=[],
                submodules=[],
                modulecode=None,
                parametermappings=[],
            ),
        ],
        modulecode=None,
        moduledef=None,
    )

    report = analyze_naming_consistency(bp)

    issues = [
        issue
        for issue in report.issues
        if issue.kind == "naming.inconsistent_style"
        and issue.data is not None
        and issue.data.get("symbol_kind") == "module"
    ]
    assert len(issues) == 1
    assert issues[0].module_path == ["Root", "cooling_stage"]
    assert issues[0].data == {
        "symbol_kind": "module",
        "name": "cooling_stage",
        "actual_style": "snake",
        "expected_style": "pascal",
    }


def test_naming_consistency_flags_inconsistent_instance_names():
    typedef = ModuleTypeDef(
        name="ValveType",
        moduleparameters=[],
        localvariables=[],
        submodules=[],
        moduledef=None,
        modulecode=None,
        parametermappings=[],
    )
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[typedef],
        localvariables=[],
        submodules=[
            ModuleTypeInstance(
                header=_hdr("ValveFeed"),
                moduletype_name="ValveType",
                parametermappings=[],
            ),
            ModuleTypeInstance(
                header=_hdr("ValveDrain"),
                moduletype_name="ValveType",
                parametermappings=[],
            ),
            ModuleTypeInstance(
                header=_hdr("valve_return"),
                moduletype_name="ValveType",
                parametermappings=[],
            ),
        ],
        modulecode=None,
        moduledef=None,
    )

    report = analyze_naming_consistency(bp)

    issues = [
        issue
        for issue in report.issues
        if issue.kind == "naming.inconsistent_style"
        and issue.data is not None
        and issue.data.get("symbol_kind") == "instance"
    ]
    assert len(issues) == 1
    assert issues[0].module_path == ["Root", "valve_return"]
    assert issues[0].data == {
        "symbol_kind": "instance",
        "name": "valve_return",
        "actual_style": "snake",
        "expected_style": "pascal",
    }


def test_naming_consistency_honors_case_insensitive_allowed_exceptions():
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[
            Variable(name="FlowRate", datatype=Simple_DataType.INTEGER),
            Variable(name="PumpSpeed", datatype=Simple_DataType.INTEGER),
            Variable(name="legacyTemp", datatype=Simple_DataType.INTEGER),
        ],
        submodules=[],
        modulecode=None,
        moduledef=None,
    )

    report = analyze_naming_consistency(
        bp,
        rules=get_configured_naming_rules(
            {
                "analysis": {
                    "naming": {
                        "variables": {
                            "style": "pascal",
                            "allow": ["LEGACYTEMP"],
                        }
                    }
                }
            }
        ),
    )

    assert report.issues == []


def test_naming_consistency_analyzer_is_enabled_by_default():
    specs = {spec.key: spec for spec in get_default_analyzers()}

    assert "naming-consistency" in specs
    assert specs["naming-consistency"].enabled is True


def test_alarm_integrity_detects_duplicate_tags_across_instances():
    detector = ModuleTypeDef(
        name="EventDetector1",
        moduleparameters=[
            Variable(name="Tag", datatype=Simple_DataType.TAGSTRING),
            Variable(name="Severity", datatype=Simple_DataType.INTEGER, init_value=2),
            Variable(name="Condition", datatype=Simple_DataType.BOOLEAN),
        ],
        localvariables=[],
        submodules=[],
        moduledef=None,
        modulecode=None,
        parametermappings=[],
        origin_file="Root.s",
    )
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[
            Variable(name="CondA", datatype=Simple_DataType.BOOLEAN),
            Variable(name="CondB", datatype=Simple_DataType.BOOLEAN),
        ],
        moduletype_defs=[detector],
        submodules=[
            ModuleTypeInstance(
                header=_hdr("AlarmA"),
                moduletype_name="EventDetector1",
                parametermappings=[
                    ParameterMapping(
                        target=_varref("Tag"),
                        source_type=const.KEY_VALUE,
                        is_duration=False,
                        is_source_global=False,
                        source_literal="Unit.Temp.High",
                    ),
                    ParameterMapping(
                        target=_varref("Condition"),
                        source_type=const.TREE_TAG_VARIABLE_NAME,
                        is_duration=False,
                        is_source_global=False,
                        source=_varref("CondA"),
                        source_literal=None,
                    ),
                ],
            ),
            ModuleTypeInstance(
                header=_hdr("AlarmB"),
                moduletype_name="EventDetector1",
                parametermappings=[
                    ParameterMapping(
                        target=_varref("Tag"),
                        source_type=const.KEY_VALUE,
                        is_duration=False,
                        is_source_global=False,
                        source_literal="Unit.Temp.High",
                    ),
                    ParameterMapping(
                        target=_varref("Condition"),
                        source_type=const.TREE_TAG_VARIABLE_NAME,
                        is_duration=False,
                        is_source_global=False,
                        source=_varref("CondB"),
                        source_literal=None,
                    ),
                ],
            ),
        ],
        origin_file="Root.s",
    )

    report = analyze_alarm_integrity(bp)

    duplicate_tag_issues = [issue for issue in report.issues if issue.kind == "alarm.duplicate_tag"]
    assert len(duplicate_tag_issues) == 2
    assert all("Unit.Temp.High" in issue.message for issue in duplicate_tag_issues)


def test_alarm_integrity_detects_duplicate_conditions_across_instances():
    detector = ModuleTypeDef(
        name="EventDetector1",
        moduleparameters=[
            Variable(name="Tag", datatype=Simple_DataType.TAGSTRING),
            Variable(name="Severity", datatype=Simple_DataType.INTEGER, init_value=2),
            Variable(name="Condition", datatype=Simple_DataType.BOOLEAN),
        ],
        localvariables=[],
        submodules=[],
        moduledef=None,
        modulecode=None,
        parametermappings=[],
        origin_file="Root.s",
    )
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[Variable(name="SharedCondition", datatype=Simple_DataType.BOOLEAN)],
        moduletype_defs=[detector],
        submodules=[
            ModuleTypeInstance(
                header=_hdr("AlarmA"),
                moduletype_name="EventDetector1",
                parametermappings=[
                    ParameterMapping(
                        target=_varref("Tag"),
                        source_type=const.KEY_VALUE,
                        is_duration=False,
                        is_source_global=False,
                        source_literal="Unit.Temp.High",
                    ),
                    ParameterMapping(
                        target=_varref("Condition"),
                        source_type=const.TREE_TAG_VARIABLE_NAME,
                        is_duration=False,
                        is_source_global=False,
                        source=_varref("SharedCondition"),
                        source_literal=None,
                    ),
                ],
            ),
            ModuleTypeInstance(
                header=_hdr("AlarmB"),
                moduletype_name="EventDetector1",
                parametermappings=[
                    ParameterMapping(
                        target=_varref("Tag"),
                        source_type=const.KEY_VALUE,
                        is_duration=False,
                        is_source_global=False,
                        source_literal="Unit.Temp.Low",
                    ),
                    ParameterMapping(
                        target=_varref("Condition"),
                        source_type=const.TREE_TAG_VARIABLE_NAME,
                        is_duration=False,
                        is_source_global=False,
                        source=_varref("SharedCondition"),
                        source_literal=None,
                    ),
                ],
            ),
        ],
        origin_file="Root.s",
    )

    report = analyze_alarm_integrity(bp)

    duplicate_condition_issues = [issue for issue in report.issues if issue.kind == "alarm.duplicate_condition"]
    assert len(duplicate_condition_issues) == 2
    assert all("SharedCondition" in issue.message for issue in duplicate_condition_issues)


def test_alarm_integrity_detects_conflicting_priorities_for_same_tag():
    detector = ModuleTypeDef(
        name="EventDetector1",
        moduleparameters=[
            Variable(name="Tag", datatype=Simple_DataType.TAGSTRING),
            Variable(name="Severity", datatype=Simple_DataType.INTEGER),
            Variable(name="Condition", datatype=Simple_DataType.BOOLEAN),
        ],
        localvariables=[],
        submodules=[],
        moduledef=None,
        modulecode=None,
        parametermappings=[],
        origin_file="Root.s",
    )
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[
            Variable(name="CondA", datatype=Simple_DataType.BOOLEAN),
            Variable(name="CondB", datatype=Simple_DataType.BOOLEAN),
        ],
        moduletype_defs=[detector],
        submodules=[
            ModuleTypeInstance(
                header=_hdr("AlarmA"),
                moduletype_name="EventDetector1",
                parametermappings=[
                    ParameterMapping(
                        target=_varref("Tag"),
                        source_type=const.KEY_VALUE,
                        is_duration=False,
                        is_source_global=False,
                        source_literal="Unit.Temp.High",
                    ),
                    ParameterMapping(
                        target=_varref("Severity"),
                        source_type=const.KEY_VALUE,
                        is_duration=False,
                        is_source_global=False,
                        source_literal=1,
                    ),
                    ParameterMapping(
                        target=_varref("Condition"),
                        source_type=const.TREE_TAG_VARIABLE_NAME,
                        is_duration=False,
                        is_source_global=False,
                        source=_varref("CondA"),
                        source_literal=None,
                    ),
                ],
            ),
            ModuleTypeInstance(
                header=_hdr("AlarmB"),
                moduletype_name="EventDetector1",
                parametermappings=[
                    ParameterMapping(
                        target=_varref("Tag"),
                        source_type=const.KEY_VALUE,
                        is_duration=False,
                        is_source_global=False,
                        source_literal="Unit.Temp.High",
                    ),
                    ParameterMapping(
                        target=_varref("Severity"),
                        source_type=const.KEY_VALUE,
                        is_duration=False,
                        is_source_global=False,
                        source_literal=3,
                    ),
                    ParameterMapping(
                        target=_varref("Condition"),
                        source_type=const.TREE_TAG_VARIABLE_NAME,
                        is_duration=False,
                        is_source_global=False,
                        source=_varref("CondB"),
                        source_literal=None,
                    ),
                ],
            ),
        ],
        origin_file="Root.s",
    )

    report = analyze_alarm_integrity(bp)

    conflicting_priority_issues = [issue for issue in report.issues if issue.kind == "alarm.conflicting_priority"]
    assert len(conflicting_priority_issues) == 2
    assert all("1" in issue.message and "3" in issue.message for issue in conflicting_priority_issues)


def test_alarm_integrity_detects_never_cleared_alarm_variable():
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[Variable(name="AlarmTrip", datatype=Simple_DataType.BOOLEAN)],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Main",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (
                            const.KEY_FUNCTION_CALL,
                            "SetBooleanValue",
                            [_varref("AlarmTrip"), True],
                        )
                    ],
                )
            ]
        ),
    )

    report = analyze_alarm_integrity(bp)

    never_cleared_issues = [issue for issue in report.issues if issue.kind == "alarm.never_cleared"]
    assert len(never_cleared_issues) == 1
    assert "AlarmTrip" in never_cleared_issues[0].message


def test_alarm_integrity_analyzer_is_enabled_by_default():
    specs = {spec.key: spec for spec in get_default_analyzers()}

    assert "alarm-integrity" in specs
    assert specs["alarm-integrity"].enabled is True


def test_safety_paths_trace_emergency_signal_across_moduletype_mapping():
    guard_type = ModuleTypeDef(
        name="GuardType",
        moduleparameters=[
            Variable(name="InSignal", datatype=Simple_DataType.BOOLEAN),
        ],
        localvariables=[
            Variable(name="Seen", datatype=Simple_DataType.BOOLEAN, init_value=False),
        ],
        submodules=[],
        moduledef=None,
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="GuardEq",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (
                            const.KEY_ASSIGN,
                            _varref("Seen"),
                            _varref("InSignal"),
                        )
                    ],
                )
            ]
        ),
        parametermappings=[],
        origin_file="Root.s",
    )
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[
            Variable(name="EmergencyShutdown", datatype=Simple_DataType.BOOLEAN, init_value=False),
        ],
        moduletype_defs=[guard_type],
        submodules=[
            ModuleTypeInstance(
                header=_hdr("Guard"),
                moduletype_name="GuardType",
                parametermappings=[
                    ParameterMapping(
                        target=_varref("InSignal"),
                        source_type=const.TREE_TAG_VARIABLE_NAME,
                        is_duration=False,
                        is_source_global=False,
                        source=_varref("EmergencyShutdown"),
                        source_literal=None,
                    )
                ],
            )
        ],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Main",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (
                            const.KEY_ASSIGN,
                            _varref("EmergencyShutdown"),
                            True,
                        )
                    ],
                )
            ]
        ),
        origin_file="Root.s",
    )

    report = analyze_safety_paths(bp)

    assert report.issues == []
    assert len(report.traces) == 1
    assert report.traces[0].canonical_path == "Root.EmergencyShutdown"
    assert report.traces[0].writer_module_paths == (("Root",),)
    assert report.traces[0].reader_module_paths == (("Root", "Guard"),)
    assert report.traces[0].spans_multiple_modules is True


def test_safety_paths_reports_unconsumed_shutdown_signal():
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[
            Variable(name="EmergencyShutdown", datatype=Simple_DataType.BOOLEAN, init_value=False),
        ],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Main",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (
                            const.KEY_ASSIGN,
                            _varref("EmergencyShutdown"),
                            True,
                        )
                    ],
                )
            ]
        ),
    )

    report = analyze_safety_paths(bp)

    assert len(report.traces) == 1
    assert len(report.issues) == 1
    assert report.issues[0].kind == "safety-path.unconsumed_signal"
    assert report.issues[0].data is not None
    assert report.issues[0].data["canonical_path"] == "Root.EmergencyShutdown"


def test_taint_paths_trace_operator_input_to_shutdown_sink_across_moduletype_mapping():
    guard_type = ModuleTypeDef(
        name="GuardType",
        moduleparameters=[
            Variable(name="InCommand", datatype=Simple_DataType.BOOLEAN),
        ],
        localvariables=[
            Variable(name="EmergencyShutdown", datatype=Simple_DataType.BOOLEAN, init_value=False),
        ],
        submodules=[],
        moduledef=None,
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="GuardEq",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (
                            const.KEY_ASSIGN,
                            _varref("EmergencyShutdown"),
                            _varref("InCommand"),
                        )
                    ],
                )
            ]
        ),
        parametermappings=[],
        origin_file="Root.s",
    )
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[
            Variable(name="OperatorCommand", datatype=Simple_DataType.BOOLEAN, init_value=False),
        ],
        moduletype_defs=[guard_type],
        submodules=[
            ModuleTypeInstance(
                header=_hdr("Guard"),
                moduletype_name="GuardType",
                parametermappings=[
                    ParameterMapping(
                        target=_varref("InCommand"),
                        source_type=const.TREE_TAG_VARIABLE_NAME,
                        is_duration=False,
                        is_source_global=False,
                        source=_varref("OperatorCommand"),
                        source_literal=None,
                    )
                ],
            )
        ],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Main",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (
                            const.KEY_ASSIGN,
                            _varref("OperatorCommand"),
                            True,
                        )
                    ],
                )
            ]
        ),
        origin_file="Root.s",
    )

    report = analyze_taint_paths(bp)

    assert len(report.traces) == 1
    assert len(report.issues) == 1
    assert report.traces[0].source_kind == "operator"
    assert report.traces[0].source_canonical_path == "Root.OperatorCommand"
    assert report.traces[0].sink_canonical_path == "Root.Guard.EmergencyShutdown"
    assert report.traces[0].path == (
        "Root.OperatorCommand",
        "Root.Guard.InCommand",
        "Root.Guard.EmergencyShutdown",
    )
    assert report.traces[0].spans_multiple_modules is True
    assert report.issues[0].kind == "taint-path.external_input_to_critical_sink"
    assert report.issues[0].data is not None
    assert report.issues[0].data["source_kind"] == "operator"


def test_safety_paths_analyzer_is_enabled_by_default():
    specs = {spec.key: spec for spec in get_default_analyzers()}

    assert "safety-paths" in specs
    assert specs["safety-paths"].enabled is True


def test_taint_paths_analyzer_is_enabled_by_default():
    specs = {spec.key: spec for spec in get_default_analyzers()}

    assert "taint-paths" in specs
    assert specs["taint-paths"].enabled is True
