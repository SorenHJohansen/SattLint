# These tests deliberately exercise private analyzer seams.
# pyright: reportPrivateUsage=false

from typing import (
    Any,
    cast,
)

from sattline_parser.ast import MappingSource
from sattline_parser.models.ast_model import (
    ParameterMapping,
    ScalarDatatype,
    SourceSpan,
    Variable,
)

from sattlint.analyzers.variables import IssueKind
from sattlint.analyzers.variables._variables_effect_flow import EffectFlowTracker
from sattlint.reporting.variables_report import (
    ALL_VARIABLE_ANALYSIS_KINDS,
    DatatypeDuplicationIssue,
    DuplicateLocation,
    FieldNeverReadIssue,
    FieldReadOnlyIssue,
    GlobalScopeMinimizationIssue,
    HiddenGlobalCouplingIssue,
    HighFanInOutIssue,
    ImplicitLatchIssue,
    MagicNumberIssue,
    MinMaxMappingMismatchIssue,
    NeverReadIssue,
    ProcedureStatusIssue,
    ReadOnlyNonConstIssue,
    ResetContaminationIssue,
    ShadowingIssue,
    StringMappingMismatchIssue,
    UnknownParameterTargetIssue,
    UnusedDatatypeFieldIssue,
    UnusedIssue,
    VariableIssue,
    VariablesReport,
    WriteWithoutEffectIssue,
)
from sattlint.resolution.scope import ScopeContext
from sattlint.types import VariableId
from tests.helpers.variable_test_support import varref as _varref


def test_variables_report_coerces_visible_kinds_and_handles_unknown_selector_kind():
    report = VariablesReport(
        basepicture_name="BasePicture",
        issues=[],
        visible_kinds=frozenset([IssueKind.UNUSED]),
    )

    assert isinstance(report.visible_kinds, frozenset)
    assert report._issues_for_kind(cast(Any, object())) == []


def test_variables_report_coerces_mutable_visible_kinds_to_frozenset():
    report = VariablesReport(
        basepicture_name="Dummy",
        issues=[],
        visible_kinds=[IssueKind.UNUSED],
    )

    assert report.visible_kinds == frozenset({IssueKind.UNUSED})


def test_variables_report_summary_formats_string_mapping_and_minmax_tables():
    string_source = Variable(name="SourceText", datatype=ScalarDatatype.STRING)
    string_target = Variable(name="TargetText", datatype=ScalarDatatype.TAGSTRING)
    min_source = Variable(name="SourceMin", datatype=ScalarDatatype.REAL)
    min_target = Variable(name="TargetMax", datatype=ScalarDatatype.REAL)
    report = VariablesReport(
        basepicture_name="BasePicture",
        issues=[
            StringMappingMismatchIssue(
                module_path=["BasePicture", "ChildA"],
                variable=string_target,
                source_variable=string_source,
                source_decl_module_path=["BasePicture", "ParentA"],
                source_role="localvariable",
            ),
            MinMaxMappingMismatchIssue(
                module_path=["BasePicture", "ChildB"],
                variable=min_target,
                source_variable=min_source,
            ),
        ],
    )

    summary = report.summary()

    assert "String mapping type mismatches" in summary
    assert "Min/Max mapping name mismatches" in summary
    assert "Source Var" in summary
    assert "Role" in summary
    assert "Declared Type" in summary
    assert "Destination Type" in summary
    assert "Declaration/final destination mismatch (1):" in summary
    assert "BasePicture.ChildA" in summary
    assert "SourceText" in summary
    assert "localvariable" in summary
    assert "tagstring" in summary
    assert "BasePicture.ChildB" in summary
    assert "SourceMin" in summary
    assert "TargetMax" in summary


