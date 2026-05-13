from sattline_parser.models.ast_model import (
    BasePicture,
    ModuleCode,
    ModuleHeader,
    Sequence,
    SFCCodeBlocks,
    SFCParallel,
    SFCStep,
    Simple_DataType,
    Variable,
)
from sattlint import constants as const
from sattlint.analyzers.registry import get_actual_cli_analyzer_keys, get_default_analyzers
from sattlint.analyzers.scan_concurrency import analyze_scan_concurrency


def _hdr(name: str) -> ModuleHeader:
    return ModuleHeader(name=name, invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0))


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


def test_scan_concurrency_analyzer_is_registered_and_opt_in_for_cli() -> None:
    specs = {spec.key: spec for spec in get_default_analyzers()}

    assert "scan_concurrency" in specs
    assert specs["scan_concurrency"].enabled is True
    assert "scan_concurrency" not in get_actual_cli_analyzer_keys()


def test_scan_concurrency_reports_parallel_write_race() -> None:
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

    report = analyze_scan_concurrency(bp)

    assert len(report.issues) == 1
    assert report.issues[0].kind == "sfc_parallel_write_race"
    assert "SeqMain" in report.issues[0].message
    assert report.summary().startswith("Report: Scan concurrency")
