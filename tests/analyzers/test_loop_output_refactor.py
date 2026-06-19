# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportPrivateUsage=false, reportMissingTypeArgument=false
from sattline_parser.models.ast_model import (
    BasePicture,
    Equation,
    FrameModule,
    ModuleCode,
    ModuleHeader,
    ModuleTypeDef,
    ModuleTypeInstance,
    Sequence,
    SFCAlternative,
    SFCCodeBlocks,
    SFCParallel,
    SFCStep,
    SFCSubsequence,
    SFCTransitionSub,
    Simple_DataType,
    SingleModule,
    Variable,
)
from sattlint import constants as const
from sattlint.analyzers import loop_output_refactor as loop_output_module
from sattlint.analyzers.loop_output_refactor import analyze_loop_output_refactor
from sattlint.analyzers.registry import get_default_analyzers


def _hdr(name: str) -> ModuleHeader:
    return ModuleHeader(name=name, invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0))


def _varref(name: str) -> dict:
    return {const.KEY_VAR_NAME: name}


def test_loop_output_refactor_detects_cycle_across_equations_and_active_step() -> None:
    eq_input = Equation(
        name="Input",
        position=(0.0, 0.0),
        size=(1.0, 1.0),
        code=[(const.KEY_ASSIGN, _varref("A"), _varref("B"))],
    )
    eq_feedback = Equation(
        name="Feedback",
        position=(1.0, 0.0),
        size=(1.0, 1.0),
        code=[(const.KEY_ASSIGN, _varref("B"), _varref("C"))],
    )
    seq = Sequence(
        name="MainSeq",
        type="sequence",
        position=(0.0, 1.0),
        size=(1.0, 1.0),
        code=[
            SFCStep(
                kind="step",
                name="Transfer",
                code=SFCCodeBlocks(active=[(const.KEY_ASSIGN, _varref("C"), _varref("A"))]),
            )
        ],
    )
    bp = BasePicture(
        header=_hdr("BasePicture"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[
            Variable(name="A", datatype=Simple_DataType.INTEGER),
            Variable(name="B", datatype=Simple_DataType.INTEGER),
            Variable(name="C", datatype=Simple_DataType.INTEGER),
        ],
        submodules=[],
        modulecode=ModuleCode(equations=[eq_input, eq_feedback], sequences=[seq]),
        moduledef=None,
    )

    report = analyze_loop_output_refactor(bp)

    issues = [issue for issue in report.issues if issue.kind == "sorting.loop_output_refactor"]
    assert len(issues) == 1
    issue = issues[0]
    assert issue.data is not None
    assert issue.data["dependency_variables"] == ["a", "b", "c"]
    assert issue.data["blocks"] == [
        "EquationBlock 'Input'",
        "EquationBlock 'Feedback'",
        "Sequence 'MainSeq' step 'Transfer' ACTIVE",
    ]
    assert "At least one dependency in this cycle is delayed by one scan" in issue.data["loop_text"]


def test_loop_output_refactor_ignores_acyclic_sorted_blocks() -> None:
    eq_source = Equation(
        name="Source",
        position=(0.0, 0.0),
        size=(1.0, 1.0),
        code=[(const.KEY_ASSIGN, _varref("A"), _varref("B"))],
    )
    eq_sink = Equation(
        name="Sink",
        position=(1.0, 0.0),
        size=(1.0, 1.0),
        code=[(const.KEY_ASSIGN, _varref("C"), _varref("A"))],
    )
    bp = BasePicture(
        header=_hdr("BasePicture"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[
            Variable(name="A", datatype=Simple_DataType.INTEGER),
            Variable(name="B", datatype=Simple_DataType.INTEGER),
            Variable(name="C", datatype=Simple_DataType.INTEGER),
        ],
        submodules=[],
        modulecode=ModuleCode(equations=[eq_source, eq_sink], sequences=[]),
        moduledef=None,
    )

    report = analyze_loop_output_refactor(bp)

    assert not any(issue.kind == "sorting.loop_output_refactor" for issue in report.issues)


def test_loop_output_refactor_analyzer_is_enabled_by_default() -> None:
    specs = {spec.key: spec for spec in get_default_analyzers()}

    assert "loop-output-refactor" in specs
    assert specs["loop-output-refactor"].enabled is True


def test_loop_output_helper_normalization_and_loop_text_helpers() -> None:
    analyzer = loop_output_module.LoopOutputRefactorAnalyzer(BasePicture(header=_hdr("Root")))

    assert loop_output_module._object_sequence([1, 2]) == [1, 2]
    assert loop_output_module._object_sequence((1, 2)) == (1, 2)
    assert loop_output_module._object_sequence("bad") is None
    assert loop_output_module._branch_pair((1, 2)) == (1, 2)
    assert loop_output_module._branch_pair((1, 2, 3)) is None
    assert loop_output_module._branch_pair([1, 2]) is None
    assert loop_output_module._root_variable_key(None) is None
    assert loop_output_module._root_variable_key("  ") is None
    assert loop_output_module._root_variable_key("Tag.Field") == "tag"

    loop_text = analyzer._format_loop_text(
        [
            loop_output_module._ExecutionBlock(0, ("Root",), "BlockA", ("a",), ("b",)),
            loop_output_module._ExecutionBlock(1, ("Root",), "BlockB", (), ()),
        ],
        [{"from": "BlockA", "to": "BlockB", "variables": ["b"]}],
    )
    assert "- BlockA: reads a; writes b" in loop_text
    assert "- BlockB: reads -; writes -" in loop_text
    assert "BlockA -> BlockB via b" in loop_text


def test_loop_output_statement_and_scc_helpers_cover_ifs_steps_and_components() -> None:
    analyzer = loop_output_module.LoopOutputRefactorAnalyzer(BasePicture(header=_hdr("Root")))
    reads: set[str] = set()
    writes: set[str] = set()

    analyzer._collect_statement_io(
        (const.KEY_ASSIGN, _varref("Target.Field"), _varref("Source.Value")),
        reads,
        writes,
    )
    analyzer._collect_statement_io(
        (
            const.GRAMMAR_VALUE_IF,
            [(_varref("Cond"), [(const.KEY_ASSIGN, _varref("BranchOut"), _varref("BranchIn"))]), "bad"],
            [(const.KEY_ASSIGN, _varref("ElseOut"), _varref("ElseIn"))],
        ),
        reads,
        writes,
    )
    analyzer._collect_statement_io(
        type(
            "StatementWrapper",
            (),
            {
                "data": const.KEY_STATEMENT,
                "children": [(const.KEY_ASSIGN, _varref("WrappedOut"), _varref("WrappedIn"))],
            },
        )(),
        reads,
        writes,
    )
    analyzer._collect_statement_io(_varref("ExprOnly"), reads, writes)

    assert reads == {"source", "cond", "branchin", "elsein", "wrappedin", "expronly"}
    assert writes == {"target", "branchout", "elseout", "wrappedout"}

    blocks: list[loop_output_module._ExecutionBlock] = []
    analyzer._collect_sequence_blocks(
        ["Root"],
        "MainSeq",
        [
            SFCStep(
                kind="step",
                name="Main",
                code=SFCCodeBlocks(
                    enter=[(const.KEY_ASSIGN, _varref("EnterOut"), _varref("EnterIn"))],
                    active=[(const.KEY_ASSIGN, _varref("ActiveOut"), _varref("ActiveIn"))],
                    exit=[(const.KEY_ASSIGN, _varref("ExitOut"), _varref("ExitIn"))],
                ),
            ),
            SFCAlternative(branches=[[(const.KEY_ASSIGN, _varref("AltOut"), _varref("AltIn"))]]),
            SFCParallel(branches=[[(const.KEY_ASSIGN, _varref("ParOut"), _varref("ParIn"))]]),
            SFCSubsequence(
                name="Nested",
                body=[
                    SFCStep(
                        kind="step",
                        name="NestedStep",
                        code=SFCCodeBlocks(active=[(const.KEY_ASSIGN, _varref("NestedOut"), _varref("NestedIn"))]),
                    )
                ],
            ),
            SFCTransitionSub(
                name="Transition",
                body=[
                    SFCStep(
                        kind="step",
                        name="TransitionStep",
                        code=SFCCodeBlocks(
                            active=[(const.KEY_ASSIGN, _varref("TransitionOut"), _varref("TransitionIn"))]
                        ),
                    )
                ],
            ),
        ],
        blocks,
    )
    assert [block.label for block in blocks] == [
        "Sequence 'MainSeq' step 'Main' ENTER",
        "Sequence 'MainSeq' step 'Main' ACTIVE",
        "Sequence 'MainSeq' step 'Main' EXIT",
        "Sequence 'MainSeq' step 'NestedStep' ACTIVE",
        "Sequence 'MainSeq' step 'TransitionStep' ACTIVE",
    ]

    components = analyzer._strongly_connected_components({0: {1}, 1: {0, 2}, 2: set(), 3: {3}})
    assert {frozenset(component) for component in components} == {frozenset({0, 1}), frozenset({2}), frozenset({3})}


def test_loop_output_run_and_module_scanning_cover_small_and_nested_paths(monkeypatch) -> None:
    typedef = ModuleTypeDef(
        name="TypeLogic",
        moduleparameters=[],
        localvariables=[],
        submodules=[],
        moduledef=None,
        modulecode=ModuleCode(equations=[]),
        parametermappings=[],
    )
    bp = BasePicture(
        header=_hdr("Root"),
        moduletype_defs=[typedef],
        submodules=[
            SingleModule(
                header=_hdr("Single"),
                moduledef=None,
                moduleparameters=[],
                localvariables=[],
                submodules=[],
                modulecode=ModuleCode(equations=[]),
                parametermappings=[],
            ),
            FrameModule(header=_hdr("Frame"), modulecode=ModuleCode(equations=[]), submodules=[]),
            ModuleTypeInstance(header=_hdr("TypeInst"), moduletype_name="TypeLogic", parametermappings=[]),
        ],
        modulecode=ModuleCode(equations=[]),
    )
    analyzer = loop_output_module.LoopOutputRefactorAnalyzer(bp)
    scanned: list[tuple[str, ...]] = []

    monkeypatch.setattr(
        analyzer, "_scan_modulecode", lambda module_path, _modulecode: scanned.append(tuple(module_path))
    )

    report = analyzer.run()

    assert report.issues == []
    assert scanned == [
        ("Root",),
        ("Root", "TypeLogic"),
        ("Root", "Single"),
        ("Root", "Frame"),
    ]

    small_analyzer = loop_output_module.LoopOutputRefactorAnalyzer(BasePicture(header=_hdr("Root")))
    monkeypatch.setattr(
        small_analyzer,
        "_collect_execution_blocks",
        lambda *_args, **_kwargs: [loop_output_module._ExecutionBlock(0, ("Root",), "Only", (), ())],
    )
    small_analyzer._scan_modulecode(["Root"], None)
    small_analyzer._scan_modulecode(["Root"], ModuleCode(equations=[]))
    assert small_analyzer._issues == []


def test_loop_output_scan_modulecode_reports_cycles_and_skips_empty_edges(monkeypatch) -> None:
    analyzer = loop_output_module.LoopOutputRefactorAnalyzer(BasePicture(header=_hdr("Root")))
    blocks = [
        loop_output_module._ExecutionBlock(0, ("Root",), "Writer", (), ("a",)),
        loop_output_module._ExecutionBlock(1, ("Root",), "Reader", ("a",), ("b",)),
        loop_output_module._ExecutionBlock(2, ("Root",), "Closer", ("b",), ()),
        loop_output_module._ExecutionBlock(3, ("Root",), "NoWrites", ("z",), ()),
    ]
    monkeypatch.setattr(analyzer, "_collect_execution_blocks", lambda *_args, **_kwargs: blocks)
    monkeypatch.setattr(analyzer, "_strongly_connected_components", lambda _adjacency: [{0, 1, 2}, {3}])

    analyzer._scan_modulecode(["Root"], ModuleCode(equations=[]))

    assert len(analyzer._issues) == 1
    issue = analyzer._issues[0]
    assert issue.data is not None
    assert issue.data["dependency_variables"] == ["a", "b"]
    assert issue.data["blocks"] == ["Writer", "Reader", "Closer"]
