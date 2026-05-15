# T-Wave-6 Pipeline and Audit Catalog Extraction

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

## Purpose / Big Picture

This plan addresses the highest-value devtools debt from the 2026-05-15 architecture review. Today, `src/sattlint/devtools/pipeline.py` and `src/sattlint/devtools/repo_audit_entrypoints.py` still centralize check catalogs, stage orchestration, finish-gate planning, and terminal reporting in very large owner files. After this work lands, the pipeline and repo-audit entrypoints will still expose the same user-facing commands and machine-readable artifacts, but the large catalogs and control-flow assembly will live in smaller helper modules that are safer to change.

The observable proof is straightforward. `bash scripts/run_repo_python.sh -m sattlint.devtools.pipeline --profile quick --output-dir artifacts/audit-plan-smoke` must still emit the same core JSON artifacts, and `bash scripts/run_repo_python.sh -m sattlint.devtools.repo_audit --profile quick --list-checks` must still list the same repo-audit checks, while the long owner functions shrink and the focused tests stay green.

## Progress

- [x] (2026-05-15) Create the ExecPlan and confirm `src/sattlint/devtools/pipeline.py` is 1898 lines, `src/sattlint/devtools/repo_audit_entrypoints.py` is 1114 lines, and `artifacts/audit-full-current/pipeline/architecture.json` flags `pipeline.main` and `_repo_audit_finding_check_definitions` as over-budget functions.
- [ ] Extract the repo-audit finding-check catalog, finish-gate recommendation builders, and adjacent helper tables into smaller helper modules or declarative data files, leaving `repo_audit_entrypoints.py` as a thin coordination and reporting surface.
- [ ] Extract pipeline stage assembly, tool-status aggregation, and failure-artifact writing out of `pipeline.py` into the existing `_pipeline_*` helper family or new sibling helpers, reducing `main()` to argument parsing and coordinator dispatch.
- [ ] Split or tighten the adjacent pipeline and repo-audit tests so the catalog and recommendation behavior can be validated without routing every change through the largest integration files.
- [ ] Rerun focused pytest, then touched-file Ruff and Pyright, and finally one quick-profile CLI smoke check that proves the artifacts and check listings stayed stable.

## Surprises & Discoveries

Observation: the repository already has several extraction seams for this work.
Evidence: `src/sattlint/devtools/pipeline.py` already imports `_pipeline_cli`, `_pipeline_execution`, `_pipeline_finish_gate`, `_pipeline_optional_reports_helpers`, and `_pipeline_parsing_helpers`, so the next shrink step should reuse those seams instead of inventing parallel orchestration code.

Observation: the main debt is concentrated in data-heavy builders and reporting glue, not in one hidden algorithm.
Evidence: the architecture report flags `_repo_audit_finding_check_definitions`, `run_recommended_repo_audit_slice`, and `pipeline.main` as oversized, and those functions mostly assemble catalogs, commands, and report payloads.

Observation: the repo-audit and pipeline surfaces share the same stability constraint.
Evidence: both files feed machine-readable artifacts and focused tests such as `tests/test_pipeline_run_recommendations.py` and `tests/test_repo_audit_entrypoints_verify.py`, so behavior drift would be easy to detect and expensive to repair after a broad rewrite.

## Decision Log

Decision: treat static catalogs and recommendation tables as extraction targets before changing runtime control flow.
Rationale: large declarative tuples and dictionaries are the easiest debt to move without changing behavior, and they currently dominate the over-budget functions.
Date/Author: 2026-05-15 / Copilot (GPT-5.4)

Decision: reuse the existing `_pipeline_*` helper family and repo-audit planning helpers before creating new public modules.
Rationale: the repository already established those seams as the preferred place for devtools decomposition, so extending them is lower risk than inventing a second control surface.
Date/Author: 2026-05-15 / Copilot (GPT-5.4)

Decision: keep artifact filenames, check ids, and CLI output contracts stable throughout the split.
Rationale: this is structural debt work, not a product change. The safest proof is that artifacts and check listings remain byte-for-byte compatible where existing tests already pin them.
Date/Author: 2026-05-15 / Copilot (GPT-5.4)

## Outcomes & Retrospective

At creation time, no code has landed yet. The current outcome is a scoped decomposition plan that isolates the largest devtools control surfaces into a validation-first slice instead of treating the whole audit stack as one rewrite.

## Context and Orientation

The main pipeline owner is `src/sattlint/devtools/pipeline.py`. It is the repeatable static-analysis pipeline that runs Ruff, Pyright, pytest, optional reports, structural reports, and final artifact writing. The file already delegates some work to sibling helpers, but it still owns large sections for stage execution, tool-status assembly, counts, failure handling, and the top-level CLI entrypoint.

The repo-audit owner is `src/sattlint/devtools/repo_audit_entrypoints.py`. It owns the selected-check catalog, recommendation planning, finish-gate command building, CLI summary formatting, and the `run_check_my_changes` flow. In this repository, a "catalog" is the static list of checks and their metadata, such as ids, path globs, owner tests, and instructional metadata. A "finish gate" is the recommended validation sequence that proves a change is safe to merge.

The closest tests are `tests/test_pipeline.py`, `tests/test_pipeline_run.py`, `tests/test_pipeline_collection.py`, `tests/test_pipeline_collection_graphs.py`, `tests/test_pipeline_run_recommendations.py`, `tests/test_repo_audit_entrypoints_helpers.py`, `tests/test_repo_audit_entrypoints_finish_gate.py`, `tests/test_repo_audit_entrypoints_verify.py`, and `tests/test_repo_audit_cli.py`. Keep validation focused there before widening to full audit runs.

## Plan of Work

