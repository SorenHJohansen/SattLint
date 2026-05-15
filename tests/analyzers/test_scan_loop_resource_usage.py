from sattline_parser.models.ast_model import (
    BasePicture,
    Equation,
    ModuleCode,
    ModuleHeader,
    Sequence,
    SFCCodeBlocks,
    SFCStep,
)
from sattlint import constants as const
from sattlint.analyzers.registry import get_default_analyzers
from sattlint.analyzers.scan_loop_resource_usage import analyze_scan_loop_resource_usage


def _hdr(name: str) -> ModuleHeader:
    return ModuleHeader(name=name, invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0))


def _varref(name: str) -> dict:
    return {const.KEY_VAR_NAME: name}


def test_scan_loop_resource_usage_flags_non_precision_builtin_in_equation_block() -> None:
    bp = BasePicture(
        header=_hdr("Program"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="MainEq",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (
                            const.KEY_FUNCTION_CALL,
                            "AssignSystemString",
                            [_varref("SysVarId"), _varref("Value"), _varref("Status")],
                        )
                    ],
                )
            ]
        ),
        moduledef=None,
    )

    report = analyze_scan_loop_resource_usage(bp)

    issues = [issue for issue in report.issues if issue.kind == "scan_cycle.resource_usage"]
    assert len(issues) == 1
    assert issues[0].data == {
        "call": "assignsystemstring",
        "context": "equation block 'MainEq'",
        "precision_scangroup": False,
    }


def test_scan_loop_resource_usage_flags_non_precision_builtin_in_active_step_code() -> None:
    bp = BasePicture(
        header=_hdr("Program"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[],
        submodules=[],
        modulecode=ModuleCode(
            sequences=[
                Sequence(
                    name="MainSeq",
                    type="SEQUENCE",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        SFCStep(
                            kind="step",
                            name="Poll",
                            code=SFCCodeBlocks(
                                active=[
                                    (
                                        const.KEY_FUNCTION_CALL,
                                        "AssignSystemString",
                                        [_varref("SysVarId"), _varref("Value"), _varref("Status")],
                                    )
                                ]
                            ),
                        )
                    ],
                )
            ]
        ),
        moduledef=None,
    )

    report = analyze_scan_loop_resource_usage(bp)

    issues = [issue for issue in report.issues if issue.kind == "scan_cycle.resource_usage"]
    assert len(issues) == 1
    assert issues[0].data == {
        "call": "assignsystemstring",
        "context": "active code of step 'Poll' in sequence 'MainSeq'",
        "precision_scangroup": False,
    }


def test_scan_loop_resource_usage_ignores_non_precision_builtin_outside_active_scan_context() -> None:
    bp = BasePicture(
        header=_hdr("Program"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[],
        submodules=[],
        modulecode=ModuleCode(
            sequences=[
                Sequence(
                    name="MainSeq",
                    type="SEQUENCE",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        SFCStep(
                            kind="step",
                            name="Setup",
                            code=SFCCodeBlocks(
                                enter=[
                                    (
                                        const.KEY_FUNCTION_CALL,
                                        "AssignSystemString",
                                        [_varref("SysVarId"), _varref("Value"), _varref("Status")],
                                    )
                                ]
                            ),
                        )
                    ],
                )
            ]
        ),
        moduledef=None,
    )

    report = analyze_scan_loop_resource_usage(bp)

    assert not any(issue.kind == "scan_cycle.resource_usage" for issue in report.issues)


def test_scan_loop_resource_usage_analyzer_is_enabled_by_default() -> None:
    specs = {spec.key: spec for spec in get_default_analyzers()}

    assert "scan-loop-resource-usage" in specs
    assert specs["scan-loop-resource-usage"].enabled is True
