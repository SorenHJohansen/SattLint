"""Tests for full-suite analyzers.

Covers SFC parallel write race, dataflow, variables analyzer suites,
version drift, initial values, naming consistency, alarm integrity,
safety paths, and taint paths.
"""

import json
from types import SimpleNamespace
from typing import Any, cast

from sattline_parser.models.ast_model import (
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
from sattlint import constants as const
from sattlint.analyzers import registry as registry_module
from sattlint.analyzers._sfc_guard_logic import _normalize_guard_signature
from sattlint.analyzers.alarm_integrity import analyze_alarm_integrity
from sattlint.analyzers.dataflow import analyze_dataflow
from sattlint.analyzers.framework import AnalyzerSpec
from sattlint.analyzers.initial_values import analyze_initial_values
from sattlint.analyzers.mms import (
    _extract_external_tag,
    _find_parameter_mapping,
    _find_variable,
    _normalize_external_tag,
    _tag_family_key,
)
from sattlint.analyzers.modules import (
    AstDiffDetail,
    CodeDiff,
    ComparisonResult,
    SubmoduleDiff,
    VariableDiff,
    _build_upgrade_notes,
    _collect_named_item_diffs,
    _common_module_prefix,
    _compact_diff,
    _diff_normalized_variants,
    _group_instances_by_variant,
    _normalize_ast_value,
    analyze_version_drift,
    compare_modules,
    create_fingerprint,
)
from sattlint.analyzers.naming import analyze_naming_consistency, get_configured_naming_rules
from sattlint.analyzers.registry import get_default_analyzers
from sattlint.analyzers.safety_paths import analyze_safety_paths
from sattlint.analyzers.sfc import analyze_sfc
from sattlint.analyzers.taint_paths import analyze_taint_paths
from sattlint.analyzers.variable_usage_reporting import (
    _find_module_instances,
    analyze_datatype_usage,
    analyze_module_localvar_fields,
    debug_variable_usage,
)
from sattlint.analyzers.variables import IssueKind, VariablesAnalyzer


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


def test_registry_catalog_report_and_key_helpers_cover_metadata_branches():
    catalog = registry_module.get_default_analyzer_catalog()

    report = cast(dict[str, Any], catalog.to_report(generated_by="test-suite"))

    assert catalog.enabled_specs()
    assert report["generated_by"] == "test-suite"
    assert report["analyzers"]
    assert report["rules"]
    assert report["semantic_layer"]["analyzer_key"] == registry_module.SEMANTIC_LAYER_ANALYZER_KEY
    assert registry_module.get_declared_cli_analyzer_keys() == tuple(
        sorted(analyzer.spec.key for analyzer in catalog.analyzers if analyzer.delivery.cli_exposed)
    )
    assert registry_module.get_actual_cli_analyzer_keys() == tuple(
        spec.key for spec in registry_module.get_default_cli_analyzers()
    )
    assert registry_module.get_declared_lsp_analyzer_keys() == tuple(
        sorted(analyzer.spec.key for analyzer in catalog.analyzers if analyzer.delivery.lsp_exposed)
    )
    assert registry_module.get_actual_lsp_analyzer_keys()


def test_build_delivery_metadata_falls_back_for_unknown_analyzer_key():
    spec = AnalyzerSpec(
        key="custom-analyzer",
        name="Custom analyzer",
        description="Synthetic analyzer for fallback coverage.",
        run=lambda context: cast(Any, "custom-analyzer"),
    )

    delivery = registry_module._build_delivery_metadata(spec, ())

    assert delivery.scope == "workspace"
    assert delivery.implementation_bucket == "analyzers"
    assert delivery.output_artifacts == ("custom-analyzer.summary",)


def test_registry_rule_corpus_cache_and_default_runner_closures_cover_remaining_paths(tmp_path, monkeypatch):
    missing_manifest_dir = tmp_path / "missing-manifests"
    monkeypatch.setattr(registry_module, "DEFAULT_CORPUS_MANIFEST_DIR", missing_manifest_dir)
    registry_module._rule_corpus_cases_by_rule_id.cache_clear()
    assert registry_module._rule_corpus_cases_by_rule_id() == {}

    manifest_dir = tmp_path / "manifests"
    manifest_dir.mkdir()
    (manifest_dir / "skip.json").mkdir()
    (manifest_dir / "case-a.json").write_text(
        json.dumps({"expectation": {"expected_finding_ids": ["rule-A"]}}),
        encoding="utf-8",
    )

    monkeypatch.setattr(registry_module, "DEFAULT_CORPUS_MANIFEST_DIR", manifest_dir)
    registry_module._rule_corpus_cases_by_rule_id.cache_clear()
    assert registry_module._rule_corpus_cases_by_rule_id() == {"rule-A": ("case-a",)}

    calls: list[str] = []

    def _record(name: str):
        def _runner(*args, **kwargs):
            calls.append(name)
            return name

        return _runner

    monkeypatch.setattr(registry_module, "analyze_variables", _record("variables"))
    monkeypatch.setattr(registry_module, "analyze_sattline_semantics", _record("sattline-semantics"))
    monkeypatch.setattr(registry_module, "analyze_mms_interface_variables", _record("mms-interface"))
    monkeypatch.setattr(registry_module, "analyze_sfc", _record("sfc"))
    monkeypatch.setattr(registry_module, "analyze_shadowing", _record("shadowing"))
    monkeypatch.setattr(registry_module, "analyze_spec_compliance", _record("spec-compliance"))
    monkeypatch.setattr(registry_module, "analyze_loop_output_refactor", _record("loop-output-refactor"))
    monkeypatch.setattr(registry_module, "analyze_alarm_integrity", _record("alarm-integrity"))
    monkeypatch.setattr(registry_module, "analyze_initial_values", _record("initial-values"))
    monkeypatch.setattr(registry_module, "analyze_naming_consistency", _record("naming-consistency"))
    monkeypatch.setattr(registry_module, "analyze_cyclomatic_complexity", _record("cyclomatic-complexity"))
    monkeypatch.setattr(registry_module, "analyze_parameter_drift", _record("parameter-drift"))
    monkeypatch.setattr(registry_module, "analyze_scan_loop_resource_usage", _record("scan-loop-resource-usage"))
    monkeypatch.setattr(registry_module, "analyze_version_drift", _record("version-drift"))
    monkeypatch.setattr(registry_module, "analyze_safety_paths", _record("safety-paths"))
    monkeypatch.setattr(registry_module, "analyze_taint_paths", _record("taint-paths"))
    monkeypatch.setattr(registry_module, "analyze_unsafe_defaults", _record("unsafe-defaults"))
    monkeypatch.setattr(registry_module, "analyze_dataflow", _record("dataflow"))
    monkeypatch.setattr(registry_module, "analyze_state_inference", _record("state_inference"))
    monkeypatch.setattr(registry_module, "analyze_comment_code", _record("comment-code"))
    monkeypatch.setattr(registry_module, "get_configured_mutually_exclusive_step_sets", lambda config: ("mutex",))
    monkeypatch.setattr(registry_module, "get_configured_step_contracts", lambda config: ("contracts",))
    monkeypatch.setattr(registry_module, "get_configured_naming_rules", lambda config: ("rules",))

    specs = {spec.key: spec for spec in registry_module.get_default_analyzers()}
    context: Any = SimpleNamespace(
        base_picture="bp",
        debug=True,
        unavailable_libraries={"MissingLib"},
        target_is_library=True,
        config={"profile": "test"},
    )
    expected_keys = {
        registry_module.SEMANTIC_LAYER_ANALYZER_KEY,
        "variables",
        "mms-interface",
        "sfc",
        "shadowing",
        "spec-compliance",
        "loop-output-refactor",
        "alarm-integrity",
        "initial-values",
        "naming-consistency",
        "cyclomatic-complexity",
        "parameter-drift",
        "scan-loop-resource-usage",
        "version-drift",
        "safety-paths",
        "taint-paths",
        "unsafe-defaults",
        "dataflow",
        "state_inference",
        "comment-code",
    }

    for key in expected_keys:
        assert specs[key].run(context) == key

    assert set(calls) == expected_keys
    registry_module._rule_corpus_cases_by_rule_id.cache_clear()


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


def test_state_inference_analyzer_is_not_in_default_cli_subset():
    from sattlint.analyzers.registry import get_actual_cli_analyzer_keys

    assert "state_inference" not in get_actual_cli_analyzer_keys()


def test_mms_tag_helpers_normalize_external_tags_and_family_keys():
    assert _normalize_external_tag("  Unit.Area.Tag42  ") == "unit.area.tag42"
    assert _normalize_external_tag("12345") is None
    assert _tag_family_key("Plant-AB12.PV") == "plant|ab|12|pv"
    assert _tag_family_key("   ") is None


def test_mms_mapping_helpers_match_casefold_names():
    mapping = ParameterMapping(
        target=_varref("WriteData"),
        source_type=const.TREE_TAG_VARIABLE_NAME,
        is_duration=False,
        is_source_global=False,
        source=_varref("OutTag"),
        source_literal=None,
    )
    variables = [Variable(name="RemoteVarName", datatype=Simple_DataType.TAGSTRING, init_value="TagA")]

    found_mapping = _find_parameter_mapping([mapping], "writedata")
    found_variable = _find_variable(variables, "remotevarname")

    assert found_mapping is mapping
    assert found_variable is variables[0]


def test_mms_extract_external_tag_uses_literal_parameter_mapping_value():
    instance = ModuleTypeInstance(
        header=_hdr("MmsWrite"),
        moduletype_name="MMSWriteVar",
        parametermappings=[
            ParameterMapping(
                target=_varref("Tag"),
                source_type=const.KEY_VALUE,
                is_duration=False,
                is_source_global=False,
                source_literal="Plant.Unit.Tag01",
            )
        ],
    )
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[],
        submodules=[instance],
        modulecode=None,
        moduledef=None,
    )

    tag = _extract_external_tag(bp, ["Root", "MmsWrite"], instance, None)

    assert tag == "Plant.Unit.Tag01"


