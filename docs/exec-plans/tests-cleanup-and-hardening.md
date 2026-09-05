# Tests Cleanup and Confidence Hardening

> Status: Draft — not started
> Depends on: nothing
> Scope: `tests/` layout, naming, coverage gaps, and analyzer FP/FN confidence

## Goal

Clean up the `tests/` tree so the layout matches the `src/` structure and the
legacy `_partN` file naming is replaced with descriptive topic names, then
close the concrete coverage and false-positive / false-negative (FP/FN)
confidence gaps that a review of the suite uncovered.

## Context

The suite is large and mature (149 Python files) but sits in two organizational
"eras":

- **Good convention** already exists under `tests/analyzers/` (one file per
  analyzer, matching `src/sattlint/analyzers/<module>.py`), plus `tests/graphics/`,
  `tests/helpers/`, and `tests/fixtures/`.
- **Legacy flat files** at the repo root still use `_partN` numbering across four
  families: `state` (6), `suites` (6), `variables` (5 + 8 `part4_*` splinters),
  `app_analysis` (4 + `project_cache`).

The review also surfaced confidence limits that a refactor alone would not fix
(see Phase C). These are worth addressing in the same effort because a re-touch
of the analyzer test surface is the natural moment to strengthen it.

## Findings (summary)

1. **Two helper conventions collide:** root-level `_*_support.py` /
   `_*_test_api.py` files vs the proper `tests/helpers/` directory.
2. **`_partN` families** map to: `state` = state-integrity analyzers (reset
   contamination, implicit latch, SFC step contract, write-without-effect,
   global coupling, fan-in/out, plus variables-report summary); `suites` =
   end-to-end registry-driven runs of many analyzers; `variables` = the
   `analyzers.variables` package + resolution + graphics picture-display;
   `app_analysis` = `application/`, `project/`, `cache/`, `models.project_graph`.
3. **`part4` of the variables family is half-split** — descriptive `part4_*`
   files exist but a leftover `test_analyzers_variables_part4.py` remains.
4. **Empty placeholders:** `test_validation_expression_semantics.py` and
   `test_validation_sequences_semantics.py` are 0 bytes; the whole
   `src/sattlint/validation/` package has no test that imports it.
5. **Duplication:** reset-contamination is spread across root `state_*`,
   `test_reset_contamination_ratchet*.py`, and `tests/analyzers/test_reset_contamination.py`;
   the `suites_*` files re-test analyzers that already have dedicated files.
6. **`tests/benchmarks/` is empty.**
7. **Analyzer FP/FN confidence is bounded** (details in Phase C):
   - Expectations are self-authored (tautological vs external ground truth).
   - The corpus exactness harness only selects `semantic.*`-prefixed manifests
     and only runs the semantic analyzer, so ~15 analyzers with committed
     manifests (state-inference, mms, naming, spec, data-dependency,
     resource-usage, version-drift, picture-display, cyclomatic-complexity,
     parameter-drift, loop-output-refactor, scan-loop-resource-usage,
     timing/dataflow) are silently skipped.
   - Assertions are positive-heavy; negative-control coverage is uneven.
   - No FP/FN rate is measured (coverage measures lines, not behavior).

## Phases

### Phase A — Relocate root support/helper files into `tests/helpers/`

Move the root `_*` modules into `tests/helpers/` with descriptive names and
update all `from tests._x import ...` references:

| Current (tests/) | Target (tests/helpers/) |
| --- | --- |
| `_analyzers_state_test_support.py` | `analyzers_state_support.py` |
| `_analyzers_suites_test_support.py` | `analyzers_suites_support.py` |
| `_analyzers_variables_test_support.py` | `analyzers_variables_support.py` |
| `_analyzers_variables_part4_support.py` | fold into `analyzers_variables_support.py` (after Phase B) |
| `_app_analysis_test_support.py` | `app_analysis_support.py` |
| `_app_menus_support.py` | `app_menus_support.py` |
| `_reset_contamination_test_api.py` | `reset_contamination_api.py` |

Acceptance: no `from tests._...` imports remain; focused pytest green.

### Phase B — Create topic subdirectories and rename `_partN` files

Introduce subdirectories mirroring `src/` and move + rename the flat families
(drops, not merges, to keep the pass low-risk). Verify with a focused pytest run
after each batch.

**`tests/analyzers/state_integrity/`** (from `state`, reporting bits moved to
Phase D):

| Current | Proposed |
| --- | --- |
| `state_part1` | `test_reset_contamination_paths.py` |
| `state_part2` | `test_reset_latch_helpers.py` |
| `state_part3` | `test_implicit_latch_and_sfc_contract.py` |
| `state_part4` | `test_sfc_contract_and_global_coupling.py` |
| `state_part5` | `test_fan_in_out.py` (report-summary funcs → Phase D) |
| `state_part6` | `test_effect_flow_tracker.py` (report-summary funcs → Phase D) |

**`tests/analyzers/suites/`** (integration-style registry runs; keep together):

