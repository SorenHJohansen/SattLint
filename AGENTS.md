# AGENTS.md

> Single AI control-plane entry for SattLint.
> Supporting docs are references, not parallel authorities.

## Quick Reference

**Purpose:** SattLint is a parser, analyzer, editor-facade, documentation, LSP, and repo-audit toolchain for SattLine.
**Default workflow:** one chat owns routing, editing, validation, and summary unless the user explicitly asks for something else.
**Global authority:** this file is the root AI guide; compatibility docs must not add competing workflow rules.
**Communication:** terse and concrete.
**Health checks:** `python scripts/context_health.py --check`; `python scripts/repo_health.py --check --audit-dir artifacts/audit`.

## Project system

`.slproj` is the central concept. A project file captures all analysis settings — targets, directories, mode, documentation, output/cache paths — in a single checked-in file. Paths in `.slproj` are relative to the file itself, making projects portable.

- `sattlint init` scaffolds a new `.slproj` in the current directory
- `sattlint --project PATH <command>` uses an explicit project file
- Auto-discovery walks up from CWD when no `--project` or `--config` is given
- Project settings are merged over `~/.config/sattlint/config.toml` defaults
- See `src/sattlint/project/` for the implementation: `types.py`, `io.py`, `models.py`

## Repo Map

- Start from the owning file, symbol, failing command, or failing test.
- Prefer `.slproj` project files over editing `~/.config/sattlint/config.toml` directly.
- For real-target debugging, check `~/.config/sattlint/config.toml` before assuming the repo contains the source file; follow `program_dir`, `ABB_lib_dir`, `icf_dir`, and `other_lib_dirs` to the actual external SattLine libraries.
- Treat SattLine source files discovered outside this repository root as read-only evidence; inspect them when needed, but do not edit them unless the user explicitly asks to work in that external repository.
- Read only the matching `.github/instructions/*.md` files for the touched surface.
- Use `docs/maintainers/repo-map.md` when owner routing is still unclear.
- Use `docs/public/architecture.md` for layering and runtime boundaries.
- Use `docs/maintainers/quality-gates.md` for wider validation commands and finish gates.

## Key Docs

- `docs/maintainers/repo-map.md`, `docs/public/architecture.md`, `docs/maintainers/quality-gates.md`
- `docs/design-docs/`, `.github/instructions/*.md`

## Critical Invariants

- Keep `AGENTS.md` as the only root AI authority.
- Prefer root-cause fixes over compatibility shims or duplicate abstractions.
- Start from the owning seam. Run focused executable validation before widening.
- Keep large files split at reasonable seams; prefer smaller focused modules over one giant file.
- Treat 100% focused coverage as the bar for the touched slice.
- Keep touched Python files Pyright strict-clean.
- `sattlint syntax-check` stays strict. No silent fallback behavior.
- Use repo venv commands or existing VS Code tasks for executable proof.
- Use markdown links for workspace file and line references.
- Treat `artifacts/audit/` outputs as snapshots; refresh them when validation changes the relevant evidence.
- Never use `python3 - << 'PY'` heredocs through the VS Code terminal tools.

## Workflow

- Go from `AGENTS.md` to the owner file or failing command immediately.
- Load `docs/maintainers/repo-map.md` or `docs/public/architecture.md` only when local routing is still unclear.
- Make the smallest grounded edit that tests the current hypothesis.
- Run the first focused validation immediately after the first substantive edit.
- Widen to Ruff, Pyright, pre-commit, or `--check-my-changes` only after the local check passes.

## Restricted Commands — Hard Prohibition, NO Workarounds

**A denied command is a hard prohibition, not a puzzle to solve.**

This repository allows ONLY the read-only git commands `git log`, `git diff`, `git show`, and `git branch -a`; all other `git` commands (`git`, `git *`, `git*`) are denied, plus `sudo`, `rm`, and `pacman`/`yay`. If any command is denied, the denial is the final answer — the action should NEVER be performed by the AI. The user will run the command themselves if it is needed.

You MUST NOT:

- Find an alternate way to run the same operation (no `python -c` wrappers, no `subprocess` calls, no shell redirects that emulate a blocked command)
- Use `git show HEAD:<path> > <path>`, `git archive`, `git diff | apply`, or any other technique as a substitute for a blocked `git checkout` / `git restore` / `git reset` / `git stash`
- Reconstruct or emulate git operations through any other tool
- Ask the user to loosen permissions, or try the same command "a different way"
- Invent creative "safe" variants of a denied command

Instead:

1. **STOP** the task immediately.
2. Give the user the exact command to run themselves in their terminal.
3. Let the user execute it and report back. Never continue the operation by other means.

Only `trash-put` is an allowed alternative — and only because it is explicitly listed as `allow` in the permission config for `rm` — and the four read-only git commands above. Anything not explicitly allowed is denied.

## Guardrails

- Do not broaden changes aimlessly.
- Do not modify SattLine source files outside this repository unless explicitly requested.
- Do not preserve temporary compatibility seams unless the phase plan still requires them.
- Do not keep parallel AI workflow docs with independent rules.
- Do not skip focused validation when a narrower executable check exists.
- Never use `git commit --no-verify` or `git push --no-verify`.

## Bulk Edit Prohibition

- Do NOT use `sed`, `find ... -exec`, Python one-liners, or Task agents to make bulk code changes across multiple files.
- Do NOT write scripts that modify source or test code. Ever.
- Every code change must be made individually with the Edit tool, with verification after each edit.
- If a change requires touching more than 5 files, stop and propose a plan first.

Last Updated: 2026-08-22
