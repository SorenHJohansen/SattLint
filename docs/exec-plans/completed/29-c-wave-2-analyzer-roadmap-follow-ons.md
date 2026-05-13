# C-Wave-2 Analyzer Roadmap Follow-Ons

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

## Purpose / Big Picture

This plan replaces the roadmap placeholders for C-013, C-014, C-015, C-017, and C-018 with one executable slice. After this work lands, SattLint will offer first-class analyzers for signal lifecycle modeling, control-loop stability, fault-handling completeness, numeric constraints, and configuration drift instead of leaving those capabilities implicit in lower-level helpers or unrelated reports. The user-visible result is a set of selectable analyzers with focused tests and stable summaries or findings, not another wave of undocumented internal hooks.

## Progress

- [x] (2026-05-13 09:12Z) Create the ExecPlan and confirm that C-013, C-014, C-015, C-017, and C-018 still lack standalone analyzer modules and focused tests, while nearby reuse seams already exist in `src/sattlint/analyzers/dataflow.py`, `src/sattlint/analyzers/state_inference.py`, `src/sattlint/analyzers/alarm_integrity.py`, `src/sattlint/analyzers/parameter_drift.py`, and `src/sattlint/devtools/differential.py`.
- [x] (2026-05-13) Extract shared analyzer support in `src/sattlint/analyzers/_wave2_support.py` for module-scope traversal, statement-site collection, assignment and read extraction, and deterministic instance-parameter resolution.
- [x] (2026-05-13) Implement `src/sattlint/analyzers/signal_lifecycle.py` for C-013 and register it through the normal analyzer registry.
- [x] (2026-05-13) Implement `src/sattlint/analyzers/loop_stability.py` for C-014 and register it through the normal analyzer registry.
- [x] (2026-05-13) Implement `src/sattlint/analyzers/fault_handling.py` for C-015 and register it through the normal analyzer registry.
- [x] (2026-05-13) Implement `src/sattlint/analyzers/numeric_constraints.py` for C-017 and register it through the normal analyzer registry.
- [x] (2026-05-13) Implement `src/sattlint/analyzers/config_drift.py` for C-018 and register it through the normal analyzer registry.
- [x] (2026-05-13) Add focused tests under `tests/analyzers/`, update the registry closure proof in `tests/_analyzers_suites_part3.py`, and pass the narrow pytest, Ruff, and Pyright validation slice for the new analyzers.

## Surprises & Discoveries

- Observation: the repository already tracks many of the facts needed for signal lifecycle and numeric constraint reasoning, but those facts are still buried in general-purpose analyzers.
  Evidence: `src/sattlint/analyzers/dataflow.py` and `src/sattlint/analyzers/state_inference.py` already derive value ranges, stable boolean state, and path-local conditions, yet there is no dedicated `signal_lifecycle` or `numeric_constraints` analyzer.
- Observation: fault and drift related checks already exist, but only as narrow policy checks rather than as the feature surfaces described by the roadmap.
  Evidence: `src/sattlint/analyzers/alarm_integrity.py` and `src/sattlint/analyzers/parameter_drift.py` already encode slices of fault and drift reasoning, and `src/sattlint/devtools/differential.py` already records `config_drift` counts, but none of those seams exposes the named roadmap analyzers.
- Observation: the control-loop and signal-lifecycle features should be modeled as conservative follow-ons to current variable-access and state tracking, not as separate symbolic engines.
  Evidence: the current analyzer stack already contains variable-access traversal helpers under `src/sattlint/analyzers/_variables_*`, plus reusable state reasoning in `dataflow`, `state_inference`, and `usage_tracker`, so a second parallel model would drift immediately.
- Observation: the cleanest shared seam for this wave was not `dataflow.py` itself but a narrower traversal helper dedicated to scope walks, statement sites, and deterministic parameter-value resolution.
  Evidence: `src/sattlint/analyzers/_wave2_support.py` now carries the reusable mechanics needed by `signal_lifecycle`, `loop_stability`, `fault_handling`, `numeric_constraints`, and `config_drift` without widening existing analyzer behavior.
