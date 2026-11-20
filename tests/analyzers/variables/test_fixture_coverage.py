# pyright: reportPrivateUsage=false
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from sattline_parser.models.ast_model import (
    BasePicture,
    ModuleTypeDef,
    ScalarDatatype,
    Variable,
)

from sattlint.analyzers.variables import (
    IssueKind,
    VariablesAnalyzer,
)
from sattlint.analyzers.variables import (
    _variables_execution as variables_execution_module,
)
from sattlint.parser_api import parse_source_file
from sattlint.reporting.variables_report import (
    ALL_VARIABLE_ANALYSIS_KINDS,
    FieldNeverReadIssue,
    FieldPathVariableIssue,
    ImplicitLatchIssue,
    NeverReadIssue,
    ReadOnlyNonConstIssue,
    VariableIssue,
    VariableTargetIssue,
    WriteWithoutEffectIssue,
)
from tests.helpers.variable_test_support import (
    UsageStub as _UsageStub,
)
from tests.helpers.variable_test_support import (
    hdr as _hdr,
)


def test_variables_execution_collect_typedef_issues_covers_branchy_typedef_roles():
    display_param = Variable(name="DisplayParam", datatype=ScalarDatatype.INTEGER)
    effect_param = Variable(name="EffectParam", datatype=ScalarDatatype.INTEGER)
    procedure_local = Variable(name="ProcedureLocal", datatype=ScalarDatatype.INTEGER)
    display_local = Variable(name="DisplayLocal", datatype=ScalarDatatype.INTEGER)
    read_only_local = Variable(name="ReadOnlyLocal", datatype=ScalarDatatype.INTEGER)
    written_only_local = Variable(name="WrittenOnlyLocal", datatype=ScalarDatatype.INTEGER)
    effect_local = Variable(name="EffectLocal", datatype=ScalarDatatype.INTEGER)
    moduletype = ModuleTypeDef(
        name="WorkerType",
        moduleparameters=[display_param, effect_param],
        localvariables=[procedure_local, display_local, read_only_local, written_only_local, effect_local],
        submodules=[],
        moduledef=None,
        modulecode=None,
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

    def _ignore(*args: object, **kwargs: object) -> None:
        return None

    def _no_effective_output_keys() -> set[str]:
        return set()

    def _always_root_origin(origin: str, origin_lib: str | None = None) -> bool:
        return True

    def _usage_for(variable: Variable) -> _UsageStub:
        return usage_by_id[id(variable)]

    def _procedure_status_for(variable: Variable, usage: _UsageStub) -> tuple[str, str] | None:
        return ("procedure-status", "Status") if variable is procedure_local else None

    def _record_issue(issue: VariableIssue) -> None:
        issues.append(
            (
                issue.kind,
                tuple(issue.module_path),
                issue.variable.name if isinstance(issue, VariableTargetIssue) else "",
                issue.role or "",
                issue.field_path if isinstance(issue, FieldPathVariableIssue) else None,
            )
        )

    def _false_flag(*args: object, **kwargs: object) -> bool:
        return False

    def _true_flag(*args: object, **kwargs: object) -> bool:
        return True

    helper: Any = SimpleNamespace(
        bp=bp,
        _limit_to_module_path=None,
        _selected_issue_kinds=None,
        _analyze_typedef=_ignore,
        _compute_effective_output_keys=_no_effective_output_keys,
        _is_from_root_origin=_always_root_origin,
        _get_usage=_usage_for,
        _procedure_status_issue=_procedure_status_for,
        _append_issue=_record_issue,
        _has_output_effect=_false_flag,
        _has_ignorable_output_binding=_false_flag,
        _has_procedure_status_binding=_false_flag,
        _is_const_candidate=_true_flag,
    )

    variables_execution_module._collect_typedef_issues(helper)

    assert (
        IssueKind.WRITE_WITHOUT_EFFECT,
        ("Root", "TypeDef:WorkerType"),
        "EffectParam",
        "moduleparameter",
        None,
    ) not in issues
    assert (
        IssueKind.PROCEDURE_STATUS,
        ("Root", "TypeDef:WorkerType"),
        "ProcedureLocal",
        "procedure-status",
        "Status",
    ) in issues
    assert (
        IssueKind.READ_ONLY_NON_CONST,
        ("Root", "TypeDef:WorkerType"),
        "DisplayLocal",
        "localvariable",
        None,
    ) in issues
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
    fixture = Path(__file__).resolve().parents[2] / "fixtures" / "sample_sattline_files" / "VariableQualityIssues.s"
    bp = parse_source_file(fixture)
    issues = VariablesAnalyzer(bp).run()

    never_read = {issue.variable.name for issue in issues if isinstance(issue, NeverReadIssue)}

    assert "DisplayValue" in never_read
    assert "UnusedWrite" in never_read
    assert "LocalFlag" in never_read
    assert "ReadValue" not in never_read
    assert "EffectWrite" not in never_read
    assert "StatusWord" not in never_read


def test_module_structure_issues_fixture_contains_expected_issue_kinds():
    fixture = (
        Path(__file__).resolve().parents[2] / "fixtures" / "corpus" / "semantic" / "analyzer" / "ModuleStructIssues.s"
    )
    bp = parse_source_file(fixture)
    issues = VariablesAnalyzer(bp).run()

    write_without_effect = {issue.variable.name for issue in issues if isinstance(issue, WriteWithoutEffectIssue)}

    assert not any(issue.kind is IssueKind.UNKNOWN_PARAMETER_TARGET for issue in issues)
    assert "Internal" in write_without_effect


def test_parameter_mapping_fixture_contains_expected_issue_kinds():
    fixture = (
        Path(__file__).resolve().parents[2]
        / "fixtures"
        / "corpus"
        / "semantic"
        / "analyzer"
        / "ParameterMappingIssues.s"
    )
    bp = parse_source_file(fixture)
    issues = VariablesAnalyzer(bp).run()

    min_max_mismatch = {
        tuple(issue.module_path) for issue in issues if issue.kind is IssueKind.MIN_MAX_MAPPING_MISMATCH
    }

    assert len(min_max_mismatch) > 0


def test_sequence_lifetime_fixture_contains_expected_issue_kinds():
    fixture = Path(__file__).resolve().parents[2] / "fixtures" / "sample_sattline_files" / "SequenceLifetime.s"
    bp = parse_source_file(fixture)
    issues = VariablesAnalyzer(bp, selected_issue_kinds=frozenset(ALL_VARIABLE_ANALYSIS_KINDS)).run()

    implicit_latch = {issue.variable.name for issue in issues if isinstance(issue, ImplicitLatchIssue)}
    field_never_read = {issue.variable.name for issue in issues if isinstance(issue, FieldNeverReadIssue)}

    assert "LatchValue" in implicit_latch
    assert "CleanValue" not in implicit_latch
    assert "Batch" in field_never_read


def test_misc_issues_fixture_contains_expected_issue_kinds():
    fixture = Path(__file__).resolve().parents[2] / "fixtures" / "sample_sattline_files" / "MiscIssues.s"
    bp = parse_source_file(fixture)
    issues = VariablesAnalyzer(bp).run()

    magic_number = len([i for i in issues if i.kind is IssueKind.MAGIC_NUMBER])
    read_only_non_const = {issue.variable.name for issue in issues if isinstance(issue, ReadOnlyNonConstIssue)}

    assert magic_number > 0
    assert "Shadowed" in read_only_non_const
