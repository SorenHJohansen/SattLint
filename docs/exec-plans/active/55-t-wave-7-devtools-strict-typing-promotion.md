# T-Wave-7 Devtools Strict Typing Promotion

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

## Purpose / Big Picture

This plan makes the remaining devtools surface ready for full strict coverage. After this work lands, the uncovered devtools files will be strict-clean, the two remaining devtools debt-allowlist entries will be removed by real fixes rather than by rebaselining, and the devtools slice will stop dominating the strict-mode blocker inventory.

The observable proof is that the owned devtools files pass touched-file `pyright`, the focused devtools owner tests remain green across AI chat, doc gardener, pipeline, repo-audit, structural reporting, and utility behavior, and the same change updates `pyproject.toml` plus a matching approval record to add newly clean files to `tool.pyright.strict` while removing the devtools debt-allowlist entries.

## Progress

- [x] (2026-05-18 15:10Z) Create the ExecPlan and capture the live baseline: `src/sattlint/devtools/` has fifty-five uncovered files, and `tool.sattlint.typing_ratchet.debt_allowlist` still contains `src/sattlint/devtools/doc_gardener.py` and `src/sattlint/devtools/review_tool.py`.
- [x] (2026-05-18 15:10Z) Capture the high-signal strict offenders for the slice: the full-strict audit reports the largest per-file counts in `_ai_work_map_planning.py`, `_repo_audit_recommended_slice.py`, `_doc_gardener_scan.py`, `repo_audit_compat.py`, and `_ai_work_map_freshness.py`.
- [x] (2026-05-18 15:12Z) Make the uncovered devtools files strict-clean in themed batches. The final full devtools strict audit run with `tmp-pyright-devtools-strict.json` reports `0` diagnostics across `87` analyzed files.
- [x] (2026-05-18 15:12Z) Resolve the two devtools debt-allowlist entries by real code fixes so they can move into `tool.pyright.strict`. `src/sattlint/devtools/doc_gardener.py` and `src/sattlint/devtools/review_tool.py` are now promoted alongside the rest of the uncovered devtools slice.
- [x] (2026-05-18 15:12Z) Update `pyproject.toml` with the newly clean devtools files, remove the allowlist entries, and add or update the required approval record. The protected-path closeout uses `.github/approvals/ratchet-rebaseline-2026-05-18-devtools.md`.
- [x] (2026-05-18 15:12Z) Run focused devtools validation, touched-file Ruff, and touched-file Pyright for the slice. Final proof: `bash scripts/run_repo_python.sh -m pyright src/sattlint/devtools`, `bash scripts/run_repo_python.sh -m ruff check src/sattlint/devtools`, and `bash scripts/run_repo_python.sh -m pytest --no-cov tests/test_ratchet_policy.py tests/test_ratchet_policy_typing.py -x -q --tb=short` all pass.

## Surprises & Discoveries

- Observation: devtools is the single biggest strict-mode blocker cluster.
  Evidence: the full-strict audit reported `514` errors under `src/sattlint/devtools`, more than any other top-level subsystem.
- Observation: the remaining explicit typing debt is concentrated in devtools.
  Evidence: the live `debt_allowlist` contains only `src/sattlint/devtools/doc_gardener.py` and `src/sattlint/devtools/review_tool.py`.
- Observation: one broad devtools edit pass would be too risky.
  Evidence: the uncovered file list spans unrelated AI chat, doc gardener, pipeline, repo-audit, structural reporting, and utility surfaces.
- Observation: the final finish-gate lint proof surfaced a small residual cleanup outside the strict blocker tail.
  Evidence: `bash scripts/run_repo_python.sh -m ruff check src/sattlint/devtools` still reported `UP040` in `corpus.py` and `E402` in `mutation_engine.py` after the strict frontier had already reached zero, so the closeout included those mechanical fixes before the ratchet tests ran.

## Decision Log

- Decision: execute this plan in themed sub-batches even though it is one ExecPlan.
  Rationale: the file count is large enough that the safest implementation path is to clean one coherent owner cluster at a time while keeping one shared document and one final protected-path update.
  Date/Author: 2026-05-18 / Copilot (GPT-5.4)
- Decision: keep `pyproject.toml` edits and debt-allowlist removal until the whole devtools slice is locally clean.
  Rationale: repeated protected-path churn would create avoidable merge conflict risk and make ratchet-policy proof harder to interpret.
  Date/Author: 2026-05-18 / Copilot (GPT-5.4)
- Decision: remove the devtools debt entries only by fixing code, never by rebaselining.
  Rationale: the ratchet rules require monotonic strict coverage and forbid growing debt to satisfy typing promotion.
  Date/Author: 2026-05-18 / Copilot (GPT-5.4)

