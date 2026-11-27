# pyright: reportPrivateUsage=false
from types import SimpleNamespace
from typing import Any, cast

from sattline_parser.ast import MappingSource
from sattline_parser.models.ast_model import (
    BasePicture,
    DataType,
    ModuleTypeDef,
    ModuleTypeInstance,
    ParameterMapping,
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
from sattlint.reporting.variables_report import (
    NestedRecordCandidateIssue,
    NeverReadIssue,
    StringMappingMismatchIssue,
    UnusedIssue,
    VariableIssue,
    VariablesReport,
)
from tests.helpers.variable_test_support import (
    UsageStub as _UsageStub,
)
from tests.helpers.variable_test_support import (
    hdr as _hdr,
)
from tests.helpers.variable_test_support import (
    varref as _varref,
)


def test_nested_record_candidate_reports_a_shared_field_group():
    signal_a = DataType(
        name="SignalA",
        description=None,
        datecode=None,
        var_list=[
            Variable(name="Raw", datatype=ScalarDatatype.REAL),
            Variable(name="Min", datatype=ScalarDatatype.REAL),
            Variable(name="Max", datatype=ScalarDatatype.REAL),
            Variable(name="Scale", datatype=ScalarDatatype.REAL),
        ],
        origin_file="LibraryRoot.s",
        origin_lib="ProjectLib",
    )
    signal_b = DataType(
        name="SignalB",
        description=None,
        datecode=None,
        var_list=[
            Variable(name="Raw", datatype=ScalarDatatype.REAL),
            Variable(name="Min", datatype=ScalarDatatype.REAL),
            Variable(name="Max", datatype=ScalarDatatype.REAL),
            Variable(name="Offset", datatype=ScalarDatatype.REAL),
        ],
        origin_file="LibraryRoot.s",
        origin_lib="ProjectLib",
    )

    bp = BasePicture(
        header=_hdr("BasePicture"),
        datatype_defs=[signal_a, signal_b],
        moduletype_defs=[],
        localvariables=[],
        submodules=[],
        modulecode=None,
        moduledef=None,
        origin_file="LibraryRoot.s",
        origin_lib="ProjectLib",
    )

    analyzer = VariablesAnalyzer(bp, analyzed_target_is_library=True)
    analyzer.run()

    duplication_issues = [issue for issue in analyzer.issues if issue.kind is IssueKind.DATATYPE_DUPLICATION]
    assert len(duplication_issues) == 1
    issue = duplication_issues[0]
    assert isinstance(issue, NestedRecordCandidateIssue)
    assert issue.field_names == ("Raw", "Min", "Max")
    assert issue.record_names == ("SignalA", "SignalB")

    summary = VariablesReport(
        basepicture_name=bp.header.name, issues=cast(list[VariableIssue], duplication_issues)
    ).summary()
    assert "Extractable nested record candidates" in summary
    assert "Fields 'Raw', 'Min', 'Max' repeat in SignalA, SignalB" in summary
    assert "Extract the group into a nested RECORD" in summary


def test_library_target_report_shows_typedef_for_same_lib_different_file_moduletype():
    typedef = ModuleTypeDef(
        name="InfoPanelType",
        moduleparameters=[Variable(name="EnableInteraktion", datatype=ScalarDatatype.BOOLEAN)],
        localvariables=[Variable(name="UnusedLocal", datatype=ScalarDatatype.BOOLEAN)],
        submodules=[],
        moduledef=None,
        modulecode=None,
        origin_file="ApplSupportLib.s",
        origin_lib="ApplSupportLib",
    )
    bp = BasePicture(
        header=_hdr("BasePicture"),
        datatype_defs=[],
        moduletype_defs=[typedef],
        localvariables=[],
        submodules=[
            ModuleTypeInstance(header=_hdr("Y_Info_Panel"), moduletype_name="InfoPanelType", parametermappings=[]),
            ModuleTypeInstance(header=_hdr("X_Info_Panel"), moduletype_name="InfoPanelType", parametermappings=[]),
        ],
        modulecode=None,
        moduledef=None,
        origin_file="ApplSupportLib.s",
        origin_lib="ApplSupportLib",
    )

    analyzer = VariablesAnalyzer(bp, analyzed_target_is_library=True)
    analyzer.run()

    # A library's module-type parameters are consumed by the programs that
    # connect them, even when the library itself never touches them.
    assert not any(
        issue.kind is IssueKind.UNUSED and issue.variable is not None and issue.variable.name == "EnableInteraktion"
        for issue in analyzer.issues
    )
    assert any(
        issue.kind is IssueKind.UNUSED
        and issue.variable is not None
        and issue.variable.name == "UnusedLocal"
        and issue.module_path == ["BasePicture", "TypeDef:InfoPanelType"]
        for issue in analyzer.issues
    )

    summary = VariablesReport(basepicture_name=bp.header.name, issues=analyzer.issues).summary()
    assert "      Moduletype:" in summary
    assert "BasePicture.TypeDef:InfoPanelType :: localvariable UnusedLocal (boolean)" in summary
    assert "      SingleModule:" in summary
    assert "EnableInteraktion" not in summary
    assert "BasePicture.Y_Info_Panel" not in summary
    assert "BasePicture.X_Info_Panel" not in summary


def test_program_target_report_dedupes_root_owned_typedef_instance_findings():
    typedef = ModuleTypeDef(
        name="InfoPanelType",
        moduleparameters=[Variable(name="EnableInteraktion", datatype=ScalarDatatype.BOOLEAN)],
        localvariables=[],
        submodules=[],
        moduledef=None,
        modulecode=None,
        origin_file="ApplSupportLib.s",
        origin_lib="ApplSupportLib",
    )
    bp = BasePicture(
        header=_hdr("BasePicture"),
        datatype_defs=[],
        moduletype_defs=[typedef],
        localvariables=[],
        submodules=[
            ModuleTypeInstance(header=_hdr("Y_Info_Panel"), moduletype_name="InfoPanelType", parametermappings=[]),
            ModuleTypeInstance(header=_hdr("X_Info_Panel"), moduletype_name="InfoPanelType", parametermappings=[]),
        ],
        modulecode=None,
        moduledef=None,
        origin_file="ApplSupportLib.s",
        origin_lib="ApplSupportLib",
    )

    analyzer = VariablesAnalyzer(bp, analyzed_target_is_library=False)
    analyzer.run()

    matching_issues = [
        issue
        for issue in analyzer.issues
        if isinstance(issue, UnusedIssue) and issue.variable.name == "EnableInteraktion"
    ]
    assert len(matching_issues) == 1
    assert matching_issues[0].module_path == ["BasePicture", "TypeDef:InfoPanelType"]

    summary = VariablesReport(basepicture_name=bp.header.name, issues=analyzer.issues).summary()
    assert "      Moduletype:" in summary
    assert "BasePicture.TypeDef:InfoPanelType :: moduleparameter EnableInteraktion (boolean)" in summary
    assert "      SingleModule:" in summary
    assert "BasePicture.Y_Info_Panel :: moduleparameter EnableInteraktion (boolean)" not in summary
    assert "BasePicture.X_Info_Panel :: moduleparameter EnableInteraktion (boolean)" not in summary


def test_library_target_does_not_report_typedefs_from_sibling_projectlib_files():
    foreign_local = Variable(name="FirstIndex", datatype=ScalarDatatype.INTEGER)
    foreign_typedef = ModuleTypeDef(
        name="ListKernel",
        moduleparameters=[],
        localvariables=[foreign_local],
        submodules=[],
        moduledef=None,
        modulecode=None,
        origin_file="ListeLibX.x",
        origin_lib="ProjectLib",
    )
    bp = BasePicture(
        header=_hdr("BasePicture"),
        datatype_defs=[],
        moduletype_defs=[foreign_typedef],
        localvariables=[],
        submodules=[],
        modulecode=None,
        moduledef=None,
        origin_file="ColumnLib.x",
        origin_lib="ProjectLib",
    )
    usage_by_id = {id(foreign_local): _UsageStub(read=True, is_read_only=True)}
    issues: list[tuple[IssueKind, tuple[str, ...], str | None]] = []
    helper: Any

    def _ignore(*args: object, **kwargs: object) -> None:
        return None

    def _no_effective_output_keys() -> set[str]:
        return set()

    def _root_origin(origin: str, origin_lib: str | None = None) -> bool:
        return VariablesAnalyzer._is_from_root_origin(helper, origin, origin_lib)

    def _usage_for(variable: Variable) -> _UsageStub:
        return usage_by_id[id(variable)]

    def _record_issue(issue: VariableIssue) -> None:
        issues.append((issue.kind, tuple(issue.module_path), issue.role))

    def _false_flag(*args: object, **kwargs: object) -> bool:
        return False

    def _true_flag(*args: object, **kwargs: object) -> bool:
        return True

    helper = SimpleNamespace(
        bp=bp,
        analyzed_target_is_library=True,
        _limit_to_module_path=None,
        _selected_issue_kinds=None,
        _analyze_typedef=_ignore,
        _compute_effective_output_keys=_no_effective_output_keys,
        _is_from_root_origin=_root_origin,
        _get_usage=_usage_for,
        _procedure_status_issue=_ignore,
        _append_issue=_record_issue,
        _has_output_effect=_false_flag,
        _has_procedure_status_binding=_false_flag,
        _is_const_candidate=_true_flag,
        _collect_issues_from_module=_ignore,
    )

    variables_execution_module._collect_typedef_issues(helper)

    assert issues == []


def test_unused_summary_splits_moduletype_and_singlemodule_groups():
    moduletype_var = Variable(name="EnableInteraktion", datatype=ScalarDatatype.BOOLEAN)
    singlemodule_var = Variable(name="MinMax", datatype=ScalarDatatype.INTEGER)
    issues = [
        UnusedIssue(
            module_path=["BasePicture", "TypeDef:InfoPanelType"],
            variable=moduletype_var,
            role="moduleparameter",
        ),
        UnusedIssue(
            module_path=["BasePicture", "TypeDef:Column", "L1", "L2", "RPDisp"],
            variable=singlemodule_var,
            role="localvariable",
        ),
    ]

    summary = VariablesReport(basepicture_name="BasePicture", issues=cast(list[VariableIssue], issues)).summary()

    assert "      Moduletype:" in summary
    assert "BasePicture.TypeDef:InfoPanelType :: moduleparameter EnableInteraktion (boolean)" in summary
    assert "      SingleModule:" in summary
    assert "BasePicture.Column.L1.L2.RPDisp :: localvariable MinMax (integer)" in summary
    assert "BasePicture.TypeDef:Column.L1.L2.RPDisp :: localvariable MinMax (integer)" not in summary


def test_never_read_summary_splits_moduletype_and_singlemodule_groups():
    moduletype_var = Variable(name="EnableInteraktion", datatype=ScalarDatatype.BOOLEAN)
    singlemodule_var = Variable(name="MinMax", datatype=ScalarDatatype.INTEGER)
    issues = [
        NeverReadIssue(
            module_path=["BasePicture", "TypeDef:InfoPanelType"],
            variable=moduletype_var,
            role="moduleparameter",
        ),
        NeverReadIssue(
            module_path=["BasePicture", "TypeDef:Column", "L1", "L2", "RPDisp"],
            variable=singlemodule_var,
            role="localvariable",
        ),
    ]

    summary = VariablesReport(basepicture_name="BasePicture", issues=cast(list[VariableIssue], issues)).summary()

    assert "Written but never read variables" in summary
    assert "      Moduletype:" in summary
    assert "BasePicture.TypeDef:InfoPanelType :: moduleparameter EnableInteraktion (boolean)" in summary
    assert "      SingleModule:" in summary
    assert "BasePicture.Column.L1.L2.RPDisp :: localvariable MinMax (integer)" in summary
    assert "BasePicture.TypeDef:Column.L1.L2.RPDisp :: localvariable MinMax (integer)" not in summary


def test_string_mapping_summary_dedupes_root_typedef_singlemodule_rows():
    child_typedef = ModuleTypeDef(
        name="ChildType",
        moduleparameters=[Variable(name="TargetValue", datatype=ScalarDatatype.IDENTSTRING)],
        localvariables=[],
        submodules=[],
        moduledef=None,
        modulecode=None,
    )
    parent_typedef = ModuleTypeDef(
        name="ParentType",
        moduleparameters=[Variable(name="SourceValue", datatype=ScalarDatatype.STRING)],
        localvariables=[],
        submodules=[
            ModuleTypeInstance(
                header=_hdr("Child"),
                moduletype_name="ChildType",
                parametermappings=[
                    ParameterMapping(
                        target=_varref("TargetValue"),
                        source_type=MappingSource.VARIABLE,
                        is_duration=False,
                        is_source_global=False,
                        source=_varref("SourceValue"),
                        source_literal=None,
                    )
                ],
            )
        ],
        moduledef=None,
        modulecode=None,
    )
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[child_typedef, parent_typedef],
        localvariables=[],
        submodules=[ModuleTypeInstance(header=_hdr("Parent"), moduletype_name="ParentType", parametermappings=[])],
        modulecode=None,
        moduledef=None,
    )

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    issues = [issue for issue in analyzer.issues if issue.kind is IssueKind.STRING_MAPPING_MISMATCH]
    assert len(issues) == 1
    assert issues[0].module_path == ["Root", "TypeDef:ParentType", "Child"]
    assert issues[0].source_decl_module_path == ["Root", "TypeDef:ParentType"]
    assert issues[0].source_role == "moduleparameter"

    summary = VariablesReport(basepicture_name=bp.header.name, issues=cast(list[VariableIssue], issues)).summary()

    assert "Root.TypeDef:ParentType.Child" in summary
    assert "Root.Parent.Child" not in summary
    assert "SourceValue" in summary
    assert "moduleparameter" in summary
    assert "identstring" in summary


