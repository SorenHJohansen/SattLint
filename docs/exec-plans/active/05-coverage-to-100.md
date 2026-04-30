# Coverage To 100 Percent

This ExecPlan is the active orchestrator for the last push to full coverage. The sections `Progress`, `Current Baseline`, `Decision Log`, and `Outcomes & Retrospective` must stay current as the remaining plans are worked.

## Purpose / Big Picture

The first coverage-lane generation is finished. Lane A, lane B, and lane C all closed their planned owner work and are now archive material, and the latest clean shared checkpoint has moved the repository to about `87%` coverage. This file now coordinates the final-phase split that is explicitly designed to eliminate the remaining `3505` uncovered lines and reach a clean repository-default `pytest -q` run at `100.00%` coverage.

## Progress

- [x] (2026-04-29) Establish the coverage campaign and prove the full suite is functionally green under `--cov-fail-under=0`.
- [x] (2026-04-30) Execute and close the first lane generation: app/devtools/docgen/engine, analyzers/semantic/LSP, and parser/reporting/GUI.
- [x] (2026-04-30) Refresh the shared checkpoint from a clean `.coverage` state and confirm the current baseline at `1236 passed, 1 warning`.
- [x] (2026-04-30) Retire the stale lane-A/B/C active split and replace it with final-phase plans keyed to the remaining coverage clusters.
- [x] (2026-04-30) Refresh the shared checkpoint again after ExecPlan 16 closeout from a clean `.coverage` state and confirm the new residual ordering at `1272 passed, 1 warning`.
- [x] (2026-04-30) Reopen the ExecPlan 16 docgen seam, drive `classification.py` and `docgen.py` to `100%` through `tests/test_docgen.py`, and refresh the shared checkpoint again at `1342 passed, 1 warning`.
- [ ] Drain the final-phase app/devtools/core cluster.
- [ ] Drain the final-phase analyzers/semantic/LSP cluster.
- [ ] Drain the final-phase parser/GUI/reporting/docgen cluster.
- [ ] Drain the orphan zero-owner modules and remaining cross-cutting residuals.
- [ ] Complete the shared residual sweep once no file still carries more than `20` misses.
- [ ] Run repository-default `pytest -q` and hit `100.00%` coverage.
- [ ] Move this orchestrator and the final-phase child plans to `docs/exec-plans/completed/` once the default gate passes.

## Current Baseline

- Full suite state: `Remove-Item -Force .coverage* -ErrorAction SilentlyContinue ; & ".venv/Scripts/python.exe" -m pytest -q --cov-fail-under=0` is clean at `1342 passed, 1 warning`.
- Coverage baseline: `coverage.xml` now reports `87.1%` line coverage with `3505` uncovered lines.
- Dominant remaining file misses: `reset_contamination.py` (`241`), `modules.py` (`200`), `engine.py` (`138`), `repo_audit.py` (`134`), `variables.py` (`117`), `app_graphics.py` (`111`), `dataflow.py` (`106`), `mms.py` (`102`), `doc_gardener.py` (`99`), `pipeline.py` (`95`), `core/semantic.py` (`87`), `_variables_effect_flow.py` (`85`), `config.py` (`79`), `_server_document.py` (`76`), and `_server_helpers.py` (`58`).
- Final-phase planning buckets from the clean checkpoint table:
  - App/devtools/core cluster: about `1061` misses.
  - Analyzers/semantic/LSP cluster: about `2122` misses.
  - Parser/GUI/reporting/docgen cluster: about `422` misses.
  - Orphan and residual sweep cluster: about `109` misses.
- The parser/GUI/reporting/docgen bucket is still the clear third-largest residual bucket under the current phase-2 mapping, but the reopened docgen seam no longer contributes to it.
- The earlier zero-owner devtools and analyzer outliers are no longer the main blockers. Current orphan and residual work is concentrated in `validation.py` (`30`), `_validation_expression.py` (`22`), `_validation_type_helpers.py` (`21`), and `utils/text_processing.py` (`15`).
- `covtest.txt` is historical only. Use `coverage.xml` and `htmlcov/status.json` as the source of truth for what remains.

## Final-Phase Plans

- `docs/exec-plans/completed/11-coverage-lane-a-app-devtools-engine.md`
  Status: completed.
  Scope: first-generation app/devtools/docgen/engine lane.
- `docs/exec-plans/completed/12-coverage-lane-b-analyzers-semantic-lsp.md`
  Status: completed.
  Scope: first-generation analyzers/semantic/LSP lane.
