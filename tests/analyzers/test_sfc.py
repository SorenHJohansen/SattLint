"""Tests for SFC analyzer checks."""

from types import SimpleNamespace

from sattline_parser.models.ast_model import (
    BasePicture,
    FrameModule,
    ModuleCode,
    ModuleHeader,
    ModuleTypeDef,
    Sequence,
    SFCAlternative,
    SFCBreak,
    SFCCodeBlocks,
    SFCFork,
    SFCParallel,
    SFCStep,
    SFCSubsequence,
    SFCTransition,
    SFCTransitionSub,
    Simple_DataType,
    SingleModule,
    Variable,
)
from sattlint import constants as const
from sattlint.analyzers import _sfc_collectors as sfc_collectors_module
from sattlint.analyzers import sfc as sfc_module
from sattlint.analyzers import variables as variables_module
from sattlint.analyzers._sfc_collectors import _SfcAccessCollector
from sattlint.analyzers._sfc_module_walk import iter_sfc_modulecodes
from sattlint.analyzers._sfc_step_contracts import StepContract
from sattlint.analyzers.framework import AnalysisContext, AnalysisSharedArtifacts
from sattlint.analyzers.issue import Issue
from sattlint.analyzers.sfc import analyze_sfc
from sattlint.analyzers.variables import analyze_variables
from sattlint.resolution import AccessKind
from sattlint.resolution.paths import CanonicalPath


def _hdr(name: str) -> ModuleHeader:
    return ModuleHeader(name=name, invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0))


def _varref(name: str) -> dict:
    return {const.KEY_VAR_NAME: name}


def _assign(name: str, value: object) -> tuple:
    return (const.KEY_ASSIGN, _varref(name), value)


def _step(name: str, active_stmts: list[object]) -> SFCStep:
    return SFCStep(kind="step", name=name, code=SFCCodeBlocks(active=active_stmts))


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
        localvariables=[Variable(name="Output", datatype=Simple_DataType.INTEGER)],
        modulecode=ModuleCode(sequences=[seq], equations=[]),
    )

    report = analyze_sfc(bp)

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
            Variable(name="OutputA", datatype=Simple_DataType.INTEGER),
            Variable(name="OutputB", datatype=Simple_DataType.INTEGER),
        ],
        modulecode=ModuleCode(sequences=[seq], equations=[]),
    )

    report = analyze_sfc(bp)

    assert not report.issues


def test_illegal_state_combination_detected_for_parallel_steps():
    seq = _sequence(
        [
            SFCParallel(
                branches=[
                    [_step("Idle", [])],
                    [_step("Running", [])],
                ]
            )
        ]
    )

    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[],
        modulecode=ModuleCode(sequences=[seq], equations=[]),
    )

    report = analyze_sfc(
        bp,
        mutually_exclusive_steps=[("Idle", "Running")],
    )

    issues = [issue for issue in report.issues if issue.kind == "sfc_illegal_state_combination"]
    assert len(issues) == 1
    assert issues[0].data is not None
    assert issues[0].data["conflicts"] == [["Idle", "Running"]]


def test_valid_parallel_state_combination_not_reported():
    seq = _sequence(
        [
            SFCParallel(
                branches=[
                    [_step("Idle", [])],
                    [_step("Holding", [])],
                ]
            )
        ]
    )

    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[],
        modulecode=ModuleCode(sequences=[seq], equations=[]),
    )

    report = analyze_sfc(
        bp,
        mutually_exclusive_steps=[("Idle", "Running")],
    )

    assert not any(issue.kind == "sfc_illegal_state_combination" for issue in report.issues)


def test_analyze_sfc_parallel_write_race_selection_skips_other_issue_collectors(monkeypatch):
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[Variable(name="Output", datatype=Simple_DataType.INTEGER)],
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
            equations=[],
        ),
    )

    monkeypatch.setattr(
        sfc_module,
        "collect_sfc_reachability_findings",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("reachability should not run")),
    )
    monkeypatch.setattr(
        sfc_module,
        "_collect_transition_logic_issues",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("transition logic should not run")),
    )
    monkeypatch.setattr(
        sfc_module,
        "_collect_illegal_state_combination_issues",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("illegal-state scan should not run")),
    )
    monkeypatch.setattr(
        sfc_module,
        "_SfcStepContractCollector",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("step contracts should not run")),
    )

    report = analyze_sfc(
        bp,
        selected_issue_kinds={"sfc_parallel_write_race"},
        mutually_exclusive_steps=[("Left", "Right")],
        step_contracts={"Left": {"required_enter_writes": ["Output"]}},
    )

    assert [issue.kind for issue in report.issues] == ["sfc_parallel_write_race"]


