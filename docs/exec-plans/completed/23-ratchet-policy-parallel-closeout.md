# Ratchet Policy Parallel Closeout

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

## Purpose / Big Picture

This orchestration plan split one ratchet-policy blocker queue into three executor lanes plus one shared consolidation lane. Lane A, lane B, and lane C have now been bootstrapped, merged back into the main worktree, and validated together; the remaining shared ratchet closeout stays in lane D.

Observable outcome: lane A, lane B, and lane C are archived under `docs/exec-plans/completed/`, their temporary executor worktrees are retired, and `docs/exec-plans/active/27-ratchet-lane-d-consolidation.md` remains the single active plan for the unfinished shared closeout.

## Progress

- [x] (2026-05-06 10:00Z) Run `scripts/check_ratchet_policy.py` and capture the live blocker list for the current worktree.
- [x] (2026-05-06 10:05Z) Split the work into lane A variables/reporting, lane B repo-audit/devtools, lane C uncovered typing inventory, and lane D shared consolidation.
- [x] (2026-05-06 10:10Z) Create dedicated active ExecPlans for lanes A through D under `docs/exec-plans/active/`.
- [x] (2026-05-06 10:20Z) Bootstrap three executor slices with isolated claims and validations.
- [x] (2026-05-06 16:10Z) Merge the lane A, B, and C worktree outputs back into the main worktree and validate the merged owner surface (`579 passed`).
- [x] (2026-05-06 16:20Z) Retire the executor lanes and hand the remaining shared ratchet closeout to lane D.

## Surprises & Discoveries

- Observation: `pyproject.toml` is the only unavoidable shared file across the typing closeout work.
  Evidence: the live blocker list combines uncovered inventory files and touched-file allowlist exits in the same `tool.pyright.strict` and `tool.sattlint.typing_ratchet.debt_allowlist` tables.
- Observation: variable-surface work cannot be mixed with repo-audit work if the goal is clean parallelism.
  Evidence: `src/sattlint/reporting/variables_report.py` is simultaneously a touched typing-debt file, a touched coverage-debt file, and a shrink-only structural debt file, while `tests/test_analyzers_variables.py` is also under shrink-only structural enforcement.
- Observation: the repo-audit and shared-devtools cluster is one coherent owner surface even though several helpers were recently split out.
  Evidence: the planning-context artifact routes the changed devtools files to the same pipeline and repo-audit owner tests that already powered the successful owner coverage rerun.
- Observation: `src/sattlint/analyzers/state_inference.py` is a typing inventory blocker, but it is also owned by active feature plan `21-c-022-state-inference.md`.
  Evidence: the shared lock currently claims `src/sattlint/analyzers/state_inference.py` for workstream `c-022-state-inference-2026-05-04`.

## Decision Log

- Decision: use three parallel implementation lanes plus one serial consolidation lane.
  Rationale: local code and test changes can run in parallel, but the shared typing inventory file should have one owner to avoid merge collisions.
  Date/Author: 2026-05-06 / Copilot (GPT-5.4)
- Decision: keep `pyproject.toml` and any debt-ledger cleanup in lane D instead of letting every lane edit them.
  Rationale: the parallel lanes should deliver type-clean files, coverage proof, and structural shrink without fighting over one shared table edit.
  Date/Author: 2026-05-06 / Copilot (GPT-5.4)
- Decision: dedicate lane A to variable analyzers and reporting.
  Rationale: that lane owns the only shrink-only structural blockers and the most direct overlap between analyzer coverage and report formatting.
  Date/Author: 2026-05-06 / Copilot (GPT-5.4)
- Decision: dedicate lane B to repo-audit and shared devtools coverage closeout.
  Rationale: those files share the same owner tests, helper splits, and finish-gate proof surface.
  Date/Author: 2026-05-06 / Copilot (GPT-5.4)
- Decision: dedicate lane C to uncovered inventory adoption outside lanes A and B.
  Rationale: it keeps a third executor productive without increasing overlap on the files already failing touched-file coverage.
  Date/Author: 2026-05-06 / Copilot (GPT-5.4)

## Outcomes & Retrospective

2026-05-06: orchestration complete. The ratchet blocker queue was split into lane-local slices that could run in parallel, lane A through C were merged back into the main worktree, and the merged owner-suite validation passed at `579 passed`. The final shared typing-inventory and ratchet-proof work was not executed inside this orchestration slice; it remains active in `docs/exec-plans/active/27-ratchet-lane-d-consolidation.md`.

## Context and Orientation

Run all commands from the repository root.

The live blocker list from `& ".venv/Scripts/python.exe" scripts/check_ratchet_policy.py` currently says four things:

- Uncovered typing inventory files: `src/sattlint/analyzers/_registry_delivery.py`, `src/sattlint/analyzers/_registry_specs.py`, `src/sattlint/analyzers/state_inference.py`, `src/sattlint/devtools/_ai_work_map_freshness.py`, `src/sattlint/devtools/_pipeline_cli.py`, `src/sattlint/devtools/_repo_audit_check_specs.py`, `src/sattlint/devtools/_repo_audit_entrypoint_runs.py`, `src/sattlint/devtools/_repo_audit_full_run.py`, `src/sattlint/devtools/_repo_audit_reporting.py`, `src/sattlint/devtools/_structural_report_impact.py`, `src/sattlint/devtools/coordination_lock_state.py`, `src/sattlint/devtools/fault_injection.py`, `src/sattlint/devtools/fuzzer.py`, `src/sattlint/devtools/impact_analyzer.py`, `src/sattlint/devtools/property_tests.py`, `src/sattlint/simulation/__init__.py`, `src/sattlint/simulation/_runtime_models.py`, and `src/sattlint/simulation/runtime.py`.
- Touched files that must leave the typing debt allowlist: `src/sattlint/analyzers/_variables_execution.py`, `src/sattlint/analyzers/registry.py`, `src/sattlint/analyzers/variable_issue_collection.py`, `src/sattlint/devtools/ai_work_map.py`, `src/sattlint/devtools/coverage_reports.py`, `src/sattlint/devtools/pipeline.py`, `src/sattlint/devtools/repo_audit.py`, `src/sattlint/devtools/repo_audit_entrypoints.py`, `src/sattlint/devtools/structural_reports.py`, and `src/sattlint/reporting/variables_report.py`.
- Touched coverage debt files that are still below `100%`: `_variables_execution.py` (`8.93%`), `registry.py` (`55.45%`), `variable_issue_collection.py` (`5.78%`), `ai_work_map.py` (`15.58%`), `coverage_reports.py` (`12.23%`), `pipeline.py` (`17.11%`), `repo_audit.py` (`22.05%`), `repo_audit_entrypoints.py` (`13.82%`), `structural_reports.py` (`14.26%`), and `variables_report.py` (`29.85%`).
- Shrink-only structural blockers: `src/sattlint/reporting/variables_report.py` is `719` lines against a `672` line baseline, and `tests/test_analyzers_variables.py` is `2511` lines against a `2232` line baseline.

This orchestration plan delegates execution to these four documents:

- `docs/exec-plans/completed/24-ratchet-lane-a-variables-reporting.md`
- `docs/exec-plans/completed/25-ratchet-lane-b-repo-audit-devtools.md`
- `docs/exec-plans/completed/26-ratchet-lane-c-uncovered-typing-inventory.md`
- `docs/exec-plans/active/27-ratchet-lane-d-consolidation.md`

The shared-claim lock lives at `.git/sattlint-ai-coordination/current_work_lock.json`. Every executor lane should claim only its own files. Do not let lane A, B, or C edit `pyproject.toml`. Lane D is the only plan that should update the typing inventory tables.

## Plan of Work

Milestone A bootstraps the parallel lanes. Open one worktree per lane and claim only the files listed in the lane documents. If the state-inference feature workstream is still active when lane C starts, either have that workstream absorb `src/sattlint/analyzers/state_inference.py` or mark that one file blocked and continue with the rest of lane C.

Milestone B lands lane A. That lane clears the variable-analyzer and reporting blockers without touching `pyproject.toml`. The lane must finish with shrunken files, focused owner tests, local `pyright` proof on the owned files, and full coverage on the owned touched source files.

Milestone C lands lane B. That lane clears the repo-audit and shared-devtools blockers without touching `pyproject.toml`. The lane must finish with focused owner tests, local `pyright` proof on the owned files, and full coverage on the owned touched source files.

Milestone D lands lane C. That lane makes the remaining uncovered inventory files type-clean and owner-tested so lane D can move them into strict coverage safely.

Milestone E runs lane D. After the three executor lanes are green, lane D updates `tool.pyright.strict`, removes files from `tool.sattlint.typing_ratchet.debt_allowlist`, deletes any now-cleared coverage debt entries from `artifacts/analysis/file_debt_ratchet.json`, and reruns the ratchet and pre-push proofs.

## Concrete Steps

Use these task ids when bootstrapping the work:

- Lane A task id: `ratchet-lane-a-variables-reporting`
- Lane B task id: `ratchet-lane-b-repo-audit-devtools`
- Lane C task id: `ratchet-lane-c-uncovered-typing-inventory`
- Lane D task id: `ratchet-lane-d-consolidation`

Before opening the executor worktrees, rerun the live blocker command once so every lane starts from the same inventory snapshot:

    & ".venv/Scripts/python.exe" scripts/check_ratchet_policy.py

Then bootstrap one executor worktree per lane using `scripts/bootstrap_ai_slice.py` and the claimed file lists and first validation command from each lane document.

After lanes A through C land, lane D should run these shared closeout commands in order:

    & ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_ratchet_policy.py tests/test_ratchet_policy_typing.py -x -q --tb=short
    & ".venv/Scripts/python.exe" scripts/check_ratchet_policy.py
    & ".venv/Scripts/sattlint-repo-audit.exe" --profile full --check-my-changes --output-dir artifacts/audit

## Validation and Acceptance

This orchestration plan is complete only when all four conditions are true:

- lane A, lane B, and lane C have each recorded focused validation and no unresolved blocker inside their owned files,
- lane D has updated the shared typing inventory without adding new debt or loosening any ratchet,
- `scripts/check_ratchet_policy.py` exits `0`,
- `sattlint-repo-audit --profile full --check-my-changes --output-dir artifacts/audit` exits clean for the merged worktree.

## Idempotence and Recovery

If lane A, B, or C discovers that it must touch `pyproject.toml`, stop and move that change into lane D instead of widening the lane. If a lane needs more coverage but the cheapest owner surface is an oversized test file owned by another lane, create a dedicated small test file rather than adding more lines to the oversized owner. If the blocker list changes while work is active, rerun `scripts/check_ratchet_policy.py`, update the affected lane plans, and keep the unchanged lanes moving.

## Artifacts and Notes

Each lane should record:

- the exact `pyright` command it used for its owned files,
- the exact focused `pytest` command and pass count,
- the lane-local coverage XML path when coverage proof is required,
- whether the lane is ready for lane D strict-list adoption.

## Interfaces and Dependencies

Do not loosen ratchets or add approvals as a substitute for fixing code or tests. The only shared state that should move in lane D is `pyproject.toml` and optional cleanup in `artifacts/analysis/file_debt_ratchet.json` when debt is actually cleared. `src/sattlint/analyzers/state_inference.py` remains coupled to active feature plan `21-c-022-state-inference.md`; if that plan is still live, coordinate ownership before lane C edits it.
