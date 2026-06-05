# T-Wave-10 Dead Code Removal and Walk Function Consolidation

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

## Purpose / Big Picture

The 2026-06-02 code review identified several categories of clearly dead or orphaned code that accumulate maintenance cost without delivering functionality. This plan removes the most clearly dead items and consolidates the inline `['.s', '.x']` extension-list duplication in `engine.py` onto the existing `code_ext` and `deps_ext` helpers that already exist in `_engine_syntax_helpers.py`.

After this work lands:

- `scripts/run_pre_push_gate.py` is deleted because it has zero references in CI, pre-commit, `pyproject.toml`, or documentation.
- `engine._find_deps` and `engine._read_text_simple` wrapper stubs are deleted because they had no production callers and only delegated to existing implementations.
- The six inline code and deps extension-list expressions in `engine.py` are rewritten to use `code_ext(mode)` and `deps_ext(mode)` while preserving the existing draft-mode fallback order.
- `iter_nested_modules()` in `analyzers/_walk_utils.py` is adopted at two low-risk analyzer sites to reduce duplicated nested-module traversal code.

The walk-function consolidation in `_picture_display_path_runtime.py` and `validation.py` remains out of scope for this plan because those files require domain review of traversal semantics.

## Progress

- [x] Verify zero production callers for `engine._find_deps` before deletion.
- [x] Verify zero production callers for `engine._read_text_simple` before deletion.
- [x] Verify zero references to `scripts/run_pre_push_gate.py` outside planning docs before deleting.
- [x] Delete `scripts/run_pre_push_gate.py`.
- [x] Delete `engine._find_deps` from `src/sattlint/engine.py`.
- [x] Delete `engine._read_text_simple` from `src/sattlint/engine.py`.
- [x] Replace the six inline code and deps extension-list expressions in `engine.py` with helper-based equivalents.
- [x] Redirect the engine helper tests that referenced the deleted wrappers.
- [x] Replace two cheap inline analyzer walk sites with `iter_nested_modules`.
- [x] Run `pyright` on the touched source files and confirm they are clean.
- [x] Run the parser test suite.
- [x] Rerun the failing full-suite test after normalizing this plan file to valid UTF-8.
- [x] Rerun the full test suite and confirm no regressions.

## Surprises & Discoveries

- `tests/parser/_parser_core_part5.py` patches `sattline_parser.api._read_text_simple`, which is a separate parser-side alias and not the engine wrapper removed by this plan. No parser test update was required there.
- `tests/parser/test_engine_loader_helpers.py` has long-standing Pyright noise because it intentionally exercises private helpers. To confirm this change did not add new source typing problems, the useful proof was a source-only Pyright run over the edited production files.
- `tests/test_ai_work_map.py` reads every active exec plan as UTF-8. The pre-existing mojibake and invalid bytes in this plan file caused the first full-suite run to fail with `UnicodeDecodeError`, so the plan file itself needed to be normalized as part of completion.

## Decision Log

- Decision: defer the full 25-walk-function consolidation to a follow-on plan.
  Rationale: each inline walk helper has slightly different filtering, recursion, or dispatch behavior. A broad sweep would require domain review file by file. This plan proves the shared helper at two low-risk sites only.
  Date/Author: 2026-06-02 / Copilot (GPT-5.4)

- Decision: keep the parser-side `_read_text_simple` alias unchanged.
  Rationale: the deleted wrapper lived in `src/sattlint/engine.py`, while `sattline_parser.api._read_text_simple` is a separate internal alias used by parser tests and parser loading. Removing it would be unrelated scope.
  Date/Author: 2026-06-02 / Copilot (GPT-5.4)

- Decision: preserve draft-mode fallback order when switching engine extension lists to helpers.
  Rationale: `code_ext(mode)` and `deps_ext(mode)` provide the primary extension only. The safe consolidation here was to build the fallback list from those helpers rather than collapse draft-mode lookup to a single extension.
  Date/Author: 2026-06-02 / Copilot (GPT-5.4)

## Outcomes & Retrospective

- `scripts/run_pre_push_gate.py` was removed.
- `src/sattlint/engine.py` no longer carries the dead `_find_deps` and `_read_text_simple` wrappers.
- Engine extension-list duplication was reduced without changing lookup behavior.
- `iter_nested_modules` now backs the nested-module descent in `cyclomatic_complexity.py` and `scan_loop_resource_usage.py`.
- Focused validation passed for the engine helper slice, the two analyzer slices, the touched source-file Pyright run, and the full parser test suite.
- The first full-suite run exposed an unrelated but real defect in active plan-file encodings. Normalizing this plan and the remaining non-UTF-8 active plan restored `tests/test_ai_work_map.py` and the repo-wide pytest gate.
- Final validation evidence: `tests/test_ai_work_map.py` passed (`16 passed`), and the full repo test suite passed (`2644 passed, 34 warnings`).

## Context and Orientation

The concrete dead-code targets for this plan were:

- `scripts/run_pre_push_gate.py`, which had zero non-plan references.
- `engine._find_deps`, which only delegated to `_find_deps_with_context(..., requester_dir=None)`.
- `engine._read_text_simple`, which only delegated to `read_text_with_fallback(path)`.

The helper reuse targets were:

- `_engine_syntax_helpers.code_ext(mode)` for primary code extensions.
- `_engine_syntax_helpers.deps_ext(mode)` for primary deps extensions.
- `analyzers/_walk_utils.iter_nested_modules(...)` for recursive nested-module traversal.

## Validation and Acceptance

Acceptance is met when all of the following are true:

1. `scripts/run_pre_push_gate.py` does not exist.
2. `engine._find_deps` and `engine._read_text_simple` do not exist in `engine.py`.
3. The engine helper tests that previously exercised those wrappers still pass after redirection.
4. `engine.py` contains fewer inline extension-list literals than before.
5. At least two analyzer walk helpers now use `iter_nested_modules`.
6. Touched source files pass Pyright, and repo pytest passes after this plan document is normalized to valid UTF-8.

## Idempotence and Recovery

The deleted code and script are recoverable from git if a hidden caller is discovered later. The extension-list changes are semantics-preserving because draft mode still tries the primary extension first and then the official fallback. The analyzer walk changes are limited to sites that already ignored `ModuleTypeInstance` recursion, which matches `iter_nested_modules(..., resolve_instance_submodules=None)`.

## Interfaces and Dependencies

No public API changes were introduced. The removed methods were private implementation details with no confirmed production consumers.
