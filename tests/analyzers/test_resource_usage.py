from sattline_parser.models.ast_model import BasePicture, Equation, ModuleCode, ModuleHeader, Simple_DataType, Variable
from sattlint import constants as const
from sattlint.analyzers.registry import get_actual_cli_analyzer_keys, get_default_analyzers
from sattlint.analyzers.resource_usage import analyze_resource_usage


def _hdr(name: str) -> ModuleHeader:
    return ModuleHeader(name=name, invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0))


def _varref(name: str) -> dict[str, str]:
    return {const.KEY_VAR_NAME: name}


def test_resource_usage_analyzer_is_registered_and_opt_in_for_cli() -> None:
    specs = {spec.key: spec for spec in get_default_analyzers()}

    assert "resource-usage" in specs
    assert specs["resource-usage"].enabled is True
    assert "resource-usage" not in get_actual_cli_analyzer_keys()


def test_resource_usage_reports_release_without_acquire() -> None:
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[
            Variable(name="FileRef", datatype="tObject"),
            Variable(name="AsyncOp", datatype="AsyncOperation"),
            Variable(name="Status", datatype=Simple_DataType.INTEGER),
        ],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Main",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (
                            const.KEY_FUNCTION_CALL,
                            "CloseFile",
                            [_varref("FileRef"), _varref("AsyncOp"), _varref("Status")],
                        )
                    ],
                )
            ]
        ),
    )

    report = analyze_resource_usage(bp)

    assert any(issue.kind == "resource_usage.release_without_acquire" for issue in report.issues)


def test_resource_usage_reports_reacquire_and_leak() -> None:
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[
            Variable(name="FileRef", datatype="tObject"),
            Variable(name="AsyncOp", datatype="AsyncOperation"),
            Variable(name="Status", datatype=Simple_DataType.INTEGER),
        ],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Main",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (
                            const.KEY_FUNCTION_CALL,
                            "OpenReadFile",
                            [_varref("FileRef"), "first.txt", _varref("AsyncOp"), _varref("Status")],
                        ),
                        (
                            const.KEY_FUNCTION_CALL,
                            "OpenWriteFile",
                            [_varref("FileRef"), "second.txt", _varref("AsyncOp"), _varref("Status")],
                        ),
                    ],
                )
            ]
        ),
    )

    report = analyze_resource_usage(bp)

    assert any(issue.kind == "resource_usage.acquire_without_release" for issue in report.issues)
    assert any(issue.kind == "resource_usage.leaked_resource" for issue in report.issues)
