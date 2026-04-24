---
description: "Use when changing DOCX generation, documentation classification, FS grouping, unit scope selection, or GUI documentation workflows in SattLint. Covers docgen-specific boundaries and tests."
name: "Documentation Generation Instructions"
applyTo: ["src/sattlint/docgenerator/**", "tests/test_docgen.py", "tests/test_gui.py"]
---
# Documentation Generation

- Keep classification config-driven under `documentation.classifications`.
- FS grouping and ordering belong in existing docgen code, not ad hoc call sites.
- Documentation scope is runtime-only and filters unit-root candidates, not arbitrary modules.
- Choose the first focused validation route from [validation map](../skills/validation-routing/references/validation-map.md) for docgen behavior.
- If GUI or app entry points change, include the nearest `tests/test_gui.py` or `tests/test_app.py` slice.