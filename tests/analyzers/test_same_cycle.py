# These tests deliberately exercise private analyzer seams.
# pyright: reportPrivateUsage=false

from typing import cast

import pytest
from sattline_parser.ast import MappingSource
from sattline_parser.models.ast_model import (
    BasePicture,
    CodeItem,
    DataType,
    Equation,
    ModuleCode,
    ModuleHeader,
    ModuleTypeDef,
    ModuleTypeInstance,
    ParameterMapping,
    ScalarDatatype,
    Sequence,
    SFCBodyItem,
    SFCCodeBlocks,
    SFCFork,
    SFCParallel,
    SFCStep,
    SFCTransition,
    SingleModule,
    Variable,
)
from sattline_parser.models.expressions import Assignment, BinOp, IfStmt, NotOp, SLExpression, VarRef

from sattlint.analyzers.dataflow import analyze_dataflow
from sattlint.analyzers.dataflow._dataflow_non_state_sites import (
    _group_site_accesses,
    _SiteAccess,
)
from sattlint.analyzers.framework import Issue
from sattlint.analyzers.registry import get_default_analyzers, get_selectable_analyzer_keys
from sattlint.analyzers.same_cycle import analyze_same_cycle

_MULTI_SITE_KIND = "dataflow.non_state_multi_site"


def _hdr(name: str) -> ModuleHeader:
    return ModuleHeader(name=name, invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0))


def _eq(name: str, code: list[CodeItem]) -> Equation:
    return Equation(name=name, position=(0.0, 0.0), size=(1.0, 1.0), code=code)


def _varref(name: str) -> VarRef:
    return VarRef(name=name)


def _assign(name: str, value: SLExpression) -> Assignment:
    return Assignment(target=_varref(name), value=value)


def _increment(name: str) -> Assignment:
    return Assignment(target=_varref(name), value=BinOp(left=_varref(name), op="+", right=1))


def _step(name: str, active_stmts: list[CodeItem]) -> SFCStep:
    return SFCStep(kind="step", name=name, code=SFCCodeBlocks(active=active_stmts))


def _sequence(nodes: list[SFCBodyItem], name: str = "SeqMain") -> Sequence:
    return Sequence(
        name=name,
        type="sequence",
        position=(0.0, 0.0),
        size=(1.0, 1.0),
        code=nodes,
    )


def _multi_site_issues(bp: BasePicture) -> list[Issue]:
    return [issue for issue in analyze_dataflow(bp).issues if issue.kind == _MULTI_SITE_KIND]


def _continuous_sites(issue: Issue) -> list[dict[str, object]]:
    assert issue.data is not None
    sites = issue.data.get("continuous_sites")
    assert isinstance(sites, list)
    return [cast("dict[str, object]", site) for site in cast("list[object]", sites)]


def _site_labels(issue: Issue) -> list[str]:
    return [str(site["site"]) for site in _continuous_sites(issue)]


def _kinds_by_site(issue: Issue) -> dict[str, list[str]]:
    kinds_by_site: dict[str, list[str]] = {}
    for site in _continuous_sites(issue):
        kinds = site["kinds"]
        assert isinstance(kinds, list)
        kinds_by_site[str(site["site"])] = [str(kind) for kind in cast("list[object]", kinds)]
    return kinds_by_site


def test_same_cycle_analyzer_is_registered_and_selectable() -> None:
    specs = {spec.key: spec for spec in get_default_analyzers()}

    assert "same-cycle" in specs
    assert specs["same-cycle"].enabled is True
    assert "same-cycle" in get_selectable_analyzer_keys()
    assert "explicit parallel sequence branches" in specs["same-cycle"].description


