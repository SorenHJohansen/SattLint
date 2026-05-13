# Feature Roadmap

Planned GUI capabilities for SattLint. Non-GUI feature work now lives in exec plans instead of this roadmap.

For actual code quality and architecture debt, see `docs/exec-plans/tech-debt-tracker.md`.

Last updated: 2026-05-13

## Quick Reference

| Check | Command |
|-------|---------|
| Parser | `sattlint syntax-check <file>` |
| All tests | `pytest tests/` |
| Quick audit | `sattlint-repo-audit --profile quick --output-dir artifacts/audit` |
| Type check | `mypy src/` |
| Lint | `ruff check src/` |
| Format | `ruff format src/` |

---

## Priority Model

- P1: high value, should be scheduled in the next planning cycle
- P2: valuable but can wait for a later cycle or external demand

## Non-GUI ExecPlan Routing

Non-GUI feature work is now tracked in exec plans instead of this roadmap.

Active non-GUI ExecPlans:

- `docs/exec-plans/completed/28-c-wave-1-semantic-core-follow-ons.md`
- `docs/exec-plans/completed/29-c-wave-2-analyzer-roadmap-follow-ons.md`
- `docs/exec-plans/completed/30-c-wave-backlog-s88-scope-lock.md`
- `docs/exec-plans/completed/31-c-wave-3-dependency-resource-follow-ons.md`
- `docs/exec-plans/completed/32-d-wave-2-devtools-follow-ons.md`
- `docs/exec-plans/active/33-d-wave-backlog-promotion-decision.md`

Completed or already shipped non-GUI coverage:

- `docs/exec-plans/completed/20-d-038-sfc-scan-cycle-simulation.md`
- `docs/exec-plans/completed/21-c-022-state-inference.md`
- `docs/exec-plans/completed/22-d-041-impact-analysis-tool.md`
- `C-021` Safety Path Depth is already live in `src/sattlint/analyzers/safety_paths.py` with focused coverage in `tests/_analyzers_suites_part5.py`, so it no longer belongs in planned feature tracking.

---

## Program E: GUI Explorer

New GUI explorer that does not exist yet.

### E Wave Summary

| Wave | Owner | Target Window | Features | Validation |
| --- | --- | --- | --- | --- |
| E-GUI-M1 | GUI core | 2026-Q3 | E1, E12 | No crash on empty |
| E-GUI-M2 | GUI + Semantic | 2026-Q4 | E3, E4 | Virtualization works |
| E-GUI-M3 | GUI + Analyzer | 2026-Q4 | E2, E9 | Diff renders |
| E-GUI-M4 | GUI + Platform | 2027-Q1 | E5, E10 | Feature flags work |
| E-GUI-M5 | GUI + Platform | 2027-Q2 | E6-E11 | a11y audit pass |
| E-GUI-M6 | GUI + Platform | 2027-Q3 | E13, E14 | Debugger functional |
| E-GUI-M8 | GUI + Platform | 2028-Q1 | E15, E16 | Export/import works |

---

### E-GUI-M1 Explorer Skeleton

**Milestone:** E-GUI-M1

**Status:** Open

**Priority:** P1

**Owner:** GUI core

**Target Window:** 2026-Q3

**Wave:** E-GUI-M1

**Purpose:** CreateExplorer GUI application skeleton with basic infrastructure.

**Implementation Guide:**

| Order | Component | File | Description |
| ------|----------|------|-------------|
| 1 | Electron main | `electron/main.ts` | Application entry |
| 2 | Renderer | `renderer/index.html` | Base HTML |
| 3 | IPC bridge | `electron/ipc.ts` | Main-renderer IPC |
| 4 | Empty state | `renderer/components/` | Empty state UI |

**Validation:** Build and run, no crash on empty workspace.

---

### E-GUI-M2 Real Data Wiring

**Milestone:** E-GUI-M2

**Status:** Open

**Priority:** P1

**Owner:** GUI core + Semantic core

**Target Window:** 2026-Q4

**Wave:** E-GUI-M2

**Purpose:** Wire real SattLine data into explorer.

**Dependencies:** E-GUI-M1

**Implementation Guide:**

| Order | Component | File | Description |
| ------|----------|------|-------------|
| 1 | Workspace loader | Wire `load_workspace_snapshot()` | Load data |
| 2 | File tree | `renderer/components/FileTree.tsx` | Virtualized file list |
| 3 | Issue list | `renderer/components/IssueList.tsx` | Virtualized issues |
| 4 | Editor | `renderer/components/Editor.tsx` | Code display |

**Validation:** Load real workspace, verify virtualization renders.

---

### E-GUI-M3 Draft vs Official Diff

**Milestone:** E-GUI-M3

**Status:** Open

**Priority:** P1

**Owner:** GUI core + Analyzer

**Target Window:** 2026-Q4

**Wave:** E-GUI-M3

**Purpose:** Render diff between draft and official code.

**Dependencies:** E-GUI-M2

**Implementation Guide:**

