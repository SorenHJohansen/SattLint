# Wave 1 Audit

Static audit generated from the current `src/**` tree.

Heuristics used:

- Dataclasses: flagged as `candidate-frozen` only when the class is not already frozen, has no obvious mutable-typed fields or mutable defaults, and has no `self` writes outside `__init__`.
- Optional returns: grouped into `genuinely-nullable`, `boundary-fallback`, `sentinel-none`, and `review` using AST return-shape plus name-based hints. `review` means the static pass was not confident enough to collapse it into the other buckets.

## Summary

| Audit | Count |
| --- | --- |
| Dataclasses scanned | 163 |
| Optional-return functions scanned | 115 |

### Dataclass status counts

| Status | Count |
| --- | --- |
| already-frozen | 100 |
| candidate-frozen | 10 |
| manual-review | 50 |
| mutable-after-construction | 3 |

### Optional-return category counts

| Category | Count |
| --- | --- |
| boundary-fallback | 17 |
| genuinely-nullable | 29 |
| review | 61 |
| sentinel-none | 8 |

## Dataclass Audit

Only non-frozen dataclasses are listed below because already-frozen entries are already closed for this refactor item.

| Path | Class | Status | Reason |
| --- | --- | --- | --- |
| src/sattline_parser/models/ast_model.py | Variable | manual-review | __post_init__ present |
| src/sattline_parser/models/ast_model.py | DataType | mutable-after-construction | assigns to self outside __init__: mark_read, mark_written |
| src/sattline_parser/models/ast_model.py | ParameterMapping | manual-review | mutable-typed fields |
| src/sattline_parser/models/ast_model.py | GraphObject | manual-review | mutable-typed fields |
| src/sattline_parser/models/ast_model.py | InteractObject | manual-review | mutable-typed fields |
| src/sattline_parser/models/ast_model.py | ModuleDef | manual-review | mutable-typed fields |
| src/sattline_parser/models/ast_model.py | Sequence | manual-review | mutable-typed fields |
| src/sattline_parser/models/ast_model.py | Equation | manual-review | mutable-typed fields |
| src/sattline_parser/models/ast_model.py | ModuleCode | manual-review | mutable-typed fields |
| src/sattline_parser/models/ast_model.py | ModuleHeader | manual-review | mutable-typed fields |
| src/sattline_parser/models/ast_model.py | SingleModule | manual-review | mutable-typed fields |
| src/sattline_parser/models/ast_model.py | FrameModule | manual-review | mutable-typed fields |
| src/sattline_parser/models/ast_model.py | ModuleTypeInstance | manual-review | mutable-typed fields |
| src/sattline_parser/models/ast_model.py | ModuleTypeDef | manual-review | mutable-typed fields |
| src/sattline_parser/models/ast_model.py | BasePicture | manual-review | mutable-typed fields |
| src/sattline_parser/models/ast_model.py | SFCCodeBlocks | manual-review | mutable-typed fields |
| src/sattline_parser/models/ast_model.py | SFCStep | candidate-frozen | no self mutation outside __init__ and no obvious mutable fields |
| src/sattline_parser/models/ast_model.py | SFCTransition | candidate-frozen | no self mutation outside __init__ and no obvious mutable fields |
| src/sattline_parser/models/ast_model.py | SFCAlternative | manual-review | mutable-typed fields |
| src/sattline_parser/models/ast_model.py | SFCParallel | manual-review | mutable-typed fields |
| src/sattline_parser/models/ast_model.py | SFCSubsequence | manual-review | mutable-typed fields |
| src/sattline_parser/models/ast_model.py | SFCTransitionSub | manual-review | mutable-typed fields |
| src/sattline_parser/models/ast_model.py | SFCFork | candidate-frozen | no self mutation outside __init__ and no obvious mutable fields |
| src/sattline_parser/models/ast_model.py | SFCBreak | candidate-frozen | no self mutation outside __init__ and no obvious mutable fields |
| src/sattlint/analyzers/alarm_integrity.py | AlarmIntegrityReport | manual-review | mutable-typed fields |
| src/sattlint/analyzers/framework.py | SimpleReport | manual-review | mutable-typed fields |
| src/sattlint/analyzers/initial_values.py | InitialValueReport | manual-review | mutable-typed fields |
| src/sattlint/analyzers/modules.py | ModuleFingerprint | manual-review | mutable-typed fields |
| src/sattlint/analyzers/modules.py | VariableDiff | manual-review | mutable-typed fields |
| src/sattlint/analyzers/modules.py | SubmoduleDiff | manual-review | mutable-typed fields |
| src/sattlint/analyzers/modules.py | CodeDiff | manual-review | mutable-typed fields |
| src/sattlint/analyzers/modules.py | ComparisonResult | manual-review | mutable-typed fields |
| src/sattlint/analyzers/modules.py | VersionDriftReport | manual-review | mutable-typed fields |
| src/sattlint/analyzers/naming.py | NamingConsistencyReport | manual-review | mutable-typed fields |
| src/sattlint/analyzers/reset_contamination.py | _PathState | candidate-frozen | no self mutation outside __init__ and no obvious mutable fields |
| src/sattlint/analyzers/reset_contamination.py | _BooleanPathState | candidate-frozen | no self mutation outside __init__ and no obvious mutable fields |
| src/sattlint/analyzers/safety_paths.py | SafetyPathReport | manual-review | mutable-typed fields |
| src/sattlint/analyzers/sattline_builtins.py | Parameter | candidate-frozen | no self mutation outside __init__ and no obvious mutable fields |
| src/sattlint/analyzers/sattline_builtins.py | BuiltinFunction | manual-review | mutable-typed fields |
| src/sattlint/analyzers/sattline_semantics.py | SattLineSemanticsReport | manual-review | mutable-typed fields |
| src/sattlint/analyzers/sfc.py | _ParallelMeta | manual-review | mutable-typed fields |
| src/sattlint/analyzers/taint_paths.py | TaintPathReport | manual-review | mutable-typed fields |
| src/sattlint/analyzers/unsafe_defaults.py | UnsafeDefaultsReport | manual-review | mutable-typed fields |
| src/sattlint/devtools/pipeline.py | CommandResult | manual-review | mutable-typed fields |
| src/sattlint/devtools/progress_reporting.py | ProgressStage | candidate-frozen | no self mutation outside __init__ and no obvious mutable fields |
| src/sattlint/devtools/repo_audit.py | Finding | candidate-frozen | no self mutation outside __init__ and no obvious mutable fields |
| src/sattlint/docgenerator/classification.py | DocumentationScope | manual-review | mutable-typed fields |
| src/sattlint/docgenerator/classification.py | DocumentationClassification | manual-review | mutable-typed fields |
| src/sattlint/docgenerator/configgen.py | ComponentInfo | manual-review | mutable-typed fields |
| src/sattlint/docgenerator/configgen.py | ConfigurationFileInfo | manual-review | mutable-typed fields |
| src/sattlint/models/project_graph.py | ProjectGraph | manual-review | mutable-typed fields |
| src/sattlint/models/usage.py | VariableUsage | mutable-after-construction | assigns to self outside __init__: mark_field_read, mark_field_written, mark_read, mark_written |
| src/sattlint/reporting/comment_code_report.py | CommentCodeReport | manual-review | mutable-typed fields |
| src/sattlint/reporting/icf_report.py | ICFValidationReport | manual-review | mutable-typed fields |
| src/sattlint/reporting/mms_report.py | MMSInterfaceReport | manual-review | mutable-typed fields |
| src/sattlint/reporting/variables_report.py | VariableIssue | manual-review | mutable-typed fields |
| src/sattlint/reporting/variables_report.py | VariablesReport | manual-review | mutable-typed fields; __post_init__ present |
| src/sattlint/resolution/access_graph.py | AccessGraph | manual-review | mutable-typed fields |
| src/sattlint/resolution/scope.py | ScopeContext | manual-review | mutable-typed fields |
| src/sattlint/resolution/symbol_table.py | CanonicalSymbolTable | manual-review | mutable-typed fields |
| src/sattlint/tracing.py | AnalysisTraceRecorder | manual-review | mutable-typed fields |
| src/sattlint_lsp/document_state.py | DocumentState | mutable-after-construction | assigns to self outside __init__: apply_changes, clear_analysis, clear_local_snapshot, preserve_analysis_result, remember_analysis, remember_local_snapshot, replace_text |
| src/sattlint_lsp/workspace_store.py | _EntrySnapshotState | candidate-frozen | no self mutation outside __init__ and no obvious mutable fields |

