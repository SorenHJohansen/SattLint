---
name: validation-routing
description: 'Choose the first focused validation command for SattLint changes. Use for routing parser, analyzer, CLI, repo-audit, and workspace or LSP work to the correct narrow check before broader verification.'
argument-hint: 'Describe files or subsystem being changed'
---

# Validation Routing

Use this skill when you need to decide which validation to run first after a SattLint edit.

## Canonical Source

- `.github/skills/validation-routing/references/validation-map.md` owns canonical first-check command text for SattLint surfaces.
- Prompts, instructions, and specialist agents should reference that map instead of duplicating command blocks.
- `Repo Verify` owns the full repo-gate procedure and report format.

## Procedure

1. Identify owning surface of changed code.
2. Choose narrowest executable check that can falsify current hypothesis.
3. Run broader verification only after focused check passes or if user explicitly asks.
4. Record command and result in `.github/coordination/current-work.md` when parallel work is active.

## Routing Map

See [validation map](./references/validation-map.md).

## Guardrails

- Do not start with full pytest when a targeted test file exists.
- Do not use VS Code test runner as first validation path in this repo.
- Do not treat `git diff` as sufficient when an executable narrow check exists.