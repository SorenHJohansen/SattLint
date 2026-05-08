---
description: "Check CodeGraph index health or refresh the repo index for SattLint"
name: "CodeGraph Maintenance"
argument-hint: "Say health, sync, or rebuild and include the reason if relevant"
---

# CodeGraph Maintenance

Use the repo-owned CodeGraph maintenance path instead of ad hoc shell commands.

Requirements:

- Start with the `AI: CodeGraph Health` task or the equivalent `codegraph status <workspace>` command.
- If the index exists but is stale, prefer `AI: Sync CodeGraph Index` before a full rebuild.
- If the index is missing, corrupted, or the config changed materially, use `AI: Rebuild CodeGraph Index`.
- Report whether the index is present, fresh enough for the task, and whether a sync or rebuild was required.
- If CodeGraph is unavailable on the machine, say that explicitly and fall back to repo-local search.