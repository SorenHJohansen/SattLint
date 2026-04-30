# D-Wave-3: Semantic And Differential Tooling

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

## Purpose / Big Picture

This plan implements D-Wave-3 roadmap items: D-020 (SattLine mutation engine), D-024 (improved dead code detection), and D-034 (differential analysis). When complete, SattLint will support controlled mutation-based semantic testing and stable baseline-vs-current drift detection, with clearer dead-code findings quality.

Observable outcome: maintainers can run deterministic mutation and differential workflows on known fixtures and review behavior drift with reproducible artifacts.

## Progress

- [x] (2026-04-29) Create this active D-Wave-3 plan with scoped milestones and validation routing.
- [ ] Milestone A complete: D-020 mutation engine foundation and deterministic fixture outputs.
- [ ] Milestone B complete: D-024 dead code detection improvements with focused regression tests.
- [ ] Milestone C complete: D-034 differential analysis workflow and stable artifact comparison output.
- [ ] Wave-close validation complete and D-Wave-3 item statuses updated in `docs/exec-plans/feature-roadmap.md`.
- [ ] Move this file to `docs/exec-plans/completed/` once all checklist items are complete.

## Surprises & Discoveries

- Observation: D-Wave-3 depends on stable analyzer outputs to make drift comparisons actionable.
  Evidence: differential tooling is only useful when fixture outputs are deterministic and noise-minimized.
- Observation: mutation tooling can accidentally break strict parser assumptions if generated variants are not constrained.
  Evidence: parser invariants require valid fixture headers and strict syntax behavior in single-file checks.

## Decision Log

- Decision: Implement D-020 before D-024 and D-034.
  Rationale: mutation engine provides reusable inputs and stress cases that help validate dead-code and differential surfaces.
  Date/Author: 2026-04-29 / Copilot (GPT-5.3-Codex)
- Decision: Keep D-024 and D-034 in the same plan to avoid split ownership of analyzer-drift behavior.
  Rationale: dead-code improvements and differential analysis share validation artifacts and should evolve together.
  Date/Author: 2026-04-29 / Copilot (GPT-5.3-Codex)

## Outcomes & Retrospective

Planning baseline complete. Execution outcomes and measured drift-quality improvements will be appended after milestone completion.

## Context and Orientation

Program D source of truth is `docs/exec-plans/feature-roadmap.md`. D-Wave-3 is the semantic and differential tooling wave targeted for 2026-Q4.

Definitions used in this plan:

- Mutation engine: tool that creates controlled variants of valid SattLine inputs to test analyzer and semantic behavior.
- Dead code detection: identifying code paths or declarations that are never used or reachable.
- Differential analysis: comparing outputs from two runs (baseline vs. current) to detect meaningful behavior change.

Expected seams for D-Wave-3 implementation:

- Semantic and analyzer cores under `src/sattlint/**` where dead-code or mutation logic is implemented.
- Devtools/pipeline seams under `src/sattlint/devtools/**` for artifact creation and comparison.
- Validation tests in nearest analyzer, pipeline, and semantic owner suites.

## Plan of Work

Milestone A (D-020): create mutation primitives and orchestration that produce deterministic variants from fixed fixtures, with explicit constraints to preserve parser validity and reproducibility.

Milestone B (D-024): improve dead-code detection precision and coverage by tightening rules and adding focused tests for false-positive and true-positive behavior.

Milestone C (D-034): implement differential analysis that compares known baseline artifacts to current outputs, emits machine-readable differences, and surfaces actionable summaries.

## Concrete Steps

Run from repository root:

    cd "c:/Users/SQHJ/OneDrive - Novo Nordisk/Workspace/GitHub.com/SattLint"

Milestone A first validation:

    & ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_analyzers_suites.py tests/test_analyzers_state.py -x -q --tb=short

Milestone B first validation:

    & ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_analyzers_suites.py tests/test_analyzers_state.py tests/test_editor_api.py -x -q --tb=short

Milestone C first validation:

    & ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_pipeline.py tests/test_repo_audit.py -x -q --tb=short

Wave-close validation:

    & ".venv/Scripts/python.exe" -m pytest -q
    & ".venv/Scripts/sattlint-repo-audit.exe" --profile quick --output-dir artifacts/audit-review-quick

## Validation and Acceptance

Acceptance requires:

- D-020 produces reproducible mutation outputs for fixed inputs,
- D-024 test coverage demonstrates improved dead-code behavior without regression in strict validation boundaries,
- D-034 produces deterministic differential artifacts with clear drift summaries,
- roadmap statuses for D-020, D-024, and D-034 updated in `docs/exec-plans/feature-roadmap.md`.

## Idempotence and Recovery

Each milestone should be rerunnable without manual cleanup. Keep generated artifacts in stable output paths and overwrite-safe modes where possible. If comparison output changes unexpectedly, inspect baseline fixture integrity before changing logic.

## Artifacts and Notes

Record per milestone:

- focused test commands and pass counts,
- sample mutation or differential artifact paths,
- before-vs-after finding deltas for dead-code detection,
- roadmap updates applied.

## Interfaces and Dependencies

Preserve core invariants:

- strict single-file syntax-check remains stricter than workspace loading,
- analyzer and semantic behavior changes are test-backed and deterministic,
- differential outputs stay machine-readable and stable for CI consumption.