## Optional Return Triage

### sentinel-none

| Path | Function | Return annotation | Reason |
| --- | --- | --- | --- |
| src/sattlint/app_graphics.py | prompt_optional_float_list | list[float] \| None | name suggests optional/cancel/input sentinel |
| src/sattlint/app_graphics.py | prompt_optional_text_list | list[str] \| None | name suggests optional/cancel/input sentinel |
| src/sattlint/app_graphics.py | prompt_optional_bool | bool \| None | name suggests optional/cancel/input sentinel |
| src/sattlint/app_graphics.py | prompt_graphics_rule_definition_with_config | dict[str, Any] \| None | name suggests optional/cancel/input sentinel |
| src/sattlint/contracts/findings.py | _coerce_int | int \| None | name suggests optional/cancel/input sentinel |
| src/sattlint/contracts/findings.py | _coerce_str | str \| None | name suggests optional/cancel/input sentinel |
| src/sattlint/devtools/corpus.py | _coerce_optional_str | str \| None | name suggests optional/cancel/input sentinel |
| src/sattlint/devtools/corpus.py | _resolve_optional_directory | Path \| None | name suggests optional/cancel/input sentinel |

### review

| Path | Function | Return annotation | Reason |
| --- | --- | --- | --- |
| src/sattline_parser/transformer/sl_transformer.py | _meta_span | SourceSpan \| None | mixed None and value returns without clear lookup/sentinel naming |
| src/sattlint/analyzers/icf.py | _normalize_group_name | str \| None | mixed None and value returns without clear lookup/sentinel naming |
| src/sattlint/analyzers/icf.py | _extract_icf_sattline_ref | tuple[str \| None, str \| None] | annotated nullable but no explicit None return found |
| src/sattlint/analyzers/icf.py | _resolve_icf_path | tuple[ResolvedModulePath \| None, Variable \| None, list[str]] | annotated nullable but no explicit None return found |
| src/sattlint/analyzers/icf.py | _validate_field_path | tuple[bool, str \| None] | annotated nullable but no explicit None return found |
| src/sattlint/analyzers/loop_output_refactor.py | _root_variable_key | str \| None | mixed None and value returns without clear lookup/sentinel naming |
| src/sattlint/analyzers/mms.py | _datatype_label | str \| None | mixed None and value returns without clear lookup/sentinel naming |
| src/sattlint/analyzers/mms.py | _normalize_external_tag | str \| None | mixed None and value returns without clear lookup/sentinel naming |
| src/sattlint/analyzers/mms.py | _tag_family_key | str \| None | mixed None and value returns without clear lookup/sentinel naming |
| src/sattlint/analyzers/mms.py | _resolve_source_details | tuple[str \| None, str \| None] | annotated nullable but no explicit None return found |
| src/sattlint/analyzers/mms.py | _best_icf_validation_report | Any \| None | annotated nullable but no explicit None return found |
| src/sattlint/analyzers/modules.py | _compact_diff | dict[str, Any] \| None | mixed None and value returns without clear lookup/sentinel naming |
| src/sattlint/analyzers/naming.py | _infer_expected_style | str \| None | mixed None and value returns without clear lookup/sentinel naming |
| src/sattlint/analyzers/reset_contamination.py | _literal_boolean | bool \| None | mixed None and value returns without clear lookup/sentinel naming |
| src/sattlint/analyzers/reset_contamination.py | _varref_casefold | str \| None | mixed None and value returns without clear lookup/sentinel naming |
| src/sattlint/analyzers/rule_profiles.py | _resolve_issue_rule | SemanticRule \| None | annotated nullable but no explicit None return found |
| src/sattlint/analyzers/rule_profiles.py | apply_rule_profile_to_issue | Any \| None | mixed None and value returns without clear lookup/sentinel naming |
| src/sattlint/analyzers/sattline_builtins.py | get_function_signature | BuiltinFunction \| None | annotated nullable but no explicit None return found |
| src/sattlint/analyzers/sattline_semantics.py | get_rule_for_framework_issue_kind | SemanticRule \| None | annotated nullable but no explicit None return found |
| src/sattlint/analyzers/sfc.py | _signature_literal_value | bool \| int \| float \| str \| None | mixed None and value returns without clear lookup/sentinel naming |
| src/sattlint/analyzers/sfc.py | _compare_literal_values | bool \| None | mixed None and value returns without clear lookup/sentinel naming |
| src/sattlint/analyzers/sfc.py | _guard_constant_truth | bool \| None | mixed None and value returns without clear lookup/sentinel naming |
| src/sattlint/app.py | _prompt_graphics_rule_definition | dict[str, Any] \| None | annotated nullable but no explicit None return found |
| src/sattlint/app.py | _prompt_graphics_rule_definition_with_config | dict[str, Any] \| None | annotated nullable but no explicit None return found |
| src/sattlint/app_graphics.py | prompt_graphics_rule_definition | dict[str, Any] \| None | annotated nullable but no explicit None return found |
| src/sattlint/core/semantic.py | _format_datatype | str \| None | mixed None and value returns without clear lookup/sentinel naming |
| src/sattlint/core/semantic.py | _first_branch_under | str \| None | mixed None and value returns without clear lookup/sentinel naming |
| src/sattlint/core/semantic.py | _source_file_key | str \| None | mixed None and value returns without clear lookup/sentinel naming |
| src/sattlint/core/semantic.py | _build_lsp_workspace_lookup | Callable[[str, list[str], Path \| None, str], Path \| None] | annotated nullable but no explicit None return found |
| src/sattlint/devtools/artifact_registry.py | artifact_reports_map | dict[str, str \| None] | annotated nullable but no explicit None return found |
| src/sattlint/devtools/baselines.py | _finding_anchor | tuple[str, str \| None, int \| None, str \| None] | annotated nullable but no explicit None return found |
| src/sattlint/devtools/baselines.py | _group_by_anchor | dict[tuple[str, str \| None, int \| None, str \| None], list[FindingRecord]] | annotated nullable but no explicit None return found |
| src/sattlint/devtools/pipeline.py | _tool_version | str \| None | mixed None and value returns without clear lookup/sentinel naming |
| src/sattlint/devtools/pipeline.py | _resolve_venv_tool | str \| None | annotated nullable but no explicit None return found |
| src/sattlint/devtools/pipeline_artifacts.py | payload_from_context | Callable[[PipelineArtifactContext], dict[str, Any] \| None] | annotated nullable but no explicit None return found |
| src/sattlint/devtools/repo_audit.py | _resolve_import | str \| None | annotated nullable but no explicit None return found |
| src/sattlint/devtools/repo_audit.py | _max_severity | str \| None | annotated nullable but no explicit None return found |
| src/sattlint/devtools/repo_audit.py | _default_corpus_manifest_dir | Path \| None | mixed None and value returns without clear lookup/sentinel naming |
| src/sattlint/devtools/structural_reports.py | _serialize_moduledef | dict[str, Any] \| None | mixed None and value returns without clear lookup/sentinel naming |
| src/sattlint/docgenerator/classification.py | _marker_anchor | DocumentedModule \| None | annotated nullable but no explicit None return found |
| src/sattlint/docgenerator/docgen.py | _mapping_value | str \| None | mixed None and value returns without clear lookup/sentinel naming |
| src/sattlint/engine.py | expected_unavailable_library_reason | str \| None | annotated nullable but no explicit None return found |
| src/sattlint/engine.py | _normalize_code_mode | CodeMode \| None | mixed None and value returns without clear lookup/sentinel naming |
| src/sattlint/engine.py | _extract_error_position | tuple[int \| None, int \| None] | annotated nullable but no explicit None return found |
| src/sattlint/resolution/common.py | varname_base | str \| None | mixed None and value returns without clear lookup/sentinel naming |
| src/sattlint/resolution/common.py | varname_full | str \| None | mixed None and value returns without clear lookup/sentinel naming |
| src/sattlint/validation.py | _ref_span | SourceSpan \| None | mixed None and value returns without clear lookup/sentinel naming |
| src/sattlint/validation.py | _bounded_levenshtein | int \| None | mixed None and value returns without clear lookup/sentinel naming |
| src/sattlint/validation.py | _suggest_datatype_name | str \| None | annotated nullable but no explicit None return found |
| src/sattlint/validation.py | _infer_literal_datatype | Simple_DataType \| str \| None | mixed None and value returns without clear lookup/sentinel naming |
| src/sattlint/validation.py | _merge_numeric_types | Simple_DataType \| None | mixed None and value returns without clear lookup/sentinel naming |
| src/sattlint/validation.py | _merge_compatible_types | Simple_DataType \| str \| None | mixed None and value returns without clear lookup/sentinel naming |
| src/sattlint/validation.py | _infer_expression_datatype | Simple_DataType \| str \| None | mixed None and value returns without clear lookup/sentinel naming |
| src/sattlint_lsp/local_parser.py | _extract_error_position | tuple[int \| None, int \| None] | annotated nullable but no explicit None return found |
| src/sattlint_lsp/server.py | infer_module_path_from_source | str \| None | annotated nullable but no explicit None return found |
| src/sattlint_lsp/server.py | resolve_definition_path | Path \| None | annotated nullable but no explicit None return found |
| src/sattlint_lsp/server.py | _resolve_reference_path | Path \| None | annotated nullable but no explicit None return found |
| src/sattlint_lsp/server.py | _reference_signature | tuple[str, str \| None, str \| None, int, int, int] | annotated nullable but no explicit None return found |
| src/sattlint_lsp/server.py | _get_or_build_local_snapshot | SemanticSnapshot \| None | annotated nullable but no explicit None return found |
| src/sattlint_lsp/server.py | _resolve_symbol_context | tuple[Path, str, SemanticSnapshot \| None, SnapshotBundle \| None, list[SymbolDefinition]] | annotated nullable but no explicit None return found |
| src/sattlint_lsp/server.py | _build_hover | Hover \| None | annotated nullable but no explicit None return found |

