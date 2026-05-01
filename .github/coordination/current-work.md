# Coverage Campaign Progress

### Workstream coverage-tranche-a-2026-04-29

- Owner: Copilot
- Goal: Finish coverage ExecPlan Closure Tranche A on docgen, repo-audit, app, and CLI owner test surfaces.
- Claims: docs/exec-plans/active/05-coverage-to-100.md, tests/test_docgen.py, tests/test_repo_audit.py, tests/test_app.py, tests/test_app_analysis.py, tests/test_app_menus.py, tests/test_cli.py, src/sattlint/docgenerator/configgen.py, src/sattlint/devtools/doc_gardener.py, src/sattlint/devtools/repo_audit.py, src/sattlint/app_analysis.py, src/sattlint/app_docs.py, src/sattlint/app_base.py, src/sattlint/app_graphics.py, src/sattlint/config.py, src/sattlint/app_cli_commands.py, src/sattlint/cli/entry.py
- First validation: & ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_docgen.py -x -q --tb=short
- Status: done
- Notes: Added focused branch tests in tests/test_cli.py and tests/test_app.py for cli/entry, app_cli_commands, and app_docs seams. Validation passed: test_docgen.py (31), test_repo_audit.py (52), app/app_analysis/app_menus/cli tranche set (158).

### Workstream coverage-tranche-b-2026-04-29

- Owner: Copilot
- Goal: Finish coverage ExecPlan Closure Tranche B on semantic, resolution, and LSP bridge owner test surfaces.
- Claims: docs/exec-plans/active/05-coverage-to-100.md, tests/test_editor_api.py, tests/test_lsp_document.py, tests/test_lsp_diagnostics.py, tests/test_moduletype_resolution_scoped.py, tests/test_canonical_resolution.py, src/sattlint/core/semantic.py, src/sattlint/resolution/common.py, src/sattlint_lsp/_server_document.py, src/sattlint_lsp/_server_helpers.py, src/sattlint_lsp/server.py, src/sattlint_lsp/workspace_store.py
- First validation: & ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_editor_api.py -x -q --tb=short
- Status: done
- Notes: Added focused tests in tranche-B owner suites; validations passed: `pytest --no-cov tests/test_editor_api.py -x -q --tb=short` (23 passed) and `pytest --no-cov tests/test_lsp_document.py tests/test_lsp_diagnostics.py tests/test_moduletype_resolution_scoped.py tests/test_canonical_resolution.py -x -q --tb=short` (84 passed).

### Workstream precommit-hooks-2026-04-29

- Owner: Copilot
- Goal: Align repo pre-commit setup with D-Wave-1 exec-plan by adding missing parser/file-hygiene hooks and CI/doc wiring.
- Claims: .github/coordination/current-work.md, .pre-commit-config.yaml, .github/workflows/typing.yml, CONTRIBUTING.md, docs/exec-plans/active/06-d-wave-1-pre-commit-hooks.md
- First validation: .venv\Scripts\pre-commit.exe run --all-files
- Status: active
- Notes: Existing repo already had broader pre-commit coverage; preserve current pyright/format hooks unless validation forces change.

### Workstream coverage-tranche-c-2026-04-29

- Owner: Copilot
- Goal: Finish coverage ExecPlan Closure Tranche C on analyzer-heavy modules using existing analyzer owner test surfaces.
- Claims: docs/exec-plans/active/05-coverage-to-100.md, tests/test_analyzers_suites.py, tests/test_analyzers_state.py, src/sattlint/analyzers/modules.py, src/sattlint/analyzers/mms.py, src/sattlint/analyzers/variable_usage_reporting.py, src/sattlint/analyzers/reset_contamination.py, src/sattlint/analyzers/_variables_effect_flow.py, src/sattlint/analyzers/_sfc_collectors.py, src/sattlint/analyzers/_sfc_guard_logic.py
- First validation: & ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_analyzers_suites.py tests/test_analyzers_state.py -x -q --tb=short
- Status: done
- Notes: Added focused helper/effect-flow tests in tests/test_analyzers_suites.py and tests/test_analyzers_state.py. Validation: & ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_analyzers_suites.py tests/test_analyzers_state.py -x -q --tb=short -> 73 passed.

### Workstream coverage-tranche-d-2026-04-29

- Owner: Copilot
- Goal: Finish coverage ExecPlan Closure Tranche D on parser utility, GUI, and remaining near-edge modules.
- Claims: docs/exec-plans/active/05-coverage-to-100.md, tests/test_gui.py, tests/test_formatter.py, tests/test_devtools_review_observability.py, src/sattline_parser/utils/formatter.py, src/sattlint/devtools/observability.py, src/sattlint/devtools/review_tool.py, src/sattlint_gui/__init__.py, src/sattlint_gui/__main__.py, src/sattlint_gui/main.py, src/sattlint_gui/theme.py, src/sattlint_gui/window.py, src/sattlint_gui/frames/__init__.py, src/sattlint_gui/frames/analyze_frame.py, src/sattlint_gui/frames/config_frame.py, src/sattlint_gui/frames/docs_frame.py, src/sattlint_gui/frames/results_frame.py, src/sattlint_gui/frames/sidebar.py, src/sattlint_gui/frames/tools_frame.py, src/sattlint_gui/widgets/__init__.py, src/sattlint_gui/widgets/analyzer_list.py, src/sattlint_gui/widgets/console.py, src/sattlint_gui/widgets/report_view.py, src/sattlint_gui/widgets/styled_widgets.py, src/sattlint_gui/widgets/target_list.py, src/sattlint_gui/binding.py
- First validation: & ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_gui.py -x -q --tb=short
- Status: done
- Notes: Added `tests/test_formatter.py`, `tests/test_devtools_review_observability.py`, and expanded `tests/test_gui.py`; focused validation passed (`45 passed`), tranche command passed (`30 passed`), full-suite checkpoint still blocked by unrelated LSP/resolution reds and global 100% gate.

