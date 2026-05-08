"""Tests for variable-quality analyzers: MMS, loop output, parameter drift, cyclomatic complexity, scan-loop resource, min/max, contract mismatch, magic numbers, shadowing, variables analysis, and datatype duplication."""

import logging
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

from sattline_parser import parse_source_text as parser_core_parse_source_text
from sattline_parser.models.ast_model import (
    BasePicture,
    DataType,
    Equation,
    FloatLiteral,
    GraphObject,
    InteractObject,
    IntLiteral,
    ModuleCode,
    ModuleDef,
    ModuleHeader,
    ModuleTypeDef,
    ModuleTypeInstance,
    ParameterMapping,
    Sequence,
    SFCTransition,
    Simple_DataType,
    SingleModule,
    SourceSpan,
    Variable,
)
from sattlint import constants as const
from sattlint.analyzers import _variables_execution as variables_execution_module
from sattlint.analyzers import variable_issue_collection as variable_issue_collection_module
from sattlint.analyzers.shadowing import analyze_shadowing
from sattlint.analyzers.variables import IssueKind, VariablesAnalyzer
from sattlint.engine import parse_source_file
from sattlint.reporting.variables_report import (
    VariableIssue,
    VariablesReport,
)
from sattlint.resolution.scope import ScopeContext
from tests._analyzers_variables_adjacent_analyzers import (  # noqa: F401
    test_cyclomatic_complexity_flags_high_complexity_program_modulecode,
    test_cyclomatic_complexity_flags_high_complexity_sfc_step,
    test_cyclomatic_complexity_ignores_low_complexity_program_modulecode,
    test_loop_output_refactor_detects_cycle_across_equations_and_active_step,
    test_loop_output_refactor_ignores_acyclic_sorted_blocks,
    test_mms_interface_collects_nested_typedef_mappings_and_write_locations,
    test_mms_interface_flags_dead_tags_for_unwritten_outgoing_variables,
    test_mms_interface_flags_duplicate_tags_and_datatype_mismatch_from_icf_entries,
    test_mms_interface_flags_naming_drift_from_icf_entries,
    test_mms_interface_uses_moduletype_default_tags_for_duplicate_and_dead_tag_checks,
    test_parameter_drift_flags_diverging_literal_parameter_values,
    test_parameter_drift_ignores_aligned_literal_parameter_values,
    test_scan_loop_resource_usage_flags_non_precision_builtin_in_active_step_code,
    test_scan_loop_resource_usage_flags_non_precision_builtin_in_equation_block,
    test_scan_loop_resource_usage_ignores_non_precision_builtin_outside_active_scan_context,
)


def _hdr(name: str) -> ModuleHeader:
    return ModuleHeader(name=name, invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0))


def _varref(s: str) -> dict:
    return {const.KEY_VAR_NAME: s}


def _state_ref(name: str, state: str) -> dict:
    return {const.KEY_VAR_NAME: name, "state": state}


def _issue_kinds(report) -> set[str]:
    return {issue.kind for issue in report.issues}


def _status_bridge_typedef() -> ModuleTypeDef:
    return ModuleTypeDef(
        name="StatusBridge",
        moduleparameters=[Variable(name="OperationStatus", datatype=Simple_DataType.INTEGER)],
        localvariables=[
            Variable(name="Source", datatype=Simple_DataType.INTEGER),
            Variable(name="Destination", datatype=Simple_DataType.INTEGER),
        ],
        moduledef=None,
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="BridgeEq",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (
                            const.KEY_FUNCTION_CALL,
                            "CopyVariable",
                            [_varref("Source"), _varref("Destination"), _varref("OperationStatus")],
                        )
                    ],
                )
            ]
        ),
    )


class _UsageStub:
    def __init__(
        self,
        *,
        is_unused: bool = False,
        is_display_only: bool = False,
        is_read_only: bool = False,
        read: bool = False,
        written: bool = False,
        field_reads: dict[str, list[object]] | None = None,
        field_writes: dict[str, list[object]] | None = None,
        usage_locations: list[tuple[object, str]] | None = None,
    ) -> None:
        self.is_unused = is_unused
        self.is_display_only = is_display_only
        self.is_read_only = is_read_only
        self.read = read
        self.written = written
        self.field_reads = field_reads or {}
        self.field_writes = field_writes or {}
        self.usage_locations = usage_locations or []

    def mark_field_read(self, field_path: str, location: object) -> None:
        self.field_reads.setdefault(field_path, []).append(location)

    def mark_field_written(self, field_path: str, location: object) -> None:
        self.field_writes.setdefault(field_path, []).append(location)

    def mark_read(self, location: object) -> None:
        self.read = True
        self.usage_locations.append((location, "read"))

    def mark_written(self, location: object) -> None:
        self.written = True
        self.usage_locations.append((location, "write"))


def _access_event(
    path_parts: tuple[str, ...],
    use_module_path: list[str],
    kind: object,
) -> SimpleNamespace:
    return SimpleNamespace(
        canonical_path=SimpleNamespace(key=lambda: path_parts),
        use_module_path=use_module_path,
        kind=kind,
    )


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


