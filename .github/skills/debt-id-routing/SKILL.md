---
name: debt-id-routing
description: 'Normalize a SattLint tech debt ID from docs/exec-plans/tech-debt-tracker.md into purpose, controlling files, likely owner surface, suggested agent, validation, and blockers.'
argument-hint: 'Tech debt ID like T-009'
---

# Debt ID Routing

Use this skill when a user wants to plan or implement one tech debt item from `docs/exec-plans/tech-debt-tracker.md`.

## Canonical Sources

- `docs/exec-plans/tech-debt-tracker.md` owns the debt IDs, purpose, implementation guide, validation, and blockers.
- `sattlint-repo-audit --profile full --planning-context --changed-file <path> --output-dir artifacts/audit` is the canonical route check once candidate files are known.
- `.github/skills/validation-routing/references/validation-map.md` is the fallback first-check source when planning-context is not being run.

## Procedure

1. Find the matching heading `### <debt-id>` in `docs/exec-plans/tech-debt-tracker.md`.
2. Extract these fields when present: `Status`, `Priority`, `Owner`, `Target Window`, `Wave`, `Purpose`, `Implementation Guide`, `Validation`, `Reuses`, and `Blocker`.
3. Treat the `Implementation Guide` rows as the ordered candidate controlling files. Keep the listed order instead of widening to related files immediately.
4. Infer the likely owner surface and specialist agent from the first controlling file that actually decides behavior:
   - `src/sattlint_lsp/**`, `src/sattlint/core/**`, `src/sattlint/editor_api.py`, or `vscode/**` -> `Workspace LSP`
   - `src/sattline_parser/**`, `src/sattlint/validation.py`, or `src/sattlint/analyzers/**` -> `Parser Analysis`
   - `src/sattlint/devtools/**` -> `Repo Audit`
   - `src/sattlint/app.py`, `src/sattlint/config.py`, `src/sattlint/cli/**`, or `src/sattlint/console.py` -> `CLI App Menu`
   - `src/sattlint/docgenerator/**` -> `Documentation Generation`
   - mixed owner surfaces, broad `src/sattlint/**/*.py` migration lanes, or unresolved ownership -> `Planner` first
5. Convert the debt item validation into a first-check candidate. If the listed validation is broad, narrow it with planning-context or the validation map before implementation.
6. Keep blockers explicit. Do not silently absorb blocker work into the same slice unless the user asked for that broader scope.
7. Suggest task and handoff paths in lower-kebab-case using the debt ID plus a short topic, for example `.ai/tasks/t-009-lsp-import-typing-cleanup.json` and `.ai/handoffs/t-009-lsp-import-typing-cleanup.json`.
8. Use `.ai/tasks/task-contract.example.json` and `.ai/handoffs/handoff.example.json` as the canonical shape references when proposing or creating new slice artifacts.

## Output Contract

- `Debt:` `<id> | status | priority | owner | wave`
- `Purpose:` `<purpose>`
- `Controlling files:` `<ordered files>`
- `Likely owner surface:` `<surface>`
- `Suggested agent:` `<agent>`
- `First validation:` `<command>`
- `Finish gate:` `<command or none yet>`
- `Blockers:` `<none or blocker>`
- `Suggested task file:` `<path>`
- `Suggested handoff file:` `<path>`
- `Artifact templates:` `.ai/tasks/task-contract.example.json | .ai/handoffs/handoff.example.json`

## Guardrails

- Do not invent files, blockers, or validations that are not grounded in the tracker or planning-context output.
- Do not split one debt item into multiple slices unless the listed files span incompatible owner surfaces or the blocker forces that split.
- Prefer the first listed controlling file over generic owner labels when they disagree.
- If the debt item touches shared AI-control files such as `.github/**`, claim them first and keep the slice narrow.
