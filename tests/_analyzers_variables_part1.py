# ruff: noqa: F403, F405
from sattlint.analyzers import _validators as validators_module
from sattlint.resolution.type_graph import TypeGraph

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


def test_string_mapping_mismatch_ignores_unresolved_source_name_even_when_same_name_exists_elsewhere():
    unrelated = SingleModule(
        header=_hdr("Unrelated"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[Variable(name="Name", datatype=Simple_DataType.STRING)],
        submodules=[],
        modulecode=None,
        parametermappings=[],
    )

    child = SingleModule(
        header=_hdr("Child"),
        moduledef=None,
        moduleparameters=[Variable(name="Name", datatype=Simple_DataType.IDENTSTRING)],
        localvariables=[],
        submodules=[],
        modulecode=None,
        parametermappings=[
            ParameterMapping(
                target=_varref("Name"),
                source_type=const.TREE_TAG_VARIABLE_NAME,
                is_duration=False,
                is_source_global=False,
                source=_varref("Name"),
                source_literal=None,
            )
        ],
    )

    parent = SingleModule(
        header=_hdr("Parent"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[],
        submodules=[unrelated, child],
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


def test_display_only_graphics_mapping_keeps_parent_parameter_ui_only():
    child = SingleModule(
        header=_hdr("Child"),
        moduledef=ModuleDef(
            graph_objects=[
                GraphObject(
                    type=const.GRAMMAR_VALUE_RECTANGLEOBJECT,
                    properties={const.KEY_TAILS: ["WindowBgColour"]},
                )
            ]
        ),
        moduleparameters=[Variable(name="WindowBgColour", datatype=Simple_DataType.INTEGER)],
        localvariables=[],
        submodules=[],
        modulecode=None,
        parametermappings=[
            ParameterMapping(
                target=_varref("WindowBgColour"),
                source_type=const.TREE_TAG_VARIABLE_NAME,
                is_duration=False,
                is_source_global=False,
                source=_varref("WindowBgColour"),
                source_literal=None,
            )
        ],
    )

    parent = SingleModule(
        header=_hdr("Parent"),
        moduledef=None,
        moduleparameters=[Variable(name="WindowBgColour", datatype=Simple_DataType.INTEGER)],
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

    ui_only = {
        (tuple(issue.module_path), issue.variable.name)
        for issue in analyzer.issues
        if issue.kind is IssueKind.UI_ONLY and issue.variable is not None
    }

    assert (("Root", "Parent"), "WindowBgColour") in ui_only
    assert (("Root", "Parent", "Child"), "WindowBgColour") in ui_only
    assert not any(
        issue.kind is IssueKind.REQUIRED_PARAMETER_CONNECTION
        and issue.variable is not None
        and issue.variable.name == "WindowBgColour"
        for issue in analyzer.issues
    )


def test_validator_helper_branches_cover_string_and_minmax_helpers():
    string_validator = validators_module.StringMappingValidator()
    minmax_validator = validators_module.MinMaxValidator()

    assert string_validator._is_string_simple_type(Simple_DataType.STRING) is True
    assert string_validator._is_string_simple_type("String") is False
    assert string_validator._string_limit("String") is None
    assert (
        string_validator.check_string_mapping(
            Variable(name="Target", datatype=Simple_DataType.INTEGER),
            Variable(name="Source", datatype=Simple_DataType.STRING),
            ["Root"],
        )
        == []
    )

    assert minmax_validator._mapping_name_text({const.KEY_VAR_NAME: 5}) is None
    assert (
        minmax_validator._mapping_name_text(Variable(name="MinLimit", datatype=Simple_DataType.INTEGER)) == "MinLimit"
    )
    assert minmax_validator._mapping_name_text("MaxLimit") == "MaxLimit"
    assert minmax_validator._mapping_name_text(5) is None
    assert minmax_validator._tokenize_name("MaxPressure2Limit") == {"max", "pressure", "2", "limit"}
    assert minmax_validator._tokenize_name(".Min") == {"min"}
    assert minmax_validator._minmax_flags("MinMaxWindow") == (True, True, True)

    ambiguous_mapping = ParameterMapping(
        target=_varref("MinMaxWindow"),
        source_type=const.TREE_TAG_VARIABLE_NAME,
        is_duration=False,
        is_source_global=False,
        source=_varref("MinSource"),
        source_literal=None,
    )
    assert (
        minmax_validator.check_min_max_mapping(
            ambiguous_mapping,
            Variable(name="MinMaxWindow", datatype=Simple_DataType.INTEGER),
            Variable(name="MinSource", datatype=Simple_DataType.INTEGER),
            ["Root"],
        )
        == []
    )

    blank_mapping = ParameterMapping(
        target={const.KEY_VAR_NAME: ""},
        source_type=const.TREE_TAG_VARIABLE_NAME,
        is_duration=False,
        is_source_global=False,
        source={const.KEY_VAR_NAME: ""},
        source_literal=None,
    )
    assert (
        minmax_validator.check_min_max_mapping(
            blank_mapping,
            Variable(name="", datatype=Simple_DataType.INTEGER),
            Variable(name="", datatype=Simple_DataType.INTEGER),
            ["Root"],
        )
        == []
    )


def test_contract_mapping_validator_helper_branches(monkeypatch):
    validator = validators_module.ContractMappingValidator(
        TypeGraph({}),
        anytype_field_contracts={
            1: {"AnyParam": validators_module.AnyTypeFieldContract(field_paths=("missing.field",))},
            2: {"AnyParam": validators_module.AnyTypeFieldContract(field_paths=())},
        },
    )
    source_var = Variable(name="Source", datatype=Simple_DataType.INTEGER)
    target_var = Variable(name="AnyParam", datatype="AnyType")
    mapping = ParameterMapping(
        target=_varref("AnyParam"),
        source_type=const.TREE_TAG_VARIABLE_NAME,
        is_duration=False,
        is_source_global=False,
        source=_varref("Source"),
        source_literal=None,
    )

    assert validator._datatype_key(None) is None
    assert validator._datatype_key(Simple_DataType.INTEGER) == "integer"
    assert validator._datatype_key("CustomType") == "customtype"
    assert validator._format_datatype(None) == "unknown"
    assert validator._format_datatype(Simple_DataType.INTEGER) == "integer"
    assert validator._format_datatype("CustomType") == "CustomType"
    assert (
        validator._resolve_source_required_field_datatype(
            ParameterMapping(
                target=_varref("AnyParam"),
                source_type=const.TREE_TAG_VARIABLE_NAME,
                is_duration=False,
                is_source_global=False,
                source=None,
                source_literal=None,
            ),
            source_var,
            "field",
        )
        is None
    )
    assert validator._resolve_source_required_field_datatype(mapping, source_var, "") == Simple_DataType.INTEGER

    monkeypatch.setattr(
        validators_module,
        "_resolve_variable_field_datatype",
        lambda _var, field_path, _graph: Simple_DataType.BOOLEAN if tuple(field_path) == ("child",) else None,
    )
    assert validator._resolve_source_required_field_datatype(mapping, source_var, "child") == Simple_DataType.BOOLEAN
    assert (
        validator._check_anytype_field_contracts(mapping, target_var, source_var, ["Root"], owner_contract_id=None)
        == []
    )
    assert validator._check_anytype_field_contracts(mapping, target_var, None, ["Root"], owner_contract_id=1) == []
    assert (
        validator._check_anytype_field_contracts(
            ParameterMapping(
                target=_varref("AnyParam"),
                source_type=const.KEY_VALUE,
                is_duration=False,
                is_source_global=False,
                source=None,
                source_literal=1,
            ),
            target_var,
            source_var,
            ["Root"],
            owner_contract_id=1,
        )
        == []
    )
    assert (
        validator._check_anytype_field_contracts(mapping, target_var, source_var, ["Root"], owner_contract_id=999) == []
    )
    assert (
        validator._check_anytype_field_contracts(mapping, target_var, source_var, ["Root"], owner_contract_id=2) == []
    )
    validator._anytype_field_contracts[3] = {"anyparam": validators_module.AnyTypeFieldContract(field_paths=("child",))}
    assert (
        validator._check_anytype_field_contracts(mapping, target_var, source_var, ["Root"], owner_contract_id=3) == []
    )

    issues = validator._check_anytype_field_contracts(mapping, target_var, source_var, ["Root"], owner_contract_id=1)
    assert len(issues) == 1
    assert issues[0].field_path == "missing.field"
    assert "missing required field 'missing.field'" in (issues[0].role or "")

    assert validator._resolve_target_datatype("AnyParam", target_var) == ("AnyType", None)
    assert validator._resolve_target_datatype("AnyParam.child", target_var) == (Simple_DataType.BOOLEAN, "child")
    assert validator._resolve_source_datatype(
        ParameterMapping(
            target=_varref("AnyParam"),
            source_type=const.KEY_VALUE,
            is_duration=False,
            is_source_global=False,
            source=None,
            source_literal=1,
        ),
        None,
    ) == (Simple_DataType.INTEGER, "1")
    assert validator._resolve_source_datatype(mapping, None) == (None, "Source")
    assert validator._resolve_source_datatype(mapping, source_var) == (Simple_DataType.INTEGER, "Source")
    assert validator._resolve_source_datatype(
        ParameterMapping(
            target=_varref("AnyParam"),
            source_type=const.TREE_TAG_VARIABLE_NAME,
            is_duration=False,
            is_source_global=False,
            source=_varref("Source.child"),
            source_literal=None,
        ),
        source_var,
    ) == (Simple_DataType.BOOLEAN, "Source.child")


def test_contract_mapping_validator_check_contract_mapping_branches(monkeypatch):
    validator = validators_module.ContractMappingValidator(TypeGraph({}))
    target_var = Variable(name="Target", datatype=Simple_DataType.INTEGER)
    source_var = Variable(name="Source", datatype=Simple_DataType.STRING)
    mapping = ParameterMapping(
        target=_varref("Target"),
        source_type=const.TREE_TAG_VARIABLE_NAME,
        is_duration=False,
        is_source_global=False,
        source=_varref("Source"),
        source_literal=None,
    )
    anytype_issue = VariableIssue(kind=IssueKind.CONTRACT_MISMATCH, module_path=["Root"], variable=target_var)

    monkeypatch.setattr(validator, "_resolve_target_datatype", lambda *_args: (None, None))
    assert validator.check_contract_mapping(mapping, target_var, source_var, ["Root"]) == []

    monkeypatch.setattr(validator, "_resolve_target_datatype", lambda *_args: (Simple_DataType.INTEGER, None))
    monkeypatch.setattr(validator, "_resolve_source_datatype", lambda *_args: (None, "Source"))
    assert validator.check_contract_mapping(mapping, target_var, source_var, ["Root"]) == []

    monkeypatch.setattr(validator, "_resolve_source_datatype", lambda *_args: (Simple_DataType.INTEGER, "Source"))
    assert validator.check_contract_mapping(mapping, target_var, source_var, ["Root"]) == []

    monkeypatch.setattr(validator, "_resolve_target_datatype", lambda *_args: ("AnyType", None))
    monkeypatch.setattr(validator, "_resolve_source_datatype", lambda *_args: (Simple_DataType.INTEGER, "Source"))
    monkeypatch.setattr(validator, "_check_anytype_field_contracts", lambda *_args, **_kwargs: [anytype_issue])
    assert validator.check_contract_mapping(mapping, target_var, source_var, ["Root"], owner_contract_id=1) == [
        anytype_issue
    ]

    literal_mapping = ParameterMapping(
        target=_varref("Target"),
        source_type=const.KEY_VALUE,
        is_duration=False,
        is_source_global=False,
        source=None,
        source_literal=1,
    )
    monkeypatch.setattr(validator, "_resolve_target_datatype", lambda *_args: (Simple_DataType.INTEGER, None))
    monkeypatch.setattr(validator, "_resolve_source_datatype", lambda *_args: ("CustomLiteral", "1"))
    monkeypatch.setattr(validators_module, "_literal_matches_expected_datatype", lambda *_args, **_kwargs: True)
    assert validator.check_contract_mapping(literal_mapping, target_var, None, ["Root"]) == []

    monkeypatch.setattr(validator, "_resolve_source_datatype", lambda *_args: (Simple_DataType.STRING, "Source"))
    monkeypatch.setattr(validator, "_resolve_target_datatype", lambda *_args: (Simple_DataType.IDENTSTRING, None))
    monkeypatch.setattr(validators_module, "_literal_matches_expected_datatype", lambda *_args, **_kwargs: False)
    assert validator.check_contract_mapping(mapping, target_var, source_var, ["Root"]) == []

    time_mapping = ParameterMapping(
        target=_varref("Target"),
        source_type=const.KEY_VALUE,
        is_duration=False,
        is_source_global=False,
        source=None,
        source_literal="1:00",
    )
    monkeypatch.setattr(validator, "_resolve_target_datatype", lambda *_args: ("CustomTimeTarget", None))
    monkeypatch.setattr(validator, "_resolve_source_datatype", lambda *_args: (const.GRAMMAR_VALUE_TIME_VALUE, "1:00"))
    monkeypatch.setattr(validators_module, "_assignment_type_matches", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(validators_module, "_has_time_literal_marker", lambda *_args, **_kwargs: False)
    assert validator.check_contract_mapping(time_mapping, target_var, None, ["Root"]) == []

    monkeypatch.setattr(validator, "_resolve_target_datatype", lambda *_args: (Simple_DataType.INTEGER, "field"))
    monkeypatch.setattr(validator, "_resolve_source_datatype", lambda *_args: (Simple_DataType.STRING, "Source"))
    issue_list = validator.check_contract_mapping(mapping, target_var, source_var, ["Root"])
    assert len(issue_list) == 1
    assert issue_list[0].field_path == "field"
    assert "Source (string) => Target (integer)" in (issue_list[0].role or "")
