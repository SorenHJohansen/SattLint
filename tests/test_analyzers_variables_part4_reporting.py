# pyright: reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportPrivateUsage=false, reportArgumentType=false, reportOptionalMemberAccess=false, reportUnusedImport=false
from types import SimpleNamespace
from typing import Any

from ._analyzers_variables_test_support import *


def test_datatype_duplication_is_scoped_per_module_and_excludes_anytype():
    fyld = ModuleTypeDef(
        name="Fyld",
        moduleparameters=[
            Variable(name="WildcardA", datatype="AnyType"),
            Variable(name="WildcardB", datatype="AnyType"),
        ],
        localvariables=[
            Variable(name="PhaseTimer", datatype="Timer"),
            Variable(name="PhaseTimerCopy", datatype="Timer"),
        ],
        submodules=[],
        moduledef=None,
        modulecode=None,
        parametermappings=[],
        origin_file="LibraryRoot.x",
        origin_lib="ProjectLib",
    )
    applik = ModuleTypeDef(
        name="Applik",
        moduleparameters=[Variable(name="WildcardC", datatype="AnyType")],
        localvariables=[Variable(name="PhaseTimer", datatype="Timer")],
        submodules=[],
        moduledef=None,
        modulecode=None,
        parametermappings=[],
        origin_file="LibraryRoot.x",
        origin_lib="ProjectLib",
    )

    bp = BasePicture(
        header=_hdr("BasePicture"),
        datatype_defs=[],
        moduletype_defs=[fyld, applik],
        localvariables=[],
        submodules=[],
        modulecode=None,
        moduledef=None,
        origin_file="LibraryRoot.x",
        origin_lib="ProjectLib",
    )

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    duplication_issues = [issue for issue in analyzer.issues if issue.kind is IssueKind.DATATYPE_DUPLICATION]
    assert len(duplication_issues) == 1

    issue = duplication_issues[0]
    assert issue.module_path == ["BasePicture", "TypeDef:Fyld"]
    assert issue.variable is not None
    assert issue.variable.name == "PhaseTimer"
    assert issue.variable.datatype_text == "Timer"
    assert issue.duplicate_count == 2
    assert issue.duplicate_locations == [(["BasePicture", "TypeDef:Fyld"], "localvariable", "PhaseTimerCopy")]

    summary = VariablesReport(basepicture_name=bp.header.name, issues=duplication_issues).summary()
    assert "Datatype 'Timer' declared 2 times in BasePicture.TypeDef:Fyld:" in summary
    assert "+ PhaseTimerCopy (localvariable)" in summary
    assert "AnyType" not in summary
    assert "TypeDef:Applik" not in summary


def test_library_target_report_shows_typedef_for_same_lib_different_file_moduletype():
    typedef = ModuleTypeDef(
        name="InfoPanelType",
        moduleparameters=[Variable(name="EnableInteraktion", datatype=Simple_DataType.BOOLEAN)],
        localvariables=[],
        submodules=[],
        moduledef=None,
        modulecode=None,
        parametermappings=[],
        origin_file="KaHAApplSupportLib.s",
        origin_lib="KaHAApplSupportLib",
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
        origin_file="KaHAApplSupportLib.s",
        origin_lib="KaHAApplSupportLib",
    )

    analyzer = VariablesAnalyzer(bp, analyzed_target_is_library=True)
    analyzer.run()

    assert any(
        issue.kind is IssueKind.UNUSED
        and issue.variable is not None
        and issue.variable.name == "EnableInteraktion"
        and issue.module_path == ["BasePicture", "TypeDef:InfoPanelType"]
        for issue in analyzer.issues
    )

    summary = VariablesReport(basepicture_name=bp.header.name, issues=analyzer.issues).summary()
    assert "      Moduletype:" in summary
    assert "BasePicture.TypeDef:InfoPanelType :: moduleparameter EnableInteraktion (boolean)" in summary
    assert "      SingleModule:" in summary
    assert "BasePicture.Y_Info_Panel :: moduleparameter EnableInteraktion (boolean)" not in summary
    assert "BasePicture.X_Info_Panel :: moduleparameter EnableInteraktion (boolean)" not in summary