def test_required_parameter_name_helper_caches_only_runtime_used_parameters():
    typedef = ModuleTypeDef(
        name="ChildType",
        moduleparameters=[
            Variable(name="RequiredValue", datatype=Simple_DataType.INTEGER),
            Variable(name="UnusedValue", datatype=Simple_DataType.INTEGER),
        ],
        localvariables=[Variable(name="Mirror", datatype=Simple_DataType.INTEGER)],
        submodules=[],
        moduledef=None,
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="UseParam",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[(const.KEY_ASSIGN, _varref("Mirror"), _varref("RequiredValue"))],
                )
            ]
        ),
        parametermappings=[],
    )
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[typedef],
        localvariables=[],
        submodules=[],
        modulecode=None,
        moduledef=None,
    )

    analyzer = VariablesAnalyzer(bp)

    first = analyzer._get_required_parameter_names_for_typedef(typedef)
    second = analyzer._get_required_parameter_names_for_typedef(typedef)

    assert first == {"requiredvalue": "RequiredValue"}
    assert second == first
    assert analyzer._required_parameter_names_by_owner[id(typedef)] == first


def test_anytype_contracts_collect_read_and_write_field_paths():
    typedef = ModuleTypeDef(
        name="ChildType",
        moduleparameters=[Variable(name="Payload", datatype="AnyType")],
        localvariables=[
            Variable(name="Mirror", datatype=Simple_DataType.INTEGER),
            Variable(name="Source", datatype=Simple_DataType.INTEGER),
        ],
        submodules=[],
        moduledef=None,
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="UsePayload",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (const.KEY_ASSIGN, _varref("Mirror"), _varref("Payload.FieldA")),
                        (const.KEY_ASSIGN, _varref("Payload.FieldB"), _varref("Source")),
                    ],
                )
            ]
        ),
        parametermappings=[],
    )
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[typedef],
        localvariables=[],
        submodules=[],
        modulecode=None,
        moduledef=None,
    )

    analyzer = VariablesAnalyzer(bp)

    contracts = analyzer._anytype_field_contracts_by_owner[id(typedef)]

    assert contracts["payload"].field_paths == ("FieldA", "FieldB")


def test_magic_number_detection_in_equations_and_sfc():
    eq = Equation(
        name="Main",
        position=(0.0, 0.0),
        size=(1.0, 1.0),
        code=[
            (
                const.KEY_ASSIGN,
                _varref("Output"),
                IntLiteral(42, SourceSpan(12, 5)),
            ),
            (
                const.KEY_ASSIGN,
                _varref("Output"),
                IntLiteral(0, SourceSpan(13, 5)),
            ),
            (
                const.KEY_ASSIGN,
                _varref("Output"),
                (const.KEY_MINUS, IntLiteral(0, SourceSpan(14, 5))),
            ),
        ],
    )

    transition = SFCTransition(
        name="ToNext",
        condition=(
            const.KEY_COMPARE,
            _varref("Output"),
            [
                (">", FloatLiteral(2.5, SourceSpan(20, 7))),
                ("<", FloatLiteral(0.0, SourceSpan(21, 9))),
            ],
        ),
    )

    seq = Sequence(
        name="SeqMain",
        type="sequence",
        position=(0.0, 0.0),
        size=(1.0, 1.0),
        code=[transition],
    )

    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[Variable(name="Output", datatype=Simple_DataType.INTEGER)],
        modulecode=ModuleCode(sequences=[seq], equations=[eq]),
        moduledef=None,
    )

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    magic = [i for i in analyzer.issues if i.kind is IssueKind.MAGIC_NUMBER]
    assert len(magic) == 2

    values = sorted(i.literal_value for i in magic if i.literal_value is not None)
    assert values == [2.5, 42]

    spans = {(i.literal_span.line, i.literal_span.column) for i in magic if i.literal_span is not None}
    assert (12, 5) in spans
    assert (20, 7) in spans
    assert (13, 5) not in spans
    assert (14, 5) not in spans
    assert (21, 9) not in spans


def test_shadowing_detected_for_nested_locals():
    child = SingleModule(
        header=_hdr("Child"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[Variable(name="value", datatype=Simple_DataType.INTEGER)],
        submodules=[],
        modulecode=None,
        parametermappings=[],
    )

    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[Variable(name="Value", datatype=Simple_DataType.INTEGER)],
        submodules=[child],
        modulecode=None,
        moduledef=None,
    )

    report = analyze_shadowing(bp)

    assert any(i.kind is IssueKind.SHADOWING for i in report.issues)


def test_shadowing_detected_for_moduletype_instance_locals():
    mt = ModuleTypeDef(
        name="TypeA",
        moduleparameters=[],
        localvariables=[Variable(name="Setting", datatype=Simple_DataType.INTEGER)],
        submodules=[],
        moduledef=None,
        modulecode=None,
        parametermappings=[],
    )

    instance = ModuleTypeInstance(
        header=_hdr("InstanceA"),
        moduletype_name="TypeA",
        parametermappings=[],
    )

    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[mt],
        localvariables=[Variable(name="setting", datatype=Simple_DataType.INTEGER)],
        submodules=[instance],
        modulecode=None,
        moduledef=None,
    )

    report = analyze_shadowing(bp)

    assert any(i.kind is IssueKind.SHADOWING for i in report.issues)


def test_variable_analysis_marks_invar_reads_across_graphics_and_interact_paths():
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0 : InVar_ "PosX",0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    PosX: integer := 0;
    PanelResize: integer := 0;
    WidthSource: integer := 0;
    FormatSource: integer := 0;
    ColourSource: integer := 0;
    ButtonTypeSource: integer := 0;
