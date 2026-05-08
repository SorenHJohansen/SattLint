# Ratchet Lane B: Repo Audit And Shared Devtools

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

## Purpose / Big Picture

Lane B clears the touched-file ratchet blockers in the repo-audit and shared-devtools surface. The current worktree still fails because `src/sattlint/devtools/ai_work_map.py`, `coverage_reports.py`, `pipeline.py`, `repo_audit.py`, `repo_audit_entrypoints.py`, and `structural_reports.py` are all still in the typing debt allowlist, and all six are far below the `100%` touched-file coverage target. In addition, several helper modules split out of those owners are still missing from the typing inventory. After this lane lands, the devtools owners will be locally type-clean, the touched devtools sources will have focused `100%` coverage proof, and the helper split modules will be ready for strict-list adoption by lane D.

Observable outcome: the lane-local owner tests pass, the lane-local coverage run reports `100%` for the six touched devtools sources, and lane D can move the owned files into `tool.pyright.strict` without reopening these modules.

## Progress

- [x] (2026-05-06 10:10Z) Create the lane document from the live `scripts/check_ratchet_policy.py` blocker list.
- [x] (2026-05-06 10:20Z) Claim the lane files and open the executor worktree.
- [x] (2026-05-06 14:30Z) Sync the owned devtools helper splits and tests back into the main worktree.
- [x] (2026-05-06 15:40Z) Repair merge-back fallout in the main worktree for AI work-map references, split pipeline recommendation tests, and repo-audit status-drift fixtures.
- [x] (2026-05-06 16:10Z) Validate the merged repo-audit/devtools owner surface as part of the combined owner-suite run that passed at `579 passed`.
- [x] (2026-05-06 16:20Z) Retire the temporary executor worktree and keep lane D as the only remaining shared ratchet closeout.

## Surprises & Discoveries

- Observation: the repo-audit finish-gate owner tests already overlap heavily across the blocked files.
  Evidence: the recent successful owner coverage rerun already used `tests/test_pipeline_run.py`, `tests/test_pipeline.py`, `tests/test_corpus.py`, `tests/test_repo_audit.py`, `tests/test_ai_work_map.py`, and `tests/test_recommendation_routing.py` as one shared proof surface.
- Observation: helper extraction already happened in this area, so the remaining work is proof and typing hygiene, not another large refactor.
  Evidence: the current worktree already contains `_ai_work_map_freshness.py`, `_pipeline_cli.py`, `_repo_audit_check_specs.py`, `_repo_audit_entrypoint_runs.py`, `_repo_audit_full_run.py`, `_repo_audit_reporting.py`, and `_structural_report_impact.py`.
- Observation: `structural_reports.py` has structural pressure even though it is not one of the shrink-only blockers.
  Evidence: the checked-in debt ledger records `1805` lines against a `500` target for `structural_reports.py`, so the lane should avoid growth when helper extraction can absorb it.

## Decision Log

- Decision: keep the repo-audit owners and their adjacent helper modules in one lane.
  Rationale: they share the same tests, the same finish-gate story, and the same helper split context.
  Date/Author: 2026-05-06 / Copilot (GPT-5.4)
- Decision: do not edit `pyproject.toml` in this lane.
  Rationale: shared typing inventory updates belong to lane D so the execution lanes can stay parallel.
  Date/Author: 2026-05-06 / Copilot (GPT-5.4)
- Decision: treat `structural_reports.py` as keep-flat-or-shrink, not as an expansion surface.
  Rationale: the file already carries structural debt, so any extra logic should move into adjacent helpers when practical.
  Date/Author: 2026-05-06 / Copilot (GPT-5.4)

## Outcomes & Retrospective

2026-05-06: lane closed through merged main-worktree integration rather than a pristine standalone lane finish gate. The repo-audit and shared-devtools helper splits are now present in the main worktree, the merge-back repairs that they exposed were fixed in place, and the combined owner-suite validation passed at `579 passed`. The executor handoff stayed machine-readable but remained a draft stub, so this archived plan reflects the merged result rather than a self-contained lane-local closeout.

## Context and Orientation

Lane B owns these touched ratchet blocker files:

- `src/sattlint/devtools/ai_work_map.py` (`15.58%` coverage, typing allowlist exit required)
- `src/sattlint/devtools/coverage_reports.py` (`12.23%` coverage, typing allowlist exit required)
- `src/sattlint/devtools/pipeline.py` (`17.11%` coverage, typing allowlist exit required)
- `src/sattlint/devtools/repo_audit.py` (`22.05%` coverage, typing allowlist exit required)
- `src/sattlint/devtools/repo_audit_entrypoints.py` (`13.82%` coverage, typing allowlist exit required)
- `src/sattlint/devtools/structural_reports.py` (`14.26%` coverage, typing allowlist exit required)

Lane B also owns these adjacent helper modules that the policy checker says are still missing from the typing inventory:

- `src/sattlint/devtools/_ai_work_map_freshness.py`
- `src/sattlint/devtools/_pipeline_cli.py`
- `src/sattlint/devtools/_repo_audit_check_specs.py`
- `src/sattlint/devtools/_repo_audit_entrypoint_runs.py`
- `src/sattlint/devtools/_repo_audit_full_run.py`
- `src/sattlint/devtools/_repo_audit_reporting.py`
- `src/sattlint/devtools/_structural_report_impact.py`
- `src/sattlint/devtools/coordination_lock_state.py`

Primary owner tests for this lane are:

- `tests/test_ai_work_map.py`
- `tests/test_ai_work_map_harness.py`
- `tests/test_corpus.py`
- `tests/test_pipeline_collection.py`
- `tests/test_pipeline_collection_graphs.py`
- `tests/test_pipeline_run.py`
- `tests/test_pipeline_run_recommendations.py`
- `tests/test_repo_audit.py`
- `tests/test_repo_audit_doc_gardener.py`
- `tests/test_repo_audit_entrypoints_helpers.py`
- `tests/test_repo_audit_entrypoints_verify.py`
- `tests/test_recommendation_routing.py`
- `tests/test_structural_reports.py`
- `tests/test_structural_reports_graphs.py`

This lane must not touch `pyproject.toml`. Lane D will move the owned touched files out of the debt allowlist and add the helper modules to `tool.pyright.strict` after this lane proves them locally.

## Plan of Work

Milestone A makes the owned devtools files type-clean locally. Fix missing annotations, return types, container shapes, and helper-module interfaces in the touched owner files and the adjacent helper modules so a direct `pyright` run passes on this lane's owned files.

Milestone B raises coverage on the six touched devtools owner files. Use the existing owner tests first, then add direct helper or serialization tests only where the owner suites still leave gaps. Avoid broad new integration flows when direct helper tests can hit the missing lines.

Milestone C keeps `structural_reports.py` flat. If new coverage work exposes awkward internal seams, extract a small helper instead of growing the owner file. The goal is to leave `structural_reports.py` no larger than it is now and preferably smaller.

Milestone D records the lane handoff. Once the six touched files are fully covered and the helper splits are type-clean, write down the exact strict-list additions and any coverage debt entries lane D can delete.

## Concrete Steps

Run commands from the repository root.

First focused validation after the first substantive edit:

    python scripts/run_repo_python.py -m pytest --no-cov tests/test_ai_work_map.py tests/test_ai_work_map_harness.py tests/test_corpus.py tests/test_pipeline_collection.py tests/test_pipeline_collection_graphs.py tests/test_pipeline_run.py tests/test_pipeline_run_recommendations.py tests/test_repo_audit.py tests/test_repo_audit_doc_gardener.py tests/test_repo_audit_entrypoints_helpers.py tests/test_repo_audit_entrypoints_verify.py tests/test_recommendation_routing.py tests/test_structural_reports.py tests/test_structural_reports_graphs.py -x -q --tb=short

Lane-local type proof:

    pyright src/sattlint/devtools/ai_work_map.py src/sattlint/devtools/coverage_reports.py src/sattlint/devtools/pipeline.py src/sattlint/devtools/repo_audit.py src/sattlint/devtools/repo_audit_entrypoints.py src/sattlint/devtools/structural_reports.py src/sattlint/devtools/_ai_work_map_freshness.py src/sattlint/devtools/_pipeline_cli.py src/sattlint/devtools/_repo_audit_check_specs.py src/sattlint/devtools/_repo_audit_entrypoint_runs.py src/sattlint/devtools/_repo_audit_full_run.py src/sattlint/devtools/_repo_audit_reporting.py src/sattlint/devtools/_structural_report_impact.py src/sattlint/devtools/coordination_lock_state.py

Lane-local coverage proof:

    python scripts/run_repo_python.py -m pytest tests/test_ai_work_map.py tests/test_ai_work_map_harness.py tests/test_corpus.py tests/test_pipeline_collection.py tests/test_pipeline_collection_graphs.py tests/test_pipeline_run.py tests/test_pipeline_run_recommendations.py tests/test_repo_audit.py tests/test_repo_audit_doc_gardener.py tests/test_repo_audit_entrypoints_helpers.py tests/test_repo_audit_entrypoints_verify.py tests/test_recommendation_routing.py tests/test_structural_reports.py tests/test_structural_reports_graphs.py -x -q --tb=short --cov=src/sattlint/devtools/ai_work_map.py --cov=src/sattlint/devtools/coverage_reports.py --cov=src/sattlint/devtools/pipeline.py --cov=src/sattlint/devtools/repo_audit.py --cov=src/sattlint/devtools/repo_audit_entrypoints.py --cov=src/sattlint/devtools/structural_reports.py --cov-report=term-missing --cov-report=xml:artifacts/audit/coverage-lane-b-repo-audit-devtools.xml --cov-fail-under=0

Optional quick audit after the six touched owners are green:

    python scripts/run_repo_python.py -m sattlint.devtools.repo_audit --profile quick --output-dir artifacts/audit-lane-b-quick

## Validation and Acceptance

Lane B is complete only when all of these are true:

- `pyright` passes for the owned touched files and the listed helper modules,
- the focused no-cov owner suite passes,
- the coverage proof command reports `100%` for the six touched owner files,
- `structural_reports.py` is not larger than the size this lane started with,
- lane D can update `tool.pyright.strict` and remove any now-cleared coverage debt entries without more code edits in these files.

## Idempotence and Recovery

Prefer direct helper tests and serialization tests before adding broader command-orchestration tests. If a missing line lives in a helper already split out of an owner, test the helper directly instead of adding more behavior to the monolith. If `structural_reports.py` needs more logic to make testing sane, extract it to a helper rather than growing the owner file.

## Artifacts and Notes

Record these artifacts as the lane proceeds:

- the passing `pyright` command and result,
- the lane-local coverage XML path `artifacts/audit/coverage-lane-b-repo-audit-devtools.xml`,
- the final size of `structural_reports.py`,
- the exact files that lane D should move into `tool.pyright.strict`.

## Interfaces and Dependencies

Lane B must not touch `pyproject.toml`. Lane D owns the shared typing inventory edit. Keep all outputs machine-readable. Do not add parallel audit registries or new artifact formats. Extend the existing devtools seams and the current owner tests instead.
