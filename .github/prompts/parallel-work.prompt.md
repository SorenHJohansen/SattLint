---
description: "Split a SattLint task into parallel workstreams with file claims and validation routing"
name: "Parallel Work"
argument-hint: "Describe task to split across chats or agents"
agent: "SattLint Orchestrator"
---

# Parallel Work

Break down the requested SattLint work into isolated workstreams.

## Requirements

- Read `.git/sattlint-ai-coordination/current_work_lock.json` first.
- Avoid overlapping file claims unless explicitly justified.
- Keep each workstream coherent; do not split one architectural fix into multiple streams just for smaller diffs.
- Assign one first validation command per workstream from [validation map](../skills/validation-routing/references/validation-map.md).
- Call out shared-risk files, merge points, and final verification owner.
- Update the shared lock state when useful.
