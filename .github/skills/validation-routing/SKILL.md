---
name: validation-routing
description: 'Choose the first focused validation command for SattLint changes. Use for routing parser, analyzer, CLI, repo-audit, and workspace or LSP work to the correct narrow check before broader verification.'
argument-hint: 'Describe files or subsystem being changed'
---

# Validation Routing

Use this skill when you need to decide which validation to run first after a SattLint edit.

## Canonical Source

- `sattlint-repo-audit --profile full --planning-context --output-dir artifacts/audit` is the default machine entrypoint for agents.
- `sattlint-repo-audit --profile full --check-my-changes --output-dir artifacts/audit` is the execution companion that runs the selected finish gate.
- `.github/skills/validation-routing/references/validation-map.md` owns canonical first-check command text for SattLint surfaces.
- `.github/skills/validation-routing/references/ai-work-map.json` is the machine-readable companion for owner suites, validation routes, and check catalogs.
- Prompts, instructions, and specialist agents should reference the planning report or generated map instead of duplicating command blocks.
- `Repo Verify` owns the full repo-gate procedure and report format.

## Procedure

1. Start from `--planning-context` and use its selected surface, instruction files, first focused validation, finish gate, and blocking invariants.
2. Run the narrowest executable check that can falsify the current hypothesis.
3. Run focused validation immediately after the first substantive edit.
4. Before finishing, run the finish gate for the touched surface: focused behavior check, then touched-file lint and type checks when applicable.
5. Run broader verification only after the focused check passes, when the touched surface is shared infra, or if the user explicitly asks.
6. Record command and result in the shared `.git/sattlint-ai-coordination/current_work_lock.json` lock state when parallel work is active.

## Routing Map

See [validation map](./references/validation-map.md).

## Guardrails

- Do not manually merge routing from AGENTS, context-loading docs, validation-map prose, and generated maps when `--planning-context` can answer it directly.
- Do not start with full pytest when a targeted test file exists.
- Do not use VS Code test runner as first validation path in this repo.
- Do not treat `git diff` as sufficient when an executable narrow check exists.
- Do not finish a Python change with touched-file Ruff or Pyright errors still present.
- Do not default to full `pre-commit --all-files` or full `pytest` just to satisfy a normal task close-out; reserve that for explicit repo-wide verification.

## Finish Gate

- Python files touched: `& ".venv/Scripts/ruff.exe" check <touched_python_files>`
- Python files touched: `& ".venv/Scripts/pyright.exe" <touched_python_files>`
- Non-Python files touched: use owning executable check or workspace diagnostics for the edited file type.
- Shared devtools or audit wiring: add owner-suite validation or `sattlint-repo-audit --profile quick` after touched-file checks.
