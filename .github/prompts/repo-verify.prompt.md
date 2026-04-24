---
description: "Run the full SattLint repo verification gate using the Repo Verify specialist"
name: "Repo Verify"
argument-hint: "Optional verification focus or failure context"
agent: "Repo Verify"
---
Run the full SattLint repo verification gate.

Requirements:
- Read `.github/coordination/current-work.md` first.
- If completed workstreams exist, summarize their touched subsystems and recorded focused validations before the full gate.
- Use [validation map](../skills/validation-routing/references/validation-map.md) only for any missing focused prechecks; keep full gate ownership and report format in `Repo Verify`.
- Run the verification commands in the correct order.
- Report with the `Repo Verify` status format.