def test_string_mapping_summary_prefers_original_declaration_type_for_intermediate_path_rows():
    final_typedef = ModuleTypeDef(
        name="FinalType",
        moduleparameters=[Variable(name="FinalValue", datatype=ScalarDatatype.IDENTSTRING)],
        localvariables=[],
        submodules=[],
        moduledef=None,
        modulecode=None,
    )
    relay_typedef = ModuleTypeDef(
        name="RelayType",
        moduleparameters=[Variable(name="RelayValue", datatype=ScalarDatatype.STRING)],
        localvariables=[],
        submodules=[
            ModuleTypeInstance(
                header=_hdr("Final"),
                moduletype_name="FinalType",
                parametermappings=[
                    ParameterMapping(
                        target=_varref("FinalValue"),
                        source_type=MappingSource.VARIABLE,
                        is_duration=False,
                        is_source_global=False,
                        source=_varref("RelayValue"),
                        source_literal=None,
                    )
                ],
            )
        ],
        moduledef=None,
        modulecode=None,
    )
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[final_typedef, relay_typedef],
        localvariables=[Variable(name="OriginalValue", datatype=ScalarDatatype.IDENTSTRING)],
        submodules=[
            ModuleTypeInstance(
                header=_hdr("Relay"),
                moduletype_name="RelayType",
                parametermappings=[
                    ParameterMapping(
                        target=_varref("RelayValue"),
                        source_type=MappingSource.VARIABLE,
                        is_duration=False,
                        is_source_global=False,
                        source=_varref("OriginalValue"),
                        source_literal=None,
                    )
                ],
            )
        ],
        modulecode=None,
        moduledef=None,
    )

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    issues = [issue for issue in analyzer.issues if issue.kind is IssueKind.STRING_MAPPING_MISMATCH]

    assert len(issues) == 1
    assert issues[0].source_variable is not None
    assert issues[0].source_variable.name == "OriginalValue"
    assert issues[0].source_variable.datatype_text == "identstring"

    summary = VariablesReport(basepicture_name=bp.header.name, issues=cast(list[VariableIssue], issues)).summary()

    assert "Intermediate path mismatch only (1):" in summary
    assert "Declaration/final destination mismatch (0):" in summary
    assert "Direct source/type show the value seen at the mismatching hop." in summary
    assert "OriginalValue" in summary
    assert "identstring" in summary
    assert "Root.Relay :: RelayValue" in summary
    assert "string" in summary
    assert "Root.Relay.Final" in summary
    assert "Root.TypeDef:RelayType" not in summary


def test_string_mapping_summary_uses_resolved_field_source_and_target_names():
    issue = StringMappingMismatchIssue(
        module_path=["Root", "Parent", "Panel", "ActivateButton"],
        variable=Variable(name="Text", datatype=ScalarDatatype.IDENTSTRING),
        source_variable=Variable(name="DV.StopText", datatype=ScalarDatatype.IDENTSTRING),
        source_decl_module_path=["Root", "Parent"],
        source_role="localvariable",
        target_display_name="Text",
    )

    summary = VariablesReport(basepicture_name="Root", issues=[issue]).summary()

    assert "Intermediate path mismatch only (1):" in summary
    assert "Declaration/final destination mismatch (0):" in summary
    assert "DV.StopText" in summary
    assert "Text" in summary
