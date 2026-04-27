# Current Work

Shared ledger for concurrent chats and agents in SattLint.

## Rules

- Read this file before first edit when parallel work is active.
- Claim exact files before editing them.
- Update first validation command when scope changes.
- Mark workstream `done` and release claims when finished.

## Active Workstreams

### Workstream repo-verify-fixall-026

- Owner: current chat
- Goal: clear remaining repo-audit import-cycle and editor type errors so repo verification can pass and commit can proceed
- Claims: .github/coordination/current-work.md, src/sattlint/devtools/coverage_reports.py, src/sattlint/devtools/pipeline.py, src/sattlint/devtools/repo_audit.py, src/sattlint/devtools/semantic_reports.py, src/sattlint/validation.py, src/sattlint_lsp/server.py, tests/test_app_menus.py, tests/test_icf_validation.py
- First validation: `& ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_repo_audit.py tests/test_pipeline.py -x -q --tb=short`
- Status: active
- Notes: start with shared devtools coverage-report extraction to break static repo_audit/pipeline cycle, then clear local validation and LSP narrowing diagnostics and rerun repo gate.

### Workstream assignment-datatype-025

- Owner: current chat
- Goal: reject incompatible assignment datatypes in strict syntax-check and keep VariableModifiers fixture valid
- Claims: none
- First validation: `& ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_parser_validation.py -x -q --tb=short -k assignment_datatype`
- Status: done
- Notes: added strict assignment datatype validation in `src/sattlint/validation.py` by comparing inferred RHS expression datatype against the target reference datatype in `_validate_statement_list`; added focused regression coverage in `tests/test_parser_validation.py` for rejecting `real` assigned to `integer`; updated `VariableModifiers.s` so `Output` is `real` and the fixture remains valid for variable-modifier coverage. Validation passed with `& ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_parser_validation.py -x -q --tb=short -k "real_assignment_to_integer or string_assignment"`, `& ".venv/Scripts/sattlint.exe" syntax-check tests/fixtures/corpus/valid/VariableModifiers.s`, and `& ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_corpus.py -x -q --tb=short`.

### Workstream subseqtransition-entry-024

- Owner: current chat
- Goal: align SUBSEQTRANSITION validation with real SattLine by requiring a transition-style entry inside the embedded body
- Claims: none
- First validation: `& ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_parser_validation.py -x -q --tb=short -k subseqtransition`
- Status: done
- Notes: added a strict-validation rule in `src/sattlint/validation.py` that rejects `SUBSEQTRANSITION` bodies starting with `SEQSTEP`; updated `SubSeqTransition.s` so the embedded body enters through `SEQTRANSITION TrCheckEnter WAIT_FOR True` before `SEQSTEP Checking`; added focused regression coverage in `tests/test_parser_validation.py`. Validation passed with `& ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_parser_validation.py -x -q --tb=short -k subseqtransition`, `& ".venv/Scripts/sattlint.exe" syntax-check tests/fixtures/corpus/valid/SubSeqTransition.s`, and `& ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_corpus.py -x -q --tb=short`.

### Workstream icf-name-repair-023

- Owner: current chat
- Goal: repair corrupted Danish field names in ignored `KaHAApplZ4.icf`
- Claims: none
- First validation: direct single-file ICF validation for `KaHAApplZ4.icf`
- Status: done
- Notes: repaired lossy `S jle` and `L b` spellings to canonical `Søjle` and `Løb` forms in units `KaHA251A` and `KaHA251B`. Direct single-file validation for `KaHAApplZ4.icf` cleared those invalid-field and missing-parameter issues; one unrelated remaining `unit structure drift` issue remains for `KaHA251Y` `LOGBATCHID1` casing.

### Workstream parallel-branch-terminal-022

