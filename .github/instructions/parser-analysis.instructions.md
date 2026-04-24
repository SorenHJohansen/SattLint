---
description: "Use when changing parser-core, strict validation, grammar, AST, transformer, parser fixtures, or parser tests in SattLint. Covers parser invariants and first validation routing."
name: "Parser Analysis Instructions"
applyTo: ["src/sattline_parser/**", "src/sattlint/grammar/**", "src/sattlint/models/ast_model.py", "src/sattlint/transformer/**", "tests/test_parser*.py", "tests/fixtures/corpus/**"]
---
# Parser Analysis

- Preserve strict single-file validation versus workspace-mode behavior.
- Do not add silent fallback behavior to `sattlint syntax-check`.
- Minimal fixtures still need three header `STRING` lines before `BasePicture`.
- Compare identifiers case-insensitively with `.casefold()`.
- `:OLD` and `:NEW` stay valid only on `STATE` variables.
- Choose the first focused validation route from [validation map](../skills/validation-routing/references/validation-map.md); parser work normally stays on strict `syntax-check` before broader pytest.
- If behavior changes, update focused parser or validation tests before wider runs.