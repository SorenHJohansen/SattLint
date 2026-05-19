# T-Wave-7 Analyzers Strict Typing Promotion

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

## Purpose / Big Picture

This plan makes the remaining analyzer helper and domain modules ready for full strict coverage. After this work lands, the uncovered analyzer files will be strict-clean and explicitly represented in `tool.pyright.strict`, which removes the largest remaining non-devtools typing blocker cluster from the strict roots.

The observable proof is that the owned analyzer files pass touched-file `pyright`, the focused analyzer owner tests remain green across dataflow, semantics, variable traversal, state inference, and domain analyzers, and the same change updates `pyproject.toml` plus a matching approval record to adopt the newly clean files into strict coverage.

## Progress

- [x] (2026-05-18 15:10Z) Create the ExecPlan and capture the live baseline: the uncovered inventory contains sixty-four files under `src/sattlint/analyzers/`.
- [x] (2026-05-18 15:10Z) Capture the high-signal strict offenders for the slice: the full-strict audit reports the largest per-file counts in `_wave2_support.py`, `_reset_path_collection.py`, `_reset_path_stmt_handlers.py`, and `_variable_traversal_walk.py`.
- [x] (2026-05-18 14:16Z) Make the uncovered analyzer files strict-clean in themed batches. Evidence: the final strict probe over the eight-file tail returned `0 errors`, and the full sixty-four-file exec-plan inventory also returned `0 errors` under strict `pyright`.
- [x] (2026-05-18 14:16Z) Update `pyproject.toml` to add the newly clean analyzer files to `tool.pyright.strict` and add or update the required approval record. Evidence: `pyproject.toml` now promotes the sixty-four analyzer files listed in this plan, and `.github/approvals/ratchet-rebaseline-2026-05-18-analyzers.md` records the same-change approval.
- [x] (2026-05-18 14:16Z) Run focused analyzer validation, touched-file Ruff, and touched-file Pyright for the slice. Evidence: the ratchet-policy pytest suite passed, all four focused analyzer pytest commands passed, `bash scripts/run_repo_python.sh -m pyright src/sattlint/analyzers` passed, and `bash scripts/run_repo_python.sh -m ruff check src/sattlint/analyzers` passed.

## Surprises & Discoveries

- Observation: analyzers are the second-largest strict-mode blocker cluster after devtools.
  Evidence: the full-strict audit reported `491` errors under `src/sattlint/analyzers`.
- Observation: the biggest analyzer error classes are unknown-variable and unknown-member typing, not one isolated API mismatch.
  Evidence: the strict-mode rule summary is dominated by `reportUnknownVariableType`, `reportUnknownArgumentType`, and `reportUnknownMemberType`.
- Observation: the uncovered analyzer inventory spans multiple distinct owner themes.
  Evidence: the file list covers dataflow, reset-path analysis, builtin or semantic rule catalogs, registry support, variable traversal, and domain analyzers.
- Observation: the full analyzer finish-gate checks exposed one backward-compatibility seam that the narrow strict probes did not cover.
  Evidence: `tests/test_analyzers_suites.py` initially failed because `sattlint.analyzers.mms` no longer re-exported `_extract_external_tag`, `_normalize_external_tag`, `_tag_family_key`, `_find_parameter_mapping`, and `_find_variable`, so the final slice restored those exports through local compatibility wrappers.
- Observation: strict-clean helper edits still need a package-level lint pass before closeout.
  Evidence: after the strict probes and focused pytest commands were green, `ruff check src/sattlint/analyzers` still caught import-order drift in ten touched files plus two `yield from` simplifications in `_wave2_support.py`.

## Decision Log

- Decision: execute analyzer cleanup in themed batches inside one ExecPlan.
  Rationale: the analyzer surface is too large for one undifferentiated pass, but one shared plan still keeps the strict-list adoption and validation story coherent.
  Date/Author: 2026-05-18 / Copilot (GPT-5.4)
- Decision: prefer explicit typed intermediates and narrow helper signatures over behavioral redesign.
  Rationale: most current strict blockers are about ambiguous local shapes, so a large semantic rewrite would add risk without helping the promotion goal.
  Date/Author: 2026-05-18 / Copilot (GPT-5.4)
