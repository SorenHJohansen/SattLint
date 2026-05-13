# T-Wave-4 Repo-Audit Decomposition

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

## Purpose / Big Picture

This plan closes the remaining structural work in T-019. The first phase of the split already landed, but `src/sattlint/devtools/repo_audit.py` still exceeds its structural target and still centralizes compatibility exports plus orchestration wiring that belong in smaller owner modules. After this work lands, `repo_audit.py` will be a thin compatibility and entry surface under 500 lines, while orchestration, ledger, leak-detection, and entrypoint logic stay in their dedicated modules without changing user-facing commands or artifact contracts.

## Progress

- [x] (2026-05-13) Create the ExecPlan and confirm `audit_core.py`, `ledger.py`, and `leak_detection.py` already exist, while `src/sattlint/devtools/repo_audit.py` is still 556 lines and ratcheted `must_shrink`, and the repository already has an existing `src/sattlint/devtools/audit_orchestration.py` seam that owns part of the full-run flow.
- [ ] Move the remaining orchestration and compatibility wiring out of `repo_audit.py` into the closest existing helper modules.
- [ ] Reduce `repo_audit.py` below the structural target without changing `sattlint-repo-audit` behavior or artifact formats.
- [ ] Add or adjust focused tests if exports or helper ownership move, then rerun the narrow repo-audit slice.

## Surprises & Discoveries

Observation: the structural split is already halfway complete.
Evidence: `src/sattlint/devtools/repo_audit.py` already imports `audit_core`, `ledger`, `leak_detection`, `repo_audit_entrypoints`, and `audit_orchestration` rather than owning every helper inline.

Observation: the remaining debt is concentrated in wrapper and export wiring, not in one missing helper extraction.
Evidence: the tail of `repo_audit.py` is now mostly compatibility constants and the large argument-forwarding call into `_audit_orchestration_module.audit_repository(...)`.

Observation: the repo already has an orchestration seam that should be reused before any new file is added.
Evidence: `src/sattlint/devtools/audit_orchestration.py` already owns harness-freshness conversion and the main `audit_repository(...)` flow.

## Decision Log

Decision: finish the split by extending existing helper modules before creating any new registry or artifact surface.
Rationale: repo-audit instructions explicitly prefer extending existing devtools seams and keeping outputs machine-readable and stable.
Date/Author: 2026-05-13 / Copilot (GPT-5.4)

Decision: treat `repo_audit.py` as the compatibility shell and public export surface only.
Rationale: the remaining debt is structural concentration. The fastest clear end state is a thin public wrapper over smaller owner modules.
Date/Author: 2026-05-13 / Copilot (GPT-5.4)

Decision: preserve all current `sattlint-repo-audit` behavior, check catalogs, and artifact names while shrinking the owner file.
Rationale: this debt item is a decomposition, not a behavior change. Changing the CLI or artifact contracts would make the structural work harder to validate.
Date/Author: 2026-05-13 / Copilot (GPT-5.4)

## Outcomes & Retrospective

Planning baseline only. T-019 is no longer a full monolith split from scratch; it is now a second-phase shrink and ownership pass that must finish without reopening artifact drift.

## Context and Orientation

The public owner file is `src/sattlint/devtools/repo_audit.py`. It still defines public constants, compatibility exports, thin write helpers, and the final wrapper around the full audit run. `artifacts/analysis/file_debt_ratchet.json` marks it `must_shrink` with a structural target of 500 lines.

The nearest extraction seams already exist. `src/sattlint/devtools/audit_orchestration.py` owns the main full-run flow. `src/sattlint/devtools/ledger.py` owns report writing and run-history helpers. `src/sattlint/devtools/leak_detection.py` owns text scanning and leak-detection helpers. `src/sattlint/devtools/repo_audit_entrypoints.py` owns runnable check routing and catalog behavior. Reuse those before inventing new modules.

The nearest tests are `tests/test_repo_audit.py`, `tests/test_repo_audit_cli.py`, and `tests/test_repo_audit_entrypoints_verify.py`. Because repo-audit outputs are point-in-time snapshots, any narrow behavior change should be validated first by tests and only then by regenerated artifacts.

## Plan of Work

Start by identifying the remaining code in `repo_audit.py` that is not genuinely public compatibility surface. Move full-run argument assembly and reusable wrappers into `audit_orchestration.py` where that ownership already exists. Move any remaining write or mirror helpers into `ledger.py` if they belong to report writing, or into `repo_audit_shared.py` if they are pure constants or small shared utilities.

Keep `repo_audit.py` as the compatibility module that re-exports public constants and entry points, and that preserves imports used elsewhere in the repository. If a helper move would break existing imports, leave a thin forwarding function or re-export instead of forcing a wide rename in the same slice.

Once the wrapper file is below the ratchet target, stop. If `audit_core.py` or `leak_detection.py` still look large after the extraction, record that as follow-on debt only if it blocks the `repo_audit.py` shrink goal. T-019 is complete when the public owner file is thin and behavior stays stable.

## Concrete Steps

Run all commands from the repository root.

Inspect the current split and the ratcheted owner before editing code:

    wc -l src/sattlint/devtools/repo_audit.py src/sattlint/devtools/audit_core.py src/sattlint/devtools/ledger.py src/sattlint/devtools/leak_detection.py
    rg -n "audit_orchestration|ledger|leak_detection|repo_audit_entrypoints" src/sattlint/devtools/repo_audit.py

After shrinking `repo_audit.py`, run the narrow validation first:

    python scripts/run_repo_python.py -m pytest --no-cov tests/test_repo_audit.py tests/test_repo_audit_cli.py tests/test_repo_audit_entrypoints_verify.py -x -q --tb=short

Run touched-file quality gates after the focused tests pass:

    python scripts/run_repo_python.py -m ruff check src/sattlint/devtools/repo_audit.py src/sattlint/devtools/audit_orchestration.py src/sattlint/devtools/ledger.py src/sattlint/devtools/repo_audit_shared.py tests/test_repo_audit.py tests/test_repo_audit_cli.py tests/test_repo_audit_entrypoints_verify.py
    python scripts/run_repo_python.py -m pyright src/sattlint/devtools/repo_audit.py src/sattlint/devtools/audit_orchestration.py src/sattlint/devtools/ledger.py src/sattlint/devtools/repo_audit_shared.py

## Validation and Acceptance

Acceptance requires three things. `src/sattlint/devtools/repo_audit.py` must shrink below 500 lines. The focused repo-audit tests must continue to pass. The public CLI and machine-readable artifact names must stay stable, including `--list-checks` behavior and the existing report filenames under the audit output directory.

## Idempotence and Recovery

This plan is safe to land as a shrink-only refactor. Move one helper cluster at a time, rerun the same focused test slice, and leave thin compatibility exports behind if moving a symbol would widen scope. Do not regenerate full-profile audit artifacts until the narrow tests pass, because those artifacts are snapshots and should not drive the refactor.

## Artifacts and Notes

Record one short before-and-after line-count artifact for `repo_audit.py`, plus a focused pytest summary. If any compatibility re-exports are kept intentionally, note them here so future cleanups do not remove them blindly.

## Interfaces and Dependencies

The implementation surface is `src/sattlint/devtools/repo_audit.py`, with preferred extraction seams in `src/sattlint/devtools/audit_orchestration.py`, `src/sattlint/devtools/ledger.py`, `src/sattlint/devtools/repo_audit_shared.py`, and `src/sattlint/devtools/repo_audit_entrypoints.py`. Keep outputs machine-readable and actionable, and do not add parallel registries or new artifact formats.
