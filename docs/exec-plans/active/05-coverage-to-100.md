# Coverage To 100 Percent

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

## Purpose / Big Picture

This plan raises SattLint test coverage to 100 percent in a controlled way instead of by one broad, unstable sweep. When this plan is complete, `pytest` from the repository root will satisfy the existing `--cov-fail-under=100` gate in `pyproject.toml`, and a developer will be able to prove that result by running the standard test command and seeing both all tests pass and the coverage gate remain green.

## Progress

- [x] (2026-04-29 08:57Z) Create the active plan, claim the first files, and choose the first low-risk uncovered slice.
- [x] (2026-04-29 08:57Z) Add focused tests for `src/sattlint/devtools/layer_linter.py` and repair current-module layer resolution so the first narrow slice validates.
- [x] (2026-04-29 09:04Z) Add the second narrow slice in `tests/test_docgen.py` for `src/sattlint/docgenerator/configgen.py`, covering parser, extractor helper, workstation lookup, and both primary `main()` return paths.
- [x] (2026-04-29 09:04Z) Group the remaining uncovered and low-coverage modules into wave-sized slices with named validation surfaces.
- [x] (2026-04-29 ~09:45Z) Add 10 focused helper tests to `tests/test_repo_audit.py` covering `doc_gardener._relative_path()`, `_read_text()`, `_should_skip_path()`, `_normalize_workstream_id()`, `_normalize_status()`, `_parse_markdown_table()`, and `_source_sync_digest()` pure functions. All 48 test_repo_audit tests pass (was 38).
- [x] (2026-04-29 ~10:10Z) Add 7 focused tests to `tests/test_comment_code.py` covering `find_disallowed_comments()` detection of freestanding comment violations, ENDDEF label allowance, and block-interior safety. All 19 test_comment_code tests pass (added 7).
- [x] (2026-04-29 ~10:35Z) Complete Wave 2b workbook-method coverage in `tests/test_docgen.py` by adding 6 focused tests for `_populate_components_sheet()`, `_populate_dependencies_sheet()`, `_create_dashboard()`, `_create_configuration_summary_sheet()`, and `_create_configuration_details_sheet()` with stub extractors and deterministic worksheet assertions. `tests/test_docgen.py` now passes with 31 tests.
- [x] (2026-04-29 ~10:45Z) Add 5 focused helper tests to `tests/test_comment_code.py` for `_is_at_keyword()`, `_advance_position()`, `_extract_code_candidates()`, and `_comment_code_indicators()` valid/invalid paths via monkeypatched grammar checks. `tests/test_comment_code.py` now passes with 24 tests.
- [x] (2026-04-29 ~11:20Z) Complete Wave 1d repo_audit orchestration coverage in `tests/test_repo_audit.py` by adding 4 focused tests for `collect_custom_findings()` aggregation, skipped-pipeline/full-profile reporting, and `main()` default/report-link branches. `tests/test_repo_audit.py` now passes with 52 tests.
- [x] (2026-04-29 ~11:55Z) Complete Wave 1f text-processing remainder coverage in `tests/test_comment_code.py` by adding 5 focused tests for multiline ENDDEF labels, nested comment handling, and `strip_sl_comments()` string/comment edge cases. `tests/test_comment_code.py` now passes with 29 tests.
- [x] (2026-04-29 ~11:50Z) Repair the pre-existing `tests/test_r2_1_expression_assignment.py` failures by updating the fixtures to current valid SattLine syntax and asserting `SyntaxValidationResult` instead of exception-based behavior. `tests/test_r2_1_expression_assignment.py` now passes with 9 tests.
- [x] (2026-04-29 ~12:10Z) Re-baseline the remaining gap from a fresh coverage run and regroup the unfinished work by owning pytest surface instead of broad subsystem waves.
- [x] (2026-04-29 ~13:20Z) Execute Closure Tranche A on the highest-yield existing test surfaces by extending app/CLI/doc-scope edge coverage in `tests/test_app.py` and `tests/test_cli.py`, then validating all tranche owner suites: `tests/test_docgen.py` (31 passed), `tests/test_repo_audit.py` (52 passed), and `tests/test_app.py tests/test_app_analysis.py tests/test_app_menus.py tests/test_cli.py` (158 passed).
- [x] (2026-04-29 15:20Z) Execute Closure Tranche B on semantic and resolution seams already covered by `tests/test_editor_api.py`, `tests/test_lsp_document.py`, `tests/test_lsp_diagnostics.py`, `tests/test_moduletype_resolution_scoped.py`, and `tests/test_canonical_resolution.py`.
- [x] (2026-04-29 ~12:40Z) Execute Closure Tranche C on analyzer-heavy modules by extending `tests/test_analyzers_suites.py` and `tests/test_analyzers_state.py` with focused helper and effect-flow tests for `modules.py`, `mms.py`, `variable_usage_reporting.py`, `_variables_effect_flow.py`, and `_sfc_guard_logic.py`; validation command passed with `73 passed`.
- [x] (2026-04-29 ~13:20Z) Execute Closure Tranche D by adding focused tests for `sattline_parser/utils/formatter.py`, `sattlint/devtools/observability.py`, `sattlint/devtools/review_tool.py`, and additional GUI helper/view branches in `tests/test_gui.py`; validate with focused no-cov suites and a scoped tranche-D coverage checkpoint.
- [x] (2026-04-29 ~16:20Z) Re-baseline the remaining gap against the latest `coverage.xml` and `htmlcov/status.json` snapshots, replacing stale tranche-only remainder notes with explicit owner buckets and dominant-miss files.
- [x] (2026-04-29 ~16:55Z) Verify the stale editor_api blocker no longer reproduces: `tests/test_editor_api.py` passes under coverage, and a full `pytest -q --cov-fail-under=0` checkpoint is now test-clean with `1059 passed`.
- [x] (2026-04-29 ~17:10Z) Start Work Package 2 on the existing `tests/test_dataflow.py` owner surface by adding 5 focused tests for `dataflow.py` typedef traversal, root-origin filtering, parameter-mapped child evaluation, GLOBAL mapping skip behavior, and unresolved moduletype-instance early return; focused validation passed with `19 passed`.
- [x] (2026-04-29 13:53Z) Start Work Package 3 on the existing `tests/test_parser_core.py` owner surface by adding 8 focused tests for `src/sattline_parser/api.py` covering parser aliasing, parse-error summary variants, decode fallbacks, compressed-source loading, and `parse_source_text()` debug/error branches; focused validation passed with `26 passed`.
- [ ] Drain the highest-yield app/devtools/docgen owners: `tests/test_docgen.py`, `tests/test_repo_audit.py`, `tests/test_app.py`, `tests/test_app_analysis.py`, `tests/test_app_menus.py`, `tests/test_cli.py`, and `tests/test_engine.py` for `configgen.py`, `repo_audit.py`, `doc_gardener.py`, `app_analysis.py`, `app_graphics.py`, `engine.py`, `config.py`, and adjacent app surfaces.
- [ ] Drain the analyzer and semantic/LSP owners: `tests/test_analyzers_suites.py`, `tests/test_analyzers_state.py`, `tests/test_dataflow.py`, `tests/test_analyzers_variables.py`, `tests/test_editor_api.py`, `tests/test_lsp_document.py`, `tests/test_lsp_diagnostics.py`, `tests/test_moduletype_resolution_scoped.py`, and `tests/test_canonical_resolution.py` for `modules.py`, `reset_contamination.py`, `mms.py`, `variables.py`, `variable_usage_reporting.py`, `dataflow.py`, `core/semantic.py`, `_server_helpers.py`, `_server_document.py`, `server.py`, and `workspace_store.py`.
- [ ] Finish parser, reporting, and GUI residue through `tests/test_parser_core.py`, `tests/test_parser_validation.py`, `tests/test_gui.py`, and the nearest existing report/app/pipeline owners for `sattline_parser/api.py`, parser AST/transformer modules, `variables_report.py`, `mms_report.py`, `icf_report.py`, and the remaining `sattlint_gui/**` files.
- [ ] Move this plan to `docs/exec-plans/completed/` once the repository-default coverage gate passes.

