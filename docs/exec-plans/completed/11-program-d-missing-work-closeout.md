# Program D Missing Work Closeout

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

## Purpose / Big Picture

The former Program D wave plans are close to implemented, but the remaining work had been split across multiple files and one superseded archive. Before this plan, a maintainer had to read `06`, `08`, `09`, `10`, the archived `07`, and the roadmap to answer two simple questions: what is still missing, and what sequence closes the Program D work. After this plan, there is one short execution surface that covers the real gaps: D-Wave-1 closeout proof, shared repo-audit blockers that stop D-Wave-2 and D-Wave-3 wave-close validation, roadmap hygiene for deferred backlog items, and missing ownership for roadmap items that appear in Program D but in no live ExecPlan.

Observable outcome: after executing this plan, `docs/exec-plans/completed/06-d-wave-1-pre-commit-hooks.md`, `docs/exec-plans/completed/08-d-wave-2-test-and-quality-infrastructure.md`, `docs/exec-plans/completed/09-d-wave-3-semantic-and-differential-tooling.md`, and `docs/exec-plans/completed/10-d-wave-backlog-advanced-analysis-gating.md` remain as historical evidence only, while this file is the only live Program D execution surface.

## Progress

- [x] (2026-05-04) Review active plans `06`, `08`, `09`, and `10` together with archived plan `07` and the Program D roadmap.
- [x] (2026-05-04) Confirm plan `07` is not a missing active plan; it was intentionally superseded and moved to `docs/exec-plans/completed/07-d-wave-2-3-backlog-execution.md`.
- [x] (2026-05-04) Confirm D-Wave-1 still lacks clean-baseline pre-commit proof and explicit deliberate-failure CI proof.
- [x] (2026-05-04) Confirm D-Wave-2 and D-Wave-3 feature milestones are complete, but shared wave-close validation remains open because the same repo-audit and generated-artifact blockers fail both plans.
- [x] (2026-05-04) Confirm backlog governance still lacks explicit roadmap rows for `D-025` and `D-035`.
- [x] (2026-05-04) Confirm Program D roadmap still lists `D-038`, `D-039`, `D-040`, `D-041`, and `D-042` in D-Wave-2 without any active ExecPlan ownership in plans `06` through `10`.
- [x] (2026-05-04) Move the now-unused Program D wave plans `06`, `08`, `09`, and `10` to `docs/exec-plans/completed/` so this file is the only active Program D ExecPlan.
- [x] (2026-05-04) Restore explicit roadmap rows for `D-025`, `D-030`, `D-035`, and `D-037`, and align D-Wave-2 completed statuses with the archived wave evidence.
- [x] (2026-05-04) Decide `D-038` through `D-042` are real Program D commitments and keep them owned in this active closeout plan as open follow-on scope.
- [x] (2026-05-04) Repair the shared repo-audit closeout drift in planning-context, verify-recommendations, and doc-gardener fallback coverage.
- [x] (2026-05-04) Rerun quick audit after the shared fixes; `sattlint-repo-audit --profile quick --output-dir artifacts/audit-review-quick` now passes at `fail-on high` with only medium findings.
- [x] (2026-05-04) Rerun `python -m pre_commit run --all-files` until the D-Wave-1 closeout gate exits clean on the current worktree.
- [x] (2026-05-04) Record equivalent deliberate-failure proof for the pre-commit CI path: the same `python -m pre_commit run --all-files` command failed locally on hook-applied rewrites before normalization, which matches the command wired in `.github/workflows/typing.yml` when branch-push CI is not practical from this workspace.
- [x] (2026-05-04) Rerun broad wave-close validation; `pytest -q` and the quick audit both pass after clearing a stale local `.coverage` database that was outside Program D implementation scope.
- [x] (2026-05-04) Refresh archived records `06`, `08`, `09`, and `10` with the new closeout evidence and next-step routing.
- [x] Milestone A complete: reconcile Program D roadmap ownership and missing-plan coverage.
- [x] Milestone B complete: repair shared repo-audit and generated-artifact blockers, then rerun wave-close validation for D-Wave-2 and D-Wave-3.
- [x] Milestone C complete: rerun D-Wave-1 closeout proof from a clean tree and record CI failure-path evidence.
- [x] Milestone D complete: update plan states, archive any completed plans, and refresh backlog gating decision inputs.

## Review Summary

