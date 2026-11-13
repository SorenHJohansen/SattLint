# pyright: reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownArgumentType=false, reportPrivateUsage=false

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
    Sequence,
    SFCBodyItem,
    SFCCodeBlocks,
    SFCFork,
    SFCParallel,
    SFCStep,
    SFCTransition,
    Simple_DataType,
    SingleModule,
    Variable,
)
from sattline_parser.models.expressions import Assignment, SLExpression, VarRef

from sattlint.analyzers.dataflow import analyze_dataflow
from sattlint.analyzers.registry import get_actual_cli_analyzer_keys, get_default_analyzers
from sattlint.analyzers.same_cycle import analyze_same_cycle


def _hdr(name: str) -> ModuleHeader:
    return ModuleHeader(name=name, invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0))


def _eq(name: str, code: list[CodeItem]) -> Equation:
    return Equation(name=name, position=(0.0, 0.0), size=(1.0, 1.0), code=code)


def _varref(name: str) -> VarRef:
    return VarRef(name=name)


def _assign(name: str, value: SLExpression) -> Assignment:
    return Assignment(target=_varref(name), value=value)


def _step(name: str, active_stmts: list[CodeItem]) -> SFCStep:
    return SFCStep(kind="step", name=name, code=SFCCodeBlocks(active=active_stmts))


def _sequence(nodes: list[SFCBodyItem]) -> Sequence:
    return Sequence(
        name="SeqMain",
        type="sequence",
        position=(0.0, 0.0),
        size=(1.0, 1.0),
        code=nodes,
    )


def test_same_cycle_analyzer_is_registered_and_in_default_cli() -> None:
    specs = {spec.key: spec for spec in get_default_analyzers()}

    assert "same-cycle" in specs
    assert specs["same-cycle"].enabled is True
    assert "same-cycle" in get_actual_cli_analyzer_keys()
    assert "explicit parallel sequence branches" in specs["same-cycle"].description


def test_same_cycle_reports_parallel_read_write_hazard() -> None:
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[
            Variable(name="SharedValue", datatype=Simple_DataType.INTEGER),
            Variable(name="Output", datatype=Simple_DataType.INTEGER),
        ],
        modulecodes=[
            ModuleCode(
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
            )
        ],
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


def test_cross_module_read_write_overlap_is_not_a_proven_hazard() -> None:
    reader = SingleModule(
        header=_hdr("Reader"),
        moduledefs=[],
        moduleparameters=[],
        localvariables=[Variable(name="Output", datatype=Simple_DataType.INTEGER)],
        submodules=[],
        modulecodes=[
            ModuleCode(
                equationblocks=[_eq("ReadEq", [_assign("Output", _varref("SharedValue"))])],
                sequences=[],
            )
        ],
        parametermappings=[],
    )
    writer = SingleModule(
        header=_hdr("Writer"),
        moduledefs=[],
        moduleparameters=[],
        localvariables=[],
        submodules=[],
        modulecodes=[ModuleCode(equationblocks=[_eq("WriteEq", [_assign("SharedValue", 0)])], sequences=[])],
        parametermappings=[],
    )
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[Variable(name="SharedValue", datatype=Simple_DataType.INTEGER)],
        submodules=[reader, writer],
        modulecodes=[ModuleCode(equationblocks=[], sequences=[])],
    )

    report = analyze_same_cycle(bp)

    assert report.issues == []


def test_external_mapping_overlap_is_not_a_proven_hazard() -> None:
    external_reader = ModuleTypeDef(
        name="ExternalReader",
        moduleparameters=[Variable(name="Input", datatype=Simple_DataType.INTEGER)],
        localvariables=[Variable(name="Output", datatype=Simple_DataType.INTEGER)],
        submodules=[],
        moduledefs=[],
        modulecodes=[
            ModuleCode(
                equationblocks=[_eq("ReadEq", [_assign("Output", _varref("Input"))])],
                sequences=[],
            )
        ],
        parametermappings=[],
        origin_file="ExternalDep.s",
        origin_lib="ExternalLib",
    )
    writer = SingleModule(
        header=_hdr("Writer"),
        moduledefs=[],
        moduleparameters=[],
        localvariables=[],
        submodules=[],
        modulecodes=[ModuleCode(equationblocks=[_eq("WriteEq", [_assign("SharedValue", 0)])], sequences=[])],
        parametermappings=[],
    )
    bp = BasePicture(
        header=_hdr("Root"),
        moduletype_defs=[external_reader],
        localvariables=[Variable(name="SharedValue", datatype=Simple_DataType.INTEGER)],
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
        modulecodes=[ModuleCode(equationblocks=[], sequences=[])],
        origin_file="Root.s",
        origin_lib="RootLib",
    )

    report = analyze_same_cycle(bp)

    assert report.issues == []


def test_dataflow_non_state_multi_site_across_equations() -> None:
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[
            Variable(name="SharedValue", datatype=Simple_DataType.INTEGER),
            Variable(name="Sink", datatype=Simple_DataType.INTEGER),
        ],
        modulecodes=[
            ModuleCode(
                equationblocks=[
                    _eq("ReadEq", [_assign("Sink", _varref("SharedValue"))]),
                    _eq("WriteEq", [_assign("SharedValue", 2)]),
                ],
                sequences=[],
            )
        ],
    )

    report = analyze_dataflow(bp)

    issue = next(issue for issue in report.issues if issue.kind == "dataflow.non_state_multi_site")
    assert "Root.SharedValue" in issue.message
    assert issue.data == {
        "symbol": "Root.SharedValue",
        "decl_module_path": ["Root"],
        "continuous_sites": [
            {
                "module_path": ["Root"],
                "site": "EQ:ReadEq",
                "kinds": ["read"],
                "evidence_sites": ["EQ:ReadEq"],
            },
            {
                "module_path": ["Root"],
                "site": "EQ:WriteEq",
                "kinds": ["write"],
                "evidence_sites": ["EQ:WriteEq"],
            },
        ],
        "site": "Root:EQ:ReadEq",
        "context": "Root.SharedValue",
    }