## Surprises & Discoveries

- Observation: The checked-in `coverage.xml` snapshot is far below the configured gate.
  Evidence: `coverage.xml` reports `line-rate="0.2033"` while `pyproject.toml` configures `--cov-fail-under=100` for normal pytest runs.
- Observation: `src/sattlint/devtools/layer_linter.py` and `src/sattlint/docgenerator/configgen.py` are at 0 percent in the saved snapshot.
  Evidence: `coverage.xml` contains `line-rate="0"` entries for both files.
- Observation: `layer_linter` was silently suppressing real violations for files under `src/` because it derived the current layer from the literal prefix `src` instead of the package path under that directory.
  Evidence: an isolated temp-repo test for `src/sattlint/core/rules.py` importing `sattlint_lsp.server` produced no violation until current-module resolution stripped the `src/` root before layer lookup.
- Observation: `configgen` can gain meaningful coverage through the existing `tests/test_docgen.py` module without starting with workbook-heavy integration scenarios.
  Evidence: focused tests for configuration parsing, dependency extraction, unit extraction, workstation mapping, and `main()` invalid-root and success paths passed in one narrow pytest run.
- Observation: `CommentPlacementViolation` from `find_disallowed_comments()` records violations with empty `text` fields because the function flags disallowed comment positions at detection time, not retroactively at comment-close.
  Evidence: testing `find_disallowed_comments()` required checking `start_line` and `start_col` instead of the `text` content itself.