ModuleDef
    ClippingBounds = ( -1.0 , -1.0 : InVar_ "PanelResize" ) ( 1.0 , 1.0 )
    GraphObjects :
        TextObject ( 0.0 , 0.0 ) ( 1.0 , 1.0 )
            "Value" VarName Width_ = 5 : InVar_ "WidthSource"
            Format_String_ = "" : InVar_ "FormatSource"
            OutlineColour : Colour0 = 5 : InVar_ "ColourSource"
    InteractObjects :
        ComBut_ ( 0.0 , 0.0 ) ( 1.0 , 1.0 )
            ButtonType = 0 : InVar_ "ButtonTypeSource"
ENDDEF (*BasePicture*);
"""

    bp = parser_core_parse_source_text(code)
    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    usage_by_name = {variable.name: analyzer._get_usage(variable) for variable in bp.localvariables}

    assert usage_by_name["PosX"].read is True
    assert usage_by_name["PanelResize"].read is True
    assert usage_by_name["WidthSource"].read is True
    assert usage_by_name["FormatSource"].read is True
    assert usage_by_name["ColourSource"].read is True
    assert usage_by_name["ButtonTypeSource"].read is True
    assert usage_by_name["WidthSource"].ui_read is True
    assert usage_by_name["ButtonTypeSource"].ui_read is True


def test_layout_overlap_detects_overlapping_module_invocations():
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
TYPEDEFINITIONS
    ChildType = MODULEDEFINITION DateCode_ 1
    ModuleDef
        ClippingBounds = ( 0.0 , 0.0 ) ( 1.0 , 1.0 )
    ENDDEF (*ChildType*);
SUBMODULES
    ChildA Invocation ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0 ) : ChildType;
    ChildB Invocation ( 0.5 , 0.5 , 0.0 , 1.0 , 1.0 ) : ChildType;
ModuleDef
    ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ENDDEF (*BasePicture*);
"""

    bp = parser_core_parse_source_text(code)
    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    overlap_issues = [issue for issue in analyzer.issues if issue.kind is IssueKind.LAYOUT_OVERLAP]

    assert len(overlap_issues) == 1
    assert overlap_issues[0].role == "module 'ChildA' overlaps module 'ChildB'"