def test_sfc_access_collector_tracks_parallel_writes_for_direct_and_resolved_writes(monkeypatch):
    collector = _SfcAccessCollector(BasePicture(header=_hdr("Root"), localvariables=[]))
    parent_calls: list[tuple[AccessKind, CanonicalPath, str]] = []

    def _fake_parent_record_access(self, kind, canonical_path, context, syntactic_ref):
        _ = context
        parent_calls.append((kind, canonical_path, syntactic_ref))

    monkeypatch.setattr(sfc_collectors_module.VariablesAnalyzer, "_record_access", _fake_parent_record_access)

    parallel_key = (("Root",), "SeqMain", 1)
    collector._parallel_stack = [(parallel_key, 0)]
    canonical_path = CanonicalPath(("Root", "Output"))

    collector._record_access(AccessKind.READ, canonical_path, SimpleNamespace(), "Output")
    collector._record_access(AccessKind.WRITE, canonical_path, SimpleNamespace(), "Output")

    assert parent_calls == [
        (AccessKind.READ, canonical_path, "Output"),
        (AccessKind.WRITE, canonical_path, "Output"),
    ]
    assert collector.parallel_writes[parallel_key][0] == {canonical_path}

    usage_calls: list[dict[str, object]] = []
    collector.usage_tracker = SimpleNamespace(mark_ref_access=lambda **kwargs: usage_calls.append(kwargs))
    variable = Variable(name="Rec", datatype=Simple_DataType.INTEGER)
    resolved_context = SimpleNamespace(
        env={},
        resolve_variable=lambda _ref: (variable, "Field.Sub", ("Root", "Unit"), ("BP:Root", "Unit")),
    )

    collector._mark_ref_access("Rec.Field.Sub", resolved_context, ["Root", "Unit"], AccessKind.READ)
    collector._mark_ref_access("Rec.Field.Sub", resolved_context, ["Root", "Unit"], AccessKind.WRITE)
    collector._mark_ref_access(
        "Missing",
        SimpleNamespace(env={}, resolve_variable=lambda _ref: (None, None, (), None)),
        ["Root"],
        AccessKind.WRITE,
    )

    assert len(usage_calls) == 2
    assert usage_calls[0]["kind"] is AccessKind.READ
    assert usage_calls[1]["kind"] is AccessKind.WRITE
    assert CanonicalPath(("Root", "Unit", "Rec", "Field", "Sub")) in collector.parallel_writes[parallel_key][0]


