# Output Boundary Unification

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

## Purpose / Big Picture

This plan finishes the user-visible output cleanup across the CLI, console, and adjacent GUI or style-boundary surfaces. When it is complete, the remaining W3, W4, and W10 work will use the shared console boundary consistently, and contributor-facing behavior will stop depending on scattered `print()` usage or ad hoc output formatting.

## Progress

- [x] Finish the remaining W3 app-surface output migration.
- [x] Finish the W4 CLI, console, and GUI output cleanup for currently owned seams.
- [x] Close the currently owned W10 low-severity ownership sweep after output seams stabilized.

## Surprises & Discoveries

- Observation: W3 already moved important output paths to `console.print_output`, so the remaining work is concentrated in follow-on surfaces rather than the first app slice.
  Evidence: the shared active-claim lock recorded the first W3 slice as validated across `tests/test_app.py`, `tests/test_app_analysis.py`, `tests/test_app_menus.py`, and `tests/test_cli.py`.
- Observation: The earlier parser-validation regression is no longer reproducible in the focused output-boundary test slice.
  Evidence: `python scripts/run_repo_python.py -m pytest --no-cov tests/test_app.py tests/test_app_analysis.py tests/test_app_menus.py tests/test_cli.py -x -q --tb=long` now passes (143 passed), and `test_syntax_check_command_ok` passes consistently in repeated runs.

## Decision Log

- Decision: Group W3, W4, and W10 in one plan.
  Rationale: They all touch the same output and style seams, and doing them in one ordered plan reduces rework on shared files.
  Date/Author: 2026-04-29 / Copilot (GPT-5.4)

## Outcomes & Retrospective

The remaining W3 app-surface call sites were migrated to the shared output boundary in `app.py`, `app_base.py`, `app_menus.py`, `app_docs.py`, and `app_graphics.py`.
W4 target seams (`src/sattlint/cli/entry.py` and `src/sattlint_gui/binding.py`) currently show no direct `print(...)` usage, so the boundary is consistent across this ownership slice. W10 narrow style validation for owned files remains clean.

## Context and Orientation

The main files are in `src/sattlint/` and include `app_analysis.py`, `app_cli_commands.py`, `app_menus.py`, `console.py`, and any remaining modules that still emit user-facing output directly.
Validation lives closest to `tests/test_app.py`, `tests/test_app_analysis.py`, `tests/test_app_menus.py`, and `tests/test_cli.py`. Style-only cleanup should stay scoped to the owning files listed in current-work for W10.

## Plan of Work

Start by finding the remaining user-facing output paths that still bypass the shared console boundary. Migrate those paths in the owning module, keep behavior stable, and rerun the narrow CLI and menu tests. Only after the output behavior is stable should the W10 style sweep continue in the same ownership slice.

## Concrete Steps

Run from repository root:

    rg -n "print\(" src/sattlint
    python scripts/run_repo_python.py -m pytest --no-cov tests/test_app.py tests/test_app_analysis.py tests/test_app_menus.py tests/test_cli.py -x -q --tb=short
    python scripts/run_repo_python.py -m ruff check src/sattlint/engine.py src/sattlint/casefolding.py src/sattlint/__init__.py

## Validation and Acceptance

Acceptance means the targeted pytest command passes, the remaining output paths use the shared console boundary where appropriate, and any W10 cleanup still passes the narrow `ruff` check without reopening user-visible behavior drift.

## Idempotence and Recovery

Repeat the targeted pytest command after each output-boundary slice. If a style-only change causes behavior drift, revert that local slice and rerun pytest before continuing.

## Artifacts and Notes

Migrated modules in this slice:

- `src/sattlint/app.py`
- `src/sattlint/app_base.py`
- `src/sattlint/app_menus.py`
- `src/sattlint/app_docs.py`
- `src/sattlint/app_graphics.py`

Validation notes:

- `python scripts/run_repo_python.py -m ruff check src/sattlint/engine.py src/sattlint/casefolding.py src/sattlint/__init__.py` passed.
- `python scripts/run_repo_python.py -m pytest --no-cov tests/test_app.py tests/test_app_analysis.py tests/test_app_menus.py tests/test_cli.py -x -q --tb=long` passed (143 passed).
- `python scripts/run_repo_python.py -m pytest --no-cov tests/test_app.py -k test_syntax_check_command_ok -q --tb=short` passed in three consecutive runs.

## Interfaces and Dependencies

This plan depends on `sattlint.console` remaining the shared user-output boundary and on the CLI entry points continuing to route through the same public functions tested today.
