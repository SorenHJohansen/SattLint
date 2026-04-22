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
- For parser, grammar, transformer, or strict-validation changes, validate with `& ".venv/Scripts/sattlint.exe" syntax-check <target>` before reaching for pytest.
- For Python tests, run pytest through the repo venv with `& ".venv/Scripts/python.exe" -m pytest ...`; do not start with the VS Code test runner in this repo.
- For CLI entry-point validation, prefer the installed repo-venv command path such as `& ".venv/Scripts/sattlint.exe" ...` so behavior matches the console script users run.
- For analyzer or repo-audit work, prefer the existing JSON pipeline in `src/sattlint/devtools/pipeline.py` and its outputs under `artifacts/analysis/`.
- Use `src/sattlint/devtools/repo_audit.py` and `artifacts/audit/` for repository-portability, PII, wiring, architecture, and public-readiness scans.
- Canonical repo audit command: `sattlint-repo-audit --profile full --output-dir artifacts/audit`.
- For fast iteration, prefer `sattlint-repo-audit --profile quick --output-dir artifacts/audit` before a final full pass.
- Open `artifacts/audit/status.json` first; it is the compact machine-readable entry report for audit results.

---

## Repo-Audit And Public-Readiness

- Agents may add or improve checks for hardcoded paths and environment leaks.
- Agents may add or improve checks for secrets and PII.
- Agents may add or improve checks for dead code or unused logic.
- Agents may add or improve checks for feature wiring and feature coverage.
- Agents may add or improve checks for architecture and structure issues.
- Agents may add or improve checks for configuration hygiene.
- Agents may add or improve checks for CLI or TUI UX consistency.
- Agents may add or improve checks for logging and observability.
- Agents may add or improve checks for test coverage gaps.
- Agents may add or improve checks for public-readiness.
- Prefer integrating with existing tooling first.
- Prefer lightweight standard tools over redundant new dependencies.
- If custom audit logic is needed, place it in a maintainable location such as `tools/audit/` or integrate it into `src/sattlint/devtools/repo_audit.py` or the shared devtools pipeline.
- Add tests for custom audit logic where practical.
- Keep audit output actionable and machine-readable when possible.

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

### Language And Parser

- The grammar start rule requires three header `STRING` lines before `BasePicture`; parser tests and minimal fixtures must include them.
- SattLine identifiers are case-insensitive. Compare names with `.casefold()`.
- Extended Latin letters are valid in identifiers.
- Keyword-prefixed identifiers such as `NOTOG217Active` or `IFState` are valid because keywords tokenize only as standalone words.
- `SEQFORK` accepts multiple comma-separated targets.
- `.s` and `.l` are draft-mode files; `.x` and `.z` are official or frozen files.

### Validation Rules To Preserve

- Post-transform validation rejects consecutive `SEQSTEP` nodes with no intervening transition, missing initial steps, duplicate sequence labels, and unknown `SEQFORK` targets.
- `:OLD` and `:NEW` access is only valid on `STATE` variables.
- Scope uniqueness checks reject duplicate local variable names, datatype names, moduletype names, and sibling submodule instance names within the same declaration scope.
- Declaration validation rejects builtin-like datatype typos and incompatible declaration init literals.
- String literals are rejected in module-code function or procedure call arguments; they are allowed in parameter mappings.
- Builtin call validation checks arity, variable-reference requirements for `in var`, `out`, and `inout`, const-write restrictions, and datatype compatibility. `SetStringPos` and `GetStringPos` on `CONST` string variables remain allowed.
- Single-file `sattlint syntax-check` rejects freestanding comments directly inside `ModuleCode` before the first `EQUATIONBLOCK` or `SEQUENCE` or `OPENSEQUENCE`.
- Single-file `syntax-check` remains stricter than workspace loading by design.

### Variable-Analysis Gotchas

- Field-level usage matters. Record access can flow through parameter mappings and nested aliases, not just direct reads or writes.
- Respect parameter mappings when tracing usage and datatype compatibility.
- Whole-record access suppresses partial-field unused findings for that datatype.
- Partial record-leaf reporting uses `UNUSED_DATATYPE_FIELD`, aggregated by datatype across the analyzed target rather than as per-variable noise.
- For analyzed targets outside `program_dir`, root `ModuleTypeDef` moduleparameters are treated as externally open for datatype-field reporting, and dependency `ModuleTypeInstance` mappings can count as external read or write usage.
- Graphics and interact `InVar_` tails can represent real reads. Preserve parser-core tail storage and analyzer coverage for invocation coordinates, `ModuleDef` clipping bounds, and supported graphics or interact properties. Ignore literal numeric or boolean tails rather than treating them as variables.

### CLI And Testing

- The installed `sattlint` console script must call `app.cli()` so `sys.argv[1:]` reaches `app.main(argv)`.
- Calling `app.main()` with no argv still opens the interactive menu.
- If you change CLI menu layout or numbering, keep `tests/test_app.py` in sync.
- Do not rely on the IDE test runner as the first validation path here; use repo-venv pytest commands directly, and treat IDE zero-test collection as expected noise rather than a project signal.
- Prefer targeted test modules first, for example `tests/test_app.py` for CLI and menu work, `tests/test_parser.py` for parser or validation work, and `tests/test_pipeline.py` or `tests/test_repo_audit.py` for devtools artifact changes.
- Use the real fixtures under `tests/fixtures/sample_sattline_files/` when uncertain about syntax or semantics.

### Workspace, Editor, And LSP

- The VS Code client and server only do live LSP analysis for `.s` and `.x` program files; `.l` and `.z` are dependency-name lists for workspace resolution.
- Workspace or editor loading may use dependency context, local snapshots, cached bundles, and proximity-based `.l` or `.z` resolution. CLI and config-driven resolution remain unchanged.
- `ControlLib` is an expected unavailable proprietary dependency in workspace or editor flows and should be reported as unavailable rather than as a normal missing-code error.
- Workspace validation intentionally differs from single-file strict validation for some dependency cases. Do not collapse those two modes together.
- Single-file strict validation still rejects unknown locally resolvable parameter targets and duplicate sibling submodule names; workspace or editor loading may continue past those issues in dependency libraries outside `program_dir`.
- The local LSP parser can report cheap dirty-buffer sequence auto-var issues; preserve that distinction from full workspace semantic analysis.
- After changing `src/sattlint_lsp/`, `src/sattlint/core/`, `src/sattlint/editor_api.py`, or `vscode/sattline-vscode/`, restart the server with the `sattlineLsp.restartServer` command.

---

## Reference Material

- For extended SattLine examples, AST notes, file maps, and task snippets, see `docs/ai-agent-reference.md`.
- For domain language details, see the `sattline_*_reference.md` files and `SattLineReferenceDocs/`.
- For parser and analyzer behavior, prefer current code and tests over stale prose.

---

*Last updated: 2026-04-21*