### Workstream d-wave-2-3-backlog-execplan-2026-04-29

- Owner: Copilot
- Goal: Create the active execution plan for D-Wave-2, D-Wave-3, and D-Wave-Backlog from the feature roadmap.
- Claims: .github/coordination/current-work.md, docs/exec-plans/active/07-d-wave-2-3-backlog-execution.md
- First validation: & ".venv/Scripts/python.exe" -m sattlint.devtools.doc_gardener
- Status: done
- Notes: Added docs/exec-plans/active/07-d-wave-2-3-backlog-execution.md. Validation command ran and failed on pre-existing tracker structure finding: docs/exec-plans/tech-debt-tracker.md missing consolidation source ledger.

### Workstream d-wave-split-execplans-2026-04-29

- Owner: Copilot
- Goal: Create separate active ExecPlans for D-Wave-2, D-Wave-3, and D-Wave-Backlog.
- Claims: .github/coordination/current-work.md, docs/exec-plans/active/08-d-wave-2-test-and-quality-infrastructure.md, docs/exec-plans/active/09-d-wave-3-semantic-and-differential-tooling.md, docs/exec-plans/active/10-d-wave-backlog-advanced-analysis-gating.md, docs/exec-plans/active/07-d-wave-2-3-backlog-execution.md
- First validation: & ".venv/Scripts/python.exe" -m sattlint.devtools.doc_gardener
- Status: done
- Notes: Added three split plans and marked combined file as superseded to avoid active-routing ambiguity. Doc-gardener still reports pre-existing tracker structure finding.

### Workstream coverage-plan-rebaseline-2026-04-29

- Owner: Copilot
- Goal: Update the active coverage exec plan with the latest remaining blockers to reach 100 percent.
- Claims: .github/coordination/current-work.md, docs/exec-plans/active/05-coverage-to-100.md
- First validation: git diff -- .github/coordination/current-work.md docs/exec-plans/active/05-coverage-to-100.md
- Status: done
- Notes: Docs-only rebaseline complete. The exec plan now uses coverage.xml and htmlcov/status.json as the current remaining-work baseline and lists the missing owner buckets explicitly.

### Workstream coverage-editor-api-checkpoint-2026-04-29

- Owner: Copilot
- Goal: Verify and clear the stale editor_api full-suite checkpoint blocker in the active coverage plan.
- Claims: .github/coordination/current-work.md, docs/exec-plans/active/05-coverage-to-100.md
- First validation: & ".venv/Scripts/python.exe" -m pytest tests/test_editor_api.py -x -q --tb=short --cov-fail-under=0
- Status: done
- Notes: The supposed editor_api blocker no longer reproduces. `tests/test_editor_api.py` passes under coverage and the full suite is now test-clean with `1059 passed` at roughly `78%` coverage when run with `--cov-fail-under=0`.


### Workstream coverage-workpackage-2-dataflow-2026-04-29

- Owner: Copilot
- Goal: Start Work Package 2 by extending `tests/test_dataflow.py` around typedef walking and parameter-mapping paths in `dataflow.py`.
- Claims: .github/coordination/current-work.md, docs/exec-plans/active/05-coverage-to-100.md, tests/test_dataflow.py
- First validation: & ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_dataflow.py -x -q --tb=short
- Status: done
- Notes: Added 5 focused tests to `tests/test_dataflow.py` covering root typedef traversal, external-origin skip behavior, parameter-mapped child constant-condition evaluation, GLOBAL mapping non-aliasing, and unresolved moduletype-instance early return. Validation passed: `19 passed`.

### Workstream coverage-wp1-configgen-stations-2026-04-29

- Owner: Copilot
- Goal: Start coverage Work Package 1 by exercising uncovered station-configuration branches in configgen through the owner docgen suite.
- Claims: .github/coordination/current-work.md, tests/test_docgen.py, src/sattlint/docgenerator/configgen.py
- First validation: & ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_docgen.py -x -q --tb=short
- Status: done
- Notes: Added station-configuration coverage in `tests/test_docgen.py` for case-insensitive transitive library enrichment and missing-config station rows. Fixed `configgen.py` to render `N/A` instead of blank IP cells for unresolved stations. Validation passed: `pytest --no-cov tests/test_docgen.py -x -q --tb=short` (33 passed).

### Workstream coverage-wp3-parser-api-2026-04-29

- Owner: Copilot
- Goal: Start coverage Work Package 3 by draining uncovered parser-core API branches through the existing parser owner suite.
- Claims: .github/coordination/current-work.md, docs/exec-plans/active/05-coverage-to-100.md, tests/test_parser_core.py, src/sattline_parser/api.py
- First validation: & ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_parser_core.py -x -q --tb=short
- Status: done
- Notes: Added 8 focused parser-core API tests in `tests/test_parser_core.py` covering `create_sl_parser()`, EOF/token/character parse summaries, plain `describe_parse_error()` fallback, cp1252/latin-1 text decoding, compressed-source loading, and `parse_source_text()` debug/error branches. Validation passed: focused `tests/test_parser_core.py` -> `26 passed`; broader WP3 parser command `tests/test_parser_core.py tests/test_parser_validation.py` -> `98 passed`.

## Current Status
- **Tests**: 970 passing
- **Coverage**: 76% (6255 uncovered lines / 26490 total executable lines)
- **Progress**: +81 tests, +135 lines covered this session

## Files with Complete Coverage (44 total)
- Full coverage achieved on various utility modules and test helpers

## Key Improvements This Session
1. **Quick-win single-line tests**: 15+ functions covered
2. **Utility module tests**: casefolding, _validation_shared, call_signatures, artifact_registry, tool_reports, progress_reporting, scope, paths, type_graph
3. **Report builder tests**: status_reports, derived_reports, coverage_reports, findings, path_sanitizer, document, console
4. **LSP document state tests**: apply_content_changes, has_analysis, replace_text
5. **Model tests**: VariableUsage all branches, ProjectGraph, findings
6. **Framework tests**: SimpleReport summary variants
7. **Analyzer tests**: _sfc_module_walk iterator

