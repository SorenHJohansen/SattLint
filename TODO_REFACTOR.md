# TODO_REFACTOR

Audit-driven parallel backlog for AI agents.

Last integrated audit snapshot: 2026-04-28
Canonical audit command: `sattlint-repo-audit --profile quick --fail-on medium --output-dir artifacts/audit`

## Audit Snapshot

- Overall status: `fail`
- Findings: `52 total`, `34 blocking`
- Severities: `22 high`, `12 medium`, `18 low`
- Categories: `37 style`, `8 logging-observability`, `4 architecture`, `3 typing`
- Most common finding IDs: `ruff-f401` (`18`), `ruff-i001` (`14`), `unexpected-print` (`8`)
- Pipeline substatus from `artifacts/audit/pipeline/status.json`: `ruff` failed with `37 findings`, `pyright` failed with `3 errors`, `pytest` passed with `93 tests`, `corpus` passed with `45 cases`
- CLI consistency from `artifacts/audit/cli_consistency.json`: `pass`, but `sattlint`, `sattlint-corpus-runner`, and `sattlint-lsp` remain undocumented scripts

Outputs integrated into this backlog:

- `artifacts/audit/status.json`
- `artifacts/audit/summary.json`
- `artifacts/audit/summary.md`
- `artifacts/audit/findings.json`
- `artifacts/audit/progress.json`
- `artifacts/audit/pipeline/status.json`
- `artifacts/audit/cli_consistency.json`

Snapshot caveat:

- The stale `pipeline.py` structural warning is resolved in the refreshed snapshot.
- Current `structural-function-budget` finding now points to `analyze_mms_interface_variables spans 383 lines` and no longer references `src/sattlint/devtools/pipeline.py`.

## Agent Rules

1. Claim exactly one workstream in `.github/coordination/current-work.md` before editing files.
2. Do not claim two workstreams that touch the same controlling file.
3. Treat each workstream below as independently shippable. Keep changes inside listed claims unless the workstream note explicitly says otherwise.
4. Run the listed first validation immediately after the first substantive edit.
5. If a workstream clears or changes an audit finding, rerun the narrow validation first, then rerun the quick audit if the workstream is audit-facing or closes a blocking lane.
6. Update this file and the current-work ledger when a lane is completed, blocked, or split further.

## Phase A: Blocking Workstreams

### W0. Refresh Audit Snapshot Before Further Devtools Splits

- Status: done
- Audit coverage: refreshed `artifacts/audit/status.json` and `artifacts/audit/summary.json` now show `52 total` findings and no stale `pipeline.py` structural-function-budget entry
- Claims: `artifacts/audit/`, `TODO_REFACTOR.md`, optionally `src/sattlint/devtools/pipeline.py` only if the refreshed audit still reports a blocking devtools structural finding
- Goal: rerun the quick audit so the backlog matches the current code state before any more devtools structural cleanup is assigned
- First slice: completed. Ran `sattlint-repo-audit --profile quick --fail-on medium --output-dir artifacts/audit`, compared updated `status.json` and `summary.json`, and closed this lane because `pipeline.py` is no longer flagged by structural-function-budget
- First validation: `& ".venv/Scripts/sattlint-repo-audit.exe" --profile quick --fail-on medium --output-dir artifacts/audit`
- Parallel-safe with: every code lane below, as long as this lane edits only `artifacts/audit/` and `TODO_REFACTOR.md`

### W1. LSP Import And Typing Cleanup

- Status: open
- Audit coverage: `18 findings`, `15 blocking`
- Files from audit: `src/sattlint_lsp/server.py`, `src/sattlint_lsp/_server_document.py`, `src/sattlint_lsp/_server_helpers.py`
- Finding IDs: multiple `ruff-f401`, one `ruff-f821`, one `pyright-error-reportUndefinedVariable`, one `pyright-error-reportOptionalMemberAccess`, plus import-sort noise
- Goal: clear all blocking LSP findings without broad behavior change
- First slice: remove dead imports in `server.py`, restore or replace missing `threading` usage in `_server_document.py`, and guard the optional `.start` access that pyright flagged
- First validation: `& ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_lsp_document.py tests/test_lsp_diagnostics.py tests/test_editor_api.py -x -q --tb=short`
- Notes: restart the LSP after this lane because it touches `src/sattlint_lsp/**`

### W2. Validation And Analyzer Import Cleanup

