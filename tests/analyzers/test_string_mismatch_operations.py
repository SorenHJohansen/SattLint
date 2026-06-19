from pathlib import Path

from sattline_parser.grammar import constants as const
from sattline_parser.models.ast_model import (
    BasePicture,
    Equation,
    ModuleCode,
    ModuleDef,
    ModuleHeader,
    Simple_DataType,
    Variable,
)
from sattlint.analyzers.variables import IssueKind, VariablesAnalyzer
from sattlint.engine import parse_source_file

SAMPLE_FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "sample_sattline_files"


def _hdr(name: str) -> ModuleHeader:
    return ModuleHeader(name=name, invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0))


def _varref(name: str) -> dict[str, str]:
    return {"var_name": name}


def _func(name: str, *args: object) -> tuple[str, str, list[object]]:
    return (const.KEY_FUNCTION_CALL, name, list(args))


def _base_picture(*, variables: list[Variable], code: list[object]) -> BasePicture:
    return BasePicture(
        header=_hdr("Root"),
        localvariables=variables,
        moduledef=ModuleDef(),
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Main",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=code,
                )
            ]
        ),
    )


def test_variables_analyzer_reports_concatenate_overflow_as_string_mismatch() -> None:
    base_picture = _base_picture(
        variables=[
            Variable(name="Left", datatype=Simple_DataType.IDENTSTRING, init_value="Test"),
            Variable(name="Right", datatype=Simple_DataType.IDENTSTRING, init_value="AnotherIdent"),
            Variable(name="Result", datatype=Simple_DataType.IDENTSTRING),
            Variable(name="Status", datatype=Simple_DataType.INTEGER),
        ],
        code=[
            _func("ClearString", _varref("Result")),
            _func("SetStringPos", _varref("Left"), 1, _varref("Status")),
            _func("SetStringPos", _varref("Right"), 1, _varref("Status")),
            _func("Concatenate", _varref("Left"), _varref("Right"), _varref("Result"), _varref("Status")),
        ],
    )

    analyzer = VariablesAnalyzer(base_picture)
    analyzer.run()

    issues = [issue for issue in analyzer.issues if issue.kind is IssueKind.STRING_MAPPING_MISMATCH]

    assert len(issues) == 1
    assert issues[0].module_path == ["Root"]
    assert issues[0].variable is not None
    assert issues[0].variable.name == "Result"
    assert issues[0].source_role == "builtin result"
    assert issues[0].source_display_name is not None
    assert "Concatenate result" in issues[0].source_display_name
    assert "TestAnotherIdent" in issues[0].source_display_name


def test_variables_analyzer_reports_insertstring_overflow_as_string_mismatch() -> None:
    base_picture = _base_picture(
        variables=[
            Variable(name="Result", datatype=Simple_DataType.IDENTSTRING, init_value="Test"),
            Variable(name="Source", datatype=Simple_DataType.IDENTSTRING, init_value="AnotherIdent"),
            Variable(name="Status", datatype=Simple_DataType.INTEGER),
        ],
        code=[
            _func("SetStringPos", _varref("Result"), 5, _varref("Status")),
            _func("InsertString", _varref("Result"), _varref("Source"), 12, _varref("Status")),
        ],
    )

    analyzer = VariablesAnalyzer(base_picture)
    analyzer.run()

    issues = [issue for issue in analyzer.issues if issue.kind is IssueKind.STRING_MAPPING_MISMATCH]

    assert len(issues) == 1
    assert issues[0].module_path == ["Root"]
    assert issues[0].variable is not None
    assert issues[0].variable.name == "Result"
    assert issues[0].source_role == "builtin result"
    assert issues[0].source_display_name is not None
    assert "InsertString result" in issues[0].source_display_name
    assert "TestAnotherIdent" in issues[0].source_display_name


def test_variables_analyzer_ignores_string_operations_that_fit_target_capacity() -> None:
    base_picture = _base_picture(
        variables=[
            Variable(name="Left", datatype=Simple_DataType.IDENTSTRING, init_value="Test"),
            Variable(name="Right", datatype=Simple_DataType.IDENTSTRING, init_value="Id"),
            Variable(name="Result", datatype=Simple_DataType.IDENTSTRING),
            Variable(name="Status", datatype=Simple_DataType.INTEGER),
        ],
        code=[
            _func("ClearString", _varref("Result")),
            _func("SetStringPos", _varref("Left"), 1, _varref("Status")),
            _func("SetStringPos", _varref("Right"), 1, _varref("Status")),
            _func("Concatenate", _varref("Left"), _varref("Right"), _varref("Result"), _varref("Status")),
        ],
    )

    analyzer = VariablesAnalyzer(base_picture)
    analyzer.run()

    assert not any(issue.kind is IssueKind.STRING_MAPPING_MISMATCH for issue in analyzer.issues)


def test_variables_analyzer_uses_overflow_fixture_end_to_end() -> None:
    base_picture = parse_source_file(SAMPLE_FIXTURE_DIR / "TestOverFlow.s")

    analyzer = VariablesAnalyzer(base_picture)
    issues = [issue for issue in analyzer.run() if issue.kind is IssueKind.STRING_MAPPING_MISMATCH]

    assert len(issues) == 1
    assert issues[0].module_path == ["BasePicture"]
    assert issues[0].variable is not None
    assert issues[0].variable.name == "PathNotOK"
    assert issues[0].source_role == "builtin result"
    assert issues[0].source_display_name is not None
    assert "Concatenate result" in issues[0].source_display_name
