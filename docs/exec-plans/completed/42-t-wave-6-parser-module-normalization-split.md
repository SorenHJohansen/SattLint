# T-Wave-6 Parser Module Normalization Split

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

## Purpose / Big Picture

This plan addresses the parser-side structural debt surfaced by the 2026-05-15 architecture review. `src/sattline_parser/transformer/_modules_mixin.py` still concentrates module-header parsing, layout extraction, base-picture assembly, and module-body normalization in one 42-method mixin. After this work lands, the parser will still build the same abstract syntax tree, but the module normalization logic will be split into smaller helpers that are safer to extend when the grammar changes.

The observable proof is that `sattlint syntax-check` still behaves strictly on real corpus files, parser-core tests remain green, and `_modules_mixin.py` stops being the single point where every module-shape change must land.

## Progress

- [x] (2026-05-15) Create the ExecPlan and confirm `src/sattline_parser/transformer/_modules_mixin.py` is 919 lines, the architecture review flags `_ModulesMixin` at 42 methods, and `artifacts/analysis/file_debt_ratchet.json` still marks the owner as structural `must_shrink`.
- [x] (2026-05-15) Extract module-header, coordinate or layout, and base-picture assembly helpers into `src/sattline_parser/transformer/_module_header_mixin.py`, `src/sattline_parser/transformer/_module_layout_mixin.py`, `src/sattline_parser/transformer/_module_assembly_mixin.py`, with shared pure helpers in `src/sattline_parser/transformer/_module_shared.py`, while preserving source-span, invoke-coord, and module-body behavior.
- [x] (2026-05-15) Update the transformer composition surface so `sl_transformer.py` now composes the dedicated module mixins directly while `_modules_mixin.py` remains a compatibility facade for existing imports and test harnesses.
- [x] (2026-05-15) Add a focused parser regression in `tests/parser/_parser_core_part6.py` that parses the real `tests/fixtures/corpus/valid/NestedSubmodules.s` fixture through the parser entrypoint and asserts nested moduletype and submodule assembly.
- [x] (2026-05-15) Rerun strict syntax-check first, then narrow parser pytest, then touched-file Ruff and Pyright.

## Surprises & Discoveries

Observation: `_modules_mixin.py` already contains useful top-level helper functions.
Evidence: `_float_tuple`, `_coord_pair`, `_meta_span`, and `_flatten_items` are already small seams that can stay as shared helpers while the class methods are split by responsibility.

Observation: the heaviest coupling is around module-header parsing and base-picture assembly.
Evidence: `module_header` and `base_picture_module` currently coordinate names, coordinates, arguments, zoom metadata, layer info, datatype definitions, moduletype definitions, local variables, and submodule collection.

Observation: parser work here must preserve strict behavior.
Evidence: the repository invariants require three header `STRING` lines before `BasePicture`, strict `syntax-check` behavior, and no silent fallback behavior anywhere in the parser path.

Observation: the old `_modules_mixin.py` import path is part of the current test surface.
Evidence: `tests/parser/_parser_core_test_support.py` imports `_ModulesMixin`, `_flatten_items`, and `_meta_span` from `_modules_mixin.py`, so a compatibility facade avoids unnecessary churn while the owner file shrinks.

## Decision Log

Decision: split by grammar responsibility rather than by arbitrary line count.
Rationale: future parser changes will be easier to route if header parsing, layout extraction, and module-body assembly live in separate, obvious files.
Date/Author: 2026-05-15 / Copilot (GPT-5.4)

Decision: keep AST shape and source-span behavior stable while shrinking the mixin.
Rationale: the parser's public value is correctness, not internal file layout. The split should not alter emitted nodes or weaken strict validation.
Date/Author: 2026-05-15 / Copilot (GPT-5.4)

Decision: validate through parser entrypoints and corpus fixtures instead of direct helper tests first.
Rationale: the helper layout is an internal refactor. The safest proof is that real parser behavior stays unchanged.
Date/Author: 2026-05-15 / Copilot (GPT-5.4)

Decision: keep `_modules_mixin.py` as a thin compatibility wrapper that re-exports the shared helpers.
Rationale: this preserves existing harness imports while still moving the behavioral code into smaller sibling modules, which reduces migration risk and keeps the refactor focused on structure rather than import churn.
Date/Author: 2026-05-15 / Copilot (GPT-5.4)

## Outcomes & Retrospective

The module-normalization split landed as planned. `sl_transformer.py` now composes dedicated header, layout, and assembly mixins directly; `_modules_mixin.py` shrank into a compatibility facade; and the shared pure helpers moved into `_module_shared.py` so the sibling mixins can reuse source-span, flattening, coordinate, and submodule collectors without circular imports.

Validation passed in the planned order:

    bash scripts/run_repo_python.sh -m sattlint syntax-check tests/fixtures/corpus/valid/VariableModifiers.s
    bash scripts/run_repo_python.sh -m pytest --no-cov tests/parser/test_parser.py tests/parser/test_parser_core.py tests/parser/test_parser_validation.py tests/parser/test_parser_decode.py -x -q --tb=short
    bash scripts/run_repo_python.sh -m ruff check src/sattline_parser/transformer/_modules_mixin.py src/sattline_parser/transformer/_module_shared.py src/sattline_parser/transformer/_module_header_mixin.py src/sattline_parser/transformer/_module_layout_mixin.py src/sattline_parser/transformer/_module_assembly_mixin.py src/sattline_parser/transformer/sl_transformer.py tests/parser/_parser_core_part6.py
    bash scripts/run_repo_python.sh -m pyright src/sattline_parser/transformer/_modules_mixin.py src/sattline_parser/transformer/_module_shared.py src/sattline_parser/transformer/_module_header_mixin.py src/sattline_parser/transformer/_module_layout_mixin.py src/sattline_parser/transformer/_module_assembly_mixin.py src/sattline_parser/transformer/sl_transformer.py tests/parser/_parser_core_part6.py