## Remaining Large Gaps
- validation.py: 435 missing lines
- dataflow.py: 788 missing lines
- variables.py: 751 missing lines
- Various LSP/GUI modules with partial coverage
- Large analyzer modules

## Next Actions
- Continue with medium-priority coverage targets
- Focus on LSP modules (_server_document.py, _server_helpers.py)
- Add tests for transformer/grammar modules

### Workstream repo-audit-full-pass-2026-04-30

- Owner: Copilot
- Goal: Reduce blocking repo-audit findings toward a passing full audit, starting with highest-leverage portability and typing blockers.
- Claims: .github/coordination/current-work.md, docs/exec-plans/active/07-d-wave-2-3-backlog-execution.md, docs/exec-plans/active/08-d-wave-2-test-and-quality-infrastructure.md, docs/exec-plans/active/09-d-wave-3-semantic-and-differential-tooling.md, docs/exec-plans/active/10-d-wave-backlog-advanced-analysis-gating.md, docs/exec-plans/completed/ai-first-repo-hardening.md, src/sattlint/devtools/repo_audit.py, src/sattlint/devtools/pipeline.py, src/sattlint/devtools/doc_gardener.py, src/sattlint/devtools/observability.py, src/sattlint/devtools/review_tool.py, src/sattlint_lsp/server.py, tests/test_repo_audit.py, tests/test_comment_code.py, tests/test_docgen.py, tests/test_gui.py, tests/test_parser_core.py, tests/test_app.py, tests/test_lsp_document.py, tests/test_r2_1_expression_assignment.py
- First validation: & ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_repo_audit.py -x -q --tb=short
- Status: done
- Notes: Full audit report is clean. Final validation: & ".venv/Scripts/sattlint-repo-audit.exe" --profile full --output-dir artifacts/audit -> 0 findings, pass. Duplicate pipeline finding-ID noise removed by fingerprint-based invariant checks.

### Workstream coverage-plan-parallelize-2026-04-30

- Owner: Copilot
- Goal: Replace the stale monolithic coverage ExecPlan with an orchestrator plus parallel lane plans that can be worked independently today.
- Claims: .github/coordination/current-work.md, docs/exec-plans/active/05-coverage-to-100.md, docs/exec-plans/active/11-coverage-lane-a-app-devtools-engine.md, docs/exec-plans/active/12-coverage-lane-b-analyzers-semantic-lsp.md, docs/exec-plans/active/13-coverage-lane-c-parser-reporting-gui.md
- First validation: git diff -- .github/coordination/current-work.md docs/exec-plans/active/05-coverage-to-100.md docs/exec-plans/active/11-coverage-lane-a-app-devtools-engine.md docs/exec-plans/active/12-coverage-lane-b-analyzers-semantic-lsp.md docs/exec-plans/active/13-coverage-lane-c-parser-reporting-gui.md
- Status: done
- Notes: Converted the coverage plan into one coordinator file plus three executable owner lanes. Actual code-file claims should now be taken from the lane plans before edits start.

### Workstream coverage-lane-b-variables-dataflow-2026-04-30

- Owner: Copilot
- Goal: Drain slice 1 of coverage lane B through focused owner tests for `dataflow.py` and `variables.py`.
- Claims: .github/coordination/current-work.md, docs/exec-plans/active/12-coverage-lane-b-analyzers-semantic-lsp.md, tests/test_dataflow.py, tests/test_analyzers_variables.py, src/sattlint/analyzers/dataflow.py, src/sattlint/analyzers/variables.py
- First validation: & ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_dataflow.py tests/test_analyzers_variables.py -x -q --tb=short
- Status: done
- Notes: Added focused owner tests for `dataflow.py` sequence-control branches and `variables.py` helper extraction paths. Validation passed: slice command -> `63 passed`; lane-close owner set -> `243 passed`. Returned to orchestrator for the next shared miss-list checkpoint.

### Workstream coverage-lane-c-parser-2026-04-30

- Owner: Copilot
- Goal: Start lane C execution by draining parser transformer residue through the existing parser owner suites.
- Claims: .github/coordination/current-work.md, docs/exec-plans/active/13-coverage-lane-c-parser-reporting-gui.md, tests/test_parser_core.py, tests/test_mms_report.py, tests/test_analyzers_state.py, tests/test_icf_validation.py, tests/test_gui.py
- First validation: & ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_parser_core.py tests/test_parser_validation.py tests/test_parser.py -x -q --tb=short
- Status: done
- Notes: Parser slice passed on the lane-local owner suites (135 passed). Reporting slice passed on tests/test_mms_report.py (3), tests/test_analyzers_state.py (32), and tests/test_icf_validation.py (21). GUI slice passed on tests/test_gui.py (35). Lane checkpoint validation passed: parser/reporting/gui owner set plus tests/test_app.py, tests/test_app_analysis.py, tests/test_app_menus.py, and tests/test_analyzers_variables.py -> 424 passed.

### Workstream coverage-lane-a-app-devtools-engine-2026-04-30

- Owner: Copilot
- Goal: Implement lane A owner-suite coverage work across docgen, repo-audit, app/CLI, and engine surfaces.
- Claims: .github/coordination/current-work.md, docs/exec-plans/completed/11-coverage-lane-a-app-devtools-engine.md, tests/test_docgen.py, tests/test_repo_audit.py, tests/test_app.py, tests/test_app_analysis.py, tests/test_app_menus.py, tests/test_cli.py, tests/test_engine.py, src/sattlint/docgenerator/configgen.py, src/sattlint/devtools/repo_audit.py, src/sattlint/devtools/doc_gardener.py, src/sattlint/app_analysis.py, src/sattlint/app_graphics.py, src/sattlint/config.py, src/sattlint/app_docs.py, src/sattlint/app_cli_commands.py, src/sattlint/cli/entry.py, src/sattlint/engine.py
- First validation: & ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_docgen.py -x -q --tb=short
- Status: done
- Notes: Lane closed through owner-suite expansions only. Validation totals: tests/test_docgen.py (51 passed), tests/test_repo_audit.py (65 passed), tests/test_app.py tests/test_app_analysis.py tests/test_app_menus.py tests/test_cli.py (174 passed), tests/test_engine.py (23 passed), lane-close owner set (313 passed). ExecPlan moved to docs/exec-plans/completed/11-coverage-lane-a-app-devtools-engine.md.