def test_variable_usage_datatype_report_returns_not_found_message():
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[],
        submodules=[],
        modulecode=None,
        moduledef=None,
    )

    report = analyze_datatype_usage(bp, "MissingValue")

    assert report == "Variable 'MissingValue' not found."


def test_variable_usage_reports_include_field_and_whole_variable_accesses():
    record_type = DataType(
        name="UsageRecord",
        description=None,
        datecode=None,
        var_list=[
            Variable(name="Source", datatype=Simple_DataType.INTEGER),
            Variable(name="Target", datatype=Simple_DataType.INTEGER),
        ],
    )
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[record_type],
        moduletype_defs=[],
        localvariables=[],
        submodules=[
            SingleModule(
                header=_hdr("Unit"),
                moduledef=None,
                moduleparameters=[],
                localvariables=[
                    Variable(name="Dv", datatype="UsageRecord"),
                    Variable(name="Mirror", datatype="UsageRecord"),
                    Variable(name="Sink", datatype=Simple_DataType.INTEGER),
                ],
                submodules=[],
                modulecode=ModuleCode(
                    equations=[
                        Equation(
                            name="Usage",
                            position=(0.0, 0.0),
                            size=(1.0, 1.0),
                            code=[
                                (const.KEY_ASSIGN, _varref("Sink"), _varref("Dv.Source")),
                                (const.KEY_ASSIGN, _varref("Dv.Target"), IntLiteral(1)),
                                (const.KEY_ASSIGN, _varref("Mirror"), _varref("Dv")),
                                (const.KEY_ASSIGN, _varref("Dv"), _varref("Mirror")),
                            ],
                        )
                    ]
                ),
                parametermappings=[],
            )
        ],
        modulecode=None,
        moduledef=None,
    )

    datatype_report = analyze_datatype_usage(bp, "Dv")
    debug_report = debug_variable_usage(bp, "Dv")

    assert "Field usage analysis for variable 'Dv':" in datatype_report
    assert "Fields accessed: 2" in datatype_report
    assert "source: read (r:1, w:0)" in datatype_report.lower()
    assert "target: write (r:0, w:1)" in datatype_report.lower()
    assert "Usage report for variable name 'Dv' (1 declaration(s)):" in debug_report
    assert "Field reads:" in debug_report
    assert "dv.source" in debug_report.lower()
    assert "Field writes:" in debug_report
    assert "dv.target" in debug_report.lower()
    assert "Whole variable:" in debug_report
    assert "R:1 W:1 | Root -> Unit" in debug_report