def test_layout_overlap_ignores_modules_on_different_layers():
    child_moduledef = ModuleDef(clipping_bounds=((-1.0, -1.0), (1.0, 1.0)))
    bp = BasePicture(
        header=_hdr("BasePicture"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[],
        submodules=[
            SingleModule(
                header=ModuleHeader(
                    name="Layer1",
                    invoke_coord=(0.0, 0.0, 0.0, 0.1, 0.1),
                    layer_info="1",
                ),
                moduledef=child_moduledef,
                moduleparameters=[],
                localvariables=[],
                submodules=[],
                modulecode=None,
                parametermappings=[],
            ),
            SingleModule(
                header=ModuleHeader(
                    name="Layer2",
                    invoke_coord=(0.02, 0.02, 0.0, 0.1, 0.1),
                    layer_info="2",
                ),
                moduledef=child_moduledef,
                moduleparameters=[],
                localvariables=[],
                submodules=[],
                modulecode=None,
                parametermappings=[],
            ),
        ],
        modulecode=None,
        moduledef=None,
    )

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    overlap_issues = [issue for issue in analyzer.issues if issue.kind is IssueKind.LAYOUT_OVERLAP]

    assert overlap_issues == []


def test_layout_overlap_uses_module_clipping_bounds_for_visible_overlap():
    child_moduledef = ModuleDef(clipping_bounds=((-1.0, -1.0), (1.0, 1.0)))
    bp = BasePicture(
        header=_hdr("BasePicture"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[],
        submodules=[
            SingleModule(
                header=ModuleHeader(name="ChildA", invoke_coord=(0.0, 0.0, 0.0, 0.1, 0.1)),
                moduledef=child_moduledef,
                moduleparameters=[],
                localvariables=[],
                submodules=[],
                modulecode=None,
                parametermappings=[],
            ),
            SingleModule(
                header=ModuleHeader(name="ChildB", invoke_coord=(0.1, 0.1, 0.0, 0.1, 0.1)),
                moduledef=child_moduledef,
                moduleparameters=[],
                localvariables=[],
                submodules=[],
                modulecode=None,
                parametermappings=[],
            ),
        ],
        modulecode=None,
        moduledef=None,
    )

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    overlap_issues = [issue for issue in analyzer.issues if issue.kind is IssueKind.LAYOUT_OVERLAP]

    assert len(overlap_issues) == 1
    assert overlap_issues[0].role == "module 'ChildA' overlaps module 'ChildB'"


def test_layout_overlap_detects_overlapping_graph_and_interact_objects():
    bp = BasePicture(
        header=_hdr("BasePicture"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[],
        submodules=[],
        modulecode=None,
        moduledef=ModuleDef(
            graph_objects=[
                GraphObject(
                    type="TextObject",
                    properties={"coords": ((0.0, 0.0), (1.0, 1.0))},
                )
            ],
            interact_objects=[
                InteractObject(
                    type="ComBut_",
                    properties={"coords": [((0.5, 0.5), (1.25, 1.25))]},
                )
            ],
        ),
    )

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    overlap_issues = [issue for issue in analyzer.issues if issue.kind is IssueKind.LAYOUT_OVERLAP]

    assert len(overlap_issues) == 1
    assert overlap_issues[0].role == "graph object TextObject #1 overlaps interact object ComBut_ #1"


def test_layout_overlap_ignores_objects_on_different_layers():
    bp = BasePicture(
        header=_hdr("BasePicture"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[],
        submodules=[],
        modulecode=None,
        moduledef=ModuleDef(
            graph_objects=[
                GraphObject(
                    type="TextObject",
                    properties={"coords": ((0.0, 0.0), (1.0, 1.0)), "layer": 1},
                )
            ],
            interact_objects=[
                InteractObject(
                    type="ComBut_",
                    properties={"coords": [((0.5, 0.5), (1.25, 1.25))], "layer": 2},
                )
            ],
        ),
    )

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    overlap_issues = [issue for issue in analyzer.issues if issue.kind is IssueKind.LAYOUT_OVERLAP]

    assert overlap_issues == []


def test_ui_only_variable_detected_for_graphics_invar_reads():
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    WidthSource: integer := 0;
ModuleDef
    ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
    GraphObjects :
        TextObject ( 0.0 , 0.0 ) ( 1.0 , 1.0 )
            "Value" VarName Width_ = 5 : InVar_ "WidthSource"
ENDDEF (*BasePicture*);
"""

    bp = parser_core_parse_source_text(code)
    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    issues = [issue for issue in analyzer.issues if issue.kind is IssueKind.UI_ONLY]

    assert len(issues) == 1
    assert issues[0].variable is not None
    assert issues[0].variable.name == "WidthSource"
    assert not any(issue.kind is IssueKind.READ_ONLY_NON_CONST for issue in analyzer.issues)


def test_ui_only_variable_detected_for_interact_invar_reads():
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    ButtonTypeSource: integer := 0;
ModuleDef
    ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
    InteractObjects :
        ComBut_ ( 0.0 , 0.0 ) ( 1.0 , 1.0 )
            ButtonType = 0 : InVar_ "ButtonTypeSource"
ENDDEF (*BasePicture*);
"""

    bp = parser_core_parse_source_text(code)
    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    issues = [issue for issue in analyzer.issues if issue.kind is IssueKind.UI_ONLY]

    assert len(issues) == 1
    assert issues[0].variable is not None
    assert issues[0].variable.name == "ButtonTypeSource"


def test_ui_only_variable_is_suppressed_by_non_ui_control_usage():
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    WidthSource: integer := 0;
    Output: integer := 0;
ModuleDef
    ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
    GraphObjects :
        TextObject ( 0.0 , 0.0 ) ( 1.0 , 1.0 )
            "Value" VarName Width_ = 5 : InVar_ "WidthSource"
    ModuleCode
        EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
            Output = WidthSource;
ENDDEF (*BasePicture*);
"""

    bp = parser_core_parse_source_text(code)
    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    assert not any(
        issue.kind is IssueKind.UI_ONLY and issue.variable is not None and issue.variable.name == "WidthSource"
        for issue in analyzer.issues
    )


def test_graphics_format_tail_keywords_do_not_log_missing_variables(caplog):
    bp = BasePicture(
        header=_hdr("BasePicture"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[Variable(name="RealSource", datatype=Simple_DataType.INTEGER)],
        submodules=[],
        modulecode=None,
        moduledef=None,
    )
    analyzer = VariablesAnalyzer(bp, debug=True)
    context = ScopeContext(
        env={"realsource": bp.localvariables[0]},
        param_mappings={},
        module_path=[bp.header.name],
        display_module_path=[bp.header.name],
    )

    with caplog.at_level(logging.DEBUG, logger="SattLint"):
        for token in ("Real_Value", "Relative_", "Decimal_", "Int_Value", "Abs_"):
            analyzer._walk_tail(token, context, [bp.header.name])
        analyzer._walk_tail("RealSource", context, [bp.header.name])
        analyzer._walk_tail("MissingVar", context, [bp.header.name])

    messages = [record.message for record in caplog.records]

    assert not any("real_value" in message.lower() for message in messages)
    assert not any("relative_" in message.lower() for message in messages)
    assert not any("decimal_" in message.lower() for message in messages)
    assert not any("int_value" in message.lower() for message in messages)
    assert not any("abs_" in message.lower() for message in messages)
    assert any("missingvar" in message.lower() for message in messages)
    assert analyzer._get_usage(bp.localvariables[0]).read is True


def test_variables_fallback_warnings_are_not_logged_without_debug(caplog):
    bp = BasePicture(
        header=_hdr("BasePicture"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[],
        submodules=[],
        modulecode=None,
        moduledef=None,
    )
    analyzer = VariablesAnalyzer(bp, debug=False, fail_loudly=False)

    with caplog.at_level(logging.WARNING, logger="SattLint"):
        analyzer._warn("test fallback warning")

    assert analyzer.analysis_warnings == ["test fallback warning"]
    assert not caplog.records


def test_interact_litstring_invar_tail_does_not_crash_variable_analysis():
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    WidthSource: integer := 0;
ModuleDef
    ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
    InteractObjects :
        ComBut_ ( 0.0 , 0.0 ) ( 1.0 , 1.0 )
            Abs_ TextObject = "" : InVar_ LitString "Start Sim"
ENDDEF (*BasePicture*);
"""

    bp = parser_core_parse_source_text(code)
    width_source = bp.localvariables[0]

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    assert analyzer._get_usage(width_source).read is False


def test_shadowing_ignores_external_moduletype_instance_locals_for_program_target():
    mt = ModuleTypeDef(
        name="TypeA",
        moduleparameters=[],
        localvariables=[Variable(name="Setting", datatype=Simple_DataType.INTEGER)],
        submodules=[],
        moduledef=None,
        modulecode=None,
        parametermappings=[],
        origin_file="TypeA.x",
        origin_lib="SomeLib",
    )

    instance = ModuleTypeInstance(
        header=_hdr("InstanceA"),
        moduletype_name="TypeA",
        parametermappings=[],
    )

    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[mt],
        localvariables=[Variable(name="setting", datatype=Simple_DataType.INTEGER)],
        submodules=[instance],
        modulecode=None,
        moduledef=None,
        origin_file="Root.x",
        origin_lib="ProgramLib",
    )

    report = analyze_shadowing(bp)

    assert not any(i.kind is IssueKind.SHADOWING for i in report.issues)


def test_variable_analysis_ignores_external_moduletype_usage_for_program_target():
    library_mt = ModuleTypeDef(
        name="LibType",
        moduleparameters=[Variable(name="Input", datatype=Simple_DataType.INTEGER)],
        localvariables=[],
        submodules=[],
        moduledef=None,
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="E1",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[_varref("Input")],
                )
            ]
        ),
        parametermappings=[],
        origin_file="LibType.x",
        origin_lib="SomeLib",
    )

    instance = ModuleTypeInstance(
        header=_hdr("LibInst"),
        moduletype_name="LibType",
        parametermappings=[
            ParameterMapping(
                target=_varref("Input"),
                source_type=const.TREE_TAG_VARIABLE_NAME,
                is_duration=False,
                is_source_global=False,
                source=_varref("ProgramVar"),
                source_literal=None,
            )
        ],
    )

    program_var = Variable(name="ProgramVar", datatype=Simple_DataType.INTEGER)
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[library_mt],
        localvariables=[program_var],
        submodules=[instance],
        modulecode=None,
        moduledef=None,
        origin_file="Root.x",
        origin_lib="ProgramLib",
    )

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    assert any(issue.kind is IssueKind.UNUSED and issue.variable is program_var for issue in analyzer.issues)