- Observation: `configgen` workbook-sheet builders are testable without file I/O by stubbing `parse_all_configuration_files()` and asserting worksheet cells, table names, and merged-range metadata directly.
  Evidence: six focused tests validated summary/details/table/title behavior entirely in-memory through openpyxl workbook state.
- Observation: internal text-processing helpers are cheap to validate directly and expose deterministic behavior without full parser integration when grammar validation is monkeypatched at the helper seam.
  Evidence: five focused tests exercised keyword-boundary parsing, newline position handling, code-candidate extraction, and comment-indicator acceptance/rejection paths in under half a second.
- Observation: `collect_custom_findings()` is easy to cover as an orchestration seam by stubbing each subordinate scanner and asserting the exact filtered inputs passed between them.
  Evidence: a single focused test covered tracked-path propagation, documentation-file existence filtering, repo-audit self-scan exclusion, and final dedupe behavior without running any real repo-wide scan.
- Observation: the repository-default pytest gate was blocked first by stale R2.1 tests rather than product code regressions.
  Evidence: `tests/test_r2_1_expression_assignment.py` failed because it used obsolete fixture syntax (`MODULEDEFINITION Test_ 1`, `ENDBLOCK`, `ENDCODE`) and expected raised exceptions even though `validate_single_file_syntax()` returns `SyntaxValidationResult` objects.
- Observation: after repairing the failing R2.1 tests, the full suite is test-clean but still far from the configured coverage floor.
  Evidence: `& ".venv/Scripts/python.exe" -m pytest -q` now reports `821 passed in 113.66s` and fails only with `Total coverage: 75.88%`.
- Observation: the easiest remaining path is clustered by existing test owners, not by the original wave labels.
  Evidence: the fresh coverage run shows large contiguous gaps in modules already exercised by current suites: `tests/test_docgen.py` owns `configgen`; `tests/test_repo_audit.py` owns `doc_gardener` and `repo_audit`; `tests/test_app*.py` and `tests/test_cli.py` already own `app_*`, `config.py`, and `cli/entry.py`; `tests/test_editor_api.py` plus `tests/test_lsp_*` own the semantic/LSP bridge.
- Observation: a fresh coverage run still surfaced one red test under coverage, so the plan must continue treating full-suite runs as checkpoints rather than the first validation step for each slice.
  Evidence: `covtest.txt` shows `1000 passed, 1 failed` with `tests/test_editor_api.py::test_build_variable_semantic_artifacts_with_diagnostics` failing while total coverage remains only `76.50%`.
- Observation: GUI and observability modules are some of the lowest percentages, but they are poor first closure targets because they sit behind richer app, semantic, and report surfaces that can remove more missing lines per focused test edit.
  Evidence: the same coverage run reports very low percentages for `src/sattlint_gui/**` and `src/sattlint/devtools/observability.py`, while much larger missing-line totals remain in `app_analysis.py`, `configgen.py`, `doc_gardener.py`, `repo_audit.py`, `core/semantic.py`, `resolution/common.py`, `app_graphics.py`, and analyzer-heavy modules.
- Observation: Tranche D-focused tests now cover the targeted residue modules, but the repository-default gate remains blocked by unrelated LSP and resolution test regressions plus broad remaining coverage debt from other surfaces.
  Evidence: focused validation passed (`tests/test_gui.py`, `tests/test_formatter.py`, `tests/test_devtools_review_observability.py`), while full `pytest -q` failed with three non-tranche test failures (`tests/test_lsp_document.py` x2 and `tests/test_moduletype_resolution_scoped.py`) and coverage stayed at 78%.
- Observation: `SattLineLanguageServer.workspace` is a read-only property on real server instances, so direct test-level assignment fails; non-integration handler tests should use lightweight fake server objects with only required attributes.
  Evidence: tranche-B test additions for `on_did_open`, `on_did_change`, and `on_did_save` initially raised `AttributeError` until those tests switched to `SimpleNamespace`-based fakes.
- Observation: analyzer-heavy closure can still move quickly when private helper seams are tested directly in owner suites rather than only via large integration fixtures.
  Evidence: targeted tests for MMS tag helpers, module-diff normalization, variable-usage instance resolution, SFC guard normalization, and effect-flow reverse reachability all passed in a single focused tranche command (`73 passed in 0.68s`).
- Observation: Tranche A app/CLI closure gains are inexpensive when routed through existing owner suites and direct seam calls instead of new integration fixtures.
  Evidence: added focused tests for CLI parser/handler error branches (`src/sattlint/cli/entry.py`), docgen command guardrails (`src/sattlint/app_cli_commands.py`), and documentation-scope edge handling (`src/sattlint/app_docs.py`) while keeping tranche commands green: `31 passed`, `52 passed`, and `158 passed` across the three Tranche A validation commands.