- Status: done
- Audit coverage: `6 blocking` plus several low-severity import-format findings
- Files from audit: `src/sattlint/_validation_expression.py`, `src/sattlint/_validation_type_helpers.py`, `src/sattlint/analyzers/_sfc_guard_logic.py`, `src/sattlint/analyzers/_sfc_module_walk.py`, `src/sattlint/analyzers/sfc.py`, `src/sattlint/validation.py`
- Finding IDs: `ruff-f401`, `ruff-i001`, and `validation.py` import noise
- Goal: clear dead imports and formatting noise in validation and SFC support modules without reopening semantic behavior
- First slice: remove unused imports first, then re-run formatter only on touched files if needed
- First validation: `& ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_parser_validation.py tests/test_analyzers_suites.py -x -q --tb=short -k "sfc or validation"`
- Parallel-safe with: W7 only if W7 does not touch `src/sattlint/validation.py`

### W3. App Surface Logging Migration

- Status: open
- Audit coverage: `6 blocking medium unexpected-print` findings plus low import-format findings
- Files from audit: `src/sattlint/app_analysis.py`, `src/sattlint/app_base.py`, `src/sattlint/app_cli_commands.py`, `src/sattlint/app_docs.py`, `src/sattlint/app_graphics.py`, `src/sattlint/app_menus.py`
- Finding IDs: `unexpected-print`, `ruff-f401`, `ruff-i001`
- Goal: replace library-layer `print()` calls with structured console or return-value based reporting while keeping the public app facade stable
- First slice: start with `app_analysis.py` and `app_cli_commands.py`, then normalize the remaining `app_*` modules to the same output contract
- First validation: `& ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_app.py tests/test_app_analysis.py tests/test_app_menus.py tests/test_cli.py -x -q --tb=short`
- Notes: read current file contents before editing because `src/sattlint/app_analysis.py` changed after the last turn

### W4. CLI, Console, And GUI Output Cleanup

- Status: in-progress
- Audit coverage: `3 blocking medium unexpected-print` findings
- Files from audit: `src/sattlint/cli/entry.py`, `src/sattlint/console.py`, `src/sattlint_gui/binding.py`
- Finding IDs: `unexpected-print`
- Goal: make output routing consistent outside the app-owner modules without overlapping W3
- First slice: decide one output boundary for CLI and GUI paths, migrate `print()` uses to that boundary, and keep interactive behavior unchanged
- First validation: `& ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_cli.py tests/test_gui.py tests/test_app.py tests/test_app_menus.py -x -q --tb=short`

### W5. Repo Metadata Portability Cleanup

- Status: done
- Audit coverage: no active portability findings in refreshed `artifacts/audit/status.json` or `artifacts/audit/findings.json`
- Files from audit: none in current snapshot
- Finding ID: cleared from current snapshot
- Goal: keep portability clean and prevent reintroduction of machine-specific paths
- First slice: completed in a prior change; this lane remains closed unless a future audit reintroduces portability findings
- First validation: markdown consistency review on `.github/skills/sattline-scaffold/SKILL.md`
- Notes: moved hardcoded path reference `<path-to-spec>` from "Primary source for rules" into the "Inputs To Collect First" section as parameterized guidance: "Reference to HA specification document (typically the SattLine Application Specification for your project)". The file now provides portable, parameterized language instead of exposing machine-specific paths. Markdown consistency review passed.

### W6. Parser Structural Split: `SLTransformer`

- Status: open
- Audit coverage: `1 blocking medium architecture` finding
- Files from audit: `src/sattline_parser/transformer/sl_transformer.py`
- Finding ID: `structural-class-budget`
- Detail from audit: `SLTransformer defines 133 methods`
- Goal: split `SLTransformer` by responsibility without changing parser behavior
- First slice: extract transformer mixins by domain, such as token coercion, expressions, SFC nodes, module structure, and graphics/interact construction
- First validation: `& ".venv/Scripts/sattlint.exe" syntax-check tests/fixtures/corpus/valid/VariableModifiers.s`; `& ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_transformer.py tests/test_parser_core.py -x -q --tb=short`

### W7. Analyzer Structural Split: `variables.py`

- Status: blocked (waiting on W6)
- Audit coverage: `1 blocking medium architecture` finding
- Files from audit: `src/sattlint/analyzers/variables.py`
- Finding ID: `structural-source-file-budget`
- Detail from audit: `2303 lines` (reduced to 1729 lines after W7 extraction)
- Goal: split `variables.py` by responsibility before it grows further
- First slice: complete. Created `_variables_effect_flow.py` (439 lines) with EffectFlowTracker class encapsulating 13 effect-flow and mapping-propagation methods. Updated VariablesAnalyzer to delegate all 13 methods to tracker. Variables file reduced from 2011 lines to 1729 lines (282 line reduction, 14% shrink).
- First validation: `& ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_analyzers_variables.py -x -q --tb=short`
- Blocker: W6 (parser structural split) removed `v_args` import from `src/sattline_parser/transformer/sl_transformer.py` during mixin extraction, causing ImportError in test conftest. Validation blocked; ready to run once W6 restores the missing import.
- Parallel-safe with: W2 only if W7 does not touch `src/sattlint/validation.py` (not touched in this split)