## Outcomes & Retrospective

Completed. The remaining uncovered devtools slice is now strict-clean, the final devtools full-strict audit reports zero diagnostics, and the last explicit devtools typing debt entries have been retired rather than rebaselined. `tool.pyright.strict` now includes the devtools files listed under this plan's Context and Orientation section, `tool.sattlint.typing_ratchet.debt_allowlist` is empty, and the protected-path approval record is present at `.github/approvals/ratchet-rebaseline-2026-05-18-devtools.md`.

The final closeout proof is green end-to-end: `bash scripts/run_repo_python.sh -m pyright src/sattlint/devtools` reports no diagnostics, `bash scripts/run_repo_python.sh -m ruff check src/sattlint/devtools` passes, and `bash scripts/run_repo_python.sh -m pytest --no-cov tests/test_ratchet_policy.py tests/test_ratchet_policy_typing.py -x -q --tb=short` passes with `23` tests. The earlier batch-local owner suites for AI chat, doc gardener, pipeline, repo-audit, structural reporting, coordination utilities, and related helper slices remained green throughout the promotion.

## Context and Orientation

The owned devtools files break into these batches.

AI chat and work-map files:

- `src/sattlint/devtools/_ai_chat_findings.py`
- `src/sattlint/devtools/_ai_chat_metrics.py`
- `src/sattlint/devtools/_ai_chat_transcripts.py`
- `src/sattlint/devtools/_ai_work_map_freshness.py`
- `src/sattlint/devtools/_ai_work_map_parsing.py`
- `src/sattlint/devtools/_ai_work_map_planning.py`
- `src/sattlint/devtools/ai_chat_observability.py`

Doc-gardener and review files:

- `src/sattlint/devtools/_doc_gardener_fixup.py`
- `src/sattlint/devtools/_doc_gardener_scan.py`
- `src/sattlint/devtools/_doc_gardener_updates.py`
- `src/sattlint/devtools/doc_gardener.py`
- `src/sattlint/devtools/review_tool.py`

Pipeline files:

- `src/sattlint/devtools/_pipeline_cli.py`
- `src/sattlint/devtools/_pipeline_execution.py`
- `src/sattlint/devtools/_pipeline_failure_outputs.py`
- `src/sattlint/devtools/_pipeline_finish_gate.py`
- `src/sattlint/devtools/_pipeline_optional_reports_helpers.py`
- `src/sattlint/devtools/_pipeline_parsing_helpers.py`
- `src/sattlint/devtools/_pipeline_recommendations.py`
- `src/sattlint/devtools/_pipeline_status_assembly.py`

Repo-audit and artifact files:

- `src/sattlint/devtools/_portable_command_text.py`
- `src/sattlint/devtools/_repo_audit_ai_gc.py`
- `src/sattlint/devtools/_repo_audit_check_catalog.py`
- `src/sattlint/devtools/_repo_audit_check_specs.py`
- `src/sattlint/devtools/_repo_audit_entrypoint_helpers.py`
- `src/sattlint/devtools/_repo_audit_entrypoint_runs.py`
- `src/sattlint/devtools/_repo_audit_full_run.py`
- `src/sattlint/devtools/_repo_audit_planning_helpers.py`
- `src/sattlint/devtools/_repo_audit_recommended_slice.py`
- `src/sattlint/devtools/_repo_audit_reporting.py`
- `src/sattlint/devtools/artifact_readiness.py`
- `src/sattlint/devtools/audit_core.py`
- `src/sattlint/devtools/audit_core_discovery.py`
- `src/sattlint/devtools/audit_orchestration.py`
- `src/sattlint/devtools/compare_audit_findings.py`
- `src/sattlint/devtools/current_debt_snapshot.py`
- `src/sattlint/devtools/repo_audit_cli_reporting.py`
- `src/sattlint/devtools/repo_audit_compat.py`
- `src/sattlint/devtools/repo_audit_runs.py`
- `src/sattlint/devtools/repo_audit_shared.py`

Structural, coordination, and utility files:

- `src/sattlint/devtools/_coordination_lock_paths.py`
- `src/sattlint/devtools/_structural_report_architecture.py`
- `src/sattlint/devtools/_structural_report_budget.py`
- `src/sattlint/devtools/_structural_report_graphics.py`
- `src/sattlint/devtools/_structural_report_graphs.py`
- `src/sattlint/devtools/_structural_report_impact.py`
- `src/sattlint/devtools/coordination_lock_state.py`
- `src/sattlint/devtools/fault_injection.py`
- `src/sattlint/devtools/fuzzer.py`
- `src/sattlint/devtools/impact_analyzer.py`
- `src/sattlint/devtools/leak_detection.py`
- `src/sattlint/devtools/leak_detection_scan_paths.py`
- `src/sattlint/devtools/ledger.py`
- `src/sattlint/devtools/metrics_dashboard.py`
- `src/sattlint/devtools/profiler.py`
- `src/sattlint/devtools/property_tests.py`
- `src/sattlint/devtools/refactoring.py`

