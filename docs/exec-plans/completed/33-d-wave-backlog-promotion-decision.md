# D-Wave-Backlog Promotion Decision

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

## Purpose / Big Picture

This plan replaces the D-025 and D-035 roadmap backlog rows as the live owner for Program D backlog decisions. The archived scope lock in `docs/exec-plans/completed/10-d-wave-backlog-advanced-analysis-gating.md` is still the historical record, but it is not the right place to make the next promotion decision. After this file is executed, maintainers will have one active surface that says whether symbolic execution lite is ready to move beyond helper-level proof, whether production code analysis should remain blocked behind it, and what the first focused implementation or continued deferral evidence must be.

## Progress

- [x] (2026-05-13 09:12Z) Create the ExecPlan and confirm that D-025 and D-035 already have archived gating context in `docs/exec-plans/completed/10-d-wave-backlog-advanced-analysis-gating.md`, while the current tree already contains partial helper surfaces in `src/sattlint/analyzers/symbolic_lite.py`, `tests/analyzers/test_symbolic_lite.py`, `src/sattlint/devtools/production_summary.py`, and `tests/devtools/test_devtools_orphans.py`.
- [x] (2026-05-13 10:57Z) Re-read the archived scope lock, inspect the current helper and test surfaces, and check the nearest integration seams in `src/sattlint/analyzers/_registry_delivery.py`, `src/sattlint/devtools/pipeline_artifacts.py`, and `src/sattlint/devtools/artifact_registry.py`.
- [x] (2026-05-13 10:57Z) Decide D-025 remains deferred because the current surface is still helper-level substrate plus delivery metadata, not a supported analyzer exposed via CLI, LSP, or a real pipeline producer.
- [x] (2026-05-13 10:57Z) Decide D-035 remains deferred with D-025 because the current surface is still helper-level production-summary logic with placeholder artifact producers, no production-corpus contract, and no runtime or triage budget.
- [x] (2026-05-13 10:57Z) Record blockers, next review conditions, and helper-level proof that reduced uncertainty, including the focused helper pytest command cited in this plan.

## Surprises & Discoveries

- Observation: the repository already has symbolic-lite helper code and tests, but not a first-class user-facing analyzer or command.
  Evidence: `src/sattlint/analyzers/symbolic_lite.py` defines `PathState`, `PathStateLattice`, and `build_symbolic_summary()`, and `tests/analyzers/test_symbolic_lite.py` exercises those helpers, but there is no active implementation plan or stable end-user surface for D-025.
- Observation: the repository already has production-summary helpers, but not a production-analysis workflow.
  Evidence: `src/sattlint/devtools/production_summary.py` and `tests/devtools/test_devtools_orphans.py` cover KLOC and allowlist behavior, but there is no dedicated production-analysis command, corpus contract, or rollout policy for D-035.
- Observation: the archived backlog gate already said the next move should happen in a new active file rather than by reopening the archive.
  Evidence: `docs/exec-plans/completed/10-d-wave-backlog-advanced-analysis-gating.md` explicitly records that the next backlog move should happen in a dedicated active decision slice.
- Observation: the closest analyzer integration seam still treats `symbolic_lite` as metadata rather than as a supported delivery surface.
  Evidence: `src/sattlint/analyzers/_registry_delivery.py` registers `symbolic_lite` with `depends_on_analyzers` and `exposed_via`, but it does not mark the analyzer as `cli_exposed` or `lsp_exposed`, and the current tree has no additional `symbolic_lite` call sites outside helper tests, metadata, and artifact registration.
- Observation: both candidate artifacts are wired through placeholder pipeline producers rather than through real payload builders.
  Evidence: `src/sattlint/devtools/pipeline_artifacts.py` registers both `production_summary` and `symbolic_summary` with `_build_none_payload`, so the current artifact plumbing acknowledges the schema names without yet producing user-facing outputs.

## Decision Log

- Decision: open a new active decision plan instead of reusing the archived D-backlog gate.
  Rationale: the archived file is still useful as scope-lock history, but it should not keep accumulating live state.
  Date/Author: 2026-05-13 / Copilot (GPT-5.4)
