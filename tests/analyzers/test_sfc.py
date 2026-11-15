# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportPrivateUsage=false, reportArgumentType=false, reportAttributeAccessIssue=false, reportMissingTypeArgument=false, reportOptionalSubscript=false
"""Tests for SFC analyzer checks."""

from sattline_parser.ast import Assignment, VarRef
from sattline_parser.models.ast_model import (
    BasePicture,
    FrameModule,
    ModuleCode,
    ModuleHeader,
    ModuleTypeDef,
    ScalarDatatype,
    Sequence,
    SFCAlternative,
    SFCCodeBlocks,
    SFCFork,
    SFCParallel,
    SFCStep,
    SFCSubsequence,
    SFCTransition,
    SFCTransitionSub,
    SingleModule,
    Variable,
)

from sattlint.analyzers import sfc as sfc_module
from sattlint.analyzers import variables as variables_module
from sattlint.analyzers.framework import AnalysisContext, AnalysisSharedArtifacts, Issue
from sattlint.analyzers.same_cycle import analyze_same_cycle
from sattlint.analyzers.sfc import analyze_sfc
from sattlint.analyzers.sfc._sfc_module_walk import iter_sfc_modulecodes
from sattlint.analyzers.variables import analyze_variables


def _hdr(name: str) -> ModuleHeader:
    return ModuleHeader(name=name, invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0))


def _varref(name: str) -> VarRef:
    return VarRef(name=name)


def _assign(name: str, value: object) -> Assignment:
    return Assignment(target=_varref(name), value=value)


def _step(name: str, active_stmts: list[object]) -> SFCStep:
    return SFCStep(kind="step", name=name, code=SFCCodeBlocks(active=active_stmts))


def _fork_step(name: str, targets: tuple[str, ...], *, has_break: bool = False) -> SFCStep:
    return SFCStep(
        kind="step",
        name=name,
        code=SFCCodeBlocks(),
        fork=SFCFork(targets=targets, has_break=has_break),
    )


def _sequence(nodes: list[object]) -> Sequence:
    return Sequence(
        name="SeqMain",
        type="sequence",
        position=(0.0, 0.0),
        size=(1.0, 1.0),
        code=nodes,
    )


def test_parallel_branch_write_race_detected():
    seq = _sequence(
        [
            SFCParallel(
                branches=[
                    [_step("Left", [_assign("Output", 1)])],
                    [_step("Right", [_assign("Output", 2)])],
                ]
            )
        ]
    )

    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[Variable(name="Output", datatype=ScalarDatatype.INTEGER)],
        modulecode=ModuleCode(sequences=[seq], equationblocks=[]),
    )

    report = analyze_same_cycle(bp)

    assert any(i.kind == "sfc_parallel_write_race" for i in report.issues)


def test_parallel_branch_distinct_writes_not_reported():
    seq = _sequence(
        [
            SFCParallel(
                branches=[
                    [_step("Left", [_assign("OutputA", 1)])],
                    [_step("Right", [_assign("OutputB", 2)])],
                ]
            )
        ]
    )

    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[
            Variable(name="OutputA", datatype=ScalarDatatype.INTEGER),
            Variable(name="OutputB", datatype=ScalarDatatype.INTEGER),
        ],
        modulecode=ModuleCode(sequences=[seq], equationblocks=[]),
    )

    report = analyze_same_cycle(bp)

    assert not report.issues


def test_analyze_same_cycle_parallel_write_race_selection_skips_other_issue_collectors(monkeypatch):
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[Variable(name="Output", datatype=ScalarDatatype.INTEGER)],
        modulecode=ModuleCode(
            sequences=[
                _sequence(
                    [
                        SFCParallel(
                            branches=[
                                [_step("Left", [_assign("Output", 1)])],
                                [_step("Right", [_assign("Output", 2)])],
                            ]
                        )
                    ]
                )
            ],
            equationblocks=[],
        ),
    )

    report = analyze_same_cycle(
        bp,
        selected_issue_kinds={"sfc_parallel_write_race"},
    )

    assert [issue.kind for issue in report.issues] == ["sfc_parallel_write_race"]


