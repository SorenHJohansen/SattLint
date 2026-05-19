# T-Wave-7 Parser Strict Typing Promotion

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

## Purpose / Big Picture

This plan makes the remaining parser-side files under the typing strict roots actually ready for full strict coverage. After this work lands, the remaining parser transformer helper files will be type-clean, the existing strict blocker in `src/sattline_parser/models/ast_model.py` will be resolved, and the parser slice can move into `tool.pyright.strict` without creating new typing debt.

The observable proof is concrete. `bash scripts/run_repo_python.sh -m pyright` must pass on `src/sattline_parser/models/ast_model.py` plus the uncovered transformer helpers, `sattlint syntax-check` must still pass on a real checked-in valid file, the focused parser tests must remain green, and the same change must update `pyproject.toml` plus a matching approval record under `.github/approvals/ratchet-rebaseline-*.md`.

## Progress

- [x] (2026-05-18 15:10Z) Create the ExecPlan and capture the live baseline: the strict-root inventory shows four uncovered parser files in `src/sattline_parser/transformer/`, and the current repo `pyright` gate already fails in `src/sattline_parser/models/ast_model.py` with a `reportArgumentType` error.
- [x] (2026-05-18) Resolve the existing strict-listed parser blocker in `src/sattline_parser/models/ast_model.py` without changing parser behavior by widening the shared formatter helper to accept a covariant read-only sequence and confirming the original narrow `pyright` error is gone.
- [x] (2026-05-18) Repair the parser regressions surfaced by the first behavior proof: `_sfc_mixin.equationblock()` was capturing the `EQUATIONBLOCK` keyword token as the equation name, and `sl_transformer.py` needed a tiny compatibility helper surface restored for parser-core tests after the mixin split.
- [x] (2026-05-18) Make the four uncovered transformer helper files type-clean under strict mode and confirm that state with a narrow strict `pyright` project before touching the protected ratchet config.
- [x] (2026-05-18) Add the newly clean parser files to `tool.pyright.strict` in `pyproject.toml` and update the required approval record in `.github/approvals/ratchet-rebaseline-2026-05-18.md`.
- [x] (2026-05-18) Run strict parser validation, focused parser pytest, touched-file Ruff, touched-file Pyright, and ratchet-policy proof for the slice.

## Surprises & Discoveries

- Observation: the uncovered parser files are all sibling helpers from the recent module-normalization split.
  Evidence: the uncovered inventory for `src/sattline_parser` is exactly `src/sattline_parser/transformer/_module_assembly_mixin.py`, `_module_header_mixin.py`, `_module_layout_mixin.py`, and `_module_shared.py`.
- Observation: the parser slice is blocked by both inventory and an existing strict-listed error.
  Evidence: the current repo `pyright` run fails in `src/sattline_parser/models/ast_model.py` before any new parser files are promoted.
- Observation: parser work here must preserve strict CLI behavior, not just type checker behavior.
  Evidence: repository invariants require `sattlint syntax-check` to stay strict and continue to reject invalid parser input without silent fallbacks.
- Observation: the first behavior proof flushed out a real parser bug that was separate from the original strict typing blocker.
  Evidence: `bash scripts/run_repo_python.sh -m sattlint syntax-check tests/fixtures/corpus/valid/VariableModifiers.s` initially failed with `BasePicture equation name Token('EQUATIONBLOCK', 'EQUATIONBLOCK') is a reserved SattLine keyword` until `_sfc_mixin.equationblock()` was updated to skip leading keyword tokens the same way `sequence()` already does.
- Observation: parser-core tests still depended on a small `sl_transformer` compatibility surface after the transformer split.
  Evidence: `tests/parser/test_parser_core.py` initially failed to collect because `_iter_tree_children` no longer imported from `sl_transformer`, and the helper assertion for `_strip_quoted()` only passed once the compatibility implementation matched `_TokensMixin.STRING` newline trimming.

## Decision Log

