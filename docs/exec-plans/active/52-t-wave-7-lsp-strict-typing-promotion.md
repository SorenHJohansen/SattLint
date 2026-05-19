# T-Wave-7 LSP Strict Typing Promotion

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

## Purpose / Big Picture

This plan makes the remaining language-server helper files under `src/sattlint_lsp/` ready for full strict coverage. After this work lands, the helper modules that power navigation, rename or completion behavior, workspace resolution, and scan helpers will be type-clean and explicitly listed in `tool.pyright.strict` instead of being uncovered strict-root inventory.

The observable proof is that the focused LSP tests remain green, the owned files pass `pyright`, and the same change updates `pyproject.toml` plus a matching approval record so the LSP slice stops blocking full strict coverage.

## Progress

- [x] (2026-05-18 15:10Z) Create the ExecPlan and capture the live baseline: `src/sattlint_lsp/` has five uncovered helper files and the full-strict audit reports eight LSP diagnostics across that helper cluster.
- [x] (2026-05-18 13:24Z) Make the five uncovered LSP helper modules strict-clean by replacing cross-helper private imports with explicit compatibility aliases in `src/sattlint_lsp/_server_helpers.py` and `src/sattlint_lsp/_server_navigation.py`.
- [x] (2026-05-18 13:24Z) Add the newly clean LSP helper files to `tool.pyright.strict` in `pyproject.toml` and extend `.github/approvals/ratchet-rebaseline-2026-05-18.md` to cover the same-change LSP promotion.
- [x] (2026-05-18 13:24Z) Run focused LSP validation, temporary narrow strict `pyright`, protected-path ratchet proof, touched-file Ruff, and touched-file Pyright for the slice.
- [ ] Restart the language server after the final code change so editor behavior uses the updated Python server code. Attempted via `sattlineLsp.restartServer`, but the command was unavailable in the current editor session.

## Surprises & Discoveries

- Observation: the LSP strict backlog is small enough to be its own bounded slice.
  Evidence: the uncovered inventory for `src/sattlint_lsp` is exactly five root-level helper files.
- Observation: this slice touches behavior that users see directly in the editor.
  Evidence: the owned files include navigation, rename or completion, symbol helper, workspace helper, and scan helper modules, so acceptance must include LSP owner tests rather than type cleanup alone.
- Observation: LSP edits require an explicit server restart in this repository.
  Evidence: the repo instructions say that after changing `src/sattlint_lsp/`, the server should be restarted with the `sattlineLsp.restartServer` command.
- Observation: a direct file-based `pyright` run was a false negative for the backlog.
  Evidence: the five owned helper files passed a plain `pyright` invocation before promotion, but a temporary narrow config that listed them under `strict` reproduced the exact eight backlog diagnostics.
- Observation: all eight strict blockers were private-usage diagnostics rather than deeper type-shape failures.
  Evidence: the temporary strict run reported one private import from `src/sattlint_lsp/_server_navigation.py` and seven private imports from `src/sattlint_lsp/_server_helpers.py`.
- Observation: the restart command is registered in the VS Code extension source but not available in this editor session.
  Evidence: `vscode/sattline-vscode/package.json` and `vscode/sattline-vscode/extension.js` register `sattlineLsp.restartServer`, but direct command invocation from this session failed.

## Decision Log

- Decision: keep the LSP strict-promotion work separate from parser strict-promotion work.
  Rationale: the user-visible behaviors, tests, and invariants differ even though both slices were low-count inventory groups.
  Date/Author: 2026-05-18 / Copilot (GPT-5.4)
- Decision: validate through the LSP owner suites first and through manual server restart second.
  Rationale: the tests are the repeatable proof, and the restart is the final step that makes the changed server code visible to editor sessions.
  Date/Author: 2026-05-18 / Copilot (GPT-5.4)
- Decision: keep `pyproject.toml` edits at the end of the slice.
  Rationale: protected-path churn is only worth taking once the helper files are already strict-clean.
  Date/Author: 2026-05-18 / Copilot (GPT-5.4)