def test_variables_report_summary_splits_minmax_moduletype_and_singlemodule_groups():
    min_source = Variable(name="SourceMin", datatype=ScalarDatatype.REAL)
    typedef_target = Variable(name="TypeMax", datatype=ScalarDatatype.REAL)
    singlemodule_target = Variable(name="InstanceMax", datatype=ScalarDatatype.REAL)
    report = VariablesReport(
        basepicture_name="BasePicture",
        issues=[
            MinMaxMappingMismatchIssue(
                module_path=["BasePicture", "TypeDef:PanelType"],
                variable=typedef_target,
                source_variable=min_source,
            ),
            MinMaxMappingMismatchIssue(
                module_path=["BasePicture", "TypeDef:Column", "L1", "L2", "Panel"],
                variable=singlemodule_target,
                source_variable=min_source,
            ),
        ],
    )

    summary = report.summary()

    assert "Min/Max mapping name mismatches" in summary
    assert "      Moduletype:" in summary
    assert "BasePicture.TypeDef:PanelType" in summary
    assert "      SingleModule:" in summary
    assert "BasePicture.Column.L1.L2.Panel" in summary
    assert "BasePicture.TypeDef:Column.L1.L2.Panel" not in summary


def test_variables_report_summary_splits_string_mapping_moduletype_and_singlemodule_groups():
    string_source = Variable(name="SourceText", datatype=ScalarDatatype.STRING)
    typedef_target = Variable(name="TypeTarget", datatype=ScalarDatatype.IDENTSTRING)
    singlemodule_target = Variable(name="InstanceTarget", datatype=ScalarDatatype.TAGSTRING)
    report = VariablesReport(
        basepicture_name="BasePicture",
        issues=[
            StringMappingMismatchIssue(
                module_path=["BasePicture", "TypeDef:PanelType"],
                variable=typedef_target,
                source_variable=string_source,
                source_decl_module_path=["BasePicture", "TypeDef:PanelType"],
                source_role="moduleparameter",
            ),
            StringMappingMismatchIssue(
                module_path=["BasePicture", "TypeDef:Column", "L1", "L2", "Panel"],
                variable=singlemodule_target,
                source_variable=string_source,
                source_decl_module_path=["BasePicture", "TypeDef:Column"],
                source_role="localvariable",
            ),
        ],
    )

    summary = report.summary()

    assert "String mapping type mismatches" in summary
    assert "      Moduletype:" in summary
    assert "Declaration/final destination mismatch (2):" in summary
    assert "Intermediate path mismatch only (0):" in summary
    assert "BasePicture.TypeDef:PanelType" in summary
    assert "BasePicture.TypeDef:Column.L1.L2.Panel" in summary
    assert "      SingleModule:" in summary
    assert "Declaration/final destination mismatch (0):" in summary


def test_variables_report_summary_dedupes_string_mapping_rows_by_source_variable_owner():
    shared_source = Variable(name="Name", datatype=ScalarDatatype.STRING)
    issues: list[VariableIssue] = [
        StringMappingMismatchIssue(
            module_path=["BasePicture", "TypeDef:EtOH_Conc", "L1", "L2", "TrendLog"],
            variable=Variable(name="TagSuffix", datatype=ScalarDatatype.IDENTSTRING),
            source_variable=shared_source,
            source_decl_module_path=["BasePicture", "TypeDef:EtOH_Conc"],
            source_role="localvariable",
        ),
        StringMappingMismatchIssue(
            module_path=["BasePicture", "TypeDef:EtOH_Conc", "L1", "L2", "CMP_AlarmPar"],
            variable=Variable(name="TagSuffix", datatype=ScalarDatatype.IDENTSTRING),
            source_variable=shared_source,
            source_decl_module_path=["BasePicture", "TypeDef:EtOH_Conc"],
            source_role="localvariable",
        ),
    ]

    summary = VariablesReport(basepicture_name="BasePicture", issues=issues).summary()

    assert "Issues: 2" in summary
    assert "String mapping type mismatches (2):" in summary
    assert "Declaration/final destination mismatch (2):" in summary
    assert "BasePicture.TypeDef:EtOH_Conc.L1.L2.TrendLog" in summary
    assert "BasePicture.TypeDef:EtOH_Conc.L1.L2.CMP_AlarmPar" in summary
    assert "Name" in summary
    assert "localvariable" in summary
    assert "identstring" in summary


