"""Focused tests for the opt-in ``datatype-fields`` analyzer."""

import pytest
from sattline_parser.models.ast_model import (
    BasePicture,
    DataType,
    Equation,
    ModuleCode,
    ModuleHeader,
    ScalarDatatype,
    SingleModule,
    Variable,
)
from sattline_parser.models.expressions import Assignment, FuncCall, FuncCallStmt, VarRef

from sattlint.analyzers.datatype_fields import analyze_datatype_fields
from sattlint.analyzers.framework import AnalysisContext, AnalysisSharedArtifacts
from sattlint.analyzers.registry import (
    get_default_analyzer_catalog,
    get_selectable_analyzer_keys,
    get_selectable_analyzers,
)
from sattlint.analyzers.variables import analyze_variables
from sattlint.reporting.variables_report import (
    DATATYPE_FIELD_ANALYSIS_KINDS,
    FieldPathVariableIssue,
    IssueKind,
    UnusedDatatypeFieldIssue,
    UnusedDatatypeIssue,
    VariablesReport,
    VariableTargetIssue,
)


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
            Variable(name="A", datatype=ScalarDatatype.INTEGER),
            Variable(name="B", datatype=ScalarDatatype.REAL),
        ],
    )
    rec = Variable(name="Rec", datatype="RecType")
    m1 = SingleModule(
        header=_hdr("M1"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[rec],
        submodules=[],
        modulecode=ModuleCode(
            equationblocks=[
                Equation(
                    name="UseField",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[Assignment(target=_varref("Rec.A"), value=1)],
                )
            ],
            sequences=[],
        ),
        parametermappings=[],
    )
    return BasePicture(
        header=_hdr("Root"),
        datatype_defs=[dt],
        moduletype_defs=[],
        localvariables=[],
        submodules=[m1],
        modulecode=None,
        moduledef=None,
    )


def test_dependency_typedef_does_not_emit_field_findings() -> None:
    from dataclasses import replace  # noqa: PLC0415

    from sattline_parser.models.ast_model import ModuleTypeDef  # noqa: PLC0415

    nested = SingleModule(
        header=_hdr("Nested"),
        moduleparameters=[],
        localvariables=[Variable(name="Foreign", datatype="RecType")],
        submodules=[],
        moduledef=None,
        modulecode=ModuleCode(
            equationblocks=[
                Equation(
                    name="ReadForeign",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[Assignment(target=_varref("Foreign.B"), value=1)],
                )
            ],
            sequences=[],
        ),
        parametermappings=[],
    )
    foreign_type = ModuleTypeDef(
        name="ForeignHolder",
        moduleparameters=[],
        localvariables=[],
        submodules=[nested],
        moduledef=None,
        modulecode=None,
        origin_file="DependencyLib.s",
        origin_lib="ProjectLib",
    )
    picture = replace(
        _picture_with_unused_field(),
        moduletype_defs=[foreign_type],
        origin_file="Root.s",
        origin_lib="ProjectLib",
    )

    report = analyze_datatype_fields(picture, analyzed_target_is_library=True)

    assert not any("TypeDef:ForeignHolder" in ".".join(issue.module_path or ()) for issue in report.issues)


def _unused_field_names(report: VariablesReport) -> set[str]:
    return {
        issue.field_path
        for issue in report.issues
        if isinstance(issue, UnusedDatatypeFieldIssue) and issue.datatype_name == "RecType"
    }


def test_analyze_datatype_fields_reports_unused_field():
    report = analyze_datatype_fields(_picture_with_unused_field())

    # A is written, which is usage even though nothing reads it. Only B has no
    # read and no write anywhere, so only B is reported.
    assert _unused_field_names(report) == {"B"}


def test_default_variables_run_does_not_emit_datatype_field_kinds():
    report = analyze_variables(_picture_with_unused_field())
    assert _unused_field_names(report) == set()
    field_kinds = {
        IssueKind.UNUSED_DATATYPE,
        IssueKind.UNUSED_DATATYPE_FIELD,
        IssueKind.FIELD_READ_ONLY,
        IssueKind.FIELD_NEVER_READ,
    }
    assert all(issue.kind not in field_kinds for issue in report.issues)


def test_datatype_fields_is_registered_and_selectable():
    assert "datatype-fields" in get_selectable_analyzer_keys()
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
            Variable(name="A", datatype=ScalarDatatype.INTEGER),
            Variable(name="B", datatype=ScalarDatatype.REAL),
        ],
    )
    param_rec = Variable(name="ParamRec", datatype="RecType")
    local_rec = Variable(name="LocalRec", datatype="RecType")
    sink = Variable(name="Sink", datatype=ScalarDatatype.INTEGER)
    module = SingleModule(
        header=_hdr("M1"),
        moduledef=None,
        moduleparameters=[param_rec],
        localvariables=[local_rec, sink],
        submodules=[],
        modulecode=ModuleCode(
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
        ),
        parametermappings=[],
    )
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[dt],
        moduletype_defs=[],
        localvariables=[],
        submodules=[module],
        modulecode=None,
        moduledef=None,
    )
    return bp, param_rec, local_rec


def test_field_usage_is_aggregated_across_module_parameter_and_local_instances():
    bp, param_rec, local_rec = _picture_with_module_and_local_records()

    report = analyze_datatype_fields(bp)

    # ParamRec.B and LocalRec.B are read; LocalRec.A is written. Both fields
    # are therefore used somewhere in the loaded unit, so neither instance may
    # produce a field verdict.
    assert _unused_field_names(report) == set()
    field_issues = [
        issue
        for issue in report.issues
        if isinstance(issue, FieldPathVariableIssue) and (issue.variable is param_rec or issue.variable is local_rec)
    ]
    assert field_issues == []


