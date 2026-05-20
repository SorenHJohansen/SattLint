# ruff: noqa: F403, F405
from ._analyzers_variables_test_support import *


def test_library_typedef_moduleparameter_unused_fields_are_suppressed():
    record_type = DataType(
        name="RecType",
        description=None,
        datecode=None,
        var_list=[
            Variable(name="Used", datatype=Simple_DataType.INTEGER),
            Variable(name="Unused", datatype=Simple_DataType.INTEGER),
        ],
        origin_file="LibraryRoot.x",
        origin_lib="ProjectLib",
    )

    exported = ModuleTypeDef(
        name="ExportedType",
        moduleparameters=[Variable(name="p", datatype="RecType")],
        localvariables=[Variable(name="sink", datatype=Simple_DataType.INTEGER)],
        submodules=[],
        moduledef=None,
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Main",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (
                            const.KEY_ASSIGN,
                            _varref("sink"),
                            _varref("p.Used"),
                        )
                    ],
                )
            ]
        ),
        parametermappings=[],
        origin_file="LibraryRoot.x",
        origin_lib="ProjectLib",
    )

    bp = BasePicture(
        header=_hdr("BasePicture"),
        datatype_defs=[record_type],
        moduletype_defs=[exported],
        localvariables=[],
        submodules=[],
        modulecode=None,
        moduledef=None,
        origin_file="LibraryRoot.x",
        origin_lib="ProjectLib",
    )

    program_analyzer = VariablesAnalyzer(bp, analyzed_target_is_library=False)
    program_analyzer.run()
    assert any(
        issue.kind is IssueKind.UNUSED_DATATYPE_FIELD
        and issue.datatype_name == "RecType"
        and issue.field_path == "Unused"
        for issue in program_analyzer.issues
    )

    library_analyzer = VariablesAnalyzer(bp, analyzed_target_is_library=True)
    library_analyzer.run()
    assert not any(
        issue.kind is IssueKind.UNUSED_DATATYPE_FIELD
        and issue.datatype_name == "RecType"
        and issue.field_path == "Unused"
        for issue in library_analyzer.issues
    )


def test_unused_datatype_fields_are_aggregated_across_variables():
    record_type = DataType(
        name="SharedRecord",
        description=None,
        datecode=None,
        var_list=[
            Variable(name="A", datatype=Simple_DataType.INTEGER),
            Variable(name="B", datatype=Simple_DataType.INTEGER),
            Variable(name="C", datatype=Simple_DataType.INTEGER),
        ],
        origin_file="Root.x",
        origin_lib="ProjectLib",
    )

    first = Variable(name="First", datatype="SharedRecord")
    second = Variable(name="Second", datatype="SharedRecord")

    module = SingleModule(
        header=_hdr("M1"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[first, second],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Main",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (const.KEY_ASSIGN, _varref("sinkA"), _varref("First.A")),
                        (const.KEY_ASSIGN, _varref("sinkB"), _varref("Second.B")),
                    ],
                )
            ]
        ),
        parametermappings=[],
    )

    bp = BasePicture(
        header=_hdr("BasePicture"),
        datatype_defs=[record_type],
        moduletype_defs=[],
        localvariables=[
            Variable(name="sinkA", datatype=Simple_DataType.INTEGER),
            Variable(name="sinkB", datatype=Simple_DataType.INTEGER),
        ],
        submodules=[module],
        modulecode=None,
        moduledef=None,
        origin_file="Root.x",
        origin_lib="ProjectLib",
    )

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    unused_fields = {
        issue.field_path
        for issue in analyzer.issues
        if issue.kind is IssueKind.UNUSED_DATATYPE_FIELD and issue.datatype_name == "SharedRecord"
    }

    assert unused_fields == {"C"}


def test_sample_fixture_contains_common_variable_quality_issues():
    fixture = Path(__file__).parent / "fixtures" / "sample_sattline_files" / "CommonQualityIssues.s"

    bp = parse_source_file(fixture)
    issues = VariablesAnalyzer(bp).run()

    unused = {issue.variable.name for issue in issues if issue.kind is IssueKind.UNUSED and issue.variable is not None}
    read_only_non_const = {
        issue.variable.name
        for issue in issues
        if issue.kind is IssueKind.READ_ONLY_NON_CONST and issue.variable is not None
    }
    never_read = {
        issue.variable.name for issue in issues if issue.kind is IssueKind.NEVER_READ and issue.variable is not None
    }
    unused_fields = {
        (issue.datatype_name, issue.field_path) for issue in issues if issue.kind is IssueKind.UNUSED_DATATYPE_FIELD
    }

    assert "UnusedValue" in unused
    assert "ReadOnlyValue" in read_only_non_const
    assert "NeverReadValue" in never_read
    assert ("QualityRecord", "UnusedField") in unused_fields


def test_search_rec_component_found_record_output_is_not_flagged_never_read():
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[
            Variable(name="CR", datatype=Simple_DataType.INTEGER),
            Variable(name="Index", datatype=Simple_DataType.INTEGER),
            Variable(name="SearchUnit", datatype=Simple_DataType.INTEGER),
            Variable(name="FoundUnit", datatype=Simple_DataType.INTEGER),
            Variable(name="srci", datatype=Simple_DataType.INTEGER),
            Variable(name="SearchSucceeded", datatype=Simple_DataType.BOOLEAN),
            Variable(name="Mirror", datatype=Simple_DataType.INTEGER),
        ],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Search",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (
                            const.KEY_ASSIGN,
                            _varref("SearchSucceeded"),
                            (
                                const.KEY_FUNCTION_CALL,
                                "SearchRecComponent",
                                [
                                    _varref("CR"),
                                    _varref("Index"),
                                    10,
                                    _varref("SearchUnit"),
                                    _varref("SearchUnit"),
                                    _varref("FoundUnit"),
                                    _varref("srci"),
                                ],
                            ),
                        ),
                        (const.KEY_ASSIGN, _varref("Mirror"), _varref("Index")),
                    ],
                )
            ],
            sequences=[],
        ),
        moduledef=None,
    )

    issues = VariablesAnalyzer(bp).run()

    never_read = {
        issue.variable.name for issue in issues if issue.kind is IssueKind.NEVER_READ and issue.variable is not None
    }

    assert "FoundUnit" not in never_read


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

    summary = VariablesReport(basepicture_name=bp.header.name, issues=analyzer.issues).summary()

    assert "Root.ParentType.Child" in summary
    assert "Root.TypeDef:ParentType.Child" not in summary
    assert "Root.Parent.Child" not in summary


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
