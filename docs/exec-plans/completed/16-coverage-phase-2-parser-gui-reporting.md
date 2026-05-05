# Coverage Phase 2: Parser, GUI, Reporting, Docgen

This ExecPlan is a living document. Keep `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` current as work proceeds.

Retired on 2026-05-04 at user request. This file is preserved as archive-only historical coverage context and no longer represents active work.

## Purpose / Big Picture

Drain the remaining parser transformer/API residue, reporting/docgen support debt, graphics-validation gaps, and headless GUI misses that still total about `422` uncovered lines after the latest clean shared checkpoint. The reopened `tests/test_docgen.py` seam has already taken `classification.py` and `docgen.py` to `100%`, so the remaining plan debt sits in parser, graphics, reporting, GUI, and adjacent docgen support files.

## Progress

- [x] (2026-04-30) Create this final-phase plan from the clean shared checkpoint baseline.
- [x] (2026-04-30) Drain the remaining parser transformer and API residue through `tests/test_parser_core.py`, `tests/test_parser_validation.py`, and `tests/test_parser.py`.
- [x] (2026-04-30) Drain `docgenerator/docgen.py` and `docgenerator/classification.py` through `tests/test_docgen.py`.
- [x] (2026-04-30) Reopen `tests/test_docgen.py`, exhaust the remaining helper-edge residue, and move `classification.py` plus `docgen.py` to `100%` focused coverage.
- [x] (2026-04-30) Reopen `tests/test_parser_core.py` and move `sl_transformer.py` to `100%` focused coverage.
- [x] (2026-04-30) Drain remaining reporting residue through `tests/test_analyzers_state.py`, `tests/test_icf_validation.py`, and `tests/test_mms_report.py`.
- [x] (2026-04-30) Reopen `tests/test_graphics_validation.py` and move `graphics_rules.py` to `100%` focused coverage.
- [x] (2026-04-30) Drain `graphics_rules.py` and `graphics_validation.py` through `tests/test_graphics_validation.py` and nearby parser or app owners.
- [x] (2026-04-30) Drain the remaining headless GUI residue through `tests/test_gui.py`.
- [x] (2026-04-30) Reopen `tests/test_gui.py` and move `window.py` to `100%` focused coverage.
- [x] (2026-05-04) Retire the remaining parser, GUI, reporting, and docgen-support coverage sweep at user request.
- [x] (2026-05-04) Archive this plan as historical coverage context instead of keeping the bucket active.

## Context and Orientation

Primary owner suites for this plan:

- `tests/test_parser_core.py`, `tests/test_parser_validation.py`, `tests/test_parser.py` -> remaining parser API, AST, transformer, formatter, fuzz, and corpus seams
- `tests/test_docgen.py` -> `src/sattlint/docgenerator/docgen.py`, `src/sattlint/docgenerator/classification.py`
- `tests/test_analyzers_state.py`, `tests/test_icf_validation.py`, `tests/test_mms_report.py` -> `src/sattlint/reporting/variables_report.py`, `src/sattlint/reporting/icf_report.py`, `src/sattlint/reporting/mms_report.py`
- `tests/test_graphics_validation.py` -> `src/sattlint/graphics_rules.py`, `src/sattlint/graphics_validation.py`
- `tests/test_gui.py` -> remaining `src/sattlint_gui/**` headless-safe surfaces

Current notable files in this plan from the latest clean shared checkpoint still include `frames/docs_frame.py` (`28`), `_modules_mixin.py` (`26`), `frames/results_frame.py` (`26`), `frames/analyze_frame.py` (`24`), `widgets/analyzer_list.py` (`24`), `_sfc_mixin.py` (`22`), `_expressions_mixin.py` (`21`), `binding.py` (`17`), `reporting/variables_report.py` (`14`), `docgenerator/configgen.py` (`12`), and `graphics_validation.py` (`11`). Local slice validations now also show `sl_transformer.py`, `graphics_rules.py`, `window.py`, `classification.py`, and `docgen.py` at `100%`.

