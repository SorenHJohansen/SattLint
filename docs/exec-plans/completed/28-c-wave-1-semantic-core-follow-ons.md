# C-Wave-1 Semantic Core Follow-Ons

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

## Purpose / Big Picture

This plan replaces the roadmap placeholders for C-010, C-011, C-012, and C-016 with one execution surface that a stateless executor can follow. After this work lands, SattLint will expose first-class analyzers for timing and determinism, power-up and restart correctness, scan-level concurrency, and interface contracts instead of leaving those capabilities as vague roadmap promises. The observable outcome is not a new document; it is four analyzers that can be selected through the normal analyzer routing, each with focused regression tests and explicit summaries or findings.

## Progress

- [x] (2026-05-13 09:12Z) Create the ExecPlan and confirm that C-010, C-011, C-012, and C-016 still have no standalone analyzer modules or focused tests, while partial foundations already exist in `src/sattlint/tracing.py`, `src/sattlint/analyzers/initial_values.py`, `src/sattlint/analyzers/scan_loop_resource_usage.py`, and `src/sattlint/analyzers/_variables_contracts.py`.
- [x] (2026-05-13 11:48Z) Expose the minimum shared helper seams by promoting existing `variables`, `initial_values`, `unsafe_defaults`, `sfc`, `scan_loop_resource_usage`, and `dataflow` findings into dedicated analyzer entry points instead of duplicating their walkers.
- [x] (2026-05-13 11:48Z) Implement `src/sattlint/analyzers/timing.py` for C-010 and register it through the normal analyzer registry.
- [x] (2026-05-13 11:48Z) Implement `src/sattlint/analyzers/powerup.py` for C-011 and register it through the normal analyzer registry.
- [x] (2026-05-13 11:48Z) Implement `src/sattlint/analyzers/scan_concurrency.py` for C-012 and register it through the normal analyzer registry.
- [x] (2026-05-13 11:48Z) Implement `src/sattlint/analyzers/interface_contracts.py` for C-016 and register it through the normal analyzer registry.
- [x] (2026-05-13 11:48Z) Add focused tests for the new analyzers and run narrow pytest, Ruff, Pyright, and direct `sattlint.app analyze --check ...` reachability validation.

## Surprises & Discoveries

- Observation: the repository already collects timing-shaped evidence, but only as trace metadata rather than as analyzer findings.
  Evidence: `src/sattlint/tracing.py` already builds timing summaries, and `src/sattlint/devtools/derived_reports.py` consumes those summaries, but there is no `src/sattlint/analyzers/timing.py` owner surface.
- Observation: power-up correctness is partially represented today as initial-value validation rather than as a dedicated restart or initialization analyzer.
  Evidence: `src/sattlint/analyzers/initial_values.py` already walks module instances and reports missing recipe or engineering defaults, but there is no `powerup` analyzer key or focused power-up test suite.
- Observation: interface-contract behavior already exists in helper form inside the variables analyzer.
  Evidence: `src/sattlint/analyzers/_variables_contracts.py` already computes required parameter names, AnyType field contracts, and missing required parameter connections, but there is no standalone `interface_contracts` module or registry entry.
- Observation: scan-loop safety checks already exist, but they do not solve the broader concurrency problem described by C-012.
  Evidence: `src/sattlint/analyzers/scan_loop_resource_usage.py` only reports precision-scan-unsafe calls in scan contexts; it does not model competing writes, arbitration order, or concurrent access conflicts.
- Observation: the non-interactive `sattlint.app analyze --check <key>` path was still filtering selected checks through the default CLI subset instead of the full enabled analyzer catalog.
  Evidence: direct `python scripts/run_repo_python.py -m sattlint.app analyze --check timing` style validation initially returned `No matching checks found` until `src/sattlint/app.py` was updated to use selectable analyzers when explicit keys are requested.

## Decision Log

- Decision: keep C-010, C-011, C-012, and C-016 in one active plan instead of creating four tiny files.
  Rationale: all four features depend on the same semantic-core seams in `dataflow`, analyzer registration, and focused analyzer tests, so a grouped plan reduces drift and makes shared helper extraction explicit.
  Date/Author: 2026-05-13 / Copilot (GPT-5.4)