- Observation: these analyzers are useful as selectable checks but too noisy and specialized to join the default CLI subset immediately.
  Evidence: the implementation marks each new analyzer `cli_exposed` in `src/sattlint/analyzers/_registry_delivery.py` so `analyze --check <key>` can select it, while `src/sattlint/analyzers/registry.py` leaves `DEFAULT_CLI_ANALYZER_KEYS` unchanged.

## Decision Log

- Decision: keep the five C-Wave-2 analyzer gaps in one active plan instead of splitting them by feature.
  Rationale: all five features depend on the same analyzer registration surfaces, the same compact fixture style under `tests/analyzers/`, and the same underlying state and access facts.
  Date/Author: 2026-05-13 / Copilot (GPT-5.4)
- Decision: treat `parameter_drift.py`, `alarm_integrity.py`, and `differential.py` as evidence of reusable logic, not as proof that C-015 or C-018 is already delivered.
  Rationale: users still cannot select `fault_handling` or `config_drift` as first-class analyzers, and the current files do not expose the roadmap behavior as stable, named reports.
  Date/Author: 2026-05-13 / Copilot (GPT-5.4)
- Decision: stage read-only, deterministic analyzers first and postpone any integration that depends on external configuration formats or uncertain domain catalogs until after feature-local tests exist.
  Rationale: C-018 in particular can become noisy or environment-dependent unless the initial implementation starts with fixture-backed inputs and a narrow, repeatable drift contract.
  Date/Author: 2026-05-13 / Copilot (GPT-5.4)
- Decision: expose the five new analyzers through `--check` without adding them to `DEFAULT_CLI_ANALYZER_KEYS`.
  Rationale: the roadmap requires first-class, selectable analyzers, but the initial conservative implementations are better treated as opt-in checks until broader noise evidence exists.
  Date/Author: 2026-05-13 / Copilot (GPT-5.4)

## Outcomes & Retrospective

Implemented. The repository now exposes first-class `signal_lifecycle`, `loop_stability`, `fault_handling`, `numeric_constraints`, and `config_drift` analyzers through the normal registry and CLI-selection path. The new analyzers share a narrow helper seam instead of cloning traversal logic, emit focused summaries or findings, and ship with dedicated tests plus registry closure coverage.

Validation completed with a focused pytest slice for the five new analyzer test modules, a focused pytest slice for the shared registry closure and metadata tests, and touched-file Ruff and Pyright checks. The analyzers remain opt-in by default, but they are now selectable through the same CLI exposure gate as the rest of the analyzer catalog.

## Context and Orientation

The core semantic reasoning still lives in `src/sattlint/analyzers/dataflow.py`, its `_dataflow_*` helper modules, and `src/sattlint/analyzers/state_inference.py`. Those files already provide the closest available building blocks for value ranges, stable conditions, and variable state, so they should remain the source of truth for C-013, C-014, and C-017.

The nearest specialized seams for the rest of the wave already exist. `src/sattlint/analyzers/alarm_integrity.py` is the closest fault-oriented analyzer surface. `src/sattlint/analyzers/parameter_drift.py` is the closest analyzer surface for contract and drift mismatches. `src/sattlint/devtools/differential.py` already emits `config_drift` summaries, which makes it the nearest repository-owned drift vocabulary for C-018 even though it is not yet a standalone analyzer.

Analyzer registration is still controlled in `src/sattlint/analyzers/_registry_specs.py`, `src/sattlint/analyzers/registry.py`, and `src/sattlint/analyzers/_registry_delivery.py`. Any feature implemented under this plan must be routed through those files or it will remain invisible to users and tooling. Focused regression tests should follow the current pattern under `tests/analyzers/`, with only small reachability additions in the broader analyzer-suite or CLI tests after the feature-local tests pass.

