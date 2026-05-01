---
name: validation-routing
description: 'Choose the first focused validation command for SattLint changes. Use for routing parser, analyzer, CLI, repo-audit, and workspace or LSP work to the correct narrow check before broader verification.'
argument-hint: 'Describe files or subsystem being changed'
---

# Validation Routing

Use this skill when you need to decide which validation to run first after a SattLint edit.

## Canonical Source

- `.github/skills/validation-routing/references/validation-map.md` owns canonical first-check command text for SattLint surfaces.
- `.github/skills/validation-routing/references/ai-work-map.json` is the machine-readable companion for owner suites, validation routes, and check catalogs.
- Prompts, instructions, and specialist agents should reference that map instead of duplicating command blocks.
- `Repo Verify` owns the full repo-gate procedure and report format.

## Procedure

1. Identify owning surface of changed code.
2. Choose narrowest executable check that can falsify current hypothesis.
3. Run focused validation immediately after the first substantive edit.
4. Before finishing, run the finish gate for touched surface: focused behavior check, then touched-file lint and type checks when applicable.
5. Run broader verification only after focused check passes, when touched surface is shared infra, or if user explicitly asks.
6. Record command and result in `.github/coordination/current-work.md` when parallel work is active.

## Routing Map

See [validation map](./references/validation-map.md).

## Guardrails

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
