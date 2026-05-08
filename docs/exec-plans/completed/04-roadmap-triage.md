# Roadmap Triage

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

## Purpose / Big Picture

This plan turns the large backlog programs in the tech debt tracker into smaller owned waves. When it is complete, Programs C, D, and E will stop reading as one undifferentiated backlog and will instead map to quarterly or milestone-sized execution slices that can become future active plans.

## Progress

- [x] Group Program C analyzer work into a small number of execution waves with named owners.
- [x] Group Program D tooling work into implementation waves with clear validation paths.
- [x] Collapse Program E into milestone-based waves that can be scheduled without reopening the retired GUI TODO files.

## Surprises & Discoveries

- Observation: Program E is too large to execute directly from the tracker without an intermediate triage pass.
  Evidence: The tracker contains more than fifty GUI items plus milestone placeholders.

## Decision Log

- Decision: Keep roadmap triage as the fourth active plan.
  Rationale: It matters, but it should not outrank the P0 structural blockers or the currently active output and CLI documentation work.
  Date/Author: 2026-04-29 / Copilot (GPT-5.4)

## Outcomes & Retrospective

Completed 2026-04-29.

- Program C: 4 waves defined. C-Wave-1 (semantic correctness, Q3, 5 items), C-Wave-2 (new analysis passes, Q3, 6 items), C-Wave-3 (safety path depth, Q4, 1 item), C-Wave-Backlog (domain-specific, 3 items). Each wave has an owner and `pytest` validation route.
- Program D: 4 waves defined. D-Wave-1 (pre-commit, Q2, 1 item), D-Wave-2 (test and quality infra, Q3, 10 items), D-Wave-3 (semantic and differential tooling, Q4, 3 items), D-Wave-Backlog (advanced analysis, 2 items). Validation routes reference `sattlint-repo-audit` and `pytest`.
- Program E: Milestone table replaces flat milestone bullet list. 5 milestones mapped to feature groups with owners and target windows spanning Q3 2026 through Q2 2027.
- doc-gardener passed after changes (docs-only, no code modified).

## Context and Orientation

The source of truth is `docs/exec-plans/feature-roadmap.md`. Program C covers analyzer and semantic work, Program D covers tooling and CI work, and Program E covers GUI and UX work. This plan is intentionally docs-only until one of the resulting waves is promoted into a narrower active implementation plan.

## Plan of Work

Review each backlog program, group related items into a few concrete waves, and record an owner, target window, and validation route for each wave. Do not create new code work inside this plan. The output is a clearer tracker and a set of candidate future active plans.

## Concrete Steps

Run from repository root:

    rg -n "^## Program [CDE]|^\| C-|^\| D-|^### E|^\- E-GUI" docs/exec-plans/feature-roadmap.md
    python scripts/run_repo_python.py -m sattlint.devtools.doc_gardener

## Validation and Acceptance

Acceptance means the tracker no longer presents Programs C, D, and E as one flat backlog, each resulting wave has an owner and target window, and doc-gardener still passes after the documentation-only change.

## Idempotence and Recovery

This plan is safe to revise incrementally. Keep edits limited to tracker and active-plan docs until a resulting wave is ready for implementation.

## Artifacts and Notes

Record the first set of proposed waves and any deferred items that remain intentionally unscheduled.

## Interfaces and Dependencies

This plan depends on `docs/exec-plans/feature-roadmap.md` remaining the single source of truth for planned new capabilities.