def test_same_cycle_reports_parallel_read_write_hazard() -> None:
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[
            Variable(name="SharedValue", datatype=ScalarDatatype.INTEGER),
            Variable(name="Output", datatype=ScalarDatatype.INTEGER),
        ],
        modulecode=ModuleCode(
            sequences=[
                _sequence(
                    [
                        SFCParallel(
                            branches=[
                                [_step("Left", [_assign("Output", _varref("SharedValue"))])],
                                [_step("Right", [_assign("SharedValue", 2)])],
                            ]
                        )
                    ]
                )
            ],
            equationblocks=[],
        ),
    )

    report = analyze_same_cycle(bp)

    issue = next(issue for issue in report.issues if issue.kind == "same_cycle_parallel_read_write_hazard")
    assert "SeqMain" in issue.message
    assert issue.data == {
        "sequence": "SeqMain",
        "parallel_id": 1,
        "conflicts": ["Root.SharedValue"],
        "site": "SQ:SeqMain > PAR:BLOCK:1",
        "context": "Root.SharedValue",
    }


def _parallel_worker_typedef() -> ModuleTypeDef:
    return ModuleTypeDef(
        name="Worker",
        moduleparameters=[],
        localvariables=[Variable(name="Shared", datatype=ScalarDatatype.INTEGER)],
        submodules=[],
        moduledef=None,
        modulecode=ModuleCode(
            sequences=[
                _sequence(
                    [
                        SFCParallel(
                            branches=[
                                [_step("Left", [_assign("Shared", 1)])],
                                [_step("Right", [_assign("Shared", 2)])],
                            ]
                        )
                    ]
                )
            ],
            equationblocks=[],
        ),
    )


def test_same_cycle_reports_a_parallel_once_when_the_typedef_is_invoked() -> None:
    worker = _parallel_worker_typedef()
    bp = BasePicture(
        header=_hdr("Root"),
        moduletype_defs=[worker],
        submodules=[
            ModuleTypeInstance(header=_hdr("WorkerInst"), moduletype_name="Worker", parametermappings=[]),
        ],
        modulecode=ModuleCode(equationblocks=[], sequences=[]),
    )

    report = analyze_same_cycle(bp)

    write_races = [issue for issue in report.issues if issue.kind == "sfc_parallel_write_race"]
    assert len(write_races) == 1
    assert write_races[0].module_path == ["Root", "WorkerInst"]


def test_same_cycle_still_walks_an_uninvoked_root_typedef() -> None:
    bp = BasePicture(
        header=_hdr("Root"),
        moduletype_defs=[_parallel_worker_typedef()],
        submodules=[],
        modulecode=ModuleCode(equationblocks=[], sequences=[]),
    )

    report = analyze_same_cycle(bp)

    write_races = [issue for issue in report.issues if issue.kind == "sfc_parallel_write_race"]
    assert len(write_races) == 1
    assert write_races[0].module_path == ["Root", "TypeDef:Worker"]