- Decision: keep this slice parser-only and do not combine it with LSP helper promotion.
  Rationale: parser and LSP have different owner tests, different invariants, and different validation entry points, so a combined plan would be harder to execute safely.
  Date/Author: 2026-05-18 / Copilot (GPT-5.4)
- Decision: fix the existing strict-listed parser error before promoting the uncovered helpers.
  Rationale: full strict coverage is not credible if the parser slice still fails on files that are already in `tool.pyright.strict`.
  Date/Author: 2026-05-18 / Copilot (GPT-5.4)
- Decision: validate with real parser entrypoints first.
  Rationale: the user-visible value is stable parsing and strict syntax-check behavior, so the first proof should exercise the parser the same way users do.
  Date/Author: 2026-05-18 / Copilot (GPT-5.4)
- Decision: restore the tiny compatibility helper surface on `src/sattline_parser/transformer/sl_transformer.py` instead of rewriting the shared parser-core test support imports.
  Rationale: the owning implementations already live in `_module_shared` and `_tokens_mixin`; re-exporting a narrow compatibility layer kept the fix local to the transformer split seam and preserved the long-standing parser-core test contract.
  Date/Author: 2026-05-18 / Copilot (GPT-5.4)

## Outcomes & Retrospective

This slice is complete. `src/sattline_parser/models/ast_model.py` no longer trips the strict variance error because the shared formatter helper now accepts a read-only sequence, which keeps the AST rendering API unchanged while making strict typing correct. The parser proof also uncovered and fixed two adjacent regressions: `_sfc_mixin.equationblock()` now ignores leading keyword tokens instead of treating `EQUATIONBLOCK` as the equation name, and `src/sattline_parser/transformer/sl_transformer.py` again exposes the small compatibility helpers expected by parser-core tests, with `_strip_quoted()` matching `_TokensMixin.STRING` behavior.

The four uncovered helper files `src/sattline_parser/transformer/_module_assembly_mixin.py`, `src/sattline_parser/transformer/_module_header_mixin.py`, `src/sattline_parser/transformer/_module_layout_mixin.py`, and `src/sattline_parser/transformer/_module_shared.py` are now represented in `tool.pyright.strict`, and the same-change approval record at `.github/approvals/ratchet-rebaseline-2026-05-18.md` explicitly covers the parser helper promotion. Final proof is green: `sattlint syntax-check tests/fixtures/corpus/valid/VariableModifiers.s` passed, the focused parser pytest suite passed (`188 passed`), touched-file `pyright` passed, touched-file `ruff check` passed, and `tests/test_ratchet_policy.py tests/test_ratchet_policy_typing.py` passed (`23 passed`).

## Context and Orientation

The parser owner files for this plan are:

- `src/sattline_parser/models/ast_model.py`
- `src/sattline_parser/transformer/_module_assembly_mixin.py`
- `src/sattline_parser/transformer/_module_header_mixin.py`
- `src/sattline_parser/transformer/_module_layout_mixin.py`
- `src/sattline_parser/transformer/_module_shared.py`

`src/sattline_parser/models/ast_model.py` is already in `tool.pyright.strict` and currently fails the repo `pyright` gate. The four transformer helpers are inside `tool.sattlint.typing_ratchet.strict_roots` but are not yet represented in either `tool.pyright.strict` or `tool.sattlint.typing_ratchet.debt_allowlist`, so they are inventory blockers.

The main behavior proof lives in the parser entrypoints and tests. `tests/parser/test_parser.py`, `tests/parser/test_parser_core.py`, `tests/parser/test_parser_validation.py`, and `tests/parser/test_parser_decode.py` are the narrow owner suites. The strict CLI proof path is `sattlint syntax-check` against a real checked-in valid file such as `tests/fixtures/corpus/valid/VariableModifiers.s`.

This plan edits a protected config path at the end: `pyproject.toml`. The ratchet rules require the same change to add or update an approval record matching `.github/approvals/ratchet-rebaseline-*.md` with `Approved-by:` and `Reason:` lines. The monotonic rule still applies: do not add debt or shrink strict coverage.

## Plan of Work

