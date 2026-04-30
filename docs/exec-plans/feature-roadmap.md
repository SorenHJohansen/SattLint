# Feature Roadmap

Planned new capabilities for SattLint. These are features that do not exist yet, not debt in existing code.

For actual code quality and architecture debt, see `docs/exec-plans/tech-debt-tracker.md`.

Last updated: 2026-04-29

## Priority Model

- P1: high value, should be scheduled in the next planning cycle
- P2: valuable but can wait for a later cycle or external demand

## Program C: New Analyzer Capabilities

New analysis passes that do not yet exist in the engine.

### C Wave Summary

| Wave | Owner | Target Window | Items | Validation Route |
| --- | --- | --- | --- | --- |
| C-Wave-1: Semantic correctness | Semantic core | 2026-Q3 | C-010, C-011, C-012, C-016, C-022 | `sattlint syntax-check` + focused `pytest tests/` for each analyzer |
| C-Wave-2: New analysis passes | Analyzer roadmap | 2026-Q3 | C-003, C-013, C-014, C-015, C-017, C-018 | `sattlint syntax-check` + `pytest tests/` for added analyzer |
| C-Wave-3: Safety path depth | Semantic core | 2026-Q4 | C-021 | `pytest tests/` safety-path fixtures |
| C-Wave-Backlog: Domain-specific | Domain integration | Backlog | C-007, C-019, C-020 | Deferred until S88 domain scope confirmed |

### C Item Backlog

| ID | Priority | Owner | Target Window | Wave | Feature | Status |
| --- | --- | --- | --- | --- | --- | --- |
| C-003 | P1 | Analyzer roadmap | 2026-Q3 | C-Wave-2 | Duplicate logic detection | Open |
| C-007 | P2 | Analyzer roadmap | Backlog | C-Wave-Backlog | Engineering unit consistency and propagation | Open |
| C-010 | P1 | Semantic core | 2026-Q3 | C-Wave-1 | Timing and determinism analysis | Partial |
| C-011 | P1 | Semantic core | 2026-Q3 | C-Wave-1 | Power-up and restart correctness | Partial |
| C-012 | P1 | Semantic core | 2026-Q3 | C-Wave-1 | Scan-level concurrency and arbitration analysis | Partial |
| C-013 | P1 | Analyzer roadmap | 2026-Q3 | C-Wave-2 | Signal lifecycle modeling | Open |
| C-014 | P1 | Analyzer roadmap | 2026-Q3 | C-Wave-2 | Control loop and stability heuristics | Open |
| C-015 | P1 | Analyzer roadmap | 2026-Q3 | C-Wave-2 | Fault handling completeness and recovery | Open |
| C-016 | P1 | Variables analyzer | 2026-Q3 | C-Wave-1 | Strong semantic interface contracts | Partial |
| C-017 | P1 | Analyzer roadmap | 2026-Q3 | C-Wave-2 | Numeric and engineering constraint analysis | Open |
| C-018 | P1 | Analyzer + config | 2026-Q3 | C-Wave-2 | Configuration drift against code and recipes | Open |
| C-019 | P2 | Domain integration | Backlog | C-Wave-Backlog | S88 control module contract analysis | Open |
| C-020 | P2 | Domain integration | Backlog | C-Wave-Backlog | S88 phase sequencing correctness | Open |
| C-021 | P1 | Semantic core | 2026-Q4 | C-Wave-3 | Safety-path correctness beyond tracing | Partial |
| C-022 | P1 | Semantic core | 2026-Q3 | C-Wave-1 | Lightweight behavioral range and state inference | Partial |

## Program D: New Tooling And CI Capabilities

New tooling, testing infrastructure, and pipeline features that do not yet exist.

### D Wave Summary

| Wave | Owner | Target Window | Items | Validation Route |
| --- | --- | --- | --- | --- |
| D-Wave-1: Pre-commit and hooks | Devtools + CI | 2026-Q2 | D-032 | `pre-commit run --all-files`; CI green |
| D-Wave-2: Test and quality infrastructure | Test infra + Parser tooling + Pipeline + UX + Config + Observability + Docs + AI | 2026-Q3 | D-016, D-017, D-018, D-022, D-023, D-026, D-030, D-033, D-036, D-037 | `pytest tests/`; `sattlint-repo-audit --profile quick` |
| D-Wave-3: Semantic and differential tooling | Semantic tooling + Pipeline | 2026-Q4 | D-020, D-024, D-034 | `pytest tests/`; differential output reviewed against known fixture |
| D-Wave-Backlog: Advanced analysis | Semantic tooling + Pipeline | Backlog | D-025, D-035 | Deferred until symbolic execution scope confirmed |

### D Item Backlog

| ID | Priority | Owner | Target Window | Wave | Feature |
| --- | --- | --- | --- | --- | --- |
| D-016 | P1 | Test infrastructure | 2026-Q3 | D-Wave-2 | Fault injection and robustness testing |
| D-017 | P1 | Parser tooling | 2026-Q3 | D-Wave-2 | Property-based parser testing |
| D-018 | P1 | Parser tooling | 2026-Q3 | D-Wave-2 | Fuzzing targets |
| D-020 | P1 | Semantic tooling | 2026-Q4 | D-Wave-3 | SattLine mutation engine |
| D-022 | P1 | Pipeline + UX loop | 2026-Q3 | D-Wave-2 | Finding validation feedback loop |
| D-023 | P1 | Devtools invariants | 2026-Q3 | D-Wave-2 | Core invariant checks |
| D-024 | P1 | Semantic tooling | 2026-Q4 | D-Wave-3 | Improved dead code detection |
| D-025 | P2 | Semantic tooling | Backlog | D-Wave-Backlog | Symbolic execution lite |
| D-026 | P1 | Config + CLI | 2026-Q3 | D-Wave-2 | Configuration validation |
| D-030 | P1 | Observability | 2026-Q3 | D-Wave-2 | Logging and observability |
| D-032 | P1 | Devtools + CI | 2026-Q2 | D-Wave-1 | Pre-commit hooks |
| D-033 | P1 | Devtools + QA | 2026-Q3 | D-Wave-2 | Repository maintainability and test quality checks |
| D-034 | P1 | Pipeline | 2026-Q4 | D-Wave-3 | Differential analysis |
| D-035 | P2 | Pipeline | Backlog | D-Wave-Backlog | Production code analysis |
| D-036 | P1 | Docs generation | 2026-Q3 | D-Wave-2 | Analyzer reference examples |
| D-037 | P1 | AI workflow | 2026-Q3 | D-Wave-2 | AI task templates |