- Decision: expose narrow compatibility aliases instead of suppressing `reportPrivateUsage`.
  Rationale: the helpers were already sharing these seams. Small public aliases make that sharing explicit under strict mode without a broader LSP refactor.
  Date/Author: 2026-05-18 / Copilot (GPT-5.4)

## Outcomes & Retrospective

The five owned LSP helper modules are now strict-clean and listed in `tool.pyright.strict`. The implementation stayed narrow: `src/sattlint_lsp/_server_helpers.py` and `src/sattlint_lsp/_server_navigation.py` now expose explicit compatibility aliases for intentionally shared helper seams, and the strict-failing imports in `src/sattlint_lsp/_server_symbol_helpers.py` and `src/sattlint_lsp/_server_rename_completion.py` now target those public aliases instead of sibling-private names.

Validation passed with `bash scripts/run_repo_python.sh -m pytest --no-cov tests/test_lsp_navigation.py tests/test_lsp_rename_completion.py tests/test_lsp_document.py tests/test_lsp_workspace_documents.py tests/test_lsp_diagnostics.py -x -q --tb=short`, a temporary narrow strict `pyright` config for the five owned helper files, `bash scripts/run_repo_python.sh -m pytest --no-cov tests/test_ratchet_policy.py tests/test_ratchet_policy_typing.py -x -q --tb=short`, `bash scripts/run_repo_python.sh -m pyright src/sattlint_lsp/_server_helpers.py src/sattlint_lsp/_server_navigation.py src/sattlint_lsp/_server_rename_completion.py src/sattlint_lsp/_server_scan_helpers.py src/sattlint_lsp/_server_symbol_helpers.py src/sattlint_lsp/_server_workspace.py`, and `bash scripts/run_repo_python.sh -m ruff check src/sattlint_lsp/_server_helpers.py src/sattlint_lsp/_server_navigation.py src/sattlint_lsp/_server_rename_completion.py src/sattlint_lsp/_server_scan_helpers.py src/sattlint_lsp/_server_symbol_helpers.py src/sattlint_lsp/_server_workspace.py`.

The protected-path update used `.github/approvals/ratchet-rebaseline-2026-05-18.md`. The only remaining gap is operational: `sattlineLsp.restartServer` was attempted after the final code changes, but the command was unavailable in this editor session, so the required post-edit restart could not be executed from here.

## Context and Orientation

The owned files are:

- `src/sattlint_lsp/_server_navigation.py`
- `src/sattlint_lsp/_server_rename_completion.py`
- `src/sattlint_lsp/_server_scan_helpers.py`
- `src/sattlint_lsp/_server_symbol_helpers.py`
- `src/sattlint_lsp/_server_workspace.py`

These files are inside `tool.sattlint.typing_ratchet.strict_roots` but are not yet represented in `tool.pyright.strict` or the debt allowlist. They support the public Python language-server process exposed by `src/sattlint_lsp/server.py` and the workspace-loading behavior that editor users see.

The narrow owner tests are `tests/test_lsp_document.py`, `tests/test_lsp_workspace_documents.py`, `tests/test_lsp_rename_completion.py`, `tests/test_lsp_navigation.py`, and `tests/test_lsp_diagnostics.py`. `tests/helpers/lsp_support.py` is supporting test infrastructure and should be read if a helper signature change affects test setup.

Like every strict-promotion slice that edits `pyproject.toml`, this plan must add or update a matching approval record under `.github/approvals/ratchet-rebaseline-*.md` with `Approved-by:` and `Reason:` lines.

## Plan of Work

Start by making the helper modules strict-clean with explicit annotations and narrow data shapes. Avoid broad LSP server refactors. The goal is to make the existing helper seams understandable to `pyright`, not to redesign request routing.

Once the files are locally clean, update `pyproject.toml` to add the five LSP helpers to `tool.pyright.strict`. Do not add new debt. Then rerun the focused LSP tests, touched-file `pyright`, and touched-file Ruff.

Finish by restarting the editor language server so any interactive verification runs against the new Python code.

## Concrete Steps

Run commands from the repository root.