def test_variables_report_summary_splits_string_mismatch_severity_by_declaration_vs_destination():
    declaration_match = StringMappingMismatchIssue(
        module_path=["BasePicture", "TypeDef:RelayType", "Leaf"],
        variable=Variable(name="FinalValue", datatype=ScalarDatatype.IDENTSTRING),
        source_variable=Variable(name="OriginalValue", datatype=ScalarDatatype.IDENTSTRING),
        source_decl_module_path=["BasePicture", "TypeDef:RelayType"],
        source_role="moduleparameter",
    )
    declaration_mismatch = StringMappingMismatchIssue(
        module_path=["BasePicture", "TypeDef:RelayType", "Alarm"],
        variable=Variable(name="EventTagPrefix", datatype=ScalarDatatype.TAGSTRING),
        source_variable=Variable(name="OriginalValue", datatype=ScalarDatatype.LINESTRING),
        source_decl_module_path=["BasePicture", "TypeDef:RelayType"],
        source_role="moduleparameter",
    )

    summary = VariablesReport(
        basepicture_name="BasePicture",
        issues=[declaration_match, declaration_mismatch],
    ).summary()

    assert "Declaration/final destination mismatch (1):" in summary
    assert "Intermediate path mismatch only (1):" in summary
    assert "tagstring" in summary
    assert "identstring" in summary


def test_variables_report_summary_renders_literal_string_mismatch_rows():
    literal_issue = StringMappingMismatchIssue(
        module_path=["BasePicture", "Child"],
        variable=Variable(name="TargetValue", datatype=ScalarDatatype.IDENTSTRING),
        source_variable=Variable(name="'LiteralText'", datatype=ScalarDatatype.STRING),
        source_decl_module_path=["BasePicture", "Child"],
        source_role="literal",
    )

    summary = VariablesReport(basepicture_name="BasePicture", issues=[literal_issue]).summary()

    assert "Issues: 1" in summary
    assert "Declaration/final destination mismatch (1):" in summary
    assert "'LiteralText'" in summary
    assert "literal" in summary
    assert "TargetValue" in summary
    assert "identstring" in summary


def test_variables_report_summary_formats_duplication_magic_numbers_and_sequence_context():
    duplicated = Variable(name="ValueA", datatype="SharedRecord")
    duplicated_typedef = Variable(name="ValueType", datatype="SharedRecord")
    implicit = Variable(name="Stage1", datatype=ScalarDatatype.BOOLEAN)
    issues: list[VariableIssue] = [
        DatatypeDuplicationIssue(
            module_path=["BasePicture", "TypeDef:PanelType"],
            variable=duplicated_typedef,
            role="localvariable",
            duplicate_count=2,
            duplicate_locations=[
                DuplicateLocation(
                    module_path=["BasePicture", "TypeDef:PanelType"],
                    role="moduleparameter",
                    variable_id=VariableId("ParamType"),
                )
            ],
        ),
        DatatypeDuplicationIssue(
            module_path=["BasePicture", "TypeDef:Column", "UnitA"],
            variable=duplicated,
            role="localvariable",
            duplicate_count=3,
            duplicate_locations=[
                DuplicateLocation(
                    module_path=["BasePicture", "TypeDef:Column", "UnitA"],
                    role="moduleparameter",
                    variable_id=VariableId("ValueB"),
                ),
                DuplicateLocation(
                    module_path=["BasePicture", "TypeDef:Column", "UnitB"],
                    role="localvariable",
                    variable_id=VariableId("ValueC"),
                ),
            ],
        ),
        MagicNumberIssue(
            module_path=["BasePicture", "TypeDef:Column", "UnitA"],
            literal_value=42,
            literal_span=SourceSpan(start=0, end=0, line=9, column=4),
            site="EquationBlock",
        ),
        ImplicitLatchIssue(
            module_path=["BasePicture", "SequenceA"],
            variable=implicit,
            role="localvariable",
            sequence_name="MainSeq",
            site="SEQ:MainSeq > STEP:One",
        ),
    ]
    report = VariablesReport(basepicture_name="BasePicture", issues=issues)
    summary = report.summary()

    assert "Duplicated complex datatypes (should be RECORD)" in summary
    assert "      Moduletype:" in summary
    assert "Datatype 'SharedRecord' declared 2 times in BasePicture.TypeDef:PanelType:" in summary
    assert "+ ParamType (moduleparameter)" in summary
    assert "      SingleModule:" in summary
    assert "Datatype 'SharedRecord' declared 3 times in BasePicture.Column.UnitA:" in summary
    assert "- ValueA (localvariable)" in summary
    assert "+ ValueB (moduleparameter)" in summary
    assert "+ BasePicture.Column.UnitB: ValueC (localvariable)" in summary
    assert "Magic numbers in code" in summary
    assert "BasePicture.Column.UnitA [EquationBlock] :: 42 (line 9, col 4)" in summary
    assert "Implicit latching (missing matching False writes)" in summary
    assert "BasePicture.SequenceA :: localvariable Stage1 (boolean) | sequence=MainSeq" in summary


