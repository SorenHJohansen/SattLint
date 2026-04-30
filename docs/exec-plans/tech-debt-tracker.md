# Tech Debt Tracker

Living document of known technical debt in SattLint.
Updated by doc-gardening agent and human developers.
Last updated: 2026-04-30

Canonical consolidated register for active debt:
- `docs/exec-plans/tech-debt-ai-first.md`

This tracker remains valid for legacy TD-* entries and scan history.

## Program T: Technical Debt Items

### T-001 Analyzer Remediation Instructions

**Tech Debt ID:** T-001

**Status:** Open

**Priority:** P1

**Owner:** Analyzer team

**Target Window:** 2026-Q2

**Wave:** T-Wave-1

**Purpose:** Embed remediation instructions directly in error messages for better developer experience.

**Implementation Guide:**

| Order | Component | File | Description |
|-------|-----------|------|-------------|
| 1 | Error formatter | `src/sattlint/analyzers/base.py` | Add remediation field to error structures |
| 2 | Message template | `src/sattlint/analyzers/issue_analyzer.py` | Update Issue analyzer with fix suggestions |
| 3 | Message template | `src/sattlint/analyzers/variable_analyzer.py` | Update Variable analyzer with fix suggestions |
| 4 | Message template | `src/sattlint/analyzers/shadowing_analyzer.py` | Update Shadowing analyzer with fix suggestions |

**Input:** Validation errors from analyzers

**Output:** Enhanced error messages with actionable remediation steps

**Validation:** Manual verification of error messages contain remediation guidance

**Reuses:** Existing analyzer infrastructure

---

### T-003 LSP Hot Reload

**Tech Debt ID:** T-003

**Status:** Open

**Priority:** P2

**Owner:** LSP team

**Target Window:** 2026-Q3

**Wave:** T-Wave-2

**Purpose:** Implement hot-reload capability when WORKFLOW.md-equivalent files change to avoid manual LSP restarts.

**Implementation Guide:**

| Order | Component | File | Description |
|-------|-----------|------|-------------|
| 1 | File watcher | `src/sattlint_lsp/workspace_store.py` | Add watch for config file changes |
| 2 | Restart trigger | `src/sattlint_lsp/server.py` | Trigger LSP restart on config changes |
| 3 | Debounce logic | `src/sattlint_lsp/server.py` | Prevent excessive restarts |

**Input:** File system events for WORKFLOW.md changes

**Output:** Automatic LSP server restart when needed

**Validation:** Verify LSP restarts automatically when config files change

**Reuses:** Existing file watching infrastructure

---

### T-005 Config Path Validation

**Tech Debt ID:** T-005

**Status:** Open

**Priority:** P2

**Owner:** Config team

**Target Window:** 2026-Q2

**Wave:** T-Wave-1

**Purpose:** Add startup validation to ensure `analyzed_programs_and_libraries` paths exist before analysis begins.

**Implementation Guide:**

| Order | Component | File | Description |
|-------|-----------|------|-------------|
| 1 | Path validator | `src/sattlint/config.py` | Add validation for program/library paths |
| 2 | Error reporter | `src/sattlint/config.py` | Report missing paths with clear messages |
| 3 | Startup hook | `src/sattlint/app.py` | Call validation during app initialization |

**Input:** Configuration paths from config.toml

**Output:** Validation errors for missing paths or successful validation

**Validation:** Verify startup fails gracefully with clear messages when paths don't exist

**Reuses:** Existing config loading infrastructure

---

### T-006 DevTools Pipeline Output Consumption

**Tech Debt ID:** T-006

**Status:** Open

**Priority:** P2

**Owner:** DevTools team

**Target Window:** 2026-Q2

**Wave:** T-Wave-1

**Purpose:** Wire pipeline outputs to be consumed by doc-gardening agent for automatic quality score updates.

**Implementation Guide:**