def test_cross_module_read_write_overlap_is_not_a_proven_hazard() -> None:
    reader = SingleModule(
        header=_hdr("Reader"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[Variable(name="Output", datatype=ScalarDatatype.INTEGER)],
        submodules=[],
        modulecode=ModuleCode(
            equationblocks=[_eq("ReadEq", [_assign("Output", _varref("SharedValue"))])],
            sequences=[],
        ),
        parametermappings=[],
    )
    writer = SingleModule(
        header=_hdr("Writer"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[],
        submodules=[],
        modulecode=ModuleCode(equationblocks=[_eq("WriteEq", [_assign("SharedValue", 0)])], sequences=[]),
        parametermappings=[],
    )
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[Variable(name="SharedValue", datatype=ScalarDatatype.INTEGER)],
        submodules=[reader, writer],
        modulecode=ModuleCode(equationblocks=[], sequences=[]),
    )

    report = analyze_same_cycle(bp)

    assert report.issues == []


def test_external_mapping_overlap_is_not_a_proven_hazard() -> None:
    external_reader = ModuleTypeDef(
        name="ExternalReader",
        moduleparameters=[Variable(name="Input", datatype=ScalarDatatype.INTEGER)],
        localvariables=[Variable(name="Output", datatype=ScalarDatatype.INTEGER)],
        submodules=[],
        moduledef=None,
        modulecode=ModuleCode(
            equationblocks=[_eq("ReadEq", [_assign("Output", _varref("Input"))])],
            sequences=[],
        ),
        origin_file="ExternalDep.s",
        origin_lib="ExternalLib",
    )
    writer = SingleModule(
        header=_hdr("Writer"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[],
        submodules=[],
        modulecode=ModuleCode(equationblocks=[_eq("WriteEq", [_assign("SharedValue", 0)])], sequences=[]),
        parametermappings=[],
    )
    bp = BasePicture(
        header=_hdr("Root"),
        moduletype_defs=[external_reader],
        localvariables=[Variable(name="SharedValue", datatype=ScalarDatatype.INTEGER)],
        submodules=[
            ModuleTypeInstance(
                header=_hdr("ReaderInst"),
                moduletype_name="ExternalReader",
                parametermappings=[
                    ParameterMapping(
                        target=_varref("Input"),
                        source_type=MappingSource.VARIABLE,
                        is_duration=False,
                        is_source_global=False,
                        source=_varref("SharedValue"),
                    )
                ],
            ),
            writer,
        ],
        modulecode=ModuleCode(equationblocks=[], sequences=[]),
        origin_file="Root.s",
        origin_lib="RootLib",
    )

    report = analyze_same_cycle(bp)

    assert report.issues == []


def test_dataflow_non_state_multi_site_treats_sibling_operation_guards_as_exclusive() -> None:
    def module(name: str, value: int, *, guarded: bool) -> SingleModule:
        statements: list[CodeItem] = [_assign("Shared", value)]
        code: list[CodeItem] = [*statements]
        if guarded:
            code = []
            code.append(
                IfStmt(
                    branches=((NotOp(operand=VarRef(name="PhaseSequence.Reset")), tuple(statements)),),
                    else_block=None,
                )
            )
        return SingleModule(
            header=_hdr(name),
            moduledef=None,
            moduleparameters=[],
            localvariables=[],
            submodules=[],
            modulecode=ModuleCode(equationblocks=[_eq("Calculations", code)], sequences=[]),
            parametermappings=[],
        )

    guarded_bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[Variable(name="Shared", datatype=ScalarDatatype.INTEGER)],
        submodules=[module("Fyld", 1, guarded=True), module("Toem", 2, guarded=True)],
        modulecode=None,
    )
    unguarded_bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[Variable(name="Shared", datatype=ScalarDatatype.INTEGER)],
        submodules=[module("Fyld", 1, guarded=False), module("Toem", 2, guarded=False)],
        modulecode=None,
    )

    assert _multi_site_issues(guarded_bp) == []
    assert len(_multi_site_issues(unguarded_bp)) == 1


def test_dataflow_non_state_multi_site_ignores_state_writes_without_new() -> None:
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[Variable(name="SharedValue", datatype=ScalarDatatype.INTEGER, state=True)],
        modulecode=ModuleCode(
            equationblocks=[
                _eq("First", [_assign("SharedValue", 1)]),
                _eq("Second", [Assignment(target=VarRef(name="SharedValue", state="new"), value=2)]),
            ],
            sequences=[],
        ),
    )

    assert _multi_site_issues(bp) == []


def test_dataflow_non_state_multi_site_ignores_record_state_writes_without_new() -> None:
    payload = DataType(
        name="PayloadType",
        description=None,
        datecode=None,
        var_list=[Variable(name="Value", datatype=ScalarDatatype.INTEGER, state=True)],
    )
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[payload],
        localvariables=[Variable(name="Payload", datatype="PayloadType")],
        modulecode=ModuleCode(
            equationblocks=[
                _eq("First", [_assign("Payload.Value", 1)]),
                _eq("Second", [_assign("Payload.Value", 2)]),
            ],
            sequences=[],
        ),
    )

    assert _multi_site_issues(bp) == []