def test_variable_analysis_treats_external_moduletype_usage_as_used_for_library_target():
    library_mt = ModuleTypeDef(
        name="LibType",
        moduleparameters=[Variable(name="Input", datatype=Simple_DataType.INTEGER)],
        localvariables=[],
        submodules=[],
        moduledef=None,
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="E1",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[_varref("Input")],
                )
            ]
        ),
        parametermappings=[],
        origin_file="LibType.x",
        origin_lib="SomeLib",
    )

    instance = ModuleTypeInstance(
        header=_hdr("LibInst"),
        moduletype_name="LibType",
        parametermappings=[
            ParameterMapping(
                target=_varref("Input"),
                source_type=const.TREE_TAG_VARIABLE_NAME,
                is_duration=False,
                is_source_global=False,
                source=_varref("LibraryVar"),
                source_literal=None,
            )
        ],
    )

    library_var = Variable(name="LibraryVar", datatype=Simple_DataType.INTEGER)
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[library_mt],
        localvariables=[library_var],
        submodules=[instance],
        modulecode=None,
        moduledef=None,
        origin_file="Root.x",
        origin_lib="ProjectLib",
    )

    analyzer = VariablesAnalyzer(bp, analyzed_target_is_library=True)
    analyzer.run()

    assert not any(issue.variable is library_var for issue in analyzer.issues)


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
        _is_from_root_origin=lambda origin: True,
        _get_usage=lambda variable: usage_by_id[id(variable)],
        _procedure_status_issue=lambda variable, usage: (
            ("procedure-status", "Status") if variable is procedure_local else None
        ),
        _add_issue=lambda kind, path, variable, role, field_path=None: issues.append(
            (kind, tuple(path), variable.name, role, field_path)
        ),
        _has_output_effect=lambda *args, **kwargs: False,
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


