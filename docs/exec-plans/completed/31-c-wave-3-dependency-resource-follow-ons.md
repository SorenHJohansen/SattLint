# C-Wave-3 Dependency And Resource Follow-Ons

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

## Purpose / Big Picture

This plan replaces the remaining C-Wave-3 roadmap placeholders with one execution surface for C-023 and C-024. C-021 no longer belongs in planned feature tracking because the `safety_paths` analyzer is already live; this file exists to cover the actual open Wave C work: data dependency analysis and resource usage analysis. After this plan is implemented, users will be able to ask SattLint which variables depend on which writes and where resource allocation patterns become unsafe or leaky.

## Progress

- [x] (2026-05-13 09:12Z) Create the ExecPlan and confirm that `src/sattlint/analyzers/data_dependency.py` and `src/sattlint/analyzers/resource_usage.py` do not exist, while nearby reuse seams already exist in `src/sattlint/analyzers/dataflow.py`, `src/sattlint/analyzers/scan_loop_resource_usage.py`, `src/sattlint/analyzers/usage_tracker.py`, and `src/sattlint/core/semantic.py`.
- [x] (2026-05-13 12:45Z) Extract a private shared fact collector in `src/sattlint/analyzers/_dependency_usage_facts.py` that walks scoped statements, preserves parameter mappings, and emits read, write, and builtin-call facts for both analyzers.
- [x] (2026-05-13 12:45Z) Implement `src/sattlint/analyzers/data_dependency.py` for C-023 and register the `data_dependency` analyzer key through `src/sattlint/analyzers/_registry_specs.py`, `src/sattlint/analyzers/registry.py`, and `src/sattlint/analyzers/_registry_delivery.py`.
- [x] (2026-05-13 12:45Z) Implement `src/sattlint/analyzers/resource_usage.py` for C-024, reuse `scan_loop_resource_usage` findings there, and register the `resource_usage` analyzer key through the normal registry files.
- [x] (2026-05-13 12:47Z) Add focused tests in `tests/analyzers/test_data_dependency.py` and `tests/analyzers/test_resource_usage.py`, update the registry runner coverage in `tests/_analyzers_suites_part3.py`, and pass focused pytest plus touched-file Ruff and Pyright validation.

## Surprises & Discoveries

- Observation: C-Wave-3 is smaller than the roadmap implied because one of its listed features is already delivered.
  Evidence: `src/sattlint/analyzers/safety_paths.py` is a real analyzer surface with tests in `tests/_analyzers_suites_part5.py`, so C-021 no longer needs roadmap ownership.
- Observation: the repository already has a resource-usage-related analyzer, but it only covers one narrow safety rule.
  Evidence: `src/sattlint/analyzers/scan_loop_resource_usage.py` reports precision-scan-unsafe calls inside scan contexts, but there is still no general `resource_usage` analyzer for allocation, release, or lifetime patterns.
- Observation: data dependency analysis should reuse existing value-flow and access tracking rather than introduce a second dependency graph implementation.
  Evidence: `src/sattlint/analyzers/dataflow.py` already tracks state evolution, and the analyzer stack already contains access-oriented helpers such as `src/sattlint/analyzers/usage_tracker.py` and the `_variables_*` modules.
- Observation: the least risky shared seam was a new private fact collector rather than another edit inside `dataflow.py` or the debt-controlled semantic layer owner.
  Evidence: `src/sattlint/analyzers/_dependency_usage_facts.py` now reuses `ScopeContext`-style resolution and module traversal without changing current dataflow reports, while `src/sattlint/analyzers/sattline_semantics.py` remains untouched.

## Decision Log

- Decision: keep C-023 and C-024 in one active plan.
  Rationale: both features need a shared graph of reads, writes, and resource-affecting operations, and they share the same registry and focused validation surfaces.
  Date/Author: 2026-05-13 / Copilot (GPT-5.4)
- Decision: explicitly remove C-021 from the planned Wave C work while keeping a note here that it is already shipped.
  Rationale: the user asked to move non-GUI planning out of the roadmap. Leaving C-021 in planned scope would misrepresent already-live behavior as unfinished work.
  Date/Author: 2026-05-13 / Copilot (GPT-5.4)
- Decision: register C-023 and C-024 as first-class analyzers without widening the shared semantic-layer owner in the same slice.
  Rationale: the registry, delivery metadata, focused rule profiles, and direct analyzer tests provide the needed reachability and reporting surface while avoiding a debt-ratcheted owner file.
  Date/Author: 2026-05-13 / Copilot (GPT-5.4)

## Outcomes & Retrospective

Implemented. Wave C now has a shared private dependency-and-usage fact layer, a `data_dependency` analyzer that reports transitive paths and initialization-order hazards, and a `resource_usage` analyzer that reports release-without-acquire, reacquire-without-release, leaked handles, and inherited scan-loop resource findings. Focused proof now lives in `tests/analyzers/test_data_dependency.py`, `tests/analyzers/test_resource_usage.py`, and the registry-runner coverage in `tests/_analyzers_suites_part3.py`, with focused pytest plus touched-file Ruff and Pyright passing on the slice.

## Context and Orientation

The controlling semantic seam is still `src/sattlint/analyzers/dataflow.py`. That file and its private helper modules already know how to evaluate expressions, track path-local state, and walk module code. Any dependency analysis added here should reuse that logic or a small extracted helper layer, not fork it.

The nearest usage-oriented seams are `src/sattlint/analyzers/usage_tracker.py`, the `_variables_*` helper modules, and `src/sattlint/analyzers/scan_loop_resource_usage.py`. Those files already describe who reads or writes which symbols, or which calls are unsafe in a scan loop. They are the correct starting point for both dependency and resource analysis, even though they do not yet provide the roadmap features directly.

