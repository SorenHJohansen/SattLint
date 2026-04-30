# Coverage Phase 2: App, Devtools, Core

This ExecPlan is a living document. Keep `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` current as work proceeds.

## Purpose / Big Picture

Drain the remaining app, devtools, engine, pipeline, and shell-helper debt that still clusters into about `925` uncovered lines in this bucket after the latest clean shared checkpoint. This plan exists because the app/devtools/core residue is still one of the dominant clusters standing between the repository and `100%` coverage.

## Progress

- [x] (2026-04-30) Create this final-phase plan from the clean shared checkpoint baseline.
- [x] (2026-04-30) Drain the biggest `app_analysis.py` helper residue through `tests/test_app_analysis.py`; file misses fell from `245` to `55`.
- [x] (2026-04-30) Drain the biggest `app_graphics.py` prompt/rule-definition residue through `tests/test_app.py`; file misses fell from `198` to `111`.
- [x] (2026-04-30) Drain the biggest `repo_audit.py` import-graph, architecture, and CLI helper residue through `tests/test_repo_audit.py`; file misses fell from `236` to `134`.
- [x] (2026-04-30) Drain `engine.py` syntax-validation and root-only loader residue through `tests/test_engine.py`; file misses fell from `168` to `138`.
- [x] (2026-04-30) Drain `doc_gardener.py` drift/update/main orchestration through `tests/test_repo_audit.py`; file misses fell from `145` to `99`.
- [x] (2026-04-30) Drain `config.py` validation/loading/target-existence and `self_check()` residue through `tests/test_app.py`; file misses fell from `79` to `29` in the latest trustworthy owner-local probe.
- [x] (2026-04-30) Drain `pipeline.py` summary/invariant helpers through the pipeline owner suites; file misses fell from `95` to `91`.
- [x] (2026-04-30) Further drain `engine.py` lookup/cache, merge, dump, and `_visit()` tail helpers through `tests/test_engine.py`; file misses fell from `138` to `57` in the latest trustworthy owner-local probe.
- [ ] Drain `app_analysis.py`, `app.py`, `app_base.py`, `app_menus.py`, and `app_support.py` through the app owner suites.
- [ ] Drain `app_graphics.py`, `config.py`, `console.py`, and `cache.py` through the nearest existing app, graphics, and config owners.
- [ ] Drain `repo_audit.py` and `doc_gardener.py` through `tests/test_repo_audit.py`.
- [ ] Drain `engine.py` through `tests/test_engine.py`.
- [ ] Drain `pipeline.py` and adjacent pipeline artifact/report seams through the pipeline owner suites.
- [ ] Run the plan-close owner validation set and return control to the orchestrator for another shared checkpoint.

## Context and Orientation

Primary owner suites for this plan:

- `tests/test_app.py`, `tests/test_app_analysis.py`, `tests/test_app_menus.py`, `tests/test_cli.py` -> `src/sattlint/app.py`, `src/sattlint/app_analysis.py`, `src/sattlint/app_base.py`, `src/sattlint/app_graphics.py`, `src/sattlint/app_menus.py`, `src/sattlint/app_support.py`, `src/sattlint/config.py`, `src/sattlint/console.py`, `src/sattlint/cache.py`, `src/sattlint/cli/entry.py`
- `tests/test_repo_audit.py` -> `src/sattlint/devtools/repo_audit.py`, `src/sattlint/devtools/doc_gardener.py`
- `tests/test_engine.py` -> `src/sattlint/engine.py`
- `tests/test_pipeline.py`, `tests/test_pipeline_collection.py`, `tests/test_pipeline_run.py`, `tests/test_pipeline_phase2.py`, `tests/test_artifact_contracts.py`, `tests/test_structural_reports.py` -> `src/sattlint/devtools/pipeline.py`, `src/sattlint/devtools/structural_reports.py`, `src/sattlint/devtools/pipeline_artifacts.py`, adjacent pipeline contract surfaces

Highest remaining files in this plan from the latest trustworthy owner-local and shared-checkpoint data now include `repo_audit.py` (`134`), `app_graphics.py` (`111`), `doc_gardener.py` (`99`), `pipeline.py` (`91`), `engine.py` (`57`), and `app_analysis.py` (`55`). `config.py` is down to `29` misses and is no longer one of the dominant blockers.

## Plan of Work

Slice 1: push the remaining app/app-analysis/app-graphics branches first because they still produce the biggest single-file misses in this plan.

Slice 2: finish repo-audit and doc-gardener helper debt while the owner suite is still warm.

Slice 3: finish engine helper and loader residue through `tests/test_engine.py`.

Slice 4: finish pipeline and structural report debt through the existing pipeline owner suites.

Slice 5: close shell-helper and config long-tail misses only after the dominant files are below `50` misses each.

## Concrete Steps

Run commands from repository root.

Per-slice first validations:

    & ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_app.py tests/test_app_analysis.py tests/test_app_menus.py tests/test_cli.py -x -q --tb=short
    & ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_repo_audit.py -x -q --tb=short
    & ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_engine.py -x -q --tb=short
    & ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_pipeline.py tests/test_pipeline_collection.py tests/test_pipeline_run.py tests/test_pipeline_phase2.py tests/test_artifact_contracts.py tests/test_structural_reports.py -x -q --tb=short