def test_variables_execution_run_typedef_and_context_helpers_cover_remaining_paths(monkeypatch):
    log_messages: list[tuple[object, ...]] = []
    original_get_logger = logging.getLogger
    monkeypatch.setattr(
        logging,
        "getLogger",
        lambda name=None: (
            SimpleNamespace(debug=lambda *args: log_messages.append(args))
            if name == "SattLint"
            else original_get_logger(name)
        ),
    )

    runner: Any = SimpleNamespace(
        _issues=[],
        context_builder=SimpleNamespace(issues=None),
        _limit_to_module_path=None,
        bp=BasePicture(
            header=_hdr("Root"),
            datatype_defs=[],
            moduletype_defs=[],
            localvariables=[],
            submodules=[],
            modulecode=None,
            moduledef=None,
        ),
        debug=True,
        _analysis_warnings=[],
        _alias_links=[],
        _trace=lambda *args, **kwargs: None,
        _analyze_root_scope=lambda: None,
        _apply_alias_back_propagation=lambda: None,
        _propagate_procedure_status_bindings=lambda: None,
        _run_post_traversal_analyses=lambda: None,
        _collect_basepicture_issues=lambda bp_path: None,
        _collect_typedef_issues=lambda: None,
        _add_naming_role_mismatch_issues=lambda: None,
        _add_global_scope_minimization_issues=lambda: None,
        _add_hidden_global_coupling_issues=lambda: None,
        _add_high_fan_in_out_issues=lambda: None,
        _add_unused_datatype_field_issues=lambda: None,
    )

    assert variables_execution_module.run(runner) == []
    assert runner.context_builder.issues == []
    assert len(log_messages) == 2

    assert variables_execution_module._is_external_typename(
        cast(Any, SimpleNamespace(typedef_index={"knowntype": object()})),
        "UnknownType",
    )
    assert not variables_execution_module._is_external_typename(
        cast(Any, SimpleNamespace(typedef_index={"knowntype": object()})),
        "KnownType",
    )

    colliding_param = Variable(name="Shared", datatype=Simple_DataType.INTEGER)
    input_param = Variable(name="Input", datatype=Simple_DataType.INTEGER)
    colliding_local = Variable(name="Shared", datatype=Simple_DataType.INTEGER)
    usage_by_id = {
        id(colliding_param): _UsageStub(),
        id(input_param): _UsageStub(read=True),
        id(colliding_local): _UsageStub(),
    }
    moduletype = ModuleTypeDef(
        name="ChildType",
        moduleparameters=[colliding_param, input_param],
        localvariables=[colliding_local],
        submodules=[],
        moduledef=None,
        modulecode=None,
        parametermappings=[
            ParameterMapping(
                target=_varref("Input"),
                source_type=const.KEY_VALUE,
                is_duration=False,
                is_source_global=False,
                source=None,
                source_literal=1,
            )
        ],
    )
    captured_display_paths: list[list[str]] = []
    checked_targets: list[tuple[Variable | None, tuple[str, ...], tuple[str, ...]]] = []
    collision_issues: list[VariableIssue] = []
    helper: Any = SimpleNamespace(
        _analyzing_typedefs={"childtype"},
        _append_issue=lambda issue: collision_issues.append(issue),
        _get_usage=lambda variable: usage_by_id[id(variable)],
        used_params_by_typedef={},
        param_reads_by_typedef={},
        param_writes_by_typedef={},
        _walk_moduledef=lambda moduledef, context, path: captured_display_paths.append(
            list(context.display_module_path)
        ),
        _walk_module_code=lambda *args, **kwargs: None,
        _walk_submodules=lambda *args, **kwargs: None,
        _walk_typedef_groupconn=lambda *args, **kwargs: None,
        _check_param_mapping=lambda mapping, target_var, env, path: checked_targets.append(
            (target_var, tuple(sorted(env)), tuple(path))
        ),
    )

    variables_execution_module._analyze_typedef(helper, moduletype, ["Root", "TypeDef:ChildType", "Nested"])
    assert collision_issues == []
    assert captured_display_paths == []

    helper._analyzing_typedefs = set()
    variables_execution_module._analyze_typedef(helper, moduletype, ["Root", "TypeDef:ChildType", "Nested"])
    assert collision_issues[0].kind is IssueKind.NAME_COLLISION
    assert collision_issues[0].source_variable is colliding_param
    assert captured_display_paths[0] == [
        variables_execution_module.decorate_segment("Root", "BP"),
        variables_execution_module.decorate_segment("TypeDef:ChildType", "TD"),
        "Nested",
    ]
    assert helper.used_params_by_typedef["ChildType"] == {"input"}
    assert helper.param_reads_by_typedef["childtype"] == {"input"}
    assert helper.param_writes_by_typedef["childtype"] == set()
    assert checked_targets[0][0] is input_param

    read_param = Variable(name="ReadParam", datatype=Simple_DataType.INTEGER)
    write_param = Variable(name="WriteParam", datatype=Simple_DataType.INTEGER)
    usage_by_id[id(read_param)] = _UsageStub(read=True)
    usage_by_id[id(write_param)] = _UsageStub(written=True)
    module = SingleModule(
        header=_hdr("Worker"),
        moduledef=None,
        moduleparameters=[read_param, write_param],
        localvariables=[],
        submodules=[],
        modulecode=None,
        parametermappings=[],
    )
    context = ScopeContext(
        env={},
        param_mappings={},
        module_path=["Root"],
        display_module_path=["Root"],
        current_library=None,
        parent_context=None,
    )
    simple_helper: Any = SimpleNamespace(
        _walk_moduledef=lambda *args, **kwargs: None,
        _walk_module_code=lambda *args, **kwargs: None,
        _walk_submodules=lambda *args, **kwargs: None,
        _get_usage=lambda variable: usage_by_id[id(variable)],
        _analyzing_typedefs={"childtype"},
    )
    used_reads, used_writes = variables_execution_module._analyze_single_module_with_context(
        simple_helper,
        module,
        context,
        ["Root", "Worker"],
    )
    assert used_reads == {"readparam"}
    assert used_writes == {"writeparam"}

    variables_execution_module._analyze_typedef_with_context(
        simple_helper,
        moduletype,
        context,
        ["Root", "TypeDef:ChildType"],
    )


def test_variables_execution_apply_alias_back_propagation_covers_prefixed_and_direct_marks():
    parent = Variable(name="Parent", datatype="Payload")
    child = Variable(name="Child", datatype="Payload")
    root_parent = Variable(name="RootParent", datatype=Simple_DataType.INTEGER)
    root_child = Variable(name="RootChild", datatype=Simple_DataType.INTEGER)

    parent_usage = _UsageStub()
    child_usage = _UsageStub(
        field_reads={"Leaf": [("reader", 1)], "": [("reader-empty", 3)]},
        field_writes={"": [("writer", 2)], "LeafWrite": [("writer-leaf", 4)]},
        usage_locations=[(("step", 1), "read"), (("step", 2), "write")],
    )
    root_parent_usage = _UsageStub()
    root_child_usage = _UsageStub(
        field_reads={"DirectLeaf": [("root-reader", 5)]},
        field_writes={"DirectWrite": [("root-writer", 6)]},
        usage_locations=[(("root", 1), "read"), (("root", 2), "write")],
    )
    usage_by_id = {
        id(parent): parent_usage,
        id(child): child_usage,
        id(root_parent): root_parent_usage,
        id(root_child): root_child_usage,
    }
    helper: Any = SimpleNamespace(
        _alias_links=[(parent, child, "Alias"), (root_parent, root_child, "")],
        _get_usage=lambda variable: usage_by_id[id(variable)],
    )

    variables_execution_module._apply_alias_back_propagation(helper)

    assert parent_usage.field_reads["Alias.Leaf"] == [("reader", 1)]
    assert parent_usage.field_reads["Alias"] == [("reader-empty", 3), ("step", 1)]
    assert parent_usage.field_writes["Alias"] == [("writer", 2), ("step", 2)]
    assert parent_usage.field_writes["Alias.LeafWrite"] == [("writer-leaf", 4)]
    assert root_parent_usage.field_reads["DirectLeaf"] == [("root-reader", 5)]
    assert root_parent_usage.field_writes["DirectWrite"] == [("root-writer", 6)]
    assert root_parent_usage.usage_locations == [(("root", 1), "read"), (("root", 2), "write")]