def test_dataflow_non_state_multi_site_reports_two_writing_equations() -> None:
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[Variable(name="SharedValue", datatype=ScalarDatatype.INTEGER)],
        modulecode=ModuleCode(
            equationblocks=[
                _eq("First", [_assign("SharedValue", 1)]),
                _eq("Second", [_assign("SharedValue", 2)]),
            ],
            sequences=[],
        ),
    )

    issues = _multi_site_issues(bp)

    assert len(issues) == 1
    issue = issues[0]
    assert "written from multiple continuous scan sites" in issue.message
    assert "read and written" not in issue.message
    assert issue.data == {
        "symbol": "Root.SharedValue",
        "decl_module_path": ["Root"],
        "continuous_sites": [
            {
                "module_path": ["Root"],
                "site": "EQ:First",
                "kinds": ["write"],
                "evidence_sites": ["EQ:First"],
            },
            {
                "module_path": ["Root"],
                "site": "EQ:Second",
                "kinds": ["write"],
                "evidence_sites": ["EQ:Second"],
            },
        ],
        "site": "Root:EQ:First",
        "context": "Root.SharedValue",
    }


def test_dataflow_non_state_multi_site_ignores_read_write_across_equations() -> None:
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[
            Variable(name="SharedValue", datatype=ScalarDatatype.INTEGER),
            Variable(name="Sink", datatype=ScalarDatatype.INTEGER),
        ],
        modulecode=ModuleCode(
            equationblocks=[
                _eq("ReadEq", [_assign("Sink", _varref("SharedValue"))]),
                _eq("WriteEq", [_assign("SharedValue", 2)]),
            ],
            sequences=[],
        ),
    )

    assert _multi_site_issues(bp) == []


def test_dataflow_non_state_multi_site_ignores_read_write_in_a_step() -> None:
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[
            Variable(name="SharedValue", datatype=ScalarDatatype.INTEGER),
            Variable(name="Sink", datatype=ScalarDatatype.INTEGER),
        ],
        modulecode=ModuleCode(
            sequences=[
                _sequence(
                    [
                        _step(
                            "Reads",
                            [_assign("Sink", _varref("SharedValue"))],
                        )
                    ]
                )
            ],
            equationblocks=[_eq("WriteEq", [_assign("SharedValue", 2)])],
        ),
    )

    assert _multi_site_issues(bp) == []


def test_dataflow_non_state_multi_site_counts_a_self_update_and_another_write() -> None:
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[Variable(name="SharedValue", datatype=ScalarDatatype.INTEGER)],
        modulecode=ModuleCode(
            equationblocks=[
                _eq("Increment", [_increment("SharedValue")]),
                _eq("Reset", [_assign("SharedValue", 0)]),
            ],
            sequences=[],
        ),
    )

    issues = _multi_site_issues(bp)

    assert len(issues) == 1
    assert _kinds_by_site(issues[0]) == {"EQ:Increment": ["read", "write"], "EQ:Reset": ["write"]}


def test_dataflow_non_state_multi_site_ignores_single_equation() -> None:
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[
            Variable(name="SharedValue", datatype=ScalarDatatype.INTEGER),
            Variable(name="Sink", datatype=ScalarDatatype.INTEGER),
        ],
        modulecode=ModuleCode(
            equationblocks=[
                _eq(
                    "MainEq",
                    [
                        _assign("Sink", _varref("SharedValue")),
                        _assign("SharedValue", 2),
                    ],
                )
            ],
            sequences=[],
        ),
    )

    assert _multi_site_issues(bp) == []


@pytest.mark.parametrize("written_field, expected", [("First", True), ("Second", False)])
def test_continuous_sites_compare_record_fields_not_whole_record(written_field: str, expected: bool) -> None:
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[
            DataType(
                name="RecordType",
                description=None,
                datecode=None,
                var_list=[
                    Variable(name="First", datatype=ScalarDatatype.INTEGER),
                    Variable(name="Second", datatype=ScalarDatatype.INTEGER),
                ],
            )
        ],
        localvariables=[Variable(name="Record", datatype="RecordType")],
        modulecode=ModuleCode(
            equationblocks=[
                _eq("WriteFirst", [_assign("Record.First", 1)]),
                _eq("WriteField", [_assign(f"Record.{written_field}", 2)]),
            ]
        ),
    )

    issues = _multi_site_issues(bp)

    assert bool(issues) is expected
    if issues:
        assert issues[0].data is not None
        assert issues[0].data["symbol"] == "Root.Record.First"