The narrow owner tests for this plan are also batch-oriented. Useful suites include `tests/test_ai_chat_observability.py`, `tests/test_repo_audit_doc_gardener.py`, `tests/test_pipeline.py`, `tests/test_pipeline_run.py`, `tests/test_pipeline_run_recommendations.py`, `tests/test_pipeline_collection.py`, `tests/test_pipeline_collection_graphs.py`, `tests/test_pipeline_owner_coverage.py`, `tests/test_pipeline_owner_coverage_runtime.py`, `tests/test_pipeline_phase2.py`, `tests/test_repo_audit.py`, `tests/test_repo_audit_cli.py`, `tests/test_repo_audit_cli_helpers.py`, `tests/test_repo_audit_entrypoints_helpers.py`, `tests/test_repo_audit_entrypoints_finish_gate.py`, `tests/test_repo_audit_entrypoints_verify.py`, `tests/test_repo_audit_precommit.py`, `tests/test_repo_audit_runs.py`, `tests/test_repo_audit_ai_gc_runtime.py`, `tests/test_repo_audit_reporting_helpers.py`, `tests/test_structural_reports.py`, `tests/test_structural_reports_graphics.py`, `tests/test_structural_reports_graphs.py`, `tests/test_structural_reports_markdown.py`, `tests/test_structural_budget_inventory.py`, `tests/devtools/test_impact_analyzer.py`, `tests/devtools/test_devtools_review_observability.py`, and `tests/devtools/test_devtools_orphans.py`.

This plan ends with a protected-path edit in `pyproject.toml`, which requires a matching approval record under `.github/approvals/ratchet-rebaseline-*.md`.

## Plan of Work

Work through the batches in dependency order. Start with AI chat or work-map files, then doc-gardener or review helpers, then pipeline helpers, then repo-audit surfaces, and finish with structural or utility files. Each batch should become locally strict-clean before the next batch starts.

Validate each batch with the smallest matching test command before widening. Do not wait until the end of the whole plan to learn that one owner cluster broke. When a batch is clean and its tests pass, move to the next cluster without touching `pyproject.toml` yet.

Once every owned devtools file is locally clean, update `pyproject.toml` in one shared change: add the uncovered files to `tool.pyright.strict`, remove `src/sattlint/devtools/doc_gardener.py` and `src/sattlint/devtools/review_tool.py` from `tool.sattlint.typing_ratchet.debt_allowlist`, add the approval record, and rerun the ratchet-policy tests.

## Concrete Steps

Run all commands from the repository root.

Inspect the batch surfaces before editing:

    rg -n "def |class |TypedDict|Protocol|cast\(|getattr\(|hasattr\(" src/sattlint/devtools/_ai_chat_findings.py src/sattlint/devtools/_ai_chat_metrics.py src/sattlint/devtools/_ai_chat_transcripts.py src/sattlint/devtools/_ai_work_map_freshness.py src/sattlint/devtools/_ai_work_map_parsing.py src/sattlint/devtools/_ai_work_map_planning.py src/sattlint/devtools/_doc_gardener_fixup.py src/sattlint/devtools/_doc_gardener_scan.py src/sattlint/devtools/_doc_gardener_updates.py src/sattlint/devtools/_pipeline_cli.py src/sattlint/devtools/_pipeline_execution.py src/sattlint/devtools/_pipeline_failure_outputs.py src/sattlint/devtools/_pipeline_finish_gate.py src/sattlint/devtools/_pipeline_optional_reports_helpers.py src/sattlint/devtools/_pipeline_parsing_helpers.py src/sattlint/devtools/_pipeline_recommendations.py src/sattlint/devtools/_pipeline_status_assembly.py src/sattlint/devtools/_repo_audit_check_specs.py src/sattlint/devtools/_repo_audit_full_run.py src/sattlint/devtools/_repo_audit_recommended_slice.py src/sattlint/devtools/repo_audit_compat.py

