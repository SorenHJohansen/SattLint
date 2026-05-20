# ruff: noqa: F403, F405
from ._analyzers_variables_test_support import *


def test_min_max_mapping_mismatch_detected():
    child = SingleModule(
        header=_hdr("Child"),
        moduledef=None,
        moduleparameters=[Variable(name="MaxValue", datatype=Simple_DataType.INTEGER)],
        localvariables=[],
        submodules=[],
        modulecode=None,
        parametermappings=[
            ParameterMapping(
                target=_varref("MaxValue"),
                source_type=const.TREE_TAG_VARIABLE_NAME,
                is_duration=False,
                is_source_global=False,
                source=_varref("MinValue"),
                source_literal=None,
            )
        ],
    )

    parent = SingleModule(
        header=_hdr("Parent"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[
            Variable(name="MinValue", datatype=Simple_DataType.INTEGER),
            Variable(name="MaxValue", datatype=Simple_DataType.INTEGER),
        ],
        submodules=[child],
        modulecode=None,
        parametermappings=[],
    )

    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[],
        submodules=[parent],
        modulecode=None,
        moduledef=None,
    )

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    assert any(i.kind is IssueKind.MIN_MAX_MAPPING_MISMATCH for i in analyzer.issues)


def test_min_max_mapping_mismatch_not_raised_for_aligned_names():
    child = SingleModule(
        header=_hdr("Child"),
        moduledef=None,
        moduleparameters=[Variable(name="MinValue", datatype=Simple_DataType.INTEGER)],
        localvariables=[],
        submodules=[],
        modulecode=None,
        parametermappings=[
            ParameterMapping(
                target=_varref("MinValue"),
                source_type=const.TREE_TAG_VARIABLE_NAME,
                is_duration=False,
                is_source_global=False,
                source=_varref("MinValue"),
                source_literal=None,
            )
        ],
    )

    parent = SingleModule(
        header=_hdr("Parent"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[Variable(name="MinValue", datatype=Simple_DataType.INTEGER)],
        submodules=[child],
        modulecode=None,
        parametermappings=[],
    )

    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[],
        submodules=[parent],
        modulecode=None,
        moduledef=None,
    )

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    assert not any(i.kind is IssueKind.MIN_MAX_MAPPING_MISMATCH for i in analyzer.issues)


