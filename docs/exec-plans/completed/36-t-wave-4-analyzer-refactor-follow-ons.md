# T-Wave-4 Analyzer Refactor Follow-Ons

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

## Purpose / Big Picture

This plan closes T-018 and T-025 together. After this work lands, the variable analyzer will have one clearly named shared helper for const-candidate and related pure classification logic, and MMS interface analysis will be decomposed out of one 383-line function into smaller, testable helpers that preserve current report behavior. The observable proof is that variable-analysis and MMS-report tests still pass, while the large owner functions and files shrink instead of growing further.

## Progress

- [x] (2026-05-13) Create the ExecPlan and confirm `variables.py` already delegates `is_const_candidate` through `_variables_contracts.py`, while `variable_issue_collection.py` and `_variables_execution.py` still consume that contract-layer helper directly, and `src/sattlint/analyzers/mms.py` still contains a 383-line `analyze_mms_interface_variables` function inside an 835-line debt-ratcheted owner file.
- [x] (2026-05-15) Extract `src/sattlint/analyzers/variable_utils.py` and move `is_const_candidate` ownership there, with `variables.py` now importing the helper from the shared utility module instead of `_variables_contracts.py`.
- [x] (2026-05-15) Decompose MMS interface analysis into `src/sattlint/analyzers/_mms_interface_analysis.py`, leaving `analyze_mms_interface_variables` in `src/sattlint/analyzers/mms.py` as a thin coordinator.
- [x] (2026-05-15) Keep caller behavior stable and run focused tests plus touched-file quality gates: focused variable tests passed, focused MMS analyzer/report tests passed, `tests/test_analyzers_variables.py tests/devtools/test_mms_report.py` passed, and touched-file Ruff plus Pyright were clean.

## Surprises & Discoveries

Observation: the const-candidate logic is already partially extracted, but it lives in the wrong ownership seam.
Evidence: `is_const_candidate` is currently defined in `src/sattlint/analyzers/_variables_contracts.py`, even though the implementation is a pure datatype predicate that is consumed by issue collection and execution paths rather than by parameter-contract validation.

Observation: `mms.py` is already structural-ratchet-controlled and must shrink on touch.
Evidence: `artifacts/analysis/file_debt_ratchet.json` marks `src/sattlint/analyzers/mms.py` as `must_shrink` with a structural target of 500 lines, while the current file remains 835 lines.

Observation: the MMS monolith is concentrated inside nested local helpers.
Evidence: `analyze_mms_interface_variables` still contains nested `_collect_write_locations`, `_resolve_param_source`, `_build_param_map`, `_walk_typedef`, and `_walk_modules` functions, which makes reuse and isolated testing difficult.

Observation: the direct MMS entry-point behavior is covered in an adjacent analyzer fixture module even though the owner validation route stays on `tests/test_analyzers_variables.py`.
Evidence: targeted MMS analyzer checks live in `tests/_analyzers_variables_adjacent_analyzers.py`, while the owner-level regression proof still passes through `tests/test_analyzers_variables.py` because that umbrella file re-exports the adjacent analyzer scenarios.

## Decision Log

Decision: move the variable helper into a new small shared module instead of leaving it in `_variables_contracts.py`.
Rationale: the helper is not contract-specific, and leaving it in the contract file obscures ownership boundaries for future refactors.
Date/Author: 2026-05-13 / Copilot (GPT-5.4)

Decision: extract MMS helper logic into a sibling private module such as `src/sattlint/analyzers/_mms_interface_analysis.py` instead of adding more top-level code to `mms.py`.
Rationale: `mms.py` is debt-ratcheted and must shrink on touch. A sibling helper module is the safest path that improves structure without widening the owner file.
Date/Author: 2026-05-13 / Copilot (GPT-5.4)

Decision: preserve current analyzer and report behavior while changing ownership seams.
Rationale: this debt item is structural, not behavioral. Any new findings or report-format drift would make the refactor harder to validate and easier to reject.
Date/Author: 2026-05-13 / Copilot (GPT-5.4)

Decision: keep issue emission in `mms.py` but move inventory collection, typedef walking, and ICF-entry translation into `_mms_interface_analysis.py`.
Rationale: that split keeps the public analyzer entry point and final issue ordering easy to audit while still shrinking the ratcheted owner file substantially.
Date/Author: 2026-05-15 / Copilot (GPT-5.4)

## Outcomes & Retrospective

Both structural follow-ons landed without behavior drift. `is_const_candidate` now lives in `src/sattlint/analyzers/variable_utils.py`, `_variables_contracts.py` no longer owns that pure predicate, and `variables.py` keeps the same facade alias surface for downstream execution and issue-collection helpers.

The MMS entry point now delegates to top-level helpers in `src/sattlint/analyzers/_mms_interface_analysis.py` for write-location collection, parameter-source resolution, parameter-map building, typedef walking, module walking, and ICF inventory translation. `src/sattlint/analyzers/mms.py` shrank from 835 lines to 210 lines, which satisfies the must-shrink constraint and leaves the final report assembly and issue emission easy to inspect.

Validation stayed green at each step: focused variable helper tests passed, focused MMS analyzer/report tests passed, `python scripts/run_repo_python.py -m pytest --no-cov tests/test_analyzers_variables.py tests/devtools/test_mms_report.py -x -q --tb=short` passed with 64 tests, and touched-file Ruff plus Pyright both passed after a small import-order and shadowing cleanup.