- Owner: current chat
- Goal: align PARALLELBRANCH validation with real SattLine by rejecting branches that end in transition-style control nodes
- Claims: none
- First validation: `& ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_parser_validation.py -x -q --tb=short -k parallel_branch`
- Status: done
- Notes: added strict-validation rules in `src/sattlint/validation.py` that reject `PARALLELSEQ` branches ending in `SEQTRANSITION`, `SUBSEQTRANSITION`, `SEQFORK`, or `SEQBREAK`, and reject `SEQSTEP` immediately after `ENDPARALLEL` without an intervening transition; updated `SequenceParallel.s` and `ParallelWriteRace.s` so each branch ends on a step and a transition follows `ENDPARALLEL`; removed unused reserved-name locals from `ParallelWriteRace.s`; added focused regression coverage in `tests/test_parser_validation.py`. Validation passed with `& ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_parser_validation.py -x -q --tb=short -k "parallel_branch or step_immediately_after_endparallel or seqfork_after_step_without_seqbreak"`, `& ".venv/Scripts/sattlint.exe" syntax-check tests/fixtures/corpus/valid/SequenceParallel.s`, `& ".venv/Scripts/sattlint.exe" syntax-check tests/fixtures/corpus/semantic/ParallelWriteRace.s`, and `& ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_corpus.py tests/test_sattline_semantics.py -x -q --tb=short`.

### Workstream wave3-app-base-021

- Owner: current chat
- Goal: start Wave 3 by extracting the first `app_base` seam from `src/sattlint/app.py` while preserving the `sattlint.app` facade
- Claims: `.github/coordination/current-work.md`, `src/sattlint/app.py`, `src/sattlint/app_base.py`, `tests/test_app_menus.py`, `tests/test_cli.py`
- First validation: `& ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_cli.py -x -q --tb=short`
- Status: active
- Notes: first slice landed `src/sattlint/app_base.py` and moved config plus console helper implementations there while `src/sattlint/app.py` stayed as the public facade. Retargeted authoritative helper ownership tests in `tests/test_app_menus.py` to the new module and preserved facade call-time monkeypatch behavior from `app.py`. Validation passed: `& ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_app_menus.py -x -q --tb=short` (39 passed). Second slice landed the CLI parser plus syntax-check and `run_cli` dispatch helpers in `src/sattlint/app_base.py`; `src/sattlint/app.py` now forwards them with injected facade collaborators so app-level monkeypatch seams remain stable. Retargeted `tests/test_cli.py` to the owner module. Validation passed: `& ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_cli.py -x -q --tb=short` (9 passed) and `& ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_app_menus.py -x -q --tb=short -k "syntax_check_command_ok or cli_entry_point_forwards_sys_argv_without_loading_ast or syntax_check_command_reports_parse_error or syntax_check_command_prints_warning_for_legacy_sequence_initstep or syntax_check_command_rejects_missing_file or main_returns_error_for_unknown_cli_command"` (6 passed, 33 deselected).

### Workstream seqfork-step-form-020

- Owner: current chat
- Goal: align SEQFORK coverage with real SattLine step-level form and optional SEQBREAK
- Claims: none
- First validation: `& ".venv/Scripts/sattlint.exe" syntax-check tests/fixtures/corpus/valid/OpenSequenceSeqFork.s`
- Status: done
- Notes: updated `OpenSequenceSeqFork.s` to cover `SEQFORK` after a step with and without `SEQBREAK`, added focused parser-validation coverage in `tests/test_parser_validation.py`, and validated with `& ".venv/Scripts/sattlint.exe" syntax-check tests/fixtures/corpus/valid/OpenSequenceSeqFork.s`, `& ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_parser_validation.py -x -q --tb=short -k "seqfork_after_step_without_seqbreak or unknown_seqfork_target"`, and `& ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_corpus.py -x -q --tb=short`.

### Workstream tooling-wave2-019

- Owner: current chat
- Goal: implement TODO_TOOLS.md wave 2 items: ID2 sattline_semantic artifact, ID3 trace timing, ID7 rule_metrics artifact, ID15 regression lock-in tests, ID21 phase2 acceptance gate tests
- Claims: none
- First validation: `& ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_pipeline.py tests/test_sattline_semantics.py tests/test_tracing.py -x -q --tb=short`
- Status: done
- Notes: delivered `sattline_semantic.json`, `rule_metrics.json`, trace timing aggregation, and lock-in plus pipeline coverage for IDs 2, 3, 7, 15, and 21. Focused validation and full suite passed in the completing chat.

### Workstream tooling-wave3-021