- Decision: keep the protected-path update until the whole analyzer slice is locally clean.
  Rationale: `pyproject.toml` should be the final adoption step, not part of iterative debugging.
  Date/Author: 2026-05-18 / Copilot (GPT-5.4)

## Outcomes & Retrospective

The analyzer strict-promotion slice is complete. The sixty-four targeted analyzer helper and domain files are now strict-clean, promoted into `tool.pyright.strict`, and covered by the same-change approval record at `.github/approvals/ratchet-rebaseline-2026-05-18-analyzers.md`.

The final proof for this plan is:

- `bash scripts/run_repo_python.sh -m pytest --no-cov tests/test_ratchet_policy.py tests/test_ratchet_policy_typing.py -x -q --tb=short`
- `bash scripts/run_repo_python.sh -m pytest --no-cov tests/test_analyzers_state.py tests/analyzers/test_canonical_resolution.py tests/analyzers/test_moduletype_resolution_scoped.py -x -q --tb=short`
- `bash scripts/run_repo_python.sh -m pytest --no-cov tests/test_analyzers_variables.py tests/test_variables_effect_flow_mappings.py tests/analyzers/test_variable_usage_reporting.py -x -q --tb=short`
- `bash scripts/run_repo_python.sh -m pytest --no-cov tests/analyzers/test_sattline_semantics.py tests/analyzers/test_sattline_semantics_regressions.py tests/analyzers/test_sattline_semantics_tail.py tests/analyzers/test_builtin_record_semantics.py tests/analyzers/test_initvariable_semantics.py -x -q --tb=short`
- `bash scripts/run_repo_python.sh -m pytest --no-cov tests/test_analyzers_suites.py tests/test_analyzers_version_drift.py tests/analyzers/test_config_drift.py tests/analyzers/test_field_mapping.py -x -q --tb=short`
- `bash scripts/run_repo_python.sh -m pyright src/sattlint/analyzers`
- `bash scripts/run_repo_python.sh -m ruff check src/sattlint/analyzers`

One small runtime regression surfaced during finish-gate validation: `sattlint.analyzers.mms` had stopped exposing several helper symbols that the analyzer suite still imports. The slice repaired that compatibility seam with local wrappers and kept the rest of the work focused on typing-shape cleanup, strict-list adoption, and finish-gate hygiene.

## Context and Orientation

The owned analyzer files break into these batches.

Dataflow and dependency support:

- `src/sattlint/analyzers/_alarm_path_traversal.py`
- `src/sattlint/analyzers/_dataflow_common.py`
- `src/sattlint/analyzers/_dataflow_conditions.py`
- `src/sattlint/analyzers/_dataflow_scope_support.py`
- `src/sattlint/analyzers/_dataflow_state.py`
- `src/sattlint/analyzers/_dataflow_traversal.py`
- `src/sattlint/analyzers/_dependency_usage_facts.py`
- `src/sattlint/analyzers/_dependency_usage_scope_support.py`

ICF, MMS, and module support:

- `src/sattlint/analyzers/_icf_datatype_resolution.py`
- `src/sattlint/analyzers/_icf_file_io.py`
- `src/sattlint/analyzers/_mms_icf_inventory.py`
- `src/sattlint/analyzers/_mms_interface_analysis.py`
- `src/sattlint/analyzers/_mms_interface_helpers.py`
- `src/sattlint/analyzers/_modules_debug.py`
- `src/sattlint/analyzers/_modules_diffing.py`
- `src/sattlint/analyzers/_modules_fingerprints.py`
- `src/sattlint/analyzers/_modules_reporting.py`

Registry support:

- `src/sattlint/analyzers/_registry_delivery.py`
- `src/sattlint/analyzers/_registry_delivery_data.py`
- `src/sattlint/analyzers/_registry_spec_templates.py`
- `src/sattlint/analyzers/_registry_specs.py`

Reset-path and latching support:

- `src/sattlint/analyzers/_reset_latching.py`
- `src/sattlint/analyzers/_reset_latching_paths.py`
- `src/sattlint/analyzers/_reset_path_collection.py`
- `src/sattlint/analyzers/_reset_path_collection_sequence.py`
- `src/sattlint/analyzers/_reset_path_condition.py`
- `src/sattlint/analyzers/_reset_path_state.py`
- `src/sattlint/analyzers/_reset_path_stmt_handlers.py`
- `src/sattlint/analyzers/_reset_path_writes.py`

Builtin and semantic rule support:

- `src/sattlint/analyzers/_sattline_builtin_types.py`
- `src/sattlint/analyzers/_sattline_builtins_part1.py`
- `src/sattlint/analyzers/_sattline_builtins_part2.py`
- `src/sattlint/analyzers/_sattline_builtins_part3.py`
- `src/sattlint/analyzers/_sattline_builtins_part4.py`
- `src/sattlint/analyzers/_sattline_builtins_part5.py`
- `src/sattlint/analyzers/_sattline_builtins_registry.py`
- `src/sattlint/analyzers/_sattline_semantic_contracts.py`
- `src/sattlint/analyzers/_sattline_semantic_issue_mapping.py`
- `src/sattlint/analyzers/_sattline_semantic_models.py`
- `src/sattlint/analyzers/_sattline_semantic_rules.py`
- `src/sattlint/analyzers/_sattline_semantic_rules_data.py`
- `src/sattlint/analyzers/_sattline_semantic_rules_more_data.py`
- `src/sattlint/analyzers/_sfc_step_contracts.py`

Variable traversal and facade support:

- `src/sattlint/analyzers/_variable_traversal_objects.py`
- `src/sattlint/analyzers/_variable_traversal_support.py`
- `src/sattlint/analyzers/_variable_traversal_walk.py`
- `src/sattlint/analyzers/_variables_analyzer_facade.py`
- `src/sattlint/analyzers/_variables_effect_sources.py`
- `src/sattlint/analyzers/_variables_facade_properties.py`
- `src/sattlint/analyzers/_variables_mapping_refs.py`
- `src/sattlint/analyzers/_wave2_support.py`

Domain analyzers:

- `src/sattlint/analyzers/config_drift.py`
- `src/sattlint/analyzers/data_dependency.py`
- `src/sattlint/analyzers/fault_handling.py`
- `src/sattlint/analyzers/interface_contracts.py`
- `src/sattlint/analyzers/loop_stability.py`
- `src/sattlint/analyzers/numeric_constraints.py`
- `src/sattlint/analyzers/powerup.py`
- `src/sattlint/analyzers/resource_usage.py`
- `src/sattlint/analyzers/scan_concurrency.py`
- `src/sattlint/analyzers/signal_lifecycle.py`
- `src/sattlint/analyzers/state_inference.py`
- `src/sattlint/analyzers/timing.py`
- `src/sattlint/analyzers/variable_utils.py`

Useful owner tests for this plan include `tests/test_analyzers_suites.py`, `tests/test_analyzers_state.py`, `tests/test_analyzers_variables.py`, `tests/test_analyzers_version_drift.py`, `tests/test_variables_effect_flow_mappings.py`, `tests/analyzers/test_sattline_semantics.py`, `tests/analyzers/test_sattline_semantics_regressions.py`, `tests/analyzers/test_sattline_semantics_tail.py`, `tests/analyzers/test_builtin_record_semantics.py`, `tests/analyzers/test_initvariable_semantics.py`, `tests/analyzers/test_config_drift.py`, `tests/analyzers/test_variable_usage_reporting.py`, `tests/analyzers/test_field_mapping.py`, `tests/analyzers/test_moduletype_resolution_scoped.py`, and `tests/analyzers/test_canonical_resolution.py`.

This plan ends with a protected-path edit in `pyproject.toml`, which requires a matching approval record under `.github/approvals/ratchet-rebaseline-*.md`.

## Plan of Work

Start with the high-signal helper clusters: dataflow or dependency support, reset-path support, and variable traversal or facade support. These groups account for many of the unknown-shape strict errors and should reduce noise for the remaining domain analyzers.

After the helper clusters are locally clean, work through registry support, builtin or semantic rule support, and then the remaining domain analyzers. Keep edits narrow. Prefer typed helper returns, explicit loop-variable annotations, and stable helper contracts over algorithm changes.