def test_variables_report_summary_includes_shadowing_section():
    report = VariablesReport(
        basepicture_name="BasePicture",
        issues=[
            ShadowingIssue(
                module_path=["BasePicture", "TypeDef:Column", "ChildC"],
                variable=Variable(name="Mode", datatype=ScalarDatatype.INTEGER),
                role="local shadows moduleparameter",
            ),
        ],
        visible_kinds=frozenset(
            {
                IssueKind.SHADOWING,
            }
        ),
    )

    summary = report.summary()

    assert isinstance(report.visible_kinds, frozenset)
    assert "Variable shadowing" in summary
    assert "BasePicture.Column.ChildC :: Mode (integer) | local shadows moduleparameter" in summary


def test_variables_report_properties_visible_kinds_and_empty_sections_cover_remaining_branches():
    issues: list[VariableIssue] = [
        UnusedIssue(module_path=["BasePicture", "Unused"], variable=Variable("A", "integer")),
        UnusedDatatypeFieldIssue(
            module_path=["BasePicture", "Datatype"],
            datatype_name="Payload",
            field_path="FieldA",
        ),
        FieldReadOnlyIssue(
            module_path=["BasePicture", "FieldReadOnly"],
            variable=Variable("PayloadA", "Payload"),
            field_path="Std",
        ),
        ReadOnlyNonConstIssue(
            module_path=["BasePicture", "ReadOnly"],
            variable=Variable("B", "integer"),
        ),
        ProcedureStatusIssue(
            module_path=["BasePicture", "Procedure"],
            variable=Variable("OperationStatus", "integer"),
        ),
        FieldNeverReadIssue(
            module_path=["BasePicture", "FieldNeverRead"],
            variable=Variable("PayloadB", "Payload"),
            field_path="Std",
        ),
        NeverReadIssue(
            module_path=["BasePicture", "NeverRead"],
            variable=Variable("WrittenOnly", "integer"),
        ),
        WriteWithoutEffectIssue(
            module_path=["BasePicture", "WriteOnly"],
            variable=Variable("NoEffect", "integer"),
        ),
        GlobalScopeMinimizationIssue(
            module_path=["BasePicture", "Global"],
            variable=Variable("GlobalA", "integer"),
        ),
        HiddenGlobalCouplingIssue(
            module_path=["BasePicture", "Coupling"],
            variable=Variable("SharedState", "integer"),
        ),
        HighFanInOutIssue(
            module_path=["BasePicture", "Fan"],
            variable=Variable("Busy", "boolean"),
            role="fan-out exceeds threshold",
        ),
        UnknownParameterTargetIssue(
            module_path=["BasePicture", "Mapping"],
            role="unknown target parameter 'Mode'",
        ),
        StringMappingMismatchIssue(
            module_path=["BasePicture", "Strings"],
            variable=Variable("TargetText", ScalarDatatype.TAGSTRING),
            source_variable=Variable("SourceText", ScalarDatatype.STRING),
        ),
        DatatypeDuplicationIssue(
            module_path=["BasePicture", "Dup"],
            variable=Variable("LocalA", "Payload"),
            role="localvariable",
            duplicate_count=2,
            duplicate_locations=[
                DuplicateLocation(
                    module_path=["BasePicture", "Dup"],
                    role="moduleparameter",
                    variable_id=VariableId("ParamA"),
                )
            ],
        ),
        MinMaxMappingMismatchIssue(
            module_path=["BasePicture", "MinMax"],
            variable=Variable("TargetMax", ScalarDatatype.REAL),
            source_variable=Variable("SourceMin", ScalarDatatype.REAL),
        ),
        MagicNumberIssue(
            module_path=["BasePicture", "Magic"],
            literal_value=7,
            literal_span=SourceSpan(start=0, end=0, line=12, column=8),
            site="EquationBlock",
        ),
        ResetContaminationIssue(
            module_path=["BasePicture", "Reset"],
            variable=Variable("Counter", "integer"),
        ),
        ImplicitLatchIssue(
            module_path=["BasePicture", "Latch"],
            variable=Variable("State", ScalarDatatype.BOOLEAN),
            role="localvariable",
            sequence_name="SeqA",
            site="SEQ:SeqA > STEP:One",
        ),
    ]
    report = VariablesReport(
        basepicture_name="BasePicture",
        issues=issues,
        visible_kinds=frozenset((*ALL_VARIABLE_ANALYSIS_KINDS, IssueKind.SHADOWING)),
    )

    selector_expectations = {
        "unused": 1,
        "unused_datatype_fields": 1,
        "field_read_only": 1,
        "read_only_non_const": 1,
        "procedure_status": 1,
        "field_never_read": 1,
        "never_read": 1,
        "write_without_effect": 1,
        "global_scope_minimization": 1,
        "hidden_global_coupling": 1,
        "high_fan_in_out": 1,
        "unknown_parameter_targets": 1,
        "string_mapping_mismatch": 1,
        "datatype_duplication": 1,
        "min_max_mapping_mismatch": 1,
        "magic_numbers": 1,
        "shadowing": 0,
        "reset_contamination": 1,
        "implicit_latches": 1,
    }

    for attr_name, expected_count in selector_expectations.items():
        assert len(getattr(report, attr_name)) == expected_count

    summary = report.summary()

    assert report.name == "BasePicture"
    assert summary.startswith("Report: Variable issues")
    assert "Status: issues" in summary
    assert "Variable shadowing: 0" in summary
    assert "Read-only fields" in summary
    assert "Read-only but not Const variables" in summary
    assert "Written but never read fields" in summary
    assert "Procedure status handling" in summary
    assert "Written but never read variables" in summary
    assert "Write-without-effect variables" in summary
    assert "Global scope minimization candidates" in summary
    assert "Hidden global coupling" in summary
    assert "High fan-in or fan-out variables" in summary
    assert "Reset contamination (missing reset writes)" in summary
    assert "Warning: fields that are only consumed outside the analyzed target may still appear unused here." in summary
    assert "      none" in summary