def test_per_instance_field_asymmetry_is_not_reported():
    bp, _param_rec, _local_rec = _picture_with_module_and_local_records()

    report = analyze_datatype_fields(bp)

    assert not [
        issue for issue in report.issues if issue.kind in {IssueKind.FIELD_READ_ONLY, IssueKind.FIELD_NEVER_READ}
    ]
    assert {issue.kind for issue in report.issues} <= {
        IssueKind.UNUSED_DATATYPE,
        IssueKind.UNUSED_DATATYPE_FIELD,
    }


def test_datatype_field_issue_kind_set_is_global_only():
    assert set(DATATYPE_FIELD_ANALYSIS_KINDS) == {
        IssueKind.UNUSED_DATATYPE,
        IssueKind.UNUSED_DATATYPE_FIELD,
    }


def _picture_with_record_copy() -> BasePicture:
    dt = DataType(
        name="RecType",
        description=None,
        datecode=None,
        var_list=[
            Variable(name="A", datatype=ScalarDatatype.INTEGER),
            Variable(name="B", datatype=ScalarDatatype.REAL),
        ],
    )
    source = Variable(name="Source", datatype="RecType")
    destination = Variable(name="Destination", datatype="RecType")
    status = Variable(name="Status", datatype=ScalarDatatype.INTEGER)
    module = SingleModule(
        header=_hdr("M1"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[source, destination, status],
        submodules=[],
        modulecode=ModuleCode(
            equationblocks=[
                Equation(
                    name="CopyRecord",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        FuncCallStmt(
                            call=FuncCall(
                                name="CopyVariable",
                                args=(_varref("Source"), _varref("Destination"), _varref("Status")),
                            )
                        )
                    ],
                )
            ],
            sequences=[],
        ),
        parametermappings=[],
    )
    return BasePicture(
        header=_hdr("Root"),
        datatype_defs=[dt],
        moduletype_defs=[],
        localvariables=[],
        submodules=[module],
        modulecode=None,
        moduledef=None,
    )


def test_record_copy_marks_every_field_used():
    report = analyze_datatype_fields(_picture_with_record_copy())

    assert _unused_field_names(report) == set()


def test_reduced_mode_reuses_published_variables_analyzer_and_keeps_findings():
    bp = _picture_with_unused_field()
    shared = AnalysisSharedArtifacts()
    context = AnalysisContext(base_picture=bp, shared_artifacts=shared)

    analyze_variables(bp, analysis_context=context)
    published = shared.variable_analyzer
    assert published is not None
    assert getattr(published, "_field_usage_only", False) is False

    reduced = analyze_datatype_fields(bp, analysis_context=context)
    full = analyze_datatype_fields(bp)

    assert shared.variable_analyzer is published
    assert reduced.accesses_by_definition_key == {}
    assert full.accesses_by_definition_key != {}

    def issue_key(report: VariablesReport) -> set[tuple[object, ...]]:
        keys: set[tuple[object, ...]] = set()
        for issue in report.issues:
            field_path = issue.field_path if isinstance(issue, FieldPathVariableIssue) else None
            variable_name = issue.variable.name if isinstance(issue, VariableTargetIssue) else None
            keys.add((issue.kind, tuple(issue.module_path or ()), field_path, variable_name))
        return keys

    assert issue_key(reduced) == issue_key(full)


def test_field_usage_only_rejects_non_field_issue_kinds():
    bp = _picture_with_unused_field()

    with pytest.raises(ValueError, match="field_usage_only"):
        analyze_variables(bp, selected_issue_kinds={IssueKind.UNUSED}, field_usage_only=True)


def _picture_with_unused_datatype() -> BasePicture:
    dead_type = DataType(
        name="DeadType",
        description=None,
        datecode=None,
        var_list=[Variable(name="A", datatype=ScalarDatatype.INTEGER)],
    )
    return BasePicture(
        header=_hdr("Root"),
        datatype_defs=[dead_type],
        moduletype_defs=[],
        localvariables=[],
        submodules=[],
        modulecode=None,
        moduledef=None,
    )


def test_unused_datatype_is_reported_once_for_the_definition():
    report = analyze_datatype_fields(_picture_with_unused_datatype())

    assert [issue.kind for issue in report.issues] == [IssueKind.UNUSED_DATATYPE]
    issue = report.issues[0]
    assert isinstance(issue, UnusedDatatypeIssue)
    assert issue.datatype_name == "DeadType"
    assert issue.module_path == ["Root", "DataType:DeadType"]


def test_unused_datatype_metadata_mentions_the_scanned_workspace():
    from sattlint.models._variable_issues import variable_issue_metadata  # noqa: PLC0415

    field_metadata = variable_issue_metadata(IssueKind.UNUSED_DATATYPE_FIELD)
    datatype_metadata = variable_issue_metadata(IssueKind.UNUSED_DATATYPE)

    assert "no consumer in the scanned workspace" in (field_metadata.suggestion or "")
    assert "no consumer in the scanned workspace" in (datatype_metadata.suggestion or "")


def test_used_datatype_does_not_emit_the_record_level_finding():
    report = analyze_datatype_fields(_picture_with_unused_field())

    assert all(issue.kind is not IssueKind.UNUSED_DATATYPE for issue in report.issues)