- Decision: treat the existing timing, initial-value, scan-loop, and variable-contract helpers as reuse seams rather than as proof that the roadmap items are already implemented.
  Rationale: users still cannot select `timing`, `powerup`, `scan_concurrency`, or `interface_contracts` as first-class analyzers, and there are no dedicated reports or focused suites proving those behaviors.
  Date/Author: 2026-05-13 / Copilot (GPT-5.4)
- Decision: register the new analyzers through `src/sattlint/analyzers/_registry_specs.py`, `src/sattlint/analyzers/registry.py`, and `src/sattlint/analyzers/_registry_delivery.py`, with default-CLI inclusion decided explicitly per analyzer after noise is measured.
  Rationale: this matches the current delivery pattern used by newer analyzers such as `state_inference` and avoids silently widening default CLI output before focused evidence exists.
  Date/Author: 2026-05-13 / Copilot (GPT-5.4)
- Decision: keep `timing`, `powerup`, `scan_concurrency`, and `interface_contracts` opt-in for the default CLI subset while still making them reachable through explicit `--check` selection.
  Rationale: the repo already distinguishes between enabled analyzers and the default CLI subset; matching the `state_inference` pattern keeps default output stable while still satisfying the first-class-analyzer requirement.
  Date/Author: 2026-05-13 / Copilot (GPT-5.4)
- Decision: promote `timing` and `powerup` into the default CLI subset, while keeping `scan_concurrency` and `interface_contracts` opt-in.
  Rationale: `timing` and `powerup` add distinct high-signal coverage that was not already present in the default subset, while `scan_concurrency` would duplicate the existing `sfc` parallel-write-race output and `interface_contracts` would duplicate the default `variables` contract and mapping sections.
  Date/Author: 2026-05-13 / Copilot (GPT-5.4)
- Decision: assign dedicated rule-metadata ownership to the wrapper analyzers in the registry catalog instead of cloning the underlying semantic findings.
  Rationale: `timing`, `powerup`, `scan_concurrency`, and `interface_contracts` intentionally reuse underlying analyzers; catalog-level alias mapping preserves one canonical rule definition while still attributing the reused rule IDs and summary outputs to the wrapper analyzer that surfaces them.
  Date/Author: 2026-05-13 / Copilot (GPT-5.4)

## Outcomes & Retrospective

Implemented. The repository now exposes first-class `timing`, `powerup`, `scan_concurrency`, and `interface_contracts` analyzers through the shared registry, with dedicated focused tests under `tests/analyzers/` and non-interactive CLI reachability via `sattlint.app analyze --check <key>`. The implementation deliberately reuses existing semantic seams from `dataflow`, `scan_loop_resource_usage`, `sfc`, `initial_values`, `unsafe_defaults`, and `variables` so the new analyzers inherit proven behavior instead of forking duplicate walkers.

The resulting Wave C slice is conservative by design. `timing` aggregates scan-cycle temporal hazards and scan-loop resource hazards; `powerup` aggregates missing startup values and unsafe startup defaults; `scan_concurrency` promotes existing parallel-write race findings into a dedicated analyzer; and `interface_contracts` promotes required-parameter, unknown-target, and cross-module contract-mismatch findings into a standalone owner surface. After noise review, `timing` and `powerup` joined the default CLI subset because they add non-duplicative signal, while `scan_concurrency` and `interface_contracts` remained opt-in to avoid duplicating `sfc` and `variables` output. Registry rule metadata now also attributes reused semantic rule IDs to the wrapper analyzers that surface them, without duplicating the underlying rule definitions.

## Context and Orientation

The nearest controlling semantic seam is `src/sattlint/analyzers/dataflow.py`, supported by helper modules under `src/sattlint/analyzers/_dataflow_*`. That code already evaluates expressions, merges branch state, and walks module code, so it must stay the source of truth for condition and value semantics. New analyzers in this plan should reuse that reasoning rather than duplicating the walker.

