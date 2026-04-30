# D-Wave-2, D-Wave-3, And Backlog Execution (Superseded)

This ExecPlan is superseded by split execution plans:

- `docs/exec-plans/active/08-d-wave-2-test-and-quality-infrastructure.md`
- `docs/exec-plans/active/09-d-wave-3-semantic-and-differential-tooling.md`
- `docs/exec-plans/active/10-d-wave-backlog-advanced-analysis-gating.md`

Do not execute milestones from this file. Keep it only as historical context from the initial combined planning pass.

## Purpose / Big Picture

This plan was replaced to provide one dedicated execution document per roadmap wave.

## Progress

- [x] (2026-04-29) Create this active plan and map all D-Wave-2, D-Wave-3, and D-Wave-Backlog items into implementation milestones.
- [ ] Execute D-Wave-2 Milestone A (D-016, D-017, D-018) with focused pytest coverage and quick audit checks.
- [ ] Execute D-Wave-2 Milestone B (D-022, D-023, D-033) and validate finding-quality loop plus maintainability checks.
- [ ] Execute D-Wave-2 Milestone C (D-026, D-030, D-036, D-037) and validate config guards, observability, docs examples, and AI templates.
- [ ] Execute D-Wave-3 Milestone D (D-020 mutation engine foundation) with deterministic fixture-driven validation.
- [ ] Execute D-Wave-3 Milestone E (D-024 dead code detection and D-034 differential analysis) and validate stable artifact diffs.
- [ ] Run wave-close validation and update `docs/exec-plans/feature-roadmap.md` status fields for all completed D items.
- [ ] Decide whether D-Wave-Backlog items (D-025, D-035) are promoted to active scope or remain deferred with explicit entry criteria.
- [ ] Move this plan to `docs/exec-plans/completed/` once all non-deferred checklist items are complete.

## Surprises & Discoveries

- Observation: Program D already has D-Wave-1 in active execution, so this plan must avoid re-opening pre-commit scope.
  Evidence: `docs/exec-plans/active/06-d-wave-1-pre-commit-hooks.md` already tracks D-032 implementation status.
- Observation: Program D spans multiple subsystems, so sequencing by test ownership and validation surface is lower-risk than sequencing by architecture layer.
  Evidence: existing instructions and active plans route work to focused commands (`pytest` owner modules and quick repo-audit profile) before broad runs.

## Decision Log

- Decision: Keep D-Wave-2 and D-Wave-3 in one active plan file, with backlog gating in the same document.
  Rationale: these waves are contiguous roadmap scope and share validation surfaces; one plan reduces handoff drift.
  Date/Author: 2026-04-29 / Copilot (GPT-5.3-Codex)
- Decision: Treat D-Wave-Backlog as a gated section with explicit promotion criteria instead of immediate implementation scope.
  Rationale: roadmap marks both backlog items as deferred pending symbolic-execution scope confirmation.
  Date/Author: 2026-04-29 / Copilot (GPT-5.3-Codex)

## Outcomes & Retrospective

Initial planning outcome complete: Program D waves now have a concrete implementation sequence and validation routing.

Milestone outcomes will be recorded here as each milestone closes, including pass/fail evidence and any scope corrections.

## Context and Orientation

Program D in `docs/exec-plans/feature-roadmap.md` defines new tooling and CI capabilities that do not exist yet. This plan implements all remaining non-Wave-1 Program D work through milestone slices that can be executed by a stateless coding agent.

Definitions used in this plan:

- Finding validation loop: tooling that shortens time between a reported finding and user-confirmed remediation or suppression.
- Invariant checks: machine-enforced assertions that repository rules stay true across code, docs, artifacts, and test quality.
- Differential analysis: comparing current analyzer output against a known baseline fixture to detect behavior drift.
- Symbolic execution lite: bounded path exploration that reasons over possible value flows without requiring full theorem-prover infrastructure.

Primary implementation seams expected for this plan:

- `src/sattline_parser/**` and parser-focused tests for D-017/D-018.
- `src/sattlint/devtools/**` and `tests/test_repo_audit.py` or `tests/test_pipeline.py` for D-022, D-023, D-033, D-034, D-035.
- `src/sattlint/config.py`, CLI wiring, and nearest CLI or app tests for D-026.
- Observability/reporting seams and tests for D-030.
- Documentation generation and docs examples for D-036.
- AI workflow surfaces under repo customization paths for D-037.
- Semantic tooling seams for D-020, D-024, D-025.

## Plan of Work

Implement in five milestones, each with a mandatory first-validation command before broad verification.

Milestone A closes parser and robustness infrastructure in D-Wave-2. Add fault injection harnessing (D-016), property-based parser coverage (D-017), and fuzz targets (D-018) in the smallest seams that reuse existing parser fixtures and strict syntax-check behavior.