## Context and Orientation

The variable analyzer’s main owner file is `src/sattlint/analyzers/variables.py`. It imports `is_const_candidate` from `src/sattlint/analyzers/_variables_contracts.py`, exposes it through `VariablesAnalyzer.is_const_candidate`, and relies on it from `src/sattlint/analyzers/_variables_execution.py` and `src/sattlint/analyzers/variable_issue_collection.py`. The remaining debt is to move this pure classification helper into a home that matches its responsibility.

The MMS owner surface is `src/sattlint/analyzers/mms.py`. That file owns the public `analyze_mms_interface_variables` entry point, plus ICF loading and report generation support. The current debt is not that the analyzer is missing; it is that the interface-analysis path still concentrates too many responsibilities in one long function inside a ratcheted oversized file.

The nearest tests are `tests/test_analyzers_variables.py` for variable-analysis behavior and `tests/devtools/test_mms_report.py` for MMS report behavior. Stay focused there before widening to broader analyzer suites.

## Plan of Work

Start with T-018. Create a new shared helper module such as `src/sattlint/analyzers/variable_utils.py` and move `is_const_candidate` there, along with any adjacent pure predicates that are reused outside contract validation. Update `variables.py`, `_variables_execution.py`, and `variable_issue_collection.py` to import from the new module. Keep `variable_traversal.py` as a traversal-only wrapper surface.

Then implement T-025 by extracting the nested helper blocks from `analyze_mms_interface_variables` into a sibling private module. Preserve the public entry point in `mms.py`, but make it a thin coordinator that delegates to named helper functions for write-location collection, parameter-source resolution, parameter-map building, typedef walking, and module walking. Because `mms.py` is ratcheted `must_shrink`, prefer extraction over additional inline cleanup.

After both extractions, rerun the owner tests before doing any secondary cleanup. If one helper cannot move cleanly without changing behavior, keep the behavior stable first and record the remaining structural gap here rather than widening scope mid-slice.

## Concrete Steps

Run all commands from the repository root.

Inspect the current helper ownership and long MMS function before editing code:

    rg -n "is_const_candidate|analyze_mms_interface_variables" src/sattlint/analyzers/variables.py src/sattlint/analyzers/_variables_contracts.py src/sattlint/analyzers/_variables_execution.py src/sattlint/analyzers/variable_issue_collection.py src/sattlint/analyzers/mms.py

After implementing the helper extraction and MMS decomposition, run the narrow validation first:

    python scripts/run_repo_python.py -m pytest --no-cov tests/test_analyzers_variables.py tests/devtools/test_mms_report.py -x -q --tb=short

Run touched-file quality gates after the focused tests pass:

    python scripts/run_repo_python.py -m ruff check src/sattlint/analyzers/variable_utils.py src/sattlint/analyzers/_variables_contracts.py src/sattlint/analyzers/_variables_execution.py src/sattlint/analyzers/variable_issue_collection.py src/sattlint/analyzers/mms.py src/sattlint/analyzers/_mms_interface_analysis.py tests/test_analyzers_variables.py tests/devtools/test_mms_report.py
    python scripts/run_repo_python.py -m pyright src/sattlint/analyzers/variable_utils.py src/sattlint/analyzers/_variables_contracts.py src/sattlint/analyzers/_variables_execution.py src/sattlint/analyzers/variable_issue_collection.py src/sattlint/analyzers/mms.py src/sattlint/analyzers/_mms_interface_analysis.py

## Validation and Acceptance

Acceptance requires stable behavior and clearer ownership. The variable analyzer must still report the same const-candidate-driven issues, but the helper must no longer live in a contract-specific file. The MMS analyzer must still produce the same interface findings and report payloads, but `analyze_mms_interface_variables` must be reduced to a coordinator that delegates to smaller helpers, and `mms.py` must shrink rather than grow.

## Idempotence and Recovery

This plan is safe to land in two small slices. Move the variable helper first and validate it. Then extract the MMS helper module and rerun the same owner tests. If the MMS extraction changes report ordering or wording, stabilize the output before continuing structural cleanup.

## Artifacts and Notes

Import diff: `src/sattlint/analyzers/variables.py` no longer imports `is_const_candidate` from `_variables_contracts`; it now imports the helper from `variable_utils` while keeping the existing analyzer alias surface stable.

Line-count comparison: `src/sattlint/analyzers/mms.py` moved from 835 lines before the slice to 210 lines after the extraction, with the extracted helper logic living in `src/sattlint/analyzers/_mms_interface_analysis.py`.

## Interfaces and Dependencies

The implementation surface is `src/sattlint/analyzers/variables.py`, `src/sattlint/analyzers/_variables_contracts.py`, `src/sattlint/analyzers/_variables_execution.py`, `src/sattlint/analyzers/variable_issue_collection.py`, and `src/sattlint/analyzers/mms.py`. The preferred new helper seams are `src/sattlint/analyzers/variable_utils.py` and `src/sattlint/analyzers/_mms_interface_analysis.py`. Keep public entry points stable and reuse existing analyzer data structures instead of inventing new report formats.