Live Program D execution now lives in this file. `06`, `08`, `09`, and `10` were moved to `docs/exec-plans/completed/` because they are no longer the active routing surface, and `07` remains a separate superseded historical record.

The real missing work fell into four buckets, and the closeout slice is now largely resolved. First, D-Wave-1 was wired but not closed. That proof is now recorded: `python -m pre_commit run --all-files` reaches a clean exit on the current worktree, and equivalent failure-path evidence was captured locally by reproducing the same command failing on hook-applied rewrites before normalization when branch-push CI was not practical from this workspace.

Second, D-Wave-2 and D-Wave-3 were functionally implemented but shared the same closeout blockers. Those shared blockers are now repaired for closeout purposes: the named repo-audit tests pass, `pytest -q` passes, and the quick audit passes at `fail-on high`. The remaining quick-audit findings are medium-severity structural or hygiene debt that no longer blocks wave-close validation.

Third, the backlog gate in `10` is still archived rather than reactivated, but the roadmap source of truth and prerequisite evidence are now restored. `docs/exec-plans/feature-roadmap.md` carries explicit deferred rows for `D-025` and `D-035`, and the archived backlog record now reflects that D-Wave-2 and D-Wave-3 closeout proof exists. The next backlog review should open a dedicated active decision slice instead of mutating the archived `10` file into live scope again.

Fourth, Program D roadmap coverage is now explicit but not yet delivered. `D-038`, `D-039`, `D-040`, `D-041`, and `D-042` remain real open roadmap commitments. With the closeout blockers removed, these follow-on items are now the only remaining live Program D implementation scope that still needs a dedicated execution slice.

## Surprises & Discoveries

- Observation: the apparent missing plan `07` is a false alarm.
  Evidence: `docs/exec-plans/completed/07-d-wave-2-3-backlog-execution.md` explicitly marks itself superseded by active plans `08`, `09`, and `10`.
- Observation: the largest remaining gap is shared closeout work, not missing feature implementation inside D-Wave-2 or D-Wave-3.
  Evidence: both active plans already record milestone completion for their feature slices and cite the same wave-close blockers.
- Observation: Program D roadmap ownership is currently less complete than the active plan set.
  Evidence: `docs/exec-plans/feature-roadmap.md` has no explicit rows for `D-025` and `D-035` and still lists `D-038` through `D-042` in the D-Wave-2 summary without a live ExecPlan owner.
- Observation: `D-038` through `D-042` are not stale summary noise.
  Evidence: the roadmap already contains full feature sections for each item, so dropping them from the D-Wave-2 summary would hide real open scope rather than correcting a typo.
- Observation: the final broad pytest blocker was a stale local coverage cache, not a Program D code regression.
  Evidence: `pytest -q` initially reported a corrupted `.coverage` database (`no such table: line_bits`) even though all tests passed; after deleting the generated cache and rerunning the same command, the suite completed at `1606 passed`.
- Observation: the last D-Wave-1 closeout failure was a Windows newline loop in the AI routing artifact writer rather than a pre-commit configuration gap.
  Evidence: `python -m pre_commit run --all-files` repeatedly failed at `mixed-line-ending` until `src/sattlint/devtools/ai_work_map.py` was updated to write LF line endings explicitly for the generated routing artifacts.

## Decision Log

- Decision: create one simple closeout plan instead of reopening all active Program D plans immediately.
  Rationale: the missing work is cross-cutting and mostly concerns shared blockers, roadmap hygiene, and archival readiness. A single plan reduces drift and makes ownership explicit.
  Date/Author: 2026-05-04 / Copilot (GPT-5.4)
- Decision: treat `D-038` through `D-042` as a coverage gap until an active plan or a roadmap correction exists.
  Rationale: the current active plan set does not own these items, so they cannot be assumed handled merely because they appear in the Program D summary row.
  Date/Author: 2026-05-04 / Copilot (GPT-5.4)
- Decision: keep `D-038` through `D-042` owned in this closeout plan as follow-on scope rather than dropping them from the roadmap.
  Rationale: each item already has a real roadmap section, but none of them has implementation proof yet. Extending this active plan keeps Program D ownership explicit without pretending the features are delivered.
  Date/Author: 2026-05-04 / Copilot (GPT-5.4)