- Decision: keep D-025 and D-035 together in the same live decision file.
  Rationale: D-035 remains downstream of D-025 scope maturity, runtime budgets, and false-positive behavior, so the two features still share one promotion gate.
  Date/Author: 2026-05-13 / Copilot (GPT-5.4)
- Decision: treat the current helper code as readiness evidence, not as implementation completion.
  Rationale: helper-level tests prove some substrate exists, but they do not yet give users a stable analyzer or direct command that fulfills the roadmap promise.
  Date/Author: 2026-05-13 / Copilot (GPT-5.4)
- Decision: keep D-025 deferred at this checkpoint instead of promoting it into active implementation.
  Rationale: the current implementation stops at path-state helpers, summary export, and analyzer-delivery metadata; it does not yet define a supported analyzer surface, deterministic path-budget contract, or owner acceptance suite for a first public rollout.
  Date/Author: 2026-05-13 / Copilot (GPT-5.4)
- Decision: keep D-035 deferred with D-025 rather than promoting production analysis independently.
  Rationale: the current production-summary code is still helper-level, the pipeline producer is a placeholder, and there is no documented production corpus, runtime budget, or finding-triage contract that would make production-scale analysis safe to start.
  Date/Author: 2026-05-13 / Copilot (GPT-5.4)

## Outcomes & Retrospective

Planning baseline only. The backlog work now has a live owner outside the roadmap, and the next promotion decision can be made here without mutating the archived scope-lock file. The intended end state is either a clear continued deferral with objective blockers or a concrete first implementation slice for D-025 and possibly D-035.

2026-05-13 review outcome: remain deferred. The current tree now reduces uncertainty more than the archived gate could because it proves that bounded symbolic-path and production-summary helpers already exist and pass focused helper tests, but the same review also shows that both features stop short of supported delivery surfaces. D-025 still lacks a first-class analyzer entrypoint with explicit exposure and acceptance proof, and D-035 still lacks a real production-analysis workflow with a corpus contract, runtime budget, and triage policy.

2026-05-13 next review conditions: revisit promotion only after a concrete D-025 public surface is proposed in the existing analyzer framework, the placeholder symbolic or production artifact producers are replaced by real payload builders or removed from the promotion story, and D-035 has an explicit opt-in production corpus plus runtime and false-positive handling rules.

## Context and Orientation

The archived scope lock remains in `docs/exec-plans/completed/10-d-wave-backlog-advanced-analysis-gating.md`. Read it first when executing this plan because it already defines the included and excluded scope for symbolic execution lite. This new file does not replace that history; it replaces the roadmap as the live owner for the next decision.

The current helper code is real but limited. `src/sattlint/analyzers/symbolic_lite.py` contains a bounded path-state lattice and a summary exporter. `tests/analyzers/test_symbolic_lite.py` proves those helpers are deterministic. `src/sattlint/devtools/production_summary.py` contains production-summary helpers with allowlist and KLOC logic, and `tests/devtools/test_devtools_orphans.py` exercises them. None of those surfaces currently provides a stable end-user analyzer or devtool that satisfies the original roadmap intent.

The current analyzer and artifact seams remain relevant, and the current checkpoint answers the remaining question negatively. `src/sattlint/analyzers/_registry_delivery.py` already knows about `symbolic_lite` metadata, but it does not expose a supported analyzer surface. `src/sattlint/devtools/artifact_registry.py` and `src/sattlint/devtools/pipeline_artifacts.py` already reserve `symbolic_summary` and `production_summary` artifact identities, but the active pipeline producers still return placeholder `None` payloads instead of real outputs.

## Plan of Work

Phase 1 is readiness review. Re-read the archived scope lock in completed plan `10`, then evaluate whether the current symbolic-lite helper layer is enough to define a first public surface for D-025. If the answer is yes, convert this file into a concrete implementation plan with explicit milestones, feature-local tests, and a narrow validation route. If the answer is no, record the missing scope or false-positive evidence here and keep the feature deferred.

