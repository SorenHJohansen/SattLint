# Coverage Lane B: Analyzers, Semantic, LSP

This ExecPlan is a completed first-generation lane record. The sections below capture how the lane closed and why it was moved out of `docs/exec-plans/active/`.

## Purpose / Big Picture

Drain the analyzer-heavy and workspace-semantic coverage debt without reopening broad exploration. This lane owned the highest-risk semantic modules plus the LSP bridge while the first-generation coverage split was still active.

## Progress

- [x] (2026-04-30) Create this lane plan and pin it to existing analyzer, editor, and LSP owner suites.
- [x] (2026-04-30) Drain `variables.py` and `dataflow.py` through `tests/test_analyzers_variables.py` and `tests/test_dataflow.py`.
- [x] (2026-04-30) Drain `modules.py`, `reset_contamination.py`, `mms.py`, and `variable_usage_reporting.py` through `tests/test_analyzers_suites.py` and `tests/test_analyzers_state.py`.
- [x] (2026-04-30) Drain `core/semantic.py` through `tests/test_editor_api.py`.
- [x] (2026-04-30) Drain `_server_helpers.py`, `_server_document.py`, `server.py`, `workspace_store.py`, and `resolution/common.py` through the LSP and resolution owner suites.
- [x] (2026-04-30) Run the lane-close validation set and return control to the orchestrator.
- [x] (2026-04-30) Refresh the shared checkpoint and confirm lane B is no longer the dominant residual cluster.
- [x] (2026-04-30) Move this completed lane plan to `docs/exec-plans/completed/` and retire it as an active workstream.

## Context and Orientation

Primary owner suites used by this lane:

- `tests/test_dataflow.py`, `tests/test_analyzers_variables.py` -> `src/sattlint/analyzers/dataflow.py`, `src/sattlint/analyzers/variables.py`
- `tests/test_analyzers_suites.py`, `tests/test_analyzers_state.py` -> `src/sattlint/analyzers/modules.py`, `src/sattlint/analyzers/reset_contamination.py`, `src/sattlint/analyzers/mms.py`, `src/sattlint/analyzers/variable_usage_reporting.py`
- `tests/test_editor_api.py` -> `src/sattlint/core/semantic.py`
- `tests/test_lsp_document.py`, `tests/test_lsp_diagnostics.py`, `tests/test_moduletype_resolution_scoped.py`, `tests/test_canonical_resolution.py` -> `src/sattlint_lsp/_server_helpers.py`, `src/sattlint_lsp/_server_document.py`, `src/sattlint_lsp/server.py`, `src/sattlint_lsp/workspace_store.py`, `src/sattlint/resolution/common.py`

## Validation and Acceptance

This lane closed successfully because:

- all listed owner suites passed with `--no-cov`,
- the next shared miss list no longer showed this lane as the dominant remaining cluster,
- no LSP-adjacent production behavior was masked by mock-only assumptions.

## Surprises & Discoveries

- Observation: analyzer closure still moved fastest through direct helper seams.
  Evidence: focused tests in `tests/test_analyzers_suites.py`, `tests/test_analyzers_variables.py`, and `tests/test_dataflow.py` reduced the biggest misses without broad new fixtures.
- Observation: LSP handler tests should keep using lightweight fake servers.
  Evidence: read-only `workspace` behavior remained easier to handle through fakes than through real server mutation.
- Observation: backlog-dominance acceptance could be met without reopening production files.
  Evidence: the decisive reductions came from owner-suite additions and the clean shared checkpoint dropped lane B below the app/devtools cluster.

## Decision Log

- Decision: group semantic core and LSP bridge work in one first-generation lane.
  Rationale: both areas shared the same editor-facing validation surface and restart rule.
  Date/Author: 2026-04-30 / Copilot (GPT-5.4)
- Decision: archive this lane once the clean shared checkpoint showed it was no longer dominant.
  Rationale: keeping it active after acceptance would misrepresent the remaining work.
  Date/Author: 2026-04-30 / Copilot (GPT-5.4)

## Outcomes & Retrospective

- Slice 1 validation: `& ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_dataflow.py tests/test_analyzers_variables.py -x -q --tb=short` -> `63 passed`.
- Slice 2 validation: `& ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_analyzers_suites.py -x -q --tb=short` -> `52 passed`.
- Slice 3 validation: `& ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_analyzers_variables.py -x -q --tb=short` -> `44 passed`.
- Lane-close validation: `& ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_analyzers_suites.py tests/test_analyzers_state.py tests/test_dataflow.py tests/test_analyzers_variables.py tests/test_editor_api.py tests/test_lsp_document.py tests/test_lsp_diagnostics.py tests/test_moduletype_resolution_scoped.py tests/test_canonical_resolution.py -x -q --tb=short` -> `243 passed`.
- Shared checkpoint refresh result: `& ".venv/Scripts/python.exe" -m pytest -q --cov-fail-under=0` -> `1236 passed, 1 warning` and about `82.35%` coverage with `4794` uncovered lines.
- Acceptance result: the refreshed artifacts put the remaining analyzer/semantic/LSP debt below the app/devtools cluster, so this first-generation lane no longer controlled the campaign backlog.

## Artifacts and Notes

- Use the active orchestrator for the current residual split and final acceptance.
- Restart the LSP after future edits to `src/sattlint_lsp/` or `src/sattlint/core/`; this completed lane did not require a restart on closeout because no such files changed in the final pass.

## Interfaces and Dependencies

Preserve strict workspace-vs-single-file behavior boundaries. Do not weaken diagnostics or add silent fallback behavior to make tests easier.
