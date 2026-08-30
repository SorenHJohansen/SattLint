# pyright: reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportPrivateUsage=false, reportArgumentType=false, reportOptionalMemberAccess=false, reportUnusedImport=false
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from ._analyzers_variables_test_support import *


def test_variables_execution_collect_typedef_issues_covers_branchy_typedef_roles():
    display_param = Variable(name="DisplayParam", datatype=Simple_DataType.INTEGER)
    effect_param = Variable(name="EffectParam", datatype=Simple_DataType.INTEGER)
    procedure_local = Variable(name="ProcedureLocal", datatype=Simple_DataType.INTEGER)
    display_local = Variable(name="DisplayLocal", datatype=Simple_DataType.INTEGER)
    read_only_local = Variable(name="ReadOnlyLocal", datatype=Simple_DataType.INTEGER)
    written_only_local = Variable(name="WrittenOnlyLocal", datatype=Simple_DataType.INTEGER)
    effect_local = Variable(name="EffectLocal", datatype=Simple_DataType.INTEGER)
    moduletype = ModuleTypeDef(
        name="WorkerType",
        moduleparameters=[display_param, effect_param],
        localvariables=[procedure_local, display_local, read_only_local, written_only_local, effect_local],
        submodules=[],
        moduledef=None,
        modulecode=None,
        parametermappings=[],
    )
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[moduletype],
        localvariables=[],
        submodules=[],
        modulecode=None,
        moduledef=None,
    )
    usage_by_id = {
        id(display_param): _UsageStub(is_display_only=True),
        id(effect_param): _UsageStub(read=True, written=True),
        id(procedure_local): _UsageStub(read=True),
        id(display_local): _UsageStub(is_display_only=True),
        id(read_only_local): _UsageStub(read=True, is_read_only=True),
        id(written_only_local): _UsageStub(written=True),
        id(effect_local): _UsageStub(read=True, written=True),
    }
    issues: list[tuple[IssueKind, tuple[str, ...], str, str, str | None]] = []
    helper: Any = SimpleNamespace(
        bp=bp,
        _limit_to_module_path=None,
        _analyze_typedef=lambda *args, **kwargs: None,
        _compute_effective_output_keys=lambda: set(),
        _is_from_root_origin=lambda origin, origin_lib=None: True,
        _get_usage=lambda variable: usage_by_id[id(variable)],
        _procedure_status_issue=lambda variable, usage: (
            ("procedure-status", "Status") if variable is procedure_local else None
        ),
        _add_issue=lambda kind, path, variable, role, field_path=None: issues.append(
            (kind, tuple(path), variable.name, role, field_path)
        ),
        _has_output_effect=lambda *args, **kwargs: False,
        _has_ignorable_output_binding=lambda *args, **kwargs: False,
        _has_procedure_status_binding=lambda *args, **kwargs: False,
        _is_const_candidate=lambda *args, **kwargs: True,
    )

    variables_execution_module._collect_typedef_issues(helper)

    assert (IssueKind.UI_ONLY, ("Root", "TypeDef:WorkerType"), "DisplayParam", "moduleparameter", None) in issues
    assert (
        IssueKind.WRITE_WITHOUT_EFFECT,
        ("Root", "TypeDef:WorkerType"),
        "EffectParam",
        "moduleparameter",
        None,
    ) in issues
    assert (
        IssueKind.PROCEDURE_STATUS,
        ("Root", "TypeDef:WorkerType"),
        "ProcedureLocal",
        "procedure-status",
        "Status",
    ) in issues
    assert (IssueKind.UI_ONLY, ("Root", "TypeDef:WorkerType"), "DisplayLocal", "localvariable", None) in issues
    assert (
        IssueKind.READ_ONLY_NON_CONST,
        ("Root", "TypeDef:WorkerType"),
        "ReadOnlyLocal",
        "localvariable",
        None,
    ) in issues
    assert (
        IssueKind.NEVER_READ,
        ("Root", "TypeDef:WorkerType"),
        "WrittenOnlyLocal",
        "localvariable",
        None,
    ) in issues
    assert (
        IssueKind.WRITE_WITHOUT_EFFECT,
        ("Root", "TypeDef:WorkerType"),
        "EffectLocal",
        "localvariable",
        None,
    ) in issues


