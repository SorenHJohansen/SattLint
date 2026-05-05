---
description: "Plan parallel-safe SattLint work slices from multiple tech debt IDs in the tracker"
name: "Plan Parallel Debt Slices"
argument-hint: "Tech debt IDs like T-009, T-010, T-011"
agent: "Planner"
---

# Plan Parallel Debt Slices

Plan parallel-safe SattLint work slices from the requested tech debt items.

Requirements:

- Use the `parallel-debt-routing` skill first.
- The skill must reuse `debt-id-routing` against `docs/exec-plans/tech-debt-tracker.md` for each requested debt ID before grouping anything.
- Read `.git/sattlint-ai-coordination/current_work_lock.json` before proposing claims.
- Keep branch policy explicit: use one branch and one worktree per isolated slice, not one per raw debt ID unless that debt item stays isolated after grouping.
- Use `.ai/tasks/task-contract.example.json` and `.ai/handoffs/handoff.example.json` as the artifact shape references when suggesting task and handoff paths.
- For each runnable slice, return a concrete `python scripts/bootstrap_ai_slice.py ...` command instead of telling the executor to edit the coordination ledger manually.
- Use `sattlint-repo-audit --profile full --planning-context --changed-file <path> --output-dir artifacts/audit` when controlling files or first validation still need a route check.
- Return `Parallel-safe slices`, `Blocked or sequential slices`, and `Conflict or shared-risk slices`.
- For each proposed slice, include the grouped debt IDs, purpose, suggested owner agent, exact file claims, bootstrap command, branch name, worktree name, suggested task path, suggested handoff path, first validation command, and blockers or conflicts.
- If two debt IDs want the same controlling file or the same shared AI-control file other than `.git/sattlint-ai-coordination/current_work_lock.json`, do not mark them parallel-safe until the conflict is isolated or sequenced.
