# TODO GUI

## Goal

Build a File-Centric Explorer GUI for SattLint that lets users pick a file, review issues tied to that file, and compare draft versus official module versions.

## Scope Anchor: File-Centric Explorer with Draft/Official Diff

Primary flow:

1. Launch app.
2. Select file from tree of available `.s` and `.x` files.
3. Show all issues whose origin matches selected file.
4. If `.x` variant exists, show draft-versus-official diff.

## Capability Backlog

### Feedback and Responsiveness

- [ ] Loading indicators (spinner and skeleton placeholders).
- [ ] Progress bar for long operations (workspace scan, analysis run, diff build).
- [ ] Non-blocking UI using async workers/background tasks.
- [ ] Status bar with contextual state (selected file, active mode, running task, elapsed time).
- [ ] Inline validation messages near form controls (not only modal dialogs).
- [ ] Subtle state animations for transitions, hover, and completion states.

### Error Handling and Resilience

- [ ] User-friendly error messages with actionable next step text.
- [ ] Retry actions for transient failures.
- [ ] Graceful partial-failure behavior (failed subpanel does not crash whole view).
- [ ] Crash reporting path (structured log and one-click export target).
- [ ] Safe rollback of temporary UI and in-memory state when an operation fails.

### Discoverability and UX Polish

- [ ] Tooltips for controls, filters, and status badges.
- [ ] Empty-state content with clear recovery action.
- [ ] First-run onboarding for explorer flow.
- [ ] Inline tips and contextual hints.
- [ ] Search and filter across file tree and issue list.
- [ ] Recently used files/actions quick access.

### Performance and Scalability

- [ ] Virtualized rendering for large file and issue lists.
- [ ] Lazy load heavy panes (diff and deep issue details).
- [ ] Cache expensive computations (file graph, issue index, parsed module comparison inputs).
- [ ] Memory usage sampling and warning thresholds.
- [ ] Startup optimization and deferred initialization.

### Extensibility and Architecture

- [ ] Plugin/extension seam for custom inspectors.
- [ ] Modular feature flags for progressive rollout.
- [ ] Scripting hooks for automation workflows.
- [ ] Local API layer to expose GUI actions for automation.
- [ ] Command palette for power workflows.

### Internationalization and Localization

- [ ] Externalize user-facing strings.
- [ ] Locale-aware formatting for numbers and dates.
- [ ] Right-to-left layout readiness.
- [ ] Runtime language switching.

### Accessibility

- [ ] Screen reader support for major controls and panels.
- [ ] Accessibility roles where applicable.
- [ ] High-contrast mode.
- [ ] Keyboard-only navigation across all key workflows.
- [ ] Clear focus indicators.
- [ ] Colorblind-safe palette checks.

### Security and Privacy

- [ ] Secure handling and storage for sensitive values.
- [ ] Permission boundaries for file/system access.
- [ ] Input sanitization for parsed content and filters.
- [ ] Audit logging for critical user actions.

### Testing and Debugging UX

- [ ] In-app debug/log panel.
- [ ] Export logs action.
- [ ] Feature-flag and debug-mode switchboard.
- [ ] Reproducibility export (state snapshot package).

### Workflow and Power-User Features

- [ ] Batch operations for multi-item issue actions.
- [ ] Multi-select support in file and issue surfaces.
- [ ] Drag reorder where ordering is user-controlled.
- [ ] Action history beyond basic undo/redo.
- [ ] Command palette integration across core actions.
- [ ] Customizable shortcuts.

### Sync and Multi-Device (if adopted)

- [ ] Cloud sync.
- [ ] Conflict resolution UX.
- [ ] Offline mode with deferred sync.

### Navigation Structure

- [ ] Breadcrumbs for context path.
- [ ] Back/forward navigation between explorer states.
- [ ] Deep linking to selected file/view/filter state.
- [ ] Split-view and multi-pane layouts.

## Backend Implementation Order

1. File enumeration
     - List all `.s` and `.x` files from configured dirs.
     - Include `program_dir`, `ABB_lib_dir`, and `other_lib_dirs`.
     - Group by directory and preserve deterministic ordering.
2. Origin-based filtering
     - Filter issues where `origin_file` (or module path mapped origin) matches selected file.
     - Keep this filter incremental and cache-backed.
3. Dual-load capability
     - Load same module in DRAFT mode (`.s` then `.x` fallback) and OFFICIAL mode (`.x` only) simultaneously.
4. Diff integration via compare_modules()
     - Reuse existing module comparison in analyzer layer.
     - Normalize result for side-by-side panel rendering.
5. Explorer UI integration
     - Add explorer view with file tree, issue panel, and diff panel.

## UI Components (Explorer)

- File browser tree:
    - All `.s` and `.x` files from configured directories.
    - Search/filter, recent files, and quick-jump.
- Issue panel:
    - Issues filtered by selected origin file.
    - Severity and analyzer filters.
    - Multi-select and batch actions.
- Diff panel:
    - Side-by-side draft (`.s`) versus official (`.x`) module diff.
    - Reuse normalized compare output.

## Planned File Touchpoints

- `src/sattlint/app.py`
    - Add dual-load entry points and shared orchestration helpers.
- `src/sattlint/cache.py`
    - Extend caching for file index, issue filter index, and compare inputs/results.
- `src/sattlint_gui/binding.py`
    - Add file enumeration, origin-filtered issue query, and compare orchestration.
- `src/sattlint_gui/frames/explore_frame.py` (new)
    - Build file tree, issue list, and diff panel view logic.
- `src/sattlint_gui/window.py`
    - Add Explorer entry to navigation/sidebar and route frame lifecycle.

## Milestones

### M1: Explorer Skeleton

- [ ] Add Explorer view shell with placeholder tree/issues/diff panels.
- [ ] Add async task runner and status bar plumbing.

### M2: Real Data Wiring

- [ ] Connect file enumeration from configured directories.
- [ ] Connect origin-based issue filtering for selected file.

### M3: Draft vs Official Diff

- [ ] Implement dual-load and compare integration.
- [ ] Render side-by-side diff with line/module grouping.

### M4: Resilience and UX Polish

- [ ] Retry, rollback, inline validation, empty states, and contextual tooltips.
- [ ] Introduce virtualization/lazy loading and baseline performance telemetry.

### M5: Accessibility, Extensibility, and Hardening

- [ ] Keyboard-first navigation and focus standards.
- [ ] Feature flags, command palette, debug panel, and log export.
- [ ] Security/privacy hardening and audit logging.