def test_dataflow_non_state_multi_site_ignores_single_active_step() -> None:
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[
            Variable(name="SharedValue", datatype=ScalarDatatype.INTEGER),
            Variable(name="Sink", datatype=ScalarDatatype.INTEGER),
        ],
        modulecode=ModuleCode(
            sequences=[
                _sequence(
                    [
                        _step(
                            "Loop",
                            [
                                _assign("Sink", _varref("SharedValue")),
                                _assign("SharedValue", 2),
                            ],
                        )
                    ]
                )
            ],
            equationblocks=[],
        ),
    )

    assert _multi_site_issues(bp) == []


def test_dataflow_non_state_multi_site_ignores_exclusive_steps_in_one_sequence() -> None:
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[Variable(name="SharedValue", datatype=ScalarDatatype.INTEGER)],
        modulecode=ModuleCode(
            sequences=[
                _sequence(
                    [
                        _step("First", [_assign("SharedValue", 1)]),
                        SFCTransition(name="Advance", condition=True),
                        _step("Second", [_assign("SharedValue", 2)]),
                    ]
                )
            ],
            equationblocks=[],
        ),
    )

    assert _multi_site_issues(bp) == []


def test_dataflow_non_state_multi_site_compares_steps_in_different_sequences() -> None:
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[Variable(name="SharedValue", datatype=ScalarDatatype.INTEGER)],
        modulecode=ModuleCode(
            sequences=[
                _sequence([_step("First", [_assign("SharedValue", 1)])], name="SeqOne"),
                _sequence([_step("Second", [_assign("SharedValue", 2)])], name="SeqTwo"),
            ],
            equationblocks=[],
        ),
    )

    issues = _multi_site_issues(bp)

    assert len(issues) == 1
    assert _site_labels(issues[0]) == [
        "STEP:First:ACTIVE",
        "STEP:Second:ACTIVE",
    ]


def test_dataflow_non_state_multi_site_compares_equation_and_active_step() -> None:
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[Variable(name="SharedValue", datatype=ScalarDatatype.INTEGER)],
        modulecode=ModuleCode(
            sequences=[_sequence([_step("Writer", [_assign("SharedValue", 1)])])],
            equationblocks=[_eq("Reset", [_assign("SharedValue", 0)])],
        ),
    )

    issues = _multi_site_issues(bp)

    assert len(issues) == 1
    assert _site_labels(issues[0]) == [
        "EQ:Reset",
        "STEP:Writer:ACTIVE",
    ]


def test_terminal_step_without_a_fork_is_not_a_continuous_self_loop() -> None:
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[Variable(name="SharedValue", datatype=ScalarDatatype.INTEGER)],
        modulecode=ModuleCode(
            sequences=[
                _sequence(
                    [
                        SFCStep(
                            kind="step",
                            name="Terminal",
                            code=SFCCodeBlocks(
                                enter=[_assign("SharedValue", 1)],
                                exit=[_assign("SharedValue", 2)],
                            ),
                        ),
                        SFCTransition(name="Finish", condition=True),
                    ]
                )
            ],
            equationblocks=[],
        ),
    )

    assert _multi_site_issues(bp) == []


def test_explicit_fork_makes_the_step_phases_continuous() -> None:
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[Variable(name="SharedValue", datatype=ScalarDatatype.INTEGER)],
        modulecode=ModuleCode(
            sequences=[
                _sequence(
                    [
                        SFCStep(
                            kind="step",
                            name="Loop",
                            code=SFCCodeBlocks(
                                enter=[_assign("SharedValue", 1)],
                                exit=[_assign("SharedValue", 2)],
                            ),
                            fork=SFCFork(targets=("Loop",)),
                        )
                    ]
                )
            ],
            equationblocks=[_eq("Reset", [_assign("SharedValue", 0)])],
        ),
    )

    issues = _multi_site_issues(bp)

    assert len(issues) == 1
    assert _site_labels(issues[0]) == [
        "EQ:Reset",
        "STEP:Loop:ENTER",
        "STEP:Loop:EXIT",
    ]


