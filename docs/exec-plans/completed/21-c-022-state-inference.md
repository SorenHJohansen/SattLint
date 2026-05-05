# C-022 State Inference

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

## Purpose / Big Picture

This plan turns the current implicit dataflow reasoning into an explicit state-inference feature. After this change, a user will be able to run a dedicated analyzer that infers stable ranges and coarse behavioral states from SattLine code and reports when the inferred state makes later logic contradictory, incomplete, or suspicious. The visible outcome is a new analyzer surface with focused findings and tests, not just additional internal bookkeeping inside `dataflow`.

## Progress

- [x] (2026-05-04) Create the ExecPlan and map the feature onto the existing dataflow and analyzer-registration seams.
- [x] (2026-05-04) Create a dedicated `state_inference` analyzer module that builds on current dataflow state tracking without duplicating the walker.
- [x] (2026-05-04) Register the new analyzer and expose it through the normal non-interactive analysis path as an opt-in CLI-selectable analyzer.
- [x] (2026-05-04) Add focused regression tests for inferred ranges, inferred boolean state, and impossible comparisons.
- [x] (2026-05-04) Validate the new analyzer with narrow pytest, Ruff, and Pyright checks before considering broader rollout.
- [x] (2026-05-05) Move this plan to `docs/exec-plans/completed/` once the implementation and validation evidence are complete.

## Surprises & Discoveries

- Observation: a significant part of the reasoning needed for state inference already exists inside the dataflow analyzer.
  Evidence: `src/sattlint/analyzers/dataflow.py` already tracks `StateMap`, merges branch state in `_merge_states()`, evaluates conditions in `_evaluate_condition()`, and evaluates expressions in `_evaluate_expression()`.
- Observation: the current repository already tests inferred contradiction behavior, but only as a side effect of `dataflow` findings rather than as an explicit state-inference report.
  Evidence: `tests/test_dataflow.py` and `tests/test_analyzers_suites.py` already assert impossible comparisons, always-true or always-false conditions, and unreachable branches.
- Observation: explicit CLI analyzer selection was narrower than the declared CLI exposure metadata.
  Evidence: `src/sattlint/app.py` previously supplied `get_default_cli_analyzers()` into the non-interactive `run_checks()` path, so `--check state_inference` would not have been reachable until the selectable-analyzer path widened to all declared CLI analyzers.

## Decision Log

- Decision: implement state inference as a dedicated analyzer module rather than quietly expanding `dataflow` output in place.
  Rationale: users need a discoverable, named feature with its own regression suite and rollout policy; hiding it inside `dataflow` would make scope and expectations ambiguous.
  Date/Author: 2026-05-04 / Copilot (GPT-5.4)
- Decision: make the first milestone opt-in through analyzer selection rather than adding it to the default analyzer set immediately.
  Rationale: inferred-state findings can be high value but also high noise if introduced without focused false-positive tuning.
  Date/Author: 2026-05-04 / Copilot (GPT-5.4)
- Decision: reuse the existing dataflow walker through a shared collection seam and keep default CLI analyzer behavior unchanged.
  Rationale: the feature needed explicit analyzer reachability and summary output, but duplicating the walker or silently widening default CLI runs would add unnecessary risk.
  Date/Author: 2026-05-04 / Copilot (GPT-5.4)

## Outcomes & Retrospective

Planning baseline only. The intended end state is an explicit analyzer that produces reproducible state-inference findings and summaries while leaving current `dataflow` behavior intact unless a shared helper extraction is deliberately validated.

First implementation milestone landed. The analyzer now reuses the existing dataflow walker through a shared collection seam, is exposed to `sattlint analyze --check state_inference` without joining the default analyzer run list, and has dedicated focused tests for numeric contradictions, stable boolean state, and summary output.

Closeout outcome complete. The touched validation slice passed after the final summary-state cleanup: focused pytest finished at `77 passed`, Ruff passed on the edited files, and Pyright reported `0 errors, 0 warnings, 0 informations`. The plan now moves to `docs/exec-plans/completed/` so `docs/exec-plans/active/` only reflects unfinished execution surfaces.