- Decision: accept equivalent local pre-commit failure-path proof for D-Wave-1 closeout instead of forcing a branch-push CI reproduction from this workspace.
  Rationale: `.github/workflows/typing.yml` runs the same `python -m pre_commit run --all-files` command. Reproducing that command failing before normalization and then passing after the fixes provides the same gate behavior when branch-push CI is not practical.
  Date/Author: 2026-05-04 / Copilot (GPT-5.4)

## Outcomes & Retrospective

2026-05-04: initial review complete. The active Program D plan set is mostly implemented, but it is not yet ready for archival. The remaining work is now grouped into one closeout plan so the next executor does not need to reconstruct missing scope from multiple files.

2026-05-04: archived the now-unused Program D wave plans `06`, `08`, `09`, and `10` into `docs/exec-plans/completed/`. Remaining work stays in this closeout plan.

2026-05-04: Milestone A complete. The Program D roadmap now carries explicit deferred rows for `D-025` and `D-035`, restored D-Wave-2 rows for `D-030` and `D-037`, and aligned completed statuses for the shipped D-Wave-2 items. `D-038` through `D-042` stay owned here as open follow-on scope.

2026-05-04: Milestone B complete. The shared repo-audit closeout drift in planning-context, verify-recommendations, and doc-gardener fallback coverage is repaired. Broad wave-close validation now passes for the shipped D-Wave-2 and D-Wave-3 slices: `pytest -q` -> `1606 passed`, and `sattlint-repo-audit --profile quick --output-dir artifacts/audit-review-quick` -> `Overall status: pass` with `0 blocking at fail-on high`.

2026-05-04: Milestone C complete. `python -m pre_commit run --all-files` now exits clean from this worktree. Equivalent failure-path proof is recorded because the same command failed locally on hook-applied rewrites before normalization, matching the CI step wired in `.github/workflows/typing.yml`.

2026-05-04: Milestone D complete. Archived records `06`, `08`, `09`, and `10` now carry fresh validation evidence and backlog-readiness routing. The remaining live Program D work is no longer wave-close repair; it is follow-on implementation planning for `D-038` through `D-042` plus a future active promotion-decision slice for `D-025` and `D-035`.

## Context and Orientation

Use these documents as the source material while executing this plan:

- `docs/exec-plans/completed/06-d-wave-1-pre-commit-hooks.md` for D-032 closeout requirements and evidence.
- `docs/exec-plans/completed/08-d-wave-2-test-and-quality-infrastructure.md` for D-Wave-2 milestone evidence and current wave-close blockers.
- `docs/exec-plans/completed/09-d-wave-3-semantic-and-differential-tooling.md` for D-Wave-3 milestone evidence and shared wave-close blockers.
- `docs/exec-plans/completed/10-d-wave-backlog-advanced-analysis-gating.md` for `D-025` and `D-035` deferment rules.
- `docs/exec-plans/completed/07-d-wave-2-3-backlog-execution.md` as historical context only. Do not reopen work from this file.
- `docs/exec-plans/feature-roadmap.md` as the Program D roadmap source of truth.

Two terms in this plan need to stay precise. A wave-close validation is the broad proof that a wave is ready to archive, not the focused proof for one milestone. In this repository that broad proof is `pytest -q` plus the quick repo audit. A coverage gap is a roadmap item with no live ExecPlan owner or a live plan goal that is not represented accurately in the roadmap summary.

## Plan of Work

Milestone A resolves documentation and ownership drift before any more implementation work. Start by reconciling Program D coverage in `docs/exec-plans/feature-roadmap.md`. Add explicit deferred rows for `D-025` and `D-035` so the backlog plan can cite the roadmap directly. Then decide whether `D-038` through `D-042` are real missing D-Wave-2 items or stale summary entries. If they are real roadmap commitments, create or extend an active ExecPlan that owns them. If they were listed prematurely, correct the D-Wave-2 summary so it matches the active execution set.

Milestone B fixes the shared blockers that stop both D-Wave-2 and D-Wave-3 from closing. Start with the three failing tests already named in the active plans: `tests/test_repo_audit.py::test_run_check_my_changes_includes_planning_context`, `tests/test_repo_audit_entrypoints_helpers.py::test_run_verify_recommendations_check_converts_catalog_issues_to_findings`, and `tests/test_repo_audit_entrypoints_helpers.py::test_run_verify_recommendations_check_flags_generated_artifact_drift`. After those pass, rerun the quick audit and clear the remaining blocker classes that both plans cite: structural-budget ratchet regression, stale generated-output manifests, and unexpected tracked root entries. Only after the shared blockers are removed should the executor rerun the broad wave-close commands for `08` and `09`.

