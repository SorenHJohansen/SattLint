# AGENTS.md - Table of Contents

> Primary AI guide for SattLint conventions, workflows, and invariants.
> Direct user instructions, code, tests take precedence if stale.
> Update only when architecture boundaries, entry points, or critical invariants materially change.

## Quick Reference

**Communication:** Terse. Drop articles/filler. Pattern: `[thing] [action] [reason]. [next step].`
**Boundaries:** Code/commits/PRs written normal. No terse mode for security warnings or irreversible actions.

**Key Docs:**

- `docs/context-loading-order.md` - Load context in priority order, stop when sufficient.
- `docs/lessons-learned/known-failure-patterns.md` - Past root causes, anti-patterns, migration lessons.
- `docs/design-docs/core-beliefs.md` - Golden principles, agent legibility rules.
- `.github/instructions/*.md` - Subsystem-scoped instructions.

## Repo Map

| Path | Purpose |
| ------ | --------- |
| `src/sattline_parser/` | Parser core: grammar, transformer, AST models |
| `src/sattlint/` | CLI, config, analyzers, reporting, doc generation |
| `src/sattlint/core/` | Shared semantic/document helpers for editor code |
| `src/sattlint_lsp/` | LSP server, workspace store, incremental parser |
| `vscode/sattline-vscode/` | No-build VS Code client |
| `tests/` | Fixtures and regression coverage |
| `artifacts/` | Machine-readable analysis/audit outputs |

## Critical Invariants (Auto-Loaded)

See `.github/instructions/sattline-invariants.instructions.md` for `src/**` and `tests/**` edits.

- **Communication style:** Terse. Drop articles/filler. Fragments OK. Technical terms exact.
- Inspect repo structure, current code, tests before changes. Reuse existing patterns.
- Validation: `sattlint syntax-check` (parser), targeted `pytest` (Python/CLI), pipeline/audit (devtools).
- No VS Code test runner; use repo venv directly.
- Match first validation to surface changed. Start narrow, then widen.
- Claim files in `.github/coordination/current-work.md` for parallel work.
- When changing CLI menus, update `tests/test_app.py` in same change.

## Workflow Rules

- Root cause before remedy: analyze bug class, prefer shared fix over local patch.
- Prefer incremental, reviewable changes over large rewrites. Propose plan before broad changes.
- When adding AI customizations, optimize for lower context waste.
- AI must fix code or tests before any ratchet rebaseline. Do not loosen structural budgets, lower coverage ratchets, or lower `--cov-fail-under` as a substitute for a real fix. Only change those surfaces after explicit user approval.
- When an ExecPlan checklist is fully complete, move it from `docs/exec-plans/active/` to `docs/exec-plans/completed/` in the same change and update affected indexes or trackers.

## Change Boundaries

**Allowed:** analyzers, validators, tests, docs, helper scripts, CI wiring, small refactors.
**Avoid:** broad rewrites, duplicate tooling, silent behavior changes, weakening validation.

## Security

- Redact secrets/PII in outputs (report by type/path, not raw value).
- Watch for `SQHJ`, local paths, machine-specific behavior. Prefer repo-relative paths.
- Never print/paste full secrets, tokens, keys. Treat OneDrive/user-profile paths as sensitive.

## Validation And Strictness

- `sattlint syntax-check` is strict. No new silent fallback behavior.
- Workspace/LSP may degrade only in established ways (unavailable deps, dirty buffers).
- Preserve distinction between single-file strict validation and dependency-aware workspace loading.
- Before finishing a code or config task, run an efficient finish gate sized to touched surface.
- Minimum finish gate for Python edits: one focused executable behavior check, `ruff check` clean on touched Python files, and `pyright` clean on touched Python files.
- Widen only when touched surface is shared infra, devtools, or cross-subsystem code; prefer owner-suite or quick-audit validation over full repo gates.
- Use full `Repo Verify` gate only when user asks for repo-wide verification or when task is commit, push, merge, or pre-release readiness.
- Do not report task complete or checks green when touched-file Ruff or Pyright errors remain, or when focused executable validation for changed behavior was skipped.

## Repo-Audit And Public-Readiness

See `.github/instructions/repo-audit.instructions.md` (auto-loaded for `src/sattlint/devtools/**` edits).

- Canonical command: `sattlint-repo-audit --profile full --output-dir artifacts/audit`.
- For fast iteration, prefer `--profile quick`. Open `artifacts/audit/status.json` first.

## Reporting Expectations

- Report: summary of changes, exact files changed, commands run.
- Root cause before remedy: analyze bug class, prefer shared fix over local patch.
- Group findings by severity. Distinguish confirmed vs suspected. Report assumptions/limitations.
- When parallel work active, report claimed files/status to `.github/coordination/current-work.md`.

## Definition Of Done

- Tests added/updated. Validation commands run. Docs updated on material change.
- Finish gate passed for touched surface: focused behavior check plus touched-file lint and type checks when applicable.
- LSP restarted if `src/sattlint_lsp/`, `src/sattlint/core/`, `editor_api.py`, or `vscode/` touched.

## Last Updated

2026-05-01
