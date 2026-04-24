---
description: "Turn completed SattLint workstreams into a final verification checklist for Repo Verify"
name: "Merge Workstreams"
argument-hint: "Optional merge focus or release note"
agent: "Repo Verify"
---
Read `.github/coordination/current-work.md` and build the final verification checklist for converging workstreams.

Requirements:
- Focus on workstreams marked `ready-for-merge` or `done`.
- Summarize claimed files, touched subsystems, and validations already recorded.
- Identify missing focused checks from [validation map](../skills/validation-routing/references/validation-map.md) before running the full verification gate.
- Run the needed verification commands in the correct order.
- Report with the `Repo Verify` status format.