### genuinely-nullable

| Path | Function | Return annotation | Reason |
| --- | --- | --- | --- |
| src/sattline_parser/transformer/sl_transformer.py | _extract_program_name_from_header_lines | str \| None | lookup/resolve/extract helper where absence is the result |
| src/sattlint/analyzers/icf.py | _find_variable_in_module_scope | Variable \| None | lookup/resolve/extract helper where absence is the result |
| src/sattlint/analyzers/icf.py | _resolve_leaf_datatype | Simple_DataType \| str \| None | lookup/resolve/extract helper where absence is the result |
| src/sattlint/analyzers/icf.py | _resolve_record_datatype | str \| None | lookup/resolve/extract helper where absence is the result |
| src/sattlint/analyzers/mms.py | _find_parameter_mapping | ParameterMapping \| None | lookup/resolve/extract helper where absence is the result |
| src/sattlint/analyzers/mms.py | _find_variable | Variable \| None | lookup/resolve/extract helper where absence is the result |
| src/sattlint/analyzers/mms.py | _resolve_string_parameter | str \| None | lookup/resolve/extract helper where absence is the result |
| src/sattlint/analyzers/mms.py | _extract_external_tag | str \| None | lookup/resolve/extract helper where absence is the result |
| src/sattlint/analyzers/reset_contamination.py | _merge_reset_states | str \| None | lookup/resolve/extract helper where absence is the result |
| src/sattlint/app.py | _extract_warning_name | str \| None | lookup/resolve/extract helper where absence is the result |
| src/sattlint/call_signatures.py | resolve_call_signature | CallSignature \| None | lookup/resolve/extract helper where absence is the result |
| src/sattlint/core/semantic.py | _resolved_path | Path \| None | lookup/resolve/extract helper where absence is the result |
| src/sattlint/core/semantic.py | _resolve_field_datatype | Simple_DataType \| str \| None | lookup/resolve/extract helper where absence is the result |
| src/sattlint/core/semantic.py | _try_resolve_instance_typedef | ModuleTypeDef \| None | lookup/resolve/extract helper where absence is the result |
| src/sattlint/core/taint_paths.py | classify_taint_source_path | str \| None | lookup/resolve/extract helper where absence is the result |
| src/sattlint/devtools/finding_exports.py | _sanitize_path | str \| None | lookup/resolve/extract helper where absence is the result |
| src/sattlint/devtools/repo_audit.py | _list_tracked_repo_paths | tuple[str, ...] \| None | lookup/resolve/extract helper where absence is the result |
| src/sattlint/docgenerator/classification.py | _resolve_instance_moduletype | ModuleTypeDef \| None | lookup/resolve/extract helper where absence is the result |
| src/sattlint/docgenerator/docgen.py | _entry_variable | Variable \| None | lookup/resolve/extract helper where absence is the result |
| src/sattlint/engine.py | resolve_graphics_companion_path | Path \| None | lookup/resolve/extract helper where absence is the result |
| src/sattlint/graphics_validation.py | _find_record_end | int \| None | lookup/resolve/extract helper where absence is the result |
| src/sattlint/graphics_validation.py | _extract_literal_path | str \| None | lookup/resolve/extract helper where absence is the result |
| src/sattlint/graphics_validation.py | _validate_literal_path | GraphicsValidationMessage \| None | lookup/resolve/extract helper where absence is the result |
| src/sattlint/path_sanitizer.py | sanitize_path_for_report | str \| None | lookup/resolve/extract helper where absence is the result |
| src/sattlint/resolution/common.py | find_var_in_scope | Variable \| None | lookup/resolve/extract helper where absence is the result |
| src/sattlint/validation.py | _extract_time_literal | str \| None | lookup/resolve/extract helper where absence is the result |
| src/sattlint/validation.py | _resolve_variable_field_datatype | Simple_DataType \| str \| None | lookup/resolve/extract helper where absence is the result |
| src/sattlint/validation.py | _resolve_ref_datatype | Simple_DataType \| str \| None | lookup/resolve/extract helper where absence is the result |
| src/sattlint/validation.py | _resolve_root_variable | Variable \| None | lookup/resolve/extract helper where absence is the result |