def test_module_localvar_field_report_includes_filtered_summary_sections():
    record_type = DataType(
        name="UsageRecord",
        description=None,
        datecode=None,
        var_list=[
            Variable(name="Source", datatype=Simple_DataType.INTEGER),
            Variable(name="Target", datatype=Simple_DataType.INTEGER),
        ],
    )
    child = SingleModule(
        header=_hdr("Child"),
        moduledef=None,
        moduleparameters=[Variable(name="Input", datatype="UsageRecord")],
        localvariables=[],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="ChildEq",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (const.KEY_ASSIGN, _varref("Input.Target"), IntLiteral(2)),
                    ],
                )
            ]
        ),
        parametermappings=[
            ParameterMapping(
                target=_varref("Input"),
                source_type=const.TREE_TAG_VARIABLE_NAME,
                is_duration=False,
                is_source_global=False,
                source=_varref("Dv"),
                source_literal=None,
            )
        ],
    )
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[record_type],
        moduletype_defs=[],
        localvariables=[],
        submodules=[
            SingleModule(
                header=_hdr("Unit"),
                moduledef=None,
                moduleparameters=[],
                localvariables=[
                    Variable(name="Dv", datatype="UsageRecord"),
                    Variable(name="Mirror", datatype="UsageRecord"),
                    Variable(name="Sink", datatype=Simple_DataType.INTEGER),
                ],
                submodules=[child],
                modulecode=ModuleCode(
                    equations=[
                        Equation(
                            name="Usage",
                            position=(0.0, 0.0),
                            size=(1.0, 1.0),
                            code=[
                                (const.KEY_ASSIGN, _varref("Sink"), _varref("Dv.Source")),
                                (const.KEY_ASSIGN, _varref("Dv.Target"), IntLiteral(1)),
                                (const.KEY_ASSIGN, _varref("Mirror"), _varref("Dv")),
                                (const.KEY_ASSIGN, _varref("Dv"), _varref("Mirror")),
                            ],
                        )
                    ]
                ),
                parametermappings=[],
            )
        ],
        modulecode=None,
        moduledef=None,
    )

    report = analyze_module_localvar_fields(bp, "Unit", "Dv")

    assert "Field usage analysis for local variable 'Dv' in module path 'Root.Unit'" in report
    assert "FIELD-LEVEL ACCESSES:" in report
    assert "dv.source [read]" in report.lower()
    assert "dv.target [write]" in report.lower()
    assert "WHOLE VARIABLE ACCESSES:" in report
    assert "Reads (1 total, 1 unique location(s))" in report
    assert "SUMMARY:" in report
    assert "Aliased parameters: 2" in report
    assert "Fields accessed: 2" in report
    assert "Total field reads: 1" in report
    assert "Total field writes: 3" in report
    assert "Whole variable reads: 1" in report
    assert "Whole variable writes: 2" in report


