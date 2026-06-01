from sattline_parser.models.ast_model import BasePicture, Equation, ModuleCode, ModuleHeader, Simple_DataType, Variable
from sattlint import constants as const
from sattlint.analyzers.data_dependency import analyze_data_dependency
from sattlint.analyzers.registry import get_actual_cli_analyzer_keys, get_default_analyzers


def _hdr(name: str) -> ModuleHeader:
    return ModuleHeader(name=name, invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0))


def _varref(name: str) -> dict[str, str]:
    return {const.KEY_VAR_NAME: name}


def test_data_dependency_analyzer_is_registered_and_opt_in_for_cli() -> None:
    specs = {spec.key: spec for spec in get_default_analyzers()}

    assert "data-dependency" in specs
    assert specs["data-dependency"].enabled is True
    assert "data-dependency" not in get_actual_cli_analyzer_keys()


def test_data_dependency_reports_transitive_dependency_path() -> None:
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[
            Variable(name="Input", datatype=Simple_DataType.BOOLEAN, init_value=True),
            Variable(name="Mid", datatype=Simple_DataType.BOOLEAN),
            Variable(name="Output", datatype=Simple_DataType.BOOLEAN),
        ],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Main",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (const.KEY_ASSIGN, _varref("Mid"), _varref("Input")),
                        (const.KEY_ASSIGN, _varref("Output"), _varref("Mid")),
                    ],
                )
            ]
        ),
    )

    report = analyze_data_dependency(bp)

    assert any(
        issue.kind == "data_dependency.path"
        and issue.data is not None
        and issue.data.get("path") == ["Output", "Mid", "Input"]
        for issue in report.issues
    )


def test_data_dependency_reports_initialization_order_hazard() -> None:
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[
            Variable(name="Source", datatype=Simple_DataType.INTEGER),
            Variable(name="Output", datatype=Simple_DataType.INTEGER),
        ],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Main",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (const.KEY_ASSIGN, _varref("Output"), _varref("Source")),
                        (const.KEY_ASSIGN, _varref("Source"), 3),
                    ],
                )
            ]
        ),
    )

    report = analyze_data_dependency(bp)

    assert any(
        issue.kind == "data_dependency.initialization_order"
        and issue.data is not None
        and issue.data.get("target") == "Output"
        and issue.data.get("source") == "Source"
        for issue in report.issues
    )