## Plan of Work

Slice 1: keep the closed local wins closed: `classification.py`, `docgen.py`, `sl_transformer.py`, `graphics_rules.py`, and `window.py` should not regress.

Slice 2: shift parser work into `_modules_mixin.py`, `_sfc_mixin.py`, and `_expressions_mixin.py` through the parser core and corpus-driven suites.

Slice 3: finish the remaining headless GUI long tail in `frames/docs_frame.py`, `frames/results_frame.py`, `frames/analyze_frame.py`, `widgets/analyzer_list.py`, and `binding.py` through `tests/test_gui.py`.

Slice 4: mop up reporting and docgen-support residue such as `variables_report.py`, `configgen.py`, and `graphics_validation.py` after the larger parser and GUI files are pushed down.

## Concrete Steps

Run commands from repository root.

Per-slice first validations:

    & ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_docgen.py -x -q --tb=short
    & ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_parser_core.py tests/test_parser_validation.py tests/test_parser.py -x -q --tb=short
    & ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_graphics_validation.py -x -q --tb=short
    & ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_gui.py tests/test_icf_validation.py tests/test_mms_report.py tests/test_analyzers_state.py -x -q --tb=short

Plan-close validation:

    & ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_docgen.py tests/test_parser_core.py tests/test_parser_validation.py tests/test_parser.py tests/test_graphics_validation.py tests/test_gui.py tests/test_icf_validation.py tests/test_mms_report.py tests/test_analyzers_state.py -x -q --tb=short

## Validation and Acceptance

This plan is complete when:

- the listed owner suites pass with `--no-cov`,
- parser/GUI/reporting/docgen debt is no longer a distinct planning bucket in the next shared checkpoint,
- `classification.py` and `docgen.py` stay at `100%` while the remaining bucket is drained,
- GUI tests remain headless-safe and parser validation remains strict.

## Idempotence and Recovery

Prefer existing owners and direct helper seams. Only add new dedicated suites here if the orphan plan explicitly declines ownership and the owner search is recorded.

## Surprises & Discoveries

- Observation: lane C closure removed the easy GUI and parser wins, but not all of the docgen and parser-api residue.
  Evidence: `docgen.py`, `classification.py`, and several parser files still hold meaningful misses after the first-generation closeout.
- Observation: `tests/test_graphics_validation.py` gives `graphics_rules.py` and `graphics_validation.py` a real owner path.
  Evidence: there is already a dedicated graphics validation suite in the repo.
- Observation: the remaining docgen residue closed cleanly through owner-local tests without further production edits.
  Evidence: focused `tests/test_docgen.py` additions covering instance-path scope behavior, invalid scope fallback, complex sequence row rendering, appendix rendering, and empty-sequence output passed on the first repaired owner-suite run.
- Observation: reopening the docgen seam finished the two highest-visibility docgen files, but it did not finish the broader ExecPlan 16 bucket.
  Evidence: the latest clean shared checkpoint puts `classification.py` and `docgen.py` at `100%`, yet the overall parser/GUI/reporting/docgen bucket still sits at about `422` misses.
- Observation: the remaining `window.py` debt was constructor and layout wiring, not the already-covered interaction methods.
  Evidence: fake-Tk tests that executed the real `__init__` and `_build_layout` paths moved `window.py` to `100%` without widening into live widget integration.
- Observation: `graphics_rules.py` is best treated as a direct-helper seam inside the graphics owner suite, not as an app-menu-only surface.
  Evidence: `tests/test_graphics_validation.py` alone was enough to drive the file to `100%` through normalization, matching, mutation, and summary tests.

## Decision Log

- Decision: keep docgen with parser/reporting/GUI in the final phase.
  Rationale: its remaining debt is medium-sized and owner-local, not large enough to justify another standalone lane.
  Date/Author: 2026-04-30 / Copilot (GPT-5.4)
