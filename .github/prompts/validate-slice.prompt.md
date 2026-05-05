---
description: "Validate a completed SattLint slice or debt-item handoff using the Test Agent"
name: "Validate Slice"
argument-hint: "Task ID, handoff path, or debt ID"
agent: "Test Agent"
---

# Validate Slice

Validate a completed SattLint slice.

## Requirements

- If the input is only a debt ID, use the `debt-id-routing` skill first to infer likely task or handoff naming plus owner tests.
- Read the executor task contract and handoff first when they exist.
- If the task contract or handoff is missing, point back to `.ai/tasks/task-contract.example.json` and `.ai/handoffs/handoff.example.json` instead of inventing an ad hoc artifact shape.
- Read `.git/sattlint-ai-coordination/current_work_lock.json` before claiming any proof files.
- Run the first focused validation from the handoff or nearest owner route before widening.
- Add only the smallest regression or edge-case coverage needed for the changed behavior.
- Report with the `Test Agent` status format and include the updated handoff path when one exists.