def test_self_loop_transition_requires_an_explicit_fork_target() -> None:
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[Variable(name="SharedFlag", datatype=ScalarDatatype.BOOLEAN)],
        modulecode=ModuleCode(
            sequences=[
                _sequence(
                    [
                        SFCStep(
                            kind="step",
                            name="Loop",
                            code=SFCCodeBlocks(enter=[_assign("SharedFlag", True)]),
                        ),
                        SFCTransition(
                            name="Gate",
                            condition=_varref("SharedFlag"),
                            fork=SFCFork(targets=("Loop",)),
                        ),
                    ]
                )
            ],
            equationblocks=[_eq("Reset", [_assign("SharedFlag", False)])],
        ),
    )

    issues = _multi_site_issues(bp)

    assert len(issues) == 1
    assert _site_labels(issues[0]) == [
        "EQ:Reset",
        "STEP:Loop:ENTER",
    ]


def test_hold_step_with_false_transition_is_not_a_continuous_self_loop() -> None:
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[
            Variable(name="Saved", datatype=ScalarDatatype.INTEGER),
            Variable(name="Current", datatype=ScalarDatatype.INTEGER),
        ],
        modulecode=ModuleCode(
            sequences=[
                _sequence(
                    [
                        SFCStep(
                            kind="step",
                            name="Hold",
                            code=SFCCodeBlocks(
                                enter=[_assign("Saved", _varref("Current"))],
                                exit=[_assign("Current", _varref("Saved"))],
                            ),
                        ),
                        SFCTransition(name="StayHeld", condition=False),
                    ]
                )
            ]
        ),
    )

    assert _multi_site_issues(bp) == []


def test_dataflow_non_state_multi_site_reports_an_invoked_typedef_once() -> None:
    worker = ModuleTypeDef(
        name="Worker",
        moduleparameters=[],
        localvariables=[Variable(name="Shared", datatype=ScalarDatatype.INTEGER)],
        submodules=[],
        moduledef=None,
        modulecode=ModuleCode(
            equationblocks=[
                _eq("First", [_assign("Shared", 1)]),
                _eq("Second", [_assign("Shared", 2)]),
            ],
            sequences=[],
        ),
    )
    bp = BasePicture(
        header=_hdr("Root"),
        moduletype_defs=[worker],
        submodules=[
            ModuleTypeInstance(header=_hdr("WorkerInst"), moduletype_name="Worker", parametermappings=[]),
        ],
        modulecode=ModuleCode(equationblocks=[], sequences=[]),
    )

    issues = _multi_site_issues(bp)

    assert len(issues) == 1
    assert issues[0].module_path == ["Root", "WorkerInst"]
    assert "TypeDef:" not in issues[0].message


def test_non_state_grouping_joins_every_prefix_of_a_symbol_path() -> None:
    def access(
        symbol_key: tuple[str, ...],
        kind: str,
        site: str,
        sequence_key: tuple[str, ...] | None = None,
    ) -> _SiteAccess:
        return _SiteAccess(
            module_path=("root",),
            symbol_key=symbol_key,
            symbol_display=".".join(symbol_key),
            decl_module_path=("root",),
            is_state_variable=False,
            continuous_site=site,
            kind=kind,
            site=site,
            sequence_key=sequence_key,
        )

    groups = _group_site_accesses(
        [
            access(("root", "rec"), "read", "EQ:A"),
            access(("root", "rec", "value"), "write", "EQ:A"),
            access(("root", "rec", "value", "deep"), "read", "EQ:B"),
        ]
    )

    representatives = {group.representative for group in groups}
    assert representatives == {
        ("root", "rec"),
        ("root", "rec", "value"),
        ("root", "rec", "value", "deep"),
    }