Milestone B closes quality-loop and maintainability infrastructure in D-Wave-2. Implement finding feedback routing (D-022), core invariant checks (D-023), and maintainability/test-quality checks (D-033) in existing devtools and pipeline seams instead of parallel registries.

Milestone C closes configuration, observability, docs examples, and AI templates in D-Wave-2. Implement configuration validation (D-026), logging and observability (D-030), analyzer reference examples (D-036), and AI task templates (D-037), then validate each through nearest owner tests and quick audit profile.

Milestone D closes D-Wave-3 mutation foundation. Implement the SattLine mutation engine core (D-020) with deterministic fixture mutations and explicit acceptance criteria on generated variants.

Milestone E closes D-Wave-3 drift controls. Implement improved dead-code detection (D-024) and differential analysis pipeline support (D-034), then validate behavior using baseline-versus-current artifact comparisons with stable outputs.

Backlog gating: D-025 and D-035 are not implemented by default. Promote only when all D-Wave-2 and D-Wave-3 items are complete and symbolic-execution scope constraints are documented in this plan.

## Concrete Steps

Run commands from repository root:

    cd "c:/Users/SQHJ/OneDrive - Novo Nordisk/Workspace/GitHub.com/SattLint"

Milestone A first validation:

    & ".venv/Scripts/sattlint.exe" syntax-check tests/fixtures/corpus/valid/VariableModifiers.s
    & ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_parser_core.py tests/test_transformer.py -x -q --tb=short

Milestone B first validation:

    & ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_repo_audit.py tests/test_pipeline.py -x -q --tb=short
    & ".venv/Scripts/sattlint-repo-audit.exe" --profile quick --output-dir artifacts/audit-review-quick

Milestone C first validation:

    & ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_cli.py tests/test_app.py tests/test_gui.py tests/test_docgen.py -x -q --tb=short
    & ".venv/Scripts/sattlint-repo-audit.exe" --profile quick --output-dir artifacts/audit-review-quick

Milestone D/E first validation:

    & ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_analyzers_suites.py tests/test_analyzers_state.py tests/test_pipeline.py -x -q --tb=short

Wave-close validation:

    & ".venv/Scripts/python.exe" -m pytest -q
    & ".venv/Scripts/sattlint-repo-audit.exe" --profile quick --output-dir artifacts/audit-review-quick

## Validation and Acceptance

D-Wave-2 acceptance:

- D-016, D-017, D-018, D-022, D-023, D-026, D-030, D-033, D-036, and D-037 each have implementation evidence and nearest focused tests updated.
- `pytest` focused routes pass for each changed subsystem before broad run.
- Quick repo audit profile runs clean for new checks and emits machine-readable outputs.

D-Wave-3 acceptance:

- D-020 mutation engine produces deterministic, reproducible outputs for fixed fixture inputs.
- D-024 dead-code improvements reduce false positives or expand true-positive coverage with tests proving the delta.
- D-034 differential analysis produces stable comparisons against known fixtures and reports drift clearly.

Backlog acceptance:

- D-025 and D-035 remain deferred unless promotion criteria are met and recorded.
- If promoted, this file must be updated with explicit milestones, first-validation routes, and non-ambiguous done criteria before implementation begins.

Final acceptance:

- Program D status in `docs/exec-plans/feature-roadmap.md` is updated for every completed item.
- This plan moves to `docs/exec-plans/completed/` with all non-deferred checklist items checked.

## Idempotence and Recovery

Each milestone is scoped so it can be rerun safely. Keep changes additive and validate narrow-first. If a broad validation fails for unrelated reasons, document the blocker in `Progress`, keep milestone status accurate, and continue with unaffected slices. If quick audit output changes unexpectedly, compare `artifacts/audit/status.json` first and fix only deterministic regressions introduced by the current milestone.

## Artifacts and Notes

Record milestone evidence directly in this file as work proceeds:

- Focused validation command used as first gate.
- Key test results (`N passed`) for each milestone.
- Any new artifact paths under `artifacts/audit/` or related generated outputs.
- Brief note for status updates applied in `docs/exec-plans/feature-roadmap.md`.

## Interfaces and Dependencies

This plan depends on existing repo validation boundaries:

- Strict parser validation remains under `sattlint syntax-check` and parser-focused tests.
- Devtools and pipeline checks remain in existing `src/sattlint/devtools/**` seams.
- CLI and app behavior remains routed through current entrypoints and nearest app or CLI tests.
- Workspace/LSP behavior changes, if any, must preserve strict-versus-workspace validation boundaries and follow restart guidance when those modules are touched.
