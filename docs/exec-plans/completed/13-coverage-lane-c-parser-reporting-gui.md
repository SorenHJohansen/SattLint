# Coverage Lane C: Parser, Reporting, GUI

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` record the execution history for this completed lane.

## Purpose / Big Picture

Drain the parser, reporting, and GUI residue after the higher-yield owner lanes start moving. This lane kept the remaining parser-core work grouped with the report presentation and GUI surfaces that depend on it, while avoiding a premature GUI-first sweep.

## Progress

- [x] (2026-04-30) Create this lane plan and map the known owner suites.
- [x] (2026-04-30) Start lane execution with direct parser mixin coverage, a dedicated `tests/test_mms_report.py` owner, additional `variables_report.py` and `icf_report.py` summary coverage, and no-Tk `config_frame.py` helper coverage. Lane checkpoint validation passed with `424 passed` across the owner set.
- [x] (2026-04-30) Drain parser API, AST, transformer, and validation residue through the parser owner suites, including direct `ast_model.py`, `formatter.py`, `_graphics_interact_mixin.py`, and additional `_modules_mixin.py` branch coverage in `tests/test_parser_core.py`.
- [x] (2026-04-30) Drain `variables_report.py` through existing analyzer owners and direct owner tests in `tests/test_analyzers_state.py`.
- [x] (2026-04-30) Drain `icf_report.py` through `tests/test_icf_validation.py` and nearby analyzer owners.
- [x] (2026-04-30) Drain `mms_report.py` through the dedicated focused owner `tests/test_mms_report.py` after confirming no stable existing owner fit cleanly.
- [x] (2026-04-30) Drain remaining `sattlint_gui/**` residue through `tests/test_gui.py`, including headless binding/window/frame/widget/config constructor coverage.
- [x] (2026-04-30) Run the lane-close validation set and return control to the orchestrator.
- [x] (2026-04-30) Move this completed lane plan to `docs/exec-plans/completed/` and update tracker references.

## Context and Orientation

Known owner suites used by this lane:

- `tests/test_parser_core.py`, `tests/test_parser_validation.py`, `tests/test_parser.py` -> parser API, AST, transformer, formatter, and validation seams
- `tests/test_analyzers_state.py`, `tests/test_app.py`, `tests/test_app_analysis.py`, `tests/test_app_menus.py` -> `src/sattlint/reporting/variables_report.py`
- `tests/test_icf_validation.py`, `tests/test_analyzers_variables.py` -> `src/sattlint/reporting/icf_report.py`
- `tests/test_gui.py` -> remaining `src/sattlint_gui/**` surfaces
- `tests/test_mms_report.py` -> dedicated `mms_report.py` owner justified by owner-search results

## Validation and Acceptance

This lane is complete because:

- parser owner suites are green with `--no-cov`,
- reporting residue is covered through stable owners plus one explicitly justified dedicated suite for `mms_report.py`,
- GUI residue is down to short residual sweeps instead of a dominant cluster,
- the lane-close owner validation set passed cleanly.

## Surprises & Discoveries

- Observation: direct helper testing remained the cheapest closure path for parser and GUI residue.
  Evidence: `tests/test_parser_core.py` and `tests/test_gui.py` absorbed the lane’s biggest remaining branches without production changes.
- Observation: `formatter.py` was a hidden parser-heavy gap once the earlier mixin work landed.
  Evidence: the first closeout coverage refresh surfaced `src/sattline_parser/utils/formatter.py` as the largest remaining parser miss cluster; direct formatter tests reduced it to `0` misses in the lane-local checkpoint.
- Observation: `config_frame.py` exposed more headless-safe coverage than the first GUI slice captured.
  Evidence: a fake-widget constructor/build test reduced `config_frame.py` from the dominant GUI file to `3` remaining misses in the final lane-local coverage refresh.
- Observation: after the final closeout sweep, lane-C misses were no longer controlled by any single GUI file.
  Evidence: the final lane-local `htmlcov/status.json` refresh showed the top remaining lane-C misses spread across short residual sweeps such as `window.py` (`39`), `sl_transformer.py` (`29`), `docs_frame.py` (`28`), `results_frame.py` (`26`), and `_modules_mixin.py` (`26`).

## Decision Log

- Decision: keep reporting with parser and GUI rather than analyzer lane B.
  Rationale: the remaining work was presentation and output shaping, not core analyzer logic.
  Date/Author: 2026-04-30 / Copilot (GPT-5.4)
- Decision: allow one dedicated `mms_report` suite after the owner search confirmed no stable existing suite fit cleanly.
  Rationale: forcing that file into unrelated owners would make the lane harder to execute, not easier.
  Date/Author: 2026-04-30 / Copilot (GPT-5.4)
- Decision: keep GUI work headless and frame-local instead of building live Tk fixtures.
  Rationale: direct helper and constructor seams were sufficient and more stable than live-root GUI tests.
  Date/Author: 2026-04-30 / Copilot (GPT-5.4)
- Decision: move the completed lane plan to `docs/exec-plans/completed/` once all checklist items and validations were done.
  Rationale: keeps `docs/exec-plans/active/` limited to in-flight plans and aligns the orchestrator with actual lane status.
  Date/Author: 2026-04-30 / Copilot (GPT-5.4)

## Outcomes & Retrospective

- Initial parser slice: added direct `_modules_mixin.py` coverage in `tests/test_parser_core.py` for helper flattening, module headers, coordinate helpers, module invocation assembly, datatype/module trees, and variable/mapping helpers. Validation: `& ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_parser_core.py tests/test_parser_validation.py tests/test_parser.py -x -q --tb=short` -> `135 passed`.
- Initial reporting slice: added `tests/test_mms_report.py`, expanded `tests/test_analyzers_state.py` for `VariablesReport` formatting branches, and expanded `tests/test_icf_validation.py` for `ICFValidationReport` summary formatting branches. Validation: `tests/test_mms_report.py` -> `3 passed`, `tests/test_analyzers_state.py` -> `32 passed`, `tests/test_icf_validation.py` -> `21 passed`.
- Initial GUI slice: expanded `tests/test_gui.py` with no-Tk coverage for `config_frame.py` helper, workflow, reload/save, and close-decision paths. Validation: `& ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_gui.py -x -q --tb=short` -> `35 passed`.
- Closeout parser/reporting slice: added direct `ast_model.py`, `formatter.py`, `_graphics_interact_mixin.py`, and additional `_modules_mixin.py` branch coverage in `tests/test_parser_core.py`, plus broader `VariablesReport` selector/empty-section coverage in `tests/test_analyzers_state.py`. Focused validations: `tests/test_parser_core.py` -> `42 passed`; `tests/test_analyzers_state.py` remained green in the lane-close set.
- Closeout GUI slice: expanded `tests/test_gui.py` for binding fallbacks, analyze/docs/tools frame routing, report/console/target/analyzer widgets, results selection, theme application, and headless `ConfigFrame` construction/build wiring. Focused validation: `tests/test_gui.py` -> `43 passed`.
- Final lane-close validation: `& ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_parser_core.py tests/test_parser_validation.py tests/test_parser.py tests/test_analyzers_state.py tests/test_app.py tests/test_app_analysis.py tests/test_app_menus.py tests/test_icf_validation.py tests/test_analyzers_variables.py tests/test_gui.py tests/test_mms_report.py -x -q --tb=short` -> `447 passed`.
- Final lane-local coverage refresh: `& ".venv/Scripts/python.exe" -m pytest tests/test_parser_core.py tests/test_parser_validation.py tests/test_parser.py tests/test_analyzers_state.py tests/test_app.py tests/test_app_analysis.py tests/test_app_menus.py tests/test_icf_validation.py tests/test_analyzers_variables.py tests/test_gui.py tests/test_mms_report.py --cov-fail-under=0 -q` refreshed `coverage.xml` and `htmlcov/status.json`. Key closeout signals: `formatter.py` reached `0` misses, `config_frame.py` dropped to `3` misses, `_modules_mixin.py` dropped to `26` misses, and no single GUI file remained a lane-sized blocker.

## Artifacts and Notes

- Current source of truth for the lane closeout: `coverage.xml` and `htmlcov/status.json`
- Dedicated `mms_report` suite justification: no stable owner suite existed after test search, so `tests/test_mms_report.py` was added as the single allowed focused owner.
- The parent orchestrator remains active until lane B, the shared residual sweep, and the repository-default `pytest -q` acceptance gate are complete.

## Interfaces and Dependencies

Keep parser validation strict and GUI tests headless-safe. Prefer existing owner suites and direct helper seams over wider fixture scaffolding when residual coverage gaps are branch-local.
