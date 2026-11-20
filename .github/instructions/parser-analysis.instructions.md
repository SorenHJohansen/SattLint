---
description: "Use when changing strict validation, grammar-boundary usage, AST helpers, parser fixtures, or parser tests in SattLint. Covers parser invariants and first validation routing. Parser-core code itself lives in the external sattline-parser package."
name: "Parser Analysis Instructions"
applyTo: ["src/sattlint/parser_api.py", "src/sattlint/project/parser_adapter.py", "tests/core/test_parser_import_boundary.py", "tests/core/test_parser_surface_contract.py", "tests/analyzers/test_ast_traversal_guard.py", "tests/fixtures/parser_surface/**", "tests/fixtures/corpus/**"]
---
# Parser Analysis

- The SattLine parser core (grammar, transformer, AST models) ships as the external `sattline-parser` package; change parser-core behavior in that repo, then bump the version pin in `pyproject.toml`.
- All parser imports in `src/` go through `src/sattlint/parser_api.py`, which re-exports the supported `sattline_parser` doors. No other source module imports the parser package directly, and `tests/core/test_parser_import_boundary.py` enforces the rule with no allowlist.
- Analyzer code reads the parser model through typed fields and the parser `walk` API. Reflective `children` lookup, `__dict__` enumeration, `.data` tree sniffing, and legacy tuple-tag constants are rejected by `tests/analyzers/test_ast_traversal_guard.py`.
- Preserve strict single-file validation versus workspace-mode behavior.
- A project load is all or nothing: `SattLineProject.load` returns a complete closure or raises a `ProjectLoadError` subclass. Catch it at every load seam (target iteration, AST refresh, ICF program load, reverse-consumer batch), report the named artifact, and continue. Never build a partial closure.
- Bump every cache version when the parser model changes shape. A renamed enum or a replaced field changes the pickled AST, and a stale entry must be rejected rather than decoded.
- Module layout blocks are singular (`moduledef`, `modulecode`), and a module type definition has no parameter mappings. A mapping belongs to the submodule or module-type instance that invokes it.
- Unit and dependency names are SattLine identifiers of at most 20 characters, so fixture file names must comply or the loader refuses to resolve them.
- Do not add silent fallback behavior around parser validation; SattLint keeps its raise-on-first-error policy in `sattlint.validation.policy`.
- Minimal fixtures still need three header `STRING` lines before `BasePicture`.
- Compare identifiers case-insensitively with `.casefold()`.
- `:OLD` and `:NEW` stay valid only on `STATE` variables.
- Choose the first focused validation route from [validation map](../../AGENTS_REFERENCE.md#validation-map); parser work normally stays on the external `sattline check` plus targeted pytest before broader runs.
- If behavior changes, update focused parser or validation tests before wider runs.