Plan-close validation:

    & ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_app.py tests/test_app_analysis.py tests/test_app_menus.py tests/test_cli.py tests/test_repo_audit.py tests/test_engine.py tests/test_pipeline.py tests/test_pipeline_collection.py tests/test_pipeline_run.py tests/test_pipeline_phase2.py tests/test_artifact_contracts.py tests/test_structural_reports.py -x -q --tb=short

## Validation and Acceptance

This plan is complete when:

- the listed owner suites pass with `--no-cov`,
- the app/devtools/core cluster is no longer one of the two dominant residual buckets in the next shared checkpoint,
- no user-facing app or engine behavior was masked by test-only special casing.

## Idempotence and Recovery

Prefer the existing owner suites and direct helper seams before inventing new app/devtools test modules. If a residual branch belongs more naturally to the orphan plan after a quick search, move the claim there instead of widening this scope indefinitely.

## Surprises & Discoveries

- Observation: the first lane generation closed the easy app/devtools branches, but left the deeper owner seams intact.
  Evidence: `app_analysis.py`, `repo_audit.py`, `app_graphics.py`, and `engine.py` still dominate the remaining backlog.
- Observation: `pipeline.py` already has stable owners and should not be treated as an orphan.
  Evidence: `tests/test_pipeline.py`, `tests/test_pipeline_collection.py`, `tests/test_pipeline_run.py`, and `tests/test_pipeline_phase2.py` already exist.
- Observation: the prompt-heavy app graphics residue is cheap to drain through direct helper tests instead of menu-level flows.
  Evidence: adding focused `tests/test_app.py` prompt/rule-definition cases cut `app_graphics.py` from `198` misses to `111` without production edits.
- Observation: `repo_audit.py` still had a large untested import-graph/architecture seam even though the owner suite was already broad.
  Evidence: focused helper tests cut `repo_audit.py` from `236` misses to `134` in one slice.
- Observation: `doc_gardener.py` still had a cheap orchestration seam even after repo-audit helper coverage landed.
  Evidence: direct `tests/test_repo_audit.py` additions cut `doc_gardener.py` from `145` misses to `99` without production edits.
- Observation: `pipeline.py` still responds well to pure helper tests; summary rollups and invariant printing do not require broader command orchestration.
  Evidence: owner-local helper tests reduced `pipeline.py` from `95` misses to `91` and the full pipeline owner set still passed cleanly.
- Observation: the recurring `.coverage.app-graphics` warning was not a repo code issue; it came from a stale terminal `COVERAGE_FILE` environment variable.
  Evidence: clearing `COVERAGE_FILE=.coverage.app-graphics` removed the coverage-database warning on the next full checkpoint.
- Observation: once the stale coverage env was cleared, the next shared checkpoint blocker moved to an unrelated parser-validation signature mismatch outside this plan.
  Evidence: the checkpoint failed in `tests/test_parser_validation.py::test_validation_internal_validate_sequence_nodes_warns_for_multiple_init_steps` with `_validate_sequence_nodes()` missing keyword-only `label_counts`.
- Observation: `engine.py` still had a large low-risk helper seam below the loader core.
  Evidence: direct owner tests for merge/dump helpers plus `_visit()` and lookup/cache helpers reduced `engine.py` from `138` misses to `57` without production edits.

## Decision Log

- Decision: keep app/devtools and pipeline together in one final-phase plan.
  Rationale: they still form a coherent user-facing and tooling-facing cluster with established owners.
  Date/Author: 2026-04-30 / Copilot (GPT-5.4)

## Outcomes & Retrospective

Current phase-2 execution reduced this plan's biggest files without production changes. Validation totals so far:

- `tests/test_app.py tests/test_app_analysis.py tests/test_app_menus.py tests/test_cli.py -x -q --tb=short` -> `202 passed`
- `tests/test_engine.py -x -q --tb=short` -> `31 passed`
- `tests/test_engine.py -x -q --tb=short` -> `47 passed`
- `tests/test_repo_audit.py -x -q --tb=short` -> `76 passed`
- `tests/test_app.py -x -q --tb=short` -> `100 passed`
- `tests/test_app.py tests/test_app_analysis.py tests/test_app_menus.py tests/test_cli.py -x -q --tb=short` -> `211 passed`
- `tests/test_pipeline_collection.py tests/test_pipeline_run.py -x -q --tb=short` -> `120 passed`
- `tests/test_pipeline.py tests/test_pipeline_collection.py tests/test_pipeline_run.py tests/test_pipeline_phase2.py tests/test_artifact_contracts.py tests/test_structural_reports.py -x -q --tb=short` -> `284 passed`
- Prior plan-close owner set -> `583 passed`
- Shared checkpoint -> `1357 passed, 1 warning`, `86%` total coverage, `3686` misses

Most recent trustworthy follow-up checkpoint data, after clearing stale `COVERAGE_FILE`, keeps this plan active with no coverage-database warning but is blocked by unrelated parser-validation work outside this slice.

The plan remains active because `repo_audit.py`, `app_graphics.py`, `doc_gardener.py`, `pipeline.py`, and the remaining app-shell helpers still dominate the app/devtools/core cluster, even though `engine.py` has now been pushed down to a shorter residual sweep.

## Artifacts and Notes

- Use the orchestrator for shared checkpoint timing and final acceptance.
- Update `.github/coordination/current-work.md` before claiming new source or test files outside the owner set above.

## Interfaces and Dependencies

Preserve console UX, CLI routing, and engine strictness. Favor direct helper tests and focused monkeypatch seams over broader interactive flows.
