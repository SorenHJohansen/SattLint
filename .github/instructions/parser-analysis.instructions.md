---
description: "Use when changing strict validation, grammar-boundary usage, AST helpers, parser fixtures, or parser tests in SattLint. Covers parser invariants and first validation routing. Parser-core code itself lives in the external sattline-parser package."
name: "Parser Analysis Instructions"
applyTo: ["src/sattlint/parser_api.py", "tests/core/test_parser_surface_contract.py", "tests/fixtures/parser_surface/**", "tests/fixtures/corpus/**"]
---
# Parser Analysis

- The SattLine parser core (grammar, transformer, AST models) ships as the external `sattline-parser` package; change parser-core behavior in that repo, then bump the version pin in `pyproject.toml`.
- All parser imports go through `src/sattlint/parser_api.py`, which re-exports the supported `sattline_parser` doors. Nothing else in `src/` imports the parser package directly; the two files that still import the removed diagnostic severity are the only temporary exceptions, and the import-boundary test enforces the rule.
- Analyzer code reads the parser model through typed fields and the parser `walk` API. Reflective `children` lookup, `__dict__` enumeration, `.data` tree sniffing, and legacy tuple-tag constants are rejected by `tests/analyzers/test_ast_traversal_guard.py`.
- Preserve strict single-file validation versus workspace-mode behavior.
- Do not add silent fallback behavior around parser validation; SattLint keeps its raise-on-first-error policy in `sattlint.validation.policy`.
- Minimal fixtures still need three header `STRING` lines before `BasePicture`.
- Compare identifiers case-insensitively with `.casefold()`.
- `:OLD` and `:NEW` stay valid only on `STATE` variables.
- Choose the first focused validation route from [validation map](../../AGENTS_REFERENCE.md#validation-map); parser work normally stays on the external `sattline check` plus targeted pytest before broader runs.
- If behavior changes, update focused parser or validation tests before wider runs.
