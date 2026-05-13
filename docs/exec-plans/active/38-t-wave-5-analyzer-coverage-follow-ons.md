# T-Wave-5 Analyzer Coverage Follow-Ons

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

## Purpose / Big Picture

This plan closes T-017 using the repository as it exists now, not the stale “38 analyzer modules” count from the old tracker text. After this work lands, the remaining legacy analyzer owner files will each have dedicated focused tests instead of depending mostly on omnibus suites, and touched-file coverage ratchets will be satisfiable through owner-local proof instead of broad incidental coverage. The observable proof is a new set of `tests/analyzers/test_<owner>.py` modules plus focused pytest and coverage proof for each batch.

## Progress

- [x] (2026-05-13) Create the ExecPlan and inventory the current dedicated-test gaps. `tests/analyzers/` already covers most new analyzers, but legacy owner files such as `alarm_integrity`, `cyclomatic_complexity`, `icf`, `initial_values`, `layout_geometry`, `loop_output_refactor`, `mms`, `modules`, `naming`, `parameter_drift`, `reset_contamination`, `safety_paths`, `scan_loop_resource_usage`, `shadowing`, `taint_paths`, and `unsafe_defaults` still lack one-file dedicated owner tests.
- [ ] Land batch 1 dedicated tests for the policy and naming analyzers.
- [ ] Land batch 2 dedicated tests for the structural and interface analyzers.
- [ ] Land batch 3 dedicated tests for the path, reset, and resource analyzers.
- [ ] Run focused pytest and touched-file coverage proof for each batch before widening scope.

## Surprises & Discoveries

Observation: the tracker’s original 38-module count is stale.
Evidence: the repository now has a large `tests/analyzers/` surface covering newer analyzers such as `config_drift`, `fault_handling`, `numeric_constraints`, `powerup`, `scan_concurrency`, `signal_lifecycle`, `timing`, and others that did not exist when the debt row was written.

Observation: raw coverage inventories also include helper files that are not analyzer-owner debts.
Evidence: files such as `framework.py`, `issue.py`, `registry.py`, `usage_tracker.py`, and `validators.py` appear in broad coverage outputs, but they are support modules rather than analyzer owner surfaces and should not drive this plan.

Observation: several legacy analyzers already have meaningful indirect coverage, but not dedicated owner tests.
Evidence: `artifacts/analysis/pytest.json` shows nonzero coverage for multiple legacy analyzers while their behavior is still exercised mainly through omnibus files such as `tests/test_analyzers_suites.py`.

## Decision Log

Decision: count only analyzer owner files in this plan, not helper or registry modules.
Rationale: T-017 is about missing dedicated analyzer tests. Helper coverage is a separate concern and would make this plan unmanageably broad.
Date/Author: 2026-05-13 / Copilot (GPT-5.4)

Decision: land the coverage work in domain batches rather than one giant test-only change.
Rationale: focused pytest and touched-file coverage proof stay tractable when each batch covers related analyzers and reuses nearby fixtures.
Date/Author: 2026-05-13 / Copilot (GPT-5.4)

Decision: reuse existing fixtures and broad-suite assertions before adding new scaffolding.
Rationale: repository policy prefers existing helpers and deterministic assertions over parallel fixture trees or snapshot-heavy tests.
Date/Author: 2026-05-13 / Copilot (GPT-5.4)

## Outcomes & Retrospective

Planning baseline only. The repository is no longer missing dedicated tests for every legacy analyzer, but it still has a meaningful set of older owner files that rely too heavily on omnibus suites.

## Context and Orientation

The dedicated analyzer-test home is `tests/analyzers/`. Modern analyzers already use compact, owner-local files there. Historical coverage still lives in `tests/test_analyzers_suites.py`, `tests/test_analyzers_state.py`, `tests/test_analyzers_variables.py`, and related split files. Those broad suites remain valuable for integration behavior, but they do not satisfy the debt item’s goal of one focused owner surface per analyzer.

