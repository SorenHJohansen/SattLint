# Coverage Phase 2: Orphans And Final Gate

This ExecPlan is a living document. Keep `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` current as work proceeds.

## Purpose / Big Picture

Own the files that still block `100%` coverage but do not fit cleanly inside the existing owner-lane structures, then drive the final residual sweep and repository-default acceptance run. This plan exists so the campaign has an explicit owner for the zero-owner modules and the last-mile gate work.

## Progress

- [x] (2026-04-30) Create this final-phase plan from the clean shared checkpoint baseline.
- [x] (2026-04-30) Confirm the nearest owner for each orphan candidate and record when a dedicated suite is justified.
- [x] (2026-04-30) Add dedicated suites for the true zero-owner modules: `accuracy_metrics.py`, `ai_templates.py`, `differential.py`, `mutation_engine.py`, `parser_properties.py`, `production_summary.py`, and `symbolic_lite.py`.
- [x] (2026-05-01) Fold the checked-in `88.26%` coverage floor into the campaign ratchet via `artifacts/analysis/coverage_ratchet.json` and the repository-default pytest gate.
- [ ] Drain the cross-cutting long-tail files that already have owners but no longer justify their own plan, including `validation.py`, `structural_reports.py`, `corpus.py`, and other sub-50 residuals.
- [ ] Run shared checkpoints until no file still carries more than `20` misses.
- [ ] Run repository-default `pytest -q` and do not close this plan until the report shows `100.00%` coverage.

## Context and Orientation

Current orphan or weak-owner files from the clean checkpoint include:

- `src/sattlint/devtools/mutation_engine.py` (`85`)
- `src/sattlint/devtools/parser_properties.py` (`52`)
- `src/sattlint/devtools/production_summary.py` (`50`)
- `src/sattlint/devtools/accuracy_metrics.py` (`48`)
- `src/sattlint/analyzers/symbolic_lite.py` (`48`)
- `src/sattlint/devtools/differential.py` (`37`)
- `src/sattlint/devtools/ai_templates.py` (`28`)

Existing owner suites that this plan may reuse instead of creating new suites when the fit is real:

- `tests/test_corpus.py`, `tests/test_artifact_contracts.py` -> `src/sattlint/devtools/corpus.py`
- `tests/test_pipeline.py`, `tests/test_pipeline_collection.py`, `tests/test_pipeline_run.py`, `tests/test_pipeline_phase2.py`, `tests/test_structural_reports.py` -> `src/sattlint/devtools/structural_reports.py`, adjacent pipeline surfaces
- `tests/test_parser_core.py`, `tests/test_parser_validation.py`, `tests/test_graphics_validation.py`, `tests/test_docgen.py` -> parser, validation, graphics, and docgen long-tail residuals

## Plan of Work

Slice 1: for each orphan candidate, do one quick owner search and either assign it to an existing suite or create a dedicated suite here.

Slice 2: use the new dedicated suites to eliminate the zero-owner modules entirely or push them to single-digit misses.

Slice 3: sweep the remaining sub-50 files by nearest owner, refreshing `htmlcov/status.json` between major closures.

Slice 4: once no file still carries more than `20` misses, switch from cluster plans to the artifact-driven final sweep.

Slice 5: run repository-default `pytest -q`, keep the `88.26%` ratchet green while the final sweep continues, and close only on `100.00%` coverage.

## Concrete Steps

Run commands from repository root.

Per-slice first validations:

    & ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_corpus.py tests/test_artifact_contracts.py tests/test_pipeline.py tests/test_pipeline_collection.py tests/test_pipeline_run.py tests/test_pipeline_phase2.py tests/test_structural_reports.py -x -q --tb=short
    & ".venv/Scripts/python.exe" -m pytest --no-cov <new dedicated orphan suite> -x -q --tb=short
  & ".venv/Scripts/python.exe" -m pytest -q
    & ".venv/Scripts/python.exe" -m pytest -q