def test_variables_report_summary_returns_ok_when_no_issues_are_present():
    summary = VariablesReport(basepicture_name="BasePicture", issues=[]).summary()

    assert "Status: ok" in summary
    assert summary.endswith("No issues found.")


def test_variables_report_summary_includes_metadata_and_init_values():
    summary = VariablesReport(
        basepicture_name="BasePicture",
        issues=[
            UnusedIssue(
                module_path=["BasePicture"],
                variable=Variable(name="Timeout", datatype=ScalarDatatype.INTEGER, init_value=10),
                role="moduleparameter",
            )
        ],
        analyzed_version="draft",
        last_changed="2024-05-17",
    ).summary()

    assert "Version: draft" in summary
    assert "Last changed: 2024-05-17" in summary
    assert "BasePicture :: moduleparameter Timeout (integer, init=10)" in summary


def test_effect_flow_tracker_computes_effective_outputs_via_reverse_edges():
    edges = {
        ("root", "source"): {("root", "mid")},
        ("root", "mid"): {("root", "sink")},
    }
    tracker = EffectFlowTracker(
        effect_flow_edges=edges,
        effect_flow_display_names={},
        external_effect_sinks=set(),
        effective_output_keys=set(),
        lookup_global_variable_fn=lambda _name: None,
        get_usage_fn=lambda _var: None,
        canonical_path_fn=lambda _path, _var, _field: None,
        record_access_fn=lambda _kind, _path, _ctx, _ref: None,
    )

    effective = tracker.compute_effective_output_keys({("root", "sink")})

    assert effective == {
        ("root", "source"),
        ("root", "mid"),
        ("root", "sink"),
    }


