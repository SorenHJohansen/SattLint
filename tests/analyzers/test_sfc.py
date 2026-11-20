# These tests deliberately exercise private analyzer seams.
# pyright: reportPrivateUsage=false

"""Tests for SFC analyzer checks."""

from collections.abc import Sequence as SequenceABC

import pytest
from sattline_parser.ast import Assignment, VarRef
from sattline_parser.models.ast_model import (
    BasePicture,
    CodeComment,
    CodeItem,
    FrameModule,
    ModuleCode,
    ModuleHeader,
    ModuleTypeDef,
    ScalarDatatype,
    Sequence,
    SFCAlternative,
    SFCBodyItem,
    SFCCodeBlocks,
    SFCFork,
    SFCParallel,
    SFCStep,
    SFCSubsequence,
    SFCTransition,
    SFCTransitionSub,
    SingleModule,
    SLExpression,
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


def _assign(name: str, value: SLExpression) -> Assignment:
    return Assignment(target=_varref(name), value=value)


def _step(name: str, active_stmts: list[CodeItem]) -> SFCStep:
    return SFCStep(kind="step", name=name, code=SFCCodeBlocks(active=active_stmts))


def _fork_step(name: str, targets: tuple[str, ...], *, has_break: bool = False) -> SFCStep:
    return SFCStep(
        kind="step",
        name=name,
        code=SFCCodeBlocks(),
        fork=SFCFork(targets=targets, has_break=has_break),
    )


def _sequence(nodes: SequenceABC[SFCBodyItem]) -> Sequence:
    return Sequence(
        name="SeqMain",
        type="sequence",
        position=(0.0, 0.0),
        size=(1.0, 1.0),
        code=list(nodes),
    )


@pytest.mark.parametrize("opening", ["init", "comment", "step", "transition", "alternative", "parallel", "empty"])
def test_each_sequence_must_begin_with_an_initial_step(opening: str) -> None:
    initial = SFCStep(kind="init", name="Start", code=SFCCodeBlocks())
    if opening == "init":
        nodes = [
            initial,
            SFCTransition(name="Proceed", condition=True),
            SFCAlternative(branches=[[_step("BranchStep", [])], [_step("OtherStep", [])]]),
        ]
    elif opening == "comment":
        nodes = [CodeComment(text="Sequence notes"), initial]
    elif opening == "step":
        nodes = [_step("NotInitial", []), SFCTransition(name="Later", condition=True), initial]
    elif opening == "transition":
        nodes = [SFCTransition(name="TooEarly", condition=True), initial]
    elif opening == "alternative":
        nodes = [SFCAlternative(branches=[[initial], [_step("OtherStep", [])]])]
    elif opening == "parallel":
        nodes = [SFCParallel(branches=[[initial], [_step("OtherStep", [])]])]
    else:
        nodes = []
    bp = BasePicture(header=_hdr("Root"), modulecode=ModuleCode(sequences=[_sequence(nodes)]))
    report = analyze_sfc(bp)
    issues = [issue for issue in report.issues if issue.kind == "sfc_missing_initial_step"]
    assert bool(issues) is (opening not in {"init", "comment"})
    if issues:
        assert len(issues) == 1
        assert issues[0].message == "Sequence 'SeqMain' must begin with an initial step (SEQINITSTEP)."
        assert issues[0].module_path == ["Root"]
        assert issues[0].data is not None and issues[0].data["site"] == "SQ:SeqMain"


def test_sequence_start_check_reaches_nested_library_modules_and_respects_selection() -> None:
    invalid = _sequence([_step("NotInitial", [])])
    library = ModuleTypeDef(
        name="LibraryType",
        submodules=[
            FrameModule(
                header=_hdr("Frame"),
                submodules=[
                    SingleModule(
                        header=_hdr("Logic"),
                        modulecode=ModuleCode(sequences=[invalid]),
                    )
                ],
            )
        ],
    )
    bp = BasePicture(header=_hdr("Root"), moduletype_defs=[library])
    report = analyze_sfc(bp, selected_issue_kinds={"sfc_missing_initial_step"})
    assert len(report.issues) == 1
    assert report.issues[0].module_path == ["Root", "TypeDef:LibraryType", "Frame", "Logic"]
    assert not analyze_sfc(bp, selected_issue_kinds={"sfc_duplicate_transition_guard"}).issues


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


def test_analyze_same_cycle_parallel_write_race_selection_skips_other_issue_collectors(monkeypatch: pytest.MonkeyPatch):
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


def test_sfc_reachability_and_active_step_helpers_cover_nested_nodes_and_previews(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
    assert findings[0].terminated_by == sfc_module.SfcTerminator(kind="SFCFork", targets=("Done",))
    assert branch_findings[0].branch_path == (0,)
    assert branch_findings[-1].terminated_by == sfc_module.SfcTerminator(kind="SFCFork", targets=("Done",))
    assert sfc_module._sequence_node_label(SFCTransition(name=None, condition=None)) == "SFCTransition"

    sequence = _sequence([_step("Idle", []), _step("Running", [])])
    bp = BasePicture(
        header=_hdr("Root"),
        submodules=[FrameModule(header=_hdr("NoCode"), modulecode=None, submodules=[])],
        modulecode=ModuleCode(sequences=[sequence], equationblocks=[]),
    )
    assert sfc_module.collect_sfc_reachability_findings(bp) == []
    assert sfc_module._format_terminator(sfc_module.SfcTerminator(kind="SFCFork", targets=("Left", "Right"))) == (
        "SFCFork targeting 'Left', 'Right'"
    )
    assert sfc_module._format_terminator(sfc_module.SfcTerminator(kind="SFCBreak")) == "SFCBreak"


def test_analyze_sfc_covers_selected_collectors_and_reachability_messages(monkeypatch: pytest.MonkeyPatch) -> None:
    def _reachability_findings(
        _bp: BasePicture,
        **_kwargs: object,
    ) -> list[sfc_module.SfcReachabilityFinding]:
        return [
            sfc_module.SfcReachabilityFinding(
                module_path=("Root",),
                sequence_name="SeqMain",
                branch_path=(1,),
                node_index=2,
                node_label="SFCTransition:LateGate",
                node_type="SFCTransition",
                terminated_by=sfc_module.SfcTerminator(kind="SFCBreak"),
            ),
            sfc_module.SfcReachabilityFinding(
                module_path=("Root",),
                sequence_name="SeqMain",
                branch_path=(),
                node_index=3,
                node_label="SFCStep:LateStep",
                node_type="SFCStep",
                terminated_by=sfc_module.SfcTerminator(kind="SFCFork", targets=("Done",)),
            ),
        ]

    def _transition_logic_issues(_bp: BasePicture, **_kwargs: object) -> list[Issue]:
        return [Issue(kind="sfc_duplicate_transition_guard", message="logic")]

    monkeypatch.setattr(sfc_module, "collect_sfc_reachability_findings", _reachability_findings)
    monkeypatch.setattr(sfc_module, "_collect_transition_logic_issues", _transition_logic_issues)

    report = analyze_sfc(BasePicture(header=_hdr("Root")))

    kinds = [issue.kind for issue in report.issues]
    assert kinds == [
        "sfc_unreachable_transition",
        "sfc_unreachable_sequence_node",
        "sfc_duplicate_transition_guard",
    ]
    assert report.issues[0].data is not None
    assert report.issues[0].data["branch_path"] == [1]
    assert "targeting 'Done'" in report.issues[1].message


def test_analyze_sfc_reuses_variable_artifacts_when_available(monkeypatch: pytest.MonkeyPatch) -> None:
    build_calls: list[str] = []
    original_builder = variables_module._build_variable_analysis_artifacts

    def _recording_builder(base_picture: BasePicture) -> variables_module.VariableAnalysisArtifacts:
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
