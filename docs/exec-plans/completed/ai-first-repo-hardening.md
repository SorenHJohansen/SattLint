# AI-First Repository Hardening And Delivery Plan

This ExecPlan is a living document. The sections Progress, Surprises & Discoveries, Decision Log, and Outcomes & Retrospective must be kept up to date as work proceeds.

## Purpose / Big Picture

SattLint already has strong AI instructions, but planning and debt tracking were split across four TODO files and multiple doc surfaces. After this plan was implemented, maintainers and coding agents gained one canonical execution path for AI-first repository operations and one consolidated technical-debt backlog that captures all active TODO items in one machine-readable location.

Observable outcome:

- AI contributors can start from one historical ExecPlan and one debt register instead of manually diffing multiple TODO files.
- TODO drift is reduced because debt and execution work are synchronized by source mapping.
- Repo audit and doc gardening can validate AI readiness from a single source of truth.

## Progress

- [x] (2026-04-29 00:00Z) Audited markdown inventory and gathered all TODO sources: TODO_GUI.md, TODO_REFACTOR.md, TODO_SATTLINT.md, TODO_TOOLS.md.
- [x] (2026-04-29 00:00Z) Created this AI-first hardening execution plan.
- [x] (2026-04-29 00:00Z) Created the consolidated debt register that now lives at docs/exec-plans/tech-debt-tracker.md.
- [x] (2026-04-29 00:30Z) Added doc-gardener enforcement so CI now fails on source-ledger drift, markdown mojibake, and stale refactor-lane status mismatches.
- [x] (2026-04-29 00:30Z) Added owner and target-window metadata to every P0 and P1 debt item in the canonical register.
- [x] (2026-04-29 00:30Z) Retired the four legacy TODO source files and recorded their consolidation state in the debt register source ledger.
- [x] (2026-04-29 00:45Z) Moved this finished ExecPlan from docs/exec-plans/active/ to docs/exec-plans/completed/ and updated repo references.

## Surprises & Discoveries

- Observation: TODO backlog is comprehensive but fragmented by theme, which creates cross-file duplication and status drift risk.
  Evidence: Active workstream status differed between TODO_REFACTOR.md and the coordination state for several lanes.

- Observation: The consolidation work had already advanced past the original plan assumptions: the legacy TODO files were removed in the active worktree before enforcement landed.
  Evidence: The current branch staged deletions for TODO_GUI.md, TODO_REFACTOR.md, TODO_SATTLINT.md, and TODO_TOOLS.md before this execution slice began.

- Observation: Markdown mojibake risk was narrow in the current snapshot and concentrated in this plan text rather than spread across the repo.
  Evidence: A targeted markdown search found the only live mojibake tokens inside this file before the enforcement check was added.

- Observation: AI control surfaces are strong, but no single canonical runbook existed for consolidating all TODO lanes into AI governance.
  Evidence: README, AGENTS.md, docs/exec-plans/index.md, and the legacy TODO files each held partial process state.

## Decision Log

- Decision: Keep TODO source files as working-area documents and introduce a consolidated debt register instead of deleting existing TODO files.
  Rationale: Superseded by the source-ledger retirement model after the canonical register was created and the legacy TODO files were removed.
  Date/Author: 2026-04-29 / Copilot (GPT-5.3-Codex)

- Decision: Place the new AI-first execution plan under docs/exec-plans/active/.
  Rationale: Matched the repo pattern for in-flight plans and kept discovery predictable during implementation.
  Date/Author: 2026-04-29 / Copilot (GPT-5.3-Codex)

- Decision: Consolidate all active debt into docs/exec-plans/tech-debt-tracker.md as the single tracker.
  Rationale: One canonical tracker is easier to navigate, easier to validate in CI, and aligns better with the harness-engineering model than parallel debt files.
  Date/Author: 2026-04-29 / Copilot (GPT-5.3-Codex)

- Decision: Retire the four legacy TODO files and keep their imported state in a source ledger inside docs/exec-plans/tech-debt-tracker.md.
  Rationale: Preserves source traceability without leaving two live backlog systems that can drift independently.
  Date/Author: 2026-04-29 / Copilot (GPT-5.4)

- Decision: Move this ExecPlan to docs/exec-plans/completed/ once all checklist items and validations were done.
  Rationale: Keeps docs/exec-plans/active/ limited to in-flight plans and aligns the repo index with actual status.
  Date/Author: 2026-04-29 / Copilot (GPT-5.4)

## Outcomes & Retrospective

The repository now has an AI-first execution anchor, a single debt aggregation surface, explicit owner and target-window metadata for all P0 and P1 debt, and CI-enforced doc-gardener checks for source-ledger drift, markdown mojibake, and stale refactor-lane statuses. This removed the previous split-brain backlog risk and gave maintainers one prioritized place to drive work.

Remaining gap: content parity work still remains for CLI docs and the larger roadmap programs, but the governance loop is now enforced instead of advisory. This file is now historical because the hardening work described here is complete.