## Validation and Acceptance

This plan is complete when:

- every true orphan module has an explicit owner suite,
- the shared miss list no longer has any file above `20` misses,
- repository-default `pytest -q` passes and reports `100.00%` coverage.

## Idempotence and Recovery

Do not create dedicated suites by default. First prove there is no stable existing owner with a quick search. Once a dedicated suite exists here, keep it tight and module-local rather than turning it into another broad catch-all bucket.

## Surprises & Discoveries

- Observation: several modules still blocking `100%` were never assigned to an active lane.
  Evidence: the clean checkpoint still shows multiple zero-owner devtools and analyzer files with material miss counts.
- Observation: the campaign needs a plan that owns the final gate explicitly.
  Evidence: without a dedicated acceptance owner, repository-default `pytest -q` would remain everyone’s responsibility and nobody’s task.
- Observation: the orphan modules were true zero-owner surfaces rather than misrouted existing owner work.
  Evidence: quick search across `tests/**` found no existing references for `accuracy_metrics.py`, `ai_templates.py`, `differential.py`, `mutation_engine.py`, `parser_properties.py`, `production_summary.py`, or `symbolic_lite.py` before adding the dedicated suites.
- Observation: reusing a stale alternate `COVERAGE_FILE` can produce unreadable SQLite coverage state on this machine.
  Evidence: the first narrow rerun against `.coverage.orphans` emitted `no such table: tracer`; a fresh file name restored a clean report.
- Observation: the next shared checkpoint exposed an order-dependent docgen failure that does not reproduce in isolation.
  Evidence: `tests/test_docgen.py::test_classification_and_docgen_final_helper_edges` failed inside the full `pytest -q --cov-fail-under=0` checkpoint (`COVERAGE_FILE=.coverage.exec17-checkpoint-2`) but passed immediately when rerun alone with `--no-cov`.
- Observation: the suspected docgen blocker did not persist after recheck; the next real suite blocker was a stale parser-validation test signature.
  Evidence: targeted reproductions with `tests/test_docgen.py` stayed green, while the fresh shared recheck failed on `tests/test_parser_validation.py::test_validation_internal_validate_sequence_nodes_warns_for_multiple_init_steps` because `_validate_sequence_nodes()` now requires `label_counts`.
- Observation: the shared checkpoint is test-clean again, but coverage report generation is still unstable on this machine.
  Evidence: after fixing the stale parser-validation call, `pytest -q --cov-fail-under=0` reached `1369 passed, 1 warning`, but `pytest-cov` emitted `CoverageWarning` failures against the fresh `.coverage.exec17-docgen-recheck-2` database (`no such table: tracer` / `line_bits`).
- Observation: the repo now has a real checked-in coverage ratchet instead of only a historical integer floor.
  Evidence: `artifacts/analysis/coverage_ratchet.json` captures the current `88.26%` baseline and repository-default `pytest -q` now enforces the same threshold through `--cov-fail-under=88.26`.

## Decision Log

- Decision: put the orphan modules and the final acceptance gate in one explicit plan.
  Rationale: reaching `100%` requires both dedicated ownership for uncovered outliers and a named owner for the default gate.
  Date/Author: 2026-04-30 / Copilot (GPT-5.4)
- Decision: keep orphan ownership split into one devtools suite and one `symbolic_lite` suite.
  Rationale: the devtools helpers share lightweight report-building patterns, while `symbolic_lite.py` is an analyzer surface and stays clearer as its own owner suite.
  Date/Author: 2026-04-30 / Copilot (GPT-5.4)

## Outcomes & Retrospective

Plan created from the clean `82.35%` checkpoint.

2026-04-30 orphan-slice checkpoint:

- Owner search confirmed no stable existing test owner for the orphan modules, so dedicated suites were justified.
- Added `tests/test_devtools_orphans.py` for `accuracy_metrics.py`, `ai_templates.py`, `differential.py`, `mutation_engine.py`, `parser_properties.py`, and `production_summary.py`.
- Added `tests/test_symbolic_lite.py` for `src/sattlint/analyzers/symbolic_lite.py`.
- Focused validation passed: `& ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_devtools_orphans.py tests/test_symbolic_lite.py -x -q --tb=short` -> `12 passed`.
- Fresh shared checkpoint passed: `& ".venv/Scripts/python.exe" -m pytest -q --cov-fail-under=0` with `COVERAGE_FILE=.coverage.orphans-final` -> `1272 passed, 1 warning` and `TOTAL 27153 / 4171 missing / 85%`.
- Orphan-module result from the fresh checkpoint: `accuracy_metrics.py`, `ai_templates.py`, `differential.py`, `mutation_engine.py`, `parser_properties.py`, `production_summary.py`, and `symbolic_lite.py` all reached `100%`.
- Remaining blockers for this plan are no longer the zero-owner files; they are the long-tail owner surfaces, currently led by `validation.py` (`30` misses), `structural_reports.py` (`44` misses), and `corpus.py` (`41` misses), plus the unfinished repository-default `pytest -q` acceptance gate.

2026-04-30 long-tail progress after the orphan closure:

- Expanded `tests/test_parser_validation.py` with helper-level owner coverage for the remaining `validation.py` branches; focused validation passed at `87 passed`.
- Expanded `tests/test_structural_reports.py` in two slices covering metadata drift findings, workspace-graph helper paths, report builders, graphics serialization, recursive moduletype layout walking, and both `collect_structural_reports()` graph-input branches; focused validation now passes at `22 passed`.
- Fresh shared checkpoint with `COVERAGE_FILE=.coverage.exec17-checkpoint-2` reached `1334 passed, 1 failed, 1 warning` and `TOTAL 27153 / 3766 missing / 86%`.
- Shared-checkpoint file results from that run: `src/sattlint/validation.py` reached `100%`, `src/sattlint/devtools/structural_reports.py` dropped to `97%` (`15` misses before the last owner-suite slice), and `src/sattlint/devtools/corpus.py` remains at `85%` (`41` misses).
- The current acceptance blocker is not yet the coverage residual alone: the shared checkpoint failed on `tests/test_docgen.py::test_classification_and_docgen_final_helper_edges`, but that test passed in immediate isolated rerun, so the suite now has an order-dependent docgen blocker in addition to the remaining coverage work.

2026-04-30 suite-blocker recheck:

- Reproductions against `tests/test_docgen.py` showed that the suspected order-dependent docgen failure no longer reproduced, including targeted predecessor slices and isolated coverage runs.
- Fresh shared checkpoint recheck with `COVERAGE_FILE=.coverage.exec17-docgen-recheck` showed the actual blocker was `tests/test_parser_validation.py::test_validation_internal_validate_sequence_nodes_warns_for_multiple_init_steps`: the helper test had not been updated after `_validate_sequence_nodes()` added the required keyword-only `label_counts` argument.
- Updated `tests/test_parser_validation.py` to pass `label_counts={}` and revalidated that owner suite: `90 passed`.
- Follow-up shared checkpoint with `COVERAGE_FILE=.coverage.exec17-docgen-recheck-2` reached `1369 passed, 1 warning`; the suite is test-clean again.
- The remaining checkpoint problem is operational rather than behavioral: `pytest-cov` still intermittently corrupts the fresh coverage SQLite database on this Windows machine, so the run completed without a trustworthy coverage table despite the clean test result.

## Artifacts and Notes

- Refresh `coverage.xml` and `htmlcov/status.json` after each meaningful orphan closure.
- Record dedicated-suite justifications in this file so they are discoverable after the campaign ends.

## Interfaces and Dependencies

Keep the orphan suites tight, factual, and module-local. The goal is to finish the campaign, not create a second permanent testing architecture by accident.
