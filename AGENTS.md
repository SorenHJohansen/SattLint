# AGENTS.md

> Single AI control-plane entry for SattLint.
> Supporting docs are references, not parallel authorities.

## Public Repository

- This repository is public. Describe behavior, not origin.
- SattLint is unofficial. Use "SattLine" only to name the file format; do not imply affiliation with ABB.

## Codebase Exploration

- Use Semble when it makes sense: discovery, symbol lookup, and similar-code search.
- For targeted reads, exact files, or when Semble misses, use `read`, `grep`, and `glob`.
- Prefer the cheapest reliable tool; do not force Semble for a one-line lookup.

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
- Use `AGENTS_REFERENCE.md` when owner routing, validation routes, or gate details are unclear.
- Use `ARCHITECTURE.md` for layering and runtime boundaries.

## Key Docs

- `AGENTS_REFERENCE.md` (repo map, quality gates, validation map, core beliefs), `ARCHITECTURE.md`
- `.github/instructions/*.md`

## Critical Invariants

- Keep `AGENTS.md` as the only root AI authority (AGENTS_REFERENCE.md core-beliefs #2).
- Start from the owning seam. Run focused executable validation before widening.
- `sattlint syntax-check` stays strict (core-beliefs #4/#10). No silent fallback behavior.
- Follow core-beliefs typing discipline (#14, #26, #27, #29): objects over dicts/tuples, no avoidable `Any`, Pyright strict-clean, typed dispatch over reflection.
- Right solution, not the safe solution (#28); root-cause fixes over compatibility shims (#25).
- Keep files at reasonable seams; prefer smaller focused modules over one giant file (core-beliefs #16/#17).
- Treat 100% focused coverage as the bar for the touched slice (core-beliefs #15).
- Use repo venv commands or existing VS Code tasks for executable proof.
- Use markdown links for workspace file and line references.

## Workflow

- Go from `AGENTS.md` to the owner file or failing command immediately.
- Load `AGENTS_REFERENCE.md` or `ARCHITECTURE.md` only when local routing is still unclear.
- Make the smallest grounded edit that tests the current hypothesis.
- Run the first focused validation immediately after the first substantive edit.
- Widen to Ruff, Pyright, `ruff format --check`, or pre-commit only after the local check passes.

## Guardrails

- Do not broaden changes aimlessly.
- Do not modify SattLine source files outside this repository unless explicitly requested.
- Do not preserve temporary compatibility seams unless the phase plan still requires them.
- Do not keep parallel AI workflow docs with independent rules.
- Do not skip focused validation when a narrower executable check exists.
- Use Semble when it makes sense; targeted reads and exact lookups may use `read`, `grep`, `glob`, or `find`.

## Internal Identifiers

- Never include internal identifiers in anything a human reads: chat replies, code comments, docstrings, commit messages, pull request descriptions, GitHub comments, documentation, fixtures, test names, and user-facing output.
- Internal identifiers include private symbol names, internal rule IDs and finding kinds, internal enum values, ticket or issue numbers, build numbers, code addresses, and non-public customer, library, or project names.
- Describe behavior in plain language and use the documented user-facing label. Keep machine IDs inside machine-readable JSON when a consumer needs them.
- Public names are fine: repository file paths, public API names, and documented labels.

Last Updated: 2026-10-31