Workspace loading and any cross-file dependence on resolved targets must continue to use `src/sattlint/core/semantic.py`. Registration and user-facing reachability remain controlled by `src/sattlint/analyzers/_registry_specs.py`, `src/sattlint/analyzers/registry.py`, and `src/sattlint/analyzers/_registry_delivery.py`.

## Plan of Work

Begin by extracting a dependency-friendly fact model from the existing analyzer stack. The first shared helper should be able to answer which variables a statement reads, which variables it writes, and which resource-affecting calls or operations it performs. Keep that helper private until both analyzers prove stable.

Implement C-023 in `src/sattlint/analyzers/data_dependency.py` first. The initial milestone should focus on deterministic dependency chains and clear initialization-order hazards, not whole-repository data-race speculation. Report concrete dependency paths and name the statements or modules that establish them.

Implement C-024 in `src/sattlint/analyzers/resource_usage.py` second. Reuse the existing scan-loop resource checks where possible, but widen the analysis to cover lifecycle mismatches such as allocate-without-release, release-without-prior-acquire, or repeated acquisition patterns that never converge. Keep the first slice conservative and fixture-backed.

After each analyzer is implemented, register it through the normal analyzer registry files and add focused tests under `tests/analyzers/` before widening into broader analyzer-suite or CLI reachability assertions.

## Concrete Steps

Run all commands from the repository root.

Inspect the current reuse seams and registry routing before editing code:

    rg -n "StateMap|_evaluate_expression|_evaluate_condition|write|read" src/sattlint/analyzers/dataflow.py src/sattlint/analyzers/usage_tracker.py src/sattlint/analyzers/scan_loop_resource_usage.py
    rg -n "AnalyzerSpec|safety_paths|state_inference" src/sattlint/analyzers/_registry_specs.py src/sattlint/analyzers/registry.py src/sattlint/analyzers/_registry_delivery.py

After implementing the analyzers and their focused tests, run the narrow validation first:

    python scripts/run_repo_python.py -m pytest --no-cov tests/analyzers/test_data_dependency.py tests/analyzers/test_resource_usage.py tests/analyzers/test_dataflow.py -x -q --tb=short

Exercise analyzer reachability through the normal non-interactive path:

    python scripts/run_repo_python.py -m sattlint.app analyze --check data_dependency
    python scripts/run_repo_python.py -m sattlint.app analyze --check resource_usage

Run touched-file quality gates after the focused tests pass:

    python scripts/run_repo_python.py -m ruff check src/sattlint/analyzers/data_dependency.py src/sattlint/analyzers/resource_usage.py src/sattlint/analyzers/_registry_specs.py src/sattlint/analyzers/registry.py src/sattlint/analyzers/_registry_delivery.py tests/analyzers/test_data_dependency.py tests/analyzers/test_resource_usage.py
    python scripts/run_repo_python.py -m pyright src/sattlint/analyzers/data_dependency.py src/sattlint/analyzers/resource_usage.py src/sattlint/analyzers/_registry_specs.py src/sattlint/analyzers/registry.py

## Validation and Acceptance

Acceptance requires that both C-023 and C-024 become first-class analyzers with stable keys, focused regression tests that fail before implementation and pass after it, and user-visible findings that explain the underlying dependency or resource path. The analyzers must stay conservative. If the existing semantic facts are not strong enough to prove a dependency or resource hazard, the analyzer must report nothing rather than guess.

## Idempotence and Recovery

This plan is safe to execute incrementally. Extract the shared helper first, then add one analyzer at a time, rerunning the same focused validation command after each slice. If an extraction from `dataflow`, `usage_tracker`, or `scan_loop_resource_usage` changes current behavior, restore compatibility in the shared helper layer before continuing.

## Artifacts and Notes

- Focused pytest proof: `python scripts/run_repo_python.py -m pytest --no-cov tests/analyzers/test_data_dependency.py tests/analyzers/test_resource_usage.py tests/_analyzers_suites_part3.py -k 'test_registry_rule_corpus_cache_and_default_runner_closures_cover_remaining_paths or data_dependency or resource_usage' -x -q --tb=short` passed with `7 passed, 9 deselected`.
- Reachability proof: `tests/analyzers/test_data_dependency.py` and `tests/analyzers/test_resource_usage.py` assert the new analyzer keys are registered and selectable as opt-in CLI analyzers, while `tests/_analyzers_suites_part3.py` confirms the registry runner closures dispatch to `data_dependency` and `resource_usage`.
- Example findings: `data_dependency.path` reports paths such as `Output -> Mid -> Input`; `resource_usage.release_without_acquire` and `resource_usage.leaked_resource` now flag unmatched `CloseFile` or unreleased `OpenReadFile` or `OpenWriteFile` handle flows.
- Note: C-021 was already live when this plan was created and remains out of planned Wave C scope.

## Interfaces and Dependencies

The implementation surface for this plan is centered on `src/sattlint/analyzers/dataflow.py`, `src/sattlint/analyzers/usage_tracker.py`, `src/sattlint/analyzers/scan_loop_resource_usage.py`, and `src/sattlint/core/semantic.py`. New public analyzer entry points must live in `src/sattlint/analyzers/data_dependency.py` and `src/sattlint/analyzers/resource_usage.py`. Registration and delivery metadata must be updated in `src/sattlint/analyzers/_registry_specs.py`, `src/sattlint/analyzers/registry.py`, and `src/sattlint/analyzers/_registry_delivery.py`. Focused regression proof belongs in new files under `tests/analyzers/`.
