# Structural Unblockers

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

## Purpose / Big Picture

This plan clears the highest-priority structural blockers in SattLint. When it is complete, the parser transformer split tracked by W6 and the variables analyzer split tracked by W7 will both validate cleanly, and the repo will no longer be blocked by oversized structural hotspots in those two ownership lanes.

## Progress

- [x] Finish the W6 parser transformer extraction so the focused parser checks pass again.
- [x] Remove the W7 blocker caused by the parser import break and rerun the variables analyzer tests.
- [x] Update the tracker and current-work notes once both lanes validate.

## Surprises & Discoveries

- Observation: W7 is already partially extracted but cannot validate until W6 restores the parser import surface.
  Evidence: the coordination state for that slice marked W7 blocked on the missing `v_args` import in the W6 slice.

## Decision Log

- Decision: Keep W6 and W7 in one active plan instead of two separate files.
  Rationale: W7 is directly blocked by W6, so splitting them into separate active plans adds coordination cost without making execution clearer.
  Date/Author: 2026-04-29 / Copilot (GPT-5.4)

## Outcomes & Retrospective

W6 and W7 are now unblocked and validated with focused commands.

Parser transformer stability was restored by repairing expression-node shape contracts and restoring missing module-structure transformer hooks (`submodules` and record/type-definition collection). With those seams fixed, parser syntax-check and focused parser tests pass again, and the variables analyzer suite now validates without the prior blocker.

## Context and Orientation

The controlling code lives in `src/sattline_parser/transformer/sl_transformer.py` for W6 and in `src/sattlint/analyzers/variables.py` plus `src/sattlint/analyzers/_variables_effect_flow.py` for W7.
The owning focused tests are `tests/test_transformer.py`, `tests/test_parser_core.py`, and `tests/test_analyzers_variables.py`. Current lane status is recorded in the shared active-claim lock and mirrored in `docs/exec-plans/tech-debt-tracker.md` under Program B.

## Plan of Work

First restore parser test stability in the W6 slice. Fix the missing import or ownership mistake introduced during the transformer extraction, rerun the narrow parser validation, and only then resume W7. After W6 is green, rerun the variables analyzer tests, finish any remaining delegation cleanup in the W7 slice, and update the tracker status so it no longer reports W7 as blocked.

## Concrete Steps

Run from repository root:

    & ".venv/Scripts/sattlint.exe" syntax-check tests/fixtures/corpus/valid/VariableModifiers.s
    & ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_transformer.py tests/test_parser_core.py -x -q --tb=short
    & ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_analyzers_variables.py -x -q --tb=short

## Validation and Acceptance

Acceptance means all three focused commands above pass, W6 and W7 can be marked done or in progress without a blocker note mismatch, and Program B in the tracker matches the shared active-claim lock.

## Idempotence and Recovery

Repeat the focused parser command after each local W6 fix. Do not widen to full pytest until the narrow parser checks pass. If W7 still fails after W6 is green, keep the repair local to the variables analyzer slice and rerun only `tests/test_analyzers_variables.py`.

## Artifacts and Notes

Implemented fixes:

- `src/sattline_parser/transformer/_expressions_mixin.py`: restored compare/add/mul tuple contracts to `(tag, base_expr, [(op, rhs), ...])` expected by validation and downstream analyzers.
- `src/sattline_parser/transformer/_modules_mixin.py`: added `submodules`, `record`, and `datatype_typedefinitions` transformer methods so submodule and datatype sections are preserved in AST assembly.

First passing focused validations:

- `& ".venv/Scripts/sattlint.exe" syntax-check tests/fixtures/corpus/valid/VariableModifiers.s` -> `OK`
- `& ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_transformer.py tests/test_parser_core.py -x -q --tb=short` -> `23 passed`
- `& ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_analyzers_variables.py -x -q --tb=short` -> `40 passed`

## Interfaces and Dependencies

This plan depends on `sattline_parser` preserving existing transformer behavior, on `sattlint.validation` continuing to accept the valid corpus fixture used above, and on the variables analyzer keeping its current public interfaces while internal helpers move.