### Workstream coverage-orchestrator-checkpoint-2026-04-30

- Owner: Copilot
- Goal: Refresh the shared coverage baseline and confirm whether lane B is still a dominant residual cluster.
- Claims: .github/coordination/current-work.md, docs/exec-plans/active/05-coverage-to-100.md, docs/exec-plans/active/12-coverage-lane-b-analyzers-semantic-lsp.md
- First validation: & ".venv/Scripts/python.exe" -m pytest -q --cov-fail-under=0
- Status: done
- Notes: Shared checkpoint reran clean after clearing stale `.coverage` state. Validation passed at `1236 passed, 1 warning`; artifacts refreshed to about `82.35%` coverage with `4794` uncovered lines. See `docs/exec-plans/active/05-coverage-to-100.md` for the current residual-cluster summary derived from the refreshed checkpoint.

### Workstream coverage-lane-b-analyzer-helpers-2026-04-30

- Owner: Copilot
- Goal: Continue lane-B backlog reduction through focused owner tests for analyzer helper surfaces, currently `modules.py`, `reset_contamination.py`, `variable_usage_reporting.py`, and `mms.py`.
- Claims: .github/coordination/current-work.md, docs/exec-plans/active/12-coverage-lane-b-analyzers-semantic-lsp.md, tests/test_analyzers_suites.py, tests/test_analyzers_state.py, tests/test_analyzers_variables.py, src/sattlint/analyzers/modules.py, src/sattlint/analyzers/reset_contamination.py, src/sattlint/analyzers/variable_usage_reporting.py, src/sattlint/analyzers/mms.py
- First validation: & ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_analyzers_suites.py tests/test_analyzers_state.py -x -q --tb=short
- Status: done
- Notes: Added focused owner tests in `tests/test_analyzers_suites.py` for `variable_usage_reporting.py` and `modules.py` helper/reporting seams, plus `tests/test_analyzers_variables.py` coverage for `mms.py` nested typedef recursion and default-tag paths. Focused validations passed: `tests/test_analyzers_suites.py` -> `52 passed`, `tests/test_analyzers_variables.py` -> `44 passed`. Clean shared checkpoint passed with `1236 passed, 1 warning`; refreshed lane totals now put lane B at about `1253` misses, below lane A at about `1335`, so backlog-dominance acceptance is met.

### Workstream merge-fix-tech-debt-tracker-2026-05-01

- Owner: Copilot
- Goal: Resolve the active merge conflict in the tech debt tracker without dropping legacy summary data.
- Claims: .github/coordination/current-work.md, docs/exec-plans/tech-debt-tracker.md
- First validation: rg -n "^(<<<<<<<|=======|>>>>>>>)" docs/exec-plans/tech-debt-tracker.md .github/coordination/current-work.md
- Status: done
- Notes: Conflict resolved by keeping the expanded T-series tracker structure and preserving the legacy TD table as a summary block. Validation passed: `rg -n "^(<<<<<<<|=======|>>>>>>>)" docs/exec-plans/tech-debt-tracker.md .github/coordination/current-work.md` returned no matches; git merge-conflicts list is empty.

### Workstream coverage-lane-c-closeout-2026-04-30

- Owner: Copilot
- Goal: Continue lane C toward closure by draining the remaining parser/reporting helper residue and then finishing the biggest headless GUI owner gaps.
- Claims: .github/coordination/current-work.md, docs/exec-plans/completed/13-coverage-lane-c-parser-reporting-gui.md, tests/test_parser_core.py, tests/test_analyzers_state.py, tests/test_icf_validation.py, tests/test_gui.py
- First validation: & ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_parser_core.py tests/test_parser_validation.py tests/test_parser.py tests/test_analyzers_state.py tests/test_icf_validation.py -x -q --tb=short
- Status: done
- Notes: Lane C closed through owner-suite expansions only. Focused validations stayed green throughout (`tests/test_parser_core.py` -> `42 passed`, `tests/test_gui.py` -> `43 passed`). Lane-close validation passed: `447 passed`. Final lane-local coverage refresh removed `formatter.py` as a blocker, reduced `_modules_mixin.py` to `26` misses, reduced `config_frame.py` to `3` misses, and left only short residual sweeps across parser/gui files.

### Workstream coverage-plan-final-phase-2026-04-30

- Owner: Copilot
- Goal: Close the finished lane plans, replace them with a final-phase split, and reframe the coverage orchestrator around the remaining work needed to reach 100 percent.
- Claims: .github/coordination/current-work.md, docs/exec-plans/active/05-coverage-to-100.md, docs/exec-plans/active/12-coverage-lane-b-analyzers-semantic-lsp.md, docs/exec-plans/completed/12-coverage-lane-b-analyzers-semantic-lsp.md, docs/exec-plans/active/14-coverage-phase-2-app-devtools-core.md, docs/exec-plans/active/15-coverage-phase-2-analyzers-semantic-lsp.md, docs/exec-plans/active/16-coverage-phase-2-parser-gui-reporting.md, docs/exec-plans/active/17-coverage-phase-2-orphans-and-final-gate.md
- First validation: git diff -- .github/coordination/current-work.md docs/exec-plans/active/05-coverage-to-100.md docs/exec-plans/active/12-coverage-lane-b-analyzers-semantic-lsp.md docs/exec-plans/active/14-coverage-phase-2-app-devtools-core.md docs/exec-plans/active/15-coverage-phase-2-analyzers-semantic-lsp.md docs/exec-plans/active/16-coverage-phase-2-parser-gui-reporting.md docs/exec-plans/active/17-coverage-phase-2-orphans-and-final-gate.md
- Status: done
- Notes: Archived the stale active lane-B plan under docs/exec-plans/completed/12-coverage-lane-b-analyzers-semantic-lsp.md, rewrote the orchestrator around the clean 82.35% / 4794-miss baseline, and created four active final-phase plans: app/devtools/core, analyzers/semantic/LSP, parser/GUI/reporting/docgen, and orphans/final gate. Validation: planning-file git diff plus active/completed directory checks.

