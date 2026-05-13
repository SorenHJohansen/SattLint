# Tech Debt Tracker

Living document of known technical debt in SattLint.
Updated by doc-gardening agent and human developers.
Last updated: 2026-05-13

Active work now lives in:

- `docs/exec-plans/active/`

Completed debt closeouts live in:

- `docs/exec-plans/completed/`

This tracker remains valid for legacy TD-* entries, still-open tech debt, and scan history.

## Consolidation Source Ledger

| Source | State | Snapshot | Sync Basis | Coverage | Notes |
|---|---|---|---|---|---|
| TODO_GUI.md | retired | 2026-05-01 | retired | Program E | Legacy GUI backlog retired into roadmap and exec-plan tracking. |
| TODO_REFACTOR.md | retired | 2026-05-01 | retired | Program T | Legacy refactor backlog retired into the consolidated tech-debt tracker and exec-plan tracking. |
| TODO_SATTLINT.md | retired | 2026-05-01 | retired | Program C | Legacy SattLint backlog retired into roadmap and exec-plan tracking. |
| TODO_TOOLS.md | retired | 2026-05-01 | retired | Program D | Legacy tools backlog retired into the consolidated tech-debt tracker and exec-plan tracking. |

## Program T: Technical Debt Items

### Legacy TD Summary

| ID | Area | Description | Severity | Planned Fix |
|----|------|-------------|----------|-------------|
| TD-003 | LSP | No hot-reload when `WORKFLOW.md`-equivalent changes | Low | Add watch + restart mechanism |
| TD-005 | Config | No validation that `analyzed_programs_and_libraries` paths exist | Low | Add startup validation |
| TD-006 | DevTools | Pipeline outputs not yet consumed by doc-gardening agent | Low | Wire artifacts ? quality-score.md |
| TD-008 | Types | Semantic type names needed for discoverability (VariableId, ProjectPath) | Low | Add semantic type aliases |

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

## Scan Log

| Date | Findings | Action Taken |
|------|-----------|--------------|
| 2026-05-06 | 0 findings | Doc-gardening scan |
| 2026-05-04 | 264 findings | Doc-gardening scan |
| 2026-05-01 | 0 findings | Doc-gardening scan |
| 2026-04-30 | 15 items | Manual tech debt review and update to exec-plan template |
| 2026-04-29 | 1 findings | Doc-gardening scan |
| 2026-04-29 | 1 findings | Doc-gardening scan |
| 2026-04-28 | 0 findings | Doc-gardening scan |
| 2026-04-28 | 1 findings | Doc-gardening scan |
| 2026-04-28 | 0 findings | Doc-gardening scan |
| 2026-04-28 | AGENTS.md 172?100 lines, docs/ restructuring | Initial restructure |
| (next scan due: weekly via CI) | | |

## Debt Categories

- **Critical**: Blocks features, causes data loss, security issue
- **High**: Affects reliability, performance, or user experience
- **Medium**: Code smell, missing feature, incomplete coverage
- **Low**: Nice-to-have, cosmetic, future-proofing
