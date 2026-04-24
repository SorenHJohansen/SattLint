# AGENTS.md - AI Working Guide for SattLint

> This file is the primary AI working guide for stable SattLint repo conventions, workflows, safety rules, and critical invariants.
> Direct user instructions, code, tests, and clearly newer repo documentation take precedence if this file is stale.
> Update this file when architecture boundaries, entry points, workflows, or critical invariants materially change.

---

## Purpose

- Keep durable agent-facing guidance here.
- Keep this file concise enough to be used as an instruction file rather than a handbook.
- Move long examples, detailed architecture notes, and extended reference material into repo docs.
- Use `docs/ai-agent-reference.md` for deeper SattLine examples, AST details, file maps, and common task snippets.

---

## Repo At A Glance

- `src/sattline_parser/` contains the parser core: grammar, transformer, AST models, and parser-side utilities.
- `src/sattlint/` contains the CLI, config, analyzers, reporting, doc generation, and compatibility wrappers.
- `src/sattlint/core/` contains the shared semantic and document helpers used by editor-facing code.
- `src/sattlint_lsp/` contains the incremental parser backend, workspace snapshot store, and language server.
- `vscode/sattline-vscode/` contains the no-build VS Code client.
- `tests/` contains fixtures and regression coverage.
- `artifacts/analysis/` contains machine-readable outputs from the dev-analysis pipeline.
- `artifacts/audit/` contains machine-readable outputs from the repository audit runner.

---

## Agent Workflow

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
- When creating a new unit, prefer a real copy-based scaffold from `NNEStart`: copy into a new `*Lib` file, keep as many copied modules as practical, add a named unit wrapper module, and have the program file invoke that wrapper.
- Propose a concise plan before broad or multi-file changes.
- Ask for clarification when intended behavior, user-facing semantics, or safety requirements are unclear.
- Prefer incremental, reviewable changes over large rewrites.
- Keep user-facing behavior explicit; avoid hidden side effects or silent mode switches.
- When changing CLI menus or prompts, update `tests/test_app.py` and related interaction coverage in the same change.
- For concurrent agent or chat work, check `.github/coordination/current-work.md` before editing, claim touched files, and release claim when done.
- Respect the claimed-file hook guard under `.github/hooks/`; active claims warn, `ready-for-merge` claims ask for confirmation, and `blocked` claims deny edits until the ledger changes.
- Prefer subsystem-scoped instructions under `.github/instructions/` over growing `AGENTS.md`; keep global guidance stable and push file-specific detail into targeted instruction files.
- When adding AI customizations, optimize for lower context waste: concise frontmatter, keyword-rich descriptions, narrow `applyTo` globs, and machine-readable or scriptable behavior when practical.

---

## Change Boundaries

### Allowed

- analyzers, validators, tests, docs, helper scripts, config or CI wiring
- small refactors required to support the requested work
- low-risk fixes discovered during implementation
- targeted editor or LSP improvements that stay within established architecture

### Avoid

- broad rewrites without clear justification and regression coverage
- duplicate or overlapping tooling when existing repo tooling can be extended
- silent user-facing behavior changes
- deleting major functionality without strong evidence, explanation, and replacement intent
- weakening strict validation semantics just to make fixtures or tests pass

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
- Group findings by severity when relevant.
- Distinguish confirmed issues from suspected or heuristic findings.
- Report assumptions and limitations.
- Report recommended follow-up work.
- Do not expose raw secrets or raw PII in reports.
- When parallel work is active, report claimed files, validation status, and any handoff notes back into `.github/coordination/current-work.md`.
- Use the merge or handoff prompt before final repo verification when multiple workstreams are converging.

---

## Definition Of Done

- Relevant tests are added or updated.
- Appropriate validation commands are run.
- Docs are updated when workflows, behavior, or architecture-facing usage materially change.
- `AGENTS.md` is updated only when stable conventions, workflows, entry points, or critical invariants materially change.
- The LSP is restarted when the change touches the language server, shared semantic core, editor facade, or VS Code client.

---

## SattLint Workflow And Architecture

- Analysis selection is driven by the config list `analyzed_programs_and_libraries`, not by a single `root` entry.
- Reports should stay scoped to explicitly analyzed targets even when dependencies are loaded for resolution.
- Program-target analysis should not let external library module code create findings or usage marks for non-root-origin moduletype definitions.
- The parser core lives under `src/sattline_parser/`; compatibility wrappers remain under `src/sattlint/grammar/`, `src/sattlint/models/ast_model.py`, and `src/sattlint/transformer/sl_transformer.py`.
- Shared editor semantics live under `src/sattlint/core/`; `src/sattlint/editor_api.py` remains a compatibility facade.
- Workspace snapshot loading and caching are centralized in `src/sattlint_lsp/workspace_store.py`.
- The VS Code client is no-build and lives under `vscode/sattline-vscode/`.
- If you materially change these boundaries, update this file and the deeper reference doc.

---

## Critical SattLine And SattLint Invariants

See `.github/instructions/sattline-invariants.instructions.md` (auto-loaded for `src/**` and `tests/**` edits).

Key rules to remember here:
- Grammar requires three header `STRING` lines before `BasePicture`.
- Identifiers are case-insensitive; compare with `.casefold()`.
- Do not weaken `syntax-check` strict semantics.
- Do not collapse workspace fallback behavior into strict single-file validation.
- Restart LSP after touching `src/sattlint_lsp/`, `src/sattlint/core/`, `src/sattlint/editor_api.py`, or `vscode/sattline-vscode/`.

---

## Reference Material

- For extended SattLine examples, AST notes, file maps, and task snippets, see `docs/ai-agent-reference.md`.
- For domain language details, see the `sattline_*_reference.md` files and `SattLineReferenceDocs/`.
- For parser and analyzer behavior, prefer current code and tests over stale prose.

---

*Last updated: 2026-04-24*
