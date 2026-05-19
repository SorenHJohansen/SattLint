# T-Wave-7 Core Support Strict Typing Promotion

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

## Purpose / Big Picture

This plan promotes the shared support files that sit between parsing, resolution, reporting, simulation, and workspace behavior. After this work lands, the semantic-core helpers, reporting helper, resolution helper, and simulation support modules in this slice will be strict-clean and represented in `tool.pyright.strict`, which removes a shared infrastructure blocker before broader app and analyzer strict-promotion work.

The observable proof is that the owned files pass strict `pyright`, the narrow owner tests for workspace snapshots, canonical resolution, variable usage reporting, and simulation remain green, and the same change updates `pyproject.toml` plus a matching approval record.

## Progress

- [x] (2026-05-18 15:10Z) Create the ExecPlan and capture the live baseline: ten support files are uncovered under the strict roots, grouped across `src/sattlint/core/`, `src/sattlint/reporting/`, `src/sattlint/resolution/`, and `src/sattlint/simulation/`.
- [x] (2026-05-18) Make the ten owned support files strict-clean.
- [x] (2026-05-18) Add the newly clean support files to `tool.pyright.strict` in `pyproject.toml` and update the existing same-day approval record.
- [x] (2026-05-18) Run focused workspace, resolution, reporting, simulation, Ruff, and ratchet validation for the slice.
- [ ] Restart the language server after the final edit because this plan touches `src/sattlint/core/`. Attempted `sattlineLsp.restartServer`, but the command was unavailable in this VS Code session.

## Surprises & Discoveries

- Observation: this support slice is shared infrastructure, not a single product surface.
  Evidence: the owned files span semantic helpers, workspace discovery, variable report rendering, alias resolution, and simulation runtime support.
- Observation: `src/sattlint/core/` edits have editor-facing consequences even when no LSP file is edited directly.
  Evidence: repository rules require restarting the language server after changes under `src/sattlint/core/`.
- Observation: the support slice is small enough to run before app, devtools, and analyzer promotion.
  Evidence: the uncovered inventory here is ten files total, much smaller than the devtools and analyzer clusters.
- Observation: the owned files were already clean under repo-basic `pyright`, but strict promotion surfaced helper-visibility and analyzer-seam issues rather than ordinary annotation gaps.
  Evidence: once the files were added to `tool.pyright.strict`, `pyright` reported 58 errors dominated by private helper imports in semantic-core files and protected `DataflowAnalyzer` usage in simulation runtime.
- Observation: `workspace_discovery.py` needed better type preservation, not new behavior.
  Evidence: the strict failures disappeared after `_resolved_path` gained overloads for `Path` versus `None`, which let the file drop dead optional branches without changing discovery order or search rules.

## Decision Log

- Decision: group `core`, `reporting`, `resolution`, and `simulation` together as one support slice.
  Rationale: these files are small shared seams that benefit from one coordinated pass before higher-level owner surfaces are cleaned up.
  Date/Author: 2026-05-18 / Copilot (GPT-5.4)
- Decision: validate this slice through behavior-oriented tests rather than only by type checking.
  Rationale: support modules matter because downstream behavior works, so the proof needs to exercise workspace, resolution, reporting, and simulation behavior directly.
  Date/Author: 2026-05-18 / Copilot (GPT-5.4)
- Decision: keep `pyproject.toml` changes until the end of the slice.
  Rationale: protected-path edits should land only after the owned support files are already strict-clean.
  Date/Author: 2026-05-18 / Copilot (GPT-5.4)
- Decision: expose a minimal public `DataflowAnalyzer` façade for simulation instead of suppressing strict warnings or duplicating analyzer logic.
  Rationale: `runtime.py` already depends on dataflow scope, state seeding, block execution, and condition semantics. Thin public wrappers preserve the existing behavior while removing strict-mode protected-member violations.
  Date/Author: 2026-05-18 / Copilot (GPT-5.4)
- Decision: fix semantic-core strict failures by reusing public helper aliases and typed dataclass factories rather than weakening the new strict coverage.
  Rationale: the root issues were cross-module private helper imports and generic `dict` default factories, so the lowest-risk fix was to clarify types and existing exports in place.
  Date/Author: 2026-05-18 / Copilot (GPT-5.4)

## Outcomes & Retrospective