Start with `src/sattline_parser/models/ast_model.py`. The current failure is a classic variance problem where a helper expects `list[object]` but the call site passes `list[Variable]`. Fix the signature or local call shape in the smallest way that keeps the AST model API clear and strict-safe.

After that, make the four uncovered transformer helpers strict-clean. Do not widen this into grammar or AST redesign. Prefer explicit annotations, narrow helper return types, and local typed intermediates over behavioral refactors.

Once the owned files are clean under strict mode, update `pyproject.toml` to add the four uncovered helper files to `tool.pyright.strict`. Keep `src/sattline_parser/models/ast_model.py` in the strict list because it is already part of the current baseline. Add the approval record in the same change.

## Concrete Steps

Run all commands from the repository root.

Inspect the parser blockers before editing:

    rg -n "format_list|class Variable|_module_" src/sattline_parser/models/ast_model.py src/sattline_parser/transformer/_module_assembly_mixin.py src/sattline_parser/transformer/_module_header_mixin.py src/sattline_parser/transformer/_module_layout_mixin.py src/sattline_parser/transformer/_module_shared.py

First focused behavior proof after the first substantive edit:

    bash scripts/run_repo_python.sh -m sattlint syntax-check tests/fixtures/corpus/valid/VariableModifiers.s

Focused parser regression proof after the slice is locally clean:

    bash scripts/run_repo_python.sh -m pytest --no-cov tests/parser/test_parser.py tests/parser/test_parser_core.py tests/parser/test_parser_validation.py tests/parser/test_parser_decode.py -x -q --tb=short

Touched-file type and lint proof:

    bash scripts/run_repo_python.sh -m pyright src/sattline_parser/models/ast_model.py src/sattline_parser/transformer/_module_assembly_mixin.py src/sattline_parser/transformer/_module_header_mixin.py src/sattline_parser/transformer/_module_layout_mixin.py src/sattline_parser/transformer/_module_shared.py
    bash scripts/run_repo_python.sh -m ruff check src/sattline_parser/models/ast_model.py src/sattline_parser/transformer/_module_assembly_mixin.py src/sattline_parser/transformer/_module_header_mixin.py src/sattline_parser/transformer/_module_layout_mixin.py src/sattline_parser/transformer/_module_shared.py

Protected-path closeout proof once `pyproject.toml` and the approval record are updated:

    bash scripts/run_repo_python.sh -m pytest --no-cov tests/test_ratchet_policy.py tests/test_ratchet_policy_typing.py -x -q --tb=short

## Validation and Acceptance

This plan is complete only when all five owned parser files are strict-clean, the four uncovered transformer helpers are represented in `tool.pyright.strict`, `sattlint syntax-check` still passes on the checked-in valid fixture, the focused parser tests pass, and the ratchet-policy tests stay green after the `pyproject.toml` update.

Acceptance is behavior, not just bookkeeping. The parser must still build the same AST shapes and keep strict syntax-check behavior unchanged.

## Idempotence and Recovery

The parser file cleanup is safe to repeat. If one helper fix changes parser behavior, revert that local change, restore the last green syntax-check and parser-test state, and retry with narrower annotations instead of a larger refactor.

Do not update `pyproject.toml` until the owned files are already strict-clean locally. If the protected-path change is made too early, recovery becomes noisier because the ratchet-policy tests will fail for both inventory and behavior at the same time.

## Artifacts and Notes

Record the following evidence as work proceeds:

- the original `pyright` failure in `src/sattline_parser/models/ast_model.py`,
- the passing `sattlint syntax-check` transcript,
- the passing focused parser pytest summary,
- the final touched-file `pyright` output,
- the approval record path added with the `pyproject.toml` update.

## Interfaces and Dependencies

This plan depends on the current parser AST model and transformer helper seams already in the repository. Keep `src/sattline_parser/models/ast_model.py` as the AST owner, keep the helper modules under `src/sattline_parser/transformer/`, and avoid widening the slice into grammar or analyzer behavior.

The only protected-path dependency is `pyproject.toml` plus a matching approval record under `.github/approvals/`. No new debt allowlist entries are allowed.