| Order | Component | File | Description |
|-------|-----------|------|-------------|
| 1 | Output parser | `src/sattlint/devtools/doc_gardener.py` | Parse pipeline JSON outputs |
| 2 | Quality updater | `src/sattlint/devtools/doc_gardener.py` | Update quality-score.md with pipeline results |
| 3 | Automation hook | `src/sattlint/devtools/doc_gardener.py` | Trigger on pipeline completion |

**Input:** Pipeline output JSON files

**Output:** Updated quality-score.md file

**Validation:** Verify quality scores reflect latest pipeline results

**Reuses:** Existing doc-gardening agent infrastructure

---

### T-007 Validation Function Refactor

**Tech Debt ID:** T-007

**Status:** Open

**Priority:** P1

**Owner:** Validation team

**Target Window:** 2026-Q2

**Wave:** T-Wave-1

**Purpose:** Refactor validation.py functions to return parsed typed objects instead of booleans for better type safety and reuse.

**Implementation Guide:**

| Order | Component | File | Description |
|-------|-----------|------|-------------|
| 1 | Function signature update | `src/sattlint/validation.py` | Change _is_valid_* functions to return Option[TypedObject] |
| 2 | Caller updates | `src/sattlint/validation.py` | Update all callers to handle new return types |
| 3 | Type safety improvement | `src/sattlint/validation.py` | Leverage returned types in downstream logic |

**Input:** AST nodes to validate

**Output:** Typed validation results (or None) instead of boolean

**Validation:** Ensure all validation logic continues to work correctly with new return types

**Reuses:** Existing validation logic

---

### T-008 Semantic Type Aliases

**Tech Debt ID:** T-008

**Status:** Open

**Priority:** P2

**Owner:** Types team

**Target Window:** 2026-Q2

**Wave:** T-Wave-1

**Purpose:** Add semantic type aliases (VariableId, ProjectPath, etc.) for improved code discoverability and self-documentation.

**Implementation Guide:**

| Order | Component | File | Description |
|-------|-----------|------|-------------|
| 1 | Type definitions | `src/sattlint/types.py` | Create NewType aliases for common concepts |
| 2 | Usage migration | `src/sattlint/**/*.py` | Replace primitive types with semantic aliases where appropriate |
| 3 | Documentation | `src/sattlint/types.py` | Add docstrings explaining each alias purpose |

**Input:** N/A (refactoring)

**Output:** Codebase with improved type clarity

**Validation:** Type checking passes with mypy; functionality unchanged

**Reuses:** Existing type system

---

### T-009 LSP Import and Typing Cleanup

**Tech Debt ID:** T-009

**Status:** Open

**Priority:** P1

**Owner:** LSP team

**Target Window:** 2026-Q2

**Wave:** T-Wave-2

**Purpose:** Clear blocking LSP findings including dead imports, missing threading usage, and optional member access issues.

**Implementation Guide:**

| Order | Component | File | Description |
|-------|-----------|------|-------------|
| 1 | Import cleanup | `src/sattlint_lsp/server.py` | Remove dead imports |
| 2 | Threading fix | `src/sattlint_lsp/_server_document.py` | Restore or replace missing threading usage |
| 3 | Optional access guard | `src/sattlint_lsp/_server_document.py` | Guard the optional `.start` access that pyright flagged |

**Input:** LSP source files

**Output:** Clean LSP code with no blocking findings

**Validation:** `pytest --no-cov tests/test_lsp_document.py tests/test_lsp_diagnostics.py tests/test_editor_api.py -x -q --tb=short`

**Reuses:** Existing LSP infrastructure

---

### T-010 App Surface Logging Migration

**Tech Debt ID:** T-010

**Status:** Open

**Priority:** P1

**Owner:** App team

**Target Window:** 2026-Q2

**Wave:** T-Wave-3

**Purpose:** Replace library-layer `print()` calls with structured console or return-value based reporting while keeping the public app facade stable.

**Implementation Guide:**

