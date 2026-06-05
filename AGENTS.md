# AGENTS.md - Table of Contents

> Primary AI guide for SattLint conventions, workflows, and invariants.
> Keep this file short; move subsystem detail to scoped instructions under `.github/instructions/`.

## Quick Reference

**Purpose:** SattLint is a parser, analyzer, editor-facade, documentation, LSP, and repo-audit toolchain for SattLine.
**Audience:** AI-only repository. Design solutions, workflows, and supporting docs for agent execution rather than human-first operation.
**Communication:** Terse. Pattern: `[thing] [action] [reason]. [next step].`
**Machine entrypoint:** `sattlint-repo-audit --profile full --planning-context --output-dir artifacts/audit`.
**Health checks:** `python scripts/context_health.py --check`; `python scripts/repo_health.py --check --audit-dir artifacts/audit`.
**Naming:** task ids, worktree folders, and handoff files use lower-kebab-case.

## Repo Map

- Start routing from `docs/repo-map.md` when you need the owning surface for CLI, editor facade, LSP, devtools, or the preview VS Code client.
- Route analyzer package structure, registry naming, and helper-boundary work through `.github/instructions/analyzer-architecture.instructions.md`.

## Key Docs

- `docs/context-loading-order.md`, `docs/repo-map.md`, `docs/architecture.md`, `docs/quality-gates.md`, `docs/ai-workflows.md`, `docs/lessons-learned/known-failure-patterns.md`, `.github/instructions/*.md`, `.ai/tasks/task-contract.schema.json`, `.ai/handoffs/handoff.schema.json`

## Critical Invariants (Auto-Loaded)

- Prefer the architecture that removes debt at the root. Reuse existing seams when they support the right design; otherwise refactor or replace them deliberately instead of layering more compatibility code or duplicate tooling.
- This repo is pre-release. Optimize for correctness, coherence, and maintainability over preserving provisional APIs, file boundaries, or legacy behavior.
- Start from the owning file or symbol. Run focused validation before widening.
- Use Semble MCP for code exploration; keep `rg` for exhaustive literal matches and exact-string confirmation.
- `sattlint syntax-check` stays strict. No silent fallback behavior.
- Use repo venv commands, not the VS Code test runner, for executable proof.
- Prefer existing VS Code tasks in `.vscode/tasks.json` for common repo workflows before composing ad hoc shell commands.
- Treat `vscode/sattline-vscode/` as the editor client for external workspaces, not the default host for this repo.
- Bootstrap slices with `python scripts/bootstrap_ai_slice.py ...`; use `--from-request-kind` for ambiguous `implement-plan`, `review-artifact`, or `chat-review` requests.
- Use `.git/sattlint-ai-coordination/current_work_lock.json` as the active-claim lock.
- One task contract and one handoff per scoped slice when work moves between executor, test, and reviewer.
- Use `@context-optimizer /audit` before growing AI control files.
- Keep AGENTS small, scoped instructions rich, and handoffs machine-readable.
- Ratchets are monotonic. Never loosen a baseline, debt allowlist, file exception, or touch rule.
- Prefer simplifying the owning design, extracting clean modules, and deleting obsolete paths when a touched owner is already open, as long as focused validation stays tractable.
- Treat `artifacts/audit/` outputs as snapshots; refresh or mark them stale when focused validation contradicts them.
- See `.github/instructions/repo-map.instructions.md`, `.github/instructions/ratchet-policy.instructions.md`, and `.github/instructions/workspace-lsp.instructions.md` for owner routing, ratchet policy, and LSP restart details.

## Workflow

- Durable edit flow: route -> choose the right design -> implement the owning refactor -> focused check -> finish gate -> handoff.
- Preferred task size: one coherent owner surface and one behavior goal; if the right fix spans adjacent owners, keep the refactor whole instead of splitting it into debt-preserving slices.
- Executor -> Test -> Reviewer uses `.ai/tasks/*.json` and `.ai/handoffs/*.json`.
- GitHub Actions split: `ci.yml` owns the integrated PR, `main`, manual, and nightly gate; `lint.yml`, `typing.yml`, and `repo-audit.yml` stay owner workflows; `publish.yml` supports manual release rehearsal, only publishes on real `v*` tags, and routes the final publish step through the protected `pypi-release` environment.
- Chat-review starts from `<workspace-storage>/GitHub.copilot-chat/transcripts/*.jsonl`; use `debug-logs/` only as session metadata, not as the controlling content seam.
- Never use `python3 - << 'PY'` heredocs through the VS Code terminal tools; prefer a named task, a temp script file, or a one-line command.
- Testing expectation: bug fix or feature change moves with focused tests in same change.
- Finish gate: focused proof plus touched-file Ruff and Pyright; widen to `--check-my-changes` for shared infra.
- Open `artifacts/audit/status.json` first, then `summary.json`, then owner artifacts when debugging audit output.
- See `docs/ai-workflows.md` and `docs/quality-gates.md` for branch, worktree, handoff, and pipeline details.
- Security: redact secrets, PII, and machine-specific paths.

## Guardrails

- Do not broaden changes aimlessly; broaden on purpose when the broader refactor is the cleaner long-term solution and can be validated.
- Do not preserve temporary compatibility shims, fallback paths, or duplicate abstractions unless the user explicitly asks for transitional behavior.
- No empty handoffs, empty final answers, or path-dump outputs.
- Do not expand global instructions when scoped instructions or prompts fit.
- Do not skip focused validation when an executable local check exists.
- When validation, hooks, or audits fail, fix the underlying problems when feasible instead of bypassing them to force completion.
- Never use `git commit --no-verify` or `git push --no-verify`; surface hook failures and resolve them or stop for direction.

## Last Updated

2026-06-05