The current uncovered owner inventory for this plan is: `alarm_integrity.py`, `cyclomatic_complexity.py`, `icf.py`, `initial_values.py`, `layout_geometry.py`, `loop_output_refactor.py`, `mms.py`, `modules.py`, `naming.py`, `parameter_drift.py`, `reset_contamination.py`, `safety_paths.py`, `scan_loop_resource_usage.py`, `shadowing.py`, `taint_paths.py`, and `unsafe_defaults.py`. Keep this list up to date as dedicated tests land.

Several of these files are coverage-ratcheted. That means a touched analyzer file must reach full-file proof when edited, not just a new smoke test. This plan therefore needs both focused owner tests and batch-specific coverage proof for the touched analyzers.

## Plan of Work

Land batch 1 first: `alarm_integrity`, `naming`, `parameter_drift`, `shadowing`, and `unsafe_defaults`. These analyzers are high-signal, mostly finding-oriented, and can reuse patterns already present in `tests/analyzers/test_rule_profiles.py`, `tests/analyzers/test_spec_compliance.py`, and the legacy omnibus suites.

Land batch 2 next: `icf`, `initial_values`, `layout_geometry`, `loop_output_refactor`, `modules`, and `mms`. These analyzers are more structural and interface-oriented, so keep assertions deterministic on rule ids, report fragments, or specific findings rather than on large snapshots.

Land batch 3 last: `safety_paths`, `scan_loop_resource_usage`, `taint_paths`, `reset_contamination`, and `cyclomatic_complexity`. Reuse the existing path and graph fixtures where possible so the new tests do not duplicate large fixture setup.

Do not broaden this plan into helper-module coverage. If a helper file still lacks direct proof after the analyzer-owner tests land, record that as follow-on work instead of derailing this slice.

## Concrete Steps

Run all commands from the repository root.

Inspect the current analyzer-test inventory before starting each batch:

    rg --files tests/analyzers | sort
    rg --files src/sattlint/analyzers | sort

After implementing batch 1, run the narrow validation first:

    python scripts/run_repo_python.py -m pytest --no-cov tests/analyzers/test_alarm_integrity.py tests/analyzers/test_naming.py tests/analyzers/test_parameter_drift.py tests/analyzers/test_shadowing.py tests/analyzers/test_unsafe_defaults.py -x -q --tb=short

After implementing batch 2, run the next narrow slice:

    python scripts/run_repo_python.py -m pytest --no-cov tests/analyzers/test_icf.py tests/analyzers/test_initial_values.py tests/analyzers/test_layout_geometry.py tests/analyzers/test_loop_output_refactor.py tests/analyzers/test_modules.py tests/analyzers/test_mms.py -x -q --tb=short

After implementing batch 3, run the final narrow slice:

    python scripts/run_repo_python.py -m pytest --no-cov tests/analyzers/test_safety_paths.py tests/analyzers/test_scan_loop_resource_usage.py tests/analyzers/test_taint_paths.py tests/analyzers/test_reset_contamination.py tests/analyzers/test_cyclomatic_complexity.py -x -q --tb=short

After each batch’s no-coverage proof passes, rerun the same batch with touched-file coverage or use `sattlint-repo-audit --check-my-changes` so touched ratcheted files satisfy the full-file coverage requirement.

## Validation and Acceptance

Acceptance requires a dedicated owner test file for every analyzer in the current inventory, plus focused pytest proof that those owner tests pass. For analyzers that are coverage-ratcheted, acceptance also requires touched-file coverage proof rather than only `--no-cov` smoke validation. Broad suites may remain, but they no longer count as the only proof for these owners.

## Idempotence and Recovery

This plan is safe to execute batch by batch. If one analyzer proves noisy, stabilize that owner test locally before adding the next module. Reuse existing fixtures and helpers whenever possible; do not fork the same sample programs into a second test-fixture tree. If a batch grows too wide, split it here before continuing.

## Artifacts and Notes

Record one focused pytest summary and one coverage-proof command per batch. Keep the inventory paragraph in `Context and Orientation` current as each dedicated test file lands so the next executor can resume from this plan alone.

## Interfaces and Dependencies

The implementation surface is the legacy analyzer owner files listed in this plan plus new focused files under `tests/analyzers/`. Reuse existing test helpers, corpus fixtures, and nearby broad suites for fixture setup and expected findings. Keep assertions deterministic on explicit fields, issue ids, or summary fragments.