## Program E: GUI Explorer

New GUI explorer that does not exist yet. All items below are new features.

### Milestones

| Milestone | Owner | Target Window | Feature Groups | Validation Route |
| --- | --- | --- | --- | --- |
| E-GUI-M1: Explorer skeleton | GUI core | 2026-Q3 | E1 (feedback basics), E12 (navigation structure) | Manual smoke test of skeleton; no crashes on empty workspace |
| E-GUI-M2: Real data wiring | GUI core + Semantic core | 2026-Q4 | E3 (discoverability), E4 (performance) | Smoke test with real SattLine workspace; virtualized list renders |
| E-GUI-M3: Draft vs official diff | GUI core + Analyzer | 2026-Q4 | E2 (error handling), E9 (testing and debugging UX) | Diff renders correctly; error paths surface actionable messages |
| E-GUI-M4: Resilience and UX polish | GUI core + Platform | 2027-Q1 | E5 (extensibility), E10 (workflow and power user) | Feature flags work; batch ops verified; command palette active |
| E-GUI-M5: Accessibility, extensibility, hardening | GUI core + Platform | 2027-Q2 | E6 (i18n), E7 (accessibility), E8 (security), E11 (sync) | Accessibility audit pass; i18n strings externalized; security review |

### E1 Feedback and Responsiveness

- E-GUI-001 Loading indicators (spinner and skeleton placeholders)
- E-GUI-002 Progress bar for long operations
- E-GUI-003 Non-blocking UI using async workers and background tasks
- E-GUI-004 Status bar with contextual state
- E-GUI-005 Inline validation near form controls
- E-GUI-006 Subtle state animations for transitions and completion

### E2 Error Handling and Resilience

- E-GUI-007 User-friendly errors with actionable next steps
- E-GUI-008 Retry actions for transient failures
- E-GUI-009 Graceful partial-failure behavior
- E-GUI-010 Crash reporting path and export target
- E-GUI-011 Safe rollback of temporary UI and in-memory state

### E3 Discoverability and UX Polish

- E-GUI-012 Tooltips for controls, filters, and status badges
- E-GUI-013 Empty-state content with recovery action
- E-GUI-014 First-run onboarding for explorer flow
- E-GUI-015 Inline tips and contextual hints
- E-GUI-016 Search and filter across file tree and issue list
- E-GUI-017 Recently used files and actions quick access

### E4 Performance and Scalability

- E-GUI-018 Virtualized rendering for large lists
- E-GUI-019 Lazy load heavy panes
- E-GUI-020 Cache expensive computations
- E-GUI-021 Memory usage sampling and warning thresholds
- E-GUI-022 Startup optimization and deferred initialization

### E5 Extensibility and Architecture

- E-GUI-023 Plugin or extension seam for custom inspectors
- E-GUI-024 Modular feature flags for progressive rollout
- E-GUI-025 Scripting hooks for automation workflows
- E-GUI-026 Local API layer for GUI actions
- E-GUI-027 Command palette for power workflows

### E6 Internationalization and Localization

- E-GUI-028 Externalize user-facing strings
- E-GUI-029 Locale-aware formatting for numbers and dates
- E-GUI-030 Right-to-left layout readiness
- E-GUI-031 Runtime language switching

### E7 Accessibility

- E-GUI-032 Screen reader support
- E-GUI-033 Accessibility roles where applicable
- E-GUI-034 High-contrast mode
- E-GUI-035 Keyboard-only navigation
- E-GUI-036 Clear focus indicators
- E-GUI-037 Colorblind-safe palette checks

### E8 Security and Privacy

- E-GUI-038 Secure handling and storage for sensitive values
- E-GUI-039 Permission boundaries for file and system access
- E-GUI-040 Input sanitization for parsed content and filters
- E-GUI-041 Audit logging for critical user actions

### E9 Testing and Debugging UX

- E-GUI-042 In-app debug and log panel
- E-GUI-043 Export logs action
- E-GUI-044 Feature-flag and debug-mode switchboard
- E-GUI-045 Reproducibility export of a state snapshot package

### E10 Workflow and Power User Features

- E-GUI-046 Batch operations for multi-item issue actions
- E-GUI-047 Multi-select support in file and issue surfaces
- E-GUI-048 Drag reorder where ordering is user-controlled
- E-GUI-049 Action history beyond basic undo and redo
- E-GUI-050 Command palette integration across core actions
- E-GUI-051 Customizable shortcuts

### E11 Sync and Multi-Device

- E-GUI-052 Cloud sync
- E-GUI-053 Conflict resolution UX
- E-GUI-054 Offline mode with deferred sync

### E12 Navigation Structure

- E-GUI-055 Breadcrumbs for context path
- E-GUI-056 Back and forward navigation between explorer states
- E-GUI-057 Deep linking to selected file, view, and filter state
- E-GUI-058 Split-view and multi-pane layouts
