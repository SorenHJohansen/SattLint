---
name: parallel-debt-routing
description: 'Group multiple SattLint tech debt IDs into isolated, blocked, and conflicting slices for safe parallel planning.'
argument-hint: 'Tech debt IDs like T-009, T-010, T-011'
---

# Parallel Debt Routing

Use this skill when a user wants to plan several tech debt items from `docs/exec-plans/tech-debt-tracker.md` as safe parallel slices.

## Canonical Sources

- `debt-id-routing` owns single-ID normalization and must be used first for each requested debt ID.
- `docs/exec-plans/tech-debt-tracker.md` owns debt purpose, implementation guide, validation, and blockers.
- The shared `.git/sattlint-ai-coordination/current_work_lock.json` lock state owns active claims and must be checked before proposing parallel slices.
- `.ai/tasks/task-contract.example.json` and `.ai/handoffs/handoff.example.json` are the artifact shape references.
- `sattlint-repo-audit --profile full --planning-context --changed-file <path> --output-dir artifacts/audit` is the canonical route check when ownership or first validation still needs confirmation.
- `docs/context-loading-order.md` keeps planning-context as the machine routing default and should be followed instead of hand-merging routes from multiple docs.

## Procedure

1. Normalize each requested debt ID separately with `debt-id-routing`. Keep each ID's purpose, ordered controlling files, likely owner surface, suggested agent, first validation candidate, blockers, and suggested artifact paths.
2. Read `.git/sattlint-ai-coordination/current_work_lock.json` before proposing claims. Treat active shared-file claims as blockers or sequencing requirements.
3. Compare the normalized IDs and group them by controlling file overlap, owner surface, blocker dependency, and shared AI-control risk.
4. Classify each requested ID into exactly one of these outcomes:
   - `parallel-safe slice`: isolated files or clearly separable owner surfaces with no active or predicted shared-file collision.
   - `blocked or sequential slice`: blocked by an explicit tracker blocker, active ledger claim, or prerequisite slice.
   - `conflict or shared-risk slice`: overlapping controlling files, mixed-owner surfaces that still need one planner decision, or shared AI-control files other than `.git/sattlint-ai-coordination/current_work_lock.json` that should not be edited in parallel.
5. Prefer one slice per isolated workstream, not one slice per raw debt ID. Combine IDs only when they resolve to the same isolated goal, same owner agent, same first validation command, and the same exact claims.
6. Make branch policy explicit: use one branch and one worktree per isolated slice; do not suggest a branch per raw debt ID unless that debt item remains isolated after grouping.
7. Use lower-kebab-case names for slice artifacts and branch slugs. When several IDs stay in one isolated slice, use a grouped slug like `t-009-lsp-diagnostics-cleanup` instead of stacking separate branches by default.
8. Use planning-context on candidate controlling files when ownership, first validation, or finish-gate choice is still ambiguous.
9. Keep blockers and conflicts explicit. Do not silently merge blocked work into a parallel-safe slice.

## Output Contract

- `Parallel-safe slices:` one bullet per slice with `Slice`, `Suggested agent`, `Claims`, `Branch`, `Worktree`, `Task file`, `Handoff file`, `First validation`, and `Blockers or conflicts`.
- `Blocked or sequential slices:` one bullet per slice with the same fields plus `Why blocked`.
- `Conflict or shared-risk slices:` one bullet per slice with the same fields plus `Shared risk`.
- `Branch policy:` `Use one branch/worktree per isolated slice, not per raw debt ID unless isolated.`
- `Lock-state check:` `Record or update claims in .git/sattlint-ai-coordination/current_work_lock.json before implementation starts.`

## Guardrails

- Do not invent debt IDs, files, blockers, or validations.
- Do not mark slices parallel-safe when they touch the same controlling file or the same shared AI-control file other than `.git/sattlint-ai-coordination/current_work_lock.json`.
- Do not drop a blocker just because other IDs in the batch are runnable.
- Do not propose one task or handoff artifact that mixes unrelated blocked and runnable slices.