- Owner: current chat
- Goal: implement TODO_TOOLS.md wave 3 items: ID11 incremental analysis planning, ID12 profiling summaries, ID13 performance budgets
- Claims: none
- First validation: `& ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_pipeline.py tests/test_tracing.py -x -q --tb=short`
- Status: done
- Notes: added derived pipeline reports for incremental planning, profiling summaries, and performance budgets; wired new artifacts and CLI flags through the analysis pipeline; and added focused regression coverage in `tests/test_pipeline.py` and `tests/test_tracing.py`. Validation passed: `& ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_pipeline.py tests/test_tracing.py -x -q --tb=short` (52 passed).

### Workstream icf-auto-formatter-018

- Owner: current chat
- Goal: make ICF unit, journal, and operation boundaries more visible with consistent blank-line formatting and add a built-in SattLint formatter command
- Claims: none
- First validation: `& ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_icf_validation.py tests/test_cli.py tests/test_app.py tests/test_app_menus.py -x -q --tb=short`
- Status: done
- Notes: added `format-icf` CLI command plus interactive `Format ICF files` action under `Analyze -> Interfaces & communication`; formatter now preserves all nonblank lines and only normalizes blank-line spacing, using two blank lines before `Unit`, `Journal`, and `Operation` headers and one before `Group` headers. Applied the formatter to 10 files under `Libs/HA/ICF/`. Validation passed: `& ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_icf_validation.py tests/test_cli.py tests/test_app.py tests/test_app_menus.py -x -q --tb=short` (130 passed), then a real-directory check run reported `Would change: 0` and `parse_icf_file()` succeeded for all 10 edited ICF files.

### Workstream icf-spacing-normalize-017

- Owner: current chat
- Goal: normalize heading spacing in `Libs/HA/ICF/*.icf` so section breaks are consistent and easier to read
- Claims: none
- First validation: semantic spacing check over `Libs/HA/ICF/*.icf` with nonblank lines unchanged
- Status: done
- Notes: normalized blank-line spacing before every section header in 10 ICF files under `Libs/HA/ICF/`, preserving each file's existing nonblank content, encoding, and newline style. Validation passed with formatter idempotence plus `parse_icf_file()` over all 10 files.

### Workstream wave1-wave2-016

- Owner: current chat
- Goal: implement Wave 1 audit outputs and Wave 2 engine plus LSP validation changes
- Claims: none
- First validation: `& ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_engine.py tests/test_lsp_document.py -x -q --tb=short`
- Status: done
- Notes: added `docs/refactor-wave1-audit.md` with Wave 1 dataclass and nullable-return triage (163 dataclasses scanned, 115 nullable-return functions scanned), updated `docs/refactor-remaining.md` to remove completed Waves 1 and 2 and point Wave 5 at the audit, enforced root-only validation before dependency traversal in strict `syntax_check` mode in `src/sattlint/engine.py`, and added request-boundary guards in `src/sattlint_lsp/server.py` with focused regression coverage. Validation passed: `& ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_engine.py tests/test_lsp_document.py -x -q --tb=short` (31 passed) plus workspace diagnostics on touched markdown files.

### Workstream tooling-starting-points-015

- Owner: current chat
- Goal: implement TODO_TOOLS.md starting-point items: ID10 baseline regression enforcement, ID14 corpus breadth manifests, ID19 pipeline coverage artifact, ID31 CLI consistency report
- Claims: src/sattlint/devtools/pipeline.py, src/sattlint/devtools/artifact_registry.py, src/sattlint/devtools/repo_audit.py, tests/test_pipeline.py, tests/test_repo_audit.py, tests/test_corpus.py, tests/fixtures/corpus/manifests/
- First validation: `& ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_pipeline.py tests/test_repo_audit.py tests/test_corpus.py -x -q --tb=short`
- Status: active

### Workstream refactor-plan-app-split-014

- Owner: current chat
- Goal: remove completed items from remaining refactor doc and replace `app.py` split notes with a staged, facade-first plan based on current code and tests
- Claims: none
- First validation: markdown-only edit; workspace diagnostics on touched markdown files
- Status: done
- Notes: rewrote `docs/refactor-remaining.md` to track only open work, removed stale completed-wave notes, and replaced the old big-bang `app.py` split plan with a staged facade-first plan based on the current seams in `src/sattlint/app.py`, `src/sattlint/app_graphics.py`, and `tests/test_app*.py`. Validation passed: workspace diagnostics on touched markdown files.

### Workstream gui-phase4-summaries-014