def test_iter_sfc_modulecodes_covers_root_nested_modules_and_typedefs():
    nested_frame = FrameModule(
        header=_hdr("FrameChild"),
        modulecode=ModuleCode(sequences=[], equationblocks=[]),
        submodules=[],
    )
    nested_single = SingleModule(
        header=_hdr("UnitChild"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[],
        submodules=[nested_frame],
        modulecode=ModuleCode(sequences=[], equationblocks=[]),
    )
    moduletype = ModuleTypeDef(
        name="TypeLogic",
        modulecode=ModuleCode(sequences=[], equationblocks=[]),
    )
    bp = BasePicture(
        header=_hdr("Root"),
        submodules=[nested_single],
        moduletype_defs=[moduletype],
        modulecode=ModuleCode(sequences=[], equationblocks=[]),
    )

    entries = list(iter_sfc_modulecodes(bp))

    assert [path for path, _modulecode in entries] == [
        ["Root"],
        ["Root", "UnitChild"],
        ["Root", "UnitChild", "FrameChild"],
        ["Root", "TypeDef:TypeLogic"],
    ]


def test_sfc_reachability_and_active_step_helpers_cover_nested_nodes_and_previews(monkeypatch) -> None:
    findings: list[sfc_module.SfcReachabilityFinding] = []
    sfc_module._inspect_sfc_linear_nodes(
        findings,
        [
            _fork_step("Break", ("Done",), has_break=True),
            _step("Active", []),
            SFCTransition(name="LateGate", condition=True),
        ],
        ["Root"],
        "SeqMain",
    )

    branch_findings: list[sfc_module.SfcReachabilityFinding] = []
    sfc_module._inspect_sfc_linear_nodes(
        branch_findings,
        [
            SFCAlternative(branches=[[_fork_step("Break", ("Done",), has_break=True), _step("AltDead", [])]]),
            SFCSubsequence(name="NestedSeq", body=[_fork_step("Break", ("Done",)), _step("Nested", [])]),
            SFCTransitionSub(
                name="NestedGate",
                body=[
                    SFCStep(
                        kind="step",
                        name="Fork",
                        code=SFCCodeBlocks(),
                        fork=SFCFork(targets=("Done",)),
                    ),
                    SFCTransition(name="AfterFork", condition=True),
                ],
            ),
        ],
        ["Root"],
        "SeqMain",
    )

    assert [finding.node_label for finding in findings] == [
        "SFCStep:Active",
        "SFCTransition:LateGate",
    ]
    assert [finding.node_label for finding in branch_findings] == [
        "SFCStep:AltDead",
        "SFCStep:Nested",
        "SFCTransition:AfterFork",
    ]
    assert findings[0].terminated_by == {"kind": "SFCFork", "targets": ["Done"]}
    assert branch_findings[0].branch_path == (0,)
    assert branch_findings[-1].terminated_by == {"kind": "SFCFork", "targets": ["Done"]}
    assert sfc_module._sequence_node_label(SFCTransition(name=None, condition=None)) == "SFCTransition"

    sequence = _sequence([_step("Idle", []), _step("Running", [])])
    bp = BasePicture(
        header=_hdr("Root"),
        submodules=[FrameModule(header=_hdr("NoCode"), modulecode=None, submodules=[])],
        modulecode=ModuleCode(sequences=[sequence], equationblocks=[]),
    )
    assert sfc_module.collect_sfc_reachability_findings(bp) == []
    assert sfc_module._format_terminator({"kind": "SFCFork", "targets": ["Left", 7, "Right"]}) == (
        "SFCFork targeting 'Left', 'Right'"
    )
    assert sfc_module._format_terminator({}) == "an earlier terminating node"


def test_analyze_sfc_covers_selected_collectors_and_reachability_messages(monkeypatch) -> None:
    monkeypatch.setattr(
        sfc_module,
        "collect_sfc_reachability_findings",
        lambda _bp, **kwargs: [
            sfc_module.SfcReachabilityFinding(
                module_path=("Root",),
                sequence_name="SeqMain",
                branch_path=(1,),
                node_index=2,
                node_label="SFCTransition:LateGate",
                node_type="SFCTransition",
                terminated_by={"kind": "SFCBreak"},
            ),
            sfc_module.SfcReachabilityFinding(
                module_path=("Root",),
                sequence_name="SeqMain",
                branch_path=(),
                node_index=3,
                node_label="SFCStep:LateStep",
                node_type="SFCStep",
                terminated_by={"kind": "SFCFork", "targets": ["Done"]},
            ),
        ],
    )
    monkeypatch.setattr(
        sfc_module,
        "_collect_transition_logic_issues",
        lambda _bp, **kwargs: [Issue(kind="sfc_duplicate_transition_guard", message="logic")],
    )

    report = analyze_sfc(BasePicture(header=_hdr("Root")))

    kinds = [issue.kind for issue in report.issues]
    assert kinds == [
        "sfc_unreachable_transition",
        "sfc_unreachable_sequence_node",
        "sfc_duplicate_transition_guard",
    ]
    assert report.issues[0].data["branch_path"] == [1]
    assert "targeting 'Done'" in report.issues[1].message


def test_analyze_sfc_reuses_variable_artifacts_when_available(monkeypatch):
    build_calls: list[str] = []
    original_builder = variables_module._build_variable_analysis_artifacts

    def _recording_builder(base_picture):
        build_calls.append(base_picture.header.name)
        return original_builder(base_picture)

    monkeypatch.setattr(variables_module, "_build_variable_analysis_artifacts", _recording_builder)

    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[Variable(name="Output", datatype=ScalarDatatype.INTEGER)],
        modulecode=ModuleCode(
            sequences=[
                _sequence(
                    [
                        SFCParallel(
                            branches=[
                                [_step("Left", [_assign("Output", 1)])],
                                [_step("Right", [_assign("Output", 2)])],
                            ]
                        )
                    ]
                )
            ],
            equationblocks=[],
        ),
    )
    shared_artifacts = AnalysisSharedArtifacts()
    context = AnalysisContext(base_picture=bp, shared_artifacts=shared_artifacts)

    analyze_variables(bp, analysis_context=context)
    analyze_sfc(bp, analysis_context=context, selected_issue_kinds={"sfc_unreachable_transition"})

    assert build_calls == ["Root"]
    assert shared_artifacts.counters.variable_foundation_builds == 1
