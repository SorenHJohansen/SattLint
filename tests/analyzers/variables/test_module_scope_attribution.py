"""Where module-type findings are attributed in full and scoped runs."""

from sattline_parser.models.ast_model import (
    BasePicture,
    ModuleCode,
    ModuleHeader,
    ModuleTypeDef,
    ModuleTypeInstance,
    ScalarDatatype,
    Variable,
)

from sattlint.analyzers.variables import VariablesAnalyzer
from sattlint.models._variable_issues import VariableIssue
from sattlint.reporting.variables_report import IssueKind


def _hdr(name: str) -> ModuleHeader:
    return ModuleHeader(name=name, invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0))


def _picture_with_unused_typedef_local() -> BasePicture:
    unused_local = Variable(name="Spare", datatype=ScalarDatatype.INTEGER)
    typedef = ModuleTypeDef(
        name="Pump",
        moduleparameters=[],
        localvariables=[unused_local],
        submodules=[],
        moduledef=None,
        modulecode=None,
        origin_file="Root.s",
    )
    instance = ModuleTypeInstance(
        header=_hdr("Pump1"),
        moduletype_name="Pump",
        parametermappings=[],
    )
    return BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[typedef],
        localvariables=[],
        submodules=[instance],
        modulecode=ModuleCode(equationblocks=[], sequences=[]),
        moduledef=None,
        origin_file="Root.s",
    )


def _unused_paths(issues: list[VariableIssue]) -> list[list[str]]:
    return [issue.module_path for issue in issues if issue.kind is IssueKind.UNUSED]


def test_full_run_reports_a_typedef_local_at_the_type_path() -> None:
    issues = VariablesAnalyzer(_picture_with_unused_typedef_local()).run()

    paths = _unused_paths(issues)
    assert paths
    assert all("TypeDef:Pump" in path for path in paths)
    assert all("Pump1" not in path for path in paths)


def test_module_scoped_run_reports_the_same_local_at_the_instance_path() -> None:
    issues = VariablesAnalyzer(_picture_with_unused_typedef_local()).run(limit_to_module_path=["Root", "Pump1"])

    paths = _unused_paths(issues)
    assert paths
    assert all("Pump1" in path for path in paths)
