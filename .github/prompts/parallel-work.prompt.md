---
description: "Split a SattLint task into safe parallel workstreams with file claims and validation routing"
name: "Parallel Work"
argument-hint: "Describe task to split across chats or agents"
agent: "SattLint Orchestrator"
---
Break down the requested SattLint work into isolated workstreams.

Requirements:
- Read `.github/coordination/current-work.md` first.
- Avoid overlapping file claims unless explicitly justified.
- Assign one first validation command per workstream from [validation map](../skills/validation-routing/references/validation-map.md).
- Call out shared-risk files, merge points, and final verification owner.
- Update the coordination ledger when useful.