### Workstream overlap-detector-clipping-layers-2026-04-30

- Owner: Copilot
- Goal: Make layout overlap detection ignore different Layer_ values by default and base module-visible overlap on ClippingBounds instead of raw invocation rectangles.
- Claims: .github/coordination/current-work.md, src/sattlint/analyzers/layout_geometry.py, tests/test_analyzers_variables.py
- First validation: & ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_analyzers_variables.py -k "layout_overlap" -x -q --tb=short
- Status: done
- Notes: Validation passed: `pytest --no-cov tests/test_analyzers_variables.py -k "layout_overlap" -x -q --tb=short` -> `5 passed`. Sample recheck now reports only visible top-level overlaps and suppresses `Layer1`/`Layer2` false positives.

### Workstream parser-validation-valid-legacy-cases-2026-04-30

- Owner: Copilot
- Goal: Fix strict validation false positives for legacy-valid AnyType comparisons, duplicate sequence labels, and CONST declarations without explicit init values.
- Claims: .github/coordination/current-work.md, src/sattlint/_validation_expression.py, src/sattlint/validation.py, tests/test_parser_validation.py
- First validation: & ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_parser_validation.py -k "anytype or const or duplicate or comparison or seqfork" -x -q --tb=short
- Status: done
- Notes: Narrow parser-validation slice completed. Actual validation run: & ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_parser_validation.py -x -q --tb=short -> pass. Kept strict unknown-target and ambiguous-target failures while allowing AnyType relational comparisons, unused duplicate labels, and CONST declarations without explicit init values.

### Workstream coverage-gate-86-2026-04-30

- Owner: Copilot
- Goal: Raise the repository-default pytest coverage gate to 86 percent.
- Claims: .github/coordination/current-work.md, pyproject.toml, docs/exec-plans/tech-debt-tracker.md
- First validation: & ".venv/Scripts/python.exe" -m pytest -q
- Status: done
- Notes: Updated `pyproject.toml` from `--cov-fail-under=70` to `--cov-fail-under=86` and aligned `docs/exec-plans/tech-debt-tracker.md`. Validation passed: & ".venv/Scripts/python.exe" -m pytest -q -> `1401 passed, 1 warning`, `Required test coverage of 86% reached. Total coverage: 88.11%`.

### Workstream coverage-phase2-app-core-2026-04-30

- Owner: Copilot
- Goal: Close the active phase-2 app/devtools/core plan by draining the remaining dominant owner-suite seams and updating the plan status.
- Claims: .github/coordination/current-work.md, docs/exec-plans/active/14-coverage-phase-2-app-devtools-core.md, tests/test_app.py, tests/test_app_analysis.py, tests/test_app_menus.py, tests/test_cli.py, tests/test_repo_audit.py, tests/test_engine.py, tests/test_pipeline.py, tests/test_pipeline_collection.py, tests/test_pipeline_run.py, tests/test_pipeline_phase2.py, tests/test_artifact_contracts.py, tests/test_structural_reports.py, src/sattlint/app.py, src/sattlint/app_analysis.py, src/sattlint/app_base.py, src/sattlint/app_graphics.py, src/sattlint/app_menus.py, src/sattlint/app_support.py, src/sattlint/config.py, src/sattlint/console.py, src/sattlint/cache.py, src/sattlint/devtools/repo_audit.py, src/sattlint/devtools/doc_gardener.py, src/sattlint/engine.py, src/sattlint/devtools/pipeline.py, src/sattlint/devtools/pipeline_artifacts.py, src/sattlint/devtools/structural_reports.py
- First validation: & ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_app.py tests/test_app_analysis.py tests/test_app_menus.py tests/test_cli.py -x -q --tb=short
- Status: active
- Notes: Expanded owner suites only: `tests/test_app.py` now covers config validation/loading/target checks plus adversarial `self_check()` helper paths, `tests/test_engine.py` now covers syntax-validation, root-only loader branches, merge/dump helpers, `_visit()` tail behavior, and lookup/cache helpers, `tests/test_repo_audit.py` covers doc_gardener drift/update/main orchestration, and pipeline helpers are covered in `tests/test_pipeline_collection.py` plus `tests/test_pipeline_run.py`. Focused validations passed: `tests/test_app.py` (`100 passed`), app owner set (`211 passed`), `tests/test_engine.py` (`31 passed`), `tests/test_engine.py` (`47 passed`), `tests/test_repo_audit.py` (`76 passed`), `tests/test_pipeline_collection.py tests/test_pipeline_run.py` (`120 passed`), broader pipeline owner set (`284 passed`). Last clean shared checkpoint passed at `1357 passed, 1 warning`, `86%` total coverage, and `3686` misses. After clearing the stale terminal `COVERAGE_FILE=.coverage.app-graphics`, the next full checkpoint stopped emitting the coverage-database warning and instead exposed an unrelated parser-validation failure (`tests/test_parser_validation.py::test_validation_internal_validate_sequence_nodes_warns_for_multiple_init_steps` missing `label_counts`). The trustworthy refreshed plan-local counts now include `src/sattlint/app_analysis.py` `245 -> 55`, `src/sattlint/app_graphics.py` `198 -> 111`, `src/sattlint/config.py` `79 -> 29`, `src/sattlint/devtools/doc_gardener.py` `145 -> 99`, `src/sattlint/devtools/pipeline.py` `95 -> 91`, `src/sattlint/devtools/repo_audit.py` `236 -> 134`, and `src/sattlint/engine.py` `168 -> 57`.