Milestone C closes the remaining D-Wave-1 operational proof. Rerun `pre-commit run --all-files` from a clean or intentionally normalized checkout so hook-applied rewrites do not contaminate the result. Then capture one deliberate-failure CI proof, either by running the existing workflow path that demonstrates a failing pre-commit step or by documenting equivalent reproducible evidence in the plan if a branch push is not practical in the current environment. Update `06` only after both proofs are recorded.

Milestone D finishes plan hygiene. Update the archived historical records in `06`, `08`, and `09` with any needed fresh validation evidence, and then revisit the archived backlog record in `10`. If D-Wave-2 and D-Wave-3 are both truly closed and roadmap rows for `D-025` and `D-035` exist, open a new active backlog decision plan using the scope lock preserved in `10`. If the prerequisites are still not met, keep `10` as historical deferment evidence only and refresh the blocker evidence in this file instead of reactivating the old wave plan.

## Concrete Steps

Run commands from the repository root.

Milestone A first validation is documentation-only. After editing Program D roadmap or active-plan ownership, run:

    & ".venv/Scripts/python.exe" scripts/run_markdownlint.py docs/exec-plans/feature-roadmap.md docs/exec-plans/active/*.md docs/exec-plans/completed/07-d-wave-2-3-backlog-execution.md

Milestone B first validation starts with the named failing tests:

    & ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_repo_audit.py tests/test_repo_audit_entrypoints_helpers.py -x -q --tb=short -k "planning_context or verify_recommendations"

When that passes, rerun the quick audit:

    & ".venv/Scripts/sattlint-repo-audit.exe" --profile quick --output-dir artifacts/audit-review-quick

If the audit still fails, fix only the remaining blocker classes already recorded by `08` and `09`, then rerun the same quick-audit command before widening.

Milestone C first validation is the D-Wave-1 gate:

    & ".venv/Scripts/python.exe" -m pre_commit run --all-files

If that command applies auto-fixes, normalize or stage the affected files, rerun the same command, and do not mark the plan complete until it exits with status `0` from a clean baseline.

Milestone D broad closeout validation happens only after Milestones B and C are complete:

    & ".venv/Scripts/python.exe" -m pytest -q
    & ".venv/Scripts/sattlint-repo-audit.exe" --profile quick --output-dir artifacts/audit-review-quick

## Validation and Acceptance

This plan is complete only when all four conditions are true.

- Program D roadmap rows and wave summaries match the active ExecPlan set, including explicit deferred rows for `D-025` and `D-035`, restored completed rows for `D-030` and `D-037`, and an ownership decision that keeps `D-038` through `D-042` in this active closeout plan as open follow-on scope.
- The shared repo-audit and generated-artifact failures that block D-Wave-2 and D-Wave-3 are fixed, and both wave-close validation commands pass or have one fresh, clearly documented blocker outside Program D scope.
- D-Wave-1 has a clean `pre-commit run --all-files` result from a clean or intentionally normalized checkout plus one recorded CI failure-path proof.
- Plans `06`, `08`, `09`, and `10` remain archived as historical context, and this file carries the fresh blocker evidence plus any next-step routing.

## Idempotence and Recovery

This plan is designed to be rerun. Do not combine Milestone A roadmap cleanup with Milestone B code fixes in one unvalidated burst. If Milestone B reveals new blocker classes beyond the ones already named in `08` and `09`, record them in this plan and in the affected wave plan before widening scope. If Milestone C cannot produce a clean pre-commit result because unrelated dirty files keep being introduced, stop treating that as a D-Wave-1 implementation gap and document it as an environment or branch-hygiene blocker.

## Artifacts and Notes

Record the following evidence as the work proceeds: the exact failing or passing pytest summary for the three shared repo-audit tests, the quick-audit status path under `artifacts/audit-review-quick`, the final `pre-commit run --all-files` result for D-Wave-1, and the roadmap or plan files changed to reconcile Program D ownership.

## Interfaces and Dependencies

This plan depends on the existing Program D wave plans and roadmap status hygiene. It must not weaken strict parser, analyzer, or repo-audit invariants while closing the remaining gaps. Any new ownership for `D-038` through `D-042` should reuse existing devtools, analyzer, CLI, or docs seams rather than inventing parallel frameworks.