def test_string_mapping_mismatch_is_reported_when_assigning_large_string_to_small_string():
    child = SingleModule(
        header=_hdr("Child"),
        moduledef=None,
        moduleparameters=[Variable(name="TargetValue", datatype=Simple_DataType.IDENTSTRING)],
        localvariables=[],
        submodules=[],
        modulecode=None,
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

    parent = SingleModule(
        header=_hdr("Parent"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[Variable(name="SourceValue", datatype=Simple_DataType.STRING)],
        submodules=[child],
        modulecode=None,
        parametermappings=[],
    )

    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[],
        submodules=[parent],
        modulecode=None,
        moduledef=None,
    )

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    issues = [issue for issue in analyzer.issues if issue.kind is IssueKind.STRING_MAPPING_MISMATCH]
    assert len(issues) == 1
    assert issues[0].module_path == ["Root", "Parent", "Child"]
    assert issues[0].variable is not None
    assert issues[0].variable.name == "TargetValue"
    assert issues[0].source_variable is not None
    assert issues[0].source_variable.name == "SourceValue"


def test_string_mapping_mismatch_is_not_reported_when_assigning_small_string_to_large_string():
    child = SingleModule(
        header=_hdr("Child"),
        moduledef=None,
        moduleparameters=[Variable(name="TargetValue", datatype=Simple_DataType.STRING)],
        localvariables=[],
        submodules=[],
        modulecode=None,
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

    parent = SingleModule(
        header=_hdr("Parent"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[Variable(name="SourceValue", datatype=Simple_DataType.IDENTSTRING)],
        submodules=[child],
        modulecode=None,
        parametermappings=[],
    )

    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[],
        submodules=[parent],
        modulecode=None,
        moduledef=None,
    )

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    assert not any(issue.kind is IssueKind.STRING_MAPPING_MISMATCH for issue in analyzer.issues)


def test_unknown_parameter_target_detected_for_single_module_mapping():
    child = SingleModule(
        header=_hdr("Child"),
        moduledef=None,
        moduleparameters=[Variable(name="DeclaredValue", datatype=Simple_DataType.INTEGER)],
        localvariables=[],
        submodules=[],
        modulecode=None,
        parametermappings=[
            ParameterMapping(
                target=_varref("MissingValue"),
                source_type=const.TREE_TAG_VARIABLE_NAME,
                is_duration=False,
                is_source_global=False,
                source=_varref("SourceValue"),
                source_literal=None,
            )
        ],
    )

    parent = SingleModule(
        header=_hdr("Parent"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[Variable(name="SourceValue", datatype=Simple_DataType.INTEGER)],
        submodules=[child],
        modulecode=None,
        parametermappings=[],
    )

    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[],
        submodules=[parent],
        modulecode=None,
        moduledef=None,
    )

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    issues = [issue for issue in analyzer.issues if issue.kind is IssueKind.UNKNOWN_PARAMETER_TARGET]
    assert len(issues) == 1
    assert issues[0].module_path == ["Root", "Parent", "Child"]
    assert issues[0].role == "unknown parameter mapping target 'MissingValue'"


def test_contract_mismatch_detected_for_moduletype_parameter_mapping():
    typedef = ModuleTypeDef(
        name="ChildType",
        moduleparameters=[Variable(name="ExpectedValue", datatype=Simple_DataType.INTEGER)],
        localvariables=[],
        submodules=[],
        moduledef=None,
        modulecode=None,
        parametermappings=[],
    )

    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[typedef],
        localvariables=[Variable(name="SourceFlag", datatype=Simple_DataType.BOOLEAN)],
        submodules=[
            ModuleTypeInstance(
                header=_hdr("Child"),
                moduletype_name="ChildType",
                parametermappings=[
                    ParameterMapping(
                        target=_varref("ExpectedValue"),
                        source_type=const.TREE_TAG_VARIABLE_NAME,
                        is_duration=False,
                        is_source_global=False,
                        source=_varref("SourceFlag"),
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

    issues = [issue for issue in analyzer.issues if issue.kind is IssueKind.CONTRACT_MISMATCH]
    assert len(issues) == 1
    assert issues[0].module_path == ["Root", "Child"]
    assert issues[0].variable is not None
    assert issues[0].variable.name == "ExpectedValue"
    assert issues[0].source_variable is not None
    assert issues[0].source_variable.name == "SourceFlag"
    assert "boolean" in (issues[0].role or "")
    assert "integer" in (issues[0].role or "")


def test_contract_mismatch_ignores_anytype_targets():
    typedef = ModuleTypeDef(
        name="ChildType",
        moduleparameters=[Variable(name="ExpectedValue", datatype="AnyType")],
        localvariables=[],
        submodules=[],
        moduledef=None,
        modulecode=None,
        parametermappings=[],
    )

    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[typedef],
        localvariables=[Variable(name="SourceFlag", datatype=Simple_DataType.BOOLEAN)],
        submodules=[
            ModuleTypeInstance(
                header=_hdr("Child"),
                moduletype_name="ChildType",
                parametermappings=[
                    ParameterMapping(
                        target=_varref("ExpectedValue"),
                        source_type=const.TREE_TAG_VARIABLE_NAME,
                        is_duration=False,
                        is_source_global=False,
                        source=_varref("SourceFlag"),
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

    assert not any(issue.kind is IssueKind.CONTRACT_MISMATCH for issue in analyzer.issues)


def test_unknown_parameter_target_detected_for_moduletype_instance_mapping():
    typedef = ModuleTypeDef(
        name="ChildType",
        moduleparameters=[Variable(name="DeclaredValue", datatype=Simple_DataType.INTEGER)],
        localvariables=[],
        submodules=[],
        moduledef=None,
        modulecode=None,
        parametermappings=[],
    )
    instance = ModuleTypeInstance(
        header=_hdr("Child"),
        moduletype_name="ChildType",
        parametermappings=[
            ParameterMapping(
                target=_varref("MissingValue"),
                source_type=const.TREE_TAG_VARIABLE_NAME,
                is_duration=False,
                is_source_global=False,
                source=_varref("SourceValue"),
                source_literal=None,
            )
        ],
    )
    parent = SingleModule(
        header=_hdr("Parent"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[Variable(name="SourceValue", datatype=Simple_DataType.INTEGER)],
        submodules=[instance],
        modulecode=None,
        parametermappings=[],
    )
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[typedef],
        localvariables=[],
        submodules=[parent],
        modulecode=None,
        moduledef=None,
    )

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    issues = [issue for issue in analyzer.issues if issue.kind is IssueKind.UNKNOWN_PARAMETER_TARGET]
    assert len(issues) == 1
    assert issues[0].module_path == ["Root", "Parent", "Child"]
    assert issues[0].role == "unknown parameter mapping target 'MissingValue'"


def test_required_parameter_connection_flags_unmapped_used_moduletype_parameter():
    typedef = ModuleTypeDef(
        name="ChildType",
        moduleparameters=[Variable(name="RequiredValue", datatype=Simple_DataType.INTEGER)],
        localvariables=[Variable(name="Mirror", datatype=Simple_DataType.INTEGER)],
        submodules=[],
        moduledef=None,
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="UseParam",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (
                            const.KEY_ASSIGN,
                            _varref("Mirror"),
                            _varref("RequiredValue"),
                        )
                    ],
                )
            ]
        ),
        parametermappings=[],
    )
    parent = SingleModule(
        header=_hdr("Parent"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[],
        submodules=[
            ModuleTypeInstance(
                header=_hdr("Child"),
                moduletype_name="ChildType",
                parametermappings=[],
            )
        ],
        modulecode=None,
        parametermappings=[],
    )
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[typedef],
        localvariables=[],
        submodules=[parent],
        modulecode=None,
        moduledef=None,
    )

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    issues = [issue for issue in analyzer.issues if issue.kind is IssueKind.REQUIRED_PARAMETER_CONNECTION]
    assert len(issues) == 1
    assert issues[0].module_path == ["Root", "Parent", "Child"]
    assert issues[0].variable is not None
    assert issues[0].variable.name == "RequiredValue"
    assert issues[0].role == "required parameter connection missing for 'RequiredValue'"


def test_required_parameter_connection_flags_unmapped_used_single_module_parameter():
    child = SingleModule(
        header=_hdr("Child"),
        moduledef=None,
        moduleparameters=[Variable(name="RequiredValue", datatype=Simple_DataType.INTEGER)],
        localvariables=[Variable(name="Mirror", datatype=Simple_DataType.INTEGER)],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="UseParam",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (
                            const.KEY_ASSIGN,
                            _varref("Mirror"),
                            _varref("RequiredValue"),
                        )
                    ],
                )
            ]
        ),
        parametermappings=[],
    )
    parent = SingleModule(
        header=_hdr("Parent"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[],
        submodules=[child],
        modulecode=None,
        parametermappings=[],
    )
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[],
        submodules=[parent],
        modulecode=None,
        moduledef=None,
    )

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    issues = [issue for issue in analyzer.issues if issue.kind is IssueKind.REQUIRED_PARAMETER_CONNECTION]
    assert len(issues) == 1
    assert issues[0].module_path == ["Root", "Parent", "Child"]
    assert issues[0].variable is not None
    assert issues[0].variable.name == "RequiredValue"
    assert issues[0].role == "required parameter connection missing for 'RequiredValue'"