| Order | Component | File | Description |
|-------|-----------|------|-------------|
| 1 | Print replacement | `src/sattlint/app_analysis.py` | Replace print() with structured reporting |
| 2 | Print replacement | `src/sattlint/app_cli_commands.py` | Replace print() with structured reporting |
| 3 | Pattern normalization | `src/sattlint/app_*.py` | Normalize remaining app_* modules to same output contract |

**Input:** App function calls that currently print

**Output:** Structured logging or return values instead of stdout prints

**Validation:** `pytest --no-cov tests/test_app.py tests/test_app_analysis.py tests/test_app_menus.py tests/test_cli.py -x -q --tb=short`

**Reuses:** Existing console/reporting infrastructure

---

### T-011 CLI/Console/GUI Output Cleanup

**Tech Debt ID:** T-011

**Status:** Open

**Priority:** P1

**Owner:** CLI team

**Target Window:** 2026-Q2

**Wave:** T-Wave-3

**Purpose:** Make output routing consistent outside the app-owner modules without overlapping T-010.

**Implementation Guide:**

| Order | Component | File | Description |
|-------|-----------|------|-------------|
| 1 | Output boundary decision | `src/sattlint/cli/entry.py`, `src/sattlint/console.py`, `src/sattlint_gui/binding.py` | Define one output boundary for CLI and GUI paths |
| 2 | Print migration | `src/sattlint/cli/entry.py`, `src/sattlint/console.py`, `src/sattlint_gui/binding.py` | Migrate print() uses to the defined boundary |
| 3 | Behavior preservation | `src/sattlint/cli/entry.py`, `src/sattlint/console.py`, `src/sattlint_gui/binding.py` | Keep interactive behavior unchanged |

**Input:** Print statements in CLI, console, and GUI binding code

**Output:** Consistent output routing through defined boundary

**Validation:** `pytest --no-cov tests/test_cli.py tests/test_gui.py tests/test_app.py tests/test_app_menus.py -x -q --tb=short`

**Reuses:** Existing output infrastructure

---

### T-012 Parser Structural Split: SLTransformer

**Tech Debt ID:** T-012

**Status:** Open

**Priority:** P1

**Owner:** Parser team

**Target Window:** 2026-Q2

**Wave:** T-Wave-4

**Purpose:** Split SLTransformer by responsibility without changing parser behavior (currently defines 133 methods).

**Implementation Guide:**

| Order | Component | File | Description |
|-------|-----------|------|-------------|
| 1 | Mixin extraction | `src/sattline_parser/transformer/` | Extract transformer mixins by domain (token coercion, expressions, SFC nodes, module structure, graphics/interact construction) |
| 2 | Class simplification | `src/sattline_parser/transformer/sl_transformer.py` | Reduce SLTransformer to use mixins |
| 3 | Interface preservation | `src/sattline_parser/transformer/sl_transformer.py` | Maintain existing public interface |

**Input:** SLTransformer class

**Output:** Modular transformer structure with same functionality

**Validation:**
- `sattlint syntax-check tests/fixtures/corpus/valid/VariableModifiers.s`
- `pytest --no-cov tests/test_transformer.py tests/test_parser_core.py -x -q --tb=short`

**Reuses:** Existing parser infrastructure

---

### T-013 Analyzer Structural Split: variables.py

**Tech Debt ID:** T-013

**Status:** Open

**Priority:** P1

**Owner:** Analyzer team

**Target Window:** 2026-Q2

**Wave:** T-Wave-4

**Purpose:** Split variables.py by responsibility before it grows further (currently 2303 lines).

**Implementation Guide:**

| Order | Component | File | Description |
|-------|-----------|------|-------------|
| 1 | Effect flow extraction | `src/sattlint/analyzers/_variables_effect_flow.py` | Create EffectFlowTracker class with 13 effect-flow and mapping-propagation methods |
| 2 | Analyzer update | `src/sattlint/analyzers/variables.py` | Update VariablesAnalyzer to delegate to tracker |
| 3 | Line reduction | `src/sattlint/analyzers/variables.py` | Reduce from ~2011 lines to ~1729 lines (282 line reduction, 14% shrink) |