- Observation: `covtest.txt` is no longer the current planning baseline for the remaining gap.
  Evidence: `coverage.xml` now reports `line-rate="0.7811"`, and `htmlcov/status.json` shows post-tranche-D reductions such as `formatter.py` with 5 misses, `observability.py` with 12, and `review_tool.py` with 11, which do not match the older `covtest.txt` dump.
- Observation: the remaining path to 100 percent is concentrated in a limited set of files with triple-digit miss counts.
  Evidence: `htmlcov/status.json` shows `modules.py` at 295 misses, `app_analysis.py` 270, `repo_audit.py` 263, `configgen.py` 258, `reset_contamination.py` 244, `app_graphics.py` 198, `doc_gardener.py` 190, `engine.py` 186, `config_frame.py` 179, `mms.py` 151, `variables.py` 122, `core/semantic.py` 118, `variable_usage_reporting.py` 113, `_server_helpers.py` 107, and `dataflow.py` 106.
- Observation: getting from roughly 78 percent to 100 percent now requires widening beyond the original tranche owners into engine, parser, reporting, and GUI-heavy surfaces.
  Evidence: the latest status snapshot still shows large misses in `engine.py`, parser AST/transformer modules, `variables_report.py`, `mms_report.py`, and `sattlint_gui/frames/config_frame.py` after the tranche A-D owners were improved.
- Observation: the editor_api checkpoint blocker in the plan is stale.
  Evidence: `& ".venv/Scripts/python.exe" -m pytest tests/test_editor_api.py -x -q --tb=short --cov-fail-under=0` now reports `23 passed`, and `& ".venv/Scripts/python.exe" -m pytest -q --cov-fail-under=0` reports `1059 passed, 1 warning` with no failing tests.
- Observation: `dataflow.py` still has cheap, high-yield uncovered branches on typedef and parameter-alias paths even after the earlier analyzer tranche work.
  Evidence: `tests/test_dataflow.py` initially covered direct equation and sequence behavior only; five focused AST-built tests reached root typedef traversal, same-origin filtering, parameter aliasing, GLOBAL mapping skip, and unresolved moduletype-instance return paths while the owner-suite validation stayed green at `19 passed`.
- Observation: `parse_source_text()` tries to attach `parse_tree` before it proves the transformer returned a `BasePicture`, so non-AST transform results still emit the parse-tree warning path before the runtime type error.
  Evidence: the new parser-core test for a transformer returning `"not-a-basepicture"` observed both debug messages, `BasePicture does not allow dynamic attributes; parse tree not attached` and `Transform result type: str`, before the expected runtime error.

## Decision Log

- Decision: Start with `src/sattlint/devtools/layer_linter.py` instead of a larger analyzer or CLI file.
  Rationale: It is small, isolated, and has no existing dedicated test module, so it offers a cheap first slice that can validate the coverage-lift workflow before broader waves start.
  Date/Author: 2026-04-29 / Copilot (GPT-5.4)
- Decision: Fix the local defect in `layer_linter` instead of adding tests around the buggy behavior.
  Rationale: The goal of coverage work is trustworthy exercised behavior, not inflated numbers. Preserving the broken `src`-prefixed layer lookup would lock in a false negative in the architecture linter.
  Date/Author: 2026-04-29 / Copilot (GPT-5.4)
- Decision: Keep `configgen` coverage inside `tests/test_docgen.py` rather than creating a separate `tests/test_configgen.py` file.
  Rationale: The doc generation instruction scope already routes docgen behavior to the existing docgen test surface, and keeping related coverage in one module reduces test fragmentation while the wave is still small.
  Date/Author: 2026-04-29 / Copilot (GPT-5.4)
- Decision: Reorder the remainder by coverage yield per owning pytest surface rather than continuing with broad Wave 1-6 labels.
  Rationale: the current blocker is no longer discovery; it is execution efficiency. Grouping by the test files that already import and exercise the remaining modules minimizes setup churn and makes each validation command obvious.
  Date/Author: 2026-04-29 / Copilot (GPT-5.4)
- Decision: Treat `coverage.xml` and `htmlcov/status.json` as the current planning baseline and downgrade `covtest.txt` to historical context.
  Rationale: the checked-in XML and HTML status artifacts reflect later tranche work and a materially different remaining gap than the older terminal transcript.
  Date/Author: 2026-04-29 / Copilot (GPT-5.4)
- Decision: Replace tranche-only remainder notes with explicit owner buckets and dominant-miss files.
  Rationale: the original tranche framing no longer says what is actually missing. The plan now needs a concrete backlog tied to the suites most likely to close the remaining 5,799 uncovered lines.
  Date/Author: 2026-04-29 / Copilot (GPT-5.4)
- Decision: Start Work Package 2 with `tests/test_dataflow.py` before widening back into semantic/LSP suites.
  Rationale: `dataflow.py` still carries a triple-digit miss count, already has a dedicated owner suite, and can absorb focused AST-level tests without LSP restart overhead or broader workspace fixture setup.
  Date/Author: 2026-04-29 / Copilot (GPT-5.4)
