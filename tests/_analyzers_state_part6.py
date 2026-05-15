# ruff: noqa: F403, F405
from ._analyzers_state_test_support import *


def test_variables_report_coerces_visible_kinds_and_handles_unknown_selector_kind():
    report = VariablesReport(
        basepicture_name="BasePicture",
        issues=[],
        visible_kinds=frozenset([IssueKind.UNUSED]),
    )

    assert isinstance(report.visible_kinds, frozenset)
    assert report._issues_for_kind(cast(Any, object())) == []


def test_variables_report_summary_formats_string_mapping_and_minmax_tables():
    string_source = Variable(name="SourceText", datatype=Simple_DataType.STRING)
    string_target = Variable(name="TargetText", datatype=Simple_DataType.TAGSTRING)
    min_source = Variable(name="SourceMin", datatype=Simple_DataType.REAL)
    min_target = Variable(name="TargetMax", datatype=Simple_DataType.REAL)
    report = VariablesReport(
        basepicture_name="BasePicture",
        issues=[
            VariableIssue(
                kind=IssueKind.STRING_MAPPING_MISMATCH,
                module_path=["BasePicture", "ChildA"],
                variable=string_target,
                source_variable=string_source,
            ),
            VariableIssue(
                kind=IssueKind.MIN_MAX_MAPPING_MISMATCH,
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
    assert "Target Var" in summary
    assert "BasePicture.ChildA" in summary
    assert "SourceText" in summary
    assert "TargetText" in summary
    assert "BasePicture.ChildB" in summary
    assert "SourceMin" in summary
    assert "TargetMax" in summary


def test_variables_report_summary_formats_duplication_magic_numbers_and_sequence_context():
    duplicated = Variable(name="ValueA", datatype="SharedRecord")
    implicit = Variable(name="Stage1", datatype=Simple_DataType.BOOLEAN)
    report = VariablesReport(
        basepicture_name="BasePicture",
        issues=[
            VariableIssue(
                kind=IssueKind.DATATYPE_DUPLICATION,
                module_path=["BasePicture", "UnitA"],
                variable=duplicated,
                role="localvariable",
                duplicate_count=3,
                duplicate_locations=[
                    (["BasePicture", "UnitA"], "moduleparameter", VariableId("ValueB")),
                    (["BasePicture", "UnitB"], "localvariable", VariableId("ValueC")),
                ],
            ),
            VariableIssue(
                kind=IssueKind.MAGIC_NUMBER,
                module_path=["BasePicture", "UnitA"],
                variable=None,
                literal_value=42,
                literal_span=SourceSpan(line=9, column=4),
                site="EquationBlock",
            ),
            VariableIssue(
                kind=IssueKind.IMPLICIT_LATCH,
                module_path=["BasePicture", "SequenceA"],
                variable=implicit,
                role="localvariable",
                sequence_name="MainSeq",
                reset_variable=VariableId("ResetCmd"),
            ),
        ],
    )

    summary = report.summary()

    assert "Duplicated complex datatypes (should be RECORD)" in summary
    assert "Datatype 'SharedRecord' declared 3 times in BasePicture.UnitA:" in summary
    assert "- ValueA (localvariable)" in summary
    assert "+ ValueB (moduleparameter)" in summary
    assert "+ BasePicture.UnitB: ValueC (localvariable)" in summary
    assert "Magic numbers in code" in summary
    assert "BasePicture.UnitA [EquationBlock] :: 42 (line 9, col 4)" in summary
    assert "Implicit latching (missing matching False writes)" in summary
    assert "BasePicture.SequenceA :: localvariable Stage1 (boolean) | sequence=MainSeq | reset=ResetCmd" in summary


def test_variables_report_summary_includes_required_contract_layout_and_shadowing_sections():
    report = VariablesReport(
        basepicture_name="BasePicture",
        issues=[
            VariableIssue(
                kind=IssueKind.REQUIRED_PARAMETER_CONNECTION,
                module_path=["BasePicture", "ChildA"],
                variable=None,
                role="required parameter 'Mode' is not connected",
            ),
            VariableIssue(
                kind=IssueKind.CONTRACT_MISMATCH,
                module_path=["BasePicture", "ChildB"],
                variable=Variable(name="TargetValue", datatype=Simple_DataType.INTEGER),
                source_variable=Variable(name="SourceValue", datatype=Simple_DataType.REAL),
                role="source and target types differ",
            ),
            VariableIssue(
                kind=IssueKind.LAYOUT_OVERLAP,
                module_path=["BasePicture", "Panel"],
                variable=None,
                role="TextA overlaps TextB",
            ),
            VariableIssue(
                kind=IssueKind.SHADOWING,
                module_path=["BasePicture", "ChildC"],
                variable=Variable(name="Mode", datatype=Simple_DataType.INTEGER),
                role="local shadows moduleparameter",
            ),
        ],
        visible_kinds=frozenset(
            {
                IssueKind.REQUIRED_PARAMETER_CONNECTION,
                IssueKind.CONTRACT_MISMATCH,
                IssueKind.LAYOUT_OVERLAP,
                IssueKind.SHADOWING,
            }
        ),
    )

    summary = report.summary()

    assert isinstance(report.visible_kinds, frozenset)
    assert "Missing required parameter connections" in summary
    assert "BasePicture.ChildA :: required parameter 'Mode' is not connected" in summary
    assert "Cross-module contract mismatches" in summary
    assert "BasePicture.ChildB :: TargetValue (integer) | source and target types differ" in summary
    assert "Overlapping layout elements" in summary
    assert "BasePicture.Panel :: TextA overlaps TextB" in summary
    assert "Variable shadowing" in summary
    assert "BasePicture.ChildC :: Mode (integer) | local shadows moduleparameter" in summary


def test_variables_report_properties_visible_kinds_and_empty_sections_cover_remaining_branches():
    issues = [
        VariableIssue(kind=IssueKind.UNUSED, module_path=["BasePicture", "Unused"], variable=Variable("A", "integer")),
        VariableIssue(
            kind=IssueKind.UNUSED_DATATYPE_FIELD,
            module_path=["BasePicture", "Datatype"],
            variable=None,
            datatype_name="Payload",
            field_path="FieldA",
        ),
        VariableIssue(
            kind=IssueKind.READ_ONLY_NON_CONST,
            module_path=["BasePicture", "ReadOnly"],
            variable=Variable("B", "integer"),
        ),
        VariableIssue(
            kind=IssueKind.NAMING_ROLE_MISMATCH,
            module_path=["BasePicture", "Naming"],
            variable=Variable("ValveStatus", "boolean"),
            role="name suggests state but only drives command",
        ),
        VariableIssue(
            kind=IssueKind.UI_ONLY,
            module_path=["BasePicture", "Display"],
            variable=Variable("Caption", Simple_DataType.STRING),
        ),
        VariableIssue(
            kind=IssueKind.PROCEDURE_STATUS,
            module_path=["BasePicture", "Procedure"],
            variable=Variable("OperationStatus", "integer"),
        ),
        VariableIssue(
            kind=IssueKind.NEVER_READ,
            module_path=["BasePicture", "NeverRead"],
            variable=Variable("WrittenOnly", "integer"),
        ),
        VariableIssue(
            kind=IssueKind.WRITE_WITHOUT_EFFECT,
            module_path=["BasePicture", "WriteOnly"],
            variable=Variable("NoEffect", "integer"),
        ),
        VariableIssue(
            kind=IssueKind.GLOBAL_SCOPE_MINIMIZATION,
            module_path=["BasePicture", "Global"],
            variable=Variable("GlobalA", "integer"),
        ),
        VariableIssue(
            kind=IssueKind.HIDDEN_GLOBAL_COUPLING,
            module_path=["BasePicture", "Coupling"],
            variable=Variable("SharedState", "integer"),
        ),
        VariableIssue(
            kind=IssueKind.HIGH_FAN_IN_OUT,
            module_path=["BasePicture", "Fan"],
            variable=Variable("Busy", "boolean"),
            role="fan-out exceeds threshold",
        ),
        VariableIssue(
            kind=IssueKind.UNKNOWN_PARAMETER_TARGET,
            module_path=["BasePicture", "Mapping"],
            variable=None,
            role="unknown target parameter 'Mode'",
        ),
        VariableIssue(
            kind=IssueKind.REQUIRED_PARAMETER_CONNECTION,
            module_path=["BasePicture", "Required"],
            variable=None,
            role="required parameter 'Enable' is not connected",
        ),
        VariableIssue(
            kind=IssueKind.CONTRACT_MISMATCH,
            module_path=["BasePicture", "Contract"],
            variable=Variable("Target", Simple_DataType.INTEGER),
            source_variable=Variable("Source", Simple_DataType.REAL),
            role="contract mismatch",
        ),
        VariableIssue(
            kind=IssueKind.STRING_MAPPING_MISMATCH,
            module_path=["BasePicture", "Strings"],
            variable=Variable("TargetText", Simple_DataType.TAGSTRING),
            source_variable=Variable("SourceText", Simple_DataType.STRING),
        ),
        VariableIssue(
            kind=IssueKind.DATATYPE_DUPLICATION,
            module_path=["BasePicture", "Dup"],
            variable=Variable("LocalA", "Payload"),
            role="localvariable",
            duplicate_count=2,
            duplicate_locations=[(["BasePicture", "Dup"], "moduleparameter", VariableId("ParamA"))],
        ),
        VariableIssue(
            kind=IssueKind.MIN_MAX_MAPPING_MISMATCH,
            module_path=["BasePicture", "MinMax"],
            variable=Variable("TargetMax", Simple_DataType.REAL),
            source_variable=Variable("SourceMin", Simple_DataType.REAL),
        ),
        VariableIssue(
            kind=IssueKind.MAGIC_NUMBER,
            module_path=["BasePicture", "Magic"],
            variable=None,
            literal_value=7,
            literal_span=SourceSpan(12, 8),
            site="EquationBlock",
        ),
        VariableIssue(
            kind=IssueKind.LAYOUT_OVERLAP,
            module_path=["BasePicture", "Layout"],
            variable=None,
            role="LabelA overlaps LabelB",
        ),
        VariableIssue(
            kind=IssueKind.RESET_CONTAMINATION,
            module_path=["BasePicture", "Reset"],
            variable=Variable("Counter", "integer"),
        ),
        VariableIssue(
            kind=IssueKind.IMPLICIT_LATCH,
            module_path=["BasePicture", "Latch"],
            variable=Variable("State", Simple_DataType.BOOLEAN),
            role="localvariable",
            sequence_name="SeqA",
            reset_variable=VariableId("ResetCmd"),
        ),
    ]
    report = VariablesReport(
        basepicture_name="BasePicture",
        issues=issues,
        visible_kinds=frozenset((*ALL_VARIABLE_ANALYSIS_KINDS, IssueKind.NAME_COLLISION, IssueKind.SHADOWING)),
    )

    selector_expectations = {
        "unused": 1,
        "unused_datatype_fields": 1,
        "read_only_non_const": 1,
        "naming_role_mismatch": 1,
        "ui_only": 1,
        "procedure_status": 1,
        "never_read": 1,
        "write_without_effect": 1,
        "global_scope_minimization": 1,
        "hidden_global_coupling": 1,
        "high_fan_in_out": 1,
        "unknown_parameter_targets": 1,
        "required_parameter_connections": 1,
        "contract_mismatches": 1,
        "string_mapping_mismatch": 1,
        "datatype_duplication": 1,
        "min_max_mapping_mismatch": 1,
        "magic_numbers": 1,
        "name_collisions": 0,
        "layout_overlaps": 1,
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
    assert "Name collisions: 0" in summary
    assert "Variable shadowing: 0" in summary
    assert "Read-only but not Const variables" in summary
    assert "Naming-to-behavior mismatches" in summary
    assert "UI/display-only variables" in summary
    assert "Procedure status handling" in summary
    assert "Written but never read variables" in summary
    assert "Write-without-effect variables" in summary
    assert "Global scope minimization candidates" in summary
    assert "Hidden global coupling" in summary
    assert "High fan-in or fan-out variables" in summary
    assert "Reset contamination (missing reset writes)" in summary
    assert "      none" in summary


def test_variables_report_summary_returns_ok_when_no_issues_are_present():
    summary = VariablesReport(basepicture_name="BasePicture", issues=[]).summary()

    assert "Status: ok" in summary
    assert summary.endswith("No issues found.")


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
    source = Variable(name="Source", datatype=Simple_DataType.INTEGER)
    target = Variable(name="Target", datatype=Simple_DataType.INTEGER)
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
    resolved_global = Variable(name="ResolvedGlobal", datatype=Simple_DataType.INTEGER)
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
            source_type=const.TREE_TAG_VARIABLE_NAME,
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
    from collections import defaultdict

    edges = defaultdict(set)
    source = Variable(name="Source", datatype=Simple_DataType.INTEGER)
    target = Variable(name="Target", datatype=Simple_DataType.INTEGER)
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