**Input:** variables.py analyzer file

**Output:** Modular analyzer structure with same functionality

**Validation:** `pytest --no-cov tests/test_analyzers_variables.py -x -q --tb=short`

**Blocker:** Waiting on T-012 (parser structural split) to restore missing v_args import

**Reuses:** Existing analyzer infrastructure

---

### T-014 Test Low-Severity Style Sweep

**Tech Debt ID:** T-014

**Status:** Open

**Priority:** P2

**Owner:** QA team

**Target Window:** 2026-Q2

**Wave:** T-Wave-5

**Purpose:** Clear remaining formatting and small-expression noise in test files once blocking lanes stop moving the same files.

**Implementation Guide:**

| Order | Component | File | Description |
|-------|-----------|------|-------------|
| 1 | Style fixes | `src/sattlint/__init__.py`, `src/sattlint/casefolding.py`, `src/sattlint/engine.py` | Fix ruf-ruf005, ruf-c416, ruf-w292, and ruf-i001 |
| 2 | Import sorting | Various test files | Apply consistent import sorting |
| 3 | Whitespace normalization | Various test files | Fix trailing newlines and whitespace issues |

**Input:** Test files with style issues

**Output:** Clean test files with no style violations

**Validation:** `ruff check src/sattlint/engine.py src/sattlint/casefolding.py src/sattlint/__init__.py` (pass)

**Reuses:** Existing linting infrastructure

---

### T-015 CLI Documentation Parity

**Tech Debt ID:** T-015

**Status:** Open

**Priority:** P2

**Owner:** Docs team

**Target Window:** 2026-Q2

**Wave:** T-Wave-5

**Purpose:** Document missing script entry points so the consistency artifact is not hiding silent documentation drift.

**Implementation Guide:**

| Order | Component | File | Description |
|-------|-----------|------|-------------|
| 1 | Doc discovery | docs/ | Find canonical CLI docs surface |
| 2 | Missing docs | docs/ | Add documentation for sattlint, sattlint-corpus-runner, and sattlint-lsp scripts |
| 3 | Subcommand preservation | docs/ | Leave subcommand docs unchanged as they already pass |

**Input:** CLI consistency report showing undocumented scripts

**Output:** Complete CLI documentation for all scripts

**Validation:** Markdown consistency review plus regeneration of artifacts/audit/cli_consistency.json

**Reuses:** Existing documentation infrastructure

### T-022 Failing Pytest Recovery

**Tech Debt ID:** T-022

**Status:** Open

**Priority:** P1

**Owner:** QA team

**Target Window:** 2026-Q2

**Wave:** T-Wave-5

**Purpose:** Fix 22 failing tests to restore full test suite reliability.

**Implementation Guide:**

| Order | Component | File | Description |
|-------|-----------|------|-------------|
| 1 | Test analysis | `tests/` | Categorize 22 failures by root cause (pre-existing bugs, missing features, infrastructure) |
| 2 | Fix tracker tests | `tests/test_analyzers_variables.py` | Fix layout_overlap_detects_overlapping_module_invocations |
| 3 | Fix editor_api tests | `tests/test_editor_api.py` | Fix 8 workspace snapshot tests |
| 4 | Fix LSP tests | `tests/test_lsp_diagnostics.py` | Fix 2 completion/semantic tests |
| 5 | Fix parser tests | `tests/test_parser_core.py`, `tests/test_parser_validation.py` | Fix 7 parser validation tests |
| 6 | Fix phase0 tests | `tests/test_phase0_guardrails.py` | Fix 2 parameter drift tests |

**Input:** 22 failing tests from pytest run

**Output:** Passing test suite

**Validation:** `pytest --tb=short -q` shows 0 failures

**Reuses:** Existing test infrastructure

---

