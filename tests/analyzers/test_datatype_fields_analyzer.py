# pyright: reportPrivateUsage=false
"""Focused tests for the opt-in ``datatype-fields`` analyzer."""

from sattline_parser.models.ast_model import (
    BasePicture,
    DataType,
    Equation,
    ModuleCode,
    ModuleHeader,
    Simple_DataType,
    SingleModule,
    Variable,
)
from sattline_parser.models.expressions import Assignment, VarRef

from sattlint.analyzers.datatype_fields import analyze_datatype_fields
from sattlint.analyzers.registry import (
    DEFAULT_CLI_ANALYZER_KEYS,
    get_default_analyzer_catalog,
    get_selectable_analyzers,
)
from sattlint.analyzers.variables import analyze_variables
from sattlint.reporting.variables_report import IssueKind, VariablesReport


def _hdr(name: str) -> ModuleHeader:
    return ModuleHeader(name=name, invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0))


def _varref(s: str) -> VarRef:
    return VarRef(name=s)


def _picture_with_unused_field() -> BasePicture:
    dt = DataType(
        name="RecType",
        description=None,
        datecode=None,
        var_list=[
            Variable(name="A", datatype=Simple_DataType.INTEGER),
            Variable(name="B", datatype=Simple_DataType.REAL),
        ],
    )
    rec = Variable(name="Rec", datatype="RecType")
    m1 = SingleModule(
        header=_hdr("M1"),
        moduledefs=[],
        moduleparameters=[],
        localvariables=[rec],
        submodules=[],
        modulecodes=[
            ModuleCode(
                equationblocks=[
                    Equation(
                        name="UseField",
                        position=(0.0, 0.0),
                        size=(1.0, 1.0),
                        code=[Assignment(target=_varref("Rec.A"), value=1)],
                    )
                ],
                sequences=[],
            )
        ],
        parametermappings=[],
    )
    return BasePicture(
        header=_hdr("Root"),
        datatype_defs=[dt],
        moduletype_defs=[],
        localvariables=[],
        submodules=[m1],
        modulecodes=[],
        moduledefs=[],
    )


def _unused_field_names(report: VariablesReport) -> set[str]:
    return {
        str(issue.field_path)
        for issue in report.issues
        if issue.kind is IssueKind.UNUSED_DATATYPE_FIELD
        and issue.datatype_name == "RecType"
        and issue.field_path is not None
    }


def test_analyze_datatype_fields_reports_unused_field():
    report = analyze_datatype_fields(_picture_with_unused_field())
    assert _unused_field_names(report) == {"B"}


def test_default_variables_run_does_not_emit_datatype_field_kinds():
    report = analyze_variables(_picture_with_unused_field())
    assert _unused_field_names(report) == set()
    field_kinds = {IssueKind.UNUSED_DATATYPE_FIELD, IssueKind.FIELD_READ_ONLY, IssueKind.FIELD_NEVER_READ}
    assert all(issue.kind not in field_kinds for issue in report.issues)


def test_datatype_fields_is_registered_selectable_but_not_default_cli():
    assert "datatype-fields" not in DEFAULT_CLI_ANALYZER_KEYS
    assert any(spec.key == "datatype-fields" for spec in get_selectable_analyzers())

    catalog = get_default_analyzer_catalog()
    entries = [analyzer for analyzer in catalog.analyzers if analyzer.spec.key == "datatype-fields"]
    assert len(entries) == 1


def _picture_with_module_and_local_records() -> tuple[BasePicture, Variable, Variable]:
    dt = DataType(
        name="RecType",
        description=None,
        datecode=None,
        var_list=[
            Variable(name="A", datatype=Simple_DataType.INTEGER),
            Variable(name="B", datatype=Simple_DataType.REAL),
        ],
    )
    param_rec = Variable(name="ParamRec", datatype="RecType")
    local_rec = Variable(name="LocalRec", datatype="RecType")
    sink = Variable(name="Sink", datatype=Simple_DataType.INTEGER)
    module = SingleModule(
        header=_hdr("M1"),
        moduledefs=[],
        moduleparameters=[param_rec],
        localvariables=[local_rec, sink],
        submodules=[],
        modulecodes=[
            ModuleCode(
                equationblocks=[
                    Equation(
                        name="UseFields",
                        position=(0.0, 0.0),
                        size=(1.0, 1.0),
                        code=[
                            Assignment(target=_varref("LocalRec.A"), value=1),
                            Assignment(target=_varref("Sink"), value=_varref("LocalRec.B")),
                            Assignment(target=_varref("Sink"), value=_varref("ParamRec.B")),
                        ],
                    )
                ],
                sequences=[],
            )
        ],
        parametermappings=[],
    )
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[dt],
        moduletype_defs=[],
        localvariables=[],
        submodules=[module],
        modulecodes=[],
        moduledefs=[],
    )
    return bp, param_rec, local_rec


def test_field_asymmetry_ignores_module_parameter_contract_fields():
    bp, param_rec, _local_rec = _picture_with_module_and_local_records()

    report = analyze_datatype_fields(bp)
    param_issues = [
        issue
        for issue in report.issues
        if issue.variable is param_rec and issue.kind in {IssueKind.FIELD_READ_ONLY, IssueKind.FIELD_NEVER_READ}
    ]

    assert param_issues == []


def test_field_asymmetry_still_reports_local_record_fields():
    bp, _param_rec, local_rec = _picture_with_module_and_local_records()

    report = analyze_datatype_fields(bp)
    local_kinds = {
        issue.kind
        for issue in report.issues
        if issue.variable is local_rec and issue.kind in {IssueKind.FIELD_READ_ONLY, IssueKind.FIELD_NEVER_READ}
    }

    assert local_kinds == {IssueKind.FIELD_READ_ONLY, IssueKind.FIELD_NEVER_READ}
