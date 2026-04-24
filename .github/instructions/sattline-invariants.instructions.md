---
description: "Use when changing src/ or tests/ in SattLint. Critical SattLine language invariants, validation rules, variable-analysis gotchas, CLI testing rules, and workspace/LSP boundaries that must not be broken."
name: "SattLine Invariants"
applyTo: ["src/**", "tests/**"]
---
# Critical SattLine And SattLint Invariants

## Language And Parser

- The grammar start rule requires three header `STRING` lines before `BasePicture`; parser tests and minimal fixtures must include them.
- SattLine identifiers are case-insensitive. Compare names with `.casefold()`.
- Extended Latin letters are valid in identifiers.
- Keyword-prefixed identifiers such as `NOTOG217Active` or `IFState` are valid because keywords tokenize only as standalone words.
- `SEQFORK` accepts multiple comma-separated targets.
- `.s` and `.l` are draft-mode files; `.x` and `.z` are official or frozen files.

## Validation Rules To Preserve

- Post-transform validation rejects consecutive `SEQSTEP` nodes with no intervening transition, missing initial steps, duplicate sequence labels, and unknown `SEQFORK` targets.
- `:OLD` and `:NEW` access is only valid on `STATE` variables.
- Scope uniqueness checks reject duplicate local variable names, datatype names, moduletype names, and sibling submodule instance names within the same declaration scope.
- Declaration validation rejects builtin-like datatype typos and incompatible declaration init literals.
- String literals are rejected in module-code function or procedure call arguments; they are allowed in parameter mappings.
- Builtin call validation checks arity, variable-reference requirements for `in var`, `out`, and `inout`, const-write restrictions, and datatype compatibility. `SetStringPos` and `GetStringPos` on `CONST` string variables remain allowed.
- Single-file `sattlint syntax-check` rejects freestanding comments directly inside `ModuleCode` before the first `EQUATIONBLOCK` or `SEQUENCE` or `OPENSEQUENCE`.
- Single-file `syntax-check` remains stricter than workspace loading by design.

## Variable-Analysis Gotchas

- Field-level usage matters. Record access can flow through parameter mappings and nested aliases, not just direct reads or writes.
- Respect parameter mappings when tracing usage and datatype compatibility.
- Whole-record access suppresses partial-field unused findings for that datatype.
- Partial record-leaf reporting uses `UNUSED_DATATYPE_FIELD`, aggregated by datatype across the analyzed target rather than as per-variable noise.
- For analyzed targets outside `program_dir`, root `ModuleTypeDef` moduleparameters are treated as externally open for datatype-field reporting, and dependency `ModuleTypeInstance` mappings can count as external read or write usage.
- Graphics and interact `InVar_` tails can represent real reads. Preserve parser-core tail storage and analyzer coverage for invocation coordinates, `ModuleDef` clipping bounds, and supported graphics or interact properties. Ignore literal numeric or boolean tails rather than treating them as variables.

## CLI And Testing

- The installed `sattlint` console script must call `app.cli()` so `sys.argv[1:]` reaches `app.main(argv)`.
- Calling `app.main()` with no argv still opens the interactive menu.
- If you change CLI menu layout or numbering, keep `tests/test_app.py` in sync.
- Do not rely on the IDE test runner as the first validation path here; use repo-venv pytest commands directly, and treat IDE zero-test collection as expected noise rather than a project signal.
- Prefer targeted test modules first, for example `tests/test_app.py` for CLI and menu work, `tests/test_parser.py` for parser or validation work, and `tests/test_pipeline.py` or `tests/test_repo_audit.py` for devtools artifact changes.
- Use the real fixtures under `tests/fixtures/sample_sattline_files/` when uncertain about syntax or semantics.

## Workspace, Editor, And LSP

- The VS Code client and server only do live LSP analysis for `.s` and `.x` program files; `.l` and `.z` are dependency-name lists for workspace resolution.
- Workspace or editor loading may use dependency context, local snapshots, cached bundles, and proximity-based `.l` or `.z` resolution. CLI and config-driven resolution remain unchanged.
- `ControlLib` is an expected unavailable proprietary dependency in workspace or editor flows and should be reported as unavailable rather than as a normal missing-code error.
- Workspace validation intentionally differs from single-file strict validation for some dependency cases. Do not collapse those two modes together.
- Single-file strict validation still rejects unknown locally resolvable parameter targets and duplicate sibling submodule names; workspace or editor loading may continue past those issues in dependency libraries outside `program_dir`.
- The local LSP parser can report cheap dirty-buffer sequence auto-var issues; preserve that distinction from full workspace semantic analysis.
- After changing `src/sattlint_lsp/`, `src/sattlint/core/`, `src/sattlint/editor_api.py`, or `vscode/sattline-vscode/`, restart the server with the `sattlineLsp.restartServer` command.
