# D-038 SFC Scan Cycle Simulation

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

## Purpose / Big Picture

This plan turns the roadmap placeholder for scan-cycle simulation into an executable slice that adds a real user-facing simulation command. After this change, a user will be able to point SattLint at a concrete SFC-bearing target, run a bounded scan loop, and see whether the module reaches steady state, enters a cycle, or keeps mutating state across scans. The observable result is not just new code; it is a reproducible command that prints or writes a scan trace and a focused test suite that proves the runtime semantics stay aligned with the existing SFC and dataflow analyzers.

## Progress

- [x] (2026-05-04) Create the ExecPlan and pin the owning seams, command surface, and first validation route.
- [x] (2026-05-05) Add a dedicated `simulate` CLI subcommand and thread its handler through the existing CLI facade.
- [x] (2026-05-05) Implement a bounded simulation package for variable state, step activation, transition firing, scan snapshots, steady-state detection, and cycle detection.
- [x] (2026-05-05) Add focused regression tests for simulation semantics, CLI plumbing, and JSON output shape.
- [x] (2026-05-05) Validate the new behavior with the narrow simulation and CLI suites, then run touched-file lint and type checks.
- [x] (2026-05-05) Prove the user-facing command against a real workspace-loaded SFC fixture and archive this plan under `docs/exec-plans/completed/`.

## Surprises & Discoveries

- Observation: the roadmap sketch says to add `--simulate`, but the current CLI is organized around subcommands rather than feature flags.
  Evidence: `src/sattlint/cli/entry.py`, `src/sattlint/app_base.py`, and `src/sattlint/app.py` all route behavior through subparsers and explicit handler injection.
- Observation: the repository already contains strong SFC and dataflow semantics that can anchor simulation behavior, even though there is no `src/sattlint/simulation/` package yet.
  Evidence: `src/sattlint/analyzers/sfc.py`, `src/sattlint/analyzers/dataflow.py`, `tests/test_analyzers_state.py`, and `tests/test_analyzers_suites.py` already cover step activation, transition guards, nested SFC shapes, and condition reasoning.
- Observation: workspace-loaded sample files do not necessarily expose the filename stem as the simulation selector.
  Evidence: loading `tests/fixtures/corpus/semantic/ParallelWriteRace.s` through `src/sattlint/core/semantic.py:load_workspace_snapshot()` resolved the top-level target name as `BasePicture`, so the real CLI proof needed `--module BasePicture` rather than `--module ParallelWriteRace`.
- Observation: simulation state export needed to translate case-folded dataflow keys back to declared symbol names.
  Evidence: the first focused post-wiring test run failed with `KeyError: 'Counter'` in `tests/test_sfc_simulation.py`, and the fix was localized to `src/sattlint/simulation/runtime.py:_export_state()`.

## Decision Log

- Decision: expose simulation as a new `sattlint simulate` subcommand rather than as an extra flag on `analyze`.
  Rationale: the existing CLI surface is subcommand-oriented, and simulation has different inputs and outputs than analyzer execution.
  Date/Author: 2026-05-04 / Copilot (GPT-5.4)
- Decision: reuse existing evaluator and SFC semantics instead of building a second interpretation model from scratch.
  Rationale: simulation must agree with the analyzer stack on condition truthiness, assignment semantics, and nested SFC traversal or it will become an inconsistent parallel framework.
  Date/Author: 2026-05-04 / Copilot (GPT-5.4)

## Outcomes & Retrospective

Implementation complete. SattLint now exposes a first-class `simulate` command through `src/sattlint/cli/entry.py`, `src/sattlint/app_base.py`, `src/sattlint/app.py`, and `src/sattlint/app_cli_commands.py`, backed by the new runtime in `src/sattlint/simulation/runtime.py`.

The runtime stayed anchored to existing analyzer semantics rather than introducing a second evaluator. `src/sattlint/simulation/runtime.py` reuses the current dataflow state seeding, block execution, and condition evaluation helpers so scan execution stays aligned with the analyzer stack.

Focused regression proof is in place through `tests/test_sfc_simulation.py`, `tests/test_cli.py`, and `tests/test_app_cli_commands.py`. The narrow validation route passed at `39 passed`, touched-file Ruff passed, touched-file Pyright passed, and the end-to-end CLI proof succeeded against `tests/fixtures/corpus/semantic/ParallelWriteRace.s` with `--module BasePicture --format json`.