Run the smallest matching analyzer owner tests after each batch. Do not wait until the end of the entire slice to learn that one semantic or variable-traversal cluster regressed. Once all owned files are locally strict-clean, update `pyproject.toml`, add the approval record, and rerun the ratchet-policy tests.

## Concrete Steps

Run all commands from the repository root.

Inspect the high-signal analyzer helpers before editing:

    rg -n "def |class |TypedDict|Protocol|cast\(|getattr\(|hasattr\(|children|branch|state|condition" src/sattlint/analyzers/_alarm_path_traversal.py src/sattlint/analyzers/_dataflow_common.py src/sattlint/analyzers/_dataflow_conditions.py src/sattlint/analyzers/_dataflow_scope_support.py src/sattlint/analyzers/_dataflow_state.py src/sattlint/analyzers/_dataflow_traversal.py src/sattlint/analyzers/_reset_path_collection.py src/sattlint/analyzers/_reset_path_stmt_handlers.py src/sattlint/analyzers/_variable_traversal_walk.py src/sattlint/analyzers/_wave2_support.py

Batch-local focused proof examples:

    bash scripts/run_repo_python.sh -m pytest --no-cov tests/test_analyzers_state.py tests/analyzers/test_canonical_resolution.py tests/analyzers/test_moduletype_resolution_scoped.py -x -q --tb=short
    bash scripts/run_repo_python.sh -m pytest --no-cov tests/test_analyzers_variables.py tests/test_variables_effect_flow_mappings.py tests/analyzers/test_variable_usage_reporting.py -x -q --tb=short
    bash scripts/run_repo_python.sh -m pytest --no-cov tests/analyzers/test_sattline_semantics.py tests/analyzers/test_sattline_semantics_regressions.py tests/analyzers/test_sattline_semantics_tail.py tests/analyzers/test_builtin_record_semantics.py tests/analyzers/test_initvariable_semantics.py -x -q --tb=short
    bash scripts/run_repo_python.sh -m pytest --no-cov tests/test_analyzers_suites.py tests/test_analyzers_version_drift.py tests/analyzers/test_config_drift.py tests/analyzers/test_field_mapping.py -x -q --tb=short

Touched-file type and lint proof after the final batch is clean:

    bash scripts/run_repo_python.sh -m pyright src/sattlint/analyzers
    bash scripts/run_repo_python.sh -m ruff check src/sattlint/analyzers

Protected-path closeout proof:

    bash scripts/run_repo_python.sh -m pytest --no-cov tests/test_ratchet_policy.py tests/test_ratchet_policy_typing.py -x -q --tb=short

## Validation and Acceptance

This plan is complete only when every owned analyzer file is strict-clean, the batch-local analyzer tests pass, the newly clean analyzer files are represented in `tool.pyright.strict`, and the approval record exists in the same change.

Acceptance is behavioral. Analyzer semantics, state tracking, variable traversal, registry behavior, builtin modeling, and domain-analyzer outputs must stay stable from the test perspective after the typing cleanup.

## Idempotence and Recovery

This plan is intentionally batchable. If one analyzer cluster turns out to need a larger design change, stop after the last green batch, record the blocker in `Progress`, and continue in a narrower follow-on slice rather than overloading this plan.

Do not touch `pyproject.toml` until all owned analyzer files are already strict-clean locally. The protected-path change should be the adoption step, not part of debugging the helper shapes.

## Artifacts and Notes

Record the following evidence as work proceeds:

- the per-batch passing analyzer pytest commands and summaries,
- the final touched-file `pyright` output for `src/sattlint/analyzers`,
- the exact files added to `tool.pyright.strict`,
- the approval record path used for the protected-path update.

## Interfaces and Dependencies

This slice depends on the analyzer helper and domain-analyzer boundaries already present under `src/sattlint/analyzers/`. Preserve analyzer behavior and emitted findings. Keep the cleanup focused on typing and local helper contracts unless a tiny extraction is the narrowest safe fix.

The protected-path dependency is `pyproject.toml` plus the required approval record. No new debt entries are allowed.