The support slice is implemented and promoted. All ten owned support files now live in `tool.pyright.strict`, the same-change approval record at `.github/approvals/ratchet-rebaseline-2026-05-18.md` was extended to cover the protected-path update, and the cleanup stayed behavioral rather than architectural.

Strict promotion also needed one adjacent support seam outside the owned file list: `src/sattlint/analyzers/dataflow.py` now exposes a small public façade that `src/sattlint/simulation/runtime.py` can call without reaching through protected members. That preserved the existing simulation behavior while satisfying strict mode.

Executable proof is green for the slice: touched-file `pyright` passed with `0 errors, 0 warnings, 0 informations` on `src/sattlint/analyzers/dataflow.py` plus the ten owned support files; touched-file Ruff passed; the focused owner tests passed at `43 passed, 11 warnings`; and the protected ratchet suite passed at `23 passed`. The only incomplete closeout item is the editor-side restart, which was attempted through `sattlineLsp.restartServer` but could not run because the command was unavailable in this VS Code session.

## Context and Orientation

The owned files are:

- `src/sattlint/core/_semantic_helpers.py`
- `src/sattlint/core/_semantic_index.py`
- `src/sattlint/core/_semantic_index_reference_support.py`
- `src/sattlint/core/_semantic_snapshot.py`
- `src/sattlint/core/workspace_discovery.py`
- `src/sattlint/reporting/_variables_report_rendering.py`
- `src/sattlint/resolution/_alias_utils.py`
- `src/sattlint/simulation/__init__.py`
- `src/sattlint/simulation/_runtime_models.py`
- `src/sattlint/simulation/runtime.py`

All ten files are inside `tool.sattlint.typing_ratchet.strict_roots` and are now represented in `tool.pyright.strict` without introducing new debt entries.

The owner tests for this plan are:

- `tests/test_editor_api_workspace_snapshot.py`
- `tests/test_lsp_workspace_documents.py`
- `tests/analyzers/test_canonical_resolution.py`
- `tests/analyzers/test_moduletype_resolution_scoped.py`
- `tests/analyzers/test_variable_usage_reporting.py`
- `tests/analyzers/test_sfc_simulation.py`

This slice edits a protected config path at the end. When `pyproject.toml` changes, the same change must add or update a `.github/approvals/ratchet-rebaseline-*.md` record with `Approved-by:` and `Reason:` lines.

## Plan of Work

Start with the five `src/sattlint/core/` files because they define the shared semantic and workspace shapes that the rest of the slice consumes. Prefer typed helper return values, explicit intermediate variables, and local protocols or typed dictionaries only when they clarify an existing data shape.

After the core files are locally clean, update the reporting, resolution, and simulation helpers. Keep the slice behavioral. Do not redesign simulation APIs or workspace discovery just to satisfy the type checker.

When all ten files pass touched-file `pyright`, update `pyproject.toml` to add them to `tool.pyright.strict`, add the approval record, rerun the focused tests, and restart the language server because the core workspace path changed.

## Concrete Steps

Run all commands from the repository root.

Inspect the owned files before editing:

    rg -n "def |class |TypedDict|Protocol|cast\(|getattr\(|hasattr\(" src/sattlint/core/_semantic_helpers.py src/sattlint/core/_semantic_index.py src/sattlint/core/_semantic_index_reference_support.py src/sattlint/core/_semantic_snapshot.py src/sattlint/core/workspace_discovery.py src/sattlint/reporting/_variables_report_rendering.py src/sattlint/resolution/_alias_utils.py src/sattlint/simulation/__init__.py src/sattlint/simulation/_runtime_models.py src/sattlint/simulation/runtime.py

First focused proof after the first substantive edit:

    bash scripts/run_repo_python.sh -m pytest --no-cov tests/test_editor_api_workspace_snapshot.py tests/test_lsp_workspace_documents.py tests/analyzers/test_canonical_resolution.py tests/analyzers/test_moduletype_resolution_scoped.py tests/analyzers/test_variable_usage_reporting.py tests/analyzers/test_sfc_simulation.py -x -q --tb=short