## Context and Orientation

SattLint currently has a thin CLI facade and a deeper application layer. `src/sattlint/cli/entry.py` defines subcommands and turns parsed arguments into injected handler calls. `src/sattlint/app_base.py` and `src/sattlint/app.py` wire those handlers to the real application functions. `src/sattlint/app_cli_commands.py` holds the concrete command implementations that operate on loaded configuration and workspace state.

The semantic building blocks for this feature already exist. `src/sattlint/analyzers/sfc.py` understands SFC structure and reports step and transition issues. `src/sattlint/analyzers/dataflow.py` already knows how to evaluate expressions and conditions, merge branch state, and walk module code. `src/sattlint/core/semantic.py` provides `load_workspace_snapshot()`, which is the repository-standard way to load real workspace inputs. The tests `tests/test_analyzers_state.py` and `tests/test_analyzers_suites.py` already construct compact SFC fixtures that should be reused for simulation tests instead of inventing a second fixture style.

There is no simulation package today. This plan therefore creates `src/sattlint/simulation/` as a new owner surface, but only for execution-specific concerns that are not already represented in the analyzer stack. Expression and condition semantics must stay shared or be extracted into a shared helper layer rather than duplicated.

## Plan of Work

Start with CLI plumbing. Update `src/sattlint/cli/entry.py` to add a `simulate` subparser with arguments for the target path, the fully qualified module or instance to simulate, the run mode, the scan budget, cycle detection, output format, and optional output path. Thread the new handler slot through `src/sattlint/app_base.py` and `src/sattlint/app.py`, then implement the handler in `src/sattlint/app_cli_commands.py`. Keep the command non-interactive and deterministic.

Create a new `src/sattlint/simulation/` package with a small number of files that match repository seams rather than the roadmap placeholder list verbatim. At minimum, define typed state containers for variable values and active SFC steps, an executor that performs one scan at a time, a steady-state and cycle detector, and an output formatter that can emit a stable JSON structure and a compact table summary. The executor should operate over one loaded workspace snapshot and one selected target at a time. Do not add background services, caches, or global mutable state.

Extract or expose the minimum shared evaluation seam needed from `src/sattlint/analyzers/dataflow.py`. The simulator must use the same condition truthiness and expression evaluation rules as the analyzer path wherever possible. If a helper must move, move it into a private shared module under `src/sattlint/analyzers/` or `src/sattlint/simulation/` and keep behavior-preserving tests around the old analyzer entry points.

Add focused tests before widening scope. Create `tests/test_sfc_simulation.py` for the new runtime, using the compact AST-construction style already present in `tests/test_analyzers_state.py`. Add CLI parser and dispatch tests to `tests/test_cli.py` and `tests/test_app_cli_commands.py`. The first milestone should prove three observable behaviors: steady state is detected and reported, a repeated hash of active steps plus values is reported as a cycle, and the JSON payload contains stable keys and counts.

Once the command works on hand-built fixtures, add one real workspace scenario that loads a sample file through the normal semantic loader rather than bypassing repository plumbing. Keep that scenario small so the first validation remains focused.

## Concrete Steps

Run all commands from the repository root.

Inspect the current CLI and command seams before editing:

    rg -n "def build_cli_parser|def run_cli|def run_analyze_command" src/sattlint/cli/entry.py src/sattlint/app_base.py src/sattlint/app.py src/sattlint/app_cli_commands.py

Implement the simulation package and CLI wiring, then run the narrow tests first:

    python scripts/run_repo_python.py -m pytest --no-cov tests/test_sfc_simulation.py tests/test_cli.py tests/test_app_cli_commands.py -x -q --tb=short

Exercise the new command on a real target once the tests pass:

  python scripts/run_repo_python.py -m sattlint simulate tests/fixtures/corpus/semantic/ParallelWriteRace.s --module BasePicture --mode steady-state --max-scans 4 --format json

Run touched-file quality gates after the feature-specific checks pass:

    python scripts/run_repo_python.py -m ruff check src/sattlint/cli/entry.py src/sattlint/app_base.py src/sattlint/app.py src/sattlint/app_cli_commands.py src/sattlint/simulation tests/test_sfc_simulation.py tests/test_cli.py tests/test_app_cli_commands.py
    python scripts/run_repo_python.py -m pyright src/sattlint/cli/entry.py src/sattlint/app_base.py src/sattlint/app.py src/sattlint/app_cli_commands.py src/sattlint/simulation