def test_find_module_instances_includes_direct_and_typedef_expansions():
    parent_typedef = ModuleTypeDef(
        name="ParentType",
        moduleparameters=[],
        localvariables=[],
        submodules=[
            ModuleTypeInstance(
                header=_hdr("WantedAlias"),
                moduletype_name="WantedType",
                parametermappings=[],
            )
        ],
        moduledef=None,
        modulecode=None,
        parametermappings=[],
    )
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[parent_typedef],
        localvariables=[],
        submodules=[
            ModuleTypeInstance(
                header=_hdr("DirectWanted"),
                moduletype_name="WantedType",
                parametermappings=[],
            ),
            ModuleTypeInstance(
                header=_hdr("ParentInstance"),
                moduletype_name="ParentType",
                parametermappings=[],
            ),
        ],
        modulecode=None,
        moduledef=None,
    )

    results = _find_module_instances(bp, "WantedType")
    paths = {tuple(path) for _module, path in results}

    assert ("Root", "DirectWanted") in paths
    assert ("Root", "ParentInstance", "WantedAlias") in paths


def test_module_diff_helpers_detect_modified_and_variant_only_names():
    variant_items: list[dict[str, tuple[str, object]]] = [
        {
            "alpha": ("Alpha", ("int", 1)),
            "beta": ("Beta", ("int", 2)),
        },
        {
            "alpha": ("Alpha", ("int", 3)),
            "gamma": ("Gamma", ("int", 4)),
        },
    ]

    common, only_in_variant, modified = _collect_named_item_diffs(variant_items)

    assert common == ["Alpha"]
    assert only_in_variant == {1: ["Beta"], 2: ["Gamma"]}
    assert "Alpha" in modified


def test_module_ast_normalizer_casefolds_names_and_ignores_position_fields():
    normalized_dict = _normalize_ast_value(
        {
            "var_name": "MiXeD",
            "state": "NeW",
            "position": (1.0, 2.0),
        }
    )
    normalized_var = _normalize_ast_value(Variable(name="FlowRate", datatype=Simple_DataType.INTEGER))

    assert "position" not in repr(normalized_dict)
    assert "mixed" in repr(normalized_dict)
    assert "new" in repr(normalized_dict)
    assert "flowrate" in repr(normalized_var)