Start with `src/sattlint/devtools/repo_audit_entrypoints.py`, because its largest function is mostly catalog data. Move the static finding-check definitions into a new helper such as `src/sattlint/devtools/_repo_audit_check_catalog.py`, and move finish-gate wording plus step-planning helpers into either `src/sattlint/devtools/_repo_audit_finish_gate_helpers.py` or the existing planning-helper seam if that file already fits. Leave the public entry functions in place so external callers and tests keep patching the same surface.

Then shrink `src/sattlint/devtools/pipeline.py` by moving the data-heavy tool-status assembly into a new helper such as `src/sattlint/devtools/_pipeline_status_assembly.py`, and by moving failure-artifact writing into a helper such as `src/sattlint/devtools/_pipeline_failure_outputs.py` if the existing `_pipeline_*` modules do not already own that behavior cleanly. Reuse the existing `_pipeline_finish_gate.py` and `_pipeline_optional_reports_helpers.py` seams when they already own nearby behavior. Avoid adding a second coordinator or changing the `main(argv)` contract; the goal is a thinner owner file, not a new CLI.

Split the adjacent tests only when it lowers validation cost for the new seams. If new pure helpers are created, add focused tests such as `tests/test_repo_audit_check_catalog.py` for the repo-audit catalog and `tests/test_pipeline_status_assembly.py` for status or count assembly instead of continuing to route every edit through the heaviest integration test.

## Concrete Steps

Run all commands from the repository root.

Inspect the current oversized owners before editing code:

    wc -l src/sattlint/devtools/pipeline.py src/sattlint/devtools/repo_audit_entrypoints.py
    rg -n "def main|_build_.*tool_status|_repo_audit_finding_check_definitions|run_check_my_changes|run_recommended_repo_audit_slice" src/sattlint/devtools/pipeline.py src/sattlint/devtools/repo_audit_entrypoints.py

After extracting the repo-audit catalog and pipeline assembly helpers, run the narrow validation first:

    bash scripts/run_repo_python.sh -m pytest --no-cov tests/test_pipeline.py tests/test_pipeline_run.py tests/test_pipeline_collection.py tests/test_pipeline_collection_graphs.py tests/test_pipeline_run_recommendations.py tests/test_repo_audit_entrypoints_helpers.py tests/test_repo_audit_entrypoints_finish_gate.py tests/test_repo_audit_entrypoints_verify.py tests/test_repo_audit_cli.py -x -q --tb=short

Run touched-file quality gates after the focused tests pass:

    bash scripts/run_repo_python.sh -m ruff check src/sattlint/devtools/pipeline.py src/sattlint/devtools/repo_audit_entrypoints.py src/sattlint/devtools/_pipeline_cli.py src/sattlint/devtools/_pipeline_finish_gate.py src/sattlint/devtools/_pipeline_optional_reports_helpers.py src/sattlint/devtools/_pipeline_execution.py src/sattlint/devtools/_pipeline_status_assembly.py src/sattlint/devtools/_pipeline_failure_outputs.py src/sattlint/devtools/_repo_audit_check_catalog.py src/sattlint/devtools/_repo_audit_finish_gate_helpers.py
    bash scripts/run_repo_python.sh -m pyright src/sattlint/devtools/pipeline.py src/sattlint/devtools/repo_audit_entrypoints.py src/sattlint/devtools/_pipeline_cli.py src/sattlint/devtools/_pipeline_finish_gate.py src/sattlint/devtools/_pipeline_optional_reports_helpers.py src/sattlint/devtools/_pipeline_execution.py src/sattlint/devtools/_pipeline_status_assembly.py src/sattlint/devtools/_pipeline_failure_outputs.py src/sattlint/devtools/_repo_audit_check_catalog.py src/sattlint/devtools/_repo_audit_finish_gate_helpers.py

Finish with one CLI smoke check that proves contracts stayed stable:

    bash scripts/run_repo_python.sh -m sattlint.devtools.pipeline --profile quick --output-dir artifacts/audit-plan-smoke
    bash scripts/run_repo_python.sh -m sattlint.devtools.repo_audit --profile quick --list-checks

## Validation and Acceptance

Acceptance requires stable behavior and smaller control surfaces. The pipeline must still write the same status, summary, findings, and tool-report artifacts for the selected profile. Repo-audit must still expose the same check ids, recommendation behavior, and `--list-checks` output. Focused pipeline and repo-audit tests must pass, and the extracted helpers must make the long owner functions materially smaller instead of moving complexity sideways into one equally large replacement file.

## Idempotence and Recovery

This plan is safe to execute in small slices. Move one catalog or helper cluster at a time, rerun the same focused tests, and leave thin compatibility wrappers behind if a test or external import still patches the old module-level name. If a quick-profile smoke run produces different artifact names or different check ids, revert that local extraction before continuing.

## Artifacts and Notes

Current owner sizes at plan creation time:

    1898 src/sattlint/devtools/pipeline.py
    1114 src/sattlint/devtools/repo_audit_entrypoints.py

Current over-budget functions called out by the architecture report include:

    src/sattlint/devtools/pipeline.py:main
    src/sattlint/devtools/repo_audit_entrypoints.py:_repo_audit_finding_check_definitions
    src/sattlint/devtools/repo_audit_entrypoints.py:run_recommended_repo_audit_slice

## Interfaces and Dependencies

The implementation surface is `src/sattlint/devtools/pipeline.py`, `src/sattlint/devtools/repo_audit_entrypoints.py`, and the existing helper family under `src/sattlint/devtools/_pipeline_*`. Preserve the current `sattlint.devtools.pipeline` and `sattlint.devtools.repo_audit` CLI entrypoints, the existing JSON artifact contracts, and the current repo-audit check ids.