### Workstream coverage-phase-2-analyzers-semantic-lsp-2026-04-30

- Owner: Copilot
- Goal: Implement final-phase analyzer, semantic, and LSP coverage work through the owner suites in ExecPlan 15.
- Claims: .github/coordination/current-work.md, docs/exec-plans/active/15-coverage-phase-2-analyzers-semantic-lsp.md, tests/test_analyzers_suites.py, tests/test_analyzers_state.py, tests/test_dataflow.py, tests/test_analyzers_variables.py, tests/test_editor_api.py, tests/test_lsp_document.py, tests/test_lsp_diagnostics.py, tests/test_moduletype_resolution_scoped.py, tests/test_canonical_resolution.py, src/sattlint/analyzers/modules.py, src/sattlint/analyzers/reset_contamination.py, src/sattlint/analyzers/mms.py, src/sattlint/analyzers/variables.py, src/sattlint/analyzers/dataflow.py, src/sattlint/analyzers/_variables_effect_flow.py, src/sattlint/analyzers/_sfc_collectors.py, src/sattlint/analyzers/_sfc_guard_logic.py, src/sattlint/analyzers/variable_traversal.py, src/sattlint/analyzers/alarm_integrity.py, src/sattlint/analyzers/naming.py, src/sattlint/analyzers/initial_values.py, src/sattlint/analyzers/sattline_semantics.py, src/sattlint/analyzers/sfc.py, src/sattlint/core/semantic.py, src/sattlint_lsp/_server_helpers.py, src/sattlint_lsp/_server_document.py, src/sattlint_lsp/workspace_store.py, src/sattlint_lsp/server.py, src/sattlint_lsp/local_parser.py, src/sattlint/resolution/common.py
- First validation: & ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_editor_api.py -x -q --tb=short
- Status: done
- Notes: Added focused owner-suite tests only: `tests/test_editor_api.py`, `tests/test_lsp_document.py`, `tests/test_lsp_diagnostics.py`, `tests/test_moduletype_resolution_scoped.py`, and `tests/test_analyzers_state.py`. The latest helper slice added three pure `_server_helpers.py` tests in `tests/test_lsp_diagnostics.py`. Validation passed: editor_api (26), lsp_document (38), lsp_diagnostics owner suite before the latest helper slice (37), latest helper slice targeted run (3), refreshed lsp_diagnostics owner suite (40), moduletype_resolution_scoped (12), analyzers_state (39), ExecPlan 15 owner closeout set (271). Earlier full repo checkpoint passed at `1310 passed, 1 warning` but emitted noisy coverage-database parse warnings; after clearing `.coverage*`, the canonical full-suite artifacts were restored and now show `87.1%` total coverage (`3505` uncovered lines), with `src/sattlint_lsp/_server_helpers.py` reduced to `58` misses in `htmlcov/status.json`. No LSP restart required because only tests/docs changed.

### Workstream coverage-phase-2-parser-gui-reporting-2026-04-30

- Owner: Copilot
- Goal: Close ExecPlan 16 through the existing parser, docgen, reporting, graphics, and GUI owner suites, starting with the remaining docgen/classification branches.
- Claims: .github/coordination/current-work.md, docs/exec-plans/active/16-coverage-phase-2-parser-gui-reporting.md, tests/test_docgen.py
- First validation: & ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_docgen.py -x -q --tb=short
- Status: done
- Notes: Added focused `tests/test_docgen.py` coverage for documentation-scope fallback and dedupe behavior, complex sequence row rendering, uncategorized appendix rendering, and empty-sequence output. Validation passed: `tests/test_docgen.py` -> `56 passed`; parser owner suites -> `143 passed`; graphics owner suite -> `7 passed`; GUI/reporting owner suites -> `104 passed`; ExecPlan 16 closeout command -> `310 passed`.

### Workstream coverage-phase-2-orphans-final-gate-2026-04-30

- Owner: Copilot

### Workstream coverage-parser-token-mixin-2026-04-30

- Owner: Copilot
- Goal: Drain the remaining parser token-coercion residue through direct owner-suite tests in `tests/test_parser_core.py`.
- Claims: .github/coordination/current-work.md, tests/test_parser_core.py, src/sattline_parser/transformer/_tokens_mixin.py
- First validation: & ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_parser_core.py -k "tokens_mixin" -x -q --tb=short
- Status: active
- Notes: Local hypothesis: the remaining `_tokens_mixin.py` misses are branch-local coercion helpers and error paths that can be exhausted without production edits.

### Workstream startup-initial-check-pause-2026-04-30

- Owner: Copilot
- Goal: Pause interactive startup on initial AST-cache or target-load failures so parse errors remain visible before the menu continues.
- Claims: .github/coordination/current-work.md, src/sattlint/app.py, tests/test_app.py
- First validation: & ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_app.py -k "startup_pause or initial_check" -x -q --tb=short
- Status: done
- Notes: Interactive startup now pauses when `ensure_ast_cache()` reports a failed initial target parse/load. Validation passed: exact node `tests/test_app.py::test_main_pauses_when_initial_ast_check_fails` and nearby startup slice (`3 passed`).
- Goal: Give the zero-owner orphan modules explicit owner suites and drive the final-gate plan in ExecPlan 17.
 - Claims: .github/coordination/current-work.md, docs/exec-plans/active/17-coverage-phase-2-orphans-and-final-gate.md, tests/test_devtools_orphans.py, tests/test_symbolic_lite.py, tests/test_parser_validation.py, tests/test_structural_reports.py
