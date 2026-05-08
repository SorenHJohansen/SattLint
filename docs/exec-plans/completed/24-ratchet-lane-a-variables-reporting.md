# Ratchet Lane A: Variables And Reporting

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

## Purpose / Big Picture

Lane A clears the ratchet blockers that all live in the variable-analyzer and report-formatting surface. Right now the worktree is blocked because three touched variable-analysis source files and one touched reporting source file still sit in the typing debt allowlist, those same source files are far below the `100%` touched-file coverage target, `src/sattlint/reporting/variables_report.py` grew above its recorded structural baseline, and `tests/test_analyzers_variables.py` also grew above its recorded structural baseline. After this lane lands, the variable-analysis source files will be locally type-clean, fully covered by focused owner tests, `variables_report.py` will be below its prior baseline, and `tests/test_analyzers_variables.py` will be smaller than the current blocked size because extracted scenarios now live in dedicated test modules.

Observable outcome: the lane-local owner suite passes, the lane-local coverage proof for the owned touched source files reports `100%`, and both oversized files are smaller than the live blocked counts (`719 -> < 672` for `variables_report.py`, `2511 -> < 2232` for `tests/test_analyzers_variables.py`).

## Progress

- [x] (2026-05-06 10:10Z) Create the lane document from the live `scripts/check_ratchet_policy.py` blocker list.
- [x] (2026-05-06 10:20Z) Claim the lane files and open the executor worktree.
- [x] (2026-05-06 13:30Z) Extract report helpers and split adjacent analyzer-variable scenarios until both oversized files shrink below their blocked baselines.
- [x] (2026-05-06 13:45Z) Validate the owned surface with focused pytest, lane-local coverage proof, Ruff, and Pyright.
- [x] (2026-05-06 14:00Z) Record lane A handoff notes for lane D strict-list adoption.
- [x] (2026-05-06 16:20Z) Sync the lane output into the main worktree and retire the temporary executor worktree.

## Surprises & Discoveries

- Observation: `tests/test_analyzers_variables.py` cannot absorb more coverage work and still satisfy the structural gate.
  Evidence: the current file is `2511` lines and the ratchet blocks at `2232`, so any solution that adds more scenarios to this file makes the structural problem worse.
- Observation: `src/sattlint/reporting/variables_report.py` has both structural and coverage pressure at the same time.
  Evidence: the ratchet reports `719` lines against a `672` line baseline and only `29.85%` touched-file coverage.
- Observation: the cheapest way to clear both structural and coverage debt is extraction, not test-only growth.
  Evidence: the current blockers ask for smaller files and more proof at the same time, which favors moving pure helpers and scenario groups into smaller sibling modules and tests.

## Decision Log

- Decision: lane A owns the variable analyzers, `variables_report.py`, and the oversized variable regression test file together.
  Rationale: structural shrink, report rendering, and analyzer coverage all share the same behavior surface.
  Date/Author: 2026-05-06 / Copilot (GPT-5.4)
- Decision: do not edit `pyproject.toml` in this lane.
  Rationale: local code and test proof can proceed in parallel, while shared typing inventory edits belong to lane D.
  Date/Author: 2026-05-06 / Copilot (GPT-5.4)
- Decision: prefer new dedicated test modules over further growth in `tests/test_analyzers_variables.py`.
  Rationale: the current oversized test file must shrink in this same lane.
  Date/Author: 2026-05-06 / Copilot (GPT-5.4)

## Outcomes & Retrospective

2026-05-06: lane complete. The lane extracted `src/sattlint/reporting/_variables_report_rendering.py`, split adjacent analyzer-variable scenarios into `tests/_analyzers_variables_adjacent_analyzers.py`, reduced `src/sattlint/reporting/variables_report.py` to `516` lines, and reduced `tests/test_analyzers_variables.py` to `2045` lines. The lane handoff recorded focused pytest, Pyright, coverage, Ruff, and follow-up Pyright proof, and the synchronized main-worktree result participated in the merged owner-suite validation that passed at `579 passed`.

## Context and Orientation

Lane A owns these production files:

- `src/sattlint/analyzers/_variables_execution.py`
- `src/sattlint/analyzers/registry.py`
- `src/sattlint/analyzers/variable_issue_collection.py`
- `src/sattlint/reporting/variables_report.py`

Lane A owns these primary tests and may create additional dedicated small tests under `tests/` when needed:

- `tests/test_analyzers_variables.py`
- `tests/test_analyzers_state.py`
- `tests/test_analyzers_suites.py`

Current live blocker details for these files are:

- typing allowlist exit still required for `_variables_execution.py`, `registry.py`, `variable_issue_collection.py`, and `variables_report.py`,
- touched-file coverage is currently `8.93%`, `55.45%`, `5.78%`, and `29.85%` respectively,
- `variables_report.py` is `719` lines against a blocked baseline of `672`,
- `tests/test_analyzers_variables.py` is `2511` lines against a blocked baseline of `2232`.

This lane must not touch `pyproject.toml`. Lane D will move these files from the typing debt allowlist into `tool.pyright.strict` after lane A proves they are clean.

## Plan of Work

Milestone A makes the owned source files type-clean locally. Fix the annotations, typed dictionaries, helper return shapes, and any import cycles needed in `_variables_execution.py`, `registry.py`, `variable_issue_collection.py`, and `variables_report.py` so a direct `pyright` run on those files passes without relying on lane D.

Milestone B shrinks `variables_report.py`. Extract pure helper logic into one or more private sibling modules under `src/sattlint/reporting/` so the owner file drops below `672` lines. Keep public behavior unchanged. A good split is pure issue-deduping or summary-rendering helpers that can be tested directly.

Milestone C shrinks `tests/test_analyzers_variables.py`. Move scenario clusters that no longer need to live in the monolith into dedicated test modules. Good candidates are report-formatting scenarios, nested-unused-parameter scenarios, or other single-owner clusters that do not need the entire analyzer kitchen sink.

Milestone D raises coverage to `100%` for the owned touched source files. Prefer direct helper tests and extracted dedicated tests over broad integration growth. If `tests/test_analyzers_suites.py` can supply proof cheaply, use it, but do not grow it unless a small dedicated file would be worse.

Milestone E records the lane handoff. Once the owned files are type-clean and fully covered, write down the exact files that lane D should move into `tool.pyright.strict` and any now-cleared coverage entries that can be removed from `artifacts/analysis/file_debt_ratchet.json`.

## Concrete Steps

Run commands from the repository root.

First focused validation after the first substantive edit:

    python scripts/run_repo_python.py -m pytest --no-cov tests/test_analyzers_state.py tests/test_analyzers_suites.py tests/test_analyzers_variables.py -x -q --tb=short

Lane-local type proof:

    pyright src/sattlint/analyzers/_variables_execution.py src/sattlint/analyzers/registry.py src/sattlint/analyzers/variable_issue_collection.py src/sattlint/reporting/variables_report.py

Lane-local coverage proof:

    python scripts/run_repo_python.py -m pytest tests/test_analyzers_state.py tests/test_analyzers_suites.py tests/test_analyzers_variables.py -x -q --tb=short --cov=src/sattlint/analyzers/_variables_execution.py --cov=src/sattlint/analyzers/registry.py --cov=src/sattlint/analyzers/variable_issue_collection.py --cov=src/sattlint/reporting/variables_report.py --cov-report=term-missing --cov-report=xml:artifacts/audit/coverage-lane-a-variables-reporting.xml --cov-fail-under=0

Optional structural proof after the shrink work lands:

    python scripts/run_repo_python.py -m pytest --no-cov tests/test_ratchet_policy.py -x -q --tb=short

## Validation and Acceptance

Lane A is complete only when all of these are true:

- `pyright` passes for the owned production files,
- the focused no-cov owner suite passes,
- the coverage proof command reports `100%` for the four owned touched source files,
- `src/sattlint/reporting/variables_report.py` is below `672` lines,
- `tests/test_analyzers_variables.py` is below `2232` lines,
- lane D can adopt the owned source files into `tool.pyright.strict` without more code edits.

## Idempotence and Recovery

Do not add more tests to `tests/test_analyzers_variables.py` after the first shrink edit unless the file is already below its blocked baseline. If an extracted helper belongs naturally in a private sibling module, move it instead of leaving it in `variables_report.py`. If the coverage proof still misses lines after the obvious owners pass, add a dedicated tiny test file rather than widening unrelated monoliths.

## Artifacts and Notes

Record these artifacts as the lane proceeds:

- the final line counts for `variables_report.py` and `tests/test_analyzers_variables.py`,
- the passing `pyright` command and result,
- the lane-local coverage XML path `artifacts/audit/coverage-lane-a-variables-reporting.xml`,
- the exact files that lane D should move into `tool.pyright.strict`.

## Interfaces and Dependencies

Lane A must not touch `pyproject.toml`. Lane D owns the shared typing inventory edit. If a variable-related behavior already belongs to a dedicated test file extracted during this lane, prefer extending that file instead of re-growing `tests/test_analyzers_variables.py`. Keep the public report text stable unless a failing assertion proves an intentional output correction is required.