The focused parser slice stayed green, including the new real-fixture regression for nested moduletype assembly.

## Context and Orientation

The controlling file is `src/sattline_parser/transformer/_modules_mixin.py`. In this repository, a "mixin" is a class that contributes grammar transformation methods to the main transformer. `_ModulesMixin` currently owns the parser behavior for module headers, base-picture modules, argument trees, layout metadata, and module-body flattening.

The composition surface is `src/sattline_parser/transformer/sl_transformer.py`. That file combines the mixins into the concrete transformer used by the parser API. If this plan creates new sibling mixins, `sl_transformer.py` must be updated so parser entrypoints continue to work the same way.

The closest tests are `tests/parser/test_parser.py`, `tests/parser/test_parser_core.py`, `tests/parser/test_parser_validation.py`, and `tests/parser/test_parser_decode.py`. The strict CLI proof path is `sattlint syntax-check` against real corpus or fixture files.

## Plan of Work

Start by separating the highest-signal responsibilities inside `_ModulesMixin`. Move module-header parsing into `src/sattline_parser/transformer/_module_header_mixin.py`, move layout or coordinate extraction into `src/sattline_parser/transformer/_module_layout_mixin.py`, and move base-picture or module-body assembly into `src/sattline_parser/transformer/_module_assembly_mixin.py`. Keep the small top-level helper functions shared when they are already pure and well named.

Update the transformer composition in `sl_transformer.py` only as much as needed to wire in the new helper classes. Do not change grammar rule names, tree tags, or AST node classes as part of this split.

When tests need updates, prefer validating through parser inputs and resulting behavior instead of locking the plan to one private helper layout. The internal file structure may evolve again, but the parser output contract must remain stable.

## Concrete Steps

Run all commands from the repository root.

Inspect the current mixin and composition surfaces before editing code:

    wc -l src/sattline_parser/transformer/_modules_mixin.py
    rg -n "class _ModulesMixin|def module_header|def base_picture_module|def module_body|def base_module_body" src/sattline_parser/transformer/_modules_mixin.py src/sattline_parser/transformer/sl_transformer.py

After the split lands, run the strict parser proof first:

    bash scripts/run_repo_python.sh -m sattlint syntax-check tests/fixtures/corpus/valid/VariableModifiers.s

Then run the narrow parser pytest slice:

    bash scripts/run_repo_python.sh -m pytest --no-cov tests/parser/test_parser.py tests/parser/test_parser_core.py tests/parser/test_parser_validation.py tests/parser/test_parser_decode.py -x -q --tb=short

Run touched-file quality gates after the focused checks pass:

    bash scripts/run_repo_python.sh -m ruff check src/sattline_parser/transformer/_modules_mixin.py src/sattline_parser/transformer/_module_header_mixin.py src/sattline_parser/transformer/_module_layout_mixin.py src/sattline_parser/transformer/_module_assembly_mixin.py src/sattline_parser/transformer/sl_transformer.py tests/parser/test_parser.py tests/parser/test_parser_core.py tests/parser/test_parser_validation.py tests/parser/test_parser_decode.py
    bash scripts/run_repo_python.sh -m pyright src/sattline_parser/transformer/_modules_mixin.py src/sattline_parser/transformer/_module_header_mixin.py src/sattline_parser/transformer/_module_layout_mixin.py src/sattline_parser/transformer/_module_assembly_mixin.py src/sattline_parser/transformer/sl_transformer.py

## Validation and Acceptance

Acceptance requires stable parser behavior. `sattlint syntax-check` must continue to pass on known-valid fixtures and fail strictly on invalid ones. The focused parser tests must stay green. The mixin must shrink because responsibility moved into clearly named sibling helpers, not because behavior was deleted or hidden behind dynamic dispatch that makes the parser harder to debug.

## Idempotence and Recovery

This plan is safe to execute one responsibility cluster at a time. Move header parsing first and rerun the same parser proof. Then move base-picture assembly or layout handling. If one split changes AST shape, immediately restore the old helper path or wrapper and keep the public behavior stable before attempting another extraction.

## Artifacts and Notes

Current owner facts at plan creation time:

    919 src/sattline_parser/transformer/_modules_mixin.py
    structural class budget finding: _ModulesMixin has 42 methods

The structural debt reason recorded in `artifacts/analysis/file_debt_ratchet.json` is: parser transformer owner surface still centralizes grammar-to-AST normalization.

## Interfaces and Dependencies

The implementation surface is `src/sattline_parser/transformer/_modules_mixin.py` and `src/sattline_parser/transformer/sl_transformer.py`. Preserve the current AST model classes in `src/sattline_parser/models/ast_model.py`, the current tree-tag constants, and the strict parser behavior required by `sattlint syntax-check`.