- `docs/exec-plans/completed/13-coverage-lane-c-parser-reporting-gui.md`
  Status: completed.
  Scope: first-generation parser/reporting/GUI lane.
- `docs/exec-plans/active/14-coverage-phase-2-app-devtools-core.md`
  Status: active.
  Scope: remaining app, devtools, engine, pipeline, and shell-helper debt.
- `docs/exec-plans/active/15-coverage-phase-2-analyzers-semantic-lsp.md`
  Status: active.
  Scope: remaining analyzer-heavy modules plus semantic core, LSP, and resolution debt.
- `docs/exec-plans/active/16-coverage-phase-2-parser-gui-reporting.md`
  Status: active.
  Scope: remaining parser transformer/API debt, reporting/docgen residue, graphics validation, and headless GUI gaps.
- `docs/exec-plans/active/17-coverage-phase-2-orphans-and-final-gate.md`
  Status: active.
  Scope: orphan zero-owner modules, the final cross-suite residual sweep, and repository-default acceptance.

## Parallel Execution Rules

1. Claim exact files in `.github/coordination/current-work.md` before touching code. Keep claims narrow and update them before widening scope.
2. Stay inside the nearest existing owner suite first. Only add a dedicated suite when a quick search confirms there is no stable owner.
3. The first post-edit validation remains slice-local and uses `--no-cov` unless the slice itself exists only to refresh shared coverage.
4. Shared checkpoints with `--cov-fail-under=0` happen only after a child plan closes a meaningful bucket or the orchestrator needs a refreshed miss list.
5. If a slice touches `src/sattlint_lsp/`, `src/sattlint/core/`, `src/sattlint/editor_api.py`, or `vscode/`, restart the LSP after validation per repo rules.
6. If a slice discovers a real product defect while adding tests, fix the product behavior in the same slice rather than encoding the bug in tests.
7. The orphan plan is the only place where new dedicated suites should be added for zero-owner modules after owner search is documented.

## Finish Strategy

Phase 1: Work the two dominant clusters in parallel through [14](14-coverage-phase-2-app-devtools-core.md) and [15](15-coverage-phase-2-analyzers-semantic-lsp.md).

Phase 2: Run [16](16-coverage-phase-2-parser-gui-reporting.md) against the remaining parser/reporting/GUI/docgen debt so the medium-sized cluster does not become the new bottleneck.

Phase 3: Use [17](17-coverage-phase-2-orphans-and-final-gate.md) to add dedicated owners for zero-owner modules, close the long-tail residuals, and keep the final gate explicit instead of implicit.

Phase 4: Once no file still carries more than `20` misses, stop optimizing by cluster and do the last sweep directly from `htmlcov/status.json` until repository-default `pytest -q` reaches `100.00%`.

## Concrete Steps

Run commands from repository root.

Coverage triage support:

    rg -n 'n_missing' htmlcov/status.json
    rg -n 'filename="sattlint/.+".*line-rate="0(\\.0+)?"' coverage.xml
    rg -n 'filename="sattlint/.+".*line-rate="0\\.[0-2]' coverage.xml

Shared checkpoint:

    & ".venv/Scripts/python.exe" -m pytest -q --cov-fail-under=0

Final acceptance:

    & ".venv/Scripts/python.exe" -m pytest -q

Expected final transcript:

    <all tests pass>
    Required test coverage of 100% reached. Total coverage: 100.00%

## Validation and Acceptance

Acceptance for each final-phase child plan means:

- its focused `--no-cov` validations are green,
- its named scope is no longer the controlling cluster in the next refreshed miss list,
- any discovered production defects were repaired locally rather than masked.

Acceptance for the full campaign means repository-default `pytest -q` passes with no overrides and reports `100.00%` coverage.

## Idempotence and Recovery

Each child plan is restartable. If a slice becomes awkward, finish the current owner seam before moving. If a shared checkpoint exposes a better split, update the relevant child plan instead of reopening the retired first-generation lane files.

## Surprises & Discoveries

- Observation: the first post-ExecPlan-16 checkpoint was not safe to treat as canonical.
  Evidence: coverage report generation hit a corrupted `.coverage` database with `no such table: tracer`, so the run was discarded and repeated from a clean `.coverage` state.
- Observation: the campaign is still not blocked by failing tests.
  Evidence: the clean rerun passes at `1272 passed, 1 warning`.
- Observation: analyzer/semantic/LSP remains the controlling residual cluster, with app/devtools/core still second.
  Evidence: the clean checkpoint table puts about `2198` misses in analyzers/semantic/LSP and about `1373` in app/devtools/core.