def test_dataflow_non_state_multi_site_ignores_single_equation() -> None:
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[
            Variable(name="SharedValue", datatype=Simple_DataType.INTEGER),
            Variable(name="Sink", datatype=Simple_DataType.INTEGER),
        ],
        modulecodes=[
            ModuleCode(
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
            )
        ],
    )

    report = analyze_dataflow(bp)

    assert not any(issue.kind == "dataflow.non_state_multi_site" for issue in report.issues)


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
                    Variable(name="First", datatype=Simple_DataType.INTEGER),
                    Variable(name="Second", datatype=Simple_DataType.INTEGER),
                ],
            )
        ],
        localvariables=[
            Variable(name="Record", datatype="RecordType"),
            Variable(name="Sink", datatype=Simple_DataType.INTEGER),
        ],
        modulecodes=[
            ModuleCode(
                equationblocks=[
                    _eq("ReadFirst", [_assign("Sink", _varref("Record.First"))]),
                    _eq("WriteField", [_assign(f"Record.{written_field}", 2)]),
                ]
            )
        ],
    )
    report = analyze_dataflow(bp)
    conflicts = [issue for issue in report.issues if issue.kind == "dataflow.non_state_multi_site"]
    assert bool(conflicts) is expected
    if conflicts:
        assert conflicts[0].data is not None
        assert conflicts[0].data["symbol"] == "Root.Record.First"


def test_dataflow_non_state_multi_site_ignores_single_active_step() -> None:
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[
            Variable(name="SharedValue", datatype=Simple_DataType.INTEGER),
            Variable(name="Sink", datatype=Simple_DataType.INTEGER),
        ],
        modulecodes=[
            ModuleCode(
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
            )
        ],
    )

    report = analyze_dataflow(bp)

    assert not any(issue.kind == "dataflow.non_state_multi_site" for issue in report.issues)


def test_dataflow_non_state_multi_site_transition_self_loop() -> None:
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[Variable(name="SharedFlag", datatype=Simple_DataType.BOOLEAN)],
        modulecodes=[
            ModuleCode(
                sequences=[
                    _sequence(
                        [
                            SFCStep(
                                kind="step",
                                name="Loop",
                                code=SFCCodeBlocks(enter=[_assign("SharedFlag", True)]),
                            ),
                            SFCTransition(name="Gate", condition=_varref("SharedFlag")),
                        ]
                    )
                ],
                equationblocks=[],
            )
        ],
    )

    report = analyze_dataflow(bp)

    issue = next(issue for issue in report.issues if issue.kind == "dataflow.non_state_multi_site")
    assert issue.data is not None
    assert [site["site"] for site in issue.data["continuous_sites"]] == [
        "STEP:Loop:ENTER",
        "STEP:Loop:TRANS:Gate",
    ]


def test_hold_step_with_false_transition_is_not_a_continuous_self_loop() -> None:
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[
            Variable(name="Saved", datatype=Simple_DataType.INTEGER),
            Variable(name="Current", datatype=Simple_DataType.INTEGER),
        ],
        modulecodes=[
            ModuleCode(
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
            )
        ],
    )
    report = analyze_dataflow(bp)
    assert not any(issue.kind == "dataflow.non_state_multi_site" for issue in report.issues)


def test_dataflow_non_state_multi_site_fork_self_loop() -> None:
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[
            Variable(name="SharedFlag", datatype=Simple_DataType.BOOLEAN),
            Variable(name="Sink", datatype=Simple_DataType.BOOLEAN),
        ],
        modulecodes=[
            ModuleCode(
                sequences=[
                    _sequence(
                        [
                            SFCStep(
                                kind="step",
                                name="Loop",
                                code=SFCCodeBlocks(
                                    enter=[_assign("SharedFlag", True)],
                                    exit=[_assign("Sink", _varref("SharedFlag"))],
                                ),
                                fork=SFCFork(targets=("Loop",)),
                            ),
                        ]
                    )
                ],
                equationblocks=[],
            )
        ],
    )

    report = analyze_dataflow(bp)

    issue = next(issue for issue in report.issues if issue.kind == "dataflow.non_state_multi_site")
    assert issue.data is not None
    assert [site["site"] for site in issue.data["continuous_sites"]] == [
        "STEP:Loop:ENTER",
        "STEP:Loop:EXIT",
    ]


def test_dataflow_non_state_multi_site_ignores_single_active_site_in_self_loop() -> None:
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[
            Variable(name="SharedValue", datatype=Simple_DataType.INTEGER),
            Variable(name="Sink", datatype=Simple_DataType.INTEGER),
        ],
        modulecodes=[
            ModuleCode(
                sequences=[
                    _sequence(
                        [
                            _step(
                                "Loop",
                                [
                                    _assign("Sink", _varref("SharedValue")),
                                    _assign("SharedValue", 1),
                                ],
                            ),
                            SFCTransition(name="Gate", condition=True),
                        ]
                    )
                ],
                equationblocks=[],
            )
        ],
    )

    report = analyze_dataflow(bp)

    assert not any(issue.kind == "dataflow.non_state_multi_site" for issue in report.issues)