- Decision: reopen `tests/test_docgen.py` instead of widening immediately into parser or GUI files after the `84.65%` checkpoint.
  Rationale: the remaining `classification.py` and `docgen.py` misses were still branch-local helper edges, so the existing owner seam remained the cheapest next move.
  Date/Author: 2026-04-30 / Copilot (GPT-5.4)
- Decision: take the next plan-16 local slices in parser, graphics, and GUI through `tests/test_parser_core.py`, `tests/test_graphics_validation.py`, and `tests/test_gui.py` before another shared checkpoint.
  Rationale: `sl_transformer.py`, `graphics_rules.py`, and `window.py` each exposed direct helper or wiring seams that could be exhausted cheaply through their nearest existing owners.
  Date/Author: 2026-04-30 / Copilot (GPT-5.4)

## Outcomes & Retrospective

The earlier owner-suite closeout was not the end of this plan. A later clean shared checkpoint still showed the broader parser/GUI/reporting/docgen bucket at about `493` misses, so the docgen seam was reopened instead of declaring plan completion.

Validated outcomes:

- `tests/test_docgen.py` -> `62 passed`
- Focused docgen slice: `tests/test_docgen.py --cov=sattlint.docgenerator.classification --cov=sattlint.docgenerator.docgen --cov-report=term-missing --cov-fail-under=0` -> `100%` on both files
- `tests/test_parser_core.py` -> `45 passed`
- Focused parser slice: `tests/test_parser_core.py --cov=sattline_parser.transformer.sl_transformer --cov-report=term-missing --cov-fail-under=0` -> `100%` on `sl_transformer.py`
- `tests/test_graphics_validation.py` -> `10 passed`
- Focused graphics slice: `tests/test_graphics_validation.py --cov=sattlint.graphics_rules --cov-report=term-missing --cov-fail-under=0` -> `100%` on `graphics_rules.py`
- `tests/test_gui.py` -> `45 passed`
- Focused GUI slice: `tests/test_gui.py --cov=sattlint_gui.window --cov-report=term-missing --cov-fail-under=0` -> `100%` on `window.py`
- `tests/test_parser_core.py tests/test_parser_validation.py tests/test_parser.py` -> `143 passed`
- `tests/test_graphics_validation.py` -> `7 passed`
- `tests/test_gui.py tests/test_icf_validation.py tests/test_mms_report.py tests/test_analyzers_state.py` -> `104 passed`
- Plan-close validation: `& ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_docgen.py tests/test_parser_core.py tests/test_parser_validation.py tests/test_parser.py tests/test_graphics_validation.py tests/test_gui.py tests/test_icf_validation.py tests/test_mms_report.py tests/test_analyzers_state.py -x -q --tb=short` -> `310 passed`
- Shared checkpoint refresh: `Remove-Item -Force .coverage* -ErrorAction SilentlyContinue ; & ".venv/Scripts/python.exe" -m pytest -q --cov-fail-under=0` -> `1342 passed, 1 warning`, `86%` total coverage, about `422` misses left in the broader plan-16 bucket

`classification.py`, `docgen.py`, `sl_transformer.py`, `graphics_rules.py`, and `window.py` are now fully drained in focused owner slices, but ExecPlan 16 itself is not complete yet. The remaining work has moved into parser mixins, headless GUI frame and widget files, reporting support code, `graphics_validation.py`, and adjacent docgen support modules. A new shared checkpoint is still pending before the orchestrator baseline should be rewritten.

The plan was retired and archived on 2026-05-04 at user request. The remaining parser, GUI, reporting, and docgen-support misses stay here only as historical checkpoint context rather than an active execution commitment.

## Artifacts and Notes

- Use the orchestrator for shared checkpoint timing and final acceptance.
- Keep GUI work headless-safe and parser work strict.

## Interfaces and Dependencies

Do not weaken parser validation or introduce live Tk dependencies just to cover residual GUI branches.