def test_module_diff_helpers_report_nested_variant_details_and_missing_items():
    variants = {
        1: _normalize_ast_value({"Config": [{"Mode": "Auto"}]}),
        2: _normalize_ast_value({"Config": [{"Mode": "Manual"}, {"Enabled": True}]}),
    }

    details = _diff_normalized_variants(variants)

    paths = {detail.path for detail in details}
    assert "Config[0].Mode" in paths
    assert "Config[1]" in paths
    detail_map = {detail.path: detail.variants for detail in details}
    assert detail_map["Config[1]"][1] == "<missing>"


def test_module_comparison_summary_covers_empty_and_single_variant_reports():
    empty_summary = ComparisonResult(module_name="Pump", total_found=0, unique_variants=0).summary()

    module = SingleModule(
        header=_hdr("Pump"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[],
        submodules=[],
        modulecode=None,
        parametermappings=[],
    )
    fingerprint = create_fingerprint(module, ["Root", "Pump"])
    single_summary = ComparisonResult(
        module_name="Pump",
        total_found=1,
        unique_variants=1,
        fingerprints=[fingerprint],
        all_instances=[(["Root", "Pump"], fingerprint)],
    ).summary()

    assert "No modules found with this name" in empty_summary
    assert "All instances are structurally identical" in single_summary
    assert "DateCode: None - Root" in single_summary


def test_module_comparison_summary_lists_variant_differences():
    variant_a = SingleModule(
        header=_hdr("Pump"),
        moduledef=None,
        moduleparameters=[Variable(name="CommonParam", datatype=Simple_DataType.INTEGER)],
        localvariables=[Variable(name="OnlyA", datatype=Simple_DataType.INTEGER)],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="MainEq",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[(const.KEY_ASSIGN, _varref("OnlyA"), IntLiteral(1))],
                )
            ]
        ),
        parametermappings=[],
    )
    variant_b = SingleModule(
        header=_hdr("Pump"),
        moduledef=None,
        moduleparameters=[Variable(name="CommonParam", datatype=Simple_DataType.INTEGER)],
        localvariables=[Variable(name="OnlyB", datatype=Simple_DataType.INTEGER)],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="OtherEq",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[(const.KEY_ASSIGN, _varref("OnlyB"), IntLiteral(2))],
                )
            ]
        ),
        parametermappings=[],
    )
    fingerprint_a = create_fingerprint(variant_a, ["Root", "PumpA"])
    fingerprint_b = create_fingerprint(variant_b, ["Root", "PumpB"])

    summary = ComparisonResult(
        module_name="Pump",
        total_found=2,
        unique_variants=2,
        fingerprints=[fingerprint_a, fingerprint_b],
        all_instances=[(["Root", "PumpA"], fingerprint_a), (["Root", "PumpB"], fingerprint_b)],
        parameter_diff=VariableDiff(common=["CommonParam"], only_in_variant={1: [], 2: []}),
        localvar_diff=VariableDiff(common=[], only_in_variant={1: ["OnlyA"], 2: ["OnlyB"]}),
        submodule_diff=SubmoduleDiff(common=[(0, "SharedChild", "Single")], only_in_variant={1: [], 2: []}),
        code_diff=CodeDiff(
            sequences_common=[],
            sequences_only_in_variant={1: [], 2: []},
            equations_common=[],
            equations_only_in_variant={1: ["MainEq"], 2: ["OtherEq"]},
        ),
    ).summary()

    assert "Found 2 different structural variants" in summary
    assert "Module Parameters Differences" in summary
    assert "Local Variables Differences" in summary
    assert "Submodules Differences (Recursive Tree)" in summary
    assert "Equations Only in Variant 1 (1): ['MainEq']" in summary


