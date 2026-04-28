# Refactor Remaining Work

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

## Purpose / Big Picture

This ExecPlan captures the remaining refactoring work needed to modernize SattLint's codebase. The goal is to improve maintainability by splitting the monolithic `app.py` into focused modules, stabilize return types, and fix console output routing. Each wave produces demonstrably working behavior that can be verified by running tests.

## Progress

- [x] (2026-04-28) Updated exec-plans template to match Codex Execution Plans format
- [ ] Wave 3: Split src/sattlint/app.py behind stable sattlint.app facade
- [ ] Wave 4: User-visible console output routing; logging levels
- [ ] Wave 5: Return type consistency
- [ ] Wave 6: Parse, Don't Validate - transform validation functions to parsing functions

## Surprises & Discoveries

- Observation: The current app.py contains multiple layers of responsibility (CLI dispatch, menu routing, project loading, analysis workflows) that make it difficult to test in isolation.
  Evidence: tests/test_app.py contains many monkeypatch.setattr() calls targeting different behaviors in the same file.
- Observation: Return type inconsistency creates silent failures that are hard to debug.
  Evidence: Several modules return None, [], or {} as sentinels instead of raising typed exceptions.

## Decision Log

- Decision: Keep sattlint.app as the only public import path during refactoring.
  Rationale: External callers (CLI, LSP) expect stable import paths. Changing these without a facade would break consumers.
  Date/Author: 2026-04-28 / sattlint

## Outcomes & Retrospective

To be filled as waves complete.

## Context and Orientation

This ExecPlan lives in `docs/exec-plans/active/refactor-remaining.md`. The reader should have access to:
- `src/sattlint/app.py` - the main application file to be refactored
- `src/sattlint/app_graphics.py` - already split graphics helpers
- `src/sattlint/console.py` - output wrappers
- Tests in `tests/test_app.py`, `tests/test_app_menus.py`, `tests/test_app_analysis.py`

Key modules:
- `sattlint.app` - public facade
- `sattlint.console` - output routing
- `sattlint.analyzers` - analysis passes

## Plan of Work

The refactoring proceeds in waves, each producing working, testable output:

1. **Wave 3** - Split app.py into focused modules (app_base.py, app_docs.py, app_analysis.py, app_menus.py)
2. **Wave 4** - Console output routing and logging levels
3. **Wave 5** - Return type consistency fixes

## Concrete Steps

### Wave 3: Split app.py

Before starting, verify current state:
```bash
cd "$(git rev-parse --show-toplevel)"
pytest tests/test_app.py -v --collect-only
```

Split sequence:

1. Extract base seam into `src/sattlint/app_base.py`:
   - Move: constants, config I/O wrappers, prompt/screen helpers, logging setup, CLI parser
   - Keep re-exports in `app.py` for backward compatibility
   - Run: `pytest tests/test_app.py -v -k "test_name"` to verify

2. Extract documentation flow into `src/sattlint/app_docs.py`:
   - Move: documentation scope state, unit-selection helpers, documentation_menu()
   - Validate with documentation tests

3. Extract analysis flow into `src/sattlint/app_analysis.py`:
   - Move: project-loading helpers, analyzer catalog, analysis submenus
   - Validate with analysis tests

4. Extract menu orchestration into `src/sattlint/app_menus.py`:
   - Move: dump_menu(), config_menu(), tools_menu(), main() loop
   - Validate with menu tests

5. Shrink app.py to facade exports only

### Wave 4: Console Output

Replace remaining `print()` calls with console wrappers:
```bash
# Find remaining ad-hoc prints
grep -r "print(" src/sattlint/*.py | grep -v console.py
```

### Wave 5: Return Types

Use audit from `docs/exec-plans/completed/refactor-wave1-audit.md` to fix module-by-module.

## Validation and Acceptance

Wave 3 acceptance:
- `pytest tests/test_app.py` passes with patches targeting the new owning module
- `pytest tests/test_app_menus.py` passes
- `pytest tests/test_app_analysis.py` passes
- No behavior drift for CLI entry points

Wave 4 acceptance:
- `sattlint` CLI produces structured output via console.py wrappers
- Debug mode shows debug-level logs; normal mode shows user-facing output only

Wave 5 acceptance:
- No sentinel returns (None, [], {}) from internal functions
- Typed exceptions raised at boundaries

## Idempotence and Recovery

Each wave can be run independently. If a split breaks tests:
1. Identify the failing test
2. Retarget patches to the correct owning module
3. Re-run the same test before proceeding

The original app.py can be recovered from git if needed.

## Artifacts and Notes

See completed wave outputs in `docs/exec-plans/completed/`:
- `refactor-wave1-audit.md` - Return type audit

## Interfaces and Dependencies

- `sattlint.app` - Public facade (must remain stable)
- `sattlint.console` - Output routing
- `sattlint.analyzers` - Analysis registry
- pytest fixtures in tests/conftest.py