## Plan of Work

Start with the two features that mostly extend existing state reasoning: C-013 signal lifecycle and C-017 numeric constraints. Reuse the current value-flow and variable-usage surfaces instead of inventing a new path model. The first lifecycle milestone should be able to distinguish at least three concrete cases: written then read, read before any known write, and written but never consumed. The first numeric-constraint milestone should report only constraints that can be derived from explicit assignments, constant-propagated comparisons, or declared limit parameters already visible to the analyzer.

Implement C-014 control-loop stability next. The first slice should stay conservative and focus on repeatable oscillation or contradictory setpoint behavior that can be derived from existing state transitions, not on generic control-theory claims. Reuse `dataflow`, `state_inference`, and variable-access history so the analyzer explains the exact statements that produced the unstable pattern.

Implement C-015 fault handling by extending the nearest fault-oriented seam in `alarm_integrity.py` or by extracting a shared helper into a small private module. The first version should detect missing recovery coverage, handlers that never clear or acknowledge a fault path, or alarm paths that are declared but not handled by any reachable logic. Do not widen into production-specific alarm catalogs in the first slice.

Implement C-018 configuration drift last because it touches external inputs most directly. Start with fixture-scale inputs and a drift definition that the repository can test deterministically. Reuse `parameter_drift.py` and `devtools/differential.py` where possible, but keep the analyzer output independent of pipeline-only artifacts so a user can run it directly.

## Concrete Steps

Run all commands from the repository root.

Inspect the current reuse seams and registry routing before editing code:

    rg -n "state_inference|range|condition_always|unreachable_branch" src/sattlint/analyzers/dataflow.py src/sattlint/analyzers/state_inference.py
    rg -n "alarm|fault|drift|config_drift" src/sattlint/analyzers/alarm_integrity.py src/sattlint/analyzers/parameter_drift.py src/sattlint/devtools/differential.py
    rg -n "AnalyzerSpec|state_inference|safety_paths" src/sattlint/analyzers/_registry_specs.py src/sattlint/analyzers/registry.py src/sattlint/analyzers/_registry_delivery.py

After implementing the analyzers and their focused tests, run the narrow validation first:

    python scripts/run_repo_python.py -m pytest --no-cov tests/analyzers/test_signal_lifecycle.py tests/analyzers/test_loop_stability.py tests/analyzers/test_fault_handling.py tests/analyzers/test_numeric_constraints.py tests/analyzers/test_config_drift.py -x -q --tb=short

Exercise analyzer reachability through the normal non-interactive path:

    python scripts/run_repo_python.py -m sattlint.app analyze --check signal_lifecycle
    python scripts/run_repo_python.py -m sattlint.app analyze --check loop_stability
    python scripts/run_repo_python.py -m sattlint.app analyze --check fault_handling
    python scripts/run_repo_python.py -m sattlint.app analyze --check numeric_constraints
    python scripts/run_repo_python.py -m sattlint.app analyze --check config_drift

Run touched-file quality gates after the focused tests pass:

    python scripts/run_repo_python.py -m ruff check src/sattlint/analyzers/signal_lifecycle.py src/sattlint/analyzers/loop_stability.py src/sattlint/analyzers/fault_handling.py src/sattlint/analyzers/numeric_constraints.py src/sattlint/analyzers/config_drift.py src/sattlint/analyzers/_registry_specs.py src/sattlint/analyzers/registry.py src/sattlint/analyzers/_registry_delivery.py tests/analyzers/test_signal_lifecycle.py tests/analyzers/test_loop_stability.py tests/analyzers/test_fault_handling.py tests/analyzers/test_numeric_constraints.py tests/analyzers/test_config_drift.py
    python scripts/run_repo_python.py -m pyright src/sattlint/analyzers/signal_lifecycle.py src/sattlint/analyzers/loop_stability.py src/sattlint/analyzers/fault_handling.py src/sattlint/analyzers/numeric_constraints.py src/sattlint/analyzers/config_drift.py src/sattlint/analyzers/_registry_specs.py src/sattlint/analyzers/registry.py

