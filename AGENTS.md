# AGENTS.md - Table of Contents

> Primary AI guide for SattLint conventions, workflows, and invariants.
> Direct user instructions, code, tests take precedence if stale.
> Update only when architecture boundaries, entry points, critical invariants, or AI operating contracts materially change.

## Quick Reference

**Purpose:** SattLint is a parser, analyzer, documentation, LSP, and repo-audit toolchain for SattLine.
**Audience:** AI-only repository. Design solutions, workflows, and supporting docs for agent execution rather than human-first operation.
**Communication:** Terse. Pattern: `[thing] [action] [reason]. [next step].`
**Machine entrypoint:** `sattlint-repo-audit --profile full --planning-context --output-dir artifacts/audit`.
**Health checks:** `python scripts/context_health.py --check`; `python scripts/context_health.py --check --section codegraph`; `python scripts/repo_health.py --check --audit-dir artifacts/audit`.
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

## CodeGraph

`.codegraph/` is initialized in this repo (347 files, 8926 nodes). Use the `codegraph-routing` skill (`.github/skills/codegraph-routing/SKILL.md`) for read-only exploration before editing.

**Main session** — lightweight tools only: `codegraph_search`, `codegraph_callers`/`codegraph_callees`, `codegraph_impact`, `codegraph_node`. For broader exploration, use `codegraph_explore` directly (one call) to gather source sections, then pass them inline to subagents.

**Subagents cannot use MCP tools.** Do not tell subagents to call codegraph tools — the main session must gather context and pass it in the prompt.

**Health** — run `python scripts/context_health.py --check --section codegraph` once before CodeGraph exploration. If it reports `healthy`, use CodeGraph-first routing. If it reports `degraded`, run one sync or rebuild and recheck once. If it reports `fallback_to_rg`, stop using CodeGraph MCP calls and fall back immediately.

## Critical Invariants (Auto-Loaded)

- Reuse existing seams. No broad rewrites or duplicate tooling.
- Start from the owning file or symbol. Run focused validation before widening.
- `sattlint syntax-check` stays strict. No silent fallback behavior.
- Use repo venv commands, not the VS Code test runner, for executable proof.
- Treat `vscode/sattline-vscode/` as the SattLine editor client for external workspaces, not as the default host for this repo.
- Bootstrap new slices with `python scripts/bootstrap_ai_slice.py ...` instead of hand-editing coordination state.
- For ambiguous `implement-plan`, `review-artifact`, or `chat-review` requests, bootstrap from `python scripts/bootstrap_ai_slice.py --from-request-kind ...` so the controlling artifact, requested files, first validation, and expected outcome are explicit before execution.
- Treat the shared active-claim lock as `.git/sattlint-ai-coordination/current_work_lock.json`; the deprecated markdown coordination ledger should not be used.
- One task contract and one handoff per scoped slice when work moves between executor, test, and reviewer.
- Use `@context-optimizer /audit` before growing AI control files.
- Keep AGENTS small, scoped instructions rich, and handoffs machine-readable.
- Ratchet is strictly monotonic and never loosens. No baseline inflation — ever. Fix code or tests to meet the existing ratchet; do not rebaseline upward to make a change pass.
- Before editing a failing owner file, classify it as a safe owner, debt-controlled owner, protected config, or shared infra. If the owner is debt-controlled or protected, prefer the nearest helper, policy, or extraction seam instead of patching the owner directly.
- If the first fix trips ratchet, approval, or finish-gate policy rather than behavior, stop and recut the slice around the controlling policy seam. Treat `artifacts/audit/` outputs as snapshots and refresh or mark them stale when newer focused validation contradicts them.
- When a claimed owner file is already oversized in `artifacts/analysis/file_debt_ratchet.json`, default to extraction into sibling modules or an explicit shrink/decomposition slice instead of appending more code to that owner file.
- Restart the language server after `src/sattlint_lsp/`, `src/sattlint/core/`, `src/sattlint/editor_api.py`, or `vscode/` edits.

## Workflow Rules

- Safe edit flow: route -> small edit -> focused check -> finish gate -> handoff.
- Preferred task size: one owner surface, one behavior goal, one clear validation command.
- Executor -> Test -> Reviewer uses `.ai/tasks/*.json` and `.ai/handoffs/*.json`.
- Worktree default: `python scripts/bootstrap_ai_slice.py --task-id <id> --stage executor --file <path> --validation "<command>"`.
- Chat-review starts from `<workspace-storage>/GitHub.copilot-chat/transcripts/*.jsonl`; use `debug-logs/` only as session metadata, not as the controlling content seam.
- Testing expectation: bug fix or feature change moves with focused tests in same change.
- Finish gate: focused proof plus touched-file Ruff and Pyright; widen to `--check-my-changes` for shared infra.
- Do not commit with `--no-verify` unless the user explicitly requests it. If pre-commit or other commit blockers fail, fix the blockers before committing instead of bypassing verification.
- CI expectation: `ci.yml` is integrated full-trust and nightly health; `lint.yml`, `typing.yml`, and `repo-audit.yml` remain owner workflows.
- Debugging flow: open `artifacts/audit/status.json` first, then `summary.json`, then owner artifacts.
- Security: redact secrets, PII, and machine-specific paths.

## Forbidden Patterns

- Broad rewrites without explicit justification.
- Lowering ratchets. Never loosen baselines, debt allowlists, file-line exceptions, or touch rules.
- Empty handoffs, empty final answers, or path-dump outputs.
- Expanding global instructions when scoped instructions or prompts fit.
- Skipping focused validation when an executable local check exists.

## Definition Of Done

- Docs updated when workflow or behavior changed.
- Focused validation passed. Ruff and Pyright clean on touched Python files.
- `python -m pre_commit run --all-files` or `sattlint-repo-audit --profile full --check-my-changes` run when the slice needs it.
- File claims released or updated. Handoff written if the slice moves to test or review.

## Last Updated

2026-05-15
