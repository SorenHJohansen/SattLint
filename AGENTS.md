# AGENTS.md

> Single AI control-plane entry for SattLint.
> Supporting docs are references, not parallel authorities.

## ⚠️ CODEBASE EXPLORATION: SEMBLE ONLY — ABSOLUTE REQUIREMENT

**Semble is the ONLY acceptable tool for exploring the codebase. It is not a preference — it is a hard requirement.**

You MUST use Semble (`semble_search` / `semble_find_related`) for ALL codebase exploration and source discovery. This is the FIRST tool you reach for, always.

You MUST NOT use `rg`, `ripgrep`, `grep`, `read`, `glob`, `find`, `ls`, `cat`, or ANY similar search/read tool to explore the codebase. These are forbidden for discovery — do not reach for them, do not fall back to them, do not "just take a quick look."

- **First attempt is ALWAYS Semble.** If a Semble search is possible for the query, use it. No exceptions.
- **Never fall back to ripgrep/grep/read/glob** because Semble "seems slower" or you are "already holding a file."
- **Navigate directly to Semble results** — do not re-search the same content with another tool.
- **Use `find_related` to discover similar code** elsewhere in the same repo instead of grepping for the pattern.
- If a Semble search returns nothing useful, refine the query or retry — only then consider a documented exception.

This rule exists because Semble is the indexed, accurate, and sanctioned way to explore this repository. The forbidden tools bypass that index and produce stale or incomplete results.

## Quick Reference

**Purpose:** SattLint is a parser, analyzer, and validation toolchain for SattLine, with a CLI and a Textual terminal UI.
**Default workflow:** one chat owns routing, editing, validation, and summary unless the user explicitly asks for something else.
**Global authority:** this file is the root AI guide; compatibility docs must not add competing workflow rules.
**Communication:** terse and concrete.

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

- Keep `AGENTS.md` as the only root AI authority (core-beliefs #2).
- Start from the owning seam. Run focused executable validation before widening.
- `sattlint syntax-check` stays strict (core-beliefs #4/#10). No silent fallback behavior.
- Follow core-beliefs typing discipline (#14, #26, #27, #29): objects over dicts/tuples, no avoidable `Any`, Pyright strict-clean, typed dispatch over reflection.
- Right solution, not the safe solution (#28); root-cause fixes over compatibility shims (#25).
- Keep files at reasonable seams; prefer smaller focused modules over one giant file (core-beliefs #16/#17).
- Treat 100% focused coverage as the bar for the touched slice (core-beliefs #15).
- Use repo venv commands or existing VS Code tasks for executable proof.
- Use markdown links for workspace file and line references.
- Never use `python3 - << 'PY'` heredocs through the VS Code terminal tools.

## Workflow

- Go from `AGENTS.md` to the owner file or failing command immediately.
- Load `docs/maintainers/repo-map.md` or `docs/public/architecture.md` only when local routing is still unclear.
- Make the smallest grounded edit that tests the current hypothesis.
- Run the first focused validation immediately after the first substantive edit.
- Widen to Ruff, Pyright, `ruff format --check`, or pre-commit only after the local check passes.

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
- Do NOT invoke `rg`, `grep`, `read`, `glob`, `find`, `ls`, `cat`, or similar tools for codebase exploration — Semble is the only sanctioned tool (see top of file).
- Never use `git commit --no-verify` or `git push --no-verify`.

## Bulk Edit Prohibition

- Do NOT use `sed`, `find ... -exec`, Python one-liners, or Task agents to make bulk code changes across multiple files.
- Do NOT write scripts that modify source or test code. Ever.
- Every code change must be made individually with the Edit tool, with verification after each edit.
- For broad multi-file changes, state the plan and confirm scope before editing.

Last Updated: 2026-09-08
