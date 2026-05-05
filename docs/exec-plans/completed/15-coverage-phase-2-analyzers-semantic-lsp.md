# Coverage Phase 2: Analyzers, Semantic, LSP

This ExecPlan is a living document. Keep `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` current as work proceeds.

Retired on 2026-05-04 at user request. This file is preserved as archive-only historical coverage context and no longer represents active work.

## Purpose / Big Picture

Drain the remaining analyzer-heavy, semantic, resolution, and LSP backlog that still accounts for about `1461` uncovered lines after the first-generation lane closed. This plan exists because the analyzer/semantic/LSP cluster is still the single largest remaining bucket in the campaign.

## Progress

- [x] (2026-04-30) Create this final-phase plan from the clean shared checkpoint baseline.
- [x] (2026-04-30) Extend `tests/test_editor_api.py` with direct helper and lookup coverage for `core/semantic.py`; current artifacts now show `87` misses there, down from `119` at plan start.
- [x] (2026-04-30) Extend `tests/test_lsp_document.py` and `tests/test_lsp_diagnostics.py` for `_server_document.py` and `workspace_store.py` helper branches; current artifacts now show `_server_document.py` at `76` misses and `workspace_store.py` at `40` misses.
- [x] (2026-04-30) Extend `tests/test_lsp_diagnostics.py` again for `_server_helpers.py` pure helper branches; current artifacts now show `_server_helpers.py` at `58` misses, down from `107` at the start of this plan.
- [x] (2026-04-30) Extend `tests/test_moduletype_resolution_scoped.py` for `resolution/common.py` helper branches; current artifacts now show `39` misses there.
- [x] (2026-04-30) Extend `tests/test_analyzers_state.py` for `_variables_effect_flow.py` helper branches; current artifacts now show `85` misses there.
- [x] (2026-04-30) Run the ExecPlan 15 owner-suite closeout set successfully (`271 passed`).
- [x] (2026-05-04) Retire the remaining analyzer, semantic, and LSP coverage sweep at user request.
- [x] (2026-05-04) Archive this plan as historical coverage context instead of keeping the bucket active.

## Context and Orientation

Primary owner suites for this plan:

- `tests/test_dataflow.py`, `tests/test_analyzers_variables.py` -> `src/sattlint/analyzers/dataflow.py`, `src/sattlint/analyzers/variables.py`, adjacent analyzer helper seams
- `tests/test_analyzers_suites.py`, `tests/test_analyzers_state.py` -> `src/sattlint/analyzers/modules.py`, `src/sattlint/analyzers/reset_contamination.py`, `src/sattlint/analyzers/mms.py`, `src/sattlint/analyzers/variable_usage_reporting.py`, additional analyzer report/helper paths
- `tests/test_editor_api.py` -> `src/sattlint/core/semantic.py`
- `tests/test_lsp_document.py`, `tests/test_lsp_diagnostics.py`, `tests/test_moduletype_resolution_scoped.py`, `tests/test_canonical_resolution.py` -> `src/sattlint_lsp/_server_helpers.py`, `src/sattlint_lsp/_server_document.py`, `src/sattlint_lsp/server.py`, `src/sattlint_lsp/workspace_store.py`, `src/sattlint/resolution/common.py`, `src/sattlint_lsp/local_parser.py`

Highest remaining files in this plan from the current checkpoint include `reset_contamination.py` (`241`), `modules.py` (`200`), `variables.py` (`117`), `dataflow.py` (`106`), `mms.py` (`102`), `core/semantic.py` (`87`), `_variables_effect_flow.py` (`85`), `_server_document.py` (`76`), and `_server_helpers.py` (`58`).

## Plan of Work

Slice 1: push the remaining big analyzer files below triple-digit misses using the existing analyzer owner suites.

Slice 2: close analyzer-adjacent helper modules that are currently leaking miss counts outside the first-generation lane scope.

Slice 3: finish semantic core through editor-facing seams before widening into LSP handlers.

Slice 4: finish the LSP and resolution files with existing fake-server and fixture-based owners, then restart the LSP if any covered files changed.

## Concrete Steps

Run commands from repository root.

Per-slice first validations:

    & ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_dataflow.py tests/test_analyzers_variables.py -x -q --tb=short
    & ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_analyzers_suites.py tests/test_analyzers_state.py -x -q --tb=short
    & ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_editor_api.py -x -q --tb=short
    & ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_lsp_document.py tests/test_lsp_diagnostics.py tests/test_moduletype_resolution_scoped.py tests/test_canonical_resolution.py -x -q --tb=short

Plan-close validation:

    & ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_analyzers_suites.py tests/test_analyzers_state.py tests/test_dataflow.py tests/test_analyzers_variables.py tests/test_editor_api.py tests/test_lsp_document.py tests/test_lsp_diagnostics.py tests/test_moduletype_resolution_scoped.py tests/test_canonical_resolution.py -x -q --tb=short

