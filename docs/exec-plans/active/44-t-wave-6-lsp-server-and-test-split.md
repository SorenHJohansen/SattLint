# T-Wave-6 LSP Server and Test Split

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

## Purpose / Big Picture

This plan addresses the workspace and editor debt from the 2026-05-15 architecture review. `src/sattlint_lsp/server.py` still carries too much handler logic in one owner file, while `tests/test_lsp_diagnostics.py` and `tests/test_lsp_document.py` are large enough to make every LSP change expensive to validate. After this work lands, the language-server owner will be a thinner wire layer over helper modules, the biggest LSP tests will be split by behavior area, and touched workspace helper code will carry stronger focused coverage.

`src/sattlint_lsp/_server_helpers.py` is 860 lines and has no ratchet entry. It is the likely destination for handler logic displaced from `server.py`, so without an explicit plan it would absorb the structural debt instead of dispersing it. This plan includes decomposing `_server_helpers.py` and adding its ratchet entry.

The observable proof is that definition, hover, reference, rename, completion, and workspace-diagnostic behavior still pass focused tests, while the server owner, the helpers file, and adjacent tests shrink and remain easier to route. Because this surface touches `src/sattlint_lsp/`, the work must finish with an LSP server restart.

## Progress

- [x] (2026-05-15) Create the ExecPlan and confirm `src/sattlint_lsp/server.py` is 585 lines, `tests/test_lsp_diagnostics.py` is 1657 lines, `tests/test_lsp_document.py` is 1434 lines, and the repo-health snapshot still flags `src/sattlint_lsp/_server_document.py` as a coverage-on-touch owner.
- [x] (2026-05-15) Gap review adds `src/sattlint_lsp/_server_helpers.py` (860 lines, no ratchet entry) as an explicit decomposition target and precondition ratchet step.
- [ ] Add a baseline ratchet entry for `_server_helpers.py` in `artifacts/analysis/file_debt_ratchet.json` using its current line count as the `current_baseline` with `must_shrink` and a 500-line target.
- [ ] Move definition, hover, reference, rename, and completion handler bodies out of `server.py` into dedicated helper modules while keeping `SattLineLanguageServer` state ownership stable.
- [ ] Decompose `_server_helpers.py` by splitting symbol-resolution and diagnostics-collection behavior into `src/sattlint_lsp/_server_symbol_helpers.py` and workspace-scan scheduling helpers into `src/sattlint_lsp/_server_scan_helpers.py`, keeping the existing import names stable.
- [ ] Split `tests/test_lsp_diagnostics.py` and `tests/test_lsp_document.py` into smaller behavior slices, such as document lifecycle, workspace scanning, navigation, rename, and completion.
- [ ] Add or extend focused coverage for `src/sattlint_lsp/_server_document.py` on the specific paths touched by the split.
- [ ] Run focused LSP pytest, touched-file Ruff and Pyright, and restart the server with `sattlineLsp.restartServer`.

## Surprises & Discoveries

Observation: `server.py` already imports a rich helper family.
Evidence: the file already depends on `_server_document` and `_server_helpers`, so the next shrink step should move handler logic toward those seams rather than inventing a second server abstraction.

Observation: the remaining concentration is mostly in request handlers.
Evidence: `server.py` is dominated by `on_initialize`, `on_did_open`, `on_did_change`, `on_did_save`, `on_definition`, `on_hover`, `on_references`, `on_rename`, and `on_completion`.

Observation: `_server_helpers.py` is larger than `server.py` and has no ratchet entry.
Evidence: `src/sattlint_lsp/_server_helpers.py` is 860 lines, making it the largest file in the LSP package. It has no entry in `file_debt_ratchet.json`, so handler logic moved from `server.py` will accumulate there unless this plan explicitly decomposes it in the same slice.

Observation: the largest adjacent debt is test concentration, not missing features.
Evidence: the LSP tests already cover document and diagnostic behavior, but they live in two very large files that make isolated refactors and selective reruns harder than necessary.

Observation: workspace helper coverage matters immediately on touch.
Evidence: the repo-health snapshot lists `src/sattlint_lsp/_server_document.py` as a coverage-ratcheted owner, so any helper extraction that modifies document or workspace scan behavior must bring focused tests with it.

## Decision Log

Decision: keep `server.py` as the wire layer and server-state owner.
Rationale: the `LanguageServer` instance and handler registration belong there. The debt is the amount of handler logic, not the existence of the server file itself.
Date/Author: 2026-05-15 / Copilot (GPT-5.4)

Decision: split tests alongside code instead of waiting until after the server shrink.
Rationale: the oversized tests are part of the refactor cost. Leaving them intact would make the LSP changes harder to validate and maintain.
Date/Author: 2026-05-15 / Copilot (GPT-5.4)

Decision: decompose `_server_helpers.py` in the same slice as `server.py`.
Rationale: `_server_helpers.py` is larger than `server.py` and has no structural guard. Extracting handler logic from `server.py` without also splitting `_server_helpers.py` would shift the debt rather than reduce it.
Date/Author: 2026-05-15 / Copilot (GPT-5.4)

Decision: add a ratchet entry for `_server_helpers.py` before starting handler extraction.
Rationale: without a `must_shrink` entry, the file can silently absorb displaced code from `server.py`. Setting the baseline first closes that escape path.
Date/Author: 2026-05-15 / Copilot (GPT-5.4)

## Outcomes & Retrospective

At creation time, no code has landed yet. The current outcome is a scoped LSP refactor plan that treats the server owner, adjacent helper coverage, and oversized tests as one cohesive slice instead of three disconnected chores.