| Order | Component | File | Description |
| ------|----------|------|-------------|
| 1 | Diff engine | Wire `analyzers/diff.py` | Compute diff |
| 2 | Diff view | `renderer/components/Diff.tsx` | Render diff |
| 3 | Error surface | `renderer/components/Errors.tsx` | Show errors |

**Validation:** Diff renders correctly.

---

### E-GUI-M4 Resilience and UX Polish

**Milestone:** E-GUI-M4

**Status:** Open

**Priority:** P1

**Owner:** GUI core + Platform

**Target Window:** 2027-Q1

**Wave:** E-GUI-M4

**Purpose:** Feature flags, batch operations, command palette.

**Dependencies:** E-GUI-M3

**Implementation Guide:**

| Order | Component | File | Description |
| ------|----------|------|-------------|
| 1 | Feature flags | `renderer/features/` | Toggle features |
| 2 | Batch ops | `renderer/components/BatchOps.tsx` | Multi-select |
| 3 | Command palette | `renderer/components/CommandPalette.tsx` | Commands |

**Validation:** Feature flags work, batch ops verified.

---

### E-GUI-M5 Accessibility

**Milestone:** E-GUI-M5

**Status:** Open

**Priority:** P1

**Owner:** GUI core + Platform

**Target Window:** 2027-Q2

**Wave:** E-GUI-M5

**Purpose:** i18n, accessibility, security hardening.

**Dependencies:** E-GUI-M4

**Implementation Guide:**

| Order | Component | File | Description |
| ------|----------|------|-------------|
| 1 | i18n | `renderer/i18n/` | Externalize strings |
| 2 | a11y | `renderer/a11y/` | Screen reader |
| 3 | Security | `renderer/security/` | Hardening |
| 4 | Sync | `renderer/sync/` | Cloud sync |

**Validation:** a11y audit pass, i18n externalized.

---

### E-GUI-M6 Interactive Debugger

**Milestone:** E-GUI-M6

**Status:** Open

**Priority:** P1

**Owner:** GUI core + Platform

**Target Window:** 2027-Q3

**Wave:** E-GUI-M6

**Purpose:** Add debugging capabilities to the GUI explorer with breakpoints, step-through execution, and variable inspection.

**Dependencies:** E-GUI-M5

**Implementation Guide:**

| Order | Component | File | Description |
| ------|----------|------|-------------|
| 1 | Debugger controller | `electron/debugger.ts` | Control debugging session |
| 2 | Breakpoint manager | `renderer/components/BreakpointManager.tsx` | Manage breakpoints |
| 3 | Step controls | `renderer/components/StepControls.tsx` | Step-through execution |
| 4 | Variable inspector | `renderer/components/VariableInspector.tsx` | Inspect variables |
| 5 | Call stack view | `renderer/components/CallStackView.tsx` | Display call stack |

**Validation:** Debugger launches and can set breakpoints, step through code, and inspect variables.

---

### E-GUI-M8 Export/Import Capabilities

**Milestone:** E-GUI-M8

**Status:** Open

**Priority:** P1

**Owner:** GUI core + Platform

**Target Window:** 2028-Q1

**Wave:** E-GUI-M8

**Purpose:** Allow exporting analysis results in various formats and importing configurations.

**Dependencies:** E-GUI-M6

**Implementation Guide:**

| Order | Component | File | Description |
| ------|----------|------|-------------|
| 1 | Export manager | `electron/export_manager.py` | Handle export operations |
| 2 | Import manager | `electron/import_manager.py` | Handle import operations |
| 3 | Format handlers | `renderer/components/FormatHandlers.tsx` | Support various formats |
| 4 | Export dialog | `renderer/components/ExportDialog.tsx` | Configure export options |
| 5 | Import dialog | `renderer/components/ImportDialog.tsx` | Configure import options |

**Validation:** Can export analysis results to JSON, CSV, HTML and import configurations successfully.

---

## Feature Implementation Template

Use this template when adding new features.

### Feature ID

**Feature ID:** F-XXX

**Status:** Open

**Priority:** P1 or P2

**Owner:** Owner team

**Target Window:** Quarter or "Backlog"

**Wave:** Program wave

**Purpose:** One-paragraph description.

**Implementation Guide:**

| Order | Component | File | Description |
| ------|----------|------|-------------|
| 1 | Component A | `path/to/file.py` | What it does |

**Input:** Input format/description

**Output:** Output format/description

**Reuses:**

- Existing component (path)

**Validation:** Command to validate

**See also:** Related features

---

## Common Reusable Components

| Component | Path | Purpose |
|-----------|------|---------|
| Workspace snapshot | `core/semantic.py:load_workspace_snapshot()` | Load workspace |
| Parser | `engine.py:parse_source_file()` | Parse file |
| Expression evaluator | `analyzers/dataflow.py:_evaluate_expression()` | Evaluate |
| Module resolver | `resolution/common.py:resolve_*()` | Resolve refs |
| AST models | `sattline_parser/models/ast_model.py` | Data structures |
| Grammar | `sattline_parser/grammar/sattline.lark` | Parser grammar |
