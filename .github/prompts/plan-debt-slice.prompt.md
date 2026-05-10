---
description: "Plan a scoped SattLint work slice from one tech debt ID in the tracker"
name: "Plan Debt Slice"
argument-hint: "Tech debt ID like T-009"
agent: "Planner"
---

# Plan Debt Slice

Plan one SattLint work slice from the requested tech debt item.

Requirements:

- Use the `debt-id-routing` skill first against `docs/exec-plans/tech-debt-tracker.md`.
- Use the `codegraph-routing` skill before broad text search when you need to confirm the controlling symbol, caller flow, or owner surface. The main session must call codegraph tools directly — subagents cannot access MCP tools.
- If the owning surface is still unclear after the first lightweight lookup, use `codegraph_explore` in the main session to gather source sections, then pass them inline to the subagent.
- Read `.git/sattlint-ai-coordination/current_work_lock.json` before proposing claims.
- Keep one slice when possible; split only when the debt item spans incompatible owner surfaces or an explicit blocker requires a precursor slice.
- Use `.ai/tasks/task-contract.example.json` and `.ai/handoffs/handoff.example.json` as the artifact shape references when suggesting task and handoff paths.
- Return a concrete `python scripts/bootstrap_ai_slice.py ...` command for the executor slice instead of telling the executor to edit the coordination ledger manually.
- When a candidate slice claims an oversized structural debt file from `artifacts/analysis/file_debt_ratchet.json`, plan it as an explicit shrink or decomposition slice and bias the edit strategy toward extraction into sibling modules instead of appending more code into that owner file.
- Use `sattlint-repo-audit --profile full --planning-context --changed-file <path> --output-dir artifacts/audit` once candidate controlling files are known if routing still needs confirmation.
- Return the debt summary, likely owner surface, suggested specialist agent, exact file claims, bootstrap command, first validation, finish gate, blockers, suggested task path, and suggested handoff path.