def test_variable_issue_collection_datatype_field_helper_covers_remaining_branches():
    external_datatype = DataType(name="ExternalPayload", description=None, datecode=None, var_list=[])
    cast(Any, external_datatype).origin_file = "external.s"
    empty_datatype = DataType(name="EmptyPayload", description=None, datecode=None, var_list=[])
    library_datatype = DataType(
        name="LibraryPayload",
        description=None,
        datecode=None,
        var_list=[Variable(name="FieldA", datatype=Simple_DataType.INTEGER)],
    )
    no_access_datatype = DataType(
        name="PayloadNoAccess",
        description=None,
        datecode=None,
        var_list=[Variable(name="FieldA", datatype=Simple_DataType.INTEGER)],
    )
    partial_datatype = DataType(
        name="PayloadPartial",
        description=None,
        datecode=None,
        var_list=[
            Variable(name="Used", datatype=Simple_DataType.INTEGER),
            Variable(name="Unused", datatype=Simple_DataType.INTEGER),
        ],
    )
    library_var = Variable(name="LibraryVar", datatype="LibraryPayload")
    no_access_var = Variable(name="NoAccessVar", datatype="PayloadNoAccess")
    partial_var = Variable(name="PartialVar", datatype="PayloadPartial")
    missing_var = Variable(name="MissingVar", datatype="MissingPayload")
    primitive_var = Variable(name="PrimitiveVar", datatype=Simple_DataType.INTEGER)
    usage_by_id = {
        id(library_var): _UsageStub(),
        id(no_access_var): _UsageStub(),
        id(partial_var): _UsageStub(field_reads={"Used": [("reader", 1)]}),
        id(missing_var): _UsageStub(),
        id(primitive_var): _UsageStub(),
    }
    issues: list[VariableIssue] = []
    helper: Any = SimpleNamespace(
        bp=BasePicture(
            header=_hdr("Root"),
            datatype_defs=[external_datatype, empty_datatype, library_datatype, no_access_datatype, partial_datatype],
            moduletype_defs=[],
            localvariables=[],
            submodules=[],
            modulecode=None,
            moduledef=None,
        ),
        _is_from_root_origin=lambda origin: origin != "external.s",
        type_graph=SimpleNamespace(
            iter_leaf_field_paths=lambda name: {
                "EmptyPayload": [],
                "LibraryPayload": [("FieldA",)],
                "PayloadNoAccess": [("FieldA",)],
                "PayloadPartial": [("Used",), ("Unused",)],
            }.get(name, [])
        ),
        _iter_variables_for_datatype_field_analysis=lambda: [
            (["Root"], primitive_var, "localvariable"),
            (["Root"], missing_var, "localvariable"),
            (["Root", "TypeDef:Carrier"], library_var, "moduleparameter"),
            (["Root"], no_access_var, "localvariable"),
            (["Root"], partial_var, "localvariable"),
        ],
        _analyzed_target_is_library=True,
        _get_usage=lambda variable: usage_by_id[id(variable)],
        _append_issue=lambda issue: issues.append(issue),
    )

    variable_issue_collection_module._add_unused_datatype_field_issues(helper)

    assert len(issues) == 1
    issue = issues[0]
    assert issue.kind is IssueKind.UNUSED_DATATYPE_FIELD
    assert issue.datatype_name == "PayloadPartial"
    assert issue.field_path == "Unused"