def test_sfc_access_collector_walk_helpers_cover_branch_labels_and_site_markers(monkeypatch):
    collector = _SfcAccessCollector(BasePicture(header=_hdr("Root"), localvariables=[]))
    context = SimpleNamespace(env={})
    site_events: list[tuple[str, str]] = []
    stmt_events: list[object] = []
    branch_labels: list[str | None] = []
    seq_node_calls: list[tuple[list[object], list[str], bool, list[str]]] = []

    monkeypatch.setattr(collector, "_push_site", lambda label: site_events.append(("push", label)))
    monkeypatch.setattr(collector, "_pop_site", lambda: site_events.append(("pop", "")))
    monkeypatch.setattr(
        collector, "_walk_stmt_or_expr", lambda statement, _context, _path: stmt_events.append(statement)
    )

    step = SFCStep(kind="step", name="Main", code=SFCCodeBlocks(active=[_assign("Output", 1)]))
    transition = SFCTransition(name=None, condition=_varref("Permit"))

    collector._walk_step_node(step, context, ["Root"], include_site_labels=True)
    collector._walk_transition_node(transition, context, ["Root"], include_site_labels=True)

    assert ("push", "STEP:Main:ACTIVE") in site_events
    assert ("push", "TRANS:<unnamed>") in site_events
    assert stmt_events == [_assign("Output", 1), _varref("Permit")]

    monkeypatch.setattr(
        collector,
        "_walk_branch_node",
        lambda nodes, _context, _path, *, label: branch_labels.append(label),
    )
    monkeypatch.setattr(
        collector,
        "_walk_transition_node",
        lambda node, _context, _path, *, include_site_labels: branch_labels.append(
            f"TRANS:{node.name}:{include_site_labels}"
        ),
    )

    collector._walk_sequence_node(transition, context, ["Root"], include_site_labels=False)
    collector._walk_sequence_node(
        SFCAlternative(branches=[[step], []]),
        context,
        ["Root"],
        include_site_labels=True,
    )
    collector._walk_sequence_node(
        SFCSubsequence(name="Nested", body=[step]),
        context,
        ["Root"],
        include_site_labels=True,
    )
    collector._walk_sequence_node(
        SFCTransitionSub(name="Gate", body=[transition]),
        context,
        ["Root"],
        include_site_labels=True,
    )

    assert branch_labels == [
        "TRANS:None:False",
        "ALT:BRANCH:0",
        "ALT:BRANCH:1",
        "SUBSEQ:Nested",
        "TRANS-SUB:Gate",
    ]

    monkeypatch.setattr(
        collector,
        "_walk_sequence_node",
        lambda node, scoped_context, path, *, include_site_labels: seq_node_calls.append(
            (scoped_context.display_module_path, path.copy(), include_site_labels, [node])
        ),
    )
    _SfcAccessCollector._walk_branch_node(collector, [step], context, ["Root", "Unit"], label="ALT:BRANCH:0")
    _SfcAccessCollector._walk_seq_nodes(collector, [transition], {}, ["Root", "Unit"])

    assert site_events[-2:] == [("push", "ALT:BRANCH:0"), ("pop", "")]
    assert seq_node_calls == [
        (["Root<BP>", "Unit"], ["Root", "Unit"], False, [step]),
        (["Root<BP>", "Unit"], ["Root", "Unit"], False, [transition]),
    ]


