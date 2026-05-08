# T-009 LSP Debt Closeout

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

## Purpose / Big Picture

T-009 says the language-server code still has blocking import and typing debt in `src/sattlint_lsp/server.py` and `src/sattlint_lsp/_server_document.py`. The current repository state does not match that description: the focused owner validation already passes, Ruff is clean, and Pyright reports zero issues on the named files. This plan exists to turn that stale debt item into an executable closeout workflow. The observable outcome is simple: either the named LSP problem really still exists and is repaired in the smallest possible slice, or the repo proves the debt is already gone and the tracker is updated with evidence instead of carrying a stale open item.

## Progress

- [x] (2026-05-04 00:00Z) Create this ExecPlan from current T-009 verification evidence and the current tracker text.
- [x] (2026-05-04) Re-run the tracker's focused acceptance route on the current worktree and record the exact output in this file.
- [x] (2026-05-04) Focused route stayed green, so no repair under `src/sattlint_lsp/server.py` or `src/sattlint_lsp/_server_document.py` was required.
- [x] (2026-05-04) Focused route passed without code changes, so update `docs/exec-plans/tech-debt-tracker.md` so T-009 is no longer an open stale debt item.
- [x] (2026-05-04) No code changes landed under `src/sattlint_lsp/` or `src/sattlint/core/`, so no language server restart was required.
- [x] (2026-05-04) Move this closed verification record to `docs/exec-plans/completed/` now that the tracker evidence is recorded.

## Surprises & Discoveries

- Observation: the tracker text for T-009 is stale relative to the current codebase.
  Evidence: `python scripts/run_repo_python.py -m pytest --no-cov tests/test_lsp_document.py tests/test_lsp_diagnostics.py tests/test_editor_api.py -x -q --tb=short` completed at `104 passed`, `python scripts/run_repo_python.py -m ruff check src/sattlint_lsp/server.py src/sattlint_lsp/_server_document.py tests/test_lsp_document.py tests/test_lsp_diagnostics.py tests/test_editor_api.py` reported `All checks passed!`, and `python scripts/run_repo_python.py -m pyright src/sattlint_lsp/server.py src/sattlint_lsp/_server_document.py tests/test_lsp_document.py tests/test_lsp_diagnostics.py tests/test_editor_api.py` reported `0 errors, 0 warnings, 0 informations`.
- Observation: the source files already contain the threading and guarded thread-start behavior called out by the debt item.
  Evidence: `src/sattlint_lsp/server.py` imports `threading` and stores `workspace_scan_condition` plus `workspace_scan_thread`; `src/sattlint_lsp/_server_document.py` builds the worker thread inside `_schedule_workspace_scan()` and starts it only after a `None` check.
- Observation: there is already an active broad workstream claiming some LSP files and tests.
  Evidence: the shared active-claim lock currently lists active claims on `src/sattlint_lsp/_server_document.py`, `tests/test_lsp_document.py`, and `tests/test_lsp_diagnostics.py` under broader coverage and repo-fix streams, so any code edit must be coordinated before it lands.

## Decision Log

- Decision: treat T-009 as a verification-first closeout plan instead of assuming a code change is still required.
  Rationale: the current focused validation and the current source state both contradict the tracker's description of an open blocking defect.
  Date/Author: 2026-05-04 / Copilot (GPT-5.4)
- Decision: keep the working scope limited to the two files named by the tracker and the three existing owner suites.
  Rationale: if the debt has truly regressed, the smallest defensible repair should stay inside the original controlling surface.
  Date/Author: 2026-05-04 / Copilot (GPT-5.4)

## Outcomes & Retrospective

The tracker entry, not the LSP code, was the stale artifact. The focused owner route reproduced the already-clean state on the current worktree, so the plan closed with documentation-only edits and preserved the active claims on the LSP source files for other workstreams.

Archive outcome complete: this file is now a historical closeout record rather than an active plan because the verification route and tracker update are both done.

## Context and Orientation

SattLint's language-server implementation lives under `src/sattlint_lsp/`. In this repository, "LSP" means the editor-facing process that publishes diagnostics, hover data, definitions, references, and rename support. The two files named by T-009 own the top-level server lifecycle and document-diagnostics orchestration:

- `src/sattlint_lsp/server.py` defines the `SattLineLanguageServer` class, initializes shared state, and wires pygls feature handlers such as open, change, save, close, hover, definition, and reference handlers.
- `src/sattlint_lsp/_server_document.py` owns document-state recording, local analysis reuse, workspace-scan scheduling, and publication of syntax and semantic diagnostics.

The nearest existing tests already exercise this surface.

Primary owner suites for this plan:

- `tests/test_lsp_document.py`, `tests/test_lsp_diagnostics.py`, `tests/test_editor_api.py` -> `src/sattlint_lsp/server.py`, `src/sattlint_lsp/_server_document.py`

The repo has one important invariant for this surface: if code changes under `src/sattlint_lsp/`, `src/sattlint/core/`, `src/sattlint/editor_api.py`, or `vscode/sattline-vscode/`, the language server must be restarted after validation. The repo also distinguishes strict one-file syntax validation from workspace-aware editor behavior; this plan must not blur those two modes just to close a debt item.

## Plan of Work

Start by rerunning the exact acceptance route already attached to T-009. That route is narrow enough to falsify the debt claim without touching code. If it fails, stay inside the tracker-named files and use the failing assertion, Ruff message, or Pyright diagnostic as the only guide for the repair. Do not reopen broad LSP or semantic exploration until that focused route is green.

If the route passes unchanged, treat the debt item itself as the bug. Update `docs/exec-plans/tech-debt-tracker.md` so it no longer claims an open blocking LSP defect that the repository cannot reproduce. If the broader project wants to preserve historical context, convert the entry into a completed item with a short note that the cleanup is already present in the current main branch. If the route fails only because of an unrelated active-claim conflict, record that explicitly instead of forcing a code edit into a shared file.

## Concrete Steps

Run commands from the repository root.

Per-slice first validations:

    python scripts/run_repo_python.py -m pytest --no-cov tests/test_lsp_document.py tests/test_lsp_diagnostics.py tests/test_editor_api.py -x -q --tb=short
    python scripts/run_repo_python.py -m ruff check src/sattlint_lsp/server.py src/sattlint_lsp/_server_document.py tests/test_lsp_document.py tests/test_lsp_diagnostics.py tests/test_editor_api.py
    python scripts/run_repo_python.py -m pyright src/sattlint_lsp/server.py src/sattlint_lsp/_server_document.py tests/test_lsp_document.py tests/test_lsp_diagnostics.py tests/test_editor_api.py

If a code repair is required, rerun the same three commands before reading other files.

If a code repair lands under the LSP surface, restart the language server after the focused validations pass:

    Run the VS Code command `sattlineLsp.restartServer`.

If the focused route passes unchanged, update the tracker entry instead of forcing source edits:

    Claim `docs/exec-plans/tech-debt-tracker.md` in the shared `.git/sattlint-ai-coordination/current_work_lock.json` lock state.
    Change T-009 from `Open` to `Done` or replace the stale problem statement with the real remaining issue, if any.

Expected success transcript for the current known-good state:

    104 passed in about 7 seconds
    All checks passed!
    0 errors, 0 warnings, 0 informations

## Validation and Acceptance

This plan is complete when all of the following are true:

- the focused LSP owner route passes,
- Ruff and Pyright remain clean on the named source files and owner tests,
- no unrelated LSP or semantic files were edited to satisfy the debt item,
- the tracker no longer records T-009 as an open blocking defect unless a fresh failing reproduction proves one still exists,
- if any LSP source file changed, the language server was restarted and that restart was recorded in this file.

## Idempotence and Recovery

The verification steps are safe to rerun. If the first focused route passes, do not invent churn just to "do work" under this plan. If a shared-file claim blocks a required code edit, stop at the reproduction point, document the exact blocker in `Progress`, and resume only after the coordinating ledger is updated. If a tracker edit conflicts with another branch, keep the source tree untouched and record the proof needed for a later tracker-only cleanup.

## Artifacts and Notes

- `python scripts/run_repo_python.py -m pytest --no-cov tests/test_lsp_document.py tests/test_lsp_diagnostics.py tests/test_editor_api.py -x -q --tb=short` -> `104 passed in 6.16s`
- `python scripts/run_repo_python.py -m ruff check src/sattlint_lsp/server.py src/sattlint_lsp/_server_document.py tests/test_lsp_document.py tests/test_lsp_diagnostics.py tests/test_editor_api.py` -> `All checks passed!`
- `python scripts/run_repo_python.py -m pyright src/sattlint_lsp/server.py src/sattlint_lsp/_server_document.py tests/test_lsp_document.py tests/test_lsp_diagnostics.py tests/test_editor_api.py` -> `0 errors, 0 warnings, 0 informations`
- No files under `src/sattlint_lsp/` or `src/sattlint/core/` changed during closeout, so no language-server restart was required.

## Interfaces and Dependencies

Use the existing LSP interfaces only. Do not introduce new test harnesses, new background workers, or new editor wiring just to satisfy this plan. `server.py` remains the pygls feature-registration layer; `_server_document.py` remains the document-state and workspace-diagnostics layer; `tests/test_lsp_document.py`, `tests/test_lsp_diagnostics.py`, and `tests/test_editor_api.py` remain the nearest owners.