- Decision: Start Work Package 3 with `src/sattline_parser/api.py` inside `tests/test_parser_core.py` before AST-model, reporting, or GUI-heavy residue.
  Rationale: `api.py` already has a stable owner suite, its remaining misses are branch-local rather than fixture-heavy, and it offers a cheap parser-side entry point with no production-code changes required.
  Date/Author: 2026-04-29 / Copilot (GPT-5.4)

## Outcomes & Retrospective

Plan started and multiple slices are complete.

**Wave 0 (Plan)**: Created active plan and claimed initial coverage work.

**Wave 1a (layer_linter)**: `src/sattlint/devtools/layer_linter.py` now has a dedicated focused test module covering helper lookup, file discovery, invalid dependency detection, parse-failure skip behavior, and both CLI exit paths. That slice also fixed a real path-to-module mapping bug that had prevented the linter from reporting some invalid imports under `src/`. Focused validation passed with `pytest --no-cov tests/test_layer_linter.py -x -q --tb=short` → `6 passed`.

**Wave 2a (configgen)**: Extended the existing `tests/test_docgen.py` to execute real `configgen` behavior without a full workbook-generation scenario. The added tests cover configuration-file parsing, component dependency and unit extraction, case-insensitive workstation mapping, header styling, table helpers, and both primary `main()` return paths. Focused validation passed with `pytest --no-cov tests/test_docgen.py -x -q --tb=short` → `25 passed`.

**Wave 1b (doc_gardener helpers)**: Added 10 focused unit tests to `tests/test_repo_audit.py` targeting pure helper functions in `doc_gardener.py`: relative-path resolution, text reading with encoding fallback, virtual-environment detection, workstream/status normalization, markdown-table parsing, and digest determinism. Focused validation passed with all 48 test_repo_audit tests passing (added 10, was 38 before). Validates without needing full repo-scan integration setup.

**Wave 1c (find_disallowed_comments)**: Added 7 focused unit tests to `tests/test_comment_code.py` for `find_disallowed_comments()` function from `text_processing.py`. Tests cover freestanding comment detection before EQUATIONBLOCK/SEQUENCE, ENDDEF label allowance, block-interior comment safety, and out-of-ModuleCode comment ignoring. Validation: all 19 test_comment_code tests pass (added 7, was 12 before).

**Wave 2b (configgen workbook methods)**: Added 6 focused tests to `tests/test_docgen.py` for workbook-generation helpers in `configgen.ExcelGenerator`: component/dependency sheet population, dashboard title/merge metadata, summary-sheet empty-state and table path, and details-sheet row/table generation. Tests use stub extractors and direct worksheet assertions for deterministic coverage without full output-file generation. Validation: `pytest --no-cov tests/test_docgen.py -x -q --tb=short` -> `31 passed`.

**Wave 1e (text_processing helpers)**: Added 5 focused tests to `tests/test_comment_code.py` for remaining utility and indicator helpers in `src/sattlint/utils/text_processing.py`: keyword-boundary matching, CR/LF position advancement, semicolon-based candidate extraction, and comment-indicator behavior when grammar checks reject or accept candidates. Validation: `pytest --no-cov tests/test_comment_code.py -x -q --tb=short` -> `24 passed`.

**Wave 1d (repo_audit orchestration)**: Added 4 focused tests to `tests/test_repo_audit.py` for collection and reporting orchestration in `src/sattlint/devtools/repo_audit.py`: `collect_custom_findings()` aggregation and filtering, `audit_repository()` skipped-pipeline/full-profile artifact behavior, and `main()` fail-on defaults plus latest-report link routing. Tests rely on monkeypatched subordinate scanners and deterministic artifact assertions instead of full repo scans. Validation: `pytest --no-cov tests/test_repo_audit.py -x -q --tb=short` -> `52 passed`.

**Wave 1f (text_processing remainder)**: Added 5 more focused tests to `tests/test_comment_code.py` covering multiline ENDDEF-label rejection, nested comment handling in `find_comments_with_code()`, and `strip_sl_comments()` preservation of strings, escapes, nested comments, and post-comment semicolon removal. Validation: `pytest --no-cov tests/test_comment_code.py -x -q --tb=short` -> `29 passed`.

**Full-suite unblocker (R2.1 tests)**: Repaired the stale fixtures and assertions in `tests/test_r2_1_expression_assignment.py` so the file now uses current valid SattLine syntax and asserts `SyntaxValidationResult` objects instead of expecting exceptions from `validate_single_file_syntax()`. Validation: `pytest --no-cov tests/test_r2_1_expression_assignment.py -x -q --tb=short` -> `9 passed`.

**Cumulative Validation**: All focused slices remain green, and the repository-default pytest run is now test-clean:

