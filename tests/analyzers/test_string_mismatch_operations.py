from pathlib import Path

from sattline_parser.models.ast_model import (
    BasePicture,
    Equation,
    ModuleCode,
    ModuleDef,
    ModuleHeader,
    Simple_DataType,
    Variable,
)
from sattline_parser.models.expressions import FuncCall, FuncCallStmt, SLExpression, VarRef

from sattlint.analyzers.variables import IssueKind, VariablesAnalyzer
from sattlint.engine import parse_source_file

SAMPLE_FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "sample_sattline_files"


def _hdr(name: str) -> ModuleHeader:
    return ModuleHeader(name=name, invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0))


def _varref(name: str) -> VarRef:
    return VarRef(name=name)


def _func(name: str, *args: SLExpression) -> FuncCallStmt:
    return FuncCallStmt(call=FuncCall(name=name, args=tuple(args)))


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
                    code=code,  # pyright: ignore[reportArgumentType]
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

    mismatch_issues = [
        issue for issue in analyzer.issues if issue.kind is IssueKind.STRING_MAPPING_MISMATCH
    ]

    assert len(mismatch_issues) >= 1
    assert any("concatenate" in (issue.role or "").casefold() for issue in mismatch_issues)


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

    mismatch_issues = [
        issue for issue in analyzer.issues if issue.kind is IssueKind.STRING_MAPPING_MISMATCH
    ]

    assert len(mismatch_issues) >= 1
    assert any("insertstring" in (issue.role or "").casefold() for issue in mismatch_issues)


def test_variables_analyzer_does_not_report_non_overflow_concatenate() -> None:
    base_picture = _base_picture(
        variables=[
            Variable(name="Left", datatype=Simple_DataType.IDENTSTRING, init_value="Hi"),
            Variable(name="Right", datatype=Simple_DataType.IDENTSTRING, init_value=" "),
            Variable(name="Result", datatype=Simple_DataType.IDENTSTRING),
            Variable(name="Status", datatype=Simple_DataType.INTEGER),
        ],
        code=[
            _func("ClearString", _varref("Result")),
            _func("Concatenate", _varref("Left"), _varref("Right"), _varref("Result"), _varref("Status")),
        ],
    )

    analyzer = VariablesAnalyzer(base_picture)
    analyzer.run()

    concatenate_mismatches = [
        issue
        for issue in analyzer.issues
        if issue.kind is IssueKind.STRING_MAPPING_MISMATCH and "concatenate" in (issue.role or "").casefold()
    ]

    assert len(concatenate_mismatches) == 0


def test_variables_analyzer_reports_mismatch_for_real_parsed_file() -> None:
    sample_file = SAMPLE_FIXTURE_DIR / "string_concatenation_overflow.sattline"
    if not sample_file.exists():
        return

    bp = parse_source_file(sample_file)
    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    mismatch_issues = [
        issue for issue in analyzer.issues if issue.kind is IssueKind.STRING_MAPPING_MISMATCH
    ]

    assert len(mismatch_issues) >= 1