## Context and Orientation

The current semantic owner surface for this feature is `src/sattlint/analyzers/dataflow.py`. That file already walks module code, branches, sequences, SFC steps, and nested module scopes while maintaining a typed map of known values. It is therefore the nearest controlling code path for range and state inference. The analyzer framework and registration layer live under `src/sattlint/analyzers/framework.py` and `src/sattlint/analyzers/registry.py`. The user-facing non-interactive analysis flow is wired through `src/sattlint/app_analysis.py`, `src/sattlint/app.py`, and `src/sattlint/cli/entry.py`.

There is no `src/sattlint/analyzers/state_inference.py` yet, and there is no dedicated test file for this feature. The nearest test surfaces are `tests/test_dataflow.py`, which covers low-level path and state reasoning, and `tests/test_analyzers_suites.py`, which covers analyzer-style scenarios with compact AST fixtures. Those tests should seed the new suite instead of being rewritten from scratch.

In this plan, "state inference" means deriving a conservative summary such as "this symbol is always `True` here", "this symbol stays within a known numeric interval", or "this comparison can never succeed after the preceding assignments." It does not mean theorem proving, solver integration, or whole-repository fixed-point analysis.

## Plan of Work

Begin by extracting the minimum reusable state facts from `src/sattlint/analyzers/dataflow.py`. Do not fork the entire walker. The new analyzer should either call a shared internal helper that yields inferred facts or reuse a small extracted layer that already understands state maps, branch merges, and path-local assignments. Keep the existing `analyze_dataflow()` entry point behavior-preserving during this extraction.

Create `src/sattlint/analyzers/state_inference.py` with a clear public entry point such as `analyze_state_inference(base_picture, unavailable_libraries=None)`. The report should carry two kinds of output: user-visible findings for clearly suspicious states, and a compact summary for inferred ranges or booleans that downstream tools can inspect. Use the existing `Issue` and `SimpleReport` patterns already used by other analyzers.

Register the analyzer in `src/sattlint/analyzers/registry.py` and thread it through the analysis surface in `src/sattlint/app_analysis.py`. The first implementation should be explicitly selectable, for example through `sattlint analyze --check state_inference`, rather than silently joining the default analyzer catalog. Update any registry or configuration tests that assert the available analyzer keys.

Add a focused new test file, `tests/test_state_inference.py`. Seed it with three categories of scenarios. First, numeric range inference where simple assignments and comparisons prove that a later branch is impossible. Second, boolean state inference where a flag is definitely set or definitely cleared before a guard. Third, state-machine-style inference where a small sequence of assignments implies a stable mode or phase label that a later branch contradicts. Reuse the compact AST construction style already present in `tests/test_dataflow.py` and `tests/test_analyzers_suites.py`.

Once the dedicated suite passes, add one or two targeted integration assertions to `tests/test_app_analysis.py` or `tests/test_cli.py` so the feature is proven reachable through the normal non-interactive analyzer path.

## Concrete Steps

Run all commands from the repository root.

Inspect the existing dataflow and analyzer registration seams:

    rg -n "def analyze_dataflow|def _evaluate_condition|def _evaluate_expression|def _merge_states" src/sattlint/analyzers/dataflow.py
    rg -n "registry|default analyzer|run_analyze_command|selected_keys" src/sattlint/analyzers/registry.py src/sattlint/app_analysis.py src/sattlint/app.py tests/test_app_analysis.py tests/test_cli.py

After implementing the new analyzer and its tests, run the narrow validation first:

    & ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_state_inference.py tests/test_dataflow.py tests/test_app_analysis.py tests/test_cli.py -x -q --tb=short

Exercise the new analyzer through the normal CLI path:

    & ".venv/Scripts/python.exe" -m sattlint.app analyze --check state_inference

Run touched-file quality gates after the focused tests pass:

    & ".venv/Scripts/python.exe" -m ruff check src/sattlint/analyzers/state_inference.py src/sattlint/analyzers/dataflow.py src/sattlint/analyzers/registry.py src/sattlint/app_analysis.py tests/test_state_inference.py tests/test_dataflow.py tests/test_app_analysis.py tests/test_cli.py
    & ".venv/Scripts/python.exe" -m pyright src/sattlint/analyzers/state_inference.py src/sattlint/analyzers/dataflow.py src/sattlint/analyzers/registry.py src/sattlint/app_analysis.py

