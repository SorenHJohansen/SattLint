# D-Wave-Backlog: Advanced Analysis Gating

This ExecPlan is archived as historical context. Remaining Program D closeout work now lives in `docs/exec-plans/completed/11-program-d-missing-work-closeout.md`.

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

## Purpose / Big Picture

This plan governs D-Wave-Backlog items D-025 (symbolic execution lite) and D-035 (production code analysis) so they are promoted to active implementation only when prerequisites are satisfied. The wave is intentionally deferred in the roadmap; this plan defines how to make that deferral explicit, testable, and reversible.

Observable outcome: maintainers can decide promotion with objective criteria instead of ad hoc judgment, and can immediately launch implementation with pre-defined milestones once gates are met.

## Progress

- [x] (2026-04-29) Create this backlog-gating plan with explicit promotion criteria and pre-defined implementation skeleton.
- [x] (2026-05-04) Confirm prerequisite status: D-Wave-2 and D-Wave-3 remain incomplete, and roadmap hygiene is not yet sufficient to record promotion from `docs/exec-plans/feature-roadmap.md` alone because D-025 and D-035 still lack explicit rows there.
- [x] (2026-05-04) Confirm symbolic-execution scope agreement and constraints are documented in this file as the current promotion gate.
- [x] (2026-05-04) Decision checkpoint: keep D-025 deferred until D-Wave-2 and D-Wave-3 close and roadmap item status rows are restorable from the Program D source of truth.
- [x] (2026-05-04) Decision checkpoint: keep D-035 deferred with D-025 because production-scale analysis remains downstream of symbolic-execution scope maturity and the same prerequisite blockers.
- [x] (2026-05-04) Closeout refresh: D-Wave-2 and D-Wave-3 wave-close validation now passes, and roadmap rows for `D-025` and `D-035` exist again.
- [ ] If promoted, replace deferred checklist entries with active milestone checklist entries and run first focused validations.
- [x] (2026-05-04) If not promoted, record next review date and blocking constraints.
- [ ] Move this file to `docs/exec-plans/completed/` only after promotion decision is final and either implementation completes or deferral is formally closed.

## Surprises & Discoveries

- Observation: Backlog items are not implementation-ready without clearer symbolic-execution boundaries.
  Evidence: Program D still keeps backlog work deferred, and no implementation-ready symbolic-execution scope or promotion metrics have been validated in focused analyzer suites.
- Observation: D-035 value depends on D-025 design maturity because production analysis risk is higher than fixture-local analysis.
  Evidence: production-analysis tooling amplifies false-positive and performance risks when path reasoning is underspecified.
- Observation: the archived backlog gate is now ready for a fresh promotion decision, but that decision should happen in a new active slice rather than by reopening this historical file.
  Evidence: D-Wave-2 and D-Wave-3 wave-close validation now passes, and `docs/exec-plans/feature-roadmap.md` again contains explicit deferred rows for D-025 and D-035.

## Decision Log

- Decision: Keep D-025 and D-035 in one backlog governance file rather than separate deferred docs.
  Rationale: the two items share promotion dependencies and should be reviewed together at each checkpoint.
  Date/Author: 2026-04-29 / Copilot (GPT-5.3-Codex)
- Decision: Require D-Wave-2 and D-Wave-3 completion before promotion.
  Rationale: backlog items build on tooling, mutation, and differential foundations from prior waves.
  Date/Author: 2026-04-29 / Copilot (GPT-5.3-Codex)
- Decision: Keep both backlog items deferred at the 2026-05-04 review checkpoint.
  Rationale: `docs/exec-plans/completed/08-d-wave-2-test-and-quality-infrastructure.md` and `docs/exec-plans/completed/09-d-wave-3-semantic-and-differential-tooling.md` originally still had open wave-close proof, and the Program D roadmap initially lacked explicit backlog item rows for D-025 and D-035.
  Date/Author: 2026-05-04 / Copilot (GPT-5.4)
- Decision: keep this file archived as scope-lock history even though the promotion prerequisites are now restored.
  Rationale: the next backlog move should happen in a dedicated new active decision plan, not by turning this archived deferment record back into the live execution surface.
  Date/Author: 2026-05-04 / Copilot (GPT-5.4)

## Outcomes & Retrospective

Initial governance baseline complete. Future entries will capture promotion decisions, constraints, and resulting implementation outcomes.

2026-05-04 review outcome: remain deferred. The plan now has explicit scope bounds, blocker evidence, and a next checkpoint so maintainers can revisit promotion without re-triaging the same gaps.

2026-05-04 closeout refresh outcome: prerequisites are now restored. D-Wave-2 and D-Wave-3 wave-close validation passes, and explicit roadmap rows for `D-025` and `D-035` exist again. This archived file now serves as the preserved scope lock for the next active backlog promotion-decision slice rather than as the live review surface itself.

## Context and Orientation

Program D backlog source is `docs/exec-plans/feature-roadmap.md`. Closeout work restored the explicit deferred roadmap rows for `D-025` and `D-035`, so a future promotion review can now cite the roadmap directly.

Definitions used in this plan:

- Symbolic execution lite: bounded reasoning over multiple potential execution paths using simplified constraints.
- Production code analysis: running advanced analysis patterns on production-scale project inputs rather than controlled fixtures.
- Promotion gate: objective condition that must be satisfied before backlog work is allowed to move into active implementation.

Prerequisites this plan enforces:

- D-Wave-2 complete and validated,
- D-Wave-3 complete and validated,
- scope agreement on what symbolic execution lite includes and excludes,
- acceptable performance and false-positive risk targets.

Current prerequisite status after the 2026-05-04 closeout refresh:

- D-Wave-2 is complete and validated: `docs/exec-plans/completed/08-d-wave-2-test-and-quality-infrastructure.md` records passing wave-close validation.
- D-Wave-3 is complete and validated: `docs/exec-plans/completed/09-d-wave-3-semantic-and-differential-tooling.md` records passing wave-close validation.
- Roadmap status hygiene is restored: `docs/exec-plans/feature-roadmap.md` carries explicit deferred rows for D-025 and D-035, so backlog promotion can now be decided from the roadmap source of truth.

## Scope Lock

The current scope agreement for symbolic execution lite is intentionally narrow. Promotion is blocked unless the implementation proposal stays inside these bounds first.

Included in scope:

- bounded path exploration over existing analyzer or semantic representations for one module or one deterministic workspace snapshot at a time,
- branch reasoning for boolean guards, equality or inequality comparisons, and constant-propagated values that can be derived without an external solver,
- deterministic path ordering and hard caps on path count, branch depth, and emitted findings so focused tests remain reproducible,
- findings that explain why a path is contradictory, unreachable, or conditionally unsafe using existing reporter seams.

Explicitly excluded from scope:

- SMT, SAT, theorem-prover, or other external constraint-solver integration,
- whole-repository symbolic state exploration across arbitrary module graphs,
- unbounded loop reasoning, recursive fixed-point search, or speculative execution over external I/O,
- automatic remediation, code rewriting, or production-default enablement before fixture-scale evidence exists.

Promotion gate metrics:

- D-025 must first prove deterministic focused-suite behavior on fixture-scale inputs with path-explosion controls and no known false-positive regressions in the nearest analyzer tests.
- D-035 must not start until D-025 scope and reporting are stable, plus an opt-in production corpus, runtime budget, and triage plan are documented.
- Neither item is promotable while the roadmap cannot record explicit status transitions for the prerequisite Program D items.

## Plan of Work

Phase 1 (Readiness): verify prerequisite wave completion and collect baseline risk data from existing analyzer and differential outputs.

Phase 2 (Scope lock): define symbolic execution lite boundaries, supported constructs, explicit exclusions, and performance budget in this file.

Phase 3 (Decision): choose one of three paths and record rationale: remain deferred, promote D-025 only, or promote D-025 and D-035 together.

Phase 4 (If promoted): convert this file into an active implementation plan by replacing deferred checklist items with concrete milestones, then execute narrow-first validations.

Current review status:

- Outcome: remain archived until a new active promotion-decision plan is opened.
- Remaining constraints: no approved symbolic-execution benchmark or false-positive budget for production-scale rollout, and no dedicated active slice has yet been opened to make the promotion decision.
- Next review date: open the next active backlog decision slice at the next Program D planning pass; do not reactivate this archived file as the live execution surface.

## Concrete Steps

Run commands from repository root.

Readiness checks:

  rg -n "D-Wave-2|D-Wave-Backlog" docs/exec-plans/feature-roadmap.md
  rg -n "D-Wave-3|D-020|D-024|D-034|D-025|D-035" docs/exec-plans/active/*.md docs/exec-plans/completed/*.md docs/exec-plans/feature-roadmap.md

If promoted, first focused validation routes:

    & ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_analyzers_suites.py tests/test_analyzers_state.py tests/test_pipeline.py -x -q --tb=short
    & ".venv/Scripts/sattlint-repo-audit.exe" --profile quick --output-dir artifacts/audit-review-quick

## Validation and Acceptance

Deferred-state acceptance:

- prerequisite status is recorded accurately,
- promotion criteria are explicit and testable,
- next review checkpoint is documented.

Promoted-state acceptance:

- D-025 and/or D-035 have concrete implementation milestones in this file,
- focused validations pass for each promoted milestone,
- roadmap statuses are updated with clear state transitions.

## Idempotence and Recovery

This plan is safe to revisit repeatedly. Each review cycle should append new evidence and leave prior rationale intact. If promotion is attempted and blocked, revert status to deferred in `Progress`, capture blocker evidence, and schedule the next checkpoint.

At the current checkpoint, readiness is restored but promotion is intentionally not decided inside this archived record. Use this file as the preserved scope lock when opening the next active backlog decision slice.

## Artifacts and Notes

Record at each review:

- prerequisite completion evidence,
- scope constraints for symbolic execution,
- decision outcome and rationale,
- promoted milestone evidence if applicable.

## Interfaces and Dependencies

This plan depends on Program D wave plans and roadmap status hygiene. It must not weaken strict parser or analyzer invariants while exploring advanced analysis scope. Any promotion must reuse existing devtools and test seams instead of introducing parallel unchecked frameworks.