def test_effect_flow_tracker_copyvariable_inputs_only_include_source():
    source = Variable(name="Source", datatype=ScalarDatatype.INTEGER)
    target = Variable(name="Target", datatype=ScalarDatatype.INTEGER)
    context = ScopeContext(
        env={"source": source, "target": target},
        param_mappings={},
        module_path=["Root"],
        display_module_path=["Root"],
        parent_context=None,
    )
    tracker = EffectFlowTracker(
        effect_flow_edges={},
        effect_flow_display_names={},
        external_effect_sinks=set(),
        effective_output_keys=set(),
        lookup_global_variable_fn=lambda _name: None,
        get_usage_fn=lambda _var: None,
        canonical_path_fn=lambda _path, _var, _field: None,
        record_access_fn=lambda _kind, _path, _ctx, _ref: None,
    )

    collect_input_effect_keys = tracker.collect_function_input_effect_keys
    source_target_args = [_varref("Source"), _varref("Target")]
    target_source_args = [_varref("Target"), _varref("Source")]
    sources = collect_input_effect_keys("CopyVariable", source_target_args, context)
    init_sources = collect_input_effect_keys("InitVariable", target_source_args, context)
    assert sources == {("root", "source")}
    assert init_sources == {("root", "source")}


def test_effect_flow_tracker_global_mapping_uses_lookup_fallback():
    resolved_global = Variable(name="ResolvedGlobal", datatype=ScalarDatatype.INTEGER)
    tracker = EffectFlowTracker(
        effect_flow_edges={},
        effect_flow_display_names={},
        external_effect_sinks=set(),
        effective_output_keys=set(),
        lookup_global_variable_fn=lambda name: resolved_global if name == "GlobalSource" else None,
        get_usage_fn=lambda _var: None,
        canonical_path_fn=lambda _path, _var, _field: None,
        record_access_fn=lambda _kind, _path, _ctx, _ref: None,
    )

    key = tracker.mapping_source_effect_key(
        ParameterMapping(
            target=_varref("Input"),
            source_type=MappingSource.VARIABLE,
            is_duration=False,
            is_source_global=True,
            source=_varref("GlobalSource"),
            source_literal=None,
        ),
        parent_env={},
        parent_context=None,
    )

    assert key == ("globalsource", "resolvedglobal")


def test_effect_flow_tracker_records_copyvariable_output_edge():
    from collections import defaultdict  # noqa: PLC0415

    edges: defaultdict[tuple[str, ...], set[tuple[str, ...]]] = defaultdict(set)
    source = Variable(name="Source", datatype=ScalarDatatype.INTEGER)
    target = Variable(name="Target", datatype=ScalarDatatype.INTEGER)
    context = ScopeContext(
        env={"source": source, "target": target},
        param_mappings={},
        module_path=["Root"],
        display_module_path=["Root"],
        parent_context=None,
    )
    tracker = EffectFlowTracker(
        effect_flow_edges=edges,
        effect_flow_display_names={},
        external_effect_sinks=set(),
        effective_output_keys=set(),
        lookup_global_variable_fn=lambda _name: None,
        get_usage_fn=lambda _var: None,
        canonical_path_fn=lambda _path, _var, _field: None,
        record_access_fn=lambda _kind, _path, _ctx, _ref: None,
    )

    tracker.record_function_call_effect_flow(
        "CopyVariable",
        [_varref("Source"), _varref("Target")],
        context,
    )

    assert edges == {("root", "source"): {("root", "target")}}