- Owner: current chat
- Goal: Phase 4 — structured summaries, two-pane Results view, run-bundle action
- Claims: none
- First validation: `& ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_gui.py -x -q --tb=short`
- Status: done
- Notes: `ReportView` now applies tag-based formatting (accent headers, colored counts); `ResultsFrame` redesigned as a two-pane view with timestamped history list and detail pane; `binding.run_bundle` runs variable analysis + checks in sequence; `AnalyzeFrame` wired with Run Bundle button. 22 tests passed.

### Workstream gui-analyzer-select-013

- Owner: current chat
- Goal: add interactive analyzer selection to Analyze view and wire Run Checks action
- Claims: none
- First validation: `& ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_gui.py -x -q --tb=short`
- Status: done
- Notes: added `AnalyzerList` widget (scrollable checkboxes, Select All/None), `binding.run_checks` (replicates `_run_checks` without interactive pause), updated `AnalyzeFrame` to use the checklist and expose a Run Checks button. Validation: 16 passed.

### Workstream gui-theme-shell-012

- Owner: current chat
- Goal: switch sattlint_gui to approved palette and improve shell result routing/state
- Claims: none
- First validation: `& ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_gui.py -x -q --tb=short`
- Status: done
- Notes: constrained `src/sattlint_gui/**` hex colors to approved palette, routed themed colors through shared widgets and config lists, added sidebar selection state, and auto-routed published output into Results. Validation passed: `& ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_gui.py -x -q --tb=short` (13 passed); follow-up palette scan found only approved hex values in `src/sattlint_gui/**`.

### Workstream icf-output-readability-011

- Owner: current chat
- Goal: make ICF invalid-entry terminal output easier to read and add durable terminal readability guidance
- Claims: none
- First validation: `& ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_icf_validation.py -q`
- Status: done
- Notes: ICF invalid-entry summaries now render drift details as structured multiline blocks (`compared`, missing/extra bullets, expected/found mismatch lines) and wrap long lines for terminal readability. Added global guidance in `AGENTS.md` to keep terminal output easy to scan. Validation passed: `& ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_icf_validation.py -q` (16 passed).

### Workstream icf-dilute-fields-010

- Owner: current chat
- Goal: add missing Dilute journal parameter fields in KaHAApplZ2/Z3/Z4 ICF units
- Claims: none
- First validation: `& ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_icf_validation.py -q`
- Status: done
- Notes: added 14 missing `JournalData_Parameters` fields under `Journal Dilute ,Dilute` for units `KaHA221X`, `KaHA231X`, `KaHA231Y`, `KaHA251X`, and `KaHA251Y`; validated with `& ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_icf_validation.py -q` (15 passed).

### Workstream icf-drift-detail-009

- Owner: current chat
- Goal: expand `unit structure drift` diagnostics with concrete missing/extra entry details
- Claims: none
- First validation: `& ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_icf_validation.py -q`
- Status: done
- Notes: `unit structure drift` now includes concrete entry previews for missing/extra sets and first mismatch details for ordering-only drift. Validation passed: `& ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_icf_validation.py -q` (15 passed).

### Workstream repo-verify-fixes-008

- Owner: current chat
- Goal: fix current pre-commit and repo-audit blockers in tests/test_app.py
- Claims: none
- First validation: `& ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_app.py`
- Status: done
- Notes: fixed test-only typing and lint cleanup in `tests/test_app.py`; isolated `config_menu` tests with `deepcopy` so list mutations no longer leak through shallow `DEFAULT_CONFIG.copy()`. Final validation passed: focused `pytest tests/test_app.py tests/test_app_menus.py`, `pre-commit --all-files`, and `sattlint-repo-audit --profile full --output-dir artifacts/audit`.

## Recent Handoffs

### Workstream validation-gaps-doc-007

- Owner: current chat
- Goal: add confirmed validation gaps to remaining-refactor notes
- Claims: `.github/coordination/current-work.md`, `docs/refactor-remaining.md`
- First validation: markdown-only edit; workspace diagnostics on touched markdown files
- Status: done
- Notes: added a dedicated "Validation gaps to add" section in `docs/refactor-remaining.md` covering operator/type enforcement gaps, :OLD/:NEW assignment semantics, missing CONST/STATE rules, missing SFC execution semantics, and missing library/dependency validation.

### Workstream ai-validation-architecture-006