## Context and Orientation

The main wire-layer owner is `src/sattlint_lsp/server.py`. It instantiates `SattLineLanguageServer`, owns the shared server state, and registers the language-server request handlers.

The main helper surfaces are `src/sattlint_lsp/_server_document.py` and `src/sattlint_lsp/_server_helpers.py`. Those files already own document-path handling, workspace-scan scheduling, symbol resolution, diagnostics collection, and helper utilities for rename and navigation behavior.

The closest tests are `tests/test_lsp_document.py` and `tests/test_lsp_diagnostics.py`. In this repository, the post-edit operational rule matters: after changing `src/sattlint_lsp/`, the language server must be restarted with `sattlineLsp.restartServer`.

## Plan of Work

Start by adding the baseline ratchet entry for `_server_helpers.py` in `artifacts/analysis/file_debt_ratchet.json`.

Then move the navigation handlers out of `server.py`. Put definition, hover, and references in `src/sattlint_lsp/_server_navigation.py`, and put rename plus completion in `src/sattlint_lsp/_server_rename_completion.py`. Keep `server.py` responsible for registration and server-state access.

Then decompose `_server_helpers.py`. Move symbol-resolution and diagnostics-collection helpers into `src/sattlint_lsp/_server_symbol_helpers.py`, and move workspace-scan scheduling helpers into `src/sattlint_lsp/_server_scan_helpers.py`. Keep the existing public names stable so callers in `server.py` and `_server_document.py` require only import-path updates.

Then split the large LSP tests by behavior area. Move document lifecycle and workspace-scan behavior into `tests/test_lsp_workspace_documents.py`, move navigation behavior into `tests/test_lsp_navigation.py`, and move rename or completion behavior into `tests/test_lsp_rename_completion.py`. Update imports and shared test support only as much as needed to keep the new split readable.

Finally, add focused `_server_document.py` coverage for the exact code touched by the split. Do not widen this plan into unrelated client-extension changes unless the helper extraction makes a genuine server or client contract bug visible.

## Concrete Steps

Run all commands from the repository root.

Inspect the current server and test surfaces before editing code:

    wc -l src/sattlint_lsp/server.py src/sattlint_lsp/_server_helpers.py tests/test_lsp_diagnostics.py tests/test_lsp_document.py
    rg -n "def on_|_server_document|_server_helpers|_load_snapshot_bundle|_publish_workspace_diagnostics_for_paths" src/sattlint_lsp/server.py src/sattlint_lsp/_server_document.py src/sattlint_lsp/_server_helpers.py

After the server and tests are split, run the narrow validation first:

    bash scripts/run_repo_python.sh -m pytest --no-cov tests/test_lsp_document.py tests/test_lsp_diagnostics.py -x -q --tb=short

Run touched-file quality gates after the focused tests pass:

    bash scripts/run_repo_python.sh -m ruff check src/sattlint_lsp/server.py src/sattlint_lsp/_server_document.py src/sattlint_lsp/_server_helpers.py src/sattlint_lsp/_server_navigation.py src/sattlint_lsp/_server_rename_completion.py src/sattlint_lsp/_server_symbol_helpers.py src/sattlint_lsp/_server_scan_helpers.py tests/test_lsp_document.py tests/test_lsp_diagnostics.py tests/test_lsp_workspace_documents.py tests/test_lsp_navigation.py tests/test_lsp_rename_completion.py
    bash scripts/run_repo_python.sh -m pyright src/sattlint_lsp/server.py src/sattlint_lsp/_server_document.py src/sattlint_lsp/_server_helpers.py src/sattlint_lsp/_server_navigation.py src/sattlint_lsp/_server_rename_completion.py src/sattlint_lsp/_server_symbol_helpers.py src/sattlint_lsp/_server_scan_helpers.py tests/test_lsp_document.py tests/test_lsp_diagnostics.py tests/test_lsp_workspace_documents.py tests/test_lsp_navigation.py tests/test_lsp_rename_completion.py

Finish with the required server restart:

    sattlineLsp.restartServer

## Validation and Acceptance

Acceptance requires the same LSP behavior with smaller owners. Focused tests must still prove document open or change flows, workspace diagnostics, definition lookup, hover, references, rename, and completion behavior. `server.py` must become a thinner wire layer, and the biggest LSP tests must no longer remain one-file bottlenecks for every change. Any touched `_server_document.py` path must be covered by focused tests in the same slice.

## Idempotence and Recovery

This plan is safe to execute in narrow steps. Move one handler family at a time and rerun the same focused tests. Split one large test file at a time. If a helper extraction changes workspace or navigation behavior, keep a thin adapter in `server.py` and restore the old handler path before continuing.

## Artifacts and Notes

Current owner sizes at plan creation time:

    585 src/sattlint_lsp/server.py
    1657 tests/test_lsp_diagnostics.py
    1434 tests/test_lsp_document.py

Added by gap review (2026-05-15):

    860 src/sattlint_lsp/_server_helpers.py  (no ratchet entry yet — add baseline as first step)

Current related coverage-on-touch note: `src/sattlint_lsp/_server_document.py` remains below full-file proof in the repo-health snapshot and must pick up focused coverage if touched.

## Interfaces and Dependencies

The implementation surface is `src/sattlint_lsp/server.py`, `src/sattlint_lsp/_server_document.py`, and `src/sattlint_lsp/_server_helpers.py`, plus the adjacent LSP tests. Preserve the current language-server feature set and the repository's LSP restart requirement after edits in `src/sattlint_lsp/`.
