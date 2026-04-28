# AGENTS.md - Table of Contents

> Primary AI guide for SattLint conventions, workflows, and invariants.
> Direct user instructions, code, tests take precedence if stale.
> Update only when architecture boundaries, entry points, or critical invariants materially change.

## Quick Reference

**Communication:** Terse. Drop articles/filler. Pattern: `[thing] [action] [reason]. [next step].`
**Boundaries:** Code/commits/PRs written normal. No terse mode for security warnings or irreversible actions.

## Repo Map

| Path | Purpose |
|------|---------|
| `src/sattline_parser/` | Parser core: grammar, transformer, AST models |
| `src/sattlint/` | CLI, config, analyzers, reporting, doc generation |
| `src/sattlint/core/` | Shared semantic/document helpers for editor code |
| `src/sattlint_lsp/` | LSP server, workspace store, incremental parser |
| `vscode/sattline-vscode/` | No-build VS Code client |
| `tests/` | Fixtures and regression coverage |
| `artifacts/` | Machine-readable analysis/audit outputs |

## Key Docs (Progressive Disclosure)

| Doc | When to Read |
|-----|-------------|
| `ARCHITECTURE.md` | Architecture overview, domains, layering |
| `docs/design-docs/core-beliefs.md` | Golden principles, agent legibility rules |
| `docs/design-docs/index.md` | Design docs index |
| `docs/exec-plans/index.md` | Execution plans template and directory structure |
| `docs/exec-plans/tech-debt-tracker.md` | Known technical debt |
| `docs/quality-score.md` | Domain quality grades |
| `.github/instructions/*.md` | Subsystem-scoped instructions |
| `docs/references/ai-agent-reference.md` | SattLine examples, AST details, task snippets |

## Critical Invariants (Auto-Loaded)

See `.github/instructions/sattline-invariants.instructions.md` for `src/**` and `tests/**` edits.

- **Communication style:** Respond terse. Drop articles (a/an/the), filler (just/really/basically), pleasantries, hedging. Fragments OK. Short synonyms. Technical terms exact. Code unchanged.
- Pattern: [thing] [action] [reason]. [next step].
- Not: "Sure! I'd be happy to help you with that."
- Yes: "Bug in auth middleware. Fix:"
- Auto-clarity: Drop terse mode for security warnings, irreversible actions, user confused. Resume after.
- Boundaries: Code, commits, PRs written normal.
- Inspect repo structure, current implementation, tests, and existing tooling before changing behavior.
- Reuse existing patterns, validators, analyzers, pipeline hooks, and tests before introducing new abstractions or new dependencies.
- Prefer repo-local commands over IDE abstractions. In this repo, the VS Code Testing UI or generic test runner is unreliable and can use the wrong interpreter or report zero collected tests.
- Match the first validation step to the surface you changed: use `sattlint syntax-check` for parser or strict-validation work, targeted `pytest` files for Python or CLI behavior, and quick pipeline or audit profiles for devtools and artifact work.
- Start narrow, then widen. Prefer the smallest real fixture, target file, or focused test module that exercises the change before running broader suites.
- When creating a new SattLine program or library scaffold, always create the `.g`, `.l`, and `.s` triplet: copy from `NNEStart.s` and `NNEStart.l`, create an empty `.g`, and do not create `.x`, `.y`, or `.z` scaffold files. Keep as many copied modules as practical, add a named unit wrapper module, and have the program file invoke that wrapper. **After syntax-check passes, always verify scaffold semantic completeness: main library moduletype must have MODULEPARAMETERS + LOCALVARIABLES + SUBMODULES invoking support-lib types; support library must define all referenced types. Do not treat "syntax-check OK" as "complete"—verify module substance exists.**
- Propose a concise plan before broad or multi-file changes.
- Ask for clarification when intended behavior, user-facing semantics, or safety requirements are unclear.
- Prefer incremental, reviewable changes over large rewrites.
- Keep user-facing behavior explicit; avoid hidden side effects or silent mode switches.
- When changing CLI menus or prompts, update `tests/test_app.py` and related interaction coverage in the same change.
- For concurrent agent or chat work, check `.github/coordination/current-work.md` before editing, claim touched files, and release claim when done.
- Respect the claimed-file hook guard under `.github/hooks/`; active claims warn, `ready-for-merge` claims ask for confirmation, and `blocked` claims deny edits until the ledger changes.
- Prefer subsystem-scoped instructions under `.github/instructions/` over growing `AGENTS.md`; keep global guidance stable and push file-specific detail into targeted instruction files.
- When adding AI customizations, optimize for lower context waste: concise frontmatter, keyword-rich descriptions, narrow `applyTo` globs, and machine-readable or scriptable behavior when practical.

## Workflow Rules