### T-023 Weak SHA1 Hash Usage

**Tech Debt ID:** T-023

**Status:** Open

**Priority:** P2

**Owner:** Security team

**Target Window:** 2026-Q2

**Wave:** T-Wave-3

**Purpose:** Replace weak SHA1 hash with secure alternative in doc_gardener.py.

**Implementation Guide:**

| Order | Component | File | Description |
|-------|-----------|------|-------------|
| 1 | Hash upgrade | `src/sattlint/devtools/doc_gardener.py` | Replace SHA1 with SHA256 or use `usedforsecurity=False` if hash is not security-critical |

**Input:** bandit-b324 finding at line 181

**Output:** Secure hash usage or explicit non-security intent

**Validation:** `bandit -r src/sattlint/devtools/doc_gardener.py` passes with no high findings

**Reuses:** Existing security tooling

---

### T-024 Test App Structural Split

**Tech Debt ID:** T-024

**Status:** Open

**Priority:** P1

**Owner:** Test team

**Target Window:** 2026-Q2

**Wave:** T-Wave-4

**Purpose:** Split test_app.py (2127 lines) by owning surface to improve maintainability.

**Implementation Guide:**

| Order | Component | File | Description |
|-------|-----------|------|-------------|
| 1 | Module analysis | `tests/test_app.py` | Identify natural split points by feature area |
| 2 | Extract helpers | `tests/test_app_helpers.py` | Extract shared test helpers and fixtures |
| 3 | Split by surface | `tests/test_app_*.py` | Create focused modules for each app surface |

**Input:** test_app.py at 2127 lines

**Output:** Multiple focused test modules under 500 lines each

**Validation:** `pytest tests/test_app*.py -x -q --tb=short` all pass

**Reuses:** Pattern from W8 (pipeline test split)

---

### T-025 MMS Interface Variables Function Decomposition

**Tech Debt ID:** T-025

**Status:** Open

**Priority:** P2

**Owner:** Analyzer team

**Target Window:** 2026-Q3

**Wave:** T-Wave-4

**Purpose:** Decompose `analyze_mms_interface_variables` (383 lines) in mms.py for readability.

**Implementation Guide:**

| Order | Component | File | Description |
|-------|-----------|------|-------------|
| 1 | Function analysis | `src/sattlint/analyzers/mms.py` | Identify extractable sub-routines in the 383-line function |
| 2 | Extract helpers | `src/sattlint/analyzers/mms.py` | Extract validation, mapping, and reporting sub-functions |
| 3 | Verify behavior | `tests/test_analyzers_*.py` | Ensure extracted functions preserve original behavior |

**Input:** `analyze_mms_interface_variables` spans 383 lines

**Output:** Function decomposed into sub-100-line helpers

**Validation:** `pytest --no-cov tests/test_analyzers_*.py -x -q --tb=short`

**Reuses:** Existing analyzer patterns

---

### T-026 Parser Logging Improvements

**Tech Debt ID:** T-026

**Status:** Open

**Priority:** P2

**Owner:** Parser team

**Target Window:** 2026-Q3

**Wave:** T-Wave-5

**Purpose:** Add structured logging to parser failure paths for better diagnostics.

**Implementation Guide:**

| Order | Component | File | Description |
|-------|-----------|------|-------------|
| 1 | API logging | `src/sattline_parser/api.py` | Add logging to failure paths |
| 2 | Model logging | `src/sattline_parser/models/ast_model.py` | Add logging to exception paths |
| 3 | Transformer logging | `src/sattline_parser/transformer/*.py` | Add logging to mixin failure paths |

**Input:** 12 `failure-path-no-diagnostic` and `missing-logging` findings

**Output:** Structured logging on all parser failure paths

**Validation:** `ruff check src/sattline_parser/` passes; review logs during parse failures

**Reuses:** Existing logging patterns in sattlint/

---

### T-027 Hardcoded Paths in Test Files

**Tech Debt ID:** T-027