- First validation: & ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_devtools_orphans.py tests/test_symbolic_lite.py -x -q --tb=short
- Status: active
- Notes: Owner search found no existing test references for the orphan modules, so dedicated suites were justified. Focused orphan validation passed at `12 passed`, and the clean orphan checkpoint (`COVERAGE_FILE=.coverage.orphans-final`) passed with `1272 passed, 1 warning`, `85%` total coverage, putting all orphan modules at `100%`. `tests/test_parser_validation.py` was expanded and `src/sattlint/validation.py` reached `100%` in the earlier clean checkpoint. `tests/test_structural_reports.py` is now `22 passed`. The suspected order-dependent docgen blocker no longer reproduced: reduced reproductions stayed green, and the fresh shared checkpoint reached `1369 passed, 1 warning`. The actual full-suite blocker was a stale helper test call in `tests/test_parser_validation.py` after `_validate_sequence_nodes()` gained required `label_counts`; that test was updated and the owner suite now passes at `90 passed`. The remaining shared-checkpoint issue is coverage SQLite corruption during report generation on this machine (`no such table: tracer/line_bits`), not a failing test.

### Workstream coverage-phase-2-checkpoint-refresh-2026-04-30

- Owner: Copilot
- Goal: Refresh the shared coverage baseline after ExecPlan 16 closeout and confirm whether the phase-2 parser/GUI/reporting/docgen bucket still controls residual planning.
- Claims: .github/coordination/current-work.md, docs/exec-plans/active/05-coverage-to-100.md
- First validation: Remove-Item -Force .coverage* -ErrorAction SilentlyContinue ; & ".venv/Scripts/python.exe" -m pytest -q --cov-fail-under=0
- Status: done
- Notes: Discarded one warning-heavy checkpoint that hit a corrupted `.coverage` report database (`no such table: tracer`). Clean rerun after clearing `.coverage*` passed at `1272 passed, 1 warning`, rewrote `coverage.xml` to `84.65%` (`4169` uncovered lines), and left the residual ordering at about `2198` analyzer/semantic/LSP misses, `1373` app/devtools/core misses, `493` parser/GUI/reporting/docgen misses, and `105` orphan/residual misses. The phase-2 parser bucket is no longer controlling, but it is still the third-largest residual bucket.

### Workstream parser-anytype-arithmetic-2026-04-30

- Owner: Copilot
- Goal: Fix strict validation false positive that rejects arithmetic expressions using `AnyType` operands in otherwise valid legacy code.
- Claims: .github/coordination/current-work.md, src/sattlint/_validation_expression.py, tests/test_parser_validation.py
- First validation: & ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_parser_validation.py -k "anytype and arithmetic" -x -q --tb=short
- Status: done
- Notes: Arithmetic and unary expression validation now treat `AnyType` like the existing comparison carve-out, while boolean arithmetic still fails. Validation passed: exact node `tests/test_parser_validation.py::test_validate_single_file_syntax_accepts_exitcode_arithmetic_with_anytype` and adjacent slice (`3 passed`).

### Workstream parser-anytype-assignment-2026-04-30

- Owner: Copilot
- Goal: Fix strict validation false positive that rejects assigning `AnyType` expression results to typed targets in legacy-valid code.
- Claims: .github/coordination/current-work.md, src/sattlint/_validation_type_helpers.py, tests/test_r2_1_expression_assignment.py
- First validation: & ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_r2_1_expression_assignment.py -k "anytype and assignment" -x -q --tb=short
- Status: done
- Notes: `_assignment_type_matches()` now treats `AnyType` as source-compatible as well as target-compatible. Validation passed: exact node `tests/test_r2_1_expression_assignment.py::test_anytype_expression_assignment_to_real_allowed`, adjacent assignment slice (`4 passed`), and real-file check via `sattlint.exe syntax-check Libs/HA/ProjectLib/KaHAKrystSupportLib.s`, which no longer reports the AnyType assignment error and now stops on an unrelated unknown datatype `RcpInteger`.

### Workstream repo-gate-fix-pass-2026-04-30

- Owner: Copilot
- Goal: Fix the current failing pre-commit and full repo-audit findings, then rerun the gates, commit, and push.
- Claims: .github/coordination/current-work.md, .github/hooks/scripts/claimed_files_guard.py, .pre-commit-config.yaml, src/sattline_parser/fuzz_harness.py, src/sattline_parser/models/ast_model.py, src/sattline_parser/transformer/_sfc_mixin.py, src/sattlint/__main__.py, src/sattlint/_validation_expression.py, src/sattlint/analyzers/_sfc_collectors.py, src/sattlint/analyzers/_sfc_guard_logic.py, src/sattlint/analyzers/alarm_integrity.py, src/sattlint/analyzers/cyclomatic_complexity.py, src/sattlint/analyzers/dataflow.py, src/sattlint/analyzers/icf.py, src/sattlint/analyzers/loop_output_refactor.py, src/sattlint/analyzers/modules.py, src/sattlint/analyzers/parameter_drift.py, src/sattlint/analyzers/registry.py, src/sattlint/analyzers/rule_profiles.py, src/sattlint/analyzers/sattline_semantics.py, src/sattlint/analyzers/scan_loop_resource_usage.py, src/sattlint/analyzers/spec_compliance.py, src/sattlint/analyzers/variable_usage_reporting.py, src/sattlint/analyzers/variables.py, src/sattlint/app.py, src/sattlint/app_analysis.py, src/sattlint/config.py, src/sattlint/core/diagnostics.py, src/sattlint/devtools/corpus.py, src/sattlint/devtools/doc_gardener.py, src/sattlint/devtools/layer_linter.py, src/sattlint/devtools/mutation_engine.py, src/sattlint/devtools/parser_properties.py, src/sattlint/devtools/pipeline.py, src/sattlint/devtools/repo_audit.py, src/sattlint/devtools/review_tool.py, src/sattlint/devtools/structural_reports.py, src/sattlint/docgenerator/docgen.py, src/sattlint/validation.py, src/sattlint_lsp/_server_document.py, src/sattlint_lsp/local_parser.py, tests/test_analyzers_state.py, tests/test_analyzers_suites.py, tests/test_analyzers_variables.py, tests/test_app_analysis.py, tests/test_devtools_review_observability.py, tests/test_docgen.py, tests/test_engine.py, tests/test_graphics_validation.py, tests/test_gui.py, tests/test_icf_validation.py, tests/test_lsp_diagnostics.py, tests/test_lsp_document.py, tests/test_parser_core.py, tests/test_parser_validation.py, tests/test_repo_audit.py
- First validation: & ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_devtools_review_observability.py -x -q --tb=short
- Status: active
- Notes: Starting from live audit artifacts, not stale ledger entries. Ruff, Pyright, and Bandit targeted slices are clean. Current focus is the broader repo-wide Ruff E501 backlog revealed by full pre-commit; preference is file-local wrapping for operational code and file-level E501 exemptions only in text-heavy rule or diagnostics catalogs.