def test_variable_issue_collection_direct_global_helpers_cover_remaining_branches():
    shared = Variable(name="Shared", datatype=Simple_DataType.INTEGER)
    issues: list[VariableIssue] = []
    helper: Any = SimpleNamespace(
        bp=BasePicture(
            header=_hdr("Root"),
            datatype_defs=[],
            moduletype_defs=[],
            localvariables=[shared],
            submodules=[],
            modulecode=None,
            moduledef=None,
        ),
        _analyzed_target_is_library=False,
        _trace=lambda *args, **kwargs: None,
        _append_issue=lambda issue: issues.append(issue),
    )
    helper.access_graph = SimpleNamespace(
        events=[
            _access_event(("root",), ["Root", "Short"], variable_issue_collection_module.AccessKind.READ),
            _access_event(("root", "other"), ["Root", "Other"], variable_issue_collection_module.AccessKind.READ),
            _access_event(("root", "shared"), ["Root", "Writer"], variable_issue_collection_module.AccessKind.WRITE),
            _access_event(("root", "shared"), ["Root", "Reader"], variable_issue_collection_module.AccessKind.READ),
        ]
    )

    variable_issue_collection_module._add_hidden_global_coupling_issues(helper)

    assert len(issues) == 1
    assert "Writer (write)" in (issues[0].role or "")
    assert "Reader (read)" in (issues[0].role or "")

    issues.clear()
    helper.access_graph = SimpleNamespace(
        events=[
            _access_event(("root", "shared"), ["Root", "ReaderA"], variable_issue_collection_module.AccessKind.READ),
            _access_event(("root", "shared"), ["Root", "ReaderB"], variable_issue_collection_module.AccessKind.READ),
        ]
    )
    variable_issue_collection_module._add_hidden_global_coupling_issues(helper)
    assert issues == []

    helper.access_graph = SimpleNamespace(
        events=[
            _access_event(("root",), ["Root", "Short"], variable_issue_collection_module.AccessKind.READ),
            _access_event(("root", "other"), ["Root", "Other"], variable_issue_collection_module.AccessKind.READ),
            _access_event(("root", "shared"), ["Root", "ReaderA"], variable_issue_collection_module.AccessKind.READ),
            _access_event(("root", "shared"), ["Root", "ReaderB"], variable_issue_collection_module.AccessKind.READ),
            _access_event(("root", "shared"), ["Root", "ReaderC"], variable_issue_collection_module.AccessKind.READ),
            _access_event(("root", "shared"), ["Root", "WriterA"], variable_issue_collection_module.AccessKind.WRITE),
            _access_event(("root", "shared"), ["Root", "WriterB"], variable_issue_collection_module.AccessKind.WRITE),
            _access_event(("root", "shared"), ["Root", "WriterC"], variable_issue_collection_module.AccessKind.WRITE),
        ]
    )
    variable_issue_collection_module._add_high_fan_in_out_issues(helper)

    assert len(issues) == 1
    assert "high fan-in with 3 readers" in (issues[0].role or "")
    assert "high fan-out with 3 writers" in (issues[0].role or "")

    issues.clear()
    helper.access_graph = SimpleNamespace(
        events=[
            _access_event(("root",), ["Root", "Short"], variable_issue_collection_module.AccessKind.READ),
            _access_event(("root", "shared"), ["Root", "Worker"], variable_issue_collection_module.AccessKind.READ),
            _access_event(
                ("root", "shared"), ["Root", "Worker", "Nested"], variable_issue_collection_module.AccessKind.WRITE
            ),
        ]
    )
    variable_issue_collection_module._add_global_scope_minimization_issues(helper)

    assert len(issues) == 1
    assert "module subtree Worker" in (issues[0].role or "")
    assert "Worker.Nested" in (issues[0].role or "")


def test_variable_issue_collection_collect_module_issue_helper_covers_remaining_branches():
    procedure_param = Variable(name="ProcedureParam", datatype=Simple_DataType.INTEGER)
    ui_param = Variable(name="UiParam", datatype=Simple_DataType.INTEGER)
    effect_param = Variable(name="EffectParam", datatype=Simple_DataType.INTEGER)
    procedure_local = Variable(name="ProcedureLocal", datatype=Simple_DataType.INTEGER)
    ui_local = Variable(name="UiLocal", datatype=Simple_DataType.INTEGER)
    read_only_local = Variable(name="ReadOnlyLocal", datatype=Simple_DataType.INTEGER)
    usage_by_id = {
        id(procedure_param): _UsageStub(read=True),
        id(ui_param): _UsageStub(is_display_only=True),
        id(effect_param): _UsageStub(read=True, written=True),
        id(procedure_local): _UsageStub(read=True),
        id(ui_local): _UsageStub(is_display_only=True),
        id(read_only_local): _UsageStub(read=True, is_read_only=True),
    }
    issues: list[tuple[IssueKind, tuple[str, ...], str, str, str | None]] = []
    module = SingleModule(
        header=_hdr("Worker"),
        moduledef=None,
        moduleparameters=[procedure_param, ui_param, effect_param],
        localvariables=[procedure_local, ui_local, read_only_local],
        submodules=[],
        modulecode=None,
        parametermappings=[],
    )
    helper: Any = SimpleNamespace(
        _get_usage=lambda variable: usage_by_id[id(variable)],
        _procedure_status_issue=lambda variable, usage: (
            ("procedure-status", "Status") if variable is procedure_param or variable is procedure_local else None
        ),
        _add_issue=lambda kind, path, variable, role, field_path=None: issues.append(
            (kind, tuple(path), variable.name, role, field_path)
        ),
        _has_output_effect=lambda *args, **kwargs: False,
        _has_procedure_status_binding=lambda *args, **kwargs: False,
        _is_const_candidate=lambda *args, **kwargs: True,
    )

    variable_issue_collection_module._collect_issues_from_module(helper, module, ["Root"])

    assert (
        IssueKind.PROCEDURE_STATUS,
        ("Root", "Worker"),
        "ProcedureParam",
        "procedure-status",
        "Status",
    ) in issues
    assert (IssueKind.UI_ONLY, ("Root", "Worker"), "UiParam", "moduleparameter", None) in issues
    assert (
        IssueKind.WRITE_WITHOUT_EFFECT,
        ("Root", "Worker"),
        "EffectParam",
        "moduleparameter",
        None,
    ) in issues
    assert (
        IssueKind.PROCEDURE_STATUS,
        ("Root", "Worker"),
        "ProcedureLocal",
        "procedure-status",
        "Status",
    ) in issues
    assert (IssueKind.UI_ONLY, ("Root", "Worker"), "UiLocal", "localvariable", None) in issues
    assert (
        IssueKind.READ_ONLY_NON_CONST,
        ("Root", "Worker"),
        "ReadOnlyLocal",
        "localvariable",
        None,
    ) in issues