**Status:** Open

**Priority:** P2

**Owner:** Test team

**Target Window:** 2026-Q2

**Wave:** T-Wave-5

**Purpose:** Replace hardcoded Windows paths in test_comment_code.py with portable alternatives.

**Implementation Guide:**

| Order | Component | File | Description |
|-------|-----------|------|-------------|
| 1 | Path cleanup | `tests/test_comment_code.py` | Replace hardcoded C:\ paths with repo-relative or temp paths |
| 2 | Pattern check | `tests/` | Search for remaining hardcoded paths in test files |

**Input:** 3 hardcoded-windows-path findings in test_comment_code.py (lines 458, 475, 479)

**Output:** Portable test code with no hardcoded paths

**Validation:** Repo audit shows no portability findings in tests/

**Reuses:** Pattern from W5 (Repo Metadata Portability Cleanup)

---

### T-016 sattline_builtins.py Monolithic Refactor

**Tech Debt ID:** T-016

**Status:** Open

**Priority:** P2

**Owner:** Analyzer team

**Target Window:** 2026-Q3

**Wave:** T-Wave-4

**Purpose:** Split 2095-line builtins file into data file (JSON/TOML) plus loader, or split by functional area for maintainability.

**Implementation Guide:**

| Order | Component | File | Description |
|-------|-----------|------|-------------|
| 1 | Data extraction | `src/sattlint/analyzers/sattline_builtins.py` | Extract builtin function definitions to `data/builtins.json` or `data/builtins.toml` |
| 2 | Loader creation | `src/sattlint/analyzers/builtins_loader.py` | Create loader that reads data file and constructs `BuiltinFunction` dataclasses |
| 3 | Validation test | `tests/test_builtins.py` | Add test to validate builtin definitions (parameter counts, types) |

**Input:** Builtin function definitions

**Output:** Modular builtins with data separated from code

**Validation:** `pytest --no-cov tests/test_builtins.py -x -q --tb=short`

**Reuses:** Existing `BuiltinFunction` and `Parameter` dataclasses

---

### T-017 Analyzer Test Coverage Gaps

**Tech Debt ID:** T-017

**Status:** Open

**Priority:** P1

**Owner:** QA team

**Target Window:** 2026-Q2

**Wave:** T-Wave-5

**Purpose:** Add dedicated tests for 38 analyzer modules lacking coverage, focusing on high-severity analyzers first.

**Implementation Guide:**

| Order | Component | File | Description |
|-------|-----------|------|-------------|
| 1 | High-severity analyzers | `tests/test_analyzers_dataflow.py`, `tests/test_analyzers_naming.py`, `tests/test_analyzers_sfc.py` | Create test files for critical analyzers |
| 2 | Medium-severity analyzers | `tests/test_analyzers_modules.py`, `tests/test_analyzers_mms.py`, `tests/test_analyzers_icf.py` | Expand coverage to medium-severity analyzers |
| 3 | Remaining analyzers | `tests/test_analyzers_*.py` | Cover remaining 38 analyzers (alarm_integrity, initial_values, parameter_drift, safety_paths, shadowing, spec_compliance, taint_paths, unsafe_defaults, etc.) |

**Input:** 38 analyzer modules without dedicated tests

**Output:** Dedicated test files for each analyzer

**Validation:** `pytest --no-cov tests/test_analyzers_*.py -x -q --tb=short`

**Reuses:** Existing test fixtures in `tests/fixtures/`

---

### T-018 Variable Module Duplication Cleanup

**Tech Debt ID:** T-018

**Priority:** P2

**Status:** Open

**Owner:** Analyzer team

**Target Window:** 2026-Q3

**Wave:** T-Wave-4

**Purpose:** Eliminate duplicated const candidate logic between `variables.py` and `variable_issue_collection.py`; clarify responsibility boundaries with `variable_traversal.py`.

**Implementation Guide:**

