---
description: "Review a completed SattLint slice or debt-item handoff using the Reviewer Agent"
name: "Review Slice"
argument-hint: "Task ID, handoff path, or debt ID"
agent: "Reviewer Agent"
---

# Review Slice

Review a completed SattLint slice for merge readiness.

## Requirements

- If the input is only a debt ID, use the `debt-id-routing` skill first to identify likely task or handoff naming and controlling files.
- Read the task contract, handoff, and changed files first.
- If the task contract or handoff is missing, point back to `.ai/tasks/task-contract.example.json` and `.ai/handoffs/handoff.example.json` instead of inventing new review-only fields.
- Read `.git/sattlint-ai-coordination/current_work_lock.json` for claims, blockers, and validation context.
- Prefer missing focused checks over broad repo verification when proof is incomplete.
- Report with the `Reviewer Agent` status format.
