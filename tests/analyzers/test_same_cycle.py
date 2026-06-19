# pyright: reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownArgumentType=false, reportPrivateUsage=false
from types import SimpleNamespace

from sattline_parser.models.ast_model import (
    BasePicture,
    ModuleCode,
    ModuleHeader,
    ModuleTypeDef,
    ModuleTypeInstance,
    ParameterMapping,
    Sequence,
    SFCCodeBlocks,
    SFCParallel,
    SFCStep,
    Simple_DataType,
    SingleModule,
    Variable,
)
from sattlint import constants as const
from sattlint.analyzers.registry import get_actual_cli_analyzer_keys, get_default_analyzers
from sattlint.analyzers.same_cycle import analyze_same_cycle


def _hdr(name: str) -> ModuleHeader:
    return ModuleHeader(name=name, invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0))


def _eq(name: str, code: list[object]) -> SimpleNamespace:
    return SimpleNamespace(name=name, code=code)


def _varref(name: str) -> dict[str, str]:
    return {const.KEY_VAR_NAME: name}


def _assign(name: str, value: object) -> tuple[object, object, object]:
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


def test_same_cycle_analyzer_is_registered_and_opt_in_for_cli() -> None:
    specs = {spec.key: spec for spec in get_default_analyzers()}

    assert "same-cycle" in specs
    assert specs["same-cycle"].enabled is True
    assert "same-cycle" not in get_actual_cli_analyzer_keys()


def test_same_cycle_reports_parallel_read_write_hazard() -> None:
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[
            Variable(name="SharedValue", datatype=Simple_DataType.INTEGER),
            Variable(name="Output", datatype=Simple_DataType.INTEGER),
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
            equations=[],
        ),
    )

    report = analyze_same_cycle(bp)

    issue = next(issue for issue in report.issues if issue.kind == "same_cycle_parallel_read_write_hazard")
    assert "SeqMain" in issue.message
    assert issue.data == {
        "sequence": "SeqMain",
        "parallel_id": 1,
        "conflicts": ["Root.SharedValue"],
    }


def test_same_cycle_reports_cross_module_shared_access_hazard() -> None:
    reader = SingleModule(
        header=_hdr("Reader"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[Variable(name="Output", datatype=Simple_DataType.INTEGER)],
        submodules=[],
        modulecode=ModuleCode(
            equations=[_eq("ReadEq", [_assign("Output", _varref("SharedValue"))])],
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
        modulecode=ModuleCode(equations=[_eq("WriteEq", [_assign("SharedValue", 0)])], sequences=[]),
        parametermappings=[],
    )
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[Variable(name="SharedValue", datatype=Simple_DataType.INTEGER)],
        submodules=[reader, writer],
        modulecode=ModuleCode(equations=[], sequences=[]),
    )

    report = analyze_same_cycle(bp)

    issue = next(issue for issue in report.issues if issue.kind == "same_cycle_shared_access_hazard")
    assert "Root.SharedValue" in issue.message
    assert "Reader (read)" in issue.message
    assert "Writer (write)" in issue.message


def test_same_cycle_reports_external_invocation_mapping_shared_access_hazard() -> None:
    external_reader = ModuleTypeDef(
        name="ExternalReader",
        moduleparameters=[Variable(name="Input", datatype=Simple_DataType.INTEGER)],
        localvariables=[Variable(name="Output", datatype=Simple_DataType.INTEGER)],
        submodules=[],
        moduledef=None,
        modulecode=ModuleCode(
            equations=[_eq("ReadEq", [_assign("Output", _varref("Input"))])],
            sequences=[],
        ),
        parametermappings=[],
        origin_file="ExternalDep.s",
        origin_lib="ExternalLib",
    )
    writer = SingleModule(
        header=_hdr("Writer"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[],
        submodules=[],
        modulecode=ModuleCode(equations=[_eq("WriteEq", [_assign("SharedValue", 0)])], sequences=[]),
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
                        source_type=const.TREE_TAG_VARIABLE_NAME,
                        is_duration=False,
                        is_source_global=False,
                        source=_varref("SharedValue"),
                    )
                ],
            ),
            writer,
        ],
        modulecode=ModuleCode(equations=[], sequences=[]),
        origin_file="Root.s",
        origin_lib="RootLib",
    )

    report = analyze_same_cycle(bp)

    issue = next(issue for issue in report.issues if issue.kind == "same_cycle_shared_access_hazard")
    assert "Root.SharedValue" in issue.message
    assert "ReaderInst (read)" in issue.message
    assert "Writer (write)" in issue.message