Inspect the owned files before editing:

    rg -n "def |class |TypedDict|Protocol|cast\(" src/sattlint_lsp/_server_navigation.py src/sattlint_lsp/_server_rename_completion.py src/sattlint_lsp/_server_scan_helpers.py src/sattlint_lsp/_server_symbol_helpers.py src/sattlint_lsp/_server_workspace.py

First focused proof after the first substantive edit:

    bash scripts/run_repo_python.sh -m pytest --no-cov tests/test_lsp_navigation.py tests/test_lsp_rename_completion.py tests/test_lsp_document.py tests/test_lsp_workspace_documents.py tests/test_lsp_diagnostics.py -x -q --tb=short

Touched-file type and lint proof:

    bash scripts/run_repo_python.sh -m pyright src/sattlint_lsp/_server_navigation.py src/sattlint_lsp/_server_rename_completion.py src/sattlint_lsp/_server_scan_helpers.py src/sattlint_lsp/_server_symbol_helpers.py src/sattlint_lsp/_server_workspace.py
    bash scripts/run_repo_python.sh -m ruff check src/sattlint_lsp/_server_navigation.py src/sattlint_lsp/_server_rename_completion.py src/sattlint_lsp/_server_scan_helpers.py src/sattlint_lsp/_server_symbol_helpers.py src/sattlint_lsp/_server_workspace.py

Protected-path closeout proof:

    bash scripts/run_repo_python.sh -m pytest --no-cov tests/test_ratchet_policy.py tests/test_ratchet_policy_typing.py -x -q --tb=short

After code and tests are green, restart the editor language server with the `sattlineLsp.restartServer` command before any interactive spot-check.

## Validation and Acceptance

This plan is complete only when all five owned LSP helper files are strict-clean, the focused LSP owner tests pass, the files are added to `tool.pyright.strict`, the approval record exists in the same change, and the server has been restarted after the final edit.

Acceptance also requires stable behavior: navigation, rename or completion, diagnostics, and workspace document handling must behave the same from the test perspective after the typing cleanup.

## Idempotence and Recovery

The typing cleanup is safe to repeat. If one helper annotation causes a behavioral regression, revert that local change and retry with narrower typed intermediates or a smaller helper extraction.

Do not update `pyproject.toml` before the LSP helpers are already strict-clean. If an approval record is added early, the ratchet tests become harder to interpret because inventory and behavior failures overlap.

## Artifacts and Notes

- Focused LSP proof: `bash scripts/run_repo_python.sh -m pytest --no-cov tests/test_lsp_navigation.py tests/test_lsp_rename_completion.py tests/test_lsp_document.py tests/test_lsp_workspace_documents.py tests/test_lsp_diagnostics.py -x -q --tb=short` passed with 83 tests green.
- Temporary narrow strict proof: a temporary `pyright` config that listed the five owned helper files under `strict` passed with 0 errors after the compatibility-alias cleanup.
- Protected-path proof: `bash scripts/run_repo_python.sh -m pytest --no-cov tests/test_ratchet_policy.py tests/test_ratchet_policy_typing.py -x -q --tb=short` passed with 23 tests green.
- Touched-file proof: `bash scripts/run_repo_python.sh -m pyright src/sattlint_lsp/_server_helpers.py src/sattlint_lsp/_server_navigation.py src/sattlint_lsp/_server_rename_completion.py src/sattlint_lsp/_server_scan_helpers.py src/sattlint_lsp/_server_symbol_helpers.py src/sattlint_lsp/_server_workspace.py` passed with 0 errors, and the matching `ruff check` passed after import sorting cleanup.
- Approval record path: `.github/approvals/ratchet-rebaseline-2026-05-18.md`.
- Restart note: attempted `sattlineLsp.restartServer` after the final code change, but the command was unavailable in this editor session.

## Interfaces and Dependencies

The owned interface is the Python LSP helper surface under `src/sattlint_lsp/`. Preserve the request and document behavior that `src/sattlint_lsp/server.py` expects. If a shared helper type from outside `src/sattlint_lsp/` needs refinement, prefer the narrowest compatible annotation change.

The only protected-path dependency is `pyproject.toml` plus the matching approval record. No new debt entries are allowed.