### W8. Oversized Test Module Split: `tests/test_pipeline.py`

- Status: done
- Audit coverage: `structural-test-file-budget` finding cleared
- Files changed: `tests/test_pipeline_collection.py` (1135 lines), `tests/test_pipeline_run.py` (967 lines), `tests/test_pipeline_phase2.py` (227 lines), `tests/test_pipeline.py` (11-line stub)
- Finding ID: `structural-test-file-budget`
- Detail from audit: `2277 lines` → replaced with 11-line stub; tests moved to three focused modules
- Goal: split the pipeline test module by artifact or behavior surface so failures become easier to localize
- First slice: completed. 49 tests pass in the three new modules; stub re-exports all 49 for backward compat.
- First validation: `& ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_pipeline_collection.py tests/test_pipeline_run.py tests/test_pipeline_phase2.py -x -q --tb=short` (49 passed)

### W9. Test Typing Cleanup

- Status: done
- Audit coverage: `1 blocking high typing` finding plus one low newline finding
- Files from audit: `tests/test_r2_1_expression_assignment.py`, `tests/test_structural_reports.py`
- Finding IDs: `pyright-error-reportArgumentType`, `ruff-w292`
- Goal: fix the typed `Path` call-site mismatch and clear the trailing-newline issue without widening scope into production code
- First slice: changed `str(source_file)` to `source_file` in `_write_and_validate` helper so the `Path` type is passed directly. Pyright reports 0 errors. Ruff-w292 was already clean.
- First validation: `& ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_r2_1_expression_assignment.py tests/test_structural_reports.py -x -q --tb=short`
- Notes: `test_structural_reports.py` passes 4/4. `test_r2_1_expression_assignment.py` has 9 pre-existing failures from invalid fixture grammar (`MODULEDEFINITION Test_ 1` contains a space) — confirmed pre-existing by git-stash check; not in W9 scope.

## Phase B: Non-Blocking But Useful Follow-Up Lanes

### W10. Low-Severity Style Sweep By Ownership Area

- Status: in-progress
- Audit coverage: `18 low` findings total
- Files from audit: `src/sattlint/__init__.py`, `src/sattlint/casefolding.py`, `src/sattlint/engine.py`, plus import-sort findings already attached to W1, W2, and W3 files
- Finding IDs: `ruff-i001`, `ruff-w292`, `ruff-ruf005`, `ruff-c416`
- Goal: clear remaining formatting and small-expression noise once blocking lanes stop moving the same files
- First slice: claimed `engine.py`, `casefolding.py`, and `__init__.py`; fixed `ruff-ruf005`, `ruff-c416`, `ruff-w292`, and `ruff-i001` in those files without behavior changes
- First validation: `& ".venv/Scripts/ruff.exe" check src/sattlint/engine.py src/sattlint/casefolding.py src/sattlint/__init__.py` (pass)

### W11. CLI Documentation Parity

- Status: open
- Audit coverage: `cli_consistency.json` passes, but it reports `3 undocumented scripts`
- Files from audit output: whichever docs describe CLI entry points
- Gaps from output: `sattlint`, `sattlint-corpus-runner`, `sattlint-lsp`
- Goal: document the missing script entry points so the consistency artifact is not hiding silent documentation drift
- First slice: find the canonical CLI docs surface, add the three missing scripts, and leave subcommand docs unchanged because they already pass
- First validation: markdown consistency review plus regeneration of `artifacts/audit/cli_consistency.json` if this lane is treated as an audit refresh lane

## Suggested Agent Allocation

- Agent 1: W1 LSP import and typing cleanup
- Agent 2: W2 validation and analyzer import cleanup
- Agent 3: W3 app surface logging migration
- Agent 4: W4 CLI, console, and GUI output cleanup
- Agent 5: W5 repo metadata portability cleanup
- Agent 6: W6 parser structural split
- Agent 7: W7 analyzer structural split
- Agent 8: W8 pipeline test split
- Agent 9: W9 test typing cleanup
- Agent 10: W0 audit refresh and backlog maintenance

## Completion Rule

- A workstream is done only when its focused validation passes, its claims are released in `.github/coordination/current-work.md`, and this file is updated if the audit snapshot or recommended next lanes changed.