def test_program_target_report_dedupes_root_owned_typedef_instance_findings():
    typedef = ModuleTypeDef(
        name="InfoPanelType",
        moduleparameters=[Variable(name="EnableInteraktion", datatype=Simple_DataType.BOOLEAN)],
        localvariables=[],
        submodules=[],
        moduledef=None,
        modulecode=None,
        parametermappings=[],
        origin_file="KaHAApplSupportLib.s",
        origin_lib="KaHAApplSupportLib",
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
        origin_file="KaHAApplSupportLib.s",
        origin_lib="KaHAApplSupportLib",
    )

    analyzer = VariablesAnalyzer(bp, analyzed_target_is_library=False)
    analyzer.run()

    matching_issues = [
        issue
        for issue in analyzer.issues
        if issue.kind is IssueKind.UNUSED and issue.variable is not None and issue.variable.name == "EnableInteraktion"
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
    foreign_local = Variable(name="FirstIndex", datatype=Simple_DataType.INTEGER)
    foreign_typedef = ModuleTypeDef(
        name="ListKernel",
        moduleparameters=[],
        localvariables=[foreign_local],
        submodules=[],
        moduledef=None,
        modulecode=None,
        parametermappings=[],
        origin_file="KaHAListeLibX.x",
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
        origin_file="KaHAMPCSøjleLib.x",
        origin_lib="ProjectLib",
    )
    usage_by_id = {id(foreign_local): _UsageStub(read=True, is_read_only=True)}
    issues: list[tuple[IssueKind, tuple[str, ...], str]] = []
    helper: Any = SimpleNamespace(
        bp=bp,
        analyzed_target_is_library=True,
        _limit_to_module_path=None,
        _analyze_typedef=lambda *args, **kwargs: None,
        _compute_effective_output_keys=lambda: set(),
        _is_from_root_origin=lambda origin, origin_lib=None: VariablesAnalyzer._is_from_root_origin(
            helper, origin, origin_lib
        ),
        _get_usage=lambda variable: usage_by_id[id(variable)],
        _procedure_status_issue=lambda *_args, **_kwargs: None,
        _add_issue=lambda kind, path, variable, role, field_path=None: issues.append(
            (kind, tuple(path), variable.name)
        ),
        _has_output_effect=lambda *args, **kwargs: False,
        _has_procedure_status_binding=lambda *args, **kwargs: False,
        _is_const_candidate=lambda *args, **kwargs: True,
        _collect_issues_from_module=lambda *args, **kwargs: None,
    )

    variables_execution_module._collect_typedef_issues(helper)

    assert issues == []


def test_unused_summary_splits_moduletype_and_singlemodule_groups():
    moduletype_var = Variable(name="EnableInteraktion", datatype=Simple_DataType.BOOLEAN)
    singlemodule_var = Variable(name="MinMax", datatype=Simple_DataType.INTEGER)
    issues = [
        VariableIssue(
            kind=IssueKind.UNUSED,
            module_path=["BasePicture", "TypeDef:InfoPanelType"],
            variable=moduletype_var,
            role="moduleparameter",
        ),
        VariableIssue(
            kind=IssueKind.UNUSED,
            module_path=["BasePicture", "TypeDef:Soejle", "L1", "L2", "RPDisp"],
            variable=singlemodule_var,
            role="localvariable",
        ),
    ]

    summary = VariablesReport(basepicture_name="BasePicture", issues=issues).summary()

    assert "      Moduletype:" in summary
    assert "BasePicture.TypeDef:InfoPanelType :: moduleparameter EnableInteraktion (boolean)" in summary
    assert "      SingleModule:" in summary
    assert "BasePicture.Soejle.L1.L2.RPDisp :: localvariable MinMax (integer)" in summary
    assert "BasePicture.TypeDef:Soejle.L1.L2.RPDisp :: localvariable MinMax (integer)" not in summary


def test_never_read_summary_splits_moduletype_and_singlemodule_groups():
    moduletype_var = Variable(name="EnableInteraktion", datatype=Simple_DataType.BOOLEAN)
    singlemodule_var = Variable(name="MinMax", datatype=Simple_DataType.INTEGER)
    issues = [
        VariableIssue(
            kind=IssueKind.NEVER_READ,
            module_path=["BasePicture", "TypeDef:InfoPanelType"],
            variable=moduletype_var,
            role="moduleparameter",
        ),
        VariableIssue(
            kind=IssueKind.NEVER_READ,
            module_path=["BasePicture", "TypeDef:Soejle", "L1", "L2", "RPDisp"],
            variable=singlemodule_var,
            role="localvariable",
        ),
    ]

    summary = VariablesReport(basepicture_name="BasePicture", issues=issues).summary()

    assert "Written but never read variables" in summary
    assert "      Moduletype:" in summary
    assert "BasePicture.TypeDef:InfoPanelType :: moduleparameter EnableInteraktion (boolean)" in summary
    assert "      SingleModule:" in summary
    assert "BasePicture.Soejle.L1.L2.RPDisp :: localvariable MinMax (integer)" in summary
    assert "BasePicture.TypeDef:Soejle.L1.L2.RPDisp :: localvariable MinMax (integer)" not in summary


def test_string_mapping_summary_dedupes_root_typedef_singlemodule_rows():
    child_typedef = ModuleTypeDef(
        name="ChildType",
        moduleparameters=[Variable(name="TargetValue", datatype=Simple_DataType.IDENTSTRING)],
        localvariables=[],
        submodules=[],
        moduledef=None,
        modulecode=None,
        parametermappings=[],
    )
    parent_typedef = ModuleTypeDef(
        name="ParentType",
        moduleparameters=[Variable(name="SourceValue", datatype=Simple_DataType.STRING)],
        localvariables=[],
        submodules=[
            ModuleTypeInstance(
                header=_hdr("Child"),
                moduletype_name="ChildType",
                parametermappings=[
                    ParameterMapping(
                        target=_varref("TargetValue"),
                        source_type=const.TREE_TAG_VARIABLE_NAME,
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
        parametermappings=[],
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

    summary = VariablesReport(basepicture_name=bp.header.name, issues=issues).summary()

    assert "Root.TypeDef:ParentType.Child" in summary
    assert "Root.Parent.Child" not in summary
    assert "SourceValue" in summary
    assert "moduleparameter" in summary
    assert "identstring" in summary


def test_string_mapping_summary_prefers_original_declaration_type_for_intermediate_path_rows():
    final_typedef = ModuleTypeDef(
        name="FinalType",
        moduleparameters=[Variable(name="FinalValue", datatype=Simple_DataType.IDENTSTRING)],
        localvariables=[],
        submodules=[],
        moduledef=None,
        modulecode=None,
        parametermappings=[],
    )
    relay_typedef = ModuleTypeDef(
        name="RelayType",
        moduleparameters=[Variable(name="RelayValue", datatype=Simple_DataType.STRING)],
        localvariables=[],
        submodules=[
            ModuleTypeInstance(
                header=_hdr("Final"),
                moduletype_name="FinalType",
                parametermappings=[
                    ParameterMapping(
                        target=_varref("FinalValue"),
                        source_type=const.TREE_TAG_VARIABLE_NAME,
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
        parametermappings=[],
    )
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[final_typedef, relay_typedef],
        localvariables=[Variable(name="OriginalValue", datatype=Simple_DataType.IDENTSTRING)],
        submodules=[
            ModuleTypeInstance(
                header=_hdr("Relay"),
                moduletype_name="RelayType",
                parametermappings=[
                    ParameterMapping(
                        target=_varref("RelayValue"),
                        source_type=const.TREE_TAG_VARIABLE_NAME,
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

    summary = VariablesReport(basepicture_name=bp.header.name, issues=issues).summary()

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
    issue = VariableIssue(
        kind=IssueKind.STRING_MAPPING_MISMATCH,
        module_path=["Root", "Parent", "Panel", "ActivateButton"],
        variable=Variable(name="Text", datatype=Simple_DataType.IDENTSTRING),
        source_variable=Variable(name="DV.StopText", datatype=Simple_DataType.IDENTSTRING),
        source_decl_module_path=["Root", "Parent"],
        source_role="localvariable",
        target_display_name="Text",
    )

    summary = VariablesReport(basepicture_name="Root", issues=[issue]).summary()

    assert "Intermediate path mismatch only (1):" in summary
    assert "Declaration/final destination mismatch (0):" in summary
    assert "DV.StopText" in summary
    assert "Text" in summary