## Validation and Acceptance

Acceptance requires that each roadmap feature in this wave becomes a first-class analyzer with a stable key, feature-local tests that fail before implementation and pass after it, and at least one user-visible report or summary that can be requested through the normal analyzer path. Configuration drift must remain deterministic on fixtures and must not depend on transient local pipeline artifacts. Lifecycle, stability, and fault findings must explain the observed path or state facts rather than returning vague warnings.

## Idempotence and Recovery

This plan is safe to execute incrementally. Land one analyzer at a time, rerun the same focused pytest command after each slice, and keep registry changes scoped to the analyzer being introduced. If a helper extraction from `dataflow`, `parameter_drift`, or `alarm_integrity` causes regressions, restore the existing behavior first and only then continue with the new analyzer.

## Artifacts and Notes

Passing focused pytest summaries:

- `python scripts/run_repo_python.py -m pytest --no-cov tests/analyzers/test_signal_lifecycle.py tests/analyzers/test_loop_stability.py tests/analyzers/test_fault_handling.py tests/analyzers/test_numeric_constraints.py tests/analyzers/test_config_drift.py -x -q --tb=short` -> `10 passed`
- `python scripts/run_repo_python.py -m pytest --no-cov tests/_analyzers_suites_part3.py -k "registry_catalog_report_and_key_helpers_cover_metadata_branches or registry_rule_corpus_cache_and_default_runner_closures_cover_remaining_paths" -x -q --tb=short` -> `2 passed`

Reachability proof:

- The new analyzer keys are registered in `src/sattlint/analyzers/_registry_specs.py` and marked `cli_exposed` in `src/sattlint/analyzers/_registry_delivery.py`, which is the shared selection gate used by `sattlint.app analyze --check <key>`.

Example findings and summaries:

- `signal_lifecycle` reports `signal_lifecycle.read_before_write` and `signal_lifecycle.unconsumed_write` with written-then-read summary counts.
- `loop_stability` reports `loop_stability.conflicting_setpoint` with the exact literal writes that disagree.
- `fault_handling` reports `fault_handling.missing_recovery` and `fault_handling.unhandled_fault` for raised but uncleared or unread fault paths.
- `numeric_constraints` reports `numeric_constraints.limit_violation` when literal writes exceed visible `Min_` or `Max_` bounds.
- `config_drift` reports `config_drift.instance_configuration` and emits a deterministic `config_drift` summary list keyed by drifting moduletype parameters.

These analyzers stay opt-in for now and do not join `DEFAULT_CLI_ANALYZER_KEYS`. The current conservative heuristics are intentionally narrow, but still specialized enough that default-on noise should be measured before widening the standard CLI subset.

## Interfaces and Dependencies

The implementation surface for this plan is centered on `src/sattlint/analyzers/dataflow.py`, `src/sattlint/analyzers/state_inference.py`, `src/sattlint/analyzers/alarm_integrity.py`, `src/sattlint/analyzers/parameter_drift.py`, and `src/sattlint/devtools/differential.py`. New public analyzer entry points must live in `src/sattlint/analyzers/signal_lifecycle.py`, `src/sattlint/analyzers/loop_stability.py`, `src/sattlint/analyzers/fault_handling.py`, `src/sattlint/analyzers/numeric_constraints.py`, and `src/sattlint/analyzers/config_drift.py`. Registration and delivery metadata must be updated in `src/sattlint/analyzers/_registry_specs.py`, `src/sattlint/analyzers/registry.py`, and `src/sattlint/analyzers/_registry_delivery.py`. Focused regression proof belongs in new files under `tests/analyzers/`, with broader integration assertions added only after the feature-local suites pass.