- test_layer_linter.py: 6 tests
- test_docgen.py: 31 tests
- test_repo_audit.py: 52 tests
- test_comment_code.py: 29 tests
- test_r2_1_expression_assignment.py: 9 tests
- full suite: `821 passed in 113.66s`

**Session Checkpoint (2026-04-29 ~12:10Z)**:
The plan is now in coverage-closure mode rather than failure-unblock mode. A fresh coverage run confirms the repository remains far from the gate and still has at least one full-suite red test under coverage (`tests/test_editor_api.py::test_build_variable_semantic_artifacts_with_diagnostics`), so the remaining work should keep using narrow validation first and treat full runs as scheduled checkpoints.

**Closure Tranche D (2026-04-29 ~13:20Z)**:
Added a new focused parser-formatter suite (`tests/test_formatter.py`), a new focused devtools suite (`tests/test_devtools_review_observability.py`), and seven additional headless-safe GUI branch tests in `tests/test_gui.py`. Focused validation passed: `45 passed` across those three suites and the tranche command `pytest --no-cov tests/test_gui.py -x -q --tb=short` passed with `30 passed`. A scoped tranche coverage checkpoint now reports `formatter.py` at 97%, `review_tool.py` at 91%, and `observability.py` at 83%, while GUI remains partially covered and should continue to be drained opportunistically. Full-suite checkpoint is still blocked by unrelated LSP/resolution test regressions and the global 100% coverage gate.

**Closure Tranche B Complete (2026-04-29 15:20Z)**:
Extended existing owner suites with focused tests for `core/semantic` helper branches, `resolution/common` strict-path and scope helpers, LSP helper validation utilities, workspace-store entry selection, and server lifecycle non-diagnostic routing branches. Validation passed on the tranche-B command set: `pytest --no-cov tests/test_editor_api.py -x -q --tb=short` (`23 passed`) and `pytest --no-cov tests/test_lsp_document.py tests/test_lsp_diagnostics.py tests/test_moduletype_resolution_scoped.py tests/test_canonical_resolution.py -x -q --tb=short` (`84 passed`).

**Closure Tranche C (2026-04-29 ~12:40Z)**: Extended the analyzer owner suites with 11 focused tests covering helper and branch seams in `modules.py`, `mms.py`, `variable_usage_reporting.py`, `_sfc_guard_logic.py`, and `_variables_effect_flow.py` while preserving existing analyzer behavior. Validation: `& ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_analyzers_suites.py tests/test_analyzers_state.py -x -q --tb=short` -> `73 passed in 0.68s`.

**Closure Tranche A (2026-04-29 ~13:20Z)**: Completed the tranche owner surfaces by adding focused branch tests in `tests/test_cli.py` and `tests/test_app.py` for `src/sattlint/cli/entry.py`, `src/sattlint/app_cli_commands.py`, and `src/sattlint/app_docs.py` (parser/handler error routing, docgen target cardinality/output guards, and documentation-scope empty/unmatched paths). Tranche validation commands passed unchanged: `tests/test_docgen.py` -> `31 passed`, `tests/test_repo_audit.py` -> `52 passed`, and `tests/test_app.py tests/test_app_analysis.py tests/test_app_menus.py tests/test_cli.py` -> `158 passed`.

**Checkpoint Repair Closed (2026-04-29 ~16:55Z)**: The plan's first remaining blocker no longer reproduces. `tests/test_editor_api.py` now passes under coverage (`23 passed` with `--cov-fail-under=0`), and the broader full-suite checkpoint is test-clean again: `1059 passed, 1 warning` with total coverage still around `78%`. The remaining work is now pure coverage debt, not a failing test gate.

**Work Package 2 Start: Dataflow Slice (2026-04-29 ~17:10Z)**: Extended `tests/test_dataflow.py` with 5 focused tests that cover the previously untouched typedef and moduletype-instance routing in `src/sattlint/analyzers/dataflow.py`. The new tests exercise same-origin typedef traversal, external-origin skip behavior, parameter-mapped child constant-condition inference, GLOBAL mapping non-aliasing, and unresolved moduletype-instance early return without changing production code. Validation passed with `& ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_dataflow.py -x -q --tb=short` -> `19 passed`.

**Work Package 3 Start: Parser API Slice (2026-04-29 13:53Z)**: Extended `tests/test_parser_core.py` with 8 focused tests that cover the previously missed branch behavior in `src/sattline_parser/api.py`. The new tests exercise `create_sl_parser()` aliasing, EOF/token/character parse-summary variants, plain `describe_parse_error()` fallback, cp1252 and latin-1 text decoding, compressed-source loading, and `parse_source_text()` debug/error paths for parse-tree attachment failures and non-`BasePicture` transform outputs. Validation passed with `& ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_parser_core.py -x -q --tb=short` -> `26 passed`.