Expected success signal for the user-facing command: the process exits with code `0`, prints whether steady state or a cycle was reached, and when `--format json` is used, emits a JSON object containing the selected target, total scan count, steady-state or cycle summary, and a bounded list of scan snapshots.

## Validation and Acceptance

Acceptance requires both behavior proof and regression proof. Behavior proof means a user can run `sattlint simulate ...` against a small SFC target and observe one of three explicit results: steady state reached, cycle detected, or scan budget exhausted without either. Regression proof means the new tests in `tests/test_sfc_simulation.py`, `tests/test_cli.py`, and `tests/test_app_cli_commands.py` fail before the implementation and pass after it.

The simulator must not guess silently. If the requested target cannot be resolved, if the target has no SFC structure, or if the scan budget is invalid, the command must fail with a specific error message and a non-zero exit code. Cycle detection must be deterministic for identical inputs. JSON output must use stable keys so downstream tooling can consume it without scraping console text.

## Idempotence and Recovery

This plan is safe to execute incrementally. The CLI wiring and runtime package are additive. If the implementation stalls after the CLI is wired but before the engine is ready, keep the command hidden behind a parser entry that returns a clear "not implemented" error rather than leaving a partially working simulator that produces misleading traces. If a shared evaluator extraction risks breaking `dataflow`, stop, add or update analyzer regression tests first, and only then continue the extraction.

## Artifacts and Notes

Recorded artifacts for closeout:

- Focused validation: `python scripts/run_repo_python.py -m pytest --no-cov tests/test_sfc_simulation.py tests/test_cli.py tests/test_app_cli_commands.py -x -q --tb=short` -> `39 passed in 1.06s`
- Touched-file lint: `python scripts/run_repo_python.py -m ruff check src/sattlint/cli/entry.py src/sattlint/app_base.py src/sattlint/app.py src/sattlint/app_cli_commands.py src/sattlint/simulation/runtime.py tests/test_cli.py tests/test_app_cli_commands.py tests/test_sfc_simulation.py` -> `All checks passed!`
- Touched-file typing: `python scripts/run_repo_python.py -m pyright src/sattlint/cli/entry.py src/sattlint/app_base.py src/sattlint/app.py src/sattlint/app_cli_commands.py src/sattlint/simulation/runtime.py tests/test_cli.py tests/test_app_cli_commands.py tests/test_sfc_simulation.py` -> `0 errors, 0 warnings, 0 informations`
- Real CLI proof: `python scripts/run_repo_python.py -m sattlint simulate tests/fixtures/corpus/semantic/ParallelWriteRace.s --module BasePicture --max-scans 4 --format json` -> exit `0` and a steady-state JSON payload with bounded scan snapshots.

Resolved semantic difference: the dataflow engine stores state on case-folded tuple keys, while the user-facing simulation payload needs declared variable names. The final runtime exports state using the resolved scope declarations so JSON output stays stable and human-readable.

The first concrete milestone should include a sample JSON shape similar to the following, updated to the real field names chosen during implementation:

    {
      "target": "Main",
      "mode": "steady-state",
      "steady_state_reached": true,
      "cycle_detected": false,
      "total_scans": 7,
      "snapshots": [ ... ]
    }

## Interfaces and Dependencies

The CLI contract must be defined in `src/sattlint/cli/entry.py` and wired through `src/sattlint/app_base.py`, `src/sattlint/app.py`, and `src/sattlint/app_cli_commands.py`. The new runtime lives under `src/sattlint/simulation/`. Workspace loading must continue to use `src/sattlint/core/semantic.py:load_workspace_snapshot()`. SFC structure must be interpreted using the same AST models already consumed by `src/sattlint/analyzers/sfc.py`. Expression and condition evaluation must reuse or extract logic from `src/sattlint/analyzers/dataflow.py`, especially the behavior currently centered around `_evaluate_condition()` and `_evaluate_expression()`. The initial tests belong in `tests/test_sfc_simulation.py`, with CLI coverage added to `tests/test_cli.py` and `tests/test_app_cli_commands.py`.