| Order | Component | File | Description |
|-------|-----------|------|-------------|
| 1 | Extract shared logic | `src/sattlint/analyzers/variable_utils.py` | Extract shared const candidate logic to common utility |
| 2 | Update callers | `src/sattlint/analyzers/variables.py`, `src/sattlint/analyzers/variable_issue_collection.py` | Replace duplicated logic with shared utility calls |
| 3 | Clarify boundaries | `src/sattlint/analyzers/variable_traversal.py` | Ensure traversal is pure; variables.py consumes it |

**Input:** Duplicated code across variable modules

**Output:** DRY variable analysis code

**Validation:** `pytest --no-cov tests/test_analyzers_variables.py -x -q --tb=short`

**Reuses:** Existing variable analysis infrastructure

---

### T-019 repo_audit.py Structural Split

**Tech Debt ID:** T-019

**Status:** Open

**Priority:** P2

**Owner:** DevTools team

**Target Window:** 2026-Q3

**Wave:** T-Wave-4

**Purpose:** Split 1787-line repo_audit.py into focused modules: `audit_core.py`, `ledger.py`, `leak_detection.py`.

**Implementation Guide:**

| Order | Component | File | Description |
|-------|-----------|------|-------------|
| 1 | Core extraction | `src/sattlint/devtools/audit_core.py` | Extract main audit orchestration logic |
| 2 | Ledger extraction | `src/sattlint/devtools/ledger.py` | Extract ledger validation logic |
| 3 | Leak detection | `src/sattlint/devtools/leak_detection.py` | Extract leak detection logic |
| 4 | Integration | `src/sattlint/devtools/repo_audit.py` | Update to use extracted modules; reduce to <500 lines |

**Input:** repo_audit.py (1787 lines)

**Output:** Modular devtools with separated concerns

**Validation:** `pytest --no-cov tests/test_repo_audit.py -x -q --tb=short`

**Reuses:** Existing devtools infrastructure

---

### T-020 core/semantic.py Structural Split

**Tech Debt ID:** T-020

**Status:** Open

**Priority:** P2

**Owner:** Core team

**Target Window:** 2026-Q3

**Wave:** T-Wave-4

**Purpose:** Split 1729-line semantic.py into `SymbolTable`, `CompletionProvider`, `ReferenceResolver` modules.

**Implementation Guide:**

| Order | Component | File | Description |
|-------|-----------|------|-------------|
| 1 | SymbolTable extraction | `src/sattlint/core/symbol_table.py` | Extract symbol table logic |
| 2 | CompletionProvider extraction | `src/sattlint/core/completion_provider.py` | Extract completion logic |
| 3 | ReferenceResolver extraction | `src/sattlint/core/reference_resolver.py` | Extract reference resolution logic |
| 4 | Integration | `src/sattlint/core/semantic.py` | Update to use extracted modules |

**Input:** semantic.py (1729 lines)

**Output:** Modular semantic analysis with separated concerns

**Validation:** `pytest --no-cov tests/test_editor_api.py -x -q --tb=short`

**Reuses:** Existing core infrastructure

---

## Scan Log

| Date | Findings | Action Taken |
|------|-----------|--------------|
| 2026-04-30 | 15 items | Manual tech debt review and update to exec-plan template |
| 2026-04-29 | 1 findings | Doc-gardening scan |
| 2026-04-29 | 1 findings | Doc-gardening scan |
| 2026-04-28 | 0 findings | Doc-gardening scan |
| 2026-04-28 | 1 findings | Doc-gardening scan |
| 2026-04-28 | 0 findings | Doc-gardening scan |
| 2026-04-28 | AGENTS.md 172→100 lines, docs/ restructuring | Initial restructure |
| (next scan due: weekly via CI) | | |

## Debt Categories

- **Critical**: Blocks features, causes data loss, security issue
- **High**: Affects reliability, performance, or user experience
- **Medium**: Code smell, missing feature, incomplete coverage
- **Low**: Nice-to-have, cosmetic, future-proofing