## Validation and Acceptance

This plan is complete when:

- the listed owner suites pass with `--no-cov`,
- the analyzer/semantic/LSP cluster is no longer the largest remaining bucket in the next shared checkpoint,
- LSP-adjacent behavior has been validated through the existing handler suites rather than mock-only shortcuts.

## Idempotence and Recovery

If a test needs real workspace semantics, step one hop to the nearest existing fixture rather than inventing a new integration harness. If a module truly has no stable owner after a quick search, move it to the orphan plan instead of silently widening this scope.

## Surprises & Discoveries

- Observation: the first lane generation proved backlog-dominance acceptance, but not full closure.
  Evidence: the clean checkpoint still shows multiple triple-digit analyzer and semantic files.
- Observation: `local_parser.py` is better treated as part of the LSP cluster than as parser-only residue.
  Evidence: its current owners and behavior sit on the LSP side of the workspace boundary.
- Observation: the cheapest semantic and LSP wins are still direct helper seams inside the owner files rather than broader handler flows.
  Evidence: `core/semantic.py` moved from `119` misses to `87`, `workspace_store.py` to `40`, `resolution/common.py` to `39`, `_server_document.py` to `76`, and `_server_helpers.py` to `58` through focused helper tests only.
- Observation: the shared full-repo checkpoint currently has noisy coverage-report output even when pytest itself passes cleanly.
  Evidence: `python -m pytest -q --cov-fail-under=0` finished at `1310 passed, 1 warning`, but `pytest-cov` emitted repeated coverage-database parse warnings and the repo-wide percentage in `coverage.xml` was not trustworthy for acceptance.
- Observation: clearing `.coverage*` before the next full rerun restored trustworthy shared artifacts after the noisy checkpoint.
  Evidence: the latest clean artifact restore rewrote `coverage.xml` to `87.1%` (`3505` uncovered lines) and preserved the updated `_server_helpers.py` miss count at `58`.

## Decision Log

- Decision: broaden the second analyzer plan to include the adjacent analyzer helper modules that still materially leak misses.
  Rationale: reaching `100%` requires exhausting the real analyzer cluster, not just the files that fit neatly in the first-generation lane.
  Date/Author: 2026-04-30 / Copilot (GPT-5.4)
- Decision: prioritize helper-heavy semantic, LSP, resolution, and analyzer seams before broader handler or walker paths.
  Rationale: the owner suites already expose these helpers directly, so they retire misses faster and with less fixture churn than new integration scaffolds.
  Date/Author: 2026-04-30 / Copilot (GPT-5.4)

## Outcomes & Retrospective

Plan created from the clean `82.35%` checkpoint.

This pass closed a semantic/LSP/helper tranche without production changes:

- `tests/test_editor_api.py` gained direct helper and lookup coverage for `core/semantic.py`.
- `tests/test_lsp_document.py` gained document-state helper coverage for `_server_document.py`.
- `tests/test_lsp_diagnostics.py` gained workspace-store helper coverage for `workspace_store.py`.
- `tests/test_lsp_diagnostics.py` gained direct helper coverage for `_server_helpers.py` request, range, merge, location, and edit helpers.
- `tests/test_moduletype_resolution_scoped.py` gained pure-helper coverage for `resolution/common.py`.
- `tests/test_analyzers_state.py` gained direct helper coverage for `_variables_effect_flow.py`.

Validation totals for this tranche:

- `tests/test_editor_api.py` -> `26 passed`
- `tests/test_lsp_document.py` -> `38 passed`
- `tests/test_lsp_diagnostics.py` -> `40 passed`
- `tests/test_moduletype_resolution_scoped.py` -> `12 passed`
- `tests/test_analyzers_state.py` -> `39 passed`
- ExecPlan 15 owner closeout set -> `271 passed`
- clean shared artifact restore after clearing `.coverage*` -> `coverage.xml` at `87.1%` with `3505` uncovered lines; `_server_helpers.py` now sits at `58` misses in `htmlcov/status.json`

The plan was retired and archived on 2026-05-04 at user request. The remaining analyzer, semantic, and LSP misses stay here only as historical checkpoint context rather than an active execution commitment.

## Artifacts and Notes

- Use the orchestrator for shared checkpoint timing and final acceptance.
- Record any required LSP restart in the shared `.git/sattlint-ai-coordination/current_work_lock.json` lock state once `src/sattlint_lsp/` or `src/sattlint/core/` files are edited.
- This tranche changed tests only, so no LSP restart was required.
- Use `htmlcov/status.json` file-level miss counts from the restored full-suite artifacts for local residual triage.

## Interfaces and Dependencies

Preserve strict workspace-versus-single-file behavior boundaries. Do not weaken diagnostics or resolution behavior to make coverage easier.