- Owner: current chat
- Goal: add direct Repo Verify prompt and collapse repeated validation routing into canonical map plus light references
- Claims: `.github/coordination/current-work.md`, `.github/prompts/`, `.github/instructions/`, `.github/agents/`, `.github/skills/validation-routing/`
- First validation: workspace diagnostics on touched customization files
- Status: done
- Notes: added a dedicated `Repo Verify` prompt, promoted `validation-map.md` to canonical first-check command source, and trimmed repeated validation command blocks from prompts, instructions, and specialist agents.

### Workstream ai-prompt-coverage-005

- Owner: current chat
- Goal: add direct slash-command prompts for remaining specialist agents so prompt coverage matches agent coverage
- Claims: `.github/coordination/current-work.md`, `.github/prompts/`, `.github/agents/`
- First validation: workspace diagnostics on new prompt and agent files
- Status: done
- Notes: added `CLI App Change` and `Documentation Generation Change` prompts, then exposed specialist agents as user-invocable so prompt frontmatter resolves cleanly for every specialist route.

### Workstream icf-draft-resolution-001

- Owner: current chat
- Goal: make draft-mode moduletype resolution prefer `.s` definitions over `.x` fallbacks within same library/name bucket
- Claims: `.github/coordination/current-work.md`, `src/sattlint/resolution/common.py`, `tests/test_moduletype_resolution_scoped.py`
- First validation: `& ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_moduletype_resolution_scoped.py`
- Status: done
- Notes: strict resolver now keeps same-library duplicates distinct by origin file, prefers source suffix matching current context, and carries enclosing definition file context while traversing nested `ModuleTypeInstance` paths. Follow-up ICF lookup now reuses that effective context when resolving variables under a moduletype instance, which clears the real `KaHAApplZ3` `Transfer.Dilute.*` failures. Validated with `tests/test_moduletype_resolution_scoped.py`, `tests/test_icf_validation.py`, and real draft-mode `KaHAApplZ3` counts.

### Workstream ai-routing-004

- Owner: current chat
- Goal: add test and fixture scoped instructions plus specialist workflow prompts for common AI repair paths
- Claims: `.github/coordination/current-work.md`, `.github/instructions/`, `.github/prompts/`
- First validation: workspace diagnostics on new instruction and prompt files
- Status: done
- Notes: added targeted test and fixture instruction files plus `Parser Fix`, `Workspace LSP Fix`, and `Repo Audit Change` prompts so common AI work enters the correct specialist flow faster.

### Workstream ai-efficiency-003

- Owner: current chat
- Goal: add subsystem-scoped instructions and lightweight session-start context for AI-only repo workflows
- Claims: `AGENTS.md`, `.github/instructions/`, `.github/hooks/`, `.github/coordination/current-work.md`
- First validation: `& ".venv/Scripts/python.exe" -m py_compile .github/hooks/scripts/session_context.py`
- Status: done
- Notes: added six subsystem-scoped instruction files to reduce context waste and a SessionStart hook that only injects coordination context when active workstreams exist.

### Workstream extend-agents-002

- Owner: current chat
- Goal: add claimed-file hook guard, more specialist agents, and repo-verify merge prompt
- Claims: `AGENTS.md`, `.github/coordination/current-work.md`, `.github/agents/`, `.github/prompts/`, `.github/skills/concurrent-work/SKILL.md`, `.github/hooks/`
- First validation: `& ".venv/Scripts/python.exe" -m py_compile .github/hooks/scripts/claimed_files_guard.py`
- Status: done
- Notes: hook guard now warns on active claims, asks on `ready-for-merge`, and denies on `blocked`; orchestrator can delegate to repo-audit, CLI/app-menu, and docgen specialists; use `Merge Workstreams` before final repo verification when multiple streams converge.

### Workstream bootstrap-agents-001

- Owner: current chat
- Goal: add initial repo-scoped agent, skill, prompt, and coordination scaffold
- Claims: `AGENTS.md`, `.github/agents/`, `.github/prompts/`, `.github/skills/`, `.github/coordination/current-work.md`
- First validation: workspace diagnostics on changed markdown files
- Status: done
- Notes: initial scaffold landed; next chats should create a new active entry instead of editing this handoff unless they are extending agent customization.

## Template

See `.github/skills/concurrent-work/assets/workstream-template.md`.