## Context and Orientation

Relevant files for this plan:

- docs/exec-plans/completed/ai-first-repo-hardening.md (this file)
- docs/exec-plans/tech-debt-tracker.md (consolidated debt register and scan history)
- docs/exec-plans/index.md (ExecPlan and debt index)
- src/sattlint/devtools/doc_gardener.py (enforcement seam for AI-first doc health)
- .github/workflows/lint.yml (CI entrypoint for doc-gardener)
- retired TODO sources recorded in the source ledger: TODO_GUI.md, TODO_REFACTOR.md, TODO_SATTLINT.md, TODO_TOOLS.md
- AGENTS.md and .github/instructions/*.md (agent and invariant constraints)

Definitions used in this plan:

- AI-first repo: a repository where agent instructions, workflows, validations, and backlog routing are explicit, discoverable, enforceable, and optimized for low context waste.
- Debt register: canonical list of unresolved work items that carry risk, quality, maintenance, or delivery burden.
- Source mapping: explicit trace from each consolidated debt entry back to one TODO source file and item identity.

## Plan of Work

1. Consolidate all active TODO items into docs/exec-plans/tech-debt-tracker.md with explicit source mapping and severity.
  Status: complete.
2. Group debt by execution program:
   - Program A: AI control-plane hardening (docs, governance, drift controls).
   - Program B: Code and architecture debt (refactor and structural lanes).
   - Program C: Analyzer and semantic roadmap debt.
   - Program D: Tooling, CI, quality loop debt.
   - Program E: GUI and UX backlog debt.
  Status: complete.
3. Define a single prioritization policy:
   - P0 blocks correctness/security/release trust.
   - P1 blocks team velocity or introduces high drift risk.
   - P2 useful but not release blocking.
  Status: complete.
4. Add index links so discoverability starts at docs/exec-plans/index.md.
  Status: complete.
5. Replace the former TODO feeder model with a retired-source ledger plus doc-gardener enforcement.
  Status: complete.

## Concrete Steps

Run commands from repository root.

Review markdown inventory:

    rg --files -g "*.md"

Review consolidated debt rows:

    rg -n "^\| TODO_|^\| B-W|^\| C-|^\| D-" docs/exec-plans/tech-debt-tracker.md

Validate new planning docs render and are linked:

    rg -n "ai-first-repo-hardening|tech-debt-tracker" README.md docs/exec-plans/index.md docs/exec-plans/tech-debt-tracker.md

Optional quick doc-health check:

    python scripts/run_repo_python.py -m pytest --no-cov tests/test_repo_audit.py -x -q --tb=short -k "doc_gardener or ai_first or debt_register"

Expected outcomes:

- The debt register contains explicit sections sourced from the four retired TODO files.
- The repo index points to this historical plan under docs/exec-plans/completed/.
- Doc-gardener exits non-zero when the source ledger, markdown encoding checks, or refactor-lane statuses drift.

## Validation and Acceptance

Acceptance criteria:

- docs/exec-plans/completed/ai-first-repo-hardening.md exists as the historical record for this finished work.
- docs/exec-plans/tech-debt-tracker.md exists, includes all imported source material, and records the retired source-ledger state for the former TODO files.
- All P0 and P1 debt rows include owner and target-window metadata.
- Doc-gardener fails CI when the source ledger, markdown encoding checks, or refactor-lane statuses drift.
- README.md and docs/exec-plans/index.md link to the completed-plan location rather than the old active-path location.
- docs/exec-plans/tech-debt-tracker.md is the consolidated debt register.

## Idempotence and Recovery

This plan is documentation and devtools enforcement, and it remains idempotent.

- Re-running consolidation updates should preserve stable IDs in the debt register.
- If a retired TODO file is restored for editing, update the source ledger state and sync basis in the same change.
- If a bad merge occurs, recover by reconciling the source ledger, shared lock-state statuses, and canonical debt rows together.
- Moving this file between active and completed is safe as long as the repo references and doc-gardener required path are updated in the same change.

## Artifacts and Notes

Key input artifacts:

- docs/exec-plans/tech-debt-tracker.md source ledger
- shared active-claim lock state
- src/sattlint/devtools/doc_gardener.py

Supporting governance docs reviewed:

- AGENTS.md
- docs/references/ai-agent-reference.md
- docs/design-docs/core-beliefs.md
- docs/context-loading-order.md
- docs/exec-plans/index.md
- docs/exec-plans/tech-debt-tracker.md

## Interfaces and Dependencies

No runtime code interfaces changed.

Process interfaces established by this plan:

- Consolidation input interface: source-ledger rows that represent the four retired TODO files.
- Consolidation output interface: docs/exec-plans/tech-debt-tracker.md.
- Discoverability interface: README.md and docs/exec-plans/index.md links.
- Enforcement interface: src/sattlint/devtools/doc_gardener.py plus the lint workflow.
