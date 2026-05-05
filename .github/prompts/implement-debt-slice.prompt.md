---
description: "Implement one SattLint tech debt item from the tracker using the orchestrator and nearest specialist path"
name: "Implement Debt Slice"
argument-hint: "Tech debt ID like T-009"
agent: "SattLint Orchestrator"
---

# Implement Debt Slice

Implement the requested SattLint tech debt item.

## Requirements

- Use the `debt-id-routing` skill first against `docs/exec-plans/tech-debt-tracker.md`.
- Read `.git/sattlint-ai-coordination/current_work_lock.json` before first edit and claim the exact files you touch.
- Keep the work in one slice when one owner surface and one first validation command are enough.
- Use `.ai/tasks/task-contract.example.json` and `.ai/handoffs/handoff.example.json` as the canonical artifact shapes when creating or updating slice artifacts.
- If the debt item resolves cleanly to one owner surface, route execution to the closest specialist agent instead of keeping the whole change in orchestration scope.
- If the debt item has a listed blocker, stop and report that blocker unless the user explicitly asked for blocker-first work.
- Preserve one task path and one handoff path for the slice when work moves between planner, executor, test, and review.
- Report the changed files, first validation run, finish-gate intent, and whether `Validate Slice` or `Review Slice` should be used next.