**Current Required Closure Order**:

1. **Drain the high-yield app/devtools/docgen/engine owners**. `tests/test_docgen.py`, `tests/test_repo_audit.py`, `tests/test_app.py`, `tests/test_app_analysis.py`, `tests/test_app_menus.py`, `tests/test_cli.py`, and `tests/test_engine.py` still own the `configgen.py` / `repo_audit.py` / `doc_gardener.py` / `app_analysis.py` / `app_graphics.py` / `engine.py` cluster that accounts for well over 1,500 missing lines.
2. **Drain analyzers and the semantic/LSP bridge**. Use `tests/test_analyzers_suites.py`, `tests/test_analyzers_state.py`, `tests/test_dataflow.py`, `tests/test_analyzers_variables.py`, `tests/test_editor_api.py`, and `tests/test_lsp_*` to remove the `modules.py`, `reset_contamination.py`, `mms.py`, `variables.py`, `variable_usage_reporting.py`, `dataflow.py`, `core/semantic.py`, `_server_helpers.py`, `_server_document.py`, `server.py`, and `workspace_store.py` backlog.
3. **Finish parser, reporting, and GUI residue**. Use `tests/test_parser_core.py`, `tests/test_parser_validation.py`, `tests/test_gui.py`, and the nearest report/app/pipeline owners for parser AST/transformer files, `variables_report.py`, `mms_report.py`, `icf_report.py`, `config_frame.py`, `binding.py`, `window.py`, and the remaining widget/frame files.
4. **Use full-suite checkpoints as measurement points, not blocker hunts**. The repository-default suite is test-clean again, so rerun `pytest -q --cov-fail-under=0` only when a major owner bucket is drained, then use the residual miss list for the final 1-20 line sweep.

## Context and Orientation

The repository already treats 100 percent line coverage as the required steady state. That rule lives in `pyproject.toml` under `[tool.pytest.ini_options]`, where pytest runs with `--cov=src`, emits terminal, HTML, and XML coverage reports, and fails if total line coverage is below 100 percent. The current planning baseline is the checked-in `coverage.xml` plus `htmlcov/status.json`, which now reflect roughly 78.11 percent coverage and about 5,799 uncovered lines. `covtest.txt` remains useful historical context, but it no longer matches the current dominant misses.

The plan is no longer in early exploration. The first uncovered slices are already complete, but the remaining work is broader than the original tranche notes now imply. The current gap is concentrated in a finite set of large modules with identifiable owner suites, plus a few parser/reporting and GUI surfaces that likely need either new focused tests or targeted extensions to nearby existing suites.

Coverage work in this repository should still stay narrow. For each slice, identify one module or one closely related branch cluster inside an existing owner test file, update that nearest focused pytest module first, run it with `--no-cov`, and only then widen to the next tranche checkpoint. Do not start each slice with a full coverage run.

## Plan of Work

The remaining work should proceed in three explicit work packages plus final sweep, not the earlier tranche shorthand.

Work Package 1 is the highest-yield app/devtools/docgen/engine cluster. Extend `tests/test_docgen.py`, `tests/test_repo_audit.py`, `tests/test_app.py`, `tests/test_app_analysis.py`, `tests/test_app_menus.py`, `tests/test_cli.py`, and `tests/test_engine.py` to drain `configgen.py`, `repo_audit.py`, `doc_gardener.py`, `app_analysis.py`, `app_graphics.py`, `engine.py`, `config.py`, and the adjacent app support surfaces. This cluster is still the fastest route to remove large blocks of misses.

Work Package 2 is analyzer plus semantic/LSP depth. Extend `tests/test_analyzers_suites.py`, `tests/test_analyzers_state.py`, `tests/test_dataflow.py`, `tests/test_analyzers_variables.py`, `tests/test_editor_api.py`, `tests/test_lsp_document.py`, `tests/test_lsp_diagnostics.py`, `tests/test_moduletype_resolution_scoped.py`, and `tests/test_canonical_resolution.py` for `modules.py`, `reset_contamination.py`, `mms.py`, `variables.py`, `variable_usage_reporting.py`, `dataflow.py`, `core/semantic.py`, `_server_helpers.py`, `_server_document.py`, `server.py`, `workspace_store.py`, and `resolution/common.py`.

Work Package 3 is parser, reporting, and GUI residue. Use `tests/test_parser_core.py`, `tests/test_parser_validation.py`, and `tests/test_gui.py` first, then extend the nearest existing report/app/pipeline owners for `sattline_parser/api.py`, `sattline_parser/models/ast_model.py`, the parser transformer mixins, `variables_report.py`, `mms_report.py`, `icf_report.py`, and the remaining `sattlint_gui/**` files. Only add a new test file when no stable owner suite fits cleanly.