Expected success signal: the CLI accepts `state_inference` as a valid analyzer key, the dedicated test file passes, and at least one state-inference scenario produces a finding or summary that was not available as a dedicated surface before the change.

## Validation and Acceptance

Acceptance requires that state inference becomes a first-class analyzer, not just a hidden helper. A user must be able to select it through the normal non-interactive analysis path and observe a stable report. The new tests in `tests/test_state_inference.py` must fail before the implementation and pass after it. Existing `dataflow` tests must continue to pass, proving the extraction did not weaken current reasoning.

The analyzer must be conservative. It should only emit findings when the inferred state is strong enough to justify them. Ambiguous paths should remain unknown rather than being guessed. Numeric ranges must be bounded only when the code truly constrains them. Boolean state must distinguish definite true, definite false, and unknown. If a later branch depends on unknown state, the analyzer must avoid emitting impossible-condition findings.

## Idempotence and Recovery

This plan is safe to execute in small steps. The safest order is helper extraction, dedicated analyzer implementation, registration, then CLI reachability tests. If the extraction from `dataflow` introduces regressions, stop and restore behavior by keeping the shared helper private and behavior-preserving before adding any new findings. If the new analyzer proves too noisy, keep it registered but opt-in only until the false-positive cases are covered by tests.

## Artifacts and Notes

Capture these artifacts as work proceeds: one passing transcript from `tests/test_state_inference.py`, one CLI run showing `--check state_inference` works, and one short before-and-after example demonstrating a branch that was previously only an implicit `dataflow` consequence but is now explicitly reported by the new analyzer.

The first milestone should also record the chosen finding IDs and summary schema in a short indented example, updated to the exact names used during implementation.

Recorded closeout validation:

    & ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_state_inference.py tests/test_dataflow.py tests/test_app_analysis.py tests/test_cli.py::test_run_cli_analyze_passes_opt_in_state_inference_key tests/test_analyzers_suites.py::test_state_inference_analyzer_is_not_in_default_cli_subset -x -q --tb=short
    77 passed in 2.20s

    & ".venv/Scripts/python.exe" -m ruff check src/sattlint/analyzers/dataflow.py src/sattlint/analyzers/state_inference.py src/sattlint/analyzers/registry.py src/sattlint/app.py tests/test_state_inference.py tests/test_dataflow.py tests/test_analyzers_suites.py tests/test_app_analysis.py tests/test_cli.py
    All checks passed!

    & ".venv/Scripts/python.exe" -m pyright src/sattlint/analyzers/dataflow.py src/sattlint/analyzers/state_inference.py src/sattlint/analyzers/registry.py src/sattlint/app.py tests/test_state_inference.py tests/test_dataflow.py tests/test_analyzers_suites.py tests/test_app_analysis.py tests/test_cli.py
    0 errors, 0 warnings, 0 informations

The touched CLI file still contains unrelated pre-existing drift in broader simulate-command coverage, so the closeout evidence records the exact touched CLI assertion rather than claiming the whole legacy `tests/test_cli.py` file is green.

## Interfaces and Dependencies

The core dependency is `src/sattlint/analyzers/dataflow.py`, especially the current `StateMap` reasoning and the helpers around `_evaluate_condition()`, `_evaluate_expression()`, `_merge_states()`, and `analyze_dataflow()`. The new public analyzer entry point belongs in `src/sattlint/analyzers/state_inference.py`. Registration and discoverability must be handled in `src/sattlint/analyzers/registry.py` and `src/sattlint/app_analysis.py`. User-facing execution continues to flow through `src/sattlint/app.py` and `src/sattlint/cli/entry.py`. The initial dedicated tests belong in `tests/test_state_inference.py`, with targeted integration assertions in `tests/test_app_analysis.py` and `tests/test_cli.py`.