| Current | Proposed |
| --- | --- |
| `suites_part1` | `test_sfc_dataflow_variables.py` |
| `suites_part2` | `test_dataflow_sfc_transition_versiondrift.py` |
| `suites_part3` | `test_versiondrift_initialvalues_registry.py` |
| `suites_part4` | `test_naming_alarm_integrity.py` |
| `suites_part5` | `test_safety_taint_mms_usage.py` |
| `suites_part6` | `test_module_diff_sfc_guard.py` |

**`tests/analyzers/variables/`** (the `variables` family + root `test_variables_*`
files): rename `part1..5` by topic (mapping/contracts, magic/shadowing/layout,
ui-only/external-usage, library-typedef, execution/issue-collection); drop the
`part4_` prefix from the seven splinters and fold the four leftover functions in
`test_analyzers_variables_part4.py` into the matching new file.

**`tests/app/`** (CLI/TUI/application): `test_app_*`, `test_cli*`;
`test_app_analysis_part1..4` → `test_analysis_run/checks/loading/load_project.py`;
`test_app_analysis_project_cache.py` → `test_analysis_project_cache.py`.

**`tests/core/`**: `test_ast_tools.py`, `test_semantic_*.py`,
`test_context_builder.py`, `test_parser_compatibility.py`.

**`tests/project/`**: `test_project_io.py`, `test_project_graph_invariants.py`.

**`tests/reporting/`**: `test_record_component_order_*.py`, the `variables_report`
summary tests pulled from `state_part5/6`, `test_semantic_analysis.py`.

**`tests/cache/`**: `test_cache_classes.py`, cache-focused funcs from
`test_app_analysis_project_cache.py`.

Acceptance: no `test_*_partN.py` files remain; each new directory runs green.

### Phase C — Confidence hardening (analyzer FP/FN)

Directly addresses the confidence review. Highest value first.

**C1 — Activate the existing corpus manifests (highest value, low effort).**
In `test_corpus_regression_exactness.py`:
- Drop the `semantic.`-prefix filter in `_iter_analyzer_manifests`
  (tests/test_corpus_regression_exactness.py:33-36) so every manifest with
  non-empty `expected_finding_ids` is selected.
- Route each manifest to its actual analyzer entrypoint (or the umbrella runner
  that emits `state_inference.*`, `mms.*`, `naming.*`, `spec.*`, etc.) instead of
  always calling `analyze_sattline_semantics` (lines 46-48).

This immediately turns on FP/FN exactness checks for ~15 analyzers whose
manifests already exist but are currently dead weight — including
state-inference, which otherwise has almost no other coverage.

Acceptance: `test_corpus_regression_exactness` collects and runs the full set of
`analyzer-*.json` manifests (not just `semantic.*`); all pass.

**C2 — Add negative-control twins.** For each finding kind across the analyzer
tests, add a deliberate near-miss case that must produce **zero** findings
(the anti-false-positive half), matching the positive "detected" cases.

**C3 — Mutation smoke check (cheap ground-truth proxy).** Script that
temporarily disables or inverts one rule and asserts the relevant test fails —
proving the tests can catch false negatives. Keep it out of normal CI (a
dev/review aid), or gate it to a separate marker.

**C4 — Break the tautology.** Have corpus expectations independently reviewed
by someone other than the analyzer author, or add a small human-labeled golden
set, so expectations are not only the author's word.

**C5 — Fill `validation` coverage.** Replace the two empty placeholders with
real tests for `validation/expression.py` and `validation/sequences.py`
semantics, plus `structure_*` / `type_helpers` where not transitively covered.

### Phase D — Consolidate duplication (separate, lower-risk pass)

- Merge root `state_part1/2` reset-contamination tests into
  `tests/analyzers/test_reset_contamination.py` and the
  `test_reset_contamination_ratchet*.py` set — only after Phase B and a coverage
  baseline; verify test counts are preserved.
- Decide whether `tests/analyzers/suites/` stays as a deliberate integration
  seam (recommended) or folds into per-analyzer files.

### Phase E — Final gates

- Regenerate `coverage.xml`/`htmlcov` and use the fresh report to confirm no
  module is near-zero beyond the known gaps (validation, state-inference).
- Delete the empty `tests/benchmarks/` dir or populate it.
- Update `docs/maintainers/repo-map.md` if it enumerates test files; confirm
  `.github/instructions/*.md` surfaces still match.

## Dependency order

A → B → C (C1 first, then C2–C5 as time allows) → D → E.

Recommended execution order: **A, B** (each batch verified), then **C1** (the
highest-value, lowest-risk confidence fix), then **C5 + C2**, then **D**, then **E**.

## Definition of Done

- `tests/` layout mirrors `src/`; no `test_*_partN.py` files remain.
- All root `_*` support modules live under `tests/helpers/` with updated imports.
- The corpus exactness harness runs every analyzer manifest (not just
  `semantic.*`) against its real analyzer.
- Validation package and state-inference have real behavioral coverage.
- Full suite, ruff, and pyright green on the touched slice.

## Gates

Focused pytest after every move/rename batch; `python -m pytest -q --tb=short`
and `python -m ruff check tests` + `python -m ruff format --check tests` at the
end. Commits are performed by the user per repository policy (git write commands
are not run by the assistant).