Work Package 4 is the final sweep. Once the dominant-miss files stop carrying triple-digit debt, rerun the repository-default `pytest -q` command, capture the residual miss list, and close the last low-yield branches directly.

## Concrete Steps

Run from repository root.

Coverage-triage support commands:

    rg -n 'filename="sattlint/.+".*line-rate="0(\\.0+)?"' coverage.xml
    rg -n 'filename="sattlint/.+".*line-rate="0\\.[0-2]' coverage.xml
  rg -n 'n_missing' htmlcov/status.json

Work Package 1 validation commands:

    & ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_docgen.py -x -q --tb=short
    & ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_repo_audit.py -x -q --tb=short
    & ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_app.py tests/test_app_analysis.py tests/test_app_menus.py tests/test_cli.py -x -q --tb=short
  & ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_engine.py -x -q --tb=short

Work Package 2 validation commands:

  & ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_analyzers_suites.py tests/test_analyzers_state.py -x -q --tb=short
  & ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_dataflow.py tests/test_analyzers_variables.py -x -q --tb=short
    & ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_editor_api.py -x -q --tb=short
    & ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_lsp_document.py tests/test_lsp_diagnostics.py tests/test_moduletype_resolution_scoped.py tests/test_canonical_resolution.py -x -q --tb=short

Work Package 3 validation commands:

  & ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_parser_core.py tests/test_parser_validation.py -x -q --tb=short
    & ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_gui.py -x -q --tb=short

Final acceptance command for the whole plan:

    & ".venv/Scripts/python.exe" -m pytest -q

Expected final-plan success transcript:

    <all tests pass>
    Required test coverage of 100% reached. Total coverage: 100.00%

## Validation and Acceptance

Acceptance for each work package means the owning focused pytest commands above pass with `--no-cov`, the freshly touched source cluster is no longer one of the dominant missing-line contributors in the next coverage checkpoint, and no new broad-suite regressions are introduced.

Acceptance for the full plan means the repository-default pytest command passes without overriding coverage settings, which proves that total line coverage across `src/` is 100 percent.

## Idempotence and Recovery

Each work package is safe to rerun because it stays inside an existing owner test surface and should prefer temporary directories, stubs, and direct object construction over repo-wide setup. If a new test reveals non-deterministic behavior, keep the repair local to the currently targeted source cluster and rerun only that owner test command until stable. Do not jump to a different work package just because a local branch is awkward; drain the current owner surface before widening again.

## Artifacts and Notes

Initial evidence gathered before implementation:

    pyproject.toml: pytest addopts include --cov=src and --cov-fail-under=100
    coverage.xml: line-rate="0.2033"
    coverage.xml: sattlint/devtools/layer_linter.py line-rate="0"
    coverage.xml: sattlint/docgenerator/configgen.py line-rate="0"

Latest re-baseline evidence used for current remaining-work planning:

  coverage.xml: line-rate="0.7811" (about 78.11%, 5799 uncovered lines)
  htmlcov/status.json: dominant misses include modules.py (295), app_analysis.py (270),
  repo_audit.py (263), configgen.py (258), reset_contamination.py (244), app_graphics.py (198),
  doc_gardener.py (190), engine.py (186), config_frame.py (179), mms.py (151), variables.py (122),
  core/semantic.py (118), variable_usage_reporting.py (113), _server_helpers.py (107), dataflow.py (106)
  covtest.txt: historical checkpoint that still mentions an editor_api failure which no longer reproduces
  pytest -q --cov-fail-under=0: full suite now test-clean at 1059 passed, 1 warning, with coverage still around 78%

First implemented slice:

    tests/test_layer_linter.py covers helper lookup, file scanning, invalid import detection,
    parse-failure skip behavior, and both main() exit paths.
    src/sattlint/devtools/layer_linter.py now resolves package paths under src/ before layer lookup.

Second implemented slice:

    tests/test_docgen.py now covers ConfigurationFileParser.parse_configuration_file(),
    SattLineConfigExtractor.get_component_info(), WorkstationMapper lookups,
    and configgen.main() invalid-root and success return paths.

Remaining closure map:

  Work Package 1: docgen, repo-audit, app, CLI, and engine owners already in active use
  Work Package 2: analyzer-heavy suites plus semantic, resolution, editor, and LSP bridge owners
  Work Package 3: parser, reporting, and GUI-heavy residue
  Work Package 4: final repository-default checkpoint plus residual 1-20 line sweeps

## Interfaces and Dependencies

This plan depends on pytest, pytest-cov, and the existing repository virtual environment under `.venv`. The dominant remaining interfaces are already exposed through existing owner tests: docgen workbook builders and CLI entry points, repo-audit and doc-gardener scan functions, app/config routing helpers, semantic snapshot builders, resolution helpers, analyzer public entry points, and the GUI/LSP adapter surfaces. Prefer those public seams over private helper testing unless the uncovered branch is otherwise unreachable without unstable fixture setup.