- Inspect repo structure, current code, tests before changes
- Reuse existing patterns/analyzers/tests before new abstractions
- Validation: `sattlint syntax-check` (parser), targeted `pytest` (Python/CLI), pipeline/audit (devtools)
- No VS Code test runner; use repo venv directly
- Claim files in `.github/coordination/current-work.md` for parallel work
- Update `tests/test_app.py` when changing CLI menus
- Prefer incremental, reviewable changes over large rewrites
- Propose plan before broad or multi-file changes
- When adding AI customizations, optimize for lower context waste

## Change Boundaries

**Allowed:** analyzers, validators, tests, docs, helper scripts, CI wiring, small refactors
**Avoid:** broad rewrites, duplicate tooling, silent behavior changes, weakening validation

## Security

- Redact secrets/PII in outputs (report by type/path, not raw value)
- Watch for `SQHJ`, local paths, machine-specific behavior
- Prefer repo-relative paths

---

## Security And Privacy

- Never print or paste full secrets, tokens, passwords, connection strings, certificates, or private keys.
- Redact sensitive values in summaries, diffs, findings, logs, and examples.
- Report PII by type or category and file path, not by raw value.
- Call out issues that may require git-history cleanup separately from normal code fixes.
- Watch for hardcoded local paths, usernames such as `SQHJ`, internal hostnames, local domains, drive-letter assumptions, and machine-specific behavior.
- Treat OneDrive-backed, user-profile, temp, and local workspace paths as potentially sensitive in reports.
- Prefer repo-relative or config-driven paths over developer-machine paths.

---

## Validation And Strictness

- `sattlint syntax-check` is strict. It should fail clearly on invalid input and should not gain new silent fallback behavior.
- Workspace, editor, and LSP flows may degrade only in already-established ways, such as unavailable proprietary dependencies, cached workspace bundles, local source snapshots, or syntax-only dirty-buffer analysis.
- Do not add new silent fallback behavior outside those established workspace or editor flows.
- Preserve the distinction between single-file strict validation and dependency-aware workspace loading.
- Prefer focused validation first, then broader repo checks when warranted.
- Do not use the VS Code test runner in this repo; run pytest through the repo venv directly.
- For first-check command routing by surface, see `.github/skills/validation-routing/references/validation-map.md`.

---

## Unit Scaffolding Semantic Validation (Critical)

When creating or repairing unit scaffolds (main library + support library + program):

**Syntax-check passing does NOT indicate completion.** Syntax validation only confirms grammar; it does not verify module substance.

**Semantic validation checks (mandatory after syntax-check passes):**

1. **Main library unit moduletype must contain:**
   - At least one MODULEPARAMETER declaration (e.g., `Name`, `TankName`, process parameters)
   - At least one LOCALVARIABLE for operational state (beyond just a tag string)
   - At least one SUBMODULE invoking equipment/operation types from support library
   - GraphObjects with descriptive TextObject labels
   - **Bare module with only `Tag: string := "299A"` is NOT functional.**

2. **Support library must contain:**
   - At least one equipment or operation MODULEDEFINITION actually used by main unit
   - Each MODULETYPE must have relevant MODULEPARAMETERS and LOCALVARIABLES
   - Every type name referenced in main lib SUBMODULES must be defined here
   - **Empty TYPEDEFINITIONS section means support lib is non-functional.**

3. **Cross-library type reference verification:**
   - Grep main library for SUBMODULE invocation type names (e.g., `SprayDryerInlet`)
   - Verify each type exists as a MODULEDEFINITION in support library TYPEDEFINITIONS
   - Missing types = unresolvable moduletype at runtime

**Failure response:** If semantic checks fail, **do not mark work complete.** Report which checks failed, what's missing, and fix the module content before closing.

---

## Repo-Audit And Public-Readiness

See `.github/instructions/repo-audit.instructions.md` (auto-loaded for `src/sattlint/devtools/**` edits).

- Prefer integrating with existing tooling before adding new audit frameworks.
- Keep audit output actionable and machine-readable.
- Canonical repo audit command: `sattlint-repo-audit --profile full --output-dir artifacts/audit`.
- For fast iteration, prefer `--profile quick` before a final full pass.
- Open `artifacts/audit/status.json` first; it is the compact entry report.

---

## Reporting Expectations

- For non-trivial work, report the summary of changes.
- For non-trivial work, report the exact files changed.
- For non-trivial work, report the commands run.
- Keep terminal output easy to scan: avoid long single-line diagnostics when practical; prefer wrapped or structured multiline blocks.
- Group findings by severity when relevant.
- Distinguish confirmed issues from suspected or heuristic findings.
- Report assumptions and limitations.
- Report recommended follow-up work.
- Do not expose raw secrets or raw PII in reports.
- When parallel work is active, report claimed files, validation status, and any handoff notes back into `.github/coordination/current-work.md`.
- Use the merge or handoff prompt before final repo verification when multiple workstreams are converging.

---

## Definition Of Done

- Tests added/updated
- Validation commands run
- Docs updated on material change
- LSP restarted if `src/sattlint_lsp/`, `src/sattlint/core/`, `editor_api.py`, or `vscode/` touched

*Last updated: 2026-04-28*