def test_module_diff_compaction_and_upgrade_notes_cover_modified_buckets():
    parameter_diff = VariableDiff(
        common=["SharedParam"],
        only_in_variant={1: ["OnlyParam"], 2: []},
        modified={
            "SharedParam": [
                AstDiffDetail(path="datatype", variants={1: "'INTEGER'", 2: "'REAL'"}),
            ]
        },
    )
    localvar_diff = VariableDiff(
        common=[],
        only_in_variant={1: [], 2: ["OnlyLocal"]},
        modified={
            "SharedLocal": [
                AstDiffDetail(path="init_value", variants={1: "1", 2: "2"}),
            ]
        },
    )
    submodule_diff = SubmoduleDiff(
        common=[(0, "SharedChild", "Single")],
        only_in_variant={1: [(1, "OnlyChild", "Frame")], 2: []},
    )
    code_diff = CodeDiff(
        sequences_common=["SharedSeq"],
        sequences_only_in_variant={1: ["OnlySeq"], 2: []},
        equations_common=["SharedEq"],
        equations_only_in_variant={1: [], 2: ["OnlyEq"]},
        modified_sequences={
            "SharedSeq": [
                AstDiffDetail(path="code[0]", variants={1: "'Auto'", 2: "'Manual'"}),
            ]
        },
        modified_equations={
            "SharedEq": [
                AstDiffDetail(path="code[1]", variants={1: "1", 2: "2"}),
            ]
        },
    )

    compact_parameter = _compact_diff(parameter_diff)
    compact_localvar = _compact_diff(localvar_diff)
    compact_submodule = _compact_diff(submodule_diff)
    compact_code = _compact_diff(code_diff)
    notes = _build_upgrade_notes(
        {
            "moduleparameters": compact_parameter,
            "localvariables": compact_localvar,
            "submodules": compact_submodule,
            "code": compact_code,
        }
    )

    assert compact_parameter is not None
    assert compact_parameter["modified"]["SharedParam"][0]["path"] == "datatype"
    assert compact_localvar is not None
    assert compact_localvar["only_in_variant"] == {2: ["OnlyLocal"]}
    assert compact_submodule is not None
    assert compact_submodule["only_in_variant"] == {1: [[1, "OnlyChild", "Frame"]]}
    assert compact_code is not None
    assert compact_code["modified_sequences"]["SharedSeq"][0]["path"] == "code[0]"
    assert _compact_diff(SubmoduleDiff(common=[], only_in_variant={1: [], 2: []})) is None
    assert any(note == "Module parameters only in variant 1: OnlyParam." for note in notes)
    assert any(note == "Module parameter 'SharedParam' changed across variants 1, 2 at datatype." for note in notes)
    assert any(note == "Local variables only in variant 2: OnlyLocal." for note in notes)
    assert any(note == "Sequence 'SharedSeq' changed across variants 1, 2 at code[0]." for note in notes)
    assert any(note == "Equations only in variant 2: OnlyEq." for note in notes)
    assert any(note == "Submodule structure differs in variant 1: 1 unique node(s)." for note in notes)


def test_module_variant_grouping_collapses_identical_structures_and_common_prefix():
    shared_a = SingleModule(
        header=_hdr("Pump"),
        datecode=100,
        moduledef=None,
        moduleparameters=[Variable(name="Shared", datatype=Simple_DataType.INTEGER)],
        localvariables=[],
        submodules=[],
        modulecode=None,
        parametermappings=[],
    )
    shared_b = SingleModule(
        header=_hdr("Pump"),
        datecode=200,
        moduledef=None,
        moduleparameters=[Variable(name="Shared", datatype=Simple_DataType.INTEGER)],
        localvariables=[],
        submodules=[],
        modulecode=None,
        parametermappings=[],
    )
    drifted = SingleModule(
        header=_hdr("Pump"),
        datecode=300,
        moduledef=None,
        moduleparameters=[Variable(name="Shared", datatype=Simple_DataType.INTEGER)],
        localvariables=[Variable(name="OnlyHere", datatype=Simple_DataType.INTEGER)],
        submodules=[],
        modulecode=None,
        parametermappings=[],
    )

    comparison = compare_modules(
        [
            (["Root", "Area", "PumpA"], shared_a),
            (["root", "area", "PumpB"], shared_b),
            (["Root", "Other", "PumpC"], drifted),
        ]
    )
    grouped = _group_instances_by_variant(comparison)

    assert comparison.unique_variants == 2
    assert len(grouped[1]) == 2
    assert len(grouped[2]) == 1
    assert _common_module_prefix(
        [["Root", "Area", "PumpA"], ["root", "area", "PumpB"], ["Root", "Other", "PumpC"]]
    ) == ["Root"]


def test_sfc_guard_signature_collapses_contradictory_and_expression_to_false():
    signature = _normalize_guard_signature(
        (
            const.GRAMMAR_VALUE_AND,
            [
                _varref("Permit"),
                (const.GRAMMAR_VALUE_NOT, _varref("Permit")),
            ],
        )
    )

    assert signature == ("bool", False)
