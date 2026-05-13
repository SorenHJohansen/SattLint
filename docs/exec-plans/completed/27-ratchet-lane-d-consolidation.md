# Ratchet Lane D: Shared Consolidation And Final Proof

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

## Purpose / Big Picture

Lane D is the serial closeout step that turns the three parallel execution lanes into one green ratchet result. The earlier lanes intentionally avoid `pyproject.toml` so they can run without merge collisions. This lane owns the shared typing inventory edit in `pyproject.toml`, any legitimate cleanup in `artifacts/analysis/file_debt_ratchet.json` after debt is actually cleared, the ratchet-policy tests, and the final end-to-end ratchet proof. After this lane lands, the typing inventory will match reality, touched files that became type-clean will be moved into `tool.pyright.strict`, any truly cleared coverage debt entries will be removed instead of left stale, and the ratchet and pre-push checks will pass on the merged worktree.

Observable outcome: `python scripts/run_repo_python.py scripts/check_ratchet_policy.py` exits `0`, and `python scripts/run_repo_python.py -m sattlint.devtools.repo_audit --profile full --check-my-changes --output-dir artifacts/audit` no longer reports ratchet-policy blockers.

## Progress

- [x] (2026-05-06 10:10Z) Create the consolidation document after splitting the implementation work into three parallel lanes.
- [x] (2026-05-06 16:10Z) Collect lane A, lane B, and lane C handoff notes and merge-back validation from the main worktree.
- [ ] Update `pyproject.toml` so uncovered files are represented in `tool.pyright.strict` and touched clean files leave the debt allowlist.
- [ ] Remove only the coverage debt entries that are truly cleared from `artifacts/analysis/file_debt_ratchet.json`.
- [ ] Run ratchet-policy tests and the standalone ratchet checker.
- [ ] Run the full `check-my-changes` gate on the merged worktree.

## Surprises & Discoveries

- Observation: the shared typing inventory is the one place where otherwise parallel work must serialize.
  Evidence: both uncovered inventory adoption and touched-file allowlist exits terminate in `tool.pyright.strict` and `tool.sattlint.typing_ratchet.debt_allowlist`.
- Observation: `file_debt_ratchet.json` should only change when debt is actually cleared.
  Evidence: the ratchet policy instructions explicitly say that the ledger is sparse and shrink-only, and cleared debt should remove entries rather than loosen them.
- Observation: the final proof burden is stronger than `scripts/check_ratchet_policy.py` alone.
  Evidence: the repo-quality contract still expects the full `sattlint-repo-audit --profile full --check-my-changes --output-dir artifacts/audit` closeout command.

## Decision Log

- Decision: keep all shared typing inventory edits in lane D.
  Rationale: this avoids merge collisions in `pyproject.toml` while the executor lanes work in parallel.
  Date/Author: 2026-05-06 / Copilot (GPT-5.4)
- Decision: allow `artifacts/analysis/file_debt_ratchet.json` edits only when a lane has actually cleared debt.
  Rationale: the ratchet rules forbid rebaselining as a substitute for real fixes.
  Date/Author: 2026-05-06 / Copilot (GPT-5.4)
- Decision: require the standalone ratchet check before the full pre-push gate.
  Rationale: a fast focused failure is cheaper to interpret than a broad audit failure.
  Date/Author: 2026-05-06 / Copilot (GPT-5.4)

## Outcomes & Retrospective

2026-05-06: still active. The executor lanes have been merged into the main worktree and archived, but the shared typing-inventory edits, debt-ledger cleanup, and final ratchet proof have not been run yet. Before resuming this plan, regenerate the live blocker inventory because the file lists below reflect the original planning snapshot rather than the post-merge-back main worktree.

## Context and Orientation

Lane D owns these shared files:

- `pyproject.toml`
- `artifacts/analysis/file_debt_ratchet.json` only if debt has actually been cleared and the stale entries should be removed
- `tests/test_ratchet_policy.py`
- `tests/test_ratchet_policy_typing.py`

When lane D starts, it should expect three handoff inputs from the executor lanes:

- lane A: the variable/reporting files that are now type-clean and the line counts proving `variables_report.py` and `tests/test_analyzers_variables.py` are below the blocked baselines,
- lane B: the repo-audit/devtools files that are now type-clean and fully covered,
- lane C: the uncovered inventory files that are now type-clean and owner-tested, plus a note about whether `state_inference.py` was resolved here or left with active plan `21-c-022-state-inference.md`.

The executor plans for lane A, lane B, and lane C are now archived under `docs/exec-plans/completed/`, and their temporary executor worktrees should stay retired. This is now the only active ratchet-policy closeout plan for this slice.

Before resuming the remaining work, rerun `python scripts/run_repo_python.py scripts/check_ratchet_policy.py` and refresh the lists below against the current main worktree.

The current touched files that must leave the typing debt allowlist once they are clean are:

- `src/sattlint/analyzers/_variables_execution.py`
- `src/sattlint/analyzers/registry.py`
- `src/sattlint/analyzers/variable_issue_collection.py`
- `src/sattlint/devtools/ai_work_map.py`
- `src/sattlint/devtools/coverage_reports.py`
- `src/sattlint/devtools/pipeline.py`
- `src/sattlint/devtools/repo_audit.py`
- `src/sattlint/devtools/repo_audit_entrypoints.py`
- `src/sattlint/devtools/structural_reports.py`
- `src/sattlint/reporting/variables_report.py`

The current uncovered inventory files that should move into `tool.pyright.strict` once they are clean are:

- `src/sattlint/analyzers/_registry_delivery.py`
- `src/sattlint/analyzers/_registry_specs.py`
- `src/sattlint/analyzers/state_inference.py` if lane C or plan `21-c-022-state-inference.md` made it clean
- `src/sattlint/devtools/_ai_work_map_freshness.py`
- `src/sattlint/devtools/_pipeline_cli.py`
- `src/sattlint/devtools/_repo_audit_check_specs.py`
- `src/sattlint/devtools/_repo_audit_entrypoint_runs.py`
- `src/sattlint/devtools/_repo_audit_full_run.py`
- `src/sattlint/devtools/_repo_audit_reporting.py`
- `src/sattlint/devtools/_structural_report_impact.py`
- `src/sattlint/devtools/coordination_lock_state.py`
- `src/sattlint/devtools/fault_injection.py`
- `src/sattlint/devtools/fuzzer.py`
- `src/sattlint/devtools/impact_analyzer.py`
- `src/sattlint/devtools/property_tests.py`
- `src/sattlint/simulation/__init__.py`
- `src/sattlint/simulation/_runtime_models.py`
- `src/sattlint/simulation/runtime.py`

Lane D must not add new debt. If a file is still not clean, leave it out of the strict-list move and reopen the relevant execution lane instead of inventing another exception.

## Plan of Work

Milestone A collects lane handoffs. Do not start editing `pyproject.toml` until lane A, B, and C have each reported their ready-for-adoption file list and any remaining blocker.

Milestone B updates `pyproject.toml`. Add the newly clean inventory files to `tool.pyright.strict` and remove the newly clean touched files from `tool.sattlint.typing_ratchet.debt_allowlist`. Keep the list sorted enough to stay readable, but do not waste time on unrelated formatting.

Milestone C cleans the sparse debt ledger. For any file that truly reached `100%` touched-file proof and no longer carries coverage debt, remove its `coverage` entry from `artifacts/analysis/file_debt_ratchet.json`. If a file still has structural debt above target after the executor lane, keep the structural entry. Do not loosen targets or touch rules.

Milestone D runs the focused ratchet proofs. Start with the ratchet-policy test files, then run the standalone ratchet checker.

Milestone E runs the full pre-push gate. Only after the focused ratchet checks pass should this lane run `sattlint-repo-audit --profile full --check-my-changes --output-dir artifacts/audit`.

## Concrete Steps

Run commands from the repository root.

First focused validation after the first substantive edit:

    python scripts/run_repo_python.py -m pytest --no-cov tests/test_ratchet_policy.py tests/test_ratchet_policy_typing.py -x -q --tb=short

Standalone ratchet proof:

    python scripts/run_repo_python.py scripts/check_ratchet_policy.py

Final closeout gate:

    python scripts/run_repo_python.py -m sattlint.devtools.repo_audit --profile full --check-my-changes --output-dir artifacts/audit

## Validation and Acceptance

Lane D is complete only when all of these are true:

- `pyproject.toml` reflects the newly clean strict files and no touched clean file remains in the debt allowlist,
- `artifacts/analysis/file_debt_ratchet.json` contains no stale coverage entries for files that now have full proof,
- `tests/test_ratchet_policy.py` and `tests/test_ratchet_policy_typing.py` pass,
- `scripts/check_ratchet_policy.py` exits `0`,
- `sattlint-repo-audit --profile full --check-my-changes --output-dir artifacts/audit` exits clean.

## Idempotence and Recovery

Do not remove a debt entry unless a lane has already produced the proof that cleared it. If lane D discovers a file that is still not type-clean or still below `100%` coverage, stop and reopen the owning lane instead of adding a new allowlist entry or rebaseline. If `state_inference.py` is still actively claimed by plan `21-c-022-state-inference.md`, leave that one file out of the strict-list move and capture the dependency explicitly.

## Artifacts and Notes

Record these artifacts as lane D proceeds:

- the exact `pyproject.toml` paths moved into `tool.pyright.strict`,
- the exact debt entries removed from `artifacts/analysis/file_debt_ratchet.json`,
- the passing ratchet-policy test summary,
- the passing `scripts/check_ratchet_policy.py` output,
- the final `artifacts/audit/status.json` path from the full `check-my-changes` run.

## Interfaces and Dependencies

Lane D depends on the executor lanes actually making files clean. It must not invent fresh debt, loosen a ratchet, or rely on an approval record instead of fixing code. Shared files belong here precisely because this is the last mile after the parallel work is ready.