def test_iter_sfc_modulecodes_covers_root_nested_modules_and_typedefs():
    nested_frame = FrameModule(
        header=_hdr("FrameChild"),
        modulecode=ModuleCode(sequences=[], equations=[]),
        submodules=[],
    )
    nested_single = SingleModule(
        header=_hdr("UnitChild"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[],
        submodules=[nested_frame],
        modulecode=ModuleCode(sequences=[], equations=[]),
    )
    moduletype = ModuleTypeDef(
        name="TypeLogic",
        modulecode=ModuleCode(sequences=[], equations=[]),
    )
    bp = BasePicture(
        header=_hdr("Root"),
        submodules=[nested_single],
        moduletype_defs=[moduletype],
        modulecode=ModuleCode(sequences=[], equations=[]),
    )

    entries = list(iter_sfc_modulecodes(bp))

    assert [path for path, _modulecode in entries] == [
        ["Root"],
        ["Root", "UnitChild"],
        ["Root", "UnitChild", "FrameChild"],
        ["Root", "TypeDef:TypeLogic"],
    ]


def test_sfc_configuration_helpers_normalize_groups_and_contracts() -> None:
    assert sfc_module._mapping_value({"analysis": 1}, "analysis") == 1
    assert sfc_module._normalize_step_groups(None) == ()
    assert sfc_module._normalize_step_groups([[" Idle ", "Running", "idle", "", 5], ["OnlyOne"]]) == (
        ("Idle", "Running"),
    )
    assert sfc_module.normalize_mutually_exclusive_step_sets("bad") == ()
    assert sfc_module.normalize_mutually_exclusive_step_sets(
        [
            ["Idle", "Running"],
            "skip",
            ("Hold", "Run"),
        ]
    ) == (("Idle", "Running"), ("Hold", "Run"))
    assert sfc_module.get_configured_mutually_exclusive_step_sets(None) == ()
    assert sfc_module.get_configured_mutually_exclusive_step_sets({"analysis": []}) == ()
    assert sfc_module.get_configured_mutually_exclusive_step_sets({"analysis": {"sfc": []}}) == ()
    assert sfc_module.get_configured_mutually_exclusive_step_sets(
        {"analysis": {"sfc": {"mutually_exclusive_steps": [["Idle", "Running"]]}}}
    ) == (("Idle", "Running"),)

    assert sfc_module._normalize_step_contract_refs("bad") == ()
    assert sfc_module._normalize_step_contract_refs([" Output ", "output", "", 3, "Done"]) == (
        "Output",
        "Done",
    )
    assert sfc_module._normalize_step_contract("bad") == StepContract()
    assert sfc_module.normalize_step_contracts("bad") == {}
    assert sfc_module.normalize_step_contracts(
        {
            3: {"required_enter_writes": ["Skip"]},
            " ": {"required_enter_writes": ["Skip"]},
            "Empty": {},
            "Main": {
                "required_enter_writes": [" Output ", "output"],
                "required_exit_writes": ["Done"],
            },
        }
    ) == {"main": StepContract(required_enter_writes=("Output",), required_exit_writes=("Done",))}
    assert sfc_module.get_configured_step_contracts(None) == {}
    assert sfc_module.get_configured_step_contracts({"analysis": []}) == {}
    assert sfc_module.get_configured_step_contracts({"analysis": {"sfc": []}}) == {}
    assert sfc_module.get_configured_step_contracts(
        {"analysis": {"sfc": {"step_contracts": {"Main": {"required_enter_writes": ["Output"]}}}}}
    ) == {"main": StepContract(required_enter_writes=("Output",), required_exit_writes=())}


def test_sfc_reachability_and_active_step_helpers_cover_nested_nodes_and_previews(monkeypatch) -> None:
    findings: list[sfc_module.SfcReachabilityFinding] = []
    sfc_module._inspect_sfc_linear_nodes(
        findings,
        [
            SFCBreak(),
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
            SFCAlternative(branches=[[SFCBreak(), _step("AltDead", [])]]),
            SFCSubsequence(name="NestedSeq", body=[SFCBreak(), _step("Nested", [])]),
            SFCTransitionSub(
                name="NestedGate",
                body=[SFCFork(targets=("Done",)), SFCTransition(name="AfterFork", condition=True)],
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
    assert findings[0].terminated_by == {"kind": "SFCBreak"}
    assert branch_findings[0].branch_path == (0,)
    assert branch_findings[-1].terminated_by == {"kind": "SFCFork", "targets": ["Done"]}
    assert sfc_module._sequence_node_label(SFCFork(targets=("Left", "Right"))) == "SFCFork:Left,Right"
    assert sfc_module._sequence_node_label(SFCBreak()) == "SFCBreak"

    active_sets = sfc_module._collect_active_step_sets(
        [
            SFCTransition(name="Gate", condition=True),
            SFCFork(targets=("Done",)),
            SFCBreak(),
            SFCAlternative(branches=[[_step("Alt", [])]]),
            SFCParallel(branches=[[_step("Left", [])], [_step("Right", [])]]),
            SFCSubsequence(name="Nested", body=[_step("Nested", [])]),
            SFCTransitionSub(name="Gate", body=[_step("TransitionBody", [])]),
        ]
    )
    assert active_sets == {
        frozenset({"Alt"}),
        frozenset({"Left", "Right"}),
        frozenset({"Nested"}),
        frozenset({"TransitionBody"}),
    }
    assert sfc_module._find_illegal_state_combinations(
        [frozenset({"Idle", "Running"}), frozenset({"Idle"})],
        (("Idle", "Running"),),
    ) == [("Idle", "Running")]
    assert sfc_module._collect_illegal_state_combination_issues(BasePicture(header=_hdr("Root")), ()) == []

    sequence = _sequence([_step("Idle", []), _step("Running", [])])
    bp = BasePicture(
        header=_hdr("Root"),
        submodules=[FrameModule(header=_hdr("NoCode"), modulecode=None, submodules=[])],
        modulecode=ModuleCode(sequences=[sequence], equations=[]),
    )
    assert sfc_module.collect_sfc_reachability_findings(bp) == []
    monkeypatch.setattr(
        sfc_module,
        "_find_illegal_state_combinations",
        lambda *_args, **_kwargs: [
            ("A", "B"),
            ("C", "D"),
            ("E", "F"),
            ("G", "H"),
            ("I", "J"),
        ],
    )
    issues = sfc_module._collect_illegal_state_combination_issues(bp, (("Idle", "Running"),))
    assert len(issues) == 1
    assert "; ... (+1 more)" in issues[0].message
    assert len(issues[0].data["conflicts"]) == 5
    assert sfc_module._format_terminator({"kind": "SFCFork", "targets": ["Left", 7, "Right"]}) == (
        "SFCFork targeting 'Left', 'Right'"
    )
    assert sfc_module._format_terminator({}) == "an earlier terminating node"


def test_analyze_sfc_covers_selected_collectors_reachability_messages_and_step_contracts(monkeypatch) -> None:
    class _FakeCollector:
        def __init__(self, _bp):
            shared_paths = {CanonicalPath(("Root", f"Var{index}")) for index in range(7)}
            self.parallel_writes = {
                (("Root",), "SeqMain", 1): {0: shared_paths, 1: shared_paths},
                (("Root",), "SeqOther", 2): {
                    0: {CanonicalPath(("Root", "OnlyLeft"))},
                    1: {CanonicalPath(("Root", "OnlyRight"))},
                },
            }
            self.parallel_meta = {
                (("Root",), "SeqMain", 1): SimpleNamespace(
                    module_path=["Root"], sequence_name="SeqMain", parallel_id=1
                ),
                (("Root",), "SeqOther", 2): SimpleNamespace(
                    module_path=["Root"], sequence_name="SeqOther", parallel_id=2
                ),
            }

        def run(self):
            return None

    class _FakeStepContractCollector:
        def __init__(self, _bp, contracts):
            self.contracts = contracts

        def collect(self):
            return [Issue(kind="sfc_missing_step_enter_contract", message="contract")]

    monkeypatch.setattr(sfc_module, "_SfcAccessCollector", _FakeCollector)
    monkeypatch.setattr(
        sfc_module,
        "collect_sfc_reachability_findings",
        lambda _bp: [
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
        lambda _bp: [Issue(kind="sfc_transition_always_true", message="logic")],
    )
    monkeypatch.setattr(
        sfc_module,
        "_collect_illegal_state_combination_issues",
        lambda _bp, _groups: [Issue(kind="sfc_illegal_state_combination", message="illegal")],
    )
    monkeypatch.setattr(sfc_module, "_SfcStepContractCollector", _FakeStepContractCollector)

    report = analyze_sfc(
        BasePicture(header=_hdr("Root")),
        mutually_exclusive_steps=[["Idle", "Running"]],
        step_contracts={"Main": {"required_enter_writes": ["Output"]}},
    )

    kinds = [issue.kind for issue in report.issues]
    assert kinds == [
        "sfc_parallel_write_race",
        "sfc_unreachable_transition",
        "sfc_unreachable_sequence_node",
        "sfc_transition_always_true",
        "sfc_illegal_state_combination",
        "sfc_missing_step_enter_contract",
    ]
    assert "... (+1 more)" in report.issues[0].message
    assert report.issues[1].data["branch_path"] == [1]
    assert "targeting 'Done'" in report.issues[2].message


def test_analyze_sfc_reuses_variable_artifacts_when_available(monkeypatch):
    build_calls: list[str] = []
    original_builder = variables_module._build_variable_analysis_artifacts

    def _recording_builder(base_picture):
        build_calls.append(base_picture.header.name)
        return original_builder(base_picture)

    monkeypatch.setattr(variables_module, "_build_variable_analysis_artifacts", _recording_builder)

    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[Variable(name="Output", datatype=Simple_DataType.INTEGER)],
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
            equations=[],
        ),
    )
    shared_artifacts = AnalysisSharedArtifacts()
    context = AnalysisContext(base_picture=bp, shared_artifacts=shared_artifacts)

    analyze_variables(bp, analysis_context=context)
    analyze_sfc(bp, analysis_context=context, selected_issue_kinds={"sfc_parallel_write_race"})

    assert build_calls == ["Root"]
    assert shared_artifacts.counters.variable_foundation_builds == 1