### boundary-fallback

| Path | Function | Return annotation | Reason |
| --- | --- | --- | --- |
| src/sattlint_lsp/server.py | _range_for_definition | Range \| None | LSP/workspace boundary helper returns None on invalid or unavailable context |
| src/sattlint_lsp/server.py | _validated_text_document_uri | str \| None | LSP/workspace boundary helper returns None on invalid or unavailable context |
| src/sattlint_lsp/server.py | _validated_text_document_position | tuple[str, int, int] \| None | LSP/workspace boundary helper returns None on invalid or unavailable context |
| src/sattlint_lsp/server.py | _validated_open_request | tuple[str, int, str] \| None | LSP/workspace boundary helper returns None on invalid or unavailable context |
| src/sattlint_lsp/server.py | _validated_change_request | tuple[str, int, list[Any]] \| None | LSP/workspace boundary helper returns None on invalid or unavailable context |
| src/sattlint_lsp/server.py | _validated_rename_request | tuple[str, int, int, str] \| None | LSP/workspace boundary helper returns None on invalid or unavailable context |
| src/sattlint_lsp/server.py | _document_state_for_path | DocumentState \| None | LSP/workspace boundary helper returns None on invalid or unavailable context |
| src/sattlint_lsp/server.py | resolve_entry_file | Path \| None | LSP/workspace boundary helper returns None on invalid or unavailable context |
| src/sattlint_lsp/server.py | _reference_expr_at_position | str \| None | LSP/workspace boundary helper returns None on invalid or unavailable context |
| src/sattlint_lsp/server.py | _resolve_bundle_source_path | Path \| None | LSP/workspace boundary helper returns None on invalid or unavailable context |
| src/sattlint_lsp/server.py | _load_snapshot_bundle | SnapshotBundle \| None | LSP/workspace boundary helper returns None on invalid or unavailable context |
| src/sattlint_lsp/server.py | _load_snapshot_bundle_compat | SnapshotBundle \| None | LSP/workspace boundary helper returns None on invalid or unavailable context |
| src/sattlint_lsp/server.py | _definition_uri | str \| None | LSP/workspace boundary helper returns None on invalid or unavailable context |
| src/sattlint_lsp/server.py | on_definition | list[Location] \| None | LSP/workspace boundary helper returns None on invalid or unavailable context |
| src/sattlint_lsp/server.py | on_hover | Hover \| None | LSP/workspace boundary helper returns None on invalid or unavailable context |
| src/sattlint_lsp/server.py | on_references | list[Location] \| None | LSP/workspace boundary helper returns None on invalid or unavailable context |
| src/sattlint_lsp/server.py | on_rename | WorkspaceEdit \| None | LSP/workspace boundary helper returns None on invalid or unavailable context |