Phase 2 depends on the D-025 decision. If D-025 is still not ready, D-035 stays deferred and this file records the next review checkpoint. If D-025 is promoted, decide whether D-035 can move at the same time or whether production analysis still lacks a safe corpus, runtime budget, or triage model.

Phase 3 captures the outcome. This file should end the work in one of two states: a live implementation plan with concrete milestones, or a live deferred decision record with explicit blockers and next review conditions. In either case, the roadmap no longer needs to carry D-025 and D-035 as the only owner.

Current review status:

- Outcome: remain deferred.
- D-025 blockers: no supported analyzer exposure, no explicit deterministic path-budget contract, and no owner acceptance route beyond helper tests.
- D-035 blockers: placeholder pipeline producer, no production corpus contract, no runtime budget, and no finding-triage policy.
- Next review trigger: a narrow implementation proposal that reuses the existing analyzer or devtool seams and defines the first real user-facing surface before code promotion starts.

## Concrete Steps

Run all commands from the repository root.

Re-read the archived scope lock and the current helper surfaces before making any decision:

    rg -n "D-025|D-035|scope|promotion" docs/exec-plans/completed/10-d-wave-backlog-advanced-analysis-gating.md docs/exec-plans/completed/11-program-d-missing-work-closeout.md
    rg -n "PathState|symbolic_summary|production_summary|findings_per_kloc" src/sattlint/analyzers/symbolic_lite.py src/sattlint/devtools/production_summary.py tests/analyzers/test_symbolic_lite.py tests/devtools/test_devtools_orphans.py

If D-025 is promoted, establish the first focused validation route:

    python scripts/run_repo_python.py -m pytest --no-cov tests/analyzers/test_symbolic_lite.py -x -q --tb=short

If D-035 is promoted, extend the focused validation route with production-summary proof:

    python scripts/run_repo_python.py -m pytest --no-cov tests/analyzers/test_symbolic_lite.py tests/devtools/test_devtools_orphans.py -x -q --tb=short

Run markdownlint after any decision or milestone updates in this file:

    python scripts/run_repo_python.py scripts/run_markdownlint.py docs/exec-plans/active/33-d-wave-backlog-promotion-decision.md

## Validation and Acceptance

Acceptance depends on the decision outcome. If the features remain deferred, this file is acceptable only when it records the blocker evidence and the next review conditions precisely enough that a later executor does not need to reconstruct them from the roadmap or the archived file. If D-025 and or D-035 are promoted, acceptance requires concrete milestones, focused validation commands, and a user-visible surface definition that goes beyond helper-level code.

## Idempotence and Recovery

This plan is safe to revisit repeatedly. Keep the archived gate intact and append new evidence here. If a promotion attempt reveals that the current helper code is too weak or too noisy, revert this file to a deferred state, record the blocker, and do not pretend the backlog work is active. If the decision changes later, update this same file rather than opening a competing backlog owner.

## Artifacts and Notes

Record the decision outcome, the exact blocker or promotion evidence, and any helper-level proof that informed the decision. The current review used this focused helper-proof command and it completed without failures:

  python scripts/run_repo_python.py -m pytest --no-cov tests/analyzers/test_symbolic_lite.py tests/devtools/test_devtools_orphans.py -x -q --tb=short

If D-025 is promoted later, capture the first passing feature-local test transcript. If D-035 is promoted later, capture the accepted production-corpus contract and runtime budget here as plain language, not as an implied assumption.

## Interfaces and Dependencies

This plan depends on `docs/exec-plans/completed/10-d-wave-backlog-advanced-analysis-gating.md` as the preserved scope lock, plus the current helper surfaces in `src/sattlint/analyzers/symbolic_lite.py`, `tests/analyzers/test_symbolic_lite.py`, `src/sattlint/devtools/production_summary.py`, and `tests/devtools/test_devtools_orphans.py`. If the backlog work is promoted, any new user-facing implementation must reuse existing analyzer or devtool seams instead of inventing a parallel framework.