Several adjacent files already contain partial facts that should be promoted into first-class analyzers. `src/sattlint/tracing.py` and `src/sattlint/devtools/derived_reports.py` already record timing summaries. `src/sattlint/analyzers/initial_values.py` already validates missing default values for instance parameters, which is the nearest available seam for power-up analysis. `src/sattlint/analyzers/scan_loop_resource_usage.py` already walks active scan contexts and reports one class of scan-safety issue. `src/sattlint/analyzers/_variables_contracts.py` already derives required parameter names and AnyType field contracts inside the variables analyzer. None of those files currently yields a selectable analyzer for the corresponding roadmap feature.

Registration and user reachability are controlled in three places. `src/sattlint/analyzers/_registry_specs.py` declares analyzer keys and runners. `src/sattlint/analyzers/registry.py` exposes the enabled and CLI-visible analyzers. `src/sattlint/analyzers/_registry_delivery.py` records delivery metadata and expected owner tests. Any analyzer added by this plan must be wired through all three surfaces or it will remain hidden.

The nearest existing test pattern is under `tests/analyzers/`. `tests/analyzers/test_state_inference.py` and `tests/analyzers/test_dataflow.py` show the preferred compact fixture style for analyzer-specific behavior. The broader analyzer-availability and CLI-routing assertions are split across files such as `tests/_analyzers_suites_part3.py`, `tests/_analyzers_suites_part5.py`, `tests/_app_analysis_part2.py`, `tests/_app_analysis_part4.py`, and `tests/test_cli.py`.

## Plan of Work

Start by extracting shared facts instead of writing four analyzers from scratch. For C-010, identify the minimum reusable timing facts in `src/sattlint/tracing.py`, `src/sattlint/analyzers/dataflow.py`, and `src/sattlint/analyzers/scan_loop_resource_usage.py`, then build `src/sattlint/analyzers/timing.py` around deterministic issue kinds such as impossible timing guards, scan-jitter hazards, or non-deterministic execution order. Keep the first milestone conservative: report only behavior that can be justified from existing semantic facts.

Implement C-011 next in `src/sattlint/analyzers/powerup.py`. Reuse the parameter-default and instance-walk logic in `src/sattlint/analyzers/initial_values.py` instead of forking it. Extend that seam so the new analyzer can tell the difference between a missing startup value, a value that is only conditionally established after startup, and a restart-sensitive state that is never re-established. If a helper extraction is needed, move the shared walk into a private helper module and keep `initial_values.py` behavior-preserving.

Implement C-012 in `src/sattlint/analyzers/scan_concurrency.py` by reusing the existing module-code walkers and variable-access tracking. The first milestone should focus on one observable class of concurrency issue: conflicting writes or unsafe arbitration inside scan or sequence contexts that are already discoverable from the existing AST and access graphs. Do not attempt whole-repository concurrency modeling in the first slice.

Implement C-016 in `src/sattlint/analyzers/interface_contracts.py` by lifting contract-related logic out of `_variables_contracts.py` into a shared helper layer. The new analyzer should report explicit interface-contract failures rather than relying on the variables analyzer to surface them as side effects. Required parameter coverage, AnyType field contracts, and parameter mapping validity should remain aligned with the current variables semantics.

After each analyzer is implemented, register it in `_registry_specs.py`, `registry.py`, and `_registry_delivery.py`, then add focused tests under `tests/analyzers/` before widening into CLI or app-analysis routing. Keep default CLI inclusion explicit. If one analyzer is not ready for the default subset, preserve opt-in selection until false-positive behavior is characterized.

## Concrete Steps

Run all commands from the repository root.

Inspect the current reuse seams and registry routing before editing code:

    rg -n "timing_summary|InitialValueAnalyzer|ScanLoopResourceUsageAnalyzer|required parameter" src/sattlint/tracing.py src/sattlint/analyzers/initial_values.py src/sattlint/analyzers/scan_loop_resource_usage.py src/sattlint/analyzers/_variables_contracts.py
    rg -n "AnalyzerSpec|state_inference|safety_paths" src/sattlint/analyzers/_registry_specs.py src/sattlint/analyzers/registry.py src/sattlint/analyzers/_registry_delivery.py

