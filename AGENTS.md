# AGENTS.md - Table of Contents

> Primary AI guide for SattLint conventions, workflows, and invariants.
> Direct user instructions, code, tests take precedence if stale.
> Update only when architecture boundaries, entry points, critical invariants, or AI operating contracts materially change.

## Quick Reference

**Purpose:** SattLint is a parser, analyzer, documentation, LSP, and repo-audit toolchain for SattLine.
**Audience:** AI-only repository. Design solutions, workflows, and supporting docs for agent execution rather than human-first operation.
**Communication:** Terse. Pattern: `[thing] [action] [reason]. [next step].`
**Machine entrypoint:** `sattlint-repo-audit --profile full --planning-context --output-dir artifacts/audit`.
**Health checks:** `python scripts/context_health.py --check`; `python scripts/repo_health.py --check --audit-dir artifacts/audit`.
**Branch model:** `main`, `develop/integration`, `ai/task-<id>`, `test/task-<id>`, `review/task-<id>`.
**Naming:** task ids, worktree folders, and handoff files use lower-kebab-case.

**Key Docs:**

- `docs/context-loading-order.md` - Human context loading order.
- `docs/repo-map.md` - Fast file and validation routing.
- `docs/architecture.md` - Short architecture summary.
- `docs/quality-gates.md` - AI edit, pre-commit, pre-push, CI, nightly gates.
- `docs/ai-workflows.md` - Executor, test, reviewer, branch, worktree, handoff flow.
- `docs/lessons-learned/known-failure-patterns.md` - Consult selectively by smell.
- `.github/instructions/*.md` - Subsystem-scoped instructions.
- `.ai/tasks/task-contract.schema.json` - Task contract schema.
- `.ai/handoffs/handoff.schema.json` - Handoff schema.

## Repo Map

See `.github/instructions/repo-map.instructions.md` for the scoped owner-surface map.

## Critical Invariants (Auto-Loaded)

- Reuse existing seams. No broad rewrites or duplicate tooling.
- Start from the owning file or symbol. Run focused validation before widening.
- `sattlint syntax-check` stays strict. No silent fallback behavior.
- Use repo venv commands, not the VS Code test runner, for executable proof.
- Bootstrap new slices with `python scripts/bootstrap_ai_slice.py ...` instead of hand-editing coordination state.
- Treat the shared active-claim lock as `.git/sattlint-ai-coordination/current_work_lock.json`; the deprecated markdown coordination ledger should not be used.
- One task contract and one handoff per scoped slice when work moves between executor, test, and reviewer.
- Use `@context-optimizer /audit` before growing AI control files.
- Keep AGENTS small, scoped instructions rich, and handoffs machine-readable.
- AI must fix code or tests before any ratchet rebaseline.
- When a claimed owner file is already oversized in `artifacts/analysis/file_debt_ratchet.json`, default to extraction into sibling modules or an explicit shrink/decomposition slice instead of appending more code to that owner file.
- Restart the language server after `src/sattlint_lsp/`, `src/sattlint/core/`, `src/sattlint/editor_api.py`, or `vscode/` edits.

## Workflow Rules

- Safe edit flow: route -> small edit -> focused check -> finish gate -> handoff.
- Preferred task size: one owner surface, one behavior goal, one clear validation command.
- Executor -> Test -> Reviewer uses `.ai/tasks/*.json` and `.ai/handoffs/*.json`.
- Worktree default: `python scripts/bootstrap_ai_slice.py --task-id <id> --stage executor --file <path> --validation "<command>"`.
- Testing expectation: bug fix or feature change moves with focused tests in same change.
- Finish gate: focused proof plus touched-file Ruff and Pyright; widen to `--check-my-changes` for shared infra.
- CI expectation: `ci.yml` is integrated full-trust and nightly health; `lint.yml`, `typing.yml`, and `repo-audit.yml` remain owner workflows.
- Debugging flow: open `artifacts/audit/status.json` first, then `summary.json`, then owner artifacts.
- Security: redact secrets, PII, and machine-specific paths.

## Forbidden Patterns

- Broad rewrites without explicit justification.
- Lowering ratchets instead of fixing root cause.
- Empty handoffs, empty final answers, or path-dump outputs.
- Expanding global instructions when scoped instructions or prompts fit.
- Skipping focused validation when an executable local check exists.

## Definition Of Done

- Docs updated when workflow or behavior changed.
- Focused validation passed. Ruff and Pyright clean on touched Python files.
- `python -m pre_commit run --all-files` or `sattlint-repo-audit --profile full --check-my-changes` run when the slice needs it.
- File claims released or updated. Handoff written if the slice moves to test or review.

## Last Updated

2026-05-04