### Workstream coverage-phase-2-parser-docgen-reopen-2026-04-30

- Owner: Copilot
- Goal: Reopen the plan-16 docgen owner seam and continue reducing the remaining parser/GUI/reporting/docgen bucket through focused `tests/test_docgen.py` helper coverage.
- Claims: .github/coordination/current-work.md, docs/exec-plans/active/05-coverage-to-100.md, docs/exec-plans/active/16-coverage-phase-2-parser-gui-reporting.md, tests/test_docgen.py
- First validation: & ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_docgen.py -x -q --tb=short
- Status: done
- Notes: Reopened `tests/test_docgen.py` closed the remaining branch-local `classification.py` and `docgen.py` helper misses without production edits. Validation passed: `tests/test_docgen.py` -> `62 passed`; focused slice coverage on `sattlint.docgenerator.classification` and `sattlint.docgenerator.docgen` -> `100%`; clean shared checkpoint -> `1342 passed, 1 warning`, `86%` total coverage, and about `422` remaining misses in the broader plan-16 bucket.

### Workstream coverage-phase-2-parser-hotspots-2026-04-30

- Owner: Copilot
- Goal: Continue ExecPlan 16 on the current parser hotspot by draining `sl_transformer.py` through focused additions in `tests/test_parser_core.py` before widening into GUI or graphics files.
- Claims: .github/coordination/current-work.md, docs/exec-plans/active/16-coverage-phase-2-parser-gui-reporting.md, tests/test_parser_core.py
- First validation: & ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_parser_core.py -x -q --tb=short
- Status: done
- Notes: Added direct helper-path coverage in `tests/test_parser_core.py` for `sl_transformer.py` header parsing, tailed-rule payload extraction, nested-tail collection, duplicated top-level helpers, and `start()` error handling. Validation passed: `tests/test_parser_core.py` -> `45 passed`; focused slice coverage on `sattline_parser.transformer.sl_transformer` -> `100%`.

### Workstream coverage-phase-2-graphics-rules-hotspots-2026-04-30

- Owner: Copilot
- Goal: Continue ExecPlan 16 on the graphics hotspot by draining `graphics_rules.py` through focused direct-helper tests in `tests/test_graphics_validation.py`.
- Claims: .github/coordination/current-work.md, docs/exec-plans/active/16-coverage-phase-2-parser-gui-reporting.md, tests/test_graphics_validation.py
- First validation: & ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_graphics_validation.py -x -q --tb=short
- Status: done
- Notes: Added direct helper and reporting coverage in `tests/test_graphics_validation.py` for `graphics_rules.py` normalization, selector handling, store mutation, entry matching, nested mismatch collection, and summary output. Validation passed: `tests/test_graphics_validation.py` -> `10 passed`; focused slice coverage on `sattlint.graphics_rules` -> `100%`.

### Workstream coverage-phase-2-gui-window-hotspots-2026-04-30

- Owner: Copilot
- Goal: Continue ExecPlan 16 on the GUI hotspot by draining `window.py` through fake-Tk tests in `tests/test_gui.py`.
- Claims: .github/coordination/current-work.md, docs/exec-plans/active/16-coverage-phase-2-parser-gui-reporting.md, tests/test_gui.py
- First validation: & ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_gui.py -x -q --tb=short
- Status: done
- Notes: Added fake-Tk coverage in `tests/test_gui.py` for the real `window.py` constructor, `_build_layout`, and the remaining `publish_result()` edge paths without live widget integration. Validation passed: `tests/test_gui.py` -> `45 passed`; focused slice coverage on `sattlint_gui.window` -> `100%`.

### Workstream coverage-phase-2-reset-contamination-hotspots-2026-04-30

- Owner: Copilot
- Goal: Continue ExecPlan 15 by draining the current top analyzer hotspot in `reset_contamination.py` through focused owner tests in `tests/test_analyzers_state.py`.
- Claims: .github/coordination/current-work.md, docs/exec-plans/active/15-coverage-phase-2-analyzers-semantic-lsp.md, tests/test_analyzers_state.py, src/sattlint/analyzers/reset_contamination.py
- First validation: & ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_analyzers_state.py -x -q --tb=short
- Status: active
- Notes: Fresh shared checkpoint restored trustworthy artifacts at `1391 passed, 1 warning`, `88%`, and `3364` misses. Current slice starts from `src/sattlint/analyzers/reset_contamination.py` at `241` misses, which is now the largest remaining single-file blocker in ExecPlan 15.

### Workstream parser-validation-colour-keyword-2026-04-30

- Owner: Copilot
- Goal: Stop strict validation from rejecting `Colour` as a reserved identifier in SattLine variable declarations.
- Claims: .github/coordination/current-work.md, src/sattlint/validation.py, tests/test_parser_validation.py
- First validation: & ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_parser_validation.py -k "colour or reserved_keyword" -x -q --tb=short
- Status: done
- Notes: Narrow parser-validation slice completed. Kept reserved-name rejection for `InteractObjects` while allowing moduletype-local variable name `Colour`. Validation passed: `& ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_parser_validation.py -k "reserved_keyword or colour" -x -q --tb=short` -> `3 passed, 88 deselected`.