Touched-file type and lint proof:

    bash scripts/run_repo_python.sh -m pyright src/sattlint/core/_semantic_helpers.py src/sattlint/core/_semantic_index.py src/sattlint/core/_semantic_index_reference_support.py src/sattlint/core/_semantic_snapshot.py src/sattlint/core/workspace_discovery.py src/sattlint/reporting/_variables_report_rendering.py src/sattlint/resolution/_alias_utils.py src/sattlint/simulation/__init__.py src/sattlint/simulation/_runtime_models.py src/sattlint/simulation/runtime.py
    bash scripts/run_repo_python.sh -m ruff check src/sattlint/core/_semantic_helpers.py src/sattlint/core/_semantic_index.py src/sattlint/core/_semantic_index_reference_support.py src/sattlint/core/_semantic_snapshot.py src/sattlint/core/workspace_discovery.py src/sattlint/reporting/_variables_report_rendering.py src/sattlint/resolution/_alias_utils.py src/sattlint/simulation/__init__.py src/sattlint/simulation/_runtime_models.py src/sattlint/simulation/runtime.py

Protected-path closeout proof:

    bash scripts/run_repo_python.sh -m pytest --no-cov tests/test_ratchet_policy.py tests/test_ratchet_policy_typing.py -x -q --tb=short

After the final code edit, restart the editor language server with the `sattlineLsp.restartServer` command.

## Validation and Acceptance

This plan is complete only when all ten owned support files are strict-clean, the focused workspace, resolution, reporting, and simulation tests pass, the files are represented in `tool.pyright.strict`, the approval record exists in the same change, and the language server has been restarted after the final edit.

Acceptance is behavior-focused. Workspace discovery, semantic snapshotting, alias resolution, variable report rendering, and simulation runtime behavior must remain stable from the test perspective after the typing cleanup.

## Idempotence and Recovery

The support cleanup is safe to repeat. If one shared helper annotation creates downstream breakage, revert that local change and retry with a smaller typed seam. Avoid broad signature churn that forces unrelated files into the slice.

Do not update `pyproject.toml` until the ten owned files are already strict-clean. If the protected-path edit happens early, the ratchet-policy tests become less useful because they mix inventory failure with unfinished support cleanup.

## Artifacts and Notes

Record the following evidence as work proceeds:

- Focused owner pytest: `bash scripts/run_repo_python.sh -m pytest --no-cov tests/test_editor_api_workspace_snapshot.py tests/test_lsp_workspace_documents.py tests/analyzers/test_canonical_resolution.py tests/analyzers/test_moduletype_resolution_scoped.py tests/analyzers/test_variable_usage_reporting.py tests/analyzers/test_sfc_simulation.py -x -q --tb=short` -> `43 passed, 11 warnings in 0.77s`.
- Touched-file `pyright`: `bash scripts/run_repo_python.sh -m pyright src/sattlint/analyzers/dataflow.py src/sattlint/core/_semantic_helpers.py src/sattlint/core/_semantic_index.py src/sattlint/core/_semantic_index_reference_support.py src/sattlint/core/_semantic_snapshot.py src/sattlint/core/workspace_discovery.py src/sattlint/reporting/_variables_report_rendering.py src/sattlint/resolution/_alias_utils.py src/sattlint/simulation/__init__.py src/sattlint/simulation/_runtime_models.py src/sattlint/simulation/runtime.py` -> `0 errors, 0 warnings, 0 informations`.
- Touched-file Ruff: `bash scripts/run_repo_python.sh -m ruff check src/sattlint/analyzers/dataflow.py src/sattlint/core/_semantic_helpers.py src/sattlint/core/_semantic_index.py src/sattlint/core/_semantic_index_reference_support.py src/sattlint/core/_semantic_snapshot.py src/sattlint/core/workspace_discovery.py src/sattlint/reporting/_variables_report_rendering.py src/sattlint/resolution/_alias_utils.py src/sattlint/simulation/__init__.py src/sattlint/simulation/_runtime_models.py src/sattlint/simulation/runtime.py` -> `All checks passed!`.
- Protected-path ratchet proof: `bash scripts/run_repo_python.sh -m pytest --no-cov tests/test_ratchet_policy.py tests/test_ratchet_policy_typing.py -x -q --tb=short` -> `23 passed in 0.31s`.
- Approval record path: `.github/approvals/ratchet-rebaseline-2026-05-18.md`.
- LSP restart note: attempted `sattlineLsp.restartServer`, but the command was unavailable in this VS Code session.

## Interfaces and Dependencies

This slice depends on shared semantic and workspace helpers under `src/sattlint/core/`, the variable report rendering helper, alias utilities, and simulation runtime support. Preserve the existing behavior and public module boundaries; the goal is strict-safe typing, not a redesign.

The only protected-path dependency is `pyproject.toml` plus the required approval record. No new debt entries are allowed.
