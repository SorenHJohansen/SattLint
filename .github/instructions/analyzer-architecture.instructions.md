---
description: "Use when changing analyzer registry wiring, analyzer entry points, helper ownership, or analyzer architecture tests in SattLint."
name: "Analyzer Architecture"
applyTo: ["src/sattlint/analyzers/**", "tests/test_analyzer_architecture.py", "tests/analyzers/**", "tests/_analyzers_*.py", "tests/test_analyzers_*.py", "tests/test_variables_*.py", "tests/test_reset_contamination*.py", "src/sattlint/app_analysis.py"]
---
# Analyzer Architecture

- Registry-facing analyzer keys are canonical kebab-case. If a legacy underscore spelling must remain selectable during a migration, add a compatibility alias at the registry selection seam instead of reintroducing underscore keys into new specs.
- Public `analyze_*` functions under `src/sattlint/analyzers/` are reserved for registry-backed analyzers. Reporting or debugging helpers should use names such as `report_*` or `debug_*`, and any surviving non-registry `analyze_*` helper must be called out explicitly in the architecture tests.
- Do not mix `from sattlint.analyzers...` imports with sibling `from .` analyzer-package imports in the same analyzer module. Keep analyzer-package imports relative within the package.
- Before adding a new recursive module walk or root-origin comparison helper, search for the analyzer-owned shared seam first and extend that seam unless a focused test-backed exception requires a local implementation.
- Internal analyzer helper modules should be underscore-prefixed and imported with the least noisy pattern that still keeps Pyright passing for the touched slice.
