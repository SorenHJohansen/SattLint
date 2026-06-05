# AGENTS.md

> Single AI control-plane entry for SattLint.
> Supporting docs are references, not parallel authorities.

## Quick Reference

**Purpose:** SattLint is a parser, analyzer, editor-facade, documentation, LSP, and repo-audit toolchain for SattLine.
**Default workflow:** one chat owns routing, editing, validation, and summary unless the user explicitly asks for something else.
**Global authority:** this file is the root AI guide; compatibility docs must not add competing workflow rules.
**Communication:** terse and concrete.
**Health checks:** `python scripts/context_health.py --check`; `python scripts/repo_health.py --check --audit-dir artifacts/audit`.

## Repo Map

- Start from the owning file, symbol, failing command, or failing test.
- Read only the matching `.github/instructions/*.md` files for the touched surface.
- Use `docs/maintainers/repo-map.md` when owner routing is still unclear.
- Use `docs/public/architecture.md` for layering and runtime boundaries.
- Use `docs/maintainers/quality-gates.md` for wider validation commands and finish gates.

## Key Docs

- `docs/maintainers/repo-map.md`
- `docs/public/architecture.md`
- `docs/maintainers/quality-gates.md`
- `docs/design-docs/`
- `docs/lessons-learned/known-failure-patterns.md`
- `.github/instructions/*.md`

## Critical Invariants

- Keep `AGENTS.md` as the only root AI authority.
- Prefer root-cause fixes over compatibility shims or duplicate abstractions.
- Start from the owning seam. Run focused executable validation before widening.
- Treat 500 lines as the hard cap for checked-in files.
- Treat 100% focused coverage as the bar for the touched slice.
- Keep touched Python files Pyright strict-clean.
- `sattlint syntax-check` stays strict. No silent fallback behavior.
- Use repo venv commands or existing VS Code tasks for executable proof.
- Use markdown links for workspace file and line references.
- Ratchets are monotonic. Never loosen a baseline, debt allowlist, file exception, or touch rule.
- Treat `artifacts/audit/` outputs as snapshots; refresh them when validation changes the relevant evidence.
- Never use `python3 - << 'PY'` heredocs through the VS Code terminal tools.

## Workflow

- Go from `AGENTS.md` to the owner file or failing command immediately.
- Load `docs/maintainers/repo-map.md` or `docs/public/architecture.md` only when local routing is still unclear.
- Make the smallest grounded edit that tests the current hypothesis.
- Run the first focused validation immediately after the first substantive edit.
- Widen to Ruff, Pyright, pre-commit, or `--check-my-changes` only after the local check passes.
- Use `docs/lessons-learned/known-failure-patterns.md` only after a dead end or repeated validation failure.

## Guardrails

- Do not broaden changes aimlessly.
- Do not preserve temporary compatibility seams unless the phase plan still requires them.
- Do not keep parallel AI workflow docs with independent rules.
- Do not skip focused validation when a narrower executable check exists.
- Never use `git commit --no-verify` or `git push --no-verify`.

## Last Updated

2026-06-05
