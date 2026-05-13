# T-Wave-2 Workspace Hot Reload

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

## Purpose / Big Picture

This plan closes T-003 for the actual control files the current LSP server uses. After this work lands, changes to workspace-affecting LSP settings and dependency-name lists will invalidate cached snapshots and schedule a background workspace rescan automatically, so users no longer need a manual restart after every entry-file or dependency-list change. The observable proof is that `didChangeConfiguration` and saves of `.l` or `.z` dependency files trigger a rescan in focused LSP tests, while ordinary markdown docs still stay outside the diagnostics pipeline.

## Progress

- [x] (2026-05-13) Create the ExecPlan and confirm `src/sattlint_lsp/workspace_store.py` already tracks `_config_version` and invalidates cached bundles for saved source files, but `src/sattlint_lsp/server.py` has no `workspace/didChangeConfiguration` handler and still returns early on non-diagnostic saves, so `.l` and `.z` dependency lists never trigger workspace rescans.
- [ ] Add a configuration-change handler that reconfigures the snapshot store and schedules a workspace scan when `entry_file`, `mode`, or other workspace settings change.
- [ ] Treat `.l` and `.z` dependency-name lists inside the workspace root as workspace-affecting saves that invalidate cached entries and trigger rescans.
- [ ] Add focused LSP tests and rerun the narrow workspace or diagnostics slice.
- [ ] Restart the LSP server after the code change as required by repository policy.

## Surprises & Discoveries

Observation: the tracker’s original “WORKFLOW.md-equivalent” wording does not match what the current LSP server actually reads.
Evidence: the current LSP code reads workspace root, entry-file, and mode settings plus on-disk source or dependency files; it does not read markdown workflow documents.

Observation: most of the invalidation machinery already exists.
Evidence: `WorkspaceSnapshotStore.invalidate_path` already marks affected entries stale and increments generation counters, and `on_did_save` already calls `_schedule_workspace_scan` for program-file saves.

Observation: the real non-program control files are `.l` and `.z` dependency-name lists, not arbitrary docs.
Evidence: repository invariants define `.l` and `.z` as dependency-name lists for workspace resolution, while `on_did_save` currently clears diagnostics and returns before any rescan for those files.

## Decision Log

Decision: watch only settings and dependency-name lists that actually affect workspace resolution.
Rationale: broad markdown watching would add noise without affecting the semantic bundle, while `.l`, `.z`, and workspace settings directly change entry selection or dependency context.
Date/Author: 2026-05-13 / Copilot (GPT-5.4)

Decision: reuse the existing workspace-scan scheduling and generation counters instead of adding a second debounce system.
Rationale: the current LSP server already has `workspace_scan_generation`, a background scan thread, and `_config_version` checks in the snapshot store. A parallel debounce path would create race conditions immediately.
Date/Author: 2026-05-13 / Copilot (GPT-5.4)

Decision: keep arbitrary markdown files out of the diagnostics path.
Rationale: this debt item is about workspace semantics and dependency resolution, not about every document in the workspace.
Date/Author: 2026-05-13 / Copilot (GPT-5.4)

## Outcomes & Retrospective

Planning baseline only. The repository already has the cache invalidation primitives needed for hot reload, but it still relies on initialization and source-file saves instead of explicit configuration changes and dependency-list saves.

## Context and Orientation

The controlling cache and discovery code lives in `src/sattlint_lsp/workspace_store.py`. `WorkspaceSnapshotStore.ensure_configured` tracks workspace root and settings state. `resolve_entry_file` already knows how to use the configured `entry_file` setting and the current workspace discovery. `invalidate_path` already marks affected entries stale and returns the entry files that should be rescanned.

The controlling LSP handlers live in `src/sattlint_lsp/server.py`. `on_initialize` resets server state and schedules the first workspace scan. `on_did_save` currently invalidates and rescans only when the saved file is treated as a diagnostic source. There is no `workspace/didChangeConfiguration` handler today.

The repository’s workspace invariants matter here. `.s` and `.x` stay the live diagnostic program files. `.l` and `.z` stay dependency-name lists used for workspace resolution, not normal diagnostic documents. `ControlLib` remains an expected unavailable dependency in workspace flows and must not be reclassified as a normal missing-code error. After any edit under `src/sattlint_lsp/`, the implementation must be followed by the `sattlineLsp.restartServer` command.

## Plan of Work

Start by adding a `workspace/didChangeConfiguration` handler in `src/sattlint_lsp/server.py`. That handler should normalize the new settings through the existing settings model, call the snapshot-store configuration path again, clear or preserve diagnostics appropriately, and schedule a workspace scan if the effective configuration changed.

Next, update the save path in `src/sattlint_lsp/server.py` so `.l` and `.z` dependency files under the workspace root are treated as workspace-affecting control files instead of dead ends. Saving one of those files should not publish program diagnostics for the list file itself, but it should invalidate the affected entry files and schedule the same background scan used for program saves.

Keep the implementation narrow. Do not collapse strict single-file `syntax-check` behavior into workspace-mode semantics. Do not widen diagnostics to arbitrary non-program documents. Reuse the existing invalidation and background-scan paths rather than creating a second refresh mechanism.

## Concrete Steps

Run all commands from the repository root.

Inspect the current configuration, save, and invalidation seams before editing code:

    rg -n "on_initialize|didSave|schedule_workspace_scan|ensure_configured|invalidate_path" src/sattlint_lsp/server.py src/sattlint_lsp/workspace_store.py

After implementing the configuration-change and dependency-list hot reload, run the narrow validation first:

    python scripts/run_repo_python.py -m pytest --no-cov tests/test_lsp_document.py tests/test_lsp_diagnostics.py -x -q --tb=short

After the tests pass, restart the language server as required for this surface:

    sattlineLsp.restartServer

Run touched-file quality gates after the focused tests pass:

    python scripts/run_repo_python.py -m ruff check src/sattlint_lsp/server.py src/sattlint_lsp/workspace_store.py tests/test_lsp_document.py tests/test_lsp_diagnostics.py
    python scripts/run_repo_python.py -m pyright src/sattlint_lsp/server.py src/sattlint_lsp/workspace_store.py tests/test_lsp_document.py tests/test_lsp_diagnostics.py

## Validation and Acceptance

Acceptance requires focused LSP tests that prove two behaviors. First, changing workspace configuration such as `entry_file` or `mode` must reschedule a workspace scan without restarting the server manually. Second, saving a workspace `.l` or `.z` dependency list must invalidate the relevant cached entry or entries and schedule a rescan, while markdown and other irrelevant non-program files must continue to bypass diagnostics.

## Idempotence and Recovery

This plan is safe to implement incrementally. Add the configuration-change handler first, validate it, then add dependency-list save handling and rerun the same tests. If a new watch path causes excessive rescans, narrow it back to effective setting changes and `.l` or `.z` files under the workspace root. Keep the existing program-save behavior unchanged while iterating.

## Artifacts and Notes

Record one short test artifact for each hot-reload path: a `didChangeConfiguration` test that observes a scheduled scan, and a dependency-list save test that observes `invalidate_path` plus a scheduled rescan. Also record that the implementation was followed by `sattlineLsp.restartServer`.

## Interfaces and Dependencies

The implementation surface is `src/sattlint_lsp/server.py` and `src/sattlint_lsp/workspace_store.py`. Reuse the current settings parsing, cache invalidation, and background scan scheduling already present in this package. Do not introduce a second cache or a second background-scan subsystem.
