# D-Wave-2: Test And Quality Infrastructure

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

## Purpose / Big Picture

This plan implements all D-Wave-2 roadmap items as one execution program: D-016, D-017, D-018, D-022, D-023, D-026, D-030, D-033, D-036, and D-037. When complete, SattLint will gain stronger test robustness, parser stress tooling, finding-quality feedback loops, invariant and maintainability checks, configuration validation, observability, analyzer examples, and AI task templates.

Observable outcome: maintainers can run focused test or audit commands per subsystem first, then run wave-close verification and update Program D statuses in the roadmap without re-triage.

## Progress

- [x] (2026-04-29) Create this active D-Wave-2 plan with milestone sequencing and validation routing.
- [ ] Milestone A complete: D-016 fault injection and robustness testing foundation.
- [ ] Milestone B complete: D-017 property-based parser testing and D-018 fuzzing targets.
- [ ] Milestone C complete: D-022 finding validation feedback loop.
- [ ] Milestone D complete: D-023 core invariant checks and D-033 maintainability/test-quality checks.
- [ ] Milestone E complete: D-026 configuration validation and D-030 logging/observability.
- [ ] Milestone F complete: D-036 analyzer reference examples and D-037 AI task templates.
- [ ] Wave-close validation complete and D-Wave-2 item statuses updated in `docs/exec-plans/feature-roadmap.md`.
- [ ] Move this file to `docs/exec-plans/completed/` once all checklist items are complete.

## Surprises & Discoveries

- Observation: D-Wave-2 spans parser, devtools, CLI/config, docs, and AI surfaces, so implementing by milestone and test ownership is safer than by file tree order.
  Evidence: existing repo instructions and active plans consistently route to nearest focused tests before full runs.
- Observation: D-Wave-1 (pre-commit hooks) is already isolated in its own active plan and should not be mixed into this execution scope.
  Evidence: `docs/exec-plans/active/06-d-wave-1-pre-commit-hooks.md` tracks D-032 independently.

## Decision Log

- Decision: Keep all D-Wave-2 items in one dedicated plan file instead of splitting by subsystem.
  Rationale: these items share a common delivery window and acceptance route (`pytest` + quick audit), and one plan reduces cross-plan drift.
  Date/Author: 2026-04-29 / Copilot (GPT-5.3-Codex)
- Decision: Sequence Milestones C through F after parser/test infrastructure to reduce churn in downstream quality checks.
  Rationale: robustness and parser-stress tooling should stabilize first so later invariant and observability checks can build on stable surfaces.
  Date/Author: 2026-04-29 / Copilot (GPT-5.3-Codex)

## Outcomes & Retrospective

Planning baseline complete. Execution outcomes will be appended as milestones close, including command outputs, updated tests, and roadmap status changes.

## Context and Orientation

Program D roadmap source of truth is `docs/exec-plans/feature-roadmap.md`. D-Wave-2 is defined there as the 2026-Q3 test and quality infrastructure wave with ten items.

Definitions used in this plan:

- Fault injection: intentionally inducing controlled failures to verify robustness behavior.
- Property-based testing: generating many randomized inputs under constraints to validate invariants.
- Fuzzing target: a parser or processing entry point exercised with large input variation to expose crashes or hangs.
- Invariant check: a machine-enforced repository rule that must remain true.
- Observability: structured logs or metrics that make runtime behavior diagnosable.

Expected seams for D-Wave-2 implementation:

- Parser testing/tooling: `src/sattline_parser/**`, parser tests under `tests/test_parser*.py` and related fixtures.
- Devtools and checks: `src/sattlint/devtools/**`, `tests/test_repo_audit.py`, `tests/test_pipeline.py`, and artifact checks.
- Config and CLI surfaces: `src/sattlint/config.py`, `src/sattlint/app.py`, `src/sattlint/cli/entry.py`, with nearest app or CLI tests.
- Documentation examples: docgen/docs seams and `tests/test_docgen.py` when behavior changes.
- AI templates: repository AI customization paths and related docs surfaces.

## Plan of Work

Milestone A: implement D-016 by adding deterministic fault-injection scaffolding to existing test infrastructure and wiring focused robustness assertions in the nearest owner suites.

Milestone B: implement D-017 and D-018 by introducing property-based parser tests and fuzz entry targets while preserving strict syntax-check invariants and fixture conventions.

Milestone C: implement D-022 by adding a finding-validation feedback loop that captures remediation signal and shortens quality iteration time.

Milestone D: implement D-023 and D-033 by extending existing devtools seams with core invariant checks plus maintainability and test-quality checks, keeping machine-readable outputs stable.

Milestone E: implement D-026 and D-030 by adding configuration validation gates and structured observability support in existing seams, with clear failure messages and no silent fallback behavior.

Milestone F: implement D-036 and D-037 by adding analyzer reference examples and AI task templates that match real workflows and are validated with nearest docs or tooling checks.

## Concrete Steps

Run commands from repository root.

Milestone A first validation:

    & ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_pipeline.py -x -q --tb=short

Milestone B first validation:

    & ".venv/Scripts/sattlint.exe" syntax-check tests/fixtures/corpus/valid/VariableModifiers.s
    & ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_parser_core.py tests/test_transformer.py -x -q --tb=short

Milestone C/D first validation:

    & ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_repo_audit.py tests/test_pipeline.py -x -q --tb=short
    & ".venv/Scripts/sattlint-repo-audit.exe" --profile quick --output-dir artifacts/audit-review-quick

Milestone E/F first validation:

    & ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_cli.py tests/test_app.py tests/test_docgen.py tests/test_gui.py -x -q --tb=short

Wave-close validation:

    & ".venv/Scripts/python.exe" -m pytest -q
    & ".venv/Scripts/sattlint-repo-audit.exe" --profile quick --output-dir artifacts/audit-review-quick

## Validation and Acceptance

Acceptance requires all ten D-Wave-2 items to have:

- implementation evidence in the relevant seams,
- focused validation command results recorded,
- nearest owner tests updated where behavior changed,
- quick audit output still machine-readable and stable.

Wave completion requires roadmap status updates for D-016, D-017, D-018, D-022, D-023, D-026, D-030, D-033, D-036, and D-037 in `docs/exec-plans/feature-roadmap.md`.

## Idempotence and Recovery

Milestones are designed as additive slices with narrow-first validation. Re-run the same focused command after each local change. If broad validation fails for unrelated reasons, keep milestone status accurate in `Progress`, note blocker evidence, and continue unaffected milestones.

## Artifacts and Notes

Record, for each milestone:

- first focused command and result (`N passed`),
- changed test files and key behavior covered,
- quick audit output path under `artifacts/audit/`,
- roadmap status updates applied.

## Interfaces and Dependencies

Preserve existing boundaries:

- strict parser checks stay strict (`sattlint syntax-check`),
- devtools checks extend current audit seams instead of creating parallel registries,
- CLI and config behavior remains consistent with existing entrypoints and tests,
- docs and AI examples reflect actual implemented behavior, not hypothetical future APIs.
