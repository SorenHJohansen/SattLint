# pyright: reportPrivateUsage=false
import pytest
from sattline_parser.ast import MappingSource
from sattline_parser.models.ast_model import (
    BasePicture,
    DataType,
    ModuleTypeDef,
    ModuleTypeInstance,
    ParameterMapping,
    ScalarDatatype,
    SingleModule,
    Variable,
)

from sattlint.analyzers.shared import _validators as validators_module
from sattlint.analyzers.variables import (
    IssueKind,
    VariablesAnalyzer,
)
from sattlint.reporting.variables_report import UnusedIssue
from sattlint.resolution.type_graph import TypeGraph
from tests.helpers.variable_test_support import (
    hdr as _hdr,
)
from tests.helpers.variable_test_support import (
    varref as _varref,
)


def test_min_max_mapping_mismatch_detected():
    child = SingleModule(
        header=_hdr("Child"),
        moduledef=None,
        moduleparameters=[Variable(name="MaxValue", datatype=ScalarDatatype.INTEGER)],
        localvariables=[],
        submodules=[],
        modulecode=None,
        parametermappings=[
            ParameterMapping(
                target=_varref("MaxValue"),
                source_type=MappingSource.VARIABLE,
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
            Variable(name="MinValue", datatype=ScalarDatatype.INTEGER),
            Variable(name="MaxValue", datatype=ScalarDatatype.INTEGER),
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
        moduleparameters=[Variable(name="MinValue", datatype=ScalarDatatype.INTEGER)],
        localvariables=[],
        submodules=[],
        modulecode=None,
        parametermappings=[
            ParameterMapping(
                target=_varref("MinValue"),
                source_type=MappingSource.VARIABLE,
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
        localvariables=[Variable(name="MinValue", datatype=ScalarDatatype.INTEGER)],
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


def test_min_max_mapping_validator_recognizes_mn_mx_bound_suffixes():
    validator = validators_module.MinMaxValidator()

    assert validator._minmax_flags("Eng.InitMM.Tryk_Afl_Min_Mn") == (True, False, False)
    assert validator._minmax_flags("Eng.InitMM.Tryk_Afl_Min_Mx") == (False, True, False)
    assert validator._minmax_flags("Eng.InitMM.Tryk_Afl_Min_Mn.Value") == (True, False, False)
    assert validator._minmax_flags("Eng.InitMM.Tryk_Afl_Min_Mx.Value") == (False, True, False)


def test_string_mapping_mismatch_is_reported_when_assigning_large_string_to_small_string():
    child = SingleModule(
        header=_hdr("Child"),
        moduledef=None,
        moduleparameters=[Variable(name="TargetValue", datatype=ScalarDatatype.IDENTSTRING)],
        localvariables=[],
        submodules=[],
        modulecode=None,
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

    parent = SingleModule(
        header=_hdr("Parent"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[Variable(name="SourceValue", datatype=ScalarDatatype.STRING)],
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
    assert issues[0].source_decl_module_path == ["Root", "Parent"]
    assert issues[0].source_role == "localvariable"


def test_string_mapping_mismatch_is_not_reported_when_assigning_small_string_to_large_string():
    child = SingleModule(
        header=_hdr("Child"),
        moduledef=None,
        moduleparameters=[Variable(name="TargetValue", datatype=ScalarDatatype.STRING)],
        localvariables=[],
        submodules=[],
        modulecode=None,
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

    parent = SingleModule(
        header=_hdr("Parent"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[Variable(name="SourceValue", datatype=ScalarDatatype.IDENTSTRING)],
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
        localvariables=[Variable(name="Name", datatype=ScalarDatatype.STRING)],
        submodules=[],
        modulecode=None,
        parametermappings=[],
    )

    child = SingleModule(
        header=_hdr("Child"),
        moduledef=None,
        moduleparameters=[Variable(name="Name", datatype=ScalarDatatype.IDENTSTRING)],
        localvariables=[],
        submodules=[],
        modulecode=None,
        parametermappings=[
            ParameterMapping(
                target=_varref("Name"),
                source_type=MappingSource.VARIABLE,
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


def test_string_mapping_mismatch_is_reported_for_string_literal_to_narrower_parameter():
    child = SingleModule(
        header=_hdr("Child"),
        moduledef=None,
        moduleparameters=[Variable(name="TargetValue", datatype=ScalarDatatype.IDENTSTRING)],
        localvariables=[],
        submodules=[],
        modulecode=None,
        parametermappings=[
            ParameterMapping(
                target=_varref("TargetValue"),
                source_type=MappingSource.VALUE,
                is_duration=False,
                is_source_global=False,
                source=None,
                source_literal="LiteralTextTooLong",
            )
        ],
    )

    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[],
        submodules=[child],
        modulecode=None,
        moduledef=None,
    )

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    issues = [issue for issue in analyzer.issues if issue.kind is IssueKind.STRING_MAPPING_MISMATCH]

    assert len(issues) == 1
    assert issues[0].module_path == ["Root", "Child"]
    assert issues[0].source_variable is not None
    assert issues[0].source_variable.name == "'LiteralTextTooLong'"
    assert issues[0].source_variable.datatype_text == "string"
    assert issues[0].source_decl_module_path == ["Root", "Child"]
    assert issues[0].source_role == "literal"


def test_string_mapping_mismatch_is_not_reported_for_short_string_literal_that_fits_parameter():
    child = SingleModule(
        header=_hdr("Child"),
        moduledef=None,
        moduleparameters=[Variable(name="TargetValue", datatype=ScalarDatatype.IDENTSTRING)],
        localvariables=[],
        submodules=[],
        modulecode=None,
        parametermappings=[
            ParameterMapping(
                target=_varref("TargetValue"),
                source_type=MappingSource.VALUE,
                is_duration=False,
                is_source_global=False,
                source=None,
                source_literal="sek",
            )
        ],
    )

    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[],
        submodules=[child],
        modulecode=None,
        moduledef=None,
    )

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    assert not any(issue.kind is IssueKind.STRING_MAPPING_MISMATCH for issue in analyzer.issues)


def test_string_mapping_mismatch_uses_resolved_datatype_field_metadata():
    opsam_type = DataType(
        name="OpsamDvType",
        description=None,
        datecode=None,
        var_list=[Variable(name="StopText", datatype=ScalarDatatype.IDENTSTRING)],
    )

    activate_button = SingleModule(
        header=_hdr("ActivateButton"),
        moduledef=None,
        moduleparameters=[Variable(name="Text", datatype=ScalarDatatype.IDENTSTRING)],
        localvariables=[],
        submodules=[],
        modulecode=None,
        parametermappings=[
            ParameterMapping(
                target=_varref("Text"),
                source_type=MappingSource.VARIABLE,
                is_duration=False,
                is_source_global=False,
                source=_varref("Name"),
                source_literal=None,
            )
        ],
    )

    panel = SingleModule(
        header=_hdr("Panel"),
        moduledef=None,
        moduleparameters=[Variable(name="Name", datatype=ScalarDatatype.STRING)],
        localvariables=[],
        submodules=[activate_button],
        modulecode=None,
        parametermappings=[
            ParameterMapping(
                target=_varref("Name"),
                source_type=MappingSource.VARIABLE,
                is_duration=False,
                is_source_global=False,
                source=_varref("DV.StopText"),
                source_literal=None,
            )
        ],
    )

    parent = SingleModule(
        header=_hdr("Parent"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[Variable(name="DV", datatype="OpsamDvType")],
        submodules=[panel],
        modulecode=None,
        parametermappings=[],
    )

    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[opsam_type],
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
    assert issues[0].source_variable is not None
    assert issues[0].source_variable.name == "DV.StopText"
    assert issues[0].source_variable.datatype_text == "identstring"
    assert issues[0].source_decl_module_path == ["Root", "Parent"]
    assert issues[0].source_role == "localvariable"
    assert issues[0].target_display_name == "Text"


def test_string_mapping_mismatch_ignores_direct_record_field_mapping_when_field_fits_target():
    opsam_type = DataType(
        name="OpsamDvType",
        description=None,
        datecode=None,
        var_list=[Variable(name="StopText", datatype=ScalarDatatype.IDENTSTRING)],
    )

    child = SingleModule(
        header=_hdr("Child"),
        moduledef=None,
        moduleparameters=[Variable(name="Text", datatype=ScalarDatatype.IDENTSTRING)],
        localvariables=[],
        submodules=[],
        modulecode=None,
        parametermappings=[
            ParameterMapping(
                target=_varref("Text"),
                source_type=MappingSource.VARIABLE,
                is_duration=False,
                is_source_global=False,
                source=_varref("DV.StopText"),
                source_literal=None,
            )
        ],
    )

    parent = SingleModule(
        header=_hdr("Parent"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[Variable(name="DV", datatype="OpsamDvType")],
        submodules=[child],
        modulecode=None,
        parametermappings=[],
    )

    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[opsam_type],
        moduletype_defs=[],
        localvariables=[],
        submodules=[parent],
        modulecode=None,
        moduledef=None,
    )

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    assert not any(issue.kind is IssueKind.STRING_MAPPING_MISMATCH for issue in analyzer.issues)


@pytest.mark.parametrize("is_source_global", [False, True])
def test_extra_mapping_target_is_accepted_for_single_module(is_source_global: bool) -> None:
    child = SingleModule(
        header=_hdr("Child"),
        moduledef=None,
        moduleparameters=[Variable(name="DeclaredValue", datatype=ScalarDatatype.INTEGER)],
        localvariables=[],
        submodules=[],
        modulecode=None,
        parametermappings=[
            ParameterMapping(
                target=_varref("MissingValue"),
                source_type=MappingSource.VARIABLE,
                is_duration=False,
                is_source_global=is_source_global,
                source=_varref("SourceValue"),
                source_literal=None,
            )
        ],
    )

    parent = SingleModule(
        header=_hdr("Parent"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[Variable(name="SourceValue", datatype=ScalarDatatype.INTEGER)],
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
    assert issues == []


@pytest.mark.parametrize("is_source_global", [False, True])
def test_extra_mapping_target_is_accepted_for_moduletype_instance(is_source_global: bool) -> None:
    typedef = ModuleTypeDef(
        name="ChildType",
        moduleparameters=[Variable(name="DeclaredValue", datatype=ScalarDatatype.INTEGER)],
        localvariables=[],
        submodules=[],
        moduledef=None,
        modulecode=None,
    )
    instance = ModuleTypeInstance(
        header=_hdr("Child"),
        moduletype_name="ChildType",
        parametermappings=[
            ParameterMapping(
                target=_varref("MissingValue"),
                source_type=MappingSource.VARIABLE,
                is_duration=False,
                is_source_global=is_source_global,
                source=_varref("SourceValue"),
                source_literal=None,
            )
        ],
    )
    parent = SingleModule(
        header=_hdr("Parent"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[Variable(name="SourceValue", datatype=ScalarDatatype.INTEGER)],
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
    assert issues == []


def test_singlemodule_groupconn_marks_child_parameter_used():
    child_header = _hdr("Child")
    child_header.groupconn = _varref("ScanGroup")

    child = SingleModule(
        header=child_header,
        moduledef=None,
        moduleparameters=[Variable(name="ScanGroup", datatype="GroupData")],
        localvariables=[],
        submodules=[],
        modulecode=None,
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

    assert not any(
        issue.kind is IssueKind.UNUSED
        and issue.variable is not None
        and issue.variable.name == "ScanGroup"
        and issue.module_path == ["Root", "Parent", "Child"]
        for issue in analyzer.issues
    )


def test_singlemodule_groupconn_with_mapping_marks_child_and_parent_used():
    child_header = _hdr("Child")
    child_header.groupconn = _varref("ScanGroup")

    child = SingleModule(
        header=child_header,
        moduledef=None,
        moduleparameters=[Variable(name="ScanGroup", datatype="GroupData")],
        localvariables=[],
        submodules=[],
        modulecode=None,
        parametermappings=[
            ParameterMapping(
                target=_varref("ScanGroup"),
                source_type=MappingSource.VARIABLE,
                is_duration=False,
                is_source_global=False,
                source=_varref("ParentGroup"),
                source_literal=None,
            )
        ],
    )

    parent = SingleModule(
        header=_hdr("Parent"),
        moduledef=None,
        moduleparameters=[Variable(name="ParentGroup", datatype="GroupData")],
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

    unused = {
        (tuple(issue.module_path), issue.variable.name) for issue in analyzer.issues if isinstance(issue, UnusedIssue)
    }

    assert (("Root", "Parent"), "ParentGroup") not in unused
    assert (("Root", "Parent", "Child"), "ScanGroup") not in unused


def test_validator_helper_branches_cover_string_and_minmax_helpers():
    string_validator = validators_module.StringMappingValidator()
    minmax_validator = validators_module.MinMaxValidator()

    assert string_validator._is_string_simple_type(ScalarDatatype.STRING) is True
    assert string_validator._is_string_simple_type("String") is False
    assert string_validator._string_limit("String") is None
    assert (
        string_validator.check_string_mapping(
            Variable(name="Target", datatype=ScalarDatatype.INTEGER),
            Variable(name="Source", datatype=ScalarDatatype.STRING),
            ["Root"],
        )
        == []
    )

    assert minmax_validator._mapping_name_text({}) is None
    assert minmax_validator._mapping_name_text(Variable(name="MinLimit", datatype=ScalarDatatype.INTEGER)) == "MinLimit"
    assert minmax_validator._mapping_name_text("MaxLimit") == "MaxLimit"
    assert minmax_validator._mapping_name_text(5) is None
    assert minmax_validator._tokenize_name("MaxPressure2Limit") == {"max", "pressure", "2", "limit"}
    assert minmax_validator._tokenize_name(".Min") == {"min"}
    assert minmax_validator._minmax_flags("MinMaxWindow") == (True, True, True)

    ambiguous_mapping = ParameterMapping(
        target=_varref("MinMaxWindow"),
        source_type=MappingSource.VARIABLE,
        is_duration=False,
        is_source_global=False,
        source=_varref("MinSource"),
        source_literal=None,
    )
    assert (
        minmax_validator.check_min_max_mapping(
            ambiguous_mapping,
            Variable(name="MinMaxWindow", datatype=ScalarDatatype.INTEGER),
            Variable(name="MinSource", datatype=ScalarDatatype.INTEGER),
            ["Root"],
        )
        == []
    )

    blank_mapping = ParameterMapping(
        target=_varref(""),
        source_type=MappingSource.VARIABLE,
        is_duration=False,
        is_source_global=False,
        source=_varref(""),
        source_literal=None,
    )
    assert (
        minmax_validator.check_min_max_mapping(
            blank_mapping,
            Variable(name="", datatype=ScalarDatatype.INTEGER),
            Variable(name="", datatype=ScalarDatatype.INTEGER),
            ["Root"],
        )
        == []
    )


def test_contract_mapping_validator_helper_branches(monkeypatch: pytest.MonkeyPatch) -> None:
    validator = validators_module.ContractMappingValidator(TypeGraph({}))
    source_var = Variable(name="Source", datatype=ScalarDatatype.INTEGER)
    target_var = Variable(name="AnyParam", datatype="AnyType")
    mapping = ParameterMapping(
        target=_varref("AnyParam"),
        source_type=MappingSource.VARIABLE,
        is_duration=False,
        is_source_global=False,
        source=_varref("Source"),
        source_literal=None,
    )

    def _field_datatype(
        _variable: Variable,
        field_path: tuple[str, ...],
        _graph: object,
    ) -> ScalarDatatype | None:
        return ScalarDatatype.BOOLEAN if tuple(field_path) == ("child",) else None

    monkeypatch.setattr(validators_module, "_resolve_variable_field_datatype", _field_datatype)

    assert validator._resolve_target_datatype("AnyParam", target_var) == ("AnyType", None)
    assert validator._resolve_target_datatype("AnyParam.child", target_var) == (ScalarDatatype.BOOLEAN, "child")
    assert validator._resolve_source_datatype(
        ParameterMapping(
            target=_varref("AnyParam"),
            source_type=MappingSource.VALUE,
            is_duration=False,
            is_source_global=False,
            source=None,
            source_literal=1,
        ),
        None,
    ) == (ScalarDatatype.INTEGER, "1")
    assert validator._resolve_source_datatype(mapping, None) == (None, "Source")
    assert validator._resolve_source_datatype(mapping, source_var) == (ScalarDatatype.INTEGER, "Source")
    assert validator._resolve_source_datatype(
        ParameterMapping(
            target=_varref("AnyParam"),
            source_type=MappingSource.VARIABLE,
            is_duration=False,
            is_source_global=False,
            source=_varref("Source.child"),
            source_literal=None,
        ),
        source_var,
    ) == (ScalarDatatype.BOOLEAN, "Source.child")


def test_contract_mapping_validator_datatype_resolution_branches(monkeypatch: pytest.MonkeyPatch) -> None:
    validator = validators_module.ContractMappingValidator(TypeGraph({}))
    target_var = Variable(name="Target", datatype=ScalarDatatype.INTEGER)
    source_var = Variable(name="Source", datatype=ScalarDatatype.STRING)
    mapping = ParameterMapping(
        target=_varref("Target"),
        source_type=MappingSource.VARIABLE,
        is_duration=False,
        is_source_global=False,
        source=_varref("Source"),
        source_literal=None,
    )

    def _unresolved_target(*_args: object) -> tuple[ScalarDatatype | str | None, str | None]:
        return (None, None)

    def _integer_target(*_args: object) -> tuple[ScalarDatatype | str | None, str | None]:
        return (ScalarDatatype.INTEGER, None)

    monkeypatch.setattr(validator, "_resolve_target_datatype", _unresolved_target)
    assert validator.resolve_target_datatype("Target", target_var) == (None, None)

    monkeypatch.setattr(validator, "_resolve_target_datatype", _integer_target)
    assert validator.resolve_target_datatype("Target", target_var) == (ScalarDatatype.INTEGER, None)

    assert validator.resolve_source_datatype(mapping, source_var) == (ScalarDatatype.STRING, "Source")