def test_variable_quality_issues_fixture_contains_expected_issue_kinds():
    fixture = Path(__file__).parent / "fixtures" / "sample_sattline_files" / "VariableQualityIssues.s"
    bp = parse_source_file(fixture)
    issues = VariablesAnalyzer(bp).run()

    never_read = {
        issue.variable.name for issue in issues if issue.kind is IssueKind.NEVER_READ and issue.variable is not None
    }
    naming_mismatch = {
        issue.variable.name
        for issue in issues
        if issue.kind is IssueKind.NAMING_ROLE_MISMATCH and issue.variable is not None
    }

    assert "DisplayValue" in never_read
    assert "UnusedWrite" in never_read
    assert "LocalFlag" in never_read
    assert "ReadValue" not in never_read
    assert "EffectWrite" not in never_read
    assert "StatusWord" not in never_read
    assert "ActiveStatus" in naming_mismatch
    assert "StatusWord" not in naming_mismatch


def test_module_structure_issues_fixture_contains_expected_issue_kinds():
    fixture = Path(__file__).parent / "fixtures" / "corpus" / "semantic" / "analyzer" / "ModuleStructureIssues.s"
    bp = parse_source_file(fixture)
    issues = VariablesAnalyzer(bp).run()

    write_without_effect = {
        issue.variable.name
        for issue in issues
        if issue.kind is IssueKind.WRITE_WITHOUT_EFFECT and issue.variable is not None
    }

    assert any("BogusParam" in str(issue) for issue in issues if issue.kind is IssueKind.UNKNOWN_PARAMETER_TARGET)
    assert "Internal" in write_without_effect


def test_parameter_mapping_fixture_contains_expected_issue_kinds():
    fixture = Path(__file__).parent / "fixtures" / "corpus" / "semantic" / "analyzer" / "ParameterMappingIssues.s"
    bp = parse_source_file(fixture)
    issues = VariablesAnalyzer(bp).run()

    contract_mismatch = {
        issue.variable.name
        for issue in issues
        if issue.kind is IssueKind.CONTRACT_MISMATCH and issue.variable is not None
    }
    required_param = {
        tuple(issue.module_path) for issue in issues if issue.kind is IssueKind.REQUIRED_PARAMETER_CONNECTION
    }

    assert "Setpoint" in contract_mismatch
    assert len(required_param) > 0


def test_sequence_lifetime_fixture_contains_expected_issue_kinds():
    fixture = Path(__file__).parent / "fixtures" / "sample_sattline_files" / "SequenceLifetimeIssues.s"
    bp = parse_source_file(fixture)
    issues = VariablesAnalyzer(bp).run()

    implicit_latch = {
        issue.variable.name for issue in issues if issue.kind is IssueKind.IMPLICIT_LATCH and issue.variable is not None
    }
    field_never_read = {
        issue.variable.name
        for issue in issues
        if issue.kind is IssueKind.FIELD_NEVER_READ and issue.variable is not None
    }

    assert "LatchValue" in implicit_latch
    assert "CleanValue" not in implicit_latch
    assert "Batch" in field_never_read


def test_misc_issues_fixture_contains_expected_issue_kinds():
    fixture = Path(__file__).parent / "fixtures" / "sample_sattline_files" / "MiscIssues.s"
    bp = parse_source_file(fixture)
    issues = VariablesAnalyzer(bp).run()

    magic_number = len([i for i in issues if i.kind is IssueKind.MAGIC_NUMBER])
    read_only_non_const = {
        issue.variable.name
        for issue in issues
        if issue.kind is IssueKind.READ_ONLY_NON_CONST and issue.variable is not None
    }
    layout_overlap = len([i for i in issues if i.kind is IssueKind.LAYOUT_OVERLAP])

    assert magic_number > 0
    assert "Shadowed" in read_only_non_const
    assert layout_overlap > 0
