# pyright: reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownArgumentType=false, reportPrivateUsage=false
from types import SimpleNamespace

from sattline_parser.models.ast_model import (
    BasePicture,
    ModuleCode,
    ModuleHeader,
    ModuleTypeDef,
    Sequence,
    SFCCodeBlocks,
    SFCParallel,
    SFCStep,
    Simple_DataType,
    Variable,
)
from sattlint import constants as const
from sattlint.analyzers import scan_concurrency as scan_concurrency_module
from sattlint.analyzers.framework import Issue
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

    assert "scan-concurrency" in specs
    assert specs["scan-concurrency"].enabled is True
    assert "scan-concurrency" not in get_actual_cli_analyzer_keys()


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


def test_scan_concurrency_requests_only_parallel_write_race(monkeypatch) -> None:
    bp = BasePicture(header=_hdr("Root"), localvariables=[], modulecode=ModuleCode(sequences=[], equations=[]))
    seen_selected_kinds: list[object] = []

    def _fake_analyze_same_cycle(*_args, **kwargs):
        seen_selected_kinds.append(kwargs.get("selected_issue_kinds"))
        return SimpleNamespace(
            issues=[
                Issue(kind="sfc_parallel_write_race", message="race", module_path=["Root"], data=None),
                Issue(kind="sfc_unreachable_transition", message="other", module_path=["Root"], data=None),
            ]
        )

    monkeypatch.setattr(scan_concurrency_module, "analyze_same_cycle", _fake_analyze_same_cycle)

    report = scan_concurrency_module.analyze_scan_concurrency(bp)

    assert seen_selected_kinds == [scan_concurrency_module._SCAN_CONCURRENCY_ISSUE_KINDS]
    assert [issue.kind for issue in report.issues] == ["sfc_parallel_write_race"]


def test_scan_concurrency_reports_root_typedef_parallel_write_race() -> None:
    typedef = ModuleTypeDef(
        name="UnitType",
        moduleparameters=[],
        localvariables=[Variable(name="SharedOutput", datatype=Simple_DataType.INTEGER)],
        submodules=[],
        moduledef=None,
        modulecode=ModuleCode(
            sequences=[
                _sequence(
                    [
                        SFCParallel(
                            branches=[
                                [_step("Left", [_assign("SharedOutput", 1)])],
                                [_step("Right", [_assign("SharedOutput", 2)])],
                            ]
                        )
                    ]
                )
            ],
            equations=[],
        ),
        parametermappings=[],
    )
    bp = BasePicture(header=_hdr("Root"), moduletype_defs=[typedef], localvariables=[], modulecode=None)

    report = analyze_scan_concurrency(bp)

    assert [issue.kind for issue in report.issues] == ["sfc_parallel_write_race"]
    assert report.issues[0].module_path == ["Root", "TypeDef:UnitType"]