- Observation: the parser/GUI/reporting/docgen workstream no longer controls campaign planning, but it still has meaningful residual debt.
  Evidence: the clean checkpoint puts that bucket at about `493` misses, well below the top two clusters but still above the orphan/residual sweep.
- Observation: the reopened docgen owner seam was fully drainable without widening beyond `tests/test_docgen.py`.
  Evidence: `tests/test_docgen.py` now passes at `62 passed`, and focused coverage on `sattlint.docgenerator.classification` plus `sattlint.docgenerator.docgen` is `100%`.
- Observation: the final push needs an explicit orphan-and-final-gate plan, not just more lane recycling.
  Evidence: even after the latest checkpoint, the remaining unassigned residuals still need explicit ownership to finish the default `pytest -q` gate.

## Decision Log

- Decision: retire the first-generation active split after lanes A, B, and C all closed.
  Rationale: leaving only lane B active after the shared checkpoint would misrepresent the actual state of the campaign.
  Date/Author: 2026-04-30 / Copilot (GPT-5.4)
- Decision: replace the old lane structure with four final-phase plans.
  Rationale: the remaining debt now breaks more cleanly into two large clusters, one medium parser/reporting/docgen cluster, and one orphan/final-gate cluster.
  Date/Author: 2026-04-30 / Copilot (GPT-5.4)
- Decision: create a dedicated orphan-and-final-gate plan.
  Rationale: reaching `100%` requires explicit ownership for zero-owner modules and the default acceptance run.
  Date/Author: 2026-04-30 / Copilot (GPT-5.4)
- Decision: discard the warning-heavy post-ExecPlan-16 checkpoint and rebaseline only from a clean `.coverage` rerun.
  Rationale: the first rerun refreshed artifacts, but the corrupted report database made the transcript ambiguous; the clean rerun removed that ambiguity.
  Date/Author: 2026-04-30 / Copilot (GPT-5.4)
- Decision: finish the reopened ExecPlan 16 docgen work by exhausting the existing owner seam before widening back into parser or GUI files.
  Rationale: the remaining misses in `classification.py` and `docgen.py` were still branch-local helper paths, so direct owner-suite tests were the cheapest discriminating fix.
  Date/Author: 2026-04-30 / Copilot (GPT-5.4)

## Outcomes & Retrospective

The first coverage-lane generation is complete and archived under `docs/exec-plans/completed/11-coverage-lane-a-app-devtools-engine.md`, `docs/exec-plans/completed/12-coverage-lane-b-analyzers-semantic-lsp.md`, and `docs/exec-plans/completed/13-coverage-lane-c-parser-reporting-gui.md`.

The latest shared checkpoint artifacts now stand at `87.1%` with `3505` uncovered lines.

This orchestrator now routes the remaining work through the final-phase plans instead of recycling the earlier lane split.

The clean checkpoint confirms that the phase-2 parser/GUI/reporting/docgen bucket is no longer a controlling residual cluster. Under the current phase-2 mapping it remains the third-largest bucket at about `422` misses, behind analyzers/semantic/LSP and app/devtools/core but ahead of the orphan long tail.

The reopened docgen seam is now exhausted locally: `src/sattlint/docgenerator/classification.py` and `src/sattlint/docgenerator/docgen.py` are both at `100%` in focused owner-slice coverage, so the remaining plan-16 work has moved back to parser, graphics, reporting, GUI, and adjacent docgen support files.

## Artifacts and Notes

- Current source of truth: `coverage.xml` and `htmlcov/status.json`
- Historical context only: `covtest.txt`
- Latest clean shared checkpoint artifacts: `coverage.xml` at `87.1%` with `3505` uncovered lines

## Interfaces and Dependencies

Preserve the current owner routing conventions:

- docgen and documentation classification work stays in `tests/test_docgen.py` when an existing owner fit exists,
- repo-audit and doc-gardener work stays in `tests/test_repo_audit.py`,
- app and CLI work stays in `tests/test_app.py`, `tests/test_app_analysis.py`, `tests/test_app_menus.py`, and `tests/test_cli.py`,
- engine work stays in `tests/test_engine.py`,
- analyzer work stays in the existing analyzer owner suites unless the orphan plan explicitly creates a dedicated suite,
- semantic/LSP work stays in `tests/test_editor_api.py` and `tests/test_lsp_*`,
- parser work stays in `tests/test_parser*.py`,
- GUI work stays in `tests/test_gui.py` unless no stable owner exists.