After implementing the analyzers and their focused tests, run the narrow validation first:

    python scripts/run_repo_python.py -m pytest --no-cov tests/analyzers/test_timing.py tests/analyzers/test_powerup.py tests/analyzers/test_scan_concurrency.py tests/analyzers/test_interface_contracts.py tests/analyzers/test_dataflow.py -x -q --tb=short

Exercise analyzer reachability through the normal non-interactive path:

    python scripts/run_repo_python.py -m sattlint.app analyze --check timing
    python scripts/run_repo_python.py -m sattlint.app analyze --check powerup
    python scripts/run_repo_python.py -m sattlint.app analyze --check scan_concurrency
    python scripts/run_repo_python.py -m sattlint.app analyze --check interface_contracts

Run touched-file quality gates after the focused tests pass:

    python scripts/run_repo_python.py -m ruff check src/sattlint/analyzers/timing.py src/sattlint/analyzers/powerup.py src/sattlint/analyzers/scan_concurrency.py src/sattlint/analyzers/interface_contracts.py src/sattlint/analyzers/_registry_specs.py src/sattlint/analyzers/registry.py src/sattlint/analyzers/_registry_delivery.py tests/analyzers/test_timing.py tests/analyzers/test_powerup.py tests/analyzers/test_scan_concurrency.py tests/analyzers/test_interface_contracts.py
    python scripts/run_repo_python.py -m pyright src/sattlint/analyzers/timing.py src/sattlint/analyzers/powerup.py src/sattlint/analyzers/scan_concurrency.py src/sattlint/analyzers/interface_contracts.py src/sattlint/analyzers/_registry_specs.py src/sattlint/analyzers/registry.py

## Validation and Acceptance

Acceptance requires more than new modules. Each feature in this plan must become a first-class analyzer with a stable key, focused regression tests that fail before implementation and pass after it, and at least one observable report or summary that a user can request through the normal analyzer path.

The new analyzers must remain conservative. If the current semantic evidence is insufficient to prove a timing, startup, concurrency, or contract violation, the analyzer must return unknown rather than inventing a finding. Shared helpers extracted from `dataflow`, `initial_values`, or `_variables_contracts` must preserve current behavior for the existing analyzers that depend on them.

## Idempotence and Recovery

This plan is safe to execute incrementally. Implement one analyzer at a time, keep the registry wiring local to the analyzer being added, and rerun the same focused validation command after each slice. If a helper extraction breaks an existing analyzer, stop and restore behavior in the helper layer before continuing with the new feature work. If default CLI inclusion proves too noisy for one of the analyzers, keep that analyzer opt-in and record the noise evidence in this plan.

## Artifacts and Notes

Record one short artifact per analyzer as work proceeds: a focused pytest summary, one CLI or app-analysis invocation that proves the analyzer key is reachable, and one example finding or summary payload. Also record whether each analyzer joined the default CLI subset or remained opt-in after focused validation.

## Interfaces and Dependencies

The implementation surface for this plan is centered on `src/sattlint/analyzers/dataflow.py`, `src/sattlint/analyzers/initial_values.py`, `src/sattlint/analyzers/scan_loop_resource_usage.py`, and `src/sattlint/analyzers/_variables_contracts.py`. New public analyzer entry points must live in `src/sattlint/analyzers/timing.py`, `src/sattlint/analyzers/powerup.py`, `src/sattlint/analyzers/scan_concurrency.py`, and `src/sattlint/analyzers/interface_contracts.py`. Registration and delivery metadata must be updated in `src/sattlint/analyzers/_registry_specs.py`, `src/sattlint/analyzers/registry.py`, and `src/sattlint/analyzers/_registry_delivery.py`. Focused regression proof belongs in new test files under `tests/analyzers/`, with any reachability assertions added to the existing analyzer-suite, app-analysis, or CLI test files only after the feature-local tests pass.