Batch-local focused proof examples:

    bash scripts/run_repo_python.sh -m pytest --no-cov tests/test_ai_chat_observability.py tests/devtools/test_devtools_review_observability.py -x -q --tb=short
    bash scripts/run_repo_python.sh -m pytest --no-cov tests/test_repo_audit_doc_gardener.py -x -q --tb=short
    bash scripts/run_repo_python.sh -m pytest --no-cov tests/test_pipeline.py tests/test_pipeline_run.py tests/test_pipeline_run_recommendations.py tests/test_pipeline_collection.py tests/test_pipeline_collection_graphs.py tests/test_pipeline_owner_coverage.py tests/test_pipeline_owner_coverage_runtime.py tests/test_pipeline_phase2.py -x -q --tb=short
    bash scripts/run_repo_python.sh -m pytest --no-cov tests/test_repo_audit.py tests/test_repo_audit_cli.py tests/test_repo_audit_cli_helpers.py tests/test_repo_audit_entrypoints_helpers.py tests/test_repo_audit_entrypoints_finish_gate.py tests/test_repo_audit_entrypoints_verify.py tests/test_repo_audit_precommit.py tests/test_repo_audit_runs.py tests/test_repo_audit_ai_gc_runtime.py tests/test_repo_audit_reporting_helpers.py -x -q --tb=short
    bash scripts/run_repo_python.sh -m pytest --no-cov tests/test_structural_reports.py tests/test_structural_reports_graphics.py tests/test_structural_reports_graphs.py tests/test_structural_reports_markdown.py tests/test_structural_budget_inventory.py tests/devtools/test_impact_analyzer.py tests/devtools/test_devtools_orphans.py -x -q --tb=short

Touched-file type and lint proof after the final batch is clean:

    bash scripts/run_repo_python.sh -m pyright src/sattlint/devtools
    bash scripts/run_repo_python.sh -m ruff check src/sattlint/devtools

Protected-path closeout proof:

    bash scripts/run_repo_python.sh -m pytest --no-cov tests/test_ratchet_policy.py tests/test_ratchet_policy_typing.py -x -q --tb=short

## Validation and Acceptance

This plan is complete only when every owned devtools file is strict-clean, the batch-local owner tests pass, `src/sattlint/devtools/doc_gardener.py` and `src/sattlint/devtools/review_tool.py` leave the debt allowlist by way of real fixes, the newly clean files are represented in `tool.pyright.strict`, and the approval record exists in the same change.

Acceptance is behavioral. Pipeline commands, repo-audit behavior, doc-gardener behavior, structural reporting, AI chat observability, and devtools utility behavior must stay stable from the test perspective after the typing cleanup.

## Idempotence and Recovery

This plan is intentionally batchable. If one owner cluster proves larger than expected, finish the last green batch, record the remaining blocker in `Progress`, and continue in a follow-on slice rather than half-promoting unfinished files.

Do not touch `pyproject.toml` until the whole devtools slice is locally clean. Do not remove the devtools debt entries unless the corresponding files are already strict-clean and ready to enter `tool.pyright.strict`.

## Artifacts and Notes

Record the following evidence as work proceeds:

- the per-batch passing pytest commands and summaries,
- the final touched-file `pyright` output for `src/sattlint/devtools`,
- the exact files added to `tool.pyright.strict`,
- the exact debt-allowlist entries removed,
- the approval record path used for the protected-path update.

Closeout evidence for this plan:

- Final full-strict proof: `bash scripts/run_repo_python.sh -m pyright -p tmp-pyright-devtools-strict.json --outputjson >| pyright_strict_devtools_results.json` reports `0` errors and `0` warnings across `87` analyzed files.
- Final touched-file proof: `bash scripts/run_repo_python.sh -m pyright src/sattlint/devtools` reports `0` errors, `0` warnings, and `0` information messages.
- Final lint proof: `bash scripts/run_repo_python.sh -m ruff check src/sattlint/devtools` reports `All checks passed!`.
- Protected-path closeout proof: `bash scripts/run_repo_python.sh -m pytest --no-cov tests/test_ratchet_policy.py tests/test_ratchet_policy_typing.py -x -q --tb=short` passes with `23` tests.
- Debt entries removed: `src/sattlint/devtools/doc_gardener.py` and `src/sattlint/devtools/review_tool.py`.
- Approval record: `.github/approvals/ratchet-rebaseline-2026-05-18-devtools.md`.

## Interfaces and Dependencies

This slice depends on the existing devtools module boundaries under `src/sattlint/devtools/`. Preserve CLI output and behavior where tests already define it. Keep the cleanup local to typing and helper-shape clarification; do not reopen unrelated product work or structural refactors unless a tiny helper extraction is the narrowest strict-safe fix.

The protected-path dependency is `pyproject.toml` plus the required approval record. No new debt entries are allowed.
